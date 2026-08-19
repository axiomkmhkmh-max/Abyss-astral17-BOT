# ============================================================
#  ASTRAL ABYSS RPG — Guild System v2
#  گیلدها | رتبه‌بندی با آزمون واقعی | کوئست‌های چندمرحله‌ای با روایت و انتخاب
#  | اکشن یکتای هر گیلد (ریسک/پاداش) | کارت شناسایی گیلد
# ============================================================
import random, time, uuid

# ─── Guilds ──────────────────────────────────────────────────
GUILDS = {
    "adventurers": {
        "name": "گیلد ماجراجویان", "emoji": "⚔️",
        "desc": "شکار هیولا، محافظت، اکتشاف — قلب تپنده‌ی هر ماجراجو.",
        "focus": "combat",
        "quest_weights": {"kill": 70, "gather": 30},
        "action": {"name": "🗡 دوئل صحرایی", "emoji": "🗡", "cooldown": 1200,
                   "desc": "یه هیولای تصادفی رو تنها به چالش بکش."},
        "s_title": "افسانه‌ی ماجراجویان",
        "npc": "پذیرش‌گر گیلد ماجراجویان",
    },
    "merchants": {
        "name": "گیلد تاجران", "emoji": "💰",
        "desc": "خرید و فروش، قراردادهای تجاری، کنترل بازار.",
        "focus": "trade",
        "quest_weights": {"zen": 60, "gather": 40},
        "action": {"name": "📈 معامله پرریسک", "emoji": "📈", "cooldown": 1500,
                   "desc": "بخشی از سرمایه‌ت رو روی یه معامله شرط ببند."},
        "s_title": "ارباب تجارت آبیس",
        "npc": "دلال ارشد گیلد تاجران",
    },
    "blacksmiths": {
        "name": "گیلد آهنگران", "emoji": "🔨",
        "desc": "ساخت و ارتقای تجهیزات، فورج کاتانا، کنترل کیفیت.",
        "focus": "forge",
        "quest_weights": {"gather": 80, "kill": 20},
        "action": {"name": "🔥 سفارش فورج", "emoji": "🔥", "cooldown": 1800,
                   "desc": "دو آیتم از کوله‌پشتیت رو ذوب کن و یه سفارش بساز."},
        "s_title": "استاد بزرگ آهنگری",
        "npc": "سرکارگر گیلد آهنگران",
    },
    "alchemists": {
        "name": "گیلد کیمیاگران", "emoji": "🧪",
        "desc": "ساخت معجون، درمان، آزمایش مواد و ترکیبات.",
        "focus": "heal",
        "quest_weights": {"gather": 80, "zen": 20},
        "action": {"name": "🧪 دم‌کردن معجون", "emoji": "🧪", "cooldown": 1500,
                   "desc": "یه آیتم رو قربانی کن تا یه معجون شفابخش بسازی."},
        "s_title": "کیمیاگر اعظم",
        "npc": "استاد آزمایشگاه کیمیاگران",
    },
    "mages": {
        "name": "گیلد جادوگران", "emoji": "🔮",
        "desc": "پژوهش جادویی، ثبت طلسم، تقویت قدرت مهارتی.",
        "focus": "skill",
        "quest_weights": {"level": 40, "gather": 40, "kill": 20},
        "action": {"name": "🔮 پژوهش طلسم", "emoji": "🔮", "cooldown": 2100,
                   "desc": "بخشی از تجربه‌ت رو صرف کشف یه طلسم جدید کن."},
        "s_title": "آرشیماگ آبیس",
        "npc": "کتابدار گیلد جادوگران",
    },
    "hunters": {
        "name": "گیلد شکارچیان", "emoji": "🏹",
        "desc": "شکار موجودات وحشی و جمع‌آوری مواد کمیاب.",
        "focus": "loot",
        "quest_weights": {"kill": 70, "gather": 30},
        "action": {"name": "🏹 کمین شکار", "emoji": "🏹", "cooldown": 1200,
                   "desc": "کمین کن و منتظر یه شکار کمیاب باش."},
        "s_title": "شکارچی سایه‌ها",
        "npc": "رئیس شکارچیان",
    },
}
GUILD_IDS = list(GUILDS.keys())

# ─── Ranks ───────────────────────────────────────────────────
RANKS = ["G", "F", "E", "D", "C", "B", "A", "S"]
RANK_NAMES_FA = {
    "G": "تازه‌کار", "F": "مبتدی", "E": "معمولی", "D": "باتجربه",
    "C": "حرفه‌ای", "B": "نخبه", "A": "مشهور", "S": "افسانه‌ای",
}
RANK_UP_CONTRIB = {
    "G": 0, "F": 150, "E": 400, "D": 900,
    "C": 1800, "B": 3500, "A": 7000, "S": 14000,
}
RANK_BONUS_PCT = {"G": 0, "F": 2, "E": 4, "D": 7, "C": 11, "B": 16, "A": 22, "S": 30}
TRIAL_COOLDOWN_BASE = 1800  # ۳۰ دقیقه، با هر شکست بیشتر می‌شه

TRIAL_NARRATIVE = {
    "F": "پذیرش گیلد ازت می‌خواد ثابت کنی دیگه تازه‌کار نیستی. یه آزمون ساده در انتظارته.",
    "E": "برای رتبه‌ی E باید در برابر یه تهدید واقعی دووم بیاری.",
    "D": "آزمون رتبه D سخت‌تره — گیلد می‌خواد مطمئن بشه از پس مأموریت‌های خطرناک برمیای.",
    "C": "فقط حرفه‌ای‌ها رتبه C می‌گیرن. این آزمون بی‌رحمه.",
    "B": "رتبه B یعنی نخبه بودن. خیلی‌ها تو همین مرحله شکست می‌خورن.",
    "A": "رتبه A افسانه‌ایه. گیلد ارشد شخصاً ناظر آزمونته.",
    "S": "آزمون رتبه S — فقط یک نفر از هر نسل بهش می‌رسه. آماده‌ای؟",
}

def get_rank(contribution: int) -> str:
    """صرفاً برای نمایش 'رتبه‌ی شایسته' استفاده می‌شه؛ رتبه‌ی رسمی از gdata['rank'] میاد."""
    rank = "G"
    for r in RANKS:
        if contribution >= RANK_UP_CONTRIB[r]:
            rank = r
    return rank


def bar(pct: float, length: int = 10) -> str:
    filled = int(max(0.0, min(1.0, pct)) * length)
    return "🟦" * filled + "⬛" * (length - filled)


# ─── Player Guild Data ───────────────────────────────────────
def ensure_guild_data(player: dict) -> dict:
    if "guilds" not in player or not isinstance(player.get("guilds"), dict):
        player["guilds"] = {}
    return player


def is_member(player: dict, guild_id: str) -> bool:
    return guild_id in player.get("guilds", {})


def join_guild(player: dict, guild_id: str) -> tuple[bool, str]:
    if guild_id not in GUILDS:
        return False, "❌ گیلد نامعتبر."
    ensure_guild_data(player)
    if guild_id in player["guilds"]:
        return False, "⚠️ قبلاً عضو این گیلد شدی!"
    player["guilds"][guild_id] = {
        "rank": "G",
        "contribution": 0,
        "quests_done": 0,
        "active_quest": None,
        "joined_at": time.time(),
        "trial_cooldown": 0,
        "trial_fails": 0,
        "last_action": 0,
        "quest_cooldown": 0,
    }
    g = GUILDS[guild_id]
    return True, (
        f"✅ به {g['emoji']} **{g['name']}** خوش اومدی!\n\n"
        f"🗣 *{g['npc']}*: «کارت عضویتت صادر شد. رتبه‌ت G ـه — تازه‌کار.\n"
        f"با کوئست‌های تابلو امتیاز جمع کن، بعد وارد آزمون ارتقا شو.»"
    )


def leave_guild(player: dict, guild_id: str) -> tuple[bool, str]:
    ensure_guild_data(player)
    if guild_id not in player["guilds"]:
        return False, "❌ عضو این گیلد نیستی."
    del player["guilds"][guild_id]
    return True, f"👋 از {GUILDS[guild_id]['name']} خارج شدی. کارت عضویتت باطل شد."


def get_guild_bonus_pct(player: dict, guild_id: str) -> int:
    g = player.get("guilds", {}).get(guild_id)
    if not g:
        return 0
    base = RANK_BONUS_PCT.get(g.get("rank", "G"), 0)
    return base + get_rally_bonus_pct(guild_id) + get_infra_bonus_pct(guild_id)


# ─── Cross-system bonus helpers (آماده برای هوک شدن به بقیه‌ی فایل‌ها) ─
def get_combat_bonus_pct(player: dict) -> int:
    return get_guild_bonus_pct(player, "adventurers") + get_guild_bonus_pct(player, "hunters") // 2

def get_trade_discount_pct(player: dict) -> int:
    return get_guild_bonus_pct(player, "merchants")

def get_forge_bonus_pct(player: dict) -> int:
    return get_guild_bonus_pct(player, "blacksmiths")

def get_heal_bonus_pct(player: dict) -> int:
    return get_guild_bonus_pct(player, "alchemists")

def get_loot_bonus_pct(player: dict) -> int:
    return get_guild_bonus_pct(player, "hunters")


# ============================================================
#  RANK-UP TRIALS
# ============================================================
def trial_next_rank(gdata: dict):
    idx = RANKS.index(gdata.get("rank", "G"))
    if idx == len(RANKS) - 1:
        return None
    return RANKS[idx + 1]


def trial_ready(player: dict, guild_id: str) -> tuple[bool, str]:
    """آیا الان می‌تونه وارد آزمون ارتقا بشه؟ (رتبه بعدی، دلیل رد اگه نمیشه)"""
    gdata = player.get("guilds", {}).get(guild_id)
    if not gdata:
        return False, "عضو نیستی"
    next_rank = trial_next_rank(gdata)
    if not next_rank:
        return False, "بالاترین رتبه رو داری"
    if gdata.get("contribution", 0) < RANK_UP_CONTRIB[next_rank]:
        need = RANK_UP_CONTRIB[next_rank] - gdata.get("contribution", 0)
        return False, f"هنوز {need:,} امتیاز دیگه لازم داری"
    if time.time() < gdata.get("trial_cooldown", 0):
        remain = int(gdata["trial_cooldown"] - time.time())
        return False, f"آزمون تو کول‌داونه ({remain//60} دقیقه دیگه)"
    return True, "آماده"


def _trial_chance(player: dict, next_rank: str) -> int:
    tier = RANKS.index(next_rank)
    base = 60 - tier * 5
    lvl_bonus = min(20, player.get("level", 1) // 5)
    katana_bonus = min(15, player.get("katana_level", 1) // 4)
    equip_bonus = sum(1 for v in player.get("equipped", {}).values() if v) * 2
    chance = base + lvl_bonus + katana_bonus + equip_bonus
    return max(8, min(92, chance))


def trial_preview(player: dict, guild_id: str) -> dict:
    gdata = player["guilds"][guild_id]
    next_rank = trial_next_rank(gdata)
    chance = _trial_chance(player, next_rank)
    return {
        "next_rank": next_rank,
        "chance": chance,
        "narrative": TRIAL_NARRATIVE.get(next_rank, "آزمون بزرگی در انتظارته."),
    }


def attempt_trial(player: dict, guild_id: str) -> tuple[bool, str]:
    ok, reason = trial_ready(player, guild_id)
    if not ok:
        return False, f"❌ {reason}."

    gdata = player["guilds"][guild_id]
    g = GUILDS[guild_id]
    next_rank = trial_next_rank(gdata)
    chance = _trial_chance(player, next_rank)
    roll = random.randint(1, 100)
    success = roll <= chance

    if success:
        gdata["rank"] = next_rank
        gdata["trial_fails"] = 0
        gdata["trial_cooldown"] = 0
        bonus_zen = 500 * (RANKS.index(next_rank) + 1)
        bonus_xp = 300 * (RANKS.index(next_rank) + 1)
        player["zen"] = player.get("zen", 0) + bonus_zen
        player["xp"] = player.get("xp", 0) + bonus_xp
        title_msg = ""
        if next_rank == "S":
            title = g["s_title"]
            titles = player.setdefault("titles_unlocked", [])
            if title not in titles:
                titles.append(title)
            title_msg = f"\n\n👑 **عنوان جدید باز شد: {title}**"
        return True, (
            f"🎉 **قبول شدی!** (تاس: {roll} ≤ شانس {chance}%)\n\n"
            f"🎖 رتبه‌ی جدید: **{next_rank}** — {RANK_NAMES_FA[next_rank]}\n"
            f"💰 +{bonus_zen:,} Zen | ✨ +{bonus_xp:,} XP{title_msg}"
        )
    else:
        gdata["trial_fails"] = gdata.get("trial_fails", 0) + 1
        cooldown = TRIAL_COOLDOWN_BASE * (1 + gdata["trial_fails"] * 0.5)
        gdata["trial_cooldown"] = time.time() + cooldown
        consolation = 80 * (RANKS.index(next_rank) + 1)
        player["zen"] = player.get("zen", 0) + consolation
        return False, (
            f"💥 **شکست خوردی!** (تاس: {roll} > شانس {chance}%)\n\n"
            f"گیلد بهت {consolation:,} Zen به‌عنوان دلداری داد.\n"
            f"⏳ می‌تونی {int(cooldown//60)} دقیقه‌ی دیگه دوباره امتحان کنی.\n"
            f"💡 با رفتن به مأموریت‌های بیشتر یا خرید تجهیزات، شانست بالاتر می‌ره."
        )


# ============================================================
#  MULTI-STAGE NARRATIVE QUESTS
# ============================================================
RARITY_ORDER = ["common", "uncommon", "rare", "epic", "mythic", "legendary"]

def _tier_index(rank: str) -> int:
    return RANKS.index(rank)

def _gather_min_rarity(tier: int) -> str:
    return RARITY_ORDER[min(tier // 2, 3)]

CHOICE_FLAVOR = [
    {
        "narrative": "تو مسیر، دو راه پیش رومه: یه میان‌بر خطرناک از دل غار، یا مسیر امن و طولانی.",
        "options": [
            {"label": "🕳 میان‌بر خطرناک (ریسک بیشتر، پاداش بیشتر)", "risk_mult": 1.5, "target_mult": 1.2,
             "result": "از دل تاریکی گذشتی. زخمی شدی ولی سریع‌تر رسیدی."},
            {"label": "🛤 مسیر امن (استاندارد)", "risk_mult": 1.0, "target_mult": 1.0,
             "result": "بی‌دردسر و آروم به مقصد رسیدی."},
        ],
    },
    {
        "narrative": "یه بازرگان دوره‌گرد کمکت رو می‌خواد؛ کمکش می‌کنی یا رد می‌شی؟",
        "options": [
            {"label": "🤝 کمک کن (کندتر، امتیاز اضافه)", "risk_mult": 1.0, "target_mult": 1.15, "bonus_contrib": 15,
             "result": "بازرگان ازت تشکر کرد و یه خبر مفید بهت داد."},
            {"label": "🚶 رد شو (سریع‌تر)", "risk_mult": 1.0, "target_mult": 0.85, "bonus_contrib": 0,
             "result": "به‌سرعت به راهت ادامه دادی."},
        ],
    },
    {
        "narrative": "نشونه‌هایی از یه کمین پیش‌رو می‌بینی. با احتیاط پیش بری یا بی‌پروا؟",
        "options": [
            {"label": "⚡ بی‌پروا حمله کن (ریسک بالا، جایزه بالا)", "risk_mult": 1.4, "target_mult": 1.0,
             "result": "با تمام قدرت وارد شدی — خطرناک بود ولی جواب داد."},
            {"label": "🛡 با احتیاط پیش برو (امن)", "risk_mult": 1.0, "target_mult": 1.0,
             "result": "قدم‌به‌قدم و بی‌خطر جلو رفتی."},
        ],
    },
]

def _build_quest(guild_id: str, tier: int, player: dict) -> dict:
    g = GUILDS[guild_id]
    weights = g["quest_weights"]
    qtype = random.choices(list(weights.keys()), weights=list(weights.values()), k=1)[0]

    from economy import MAP_ENEMIES, MAPS_DATA
    map_name = random.choice(list(MAP_ENEMIES.keys()))
    enemy = random.choice(MAP_ENEMIES[map_name])

    stages = []
    # ── Intro ──
    intros = {
        "kill": f"🗣 *{g['npc']}*: «تو **{map_name}** یه دسته {enemy} دردسر درست کردن. برو حسابشونو برس.»",
        "gather": f"🗣 *{g['npc']}*: «برای این سفارش به موادی نیاز داریم که تو **{map_name}** پیدا می‌شن.»",
        "zen": f"🗣 *{g['npc']}*: «گیلد به سرمایه نیاز داره. می‌تونی کمک کنی؟»",
        "level": f"🗣 *{g['npc']}*: «ثابت کن که داری قوی‌تر می‌شی — بیشتر تمرین کن و سطح بگیر.»",
    }
    stages.append({"kind": "intro", "narrative": intros[qtype]})

    # ── Choice (شانس ۶۰٪) ──
    has_choice = random.random() < 0.6
    if has_choice:
        stages.append({"kind": "choice", **random.choice(CHOICE_FLAVOR)})

    # ── Objective ──
    if qtype == "kill":
        target = random.randint(3, 6) + tier * 2
        stages.append({
            "kind": "kill", "target": target,
            "narrative": f"⚔️ در حال شکار {enemy} تو **{map_name}**... (با ⚔️ حمله یا 🗺 لوت پیشرفت می‌کنه)",
        })
        title = f"🗡 پاکسازی {map_name} از {enemy}"
    elif qtype == "gather":
        min_rarity = _gather_min_rarity(tier)
        target = random.randint(2, 4) + tier
        stages.append({
            "kind": "gather", "target": target, "min_rarity": min_rarity,
            "narrative": f"📦 {target} آیتم (حداقل ندرت: {min_rarity}) از لوت‌هات جمع‌آوری کن.",
        })
        title = f"📦 تهیه‌ی {target} محموله برای {g['name']}"
    elif qtype == "zen":
        target = random.randint(300, 800) + tier * 500
        stages.append({
            "kind": "zen", "target": target,
            "narrative": f"💰 {target:,} Zen رو به‌عنوان سرمایه به گیلد بسپار.",
        })
        title = f"💰 تأمین سرمایه‌ی {target:,} Zen"
    else:  # level
        target = player.get("level", 1) + random.randint(2, 4) + tier
        stages.append({
            "kind": "level", "target": target,
            "narrative": f"⭐ با گرفتن XP به سطح {target} برس.",
        })
        title = f"⭐ رسیدن به سطح {target}"

    # ── Outro ──
    outros = {
        "kill": "🏁 برگشتی به گیلد؛ خبر شکست هیولاها رو اعلام کن و پاداشتو بگیر.",
        "gather": "🏁 محموله رو تحویل انباردار گیلد بده.",
        "zen": "🏁 سرمایه رو نقد کن و سود گیلد رو دریافت کن.",
        "level": "🏁 پیشرفتت رو به گیلد گزارش بده.",
    }
    stages.append({"kind": "outro", "narrative": outros[qtype]})

    return {
        "id": uuid.uuid4().hex[:8],
        "guild": guild_id,
        "type": qtype,
        "title": title,
        "stages": stages,
        "stage_idx": 0,
        "risk_mult": 1.0,
        "bonus_contrib": 0,
    }


def _reward_for(tier: int, rank_bonus_pct: int, risk_mult: float) -> dict:
    base_zen = random.randint(60, 130) * (tier + 1)
    base_xp = random.randint(30, 70) * (tier + 1)
    mult = (1 + rank_bonus_pct / 100) * risk_mult
    return {
        "zen": int(base_zen * mult),
        "xp": int(base_xp * mult),
        "contribution": int(random.randint(12, 22) * (tier + 1) * risk_mult),
    }


def offer_quests(player: dict, guild_id: str, n: int = 3) -> list[dict]:
    ensure_guild_data(player)
    gdata = player["guilds"].get(guild_id)
    if not gdata:
        return []
    tier = _tier_index(gdata.get("rank", "G"))
    return [_build_quest(guild_id, tier, player) for _ in range(n)]


QUEST_COOLDOWN_SEC = 900  # ⏳ فاصله‌ی اجباری بین تحویل یه کوئست و قبول کردن بعدی (۱۵ دقیقه) — جلوگیری از فارم کردن


def accept_quest(player: dict, guild_id: str, quest: dict) -> tuple[bool, str]:
    ensure_guild_data(player)
    gdata = player["guilds"].get(guild_id)
    if not gdata:
        return False, "❌ عضو این گیلد نیستی."
    if gdata.get("active_quest"):
        return False, "⚠️ همین الان یه کوئست فعال داری. اول تحویلش بده یا لغوش کن."
    remain = gdata.get("quest_cooldown", 0) - time.time()
    if remain > 0:
        mins = int(remain // 60) + 1
        return False, f"⏳ گیلد هنوز داره سفارش قبلی رو پردازش می‌کنه. {mins} دقیقه‌ی دیگه دوباره سر بزن."
    for s in quest["stages"]:
        if s["kind"] == "kill":
            s["start_value"] = player.get("kills", 0)
    gdata["active_quest"] = quest
    return True, f"✅ کوئست پذیرفته شد:\n**{quest['title']}**"


def cancel_quest(player: dict, guild_id: str) -> tuple[bool, str]:
    ensure_guild_data(player)
    gdata = player["guilds"].get(guild_id)
    if not gdata or not gdata.get("active_quest"):
        return False, "❌ کوئست فعالی نداری."
    gdata["active_quest"] = None
    return True, "🗑 کوئست لغو شد (بدون جریمه)."


def current_stage(player: dict, guild_id: str):
    gdata = player.get("guilds", {}).get(guild_id)
    if not gdata or not gdata.get("active_quest"):
        return None
    q = gdata["active_quest"]
    return q["stages"][q["stage_idx"]]


def stage_progress(player: dict, guild_id: str) -> tuple[int, int, bool]:
    """پیشرفت مرحله‌ی *فعلی* کوئست (فقط برای مراحل objective معنی داره)."""
    stage = current_stage(player, guild_id)
    if not stage:
        return 0, 0, False
    kind = stage["kind"]
    if kind not in ("kill", "gather", "zen", "level"):
        return 0, 0, True  # مراحل روایی همیشه با یه دکمه قابل ادامه‌ان
    target = stage["target"]
    if kind == "kill":
        cur = player.get("kills", 0) - stage.get("start_value", 0)
    elif kind == "gather":
        cur = sum(1 for it in player.get("inventory", [])
                  if RARITY_ORDER.index(it.get("rarity", "common")) >= RARITY_ORDER.index(stage["min_rarity"]))
    elif kind == "zen":
        cur = player.get("zen", 0)
    else:  # level
        cur = player.get("level", 1)
    cur = max(0, cur)
    return cur, target, cur >= target


def choose_option(player: dict, guild_id: str, opt_idx: int) -> tuple[bool, str]:
    gdata = player["guilds"].get(guild_id)
    if not gdata or not gdata.get("active_quest"):
        return False, "❌ کوئست فعالی نداری."
    q = gdata["active_quest"]
    stage = q["stages"][q["stage_idx"]]
    if stage["kind"] != "choice":
        return False, "❌ این مرحله انتخابی نیست."
    opt = stage["options"][opt_idx]
    q["risk_mult"] = q.get("risk_mult", 1.0) * opt.get("risk_mult", 1.0)
    q["bonus_contrib"] = q.get("bonus_contrib", 0) + opt.get("bonus_contrib", 0)
    if "target_mult" in opt:
        for s in q["stages"]:
            if s["kind"] in ("kill", "gather", "zen", "level"):
                s["target"] = max(1, int(s["target"] * opt["target_mult"]))
                if s["kind"] == "kill":
                    s["start_value"] = player.get("kills", 0)
    q["stage_idx"] += 1
    return True, f"📖 {opt['result']}"


def advance_quest(player: dict, guild_id: str) -> tuple[bool, str, bool]:
    """پیش‌بردن کوئست یه مرحله. (موفق؟, پیام, تمام‌شده؟)"""
    gdata = player.get("guilds", {}).get(guild_id)
    if not gdata or not gdata.get("active_quest"):
        return False, "❌ کوئست فعالی نداری.", False
    q = gdata["active_quest"]
    stage = q["stages"][q["stage_idx"]]
    kind = stage["kind"]

    if kind == "choice":
        return False, "❌ اول یکی از گزینه‌ها رو انتخاب کن.", False

    if kind in ("kill", "gather", "zen", "level"):
        cur, target, ready = stage_progress(player, guild_id)
        if not ready:
            return False, f"⏳ هنوز آماده نیست ({cur}/{target}).", False
        if kind == "gather":
            need = target
            inv = player.get("inventory", [])
            keep, removed = [], 0
            min_idx = RARITY_ORDER.index(stage["min_rarity"])
            for it in inv:
                if removed < need and RARITY_ORDER.index(it.get("rarity", "common")) >= min_idx:
                    removed += 1
                    continue
                keep.append(it)
            player["inventory"] = keep
        elif kind == "zen":
            player["zen"] = player.get("zen", 0) - target

    # آخرین مرحله (outro) → پایان کوئست و پاداش
    if q["stage_idx"] == len(q["stages"]) - 1:
        return _finalize_quest(player, guild_id)

    q["stage_idx"] += 1
    return True, stage.get("narrative", "..."), False


def _finalize_quest(player: dict, guild_id: str) -> tuple[bool, str, bool]:
    gdata = player["guilds"][guild_id]
    q = gdata["active_quest"]
    tier = _tier_index(gdata.get("rank", "G"))
    reward = _reward_for(tier, RANK_BONUS_PCT[gdata.get("rank", "G")], q.get("risk_mult", 1.0))
    reward["contribution"] += q.get("bonus_contrib", 0)

    # 🛡 اگه کوئست از نوع «سرمایه» بود، پاداش Zen نباید از خودِ سرمایه‌ی سپرده‌شده بیشتر باشه
    # (وگرنه گیلد تبدیل به چاپ پول بی‌نهایت می‌شه)
    zen_stage = next((s for s in q["stages"] if s["kind"] == "zen"), None)
    if zen_stage:
        reward["zen"] = min(reward["zen"], int(zen_stage["target"] * 0.35))

    player["zen"] = player.get("zen", 0) + reward["zen"]
    player["xp"] = player.get("xp", 0) + reward["xp"]
    gdata["contribution"] = gdata.get("contribution", 0) + reward["contribution"]
    add_war_points(guild_id, reward["contribution"])
    gdata["quests_done"] = gdata.get("quests_done", 0) + 1
    gdata["active_quest"] = None
    gdata["quest_cooldown"] = time.time() + QUEST_COOLDOWN_SEC

    msg = (
        f"🎉 **مأموریت کامل شد: {q['title']}**\n\n"
        f"💰 +{reward['zen']:,} Zen\n"
        f"✨ +{reward['xp']:,} XP\n"
        f"📈 +{reward['contribution']} امتیاز گیلد"
    )
    ready, _ = trial_ready(player, guild_id)
    if ready:
        msg += "\n\n🎖 **آزمون ارتقای رتبه در دسترسه!**"
    return True, msg, True


# ============================================================
#  UNIQUE GUILD ACTIONS (ریسک/پاداش تکرارشونده)
# ============================================================
def action_ready(player: dict, guild_id: str) -> tuple[bool, int]:
    gdata = player.get("guilds", {}).get(guild_id)
    if not gdata:
        return False, 0
    cd = GUILDS[guild_id]["action"]["cooldown"]
    remain = int(gdata.get("last_action", 0) + cd - time.time())
    return remain <= 0, max(0, remain)


def do_guild_action(player: dict, guild_id: str) -> tuple[bool, str]:
    gdata = player.get("guilds", {}).get(guild_id)
    if not gdata:
        return False, "❌ عضو این گیلد نیستی."
    ready, remain = action_ready(player, guild_id)
    if not ready:
        return False, f"⏳ صبر کن {remain//60} دقیقه‌ی دیگه."

    rank_bonus = RANK_BONUS_PCT[gdata.get("rank", "G")]
    gdata["last_action"] = time.time()

    if guild_id in ("adventurers", "hunters"):
        from economy import MAP_ENEMIES
        enemy = random.choice(sum(MAP_ENEMIES.values(), []))
        chance = 50 + rank_bonus + min(20, player.get("level", 1) // 4)
        roll = random.randint(1, 100)
        if roll <= chance:
            zen = random.randint(200, 500)
            contrib = random.randint(10, 25)
            player["zen"] = player.get("zen", 0) + zen
            gdata["contribution"] = gdata.get("contribution", 0) + contrib
            add_war_points(guild_id, contrib)
            msg = f"⚔️ {enemy} رو شکست دادی! 💰+{zen:,} Zen | 📈+{contrib} امتیاز"
            if guild_id == "hunters":
                from economy import roll_loot
                loot = roll_loot(player.get("map", "Verdant Vale"), count=1, player_level=player.get("level", 1))
                player.setdefault("inventory", []).extend(loot)
                msg += f"\n🎁 لوت اضافه: {loot[0]['emoji']} {loot[0]['name']}"
            return True, msg
        else:
            dmg = random.randint(5, 15)
            player["hp"] = max(1, player.get("hp", 100) - dmg)
            return False, f"💥 {enemy} شکستت داد! -{dmg} HP. دفعه‌ی بعد بیشتر مراقب باش."

    if guild_id == "merchants":
        stake = min(500, int(player.get("zen", 0) * 0.15))
        if stake < 50:
            return False, "❌ Zen کافی برای معامله نداری (حداقل ۳۳۰ نیاز داری)."
        player["zen"] -= stake
        roll = random.randint(1, 100)
        if roll <= 55 + rank_bonus // 2:
            profit_mult = random.uniform(1.5, 2.2)
            gain = int(stake * profit_mult)
            player["zen"] += gain
            gdata["contribution"] = gdata.get("contribution", 0) + 15
            add_war_points(guild_id, 15)
            return True, f"📈 معامله موفق! {stake:,} → {gain:,} Zen (سود {gain-stake:,})"
        else:
            loss_back = stake // 2
            player["zen"] += loss_back
            return False, f"📉 معامله ضرر داد! فقط {loss_back:,} از {stake:,} برگشت."

    if guild_id == "blacksmiths":
        inv = player.get("inventory", [])
        if len(inv) < 2:
            return False, "❌ حداقل ۲ آیتم تو کوله‌پشتی لازم داری."
        used = [inv.pop(), inv.pop()]
        base = sum(i.get("sell", 50) for i in used)
        crit = random.random() < (0.15 + rank_bonus / 100)
        zen = int(base * (2.5 if crit else 1.5))
        contrib = random.randint(15, 30) + (10 if crit else 0)
        player["zen"] = player.get("zen", 0) + zen
        gdata["contribution"] = gdata.get("contribution", 0) + contrib
        add_war_points(guild_id, contrib)
        crit_txt = "\n🔥 **کیفیت بحرانی!** جایزه دو برابر شد!" if crit else ""
        return True, f"🔨 {used[0]['name']} و {used[1]['name']} ذوب شد → 💰{zen:,} Zen{crit_txt}"

    if guild_id == "alchemists":
        inv = player.get("inventory", [])
        if not inv:
            return False, "❌ کوله‌پشتیت خالیه — یه چیزی برای دم‌کردن لازمه."
        used = inv.pop()
        heal_pct = 40 + rank_bonus
        max_hp = player.get("max_hp", 100)
        healed = int(max_hp * heal_pct / 100)
        player["hp"] = min(max_hp, player.get("hp", 100) + healed)
        contrib = random.randint(12, 22)
        gdata["contribution"] = gdata.get("contribution", 0) + contrib
        add_war_points(guild_id, contrib)
        return True, f"🧪 {used['name']} رو دم کردی → ❤️+{healed} HP | 📈+{contrib} امتیاز"

    if guild_id == "mages":
        cost = min(200, int(player.get("xp", 0) * 0.25))
        if cost < 30:
            return False, "❌ XP کافی برای پژوهش نداری."
        player["xp"] -= cost
        success = random.random() < (0.6 + rank_bonus / 100)
        contrib = random.randint(15, 30)
        gdata["contribution"] = gdata.get("contribution", 0) + contrib
        add_war_points(guild_id, contrib)
        if success:
            player["skill_points"] = player.get("skill_points", 0) + 1
            return True, f"🔮 طلسم جدید کشف شد! 🌟+۱ امتیاز مهارت (هزینه: {cost} XP)"
        else:
            player["zen"] = player.get("zen", 0) + cost * 2
            return False, f"🔮 پژوهش شکست خورد، ولی XP سوخته رو به Zen تبدیل کردیم: +{cost*2:,} Zen"

    return False, "❌ خطای ناشناخته."


# ============================================================
#  GUILD CARD
# ============================================================
def guild_card_text(player: dict) -> str:
    ensure_guild_data(player)
    if not player["guilds"]:
        return "🏛 هنوز عضو هیچ گیلدی نیستی. با «🏛 گیلدها» یه گیلد انتخاب کن."
    lines = [f"🪪 **کارت شناسایی گیلدی — {player.get('name','?')}**\n"]
    for gid, gdata in player["guilds"].items():
        g = GUILDS[gid]
        rank = gdata.get("rank", "G")
        lines.append(
            f"{g['emoji']} **{g['name']}** — رتبه {rank} ({RANK_NAMES_FA[rank]})\n"
            f"   📈 امتیاز: {gdata.get('contribution',0):,} | ✅ کوئست: {gdata.get('quests_done',0)}\n"
        )
    titles = [t for t in player.get("titles_unlocked", []) if any(t == g["s_title"] for g in GUILDS.values())]
    if titles:
        lines.append("\n👑 **عناوین گیلدی:** " + "، ".join(titles))
    return "\n".join(lines)


# ============================================================
#  ۱) پرک‌های غیرفعال بر اساس رتبه (Guild Rank Perks)
#  هرچی رتبه‌ت تو گیلد بالاتر بره، یه بونوس دائمی متناسب با تخصص
#  همون گیلد می‌گیری. جمع‌شونده‌ست (اگه عضو چند گیلد باشی).
# ============================================================
PERK_STAT = {
    "adventurers": "pve_dmg_pct",   # دمیج بیشتر تو نبرد PvE
    "hunters":     "rare_loot_pct", # شانس لوت‌های نادرتر
    "merchants":   "zen_gain_pct",  # Zen بیشتر از کشتن/لوت
    "blacksmiths": "forge_zen_pct", # سود بیشتر از ذوب/فروش
    "alchemists":  "heal_pct",      # درمان بیشتر
    "mages":       "xp_gain_pct",   # XP بیشتر از کشتن/لوت
}
PERK_PER_RANK = {  # به ازای هر پله‌ی رتبه (G=0 .. S=7) — واحد: کسر (0.02 = ۲٪)
    "adventurers": 0.018,
    "hunters":     0.015,
    "merchants":   0.018,
    "blacksmiths": 0.020,
    "alchemists":  0.020,
    "mages":       0.015,
}

def get_guild_perks(player: dict) -> dict:
    """درصدِ (کسری) بونوس‌های غیرفعالِ گیلدی. صفر یعنی عضو نیستی/رتبه‌ت پایینه."""
    perks = {stat: 0.0 for stat in set(PERK_STAT.values())}
    for gid, gdata in player.get("guilds", {}).items():
        stat = PERK_STAT.get(gid)
        if not stat:
            continue
        tier = RANKS.index(gdata.get("rank", "G"))
        perks[stat] += tier * PERK_PER_RANK[gid]
    return perks


def get_perk(player: dict, stat: str) -> float:
    return get_guild_perks(player).get(stat, 0.0)


def perks_summary_text(player: dict) -> str:
    """متنِ خلاصه‌ی پرک‌های فعال — برای نمایش تو کارت گیلد."""
    perks = get_guild_perks(player)
    labels = {
        "pve_dmg_pct":   "⚔️ دمیج PvE",
        "rare_loot_pct": "🎁 شانس لوت نادر",
        "zen_gain_pct":  "💰 Zen بیشتر",
        "forge_zen_pct": "🔨 سود ذوب",
        "heal_pct":      "❤️ درمان بیشتر",
        "xp_gain_pct":   "✨ XP بیشتر",
    }
    active = [(labels[k], v) for k, v in perks.items() if v > 0]
    if not active:
        return ""
    lines = ["\n🌟 **پرک‌های فعال:**"]
    for label, v in active:
        lines.append(f"   {label}: +{v*100:.1f}٪")
    return "\n".join(lines)


# ============================================================
#  ۲) فروشگاه گیلد (خرج کردن امتیاز مشارکت)
# ============================================================
GUILD_SHOP = {
    "adventurers": [
        {"id": "adv_potion", "name": "🧪 معجون بقای ماجراجو", "cost": 80,
         "desc": "بلافاصله ۵۰٪ از HP ماکسیممت رو پر می‌کنه.", "kind": "heal_pct", "value": 0.5},
        {"id": "adv_zen", "name": "💰 غنیمت جنگی", "cost": 150,
         "desc": "۶۰۰-۱۰۰۰ Zen نقد فوری.", "kind": "zen", "value": (600, 1000)},
    ],
    "merchants": [
        {"id": "mer_zen_big", "name": "💰 سهم از سود گیلد", "cost": 120,
         "desc": "۸۰۰-۱۴۰۰ Zen نقد فوری.", "kind": "zen", "value": (800, 1400)},
        {"id": "mer_title", "name": "👑 لقب «دلال آبیس»", "cost": 400,
         "desc": "یه لقب نمایشی برای پروفایلت.", "kind": "title", "value": "دلال آبیس"},
    ],
    "blacksmiths": [
        {"id": "bs_repair", "name": "🔨 تعمیر کامل تجهیزات", "cost": 100,
         "desc": "دوام همه‌ی وسایل پوشیده‌ت رو صد در صد می‌کنه.", "kind": "repair_all", "value": None},
        {"id": "bs_zen", "name": "💰 سفارش ویژه", "cost": 150,
         "desc": "۷۰۰-۱۲۰۰ Zen نقد فوری.", "kind": "zen", "value": (700, 1200)},
    ],
    "alchemists": [
        {"id": "alc_fullheal", "name": "❤️ درمان کامل", "cost": 90,
         "desc": "HP رو صد در صد پر می‌کنه.", "kind": "heal_pct", "value": 1.0},
        {"id": "alc_zen", "name": "💰 فروش معجون‌ها", "cost": 130,
         "desc": "۶۰۰-۱۰۰۰ Zen نقد فوری.", "kind": "zen", "value": (600, 1000)},
    ],
    "mages": [
        {"id": "mage_sp", "name": "🌟 امتیاز مهارت آزاد", "cost": 350,
         "desc": "۱ امتیاز درخت مهارت فوری.", "kind": "skill_point", "value": 1},
        {"id": "mage_zen", "name": "💰 فروش طلسم", "cost": 130,
         "desc": "۶۰۰-۱۰۰۰ Zen نقد فوری.", "kind": "zen", "value": (600, 1000)},
    ],
    "hunters": [
        {"id": "hunt_zen", "name": "💰 فروش پوست و تروفی", "cost": 130,
         "desc": "۷۰۰-۱۱۰۰ Zen نقد فوری.", "kind": "zen", "value": (700, 1100)},
        {"id": "hunt_title", "name": "👑 لقب «سایه‌ی شکارچی»", "cost": 400,
         "desc": "یه لقب نمایشی برای پروفایلت.", "kind": "title", "value": "سایه‌ی شکارچی"},
    ],
}


def get_shop_items(guild_id: str) -> list[dict]:
    return GUILD_SHOP.get(guild_id, [])


def buy_shop_item(player: dict, guild_id: str, item_id: str) -> tuple[bool, str]:
    ensure_guild_data(player)
    gdata = player["guilds"].get(guild_id)
    if not gdata:
        return False, "❌ عضو این گیلد نیستی."
    item = next((i for i in get_shop_items(guild_id) if i["id"] == item_id), None)
    if not item:
        return False, "❌ آیتم نامعتبر."
    if gdata.get("contribution", 0) < item["cost"]:
        return False, f"❌ امتیاز مشارکت کافی نداری ({gdata.get('contribution',0)}/{item['cost']})."

    gdata["contribution"] -= item["cost"]
    kind, value = item["kind"], item["value"]

    if kind == "zen":
        amt = random.randint(*value)
        player["zen"] = player.get("zen", 0) + amt
        return True, f"✅ خریدی شد: **{item['name']}**\n💰 +{amt:,} Zen"

    if kind == "heal_pct":
        max_hp = player.get("max_hp", 100)
        healed = int(max_hp * value)
        player["hp"] = min(max_hp, player.get("hp", 100) + healed)
        return True, f"✅ خریدی شد: **{item['name']}**\n❤️ +{healed} HP"

    if kind == "title":
        titles = player.setdefault("titles_unlocked", [])
        if value not in titles:
            titles.append(value)
        return True, f"✅ خریدی شد: **{item['name']}**\n👑 لقب «{value}» به پروفایلت اضافه شد."

    if kind == "skill_point":
        player["skill_points"] = player.get("skill_points", 0) + value
        return True, f"✅ خریدی شد: **{item['name']}**\n🌟 +{value} امتیاز مهارت"

    if kind == "repair_all":
        eq = player.get("equipped", {})
        fixed = 0
        for slot, it in eq.items():
            if it and it.get("durability", 100) < it.get("max_durability", 100):
                it["durability"] = it.get("max_durability", 100)
                fixed += 1
        return True, f"✅ خریدی شد: **{item['name']}**\n🔧 {fixed} وسیله تعمیر شد."

    return False, "❌ خطای ناشناخته تو فروشگاه."


# ============================================================
#  ۳) جنگ هفتگی گیلدها (Weekly Guild War)
#  تمام امتیازِ مشارکتیِ کسب‌شده تو هفته جمع می‌شه، گیلدِ برنده یه
#  بافر همگانی (XP) برای همه‌ی اعضاش تا هفته‌ی بعد می‌گیره.
# ============================================================
WAR_DURATION_SEC = 7 * 24 * 3600
WAR_WINNER_XP_BUFF = 0.10  # +۱۰٪ XP برای همه‌ی اعضای گیلدِ برنده


def _war_doc():
    from database import system_col
    doc = system_col().find_one({"_id": "guild_war"})
    if not doc:
        doc = {
            "_id": "guild_war",
            "week_start": time.time(),
            "scores": {gid: 0 for gid in GUILD_IDS},
            "last_winner": None,
            "last_winner_score": 0,
        }
        system_col().update_one({"_id": "guild_war"}, {"$set": doc}, upsert=True)
    return doc


def _save_war(doc: dict):
    from database import system_col
    data = {k: v for k, v in doc.items() if k != "_id"}
    system_col().update_one({"_id": "guild_war"}, {"$set": data}, upsert=True)


def add_war_points(guild_id: str, points: int):
    """هر بار امتیاز مشارکت گیلدی گرفته می‌شه (کوئست/اکشن/باس) صدا زده می‌شه."""
    if points <= 0 or guild_id not in GUILD_IDS:
        return
    doc = _war_doc()
    _maybe_resolve_war(doc)
    doc["scores"][guild_id] = doc.get("scores", {}).get(guild_id, 0) + points
    _save_war(doc)


def _maybe_resolve_war(doc: dict):
    if time.time() - doc.get("week_start", 0) < WAR_DURATION_SEC:
        return
    scores = doc.get("scores", {gid: 0 for gid in GUILD_IDS})
    winner = max(scores, key=lambda g: scores[g]) if any(scores.values()) else None
    doc["last_winner"] = winner
    doc["last_winner_score"] = scores.get(winner, 0) if winner else 0
    doc["week_start"] = time.time()
    doc["scores"] = {gid: 0 for gid in GUILD_IDS}


def get_war_state() -> dict:
    doc = _war_doc()
    _maybe_resolve_war(doc)
    _save_war(doc)
    return doc


def war_status_text() -> str:
    doc = get_war_state()
    remain = int(WAR_DURATION_SEC - (time.time() - doc["week_start"]))
    days, hrs = remain // 86400, (remain % 86400) // 3600
    scores = doc.get("scores", {})
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    lines = [f"⚔️ **جنگ هفتگی گیلدها** — {days} روز و {hrs} ساعت تا پایان\n"]
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣"]
    for i, (gid, score) in enumerate(ranked):
        g = GUILDS[gid]
        lines.append(f"{medals[i]} {g['emoji']} {g['name']} — {score:,} امتیاز")
    if doc.get("last_winner"):
        wg = GUILDS[doc["last_winner"]]
        lines.append(
            f"\n👑 برنده‌ی هفته‌ی قبل: {wg['emoji']} {wg['name']} "
            f"({doc['last_winner_score']:,} امتیاز) — اعضاش +{int(WAR_WINNER_XP_BUFF*100)}٪ XP دارن!"
        )
    return "\n".join(lines)


def get_war_xp_buff(player: dict) -> float:
    """اگه بازیکن عضو گیلدِ برنده‌ی هفته‌ی قبل باشه، یه بافِ XP اضافه می‌گیره."""
    doc = get_war_state()
    winner = doc.get("last_winner")
    if winner and winner in player.get("guilds", {}):
        return WAR_WINNER_XP_BUFF
    return 0.0


# ============================================================
#  ۴) رئیس اختصاصی هر گیلد (Guild Boss)
#  فقط اعضای رتبه B به بالا می‌تونن بزنن. HP مشترک، پاداش
#  متناسب با سهمِ دمیج + یه آیتم افسانه‌ای مخصوص گیلد به بالاترین ضربه‌زن.
# ============================================================
GUILD_BOSS_MIN_RANK = "B"
GUILD_BOSS_DATA = {
    # loot_slot: اسلاتِ درستِ آیتمِ لوت (باگ‌فیکس: قبلاً همه چیز به‌زور "relic" بود
    # و مثلاً شمشیرِ پادشاهِ تباهی تو اسلاتِ مصنوعه می‌رفت نه سلاح)
    "adventurers": {"name": "👹 پادشاه تباهی صحرا", "hp": 8000,
                     "loot_name": "🗡 شمشیر پادشاه تباهی", "loot_slot": "weapon", "element": "dark"},
    "merchants":   {"name": "🐙 اختاپوس طلایی بازار", "hp": 7000,
                     "loot_name": "💍 حلقه‌ی سود بی‌کران", "loot_slot": "ring", "element": "gold"},
    "blacksmiths": {"name": "🔥 گولم آتشین کوره", "hp": 9000,
                     "loot_name": "🔨 چکش استاد آهنگر", "loot_slot": "weapon", "element": "fire"},
    "alchemists":  {"name": "🧪 هیولای معجون فراری", "hp": 7500,
                     "loot_name": "🧪 معجون جاودانگی", "loot_slot": "relic", "element": "poison"},
    "mages":       {"name": "🔮 نگهبان کتابخانه‌ی ممنوعه", "hp": 8500,
                     "loot_name": "🔮 عصای آرشیماگ", "loot_slot": "weapon", "element": "arcane"},
    "hunters":     {"name": "🐺 گرگ‌سالار سایه‌ها", "hp": 7800,
                     "loot_name": "🏹 کمان سایه‌شکار", "loot_slot": "weapon", "element": "shadow"},
}


def repair_guild_boss_loot_slots(doc: dict) -> bool:
    """خودترمیمیِ داده‌های قبلاً خراب‌شده: قبل از باگ‌فیکسِ بالا (GUILD_BOSS_DATA
    → loot_slot)، همه‌ی لوت‌های رئیسِ گیلد به‌زور اسلاتِ "relic" می‌گرفتن —
    یعنی مثلاً شمشیرِ پادشاهِ تباهی که باید تو اسلاتِ weapon بره، تو اینونتوری/
    اکیپمنتِ پلیرهایی که از قبل این باس رو کشته بودن هنوز با slot="relic"
    ذخیره‌ست. این تابع، هر آیتمی که اسمش با یکی از loot_nameهای GUILD_BOSS_DATA
    یکی باشه رو پیدا می‌کنه و slot ش رو با loot_slot درست جایگزین می‌کنه.
    اگه همچین آیتمی الان اشتباهی اکیپ شده باشه، برش می‌گردونه به کوله‌پشتی
    (چون ممکنه اسلاتِ درستش از قبل یه چیزِ دیگه اکیپ داشته باشه).
    idempotent است — روی دیتای سالم صدا زدنش هیچ اثری نداره.
    برمی‌گردونه True اگه چیزی عوض شده باشه (یعنی صدازننده باید save_player رو صدا بزنه)."""
    changed = False
    correct_slot = {b["loot_name"]: b["loot_slot"] for b in GUILD_BOSS_DATA.values()}

    inv = doc.get("inventory")
    if inv:
        for it in inv:
            want = correct_slot.get(it.get("name"))
            if want and it.get("slot") != want:
                it["slot"] = want
                changed = True

    eq = doc.get("equipped")
    if eq:
        inv = doc.setdefault("inventory", inv or [])
        for slot_key, item in list(eq.items()):
            if not item:
                continue
            want = correct_slot.get(item.get("name"))
            if want and (item.get("slot") != want or slot_key != want):
                item["slot"] = want
                inv.append(item)
                eq[slot_key] = None
                changed = True
        if changed:
            doc["inventory"] = inv

    return changed


def guild_boss_unlocked(player: dict, guild_id: str) -> bool:
    gdata = player.get("guilds", {}).get(guild_id)
    if not gdata:
        return False
    return RANKS.index(gdata.get("rank", "G")) >= RANKS.index(GUILD_BOSS_MIN_RANK)


def _gb_doc(guild_id: str) -> dict:
    from database import guild_boss_col
    doc = guild_boss_col().find_one({"_id": guild_id})
    if not doc or not doc.get("alive"):
        base = GUILD_BOSS_DATA[guild_id]
        doc = {
            "_id": guild_id, "name": base["name"], "hp": base["hp"], "max_hp": base["hp"],
            "alive": True, "contributors": {}, "spawned_at": time.time(),
        }
        guild_boss_col().update_one({"_id": guild_id}, {"$set": doc}, upsert=True)
    return doc


def _save_gb(doc: dict):
    from database import guild_boss_col
    data = {k: v for k, v in doc.items() if k != "_id"}
    guild_boss_col().update_one({"_id": doc["_id"]}, {"$set": data}, upsert=True)


def get_guild_boss(guild_id: str) -> dict:
    return _gb_doc(guild_id)


def reset_guild_boss(guild_id: str):
    """ادمین: رئیسِ گیلد رو دستی ریست می‌کنه (دفعه‌ی بعد که کسی صفحه رو باز کنه، از نو اسپان می‌شه)."""
    from database import guild_boss_col
    guild_boss_col().update_one({"_id": guild_id}, {"$set": {"alive": False, "hp": 0}}, upsert=True)


def guild_boss_status_text(guild_id: str) -> str:
    boss = get_guild_boss(guild_id)
    pct = boss["hp"] / boss["max_hp"] if boss["max_hp"] else 0
    bar_len = 14
    filled = int(pct * bar_len)
    bar = "🟥" * filled + "⬛" * (bar_len - filled)
    return (
        f"👹 **{boss['name']}**\n"
        f"{bar}\n"
        f"❤️ {boss['hp']:,} / {boss['max_hp']:,}\n"
        f"👥 مشارکت‌کننده‌ها: {len(boss.get('contributors', {}))}"
    )


def guild_boss_attack(player: dict, guild_id: str, dmg: int) -> tuple[dict, bool]:
    """دمیج به رئیس گیلد می‌زنه. خروجی: (boss_doc, killed_this_hit؟)"""
    boss = _gb_doc(guild_id)
    uid = str(player.get("id"))
    was_alive = boss["hp"] > 0
    boss["hp"] = max(0, boss["hp"] - dmg)
    boss["contributors"][uid] = boss.get("contributors", {}).get(uid, 0) + dmg
    add_war_points(guild_id, max(1, dmg // 50))
    killed = was_alive and boss["hp"] <= 0
    if killed:
        boss["alive"] = False
    _save_gb(boss)
    return boss, killed


def guild_boss_rewards(guild_id: str, boss: dict) -> dict:
    """موقع کشتنِ رئیس صدا زده می‌شه — پاداشِ هر شرکت‌کننده رو متناسب با سهمِ دمیجش برمی‌گردونه."""
    total_dmg = sum(boss.get("contributors", {}).values()) or 1
    total_zen_pool = boss["max_hp"] * 2
    total_xp_pool = boss["max_hp"]
    rewards = {}
    top_uid, top_dmg = None, 0
    for uid, dmg in boss.get("contributors", {}).items():
        share = dmg / total_dmg
        rewards[uid] = {
            "zen": int(total_zen_pool * share),
            "xp": int(total_xp_pool * share),
            "contribution": int(40 * share) + 10,
        }
        if dmg > top_dmg:
            top_uid, top_dmg = uid, dmg
    return {
        "per_player": rewards, "top_uid": top_uid,
        "loot_name": GUILD_BOSS_DATA[guild_id]["loot_name"],
        "loot_slot": GUILD_BOSS_DATA[guild_id]["loot_slot"],
    }


# ============================================================
#  صندوق مشترکِ گیلد (Treasury) — روحیه‌ی گروهی
# ------------------------------------------------------------
#  اعضای هر گیلد می‌تونن Zen به صندوقِ گیلدشون واریز کنن. وقتی
#  صندوق به سقفِ لازم برسه، هر عضوی می‌تونه «روحیه‌ی گروهی» رو
#  فعال کنه: یه بونوسِ موقتِ درصدی که رو همون get_guild_bonus_pct
#  سوار می‌شه — یعنی خودکار رو کامبت/لوت/تجارت/فورج/درمانِ همه‌ی
#  اعضا اثر می‌ذاره (چون همه‌شون از همین تابع تغذیه می‌کنن).
# ============================================================
from database import guild_treasury_col, system_col

RALLY_COST = 20_000
RALLY_DURATION_SEC = 12 * 3600
RALLY_BONUS_PCT = 8
RALLY_COOLDOWN_SEC = 6 * 3600   # بعد از اتمامِ هر روحیه، یه مدت نمی‌شه دوباره فعالش کرد


def _treasury_doc(guild_id: str) -> dict:
    doc = guild_treasury_col().find_one({"_id": guild_id})
    if not doc:
        doc = {"_id": guild_id, "zen": 0, "contributors": {}, "total_alltime": 0,
               "rally_until": 0, "rally_cooldown_until": 0, "infra_level": 0}
        guild_treasury_col().update_one({"_id": guild_id}, {"$set": doc}, upsert=True)
    return doc


def get_treasury(guild_id: str) -> dict:
    return _treasury_doc(guild_id)


def contribute_treasury(player: dict, guild_id: str, amount: int) -> tuple[bool, str]:
    if amount <= 0:
        return False, "❌ مقدار نامعتبره."
    if player.get("zen", 0) < amount:
        return False, "❌ Zen کافی نداری!"
    if guild_id not in player.get("guilds", {}):
        return False, "❌ اول باید عضوِ این گیلد بشی."

    player["zen"] -= amount
    uid = str(player.get("id", ""))
    guild_treasury_col().update_one(
        {"_id": guild_id},
        {"$inc": {"zen": amount, "total_alltime": amount, f"contributors.{uid}": amount}},
        upsert=True,
    )
    # کمکِ مالی هم یه‌کم به امتیازِ رتبه‌ی گیلدیِ خودِ فرد اضافه می‌کنه (تشویقی)
    gdata = player["guilds"][guild_id]
    gdata["contribution"] = gdata.get("contribution", 0) + max(1, amount // 200)

    try:
        from economy_ledger import record_treasury_contribution
        record_treasury_contribution(amount)
    except Exception:
        pass

    return True, f"✅ **{amount:,} Zen** به صندوقِ {GUILDS[guild_id]['name']} واریز شد. سپاس‌گزاریم! 🙏"


def get_rally_bonus_pct(guild_id: str) -> int:
    doc = _treasury_doc(guild_id)
    return RALLY_BONUS_PCT if time.time() < doc.get("rally_until", 0) else 0


def rally_ready(guild_id: str) -> tuple[bool, str]:
    doc = _treasury_doc(guild_id)
    if time.time() < doc.get("rally_until", 0):
        remain = int(doc["rally_until"] - time.time())
        return False, f"🔥 روحیه‌ی گروهی الان فعاله! ({remain//60} دقیقه‌ی دیگه مونده)"
    if time.time() < doc.get("rally_cooldown_until", 0):
        remain = int(doc["rally_cooldown_until"] - time.time())
        return False, f"⏳ صندوق داره نفس تازه می‌کنه — {remain//60} دقیقه‌ی دیگه دوباره می‌تونی فعالش کنی."
    if doc.get("zen", 0) < RALLY_COST:
        return False, f"❌ صندوق کمه — {RALLY_COST:,} Zen لازم داره (فعلاً {doc.get('zen',0):,} Zen داره)."
    return True, ""


def start_rally(guild_id: str) -> tuple[bool, str]:
    ok, reason = rally_ready(guild_id)
    if not ok:
        return False, reason
    now = time.time()
    guild_treasury_col().update_one(
        {"_id": guild_id},
        {"$inc": {"zen": -RALLY_COST},
         "$set": {"rally_until": now + RALLY_DURATION_SEC, "rally_cooldown_until": now + RALLY_DURATION_SEC + RALLY_COOLDOWN_SEC}},
    )
    hrs = RALLY_DURATION_SEC // 3600
    return True, (
        f"🔥 **روحیه‌ی گروهیِ {GUILDS[guild_id]['name']} فعال شد!**\n"
        f"همه‌ی اعضا تا {hrs} ساعتِ دیگه +{RALLY_BONUS_PCT}٪ بونوس اضافه دارن (رو کامبت/لوت/تجارت/فورج/درمان)."
    )


def treasury_top_contributors(guild_id: str, n: int = 5) -> list[tuple[str, int]]:
    doc = _treasury_doc(guild_id)
    contributors = doc.get("contributors", {})
    return sorted(contributors.items(), key=lambda x: -x[1])[:n]


# ============================================================
#  🏛 ارتقای دائمیِ زیرساختِ گیلد (Treasury Infrastructure)
# ------------------------------------------------------------
#  برخلافِ «روحیه‌ی گروهی» که موقتیه، این یه سرمایه‌گذاریِ دائمیه:
#  صندوق Zenِ خودش رو خرجِ ارتقایِ سطحِ زیرساخت می‌کنه (غیرقابلِ
#  بازگشت) و در عوض، تا ابد یه بونوسِ درصدیِ ثابت به همه‌ی اعضای
#  فعلی و آینده‌ی همون گیلد اضافه می‌کنه — رو همون get_guild_bonus_pct
#  سوار می‌شه (یعنی خودکار رو کامبت/لوت/تجارت/فورج/درمانِ همه اثر داره).
#  هر گیلد باید بینِ «نگه‌داشتنِ صندوق برای روحیه‌ی گروهیِ مکرر»
#  و «خرجِ یک‌بارِ صندوق برای یه بونوسِ دائمیِ بزرگ‌تر» تصمیم بگیره.
# ============================================================
INFRA_MAX_LEVEL = 5
INFRA_BONUS_PCT_PER_LEVEL = 3       # هر سطح +۳٪ بونوسِ دائمی (سقف با ۵ سطح: +۱۵٪)
INFRA_BASE_COST = 60_000            # هزینه‌ی سطحِ اول
INFRA_COST_GROWTH = 1.8             # هر سطحِ بعدی این‌قدر گرون‌تره
INFRA_LEVEL_NAMES = ["پایه", "توسعه‌یافته", "پیشرفته", "نخبه", "افسانه‌ای"]


def infra_cost(next_level: int) -> int:
    """هزینه‌ی ارتقا *به* سطحِ next_level (۱..INFRA_MAX_LEVEL)."""
    return int(INFRA_BASE_COST * (INFRA_COST_GROWTH ** (next_level - 1)))


def get_infra_level(guild_id: str) -> int:
    return _treasury_doc(guild_id).get("infra_level", 0)


def get_infra_bonus_pct(guild_id: str) -> int:
    return get_infra_level(guild_id) * INFRA_BONUS_PCT_PER_LEVEL


def infra_upgrade_ready(guild_id: str) -> tuple[bool, str]:
    level = get_infra_level(guild_id)
    if level >= INFRA_MAX_LEVEL:
        return False, "🏛 زیرساختِ این گیلد به حداکثر سطح رسیده."
    cost = infra_cost(level + 1)
    doc = _treasury_doc(guild_id)
    if doc.get("zen", 0) < cost:
        return False, f"❌ صندوق کمه — {cost:,} Zen لازمه (فعلاً {doc.get('zen',0):,} Zen داره)."
    return True, ""


def buy_infra_upgrade(player: dict, guild_id: str) -> tuple[bool, str]:
    if guild_id not in player.get("guilds", {}):
        return False, "❌ اول باید عضوِ این گیلد بشی."
    ok, reason = infra_upgrade_ready(guild_id)
    if not ok:
        return False, reason
    level = get_infra_level(guild_id)
    cost = infra_cost(level + 1)
    guild_treasury_col().update_one(
        {"_id": guild_id},
        {"$inc": {"zen": -cost}, "$set": {"infra_level": level + 1}},
    )
    new_bonus = (level + 1) * INFRA_BONUS_PCT_PER_LEVEL
    name = INFRA_LEVEL_NAMES[level] if level < len(INFRA_LEVEL_NAMES) else f"سطح {level+1}"
    return True, (
        f"🏛 **زیرساختِ {GUILDS[guild_id]['name']} ارتقا یافت: «{name}»!**\n"
        f"از این به بعد همه‌ی اعضا برای همیشه **+{new_bonus}٪** بونوسِ دائمی دارن.\n"
        f"💸 هزینه: {cost:,} Zen از صندوقِ مشترک کسر شد."
    )
