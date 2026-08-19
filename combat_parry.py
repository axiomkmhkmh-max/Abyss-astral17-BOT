# ============================================================
#  ASTRAL ABYSS — Counter/Parry System (مکانیک کاملاً جدید)
# ------------------------------------------------------------
#  چون تلگرام تایمینگِ واقعیِ کلاینت رو بهمون نمی‌ده، تایمینگ رو با
#  فاصله‌ی زمانیِ سمت سرور اندازه می‌گیریم: از لحظه‌ای که پنلِ حمله
#  نشون داده شد (player["_panel_shown_at"]) تا لحظه‌ای که دکمه‌ی
#  «پری/کانتر» زده شد. هرچی سریع‌تر بزنی، شانسِ پریِ کاملت بیشتره —
#  ریسک بالا-پاداش بالا: اگه دیر بزنی، ضدحمله‌ی کامل + یه‌کم اضافه می‌خوری.
# ============================================================
import time

# ─── پنجره‌های تایمینگ (ثانیه) ─────────────────────────────────
PERFECT_WINDOW  = 2.0   # زیر این = پریِ کامل تقریباً تضمینی
GOOD_WINDOW     = 4.5   # زیر این = شانسِ خوب
LATE_PENALTY_MULT = 1.25  # اگه کامل خراب کنی، ضدحمله ۲۵٪ قوی‌تر می‌خوره

PERFECT_SUCCESS_CHANCE = 0.92
GOOD_SUCCESS_CHANCE    = 0.55
LATE_SUCCESS_CHANCE    = 0.18

COUNTER_BONUS_MULT = 1.9  # اگه پری موفق بشه، خودِ ضربه‌ی پری این‌قدر تقویت می‌شه


def mark_panel_shown(player: dict):
    """هر بار پنلِ حمله رندر می‌شه صدا زده می‌شه (مثل رندرِ استنس/زنجیره)."""
    player["_panel_shown_at"] = time.time()


def _reaction_time(player: dict) -> float:
    shown_at = player.get("_panel_shown_at", 0)
    if not shown_at:
        return 999.0
    return max(0.0, time.time() - shown_at)


def resolve_parry(result: dict, player: dict, enemy: dict) -> str:
    """
    فقط وقتی atk_type == 'parry' صدا زده می‌شه. result رو mutate می‌کنه
    و یه خط لاگِ فارسی برمی‌گردونه.
    """
    import random
    rt = _reaction_time(player)

    if rt <= PERFECT_WINDOW:
        chance, tier_label = PERFECT_SUCCESS_CHANCE, "پرفکت"
    elif rt <= GOOD_WINDOW:
        chance, tier_label = GOOD_SUCCESS_CHANCE, "خوب"
    else:
        chance, tier_label = LATE_SUCCESS_CHANCE, "دیر"

    success = random.random() < chance

    if success:
        if not result.get("miss"):
            result["dmg"] = int(result.get("dmg", 0) * COUNTER_BONUS_MULT)
            result["crit"] = True
        result["counter"] = False
        result["enemy_dmg"] = 0
        return (
            f"🛡️✨ **پری {tier_label}!** (⏱️{rt:.1f}s) ضدحمله‌ی دشمن رو کامل خنثی کردی "
            f"و کانترِ سنگینی زدی!"
        )

    # ─── شکست خورد ───────────────────────────────────────────
    if result.get("enemy_dmg", 0) > 0:
        result["enemy_dmg"] = int(result["enemy_dmg"] * LATE_PENALTY_MULT)
        result["counter"] = True
    else:
        # اگه از قبل قرار نبود دشمن ضدحمله کنه، حداقل یه ضربه‌ی مجازاتی می‌خوره
        result["counter"] = True
        result["enemy_dmg"] = max(result.get("enemy_dmg", 0), int(enemy.get("dmg", 10) * 0.8))
    return f"🥊 **پری ناموفق!** (⏱️{rt:.1f}s) دیر واکنش نشون دادی و ضدحمله‌ی دشمن رو کامل خوردی."
