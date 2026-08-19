# ============================================================
#  ASTRAL ABYSS — Stand System v2 (عمیق‌تر)
# ------------------------------------------------------------
#  هر بازیکن، جدا از خودِ کاراکتر و کاتاناش، یه «استند» داره —
#  یه همراهِ روحانی با توانایی‌های کاملاً مستقل از پاورهای خودِ
#  کاراکتر. این نسخه نسبت به v1 عمیق‌تره:
#
#   ۱) هر توانایی سطحِ خودشو داره (۱ تا ۵) و جدا جدا با Zen آپگرید
#      می‌شه — یعنی بازیکن انتخاب داره رو کدوم ability سرمایه‌گذاری
#      کنه (تخصصی‌شدن)، نه یه عددِ کلیِ بی‌معنی.
#   ۲) رتبه/تیرِ استند (خفته → بیدارشده → متعالی → فراانسانی) از رویِ
#      مجموعِ سطحِ توانایی‌ها محاسبه می‌شه — هر تیر یه لقبِ جدید و یه
#      ضریبِ قدرتِ بیشتر می‌ده.
#   ۳) توانایی نهایی (Ultimate) یا از rarityِ خودِ کاراکتر باز می‌شه
#      (rare به بالا از اول دارنش)، یا هر کاراکترِ common هم می‌تونه
#      با رسیدن به تیرِ «متعالی» (گرایندِ طولانی) بازش کنه — یعنی
#      common بودنِ کاراکتر یعنیِ مسیرِ سخت‌تر، نه بی‌بهره‌بودن.
#   ۴) هر دسته (زمان/روان/دفاعی/تهاجمی/پشتیبان/فضایی) یه اثرِ پسیوِ
#      فلیورِ خودشو داره که تو کارت نشون داده می‌شه.
#
#  همه‌چی هنوز deterministic از رویِ اسمِ کاراکتره (بدون نیاز به
#  ذخیره‌سازیِ دستی برای ۳۸۰+ کاراکتر)؛ فقط سطحِ هر ability و تیرِ
#  نهایی این‌هاست که تو دیتای بازیکن (player["stand_abilities"])
#  ذخیره و گرایند می‌شه.
# ============================================================
from __future__ import annotations

import random

from characters import ALL_CHARACTERS

# ─── دسته‌بندیِ استندها ────────────────────────────────────────
STAND_CATEGORIES: dict[str, dict] = {
    "زمان": {
        "emoji": "⏳",
        "passive": "هر ۱۰ سطحِ مجموعِ توانایی‌ها، ۱٪ شانسِ ضربه‌ی دوم رایگان",
        "abilities": [
            "توقفِ لحظه‌ای زمان", "پیش‌بینیِ ضربه", "بازگشتِ یک‌ثانیه‌ای",
            "کندسازیِ میدان", "پژواکِ آینده",
        ],
    },
    "روان": {
        "emoji": "🧠",
        "passive": "دشمن‌ها ۲٪ به‌ازای هر تیرِ استند، شانسِ کمتری برای کریتیکال دارن",
        "abilities": [
            "خوانشِ ذهنِ دشمن", "توهم‌سازی", "فلجِ روانی",
            "پیوندِ دردِ مشترک", "کنترلِ کوتاهِ اراده",
        ],
    },
    "دفاعی": {
        "emoji": "🛡️",
        "passive": "کاهشِ ثابتِ آسیبِ دریافتی به‌ازای هر تیرِ استند",
        "abilities": [
            "بارریرِ روحی", "بازتابِ آسیب", "جذبِ ضربه",
            "پوستِ سنگی موقت", "میدانِ محافظِ گروهی",
        ],
    },
    "تهاجمی": {
        "emoji": "👊",
        "passive": "افزایشِ آسیبِ پایه به‌ازای هر تیرِ استند",
        "abilities": [
            "یورشِ چندضربه‌ای", "احضارِ سلاحِ روحی", "شکافِ نامرئی",
            "ضربه‌ی ماورایی", "قفلِ هدف",
        ],
    },
    "پشتیبان": {
        "emoji": "💫",
        "passive": "بازیابیِ کوچیکِ HP بعدِ هر پیروزی، متناسب با تیرِ استند",
        "abilities": [
            "شفای تدریجی", "انتقالِ انرژی", "تقویتِ هم‌تیمی‌ها",
            "پاک‌سازیِ وضعیت‌های منفی", "هاله‌ی الهام‌بخش",
        ],
    },
    "فضایی": {
        "emoji": "🌀",
        "passive": "شانسِ فرارِ بهتر از نبردهای بازنده، متناسب با تیرِ استند",
        "abilities": [
            "تله‌پورتِ کوتاه", "بازکردنِ درگاه", "جابه‌جاییِ اجباریِ دشمن",
            "قفسِ بُعدی", "گامِ میانِ‌جهانی",
        ],
    },
}

STAND_ULTIMATES = [
    "بیدارسازیِ کامل — همه‌ی توانایی‌ها هم‌زمان فعال می‌شن",
    "شکستنِ مرزِ استند — برای چند لحظه هیچ قانونی روش اثر نداره",
    "پژواکِ ابدی — آسیب‌های واردشده رو ذخیره و یک‌جا برمی‌گردونه",
    "چشمِ آبیس — ضعفِ حریف رو می‌بینه و دقیقاً همونجا می‌زنه",
]
ULTIMATE_KEY = "اولتیمیت"

_NAME_PREFIXES = [
    "Sar", "Vel", "Nyx", "Kro", "Zeph", "Aeth", "Sol", "Vor",
    "Cry", "Thal", "Mor", "Xer", "Ilv", "Quor", "Bra", "Fen",
    "Gor", "Hex", "Iso", "Jyn", "Kael", "Lum", "Myr", "Noc",
]
_NAME_SUFFIXES = [
    "to", "eth", "ion", "ael", "yx", "oth", "ara", "iel",
    "ux", "orn", "ith", "ael", "yn", "os", "ar", "ien",
    "ova", "esh", "ryn", "ol", "um", "ex", "ea", "on",
]

RARITY_STAND_TIER = {"common": 1, "rare": 2, "legendary": 3, "special": 4}

# ─── ماتریسِ هم‌کنشیِ دسته‌ها (Affinity) — برای PvP/دوئل ────────────
# چرخه‌ی ۶ ضلعیِ کاملاً سازگار: هر دسته به ۲ تای بعدیِ خودش تو چرخه
# قوی‌ئه و از ۲ تای قبلی ضعیف می‌خوره — هیچ دسته‌ای مطلقاً برتر نیست.
_AFFINITY_ORDER = ["زمان", "روان", "دفاعی", "تهاجمی", "پشتیبان", "فضایی"]
STAND_AFFINITY: dict[str, dict[str, list[str]]] = {
    cat: {
        "strong_vs": [_AFFINITY_ORDER[(i + 1) % 6], _AFFINITY_ORDER[(i + 2) % 6]],
        "weak_vs":   [_AFFINITY_ORDER[(i - 1) % 6], _AFFINITY_ORDER[(i - 2) % 6]],
    }
    for i, cat in enumerate(_AFFINITY_ORDER)
}
AFFINITY_ADVANTAGE_MULT = 1.15
AFFINITY_DISADVANTAGE_MULT = 0.87


def affinity_multiplier(attacker_category: str, defender_category: str) -> float:
    """ضریبِ آسیب/قدرتِ استندِ حمله‌کننده در برابرِ دسته‌ی استندِ حریف."""
    rel = STAND_AFFINITY.get(attacker_category)
    if not rel:
        return 1.0
    if defender_category in rel["strong_vs"]:
        return AFFINITY_ADVANTAGE_MULT
    if defender_category in rel["weak_vs"]:
        return AFFINITY_DISADVANTAGE_MULT
    return 1.0

# ─── سطحِ اِوولوشِنِ ابیلیتی‌ها ────────────────────────────────────
# وقتی یه ability به سطحِ ۵ برسه، دیگه max شده ولی می‌شه با «فرگمنتِ
# استند» (منبعی که از تمرینِ استند/stand_bond.py میاد) evolve ـش کرد:
# اسمش عوض می‌شه (نسخه‌ی قوی‌ترش) و قدرتش تو Combat Power دو برابر
# حساب می‌شه (انگار سطح ۱۰ داره، نه ۵).
_EVOLUTION_PREFIXES = ["برین‌شده", "استعلایی", "کاملِ", "نهاییِ", "خالصِ"]
EVOLUTION_FRAGMENT_COST = 12


def _evo_seed(char_name: str, ability_name: str) -> int:
    h = _seed_for(char_name)
    for ch in ability_name:
        h = (h * 131 + ord(ch)) % 1_000_003
    return h


def get_evolved_name(char_name: str, ability_name: str) -> str:
    rng = random.Random(_evo_seed(char_name, ability_name))
    prefix = rng.choice(_EVOLUTION_PREFIXES)
    return f"{prefix} {ability_name}"


def is_ability_evolved(player: dict, ability_name: str) -> bool:
    return ability_name in player.get("stand_evolved", [])


def evolve_ability(player: dict, ability_name: str) -> tuple[bool, str]:
    from stand_bond import get_fragments

    char_name = player.get("character", "")
    if not char_name:
        return False, "❌ اول باید یه کاراکتر داشته باشی!"
    stand = get_stand(char_name)

    valid_keys = set(stand["core_abilities"])
    if ultimate_unlocked(player, stand):
        valid_keys.add(ULTIMATE_KEY)
    if ability_name not in valid_keys:
        return False, "❌ این توانایی برای استندت در دسترس نیست."

    levels = player.get("stand_abilities", {})
    if levels.get(ability_name, 1) < MAX_ABILITY_LEVEL:
        return False, f"❌ اول باید این توانایی رو به سطح {MAX_ABILITY_LEVEL} برسونی."
    if is_ability_evolved(player, ability_name):
        return False, "🌟 این توانایی از قبل اوولو شده!"

    frags = get_fragments(player)
    if frags < EVOLUTION_FRAGMENT_COST:
        return False, f"❌ فرگمنتِ استند کافی نداری! ({frags}/{EVOLUTION_FRAGMENT_COST} 🧩)"

    player["stand_fragments"] = frags - EVOLUTION_FRAGMENT_COST
    player.setdefault("stand_evolved", []).append(ability_name)
    evolved_name = get_evolved_name(char_name, ability_name)
    return True, f"🧬 «{ability_name}» اوولو شد → **{evolved_name}**!"


# ─── تیر/رتبه‌ی استند — بر اساسِ مجموعِ سطحِ همه‌ی توانایی‌ها ─────────
# (۴ توانایی × حداکثر ۵ سطح = ۲۰؛ + اولتیمیت × ۵ = ۲۵ حداکثرِ مطلق)
STAND_RANKS = [
    (0,  "خفته",        1.0),
    (8,  "بیدارشده",    1.3),
    (14, "متعالی",      1.7),
    (20, "فراانسانی",   2.2),
]

MAX_ABILITY_LEVEL = 5
BASE_ABILITY_COST = 120


def _seed_for(char_name: str) -> int:
    h = 0
    for ch in char_name:
        h = (h * 131 + ord(ch)) % 1_000_003
    return h


def get_stand(char_name: str) -> dict:
    """استندِ ثابتِ متناظر با یه کاراکتر: {name, category, emoji, passive,
    core_abilities: [4 اسم], ultimate: اسم, rarity_tier}."""
    char = ALL_CHARACTERS.get(char_name, {})
    rng = random.Random(_seed_for(char_name))

    cat_key = rng.choice(list(STAND_CATEGORIES.keys()))
    cat = STAND_CATEGORIES[cat_key]

    name = rng.choice(_NAME_PREFIXES) + rng.choice(_NAME_SUFFIXES)
    stand_name = f"The {name}"

    core_abilities = rng.sample(cat["abilities"], k=min(4, len(cat["abilities"])))
    ultimate = rng.choice(STAND_ULTIMATES)

    rarity = char.get("rarity", "common")
    rarity_tier = RARITY_STAND_TIER.get(rarity, 1)

    return {
        "name": stand_name,
        "category": cat_key,
        "emoji": cat["emoji"],
        "passive": cat["passive"],
        "core_abilities": core_abilities,
        "ultimate": ultimate,
        "rarity_tier": rarity_tier,
    }


def _ability_keys(stand: dict) -> list[str]:
    return list(stand["core_abilities"])


def get_ability_levels(player: dict, stand: dict) -> dict[str, int]:
    """سطحِ هر ability از دیتای پلیر — پیشفرض ۱ برای هرچی هنوز آپگرید نشده."""
    saved = player.get("stand_abilities", {})
    levels = {a: saved.get(a, 1) for a in _ability_keys(stand)}
    if ultimate_unlocked(player, stand):
        levels[ULTIMATE_KEY] = saved.get(ULTIMATE_KEY, 1)
    return levels


def total_stand_score(player: dict, stand: dict | None = None) -> int:
    """مجموعِ سطحِ همه‌ی ability ها — هر ability یِ evolve‌شده دو برابر
    حساب می‌شه (انگار سطح ۱۰ داره)."""
    char_name = player.get("character", "")
    stand = stand or get_stand(char_name)
    levels = get_ability_levels(player, stand)
    total = 0
    for name, lvl in levels.items():
        total += lvl * 2 if is_ability_evolved(player, name) else lvl
    return total


def get_stand_rank(total: int) -> tuple[str, float]:
    rank_name, mult = STAND_RANKS[0][1], STAND_RANKS[0][2]
    for threshold, name, m in STAND_RANKS:
        if total >= threshold:
            rank_name, mult = name, m
    return rank_name, mult


def ultimate_unlocked(player: dict, stand: dict) -> bool:
    """rare به بالا از اول دارنش؛ common هم با رسیدنِ تیرِ مجموع به
    آستانه‌ی «متعالی» (بدونِ احتسابِ خودِ اولتیمیت) بازش می‌کنه."""
    if stand["rarity_tier"] >= 2:
        return True
    base_total = sum(
        player.get("stand_abilities", {}).get(a, 1) for a in stand["core_abilities"]
    )
    return base_total >= STAND_RANKS[2][0]  # آستانه‌ی «متعالی» = ۱۴


def ability_upgrade_cost(level: int) -> int:
    if level >= MAX_ABILITY_LEVEL:
        return 0
    return int(BASE_ABILITY_COST * (level ** 1.8))


def upgrade_stand_ability(player: dict, ability_name: str) -> tuple[bool, str]:
    char_name = player.get("character", "")
    if not char_name:
        return False, "❌ اول باید یه کاراکتر داشته باشی!"
    stand = get_stand(char_name)

    valid_keys = set(stand["core_abilities"])
    if ultimate_unlocked(player, stand):
        valid_keys.add(ULTIMATE_KEY)
    if ability_name not in valid_keys:
        return False, "❌ این توانایی برای استندت در دسترس نیست."

    levels = player.setdefault("stand_abilities", {})
    level = levels.get(ability_name, 1)
    if level >= MAX_ABILITY_LEVEL:
        return False, "🌟 این توانایی از قبل به حداکثر سطح رسیده!"

    cost = ability_upgrade_cost(level)
    zen = player.get("zen", 0)
    if zen < cost:
        return False, f"❌ Zen کافی نداری! ({zen:,}/{cost:,})"

    player["zen"] = zen - cost
    levels[ability_name] = level + 1
    return True, f"✨ «{ability_name}» به سطح {level + 1} رسید!"


def stand_power_bonus(player: dict) -> float:
    """سهمِ استند تو Combat Power — مجموعِ سطح × ضریبِ رتبه × ضریبِ پیوند (Bond)."""
    char_name = player.get("character", "")
    if not char_name:
        return 0.0
    stand = get_stand(char_name)
    total = total_stand_score(player, stand)
    _, rank_mult = get_stand_rank(total)

    try:
        from stand_bond import bond_power_multiplier
        bond_mult = bond_power_multiplier(player)
    except Exception:
        bond_mult = 1.0

    return total * rank_mult * bond_mult * 6.0


def format_stand_card(player: dict) -> str:
    char_name = player.get("character", "")
    if not char_name:
        return "❌ اول باید یه کاراکتر داشته باشی!"

    stand = get_stand(char_name)
    levels = get_ability_levels(player, stand)
    total = total_stand_score(player, stand)
    rank_name, mult = get_stand_rank(total)
    has_ultimate = ULTIMATE_KEY in levels

    try:
        from stand_bond import get_bond_level, bond_xp_to_next, get_fragments, bond_power_multiplier, get_train_streak
        bond_lvl = get_bond_level(player)
        cur_xp, need_xp = bond_xp_to_next(player)
        frags = get_fragments(player)
        bond_mult = bond_power_multiplier(player)
        streak = get_train_streak(player)
        xp_txt = f"{cur_xp}/{need_xp} XP" if need_xp else "حداکثر"
        bond_line = f"🤝 پیوند: سطح {bond_lvl} ({xp_txt}) | ×{bond_mult:.2f} قدرت | 🧩 {frags} فرگمنت | استریکِ تمرین: {streak}🔥"
    except Exception:
        bond_line = ""

    affinity = STAND_AFFINITY.get(stand["category"], {})

    lines = [
        f"{stand['emoji']} **استندِ {player.get('name','بازیکن')}: {stand['name']}**",
        f"🏷 دسته: {stand['category']} | رتبه: **{rank_name}** (×{mult})",
    ]
    if bond_line:
        lines.append(bond_line)
    lines.append(f"\n_{stand['passive']}_\n")
    if affinity:
        lines.append(
            f"⚔️ قوی روی: {' و '.join(affinity['strong_vs'])} | ضعیف در برابرِ: {' و '.join(affinity['weak_vs'])}\n"
        )
    lines.append("✨ **توانایی‌ها:**")

    for a in stand["core_abilities"]:
        lvl = levels[a]
        evolved = is_ability_evolved(player, a)
        display_name = get_evolved_name(char_name, a) if evolved else a
        tag = " 🧬" if evolved else ""
        if lvl >= MAX_ABILITY_LEVEL and not evolved:
            action = f"(می‌تونی evolve کنی: {EVOLUTION_FRAGMENT_COST} 🧩)"
        elif evolved:
            action = "(اوولو شده — MAX)"
        else:
            cost = ability_upgrade_cost(lvl)
            action = f"(ارتقا: {cost:,} Zen)"
        lines.append(f"  • {display_name}{tag} — سطح {lvl}/{MAX_ABILITY_LEVEL} {action}")

    if has_ultimate:
        lvl = levels[ULTIMATE_KEY]
        evolved = is_ability_evolved(player, ULTIMATE_KEY)
        tag = " 🧬" if evolved else ""
        if lvl >= MAX_ABILITY_LEVEL and not evolved:
            action = f"(می‌تونی evolve کنی: {EVOLUTION_FRAGMENT_COST} 🧩)"
        elif evolved:
            action = "(اوولو شده — MAX)"
        else:
            cost = ability_upgrade_cost(lvl)
            action = f"(ارتقا: {cost:,} Zen)"
        lines.append(f"\n🌟 **{stand['ultimate']}**{tag} — سطح {lvl}/{MAX_ABILITY_LEVEL} {action}")
    else:
        need = STAND_RANKS[2][0]
        base_total = sum(player.get("stand_abilities", {}).get(a, 1) for a in stand["core_abilities"])
        lines.append(f"\n🔒 اولتیمیت قفله — با رسیدنِ مجموعِ توانایی‌ها به {need} باز می‌شه ({base_total}/{need})")

    lines.append(
        "\n_توانایی‌های استند کاملاً جدا از پاورهای خودِ کاراکترته؛ هرکدوم رو "
        "جدا آپگرید کن، و با تمرینِ استند فرگمنت جمع کن تا evolve‌شون کنی._"
    )
    return "\n".join(lines)
