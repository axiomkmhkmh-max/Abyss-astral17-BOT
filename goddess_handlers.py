# ============================================================
#  ASTRAL ABYSS RPG — Goddess Handlers (Telegram UI) 🕊
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
from action_lock import no_double_tap
import goddess_system as gs


def _kb(player: dict) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="🙏 دعا کن", callback_data="goddess_pray", style=ButtonStyle.PRIMARY)]]
    if gs.can_claim_cheat_skill(player):
        rows.append([InlineKeyboardButton(text="⚡ درخواستِ چیت‌اسکیل", callback_data="goddess_cheat_menu", style=ButtonStyle.SUCCESS)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _panel_text(player: dict) -> str:
    tier_name, flavor = gs.favor_tier(player)
    next_name, gap = gs.next_tier_gap(player)
    dialogue = gs.get_dialogue(player)
    lines = [
        "🕊 **الهه‌ی آغازها**\n",
        f"«{dialogue}»\n",
        f"لطف: {tier_name} ({player.get('goddess_favor',0):,})",
    ]
    if next_name:
        lines.append(f"   ↳ {gap:,} تا {next_name}")
    if player.get("goddess_cheat_skill"):
        skill = gs.CHEAT_SKILLS.get(player["goddess_cheat_skill"])
        if skill:
            lines.append(f"\n⚡ چیت‌اسکیل: {skill['name']}")
    return "\n".join(lines)


async def cmd_goddess(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    await msg.answer(_panel_text(player), reply_markup=_kb(player))


@no_double_tap()
async def cb_goddess_pray(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    result = gs.pray(player)
    if result["ok"]:
        save_player(uid, player)
    await cb.answer(result["message"], show_alert=True)
    await cb.message.edit_text(_panel_text(player), reply_markup=_kb(player))


async def cb_goddess_cheat_menu(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    if not gs.can_claim_cheat_skill(player):
        await cb.answer("❌ قبلاً یکی گرفتی.", show_alert=True)
        return
    rows = []
    for sid, s in gs.CHEAT_SKILLS.items():
        rows.append([InlineKeyboardButton(text=f"{s['name']} — {s['desc']}", callback_data=f"goddess_claim:{sid}")])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data="goddess_back")])
    await cb.answer()
    await cb.message.edit_text(
        "⚡ **انتخابِ چیت‌اسکیل** (فقط یه‌بار، برای همیشه):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )


@no_double_tap()
async def cb_goddess_claim(cb: CallbackQuery):
    uid = cb.from_user.id
    skill_id = cb.data.split(":")[1]
    player = get_player(uid)
    ok, text = gs.claim_cheat_skill(player, skill_id)
    if ok:
        save_player(uid, player)
    await cb.answer("✅ گرفته شد!" if ok else text, show_alert=True)
    await cb.message.edit_text(_panel_text(player), reply_markup=_kb(player))


async def cb_goddess_back(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    await cb.answer()
    await cb.message.edit_text(_panel_text(player), reply_markup=_kb(player))


def register_goddess_handlers(dp, bot):
    dp.message.register(cmd_goddess, Command("goddess"))
    dp.callback_query.register(cb_goddess_pray, F.data == "goddess_pray")
    dp.callback_query.register(cb_goddess_cheat_menu, F.data == "goddess_cheat_menu")
    dp.callback_query.register(cb_goddess_claim, F.data.startswith("goddess_claim:"))
    dp.callback_query.register(cb_goddess_back, F.data == "goddess_back")
