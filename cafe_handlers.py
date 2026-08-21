# ============================================================
#  ASTRAL ABYSS RPG — Isekai Cafe Handlers (Telegram UI) ☕
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from action_lock import no_double_tap
import isekai_cafe as cafe


def _main_kb(player: dict) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🙋 پذیرایی از مهمون", callback_data="cafe_serve", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="📋 منو", callback_data="cafe_menu", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text=f"⬆️ ارتقای کافه ({cafe.upgrade_cost(player):,} Zen)", callback_data="cafe_upgrade", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="💰 برداشتِ خزانه", callback_data="cafe_withdraw", style=ButtonStyle.SUCCESS)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cmd_cafe(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player or not player.get("class"):
        await msg.answer("❌ اول باید کاراکترت رو بسازی: /start")
        return
    await msg.answer(cafe.status_text(player), reply_markup=_main_kb(player))


@no_double_tap()
async def cb_cafe_serve(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    ok, text = cafe.serve_guest(player)
    if ok:
        await asave_player(uid, player)
    await cb.answer(text, show_alert=True)
    if ok:
        await cb.message.edit_text(cafe.status_text(player), reply_markup=_main_kb(player))


async def cb_cafe_menu(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    c = player.get("cafe", {})
    rows = []
    for iid, item in cafe.MENU_ITEMS.items():
        tag = " ✅" if iid in c.get("menu", []) else f" — {item['cost']:,}Z"
        rows.append([InlineKeyboardButton(text=f"{item['name']}{tag}", callback_data=f"cafe_unlock:{iid}", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data="cafe_back", style=ButtonStyle.PRIMARY)])
    await cb.answer()
    await cb.message.edit_text("📋 **منوی کافه**", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@no_double_tap()
async def cb_cafe_unlock(cb: CallbackQuery):
    uid = cb.from_user.id
    item_id = cb.data.split(":")[1]
    player = await aget_player(uid)
    ok, text = cafe.unlock_menu_item(player, item_id)
    if ok:
        await asave_player(uid, player)
    await cb.answer(text, show_alert=not ok)
    await cb_cafe_menu(cb)


@no_double_tap()
async def cb_cafe_upgrade(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    ok, text = cafe.upgrade_cafe(player)
    if ok:
        await asave_player(uid, player)
    await cb.answer(text, show_alert=True)
    if ok:
        await cb.message.edit_text(cafe.status_text(player), reply_markup=_main_kb(player))


@no_double_tap()
async def cb_cafe_withdraw(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    collected = cafe.collect_income(player)
    c = player["cafe"]
    withdrawn = c["treasury"]
    player["zen"] = player.get("zen", 0) + withdrawn
    c["treasury"] = 0
    await asave_player(uid, player)
    await cb.answer(f"💰 {withdrawn:,} Zen برداشت شد." if withdrawn else "❌ خزانه خالیه.", show_alert=True)
    await cb.message.edit_text(cafe.status_text(player), reply_markup=_main_kb(player))


async def cb_cafe_back(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    await cb.answer()
    await cb.message.edit_text(cafe.status_text(player), reply_markup=_main_kb(player))


def register_cafe_handlers(dp, bot):
    dp.message.register(cmd_cafe, Command("cafe"))
    dp.callback_query.register(cb_cafe_serve, F.data == "cafe_serve")
    dp.callback_query.register(cb_cafe_menu, F.data == "cafe_menu")
    dp.callback_query.register(cb_cafe_unlock, F.data.startswith("cafe_unlock:"))
    dp.callback_query.register(cb_cafe_upgrade, F.data == "cafe_upgrade")
    dp.callback_query.register(cb_cafe_withdraw, F.data == "cafe_withdraw")
    dp.callback_query.register(cb_cafe_back, F.data == "cafe_back")
