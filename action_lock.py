# ============================================================
#  ASTRAL ABYSS — Action Lock (Anti Double-Tap / Anti Dupe)
# ------------------------------------------------------------
#  باگ‌فیکس: تا قبل از این، یه هندلر مثل «حمله» این‌شکلی بود:
#    ۱) get_player  ۲) چکِ کول‌داون  ۳) محاسبه‌ی جایزه  ۴) ست‌کردنِ
#    کول‌داون  ۵) save_player
#  اگه کاربر خیلی سریع (دابل-تپ) رو دکمه می‌زد، دو تا ریکوئست
#  هم‌زمان اجرا می‌شدن و چون کول‌داون فقط تو مرحله‌ی ۴ ست می‌شد، هر
#  دو ریکوئست از چکِ مرحله‌ی ۲ رد می‌شدن — یعنی کاربر می‌تونست با
#  چند تا تپِ پشتِ‌سرِهم، چند برابرِ عادی Zen/XP بگیره (اکسپلویتِ
#  دوپلیکیت). این ماژول با یه قفلِ ساده به‌ازای هر uid جلوی اجرای
#  هم‌زمانِ دوباره‌ی همون اکشن رو می‌گیره: تپِ دوم رد می‌شه (نه صف)،
#  کاربر بلافاصله فیدبک می‌گیره که «صبر کن»، نه این‌که منتظر بمونه.
# ============================================================
import asyncio
from functools import wraps

_locks: dict[int, asyncio.Lock] = {}


def _get_lock(uid: int) -> asyncio.Lock:
    lock = _locks.get(uid)
    if lock is None:
        lock = asyncio.Lock()
        _locks[uid] = lock
    return lock


def no_double_tap(get_uid=lambda cb: cb.from_user.id, busy_msg: str = "⏳ اکشن قبلی هنوز در حال پردازشه، یه لحظه صبر کن!"):
    """
    دکوریتور برای هندلرهای callback_query/message. اگه همون کاربر یه
    اکشنِ قبلی (با همین دکوریتور) هنوز در حالِ پردازش داشته باشه،
    اکشنِ جدید رد می‌شه به‌جای این‌که هم‌زمان اجرا بشه.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(event, *args, **kwargs):
            uid = get_uid(event)
            lock = _get_lock(uid)
            if lock.locked():
                try:
                    await event.answer(busy_msg, show_alert=True)
                except Exception:
                    pass
                return
            async with lock:
                return await func(event, *args, **kwargs)
        return wrapper
    return decorator
