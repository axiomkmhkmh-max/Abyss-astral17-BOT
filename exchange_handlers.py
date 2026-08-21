# ============================================================
#  ASTRAL ABYSS — بورسِ آبیس: Handlers
# ============================================================
import time

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.enums import ButtonStyle
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from logger import log_sync
import exchange_system as ex

_awaiting_text: dict[int, tuple[str, float]] = {}   # uid -> (mode:"buy:<id>"|"sell:<id>", ttl)
EXCHANGE_TTL = 120


def _trend_arrow(price: float, prev: float) -> str:
    if price > prev:
        return "🟢▲"
    if price < prev:
        return "🔴▼"
    return "⚪️"


def _panel_text(player: dict) -> str:
    prices = ex.get_prices()
    h = ex.holdings(player)
    lines = ["📈 **بورسِ آبیس**\n"]
    for inst in ex.INSTRUMENTS:
        iid = inst["id"]
        p = prices[iid]
        arrow = _trend_arrow(p["price"], p["prev"])
        owned = h.get(iid, 0.0)
        lines.append(f"{p['name']}  {arrow}  **{p['price']:,.2f} Zen**")
        lines.append(f"   {p['desc']}")
        if owned > 0:
            value = owned * p["price"]
            lines.append(f"   💼 داری: {owned:.2f} واحد (ارزش: {value:,.0f} Zen)")
        lines.append("")
    total_value = ex.portfolio_value(player, prices)
    lines.append(f"💰 موجودیِ نقد: **{player.get('zen', 0):,} Zen**")
    lines.append(f"📊 ارزشِ کلِ پرتفوی: **{total_value:,.0f} Zen**")
    lines.append(f"\n🧾 کارمزدِ هر معامله: {int(ex.TRADE_FEE_PCT*100)}٪ (می‌ره تو صندوقِ مالیاتِ سراسری).")
    return "\n".join(lines)


def _kb() -> InlineKeyboardMarkup:
    rows = []
    for inst in ex.INSTRUMENTS:
        rows.append([
            InlineKeyboardButton(text=f"🟢 خریدِ {inst['name']}", callback_data=f"exch_buy:{inst['id']}", style=ButtonStyle.SUCCESS),
            InlineKeyboardButton(text=f"🔴 فروشِ {inst['name']}", callback_data=f"exch_sell:{inst['id']}", style=ButtonStyle.DANGER),
        ])
    rows.append([InlineKeyboardButton(text="🔄 به‌روزرسانی", callback_data="exch_refresh", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cmd_exchange(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    from level_gate import check_level
    ok, why = check_level(player, "exchange")
    if not ok:
        await msg.answer(why)
        return
    await msg.answer(_panel_text(player), reply_markup=_kb())


async def cb_exch_refresh(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    await cb.message.edit_text(_panel_text(player), reply_markup=_kb())
    await cb.answer()


async def cb_exch_buy(cb: CallbackQuery):
    inst_id = cb.data.split(":")[1]
    uid = cb.from_user.id
    inst = ex.INSTRUMENT_BY_ID.get(inst_id)
    if not inst:
        await cb.answer("❌", show_alert=True); return
    _awaiting_text[uid] = (f"buy:{inst_id}", time.time() + EXCHANGE_TTL)
    await cb.message.answer(
        f"🟢 **خریدِ {inst['name']}**\n\nچند Zen می‌خوای سرمایه‌گذاری کنی؟ فقط عدد بفرست.\n"
        f"(حداقل: {ex.MIN_TRADE_ZEN:,} Zen)"
    )
    await cb.answer()


async def cb_exch_sell(cb: CallbackQuery):
    inst_id = cb.data.split(":")[1]
    uid = cb.from_user.id
    player = await aget_player(uid)
    inst = ex.INSTRUMENT_BY_ID.get(inst_id)
    if not inst or not player:
        await cb.answer("❌", show_alert=True); return
    owned = ex.holdings(player).get(inst_id, 0.0)
    if owned <= 0:
        await cb.answer("❌ از این سهم چیزی نداری.", show_alert=True)
        return
    _awaiting_text[uid] = (f"sell:{inst_id}", time.time() + EXCHANGE_TTL)
    await cb.message.answer(
        f"🔴 **فروشِ {inst['name']}**\n\n"
        f"💼 الان **{owned:.2f}** واحد داری. چند واحد بفروشم؟ یه عدد بفرست، یا بنویس `همه`."
    )
    await cb.answer()


async def handle_exchange_text(msg: Message):
    uid = msg.from_user.id
    entry = _awaiting_text.get(uid)
    if not entry:
        return
    mode, expires = entry
    if time.time() > expires:
        del _awaiting_text[uid]
        await msg.answer("⏰ زمان تموم شد، دوباره از منوی بورس شروع کن.")
        return
    del _awaiting_text[uid]

    action, inst_id = mode.split(":", 1)
    text = (msg.text or "").strip()
    player = await aget_player(uid)
    if not player:
        return

    if action == "buy":
        if not (text.isdigit() and int(text) > 0):
            await msg.answer("❌ باید یه عددِ مثبت بفرستی!")
            return
        player["_uid"] = uid
        ok, res_msg = ex.buy(player, inst_id, int(text))
        await asave_player(uid, player)
        await msg.answer(res_msg)
        if ok:
            log_sync(f"📈 **EXCHANGE BUY**\n👤 {player.get('name', uid)} (`{uid}`)\n{res_msg}", "ECONOMY")
        return

    if action == "sell":
        if text in ("همه", "all", "همش"):
            shares = None
        else:
            try:
                shares = float(text)
                if shares <= 0:
                    raise ValueError
            except ValueError:
                await msg.answer("❌ یه عددِ مثبت بفرست یا بنویس `همه`.")
                return
        player["_uid"] = uid
        ok, res_msg = ex.sell(player, inst_id, shares)
        await asave_player(uid, player)
        await msg.answer(res_msg)
        if ok:
            log_sync(f"📈 **EXCHANGE SELL**\n👤 {player.get('name', uid)} (`{uid}`)\n{res_msg}", "ECONOMY")
        return


def register_exchange_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_exchange, Command("exchange"))
    dp.callback_query.register(cb_exch_refresh, F.data == "exch_refresh")
    dp.callback_query.register(cb_exch_buy,     F.data.startswith("exch_buy:"))
    dp.callback_query.register(cb_exch_sell,    F.data.startswith("exch_sell:"))
    dp.message.register(handle_exchange_text, lambda m: m.from_user.id in _awaiting_text)
