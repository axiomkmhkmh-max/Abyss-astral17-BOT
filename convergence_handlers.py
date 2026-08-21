# ============================================================
#  ASTRAL ABYSS RPG — Convergence Event Handlers (Telegram UI) 🌌
# ============================================================
from aiogram import F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from action_lock import no_double_tap
import convergence_system as cv


class ConvergenceStates(StatesGroup):
    waiting_zen_amount = State()
    waiting_shard_amount = State()


def _kb(active: bool) -> InlineKeyboardMarkup:
    if not active:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="conv_refresh")],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 تقدیمِ Zen", callback_data="conv_give_zen")],
        [InlineKeyboardButton(text="🔹 تقدیمِ Echo Shard", callback_data="conv_give_shard")],
        [InlineKeyboardButton(text="🏆 برترین مشارکت‌کننده‌ها", callback_data="conv_top")],
        [InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="conv_refresh")],
    ])


async def cmd_convergence(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    state = cv.get_state()
    await msg.answer(cv.status_text(player), reply_markup=_kb(state.get("active", False)))


async def cb_conv_refresh(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    state = cv.get_state()
    await cb.answer()
    await cb.message.edit_text(cv.status_text(player), reply_markup=_kb(state.get("active", False)))


async def cb_conv_top(cb: CallbackQuery):
    from database import get_player as gp
    top = cv.get_top_contributors(10)
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    lines = ["🏆 **برترین مشارکت‌کننده‌های رخدادِ هم‌گرایی:**\n"]
    for i, (uid_str, units) in enumerate(top):
        p = gp(int(uid_str))
        name = p.get("name", "—") if p else "—"
        lines.append(f"{medals[i]} **{name}** — {units:,} واحد")
    if not top:
        lines.append("هنوز کسی مشارکت نکرده — اولین نفر باش!")
    await cb.answer()
    await cb.message.answer("\n".join(lines))


async def cb_conv_give_zen(cb: CallbackQuery, state: FSMContext):
    if not cv.is_active():
        await cb.answer("❌ الان رخدادِ فعالی نیست.", show_alert=True)
        return
    await cb.answer()
    await cb.message.answer("💰 چقدر Zen می‌خوای تقدیم کنی؟ (فقط عدد بفرست)")
    await state.set_state(ConvergenceStates.waiting_zen_amount)


async def cb_conv_give_shard(cb: CallbackQuery, state: FSMContext):
    if not cv.is_active():
        await cb.answer("❌ الان رخدادِ فعالی نیست.", show_alert=True)
        return
    await cb.answer()
    await cb.message.answer("🔹 چند Echo Shard می‌خوای تقدیم کنی؟ (فقط عدد بفرست)")
    await state.set_state(ConvergenceStates.waiting_shard_amount)


async def _do_contribute(msg: Message, state: FSMContext, kind: str):
    uid = msg.from_user.id
    txt = (msg.text or "").strip()
    if not txt.isdigit():
        await msg.answer("❌ فقط عدد بفرست.")
        return
    amount = int(txt)
    player = await aget_player(uid)
    result = cv.contribute(uid, player, kind, amount)
    if not result["ok"]:
        await msg.answer(result["message"])
        return
    await asave_player(uid, player)
    await state.clear()

    unit_label = "Zen" if kind == "zen" else "🔹 Echo Shard"
    text = (
        f"✅ {amount:,} {unit_label} تقدیم شد! (+{result['units']:,} واحدِ رخداد)\n\n"
        f"{cv.progress_bar(cv.get_state())} {result['pct']}٪"
    )
    await msg.answer(text)

    if result["milestones_crossed"]:
        bot = msg.bot
        await cv._broadcast_milestone(bot, cv.get_state(), result["milestones_crossed"][-1])

    if result["completed"]:
        bot = msg.bot
        await cv.close_event(bot, partial=False)


async def msg_conv_zen_amount(msg: Message, state: FSMContext):
    await _do_contribute(msg, state, "zen")


async def msg_conv_shard_amount(msg: Message, state: FSMContext):
    await _do_contribute(msg, state, "shard")


def register_convergence_handlers(dp, bot):
    dp.message.register(cmd_convergence, Command("convergence"))
    dp.callback_query.register(cb_conv_refresh, F.data == "conv_refresh")
    dp.callback_query.register(cb_conv_top, F.data == "conv_top")
    dp.callback_query.register(cb_conv_give_zen, F.data == "conv_give_zen")
    dp.callback_query.register(cb_conv_give_shard, F.data == "conv_give_shard")
    dp.message.register(msg_conv_zen_amount, ConvergenceStates.waiting_zen_amount)
    dp.message.register(msg_conv_shard_amount, ConvergenceStates.waiting_shard_amount)
