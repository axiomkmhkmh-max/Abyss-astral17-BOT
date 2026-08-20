# ============================================================
#  ASTRAL ABYSS RPG — Academy Handlers (Telegram UI) 🎓
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, all_players
from action_lock import no_double_tap
import academy_system as acs


def _main_kb(player: dict) -> InlineKeyboardMarkup:
    a = player.get("academy", {})
    rows = []
    if not a.get("enrolled"):
        rows.append([InlineKeyboardButton(text="📝 ثبت‌نام", callback_data="academy_enroll", style=ButtonStyle.SUCCESS)])
    elif not a.get("graduated"):
        for sid, s in acs.SUBJECTS.items():
            rows.append([InlineKeyboardButton(text=f"سرِ کلاس: {s['name']}", callback_data=f"academy_class:{sid}", style=ButtonStyle.PRIMARY)])
        rows.append([InlineKeyboardButton(text="📝 امتحان بده", callback_data="academy_exam", style=ButtonStyle.SUCCESS)])
    rows.append([InlineKeyboardButton(text="🏆 رتبه‌بندیِ دانش‌آموزان", callback_data="academy_ranking", style=ButtonStyle.SECONDARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cmd_academy(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player or not player.get("class"):
        await msg.answer("❌ اول باید کاراکترت رو بسازی: /start")
        return
    await msg.answer(acs.status_text(player), reply_markup=_main_kb(player))


@no_double_tap()
async def cb_academy_enroll(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    ok, text = acs.enroll(player)
    if ok:
        save_player(uid, player)
    await cb.answer(text if not ok else "🎓 ثبت‌نام شد!", show_alert=not ok)
    if ok:
        await cb.message.edit_text(text + "\n\n" + acs.status_text(player), reply_markup=_main_kb(player))


@no_double_tap()
async def cb_academy_class(cb: CallbackQuery):
    uid = cb.from_user.id
    subject_id = cb.data.split(":")[1]
    player = get_player(uid)
    ok, text = acs.attend_class(player, subject_id)
    if ok:
        save_player(uid, player)
    await cb.answer(text, show_alert=True)
    if ok:
        await cb.message.edit_text(acs.status_text(player), reply_markup=_main_kb(player))


@no_double_tap()
async def cb_academy_exam(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    ok, text = acs.take_exam(player)
    save_player(uid, player)
    await cb.answer("📝 نتیجه اومد!" if ok else text, show_alert=not ok)
    await cb.message.edit_text(text + "\n\n" + acs.status_text(player), reply_markup=_main_kb(player))


async def cb_academy_ranking(cb: CallbackQuery):
    top = acs.top_students(all_players(), limit=10)
    lines = ["🏆 **رتبه‌بندیِ دانش‌آموزانِ آکادمی**\n"]
    if not top:
        lines.append("هنوز هیچ‌کس ثبت‌نام نکرده.")
    else:
        for i, (uid, p) in enumerate(top, start=1):
            a = p.get("academy", {})
            tag = " 🎓" if a.get("graduated") else f" (سالِ {a.get('year',1)})"
            lines.append(f"{i}. {p.get('name','—')}{tag} — {a.get('academy_points',0):,} امتیاز")
    await cb.answer()
    await cb.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ برگشت", callback_data="academy_back", style=ButtonStyle.SECONDARY)
    ]]))


async def cb_academy_back(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    await cb.answer()
    await cb.message.edit_text(acs.status_text(player), reply_markup=_main_kb(player))


def register_academy_handlers(dp, bot):
    dp.message.register(cmd_academy, Command("academy"))
    dp.callback_query.register(cb_academy_enroll, F.data == "academy_enroll")
    dp.callback_query.register(cb_academy_class, F.data.startswith("academy_class:"))
    dp.callback_query.register(cb_academy_exam, F.data == "academy_exam")
    dp.callback_query.register(cb_academy_ranking, F.data == "academy_ranking")
    dp.callback_query.register(cb_academy_back, F.data == "academy_back")
