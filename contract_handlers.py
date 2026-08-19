# ============================================================
#  ASTRAL ABYSS RPG — Contract Board Handlers (Telegram UI)
# ============================================================
import random
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
from logger import log_sync
import contract_system as cs


def _board_text_kb(player: dict):
    cs._prune_stale_active(player)  # 🐛 فیکس: قراردادهای قدیمیِ گیرکرده رو پاک کن
    doc = cs.get_board()
    active = player.get("active_contracts", {})
    lines = [
        "📜 **تابلوی کارگزار**\n",
        f"_{random.choice(cs.BROKER_LINES)}_\n",
    ]
    buttons = []
    for c in doc["contracts"]:
        slots_left = max(0, cs.MAX_FULL_CLAIMS - len(c["claims"]))
        lines.append(
            f"\n**{c['title']}**\n_{c['desc']}_\n"
            f"🎁 {c['reward_zen']:,} Zen | {c['reward_xp']} XP | 🏁 {slots_left}/{cs.MAX_FULL_CLAIMS} جایزه‌ی کامل مونده"
        )
        if c["id"] in active:
            buttons.append([InlineKeyboardButton(text=f"📦 تحویلِ «{c['title']}»", callback_data=f"contract_turnin:{c['id']}", style=ButtonStyle.PRIMARY)])
        else:
            buttons.append([InlineKeyboardButton(text=f"✅ قبول «{c['title']}»", callback_data=f"contract_accept:{c['id']}", style=ButtonStyle.SUCCESS)])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)


async def cmd_contracts(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    from level_gate import check_level
    ok, why = check_level(player, "contracts")
    if not ok:
        await msg.answer(why)
        return
    pruned = cs._prune_stale_active(player)
    if pruned:
        save_player(uid, player)
    text, kb = _board_text_kb(player)
    await msg.answer(text, reply_markup=kb)


async def cb_contract_accept(cb: CallbackQuery):
    contract_id = cb.data.split(":")[1]
    uid = cb.from_user.id
    player = get_player(uid)
    ok, msg = cs.accept_contract(player, contract_id)
    save_player(uid, player)  # حتی موقعِ رد شدن هم ممکنه pruneِ قراردادِ گیرکرده انجام شده باشه
    await cb.answer(msg, show_alert=True)
    text, kb = _board_text_kb(player)
    await cb.message.edit_text(text, reply_markup=kb)


async def cb_contract_turnin(cb: CallbackQuery):
    contract_id = cb.data.split(":")[1]
    uid = cb.from_user.id
    player = get_player(uid)
    ok, msg, info = cs.turn_in(player, contract_id)
    if ok:
        save_player(uid, player)
        tag = "🏆 جایزه‌ی کامل!" if info["full"] else "🥈 جایزه‌ی تسلی (ظرفیت پر شده بود)"
        log_sync(
            f"📜 **CONTRACT TURNED IN**\n👤 {player.get('name','—')} (`{uid}`)\n"
            f"📦 {info['title']} | {tag} | +{info['zen']:,} Zen +{info['xp']} XP",
            "CONTRACT"
        )
        await cb.answer(f"{tag}\n+{info['zen']:,} Zen | +{info['xp']} XP", show_alert=True)
    else:
        await cb.answer(msg, show_alert=True)
    text, kb = _board_text_kb(player)
    await cb.message.edit_text(text, reply_markup=kb)


def register_contract_handlers(dp, bot):
    dp.message.register(cmd_contracts, Command("contracts"))
    dp.callback_query.register(cb_contract_accept, F.data.startswith("contract_accept:"))
    dp.callback_query.register(cb_contract_turnin, F.data.startswith("contract_turnin:"))
