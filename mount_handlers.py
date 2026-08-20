# ============================================================
#  ASTRAL ABYSS RPG — Mount Handlers (Telegram UI) 🐎
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
from action_lock import no_double_tap
import mount_system as ms


def _main_kb(player: dict) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🐎 کالکشنِ من", callback_data="mount_collection", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🛒 فروشگاه (Echo Shard)", callback_data="mount_shop", style=ButtonStyle.SUCCESS)],
    ]
    if player.get("active_mount"):
        rows.append([InlineKeyboardButton(text="🚫 پیاده شو", callback_data="mount_unequip", style=ButtonStyle.DANGER)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cmd_mounts(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    active = player.get("active_mount")
    header = "🐎 **مونت‌ها**\n\n"
    if active:
        m = ms.get_mount(active)
        header += f"سوارِ فعلی: {m['name']} (قدرت +{m['power']})\n\n"
    else:
        header += "الان سوارِ هیچ مونتی نیستی.\n\n"
    header += f"🔹 Echo Shard: {player.get('rift_shards', 0):,} (از 🌀 شکافِ Abyss به دست میاد)"
    await msg.answer(header, reply_markup=_main_kb(player))


async def cb_mount_collection(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    owned = ms.owned_mounts(player)
    text = ms.collection_text(player)
    rows = []
    order = {r: i for i, r in enumerate(ms.RARITY_ORDER)}
    for mid in sorted(owned, key=lambda x: order.get(ms.MOUNTS[x]["rarity"], 9)):
        if mid == player.get("active_mount"):
            continue
        m = ms.MOUNTS[mid]
        rows.append([InlineKeyboardButton(text=f"سوار شو: {m['name']}", callback_data=f"mount_equip:{mid}", style=ButtonStyle.SUCCESS)])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data="mount_back", style=ButtonStyle.SECONDARY)])
    await cb.answer()
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


async def cb_mount_shop(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    listing = ms.shop_listing(player)
    lines = [f"🛒 **فروشگاهِ مونت** — موجودی: {player.get('rift_shards',0):,} 🔹\n"]
    rows = []
    for r in listing:
        tag = " ✅ داری" if r["owned"] else f" — {r['price_shards']:,} 🔹"
        lines.append(f"{ms.RARITY_LABELS[r['rarity']]} {r['name']} (قدرت {r['power']}){tag}")
        if not r["owned"] and r["price_shards"] is not None:
            rows.append([InlineKeyboardButton(
                text=f"خرید: {r['name']} ({r['price_shards']:,}🔹)",
                callback_data=f"mount_buy:{r['id']}", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data="mount_back", style=ButtonStyle.SECONDARY)])
    await cb.answer()
    await cb.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@no_double_tap()
async def cb_mount_buy(cb: CallbackQuery):
    uid = cb.from_user.id
    mount_id = cb.data.split(":")[1]
    player = get_player(uid)
    ok, text = ms.buy_with_shards(player, mount_id)
    if ok:
        save_player(uid, player)
    await cb.answer(text, show_alert=not ok)
    await cb_mount_shop(cb)


@no_double_tap()
async def cb_mount_equip(cb: CallbackQuery):
    uid = cb.from_user.id
    mount_id = cb.data.split(":")[1]
    player = get_player(uid)
    ok, text = ms.equip_mount(player, mount_id)
    if ok:
        save_player(uid, player)
    await cb.answer(text, show_alert=not ok)
    await cb_mount_collection(cb)


@no_double_tap()
async def cb_mount_unequip(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    text = ms.unequip_mount(player)
    save_player(uid, player)
    await cb.answer(text)
    await cb.message.edit_text(
        "🐎 **مونت‌ها**\n\nالان سوارِ هیچ مونتی نیستی.",
        reply_markup=_main_kb(player)
    )


async def cb_mount_back(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    active = player.get("active_mount")
    header = "🐎 **مونت‌ها**\n\n"
    if active:
        m = ms.get_mount(active)
        header += f"سوارِ فعلی: {m['name']} (قدرت +{m['power']})\n\n"
    else:
        header += "الان سوارِ هیچ مونتی نیستی.\n\n"
    header += f"🔹 Echo Shard: {player.get('rift_shards', 0):,}"
    await cb.answer()
    await cb.message.edit_text(header, reply_markup=_main_kb(player))


def register_mount_handlers(dp, bot):
    dp.message.register(cmd_mounts, Command("mounts"))
    dp.callback_query.register(cb_mount_collection, F.data == "mount_collection")
    dp.callback_query.register(cb_mount_shop, F.data == "mount_shop")
    dp.callback_query.register(cb_mount_buy, F.data.startswith("mount_buy:"))
    dp.callback_query.register(cb_mount_equip, F.data.startswith("mount_equip:"))
    dp.callback_query.register(cb_mount_unequip, F.data == "mount_unequip")
    dp.callback_query.register(cb_mount_back, F.data == "mount_back")
