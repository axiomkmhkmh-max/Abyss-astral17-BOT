# ============================================================
#  ASTRAL ABYSS RPG — Passive HP Regeneration
# ------------------------------------------------------------
#  بعد از اینکه بازیکن دمیج می‌خوره، به مدتِ REGEN_DELAY_SECONDS
#  هیچ ریجنی اتفاق نمی‌افته (تازه از نبرد خارج شده). بعد از اون
#  فاصله، HP به‌آرومی و بر اساسِ زمانِ واقعیِ سپری‌شده شارژ می‌شه —
#  یعنی حتی اگه بازیکن آفلاین باشه، دفعه‌ی بعد که پروفایلش لود
#  بشه (get_player)، دلتای زمان محاسبه و HP بهش اضافه می‌شه.
#
#  این ماژول عمداً «lazy/idempotent» طراحی شده (مثلِ الگوی
#  _sync_pending_levelups تو database.py) — هیچ background loop
#  یا jobِ زمان‌بندی‌شده‌ای لازم نداره و برای هزاران بازیکنِ
#  همزمان هم سبک می‌مونه.
# ============================================================
import time

REGEN_DELAY_SECONDS = 6          # چند ثانیه بعد از آخرین دمیج، ریجن شروع می‌شه
REGEN_PERCENT_PER_SECOND = 0.008  # هر ثانیه ٪۰.۸ از Max HP (پرشدنِ کامل ≈ ۲ دقیقه)
REGEN_MIN_PER_SECOND = 0.5        # کف مطلق، برای بازیکن‌های Max HP پایین


def _effective_max_hp(player: dict) -> int:
    try:
        from skill_tree import effective_max_hp
        return effective_max_hp(player)
    except Exception:
        return player.get("max_hp", 100)


def is_regen_blocked(player: dict) -> bool:
    """قفل‌های خاصِ گیم (مثلاً heal_lockout_until بعدِ مرگِ حالت‌سخت) که
    نباید باهاشون ریجنِ غیرفعال قاطی بشه."""
    return time.time() < player.get("heal_lockout_until", 0)


def mark_damage_taken(player: dict) -> None:
    """اختیاری: هر جا صریحاً بخوای تایمرِ ریجن رو ریست کنی می‌تونی صداش بزنی.
    در عمل database.save_player این کار رو خودکار تشخیص می‌ده، پس صدا زدنِ
    دستیِ این تابع لازم نیست — فقط برای موارد خاص نگه داشته شده."""
    player["last_damage_ts"] = time.time()


def apply_passive_regen(player: dict) -> bool:
    """اگه به اندازه‌ی کافی از آخرین دمیج گذشته باشه، بر اساسِ زمانِ واقعی
    سپری‌شده HP رو شارژ می‌کنه. خروجی True یعنی چیزی تغییر کرد (باید ذخیره بشه)."""
    hp = player.get("hp", 0)
    max_hp = _effective_max_hp(player)
    now = time.time()

    if hp <= 0 or hp >= max_hp:
        player["hp_regen_last_ts"] = now
        return False

    if is_regen_blocked(player):
        return False

    last_damage_ts = player.get("last_damage_ts", 0)
    regen_can_start_at = last_damage_ts + REGEN_DELAY_SECONDS
    anchor = max(regen_can_start_at, player.get("hp_regen_last_ts", 0))

    if now <= anchor:
        return False

    elapsed = now - anchor

    try:
        from house_system import hp_regen_bonus
        house_bonus = hp_regen_bonus(player)  # ۰ تا ۰.۱۵ بسته به سطحِ خونه
    except Exception:
        house_bonus = 0.0

    per_second = max(max_hp * REGEN_PERCENT_PER_SECOND, REGEN_MIN_PER_SECOND)
    per_second *= (1 + house_bonus)

    healed = elapsed * per_second
    new_hp = min(max_hp, hp + healed)

    if new_hp - hp < 0.5:
        # تغییرِ ناچیز — صرفه‌جویی تو نوشتنِ دیتابیس، ولی anchor رو جلو نمی‌بریم
        # تا دفعه‌ی بعد همون دلتای زمان محاسبه بشه.
        return False

    player["hp"] = int(round(new_hp))
    player["hp_regen_last_ts"] = now
    return True
