# ============================================================
#  ASTRAL ABYSS — Black Market Expansion Handlers (Telegram UI)
# ------------------------------------------------------------
#  سه دکمه‌ی جدید به منوی بازارِ سیاه (bm_main_kb تو loot_handlers.py)
#  اضافه می‌کنه:
#    🏷️ رتبه‌ی دیلر      — نمایشِ رتبه + نردبانِ کامل
#    🕴️ دیلرهای گردشی    — موجودیِ محدود + ریسکِ گیرافتادن
#    📦 تابلوی قاچاق      — سفارش‌گذاریِ بازیکن‌محور
#  منطقِ خالص از black_market_reputation.py, black_market_dealers.py,
#  smuggling_contracts.py میاد — اینجا فقط UI/دکوریتوره.
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
from logger import log_sync
import black_market_reputation as bmrep
import black_market_dealers as deal
import smuggling_contracts as smug


def _owner_ok(cb: CallbackQuery, uid: int) -> bool:
    return cb.from_user.id == uid


def _back_bm_kb(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔙 برگشت به بازار", callback_data="bm:back", style=ButtonStyle.DANGER)
    ]])


# ─── 🏷️ رتبه‌ی دیلر ─────────────────────────────────────────────
async def cb_bm_rank(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    text = bmrep.tier_progress_text(player) + "\n\n" + bmrep.all_tiers_text()
    try:
        await cb.message.edit_text(text, reply_markup=_back_bm_kb(uid))
    except Exception:
        await cb.message.answer(text, reply_markup=_back_bm_kb(uid))
    await cb.answer()


# ─── 🕴️ دیلرهای گردشی ───────────────────────────────────────────
def _dealers_list_kb(uid: int) -> InlineKeyboardMarkup:
    rows = []
    for d in deal.active_dealers():
        left = int(d["expires_at"] - __import__("time").time())
        rows.append([InlineKeyboardButton(
            text=f"{d['emoji']} {d['name']} — {d['_id']} ({left//60}m)",
            callback_data=f"deal_view:{d['_id']}"
        )])
    if not rows:
        rows.append([InlineKeyboardButton(text="— الان هیچ دیلری فعال نیست —", callback_data="bm:dealers")])
    rows.append([InlineKeyboardButton(text="🔙 برگشت به بازار", callback_data="bm:back", style=ButtonStyle.DANGER)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_bm_dealers(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    if not bmrep.has_unlock(player, "dealers"):
        await cb.answer("🔒 رتبه‌ی «آشنا» یا بالاتر لازمه (بزن رو 🏷️ رتبه‌ی دیلر ببین چقدر مونده).", show_alert=True)
        return
    text = ("🕴️ **دیلرهای گردشی**\n\n"
            "هر ساعت رو چند تا نقشه یه دیلر اسپان می‌شه، موجودیِ محدود داره. "
            "خرید ازشون ریسکِ گیرافتادن داره — هرچی نقشه خطرناک‌تر، ریسک بیشتر.\n\n"
            "یه دیلر رو انتخاب کن:")
    try:
        await cb.message.edit_text(text, reply_markup=_dealers_list_kb(uid))
    except Exception:
        await cb.message.answer(text, reply_markup=_dealers_list_kb(uid))
    await cb.answer()


def _dealer_view_kb(map_name: str, doc: dict, uid: int) -> InlineKeyboardMarkup:
    rows = []
    for row in doc["stock"]:
        if row["qty_left"] <= 0:
            continue
        it = row["item"]
        rows.append([InlineKeyboardButton(
            text=f"{it['emoji']} {it['name']} ({row['qty_left']}x) — {row['price']:,} Zen",
            callback_data=f"deal_buy:{map_name}:{row['row_id']}"
        )])
    if not rows:
        rows.append([InlineKeyboardButton(text="— موجودی تموم شده —", callback_data=f"deal_view:{map_name}")])
    rows.append([InlineKeyboardButton(text="🔙 لیستِ دیلرها", callback_data="bm:dealers", style=ButtonStyle.DANGER)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_deal_view(cb: CallbackQuery):
    uid = cb.from_user.id
    map_name = cb.data.split(":", 1)[1]
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    doc = deal.get_dealer(map_name, player=player, uid=uid)
    if not doc:
        await cb.answer("❌ این دیلر دیگه اونجا نیست.", show_alert=True)
        return
    risk = deal.catch_risk(player, map_name)
    text = (f"{doc['emoji']} **{doc['name']}** — {map_name}\n_{doc['flavor']}_\n\n"
            f"🚨 ریسکِ گیرافتادن اینجا: **{int(risk*100)}٪**\n\n"
            f"💰 موجودی: **{player.get('zen',0):,} Zen**\n\n📦 کالاها:")
    try:
        await cb.message.edit_text(text, reply_markup=_dealer_view_kb(map_name, doc, uid))
    except Exception:
        await cb.message.answer(text, reply_markup=_dealer_view_kb(map_name, doc, uid))
    await cb.answer()


async def cb_deal_buy(cb: CallbackQuery):
    uid = cb.from_user.id
    _, map_name, row_id = cb.data.split(":")
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return

    ok, msg, info = deal.buy_from_dealer(player, map_name, row_id, uid=uid)
    if not ok:
        await cb.answer(msg, show_alert=True)
        return
    save_player(uid, player)

    log_sync(
        f"🕴️ **DEALER BUY** | {player.get('name','—')} (`{uid}`)\n"
        f"📍 {map_name} | caught={info['caught']}\n{msg}",
        "ECONOMY"
    )
    await cb.answer("🚨 گیر افتادی!" if info["caught"] else "✅ خریدی!", show_alert=True)
    doc = deal.get_dealer(map_name, player=player, uid=uid)
    if doc:
        text = f"{doc['emoji']} **{doc['name']}** — {map_name}\n\n{msg}"
        try:
            await cb.message.edit_text(text, reply_markup=_dealer_view_kb(map_name, doc, uid))
        except Exception:
            await cb.message.answer(msg)
    else:
        try:
            await cb.message.edit_text(msg, reply_markup=_back_bm_kb(uid))
        except Exception:
            await cb.message.answer(msg)


# ─── 📦 تابلوی قاچاق ─────────────────────────────────────────────
class SmuggleState(StatesGroup):
    waiting_post = State()


def _smuggle_home_kb(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 سفارش‌های باز (بقیه)", callback_data="smug_list:0")],
        [InlineKeyboardButton(text="🧾 سفارش‌های من", callback_data="smug_mine")],
        [InlineKeyboardButton(text="➕ ثبتِ سفارشِ جدید", callback_data="smug_new", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="🔙 برگشت به بازار", callback_data="bm:back", style=ButtonStyle.DANGER)],
    ])


async def cb_bm_smuggle(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    if not bmrep.has_unlock(player, "smuggling"):
        await cb.answer("🔒 رتبه‌ی «معتمد» یا بالاتر لازمه تا سفارش بذاری (دیدنِ سفارش‌های دیگران هم همینطور).", show_alert=True)
        return
    text = ("📦 **تابلوی قاچاق**\n\n"
            "سفارش بذار: فلان آیتم رو با فلان تعداد بیار فلان نقشه، در ازاش Zen بگیر. "
            "بقیه‌ی بازیکن‌ها می‌تونن تحویل بدن و پول رو نقد بگیرن.")
    try:
        await cb.message.edit_text(text, reply_markup=_smuggle_home_kb(uid))
    except Exception:
        await cb.message.answer(text, reply_markup=_smuggle_home_kb(uid))
    await cb.answer()


def _contract_line(c: dict) -> str:
    return f"📦 {c['qty']}x **{c['item_name']}** → {c['dest_map']} | 💰 {c['bounty']:,} Zen"


async def cb_smug_list(cb: CallbackQuery):
    uid = cb.from_user.id
    contracts = smug.open_contracts(exclude_uid=uid)
    if not contracts:
        text = "📋 الان هیچ سفارشِ بازی از بقیه نیست."
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 برگشت", callback_data="bm:smuggle", style=ButtonStyle.DANGER)
        ]])
    else:
        lines = ["📋 **سفارش‌های باز:**\n"]
        rows = []
        for c in contracts[:10]:
            lines.append(_contract_line(c) + f" — از {c['poster_name']}\n")
            rows.append([InlineKeyboardButton(text=f"🚚 تحویلِ {c['item_name'][:20]}", callback_data=f"smug_fulfill:{c['_id']}")])
        rows.append([InlineKeyboardButton(text="🔙 برگشت", callback_data="bm:smuggle", style=ButtonStyle.DANGER)])
        text = "\n".join(lines)
        kb = InlineKeyboardMarkup(inline_keyboard=rows)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


async def cb_smug_mine(cb: CallbackQuery):
    uid = cb.from_user.id
    contracts = smug.my_contracts(uid)
    rows = []
    if not contracts:
        text = "🧾 هیچ سفارشی ثبت نکردی."
    else:
        lines = ["🧾 **سفارش‌های من:**\n"]
        for c in contracts:
            status_e = {"open": "🟢", "fulfilled": "✅", "expired": "⌛", "cancelled": "↩️"}.get(c["status"], "•")
            lines.append(f"{status_e} {_contract_line(c)} [{c['status']}]\n")
            if c["status"] == "open":
                rows.append([InlineKeyboardButton(text=f"❌ لغوِ {c['item_name'][:18]}", callback_data=f"smug_cancel:{c['_id']}")])
        text = "\n".join(lines)
    rows.append([InlineKeyboardButton(text="🔙 برگشت", callback_data="bm:smuggle", style=ButtonStyle.DANGER)])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


async def cb_smug_fulfill(cb: CallbackQuery):
    uid = cb.from_user.id
    contract_id = cb.data.split(":", 1)[1]
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    ok, msg = smug.fulfill_contract(player, contract_id)
    if not ok:
        await cb.answer(msg, show_alert=True)
        return
    save_player(uid, player)
    log_sync(f"📦 **SMUGGLE FULFILL** | {player.get('name','—')} (`{uid}`)\n{msg}", "ECONOMY")
    await cb.answer("✅ تحویل داده شد!", show_alert=True)
    await cb_smug_list(cb)


async def cb_smug_cancel(cb: CallbackQuery):
    uid = cb.from_user.id
    contract_id = cb.data.split(":", 1)[1]
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    ok, msg = smug.cancel_contract(player, contract_id)
    if not ok:
        await cb.answer(msg, show_alert=True)
        return
    save_player(uid, player)
    await cb.answer(msg, show_alert=True)
    await cb_smug_mine(cb)


async def cb_smug_new(cb: CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    if not bmrep.has_unlock(player, "smuggling"):
        await cb.answer("🔒 رتبه‌ی «معتمد» یا بالاتر لازمه.", show_alert=True)
        return
    await state.set_state(SmuggleState.waiting_post)
    text = (
        "➕ **ثبتِ سفارشِ قاچاق**\n\n"
        "یه پیام به این فرمت بفرست (با `;` جدا کن):\n"
        "`نامِ آیتم;تعداد;نامِ دقیقِ نقشه;پاداش`\n\n"
        "مثال:\n`Sand Crystal;3;Voidbreak;4000`\n\n"
        "برای لغو، /cancel بفرست."
    )
    try:
        await cb.message.edit_text(text)
    except Exception:
        await cb.message.answer(text)
    await cb.answer()


async def handle_smug_post_text(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    if (msg.text or "").strip() == "/cancel":
        await state.clear()
        await msg.reply("❌ لغو شد.")
        return
    parts = [p.strip() for p in (msg.text or "").split(";")]
    if len(parts) != 4:
        await msg.reply("❌ فرمت درست نیست. باید ۴ تا بخش با `;` جدا شده باشه:\n`نامِ آیتم;تعداد;نقشه;پاداش`")
        return
    item_name, qty_s, dest_map, bounty_s = parts
    try:
        qty = int(qty_s)
        bounty = int(bounty_s)
    except ValueError:
        await msg.reply("❌ تعداد و پاداش باید عددی باشن.")
        return

    from economy import MAPS_DATA
    if dest_map not in MAPS_DATA:
        names = "، ".join(list(MAPS_DATA.keys())[:6]) + "، ..."
        await msg.reply(f"❌ نقشه‌ی «{dest_map}» پیدا نشد. مثلاً: {names}")
        return

    player = get_player(uid)
    if not player:
        await state.clear()
        return
    ok, result_msg = smug.post_contract(player, item_name, qty, dest_map, bounty)
    if ok:
        save_player(uid, player)
        log_sync(f"📦 **SMUGGLE POST** | {player.get('name','—')} (`{uid}`)\n{result_msg}", "ECONOMY")
        await state.clear()
    await msg.reply(result_msg)


# ─── Register ────────────────────────────────────────────────
def register_black_market_expansion_handlers(dp, bot):
    dp.callback_query.register(cb_bm_rank,    F.data == "bm:rank")
    dp.callback_query.register(cb_bm_dealers, F.data == "bm:dealers")
    dp.callback_query.register(cb_deal_view,  F.data.startswith("deal_view:"))
    dp.callback_query.register(cb_deal_buy,   F.data.startswith("deal_buy:"))

    dp.callback_query.register(cb_bm_smuggle, F.data == "bm:smuggle")
    dp.callback_query.register(cb_smug_list,  F.data.startswith("smug_list:"))
    dp.callback_query.register(cb_smug_mine,  F.data == "smug_mine")
    dp.callback_query.register(cb_smug_fulfill, F.data.startswith("smug_fulfill:"))
    dp.callback_query.register(cb_smug_cancel,  F.data.startswith("smug_cancel:"))
    dp.callback_query.register(cb_smug_new,   F.data == "smug_new")
    dp.message.register(handle_smug_post_text, SmuggleState.waiting_post)
