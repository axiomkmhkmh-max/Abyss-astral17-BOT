# ============================================================
#  ASTRAL ABYSS — Material Exchange Handlers (Gap UI)
# ------------------------------------------------------------
#  پورتِ material_exchange_handlers.py (تلگرام) برای گپ. منطقِ خالص
#  (material_exchange.py) عیناً importه — فقط کیبورد/دکوریتور عوض شده.
#  چون خودِ منویِ کارگاهِ تلگرام (crafting_handlers.py) هنوز رو گپ
#  پورت نشده، دکمه‌ی برگشت به‌جای cft_home به منوی کوچیکِ کارگاهِ گپ
#  (gap_workshop_handlers.wsp:home) وصل می‌شه.
# ============================================================
from gap_dispatcher import GapDispatcher
from gap_types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
from logger import log_sync
import material_exchange as mex

WORKSHOP_BACK_CB = "wsp:home"


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


def _home_kb() -> InlineKeyboardMarkup:
    rows = []
    for cat, label in mex.CATEGORY_LABELS.items():
        rows.append([InlineKeyboardButton(text=f"🔄 تبدیل همه → {label}", callback_data=f"mex_all:{cat}")])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت به کارگاه", callback_data=WORKSHOP_BACK_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_mex_home(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    try:
        await cb.message.edit_text(_home_text(player), reply_markup=_home_kb())
    except Exception:
        await cb.message.answer(_home_text(player), reply_markup=_home_kb())
    await cb.answer()


async def cb_mex_all(cb: CallbackQuery):
    uid = cb.from_user.id
    category = cb.data.split(":", 1)[1]
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    if category not in mex.CATEGORY_TIERS:
        await cb.answer("❌", show_alert=True)
        return

    count, gained = mex.convert_all(player, category)
    if count == 0:
        await cb.answer("چیزی برای تبدیل نداری.", show_alert=True)
        return
    save_player(uid, player)

    lines = "\n".join(f"  {label}: +{qty}" for label, qty in gained.items())
    log_sync(
        f"🔄 **MATERIAL EXCHANGE (GAP)** | {player.get('name','—')} (`{uid}`)\n"
        f"📦 {count} آیتم → {category}\n{lines}",
        "ECONOMY"
    )
    await cb.answer(f"✅ {count} آیتم تبدیل شد!", show_alert=True)
    try:
        await cb.message.edit_text(_home_text(player), reply_markup=_home_kb())
    except Exception:
        await cb.message.answer(_home_text(player), reply_markup=_home_kb())


def register_gap_material_exchange_handlers(dp: GapDispatcher):
    dp.register_callback(cb_mex_home, data="mex_home")
    dp.register_callback(cb_mex_all, data_startswith="mex_all:")
