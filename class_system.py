# ============================================================
#  ASTRAL ABYSS RPG — Class & System Selection Engine
#  (class_system.py) — STAGE 1 / Core
# ============================================================
#
# این ماژول جایگزینِ کاملِ سیستمِ قدیمیِ «۳۵۰ کرکترِ رندوم» برای
# فرآیندِ ساختِ کاراکتره. به‌جای اینکه بازیکن یه کرکترِ آماده بگیره،
# حالا یه اسمِ دلخواه می‌ذاره و یکی از ۴ کلاس رو انتخاب می‌کنه — هرکلاس
# یه سیستمِ منبع/مکانیزم/اسکیلِ کاملاً جدا داره.
#
# نکته‌ی مهم دربارهٔ کاتانا: طبق تصمیمِ پروژه، سیستمِ کاتانا (katana_core /
# katana_system / katana_skills و بقیه) که قبلاً به «کرکترِ ۳۵۰تایی» گره
# خورده بود، در این مرحله منحصراً برای کلاسِ ماجراجو حفظ می‌شه. چون اون
# سیستم‌ها هنوز عمیقاً بر پایه‌ی ALL_CHARACTERS (از characters.py) کار
# می‌کنن، این ماژول برای ماجراجوها یه هویتِ کاتانا از همون استخر با
# assign_random_char() می‌گیره — ولی این دیگه به بازیکن به‌عنوانِ «انتخابِ
# کرکتر» نشون داده نمی‌شه؛ صرفاً موتورِ داخلیِ کاتاناست. سه کلاسِ دیگه
# اصلاً کاتانا/کرکتر نمی‌گیرن.
#
# محدودیتِ شناخته‌شده (Stage 1): ده‌ها فایلِ دیگه (combat, profile_card,
# shop, guild, ...) هنوز به player["character"] / ALL_CHARACTERS تکیه
# دارن و برای کلاس‌های غیر-ماجراجو ارور/رفتارِ نادرست می‌دن — این عمداً
# به مراحلِ بعدی موکول شده (طبق تأییدِ کارفرما).
# ============================================================

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ButtonStyle

# ─── شناسه‌های کلاس ────────────────────────────────────────────
CLASS_WIZARD     = "wizard"
CLASS_ADVENTURER = "adventurer"
CLASS_MERCHANT   = "merchant"
CLASS_HEALER     = "healer"

CLASS_ORDER = [CLASS_WIZARD, CLASS_ADVENTURER, CLASS_MERCHANT, CLASS_HEALER]


def _wizard_system_data() -> dict:
    """جادوگر → سیستمِ مانا و ترکیبِ طلسم (Spell Synergy)."""
    return {
        "mana": 50,
        "max_mana": 50,
        "mana_regen": 5,               # مانا در هر تیک ریجن
        "elements_known": ["fire"],     # عناصرِ بازشده: fire / water / lightning
        "synergy_combos_used": 0,       # چند بار عناصر رو ترکیب کرده (برای پیشرفتِ سینرژی)
        "mana_shield_charges": 0,
    }


def _adventurer_system_data() -> dict:
    """ماجراجو → سیستمِ اکسپلوریشن و رلیک (استامینا + شانسِ اکتشاف)."""
    return {
        "stamina": 100,
        "max_stamina": 100,
        "stamina_regen": 10,
        "exploration_luck": 5,          # شانسِ پیداکردنِ رلیک/فرارِ تله
        "relics_collected": [],
        "weapon_mastery": {},           # {weapon_type: mastery_xp} — Multi-Class Weapon Mastery
        "dungeons_cleared": 0,
    }


def _merchant_system_data() -> dict:
    """تاجر → سیستمِ اقتصاد و امپراتوریِ تجاری."""
    return {
        "market_influence": 0,
        "gold_multiplier": 1.0,         # ضریبِ درآمدِ طلا (با هَگل/کاروان بالا می‌ره)
        "caravans": [],                 # لیستِ کاروان‌های فعال
        "mercenaries_hired": [],        # مزدورهایی که برای کمک تو نبرد اجیر کرده
        "haggle_discount_pct": 5,
    }


def _healer_system_data() -> dict:
    """درمانگر → سیستمِ فیضِ الهی و ساپورت."""
    return {
        "faith": 40,
        "max_faith": 40,
        "faith_regen": 4,
        "hp_regen_bonus_pct": 10,       # ریجنِ HP اضافه‌ی مخصوصِ درمانگر
        "undead_purged": 0,
        "revives_available": 1,         # تعدادِ Self-Revive در دسترس
    }


def _abyss_avatar_system_data() -> dict:
    """🌌 آواتارِ آبیس → کلاسِ مخفیِ اولترا-نادر (secret_class_system.py).
    منبعش «انرژیِ آبیس»ه — ترکیبی از هر سه‌ی دیگه، ولی هیچ‌جا به بازیکن
    قبل از گرفتنش نشون داده نمی‌شه."""
    return {
        "abyss_energy": 100,
        "max_abyss_energy": 100,
        "abyss_energy_regen": 12,
        "corruption_resist": 25,
    }


# ─── جدولِ اصلیِ کلاس‌ها ────────────────────────────────────────
CLASSES = {
    CLASS_WIZARD: {
        "id": CLASS_WIZARD,
        "name_fa": "جادوگر",
        "name_en": "Wizard",
        "emoji": "🧙‍♂️",
        "tagline": "مانا و ترکیبِ عناصر",
        "system_desc": "سیستمِ مانا/انرژیِ آرکین + Spell Synergy (آتش، آب، رعد)",
        "resource_key": "mana",
        "resource_label_fa": "مانا",
        "base_stats": {"hp": 90, "max_hp": 90, "atk": 13, "def": 3},
        "system_data_fn": _wizard_system_data,
        "skills": ["burst_bolt", "mana_shield", "arcane_nova"],
        "skills_fa": ["🔥 ضربه‌ی آتشین (دمیجِ بالا)", "🛡 سپرِ مانا", "🌀 طوفانِ ناحیه‌ای (AoE)"],
        "grants_katana": False,
    },
    CLASS_ADVENTURER: {
        "id": CLASS_ADVENTURER,
        "name_fa": "ماجراجو",
        "name_en": "Adventurer",
        "emoji": "🗺️",
        "tagline": "اکتشاف و رلیک",
        "system_desc": "دخمه‌ها، فرار از تله، تسلط بر چند نوع سلاح و جمع‌آوریِ رلیک",
        "resource_key": "stamina",
        "resource_label_fa": "استامینا",
        "base_stats": {"hp": 110, "max_hp": 110, "atk": 11, "def": 6},
        "system_data_fn": _adventurer_system_data,
        "skills": ["swift_dodge", "treasure_hunter", "critical_strike"],
        "skills_fa": ["💨 جاخالیِ سریع", "🗝 گنج‌یاب", "🎯 ضربه‌ی بحرانی"],
        "grants_katana": True,   # تنها کلاسی که کاتانا می‌گیره
    },
    CLASS_MERCHANT: {
        "id": CLASS_MERCHANT,
        "name_fa": "تاجر",
        "name_en": "Merchant",
        "emoji": "💰",
        "tagline": "اقتصاد و امپراتوریِ تجاری",
        "system_desc": "حراج/تجارت، کاروان، نوسانِ قیمت و اجیرکردنِ مزدور برای نبرد",
        "resource_key": "gold_multiplier",
        "resource_label_fa": "نفوذِ بازار",
        "base_stats": {"hp": 85, "max_hp": 85, "atk": 8, "def": 5},
        "system_data_fn": _merchant_system_data,
        "skills": ["haggling", "mercenary_call", "bribe_enemy"],
        "skills_fa": ["🤝 چانه‌زنی (تخفیف/طلای اضافه)", "⚔️ فراخوانِ مزدور", "💸 رشوه به دشمن"],
        "grants_katana": False,
    },
    CLASS_HEALER: {
        "id": CLASS_HEALER,
        "name_fa": "درمانگر",
        "name_en": "Healer",
        "emoji": "✨",
        "tagline": "فیضِ الهی و ساپورت",
        "system_desc": "ریجنِ HP، باف/دیباف، پاکسازیِ مردگانِ متحرک، Revive/Self-Heal در نبرد",
        "resource_key": "faith",
        "resource_label_fa": "فیض",
        "base_stats": {"hp": 100, "max_hp": 100, "atk": 7, "def": 6},
        "system_data_fn": _healer_system_data,
        "skills": ["holy_light", "divine_shield", "purification"],
        "skills_fa": ["🌟 نورِ مقدس (دمیج به مردگان/هیل به خود)", "🛡 سپرِ الهی", "💧 پاکسازی"],
        "grants_katana": False,
    },

    # ─── 🌌 کلاسِ مخفیِ اولترا-نادر (secret_class_system.py) ──────────
    # عمداً تو CLASS_ORDER نیست — یعنی هیچ‌وقت تو کیبوردِ انتخابِ کلاس
    # دیده نمی‌شه. فقط با رولِ ۱٪ (SECRET_CLASS_CHANCE) موقعِ ساختِ
    # کاراکتر، جایگزینِ کلاسِ انتخابیِ بازیکن می‌شه.
    "abyss_avatar": {
        "id": "abyss_avatar",
        "name_fa": "آواتارِ آبیس",
        "name_en": "Abyss Avatar",
        "emoji": "🌌",
        "tagline": "چیزی که نباید وجود داشته باشه",
        "system_desc": "ترکیبِ هر سه‌ی دیگه در یه بدن — مانا، استامینا و فیض هم‌زمان، با استتِ پایه‌ی چند برابر",
        "resource_key": "abyss_energy",
        "resource_label_fa": "انرژیِ آبیس",
        "base_stats": {"hp": 220, "max_hp": 220, "atk": 26, "def": 16},
        "system_data_fn": _abyss_avatar_system_data,
        "skills": ["abyss_rend", "null_ward", "world_break"],
        "skills_fa": ["🌌 شکافِ آبیس (دمیجِ خام)", "🖤 سپرِ نیستی", "💥 شکستنِ واقعیت (اولتیمیت)"],
        "grants_katana": True,
        "secret": True,
    },
}


# ─── کیبوردِ انتخابِ کلاس ───────────────────────────────────────
def class_selection_kb() -> InlineKeyboardMarkup:
    rows = []
    for cid in CLASS_ORDER:
        c = CLASSES[cid]
        rows.append([InlineKeyboardButton(
            text=f"{c['emoji']} {c['name_fa']} — {c['tagline']}",
            callback_data=f"set_class:{cid}",
            style=ButtonStyle.PRIMARY,
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def class_selection_text() -> str:
    lines = ["⚜️ **حالا کلاسِ کاراکترت رو انتخاب کن — این تعیین‌کننده‌ی کل سبکِ بازیته:**\n"]
    for cid in CLASS_ORDER:
        c = CLASSES[cid]
        lines.append(f"{c['emoji']} **{c['name_fa']}** ({c['name_en']}) — {c['system_desc']}")
    return "\n".join(lines)


# ─── اعمالِ کلاس روی سندِ بازیکن ────────────────────────────────
def apply_class_to_player(player: dict, class_id: str) -> dict:
    """پروفایلِ بازیکن رو طبقِ اسکیمای درخواست‌شده برای کلاسِ انتخابی می‌سازه:
    level/xp/stats/class_system_data/skills/inventory. این تابع idempotent
    نیست عمداً — فقط یه‌بار موقعِ ساختِ کاراکتر صدا زده می‌شه."""
    c = CLASSES[class_id]

    player["class"] = class_id
    player["level"] = player.get("level", 1)
    player["xp"] = player.get("xp", 0)

    stats = dict(c["base_stats"])
    player["stats"] = stats
    # هم‌زمان فیلدهای تاپ-لولِ قدیمی (hp/max_hp) رو هم سینک می‌کنیم چون
    # ده‌ها فایلِ دیگه (combat, hp_regen, ...) هنوز مستقیم از این فیلدها
    # می‌خونن — این‌جا عمداً یه لایه‌ی سازگاری نگه داشته شده.
    player["hp"] = stats["hp"]
    player["max_hp"] = stats["max_hp"]

    player["class_system_data"] = c["system_data_fn"]()
    player["skills"] = list(c["skills"])
    player["inventory"] = player.get("inventory", [])

    return player


def class_card_text(player: dict) -> str:
    cid = player.get("class")
    c = CLASSES.get(cid)
    if not c:
        return "❌ هنوز کلاسی انتخاب نشده."
    csd = player.get("class_system_data", {})
    res_val = csd.get(c["resource_key"], "—")
    skills_block = "\n".join(f"  • {s}" for s in c.get("skills_fa", []))
    return (
        f"{c['emoji']} **{player.get('name','—')}** — {c['name_fa']} ({c['name_en']})\n"
        f"📊 سطح {player.get('level',1)} | ❤️ {player['stats']['hp']}/{player['stats']['max_hp']} | "
        f"⚔️ {player['stats']['atk']} | 🛡 {player['stats']['def']}\n"
        f"🔹 {c['resource_label_fa']}: {res_val}\n\n"
        f"**مهارت‌ها:**\n{skills_block}"
    )


def get_class(class_id: str) -> dict | None:
    return CLASSES.get(class_id)


# ─── 🐛 باگ‌فیکس: اسکیل‌شدنِ منبعِ کلاس با لول ──────────────────
# قبلاً max_mana/max_stamina/max_faith/max_abyss_energy فقط تو
# apply_class_to_player() (موقعِ ساختِ کاراکتر) مقداردهی می‌شدن و بعدش
# level_up_check() (تو bot.py و کپی‌هاش تو boss_handlers.py،
# collection_codex_handlers.py، gap_collection_codex_handlers.py) فقط
# max_hp رو زیاد می‌کرد — منبعِ کلاس (مانا/استامینا/فیض) هیچ‌وقت با
# لول رشد نمی‌کرد. این تابعِ مشترک باید تو هر ۴ مسیرِ لول‌آپ صدا زده بشه.

# رشدِ منبع در هر لول (فلت، هم‌سنگِ +۵ HP در هر لول)
RESOURCE_KEY_PER_CLASS = {
    CLASS_WIZARD:     ("mana",         "max_mana",         3),   # +۳ مانا در هر لول
    CLASS_ADVENTURER: ("stamina",      "max_stamina",      4),   # +۴ استامینا در هر لول
    CLASS_MERCHANT:   (None,           None,               0),   # منبعِ تاجر عددی نیست (gold_multiplier)
    CLASS_HEALER:     ("faith",        "max_faith",         2),   # +۲ فیض در هر لول
    "abyss_avatar":   ("abyss_energy", "max_abyss_energy",  5),   # +۵ انرژیِ آبیس در هر لول
}


def scale_class_resource_on_levelup(player: dict, old_level: int, new_level: int) -> int:
    """موقعِ لول‌آپ صدا زده می‌شه (بعدِ اینکه player['level'] آپدیت شد).
    max_mana/max_stamina/max_faith/max_abyss_energy رو متناسب با تعدادِ
    لول‌هایی که رفته بالا زیاد می‌کنه و مقدارِ فعلی (mana/stamina/...) رو هم
    به همون اندازه پر می‌کنه (شبیهِ رفتارِ HP). خروجی: مقدارِ اضافه‌شده."""
    levels_gained = new_level - old_level
    if levels_gained <= 0:
        return 0

    class_id = player.get("class")
    key_cfg = RESOURCE_KEY_PER_CLASS.get(class_id)
    if not key_cfg or not key_cfg[0]:
        return 0

    cur_key, max_key, per_level = key_cfg
    gained = per_level * levels_gained

    csd = player.setdefault("class_system_data", {})
    csd[max_key] = csd.get(max_key, 0) + gained
    csd[cur_key] = csd.get(cur_key, 0) + gained  # موقعِ لول‌آپ منبع هم پر می‌شه، مثلِ HP

    return gained
