# ============================================================
#  ASTRAL ABYSS RPG — Villainess Arc Handlers (Telegram UI) 🌹
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
from action_lock import no_double_tap
import villainess_arc as va


def _main_kb(player: dict) -> InlineKeyboardMarkup:
    a = player.get("villainess_arc", {})
    rows = []
    if not a.get("active") and not a.get("escaped"):
        rows.append([InlineKeyboardButton(text="🌹 وارد این مسیر شو", callback_data="villainess_start", style=ButtonStyle.SUCCESS)])
    elif a.get("active") and not a.get("escaped"):
        for aid, action in va.ESCAPE_ACTIONS.items():
            rows.append([InlineKeyboardButton(text=action["name"], callback_data=f"villainess_act:{aid}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cmd_villainess(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player or not player.get("class"):
        await msg.answer("❌ اول باید کاراکترت رو بسازی: /start")
        return
    await msg.answer(va.status_text(player), reply_markup=_main_kb(player))


@no_double_tap()
async def cb_villainess_start(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    ok, text = va.start_arc(player)
    if ok:
        save_player(uid, player)
    await cb.answer(text if not ok else "🌹 وارد شدی!", show_alert=not ok)
    if ok:
        await cb.message.edit_text(text, reply_markup=_main_kb(player))


@no_double_tap()
async def cb_villainess_act(cb: CallbackQuery):
    uid = cb.from_user.id
    action_id = cb.data.split(":")[1]
    player = get_player(uid)
    ok, text = va.perform_action(player, action_id)
    if ok:
        save_player(uid, player)
    await cb.answer(text, show_alert=True)
    if ok:
        await cb.message.edit_text(va.status_text(player), reply_markup=_main_kb(player))


def register_villainess_handlers(dp, bot):
    dp.message.register(cmd_villainess, Command("villainess"))
    dp.callback_query.register(cb_villainess_start, F.data == "villainess_start")
    dp.callback_query.register(cb_villainess_act, F.data.startswith("villainess_act:"))
