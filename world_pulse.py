# ============================================================
#  ASTRAL ABYSS RPG — World Pulse ⚡ (ضربان آبیس) — v3 "بمب‌گونه"
#  Abyss یه زخمِ زنده‌ست — هر از گاهی «ضربان» می‌زنه و اثرش رو
#  هم‌زمان رو کل دنیا (همه‌ی بازیکن‌ها) می‌ذاره.
#
#  v3 چه فرقی داره؟
#  • ایونت‌ها الان تو ۴ لایه‌ی جدا دسته‌بندی می‌شن:
#      🔹 معمولی (common)  — پرتکرار، اثرِ متوسط
#      🔶 نادر    (rare)    — کمیاب‌تر، اثرِ ترکیبیِ قوی‌تر
#      ⭐ ویژه    (special) — فقط وقتی فسادِ جهان به آستانه‌ی افراطی برسه
#      💣 بمب     (bomb)    — کاملاً مستقل و کمیاب، اثرِ چندگانه‌ی
#         خطرناک/پرسود هم‌زمان + یه اعلانِ دو مرحله‌ای («لرزش» → «انفجار»)
#         که قبل از فعال‌شدنِ واقعیِ اثر، به بازیکن‌ها هشدار می‌ده.
#  • هر ایونت الان می‌تونه هم‌زمان چند effect_key رو تحتِ تاثیر بذاره
#    (مثلاً هم XP هم Zen هم شانسِ کریت) — به‌جای فقط یکی.
#  • گیجِ فسادِ جهان دیگه با ایموجیِ قلبِ سیاه/سفید نشون داده نمی‌شه؛
#    یه نوارِ درجه‌ایِ رنگی داره که با وضعیتِ واقعیِ دنیا رنگ عوض می‌کنه.
#  • همون منطقِ v2 برای فسادِ نرم (میانگینِ Resonance جمعی) و تاریخچه
#    و ضدِ تکرارِ پشتِ‌سرِهم حفظ شده.
#
#  v4 چه اضافه شد؟
#  • ایونت‌های معمولی/نادر/بمب الان به یه نقشه‌ی خاص (target_map) وصل
#    می‌شن — اثرشون (XP/Zen/کریت/دمیج/شانسِ لوت) فقط رو همون نقشه
#    اعمال می‌شه، نه کل دنیا. ایونت‌های ویژه (void/light) چون از فسادِ
#    کلِ دنیا میان، همچنان سراسری می‌مونن.
#  • یه شانسِ اضافه‌ی «آیتمِ ضربان» هست: کشتن تو نقشه‌ی هدف، وقتی
#    ضربانِ فعال از نوعِ blessing باشه، شانسِ کمی داره یه آیتمِ کمیاب
#    از پولِ لوتِ همون نقشه، جدا از لوتِ عادی، بهت بده.
# ============================================================
import random, time, asyncio

CHECK_INTERVAL = 1800          # 🆕 هر ۳۰ دقیقه یه‌بار چک می‌شه (قبلاً هر ۱۰ دقیقه)
PULSE_CHANCE = 0.95             # 🆕 هر چک، ۹۵٪ شانسِ شروعِ یه ضربانِ معمولی/نادر — یعنی عملاً هر نیم‌ساعت یه ایونتِ جدید
PULSE_DURATION = 30 * 60       # مدتِ پیش‌فرضِ ضربان‌های معمولی

TIER_WEIGHTS = {"common": 0.76, "rare": 0.24}   # وقتی یه ضربانِ معمولی/نادر قراره شروع بشه، هرکدوم چقدر شانس دارن

# ─── گیجِ فساد ────────────────────────────────────────────────
CORRUPTION_MIN, CORRUPTION_MAX = 0, 100
CORRUPTION_SMOOTHING = 0.15
CORRUPTION_JITTER = 2

SPECIAL_THRESHOLD_HIGH = 82
SPECIAL_THRESHOLD_LOW = 18
SPECIAL_COOLDOWN_SEC = 12 * 3600

# ─── بمب‌های جهانی — کاملاً مستقل از فساد، خیلی کمیاب، اثرِ چندگانه ───
BOMB_CHANCE = 0.022             # هر چک (هر ۱۰ دقیقه) ۲.۲٪ شانس
BOMB_COOLDOWN_SEC = 6 * 3600    # حداکثر هر ۶ ساعت یه بمب
BOMB_FUSE_SEC = 14              # فاصله‌ی بینِ هشدارِ «لرزش» و خودِ «انفجار»

# اثرهای شناخته‌شده و مقدارِ خنثی‌شون (وقتی هیچ ضربانی فعال نیست یا اون
# effect_key رو تحتِ تاثیر نمی‌ذاره، همین مقدار برگردونده می‌شه)
NEUTRAL = {
    "xp_mult": 1.0, "zen_mult": 1.0, "enemy_dmg_mult": 1.0,
    "loot_luck": 0.0, "crit_add": 0.0, "boss_dmg_mult": 1.0,
}

# ─── لایه‌ی معمولی ─────────────────────────────────────────────
COMMON_EVENTS = [
    {
        "id": "double_xp", "kind": "blessing", "tier": "common",
        "name": "🌠 طنینِ آبیس", "effects": {"xp_mult": 1.6}, "duration": 30 * 60,
        "desc": "برای لحظه‌ای، آبیس خاطراتِ بلعیده‌شده رو پس می‌ده — **XP از نبرد ۶۰٪ بیشتره**.",
    },
    {
        "id": "double_zen", "kind": "blessing", "tier": "common",
        "name": "💸 بارشِ زِن", "effects": {"zen_mult": 1.6}, "duration": 30 * 60,
        "desc": "شکاف‌های آبیس گنجینه‌های بلعیده‌شده رو بیرون می‌ریزن — **Zen از نبرد ۶۰٪ بیشتره**.",
    },
    {
        "id": "loot_frenzy", "kind": "blessing", "tier": "common",
        "name": "🏴‍☠️ هجومِ غارتگران", "effects": {"loot_luck": 0.15}, "duration": 30 * 60,
        "desc": "غارتگرانِ سایه اجناسِ نایاب به‌جا گذاشتن — **شانسِ لوتِ کمیاب بالاتره**.",
    },
    {
        "id": "keen_edge", "kind": "blessing", "tier": "common",
        "name": "🎯 چشمِ تیزبینِ آبیس", "effects": {"crit_add": 0.12}, "duration": 25 * 60,
        "desc": "برای لحظه‌ای ضربانِ قلبت با آبیس هم‌زمان می‌شه — **شانسِ کریت ۱۲٪ بالاتره**.",
    },
    {
        "id": "abyss_corruption", "kind": "curse", "tier": "common",
        "name": "🕳️ فسادِ گسترش‌یابنده", "effects": {"zen_mult": 0.7}, "duration": 30 * 60,
        "desc": "آبیس داره یه قلمروی دیگه رو می‌بلعه — **درآمدِ Zen موقتاً ۳۰٪ کمتره**.",
    },
    {
        "id": "monster_surge", "kind": "curse", "tier": "common",
        "name": "👺 خیزشِ زوایای فراموش‌شده", "effects": {"enemy_dmg_mult": 1.25, "loot_luck": 0.08}, "duration": 30 * 60,
        "desc": "هیولاهای بیشتری از شکاف‌ها بیرون می‌زنن — **دشمن‌ها ۲۵٪ قوی‌ترن، ولی لوت‌شون هم بیشتره**.",
    },
    {
        "id": "fog_of_forgetting", "kind": "curse", "tier": "common",
        "name": "🌫️ مهِ فراموشی", "effects": {"xp_mult": 0.75}, "duration": 25 * 60,
        "desc": "آبیس یه لحظه خاطراتِ نبردت رو محو می‌کنه — **XP از نبرد ۲۵٪ کمتره**.",
    },
    {
        "id": "bone_hunger", "kind": "curse", "tier": "common",
        "name": "🦴 گرسنگیِ استخوان", "effects": {"zen_mult": 0.8, "loot_luck": -0.05}, "duration": 25 * 60,
        "desc": "چیزی زیرِ خاک داره سهمِ تو رو می‌بلعه — **Zen و شانسِ لوتِ نادر هردو کمی کمترن**.",
    },
]

# ─── لایه‌ی نادر — کمیاب‌تر، ترکیبیِ قوی‌تر ─────────────────────
RARE_EVENTS = [
    {
        "id": "fate_echo", "kind": "blessing", "tier": "rare",
        "name": "🔮 پژواکِ سرنوشت", "effects": {"loot_luck": 0.25, "crit_add": 0.08}, "duration": 25 * 60,
        "desc": "برای مدتی کوتاه، آبیس مسیرِ شانس رو به نفعِ تو خم می‌کنه — **شانسِ لوتِ نادر و کریت هردو جهش می‌کنن**.",
    },
    {
        "id": "abyssal_wrath", "kind": "blessing", "tier": "rare",
        "name": "⚔️ خشمِ آبیس", "effects": {"crit_add": 0.2, "boss_dmg_mult": 1.3}, "duration": 20 * 60,
        "desc": "خشمِ آبیس تو رگ‌های تو جاری می‌شه — **کریت و دمیج به باسِ جهانی هردو به‌شدت بیشترن**.",
    },
    {
        "id": "hungry_shadow", "kind": "curse", "tier": "rare",
        "name": "🌑 سایه‌ی گرسنه", "effects": {"enemy_dmg_mult": 1.35, "zen_mult": 0.65}, "duration": 20 * 60,
        "desc": "یه سایه‌ی قدیمی بیدار شده و داره از خطِ داستان تغذیه می‌کنه — **دشمن‌ها خیلی قوی‌ترن و درآمدت افت می‌کنه**.",
    },
    {
        "id": "abyss_chains", "kind": "curse", "tier": "rare",
        "name": "⛓️ زنجیرهای آبیس", "effects": {"xp_mult": 0.6, "zen_mult": 0.6}, "duration": 15 * 60,
        "desc": "برای مدتی کوتاه، آبیس هرچی به‌دست میاری رو نصفه می‌بلعه — **XP و Zen هردو به‌شدت کمترن**، ولی زود تموم می‌شه.",
    },
]

# ─── لایه‌ی ویژه — فقط در آستانه‌ی افراطیِ فساد ─────────────────
SPECIAL_EVENTS = {
    "void": {
        "id": "nal_surge", "kind": "curse", "tier": "special",
        "name": "🌪️ طغیانِ نال", "effects": {"enemy_dmg_mult": 1.4, "loot_luck": 0.2}, "duration": 45 * 60,
        "desc": "آبیس فسادش رو به اوج رسونده و نال داره از شکاف‌ها بیرون می‌خزه — **دشمن‌ها ۴۰٪ قوی‌ترن**، ولی هرکی زنده بمونه لوتِ نادرِ ویژه می‌گیره.",
    },
    "light": {
        "id": "light_return", "kind": "blessing", "tier": "special",
        "name": "🕊️ بازگشتِ نور", "effects": {"zen_mult": 2.0, "xp_mult": 1.3}, "duration": 45 * 60,
        "desc": "برای لحظه‌ای، آبیس آروم گرفته و نورِ فراموش‌شده برگشته — **Zen از نبرد ۱۰۰٪ و XP هم ۳۰٪ بیشتره**.",
    },
}

# ─── لایه‌ی بمب — کاملاً مستقل، خیلی کمیاب، خطرناک و پرسود هم‌زمان ───
BOMB_EVENTS = [
    {
        "id": "resonance_bomb", "kind": "bomb", "tier": "bomb",
        "name": "💣 انفجارِ رزوننس", "effects": {"xp_mult": 2.2, "zen_mult": 2.2, "enemy_dmg_mult": 1.5}, "duration": 50 * 60,
        "desc": "خطِ داستانیِ همه‌ی بازیکن‌ها هم‌زمان تو یه نقطه منفجر شد — **XP و Zen بیشتر از دوبرابر شدن**، ولی دشمن‌ها هم **۵۰٪ قوی‌ترن**. کسایی که الان بجنگن، یا بزرگ می‌برن یا بزرگ می‌بازن.",
    },
    {
        "id": "black_rift", "kind": "bomb", "tier": "bomb",
        "name": "🌪️ شکافِ سیاه", "effects": {"loot_luck": 0.4, "enemy_dmg_mult": 1.6, "crit_add": -0.05}, "duration": 45 * 60,
        "desc": "یه شکافِ کاملاً سیاه دقیقاً وسطِ دنیا باز شده — **شانسِ لوتِ نادر به‌شدت بالا رفته**، ولی دشمن‌ها وحشی‌ان و **دستِ تو کمی می‌لرزه (کریت پایین‌تر)**.",
    },
    {
        "id": "dead_star_fall", "kind": "bomb", "tier": "bomb",
        "name": "☄️ سقوطِ ستاره‌ی مرده", "effects": {"boss_dmg_mult": 1.8, "zen_mult": 1.4, "xp_mult": 0.7}, "duration": 40 * 60,
        "desc": "یه ستاره‌ی مرده رو آسمونِ آبیس سقوط کرده — **دمیج به باسِ جهانی نزدیکِ دوبرابره** و Zen هم بیشتره، ولی تمرکز رو نبردهای معمولی گرفته و **XP کمتره**.",
    },
]

EFFECT_LABELS = {
    "xp_mult": "✨ XP", "zen_mult": "💰 Zen", "loot_luck": "🎲 شانسِ لوت",
    "enemy_dmg_mult": "👹 دمیجِ دشمن", "crit_add": "🎯 کریت", "boss_dmg_mult": "👑 دمیجِ باس",
}

TIER_BADGE = {"common": "🔹 معمولی", "rare": "🔶 نادر", "special": "⭐ ویژه", "bomb": "💣 بمب"}

# ─── زنجیره‌ی «آبیس عصبانیه» ────────────────────────────────────
#  وقتی یه بمب منفجر می‌شه، علاوه بر اثرِ خودش، ۵۰٪ شانس داره یکی
#  از این دو پیامدِ زنجیره‌ای هم فعال بشه: یا نمسیس‌های تقویت‌شده
#  برای همه محتمل‌تر می‌شن، یا جایزه‌ی حلقه‌ی سایه موقتاً بالا می‌ره.
CHAIN_DURATION_SEC = 40 * 60
CHAIN_NEMESIS_SPAWN_MULT = 1.8
CHAIN_NEMESIS_TIER_BONUS = 1
CHAIN_UNDERGROUND_STAKE_BONUS = 0.5   # ۵۰٪ به Zenِ ردوبدل‌شده تو حلقه‌ی سایه اضافه می‌شه

CHAIN_ANNOUNCE = {
    "nemesis_surge": (
        "😡 **آبیس عصبانیه!**\n\n"
        "طنینِ خشمش تا نمسیس‌ها هم رسیده — برای مدتی، تو کل دنیا نمسیس‌ها "
        "محتمل‌تر و قوی‌تر ظاهر می‌شن. مراقبِ دشمن‌های قدیمیت باش..."
    ),
    "underground_surge": (
        "😡 **آبیس عصبانیه!**\n\n"
        "خشمش راهشو به حلقه‌ی سایه باز کرده — داور امشب سخاوتمندتره: "
        "Zenِ ردوبدل‌شده تو حلقه‌ی سایه موقتاً بیشتره!"
    ),
}


def _maybe_start_chain(doc: dict, now: float) -> str | None:
    """بعدِ منفجرشدنِ یه بمب صدا زده می‌شه — ۵۰/۵۰ بینِ دو پیامدِ زنجیره‌ای."""
    chain_type = "nemesis_surge" if random.random() < 0.5 else "underground_surge"
    doc["chain_effect"] = {"type": chain_type, "expires_at": now + CHAIN_DURATION_SEC}
    _save(doc)
    return chain_type


def get_chain_effect() -> str | None:
    """اگه زنجیره‌ی «آبیس عصبانیه» فعاله، نوعش رو برمی‌گردونه، وگرنه None."""
    doc = _doc()
    chain = doc.get("chain_effect")
    if chain and chain.get("expires_at", 0) > time.time():
        return chain.get("type")
    return None


def nemesis_spawn_boost() -> tuple[float, int]:
    """(ضریبِ شانسِ اسپاون، بونوسِ تایر) اگه زنجیره‌ی نمسیس فعال باشه، وگرنه خنثی."""
    if get_chain_effect() == "nemesis_surge":
        return CHAIN_NEMESIS_SPAWN_MULT, CHAIN_NEMESIS_TIER_BONUS
    return 1.0, 0


def underground_stake_bonus() -> float:
    """درصدِ اضافه به Zenِ ردوبدل‌شده‌ی حلقه‌ی سایه، اگه زنجیره‌ی مربوطه فعال باشه."""
    if get_chain_effect() == "underground_surge":
        return CHAIN_UNDERGROUND_STAKE_BONUS
    return 0.0


async def _announce_chain(bot, chain_type: str):
    from database import all_players
    text = CHAIN_ANNOUNCE.get(chain_type)
    if not text:
        return
    players = all_players()
    for pid in players:
        try:
            await bot.send_message(int(pid), text)
        except Exception:
            pass
        await asyncio.sleep(0.03)


def _all_events() -> list[dict]:
    return COMMON_EVENTS + RARE_EVENTS + list(SPECIAL_EVENTS.values()) + BOMB_EVENTS


def _doc():
    from database import system_col
    doc = system_col().find_one({"_id": "world_pulse"})
    if not doc:
        doc = {
            "_id": "world_pulse", "active": None, "expires_at": 0, "last_check": 0,
            "corruption": 50.0, "last_event_id": None, "history": [],
            "last_special_at": 0, "last_bomb_at": 0, "paused": False, "target_map": None,
        }
        system_col().update_one({"_id": "world_pulse"}, {"$set": doc}, upsert=True)
    # سازگاری با اسنادِ قدیمی که این فیلدها رو نداشتن
    doc.setdefault("corruption", 50.0)
    doc.setdefault("last_event_id", None)
    doc.setdefault("history", [])
    doc.setdefault("last_special_at", 0)
    doc.setdefault("last_bomb_at", 0)
    doc.setdefault("paused", False)
    doc.setdefault("chain_effect", None)
    doc.setdefault("target_map", None)
    return doc


def _save(doc: dict):
    from database import system_col
    data = {k: v for k, v in doc.items() if k != "_id"}
    system_col().update_one({"_id": "world_pulse"}, {"$set": data}, upsert=True)


def _clamp_corruption(v: float) -> float:
    return max(CORRUPTION_MIN, min(CORRUPTION_MAX, v))


def _target_corruption() -> float:
    """میانگینِ Resonance جمعیِ بازیکن‌ها رو به بازه‌ی فسادِ ۰..۱۰۰ نگاشت می‌کنه.
    Resonance: -100 (Void) .. +100 (Light). فساد: 0 (روشن) .. 100 (فاسد)."""
    try:
        from database import all_players
        players = all_players()
        resonances = [p.get("resonance", 0) for p in players.values() if p.get("main_chapter", 0) > 0]
        if not resonances:
            return 50.0
        avg_res = sum(resonances) / len(resonances)
        return _clamp_corruption((100 - avg_res) / 2)
    except Exception:
        return 50.0


def update_corruption(doc: dict) -> float:
    target = _target_corruption()
    current = doc.get("corruption", 50.0)
    new_val = current + (target - current) * CORRUPTION_SMOOTHING
    new_val += random.uniform(-CORRUPTION_JITTER, CORRUPTION_JITTER)
    doc["corruption"] = round(_clamp_corruption(new_val), 1)
    return doc["corruption"]


def _weighted_from_pool(pool: list[dict], corruption: float, exclude_id: str | None) -> dict:
    filtered = [e for e in pool if e["id"] != exclude_id] or list(pool)
    weights = []
    for e in filtered:
        if e["kind"] == "curse":
            w = 0.5 + (corruption / 100)
        else:
            w = 0.5 + ((100 - corruption) / 100)
        weights.append(w)
    return random.choices(filtered, weights=weights, k=1)[0]


def _pick_pulse_event(corruption: float, exclude_id: str | None) -> dict:
    """اول لایه (معمولی/نادر) رو انتخاب می‌کنه، بعد داخلِ همون لایه بر اساسِ فساد وزن‌دهی می‌کنه."""
    tier = random.choices(list(TIER_WEIGHTS.keys()), weights=list(TIER_WEIGHTS.values()), k=1)[0]
    pool = COMMON_EVENTS if tier == "common" else RARE_EVENTS
    return _weighted_from_pool(pool, corruption, exclude_id)


def get_active_pulse() -> dict | None:
    doc = _doc()
    if doc.get("active") and doc.get("expires_at", 0) > time.time():
        return next((e for e in _all_events() if e["id"] == doc["active"]), None)
    return None


def get_pulse_target_map() -> str | None:
    """نقشه‌ای که ضربانِ فعلی روش متمرکزه، یا None اگه سراسری باشه یا هیچ ضربانی فعال نباشه."""
    doc = _doc()
    if doc.get("active") and doc.get("expires_at", 0) > time.time():
        return doc.get("target_map")
    return None


def pulse_value(effect_key: str, map_name: str | None = None) -> float:
    """اگه ضربانِ فعال روی effect_key اثر بذاره مقدارش رو می‌ده، وگرنه مقدارِ خنثی.
    اگه ضربان به یه نقشه‌ی خاص وصل باشه (target_map) و map_name پاس داده بشه ولی
    با نقشه‌ی هدف فرق کنه، اثری نداره (خنثی برمی‌گرده) — یعنی باید بری همون
    نقشه‌ای که ضربان روشه تا اثرش بهت برسه. اگه map_name پاس داده نشه (None)،
    مثلِ قبل بدونِ محدودیتِ نقشه اعمال می‌شه (برای مواردی مثل باسِ جهانی که به
    یه نقشه‌ی مشخص وصل نیست)."""
    neutral = NEUTRAL.get(effect_key, 1.0)
    pulse = get_active_pulse()
    if not pulse:
        return neutral
    target = get_pulse_target_map()
    if target and map_name and map_name != target:
        return neutral
    return pulse.get("effects", {}).get(effect_key, neutral)


def pulse_loot_bonus_chance(map_name: str) -> float:
    """شانسِ گرفتنِ یه «آیتمِ ضربان» اضافه (جدا از لوتِ عادی) وقتی تو نقشه‌ی
    هدفِ ضربانِ فعال بکشی و ضربان از نوعِ blessing باشه. اگه نقشه با هدفِ
    ضربان یکی نباشه یا ضربان curse/سراسری باشه، صفره."""
    pulse = get_active_pulse()
    if not pulse or pulse.get("kind") != "blessing":
        return 0.0
    if get_pulse_target_map() != map_name:
        return 0.0
    return {"common": 0.10, "rare": 0.16, "special": 0.22, "bomb": 0.20}.get(pulse.get("tier"), 0.08)


def _record_history(doc: dict, event: dict):
    doc.setdefault("history", []).append({
        "id": event["id"], "name": event["name"], "tier": event.get("tier", "common"),
        "at": time.time(), "corruption": doc.get("corruption", 50.0),
    })
    doc["history"] = doc["history"][-15:]


def _activate(doc: dict, event: dict, now: float):
    duration = event.get("duration", PULSE_DURATION)
    doc["active"] = event["id"]
    doc["expires_at"] = now + duration
    doc["last_check"] = now
    doc["last_event_id"] = event["id"]
    if event.get("tier") in ("common", "rare", "bomb"):
        from economy import MAPS_DATA
        doc["target_map"] = random.choice(list(MAPS_DATA.keys()))
    else:
        doc["target_map"] = None   # ویژه (void/light) از فسادِ کلِ دنیا میاد → سراسری می‌مونه
    if event.get("tier") == "special":
        doc["last_special_at"] = now
    if event.get("tier") == "bomb":
        doc["last_bomb_at"] = now
    _record_history(doc, event)
    _save(doc)
    return duration


async def maybe_trigger_pulse(bot) -> dict | None:
    doc = _doc()
    if doc.get("paused"):
        return None
    if doc.get("active") and doc.get("expires_at", 0) > time.time():
        return None  # یکی از قبل فعاله

    corruption = update_corruption(doc)
    now = time.time()

    # ─── لایه‌ی بمب — مستقل از فساد، خیلی کمیاب ───────────────
    if now - doc.get("last_bomb_at", 0) > BOMB_COOLDOWN_SEC and random.random() < BOMB_CHANCE:
        bomb = random.choice(BOMB_EVENTS)
        await _announce_bomb(bot, bomb)
        # فاصله‌ی «لرزش» تا «انفجارِ واقعی» — اثر تازه بعد از این فعال می‌شه
        await asyncio.sleep(BOMB_FUSE_SEC)
        doc = _doc()
        _activate(doc, bomb, time.time())
        await _announce(bot, bomb, bomb.get("duration", PULSE_DURATION), detonated=True)
        chain_type = _maybe_start_chain(doc, time.time())
        await _announce_chain(bot, chain_type)
        return bomb

    # ─── لایه‌ی ویژه — فقط در آستانه‌ی افراطیِ فساد ────────────
    if now - doc.get("last_special_at", 0) > SPECIAL_COOLDOWN_SEC:
        special = None
        if corruption >= SPECIAL_THRESHOLD_HIGH:
            special = SPECIAL_EVENTS["void"]
        elif corruption <= SPECIAL_THRESHOLD_LOW:
            special = SPECIAL_EVENTS["light"]
        if special:
            duration = _activate(doc, special, now)
            await _announce(bot, special, duration)
            return special

    # ─── لایه‌ی معمولی/نادر ─────────────────────────────────────
    if random.random() > PULSE_CHANCE:
        doc["last_check"] = now
        _save(doc)
        return None

    event = _pick_pulse_event(corruption, doc.get("last_event_id"))
    duration = _activate(doc, event, now)
    await _announce(bot, event, duration)
    return event


async def force_trigger(bot, event_id: str) -> dict | None:
    """برای پنل ادمین: دستی یه ایونتِ خاص رو (از هر لایه‌ای) فورس می‌کنه."""
    event = next((e for e in _all_events() if e["id"] == event_id), None)
    if not event:
        return None
    doc = _doc()
    now = time.time()
    if event.get("tier") == "bomb":
        await _announce_bomb(bot, event)
        await asyncio.sleep(BOMB_FUSE_SEC)
        doc = _doc()
        duration = _activate(doc, event, time.time())
        await _announce(bot, event, duration, detonated=True)
        chain_type = _maybe_start_chain(doc, time.time())
        await _announce_chain(bot, chain_type)
        return event
    duration = _activate(doc, event, now)
    await _announce(bot, event, duration)
    return event


def set_paused(paused: bool):
    doc = _doc()
    doc["paused"] = paused
    _save(doc)


def adjust_corruption(delta: float) -> float:
    """برای پنل ادمین: دستی فسادِ جهان رو کم/زیاد می‌کنه (برای تستِ ایونت‌های ویژه)."""
    doc = _doc()
    doc["corruption"] = round(_clamp_corruption(doc.get("corruption", 50.0) + delta), 1)
    _save(doc)
    return doc["corruption"]


def clear_active(doc: dict | None = None):
    doc = doc or _doc()
    doc["active"] = None
    doc["expires_at"] = 0
    _save(doc)


def _effects_line(effects: dict) -> str:
    parts = []
    for key, val in effects.items():
        label = EFFECT_LABELS.get(key, key)
        if key == "loot_luck" or key == "crit_add":
            parts.append(f"{label} {val:+.0%}")
        else:
            parts.append(f"{label} ×{val:.2f}")
    return " | ".join(parts)


async def _announce_bomb(bot, event: dict):
    """مرحله‌ی اول — فقط یه هشدارِ «لرزش»، بدون فعال‌کردنِ اثر."""
    from database import all_players
    text = (
        f"⚠️ **لرزش‌های عجیبی تو آبیس حس می‌شه...**\n\n"
        f"چیزی بزرگ داره شکل می‌گیره — انگار خودِ دنیا داره نفس می‌کِشه.\n"
        f"تا **{BOMB_FUSE_SEC} ثانیه‌ی دیگه** یه چیزی منفجر می‌شه. 💣"
    )
    players = all_players()
    for pid in players:
        try:
            await bot.send_message(int(pid), text)
        except Exception:
            pass
        await asyncio.sleep(0.03)


async def _announce(bot, event: dict, duration: int, detonated: bool = False):
    from database import all_players
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.enums import ButtonStyle
    from economy import MAPS_DATA
    minutes = duration // 60
    header = "💥 **انفجار!**" if detonated else event["name"]
    prefix = f"{header}\n\n{event['name']}\n\n" if detonated else ""
    target_map = get_pulse_target_map()
    map_emoji = MAPS_DATA.get(target_map, {}).get("emoji", "🗺") if target_map else None
    if target_map:
        map_line = (
            f"🗺 **نقشه‌ی هدف: {map_emoji} {target_map}**\n"
            f"اثرِ این ضربان فقط رو همین نقشه‌ست — همین الان راه بیفت! 🏃\n\n"
        )
    else:
        map_line = "🌍 این ضربان **سراسریه** — روی کلِ دنیا اثر داره.\n\n"
    text = (
        f"{prefix}{event['desc']}\n\n"
        f"{map_line}"
        f"📊 {_effects_line(event.get('effects', {}))}\n\n"
        f"⏳ تا **{minutes} دقیقه‌ی دیگه** فعاله — همین الان با ⚔️ حمله یا 🗺 لوت ازش استفاده کن.\n"
        f"هر وقت خواستی وضعیتِ زنده‌ش رو ببینی: /pulse"
    )
    kb_rows = [
        [InlineKeyboardButton(
            text="وضعیتِ زندهٔ ضربان",
            callback_data="pulse:status",
            style=ButtonStyle.PRIMARY,
            icon_custom_emoji_id="5231200819986047254",  # 📊 از NEWS_EMOJI
        )]
    ]
    if target_map:
        # همون شماره‌ایندکسی که loot_handlers.py برای دکمه‌های سفر به نقشه استفاده می‌کنه
        # (lg:{i} روی MAP_LIST = list(MAPS_DATA.keys())) — چون هردو از یه MAPS_DATA
        # میان، ایندکس‌ها همیشه با هم هم‌خونی دارن.
        map_idx = list(MAPS_DATA.keys()).index(target_map)
        kb_rows.append([InlineKeyboardButton(
            text=f"🗺 برو به {map_emoji} {target_map}",
            callback_data=f"lg:{map_idx}",
            style=ButtonStyle.SUCCESS,
        )])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    players = all_players()
    for pid in players:
        try:
            await bot.send_message(int(pid), text, reply_markup=kb)
        except Exception:
            pass
        await asyncio.sleep(0.04)


async def world_pulse_loop(bot):
    while True:
        try:
            await maybe_trigger_pulse(bot)
        except Exception:
            pass
        await asyncio.sleep(CHECK_INTERVAL)


# ─── نمایشِ گیج — دیگه قلبِ سیاه/سفید نیست؛ یه نوارِ درجه‌ایِ رنگی ───
def _corruption_bar(v: float, length: int = 10) -> str:
    filled = int(round(v / 100 * length))
    filled = max(0, min(length, filled))
    if v >= SPECIAL_THRESHOLD_HIGH:
        fill = "🟥"
    elif v >= 60:
        fill = "🟧"
    elif v <= SPECIAL_THRESHOLD_LOW:
        fill = "🟦"
    elif v <= 40:
        fill = "🟩"
    else:
        fill = "🟨"
    return fill * filled + "⬛" * (length - filled)


def _corruption_label(v: float) -> str:
    if v >= SPECIAL_THRESHOLD_HIGH:
        return "🌑 آستانه‌ی طغیان (Void)"
    if v <= SPECIAL_THRESHOLD_LOW:
        return "✨ آستانه‌ی روشنایی (Light)"
    if v >= 60:
        return "🌘 رو به فساد"
    if v <= 40:
        return "🌗 رو به روشنایی"
    return "⚖️ در تعادل"


def pulse_status_text() -> str:
    doc = _doc()
    corruption = doc.get("corruption", 50.0)
    pulse = get_active_pulse()

    lines = [
        "⚡ **ضربانِ آبیس**\n",
        f"{_corruption_bar(corruption)}  {corruption:.0f}/100",
        f"{_corruption_label(corruption)}\n",
    ]
    if not pulse:
        lines.append("الان دنیا آرومه — هیچ ضربانِ فعالی نیست.")
    else:
        remain = int(doc["expires_at"] - time.time())
        mins = max(0, remain // 60)
        badge = TIER_BADGE.get(pulse.get("tier", "common"), "")
        target_map = doc.get("target_map")
        if target_map:
            from economy import MAPS_DATA
            map_emoji = MAPS_DATA.get(target_map, {}).get("emoji", "🗺")
            map_line = f"🗺 نقشه‌ی هدف: **{map_emoji} {target_map}**\n"
        else:
            map_line = "🌍 سراسری (روی کلِ دنیا)\n"
        lines.append(
            f"{badge}\n{pulse['name']}\n{pulse['desc']}\n\n"
            f"{map_line}"
            f"📊 {_effects_line(pulse.get('effects', {}))}\n\n"
            f"⏳ {mins} دقیقه مونده."
        )

    chain = get_chain_effect()
    if chain:
        chain_doc = doc.get("chain_effect", {})
        chain_remain = max(0, int(chain_doc.get("expires_at", 0) - time.time()) // 60)
        if chain == "nemesis_surge":
            lines.append(f"\n😡 **آبیس عصبانیه:** نمسیس‌ها تقویت شدن ({chain_remain} دقیقه مونده)")
        elif chain == "underground_surge":
            lines.append(f"\n😡 **آبیس عصبانیه:** جایزه‌ی حلقه‌ی سایه بالا رفته ({chain_remain} دقیقه مونده)")

    return "\n".join(lines)
