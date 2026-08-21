# ============================================================
#  ASTRAL ABYSS — Gap Shop Handlers (پورت از shop_handlers.py)
# ------------------------------------------------------------
#  منطقِ خالص (shop_system.py) عیناً import می‌شه — صفر تغییر.
#  فقط کیبورد/پیام‌رسانی برای گپ بازنویسی شده، و به‌جای دو تا
#  دیکشنریِ محلی + یه لامبدا-فیلترِ سراسری (که تو aiogram برای
#  گرفتنِ «متنِ بعدی» استفاده می‌شد)، از state-routing خودِ
#  GapDispatcher استفاده می‌کنیم (dp.on_state / dp.state.set_state).
# ============================================================
from __future__ import annotations

import time

from gap_dispatcher import GapDispatcher
from gap_types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message

from database import get_player, save_player, asave_player, aget_player
from logger import log_sync
import shop_system as ss

# uid -> (item, expires) | uid -> expires   — همون منطقِ اصلی، فقط
# مسیریابیِ «الان منتظرِ چه متنی هستیم» رو دیگه GapDispatcher.state انجام می‌ده
_awaiting_price: dict[int, tuple[dict, float]] = {}
_awaiting_name: dict[int, float] = {}

STATE_PRICE = "shop:awaiting_price"
STATE_NAME = "shop:awaiting_name"


def _owner_ok(cb: CallbackQuery, uid: int) -> bool:
    return cb.from_user.id == uid


def _my_shop_text(player: dict) -> str:
    shop = ss.ensure_shop(player)
    tier = ss.tier_data(shop)
    lines = [
        f"🏪 **{shop['name']}**\n_{ss.reputation_title(shop)}_\n",
        f"📊 سطح: {tier['name']} | جایگاه: {len(shop['listings'])}/{tier['slots']}",
        f"⭐ اعتبار: {shop.get('reputation',0)} (از {len(shop.get('ratings',[]))} امتیاز) | 💰 کارمزد: {int(tier['fee_pct']*100)}٪",
        f"🧾 کل فروش: {shop.get('total_sales',0)}",
    ]
    if shop["listings"]:
        lines.append("\n📦 **کالاهات:**")
        for l in shop["listings"]:
            lines.append(f"   {l['item'].get('emoji','📦')} {l['item']['name']} — 💰 {l['price']:,}")
    else:
        lines.append("\n📭 مغازه‌ت خالیه.")
    return "\n".join(lines)


def _my_shop_kb(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ افزودن کالا", callback_data=f"shop_add:{uid}")],
        [InlineKeyboardButton(text="➖ برداشتن کالا", callback_data=f"shop_remove:{uid}")],
        [InlineKeyboardButton(text="✏️ تغییر اسم مغازه", callback_data=f"shop_rename:{uid}")],
        [InlineKeyboardButton(text="⬆️ ارتقای مغازه", callback_data=f"shop_upgrade:{uid}")],
    ])


def _visit_text_kb(owner: dict, visitor_uid: int):
    shop = ss.ensure_shop(owner)
    lines = [
        f"🏪 **{shop['name']}**\n_{ss.reputation_title(shop)}_\n",
        f"⭐ اعتبار: {shop.get('reputation',0)} (از {len(shop.get('ratings',[]))} امتیاز)\n",
    ]
    buttons = []
    if not shop["listings"]:
        lines.append("📭 این مغازه فعلاً خالیه.")
    else:
        for l in shop["listings"]:
            lines.append(f"{l['item'].get('emoji','📦')} **{l['item']['name']}** — 💰 {l['price']:,}")
            buttons.append([InlineKeyboardButton(
                text=f"🛍 خرید {l['item']['name']} ({l['price']:,})",
                callback_data=f"shop_buy:{owner['id']}:{l['item']['id']}:{visitor_uid}",
            )])
    buttons.append([
        InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data=f"shop_rate:{owner['id']}:5:{visitor_uid}"),
        InlineKeyboardButton(text="⭐", callback_data=f"shop_rate:{owner['id']}:1:{visitor_uid}"),
    ])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)


def register_gap_shop_handlers(dp: GapDispatcher):

    @dp.message(commands=["shop"])
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

    @dp.message(commands=["visit"])
    async def cmd_visit(msg: Message):
        uid = msg.from_user.id
        args = msg.text.split(maxsplit=1)
        if len(args) < 2:
            await msg.answer("📖 فرمت: `/visit @username`")
            return
        from gap_pvp_handlers import _resolve_track_target
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

    @dp.callback_query(data_startswith="shop_home:")
    async def cb_shop_home(cb: CallbackQuery):
        uid = int(cb.data.split(":")[1])
        if not _owner_ok(cb, uid):
            await cb.answer("❌", show_alert=True)
            return
        player = await aget_player(uid)
        await cb.answer()
        await cb.message.edit_text(_my_shop_text(player), reply_markup=_my_shop_kb(uid))

    @dp.callback_query(data_startswith="shop_upgrade:")
    async def cb_shop_upgrade(cb: CallbackQuery):
        uid = int(cb.data.split(":")[1])
        if not _owner_ok(cb, uid):
            await cb.answer("❌", show_alert=True)
            return
        player = await aget_player(uid)
        ok, msg_ = ss.upgrade_shop(player)
        if ok:
            await asave_player(uid, player)
            log_sync(f"🏪 **SHOP UPGRADE**\n👤 {player.get('name','—')} (`{uid}`)\n{msg_}", "SHOP")
        await cb.answer(msg_, show_alert=True)
        await cb.message.edit_text(_my_shop_text(player), reply_markup=_my_shop_kb(uid))

    @dp.callback_query(data_startswith="shop_rename:")
    async def cb_shop_rename(cb: CallbackQuery):
        uid = int(cb.data.split(":")[1])
        if not _owner_ok(cb, uid):
            await cb.answer("❌", show_alert=True)
            return
        _awaiting_name[uid] = time.time() + 90
        dp.state.set_state(uid, STATE_NAME)
        await cb.answer()
        await cb.message.edit_text("✏️ اسم جدید مغازه‌ت رو بفرست (۲ تا ۳۰ کاراکتر):")

    @dp.callback_query(data_startswith="shop_add_pick:")
    async def cb_shop_add_pick(cb: CallbackQuery):
        _, item_id, uid_s = cb.data.split(":")
        uid = int(uid_s)
        if not _owner_ok(cb, uid):
            await cb.answer("❌", show_alert=True)
            return
        player = await aget_player(uid)
        item = next((it for it in player.get("inventory", []) if it.get("id") == item_id), None)
        if not item:
            await cb.answer("❌ پیدا نشد.", show_alert=True)
            return
        _awaiting_price[uid] = (item, time.time() + 120)
        dp.state.set_state(uid, STATE_PRICE)
        await cb.answer()
        await cb.message.edit_text(f"💰 قیمتِ **{item['name']}** رو به Zen بفرست (فقط عدد، حداقل 50).")

    @dp.callback_query(data_startswith="shop_add:")
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
        buttons = [[InlineKeyboardButton(text=f"{it.get('emoji','📦')} {it['name']}", callback_data=f"shop_add_pick:{it['id']}:{uid}")]
                   for it in inv[:20]]
        buttons.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"shop_home:{uid}")])
        await cb.answer()
        await cb.message.edit_text("➕ کدوم آیتم رو می‌خوای بذاری تو مغازه؟", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

    @dp.callback_query(data_startswith="shop_remove_pick:")
    async def cb_shop_remove_pick(cb: CallbackQuery):
        _, item_id, uid_s = cb.data.split(":")
        uid = int(uid_s)
        if not _owner_ok(cb, uid):
            await cb.answer("❌", show_alert=True)
            return
        player = await aget_player(uid)
        ok, msg_ = ss.remove_item(player, item_id)
        if ok:
            await asave_player(uid, player)
        await cb.answer(msg_, show_alert=True)
        await cb.message.edit_text(_my_shop_text(player), reply_markup=_my_shop_kb(uid))

    @dp.callback_query(data_startswith="shop_remove:")
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
        buttons = [[InlineKeyboardButton(text=f"❌ {l['item']['name']}", callback_data=f"shop_remove_pick:{l['item']['id']}:{uid}")]
                   for l in shop["listings"]]
        buttons.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"shop_home:{uid}")])
        await cb.answer()
        await cb.message.edit_text("➖ کدوم آیتم رو برداری؟", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

    @dp.callback_query(data_startswith="shop_buy:")
    async def cb_shop_buy(cb: CallbackQuery):
        _, owner_id_s, item_id, uid_s = cb.data.split(":")
        owner_id, uid = int(owner_id_s), int(uid_s)
        if not _owner_ok(cb, uid):
            await cb.answer("❌", show_alert=True)
            return
        buyer = await aget_player(uid)
        owner = await aget_player(owner_id)
        if not owner:
            await cb.answer("❌ خطا!", show_alert=True)
            return
        ok, msg_, info = ss.buy_from_shop(buyer, owner, item_id)
        if not ok:
            await cb.answer(msg_, show_alert=True)
            return
        await asave_player(uid, buyer)
        owner["zen"] = owner.get("zen", 0) + info["owner_gain"]
        await asave_player(owner_id, owner)
        log_sync(
            f"🏪 **SHOP SALE**\n🛍 خریدار: {buyer.get('name','—')} (`{uid}`)\n"
            f"🏪 مغازه‌ی: {owner.get('name','—')}\n📦 {info['item_name']} | 💰 فروشنده گرفت: {info['owner_gain']:,}",
            "SHOP",
        )
        await cb.answer(msg_, show_alert=True)
        text, kb = _visit_text_kb(owner, uid)
        await cb.message.edit_text(text, reply_markup=kb)

    @dp.callback_query(data_startswith="shop_rate:")
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
        ok, msg_ = ss.rate_shop(owner, uid, stars)
        if ok:
            await asave_player(owner_id, owner)
        await cb.answer(msg_, show_alert=True)

    async def _handle_shop_state_text(msg: Message):
        uid = msg.from_user.id
        dp.state.set_state(uid, None)

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
            item, expires = entry
            if time.time() > expires:
                del _awaiting_price[uid]
                await msg.answer("⏰ زمان تموم شد.")
                return
            text = (msg.text or "").strip()
            if not text.isdigit() or int(text) <= 0:
                await msg.answer("❌ یه عددِ درست بفرست!")
                dp.state.set_state(uid, STATE_PRICE)  # هنوز منتظریم، دوباره امتحان کنه
                return
            del _awaiting_price[uid]
            player = await aget_player(uid)
            ok, result = ss.list_item(player, item, int(text))
            if ok:
                await asave_player(uid, player)
                log_sync(f"🏪 **SHOP LIST**\n👤 {player.get('name','—')} (`{uid}`)\n📦 {item['name']} — {text} Zen", "SHOP")
            await msg.answer(result, reply_markup=_my_shop_kb(uid))
            return

    dp.register_state(STATE_NAME, _handle_shop_state_text)
    dp.register_state(STATE_PRICE, _handle_shop_state_text)
