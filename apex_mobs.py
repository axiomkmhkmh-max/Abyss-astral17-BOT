# ============================================================
#  ASTRAL ABYSS — Apex Mobs 🌟 (هیولاهای امضادار فوق‌کمیاب)
# ------------------------------------------------------------
#  جدا از موبِ وحشیِ معمولی و جدا از نخبه‌ی رندومِ elite_mobs.py،
#  هر مپ یه Apex مخصوصِ خودش داره: یه هیولای دست‌ساز با اسم، لور و
#  ability ثابت (نه رندوم) — خیلی کمیاب‌تر از باسِ مپ نیست، ولی تو
#  لوتِ وحشیِ معمولی ظاهر می‌شه (بدونِ نیاز به چالشِ مستقیمِ باس).
#  کشتنش HP/دمیجِ نزدیک به باس می‌خواد ولی جایزه‌ش هم به همون اندازه
#  سنگینه — یه هدفِ جانبیِ نادر برای هر مپ.
# ============================================================
import random

APEX_CHANCE = 0.02  # ۲٪ شانس، هر بار که یه موجودِ وحشی قراره ظاهر بشه

APEX_MOBS = {
    "Verdant Vale": {
        "name": "کهن‌ریشه، جانِ جنگل", "emoji": "🌲", "weak": "آتش", "ability": "regenerating",
        "hp_mult": 0.55, "dmg_mult": 0.75, "reward_mult": 2.4,
        "lore": "قدیمی‌تر از خودِ جنگله؛ می‌گن هر درختِ این مپ یه شاخه از اونه. هر زخمی که بهش بزنی، تا طلوعِ بعدی خودش رو ترمیم می‌کنه.",
    },
    "Frostheim": {
        "name": "یخِ بی‌پایان", "emoji": "🧊", "weak": "آتش", "ability": "armored_hide",
        "hp_mult": 0.5, "dmg_mult": 0.7, "reward_mult": 2.3,
        "lore": "یه بلوکِ یخِ زنده که هزار زمستون تو دلش نگه داشته. پوستش سرده و سخت‌تر از هر فلزی.",
    },
    "Voidbreak Wastes": {
        "name": "چشمِ بی‌انتها", "emoji": "🌀", "weak": "نور", "ability": "cursed_gaze",
        "hp_mult": 0.5, "dmg_mult": 0.8, "reward_mult": 2.6,
        "lore": "یه شکافِ زنده تو خلأ که همه‌چیزو می‌بینه — حتی ضربه‌ی بعدیِ تو رو، قبل از اینکه بزنیش.",
    },
    "Emberhollow": {
        "name": "قلبِ مذاب", "emoji": "🔥", "weak": "یخ", "ability": "enrage",
        "hp_mult": 0.55, "dmg_mult": 0.85, "reward_mult": 2.5,
        "lore": "هسته‌ی زنده‌ی خودِ آتشفشان. هرچی کمتر ازش مونده باشه، خشمش سوزنده‌تره.",
    },
    "Dragonnest Peaks": {
        "name": "بال‌شکسته، آخرینِ نسل", "emoji": "🐉", "weak": "خلأ", "ability": "double_strike",
        "hp_mult": 0.6, "dmg_mult": 0.9, "reward_mult": 2.8,
        "lore": "بالش سال‌ها پیش تو یه جنگ شکست، ولی دو پنجه‌ش هنوز هم‌زمان می‌زنن.",
    },
    "Ruins of Orion-7": {
        "name": "هستهٔ سرکش OR-0", "emoji": "🖥️", "weak": "برق", "ability": "ironclad",
        "hp_mult": 0.5, "dmg_mult": 0.8, "reward_mult": 2.4,
        "lore": "آخرین پروتوتایپِ دفاعیِ Orion-7؛ زره‌ش هنوز داره از یه پروتکلِ فراموش‌شده دستور می‌گیره.",
    },
    "Dreadgate Citadel": {
        "name": "نگهبانِ دروازه‌ی هزارساله", "emoji": "😈", "weak": "نور", "ability": "vampiric",
        "hp_mult": 0.55, "dmg_mult": 0.85, "reward_mult": 2.5,
        "lore": "هزار سال جلوی دروازه ایستاده و از خونِ هر مهاجمی زنده مونده.",
    },
    "Stormward Archipelago": {
        "name": "چشمِ طوفانِ ابدی", "emoji": "🌪️", "weak": "زمین", "ability": "double_strike",
        "hp_mult": 0.5, "dmg_mult": 0.85, "reward_mult": 2.5,
        "lore": "مرکزِ یه طوفانی که هیچ‌وقت آروم نمی‌گیره — رعد و برقش دوتا-دوتا می‌زنه.",
    },
    "Holy Luminarchy": {
        "name": "سرافِ خاکستری", "emoji": "👼", "weak": "تاریکی", "ability": "cursed_gaze",
        "hp_mult": 0.55, "dmg_mult": 0.85, "reward_mult": 2.6,
        "lore": "نه کاملاً فرشته، نه کاملاً سقوط‌کرده — یه‌جایی وسطِ نور و تاریکی گیر افتاده و نگاهش هنوز مقدسه.",
    },
    "Clockwork Depths": {
        "name": "چرخ‌دنده‌ی صفر", "emoji": "⚙️", "weak": "برق", "ability": "armored_hide",
        "hp_mult": 0.5, "dmg_mult": 0.8, "reward_mult": 2.4,
        "lore": "اولین ماشینی که تو اعماقِ ساعت‌کاری ساخته شد؛ بدنش از فلزی‌ه که دیگه کسی نمی‌سازتش.",
    },
    "Azure Tides Empire": {
        "name": "لویاتانِ کوچک", "emoji": "🐋", "weak": "برق", "ability": "regenerating",
        "hp_mult": 0.6, "dmg_mult": 0.75, "reward_mult": 2.5,
        "lore": "بچه‌ی لویاتانِ اعماق — کوچیک‌تر از مادرش، ولی همون‌قدر سخت‌جون.",
    },
    "The Sunken City": {
        "name": "روحِ آخرینِ اهالی", "emoji": "👻", "weak": "مقدس", "ability": "vampiric",
        "hp_mult": 0.5, "dmg_mult": 0.8, "reward_mult": 2.4,
        "lore": "آخرین کسی که تو شهرِ غرق‌شده زنده موند، حالا فقط یه روحه که از هر جونِ تازه‌ای تغذیه می‌کنه.",
    },
    "Sands of Eternity": {
        "name": "فرعونِ بی‌نام", "emoji": "🏺", "weak": "آب", "ability": "thorned",
        "hp_mult": 0.5, "dmg_mult": 0.75, "reward_mult": 2.4,
        "lore": "اسمش از تاریخ پاک شده، ولی نفرینش هنوز رو مقبره‌ش زندست — هر ضربه‌ای مجازات داره.",
    },
    "Celestial Spire": {
        "name": "ناظرِ برجِ ستاره", "emoji": "🔭", "weak": "خلأ", "ability": "ironclad",
        "hp_mult": 0.55, "dmg_mult": 0.85, "reward_mult": 2.7,
        "lore": "از بالای برج، حرکتِ هر ستاره رو دیده — و یاد گرفته چطور جلوی هر ضربه‌ای رو بگیره.",
    },
    "Abyssal Black Market": {
        "name": "دلالِ سایه‌ها", "emoji": "🎭", "weak": "نور", "ability": "ambush_hunter",
        "hp_mult": 0.5, "dmg_mult": 0.85, "reward_mult": 2.6,
        "lore": "همیشه یه قدم جلوتره — تا اسلحه‌ت رو دربیاری، از سایه ضربه‌ش رو زده.",
    },
}


def maybe_spawn_apex(map_name: str, base_enemy: dict) -> dict:
    """
    شانسِ کمی هست که یه موجودِ وحشیِ معمولی، به‌جاش Apex Mob همون مپ
    ظاهر بشه. اگه شانس نیاد، دقیقاً همون base_enemy ورودی رو پس می‌ده.
    """
    apex = APEX_MOBS.get(map_name)
    if not apex or random.random() > APEX_CHANCE:
        return base_enemy

    src_hp  = max(base_enemy.get("hp", 100),  120)
    src_dmg = max(base_enemy.get("dmg", 15),  15)
    hp  = int(src_hp  * (10 + apex["hp_mult"] * 22))   # چند برابرِ موبِ معمولیِ مپ، در حدِ نزدیکِ باس
    dmg = int(src_dmg * (4 + apex["dmg_mult"] * 6))
    xp  = int(base_enemy.get("xp", 30)  * apex["reward_mult"] * 6)
    zen = int(base_enemy.get("zen", 25) * apex["reward_mult"] * 6)

    return {
        "name": f"🌟 {apex['emoji']} {apex['name']}",
        "hp": hp, "max_hp": hp, "dmg": dmg,
        "weak": apex["weak"], "tier": "legendary", "drop_chance": 1.0,
        "xp": xp, "zen": zen,
        "ability": apex["ability"],
        "is_apex": True,
        "is_boss": False,
        "lore": apex["lore"],
    }


def apex_intro_line(enemy: dict) -> str:
    """یه خطِ معرفیِ ویژه برای بالای صفحه‌ی نبرد، فقط وقتی enemy یه Apex باشه."""
    if not enemy.get("is_apex"):
        return ""
    return (
        f"🌟🌟🌟 **یک Apex نایاب ظاهر شد!** 🌟🌟🌟\n"
        f"_{enemy.get('lore', '')}_\n\n"
    )
