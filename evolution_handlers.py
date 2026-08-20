# ============================================================
#  ASTRAL ABYSS RPG — Evolution Handlers (Telegram UI) 🧬
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
from action_lock import no_double_tap
import evolution_system as es


def _pending_kb(player: dict) -> InlineKeyboardMarkup | None:
    stage = es.pending_stage(player)
    if not stage:
        return None
    rows = []
    for branch_id, branch in stage["branches"].items():
        rows.append([InlineKeyboardButton(
            text=f"{branch['name']}", callback_data=f"evo_pick:{branch_id}", style=ButtonStyle.SUCCESS,
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cmd_evolve(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    if not player.get("class"):
        await msg.answer("❌ اول باید کاراکترت رو بسازی.")
        return

    stage = es.pending_stage(player)
    if stage:
        text = (
            f"🧬 **{stage['title']}**\n"
            f"_{stage['flavor']}_\n\n"
            "یه مسیر رو انتخاب کن — این تصمیم دائمیه:\n\n"
        )
        for branch in stage["branches"].values():
            text += f"**{branch['name']}**\n_{branch['flavor']}_\n\n"
        await msg.answer(text, reply_markup=_pending_kb(player))
    else:
        await msg.answer(es.status_text(player))


@no_double_tap()
async def cb_evo_pick(cb: CallbackQuery):
    uid = cb.from_user.id
    branch_id = cb.data.split(":", 1)[1]
    player = get_player(uid)
    ok, text = es.apply_evolution(player, branch_id)
    if ok:
        save_player(uid, player)
    await cb.answer("🧬 تکامل انجام شد!" if ok else text, show_alert=not ok)
    try:
        await cb.message.edit_text(text, reply_markup=None)
    except Exception:
        pass


def register_evolution_handlers(dp, bot):
    dp.message.register(cmd_evolve, Command("evolve"))
    dp.callback_query.register(cb_evo_pick, F.data.startswith("evo_pick:"))
