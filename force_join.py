# ============================================================
#  ASTRAL ABYSS — جوینِ اجباری (Force Join Gate)
# ------------------------------------------------------------
#  قبل از استفاده از هر بخشی از ربات، بازیکن باید عضوِ گپ و
#  کانالِ رسمیِ بازی باشه. این ماژول دو چیز می‌سازه:
#
#   ۱) چک عضویت (bot.get_chat_member) روی کانال و گروه.
#   ۲) یه middleware که رو همه‌ی پیام‌ها و دکمه‌های شیشه‌ای نصب
#      می‌شه؛ اگه عضو نبود، به‌جای رسیدن به هندلرِ اصلی، یه پیامِ
#      «اول جوین کن» با دکمه‌های Join + دکمه‌ی «✅ عضو شدم» نشون
#      داده می‌شه.
#
#  ⚠️ نکته‌ی مهم درباره‌ی گروه:
#  لینکِ گروه یه لینکِ دعوتِ خصوصیه (https://t.me/+...)، و API
#  تلگرام از رویِ همچین لینکی نمی‌تونه chat_id عددی رو خودش پیدا
#  کنه — فقط با chat_id عددی می‌شه عضویت رو واقعاً چک کرد. برای
#  فعال‌شدنِ چکِ گروه:
#    ۱) ربات رو به‌عنوان ادمین به گروه اضافه کن.
#    ۲) هرکسی (خودت) تو گروه دستورِ /getgroupid رو بزنه — ربات
#       chat_id عددیِ همون گروه رو جواب می‌ده.
#    ۳) اون عدد رو تو Environment Variable به اسمِ FORCE_JOIN_GROUP_ID
#       ست کن و ربات رو ری‌استارت کن.
#  تا وقتی این عدد ست نشده، فقط عضویتِ کانال چک می‌شه (چون کانال
#  عمومیه و با یوزرنیم قابلِ چکه) و دکمه‌ی گروه فقط برای دعوت
#  نمایش داده می‌شه، بدون اینکه واقعاً بلاک کنه.
# ============================================================
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.enums import ButtonStyle, ChatMemberStatus

# ─── تنظیمات ─────────────────────────────────────────────────
GROUP_LINK   = "https://t.me/+zOY3-jx2gbUxOWY0"
CHANNEL_LINK = "https://t.me/ASTRALABYSSChannel"
CHANNEL_REF  = "@ASTRALABYSSChannel"   # کانال عمومیه، پس با یوزرنیم قابلِ چکه

_raw_group_id = os.getenv("FORCE_JOIN_GROUP_ID", "").strip()
GROUP_CHAT_ID: int | None = int(_raw_group_id) if _raw_group_id.lstrip("-").isdigit() else None

_JOINED_STATUSES = {
    ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR,
}

# ادمین‌ها هیچ‌وقت پشتِ این گیت گیر نمی‌کنن (برای پشتیبانی/تست)
try:
    from admin_panel import ADMIN_IDS
except Exception:
    ADMIN_IDS = set()


async def _is_member(bot: Bot, chat_ref, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_ref, user_id)
        return member.status in _JOINED_STATUSES
    except Exception:
        # اگه ربات ادمینِ اون چت نباشه یا هر خطای دیگه‌ای پیش بیاد،
        # به‌جای بلاک‌کردنِ کاذبِ همه، عبور می‌دیم (fail-open) — یه
        # گیتِ خراب نباید کلِ بازی رو برای همه قفل کنه.
        return True


async def get_missing_joins(bot: Bot, user_id: int) -> list[dict]:
    """لیستِ جاهایی که بازیکن هنوز عضو نیست (برای ساختِ پیام/کیبورد)."""
    missing = []
    if not await _is_member(bot, CHANNEL_REF, user_id):
        missing.append({"name": "📢 کانال رسمی", "url": CHANNEL_LINK})
    if GROUP_CHAT_ID is not None:
        if not await _is_member(bot, GROUP_CHAT_ID, user_id):
            missing.append({"name": "💬 گپ رسمی", "url": GROUP_LINK})
    return missing


def join_gate_kb(missing: list[dict]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=m["name"], url=m["url"], style=ButtonStyle.PRIMARY)]
        for m in missing
    ]
    buttons.append([InlineKeyboardButton(
        text="✅ عضو شدم، بررسی کن", callback_data="fj:check", style=ButtonStyle.SUCCESS)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


JOIN_GATE_TEXT = (
    "🔒 **برای استفاده از ربات اول باید عضوِ این‌ها بشی:**\n\n"
    "بعدِ جوین‌شدن رو دکمه‌ی «✅ عضو شدم» بزن."
)


async def cb_check_join(cb: CallbackQuery, bot: Bot):
    uid = cb.from_user.id
    missing = await get_missing_joins(bot, uid)
    if missing:
        await cb.answer("❌ هنوز همه‌جا رو جوین نکردی!", show_alert=True)
        try:
            await cb.message.edit_reply_markup(reply_markup=join_gate_kb(missing))
        except Exception:
            pass
        return
    await cb.answer("✅ خوش اومدی! حالا دوباره دستور/دکمه‌ی موردنظرت رو بزن.", show_alert=True)
    try:
        await cb.message.edit_text("🎉 عضویتت تایید شد! حالا می‌تونی از ربات استفاده کنی.")
    except Exception:
        pass


async def cmd_get_group_id(msg: Message):
    """کمکی برای پیداکردنِ chat_id عددیِ گروه (فقط همین‌جا کاربرد داره،
    برای ست‌کردنِ FORCE_JOIN_GROUP_ID)."""
    await msg.answer(f"🆔 chat_id این گروه: `{msg.chat.id}`")


def register_force_join(dp: Dispatcher, bot: Bot):
    from aiogram.filters import Command

    dp.message.register(cmd_get_group_id, Command("getgroupid"))

    async def _cb_check(c: CallbackQuery):
        await cb_check_join(c, bot)
    dp.callback_query.register(_cb_check, F.data == "fj:check")

    @dp.message.middleware()
    async def force_join_message_middleware(handler, event: Message, data: dict):
        uid = event.from_user.id if event.from_user else None
        # فقط تو PV گیت می‌زنیم — تو گروه/سوپرگروه خودِ عضویت تو همون
        # چت شرطِ حضوره، جوینِ اجباری اونجا معنی نداره.
        if uid and event.chat and event.chat.type == "private" and uid not in ADMIN_IDS:
            missing = await get_missing_joins(bot, uid)
            if missing:
                await event.answer(JOIN_GATE_TEXT, reply_markup=join_gate_kb(missing))
                return
        return await handler(event, data)

    @dp.callback_query.middleware()
    async def force_join_callback_middleware(handler, event: CallbackQuery, data: dict):
        uid = event.from_user.id if event.from_user else None
        if event.data == "fj:check":
            return await handler(event, data)
        if (
            uid and event.message and event.message.chat
            and event.message.chat.type == "private" and uid not in ADMIN_IDS
        ):
            missing = await get_missing_joins(bot, uid)
            if missing:
                await event.answer("🔒 اول باید جوین کنی!", show_alert=True)
                try:
                    await event.message.edit_text(JOIN_GATE_TEXT, reply_markup=join_gate_kb(missing))
                except Exception:
                    pass
                return
        return await handler(event, data)
