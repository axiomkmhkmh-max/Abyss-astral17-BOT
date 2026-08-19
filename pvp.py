# ============================================================
#  ASTRAL ABYSS — PvP Engine (v3 — "زنده‌تر")
#  لابی + چالش/شرط + نبردِ نوبتیِ همزمان با انرژی، ابیلیتی، لیگ
#  + کومبو، مومنتوم/اوردرایو، دیسپریشن، فینیشینگ‌بلو، دوج، کلش
# ============================================================
import time
import random
from dataclasses import dataclass, field

FIGHT_TIMEOUT   = 30   # مهلتِ پاسخ به چالش
TURN_TIMEOUT    = 20   # مهلتِ هر نوبت
FIGHT_MAX_TURNS = 40   # سقفِ نوبت — جلوگیری از گیرکردنِ ابدی (اگه رسید، مساوی)

# ────────────────────────────────────────────────────────────
# لیگ‌ها
# ────────────────────────────────────────────────────────────
LEAGUES = [
    ("🥉 Bronze V", 0),     ("🥉 Bronze IV", 50),   ("🥉 Bronze III", 100), ("🥉 Bronze II", 150), ("🥉 Bronze I", 200),
    ("🥈 Silver V", 250),   ("🥈 Silver IV", 320),  ("🥈 Silver III", 390), ("🥈 Silver II", 460),  ("🥈 Silver I", 530),
    ("🥇 Gold V", 600),     ("🥇 Gold IV", 700),    ("🥇 Gold III", 800),   ("🥇 Gold II", 900),    ("🥇 Gold I", 1000),
    ("💎 Platinum V", 1100),("💎 Platinum IV",1250),("💎 Platinum III",1400),("💎 Platinum II",1550),("💎 Platinum I",1700),
    ("🔮 Diamond V", 1850), ("🔮 Diamond IV",2050), ("🔮 Diamond III",2250), ("🔮 Diamond II",2450), ("🔮 Diamond I",2650),
    ("👑 Master V", 2850),  ("👑 Master IV", 3100), ("👑 Master III", 3350), ("👑 Master II", 3600), ("👑 Master I", 3850),
    ("🌟 Grandmaster", 4200),
    ("🌌 Legend", 5000),
    ("⚡ Mythic", 6000),
    ("♾️ Eternal", 8000),
]

def league_for_points(points: int) -> str:
    name = LEAGUES[0][0]
    for lname, threshold in LEAGUES:
        if points >= threshold:
            name = lname
        else:
            break
    return name

def next_league_gap(points: int):
    for lname, threshold in LEAGUES:
        if points < threshold:
            return lname, threshold - points
    return None, 0


# ────────────────────────────────────────────────────────────
# جایزه‌ی پایانِ فصل بر اساسِ لیگِ نهایی
# ────────────────────────────────────────────────────────────
SEASON_TIER_REWARDS = [
    ("🥉", 2_000),     # Bronze
    ("🥈", 4_000),     # Silver
    ("🥇", 8_000),     # Gold
    ("💎", 15_000),    # Platinum
    ("🔮", 25_000),    # Diamond
    ("👑", 40_000),    # Master
    ("🌟", 60_000),    # Grandmaster
    ("🌌", 90_000),    # Legend
    ("⚡", 130_000),   # Mythic
    ("♾️", 200_000),   # Eternal
]

def season_reward_for_league(league_name: str) -> int:
    for emoji, reward in SEASON_TIER_REWARDS:
        if league_name.startswith(emoji):
            return reward
    return 0

WIN_POINTS  = 20
LOSE_POINTS = -10
STREAK_BONUS_5  = 0.5
STREAK_BONUS_10 = 1.0

def points_for_win(streak_after: int) -> int:
    base = WIN_POINTS
    if streak_after >= 10:
        base = int(base * (1 + STREAK_BONUS_10))
    elif streak_after >= 5:
        base = int(base * (1 + STREAK_BONUS_5))
    return base


# ────────────────────────────────────────────────────────────
# مکانیک‌های عمق‌دهنده — ثابت‌ها
# ────────────────────────────────────────────────────────────
DODGE_BASE_CHANCE      = 0.08   # شانسِ پایه‌ی جاخالی‌دادن در برابرِ هر ضربه
DESPERATION_HP_PCT     = 0.20   # زیرِ این درصدِ HP خودت وارد «بقای وحشیانه» می‌شی
DESPERATION_DMG_BONUS  = 0.20
DESPERATION_CRIT_BONUS = 0.12
EXECUTE_HP_PCT         = 0.20   # زیرِ این درصدِ HP حریف، ضربه‌هات «فینیشینگ‌بلو» می‌شن
EXECUTE_DMG_BONUS       = 0.30
COMBO_DMG_PER_STACK    = 0.05   # هر پله‌ی کومبو
COMBO_MAX_STACK        = 5
MOMENTUM_MAX           = 100
MOMENTUM_HIT_FLAT      = 8
MOMENTUM_CRIT_FLAT     = 14
MOMENTUM_TAKEN_FLAT    = 5      # گرفتنِ ضربه هم مقداری مومنتوم می‌ده — شانسِ کامبک
OVERDRIVE_DMG_BONUS    = 0.35
CLASH_MOMENTUM_BONUS   = 6

# ─── وضعیت‌های منفی (DOT / کنترل) — لایه‌ی جدید عمق ────────────
BLEED_DMG_PCT   = 0.05   # % از max_hp قربانی، هر نوبت
POISON_DMG_PCT  = 0.04   # % از max_hp قربانی، هر نوبت (استک می‌شه)
BURN_DMG_PCT    = 0.06   # % از max_hp قربانی، هر نوبت (فروکش می‌کنه)
DOT_DEFAULT_TURNS = 2
SILENCE_TURNS   = 1      # ابیلیتی قفل می‌شه، فقط حمله/دفاع
SLOW_TURNS      = 1      # ری‌جنِ انرژی نصف می‌شه
SLOW_ENERGY_REGEN = 12   # به‌جای ۲۵ عادی


# ────────────────────────────────────────────────────────────
# جعبه‌ابزارِ روایت — چند نسخه‌ی متنوع برای هر رویداد که تصادفی
# انتخاب می‌شن تا هر نبرد یه‌کم فرق کنه و حس تکراری نده
# ────────────────────────────────────────────────────────────
FLAVOR = {
    "hit": [
        "⚔️ {actor} ضربه‌ی محکمی زد",
        "⚔️ {actor} با یه حمله‌ی سریع رسید",
        "⚔️ {actor} خطِ دفاعیِ حریف رو شکافت",
        "⚔️ {actor} بی‌رحمانه حمله کرد",
    ],
    "crit": [
        "💥 **ضربه‌ی حیاتی!** {actor} دقیقاً رو نقطه‌ی ضعف زد",
        "💥 **CRITICAL!** {actor} یه شکافِ خونین باز کرد",
        "💥 **ضربه‌ی مرگبار!** {actor} حریف رو تکون داد",
    ],
    "dodge": [
        "💨 {target} در آخرین لحظه جاخالی داد! ضربه به هوا رفت",
        "💨 {target} مثلِ سایه غیب شد — حمله خورد به خالی!",
        "👻 {target} یه قدم عقب رفت و ضربه رو رد کرد",
    ],
    "shield": [
        "🛡️ {actor} یه سپرِ درخشان دورِ خودش کشید",
        "🛡️ {actor} پشتِ یه دیوارِ انرژی سنگر گرفت",
        "🕊️ {actor} حالتِ دفاعی گرفت و نفسی تازه کرد",
    ],
    "stun": [
        "⏳ {target} گیج شد و یه نوبت از دست داد!",
        "⏳ {target} تعادلش رو باخت — نمی‌تونه حرکت کنه!",
        "🌀 {target} تو جاش میخکوب شد!",
    ],
    "stunned_skip": [
        "⏳ {actor} هنوز گیجه و نتونست حرکت کنه!",
        "🌀 {actor} تلاش کرد ولی هنوز رو پاش بند نبود!",
    ],
    "ultimate": [
        "🌌 {actor} قدرتِ نهایی‌شو آزاد کرد!",
        "☄️ {actor} یه ضربه‌ی ویرانگر فرود آورد!",
        "🌠 {actor} تمامِ انرژیشو تو یه ضربه ریخت!",
    ],
    "desperation": [
        "🩸 {actor} با HP کم وارد **بقای وحشیانه** شد — دیگه چیزی برای از دست دادن نداره!",
        "🔥 {actor} با پشت به دیوار، وحشی‌تر از همیشه حمله می‌کنه!",
        "⚠️ {actor} روی لبه‌ی مرگه — و دقیقاً همینه که خطرناکش می‌کنه!",
    ],
    "execute": [
        "🔪 **فینیشینگ‌بلو!** {target} رو تو آستانه‌ی مرگ گیر انداخت!",
        "🩸 **ضربه‌ی خلاصی!** {target} دیگه جایی برای فرار نداره!",
        "☠️ {actor} بو کشیده که {target} داره می‌افته — و بی‌رحمانه فشار آورد!",
    ],
    "combo": [
        "🔗 کومبو x{stack}! {actor} داره ریتم می‌گیره",
        "🔗 x{stack} کومبو پشتِ‌سرهم از {actor}!",
    ],
    "overdrive_ready": [
        "🔥 **مومنتومِ {actor} پر شد — اوردرایو آماده‌ست!**",
    ],
    "overdrive_hit": [
        "⚡🔥 **اوردرایو فعال شد!** {actor} یه ضربه‌ی طوفانی زد!",
        "🌪️ **OVERDRIVE!** {actor} کنترلِ نبرد رو دستِ گرفت!",
    ],
    "clash": [
        "⚔️💥 **CLASH!** هر دو همزمان حمله کردن و ضربه‌ها تو هوا برخورد کردن!",
        "⚔️💥 هر دو با هم حمله کردن — یه لحظه‌ی نفس‌گیر!",
    ],
    "low_hp_warning": [
        "🚨 {name} رو خط قرمزه! یه ضربه‌ی دیگه می‌تونه تمومش کنه!",
    ],
    "bleed_apply": [
        "🩸 {target} زخمی شد و داره خونریزی می‌کنه!",
    ],
    "poison_apply": [
        "☣️ {target} مسموم شد!",
    ],
    "burn_apply": [
        "🔥 {target} آتیش گرفت!",
    ],
    "silence_apply": [
        "🔇 {target} گیج شد — نوبتِ بعد نمی‌تونه از ابیلیتی استفاده کنه!",
    ],
    "slow_apply": [
        "🐌 {target} کند شد — نوبتِ بعد انرژیِ کمتری برمی‌گردونه!",
    ],
    "dot_tick": [
        "🩸 {name} از خونریزی **{dmg}** آسیب دید",
        "☣️ {name} از سم **{dmg}** آسیب دید",
        "🔥 {name} از آتیش **{dmg}** آسیب دید",
    ],
    "silenced_skip_ability": [
        "🔇 {actor} هنوز گیجه و نتونست از ابیلیتی استفاده کنه — به‌جاش حمله‌ی معمولی زد.",
    ],
    "comeback_momentum": [
        "💢 {name} از ضربه خوردن، عزمش جزم‌تر شد!",
    ],
}

def _say(key: str, **kw) -> str:
    return random.choice(FLAVOR[key]).format(**kw)


# ────────────────────────────────────────────────────────────
# تولیدِ ۵ ابیلیتیِ هر جنگجو، از رویِ کاراکترِ خودش
# ────────────────────────────────────────────────────────────
ABILITY_SLOTS = [
    {"kind": "dmg",       "cost": 20,  "dmg_mult": 1.6, "label": "DMG"},
    {"kind": "cc",        "cost": 30,  "dmg_mult": 0.4, "label": "CC",      "stun_turns": 1},
    {"kind": "defense",   "cost": 25,  "dmg_mult": 0.0, "label": "Defense", "shield_pct": 0.30},
    {"kind": "ultimate",  "cost": 100, "dmg_mult": 3.0, "label": "Ultimate","armor_pierce": 0.5},
]

def generate_abilities(char_data: dict) -> tuple[list[dict], dict]:
    powers = list(char_data.get("powers", []) or ["ضربه‌ی ناشناخته"] * 5)
    while len(powers) < 5:
        powers = powers + powers
    abilities = []
    for i, slot in enumerate(ABILITY_SLOTS):
        ab = dict(slot)
        ab["name"] = powers[i % len(powers)]
        abilities.append(ab)
    passive_name = powers[4 % len(powers)]
    passive = {"kind": "passive", "name": passive_name, "label": "Passive"}
    return abilities, passive


# ────────────────────────────────────────────────────────────
# حالتِ هر جنگجو و هر فایت
# ────────────────────────────────────────────────────────────
@dataclass
class FighterState:
    uid: int
    name: str
    character: str
    level: int
    element: str
    max_hp: int
    hp: int
    base_dmg: int
    abilities: list = field(default_factory=list)
    passive: dict = field(default_factory=dict)
    skill_bonuses: dict = field(default_factory=dict)
    set_bonuses: dict = field(default_factory=dict)
    energy: int = 50
    stunned_turns: int = 0
    shield: int = 0
    used_ability_count: dict = field(default_factory=dict)   # {ability_name: count} برای /stats

    # ─── وضعیت‌های منفی (v5) ─────────────────────────────────
    dots: list = field(default_factory=list)   # [{"kind":"bleed/poison/burn","turns":int,"dmg_pct":float}]
    silence_turns: int = 0
    slow_turns: int = 0

    # ─── مکانیک‌های عمق (v3) ─────────────────────────────────
    combo: int = 0                 # پله‌ی کومبوی جاری
    max_combo: int = 0             # بیشترین کومبوی این فایت (برای رکپ)
    momentum: int = 0              # 0..100 — پر شدنش اوردرایو رو آماده می‌کنه
    overdrive_ready: bool = False  # اگه True، ضربه‌ی بعدی اوردرایوِ خودکاره
    overdrive_count: int = 0       # چندبار اوردرایو زده (رکپ)
    dodge_count: int = 0           # چندبار خودش جاخالی داده (رکپ)
    finisher_count: int = 0        # چندبار فینیشینگ‌بلو زده (رکپ)
    clutch_turns: int = 0          # چند نوبت زیرِ ۲۰٪ HP زنده مونده

    # ─── استند (v4) ──────────────────────────────────────────
    stand_category: str = ""       # دسته‌ی استند، برای محاسبه‌ی Affinity


@dataclass
class FightSession:
    fight_id: str
    chat_id: int
    p1: FighterState
    p2: FighterState
    turn: int = 1
    phase: str = "action_select"     # action_select | resolving | ended
    winner_uid: int | None = None
    stake_zen: int = 0
    stake_p1_item: dict | None = None
    stake_p2_item: dict | None = None
    pending: dict = field(default_factory=dict)   # {uid: {"type":..., "ability_idx":...}}
    created_at: float = field(default_factory=time.time)
    turn_deadline: float = field(default_factory=lambda: time.time() + TURN_TIMEOUT)
    total_dmg: dict = field(default_factory=dict)     # {uid: total_dmg_dealt}
    crit_count: dict = field(default_factory=dict)    # {uid: crit_count}
    biggest_hit: dict = field(default_factory=dict)   # {uid: int}
    prompt_msgs: dict = field(default_factory=dict)   # {uid: message_id}
    clash_count: int = 0           # چندبار هر دو همزمان حمله زدن


# ─── حافظه‌ی سراسری (in-memory) ─
active_fights: dict[str, FightSession] = {}
player_in_fight: dict[int, str] = {}         # uid -> fight_id
pending_duels: dict[int, dict] = {}          # challenger_uid -> duel info
last_opponent: dict[int, int] = {}           # uid -> آخرین حریف (برای /revenge)


def get_fight_by_uid(uid: int) -> FightSession | None:
    fid = player_in_fight.get(uid)
    return active_fights.get(fid) if fid else None

def get_self(fight: FightSession, uid: int) -> FighterState:
    return fight.p1 if fight.p1.uid == uid else fight.p2

def get_opponent(fight: FightSession, uid: int) -> FighterState:
    return fight.p2 if fight.p1.uid == uid else fight.p1


def hp_bar(hp: int, max_hp: int, length: int = 10) -> str:
    hp = max(0, hp)
    pct = hp / max_hp if max_hp else 0
    filled = int(pct * length)
    if pct <= 0.20:
        block = "🟥"
    elif pct <= 0.50:
        block = "🟨"
    else:
        block = "🟩"
    return block * filled + "⬜" * (length - filled)


def momentum_bar(value: int, length: int = 5) -> str:
    filled = int((value / MOMENTUM_MAX) * length)
    filled = max(0, min(length, filled))
    return "🔶" * filled + "▫️" * (length - filled)


def build_fighter(uid: int, player: dict, char_data: dict) -> FighterState:
    from skill_tree import get_skill_bonuses
    try:
        from loot_engine import get_set_bonus_stats
        setb = get_set_bonus_stats(player)
    except ImportError:
        setb = {}
    abilities, passive = generate_abilities(char_data)
    skb = get_skill_bonuses(player)
    max_hp = int(player.get("max_hp", 100) * (1 + skb.get("max_hp_pct", 0) + setb.get("hp_pct", 0)))
    try:
        from stand_system import get_stand
        stand_category = get_stand(player.get("character", "")).get("category", "")
    except Exception:
        stand_category = ""

    # ─── باگ‌فیکس: character فقط برای کلاسِ ماجراجو پر می‌شه؛ برای بقیه‌ی
    # کلاس‌ها (جادوگر/تاجر/شفا) char_data خالیه، پس باید base_dmg/element
    # رو از stats.atk بگیریم (دقیقاً مثلِ منطقِ combat.py برای نبردِ عادی)،
    # وگرنه غیرِ‌ماجراجوها همیشه با base_dmg پیش‌فرضِ ثابت وارد پی‌وی‌پی می‌شن.
    is_adventurer = bool(player.get("character"))
    if is_adventurer:
        base_dmg = char_data.get("base_dmg", 10)
        element = char_data.get("element", "—")
    else:
        base_dmg = (player.get("stats") or {}).get("atk", 10)
        element = player.get("class", "—")

    return FighterState(
        uid=uid, name=player.get("name", "Bearer"), character=player.get("character", "?"),
        level=player.get("level", 1), element=element,
        max_hp=max_hp, hp=max_hp,
        base_dmg=base_dmg,
        abilities=abilities, passive=passive,
        skill_bonuses=skb, set_bonuses=setb,
        energy=50,
        stand_category=stand_category,
    )


def fighter_block_text(f: FighterState) -> str:
    ab_lines = "\n".join(f"   {i+1}. {a['name']} ({a['label']}) — {a['cost']} انرژی" for i, a in enumerate(f.abilities))
    return (
        f"**{f.name}** (Lv.{f.level} | {f.character})\n"
        f"   ❤️ {f.hp}/{f.max_hp} | 🌀 {f.element}\n"
        f"   ⚡ Abilityها:\n{ab_lines}\n"
        f"   5. {f.passive['name']} (Passive) — همیشه فعال"
    )


def fight_status_text(fight: FightSession) -> str:
    def _tag(f: FighterState) -> str:
        tags = []
        if f.stunned_turns > 0:
            tags.append("⏳ متوقف")
        if f.shield > 0:
            tags.append(f"🛡️{f.shield}")
        if f.combo >= 2:
            tags.append(f"🔗x{f.combo}")
        if f.overdrive_ready:
            tags.append("🔥اوردرایو‌آماده")
        if f.hp > 0 and f.hp <= f.max_hp * DESPERATION_HP_PCT:
            tags.append("🚨خط‌قرمز")
        dot_icons = {"bleed": "🩸", "poison": "☣️", "burn": "🔥"}
        for d in f.dots:
            tags.append(f"{dot_icons.get(d['kind'], '💢')}x{d['turns']}")
        if f.silence_turns > 0:
            tags.append("🔇بی‌صدا")
        if f.slow_turns > 0:
            tags.append("🐌کند")
        return (" | " + " ".join(tags)) if tags else ""

    return (
        f"📊 **وضعیتِ فعلی — نوبت {fight.turn}:**\n"
        f"🔴 {fight.p1.name}: {hp_bar(fight.p1.hp, fight.p1.max_hp)} {fight.p1.hp}/{fight.p1.max_hp} | "
        f"🔋{fight.p1.energy} | {momentum_bar(fight.p1.momentum)}{_tag(fight.p1)}\n"
        f"🔵 {fight.p2.name}: {hp_bar(fight.p2.hp, fight.p2.max_hp)} {fight.p2.hp}/{fight.p2.max_hp} | "
        f"🔋{fight.p2.energy} | {momentum_bar(fight.p2.momentum)}{_tag(fight.p2)}"
    )


# ────────────────────────────────────────────────────────────
# کمک‌تابع‌های مکانیکِ عمق
# ────────────────────────────────────────────────────────────
def _roll_dodge(target: FighterState) -> bool:
    return random.random() < DODGE_BASE_CHANCE


def _gain_momentum(actor: FighterState, was_crit: bool, logs: list):
    gain = MOMENTUM_CRIT_FLAT if was_crit else MOMENTUM_HIT_FLAT
    actor.momentum = min(MOMENTUM_MAX, actor.momentum + gain)
    if actor.momentum >= MOMENTUM_MAX and not actor.overdrive_ready:
        actor.overdrive_ready = True
        logs.append(_say("overdrive_ready", actor=actor.name))


def _combo_multiplier(actor: FighterState) -> float:
    stacks = min(actor.combo, COMBO_MAX_STACK)
    return 1 + stacks * COMBO_DMG_PER_STACK


def _register_hit(actor: FighterState, logs: list, was_crit: bool):
    actor.combo += 1
    actor.max_combo = max(actor.max_combo, actor.combo)
    if actor.combo >= 2:
        logs.append(_say("combo", actor=actor.name, stack=actor.combo))
    _gain_momentum(actor, was_crit, logs)


def _break_combo(actor: FighterState):
    actor.combo = 0


def _compute_dmg_modifiers(actor: FighterState, target: FighterState) -> tuple[float, bool, bool]:
    """برمی‌گردونه: (ضریبِ کلیِ دمیج از مکانیک‌های عمق, در حالتِ دیسپریشنه؟, داره فینیشینگ‌بلو می‌زنه؟)"""
    mult = 1.0
    desperate = actor.hp > 0 and actor.hp <= actor.max_hp * DESPERATION_HP_PCT
    executing = target.hp > 0 and target.hp <= target.max_hp * EXECUTE_HP_PCT
    if desperate:
        mult *= (1 + DESPERATION_DMG_BONUS)
    if executing:
        mult *= (1 + EXECUTE_DMG_BONUS)
    mult *= _combo_multiplier(actor)
    try:
        from stand_system import affinity_multiplier
        if actor.stand_category and target.stand_category:
            mult *= affinity_multiplier(actor.stand_category, target.stand_category)
    except Exception:
        pass
    return mult, desperate, executing


def fighter_block_text_ext(f: FighterState) -> str:
    return fighter_block_text(f)


# ────────────────────────────────────────────────────────────
# حلِ یه نوبت — هر دو اکشن رو همزمان اعمال می‌کنه
# ────────────────────────────────────────────────────────────
def _apply_action(fight: FightSession, actor: FighterState, target: FighterState, action: dict) -> list[str]:
    logs = []
    kind = action.get("type", "attack")

    if actor.stunned_turns > 0:
        actor.stunned_turns -= 1
        _break_combo(actor)
        logs.append(_say("stunned_skip", actor=actor.name))
        return logs

    if kind == "attack":
        if _roll_dodge(target):
            target.dodge_count += 1
            _break_combo(actor)
            logs.append(_say("dodge", target=target.name))
            return logs

        dmg = actor.base_dmg + actor.level * 2 + random.randint(0, actor.level)
        dmg = int(dmg * (1 + actor.skill_bonuses.get("dmg_pct", 0) + actor.set_bonuses.get("dmg_pct", 0)))
        crit_chance = 0.10 + actor.skill_bonuses.get("crit_chance", 0) + actor.set_bonuses.get("crit_pct", 0)
        desperate_now = actor.hp > 0 and actor.hp <= actor.max_hp * DESPERATION_HP_PCT
        if desperate_now:
            crit_chance += DESPERATION_CRIT_BONUS
        is_crit = random.random() < crit_chance
        if is_crit:
            dmg = int(dmg * 2)
            fight.crit_count[actor.uid] = fight.crit_count.get(actor.uid, 0) + 1

        mods, desperate, executing = _compute_dmg_modifiers(actor, target)
        overdrive_now = actor.overdrive_ready
        if overdrive_now:
            mods *= (1 + OVERDRIVE_DMG_BONUS)
        dmg = int(dmg * mods)

        head = _say("crit", actor=actor.name) if is_crit else _say("hit", actor=actor.name)
        logs.append(f"{head} — **{dmg}** آسیب")
        if desperate:
            logs.append(_say("desperation", actor=actor.name))
        if executing:
            logs.append(_say("execute", actor=actor.name, target=target.name))
            actor.finisher_count += 1
        if overdrive_now:
            logs.append(_say("overdrive_hit", actor=actor.name))
            actor.overdrive_ready = False
            actor.overdrive_count += 1
            actor.momentum = 0

        _deal_damage(fight, actor, target, dmg)
        _register_hit(actor, logs, is_crit)
        # ─── کریتِ حمله‌ی معمولی، ۲۵٪ شانس داره حریف رو کند کنه (ری‌جنِ
        # انرژیِ نوبتِ بعدش نصف می‌شه) — یه ریواردِ اضافه برای کریت ─────
        if is_crit and target.hp > 0 and random.random() < 0.25:
            target.slow_turns = max(target.slow_turns, SLOW_TURNS)
            logs.append(_say("slow_apply", target=target.name))

    elif kind == "defend":
        _break_combo(actor)
        shield = int(actor.max_hp * 0.15)
        actor.shield += shield
        logs.append(f"{_say('shield', actor=actor.name)} (+{shield} سپر)")

    elif kind == "ability":
        idx = action.get("ability_idx", 0)
        ab = actor.abilities[idx]
        if actor.silence_turns > 0:
            actor.silence_turns -= 1
            logs.append(_say("silenced_skip_ability", actor=actor.name))
            if _roll_dodge(target):
                target.dodge_count += 1
                _break_combo(actor)
                logs.append(_say("dodge", target=target.name))
            else:
                dmg = actor.base_dmg + actor.level * 2
                mods, desperate, executing = _compute_dmg_modifiers(actor, target)
                dmg = int(dmg * mods)
                _deal_damage(fight, actor, target, dmg)
                logs.append(f"⚔️ {actor.name}: **{dmg}** آسیب")
                _register_hit(actor, logs, False)
        elif actor.energy < ab["cost"]:
            logs.append(f"❌ {actor.name} انرژیِ کافی برای **{ab['name']}** نداشت — به‌جاش حمله‌ی معمولی زد.")
            if _roll_dodge(target):
                target.dodge_count += 1
                _break_combo(actor)
                logs.append(_say("dodge", target=target.name))
            else:
                dmg = actor.base_dmg + actor.level * 2
                mods, desperate, executing = _compute_dmg_modifiers(actor, target)
                dmg = int(dmg * mods)
                _deal_damage(fight, actor, target, dmg)
                logs.append(f"⚔️ {actor.name}: **{dmg}** آسیب")
                _register_hit(actor, logs, False)
        else:
            actor.energy -= ab["cost"]
            actor.used_ability_count[ab["name"]] = actor.used_ability_count.get(ab["name"], 0) + 1

            if ab["kind"] == "dmg":
                if _roll_dodge(target):
                    target.dodge_count += 1
                    _break_combo(actor)
                    logs.append(_say("dodge", target=target.name))
                else:
                    dmg = int((actor.base_dmg + actor.level * 3) * ab["dmg_mult"])
                    dmg = int(dmg * (1 + actor.skill_bonuses.get("dmg_pct", 0)))
                    is_crit = random.random() < (0.15 + actor.skill_bonuses.get("crit_chance", 0))
                    mods, desperate, executing = _compute_dmg_modifiers(actor, target)
                    overdrive_now = actor.overdrive_ready
                    if is_crit:
                        dmg = int(dmg * 1.8)
                        fight.crit_count[actor.uid] = fight.crit_count.get(actor.uid, 0) + 1
                        logs.append(f"🌟 **ABILITY CRIT!**")
                    if overdrive_now:
                        mods *= (1 + OVERDRIVE_DMG_BONUS)
                    dmg = int(dmg * mods)
                    logs.append(f"🗡️ {actor.name}: **{ab['name']}** — **{dmg}** آسیب")
                    if desperate:
                        logs.append(_say("desperation", actor=actor.name))
                    if executing:
                        logs.append(_say("execute", actor=actor.name, target=target.name))
                        actor.finisher_count += 1
                    if overdrive_now:
                        logs.append(_say("overdrive_hit", actor=actor.name))
                        actor.overdrive_ready = False
                        actor.overdrive_count += 1
                        actor.momentum = 0
                    _deal_damage(fight, actor, target, dmg)
                    _register_hit(actor, logs, is_crit)

            elif ab["kind"] == "cc":
                dmg = int((actor.base_dmg + actor.level * 2) * ab["dmg_mult"])
                mods, desperate, executing = _compute_dmg_modifiers(actor, target)
                dmg = int(dmg * mods)
                target.stunned_turns = max(target.stunned_turns, ab.get("stun_turns", 1))
                logs.append(f"{_say('stun', target=target.name)} ({dmg} آسیب — **{ab['name']}**)")
                _deal_damage(fight, actor, target, dmg)
                _register_hit(actor, logs, False)
                # ─── علاوه‌بر استان، یه خونریزیِ سبک هم می‌ذاره — CC حالا
                # هم کنترل می‌کنه هم فشارِ مداوم وارد می‌کنه ───────────────
                if target.hp > 0:
                    _apply_dot(target, "bleed", BLEED_DMG_PCT, DOT_DEFAULT_TURNS, logs)

            elif ab["kind"] == "defense":
                _break_combo(actor)
                shield = int(actor.max_hp * ab.get("shield_pct", 0.3))
                actor.shield += shield
                logs.append(f"🕊️ {actor.name}: **{ab['name']}** — +{shield} سپر")

            elif ab["kind"] == "ultimate":
                dmg = int((actor.base_dmg + actor.level * 4) * ab["dmg_mult"])
                dmg = int(dmg * (1 + actor.skill_bonuses.get("dmg_pct", 0)))
                pierce = ab.get("armor_pierce", 0.5)
                ignored_shield = int(target.shield * pierce)
                effective_shield = target.shield - ignored_shield
                is_crit = random.random() < (0.20 + actor.skill_bonuses.get("crit_chance", 0))
                mods, desperate, executing = _compute_dmg_modifiers(actor, target)
                overdrive_now = actor.overdrive_ready
                if is_crit:
                    dmg = int(dmg * 2)
                    fight.crit_count[actor.uid] = fight.crit_count.get(actor.uid, 0) + 1
                    logs.append(f"☄️ **ULTIMATE CRITICAL!**")
                if overdrive_now:
                    mods *= (1 + OVERDRIVE_DMG_BONUS)
                dmg = int(dmg * mods)
                logs.append(f"{_say('ultimate', actor=actor.name)} — **{ab['name']}**: **{dmg}** آسیب!")
                if desperate:
                    logs.append(_say("desperation", actor=actor.name))
                if executing:
                    logs.append(_say("execute", actor=actor.name, target=target.name))
                    actor.finisher_count += 1
                if overdrive_now:
                    logs.append(_say("overdrive_hit", actor=actor.name))
                    actor.overdrive_ready = False
                    actor.overdrive_count += 1
                    actor.momentum = 0
                _deal_damage(fight, actor, target, dmg, shield_override=effective_shield)
                _register_hit(actor, logs, is_crit)
                # ─── اولتیمیت اونقدر ویرانگره که حریف رو یه نوبت گیج می‌کنه:
                # نمی‌تونه ابیلیتی بزنه (فقط حمله/دفاع) ─────────────────
                if target.hp > 0:
                    target.silence_turns = max(target.silence_turns, SILENCE_TURNS)
                    logs.append(_say("silence_apply", target=target.name))
                    # داغِ آتیشِ اولتیمیت هم روش می‌مونه
                    _apply_dot(target, "burn", BURN_DMG_PCT, DOT_DEFAULT_TURNS, logs)

    return logs


def _deal_damage(fight: FightSession, actor: FighterState, target: FighterState, dmg: int, shield_override: int | None = None):
    shield = target.shield if shield_override is None else shield_override
    absorbed = min(shield, dmg)
    target.shield = max(0, target.shield - absorbed)
    real_dmg = dmg - absorbed
    target.hp = max(0, target.hp - real_dmg)
    fight.total_dmg[actor.uid] = fight.total_dmg.get(actor.uid, 0) + real_dmg
    fight.biggest_hit[actor.uid] = max(fight.biggest_hit.get(actor.uid, 0), real_dmg)
    # ─── کامبک‌مکانیک: گرفتنِ ضربه‌ی واقعی هم کمی مومنتوم می‌ده ───
    if real_dmg > 0 and target.hp > 0:
        target.momentum = min(MOMENTUM_MAX, target.momentum + MOMENTUM_TAKEN_FLAT)
        if target.momentum >= MOMENTUM_MAX and not target.overdrive_ready:
            target.overdrive_ready = True


def _apply_dot(target: FighterState, kind: str, dmg_pct: float, turns: int, logs: list):
    """یه وضعیتِ منفیِ آسیب‌تدریجی (خونریزی/سم/آتیش) رو روی هدف می‌ذاره."""
    for d in target.dots:
        if d["kind"] == kind:
            d["turns"] = max(d["turns"], turns)
            d["dmg_pct"] = max(d["dmg_pct"], dmg_pct)
            return
    target.dots.append({"kind": kind, "turns": turns, "dmg_pct": dmg_pct})
    logs.append(_say(f"{kind}_apply", target=target.name))


def _tick_dots(fight: FightSession, fighter: FighterState, logs: list):
    """ابتدای هر نوبت، همه‌ی DOTهای فعالِ این جنگجو رو اعمال می‌کنه."""
    if fighter.hp <= 0 or not fighter.dots:
        return
    still_active = []
    for d in fighter.dots:
        if fighter.hp <= 0:
            still_active.append(d)
            continue
        dmg = max(1, int(fighter.max_hp * d["dmg_pct"]))
        fighter.hp = max(0, fighter.hp - dmg)
        logs.append(_say("dot_tick", name=fighter.name, dmg=dmg))
        d["turns"] -= 1
        if d["turns"] > 0:
            still_active.append(d)
    fighter.dots = still_active


def resolve_turn(fight: FightSession) -> list[str]:
    """هر دو اکشنِ pending رو همزمان اعمال می‌کنه و لاگ برمی‌گردونه."""
    logs = [f"🔥 **نوبت {fight.turn} — نتیجه:**\n"]

    a1 = fight.pending.get(fight.p1.uid, {"type": "attack"})
    a2 = fight.pending.get(fight.p2.uid, {"type": "attack"})

    # ─── فازِ ابتدای نوبت: تیکِ DOTها (خونریزی/سم/آتیش) ────────────
    for f in (fight.p1, fight.p2):
        _tick_dots(fight, f, logs)

    if fight.p1.hp <= 0 or fight.p2.hp <= 0:
        fight.pending = {}
        return logs

    if a1.get("type") == "attack" and a2.get("type") == "attack":
        fight.clash_count += 1
        logs.append(_say("clash"))
        for f in (fight.p1, fight.p2):
            f.momentum = min(MOMENTUM_MAX, f.momentum + CLASH_MOMENTUM_BONUS)

    for f in (fight.p1, fight.p2):
        regen = SLOW_ENERGY_REGEN if f.slow_turns > 0 else 25
        f.energy = min(100, f.energy + regen)
        if f.slow_turns > 0:
            f.slow_turns -= 1

    if fight.p1.hp > 0:
        logs += _apply_action(fight, fight.p1, fight.p2, a1)
    if fight.p2.hp > 0:
        logs += _apply_action(fight, fight.p2, fight.p1, a2)

    for f, other in ((fight.p1, fight.p2), (fight.p2, fight.p1)):
        if 0 < f.hp <= f.max_hp * DESPERATION_HP_PCT:
            f.clutch_turns += 1
            if f.clutch_turns == 1:
                logs.append(_say("low_hp_warning", name=f.name))

    fight.pending = {}
    fight.turn += 1
    fight.turn_deadline = time.time() + TURN_TIMEOUT
    return logs


# ────────────────────────────────────────────────────────────
# عنوانِ پایانِ نبرد — بر اساسِ آمار، یه لقبِ دراماتیک می‌سازه
# ────────────────────────────────────────────────────────────
def battle_epithet(f: FighterState, fight: FightSession) -> str | None:
    """یه لقبِ افتخاری برای کارنامه‌ی این جنگجو تو این نبردِ خاص، اگه شایسته باشه."""
    crits = fight.crit_count.get(f.uid, 0)
    if f.overdrive_count >= 2:
        return "⚡ طوفانِ اوردرایو"
    if f.finisher_count >= 2:
        return "🔪 جلادِ آرنا"
    if f.dodge_count >= 3:
        return "👻 روحِ فراری"
    if f.max_combo >= 4:
        return "🔗 استادِ ریتم"
    if f.clutch_turns >= 3:
        return "🩸 بازمانده‌ی خط‌قرمز"
    if crits >= 4:
        return "💥 بارانِ کریتیکال"
    return None


def battle_headline(fight: FightSession, winner: FighterState) -> str:
    """یه تیترِ دراماتیک برای کلِ نبرد، بر اساسِ روندِ نبرد."""
    turns = fight.turn - 1
    if turns <= 3:
        return "⚡ **نابودیِ برق‌آسا!** — نبرد تو چشم‌به‌هم‌زدنی تموم شد"
    if winner.hp <= winner.max_hp * 0.15:
        return "🩸 **برد در آخرین نفس!** — به‌سختی زنده موند و برد"
    if fight.clash_count >= 3:
        return "⚔️ **نبردِ تن‌به‌تن!** — پر از لحظه‌های هم‌زمانِ نفس‌گیر"
    if turns >= FIGHT_MAX_TURNS - 5:
        return "🩶 **نبردِ فرسایشی!** — تا آخرین نوبتِ ممکن کشیده شد"
    return "🔥 **یه نبردِ به‌یادموندنی!**"
