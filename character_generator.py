# ============================================================
#  ASTRAL ABYSS RPG — Procedural Character Generator
# ============================================================
#
# وقتی ۳۵۰ کرکترِ دستیِ RANDOM_CHARACTERS تموم بشه، این ماژول
# کرکترای جدید می‌سازه — با ترکیبِ همون قطعاتِ ساختاریِ کرکترای
# فعلی (عنصر، رنگ، پاورها) و یه اسم/کاتانای تازه که با ترکیبِ
# سیلاب‌های اسم‌ها و کاتاناهای موجود ساخته می‌شه. هیچ API/هزینه‌ای
# لازم نداره و آنی اجرا می‌شه.

import random
import re

from characters import RANDOM_CHARACTERS

# ─── استخرهای برداشته‌شده از ۳۵۰ کرکترِ دستی ──────────────────
_ELEMENTS = sorted({v["element"] for v in RANDOM_CHARACTERS.values()})
_COLORS = sorted({v["color"] for v in RANDOM_CHARACTERS.values()})
_ALL_POWERS = sorted({p for v in RANDOM_CHARACTERS.values() for p in v["powers"]})

# توزیعِ rarity و رنجِ base_dmg دقیقاً برابرِ چیزیه که تو ۳۵۰ تای فعلی هست
_RARITY_WEIGHTS = {"common": 232, "rare": 104, "legendary": 14}
_DMG_RANGE = {"common": (9, 13), "rare": (12, 14), "legendary": (14, 16)}


# پسوندهای رایج توی اسمِ کاتاناها (برای جدا کردنِ کلمه‌های تک-حرفِ-بزرگ
# مثلِ 'Deepmaw' سرِ یه مرزِ واقعیِ کلمه، نه وسطِ کلمه)
_KNOWN_SUFFIX_WORDS = [
    "breaker", "piercer", "pierce", "shroud", "cleave", "strike", "flare",
    "thorn", "storm", "frost", "blood", "shadow", "howl", "gaze", "claw",
    "wing", "scar", "blade", "edge", "fall", "coil", "bite", "born",
    "wrath", "veil", "song", "bone", "ash", "ember", "moon", "star",
    "night", "void", "soul", "doom", "grave", "rend", "spark", "fang",
    "maw",
]


def _split_two(word: str):
    """یه اسمِ کاتانای دو-تکه‌ای رو می‌شکنه: 'AshPierce' -> ('Ash','Pierce')،
    'Abyss Tide' -> ('Abyss','Tide')، 'Deepmaw' -> ('Dee','maw')."""
    if " " in word:
        a, b = word.split(" ", 1)
        return a, b
    caps = re.findall(r"[A-Z][a-z]*", word)
    if len(caps) >= 2:
        return caps[0], "".join(caps[1:])
    low = word.lower()
    for suf in _KNOWN_SUFFIX_WORDS:
        if low.endswith(suf) and len(word) - len(suf) >= 2:
            cut = len(word) - len(suf)
            return word[:cut], word[cut:]
    mid = max(1, len(word) // 2)
    return word[:mid], word[mid:]


# ─── بانکِ سیلاب برای اسمِ کرکتر (پیشوند/پسوند از رویِ ۳۵۰ اسمِ فعلی) ───
_NAME_PREFIXES = []
_NAME_SUFFIXES = []
for _n in RANDOM_CHARACTERS:
    _cut = max(2, min(len(_n) - 2, round(len(_n) * 0.45)))
    _NAME_PREFIXES.append(_n[:_cut])
    _NAME_SUFFIXES.append(_n[_cut:])

# ─── بانکِ پیشوند/پسوند برای اسمِ کاتانا ───────────────────────
_KATANA_PREFIXES = []
_KATANA_SUFFIXES = []
for _v in RANDOM_CHARACTERS.values():
    _a, _b = _split_two(_v["katana"])
    _KATANA_PREFIXES.append(_a)
    _KATANA_SUFFIXES.append(_b)


def _pick_rarity() -> str:
    rarities = list(_RARITY_WEIGHTS.keys())
    weights = list(_RARITY_WEIGHTS.values())
    return random.choices(rarities, weights=weights, k=1)[0]


def generate_unique_name(existing_names) -> str:
    """یه اسمِ فانتزیِ جدید می‌سازه که تو existing_names نباشه."""
    existing = set(existing_names)
    for _ in range(500):
        name = random.choice(_NAME_PREFIXES) + random.choice(_NAME_SUFFIXES)
        if 6 <= len(name) <= 13 and name not in existing:
            return name
    # فال‌بکِ خیلی بعیدِ تمومِ ترکیب‌ها: یه عدد بهش می‌چسبونیم
    base = random.choice(_NAME_PREFIXES) + random.choice(_NAME_SUFFIXES)
    n = 2
    while f"{base}{n}" in existing:
        n += 1
    return f"{base}{n}"


def generate_katana_name(existing_katanas) -> str:
    existing = set(existing_katanas)
    for _ in range(300):
        prefix = random.choice(_KATANA_PREFIXES)
        suffix = random.choice(_KATANA_SUFFIXES)
        katana = f"{prefix}{suffix}" if random.random() < 0.5 else f"{prefix} {suffix}"
        if katana not in existing:
            return katana
    return f"{prefix} {suffix} {random.randint(2, 999)}"


def generate_character(existing_names, existing_katanas):
    """یه کرکترِ کاملاً جدید می‌سازه، هم‌ساختار با اسکیمِ RANDOM_CHARACTERS.
    خروجی: (name, data_dict) — data_dict شاملِ element/color/katana/rarity/
    powers/base_dmg هست + یه فلگِ generated=True برای تشخیصِ بعدی."""
    rarity = _pick_rarity()
    name = generate_unique_name(existing_names)
    katana = generate_katana_name(existing_katanas)
    lo, hi = _DMG_RANGE[rarity]
    data = {
        "element": random.choice(_ELEMENTS),
        "color": random.choice(_COLORS),
        "katana": katana,
        "rarity": rarity,
        "powers": random.sample(_ALL_POWERS, 5),
        "base_dmg": random.randint(lo, hi),
        "generated": True,
    }
    return name, data
