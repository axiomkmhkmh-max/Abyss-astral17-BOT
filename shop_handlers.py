# ============================================================
#  ASTRAL ABYSS RPG — Shop Handlers (Telegram UI)  (v2)
# ============================================================
import time
import uuid
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from logger import log_sync
import shop_system as ss

_awaiting_price: dict[int, tuple[list, float]] = {}   # uid -> (items, expires)
_awaiting_name: dict[int, float] = {}
_awaiting_qty: dict[int, tuple[list, float]] = {}      # uid -> (same-name items, expires)

HAGGLE_DISCOUNTS = [0.10, 0.20, 0.30, 0.40]


def _ensure_item_ids(inv: list) -> bool:
    """بعضی آیتم‌ها (مثلاً غنیمت‌های spy/defense/legendary تو بازارِ سیاه) بدونِ
    کلیدِ id ساخته می‌شن. بدونِ id، ساختِ دکمه‌ی «افزودن کالا» با KeyError می‌ترکید
    و کاربر هیچ خطایی نمی‌دید — انگار دکمه کار نمی‌کرد. اینجا برای هر آیتمِ بی‌id
    یکی می‌سازیم تا هم تو لیست دیده بشه، هم بشه انتخابش کرد."""
    changed = False
    for it in inv:
        if not it.get("id"):
            it["id"] = it.get("item_id") or uuid.uuid4().hex[:12]
            changed = True
    return changed


def _owner_ok(cb: CallbackQuery, uid: int) -> bool:
    return cb.from_user.id == uid


def _my_shop_text(player: dict) -> str:
    shop = ss.ensure_shop(player)
    tier = ss.tier_data(shop)
    lines = [
        f"🏪 **{shop['name']}**\n_{ss.reputation_title(shop)}_\n",
        f"📊 سطح: {tier['name']} | جایگاه: {len(shop['listings'])}/{tier['slots']}",
        f"⭐ اعتبار: {shop.get('reputation',0)} (از {len(shop.get('ratings',[]))} امتیاز) | 💰 کارمزد: {int(tier['fee_pct']*100)}٪",
        f"🔓 سقفِ فروش: {ss.max_listable_rarity_label(player)}",
        f"🧾 کل فروش: {shop.get('total_sales',0)}",
    ]
    if shop["listings"]:
        lines.append("\n📦 **کالاهات:**")
        for l in shop["listings"]:
            qty = len(l["items"])
            qty_note = f" ×{qty}" if qty > 1 else ""
            unit_note = "/عدد" if qty > 1 else ""
            lines.append(f"   {l.get('emoji','📦')} {l['name']}{qty_note} — 💰 {l['price']:,}{unit_note}")
    else:
        lines.append("\n📭 مغازه‌ت خالیه.")
    return "\n".join(lines)


def _my_shop_kb(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ افزودن کالا", callback_data=f"shop_add:{uid}", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="➖ برداشتن کالا", callback_data=f"shop_remove:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="✏️ تغییر اسم مغازه", callback_data=f"shop_rename:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="⬆️ ارتقای مغازه", callback_data=f"shop_upgrade:{uid}", style=ButtonStyle.SUCCESS)],
    ])


async def cmd_shop(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    from level_gate import check_level
    ok, why = check_level(player, "shop")
    if not ok:
        await msg.answer(why)
        return

    visit = ss.maybe_refugee_visit(player)
    if visit:
        await asave_player(uid, player)
        await msg.answer(
            f"🌫️ **{visit['buyer']}** رد شد و **{visit['item_name']}** رو از مغازه‌ت خرید!\n"
            f"💰 +{visit['gain']:,} Zen"
        )

    await msg.answer(_my_shop_text(player), reply_markup=_my_shop_kb(uid))


async def cb_shop_home(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    await cb.answer()
    await cb.message.edit_text(_my_shop_text(player), reply_markup=_my_shop_kb(uid))


async def cb_shop_upgrade(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    ok, msg = ss.upgrade_shop(player)
    if ok:
        await asave_player(uid, player)
        log_sync(f"🏪 **SHOP UPGRADE**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "SHOP")
    await cb.answer(msg, show_alert=True)
    await cb.message.edit_text(_my_shop_text(player), reply_markup=_my_shop_kb(uid))


async def cb_shop_rename(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    _awaiting_name[uid] = time.time() + 90
    await cb.answer()
    await cb.message.edit_text("✏️ اسم جدید مغازه‌ت رو بفرست (۲ تا ۳۰ کاراکتر):")


async def cb_shop_add(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    inv = player.get("inventory", [])
    if not inv:
        await cb.answer("🎒 کوله‌پشتیت خالیه!", show_alert=True)
        return
    if _ensure_item_ids(inv):
        await asave_player(uid, player)
    # از اندیسِ آیتم تو کوله‌پشتی استفاده می‌کنیم نه خودِ id، چون بعضی idها
    # (مثلاً موادِ کرفتینگ) طولانی‌ان و با پیشوند+uid از سقفِ ۶۴ بایتیِ
    # callback_data تلگرام رد می‌شن و خطای BUTTON_DATA_INVALID می‌دن.
    buttons = [[InlineKeyboardButton(text=f"{it.get('emoji','📦')} {it.get('name','—')}", callback_data=f"shop_add_pick:{idx}:{uid}", style=ButtonStyle.PRIMARY)]
               for idx, it in enumerate(inv[:20])]
    buttons.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"shop_home:{uid}", style=ButtonStyle.PRIMARY)])
    await cb.answer()
    await cb.message.edit_text(
        f"➕ کدوم آیتم رو می‌خوای بذاری تو مغازه؟\n🔓 سقفِ فروش با سطحت: {ss.max_listable_rarity_label(player)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


async def cb_shop_add_pick(cb: CallbackQuery):
    _, idx_s, uid_s = cb.data.split(":")
    uid = int(uid_s)
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    inv = player.get("inventory", [])
    idx = int(idx_s)
    item = inv[idx] if 0 <= idx < len(inv) else None
    if not item:
        await cb.answer("❌ پیدا نشد.", show_alert=True)
        return
    ok, why = ss.can_list_item(player, item)
    if not ok:
        await cb.answer(why, show_alert=True)
        return

    same = [it for it in inv if it.get("name") == item.get("name")]
    if len(same) > 1:
        n = min(len(same), 10)
        _awaiting_qty[uid] = (same[:n], time.time() + 120)
        buttons, row = [], []
        for q in range(1, n + 1):
            row.append(InlineKeyboardButton(text=str(q), callback_data=f"shop_qty:{q}:{uid}", style=ButtonStyle.PRIMARY))
            if len(row) == 5:
                buttons.append(row); row = []
        if row:
            buttons.append(row)
        buttons.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"shop_home:{uid}", style=ButtonStyle.PRIMARY)])
        await cb.answer()
        await cb.message.edit_text(
            f"📦 {n} تا **{item['name']}** داری. چندتاشو با هم، با یه قیمتِ واحد بذارم؟",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
        return

    _awaiting_price[uid] = ([item], time.time() + 120)
    await cb.answer()
    await cb.message.edit_text(f"💰 قیمتِ **{item['name']}** رو به Zen بفرست (فقط عدد، حداقل 50).")


async def cb_shop_qty(cb: CallbackQuery):
    _, q_s, uid_s = cb.data.split(":")
    q, uid = int(q_s), int(uid_s)
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    entry = _awaiting_qty.pop(uid, None)
    if not entry or time.time() > entry[1]:
        await cb.answer("⏰ زمان تموم شد، دوباره امتحان کن.", show_alert=True)
        return
    same, _ = entry
    chosen = same[:max(1, min(q, len(same)))]
    _awaiting_price[uid] = (chosen, time.time() + 120)
    await cb.answer()
    qty_note = f" ×{len(chosen)}" if len(chosen) > 1 else ""
    unit_note = "/عدد" if len(chosen) > 1 else ""
    await cb.message.edit_text(f"💰 قیمتِ **{chosen[0]['name']}**{qty_note} رو به Zen بفرست{unit_note} (فقط عدد، حداقل 50).")


async def cb_shop_remove(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    shop = ss.ensure_shop(player)
    if not shop["listings"]:
        await cb.answer("📭 مغازه‌ت خالیه.", show_alert=True)
        return
    buttons = []
    for l in shop["listings"]:
        qty_note = f" ×{len(l['items'])}" if len(l["items"]) > 1 else ""
        buttons.append([InlineKeyboardButton(
            text=f"❌ {l['name']}{qty_note}", callback_data=f"shop_remove_pick:{l['listing_id']}:{uid}", style=ButtonStyle.DANGER
        )])
    buttons.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"shop_home:{uid}", style=ButtonStyle.PRIMARY)])
    await cb.answer()
    await cb.message.edit_text("➖ کدوم کالا رو برداری؟", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


async def cb_shop_remove_pick(cb: CallbackQuery):
    _, listing_id, uid_s = cb.data.split(":")
    uid = int(uid_s)
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    ok, msg = ss.remove_listing(player, listing_id)
    if ok:
        await asave_player(uid, player)
    await cb.answer(msg, show_alert=True)
    await cb.message.edit_text(_my_shop_text(player), reply_markup=_my_shop_kb(uid))


async def handle_shop_text(msg: Message):
    uid = msg.from_user.id
    if uid in _awaiting_name:
        expires = _awaiting_name.pop(uid)
        if time.time() > expires:
            await msg.answer("⏰ زمان تموم شد.")
            return
        player = await aget_player(uid)
        ok, result = ss.rename_shop(player, (msg.text or "").strip())
        if ok:
            await asave_player(uid, player)
        await msg.answer(result)
        return

    entry = _awaiting_price.get(uid)
    if entry:
        items, expires = entry
        if time.time() > expires:
            del _awaiting_price[uid]
            await msg.answer("⏰ زمان تموم شد.")
            return
        text = (msg.text or "").strip()
        if not text.isdigit() or int(text) <= 0:
            await msg.answer("❌ یه عددِ درست بفرست!")
            return
        del _awaiting_price[uid]
        player = await aget_player(uid)
        ok, result = ss.list_items(player, items, int(text))
        if ok:
            await asave_player(uid, player)
            log_sync(f"🏪 **SHOP LIST**\n👤 {player.get('name','—')} (`{uid}`)\n📦 {items[0]['name']} ×{len(items)} — {text} Zen", "SHOP")
        await msg.answer(result, reply_markup=_my_shop_kb(uid))
        return


# ─── 🔍 بازدید از مغازه‌ی بقیه ─────────────────────────────────
def _visit_text_kb(owner: dict, visitor_uid: int):
    shop = ss.ensure_shop(owner)
    tier = ss.tier_data(shop)
    lines = [
        f"🏪 **{shop['name']}**\n_{ss.reputation_title(shop)}_\n",
        f"⭐ اعتبار: {shop.get('reputation',0)} (از {len(shop.get('ratings',[]))} امتیاز)\n",
    ]
    buttons = []
    if not shop["listings"]:
        lines.append("📭 این مغازه فعلاً خالیه.")
    else:
        for l in shop["listings"]:
            qty = len(l["items"])
            qty_note = f" (موجودی: {qty})" if qty > 1 else ""
            lines.append(f"{l.get('emoji','📦')} **{l['name']}**{qty_note} — 💰 {l['price']:,}")
            buttons.append([
                InlineKeyboardButton(text=f"🛍 خرید ({l['price']:,})",
                    callback_data=f"shop_buy:{owner['id']}:{l['listing_id']}:{visitor_uid}", style=ButtonStyle.SUCCESS),
                InlineKeyboardButton(text="🤝 چانه بزن",
                    callback_data=f"shop_haggle:{owner['id']}:{l['listing_id']}:{visitor_uid}", style=ButtonStyle.PRIMARY),
            ])
    buttons.append([InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data=f"shop_rate:{owner['id']}:5:{visitor_uid}", style=ButtonStyle.PRIMARY),
                     InlineKeyboardButton(text="⭐", callback_data=f"shop_rate:{owner['id']}:1:{visitor_uid}", style=ButtonStyle.PRIMARY)])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)


async def cmd_visit(msg: Message):
    uid = msg.from_user.id
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        await msg.answer("📖 فرمت: `/visit @username`")
        return
    from pvp_handlers import _resolve_track_target
    target_id = _resolve_track_target(args[1], uid)
    if not target_id:
        await msg.answer("❌ این بازیکن پیدا نشد.")
        return
    owner = await aget_player(target_id)
    if not owner:
        await msg.answer("❌ این بازیکن پیدا نشد.")
        return
    text, kb = _visit_text_kb(owner, uid)
    await msg.answer(text, reply_markup=kb)


async def cb_shop_buy(cb: CallbackQuery):
    _, owner_id_s, listing_id, uid_s = cb.data.split(":")
    owner_id, uid = int(owner_id_s), int(uid_s)
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    buyer = await aget_player(uid)
    owner = await aget_player(owner_id)
    if not owner:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    ok, msg, info = ss.buy_from_shop(buyer, owner, listing_id)
    if not ok:
        await cb.answer(msg, show_alert=True)
        return
    await asave_player(uid, buyer)
    owner["zen"] = owner.get("zen", 0) + info["owner_gain"]
    await asave_player(owner_id, owner)
    log_sync(
        f"🏪 **SHOP SALE**\n🛍 خریدار: {buyer.get('name','—')} (`{uid}`)\n"
        f"🏪 مغازه‌ی: {owner.get('name','—')}\n📦 {info['item_name']} | 💰 فروشنده گرفت: {info['owner_gain']:,}",
        "SHOP"
    )
    await cb.answer(msg, show_alert=True)
    text, kb = _visit_text_kb(owner, uid)
    await cb.message.edit_text(text, reply_markup=kb)


async def cb_shop_haggle(cb: CallbackQuery):
    _, owner_id_s, listing_id, uid_s = cb.data.split(":")
    owner_id, uid = int(owner_id_s), int(uid_s)
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    owner = await aget_player(owner_id)
    if not owner:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    shop = ss.ensure_shop(owner)
    listing = ss._find_listing(shop, listing_id)
    if not listing or not listing["items"]:
        await cb.answer("❌ این آیتم دیگه موجود نیست.", show_alert=True)
        return
    base = listing["price"]
    buttons = [[InlineKeyboardButton(
        text=f"{int(d*100)}٪ تخفیف ({int(base*(1-d)):,} Zen)",
        callback_data=f"shop_hoffer:{owner_id}:{listing_id}:{int(base*(1-d))}:{uid}",
        style=ButtonStyle.PRIMARY)] for d in HAGGLE_DISCOUNTS]
    buttons.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"shop_visitback:{owner_id}:{uid}", style=ButtonStyle.PRIMARY)])
    await cb.answer()
    await cb.message.edit_text(
        f"🤝 چقدر پیشنهاد بدم برای **{listing['name']}**؟\n💰 قیمتِ پایه: {base:,} Zen",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


async def cb_shop_haggle_offer(cb: CallbackQuery):
    _, owner_id_s, listing_id, offer_s, uid_s = cb.data.split(":")
    owner_id, offer, uid = int(owner_id_s), int(offer_s), int(uid_s)
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    owner = await aget_player(owner_id)
    buyer = await aget_player(uid)
    if not owner or not buyer:
        await cb.answer("❌ خطا!", show_alert=True)
        return

    ok, msg, result = ss.haggle_offer(uid, owner, listing_id, offer)
    if not ok:
        await asave_player(owner_id, owner)  # تلاش/قفل ثبت بشه حتی وقتی رد می‌شه
        await cb.answer(msg, show_alert=True)
        return

    buy_ok, buy_msg, info = ss.buy_from_shop(buyer, owner, listing_id, unit_price=result["price"])
    if not buy_ok:
        await asave_player(owner_id, owner)
        await cb.answer(buy_msg, show_alert=True)
        return
    await asave_player(uid, buyer)
    owner["zen"] = owner.get("zen", 0) + info["owner_gain"]
    await asave_player(owner_id, owner)
    log_sync(
        f"🤝 **SHOP HAGGLE SALE**\n🛍 {buyer.get('name','—')} (`{uid}`)\n"
        f"🏪 {owner.get('name','—')}\n📦 {info['item_name']} | 💰 {result['price']:,} (چانه‌زنی)",
        "SHOP"
    )
    await cb.answer(f"{msg}\n{buy_msg}", show_alert=True)
    text, kb = _visit_text_kb(owner, uid)
    await cb.message.edit_text(text, reply_markup=kb)


async def cb_shop_visit_back(cb: CallbackQuery):
    _, owner_id_s, uid_s = cb.data.split(":")
    owner_id, uid = int(owner_id_s), int(uid_s)
    owner = await aget_player(owner_id)
    if not owner:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    text, kb = _visit_text_kb(owner, uid)
    await cb.answer()
    await cb.message.edit_text(text, reply_markup=kb)


async def cb_shop_rate(cb: CallbackQuery):
    _, owner_id_s, stars_s, uid_s = cb.data.split(":")
    owner_id, stars, uid = int(owner_id_s), int(stars_s), int(uid_s)
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    owner = await aget_player(owner_id)
    if not owner:
        await cb.answer("❌", show_alert=True)
        return
    ok, msg = ss.rate_shop(owner, uid, stars)
    if ok:
        await asave_player(owner_id, owner)
    await cb.answer(msg, show_alert=True)


def register_shop_handlers(dp, bot):
    dp.message.register(cmd_shop, Command("shop"))
    dp.message.register(cmd_visit, Command("visit"))
    dp.callback_query.register(cb_shop_home,          F.data.startswith("shop_home:"))
    dp.callback_query.register(cb_shop_upgrade,        F.data.startswith("shop_upgrade:"))
    dp.callback_query.register(cb_shop_rename,         F.data.startswith("shop_rename:"))
    dp.callback_query.register(cb_shop_add_pick,       F.data.startswith("shop_add_pick:"))
    dp.callback_query.register(cb_shop_add,            F.data.startswith("shop_add:"))
    dp.callback_query.register(cb_shop_qty,            F.data.startswith("shop_qty:"))
    dp.callback_query.register(cb_shop_remove_pick,    F.data.startswith("shop_remove_pick:"))
    dp.callback_query.register(cb_shop_remove,         F.data.startswith("shop_remove:"))
    dp.callback_query.register(cb_shop_buy,            F.data.startswith("shop_buy:"))
    dp.callback_query.register(cb_shop_haggle_offer,   F.data.startswith("shop_hoffer:"))
    dp.callback_query.register(cb_shop_haggle,         F.data.startswith("shop_haggle:"))
    dp.callback_query.register(cb_shop_visit_back,     F.data.startswith("shop_visitback:"))
    dp.callback_query.register(cb_shop_rate,           F.data.startswith("shop_rate:"))
    dp.message.register(handle_shop_text, lambda m: m.from_user.id in _awaiting_price or m.from_user.id in _awaiting_name)
