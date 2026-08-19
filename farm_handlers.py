# ============================================================
#  ASTRAL ABYSS RPG — Farm Handlers (Telegram UI)  — v1
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
from logger import log_sync
import farm_system as fs


def _owner_ok(cb: CallbackQuery, uid: int) -> bool:
    return cb.from_user.id == uid


def _farm_kb(uid: int) -> InlineKeyboardMarkup:
    crops = fs.farm_status(uid)
    barn = fs.barn_status(uid)
    rows = []
    for c in crops:
        crop = fs.CROPS[c["crop"]]
        if c["state"] == "ready":
            rows.append([InlineKeyboardButton(text=f"🌾 برداشتِ {crop['name']} ({c['quality_label']})",
                        callback_data=f"farm_harvest:{uid}:{c['idx']}", style=ButtonStyle.SUCCESS)])
        elif c["state"] == "spoiled":
            rows.append([InlineKeyboardButton(text=f"🥀 پاک‌کردنِ {crop['name']} پوسیده",
                        callback_data=f"farm_harvest:{uid}:{c['idx']}", style=ButtonStyle.DANGER)])
    for a in barn:
        animal = fs.LIVESTOCK[a["animal"]]
        if a["cycles_ready"] > 0:
            rows.append([InlineKeyboardButton(text=f"📦 برداشتِ {animal['name']}",
                        callback_data=f"farm_collect:{uid}:{a['idx']}", style=ButtonStyle.SUCCESS)])
        rows.append([InlineKeyboardButton(text=f"🍽 تغذیه‌ی {animal['name']} (شادی {a['happiness']})",
                    callback_data=f"farm_feed:{uid}:{a['idx']}", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="🌱 کاشتنِ محصول", callback_data=f"farm_plant_menu:{uid}", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="🐄 خریدِ دام", callback_data=f"farm_buy_menu:{uid}", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="🍲 آشپزخانه", callback_data=f"cook_home:{uid}", style=ButtonStyle.SUCCESS)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cmd_farm(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    await msg.answer("🌾 **مزرعه**\n\n" + fs.farm_summary_text(uid), reply_markup=_farm_kb(uid))


async def cb_farm_home(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    await cb.answer()
    await cb.message.edit_text("🌾 **مزرعه**\n\n" + fs.farm_summary_text(uid), reply_markup=_farm_kb(uid))


def _plant_menu_kb(uid: int) -> InlineKeyboardMarkup:
    rows = []
    for key, crop in fs.CROPS.items():
        rows.append([InlineKeyboardButton(
            text=f"{crop['name']} — {crop['seed_cost']:,} Zen ({crop['grow_seconds']//60}m)",
            callback_data=f"farm_plant:{uid}:{key}", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data=f"farm_home:{uid}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_farm_plant_menu(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    await cb.answer()
    await cb.message.edit_text("🌱 **کدوم بذر رو بکاریم؟**", reply_markup=_plant_menu_kb(uid))


async def cb_farm_plant(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid, crop_key = int(parts[1]), parts[2]
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    ok, msg = fs.plant_crop(uid, player, crop_key)
    if ok:
        save_player(uid, player)
        log_sync(f"🌱 **FARM PLANT**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "HOUSE")
    await cb.answer(msg, show_alert=True)
    await cb.message.edit_text("🌾 **مزرعه**\n\n" + fs.farm_summary_text(uid), reply_markup=_farm_kb(uid))


async def cb_farm_harvest(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid, slot_idx = int(parts[1]), int(parts[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    ok, msg = fs.harvest_crop(uid, player, slot_idx)
    save_player(uid, player)
    if ok:
        log_sync(f"🌾 **FARM HARVEST**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "HOUSE")
    await cb.answer(msg, show_alert=True)
    await cb.message.edit_text("🌾 **مزرعه**\n\n" + fs.farm_summary_text(uid), reply_markup=_farm_kb(uid))


def _buy_menu_kb(uid: int) -> InlineKeyboardMarkup:
    rows = []
    for key, animal in fs.LIVESTOCK.items():
        rows.append([InlineKeyboardButton(
            text=f"{animal['name']} — {animal['cost']:,} Zen",
            callback_data=f"farm_buy:{uid}:{key}", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data=f"farm_home:{uid}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_farm_buy_menu(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    await cb.answer()
    await cb.message.edit_text("🐄 **کدوم دام رو بخریم؟**", reply_markup=_buy_menu_kb(uid))


async def cb_farm_buy(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid, animal_key = int(parts[1]), parts[2]
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    ok, msg = fs.buy_animal(uid, player, animal_key)
    if ok:
        save_player(uid, player)
        log_sync(f"🐄 **FARM BUY ANIMAL**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "HOUSE")
    await cb.answer(msg, show_alert=True)
    await cb.message.edit_text("🌾 **مزرعه**\n\n" + fs.farm_summary_text(uid), reply_markup=_farm_kb(uid))


async def cb_farm_feed(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid, slot_idx = int(parts[1]), int(parts[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    ok, msg = fs.feed_animal(uid, player, slot_idx)
    if ok:
        save_player(uid, player)
        log_sync(f"🍽 **FARM FEED**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "HOUSE")
    await cb.answer(msg, show_alert=True)
    await cb.message.edit_text("🌾 **مزرعه**\n\n" + fs.farm_summary_text(uid), reply_markup=_farm_kb(uid))


async def cb_farm_collect(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid, slot_idx = int(parts[1]), int(parts[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    ok, msg = fs.collect_produce(uid, player, slot_idx)
    if ok:
        save_player(uid, player)
        log_sync(f"📦 **FARM COLLECT**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "HOUSE")
    await cb.answer(msg, show_alert=True)
    await cb.message.edit_text("🌾 **مزرعه**\n\n" + fs.farm_summary_text(uid), reply_markup=_farm_kb(uid))


async def cmd_sellanimal(msg: Message):
    uid = msg.from_user.id
    parts = msg.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await msg.answer("❌ فرمت درست: `/sellanimal <شماره>` (شماره رو از /farm ببین)")
        return
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    ok, m = fs.sell_animal(uid, player, int(parts[1]) - 1)
    if ok:
        save_player(uid, player)
    await msg.answer(m)


def register_farm_handlers(dp, bot):
    dp.message.register(cmd_farm, Command("farm"))
    dp.message.register(cmd_sellanimal, Command("sellanimal"))
    dp.callback_query.register(cb_farm_home,       F.data.startswith("farm_home:"))
    dp.callback_query.register(cb_farm_plant_menu, F.data.startswith("farm_plant_menu:"))
    dp.callback_query.register(cb_farm_plant,      F.data.startswith("farm_plant:"))
    dp.callback_query.register(cb_farm_harvest,    F.data.startswith("farm_harvest:"))
    dp.callback_query.register(cb_farm_buy_menu,   F.data.startswith("farm_buy_menu:"))
    dp.callback_query.register(cb_farm_buy,        F.data.startswith("farm_buy:"))
    dp.callback_query.register(cb_farm_feed,       F.data.startswith("farm_feed:"))
    dp.callback_query.register(cb_farm_collect,    F.data.startswith("farm_collect:"))
