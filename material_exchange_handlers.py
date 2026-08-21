# ============================================================
#  ASTRAL ABYSS — Material Exchange Handlers (Telegram UI)
# ------------------------------------------------------------
#  دکمه‌ی «🔄 صرافیِ متریال» تو منوی کارگاه (crafting_handlers.py)
#  به cb_mex_home وصله. تبدیلِ دسته‌جمعیِ همه‌ی متریال‌های نقشه‌ایِ
#  کوله‌پشتی، یک‌جا، به دسته‌ی موردنظر — راهِ سریع برای خالی‌کردنِ
#  انبارِ آیتمِ بی‌مصرف و تبدیلش به چیزی که واقعاً تو Forge/Alchemy
#  مصرف می‌شه.
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from logger import log_sync
import material_exchange as mex


def _owner_ok(cb: CallbackQuery, uid: int) -> bool:
    return cb.from_user.id == uid


def _home_text(player: dict) -> str:
    items = mex.exchangeable_items(player)
    if not items:
        return ("🔄 **صرافیِ متریال**\n\n"
                "کوله‌پشتیت خالی از متریالِ نقشه‌ایه — چیزی برای تبدیل نیست.\n"
                "برو گشت بزن، یه چیزی جمع کن، بعد بیا اینجا.")
    total_sell = sum(it.get("sell", 0) for _, it in items)
    return (f"🔄 **صرافیِ متریال**\n\n"
            f"متریال‌های نقشه‌ای (Sand Crystal، Divine Shard و امثالش) قبلاً فقط قابلِ‌فروش بودن.\n"
            f"الان می‌تونی یک‌جا تبدیلشون کنی به موادِ خامِ کارگاه که تو Forge/Alchemy مصرف می‌شن.\n\n"
            f"📦 {len(items)} آیتمِ قابل‌تبدیل تو کوله‌پشتیت | ارزشِ فروششون: {total_sell:,} Zen\n\n"
            f"دسته‌ای که می‌خوای بهش تبدیل بشن رو انتخاب کن:")


def _home_kb(uid: int) -> InlineKeyboardMarkup:
    rows = []
    for cat, label in mex.CATEGORY_LABELS.items():
        rows.append([InlineKeyboardButton(
            text=f"🔄 تبدیل همه → {label}",
            callback_data=f"mex_all:{cat}:{uid}",
            style=ButtonStyle.SUCCESS,
        )])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت به کارگاه", callback_data=f"cft_home:{uid}", style=ButtonStyle.DANGER)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_mex_home(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True); return
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    try:
        await cb.message.edit_text(_home_text(player), reply_markup=_home_kb(uid))
    except Exception:
        await cb.message.answer(_home_text(player), reply_markup=_home_kb(uid))
    await cb.answer()


async def cb_mex_all(cb: CallbackQuery):
    parts = cb.data.split(":")
    category, uid = parts[1], int(parts[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True); return
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    if category not in mex.CATEGORY_TIERS:
        await cb.answer("❌", show_alert=True); return

    count, gained = mex.convert_all(player, category)
    if count == 0:
        await cb.answer("چیزی برای تبدیل نداری.", show_alert=True)
        return
    await asave_player(uid, player)

    lines = "\n".join(f"  {label}: +{qty}" for label, qty in gained.items())
    log_sync(
        f"🔄 **MATERIAL EXCHANGE** | {player.get('name','—')} (`{uid}`)\n"
        f"📦 {count} آیتم → {category}\n{lines}",
        "ECONOMY"
    )
    await cb.answer(f"✅ {count} آیتم تبدیل شد!", show_alert=True)
    try:
        await cb.message.edit_text(_home_text(player), reply_markup=_home_kb(uid))
    except Exception:
        await cb.message.answer(_home_text(player), reply_markup=_home_kb(uid))


def register_material_exchange_handlers(dp, bot):
    dp.callback_query.register(cb_mex_home, F.data.startswith("mex_home:"))
    dp.callback_query.register(cb_mex_all,  F.data.startswith("mex_all:"))
