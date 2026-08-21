# ============================================================
#  ASTRAL ABYSS RPG — Auction House Handlers (Telegram UI) — v2
# ============================================================
import time
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from logger import log_sync
import auction_system as ah

_awaiting_price: dict[int, tuple[dict, float]] = {}   # uid -> (item, expires_at)  — درجِ آگهی
_awaiting_bid:   dict[int, tuple[str, float]] = {}     # uid -> (listing_id, expires_at) — ثبتِ پیشنهاد


def _owner_ok(cb: CallbackQuery, uid: int) -> bool:
    return cb.from_user.id == uid


# ─── 🏠 منوی اصلی ───────────────────────────────────────────────
def _home_kb(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 مرور آگهی‌ها", callback_data=f"ah_browse:0:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="📦 آگهی‌های من", callback_data=f"ah_mine:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="💰 پیشنهادهای من", callback_data=f"ah_mybids:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="➕ فروش آیتم جدید", callback_data=f"ah_sell:{uid}", style=ButtonStyle.DANGER)],
    ])


_HOME_TEXT = (
    "🏛️ **حراجی زنده‌ی آبیس**\n\n"
    "روی آیتمِ بازیکن‌های دیگه پیشنهاد بده یا آیتمِ خودت رو با یه قیمتِ شروع بذار حراج.\n"
    "⏱ اگه تو ۳۰ ثانیه‌ی آخر پیشنهادِ جدید بیاد، زمان خودکار تمدید می‌شه (ضدِ اسنایپ).\n"
    "🤖 می‌تونی موقعِ پیشنهاد یه سقفِ مخفی (auto-bid) هم بذاری تا خودکار برات رقابت کنه."
)


async def cmd_auction(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    from level_gate import check_level
    ok, why = check_level(player, "auction")
    if not ok:
        await msg.answer(why)
        return
    returned = ah.claim_expired(player)
    if returned:
        await asave_player(uid, player)
    text = _HOME_TEXT
    if returned:
        text += f"\n\n↩️ چون پیشنهادی نگرفته بودن، این آیتم‌ها به کوله‌پشتیت برگشت: {', '.join(returned)}"
    await msg.answer(text, reply_markup=_home_kb(uid))


async def cb_ah_home(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    await cb.answer()
    await cb.message.edit_text(_HOME_TEXT, reply_markup=_home_kb(uid))


# ─── 🛒 مرور آگهی‌ها ────────────────────────────────────────────
PAGE_SIZE = 5

async def cb_ah_browse(cb: CallbackQuery):
    _, page_s, uid_s = cb.data.split(":")
    page, uid = int(page_s), int(uid_s)
    listings = ah.get_active_listings(exclude_uid=uid, limit=200)
    if not listings:
        await cb.answer()
        await cb.message.edit_text(
            "🛒 فعلاً هیچ آگهی‌ای تو حراجی نیست.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"ah_home:{uid}", style=ButtonStyle.PRIMARY)]])
        )
        return

    chunk = listings[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    lines = [f"🛒 **آگهی‌های فعال** (صفحه {page+1})\n"]
    buttons = []
    for doc in chunk:
        it = doc["item"]
        remain_m = max(0, int((doc["expires_at"] - time.time()) // 60))
        cur = doc.get("current_bid")
        price_line = f"💰 پیشنهادِ فعلی: {cur:,} Zen ({doc.get('current_bidder_name','—')})" if cur else f"💰 قیمتِ شروع: {doc['starting_price']:,} Zen (هنوز پیشنهادی نداره)"
        lines.append(
            f"\n{it.get('emoji','📦')} **{it['name']}** ({it.get('rarity','common')})\n"
            f"   {price_line} | فروشنده: {doc['seller_name']} | ⏳ {remain_m} دقیقه مونده"
        )
        buttons.append([InlineKeyboardButton(
            text=f"💰 پیشنهاد رو {it['name']}", callback_data=f"ah_view:{doc['_id']}:{uid}"
        , style=ButtonStyle.SUCCESS)])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ قبلی", callback_data=f"ah_browse:{page-1}:{uid}", style=ButtonStyle.PRIMARY))
    if (page + 1) * PAGE_SIZE < len(listings):
        nav.append(InlineKeyboardButton(text="➡️ بعدی", callback_data=f"ah_browse:{page+1}:{uid}", style=ButtonStyle.PRIMARY))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"ah_home:{uid}", style=ButtonStyle.PRIMARY)])

    await cb.answer()
    await cb.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


def _listing_detail_text(doc: dict) -> str:
    it = doc["item"]
    remain_m = max(0, int((doc["expires_at"] - time.time()) // 60))
    cur = doc.get("current_bid")
    min_next = ah.min_next_bid(doc)
    price_line = (
        f"💰 بالاترین پیشنهاد: {cur:,} Zen — از طرفِ {doc.get('current_bidder_name','—')}"
        if cur else f"💰 قیمتِ شروع: {doc['starting_price']:,} Zen (هنوز پیشنهادی نداره)"
    )
    return (
        f"{it.get('emoji','📦')} **{it['name']}** ({it.get('rarity','common')})\n\n"
        f"{price_line}\n"
        f"📈 حداقلِ پیشنهادِ بعدی: {min_next:,} Zen\n"
        f"👤 فروشنده: {doc['seller_name']}\n"
        f"⏳ {remain_m} دقیقه تا پایان\n"
        f"🔢 تعدادِ پیشنهادها: {doc.get('bid_count', 0)}\n\n"
        "برای پیشنهاد دادن دکمه‌ی زیر رو بزن — بعدش می‌تونی یه عدد (مبلغِ پیشنهاد) یا "
        "دو عدد با فاصله (مبلغِ پیشنهاد، سقفِ مخفیِ auto-bid) بفرستی."
    )


async def cb_ah_view(cb: CallbackQuery):
    _, listing_id, uid_s = cb.data.split(":")
    uid = int(uid_s)
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    doc = ah.get_listing(listing_id)
    if not doc or doc.get("status") != "active":
        await cb.answer("❌ این آگهی دیگه فعال نیست.", show_alert=True)
        return
    await cb.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 پیشنهاد بده", callback_data=f"ah_bid_start:{listing_id}:{uid}", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"ah_browse:0:{uid}", style=ButtonStyle.PRIMARY)],
    ])
    await cb.message.edit_text(_listing_detail_text(doc), reply_markup=kb)


async def cb_ah_bid_start(cb: CallbackQuery):
    _, listing_id, uid_s = cb.data.split(":")
    uid = int(uid_s)
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    doc = ah.get_listing(listing_id)
    if not doc or doc.get("status") != "active":
        await cb.answer("❌ این آگهی دیگه فعال نیست.", show_alert=True)
        return
    min_next = ah.min_next_bid(doc)
    _awaiting_bid[uid] = (listing_id, time.time() + 120)
    await cb.answer()
    await cb.message.edit_text(
        f"💰 حداقلِ پیشنهادِ لازم: **{min_next:,} Zen**\n\n"
        f"یه عدد (فقط مبلغِ پیشنهاد) یا دو عدد با فاصله (مبلغِ پیشنهاد + سقفِ مخفیِ auto-bid) بفرست.\n"
        f"مثال: `{min_next}` یا `{min_next} {min_next*3}`"
    )


async def handle_auction_bid_text(msg: Message):
    uid = msg.from_user.id
    entry = _awaiting_bid.get(uid)
    if not entry:
        return
    listing_id, expires = entry
    if time.time() > expires:
        del _awaiting_bid[uid]
        await msg.answer("⏰ زمان تموم شد، دوباره از منوی حراجی امتحان کن.")
        return
    parts = (msg.text or "").strip().split()
    if not parts or not all(p.isdigit() for p in parts[:2]) or len(parts) > 2:
        await msg.answer("❌ یا یه عدد بفرست (مبلغِ پیشنهاد) یا دو عدد با فاصله (پیشنهاد + سقفِ مخفی).")
        return
    bid_amount = int(parts[0])
    auto_cap = int(parts[1]) if len(parts) == 2 else None
    if bid_amount <= 0:
        await msg.answer("❌ یه عددِ درست بفرست!")
        return
    del _awaiting_bid[uid]

    bidder = await aget_player(uid)
    ok, result_msg = await ah.place_bid(bidder, listing_id, bid_amount, auto_cap)
    await asave_player(uid, bidder)  # چه برنده بشه چه نه، zen ممکنه تغییر کرده باشه (escrow)
    if ok:
        log_sync(
            f"🏛️ **AUCTION BID**\n👤 {bidder.get('name','—')} (`{uid}`)\n"
            f"💰 پیشنهاد: {bid_amount:,} Zen" + (f" (سقفِ مخفی: {auto_cap:,})" if auto_cap else ""),
            "AUCTION"
        )
    await msg.answer(result_msg, reply_markup=_home_kb(uid))


# ─── 📦 آگهی‌های من ─────────────────────────────────────────────
async def cb_ah_mine(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    mine = ah.get_my_listings(uid)
    await cb.answer()
    if not mine:
        await cb.message.edit_text(
            "📦 هیچ آگهی فعالی نداری.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"ah_home:{uid}", style=ButtonStyle.PRIMARY)]])
        )
        return
    lines = ["📦 **آگهی‌های من**\n"]
    buttons = []
    for doc in mine:
        it = doc["item"]
        remain_m = max(0, int((doc["expires_at"] - time.time()) // 60))
        cur = doc.get("current_bid")
        price_line = f"💰 بالاترین پیشنهاد: {cur:,} Zen ({doc.get('current_bidder_name','—')})" if cur else f"💰 قیمتِ شروع: {doc['starting_price']:,} Zen (بدون پیشنهاد)"
        lines.append(f"\n{it.get('emoji','📦')} **{it['name']}** — {price_line} | ⏳ {remain_m}m")
        if not cur:
            buttons.append([InlineKeyboardButton(text=f"❌ لغو {it['name']}", callback_data=f"ah_cancel:{doc['_id']}:{uid}", style=ButtonStyle.DANGER)])
    buttons.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"ah_home:{uid}", style=ButtonStyle.PRIMARY)])
    await cb.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


async def cb_ah_cancel(cb: CallbackQuery):
    _, listing_id, uid_s = cb.data.split(":")
    uid = int(uid_s)
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    ok, msg = ah.cancel_listing(player, listing_id)
    if ok:
        await asave_player(uid, player)
    await cb.answer(msg, show_alert=True)
    cb.data = f"ah_mine:{uid}"
    await cb_ah_mine(cb)


# ─── 💰 پیشنهادهای من ───────────────────────────────────────────
async def cb_ah_mybids(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    mine = ah.get_my_bids(uid)
    await cb.answer()
    if not mine:
        await cb.message.edit_text(
            "💰 فعلاً رو هیچ آگهی‌ای بالاترین پیشنهاد رو نداری.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"ah_home:{uid}", style=ButtonStyle.PRIMARY)]])
        )
        return
    lines = ["💰 **پیشنهادهای فعالِ من** (جایی که الان بالاترینی)\n"]
    for doc in mine:
        it = doc["item"]
        remain_m = max(0, int((doc["expires_at"] - time.time()) // 60))
        cap_note = " 🤖" if doc.get("leader_auto_cap") else ""
        lines.append(f"\n{it.get('emoji','📦')} **{it['name']}** — {doc['current_bid']:,} Zen{cap_note} | ⏳ {remain_m}m")
    await cb.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"ah_home:{uid}", style=ButtonStyle.PRIMARY)]
    ]))


# ─── ➕ فروش آیتم جدید ──────────────────────────────────────────
async def cb_ah_sell(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    inv = player.get("inventory", [])
    if not inv:
        await cb.answer("🎒 کوله‌پشتیت خالیه!", show_alert=True)
        return
    buttons = []
    for it in inv[:20]:
        buttons.append([InlineKeyboardButton(
            text=f"{it.get('emoji','📦')} {it['name']}", callback_data=f"ah_sell_pick:{it['id']}:{uid}"
        , style=ButtonStyle.PRIMARY)])
    buttons.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"ah_home:{uid}", style=ButtonStyle.PRIMARY)])
    await cb.answer()
    await cb.message.edit_text("➕ کدوم آیتم رو می‌خوای بذاری حراج؟", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


async def cb_ah_sell_pick(cb: CallbackQuery):
    _, item_id, uid_s = cb.data.split(":")
    uid = int(uid_s)
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    item = next((it for it in player.get("inventory", []) if it.get("id") == item_id), None)
    if not item:
        await cb.answer("❌ این آیتم پیدا نشد.", show_alert=True)
        return
    _awaiting_price[uid] = (item, time.time() + 120)
    await cb.answer()
    await cb.message.edit_text(
        f"💰 قیمتِ **شروعِ** مزایده‌ی **{item['name']}** رو به Zen بفرست (فقط عدد، حداقل {ah.MIN_PRICE:,}).\n"
        f"⚠️ {int(ah.LISTING_FEE_PCT*100)}٪ هزینه‌ی درج آگهی از موجودیت کسر می‌شه (غیرقابل‌استرداد)."
    )


async def handle_auction_text(msg: Message):
    uid = msg.from_user.id
    entry = _awaiting_price.get(uid)
    if not entry:
        return
    item, expires = entry
    if time.time() > expires:
        del _awaiting_price[uid]
        await msg.answer("⏰ زمان تموم شد، دوباره از منوی حراجی امتحان کن.")
        return
    text = (msg.text or "").strip()
    if not text.isdigit() or int(text) <= 0:
        await msg.answer("❌ یه عددِ درست بفرست!")
        return
    price = int(text)
    del _awaiting_price[uid]

    player = await aget_player(uid)
    ok, result_msg = ah.create_listing(player, item, price)
    if ok:
        await asave_player(uid, player)
        log_sync(
            f"🏛️ **AUCTION LIST**\n👤 {player.get('name','—')} (`{uid}`)\n"
            f"📦 {item['name']} — شروع از {price:,} Zen", "AUCTION"
        )
    await msg.answer(result_msg, reply_markup=_home_kb(uid))


def _handle_any_text(m: Message) -> bool:
    return m.from_user.id in _awaiting_price or m.from_user.id in _awaiting_bid


async def handle_auction_any_text(msg: Message):
    uid = msg.from_user.id
    if uid in _awaiting_bid:
        await handle_auction_bid_text(msg)
    elif uid in _awaiting_price:
        await handle_auction_text(msg)


# ─── registration ────────────────────────────────────────────
def register_auction_handlers(dp, bot):
    dp.message.register(cmd_auction, Command("auction"))
    dp.callback_query.register(cb_ah_home,       F.data.startswith("ah_home:"))
    dp.callback_query.register(cb_ah_browse,     F.data.startswith("ah_browse:"))
    dp.callback_query.register(cb_ah_view,       F.data.startswith("ah_view:"))
    dp.callback_query.register(cb_ah_bid_start,  F.data.startswith("ah_bid_start:"))
    dp.callback_query.register(cb_ah_mine,       F.data.startswith("ah_mine:"))
    dp.callback_query.register(cb_ah_mybids,     F.data.startswith("ah_mybids:"))
    dp.callback_query.register(cb_ah_cancel,     F.data.startswith("ah_cancel:"))
    dp.callback_query.register(cb_ah_sell_pick,  F.data.startswith("ah_sell_pick:"))
    dp.callback_query.register(cb_ah_sell,       F.data.startswith("ah_sell:"))
    dp.message.register(handle_auction_any_text, _handle_any_text)
