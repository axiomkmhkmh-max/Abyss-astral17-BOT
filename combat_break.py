# ============================================================
#  ASTRAL ABYSS — Weak Point / Break System (مکانیک کاملاً جدید)
# ------------------------------------------------------------
#  هر دشمن یه گیجِ «تعادل» (poise) نامرئی داره که با تیر ۱۰۰ شروع می‌شه.
#  هر بار که بازیکن دقیقاً از نقطه‌ضعفِ عنصریِ دشمن (enemy["weak"]) استفاده
#  کنه، این گیج کم می‌شه. وقتی به صفر برسه، دشمن «می‌شکنه» (break):
#    • ضربه‌ی همون تِرن، دمیجِ تضمینی‌شده (کریتِ اجباری + ضریبِ اضافه) می‌گیره
#    • ضدحمله‌ی دشمن تو همون تِرن کامل خنثی می‌شه (استان شده)
#    • گیج دوباره پر می‌شه (با سقفِ کمی بالاتر، چون دشمن هوشیارتر می‌شه)
#
#  این ماژول فقط روی دیکشنری‌های `result` (خروجی calc_combat_v3) و `enemy`
#  (که همون آبجکتِ fight ذخیره‌شده روی پروفایلِ بازیکنه) کار می‌کنه — هیچ
#  فایل دیگه‌ای رو دست نمی‌زنه، دقیقاً مثل الگوی combat_stance/combat_chain.
# ============================================================
import random

POISE_MAX_BASE = 100
POISE_MAX_GROWTH_PER_BREAK = 15   # هر بار که شکست، دفعه‌ی بعد یه‌کم سخت‌تر می‌شکنه
POISE_DAMAGE_PER_WEAKHIT = 34     # هر ضربه‌ی درست به نقطه‌ضعف چقدر از گیج کم می‌کنه

BREAK_BONUS_DMG_MULT = 1.6        # ضربه‌ای که باعثِ شکستن می‌شه، این‌قدر تقویت می‌شه
STAGGER_BONUS_DMG_MULT = 1.35     # یه ضربه‌ی اضافه‌ی «رایگان» بلافاصله بعد از شکستن


def _poise_max(enemy: dict) -> int:
    return enemy.get("_poise_max", POISE_MAX_BASE)


def get_poise(enemy: dict) -> int:
    if "_poise" not in enemy:
        enemy["_poise"] = _poise_max(enemy)
    return enemy["_poise"]


def is_broken(enemy: dict) -> bool:
    return bool(enemy.get("_broken_turn"))


def apply_break(result: dict, player: dict, enemy: dict, attack_type: str) -> str | None:
    """
    بعد از calc_combat_v3 و قبل از اعمالِ استنس صدا زده می‌شه.
    خروجی: یه خط لاگِ فارسی برای اضافه‌شدن به نتیجه (یا None اگه اتفاقی نیفتاد).
    result رو مستقیم mutate می‌کنه (dmg / counter / enemy_dmg).
    """
    if result.get("miss") or result.get("dmg", 0) <= 0:
        return None

    from characters import ALL_CHARACTERS
    char = ALL_CHARACTERS.get(player.get("character", ""), {})
    element = char.get("element", "")
    weak = enemy.get("weak", "")

    # ─── اگه دشمن همین الان از یه ضربه‌ی قبلی «شکسته» مونده بود (استان) ──
    if is_broken(enemy):
        enemy["_broken_turn"] = False
        result["dmg"] = int(result["dmg"] * STAGGER_BONUS_DMG_MULT)
        result["counter"] = False
        result["enemy_dmg"] = 0
        return "🌀 **دشمن هنوز مستِ ضربه‌ی قبلیه!** ضربه‌ی اضافه‌ی رایگان زدی."

    hit_weakpoint = bool(element) and element == weak and attack_type in ("element", "heavy", "ultimate", "combo")
    if not hit_weakpoint:
        # آسیبِ عادی هم یه‌کم گیج رو کم می‌کنه (خیلی کمتر از ضربه‌ی دقیق)
        enemy["_poise"] = max(0, get_poise(enemy) - 4)
        return None

    enemy["_poise"] = max(0, get_poise(enemy) - POISE_DAMAGE_PER_WEAKHIT)

    if enemy["_poise"] > 0:
        return f"🎯 **زدی به نقطه‌ضعف!** گیجِ تعادلِ دشمن: {enemy['_poise']}/{_poise_max(enemy)}"

    # ─── شکست! ───────────────────────────────────────────────
    enemy["_poise_max"] = _poise_max(enemy) + POISE_MAX_GROWTH_PER_BREAK
    enemy["_poise"] = enemy["_poise_max"]
    enemy["_broken_turn"] = True  # ضربه‌ی بعدی (این‌همون‌تِرن یا تِرنِ بعد) بونوس می‌گیره

    result["dmg"] = int(result["dmg"] * BREAK_BONUS_DMG_MULT)
    result["crit"] = True
    result["counter"] = False
    result["enemy_dmg"] = 0
    return "💥⚡ **نقطه‌ضعف شکست!** دشمن استان شد — ضدحمله‌اش خنثی شد و دمیجت جهش کرد!"
