from aiogram.enums import ButtonStyle
# ============================================================
#  ASTRAL ABYSS — WORLD BOSS ENGINE (Multi-Phase, Elemental, Mechanics)
#  فایل منطق خالص — بدون aiogram import مستقیم (به‌جز InlineKeyboardMarkup
#  برای ساخت کیبورد که خروجی خودشه، نه هندلر)
# ============================================================
import random
import time
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from characters import ALL_CHARACTERS
from economy import bz_to_display
from logger import log_sync

# ================================================================
#  ELEMENT SYSTEM
# ================================================================
# هر کاراکتر یه فیلد آزاد "element" (فارسی، ~۹۰ مقدار متفاوت) داره که برای فلیور نوشته
# شده. این‌ها رو به ۸ عنصر ترکیبی (canonical) نگاشت می‌کنیم تا بشه رو weakness/resist
# باس حساب کرد، بدون اینکه مجبور باشیم دستی به ۹۰ کاراکتر یه فیلد جدید اضافه کنیم.

ELEMENT_META = {
    "fire":      {"name": "آتش",      "emoji": "🔥"},
    "ice":       {"name": "یخ",       "emoji": "❄️"},
    "lightning": {"name": "برق",      "emoji": "⚡"},
    "void":      {"name": "تاریکی/خلأ", "emoji": "🌑"},
    "holy":      {"name": "مقدس/نور", "emoji": "✨"},
    "nature":    {"name": "طبیعت/سم", "emoji": "🌿"},
    "arcane":    {"name": "کیهانی/آرکین", "emoji": "🔮"},
    "physical":  {"name": "فیزیکی",   "emoji": "⚔️"},
}

# ترتیب مهمه: اولین کیورد مچ‌شده برنده‌ست
_ELEMENT_KEYWORDS = [
    ("fire",      ["آتش", "ماگما", "انفجار", "غروب", "شعله", "قمری"]),
    ("ice",       ["یخ", "برفک", "برف", "یخچال", "سرما"]),
    ("lightning", ["برق", "صاعقه", "رعد", "الکتریک", "طوفان", "شوک"]),
    ("void",      ["خلأ", "سایه", "تاریک", "شب", "مغاک", "نفرین", "استخوان", "خون", "فراموشی"]),
    ("holy",      ["مقدس", "نور", "تابش", "خورشید", "شفق", "روشن"]),
    ("nature",    ["طبیعت", "سم", "خار", "جنگل", "مرداب", "زمین", "خاک", "شن", "گیاه"]),
    ("arcane",    ["فضا", "ذهن", "کیهان", "رویا", "کریستال", "کیمیا", "جاذبه",
                   "صدا", "مه", "دود", "ماه", "شیشه", "فلز", "آب", "باد", "نمک", "انرژی"]),
]

_element_cache: dict[str, str] = {}

def get_char_element(char_name: str) -> str:
    """عنصر ترکیبی یه کاراکتر رو برمی‌گردونه (fire/ice/.../physical)."""
    if char_name in _element_cache:
        return _element_cache[char_name]
    raw = ALL_CHARACTERS.get(char_name, {}).get("element", "")
    result = "physical"
    for canonical, keywords in _ELEMENT_KEYWORDS:
        if any(kw in raw for kw in keywords):
            result = canonical
            break
    _element_cache[char_name] = result
    return result

def element_tag(canonical: str) -> str:
    m = ELEMENT_META.get(canonical, ELEMENT_META["physical"])
    return f"{m['emoji']} {m['name']}"

# ================================================================
#  BOSS TEMPLATES  (هر باس = ۳ فاز، هر فاز مکانیک متفاوت)
# ================================================================
# مکانیک هر فاز یکی از این‌هاست:
#   "shield"  → باس یه سپر داره؛ اول باید سپر بشکنه بعد آسیب واقعی می‌خوره.
#               ضربه با عنصر ضعف فاز، ۲ برابر به سپر آسیب می‌زنه.
#               اگه سپر شکسته بشه ولی HP فاز هنوز صفر نشده، بعد از یه بازه، سپر دوباره شارژ میشه.
#   "area"    → هر چند وقت یه‌بار باس یه حمله ناحیه‌ای می‌زنه؛ بازیکن‌ها باید دکمه
#               "🛡 دفاع کن" رو تو بازه‌ی زمانی مشخص بزنن وگرنه HP واقعی‌شون کم میشه.
#   "enrage"  → یه تایمر جهانی داره؛ اگه فاز تا قبل از اون تموم نشه باس "خشمگین" میشه
#               (دمیج بیشتر میزنه + هر چند ثانیه به یه بازیکن رندوم دمیج می‌زنه) تا تموم شدن فاز.

WORLD_BOSS_TEMPLATES = {
    "abyss_sovereign": {
        "name": "👹 مائو، سرورِ آبیس (Maō)",
        "title": "لردِ شیطانیِ فسادِ آبیس",
        "intro": (
            "💀 *زمین می‌لرزد... شکافی سیاه باز می‌شود...*\n"
            "👹 **مائو (魔王)** — همون کسی که world_pulse (ضربانِ آبیس) رو تغذیه می‌کنه — "
            "شخصاً از اعماقِ آبیس ظهور کرد! این دیگه فقط یه سایه نیست."
        ),
        "total_hp": 9000,
        "speed_kill_seconds": 900,   # زیر ۱۵ دقیقه = پاداش سرعت
        "item_level": 55,
        "loot_item": {"name": "شمشیر سلطنت آبیس", "emoji": "🗡️", "slot": "weapon"},
        "phases": [
            {
                "name": "فاز ۱ — حلقه‌ی سایه",
                "hp_pct": 0.40,
                "weak": "holy", "resist": "void",
                "mechanic": "shield",
                "shield_pct": 0.30,        # سپر = ۳۰٪ HP این فاز
                "shield_regen_sec": 35,     # اگه سپر شکست ولی فاز تموم نشد، بعد این‌قدر دوباره شارژ میشه
                "enter_msg": "🛡 **مائو یه سپر تاریک دور خودش کشید!**\nتا سپر نشکنه، آسیب واقعی روش کار نمی‌کنه.\nعنصر {weak} روی سپر ۲ برابر آسیب می‌زنه!",
            },
            {
                "name": "فاز ۲ — خشم آبیس",
                "hp_pct": 0.35,
                "weak": "lightning", "resist": "arcane",
                "mechanic": "area",
                "area_interval_sec": 40,
                "area_window_sec": 15,
                "area_dmg_pct": 0.28,       # درصد از max_hp بازیکن اگه دفاع نکنه
                "enter_msg": "🌊 **مائو داره یه موج تاریکی جمع می‌کنه!**\nهر از گاهی وقتی گفت، سریع «🛡 دفاع کن» رو بزن وگرنه آسیب سنگین می‌خوری!",
            },
            {
                "name": "فاز ۳ — قلب آبیس",
                "hp_pct": 0.25,
                "weak": "fire", "resist": "ice",
                "mechanic": "enrage",
                "enrage_after_sec": 120,
                "enrage_tick_sec": 12,
                "enrage_dmg_pct": 0.10,
                "enter_msg": "⚠️ **آخرین فاز! مائو داره تمام قدرتش رو آزاد می‌کنه!**\nاگه سریع تمومش نکنید، خشمگین میشه و شروع می‌کنه به آسیب زدن رندوم!",
            },
        ],
    },

    "pyrothrax": {
        "name": "🐉 Pyrothrax",
        "title": "اژدهای شعله‌ی ابر Ember Hollow",
        "intro": "🔥 *آسمان سرخ می‌شود... غرشی زمین را می‌لرزاند...*\n🐉 **Pyrothrax** از دل Ember Hollow بیرون آمد!",
        "total_hp": 11000,
        "speed_kill_seconds": 1000,
        "item_level": 58,
        "loot_item": {"name": "دندانه شعله‌ی پیروترکس", "emoji": "⚔️", "slot": "weapon"},
        "phases": [
            {
                "name": "فاز ۱ — پوسته‌ی مذاب",
                "hp_pct": 0.35,
                "weak": "ice", "resist": "fire",
                "mechanic": "shield",
                "shield_pct": 0.35,
                "shield_regen_sec": 30,
                "enter_msg": "🛡 **Pyrothrax پوسته‌ی مذاب دور بدنش سفت کرد!**\nعنصر {weak} روی این پوسته ۲ برابر آسیب می‌زنه!",
            },
            {
                "name": "فاز ۲ — بارش شهاب",
                "hp_pct": 0.35,
                "weak": "nature", "resist": "arcane",
                "mechanic": "area",
                "area_interval_sec": 35,
                "area_window_sec": 14,
                "area_dmg_pct": 0.32,
                "enter_msg": "☄️ **Pyrothrax داره از آسمون شهاب می‌باره!**\nموقع هشدار سریع «🛡 دفاع کن» رو بزن!",
            },
            {
                "name": "فاز ۳ — خشم اژدها",
                "hp_pct": 0.30,
                "weak": "lightning", "resist": "holy",
                "mechanic": "enrage",
                "enrage_after_sec": 140,
                "enrage_tick_sec": 10,
                "enrage_dmg_pct": 0.12,
                "enter_msg": "⚠️ **Pyrothrax داره کاملاً خشمگین میشه!**\nهر ثانیه‌ای که می‌گذره خطرناک‌تر میشه!",
            },
        ],
    },

    "glacies_regina": {
        "name": "🧊 Glacies Regina",
        "title": "ملکه‌ی یخ Frostheim",
        "intro": "❄️ *بادی سرد همه‌جا را می‌گیرد... یخ زمین را می‌پوشاند...*\n🧊 **Glacies Regina** بر تخت یخی‌اش ظاهر شد!",
        "total_hp": 8000,
        "speed_kill_seconds": 800,
        "item_level": 52,
        "loot_item": {"name": "تاج بلورین ملکه‌ی یخ", "emoji": "👑", "slot": "helmet"},
        "phases": [
            {
                "name": "فاز ۱ — تاج یخی",
                "hp_pct": 0.40,
                "weak": "fire", "resist": "ice",
                "mechanic": "shield",
                "shield_pct": 0.25,
                "shield_regen_sec": 25,
                "enter_msg": "🛡 **Glacies Regina یه سپر یخی احضار کرد!**\nعنصر {weak} روی سپر ۲ برابر آسیب می‌زنه!",
            },
            {
                "name": "فاز ۲ — توفان تگرگ",
                "hp_pct": 0.35,
                "weak": "physical", "resist": "arcane",
                "mechanic": "area",
                "area_interval_sec": 30,
                "area_window_sec": 12,
                "area_dmg_pct": 0.25,
                "enter_msg": "🌨️ **توفان تگرگ شروع شد!**\nسریع «🛡 دفاع کن» رو بزن وگرنه یخ می‌زنی!",
            },
            {
                "name": "فاز ۳ — دل منجمد",
                "hp_pct": 0.25,
                "weak": "lightning", "resist": "holy",
                "mechanic": "enrage",
                "enrage_after_sec": 100,
                "enrage_tick_sec": 12,
                "enrage_dmg_pct": 0.10,
                "enter_msg": "⚠️ **آخرین لحظات! Glacies Regina داره منجمد و خطرناک‌تر میشه!**",
            },
        ],
    },

    # ============================================================
    #  ۱۷ باسِ جدید — تا مجموعاً ۲۰ باسِ جهانی داشته باشیم.
    #  ترتیبِ مکانیک‌ها بینشون عوض شده (بعضی‌ها enrage وسط دارن نه آخر)
    #  که مبارزه هر بار حس متفاوتی بده. HP از کم‌سخت به سخت‌ترین می‌ره.
    # ============================================================

    "tempestas_rex": {
        "name": "⚡ تمپستاس رکس",
        "title": "پادشاهِ توفانِ آسمانِ خاکستری",
        "intro": "⚡ *ابرها سیاه می‌شوند... صاعقه‌ای پیاپی زمین را می‌کوبد...*\n⚡ **تمپستاس رکس** از دلِ توفان فرود آمد!",
        "total_hp": 9500,
        "speed_kill_seconds": 950,
        "item_level": 55,
        "loot_item": {"name": "عصای صاعقه‌ی رکس", "emoji": "⚡", "slot": "weapon"},
        "phases": [
            {
                "name": "فاز ۱ — زره‌ی رعد", "hp_pct": 0.40,
                "weak": "nature", "resist": "lightning", "mechanic": "shield",
                "shield_pct": 0.30, "shield_regen_sec": 32,
                "enter_msg": "🛡 **تمپستاس رکس زره‌ای از رعد پوشید!**\nعنصر {weak} روی زره‌ش ۲ برابر آسیب می‌زنه!",
            },
            {
                "name": "فاز ۲ — بارانِ صاعقه", "hp_pct": 0.35,
                "weak": "fire", "resist": "arcane", "mechanic": "area",
                "area_interval_sec": 38, "area_window_sec": 14, "area_dmg_pct": 0.28,
                "enter_msg": "🌩️ **صاعقه‌ها از آسمون می‌بارن!**\nموقع هشدار سریع «🛡 دفاع کن» رو بزن!",
            },
            {
                "name": "فاز ۳ — چشمِ توفان", "hp_pct": 0.25,
                "weak": "ice", "resist": "holy", "mechanic": "enrage",
                "enrage_after_sec": 115, "enrage_tick_sec": 11, "enrage_dmg_pct": 0.11,
                "enter_msg": "⚠️ **تمپستاس رکس وارد چشمِ توفان شد! خشمش داره اوج می‌گیره!**",
            },
        ],
    },

    "umbra_matriarch": {
        "name": "🕷 اربرا، مادرِ سایه‌ها",
        "title": "ملکه‌ی تارهای تاریکی",
        "intro": "🕸️ *تارهایی از دلِ سیاهی بیرون می‌زنند...*\n🕷 **اربرا** از سقفِ مغاک آویزان شد!",
        "total_hp": 9800,
        "speed_kill_seconds": 980,
        "item_level": 56,
        "loot_item": {"name": "حلقه‌ی هشت‌چشم", "emoji": "💍", "slot": "ring"},
        "phases": [
            {
                "name": "فاز ۱ — تارِ سمی", "hp_pct": 0.40,
                "weak": "holy", "resist": "void", "mechanic": "area",
                "area_interval_sec": 34, "area_window_sec": 13, "area_dmg_pct": 0.30,
                "enter_msg": "🕸️ **اربرا داره یه تارِ سمی می‌تنه!**\nسریع «🛡 دفاع کن» رو بزن وگرنه مسموم می‌شی!",
            },
            {
                "name": "فاز ۲ — پیله‌ی تاریکی", "hp_pct": 0.35,
                "weak": "fire", "resist": "nature", "mechanic": "shield",
                "shield_pct": 0.28, "shield_regen_sec": 28,
                "enter_msg": "🛡 **اربرا خودش رو تو یه پیله پیچید!**\nعنصر {weak} روی پیله ۲ برابر آسیب می‌زنه!",
            },
            {
                "name": "فاز ۳ — هجومِ نهایی", "hp_pct": 0.25,
                "weak": "lightning", "resist": "arcane", "mechanic": "enrage",
                "enrage_after_sec": 110, "enrage_tick_sec": 10, "enrage_dmg_pct": 0.12,
                "enter_msg": "⚠️ **اربرا وحشیانه هجوم آورد! زودتر تمومش کنید!**",
            },
        ],
    },

    "seraphine_ordo": {
        "name": "😇 سرافینِ داوری",
        "title": "فرشته‌ی سقوط‌کرده‌ی نظمِ مقدس",
        "intro": "✨ *نوری خیره‌کننده آسمان را می‌شکافد...*\n😇 **سرافینِ داوری** برای محاکمه‌ی آبیس فرود آمد!",
        "total_hp": 10200,
        "speed_kill_seconds": 1000,
        "item_level": 57,
        "loot_item": {"name": "شمشیرِ داوریِ سرافین", "emoji": "🗡️", "slot": "weapon"},
        "phases": [
            {
                "name": "فاز ۱ — هاله‌ی نور", "hp_pct": 0.40,
                "weak": "void", "resist": "holy", "mechanic": "shield",
                "shield_pct": 0.32, "shield_regen_sec": 30,
                "enter_msg": "🛡 **سرافین یه هاله‌ی نورانی دورش کشید!**\nعنصر {weak} روی هاله ۲ برابر آسیب می‌زنه!",
            },
            {
                "name": "فاز ۲ — خشمِ داوری", "hp_pct": 0.30,
                "weak": "nature", "resist": "arcane", "mechanic": "enrage",
                "enrage_after_sec": 100, "enrage_tick_sec": 9, "enrage_dmg_pct": 0.11,
                "enter_msg": "⚠️ **سرافین حکمِ نهایی رو صادر کرد! داره خشمگین می‌شه!**",
            },
            {
                "name": "فاز ۳ — بارشِ نور", "hp_pct": 0.30,
                "weak": "fire", "resist": "ice", "mechanic": "area",
                "area_interval_sec": 36, "area_window_sec": 14, "area_dmg_pct": 0.30,
                "enter_msg": "☀️ **بارشِ نورِ سوزان شروع شد!**\nموقع هشدار «🛡 دفاع کن» رو بزن!",
            },
        ],
    },

    "sylvanroot_ancient": {
        "name": "🌳 سیلوان‌روتِ باستانی",
        "title": "درختِ کهن‌سالِ جنگلِ فراموش‌شده",
        "intro": "🌲 *ریشه‌هایی عظیم زمین را می‌شکافند...*\n🌳 **سیلوان‌روت** از خوابِ هزارساله بیدار شد!",
        "total_hp": 9600,
        "speed_kill_seconds": 960,
        "item_level": 55,
        "loot_item": {"name": "زره‌ی پوستِ سیلوان", "emoji": "🛡️", "slot": "armor"},
        "phases": [
            {
                "name": "فاز ۱ — ریشه‌های خشمگین", "hp_pct": 0.40,
                "weak": "fire", "resist": "nature", "mechanic": "area",
                "area_interval_sec": 40, "area_window_sec": 15, "area_dmg_pct": 0.27,
                "enter_msg": "🌿 **ریشه‌ها از زیرِ زمین بیرون می‌زنن!**\nموقع هشدار سریع «🛡 دفاع کن» رو بزن!",
            },
            {
                "name": "فاز ۲ — پوسته‌ی سنگی", "hp_pct": 0.35,
                "weak": "ice", "resist": "physical", "mechanic": "shield",
                "shield_pct": 0.30, "shield_regen_sec": 33,
                "enter_msg": "🛡 **سیلوان‌روت پوسته‌ای سنگی رشد داد!**\nعنصر {weak} روی پوسته ۲ برابر آسیب می‌زنه!",
            },
            {
                "name": "فاز ۳ — خشمِ جنگل", "hp_pct": 0.25,
                "weak": "arcane", "resist": "holy", "mechanic": "enrage",
                "enrage_after_sec": 120, "enrage_tick_sec": 12, "enrage_dmg_pct": 0.10,
                "enter_msg": "⚠️ **سیلوان‌روت داره کاملاً بیدار می‌شه! خطرناک‌تر می‌شه!**",
            },
        ],
    },

    "astral_cartographer": {
        "name": "🔭 نقشه‌بردارِ اختری",
        "title": "ناظرِ راه‌های میان‌کهکشانی",
        "intro": "🌌 *فضا به‌طرزِ عجیبی خم می‌شود...*\n🔭 **نقشه‌بردارِ اختری** از شکافِ بُعدی بیرون اومد!",
        "total_hp": 10500,
        "speed_kill_seconds": 1020,
        "item_level": 58,
        "loot_item": {"name": "عصای نقشه‌ی کیهانی", "emoji": "🔮", "slot": "weapon"},
        "phases": [
            {
                "name": "فاز ۱ — میدانِ اختری", "hp_pct": 0.40,
                "weak": "physical", "resist": "arcane", "mechanic": "shield",
                "shield_pct": 0.33, "shield_regen_sec": 27,
                "enter_msg": "🛡 **نقشه‌بردار یه میدانِ محافظِ اختری کشید!**\nعنصر {weak} روش ۲ برابر آسیب می‌زنه!",
            },
            {
                "name": "فاز ۲ — پارگیِ فضا", "hp_pct": 0.35,
                "weak": "void", "resist": "holy", "mechanic": "area",
                "area_interval_sec": 33, "area_window_sec": 13, "area_dmg_pct": 0.31,
                "enter_msg": "🌀 **فضا داره پاره می‌شه!**\nسریع «🛡 دفاع کن» رو بزن!",
            },
            {
                "name": "فاز ۳ — فروپاشیِ بُعدی", "hp_pct": 0.25,
                "weak": "lightning", "resist": "nature", "mechanic": "enrage",
                "enrage_after_sec": 105, "enrage_tick_sec": 10, "enrage_dmg_pct": 0.12,
                "enter_msg": "⚠️ **بُعدها دارن فرومی‌پاشن! سریع‌تر باشید!**",
            },
        ],
    },

    "ferrum_juggernaut": {
        "name": "🤖 فرومِ جاگرنات",
        "title": "کولوسوسِ آهنینِ کارخانه‌ی متروک",
        "intro": "⚙️ *صدای فلز روی فلز می‌پیچد...*\n🤖 **فرومِ جاگرنات** از دلِ کارخانه‌ی متروک بیدار شد!",
        "total_hp": 10000,
        "speed_kill_seconds": 1000,
        "item_level": 57,
        "loot_item": {"name": "دستکشِ فشارِ فرومی", "emoji": "🧤", "slot": "gloves"},
        "phases": [
            {
                "name": "فاز ۱ — بدنه‌ی زرهی", "hp_pct": 0.40,
                "weak": "lightning", "resist": "physical", "mechanic": "shield",
                "shield_pct": 0.35, "shield_regen_sec": 25,
                "enter_msg": "🛡 **فروم بدنه‌شو کاملاً زرهی کرد!**\nعنصر {weak} روش ۲ برابر آسیب می‌زنه!",
            },
            {
                "name": "فاز ۲ — بمبارانِ گلوله", "hp_pct": 0.35,
                "weak": "fire", "resist": "ice", "mechanic": "area",
                "area_interval_sec": 30, "area_window_sec": 12, "area_dmg_pct": 0.33,
                "enter_msg": "💥 **فروم داره گلوله شلیک می‌کنه!**\nسریع «🛡 دفاع کن» رو بزن!",
            },
            {
                "name": "فاز ۳ — اضافه‌بارِ هسته", "hp_pct": 0.25,
                "weak": "arcane", "resist": "nature", "mechanic": "enrage",
                "enrage_after_sec": 95, "enrage_tick_sec": 9, "enrage_dmg_pct": 0.13,
                "enter_msg": "⚠️ **هسته‌ی فروم داره اضافه‌بار می‌کنه! خطرناک‌ترین لحظه‌ست!**",
            },
        ],
    },

    "korvexia_venom_queen": {
        "name": "🐍 کوروکسیا، ملکه‌ی زهر",
        "title": "هیدرای هفت‌سرِ مردابِ سیاه",
        "intro": "☠️ *بخاری سبز از مرداب بلند می‌شود...*\n🐍 **کوروکسیا** از اعماقِ مرداب بیرون خزید!",
        "total_hp": 11500,
        "speed_kill_seconds": 1100,
        "item_level": 59,
        "loot_item": {"name": "چکمه‌ی گامِ زهرآگین", "emoji": "🥾", "slot": "boots"},
        "phases": [
            {
                "name": "فاز ۱ — نفسِ زهرآگین", "hp_pct": 0.40,
                "weak": "lightning", "resist": "nature", "mechanic": "area",
                "area_interval_sec": 37, "area_window_sec": 14, "area_dmg_pct": 0.29,
                "enter_msg": "☠️ **کوروکسیا داره زهر می‌پاشه!**\nموقع هشدار «🛡 دفاع کن» رو بزن!",
            },
            {
                "name": "فاز ۲ — پوستِ فلسی", "hp_pct": 0.35,
                "weak": "fire", "resist": "void", "mechanic": "shield",
                "shield_pct": 0.29, "shield_regen_sec": 31,
                "enter_msg": "🛡 **فلس‌های کوروکسیا سفت شدن!**\nعنصر {weak} روشون ۲ برابر آسیب می‌زنه!",
            },
            {
                "name": "فاز ۳ — خشمِ هفت‌سر", "hp_pct": 0.25,
                "weak": "holy", "resist": "arcane", "mechanic": "enrage",
                "enrage_after_sec": 118, "enrage_tick_sec": 11, "enrage_dmg_pct": 0.11,
                "enter_msg": "⚠️ **همه‌ی سرهای کوروکسیا هم‌زمان خشمگین شدن!**",
            },
        ],
    },

    "thanotep_reaper": {
        "name": "💀 تاناتپ، دروگرِ ارواح",
        "title": "قاصدِ خاموشیِ ابدی",
        "intro": "🕯️ *شمع‌ها یکی‌یکی خاموش می‌شوند...*\n💀 **تاناتپ** با داسی از استخوان ظاهر شد!",
        "total_hp": 12000,
        "speed_kill_seconds": 1150,
        "item_level": 60,
        "loot_item": {"name": "داسِ روحِ تاناتپ", "emoji": "⚔️", "slot": "weapon"},
        "phases": [
            {
                "name": "فاز ۱ — پرده‌ی مرگ", "hp_pct": 0.40,
                "weak": "holy", "resist": "void", "mechanic": "shield",
                "shield_pct": 0.34, "shield_regen_sec": 29,
                "enter_msg": "🛡 **تاناتپ یه پرده‌ی مرگ دورش کشید!**\nعنصر {weak} روش ۲ برابر آسیب می‌زنه!",
            },
            {
                "name": "فاز ۲ — احضارِ ارواح", "hp_pct": 0.30,
                "weak": "fire", "resist": "arcane", "mechanic": "enrage",
                "enrage_after_sec": 100, "enrage_tick_sec": 9, "enrage_dmg_pct": 0.13,
                "enter_msg": "⚠️ **تاناتپ داره ارواح احضار می‌کنه! خشمش بالا می‌ره!**",
            },
            {
                "name": "فاز ۳ — بادِ استخوان", "hp_pct": 0.30,
                "weak": "nature", "resist": "ice", "mechanic": "area",
                "area_interval_sec": 32, "area_window_sec": 13, "area_dmg_pct": 0.34,
                "enter_msg": "🦴 **بادی از استخوان و خاکستر می‌وزه!**\nسریع «🛡 دفاع کن» رو بزن!",
            },
        ],
    },

    "solisara_phoenix": {
        "name": "🔥 سولیسارا، ققنوسِ سپیده‌دم",
        "title": "پرنده‌ی جاودانِ آتش و نور",
        "intro": "🌅 *آسمان طلایی و سرخ می‌شود...*\n🔥 **سولیسارا** از میانِ شعله‌ها متولد شد!",
        "total_hp": 12500,
        "speed_kill_seconds": 1180,
        "item_level": 61,
        "loot_item": {"name": "گردنبندِ خاکسترِ جاودان", "emoji": "📿", "slot": "amulet"},
        "phases": [
            {
                "name": "فاز ۱ — بالِ شعله‌ور", "hp_pct": 0.40,
                "weak": "ice", "resist": "fire", "mechanic": "area",
                "area_interval_sec": 35, "area_window_sec": 14, "area_dmg_pct": 0.30,
                "enter_msg": "🔥 **سولیسارا بال‌هاشو باز کرد و شعله بارید!**\nموقع هشدار «🛡 دفاع کن» رو بزن!",
            },
            {
                "name": "فاز ۲ — نورِ سپیده", "hp_pct": 0.35,
                "weak": "void", "resist": "holy", "mechanic": "shield",
                "shield_pct": 0.31, "shield_regen_sec": 28,
                "enter_msg": "🛡 **سولیسارا خودش رو تو نور پیچید!**\nعنصر {weak} روش ۲ برابر آسیب می‌زنه!",
            },
            {
                "name": "فاز ۳ — تولدِ دوباره", "hp_pct": 0.25,
                "weak": "arcane", "resist": "physical", "mechanic": "enrage",
                "enrage_after_sec": 108, "enrage_tick_sec": 10, "enrage_dmg_pct": 0.12,
                "enter_msg": "⚠️ **سولیسارا داره از خاکستر دوباره متولد می‌شه!**",
            },
        ],
    },

    "glaciovorn_leviathan": {
        "name": "🐋 گلاسیورن، لویاتانِ اعماق",
        "title": "هیولای دریای یخ‌زده",
        "intro": "🌊 *امواجی یخ‌زده به ساحل می‌کوبند...*\n🐋 **گلاسیورن** از اعماقِ دریای یخ سر برآورد!",
        "total_hp": 13000,
        "speed_kill_seconds": 1200,
        "item_level": 62,
        "loot_item": {"name": "تاجِ موج‌های منجمد", "emoji": "👑", "slot": "helmet"},
        "phases": [
            {
                "name": "فاز ۱ — زره‌ی یخی", "hp_pct": 0.40,
                "weak": "fire", "resist": "ice", "mechanic": "shield",
                "shield_pct": 0.36, "shield_regen_sec": 26,
                "enter_msg": "🛡 **گلاسیورن پوسته‌ای از یخِ جاودان کشید!**\nعنصر {weak} روش ۲ برابر آسیب می‌زنه!",
            },
            {
                "name": "فاز ۲ — موجِ سهمگین", "hp_pct": 0.35,
                "weak": "lightning", "resist": "arcane", "mechanic": "area",
                "area_interval_sec": 34, "area_window_sec": 13, "area_dmg_pct": 0.32,
                "enter_msg": "🌊 **موجی عظیم داره میاد!**\nسریع «🛡 دفاع کن» رو بزن!",
            },
            {
                "name": "فاز ۳ — غرشِ اعماق", "hp_pct": 0.25,
                "weak": "holy", "resist": "nature", "mechanic": "enrage",
                "enrage_after_sec": 100, "enrage_tick_sec": 9, "enrage_dmg_pct": 0.13,
                "enter_msg": "⚠️ **گلاسیورن از اعماق غرید! داره خشمگین می‌شه!**",
            },
        ],
    },

    "voltarion_titan": {
        "name": "⚡ ولتاریون، تایتانِ رعد",
        "title": "غول‌آسای برخاسته از توفانِ ابدی",
        "intro": "⚡ *زمین زیرِ پا می‌لرزد...*\n⚡ **ولتاریون** با هر قدم رعد تولید می‌کنه!",
        "total_hp": 13500,
        "speed_kill_seconds": 1230,
        "item_level": 63,
        "loot_item": {"name": "زرهِ رعدِ ولتاریون", "emoji": "🥋", "slot": "armor"},
        "phases": [
            {
                "name": "فاز ۱ — قدم‌های رعد", "hp_pct": 0.40,
                "weak": "nature", "resist": "lightning", "mechanic": "area",
                "area_interval_sec": 30, "area_window_sec": 12, "area_dmg_pct": 0.34,
                "enter_msg": "⚡ **هر قدمِ ولتاریون رعد می‌فرسته!**\nسریع «🛡 دفاع کن» رو بزن!",
            },
            {
                "name": "فاز ۲ — زره‌ی الکتریکی", "hp_pct": 0.35,
                "weak": "ice", "resist": "physical", "mechanic": "shield",
                "shield_pct": 0.33, "shield_regen_sec": 27,
                "enter_msg": "🛡 **ولتاریون زره‌ای الکتریکی فعال کرد!**\nعنصر {weak} روش ۲ برابر آسیب می‌زنه!",
            },
            {
                "name": "فاز ۳ — تخلیه‌ی نهایی", "hp_pct": 0.25,
                "weak": "void", "resist": "holy", "mechanic": "enrage",
                "enrage_after_sec": 95, "enrage_tick_sec": 8, "enrage_dmg_pct": 0.14,
                "enter_msg": "⚠️ **ولتاریون داره کل انرژیشو تخلیه می‌کنه! خطرناک‌ترین لحظه‌ست!**",
            },
        ],
    },

    "obscura_veil_empress": {
        "name": "🌑 آبسکورا، ملکه‌ی پرده‌ی سیاه",
        "title": "فرمانروای دنیای میانِ سایه‌ها",
        "intro": "🌑 *نور به‌آرومی از دنیا می‌ره...*\n🌑 **آبسکورا** با پرده‌ای از تاریکیِ محض وارد شد!",
        "total_hp": 14000,
        "speed_kill_seconds": 1260,
        "item_level": 64,
        "loot_item": {"name": "حلقه‌ی پرده‌ی ابدی", "emoji": "💍", "slot": "ring"},
        "phases": [
            {
                "name": "فاز ۱ — پرده‌ی محافظ", "hp_pct": 0.40,
                "weak": "holy", "resist": "void", "mechanic": "shield",
                "shield_pct": 0.35, "shield_regen_sec": 25,
                "enter_msg": "🛡 **آبسکورا پشتِ پرده‌ی تاریکی پنهون شد!**\nعنصر {weak} روش ۲ برابر آسیب می‌زنه!",
            },
            {
                "name": "فاز ۲ — خشمِ سایه", "hp_pct": 0.30,
                "weak": "fire", "resist": "arcane", "mechanic": "enrage",
                "enrage_after_sec": 90, "enrage_tick_sec": 8, "enrage_dmg_pct": 0.14,
                "enter_msg": "⚠️ **آبسکورا کنترلشو از دست داد! خشمگین شد!**",
            },
            {
                "name": "فاز ۳ — بارشِ سایه", "hp_pct": 0.30,
                "weak": "lightning", "resist": "nature", "mechanic": "area",
                "area_interval_sec": 28, "area_window_sec": 11, "area_dmg_pct": 0.35,
                "enter_msg": "🌑 **سایه‌ها از هر طرف می‌بارن!**\nسریع «🛡 دفاع کن» رو بزن!",
            },
        ],
    },

    "terra_behemoth": {
        "name": "🦣 تراوث، بهیموتِ خاک",
        "title": "کوهی که راه می‌رود",
        "intro": "🏔️ *زمین زیرِ پاهاش می‌شکافه...*\n🦣 **تراوث** از دلِ کوه بیرون اومد!",
        "total_hp": 14500,
        "speed_kill_seconds": 1300,
        "item_level": 65,
        "loot_item": {"name": "چکمه‌ی لرزشِ زمین", "emoji": "🥾", "slot": "boots"},
        "phases": [
            {
                "name": "فاز ۱ — کوبشِ خاک", "hp_pct": 0.40,
                "weak": "fire", "resist": "physical", "mechanic": "area",
                "area_interval_sec": 33, "area_window_sec": 13, "area_dmg_pct": 0.32,
                "enter_msg": "🏔️ **تراوث زمین رو می‌کوبه!**\nسریع «🛡 دفاع کن» رو بزن!",
            },
            {
                "name": "فاز ۲ — پوسته‌ی سنگی", "hp_pct": 0.35,
                "weak": "ice", "resist": "nature", "mechanic": "shield",
                "shield_pct": 0.34, "shield_regen_sec": 28,
                "enter_msg": "🛡 **پوستِ تراوث به سنگ تبدیل شد!**\nعنصر {weak} روش ۲ برابر آسیب می‌زنه!",
            },
            {
                "name": "فاز ۳ — خشمِ کوه", "hp_pct": 0.25,
                "weak": "arcane", "resist": "lightning", "mechanic": "enrage",
                "enrage_after_sec": 100, "enrage_tick_sec": 9, "enrage_dmg_pct": 0.13,
                "enter_msg": "⚠️ **تراوث کاملاً خشمگین شد! زمین زیرِ پاتون می‌لرزه!**",
            },
        ],
    },

    "infernus_warlord": {
        "name": "😈 اینفرنوس، سالارِ جهنم",
        "title": "فرمانده‌ی سپاهِ شعله‌های ابدی",
        "intro": "🔥 *دروازه‌ای از آتش باز می‌شود...*\n😈 **اینفرنوس** با سپاهی از شعله ظاهر شد!",
        "total_hp": 15000,
        "speed_kill_seconds": 1320,
        "item_level": 66,
        "loot_item": {"name": "شمشیرِ شعله‌ی جهنمی", "emoji": "🗡️", "slot": "weapon"},
        "phases": [
            {
                "name": "فاز ۱ — زره‌ی مذاب", "hp_pct": 0.40,
                "weak": "ice", "resist": "fire", "mechanic": "shield",
                "shield_pct": 0.36, "shield_regen_sec": 24,
                "enter_msg": "🛡 **اینفرنوس زره‌ای مذاب پوشید!**\nعنصر {weak} روش ۲ برابر آسیب می‌زنه!",
            },
            {
                "name": "فاز ۲ — بارشِ آتش", "hp_pct": 0.35,
                "weak": "holy", "resist": "void", "mechanic": "area",
                "area_interval_sec": 30, "area_window_sec": 12, "area_dmg_pct": 0.35,
                "enter_msg": "🔥 **اینفرنوس داره از جهنم آتش می‌باره!**\nسریع «🛡 دفاع کن» رو بزن!",
            },
            {
                "name": "فاز ۳ — خشمِ سالار", "hp_pct": 0.25,
                "weak": "nature", "resist": "arcane", "mechanic": "enrage",
                "enrage_after_sec": 90, "enrage_tick_sec": 8, "enrage_dmg_pct": 0.15,
                "enter_msg": "⚠️ **اینفرنوس کاملاً خشمگین شد! خطرناک‌ترین لحظه‌ست!**",
            },
        ],
    },

    "celestine_guardian": {
        "name": "✨ سلستین، نگهبانِ سپیده",
        "title": "ساختارِ مقدسِ فراموش‌شده",
        "intro": "✨ *نوری از دلِ خرابه‌های باستانی می‌تابد...*\n✨ **سلستین** بعد از قرن‌ها بیدار شد!",
        "total_hp": 15500,
        "speed_kill_seconds": 1350,
        "item_level": 67,
        "loot_item": {"name": "سپرِ نورِ سلستین", "emoji": "🛡️", "slot": "armor"},
        "phases": [
            {
                "name": "فاز ۱ — بارشِ نور", "hp_pct": 0.40,
                "weak": "void", "resist": "holy", "mechanic": "area",
                "area_interval_sec": 32, "area_window_sec": 13, "area_dmg_pct": 0.33,
                "enter_msg": "✨ **سلستین داره نورِ سوزان می‌باره!**\nسریع «🛡 دفاع کن» رو بزن!",
            },
            {
                "name": "فاز ۲ — سپرِ مقدس", "hp_pct": 0.35,
                "weak": "nature", "resist": "arcane", "mechanic": "shield",
                "shield_pct": 0.35, "shield_regen_sec": 26,
                "enter_msg": "🛡 **سلستین یه سپرِ مقدس فعال کرد!**\nعنصر {weak} روش ۲ برابر آسیب می‌زنه!",
            },
            {
                "name": "فاز ۳ — خشمِ سپیده", "hp_pct": 0.25,
                "weak": "fire", "resist": "ice", "mechanic": "enrage",
                "enrage_after_sec": 95, "enrage_tick_sec": 9, "enrage_dmg_pct": 0.14,
                "enter_msg": "⚠️ **سلستین آخرین دفاعشو فعال کرد! خطرناک‌تر می‌شه!**",
            },
        ],
    },

    "astral_devourer": {
        "name": "🌌 استرال، بلعنده‌ی کهکشان‌ها",
        "title": "موجودی از فراسوی واقعیت",
        "intro": "🌀 *واقعیت به‌طرزِ ناخوشایندی می‌پیچد...*\n🌌 **استرال** از بیرونِ این جهان وارد شد!",
        "total_hp": 16000,
        "speed_kill_seconds": 1400,
        "item_level": 69,
        "loot_item": {"name": "گردنبندِ بلعِ کیهانی", "emoji": "📿", "slot": "amulet"},
        "phases": [
            {
                "name": "فاز ۱ — میدانِ واقعیت", "hp_pct": 0.40,
                "weak": "physical", "resist": "arcane", "mechanic": "shield",
                "shield_pct": 0.37, "shield_regen_sec": 24,
                "enter_msg": "🛡 **استرال میدانی از واقعیتِ خم‌شده کشید!**\nعنصر {weak} روش ۲ برابر آسیب می‌زنه!",
            },
            {
                "name": "فاز ۲ — بلعِ ستاره‌ها", "hp_pct": 0.30,
                "weak": "lightning", "resist": "void", "mechanic": "enrage",
                "enrage_after_sec": 85, "enrage_tick_sec": 8, "enrage_dmg_pct": 0.15,
                "enter_msg": "⚠️ **استرال داره ستاره‌ها رو می‌بلعه! خشمش بالا می‌ره!**",
            },
            {
                "name": "فاز ۳ — فروپاشیِ کیهانی", "hp_pct": 0.30,
                "weak": "holy", "resist": "nature", "mechanic": "area",
                "area_interval_sec": 28, "area_window_sec": 11, "area_dmg_pct": 0.36,
                "enter_msg": "🌌 **فضا-زمان داره فرومی‌پاشه!**\nسریع «🛡 دفاع کن» رو بزن!",
            },
        ],
    },

    "nyx_absolute": {
        "name": "🖤 نیکس، تاریکیِ مطلق",
        "title": "ذاتِ خالصِ نیستی — آخرینِ باسِ آبیس",
        "intro": (
            "🖤 *همه چیز برای یک لحظه محو می‌شود...*\n"
            "🖤 **نیکس** — چیزی که حتی world_pulse هم ازش می‌ترسه — بالاخره ظاهر شد. "
            "این آخرین و سخت‌ترین باسِ جهانِ آبیسه."
        ),
        "total_hp": 20000,
        "speed_kill_seconds": 1600,
        "item_level": 72,
        "loot_item": {"name": "تاجِ نیستیِ مطلق", "emoji": "👑", "slot": "helmet"},
        "phases": [
            {
                "name": "فاز ۱ — مرزِ نیستی", "hp_pct": 0.40,
                "weak": "holy", "resist": "void", "mechanic": "shield",
                "shield_pct": 0.38, "shield_regen_sec": 22,
                "enter_msg": "🛡 **نیکس مرزی از نیستی دورش کشید!**\nعنصر {weak} روش ۲ برابر آسیب می‌زنه!",
            },
            {
                "name": "فاز ۲ — بارشِ خلأ", "hp_pct": 0.35,
                "weak": "lightning", "resist": "arcane", "mechanic": "area",
                "area_interval_sec": 26, "area_window_sec": 10, "area_dmg_pct": 0.38,
                "enter_msg": "🖤 **خلأ داره از هر طرف می‌باره!**\nسریع «🛡 دفاع کن» رو بزن وگرنه محو می‌شی!",
            },
            {
                "name": "فاز ۳ — پایانِ همه‌چیز", "hp_pct": 0.25,
                "weak": "fire", "resist": "ice", "mechanic": "enrage",
                "enrage_after_sec": 80, "enrage_tick_sec": 7, "enrage_dmg_pct": 0.16,
                "enter_msg": "⚠️⚠️ **آخرین فاز! نیکس داره کل قدرتشو آزاد می‌کنه! این سخت‌ترین لحظه‌ی نبرده!**",
            },
        ],
    },
}

WEAK_MULT = 2.2
RESIST_MULT = 0.5

RANK_REWARDS_ZEN = [3500, 2000, 1200, 700, 500, 350, 300, 250, 200, 150]
PARTICIPATION_ZEN = 80
BONUS_TITLE_ZEN = 900
SPEED_KILL_BONUS_PCT = 0.15

# ─── باسِ هفته (Weekly Featured Boss) ───────────────────────────
# هر هفته یکی از باس‌های جهانی به‌عنوان «باسِ هفته» انتخاب می‌شه
# (weekly_rewards.py مسئولِ چرخوندنش هست). نفرِ اولِ دمیج‌کننده به
# این باسِ خاص، علاوه بر جایزه‌ی معمولی، یه آیتمِ اختصاصی هم می‌گیره
# که فقط تا آخرِ همون هفته قابل‌کسب‌کردنه.
# باگ‌فیکس: قبلاً همه‌ی این‌ها فقط رشته بودن و اسلاتشون به‌زور "relic" می‌شد
# (مثلاً تاجِ ملکه‌ی یخ باید تو اسلاتِ کلاهخود می‌رفت نه مصنوعه). حالا هر
# باس اسلاتِ درستِ خودشو داره.
WEEKLY_BOSS_EXCLUSIVE_ITEM = {
    "abyss_sovereign":       {"name": "مهرِ سلطنتِ آبیس", "emoji": "🌌", "slot": "relic"},
    "pyrothrax":             {"name": "خاکسترِ جاودانِ پیروترکس", "emoji": "🔥", "slot": "relic"},
    "glacies_regina":        {"name": "تاجِ یخیِ ملکه‌ی یخ", "emoji": "❄️", "slot": "helmet"},
    "tempestas_rex":         {"name": "بالِ توفانیِ رکس", "emoji": "⚡", "slot": "relic"},
    "umbra_matriarch":       {"name": "تارِ ابدیِ اربرا", "emoji": "🕸️", "slot": "relic"},
    "seraphine_ordo":        {"name": "پرِ سرافینِ داوری", "emoji": "🪽", "slot": "relic"},
    "sylvanroot_ancient":    {"name": "دانه‌ی جاودانِ سیلوان", "emoji": "🌰", "slot": "relic"},
    "astral_cartographer":   {"name": "نقشه‌ی راه‌های ممنوعه", "emoji": "🗺️", "slot": "relic"},
    "ferrum_juggernaut":     {"name": "هسته‌ی فرومیِ جاگرنات", "emoji": "⚙️", "slot": "relic"},
    "korvexia_venom_queen":  {"name": "دندانِ کوروکسیا", "emoji": "🐍", "slot": "relic"},
    "thanotep_reaper":       {"name": "ساعتِ شنیِ تاناتپ", "emoji": "⏳", "slot": "relic"},
    "solisara_phoenix":      {"name": "پرِ آتشینِ سولیسارا", "emoji": "🪶", "slot": "relic"},
    "glaciovorn_leviathan":  {"name": "مرواریدِ یخیِ لویاتان", "emoji": "🌊", "slot": "relic"},
    "voltarion_titan":       {"name": "هسته‌ی رعدِ ولتاریون", "emoji": "🌩️", "slot": "relic"},
    "obscura_veil_empress":  {"name": "پرده‌ی سیاهِ آبسکورا", "emoji": "🕳️", "slot": "relic"},
    "terra_behemoth":        {"name": "سنگِ قلبِ تراوث", "emoji": "🪨", "slot": "relic"},
    "infernus_warlord":      {"name": "نشانِ سالارِ جهنم", "emoji": "🔥", "slot": "relic"},
    "celestine_guardian":    {"name": "هسته‌ی نورِ سلستین", "emoji": "✨", "slot": "relic"},
    "astral_devourer":       {"name": "چشمِ بلعنده", "emoji": "🌀", "slot": "relic"},
    "nyx_absolute":          {"name": "قلبِ نیستیِ مطلق", "emoji": "🖤", "slot": "relic"},
}
WEEKLY_BOSS_BONUS_ZEN = 5000

def _build_weekly_trophy(tid: str) -> dict:
    """آیتمِ اختصاصیِ باسِ هفته رو می‌سازه (legendary، اسلاتِ درست، قابل‌اکیپ)."""
    from item_system import generate_item
    tpl = WEEKLY_BOSS_EXCLUSIVE_ITEM[tid]
    template = {"name": tpl["name"], "emoji": tpl["emoji"], "slot": tpl["slot"], "sell": 8000, "buy": 16000}
    lvl = WORLD_BOSS_TEMPLATES.get(tid, {}).get("item_level", 60)
    return generate_item(template, player_level=lvl, forced_rarity="legendary", drop_source="weekly_boss")

# ================================================================
#  BOSS LIFECYCLE
# ================================================================

def spawn_boss(template_id: str, chat_id: int) -> dict:
    tpl = WORLD_BOSS_TEMPLATES[template_id]
    boss = {
        "template_id": template_id,
        "name": tpl["name"],
        "title": tpl["title"],
        "chat_id": chat_id,
        "alive": True,
        "phase_index": 0,
        "spawn_time": time.time(),
        "contributors": {},   # uid -> stats
        "total_hp": tpl["total_hp"],
        "hp_cleared": 0,       # مجموع HP فازهای قبلی که تموم شدن (برای درصد کلی)
    }
    _start_phase(boss, 0)
    log_sync(
        f"👹 **BOSS SPAWNED**\n"
        f"🏷️ {tpl['name']} — {tpl['title']}\n"
        f"❤️ HP کل: {tpl['total_hp']:,}\n"
        f"📍 چت: {chat_id}",
        "BOSS"
    )
    return boss

def _phase_tpl(boss: dict) -> dict:
    tpl = WORLD_BOSS_TEMPLATES[boss["template_id"]]
    return tpl["phases"][boss["phase_index"]]

def _start_phase(boss: dict, phase_index: int):
    tpl = WORLD_BOSS_TEMPLATES[boss["template_id"]]
    phase = tpl["phases"][phase_index]
    phase_hp = int(tpl["total_hp"] * phase["hp_pct"])

    boss["phase_index"] = phase_index
    boss["phase_max_hp"] = phase_hp
    boss["hp"] = phase_hp
    boss["phase_start_time"] = time.time()
    boss["weak"] = phase["weak"]
    boss["resist"] = phase["resist"]
    boss["mechanic"] = phase["mechanic"]

    boss["shield_active"] = False
    boss["shield_hp"] = 0
    boss["shield_max"] = 0
    boss["shield_broken_at"] = 0

    boss["area_active"] = False
    boss["area_deadline"] = 0
    boss["area_next_at"] = 0
    boss["area_responses"] = {}
    boss["area_round"] = 0

    boss["enraged"] = False
    boss["enrage_at"] = 0
    boss["last_enrage_tick"] = 0

    if phase["mechanic"] == "shield":
        boss["shield_max"] = int(phase_hp * phase["shield_pct"])
        boss["shield_hp"] = boss["shield_max"]
        boss["shield_active"] = True
        
    elif phase["mechanic"] == "area":
        boss["area_next_at"] = time.time() + phase["area_interval_sec"]
    elif phase["mechanic"] == "enrage":
        boss["enrage_at"] = time.time() + phase["enrage_after_sec"]
    
    log_sync(
        f"🌀 **BOSS PHASE {phase_index+1}**\n"
        f"🏷️ {tpl['name']}\n"
        f"📌 {phase['name']}\n"
        f"⚔️ ضعف: {phase['weak']} | 🛡 مقاوم: {phase['resist']}\n"
        f"🔧 مکانیک: {phase['mechanic']}\n"
        f"❤️ HP فاز: {phase_hp:,}",
        "BOSS_PHASE"
    )

def is_last_phase(boss: dict) -> bool:
    tpl = WORLD_BOSS_TEMPLATES[boss["template_id"]]
    return boss["phase_index"] >= len(tpl["phases"]) - 1

def overall_hp_pct(boss: dict) -> float:
    total = boss["total_hp"]
    remaining = total - boss["hp_cleared"] - (boss["phase_max_hp"] - boss["hp"])
    return max(0.0, min(100.0, (remaining / total) * 100))

def _bump_contrib(boss: dict, uid: int, **kwargs):
    c = boss["contributors"].setdefault(str(uid), {
        "dmg": 0, "hits": 0, "shield_dmg": 0, "defended": 0, "failed_defense": 0,
    })
    for k, v in kwargs.items():
        c[k] = c.get(k, 0) + v

# ================================================================
#  ATTACK RESOLUTION
# ================================================================

def process_attack(boss: dict, uid: int, char_name: str, raw_dmg: int, amplify_bonus: float = 0.0) -> dict:
    """
    یه ضربه رو به باس اعمال می‌کنه. boss رو in-place تغییر میده.
    amplify_bonus: از katana_system.element_amplify_bonus(level) میاد — کاتانای بالاتر
    یعنی ضربه‌ی عنصر ضعف باس قوی‌تر میشه (پاداش پیشرفت کاتانا).
    خروجی: دیکشنری با اطلاعات لازم برای نمایش به کاربر.
    """
    result = {
        "element": get_char_element(char_name),
        "mult": 1.0,
        "shield_dmg": 0,
        "hp_dmg": 0,
        "shield_broken": False,
        "phase_cleared": False,
        "boss_killed": False,
        "phase_enter_msg": None,
    }

    elem = result["element"]
    mult = 1.0
    if elem == boss["weak"]:
        mult = WEAK_MULT + amplify_bonus
    elif elem == boss["resist"]:
        mult = RESIST_MULT
    result["mult"] = mult
    dmg = int(raw_dmg * mult)

    # اگه فاز خشمگین شده، باس چیزی از این کم نمی‌شه ولی خود مکانیک تغییر نمی‌کنه
    if boss.get("mechanic") == "shield" and boss.get("shield_active"):
        applied = min(dmg, boss["shield_hp"])
        boss["shield_hp"] -= applied
        result["shield_dmg"] = applied
        _bump_contrib(boss, uid, shield_dmg=applied, hits=1)
        if boss["shield_hp"] <= 0:
            boss["shield_active"] = False
            boss["shield_broken_at"] = time.time()
            result["shield_broken"] = True
        return _finalize(boss, result)

    # ضربه معمولی به HP واقعی فاز
    applied = min(dmg, boss["hp"])
    boss["hp"] -= applied
    result["hp_dmg"] = applied
    _bump_contrib(boss, uid, dmg=applied, hits=1)

    return _finalize(boss, result)

def _finalize(boss: dict, result: dict) -> dict:
    if boss["hp"] <= 0:
        boss["hp"] = 0
        boss["hp_cleared"] += boss["phase_max_hp"]
        if is_last_phase(boss):
            boss["alive"] = False
            result["boss_killed"] = True
        else:
            result["phase_cleared"] = True
            next_index = boss["phase_index"] + 1
            _start_phase(boss, next_index)
            tpl = WORLD_BOSS_TEMPLATES[boss["template_id"]]
            phase = tpl["phases"][next_index]
            result["phase_enter_msg"] = (
                f"🔔 **{phase['name']}** آغاز شد!\n" +
                phase["enter_msg"].format(weak=element_tag(phase["weak"]))
            )
    # اگه سپر تازه شکسته، دوباره شارژ مجدد رو زمان‌بندی کن (اگه فاز عوض نشده بود)
    elif result.get("shield_broken") and boss.get("mechanic") == "shield" and boss["hp"] > 0:
        phase = _phase_tpl(boss)
        boss["shield_regen_at"] = time.time() + phase.get("shield_regen_sec", 30)
    return result

# ================================================================
#  MECHANIC TICKING  (صدا زده میشه از watcher loop یا موقع هر تعامل)
# ================================================================

def tick_shield_regen(boss: dict) -> bool:
    """اگه زمان شارژ مجدد سپر رسیده، سپر رو دوباره فعال می‌کنه. True اگه اتفاق افتاد."""
    if boss.get("mechanic") != "shield" or boss.get("shield_active") or boss["hp"] <= 0:
        return False
    regen_at = boss.get("shield_regen_at", 0)
    if regen_at and time.time() >= regen_at:
        boss["shield_active"] = True
        boss["shield_max"] = int(boss["phase_max_hp"] * _phase_tpl(boss)["shield_pct"] * 0.6)
        boss["shield_hp"] = boss["shield_max"]
        boss["shield_regen_at"] = 0
        log_sync(
            f"🛡 **BOSS SHIELD REGEN**\n"
            f"🏷️ {boss['name']}\n"
            f"🛡 سپر دوباره شارژ شد: {boss['shield_hp']:,}/{boss['shield_max']:,}",
            "BOSS"
        )
        return True
    return False

def tick_area_attack(boss: dict) -> str | None:
    """
    چک می‌کنه آیا زمان شروع حمله ناحیه‌ای جدید رسیده، یا زمان resolve پنجره‌ی فعلی.
    خروجی: "open" اگه پنجره باز شد، "resolve" اگه باید resolve بشه، None اگه کاری نیست.
    """
    if boss.get("mechanic") != "area" or boss["hp"] <= 0:
        return None
    now = time.time()
    if not boss["area_active"] and boss.get("area_next_at", 0) and now >= boss["area_next_at"]:
        phase = _phase_tpl(boss)
        boss["area_active"] = True
        boss["area_round"] += 1
        boss["area_responses"] = {}
        boss["area_deadline"] = now + phase["area_window_sec"]
        return "open"
    if boss["area_active"] and now >= boss["area_deadline"]:
        return "resolve"
    return None

def resolve_area_attack(boss: dict) -> list[tuple[int, float]]:
    """پنجره‌ی حمله ناحیه‌ای رو می‌بنده و لیست (uid, dmg_pct) کسانی که دفاع نکردن رو برمی‌گردونه."""
    phase = _phase_tpl(boss)
    penalized = []
    for uid_str, c in boss["contributors"].items():
        uid = int(uid_str)
        if boss["area_responses"].get(uid_str):
            _bump_contrib(boss, uid, defended=1)
        else:
            _bump_contrib(boss, uid, failed_defense=1)
            penalized.append((uid, phase["area_dmg_pct"]))
    boss["area_active"] = False
    boss["area_next_at"] = time.time() + phase["area_interval_sec"]
    return penalized

def register_area_defense(boss: dict, uid: int) -> bool:
    if not boss.get("area_active"):
        return False
    boss["area_responses"][str(uid)] = True
    return True

def tick_enrage(boss: dict) -> str | None:
    """
    خروجی: "start" وقتی تازه خشمگین میشه، "tick" وقتی باید به یه بازیکن رندوم آسیب بزنه، None در غیر اینصورت.
    """
    if boss.get("mechanic") != "enrage" or boss["hp"] <= 0:
        return None
    now = time.time()
    if not boss["enraged"] and boss.get("enrage_at", 0) and now >= boss["enrage_at"]:
        boss["enraged"] = True
        boss["last_enrage_tick"] = now
        log_sync(
            f"💢 **BOSS ENRAGED**\n"
            f"🏷️ {boss['name']}\n"
            f"⚡ باس خشمگین شد! هر {_phase_tpl(boss).get('enrage_tick_sec', 10)} ثانیه به یکی آسیب می‌زنه!",
            "BOSS"
        )
        return "start"
    if boss["enraged"]:
        phase = _phase_tpl(boss)
        if now - boss.get("last_enrage_tick", 0) >= phase["enrage_tick_sec"]:
            boss["last_enrage_tick"] = now
            return "tick"
    return None

def pick_random_contributor(boss: dict) -> int | None:
    if not boss["contributors"]:
        return None
    uid_str = random.choice(list(boss["contributors"].keys()))
    return int(uid_str)

def enrage_dmg_pct(boss: dict) -> float:
    return _phase_tpl(boss).get("enrage_dmg_pct", 0.1)

# ================================================================
#  🩹 باگ‌فیکس: ضدحمله‌ی تضمینی باس جهانی
# ------------------------------------------------------------
#  قبلاً باس فقط زیرِ مکانیکِ "area"/"enrage" به بازیکن آسیب می‌زد؛
#  اگه باس تو فازِ "shield" کشته می‌شد (یا این دو تیک به هر دلیلی —
#  مثلاً کرش تو ارسال پیام قبل از save_boss — هیچ‌وقت resolve/ذخیره
#  نمی‌شدن)، بازیکن‌ها هیچ‌وقت ضدحمله‌ای حس نمی‌کردن. حالا یه تیکِ
#  مستقلِ «ضدحمله‌ی پایه» داریم که کاملاً مستقل از مکانیکِ فاز، هر
#  چند ثانیه یه بار یکی از مشارکت‌کننده‌ها رو می‌زنه — تا باس جهانی
#  همیشه، تو هر فاز و هر مکانیکی، واقعاً به پلیرا اتک بده.
# ================================================================
PASSIVE_RETALIATION_INTERVAL = 18   # هر ۱۸ ثانیه یه ضدحمله‌ی پایه
PASSIVE_RETALIATION_DMG_PCT  = 0.06 # ۶٪ از max_hp بازیکنِ هدف

def tick_passive_retaliation(boss: dict) -> int | None:
    """مستقل از مکانیکِ فاز صدا زده می‌شه. اگه وقتِ ضدحمله‌ی پایه رسیده
    باشه، uid یه مشارکت‌کننده‌ی رندوم رو برمی‌گردونه (وگرنه None)."""
    if boss.get("hp", 0) <= 0 and boss.get("shield_hp", 0) <= 0:
        return None
    now = time.time()
    next_at = boss.get("passive_retaliation_next_at", 0)
    if not next_at:
        boss["passive_retaliation_next_at"] = now + PASSIVE_RETALIATION_INTERVAL
        return None
    if now < next_at:
        return None
    boss["passive_retaliation_next_at"] = now + PASSIVE_RETALIATION_INTERVAL
    return pick_random_contributor(boss)

# ================================================================
#  DISPLAY HELPERS
# ================================================================

def hp_bar(current: int, maximum: int, length: int = 14) -> str:
    filled = int((current / maximum) * length) if maximum else 0
    filled = max(0, min(length, filled))
    return "🟥" * filled + "⬛" * (length - filled)

def build_status_text(boss: dict) -> str:
    tpl = WORLD_BOSS_TEMPLATES[boss["template_id"]]
    phase = tpl["phases"][boss["phase_index"]]
    overall_pct = overall_hp_pct(boss)
    lines = [
        f"👑 **{boss['name']}** — {boss['title']}",
        f"🌀 {phase['name']} ({boss['phase_index']+1}/{len(tpl['phases'])})",
        "",
        f"🔴 HP کلی: {overall_pct:.1f}%",
        hp_bar(int(overall_pct), 100, 16),
        "",
        f"⚔️ ضعف فاز: {element_tag(phase['weak'])}  |  🛡 مقاوم به: {element_tag(phase['resist'])}",
    ]
    if boss.get("mechanic") == "shield" and boss.get("shield_active"):
        lines.append("")
        lines.append(f"🛡 سپر: {boss['shield_hp']:,}/{boss['shield_max']:,}")
        lines.append(hp_bar(boss["shield_hp"], boss["shield_max"], 12))
        lines.append("_تا سپر نشکنه آسیب واقعی نمی‌زنی!_")
    elif boss.get("mechanic") == "shield" and not boss.get("shield_active"):
        lines.append("")
        lines.append(f"🔥 HP فاز: {boss['hp']:,}/{boss['phase_max_hp']:,}")
        lines.append(hp_bar(boss["hp"], boss["phase_max_hp"], 12))
    else:
        lines.append("")
        lines.append(f"🔥 HP فاز: {boss['hp']:,}/{boss['phase_max_hp']:,}")
        lines.append(hp_bar(boss["hp"], boss["phase_max_hp"], 12))

    if boss.get("mechanic") == "area" and boss.get("area_active"):
        remain = max(0, int(boss["area_deadline"] - time.time()))
        lines.append("")
        lines.append(f"🌊 **حمله ناحیه‌ای در جریانه!** {remain} ثانیه فرصت داری «🛡 دفاع کن» رو بزنی!")
    if boss.get("mechanic") == "enrage" and boss.get("enraged"):
        lines.append("")
        lines.append("💢 **باس خشمگین شده!** هر چند ثانیه به یکی آسیب می‌زنه!")

    return "\n".join(lines)

def build_attack_kb(boss: dict) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="⚔️ ضربه به باس!", callback_data="bosshit", style=ButtonStyle.DANGER)]]
    if boss.get("mechanic") == "area" and boss.get("area_active"):
        rows.append([InlineKeyboardButton(text="🛡 دفاع کن!", callback_data="bossdef", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="📨 دعوت یه دوست", callback_data="binv:world:0", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ================================================================
#  REWARDS
# ================================================================

def distribute_rewards(boss: dict, is_weekly_featured: bool = False) -> dict:
    """
    خروجی: uid -> {"zen": int, "titles": [str, ...], "items": [dict, ...]}
    فقط محاسبه می‌کنه؛ ذخیره تو دیتابیس وظیفه‌ی handler هست.
    """
    contributors = boss["contributors"]
    rewards: dict[int, dict] = {}

    ranked = sorted(contributors.items(), key=lambda kv: kv[1]["dmg"], reverse=True)
    for i, (uid_str, c) in enumerate(ranked):
        uid = int(uid_str)
        zen = RANK_REWARDS_ZEN[i] if i < len(RANK_REWARDS_ZEN) else PARTICIPATION_ZEN
        titles = []
        if i == 0:
            titles.append("🏆 قهرمان نبرد")
        elif i == 1:
            titles.append("🥈 نایب قهرمان")
        elif i == 2:
            titles.append("🥉 نفر سوم")
        rewards[uid] = {"zen": zen, "titles": titles, "items": []}

    # ─── لوتِ خفن هر باس (نه فقط باسِ هفته!) ─────────────────────
    # نفر اول: نسخه‌ی legendary از آیتمِ امضادارِ همون باس (سلاح/زره/... واقعی، اسلاتِ درست).
    # نفر دوم: تجهیزِ رندومِ mythic. نفر سوم: تجهیزِ رندومِ epic.
    # این باعث می‌شه هر کشتنِ باسِ جهانی لوتِ واقعی و هیجانی بده، نه فقط Zen/لقب.
    tpl = WORLD_BOSS_TEMPLATES.get(boss["template_id"], {})
    loot_tpl = tpl.get("loot_item")
    item_lvl = tpl.get("item_level", 55)
    if ranked:
        from item_system import generate_item, generate_random_equipment
        if loot_tpl:
            top_uid = int(ranked[0][0])
            item = generate_item(
                {**loot_tpl, "sell": 5000, "buy": 10000}, item_lvl,
                forced_rarity="legendary", drop_source="worldboss",
            )
            rewards[top_uid]["items"].append(item)
        if len(ranked) > 1:
            uid2 = int(ranked[1][0])
            item2 = generate_random_equipment(item_lvl, forced_rarity="mythic", drop_source="worldboss")
            rewards[uid2]["items"].append(item2)
        if len(ranked) > 2:
            uid3 = int(ranked[2][0])
            item3 = generate_random_equipment(item_lvl, forced_rarity="epic", drop_source="worldboss")
            rewards[uid3]["items"].append(item3)

    if is_weekly_featured and ranked:
        top_uid = int(ranked[0][0])
        if boss["template_id"] in WEEKLY_BOSS_EXCLUSIVE_ITEM:
            rewards[top_uid]["items"].append(_build_weekly_trophy(boss["template_id"]))
            rewards[top_uid]["zen"] += WEEKLY_BOSS_BONUS_ZEN
            rewards[top_uid]["titles"].append("👑 فاتح باسِ هفته")

    if contributors:
        shield_leader = max(contributors.items(), key=lambda kv: kv[1].get("shield_dmg", 0))
        if shield_leader[1].get("shield_dmg", 0) > 0:
            uid = int(shield_leader[0])
            rewards.setdefault(uid, {"zen": 0, "titles": [], "items": []})
            rewards[uid]["zen"] += BONUS_TITLE_ZEN
            rewards[uid]["titles"].append("💥 شکننده‌ی سپر")

        guardian = max(contributors.items(), key=lambda kv: kv[1].get("defended", 0))
        if guardian[1].get("defended", 0) > 0:
            uid = int(guardian[0])
            rewards.setdefault(uid, {"zen": 0, "titles": [], "items": []})
            rewards[uid]["zen"] += BONUS_TITLE_ZEN
            rewards[uid]["titles"].append("🛡 نگهبان برتر")

    tpl = WORLD_BOSS_TEMPLATES[boss["template_id"]]
    elapsed = time.time() - boss["spawn_time"]
    speed_kill = elapsed <= tpl["speed_kill_seconds"]
    if speed_kill:
        for uid in rewards:
            rewards[uid]["zen"] = int(rewards[uid]["zen"] * (1 + SPEED_KILL_BONUS_PCT))
        log_sync(
            f"⚡ **BOSS SPEED KILL**\n"
            f"🏷️ {boss['name']}\n"
            f"⏱️ {elapsed:.0f} ثانیه (رکورد: {tpl['speed_kill_seconds']}s)\n"
            f"🎁 +{int(SPEED_KILL_BONUS_PCT*100)}٪ پاداش به همه",
            "BOSS"
        )

    log_sync(
        f"💀 **BOSS DEFEATED**\n"
        f"🏷️ {boss['name']}\n"
        f"👥 شرکت‌کنندگان: {len(contributors)}\n"
        f"🏆 بیشترین دمیج: {ranked[0][1]['dmg']:,} توسط {ranked[0][0]}" if ranked else "",
        "BOSS_DEATH"
    )

    return rewards, speed_kill

_RARITY_EMOJI = {"common": "⚪", "uncommon": "🟢", "rare": "🔵", "epic": "🟣", "mythic": "🟠", "legendary": "🟡"}

def _format_reward_item(item: dict) -> str:
    """یه خط خلاصه و خوانا برای آیتمِ پاداش می‌سازه (نه دیکشنریِ خام)."""
    emoji = item.get("emoji", "📦")
    name = item.get("name", "آیتم")
    rarity = _RARITY_EMOJI.get(item.get("rarity", "common"), "⚪")
    return f"{emoji} **{name}** {rarity}"

def build_kill_summary(boss: dict, rewards: dict, speed_kill: bool, name_lookup) -> str:
    ranked = sorted(boss["contributors"].items(), key=lambda kv: kv[1]["dmg"], reverse=True)
    lines = [f"💀 **{boss['name']} شکست خورد!**", ""]
    if speed_kill:
        lines.append(f"⚡ **پاداش کشتار سریع!** (+{int(SPEED_KILL_BONUS_PCT*100)}٪ به همه)")
        lines.append("")
    lines.append("🏆 **رده‌بندی نهایی:**")
    medals = "🥇🥈🥉"
    for i, (uid_str, c) in enumerate(ranked[:10]):
        uid = int(uid_str)
        name = name_lookup(uid)
        medal = medals[i] if i < 3 else "🔹"
        r = rewards.get(uid, {"zen": 0, "titles": [], "items": []})
        title_txt = " " + " ".join(r["titles"]) if r["titles"] else ""
        lines.append(f"{medal} {name}: {c['dmg']:,} دمیج → +{bz_to_display(r['zen'])}{title_txt}")
        for it in r.get("items", []):
            lines.append(f"   🎁 {_format_reward_item(it)}")
    return "\n".join(lines)
