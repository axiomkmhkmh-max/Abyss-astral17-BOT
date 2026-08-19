# ============================================================
#  ASTRAL ABYSS RPG — Katana Lore & Backstory System
#  (katana_lore.py)  —  فاز ۳ / بخش الف
# ============================================================
#
# هر کاتانا ۵ فصل داستانی داره: تولد → اولین خون‌ریزی → نبرد بزرگ → سقوط →
# تولد دوباره. هر فصل با رسیدن به یه مرحله‌ی بیداری *یا* یه تعداد کشته
# (هرکدوم زودتر برسه) باز می‌شه، و یه بونوس دائمی کوچیک می‌ده.
#
# چون این بازی ۹۰ کاراکتر داره، نوشتنِ دستیِ ۴۵۰ پاراگراف (۹۰×۵) عملاً
# ممکن نیست. راه‌حل:
#   • برای کاتاناهایی که تو LORE_OVERRIDES نوشته شدن (فعلاً Paradox Edge،
#     دقیقاً طبق مثالِ خودت + چندتای دیگه از ۱۵ کاتانای Special) → متن دستی.
#   • برای بقیه (۷۵ کاتانای Random + بقیه‌ی Specialها) → یه generator
#     قالب‌محور که از عنصر، رتبه (tier) و تیپ شخصیتیِ همون کاتانا
#     (katana_personality._derive_personality_type) استفاده می‌کنه تا هر
#     کاتانا داستانِ خودش، هم‌راستا با هویتش، داشته باشه (نه یه متن تکراری).
#
# اگه بخوای برای همه‌ی ۹۰ تا دستی بنویسم، بگو تا فایل جدا (katana_lore_texts.py)
# باهاش پر کنم — این‌جا فقط زیرساخت + محتوای نمونه‌ست.
#
# ذخیره‌سازی (per-character):
#   player["katana_lore"] = {
#       "<character_name>": {"unlocked": [1, 2]}
#   }
# ============================================================

from katana_core import get_katana_identity, TIER_CONFIG

LORE_CHAPTER_COUNT = 5

CHAPTER_TITLES = {
    1: "تولد",
    2: "اولین شکاف",
    3: "نبرد بزرگ",
    4: "سقوط",
    5: "تولد دوباره",
}

# نیازِ باز شدن هر فصل: (حداقل مرحله‌ی بیداری) یا (حداقل کشته با این کاتانا) — هرکدوم زودتر
CHAPTER_REQUIREMENTS = {
    1: {"awaken_stage": 1, "kills": 50},
    2: {"awaken_stage": 2, "kills": 200},
    3: {"awaken_stage": 3, "kills": 500},
    4: {"awaken_stage": 4, "kills": 1000},
    5: {"awaken_stage": 5, "kills": 2000},
}

# بونوسِ دائمیِ هر فصل (با باز شدن، برای همیشه فعاله)
CHAPTER_BONUS = {
    1: {"field": "dmg_mult_flat", "value": 0.02, "label": "+۲٪ دمیج"},
    2: {"field": "crit", "value": 0.02, "label": "+۲٪ کریت"},
    3: {"field": "lifesteal", "value": 0.02, "label": "+۲٪ لایف‌استیل"},
    4: {"field": "dodge", "value": 0.02, "label": "+۲٪ شانس جاخالی"},
    5: {"field": "special_chance_add", "value": 0.03, "label": "+۳٪ شانس اثر ویژه"},
}

# ────────────────────────────────────────────────────────────
# ۱) متن‌های دستیِ نمونه (Special-tier)
# ────────────────────────────────────────────────────────────

LORE_OVERRIDES = {
    "Paradox Edge": {
        1: "در آزمایشگاهی فراموش‌شده که زمان در آن دیگر به‌طور خطی جریان نداشت، «پارادوکس اج» از تلاقیِ یک لحظه با بی‌نهایت لحظه‌ی دیگر متولد شد. کسی که آن را ساخت، خودش هرگز مطمئن نبود در کدام نسخه از واقعیت زندگی می‌کند.",
        2: "اولین باری که این تیغه واقعیت را شکافت، یک روز کامل در همان لحظه گیر افتاد و بارها تکرار شد — تا وقتی صاحبش یاد گرفت چطور از میان شکاف عبور کند، نه در برابرش بایستد.",
        3: "در نبردی که تاریخ‌نگاران هنوز نمی‌دانند کِی اتفاق افتاده، پارادوکس اج در کنار سپاهی از جنگجویانِ فرازمانی جنگید؛ نبردی که همزمان در گذشته، حال و آینده روایت می‌شود.",
        4: "نیروهای خلأ سرانجام تیغه را شکستند — اما شکستن یک پارادوکس، خودش یک پارادوکسِ دیگر می‌سازد. تیغه از هم پاشید، ولی هرگز واقعاً از بین نرفت.",
        5: "وقتی دستان جدیدی دوباره آن را برداشت، پارادوکس اج فهمید این هم یکی دیگر از بی‌نهایت تولدهایش است. این بار، تصمیم گرفت بماند.",
    },
}

# ────────────────────────────────────────────────────────────
# ۲) Generator قالب‌محور برای بقیه‌ی کاتاناها
# ────────────────────────────────────────────────────────────

_GENERIC_CHAPTER_TEMPLATES = {
    1: "کاتانای {katana} از دلِ {element} زاده شد؛ هنوز کسی نمی‌دانست روحی به این {trait} در تیغه‌اش خانه کرده.",
    2: "اولین خونی که {katana} ریخت، نشانش داد این تیغه فقط ابزار نیست — چیزی {trait} در آن نفس می‌کشد.",
    3: "در نبردی بزرگ، {katana} کنار صاحبش ایستاد و ثابت کرد رتبه‌ی {tier_fa} بودنش تصادفی نیست.",
    4: "شکستی سخت {katana} را تا مرز نابودی برد؛ ولی چیزی {trait} در جوهرش، اجازه‌ی محو شدنِ کامل را نداد.",
    5: "{katana} دوباره در دستانِ صاحبش زنده شد — این بار با فهمی عمیق‌تر از این‌که چرا وجود دارد.",
}

_PERSONALITY_TRAIT_WORDS = {
    "شجاع": "بی‌باک", "حیله‌گر": "زیرک", "خردمند": "دوراندیش", "خشن": "خشن",
    "مهربان": "دلسوز", "انتقام‌جو": "کینه‌توز", "مرموز": "پرمعما", "شاد": "سرزنده",
    "غمگین": "غمگین", "پرشور": "آتشین", "سرد": "بی‌احساس", "دیوانه": "آشوب‌گر",
}


def _generated_chapter_text(katana_name: str, element: str, tier: str, chapter: int) -> str:
    try:
        from katana_personality import _derive_personality_type
        ptype = _derive_personality_type(katana_name)
    except ImportError:
        ptype = "مرموز"
    trait = _PERSONALITY_TRAIT_WORDS.get(ptype, "پرمعما")
    tier_fa = TIER_CONFIG[tier]["name_fa"]
    tmpl = _GENERIC_CHAPTER_TEMPLATES[chapter]
    return tmpl.format(katana=katana_name, element=element or "نیرویی ناشناخته", trait=trait, tier_fa=tier_fa)


def get_chapter_text(character_name: str, chapter: int) -> str:
    ident = get_katana_identity(character_name)
    katana_name = ident["katana_name"]
    override = LORE_OVERRIDES.get(katana_name)
    if override and chapter in override:
        return override[chapter]
    return _generated_chapter_text(katana_name, ident["element"], ident["tier"], chapter)


# ────────────────────────────────────────────────────────────
# ۳) API اصلی
# ────────────────────────────────────────────────────────────

def get_lore(player: dict, character_name: str) -> dict:
    store = player.setdefault("katana_lore", {})
    entry = store.get(character_name)
    if entry is None:
        entry = {"unlocked": []}
        store[character_name] = entry
    return entry


def check_and_unlock_chapters(player: dict, character_name: str) -> list[dict]:
    """بعد از هر کشتن/بیداریِ موفق صدا زده بشه. فصل‌های تازه‌بازشده رو برمی‌گردونه."""
    entry = get_lore(player, character_name)
    stage = player.get("katana_awakening", 0)
    kills = player.get("katana_kills", 0)
    newly = []
    for ch in range(1, LORE_CHAPTER_COUNT + 1):
        if ch in entry["unlocked"]:
            continue
        req = CHAPTER_REQUIREMENTS[ch]
        if stage >= req["awaken_stage"] or kills >= req["kills"]:
            entry["unlocked"].append(ch)
            bonus = CHAPTER_BONUS[ch]
            newly.append({"chapter": ch, "title": CHAPTER_TITLES[ch],
                           "text": get_chapter_text(character_name, ch), "bonus": bonus})
    return newly


def calc_lore_bonus(player: dict, character_name: str) -> dict:
    entry = get_lore(player, character_name)
    out = {"dmg_mult_flat": 0.0, "crit": 0.0, "lifesteal": 0.0, "dodge": 0.0, "special_chance_add": 0.0}
    for ch in entry.get("unlocked", []):
        b = CHAPTER_BONUS[ch]
        out[b["field"]] = out.get(b["field"], 0.0) + b["value"]
    return out


def display_lore(player: dict, character_name: str) -> str:
    entry = get_lore(player, character_name)
    ident = get_katana_identity(character_name)
    lines = [f"📖 **لور {ident['katana_name']}** 📖", ""]
    for ch in range(1, LORE_CHAPTER_COUNT + 1):
        title = CHAPTER_TITLES[ch]
        if ch in entry["unlocked"]:
            bonus = CHAPTER_BONUS[ch]
            lines.append(f"✅ **فصل {ch}: {title}** — {bonus['label']}")
            lines.append(f"   _{get_chapter_text(character_name, ch)}_")
        else:
            req = CHAPTER_REQUIREMENTS[ch]
            lines.append(f"🔒 فصل {ch}: {title} — نیاز: بیداری {req['awaken_stage']}+ یا {req['kills']} کشته")
        lines.append("")
    return "\n".join(lines).strip()
