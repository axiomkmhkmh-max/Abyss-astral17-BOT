# ============================================================
#  ASTRAL ABYSS — Map Boss Pool 👑 (توسعه‌ی باس‌های بخش لوت)
# ------------------------------------------------------------
#  قبلاً هر مپ دقیقاً یه باس ثابت داشت (همیشه همون اسم، همون
#  آمار) — هم تو کمینِ تصادفیِ حین لوت، هم تو انتهای دانجن.
#  این ماژول اون رو به یه "استخر" ۳تایی به‌ازای هر مپ تبدیل کرده:
#
#    • guardian   → همون باسِ قدیمیِ هر مپ (بدون تغییر آمار)
#    • warlord    → یه باسِ جدید و کمی سنگین‌تر، تو کمینِ تصادفی
#                    هم ممکنه ظاهر بشه
#    • harbinger  → یه باسِ جدید، نادر و خیلی سنگین‌تر — فقط ته
#                    زنجیره‌ی دانجن پیدا می‌شه (هیچ‌وقت تو کمینِ
#                    تصادفیِ لوتِ عادی ظاهر نمی‌شه)
#
#  یعنی جمعاً ۴۵ باسِ متمایز (۱۵ قدیمی + ۳۰ تای جدید)، و خودِ
#  "رسیدن" بهشون هم متفاوته: باسِ نادرِ هر مپ رو فقط با پیدا کردن
#  دروازه‌ی دانجن و رد کردن مراحلش می‌شه دید — کمینِ تصادفی هیچ‌وقت
#  گرون‌ترین باسِ هر مپ رو نشون نمی‌ده.
#
#  علاوه بر این، هر باس (فارغ از تایر) یه فازِ "بیداری" داره: زیرِ
#  یه درصدِ مشخصی از HP، واقعاً قوی‌تر می‌شه و یه پیامِ فلیورِ
#  اختصاصی نشون می‌ده — انگار فرمِ واقعیشو نشون می‌ده.
# ============================================================
import random

# ─── فازِ بیداری (همه‌ی باس‌ها) ─────────────────────────────────
AWAKEN_PCT  = 0.35   # زیرِ این درصد از HP، باس بیدار می‌شه
AWAKEN_MULT = 1.35   # دمیجش از این لحظه به بعد این‌قدر ضرب می‌شه

AWAKEN_FLAVORS = {
    "guardian": [
        "🔥 **{name} خشمگین‌تر شد!** ضربه‌هاش از این لحظه سنگین‌تره.",
        "⚡ **{name} آخرین توانش رو جمع کرد!** حالا مرگبارتره.",
    ],
    "warlord": [
        "💢 **{name} دیگه بازی نمی‌کنه!** فرمِ واقعیِ خشمش رو نشون می‌ده.",
        "🩸 **{name} خون‌آلود و بی‌رحم‌تر شد!** مراقب ضربه‌ی بعدیش باش.",
    ],
    "harbinger": [
        "👑💀 **{name} نقابش رو کنار می‌ذاره...** این همون لحظه‌ایه که همه ازش می‌ترسیدن.",
        "🌑 **{name} فرمِ واقعیشو آزاد می‌کنه!** هوا سنگین می‌شه، زمین می‌لرزه.",
    ],
}

def awaken_message(enemy: dict) -> str:
    tier = enemy.get("boss_tier", "guardian")
    pool = AWAKEN_FLAVORS.get(tier, AWAKEN_FLAVORS["guardian"])
    return random.choice(pool).format(name=enemy.get("name", "باس"))

# ─── استخرِ باس‌های هر مپ ────────────────────────────────────────
# فرمت هر ورودی: name, emoji, hp, dmg, weak, xp, zen, tier, epithet
MAP_BOSS_POOL = {
    "Verdant Vale": [
        {"name": "روح‌پادشاه جنگل کهن",       "emoji": "🌳", "hp": 1260, "dmg": 45, "weak": "آتش",  "xp": 400, "zen": 350, "tier": "guardian",  "epithet": "نگهبانِ باستانیِ ریشه‌ها"},
        {"name": "گرگ‌شاهِ مهِ سیاه",          "emoji": "🐺", "hp": 1580, "dmg": 58, "weak": "برق",  "xp": 500, "zen": 430, "tier": "warlord",   "epithet": "شکارچیِ سایه‌های جنگل"},
        {"name": "پیرِ ریشه‌های نفرین‌شده",     "emoji": "🖤", "hp": 2050, "dmg": 72, "weak": "نور",  "xp": 640, "zen": 560, "tier": "harbinger", "epithet": "سلطانِ تاریکیِ جنگل کهن"},
    ],
    "Frostheim": [
        {"name": "پادشاه یخ ابدی",            "emoji": "❄️", "hp": 4200, "dmg": 150, "weak": "آتش", "xp": 450, "zen": 380, "tier": "guardian",  "epithet": "فرمانروای تاجِ یخی"},
        {"name": "بانوی بهمنِ برق‌آسا",         "emoji": "🌨️", "hp": 5300, "dmg": 190, "weak": "برق", "xp": 560, "zen": 480, "tier": "warlord",   "epithet": "طوفانی که کوه‌ها رو خاموش می‌کنه"},
        {"name": "اژدهای یخِ ازل، آخرین بازمانده", "emoji": "🐉", "hp": 6800, "dmg": 245, "weak": "آتش", "xp": 720, "zen": 620, "tier": "harbinger", "epithet": "آخرین بازمانده‌ی عصرِ یخبندان"},
    ],
    "Voidbreak Wastes": [
        {"name": "خداوند خلأ",                "emoji": "🕳️", "hp": 5880, "dmg": 210, "weak": "نور",  "xp": 700, "zen": 600, "tier": "guardian",  "epithet": "شکافِ زنده‌ی نیستی"},
        {"name": "شکافنده‌ی واقعیت",           "emoji": "🌀", "hp": 7300, "dmg": 260, "weak": "مقدس", "xp": 880, "zen": 760, "tier": "warlord",   "epithet": "کسی که مرزِ جهان‌ها رو پاره می‌کنه"},
        {"name": "زاده‌ی پوچیِ مطلق",           "emoji": "⚫", "hp": 9400, "dmg": 330, "weak": "نور",  "xp": 1150, "zen": 980, "tier": "harbinger", "epithet": "کابوسِ آخرالزمان"},
    ],
    "Emberhollow": [
        {"name": "اژدهای آتشفشان",            "emoji": "🌋", "hp": 4620, "dmg": 180, "weak": "یخ",   "xp": 500, "zen": 420, "tier": "guardian",  "epithet": "شعله‌ی خفته‌ی کوه"},
        {"name": "سالامانداری از خاکستر",      "emoji": "🦎", "hp": 5800, "dmg": 225, "weak": "آب",   "xp": 640, "zen": 540, "tier": "warlord",   "epithet": "زاده‌ی خاکسترِ داغ"},
        {"name": "پادشاهِ گدازه، قلبِ کوه",     "emoji": "👑", "hp": 7400, "dmg": 290, "weak": "یخ",   "xp": 810, "zen": 700, "tier": "harbinger", "epithet": "خشمِ خفته‌ی آتشفشان"},
    ],
    "Dragonnest Peaks": [
        {"name": "اژدهای ارشد باستانی",        "emoji": "🐲", "hp": 6720, "dmg": 255, "weak": "مقدس", "xp": 800, "zen": 700, "tier": "guardian",  "epithet": "پیرترین ساکنِ قله‌ها"},
        {"name": "اژدهای سایه‌بال",            "emoji": "🖤", "hp": 8400, "dmg": 320, "weak": "نور",  "xp": 1030, "zen": 900, "tier": "warlord",   "epithet": "سایه‌ای که آسمون رو تاریک می‌کنه"},
        {"name": "مادرِ اژدهایان، خشمِ قله‌ها",  "emoji": "👑", "hp": 10700, "dmg": 410, "weak": "مقدس", "xp": 1300, "zen": 1150, "tier": "harbinger", "epithet": "افسانه‌ی زنده‌ی قله‌های اژدها"},
    ],
    "Ruins of Orion-7": [
        {"name": "هسته هوش مصنوعی",           "emoji": "🖥️", "hp": 4200, "dmg": 165, "weak": "برق",  "xp": 480, "zen": 400, "tier": "guardian",  "epithet": "بازمانده‌ی تمدنِ نابودشده"},
        {"name": "ربات نگهبانِ زنگ‌زده",        "emoji": "🤖", "hp": 5250, "dmg": 205, "weak": "آتش",  "xp": 620, "zen": 520, "tier": "warlord",   "epithet": "آخرین محافظِ ویرانه‌ها"},
        {"name": "Orion Prime، هوشِ بیدارشده", "emoji": "👁️", "hp": 6700, "dmg": 265, "weak": "برق",  "xp": 790, "zen": 680, "tier": "harbinger", "epithet": "ذهنی که فکر می‌کرد خاموش شده"},
    ],
    "Dreadgate Citadel": [
        {"name": "پادشاه دروازه دوزخ",        "emoji": "😈", "hp": 6300, "dmg": 240, "weak": "نور",  "xp": 750, "zen": 650, "tier": "guardian",  "epithet": "نگهبانِ ابدیِ دروازه"},
        {"name": "شوالیه‌ی سیاه‌زره",          "emoji": "⚔️", "hp": 7900, "dmg": 300, "weak": "مقدس", "xp": 980, "zen": 850, "tier": "warlord",   "epithet": "سربازِ فراموش‌نشدنیِ دوزخ"},
        {"name": "شاهزاده‌ی جهنم، وارثِ دروازه", "emoji": "🔥", "hp": 10100, "dmg": 385, "weak": "نور", "xp": 1230, "zen": 1080, "tier": "harbinger", "epithet": "کسی که دروازه رو باز نگه می‌داره"},
    ],
    "Stormward Archipelago": [
        {"name": "خدای طوفان",                "emoji": "⚡", "hp": 5040, "dmg": 195, "weak": "زمین", "xp": 550, "zen": 470, "tier": "guardian",  "epithet": "فرمانروای آسمانِ خشمگین"},
        {"name": "کوسه‌ی رعد",                "emoji": "🦈", "hp": 6300, "dmg": 240, "weak": "زمین", "xp": 700, "zen": 600, "tier": "warlord",   "epithet": "شکارچیِ موج‌های برق‌گرفته"},
        {"name": "فرمانروای امواج، طوفانِ ابدی", "emoji": "🌊", "hp": 8000, "dmg": 310, "weak": "آب",  "xp": 880, "zen": 760, "tier": "harbinger", "epithet": "طوفانی که هیچ‌وقت آروم نمی‌گیره"},
    ],
    "Holy Luminarchy": [
        {"name": "فرشته سقوط‌کرده",           "emoji": "👼", "hp": 5460, "dmg": 204, "weak": "تاریکی", "xp": 600, "zen": 500, "tier": "guardian",  "epithet": "نوری که به تاریکی آلوده شد"},
        {"name": "فرشته‌ی قضاوت",             "emoji": "⚖️", "hp": 6800, "dmg": 255, "weak": "تاریکی", "xp": 760, "zen": 650, "tier": "warlord",   "epithet": "داورِ بی‌رحمِ آسمان‌ها"},
        {"name": "سرافینِ نه‌بال، آخرین وفادار", "emoji": "🕊️", "hp": 8700, "dmg": 330, "weak": "خلأ",  "xp": 950, "zen": 830, "tier": "harbinger", "epithet": "آخرین نگهبانِ آسمان‌های سقوط‌کرده"},
    ],
    "Clockwork Depths": [
        {"name": "ماشین جنگی باستانی",        "emoji": "⚙️", "hp": 4200, "dmg": 174, "weak": "برق",  "xp": 500, "zen": 420, "tier": "guardian",  "epithet": "بازمانده‌ی جنگِ فراموش‌شده"},
        {"name": "غول ساعت‌ساز",              "emoji": "🦾", "hp": 5250, "dmg": 215, "weak": "برق",  "xp": 630, "zen": 530, "tier": "warlord",   "epithet": "سازنده‌ی چرخ‌دنده‌های بی‌پایان"},
        {"name": "مغزِ مرکزیِ ماشین، هسته‌ی ابدی", "emoji": "🧠", "hp": 6700, "dmg": 280, "weak": "آتش", "xp": 800, "zen": 690, "tier": "harbinger", "epithet": "چرخ‌دنده‌ای که زمان رو می‌سازه"},
    ],
    "Azure Tides Empire": [
        {"name": "لویاتان اعماق",             "emoji": "🐋", "hp": 1960, "dmg": 70, "weak": "برق",  "xp": 650, "zen": 550, "tier": "guardian",  "epithet": "غولِ خفته‌ی اقیانوس"},
        {"name": "کرکنِ اقیانوس",             "emoji": "🐙", "hp": 2450, "dmg": 88, "weak": "برق",  "xp": 810, "zen": 690, "tier": "warlord",   "epithet": "پنجه‌ای که کشتی‌ها رو غرق می‌کنه"},
        {"name": "امپراتورِ آبی، فرمانروای اعماق", "emoji": "👑", "hp": 3140, "dmg": 113, "weak": "زمین", "xp": 1020, "zen": 880, "tier": "harbinger", "epithet": "کسی که دریاها ازش می‌ترسن"},
    ],
    "The Sunken City": [
        {"name": "ملکه آتلانتیس",             "emoji": "🐙", "hp": 5040, "dmg": 186, "weak": "برق",  "xp": 580, "zen": 480, "tier": "guardian",  "epithet": "بانوی شهرِ غرق‌شده"},
        {"name": "شوالیه‌ی غرق‌شده",           "emoji": "🐚", "hp": 6300, "dmg": 230, "weak": "برق",  "xp": 730, "zen": 620, "tier": "warlord",   "epithet": "نگهبانی که هرگز اسلحه‌شو زمین نذاشت"},
        {"name": "پادشاهِ آتلانتیسِ فراموش‌شده", "emoji": "🏛️", "hp": 8000, "dmg": 300, "weak": "آتش", "xp": 920, "zen": 800, "tier": "harbinger", "epithet": "شهری که هرگز نمرد"},
    ],
    "Sands of Eternity": [
        {"name": "فرعون بیدارشده",            "emoji": "🏺", "hp": 1540, "dmg": 60, "weak": "آب",   "xp": 520, "zen": 440, "tier": "guardian",  "epithet": "پادشاهی که از خواب برخاست"},
        {"name": "اسفینکسِ نگهبان",           "emoji": "🦁", "hp": 1930, "dmg": 75, "weak": "آب",   "xp": 650, "zen": 560, "tier": "warlord",   "epithet": "معماگویِ ابدیِ صحرا"},
        {"name": "فرعونِ ابدی، بیدارشده از هزاره‌ها", "emoji": "👑", "hp": 2470, "dmg": 97, "weak": "برق", "xp": 830, "zen": 710, "tier": "harbinger", "epithet": "کسی که زمان نمی‌تونه بکشدش"},
    ],
    "Celestial Spire": [
        {"name": "پروردگار کهکشان",           "emoji": "🌌", "hp": 6300, "dmg": 225, "weak": "خلأ",  "xp": 700, "zen": 600, "tier": "guardian",  "epithet": "نگهبانِ برجِ ستاره‌ها"},
        {"name": "ستاره‌ی فروپاشیده",          "emoji": "💥", "hp": 7900, "dmg": 280, "weak": "خلأ",  "xp": 880, "zen": 760, "tier": "warlord",   "epithet": "باقیمانده‌ی نوری که مُرد"},
        {"name": "خالقِ نور، پروردگارِ کهکشان‌ها", "emoji": "👑", "hp": 10100, "dmg": 360, "weak": "تاریکی", "xp": 1120, "zen": 970, "tier": "harbinger", "epithet": "کسی که کیهان ازش شکل گرفت"},
    ],
    "Abyssal Black Market": [
        {"name": "ارباب سایه‌ها",             "emoji": "🌑", "hp": 5460, "dmg": 210, "weak": "نور",  "xp": 650, "zen": 550, "tier": "guardian",  "epithet": "دلالِ سایه‌های بازارِ سیاه"},
        {"name": "قاچاقچیِ سایه‌ها",           "emoji": "🗡️", "hp": 6800, "dmg": 260, "weak": "نور",  "xp": 760, "zen": 650, "tier": "warlord",   "epithet": "کسی که هیچ قانونی نمی‌شناسه"},
        {"name": "فرمانروای زیرزمین، سایه‌ی اصلی", "emoji": "🖤", "hp": 8700, "dmg": 335, "weak": "مقدس", "xp": 970, "zen": 840, "tier": "harbinger", "epithet": "کسی که هیچ نوری بهش نمی‌رسه"},
    ],
    # 🆕 Throne of Oblivion — سخت‌ترین مپِ بازی (Tier 6)، آمارِ باس‌ها از هر مپِ
    # دیگه‌ای بالاتره؛ harbinger‌ش (اُبلیویون) بالاترین باسِ کل بازیه.
    "Throne of Oblivion": [
        {"name": "نگهبانِ تختِ خاکستری",       "emoji": "⚰️", "hp": 2000000, "dmg": 430, "weak": "برق",  "xp": 1400, "zen": 1220, "tier": "guardian",  "epithet": "کسی که تخت رو هزار سال تنها نگه داشت"},
        {"name": "شوالیه‌ی زنجیرِ ابدیت",      "emoji": "⛓️", "hp": 5000000, "dmg": 500, "weak": "آتش",  "xp": 1650, "zen": 1450, "tier": "warlord",   "epithet": "زنجیری که خودش رو دوباره می‌سازه"},
        {"name": "اُبلیویون، پادشاهِ خاکسترها", "emoji": "👑", "hp": 10000000, "dmg": 600, "weak": "مقدس", "xp": 2100, "zen": 1900, "tier": "harbinger", "epithet": "آخرین چیزی که هر پادشاهی می‌بینه"},
    ],
}

# وزن‌دهیِ انتخاب بر اساسِ حالت — چه مسیری بهت این باس رو نشون می‌ده
_AMBUSH_WEIGHTS   = {"guardian": 0.55, "warlord": 0.45, "harbinger": 0.0}
_DUNGEON_WEIGHTS  = {"guardian": 0.15, "warlord": 0.35, "harbinger": 0.50}

def _pick_from_pool(map_name: str, mode: str) -> dict:
    pool = MAP_BOSS_POOL.get(map_name) or next(iter(MAP_BOSS_POOL.values()))
    weights_map = _DUNGEON_WEIGHTS if mode == "dungeon" else _AMBUSH_WEIGHTS
    candidates = [b for b in pool if weights_map.get(b["tier"], 0) > 0]
    if not candidates:
        candidates = pool
    weights = [weights_map.get(b["tier"], 0.01) for b in candidates]
    return random.choices(candidates, weights=weights, k=1)[0]

def build_boss_enemy(map_name: str, mode: str = "ambush") -> dict:
    """
    مود:
      "ambush"  → کمینِ تصادفیِ حین لوت (فقط guardian/warlord)
      "dungeon" → باسِ نهاییِ زنجیره‌ی دانجن (هر سه تایر، وزن‌دار به سمتِ harbinger)
    """
    b = _pick_from_pool(map_name, mode)
    return {
        "name": f"{b['emoji']} {b['name']}",
        "hp": b["hp"], "max_hp": b["hp"], "dmg": b["dmg"],
        "weak": b["weak"], "tier": "legendary", "drop_chance": 1.0,
        "xp": b["xp"], "zen": b["zen"], "is_boss": True,
        "boss_key": f"{map_name}::{b['name']}",
        "boss_tier": b["tier"], "epithet": b.get("epithet", ""),
        "awaken_pct": AWAKEN_PCT, "awaken_mult": AWAKEN_MULT, "_awakened": False,
    }
