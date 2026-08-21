# ============================================================
#  ASTRAL ABYSS RPG — 🧳 تاجرانِ دوره‌گرد (Road Merchant Handlers)
# ------------------------------------------------------------
#  بعدِ رسیدن به هر مپی (توسطِ سیستمِ سفرِ loot)، هر بازیکنی —
#  فارغ از کلاس — می‌تونه با یه تاجرِ دوره‌گرد حرف بزنه، واقعاً ازش
#  آیتمِ مصرفی بخره یا از اینونتوریِ خودش بهش بفروشه.
#  استاکِ خرید فقط تو حافظه نگه داشته می‌شه (regenerate هر بارِ ورود).
# ============================================================
from __future__ import annotations

from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from logger import log_sync
import road_merchants as rm

# uid -> {"npc_id": str, "stock": [item,...], "map": str}
_SESSIONS: dict[int, dict] = {}


def _get_session(uid: int, map_name: str, player_level: int) -> dict:
    s = _SESSIONS.get(uid)
    if not s or s.get("map") != map_name:
        npc = rm.roll_road_npc()
        s = {"npc_id": npc["id"], "stock": rm.roll_stock(player_level), "map": map_name}
        _SESSIONS[uid] = s
    return s


def _hub_kb(map_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛍️ خرید", callback_data=f"road:buy:{map_name}"),
            InlineKeyboardButton(text="💰 فروش", callback_data=f"road:sell:{map_name}"),
        ],
        [InlineKeyboardButton(text="👋 خداحافظی", callback_data=f"road:bye:{map_name}")],
    ])


def _back_kb(map_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 برگشت", callback_data=f"road:open:{map_name}")],
    ])


async def cb_road_open(cb: CallbackQuery):
    map_name = cb.data.split(":", 2)[2]
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ اول باید بازی رو شروع کنی: /start", show_alert=True)
        return
    await cb.answer()

    s = _get_session(uid, map_name, player.get("level", 1))
    npc = rm.get_road_npc(s["npc_id"])
    greet = rm.pick_line(npc, "greeting")

    text = (
        f"{npc['title']}\n**{npc['name']}**\n\n"
        f"💬 {greet}"
    )
    await cb.message.answer(text, reply_markup=_hub_kb(map_name))


async def cb_road_buy(cb: CallbackQuery):
    map_name = cb.data.split(":", 2)[2]
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    await cb.answer()

    s = _get_session(uid, map_name, player.get("level", 1))
    stock = s["stock"]
    if not stock:
        await cb.message.edit_text("🛍️ فعلاً چیزی برای فروش نداره.", reply_markup=_back_kb(map_name))
        return

    rows = []
    lines = ["🛍️ **جنسِ تاجرِ دوره‌گرد:**\n"]
    for i, item in enumerate(stock):
        price = item.get("buy", item.get("sell", 0) * 2)
        lines.append(f"{item.get('emoji','📦')} **{item['name']}** ({item.get('rarity','common')}) — {price:,} Zen\n_{item.get('desc','')}_\n")
        rows.append([InlineKeyboardButton(text=f"{item.get('emoji','📦')} {item['name']} — {price:,} Zen", callback_data=f"road:buyitem:{map_name}:{i}")])
    rows.append([InlineKeyboardButton(text="🔙 برگشت", callback_data=f"road:open:{map_name}")])
    await cb.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


async def cb_road_buyitem(cb: CallbackQuery):
    _, _, map_name, idx_s = cb.data.split(":")
    idx = int(idx_s)
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    s = _SESSIONS.get(uid)
    if not s or s.get("map") != map_name or idx >= len(s["stock"]):
        await cb.answer("❌ این جنس دیگه موجود نیست.", show_alert=True)
        return

    item = s["stock"][idx]
    price = item.get("buy", item.get("sell", 0) * 2)
    if player.get("zen", 0) < price:
        await cb.answer(f"❌ Zen کافی نداری! ({price:,} لازمه)", show_alert=True)
        return

    player["zen"] -= price
    player.setdefault("inventory", []).append(dict(item))
    await asave_player(uid, player)
    del s["stock"][idx]

    npc = rm.get_road_npc(s["npc_id"])
    flavor = rm.pick_line(npc, "sell_flavor")
    await cb.answer(f"✅ {item['name']} خریداری شد!")
    log_sync(f"🧳 **ROAD BUY** — {player.get('name','—')} (`{uid}`) از {npc['name']} خرید: {item['name']} ({price:,} Zen)", "ROAD")

    text = f"{npc['title']} **{npc['name']}**\n\n💬 {flavor}"
    await cb.message.edit_text(text, reply_markup=_hub_kb(map_name))


async def cb_road_sell(cb: CallbackQuery):
    map_name = cb.data.split(":", 2)[2]
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    inv = [it for it in player.get("inventory", []) if not it.get("shop_exclusive")]
    if not inv:
        await cb.answer("🎒 کوله‌پشتیت خالیه یا همه‌ی آیتم‌هات ویژه‌ن.", show_alert=True)
        return
    await cb.answer()

    rows = []
    lines = ["💰 **چی می‌خوای بفروشی؟**\n"]
    for item in inv[:10]:
        sell_p = item.get("sell", 0)
        iid = item.get("item_id") or item.get("id")
        lines.append(f"{item.get('emoji','📦')} {item['name']} — {sell_p:,} Zen\n")
        rows.append([InlineKeyboardButton(text=f"{item.get('emoji','📦')} {item['name']} — {sell_p:,} Zen", callback_data=f"road:sellitem:{map_name}:{iid}")])
    if len(inv) > 10:
        lines.append(f"\n... و {len(inv)-10} آیتمِ دیگه (اول اینا رو بفروش)")
    rows.append([InlineKeyboardButton(text="🔙 برگشت", callback_data=f"road:open:{map_name}")])
    await cb.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


async def cb_road_sellitem(cb: CallbackQuery):
    _, _, map_name, item_id = cb.data.split(":")
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    inv = player.get("inventory", [])
    target = None
    for it in inv:
        if (it.get("item_id") or it.get("id")) == item_id:
            target = it
            break
    if not target:
        await cb.answer("❌ این آیتم دیگه تو کوله‌پشتیت نیست.", show_alert=True)
        return

    sell_p = target.get("sell", 0)
    inv.remove(target)
    player["zen"] = player.get("zen", 0) + sell_p
    await asave_player(uid, player)

    s = _get_session(uid, map_name, player.get("level", 1))
    npc = rm.get_road_npc(s["npc_id"])
    flavor = rm.pick_line(npc, "buy_flavor")
    await cb.answer(f"✅ فروخته شد! +{sell_p:,} Zen")
    log_sync(f"🧳 **ROAD SELL** — {player.get('name','—')} (`{uid}`) به {npc['name']} فروخت: {target.get('name','—')} ({sell_p:,} Zen)", "ROAD")

    text = f"{npc['title']} **{npc['name']}**\n\n💬 {flavor}"
    await cb.message.edit_text(text, reply_markup=_hub_kb(map_name))


async def cb_road_bye(cb: CallbackQuery):
    map_name = cb.data.split(":", 2)[2]
    uid = cb.from_user.id
    s = _SESSIONS.get(uid)
    npc = rm.get_road_npc(s["npc_id"]) if s else None
    await cb.answer()
    if npc:
        flavor = rm.pick_line(npc, "farewell")
        await cb.message.edit_text(f"{npc['title']} **{npc['name']}**\n\n👋 {flavor}")
    else:
        await cb.message.edit_text("👋 خداحافظ!")
    _SESSIONS.pop(uid, None)


def register_road_merchant_handlers(dp, bot):
    dp.callback_query.register(cb_road_open, F.data.startswith("road:open:"))
    dp.callback_query.register(cb_road_buy, F.data.startswith("road:buy:"))
    dp.callback_query.register(cb_road_buyitem, F.data.startswith("road:buyitem:"))
    dp.callback_query.register(cb_road_sell, F.data.startswith("road:sell:"))
    dp.callback_query.register(cb_road_sellitem, F.data.startswith("road:sellitem:"))
    dp.callback_query.register(cb_road_bye, F.data.startswith("road:bye:"))
