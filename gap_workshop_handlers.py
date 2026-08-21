# ============================================================
#  ASTRAL ABYSS — Workshop Entry Point (Gap UI)
# ------------------------------------------------------------
#  نکته‌ی مهم: خودِ منوی کاملِ کارگاهِ تلگرام (crafting_handlers.py —
#  میزِ آهنگری/کیمیاگری/کاوش/تجزیه/سوکت/ریرول) هنوز رو گپ پورت نشده
#  (طبق ROADMAP_GAP.md). این فایل فقط یه ورودیِ سبک می‌سازه که سه
#  سیستمِ تازه‌پورت‌شده رو در دسترس می‌ذاره:
#    🔄 صرافیِ متریال | 🗺️ دستورهای ویژه‌ی نقشه | 📯 کدکسِ کالکشن
#  وقتی بقیه‌ی کارگاه (فورج/آلکمی/گدرینگ) هم پورت شد، کافیه دکمه‌هاشون
#  اینجا به _workshop_kb اضافه بشه — چیزِ دیگه‌ای نیاز به تغییر نداره.
# ============================================================
from gap_dispatcher import GapDispatcher
from gap_types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, aget_player
import crafting_system as cfs


def _workshop_text(player: dict) -> str:
    return (
        cfs.crafting_summary_text(player)
        + "\n\n_(میزِ آهنگری/کیمیاگری و کاوشِ مواد فعلاً فقط رو تلگرام در دسترسن — "
          "به‌زودی رو گپ هم میان.)_"
    )


def _workshop_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 صرافیِ متریال", callback_data="mex_home")],
        [InlineKeyboardButton(text="🗺️ دستورهای ویژه‌ی نقشه", callback_data="mrc_home")],
        [InlineKeyboardButton(text="📯 کدکسِ کالکشن", callback_data="cdx_home")],
        [InlineKeyboardButton(text="🏠 پنل اصلی", callback_data="menu:home")],
    ])


async def cmd_workshop(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    await msg.answer(_workshop_text(player), reply_markup=_workshop_kb())


async def cb_workshop_home(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    try:
        await cb.message.edit_text(_workshop_text(player), reply_markup=_workshop_kb())
    except Exception:
        await cb.message.answer(_workshop_text(player), reply_markup=_workshop_kb())
    await cb.answer()


def register_gap_workshop_handlers(dp: GapDispatcher):
    from gap_material_exchange_handlers import register_gap_material_exchange_handlers
    from gap_map_recipes_handlers import register_gap_map_recipes_handlers
    from gap_collection_codex_handlers import register_gap_collection_codex_handlers

    register_gap_material_exchange_handlers(dp)
    register_gap_map_recipes_handlers(dp)
    register_gap_collection_codex_handlers(dp)

    dp.register_message(cmd_workshop, commands=["workshop", "kargah", "craft"])
    dp.register_callback(cb_workshop_home, data="wsp:home")
