# -*- coding: utf-8 -*-
"""
ownership.py

🔒 ابزار مشترک برای جلوگیری از باگِ «استفاده از پنلِ پلیرِ دیگه».

مشکل: خیلی از دکمه‌های اینلاین (مثلِ «▶️ ادامه»، «⚔️ نبرد»، «🎒
کوله‌پشتی») یه پیام رو ویرایش می‌کنن بر اساسِ دیتای پلیریِ که
`cb.from_user.id`ه — نه صاحبِ واقعیِ اون پیام. تو یه گروه، هرکسی
می‌تونه رو دکمه‌ی پیامِ یه پلیرِ دیگه بزنه و دیتای خودش رو تو پیامِ
اون یکی بارگذاری کنه (باگی که تو quest_handlers.py پیدا و فیکس شد).

راه‌حل: هر جا دکمه‌ای برای یه پلیرِ خاص ساخته می‌شه، آیدیِ اون پلیر
باید تو خودِ callback_data باشه، و هندلر با این دکوریتور تزئین بشه.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
نحوه‌ی استفاده
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

۱) موقعِ ساختنِ دکمه، آیدیِ صاحبش رو تو callback_data بذار — همیشه
   بعد از پیشوند و قبل از بقیه‌ی آرگومان‌ها:

    InlineKeyboardButton(
        text="▶️ ادامه",
        callback_data=f"qst_next:{owner_uid}:{next_node_id}",
    )

۲) هندلرش رو با @user_only تزئین کن. این دکوریتور خودش قسمتِ دومِ
   callback_data (بعد از اولین ':') رو به‌عنوانِ آیدیِ صاحب می‌خونه،
   با cb.from_user.id مقایسه می‌کنه، و اگه مطابقت نداشت، خودکار یه
   alert می‌فرسته و اجازه نمی‌ده تابع اجرا بشه — دیگه لازم نیست تو
   بدنه‌ی هر هندلر این چک رو دستی بنویسی:

    @user_only
    async def cb_quest_next(cb: CallbackQuery, owner_uid: int, rest: str):
        # rest = بقیه‌ی callback_data بعد از آیدی (اینجا: next_node_id)
        next_id = rest
        ...

   تابعت باید ۳ تا آرگومان بگیره: cb، owner_uid (که دکوریتور خودش
   استخراج و به int تبدیلش کرده)، و rest (باقیِ رشته‌ی بعد از
   آیدی، دقیقاً همونی که تو callback_data بعد از پیشوند:آیدی: اومده).
"""

import functools
from aiogram.types import CallbackQuery

OWNERSHIP_DENIED_MSG = "❌ این پیام برای تو نیست. برای شروع/ادامه‌ی کار خودت، دستورِ مربوطه رو خودت بزن."


def user_only(handler):
    """
    دکوریتورِ هندلرهای callback_query که پیامِ یه پلیرِ خاص رو
    ویرایش می‌کنن. انتظار داره callback_data به فرمِ زیر باشه:

        <prefix>:<owner_uid>:<rest...>

    اگه کلیک‌کننده (cb.from_user.id) با <owner_uid> فرق داشته
    باشه، هندلر اصلاً اجرا نمی‌شه و فقط یه alert نشون داده می‌شه.
    """
    @functools.wraps(handler)
    async def wrapper(cb: CallbackQuery, *args, **kwargs):
        try:
            _, owner_s, rest = cb.data.split(":", 2)
            owner_uid = int(owner_s)
        except (ValueError, AttributeError):
            await cb.answer("❌ خطا در پردازشِ دکمه!", show_alert=True)
            return
        if owner_uid != cb.from_user.id:
            await cb.answer(OWNERSHIP_DENIED_MSG, show_alert=True)
            return
        return await handler(cb, owner_uid, rest, *args, **kwargs)
    return wrapper


def user_only_no_rest(handler):
    """
    مثلِ user_only، ولی برای دکمه‌هایی که بعد از آیدیِ صاحب هیچ
    آرگومانِ دیگه‌ای ندارن (فرمت: <prefix>:<owner_uid>).
    """
    @functools.wraps(handler)
    async def wrapper(cb: CallbackQuery, *args, **kwargs):
        try:
            _, owner_s = cb.data.split(":", 1)
            owner_uid = int(owner_s)
        except (ValueError, AttributeError):
            await cb.answer("❌ خطا در پردازشِ دکمه!", show_alert=True)
            return
        if owner_uid != cb.from_user.id:
            await cb.answer(OWNERSHIP_DENIED_MSG, show_alert=True)
            return
        return await handler(cb, owner_uid, *args, **kwargs)
    return wrapper
