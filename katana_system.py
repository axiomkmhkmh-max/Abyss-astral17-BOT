# ============================================================
#  ASTRAL ABYSS RPG — Katana Forge System v3 (با لاگ‌گذاری کامل)
#  ← بازنویسیِ v2: هر تیر از ۵ زیرسطح به ۱۰ زیرسطح رسید (جمعاً ۱۰۰ سطح عادی)
# ============================================================
#
# ساختار جدید:
#   • ۱۰ تیر اصلی (Awakening → Void-Forged) × ۱۰ زیرسطح = ۱۰۰ سطح عادی
#   • + سطح ۱ خام (بدون ارتقا) = جمعاً ۱۰۱ سطح عادی
#   • + یک سطح نهایی افسانه‌ای «Transcendent» (سطح ۱۰۲) که نیاز به Soul Stone داره
#
# نکته‌ی مهمِ بالانس: فرمول‌های قدرت (dmg/crit/lifesteal/elem_amplify) طوری
# دوباره کالیبره شدن که **قدرتِ نهایی در سطح ۱۰۰ تقریباً همون قدرت نهاییِ
# سطح ۵۱ نسخه‌ی قبلی باشه** — یعنی گرایند طولانی‌تر و نرم‌تر شده، ولی یهو
# کاراکترها چند برابر قوی‌تر از قبل نمی‌شن. اگه می‌خوای سقفِ قدرت هم واقعاً
# بالاتر بره (نه فقط نرم‌تر بشه)، بگو تا ضرایب رو عمداً بزرگ‌تر کنم.
#
# هر ارتقا سه چیز لازم داره: طلا + مواد اولیه (بر اساس rarity) + شانس موفقیت.
# فورج‌های سطح بالا شانس شکست دارن؛ شکست بدون «طومار محافظت» یعنی افت یک سطح.
#
# این فایل مستقل کار می‌کنه و هم‌زمان API قدیمی (KATANA_LEVELS[lvl]["dmg"/"cost"/...])
# رو هم حفظ می‌کنه تا combat.py و economy.py بدون شکستن چیزی باهاش کار کنن.
# ============================================================

import random
from logger import log_sync

# ---------- ۱۰ تیر اصلی ----------
KATANA_TIERS = [
    {"key": "awakening",   "name_fa": "بیداری",       "name_en": "Awakening",   "emoji": "🗡️", "mat_low": "common",    "mat_high": "uncommon"},
    {"key": "adept",       "name_fa": "ماهر",         "name_en": "Adept",       "emoji": "🔷", "mat_low": "uncommon",  "mat_high": "rare"},
    {"key": "veteran",     "name_fa": "کهنه‌کار",     "name_en": "Veteran",     "emoji": "🟢", "mat_low": "rare",      "mat_high": "rare"},
    {"key": "elite",       "name_fa": "نخبه",         "name_en": "Elite",       "emoji": "🟣", "mat_low": "rare",      "mat_high": "epic"},
    {"key": "master",      "name_fa": "استاد",        "name_en": "Master",      "emoji": "🟠", "mat_low": "epic",      "mat_high": "epic"},
    {"key": "grandmaster", "name_fa": "بزرگ‌استاد",   "name_en": "Grandmaster", "emoji": "⭐", "mat_low": "epic",      "mat_high": "mythic"},
    {"key": "mythic",      "name_fa": "اسطوره‌ای",    "name_en": "Mythic",      "emoji": "💜", "mat_low": "mythic",    "mat_high": "mythic"},
    {"key": "ascended",    "name_fa": "متعالی",       "name_en": "Ascended",    "emoji": "👑", "mat_low": "mythic",    "mat_high": "legendary"},
    {"key": "celestial",   "name_fa": "آسمانی",       "name_en": "Celestial",   "emoji": "✨", "mat_low": "legendary", "mat_high": "legendary"},
    {"key": "void_forged", "name_fa": "پوچی‌ساخته",   "name_en": "Void-Forged", "emoji": "🌌", "mat_low": "legendary", "mat_high": "legendary"},
]

SUB_LEVELS_PER_TIER = 10   # قبلاً ۵ بود

MAX_NORMAL_LEVEL   = 1 + SUB_LEVELS_PER_TIER * len(KATANA_TIERS)   # = 101
TRANSCENDENT_LEVEL = MAX_NORMAL_LEVEL + 1                          # = 102

# ---------- کمکی‌ها ----------

def tier_index_of(level: int) -> int:
    """این سطح تو کدوم تیر (۰..۹) قرار داره. سطح ۱ = خام، بدون تیر."""
    if level <= 1:
        return -1
    if level >= TRANSCENDENT_LEVEL:
        return len(KATANA_TIERS) - 1
    return (level - 2) // SUB_LEVELS_PER_TIER

def sub_level_of(level: int) -> int:
    """زیرسطح ۱ تا ۱۰ داخل تیر."""
    if level <= 1:
        return 0
    if level >= TRANSCENDENT_LEVEL:
        return SUB_LEVELS_PER_TIER
    return (level - 2) % SUB_LEVELS_PER_TIER + 1

def _roman(n: int) -> str:
    return {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V",
            6: "VI", 7: "VII", 8: "VIII", 9: "IX", 10: "X"}.get(n, str(n))

def get_katana_title(level: int) -> str:
    if level <= 1:
        return "خام (بدون ارتقا)"
    if level >= TRANSCENDENT_LEVEL:
        return "🌌👑 فراتر از واقعیت — Transcendent 👑🌌"
    t = KATANA_TIERS[tier_index_of(level)]
    return f"{t['emoji']} {t['name_fa']} ({t['name_en']} {_roman(sub_level_of(level))})"

def get_katana_suffix(level: int) -> str:
    if level <= 1:
        return ""
    if level >= TRANSCENDENT_LEVEL:
        return " 🌌👑∞"
    t = KATANA_TIERS[tier_index_of(level)]
    return f" {t['emoji']}{'+' * sub_level_of(level)}"

def is_breakthrough_level(level: int) -> bool:
    """آیا این سطح، پایان یک تیر (رونمایی/ارتقای بزرگ) هست؟"""
    return level > 1 and (sub_level_of(level) == SUB_LEVELS_PER_TIER)

# ---------- فرمول‌های قدرت (بازکالیبره‌شده برای ۱۰۰ سطح) ----------
# توضیح کالیبراسیون بالای فایل رو ببین: هدف اینه که سقف قدرت در سطح ۱۰۰
# (min(level, TRANSCENDENT_LEVEL)-1 == 100) تقریباً برابر سقف قدیمی (لول ۵۱، step=50) باشه.

# ─── حالت سخت (Hardcore Mode) ──────────────────────────────────
# بونوس دمیج/کریت/لایف‌استیل کاتانا همگی نصف مقدار قبلی شدن (طبق
# درخواست بند ۱۳: «بونوس بیداری کاتانا: نصف مقدار فعلی»).
HARDCORE_BONUS_MULT = 0.5

def dmg_bonus(level: int) -> int:
    if level <= 1:
        return 0
    lvl = min(level, TRANSCENDENT_LEVEL)
    base = 2 + ((lvl - 1) ** 1.376) * 1.15
    if level >= TRANSCENDENT_LEVEL:
        base *= 1.35
    return int(round(base * HARDCORE_BONUS_MULT))

def crit_bonus(level: int) -> float:
    """درصد کریت اضافه (۰ تا ۱، مثلاً ۰.۱۵ = ۱۵٪)."""
    if level <= 1:
        return 0.0
    steps = min(level, TRANSCENDENT_LEVEL) - 1
    val = steps * 0.003
    if level >= TRANSCENDENT_LEVEL:
        val += 0.05
    val *= HARDCORE_BONUS_MULT
    return round(min(val, 0.40), 3)

def lifesteal_bonus(level: int) -> float:
    """لایف‌استیل — از تیر Master (سطح ۴۲؛ قبلاً ۲۲) باز میشه."""
    unlock_level = 2 + 4 * SUB_LEVELS_PER_TIER  # شروع تیر Master (index 4) = 42
    if level < unlock_level:
        return 0.0
    val = (min(level, TRANSCENDENT_LEVEL) - (unlock_level - 1)) * 0.002
    if level >= TRANSCENDENT_LEVEL:
        val += 0.05
    val *= HARDCORE_BONUS_MULT
    return round(min(val, 0.20), 3)

def element_amplify_bonus(level: int) -> float:
    """ضریب اضافه روی بونوس ضعف عنصری — از تیر Ascended (سطح ۷۲؛ قبلاً ۳۷) باز میشه."""
    unlock_level = 2 + 7 * SUB_LEVELS_PER_TIER  # شروع تیر Ascended (index 7) = 72
    if level < unlock_level:
        return 0.0
    val = ((min(level, TRANSCENDENT_LEVEL) - (unlock_level - 1)) // SUB_LEVELS_PER_TIER) * 0.05
    if level >= TRANSCENDENT_LEVEL:
        val += 0.15
    return round(val, 3)

# ---------- هزینه و مواد فورج ----------

def forge_cost(level: int) -> int:
    """هزینه طلا برای رفتن از level-1 به level."""
    if level <= 1:
        return 0
    if level >= TRANSCENDENT_LEVEL:
        return 3_000_000
    n = level - 1
    # ضریب رشد نسبت به v2 کم‌تر شده (۰.۲۲ → ۰.۱۰) چون حالا دو برابر پله داریم؛
    # این‌جوری هزینه‌ی هر پله منطقی‌تره ولی هزینه‌ی کلِ رسیدن به سقف بازم بالاتر می‌مونه.
    return int(1400 * n * (1 + n * 0.10))

def forge_materials(level: int) -> dict:
    """مواد لازم برای ارتقا به این سطح (rarity -> تعداد).
    حالت سخت: نیاز به مواد ۳ برابر شد."""
    if level <= 1:
        return {}
    if level >= TRANSCENDENT_LEVEL:
        return {"legendary": 15, "soul_stone": 1}
    t = KATANA_TIERS[tier_index_of(level)]
    sub = sub_level_of(level)
    reqs = {t["mat_low"]: (2 + sub) * 3}
    if sub >= 4:
        reqs[t["mat_high"]] = reqs.get(t["mat_high"], 0) + (sub - 3) * 3
    return reqs

def success_chance(level: int) -> float:
    """شانس موفقیت فورج (بیداری) — حالت سخت: نصف مقدار قبلی، سقف ۴۰٪ برای بالاترین سطح."""
    if level <= 15:
        base = 1.0
    elif level >= TRANSCENDENT_LEVEL:
        base = 0.20
    else:
        base = max(0.30, 1.0 - (level - 15) * 0.0077)
    return round(max(0.05, min(0.40, base * 0.5)), 3)

def get_katana_full_stats(level: int) -> dict:
    """خلاصه‌ی کامل وضعیت فعلی کاتانا + پیش‌نمایش ارتقای بعدی."""
    nxt = level + 1 if level < TRANSCENDENT_LEVEL else None
    return {
        "level": level,
        "title": get_katana_title(level),
        "suffix": get_katana_suffix(level),
        "dmg": dmg_bonus(level),
        "crit": crit_bonus(level),
        "lifesteal": lifesteal_bonus(level),
        "elem_amplify": element_amplify_bonus(level),
        "is_max": nxt is None,
        "next_title": get_katana_title(nxt) if nxt else None,
        "next_cost": forge_cost(nxt) if nxt else None,
        "next_materials": forge_materials(nxt) if nxt else None,
        "next_chance": success_chance(nxt) if nxt else None,
    }

# ---------- عملیات واقعی فورج ----------

FORGE_BREAK_ON_FAIL = True  # شکست بدون طومار محافظت = افت یک سطح

def attempt_forge(current_level: int, inventory: dict, gold: int, use_protection: bool = False) -> dict:
    """
    inventory: دیکشنری rarity/آیتم -> تعداد (شامل protection_scroll و soul_stone در صورت نیاز)
    خروجی: dict شامل success / new_level / gold_spent / materials_spent / message / chance
    توجه: کم کردن طلا و مواد از موجودی واقعی پلیر، وظیفه‌ی هندلر صداکننده‌ست —
    این تابع فقط محاسبه و نتیجه رو برمی‌گردونه.
    """
    target = current_level + 1
    if target > TRANSCENDENT_LEVEL:
        return {"success": False, "new_level": current_level, "gold_spent": 0,
                "materials_spent": {}, "chance": 0.0, "protection_used": False,
                "message": "⚔️ کاتانات به اوج مطلق رسیده! چیزی بالاتر از این وجود نداره."}

    cost   = forge_cost(target)
    mats   = forge_materials(target)
    chance = success_chance(target)

    if gold < cost:
        return {"success": False, "new_level": current_level, "gold_spent": 0,
                "materials_spent": {}, "chance": chance, "protection_used": False,
                "message": f"💰 طلای کافی نداری! به {cost:,} سکه نیاز داری."}

    for mat, need in mats.items():
        if inventory.get(mat, 0) < need:
            return {"success": False, "new_level": current_level, "gold_spent": 0,
                    "materials_spent": {}, "chance": chance, "protection_used": False,
                    "message": f"📦 مواد کافی نداری! به {need}x {mat} نیاز داری."}

    if use_protection and inventory.get("protection_scroll", 0) < 1:
        return {"success": False, "new_level": current_level, "gold_spent": 0,
                "materials_spent": {}, "chance": chance, "protection_used": False,
                "message": "🛡️ طومار محافظت نداری!"}

    success = random.random() < chance
    new_level = current_level
    protection_used = False

    if success:
        new_level = target
        tag = " 🎉 **رونمایی تیر جدید!**" if is_breakthrough_level(target) else ""
        message = f"✅ فورج موفق! کاتانا به سطح {target} رسید.\n{get_katana_title(target)}{tag}"
        
        log_sync(
            f"🔨 **KATANA FORGE SUCCESS**\n"
            f"📊 سطح: {current_level} → {target}\n"
            f"💰 هزینه: {cost:,}\n"
            f"📦 مواد: {mats}\n"
            f"🎲 شانس: {chance*100:.1f}%",
            "CRAFT"
        )
    else:
        if use_protection:
            protection_used = True
            message = "🛡️ فورج شکست خورد، ولی طومار محافظت مانع افت سطح شد."
        elif FORGE_BREAK_ON_FAIL and current_level > 1:
            new_level = current_level - 1
            message = f"💥 فورج شکست خورد! کاتانا یک سطح افت کرد → سطح {new_level}."
            
            log_sync(
                f"💥 **KATANA FORGE FAIL**\n"
                f"📊 سطح: {current_level} → {new_level}\n"
                f"💰 هزینه: {cost:,}\n"
                f"📦 مواد: {mats}\n"
                f"🎲 شانس: {chance*100:.1f}%",
                "CRAFT"
            )
        else:
            message = "💥 فورج شکست خورد. طلا و مواد از دست رفت ولی سطح حفظ شد."

    return {
        "success": success, "new_level": new_level, "gold_spent": cost,
        "materials_spent": mats, "chance": chance,
        "protection_used": protection_used, "message": message,
    }

# ---------- سازگاری با کد قدیم ----------
# combat.py و economy.py با KATANA_LEVELS[lvl]["dmg"/"cost"/"label"/"suffix"] کار می‌کردن.
# این دیکشنری همون API رو حفظ می‌کنه ولی از موتور جدید بالا تغذیه میشه، به‌علاوه‌ی
# فیلدهای جدید (crit, lifesteal, elem_amplify) که کد جدید ازش استفاده می‌کنه.

KATANA_LEVELS = {
    lvl: {
        "label":        get_katana_title(lvl),
        "cost":         forge_cost(lvl),
        "dmg":          dmg_bonus(lvl),
        "suffix":       get_katana_suffix(lvl),
        "crit":         crit_bonus(lvl),
        "lifesteal":    lifesteal_bonus(lvl),
        "elem_amplify": element_amplify_bonus(lvl),
        "materials":    forge_materials(lvl),
        "chance":       success_chance(lvl),
    }
    for lvl in range(1, TRANSCENDENT_LEVEL + 1)
}

# ---------- آیتم‌های جدید مغازه، مرتبط با فورج ----------
FORGE_SHOP_ITEMS = [
    {"name": "Protection Scroll", "emoji": "🛡️", "cost": 15000, "rarity": "epic",
     "effect": "در صورت شکست فورج، از افت سطح کاتانا جلوگیری می‌کنه"},
    {"name": "Forge Catalyst",    "emoji": "🔥", "cost": 8000,  "rarity": "rare",
     "effect": "شانس موفقیت فورج بعدی رو ۱۰٪ افزایش می‌ده"},
]
