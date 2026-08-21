# ============================================================
#  ASTRAL ABYSS RPG — Land Handlers (Telegram UI)  — v1
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from logger import log_sync
import land_system as ls


def _owner_ok(cb: CallbackQuery, uid: int) -> bool:
    return cb.from_user.id == uid


def _home_kb(uid: int, player: dict) -> InlineKeyboardMarkup:
    doc = ls.get_my_land(uid)
    rows = []
    if doc:
        rows.append([InlineKeyboardButton(text="🌾 مزرعه", callback_data=f"farm_home:{uid}", style=ButtonStyle.SUCCESS)])
        rows.append([InlineKeyboardButton(text="💰 برداشتِ درآمدِ اجاره", callback_data=f"land_collect:{uid}", style=ButtonStyle.SUCCESS)])
        rows.append([InlineKeyboardButton(text="📈 بزرگ‌کردنِ زمین", callback_data=f"land_expand:{uid}", style=ButtonStyle.SUCCESS)])
        if doc.get("listed_price"):
            rows.append([InlineKeyboardButton(text="🚫 برداشتن از بازارِ فروش", callback_data=f"land_unlist:{uid}", style=ButtonStyle.DANGER)])
        else:
            rows.append([InlineKeyboardButton(text="🏷️ گذاشتن رو بازارِ فروش", callback_data=f"land_list:{uid}", style=ButtonStyle.PRIMARY)])
        rows.append([InlineKeyboardButton(text="🔑 تنظیمِ قیمتِ اجاره", callback_data=f"land_setrent:{uid}", style=ButtonStyle.PRIMARY)])
        rows.append([InlineKeyboardButton(text="👋 رهاکردنِ زمین", callback_data=f"land_abandon:{uid}", style=ButtonStyle.DANGER)])
    else:
        map_name = player.get("map", "Verdant Vale")
        rows.append([InlineKeyboardButton(text=f"🗺 پلاک‌های همین نقشه ({map_name})", callback_data=f"land_map:{uid}:{map_name}", style=ButtonStyle.PRIMARY)])
        rows.append([InlineKeyboardButton(text="🏷️ زمین‌های رو بازارِ فروش", callback_data=f"land_market:{uid}", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت به ملک", callback_data=f"house_home:{uid}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cmd_land(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    await msg.answer("🗺 **زمین**\n\n" + ls.land_summary_text(uid), reply_markup=_home_kb(uid, player))


async def cb_land_home(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    await cb.answer()
    await cb.message.edit_text("🗺 **زمین**\n\n" + ls.land_summary_text(uid), reply_markup=_home_kb(uid, player))


def _plot_kb(uid: int, map_name: str, plots: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for p in plots:
        size = ls.size_data(p["size"])
        if p["owner"] is None:
            label = f"{size['name']} — خالی — {size['cost']:,} Zen"
            cb_data = f"land_buy:{uid}:{map_name}:{p['plot_id']}"
        elif p["owner"] == uid:
            label = f"{size['name']} — زمینِ خودت ✅"
            cb_data = "atk:locked"
        else:
            label = f"{size['name']} — متعلق به {p.get('owner_name','—')}"
            cb_data = "atk:locked"
        rows.append([InlineKeyboardButton(text=label, callback_data=cb_data, style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data=f"land_home:{uid}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_land_map(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid = int(parts[1])
    map_name = parts[2]
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    plots = ls.list_plots(map_name)
    await cb.answer()
    await cb.message.edit_text(
        f"🗺 **پلاک‌های {map_name}**\n\nهر بازیکن فقط یه زمین می‌تونه داشته باشه.",
        reply_markup=_plot_kb(uid, map_name, plots),
    )


async def cb_land_buy(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid = int(parts[1])
    map_name = parts[2]
    plot_id = int(parts[3])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    ok, msg = ls.buy_land(uid, player, map_name, plot_id)
    if ok:
        await asave_player(uid, player)
        log_sync(f"🗺 **LAND BUY**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "HOUSE")
    await cb.answer(msg, show_alert=True)
    await cb.message.edit_text("🗺 **زمین**\n\n" + ls.land_summary_text(uid), reply_markup=_home_kb(uid, player))


async def cb_land_expand(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    ok, msg = ls.expand_land(uid, player)
    if ok:
        await asave_player(uid, player)
        log_sync(f"🗺 **LAND EXPAND**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "HOUSE")
    await cb.answer(msg, show_alert=True)
    await cb.message.edit_text("🗺 **زمین**\n\n" + ls.land_summary_text(uid), reply_markup=_home_kb(uid, player))


async def cb_land_abandon(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    ok, msg = ls.abandon_land(uid, player)
    if ok:
        await asave_player(uid, player)
        log_sync(f"🗺 **LAND ABANDON**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "HOUSE")
    await cb.answer(msg, show_alert=True)
    await cb.message.edit_text("🗺 **زمین**\n\n" + ls.land_summary_text(uid), reply_markup=_home_kb(uid, player))


async def cb_land_collect(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    ok, msg = ls.collect_rent_income(uid)
    if ok:
        log_sync(f"💰 **LAND RENT COLLECT**\n👤 (`{uid}`)\n{msg}", "HOUSE")
    await cb.answer(msg, show_alert=True)
    player = await aget_player(uid)
    await cb.message.edit_text("🗺 **زمین**\n\n" + ls.land_summary_text(uid), reply_markup=_home_kb(uid, player))


# ─── فروش رو بازار ───────────────────────────────────────────────
async def cb_land_list(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    await cb.answer()
    await cb.message.edit_text(
        "🏷️ برای گذاشتنِ زمینت رو بازار، این دستور رو بزن:\n`/landsell <قیمت>`\nمثال: `/landsell 15000`",
    )


async def cmd_landsell(msg: Message):
    uid = msg.from_user.id
    parts = msg.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await msg.answer("❌ فرمت درست: `/landsell <قیمت>`\nمثال: `/landsell 15000`")
        return
    ok, m = ls.list_for_sale(uid, int(parts[1]))
    await msg.answer(m)
    if ok:
        log_sync(f"🏷️ **LAND LISTED**\n👤 (`{uid}`)\n{m}", "HOUSE")


async def cb_land_unlist(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    ok, msg = ls.cancel_listing(uid)
    await cb.answer(msg, show_alert=True)
    player = await aget_player(uid)
    await cb.message.edit_text("🗺 **زمین**\n\n" + ls.land_summary_text(uid), reply_markup=_home_kb(uid, player))


def _market_kb(uid: int, listings: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for doc in listings:
        size = ls.size_data(doc["size"])
        label = f"{doc['map']} #{doc['plot_id']+1} — {size['name']} — {doc['listed_price']:,} Zen"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"land_buylisted:{uid}:{doc['map']}:{doc['plot_id']}", style=ButtonStyle.SUCCESS)])
    if not rows:
        rows.append([InlineKeyboardButton(text="— فعلاً چیزی رو بازار نیست —", callback_data="atk:locked", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data=f"land_home:{uid}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_land_market(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    listings = ls.list_for_sale_all()
    await cb.answer()
    await cb.message.edit_text("🏷️ **زمین‌های رو بازارِ فروش**", reply_markup=_market_kb(uid, listings))


async def cb_land_buylisted(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid = int(parts[1])
    map_name = parts[2]
    plot_id = int(parts[3])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    ok, msg = ls.buy_listed_land(uid, player, map_name, plot_id)
    if ok:
        await asave_player(uid, player)
        log_sync(f"🗺 **LAND SOLD**\n👤 خریدار: {player.get('name','—')} (`{uid}`)\n{msg}", "HOUSE")
    await cb.answer(msg, show_alert=True)
    await cb.message.edit_text("🗺 **زمین**\n\n" + ls.land_summary_text(uid), reply_markup=_home_kb(uid, player))


# ─── اجاره‌دادن ──────────────────────────────────────────────────
async def cb_land_setrent(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    await cb.answer()
    await cb.message.edit_text(
        "🔑 برای تنظیمِ قیمتِ اجاره‌ی روزانه‌ی زمینت، این دستور رو بزن:\n`/landrent <قیمت روزانه>`\nمثال: `/landrent 500`",
    )


async def cmd_landrent(msg: Message):
    uid = msg.from_user.id
    parts = msg.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await msg.answer("❌ فرمت درست: `/landrent <قیمت روزانه>`\nمثال: `/landrent 500`")
        return
    ok, m = ls.set_rent_price(uid, int(parts[1]))
    await msg.answer(m)
    if ok:
        log_sync(f"🔑 **LAND RENT SET**\n👤 (`{uid}`)\n{m}", "HOUSE")


async def cmd_rentland(msg: Message):
    """بازیکنِ دیگه با /rentland <نقشه> <شماره پلاک از ۱> یه زمینِ اجاره‌ای رو کرایه می‌کنه."""
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    parts = msg.text.split(maxsplit=2)
    if len(parts) < 3 or not parts[2].split()[-1].isdigit():
        await msg.answer("❌ فرمت درست: `/rentland <نامِ نقشه> <شماره پلاک>`\nمثال: `/rentland Verdant Vale 3`")
        return
    rest = parts[1] + " " + parts[2]
    map_part, _, plot_part = rest.rpartition(" ")
    if not plot_part.isdigit():
        await msg.answer("❌ فرمت درست: `/rentland <نامِ نقشه> <شماره پلاک>`")
        return
    plot_id = int(plot_part) - 1
    ok, m = ls.rent_land(uid, player, map_part.strip(), plot_id)
    if ok:
        await asave_player(uid, player)
        log_sync(f"🔑 **LAND RENTED**\n👤 مستأجر: {player.get('name','—')} (`{uid}`)\n{m}", "HOUSE")
    await msg.answer(m)


def register_land_handlers(dp, bot):
    dp.message.register(cmd_land, Command("land"))
    dp.message.register(cmd_landsell, Command("landsell"))
    dp.message.register(cmd_landrent, Command("landrent"))
    dp.message.register(cmd_rentland, Command("rentland"))
    dp.callback_query.register(cb_land_home,       F.data.startswith("land_home:"))
    dp.callback_query.register(cb_land_map,        F.data.startswith("land_map:"))
    dp.callback_query.register(cb_land_buy,        F.data.startswith("land_buy:"))
    dp.callback_query.register(cb_land_expand,     F.data.startswith("land_expand:"))
    dp.callback_query.register(cb_land_abandon,    F.data.startswith("land_abandon:"))
    dp.callback_query.register(cb_land_collect,    F.data.startswith("land_collect:"))
    dp.callback_query.register(cb_land_list,       F.data.startswith("land_list:"))
    dp.callback_query.register(cb_land_unlist,     F.data.startswith("land_unlist:"))
    dp.callback_query.register(cb_land_market,     F.data.startswith("land_market:"))
    dp.callback_query.register(cb_land_buylisted,  F.data.startswith("land_buylisted:"))
    dp.callback_query.register(cb_land_setrent,    F.data.startswith("land_setrent:"))
