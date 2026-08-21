# ============================================================
#  ASTRAL ABYSS RPG — Dungeon Core Handlers (Telegram UI) 🏰
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, all_players, asave_player, aget_player
from action_lock import no_double_tap
import dungeon_core_system as dcs


def _main_kb(player: dict) -> InlineKeyboardMarkup:
    core = dcs.get_or_init_core(player)
    rows = [
        [InlineKeyboardButton(text="🕳 چیدنِ تله", callback_data="dcore_traps", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="👹 استخدامِ نگهبان", callback_data="dcore_monsters", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text=f"⚒️ تقویتِ هسته ({dcs.reinforce_cost(player):,} Zen)", callback_data="dcore_reinforce", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="💰 برداشتِ خزانه", callback_data="dcore_withdraw", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="🗡 راید به یه سیاه‌چالِ دیگه", callback_data="dcore_raid", style=ButtonStyle.DANGER)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cmd_dungeon_core(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player or not player.get("class"):
        await msg.answer("❌ اول باید کاراکترت رو بسازی: /start")
        return
    await msg.answer(dcs.status_text(player), reply_markup=_main_kb(player))


async def cb_dcore_traps(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    core = dcs.get_or_init_core(player)
    rows = []
    for tid, t in dcs.TRAPS.items():
        if tid in core["traps"]:
            rows.append([InlineKeyboardButton(text=f"🗑 حذف: {t['name']}", callback_data=f"dcore_untrap:{tid}", style=ButtonStyle.DANGER)])
        else:
            rows.append([InlineKeyboardButton(text=f"{t['name']} — {t['cost']:,}Z (دفاع +{t['defense']})", callback_data=f"dcore_trap:{tid}", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data="dcore_back", style=ButtonStyle.PRIMARY)])
    await cb.answer()
    await cb.message.edit_text(f"🕳 **تله‌ها** ({len(core['traps'])}/{dcs.MAX_TRAP_SLOTS} اسلات)", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@no_double_tap()
async def cb_dcore_trap_buy(cb: CallbackQuery):
    uid = cb.from_user.id
    trap_id = cb.data.split(":")[1]
    player = await aget_player(uid)
    ok, text = dcs.build_trap(player, trap_id)
    if ok:
        await asave_player(uid, player)
    await cb.answer(text, show_alert=not ok)
    await cb_dcore_traps(cb)


@no_double_tap()
async def cb_dcore_trap_remove(cb: CallbackQuery):
    uid = cb.from_user.id
    trap_id = cb.data.split(":")[1]
    player = await aget_player(uid)
    ok, text = dcs.remove_trap(player, trap_id)
    if ok:
        await asave_player(uid, player)
    await cb.answer(text, show_alert=not ok)
    await cb_dcore_traps(cb)


async def cb_dcore_monsters(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    core = dcs.get_or_init_core(player)
    rows = []
    for mid, m in dcs.MONSTERS.items():
        tag = " ✅ (فعلی)" if core.get("monster") == mid else ""
        rows.append([InlineKeyboardButton(text=f"{m['name']} — {m['cost']:,}Z (دفاع +{m['defense']}){tag}", callback_data=f"dcore_hire:{mid}", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data="dcore_back", style=ButtonStyle.PRIMARY)])
    await cb.answer()
    await cb.message.edit_text("👹 **نگهبان‌ها** — فقط یکی می‌تونه فعال باشه", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@no_double_tap()
async def cb_dcore_hire(cb: CallbackQuery):
    uid = cb.from_user.id
    monster_id = cb.data.split(":")[1]
    player = await aget_player(uid)
    ok, text = dcs.hire_monster(player, monster_id)
    if ok:
        await asave_player(uid, player)
    await cb.answer(text, show_alert=not ok)
    await cb_dcore_monsters(cb)


@no_double_tap()
async def cb_dcore_reinforce(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    ok, text = dcs.reinforce_core(player)
    if ok:
        await asave_player(uid, player)
    await cb.answer(text, show_alert=True)
    if ok:
        await cb.message.edit_text(dcs.status_text(player), reply_markup=_main_kb(player))


@no_double_tap()
async def cb_dcore_withdraw(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    ok, text = dcs.withdraw_treasury(player)
    await asave_player(uid, player)
    await cb.answer(text, show_alert=True)
    await cb.message.edit_text(dcs.status_text(player), reply_markup=_main_kb(player))


@no_double_tap()
async def cb_dcore_raid(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    ok, remaining = dcs.can_raid(player)
    if not ok:
        hrs = remaining // 3600
        mins = (remaining % 3600) // 60
        await cb.answer(f"⏳ سیاه‌چالت هنوز خسته‌ست — {hrs} ساعت و {mins} دقیقه‌ی دیگه دوباره بیا.", show_alert=True)
        return

    target = dcs.pick_raid_target(all_players(), uid)
    if not target:
        await cb.answer("❌ الان هیچ سیاه‌چالِ دیگه‌ای برای راید پیدا نشد.", show_alert=True)
        return

    target_uid, defender = target
    result = dcs.resolve_raid(player, defender)
    await asave_player(uid, player)
    await asave_player(int(target_uid), defender)

    await cb.answer("⚔️ راید انجام شد!")
    await cb.message.edit_text(f"{result['msg']}\n\n📊 Combat Power: {result['attacker_cp']:,} در برابرِ دفاعِ {result['defense_power']:,}", reply_markup=None)


async def cb_dcore_back(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    await cb.answer()
    await cb.message.edit_text(dcs.status_text(player), reply_markup=_main_kb(player))


def register_dungeon_core_handlers(dp, bot):
    dp.message.register(cmd_dungeon_core, Command("dungeoncore"))
    dp.callback_query.register(cb_dcore_traps, F.data == "dcore_traps")
    dp.callback_query.register(cb_dcore_trap_buy, F.data.startswith("dcore_trap:"))
    dp.callback_query.register(cb_dcore_trap_remove, F.data.startswith("dcore_untrap:"))
    dp.callback_query.register(cb_dcore_monsters, F.data == "dcore_monsters")
    dp.callback_query.register(cb_dcore_hire, F.data.startswith("dcore_hire:"))
    dp.callback_query.register(cb_dcore_reinforce, F.data == "dcore_reinforce")
    dp.callback_query.register(cb_dcore_withdraw, F.data == "dcore_withdraw")
    dp.callback_query.register(cb_dcore_raid, F.data == "dcore_raid")
    dp.callback_query.register(cb_dcore_back, F.data == "dcore_back")
