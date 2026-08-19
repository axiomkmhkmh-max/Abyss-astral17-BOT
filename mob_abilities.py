# ============================================================
#  ASTRAL ABYSS — Mob Abilities ⚔️ (عمیق‌سازیِ واقعیِ دشمن‌ها)
# ------------------------------------------------------------
#  هر دشمنِ وحشی (تو ENEMIES) یه "ability" واقعی می‌گیره — نه فقط
#  یه خطِ نمایشی، بلکه یه مکانیکِ واقعی که مستقیم تو calc_combat
#  (combat.py) و تو resolve-ِ راند (mob_combat.py) اثر می‌ذاره.
#
#  تخصیصِ ability به هر دشمن، هم بر اساسِ کلیدواژه‌ی اسمشه (مثلاً
#  "زهر"/"سمی" → venomous) و هم، اگه هیچ کلیدواژه‌ای نخورد، بر
#  اساسِ یه seed پایدار از رویِ خودِ اسمش (deterministic — هر بار
#  ربات بالا میاد، دقیقاً همون ability رو می‌گیره، نه یه چیزِ رندومِ
#  جدید هر ری‌استارت).
# ============================================================
import random

ABILITIES = {
    "venomous": {
        "name": "زهرآگین", "emoji": "☠️",
        "desc": "ضدحمله‌هاش زهرآلودن — یه دمیجِ اضافه‌ی زهر هم می‌خوری.",
    },
    "vampiric": {
        "name": "خون‌آشام", "emoji": "🩸",
        "desc": "با هر ضدحمله‌ای که بهت می‌زنه، بخشی از HPـش رو از خونِ تو پس می‌گیره.",
    },
    "enrage": {
        "name": "خشم", "emoji": "😡",
        "desc": "زیرِ ۳۰٪ HP وحشی‌تر می‌شه — ضدحمله‌هاش خیلی سنگین‌تر می‌شن.",
    },
    "armored_hide": {
        "name": "پوست زره‌ای", "emoji": "🛡️",
        "desc": "پوستِ سختش بخشی از دمیجِ تو رو خنثی می‌کنه.",
    },
    "thorned": {
        "name": "خاردار", "emoji": "🌵",
        "desc": "هر بار ضربه‌ش بزنی، خارهاش بخشی از همون دمیج رو به خودت برمی‌گردونن.",
    },
    "regenerating": {
        "name": "خودترمیم‌گر", "emoji": "💫",
        "desc": "اگه تو یه راند نکشیش، بخشی از HP از دست‌رفته‌ش رو ترمیم می‌کنه.",
    },
    "double_strike": {
        "name": "ضربه‌ی دوگانه", "emoji": "⚔️",
        "desc": "ضدحمله‌هاش گاهی دوبار پشتِ‌سرِهم بهت می‌خورن.",
    },
    "cursed_gaze": {
        "name": "نگاه نفرین‌شده", "emoji": "👁️",
        "desc": "نگاهش دستِ تو رو می‌لرزونه — تو این نبرد شانسِ کریتِ تو کمتره.",
    },
    "ironclad": {
        "name": "زره‌پوش آهنین", "emoji": "⛓️",
        "desc": "گاهی حمله‌ت رو کاملاً بلاک می‌کنه — انگار اصلاً بهش نخورده.",
    },
    "ambush_hunter": {
        "name": "شکارچی کمین‌گر", "emoji": "🌑",
        "desc": "استادِ کمین کردنه — شانس و شدتِ کمینش رو این مواجهه خیلی بیشتره.",
    },
}

# ─── تخصیصِ خودکار بر اساسِ کلیدواژه‌ی اسمِ دشمن ────────────────
_KEYWORD_RULES = [
    (("زهر", "سمی", "سم "), "venomous"),
    (("خون", "پشه", "زالو"), "vampiric"),
    (("روح", "شبح", "ارواح", "سایه", "تاریک", "خلأ", "چشم"), "cursed_gaze"),
    (("گلم", "ربات", "مکانیک", "فولاد", "زره", "سنتینل", "ماشین", "تیرانداز"), "armored_hide"),
    (("عقرب", "خار", "کژدم", "کاکتوس"), "thorned"),
    (("اژدها", "غول", "خرس", "کرم", "لویاتان"), "regenerating"),
    (("دزد", "قاتل", "شکارچی", "کمین", "اوباش", "فریبکار"), "ambush_hunter"),
    (("شوالیه", "سرباز", "دیو", "شیطان", "دیوان", "نگهبان", "سپربان"), "ironclad"),
    (("طوفان", "صاعقه", "برق", "موج"), "double_strike"),
]

# اگه هیچ کلیدواژه‌ای نخورد، بر اساسِ تایرِ خودِ دشمن یه استخرِ مناسب
# انتخاب می‌شه (تایرِ بالاتر → ability های سخت‌تر/تاکتیکی‌تر).
_TIER_FALLBACK_POOL = {
    "common":    ["venomous", "thorned", "armored_hide"],
    "rare":      ["vampiric", "thorned", "double_strike", "armored_hide"],
    "epic":      ["cursed_gaze", "ironclad", "enrage", "regenerating"],
    "legendary": ["cursed_gaze", "ironclad", "enrage", "regenerating", "double_strike"],
}


def _pick_ability(name: str, tier: str) -> str:
    for keywords, ability in _KEYWORD_RULES:
        if any(k in name for k in keywords):
            return ability
    pool = _TIER_FALLBACK_POOL.get(tier, _TIER_FALLBACK_POOL["common"])
    # seed پایدار از رویِ اسم — همیشه همون نتیجه رو می‌ده، بدونِ اینکه
    # رو state سراسریِ random تاثیر بذاره (Random جدا از global استفاده می‌شه).
    return _TIER_FALLBACK_POOL and random.Random(name).choice(pool)


def assign_abilities(enemies: dict) -> None:
    """به هر دشمنِ تو دیکشنریِ ENEMIES (اگه از قبل نداشته) یه ability واقعی می‌ده. In-place."""
    for name, data in enemies.items():
        if "ability" in data:
            continue
        data["ability"] = _pick_ability(name, data.get("tier", "common"))


# ─── هوک‌های واقعی برای calc_combat (combat.py) ─────────────────

def crit_penalty(enemy: dict) -> float:
    """نگاه نفرین‌شده: شانسِ کریتِ بازیکن رو کم می‌کنه."""
    return 0.06 if enemy.get("ability") == "cursed_gaze" else 0.0


def dmg_reduction_mult(enemy: dict) -> float:
    """پوست زره‌ای: بخشی از دمیجِ خامِ بازیکن رو خنثی می‌کنه."""
    return 0.82 if enemy.get("ability") == "armored_hide" else 1.0


def block_chance(enemy: dict) -> float:
    """زره‌پوش آهنین: شانسِ بلاک‌کردنِ کاملِ حمله."""
    return 0.16 if enemy.get("ability") == "ironclad" else 0.0


def thorns_reflect(enemy: dict, dealt_dmg: int) -> int:
    """خاردار: با ضربه زدن، بخشی از همون دمیج به خودت برمی‌گرده."""
    if enemy.get("ability") == "thorned" and dealt_dmg > 0:
        return max(1, int(dealt_dmg * 0.12))
    return 0


def counter_bonus_mult(enemy: dict) -> float:
    """خشم: زیرِ ۳۰٪ HP، ضدحمله‌ی دشمن خیلی سنگین‌تر می‌شه."""
    if enemy.get("ability") == "enrage":
        mx = enemy.get("max_hp", enemy.get("hp", 1)) or 1
        if enemy.get("hp", 0) / mx < 0.3:
            return 1.6
    return 1.0


def venom_bonus(enemy: dict, base_enemy_dmg: int) -> int:
    """زهرآگین: به ضدحمله یه دمیجِ زهرِ اضافه می‌ده."""
    if enemy.get("ability") == "venomous" and base_enemy_dmg > 0:
        return max(1, int(base_enemy_dmg * 0.35))
    return 0


def maybe_double_strike(enemy: dict) -> bool:
    """ضربه‌ی دوگانه: ۳۰٪ شانس یه ضربه‌ی دومِ اضافه رو ضدحمله."""
    return enemy.get("ability") == "double_strike" and random.random() < 0.3


def vamp_heal(enemy: dict, counter_dmg: int) -> int:
    """خون‌آشام: بخشی از دمیجِ ضدحمله رو به‌صورتِ هیل به خودش برمی‌گردونه."""
    if enemy.get("ability") == "vampiric" and counter_dmg > 0:
        return max(1, int(counter_dmg * 0.4))
    return 0


def regen_tick(enemy: dict) -> int:
    """خودترمیم‌گر: اگه سرِ پا مونده، هر راند بخشی از max_hp رو ترمیم می‌کنه."""
    if enemy.get("ability") == "regenerating":
        mx = enemy.get("max_hp", enemy.get("hp", 1))
        return max(1, int(mx * 0.05))
    return 0


def ambush_bonus(enemy: dict) -> tuple[float, float]:
    """شکارچی کمین‌گر: (بونوسِ شانسِ کمین, ضریبِ دمیجِ کمین)."""
    if enemy.get("ability") == "ambush_hunter":
        return (0.20, 1.4)
    return (0.0, 1.0)


def ability_intro_line(enemy: dict) -> str:
    """یه خطِ معرفیِ ability برای بالای صفحه‌ی نبرد."""
    ab = enemy.get("ability")
    if not ab or ab not in ABILITIES or enemy.get("is_boss") or enemy.get("is_nemesis"):
        return ""
    a = ABILITIES[ab]
    return f"{a['emoji']} **توانایی: {a['name']}** — _{a['desc']}_\n\n"
