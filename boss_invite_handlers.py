# ============================================================
#  ASTRAL ABYSS — BOSS INVITE HANDLERS
# ------------------------------------------------------------
#  /binvite — یه بازیکنِ خاص رو به هر باسِ چندنفره‌ای که همین الان
#  فعاله دعوت می‌کنه (باسِ جهانی، باسِ همین گروه، یا باسِ منطقه‌ایِ
#  مپی که خودِ دعوت‌کننده توشه). طرفِ دعوت‌شده حتی اگه تو پی‌وی
#  خصوصیِ خودش باشه، با زدنِ «⚔️ بپیوند» مستقیم وارد همون نبرد
#  می‌شه و لوتش دقیقاً با همون فرمولِ رتبه‌ایِ boss_engine (سهم
#  متناسب با دمیج) حساب می‌شه — یعنی تقسیمِ لوت کاملاً عادلانه‌ست.
#
#  استفاده:
#   • تو گروه: رو پیامِ طرف ریپلای کن و /binvite بزن (یا /binvite @username)
#   • تو پی‌وی: /binvite @username  → اگه باسِ جهانی زنده باشه یا خودت
#     رو یه مپی باشی که باسِ منطقه‌ایش زنده‌ست، دعوت‌نامه براش می‌ره.
# ============================================================
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, all_players
from logger import log_sync

from boss_invite_system import (
    create_invite, pop_invite, get_boss_by_ref, boss_type_label,
)

NEED_START_MSG = "❌ اول /start بزن!"


def _resolve_target(msg: Message, uid: int) -> int | None:
    if msg.reply_to_message and msg.reply_to_message.from_user:
        return msg.reply_to_message.from_user.id
    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return None
    arg = parts[1].strip().lstrip("@").lower()
    if not arg:
        return None
    for pid, p in all_players().items():
        if (p.get("username") or "").lower() == arg:
            return int(pid)
    return None


def _find_active_boss_for_inviter(msg: Message, inviter: dict):
    """اولویت: باسِ همین گروه (اگه تو گروهیم) → باسِ جهانی → باسِ منطقه‌ایِ مپِ فعلیِ خودِ بازیکن."""
    if msg.chat.type != "private":
        from group_system import get_group_boss
        gboss = get_group_boss(msg.chat.id)
        if gboss and gboss.get("alive"):
            return "group", msg.chat.id, gboss

    from database import get_boss
    wboss = get_boss()
    if wboss.get("alive"):
        return "world", 0, wboss

    player_map = inviter.get("map")
    if player_map:
        from region_boss_system import get_region_boss
        rboss = get_region_boss(player_map)
        if rboss and rboss.get("alive"):
            return "region", player_map, rboss

    return None, None, None


async def cmd_binvite(msg: Message):
    uid = msg.from_user.id
    inviter = get_player(uid)
    if not inviter or not inviter.get("character"):
        await msg.answer(NEED_START_MSG)
        return

    target_id = _resolve_target(msg, uid)
    if not target_id:
        await msg.answer(
            "📝 استفاده:\n"
            "• رو پیامِ یه نفر ریپلای کن و `/binvite` بزن\n"
            "• یا بنویس `/binvite @username`"
        )
        return
    if target_id == uid:
        await msg.answer("❌ نمی‌تونی خودت رو دعوت کنی!")
        return

    target = get_player(target_id)
    if not target or not target.get("character"):
        await msg.answer("❌ این بازیکن هنوز /start نزده!")
        return

    boss_type, ref, boss = _find_active_boss_for_inviter(msg, inviter)
    if not boss:
        await msg.answer(
            "😴 الان هیچ باسِ زنده‌ای برای دعوت‌کردن پیدا نکردم "
            "(نه تو این گروه، نه باسِ جهانی، نه باسِ منطقه‌ایِ مپِ فعلیت)."
        )
        return

    create_invite(uid, target_id, boss_type, ref, boss.get("name", "باس"))

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⚔️ بپیوند به نبرد!", callback_data="binvacc", style=ButtonStyle.DANGER),
        InlineKeyboardButton(text="❌ رد کن", callback_data="binvdec", style=ButtonStyle.PRIMARY),
    ]])
    try:
        await msg.bot.send_message(
            target_id,
            f"📨 **{inviter.get('name','یه بازیکن')}** تو رو به یه باس‌فایتِ گروهی دعوت کرد!\n\n"
            f"👑 {boss.get('name','باس')} — {boss_type_label(boss_type)}\n"
            f"هرکی به این نبرد ملحق بشه، لوتش دقیقاً بر اساسِ دمیجی که می‌زنه (سهمِ عادلانه) حساب می‌شه.\n\n"
            f"⏰ این دعوت تا ۵ دقیقه‌ی دیگه معتبره.",
            reply_markup=kb,
        )
    except Exception:
        await msg.answer("❌ نتونستم برای این بازیکن پیام بفرستم (شاید هنوز تو پی‌وی ربات رو استارت نکرده).")
        return

    log_sync(
        f"📨 **BOSS INVITE**\n👤 از: `{uid}`\n🎯 به: `{target_id}`\n🏷️ نوع: {boss_type}",
        "BOSS_INVITE"
    )
    await msg.answer(f"📨 دعوت‌نامه برای **{target.get('name','بازیکن')}** فرستاده شد!")


# ─── قبول/ردِ دعوت ────────────────────────────────────────────────

async def cb_binvite_accept(cb: CallbackQuery):
    uid = cb.from_user.id
    invite = pop_invite(uid)
    if not invite:
        await cb.answer("⏰ این دعوت منقضی شده یا قبلاً جواب داده شده!", show_alert=True)
        return

    boss_type, ref = invite["boss_type"], invite["ref"]
    boss = get_boss_by_ref(boss_type, ref)
    if not boss or not boss.get("alive"):
        await cb.answer("😴 این باس دیگه زنده نیست!", show_alert=True)
        try:
            await cb.message.edit_text("😴 این باس دیگه زنده نیست — دعوت منقضی شد.")
        except Exception:
            pass
        return

    player = get_player(uid)
    if not player or not player.get("character"):
        await cb.answer(NEED_START_MSG, show_alert=True)
        return

    if boss_type == "world":
        import boss_engine as be
        text = be.build_status_text(boss)
        kb = be.build_attack_kb(boss)
        await cb.message.edit_text(f"⚔️ به باسِ جهانی ملحق شدی!\n\n{text}", reply_markup=kb)

    elif boss_type == "group":
        from group_system import get_group_boss, save_group_boss
        from group_handlers import _build_kb, _status_with_top
        gboss = get_group_boss(int(ref))
        if not gboss or not gboss.get("alive"):
            await cb.answer("😴 این باس دیگه زنده نیست!", show_alert=True)
            return
        gboss.setdefault("invited_uids", [])
        if uid not in gboss["invited_uids"]:
            gboss["invited_uids"].append(uid)
        save_group_boss(int(ref), gboss)
        text = _status_with_top(int(ref), gboss)
        kb = _build_kb(int(ref), gboss)
        await cb.message.edit_text(
            f"⚔️ به باسِ اون گروه ملحق شدی! از همینجا (پی‌وی خودت) می‌تونی بزنیش.\n\n{text}",
            reply_markup=kb,
        )

    elif boss_type == "region":
        from region_boss_handlers import build_region_kb, _status_with_top as _rb_status, _map_idx
        map_idx = _map_idx(str(ref))
        text = _rb_status(str(ref), boss)
        kb = build_region_kb(map_idx, boss)
        await cb.message.edit_text(f"⚔️ به باسِ منطقه‌ایِ {ref} ملحق شدی!\n\n{text}", reply_markup=kb)

    else:
        await cb.answer("❌ خطا!", show_alert=True)
        return

    await cb.answer("⚔️ وارد نبرد شدی!")

    try:
        await cb.message.bot.send_message(
            invite["from_uid"],
            f"✅ **{player.get('name','دوستت')}** دعوتت به {boss_type_label(boss_type)} رو قبول کرد و ملحق شد!"
        )
    except Exception:
        pass


async def cb_binvite_decline(cb: CallbackQuery):
    uid = cb.from_user.id
    invite = pop_invite(uid)
    if not invite:
        await cb.answer("⏰ این دعوت دیگه معتبر نیست.", show_alert=True)
        return
    try:
        await cb.message.edit_text("❌ دعوت رو رد کردی.")
    except Exception:
        pass
    try:
        await cb.message.bot.send_message(invite["from_uid"], "😕 دعوتت به باس‌فایت رد شد.")
    except Exception:
        pass
    await cb.answer()


# ─── دکمه‌های راهنما زیرِ کیبوردِ هر سه نوع باس ───────────────────

async def cb_binvite_hint(cb: CallbackQuery):
    parts = cb.data.split(":")
    boss_type = parts[1] if len(parts) > 1 else "world"
    if boss_type == "group":
        txt = "📨 برای دعوتِ یه بازیکنِ دیگه: تو همین گروه رو پیامش ریپلای کن و /binvite بزن (یا بنویس /binvite @username)."
    elif boss_type == "region":
        txt = "📨 برای دعوتِ یه دوست به این باسِ منطقه‌ای: تو پی‌وی خودت بنویس /binvite @username — لازم نیست بیاد سراغِ همین مپ، از پی‌وی خودش می‌جنگه."
    else:
        txt = "📨 برای دعوتِ یه دوست به باسِ جهانی: بنویس /binvite @username."
    await cb.answer(txt, show_alert=True)


def register_boss_invite_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_binvite, Command("binvite"))
    dp.callback_query.register(cb_binvite_accept, F.data == "binvacc")
    dp.callback_query.register(cb_binvite_decline, F.data == "binvdec")
    dp.callback_query.register(cb_binvite_hint, F.data.startswith("binv:"))
