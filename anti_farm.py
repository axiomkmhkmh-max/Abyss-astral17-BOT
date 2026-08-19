# ============================================================
#  ASTRAL ABYSS — Anti-Farm Guard
#  جلوگیری از فارم بیش‌ازحدِ Zen/XP: سقفِ نرمِ روزانه + کپ‌کردنِ
#  بونوس‌های درصدیِ استکی + هشدار لاگ برای الگوهای مشکوک.
#
#  ⚠️ باگ‌فیکس: این ماژول تو mob_combat.py و combat_handlers.py
#  ایمپورت می‌شد (`import anti_farm as af`) ولی خودِ فایلش اصلاً
#  تو پروژه وجود نداشت. نتیجه: دقیقاً وسطِ محاسبه‌ی پاداشِ کشتنِ
#  هر دشمن (چه از /loot چه از /attack)، بلافاصله بعد از پیامِ
#  «در حال شمارش غنائم...»، پایتون ModuleNotFoundError می‌داد و
#  کل هندلر کرش می‌کرد — همون چیزی که تو کلاینت به‌شکلِ
#  «یه مشکلی پیش اومد، دوباره امتحان کن!» دیده می‌شد.
# ============================================================
import time
import statistics

# ─── کَپِ سقفِ بونوس‌های درصدیِ استکی (zen_gain_pct / xp_gain_pct و...) ─
MAX_STACKED_BONUS_PCT = 0.75   # هیچ‌وقت مجموع بونوس‌ها بیشتر از ۷۵٪ نمی‌شه

# ─── سقفِ نرمِ روزانه‌ی Zen/XP — بعد از این حد، جایزه‌ها کم‌کم افت می‌کنن ─
# قبلاً 50,000 Zen / 20,000 XP بود — خیلی سخاوتمند بود، همین باعث می‌شد
# یه بازیکنِ گرایندی تو ۲-۳ روز به لول ۱۷ و ۱۳۸ هزار Zen برسه. عددها
# به‌طور محسوس کم شدن؛ سازوکار «نرم» (افتِ تدریجی به‌جای قطعِ کامل)
# طبق درخواست دست‌نخورده موند.
DAILY_SOFT_CAP = {
    "zen": 8_000,
    "xp": 3_000,
}
DAILY_RESET = 86400  # 24 ساعت

# ─── آستانه‌ی مشکوک‌بودنِ یه برد تکی (برای لاگِ هشدار) ────────────
SUSPICIOUS_ZEN_THRESHOLD = 5_000
SUSPICIOUS_XP_THRESHOLD = 2_000
ALERT_THROTTLE_SEC = 300  # هر uid حداکثر هر ۵ دقیقه یه‌بار لاگ هشدار می‌گیره

_last_alert_at: dict[int, float] = {}  # uid -> timestamp آخرین هشدار (فقط throttle لاگ، حیاتی نیست)


def cap_bonus(pct: float) -> float:
    """جلوگیری از استک شدنِ بی‌نهایتِ بونوس‌های درصدیِ zen/xp."""
    if not pct:
        return 0.0
    return max(0.0, min(pct, MAX_STACKED_BONUS_PCT))


# ─── باگ‌فیکس: قبلاً سقفِ روزانه تو یه dict در حافظه‌ی پروسه نگه‌داری
# می‌شد نه تو خودِ رکوردِ بازیکن. یعنی با هر ری‌استارت/دیپلویِ ربات
# سقفِ همه صفر می‌شد و می‌تونستن همون لحظه دوباره فارم کنن. الان مقدارِ
# روزانه مستقیم رو خودِ player ذخیره می‌شه (با همون save_player که
# بعد از هر نبرد صدا زده می‌شه، تو دیتابیس هم می‌مونه).
def _ensure_daily(player: dict):
    now = time.time()
    if now >= player.get("af_reset_at", 0):
        player["af_zen_today"] = 0
        player["af_xp_today"] = 0
        player["af_reset_at"] = now + DAILY_RESET


def daily_mult(player: dict, kind: str) -> float:
    """
    هرچی به سقفِ نرمِ روزانه نزدیک‌تر بشی، ضریبِ دریافتیِ Zen/XP
    کم‌کم کمتر می‌شه (افتِ تدریجی، نه قطعِ ناگهانی).
    """
    _ensure_daily(player)
    cap = DAILY_SOFT_CAP.get(kind, 0)
    if cap <= 0:
        return 1.0
    total = player.get(f"af_{kind}_today", 0)
    ratio = total / cap
    if ratio < 0.7:
        return 1.0
    if ratio < 1.0:
        return 0.75
    if ratio < 1.5:
        return 0.4
    return 0.15


def register_daily_gain(player: dict, kind: str, amount: int):
    """مقدارِ Zen/XP گرفته‌شده رو برای محاسبه‌ی سقفِ روزانه ثبت می‌کنه (رو خودِ پروفایل)."""
    if amount <= 0:
        return
    _ensure_daily(player)
    key = f"af_{kind}_today"
    player[key] = player.get(key, 0) + amount


def log_if_suspicious(uid: int, name: str, zen_gain: int, xp_gain: int, source: str):
    """اگه یه برد تکی خیلی بزرگ بود، تو کانالِ لاگ هشدار می‌ده (با throttle)."""
    if zen_gain < SUSPICIOUS_ZEN_THRESHOLD and xp_gain < SUSPICIOUS_XP_THRESHOLD:
        return
    now = time.time()
    if now - _last_alert_at.get(uid, 0) < ALERT_THROTTLE_SEC:
        return
    _last_alert_at[uid] = now
    try:
        from logger import log_sync
        log_sync(
            f"⚠️ **دریافتِ مشکوک**\n"
            f"👤 {name} (`{uid}`)\n"
            f"💰 Zen: +{zen_gain} | ✨ XP: +{xp_gain}\n"
            f"📍 منبع: {source}",
            "WARN"
        )
    except Exception:
        pass


# ============================================================
#  تشخیصِ الگوی رفتاریِ مشکوک (بات/اسکریپت) — نه فقط سقفِ عددی
# ------------------------------------------------------------
#  سقفِ روزانه‌ی بالا فقط جلوی «فارمِ زیاد» رو می‌گیره، ولی یه اسکریپتِ
#  خودکار که هر ۲ ثانیه دقیق /attack می‌زنه رو تشخیص نمی‌ده چون شاید
#  اصلاً به سقف نرسیده باشه. اینجا فاصله‌ی زمانیِ بینِ چند اکشنِ آخرِ
#  هر بازیکن رو نگه می‌داریم و دو چیز رو با هم چک می‌کنیم:
#    ۱) سرعت: میانگینِ فاصله‌ها سریع‌تر از یه انسانِ عادیه؟
#    ۲) یکنواختی: واریانسِ نسبیِ فاصله‌ها خیلی پایینه؟ (آدم‌ها نامنظمن،
#       اسکریپت‌ها معمولاً تقریباً دقیق یه فاصله‌ی ثابت دارن)
#  فقط وقتی *هر دو* با هم صادق باشن هشدار می‌ده — تا false-positive
#  رو برای بازیکنِ سریع ولی معمولی کم کنه. این تابع چیزی رو بلاک
#  نمی‌کنه، فقط لاگِ هشدار می‌ده تا ادمین دستی تصمیم بگیره.
# ============================================================
BEHAVIOR_WINDOW = 12                # چند اکشنِ آخر رو نگه می‌داریم و تحلیل می‌کنیم
MIN_HUMAN_INTERVAL_SEC = 1.2        # کمتر از این، برای کلیک/تایپِ پشتِ‌سرهم انسانی غیرعادیه
UNIFORM_VARIANCE_THRESHOLD = 0.12   # واریانسِ نسبیِ زیرِ این یعنی فاصله‌ها تقریباً ثابتن (ماشینی)
BEHAVIOR_ALERT_THROTTLE_SEC = 900   # هر uid حداکثر هر ۱۵ دقیقه یه‌بار این هشدار رو می‌گیره

_last_behavior_alert: dict[int, float] = {}


def register_action_time(player: dict, uid: int, name: str, source: str) -> None:
    """
    هر بار که یه اکشنِ حساس (attack/loot/bosshit) انجام می‌شه صدا زده
    می‌شه. timestamp رو رو خودِ رکوردِ پلیر نگه می‌داره (پایدار بینِ
    ری‌استارت‌ها، برخلافِ لاگِ throttle که فقط تو حافظه‌ی پروسه‌ست).
    """
    now = time.time()
    times = player.setdefault("af_action_times", [])
    times.append(now)
    if len(times) > BEHAVIOR_WINDOW:
        del times[: len(times) - BEHAVIOR_WINDOW]

    if len(times) < BEHAVIOR_WINDOW:
        return

    intervals = [t2 - t1 for t1, t2 in zip(times, times[1:])]
    mean_gap = sum(intervals) / len(intervals)
    if mean_gap <= 0:
        return

    rel_variance = statistics.pstdev(intervals) / mean_gap
    too_fast = mean_gap < MIN_HUMAN_INTERVAL_SEC
    too_uniform = rel_variance < UNIFORM_VARIANCE_THRESHOLD
    if not (too_fast and too_uniform):
        return

    last = _last_behavior_alert.get(uid, 0)
    if now - last < BEHAVIOR_ALERT_THROTTLE_SEC:
        return
    _last_behavior_alert[uid] = now
    try:
        from logger import log_sync
        log_sync(
            f"🤖 **الگوی رفتاریِ مشکوک — احتمالِ بات/اسکریپت**\n"
            f"👤 {name} (`{uid}`)\n"
            f"⏱️ میانگینِ فاصله بینِ اکشن‌ها: {mean_gap:.2f}s | یکنواختی: {rel_variance:.2f}\n"
            f"📍 منبع: {source} — این فقط هشداره، چیزی خودکار بلاک نشده.",
            "WARN"
        )
    except Exception:
        pass
