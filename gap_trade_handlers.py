# ============================================================
#  ASTRAL ABYSS — Direct Player Trading
# ------------------------------------------------------------
#  /trade @user یا دکمه‌ی «🤝 معامله» یه پیشنهادِ معامله می‌سازه:
#  پیشنهاددهنده یه چیز می‌ده (آیتم یا Zen) و یه چیز می‌خواد (Zen، یه
#  آیتمِ خاص، یا هیچی = هدیه). طرفِ مقابل با دکمه تأیید/رد می‌کنه.
#  فقط موقعِ تأییدِ نهایی چک می‌شه که هر دو طرف واقعاً چیزی که وعده
#  دادن رو دارن — تا کسی نتونه با تأخیر یا هم‌زمانی تقلب کنه.
# ============================================================
import time
import random
import string

from gap_dispatcher import GapDispatcher
from gap_types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, player_lock_pair, asave_player, aget_player
from logger import log_sync

# draft هایی که هنوز کامل نشدن (کلید = uid پیشنهاددهنده)
_drafts: dict[int, dict] = {}
# پیشنهادهای ارسال‌شده و منتظرِ تأیید (کلید = یه شناسه‌ی کوتاه)
_pending: dict[str, dict] = {}
# منتظرِ ورودیِ متنی (برای مقدار Zen یا اسمِ آیتم)
_awaiting_text: dict[int, tuple[str, int]] = {}  # uid -> (mode, ttl)

TRADE_TTL = 600  # ۱۰ دقیقه فرصت برای تکمیل/تأیید
STATE_TRADE = "trade:awaiting_text"


_DP = None  # پرشده تو register_gap_trade_handlers، برای دسترسی به dp.state


def _gen_id() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


def _resolve_target(arg: str, uid: int) -> int | None:
    from gap_pvp_handlers import _resolve_track_target
    return _resolve_track_target(arg, uid)


def _inventory_kb(player: dict, prefix: str) -> InlineKeyboardMarkup:
    from item_system import group_inventory
    groups = group_inventory(player.get("inventory", []))[:10]
    rows = []
    for i, g in enumerate(groups):
        item = g["item"]
        tag = f" ×{g['qty']}" if g["qty"] > 1 else ""
        label = f"{item.get('emoji','📦')} {item.get('name','آیتم')}{tag}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"{prefix}:item:{i}")])
    rows.append([InlineKeyboardButton(text="💰 Zen", callback_data=f"{prefix}:zen")])
    rows.append([InlineKeyboardButton(text="❌ لغو", callback_data="trade:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _qty_kb(max_qty: int) -> InlineKeyboardMarkup:
    presets = [10, 50, 100, 500]
    rows = []
    row = []
    for p in presets:
        if p < max_qty:
            row.append(InlineKeyboardButton(text=str(p), callback_data=f"trade:giveqty:{p}"))
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=f"✅ همه ({max_qty})", callback_data=f"trade:giveqty:{max_qty}")])
    rows.append([InlineKeyboardButton(text="🔢 عددِ دلخواه", callback_data="trade:giveqty:custom")])
    rows.append([InlineKeyboardButton(text="❌ لغو", callback_data="trade:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cmd_trade(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    from level_gate import check_level
    ok, why = check_level(player, "trade")
    if not ok:
        await msg.answer(why)
        return
    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await msg.answer(
            "🤝 **معامله**\n\n"
            "`/trade @username` یا `/trade user_id` یا `/trade نام_بازیکن`"
        )
        return
    target_id = _resolve_target(parts[1], uid)
    if not target_id or target_id == uid:
        await msg.answer("❌ همچین بازیکنی پیدا نشد (یا خودتی)!")
        return
    target = await aget_player(target_id)
    if not target:
        await msg.answer("❌ این بازیکن پیدا نشد!")
        return

    _drafts[uid] = {"to_uid": target_id, "give": None, "want": None, "created_at": time.time()}
    await msg.answer(
        f"🤝 **معامله با {target['name']}**\n\nاول چی می‌خوای بدی؟",
        reply_markup=_inventory_kb(player, "trade:give")
    )


async def cb_trade_give(cb: CallbackQuery):
    uid = cb.from_user.id
    draft = _drafts.get(uid)
    if not draft:
        await cb.answer("⏰ این معامله منقضی شده!", show_alert=True)
        return
    parts = cb.data.split(":")
    player = await aget_player(uid)

    if parts[2] == "zen":
        _awaiting_text[uid] = ("give_zen", time.time() + TRADE_TTL)
        if _DP:
            _DP.state.set_state(uid, STATE_TRADE)
        await cb.message.edit_text("💰 چقدر Zen می‌خوای بدی؟ (فقط عدد بفرست)")
        await cb.answer()
        return

    from item_system import group_inventory
    gi = int(parts[3])
    groups = group_inventory(player.get("inventory", []))
    if gi >= len(groups):
        await cb.answer("❌ این آیتم دیگه نداری!", show_alert=True)
        return
    g = groups[gi]
    item, avail_qty = g["item"], g["qty"]

    if avail_qty > 1:
        draft["_give_pending_name"] = item["name"]
        draft["_give_pending_max"] = avail_qty
        await cb.message.edit_text(
            f"{item.get('emoji','📦')} **{item['name']}** — {avail_qty} تا داری.\n\nچند تا می‌خوای بدی؟",
            reply_markup=_qty_kb(avail_qty)
        )
        await cb.answer()
        return

    draft["give"] = {"type": "item", "name": item["name"], "qty": 1}
    target = await aget_player(draft["to_uid"])
    await cb.message.edit_text(
        f"🤝 **معامله با {target['name']}**\n\n"
        f"✅ می‌دی: {item.get('emoji','📦')} {item['name']}\n\n"
        f"حالا چی می‌خوای بگیری؟",
        reply_markup=_want_kb()
    )
    await cb.answer()


async def cb_trade_give_qty(cb: CallbackQuery):
    uid = cb.from_user.id
    draft = _drafts.get(uid)
    if not draft or "_give_pending_name" not in draft:
        await cb.answer("⏰ این معامله منقضی شده!", show_alert=True)
        return
    amount_s = cb.data.split(":")[2]

    if amount_s == "custom":
        _awaiting_text[uid] = ("give_qty", time.time() + TRADE_TTL)
        if _DP:
            _DP.state.set_state(uid, STATE_TRADE)
        await cb.message.edit_text(
            f"🔢 چند تا {draft['_give_pending_name']} می‌خوای بدی؟ "
            f"(بینِ ۱ تا {draft['_give_pending_max']} — فقط عدد بفرست)"
        )
        await cb.answer()
        return

    amount = int(amount_s)
    amount = max(1, min(amount, draft["_give_pending_max"]))
    draft["give"] = {"type": "item", "name": draft.pop("_give_pending_name"), "qty": amount}
    draft.pop("_give_pending_max", None)
    target = await aget_player(draft["to_uid"])
    item = draft["give"]
    await cb.message.edit_text(
        f"🤝 **معامله با {target['name']}**\n\n"
        f"✅ می‌دی: {item['name']} ×{item['qty']}\n\n"
        f"حالا چی می‌خوای بگیری؟",
        reply_markup=_want_kb()
    )
    await cb.answer()


def _want_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Zen", callback_data="trade:want:zen")],
        [InlineKeyboardButton(text="📦 یه آیتمِ خاص", callback_data="trade:want:item")],
        [InlineKeyboardButton(text="🎁 هیچی (فقط هدیه)", callback_data="trade:want:gift")],
        [InlineKeyboardButton(text="❌ لغو", callback_data="trade:cancel")],
    ])


async def cb_trade_want(cb: CallbackQuery):
    uid = cb.from_user.id
    draft = _drafts.get(uid)
    if not draft:
        await cb.answer("⏰ این معامله منقضی شده!", show_alert=True)
        return
    mode = cb.data.split(":")[2]
    if mode == "zen":
        _awaiting_text[uid] = ("want_zen", time.time() + TRADE_TTL)
        if _DP:
            _DP.state.set_state(uid, STATE_TRADE)
        await cb.message.edit_text("💰 چقدر Zen می‌خوای بگیری؟ (فقط عدد بفرست)")
    elif mode == "item":
        _awaiting_text[uid] = ("want_item", time.time() + TRADE_TTL)
        if _DP:
            _DP.state.set_state(uid, STATE_TRADE)
        await cb.message.edit_text("📦 اسمِ آیتمی که می‌خوای رو بنویس (باید تو اینونتوریِ طرف مقابل باشه)")
    else:
        draft["want"] = {"type": "gift"}
        await _show_summary(cb.message, uid)
    await cb.answer()


async def handle_trade_text(msg: Message):
    uid = msg.from_user.id
    if _DP:
        _DP.state.set_state(uid, None)
    entry = _awaiting_text.get(uid)
    if not entry:
        return
    mode, expires = entry
    if time.time() > expires:
        del _awaiting_text[uid]
        await msg.answer("⏰ زمانِ معامله تموم شد، دوباره /trade بزن.")
        return
    draft = _drafts.get(uid)
    if not draft:
        del _awaiting_text[uid]
        return

    text = (msg.text or "").strip()
    if mode in ("give_zen", "want_zen"):
        if not text.isdigit() or int(text) <= 0:
            await msg.answer("❌ یه عددِ درست بفرست!")
            return
        amount = int(text)
        key = "give" if mode == "give_zen" else "want"
        draft[key] = {"type": "zen", "amount": amount}
    elif mode == "give_qty":
        max_qty = draft.get("_give_pending_max", 1)
        if not text.isdigit() or int(text) <= 0:
            await msg.answer(f"❌ یه عددِ درست بینِ ۱ تا {max_qty} بفرست!")
            _awaiting_text[uid] = (mode, expires)
            if _DP:
                _DP.state.set_state(uid, STATE_TRADE)
            return
        amount = max(1, min(int(text), max_qty))
        draft["give"] = {"type": "item", "name": draft.pop("_give_pending_name"), "qty": amount}
        draft.pop("_give_pending_max", None)
    else:  # want_item
        draft["want"] = {"type": "item", "name": text}

    del _awaiting_text[uid]

    if draft.get("give") and mode == "give_zen":
        target = await aget_player(draft["to_uid"])
        await msg.answer(
            f"🤝 **معامله با {target['name']}**\n\n"
            f"✅ می‌دی: 💰 {amount:,} Zen\n\nحالا چی می‌خوای بگیری؟",
            reply_markup=_want_kb()
        )
    elif draft.get("give") and mode == "give_qty":
        target = await aget_player(draft["to_uid"])
        item = draft["give"]
        await msg.answer(
            f"🤝 **معامله با {target['name']}**\n\n"
            f"✅ می‌دی: {item['name']} ×{item['qty']}\n\nحالا چی می‌خوای بگیری؟",
            reply_markup=_want_kb()
        )
    else:
        await _show_summary(msg, uid)


def _describe(side: dict | None) -> str:
    if not side:
        return "—"
    if side["type"] == "zen":
        return f"💰 {side['amount']:,} Zen"
    if side["type"] == "item":
        qty = side.get("qty", 1)
        tag = f" ×{qty}" if qty > 1 else ""
        return f"📦 {side['name']}{tag}"
    return "🎁 هیچی"


async def _show_summary(target_msg, uid: int):
    draft = _drafts.get(uid)
    if not draft:
        return
    target = await aget_player(draft["to_uid"])
    text = (
        f"🤝 **خلاصه‌ی معامله با {target['name']}**\n\n"
        f"می‌دی: {_describe(draft['give'])}\n"
        f"می‌خوای: {_describe(draft['want'])}\n\n"
        f"مطمئنی؟"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 ارسالِ پیشنهاد", callback_data="trade:send")],
        [InlineKeyboardButton(text="❌ لغو", callback_data="trade:cancel")],
    ])
    await target_msg.answer(text, reply_markup=kb)


async def cb_trade_send(cb: CallbackQuery):
    uid = cb.from_user.id
    draft = _drafts.pop(uid, None)
    if not draft:
        await cb.answer("⏰ این معامله منقضی شده!", show_alert=True)
        return
    proposer = await aget_player(uid)
    target_id = draft["to_uid"]
    target = await aget_player(target_id)
    if not target:
        await cb.answer("❌ طرفِ مقابل دیگه پیدا نشد!", show_alert=True)
        return

    proposal_id = _gen_id()
    _pending[proposal_id] = {**draft, "from_uid": uid, "created_at": time.time()}

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ قبول", callback_data=f"trade:accept:{proposal_id}"),
        InlineKeyboardButton(text="❌ رد", callback_data=f"trade:decline:{proposal_id}"),
    ]])
    text = (
        f"🤝 **پیشنهادِ معامله از {proposer['name']}**\n\n"
        f"بهت می‌ده: {_describe(draft['give'])}\n"
        f"می‌خواد بگیره: {_describe(draft['want'])}"
    )
    try:
        # نکته‌ی گپ: target_id یه uid داخلیه (منفی) → chat_id واقعی abs()
        await cb.bot.send_message(abs(target_id), text, reply_markup=kb)
        await cb.message.edit_text("📤 پیشنهاد فرستاده شد! منتظرِ جوابش باش.")
    except Exception:
        await cb.message.edit_text("❌ نتونستم پیام بفرستم (شاید طرف هنوز /start نزده).")
    await cb.answer()


def _take_from_inventory(player: dict, item_name: str) -> dict | None:
    inv = player.get("inventory", [])
    for i, it in enumerate(inv):
        if it.get("name") == item_name:
            return inv.pop(i)
    return None


async def cb_trade_accept(cb: CallbackQuery):
    proposal_id = cb.data.split(":")[2]
    deal = _pending.pop(proposal_id, None)
    if not deal:
        await cb.answer("⏰ این پیشنهاد دیگه معتبر نیست!", show_alert=True)
        return

    from_uid, to_uid = deal["from_uid"], deal["to_uid"]
    give, want = deal["give"], deal["want"]

    from item_system import group_qty_available, take_qty_by_name, merge_into_inventory

    async with player_lock_pair(from_uid, to_uid):
        # نکته: عمداً giver/taker رو *داخل* قفل دوباره می‌خونیم (نه قبلش)،
        # چون بینِ لحظه‌ی propose و لحظه‌ی accept ممکنه یکی از طرفین یه
        # اکشنِ دیگه زده باشه؛ باید تازه‌ترین نسخه رو زیرِ قفل ببینیم.
        giver = await aget_player(from_uid)
        taker = await aget_player(to_uid)
        if not giver or not taker:
            await cb.answer("❌ خطا!", show_alert=True)
            return

        # ─── چک نهایی: هر دو طرف واقعاً چیزی که وعده دادن رو دارن ───
        if give["type"] == "zen" and giver.get("zen", 0) < give["amount"]:
            await cb.answer("❌ طرفِ مقابل دیگه اون مقدار Zen رو نداره!", show_alert=True)
            return
        if give["type"] == "item":
            need = give.get("qty", 1)
            if group_qty_available(giver.get("inventory", []), give["name"]) < need:
                await cb.answer("❌ طرفِ مقابل دیگه اون تعداد رو نداره!", show_alert=True)
                return
        if want["type"] == "zen" and taker.get("zen", 0) < want["amount"]:
            await cb.answer("❌ تو دیگه اون مقدار Zen رو نداری!", show_alert=True)
            return
        if want["type"] == "item" and want["name"] not in [i.get("name") for i in taker.get("inventory", [])]:
            await cb.answer("❌ تو همچین آیتمی نداری!", show_alert=True)
            return

        # ─── اجرا ───
        if give["type"] == "zen":
            giver["zen"] -= give["amount"]
            taker["zen"] = taker.get("zen", 0) + give["amount"]
        elif give["type"] == "item":
            item = take_qty_by_name(giver, give["name"], give.get("qty", 1))
            if item:
                merge_into_inventory(taker.setdefault("inventory", []), item)

        if want["type"] == "zen":
            taker["zen"] -= want["amount"]
            giver["zen"] = giver.get("zen", 0) + want["amount"]
        elif want["type"] == "item":
            item = _take_from_inventory(taker, want["name"])
            if item:
                merge_into_inventory(giver.setdefault("inventory", []), item)

        await asave_player(from_uid, giver)
        await asave_player(to_uid, taker)

    log_sync(f"🤝 **TRADE COMPLETED**\n{giver['name']} ↔ {taker['name']}", "TRADE")

    await cb.message.edit_text("✅ معامله انجام شد!")
    try:
        await cb.bot.send_message(abs(from_uid), f"✅ {taker['name']} معامله رو قبول کرد!")
    except Exception:
        pass
    await cb.answer()


async def cb_trade_decline(cb: CallbackQuery):
    proposal_id = cb.data.split(":")[2]
    deal = _pending.pop(proposal_id, None)
    await cb.message.edit_text("❌ پیشنهاد رد شد.")
    if deal:
        try:
            await cb.bot.send_message(abs(deal["from_uid"]), "❌ طرفِ مقابل پیشنهادِ معامله رو رد کرد.")
        except Exception:
            pass
    await cb.answer()


async def cb_trade_cancel(cb: CallbackQuery):
    _drafts.pop(cb.from_user.id, None)
    _awaiting_text.pop(cb.from_user.id, None)
    await cb.message.edit_text("❌ معامله لغو شد.")
    await cb.answer()


def register_gap_trade_handlers(dp: GapDispatcher):
    global _DP
    _DP = dp
    dp.register_message(cmd_trade, commands=["trade"], text="🤝 معامله")
    dp.register_callback(cb_trade_give, data_startswith="trade:give:")
    dp.register_callback(cb_trade_give_qty, data_startswith="trade:giveqty:")
    dp.register_callback(cb_trade_want, data_startswith="trade:want")
    dp.register_callback(cb_trade_send, data="trade:send")
    dp.register_callback(cb_trade_accept, data_startswith="trade:accept:")
    dp.register_callback(cb_trade_decline, data_startswith="trade:decline:")
    dp.register_callback(cb_trade_cancel, data="trade:cancel")
    dp.register_state(STATE_TRADE, handle_trade_text)
