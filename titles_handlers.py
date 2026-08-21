# ============================================================
#  ASTRAL ABYSS RPG — Handlers صفحه‌ی یکپارچه‌ی عنوان‌ها 🏅
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
import titles_system as ts


def _build_titles_view(player: dict):
    available = ts.collect_titles(player)
    active = ts.get_active_title(player)
    if not available:
        text = (
            "🏅 **عنوان‌های تو**\n\n"
            "هنوز هیچ عنوانی باز نکردی. دستاورد بگیر، تو گیلد لقب بخر، "
            "یه نمسیس رو شکار کن یا یه نقشه رو ۱۰۰٪ اکتشاف کن!"
        )
        return text, None

    lines = ["🏅 **عنوان‌های تو**\n_روی شماره بزن تا همون رو رو پروفایلت نشون بدی._\n"]
    buttons = []
    row = []
    for i, t in enumerate(available, start=1):
        mark = "✅ " if t["title"] == active else ""
        lines.append(f"{mark}{i}. {t['title']} — _{t['source']}_")
        row.append(InlineKeyboardButton(text=str(i), callback_data=f"title_set:{i-1}"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔁 حالتِ خودکار", callback_data="title_auto", style=ButtonStyle.PRIMARY)])

    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)


async def cmd_titles(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    text, kb = _build_titles_view(player)
    await msg.answer(text, reply_markup=kb)


async def cb_title_set(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    idx = int(cb.data.split(":")[1])
    available = ts.collect_titles(player)
    if idx < 0 or idx >= len(available):
        await cb.answer("❌ این عنوان دیگه در دسترس نیست، لیست رو رفرش کن.", show_alert=True)
        return
    title = available[idx]["title"]
    ts.set_active_title(player, title)
    await asave_player(uid, player)
    text, kb = _build_titles_view(player)
    await cb.answer(f"✅ عنوانِ فعال: {title}")
    await cb.message.edit_text(text, reply_markup=kb)


async def cb_title_auto(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    ts.clear_active_title(player)
    await asave_player(uid, player)
    text, kb = _build_titles_view(player)
    await cb.answer("🔁 برگشت به حالتِ خودکار.")
    await cb.message.edit_text(text, reply_markup=kb)


def register_titles_handlers(dp, bot):
    dp.message.register(cmd_titles, Command("titles"))
    dp.callback_query.register(cb_title_set, F.data.startswith("title_set:"))
    dp.callback_query.register(cb_title_auto, F.data == "title_auto")
