# ============================================================
#  ASTRAL ABYSS RPG — Mentor Handlers (Telegram UI)
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from logger import log_sync
import mentor_system as ms


async def cmd_mentor(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return

    args = msg.text.split(maxsplit=1) if msg.text.startswith("/mentor") else [msg.text]
    if len(args) == 1:
        lines = ["🎓 **سیستم استادی**\n"]
        if player.get("mentee_of"):
            mentor = await aget_player(player["mentee_of"])
            mname = mentor.get("name", "—") if mentor else "—"
            lines.append(f"👨‍🏫 استادت: **{mname}**")
            lines.append(f"✨ الان +{int(ms.MENTEE_XP_BONUS*100)}٪ XP اضافه می‌گیری.")
            lines.append(f"🎯 برای فارغ‌التحصیلی باید به Lv.{ms.GRADUATE_LEVEL} برسی (الان: Lv.{player.get('level',1)}).")
            lines.append(f"🔗 هر {ms.BOND_MILESTONE_EVERY} سطح یه لحظه‌ی باند فعال می‌شه (پاداشِ مشترکِ کوچیک).")
            if mentor:
                import battle_pass as bp
                bar = bp.pair_progress_bar(mentor, player)
                tier = bp.pair_tier(mentor, player)
                lines.append(f"\n🎫 **مسیرِ مشترکِ پس نبرد** — {bar} تایر {tier}/{bp.PAIR_MAX_TIER}")
                claimable = bp.pair_claimable_tiers(mentor, player)
                if claimable:
                    lines.append(f"🎁 {len(claimable)} جایزه‌ی مشترکِ آماده‌ی دریافت! `/mentorpass`")
        elif player.get("mentor_of"):
            names = []
            for mid in player["mentor_of"]:
                m = await aget_player(mid)
                names.append(m.get("name", f"#{mid}") if m else f"#{mid}")
            lines.append(f"🎓 شاگردات: {', '.join(names)}")
            lines.append(f"✨ الان +{int(ms.MENTOR_XP_BONUS*100)}٪ XP اضافه می‌گیری.")
            lines.append(f"🪑 ظرفیت باقی‌مونده: {ms.mentor_slots_left(player)}/{ms.MAX_MENTEES}")
            title = ms.mentor_title(player)
            grad = player.get("graduated_mentee_count", 0)
            if title:
                lines.append(f"🏅 عنوانِ استادی: {title} ({grad} فارغ‌التحصیل)")
            import battle_pass as bp
            any_claimable = False
            for mid in player["mentor_of"]:
                m = await aget_player(mid)
                if not m:
                    continue
                tier = bp.pair_tier(player, m)
                bar = bp.pair_progress_bar(player, m)
                lines.append(f"\n🎫 مسیرِ مشترک با **{m.get('name','—')}**: {bar} تایر {tier}/{bp.PAIR_MAX_TIER}")
                if bp.pair_claimable_tiers(player, m):
                    any_claimable = True
            if any_claimable:
                lines.append(f"\n🎁 جایزه‌ی مشترک آماده‌ست! `/mentorpass`")
        else:
            if ms.eligible_mentor(player):
                lines.append(f"✅ می‌تونی استاد بشی! (رتبه‌ت Lv.{ms.MENTOR_MIN_LEVEL}+ هست)")
                lines.append("📖 `/mentor @username` بزن تا یه تازه‌وارد (Lv.5 یا کمتر) رو شاگرد کنی.")
                title = ms.mentor_title(player)
                grad = player.get("graduated_mentee_count", 0)
                if title:
                    lines.append(f"🏅 عنوانِ استادیِ فعلیت: {title} ({grad} فارغ‌التحصیل تا الان)")
            elif ms.eligible_mentee(player):
                lines.append("✅ می‌تونی شاگرد یه بازیکن باتجربه بشی.")
                lines.append("📖 یه بازیکن Lv.15+ می‌تونه با `/mentor @username` تو رو دعوت کنه —")
                lines.append("یا خودت از لیستِ پایین یکی رو انتخاب کن و درخواست بده:")
                mentors = ms.available_mentors(uid)
                if mentors:
                    rows = [
                        [InlineKeyboardButton(
                            text=f"📩 درخواست از {m['name']} (Lv.{m.get('level',1)})",
                            callback_data=f"mentor_req:{uid}:{m['id']}", style=ButtonStyle.PRIMARY)]
                        for m in mentors
                    ]
                    await msg.answer("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
                    return
                else:
                    lines.append("\n😕 الان استادِ آزادی تو سرور نیست — بعداً دوباره سر بزن.")
            else:
                lines.append(f"ℹ️ برای استاد شدن باید Lv.{ms.MENTOR_MIN_LEVEL}+ باشی.")
                lines.append(f"ℹ️ برای شاگرد شدن باید Lv.{ms.MENTEE_MAX_LEVEL} یا کمتر باشی.")
        await msg.answer("\n".join(lines))
        return

    # /mentor @username → درخواست استادی
    if not ms.eligible_mentor(player):
        await msg.answer(f"❌ باید حداقل Lv.{ms.MENTOR_MIN_LEVEL} باشی تا استاد بشی.")
        return
    if ms.mentor_slots_left(player) <= 0:
        await msg.answer(f"❌ ظرفیت شاگردیت پره (حداکثر {ms.MAX_MENTEES} نفر).")
        return

    from pvp_handlers import _resolve_track_target
    target_id = _resolve_track_target(args[1], uid)
    if not target_id:
        await msg.answer("❌ این بازیکن پیدا نشد.")
        return
    mentee = await aget_player(target_id)
    if not mentee:
        await msg.answer("❌ این بازیکن پیدا نشد.")
        return
    if not ms.eligible_mentee(mentee):
        if mentee.get("mentee_of"):
            await msg.answer("❌ این بازیکن از قبل یه استاد داره.")
        else:
            await msg.answer(f"❌ این بازیکن باید Lv.{ms.MENTEE_MAX_LEVEL} یا کمتر باشه.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ قبول", callback_data=f"mentor_acc:{uid}:{target_id}", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="❌ رد", callback_data=f"mentor_dec:{uid}:{target_id}", style=ButtonStyle.DANGER)],
    ])
    await msg.answer(f"🎓 درخواست استادی برای **{mentee.get('name','—')}** فرستاده شد.")
    try:
        from bot import bot as _bot
        await _bot.send_message(
            target_id,
            f"🎓 **{player.get('name','—')}** (Lv.{player.get('level',1)}) می‌خواد استادت بشه!\n\n"
            f"✨ اگه قبول کنی: +{int(ms.MENTEE_XP_BONUS*100)}٪ XP اضافه می‌گیری تا برسی Lv.{ms.GRADUATE_LEVEL}.\n"
            f"🎁 موقع فارغ‌التحصیلی هردوتون پاداش بزرگ می‌گیرین.",
            reply_markup=kb
        )
    except Exception:
        await msg.answer("⚠️ نتونستم بهش پیام بدم (شاید ربات رو استارت نکرده).")


async def cb_mentor_accept(cb: CallbackQuery):
    _, mentor_id_s, mentee_id_s = cb.data.split(":")
    mentor_id, mentee_id = int(mentor_id_s), int(mentee_id_s)
    if cb.from_user.id != mentee_id:
        await cb.answer("❌ این درخواست مالِ تو نیست.", show_alert=True)
        return

    mentor = await aget_player(mentor_id)
    mentee = await aget_player(mentee_id)
    if not mentor or not mentee:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    if not ms.eligible_mentee(mentee):
        await cb.answer("❌ دیگه واجد شرایط شاگردی نیستی.", show_alert=True)
        return
    if ms.mentor_slots_left(mentor) <= 0:
        await cb.answer("❌ ظرفیت استاد پر شده.", show_alert=True)
        return

    ms.start_mentorship(mentor, mentee)
    await asave_player(mentor_id, mentor)
    await asave_player(mentee_id, mentee)

    log_sync(
        f"🎓 **MENTORSHIP STARTED**\n👨‍🏫 استاد: {mentor.get('name','—')} (`{mentor_id}`)\n"
        f"🎓 شاگرد: {mentee.get('name','—')} (`{mentee_id}`)", "MENTOR"
    )
    await cb.answer("✅ قبول شد!")
    await cb.message.edit_text(f"🎓 حالا شاگردِ **{mentor.get('name','—')}** هستی! +{int(ms.MENTEE_XP_BONUS*100)}٪ XP اضافه می‌گیری.")
    try:
        from bot import bot as _bot
        await _bot.send_message(mentor_id, f"🎉 **{mentee.get('name','—')}** درخواست استادیت رو قبول کرد!")
    except Exception:
        pass


async def cb_mentor_decline(cb: CallbackQuery):
    _, mentor_id_s, mentee_id_s = cb.data.split(":")
    mentee_id = int(mentee_id_s)
    if cb.from_user.id != mentee_id:
        await cb.answer("❌ این درخواست مالِ تو نیست.", show_alert=True)
        return
    await cb.answer("رد شد.")
    await cb.message.edit_text("❌ درخواست استادی رد شد.")


async def cb_mentor_reqsend(cb: CallbackQuery):
    """شاگردِ بالقوه از لیستِ /mentor یه استادِ خاص رو انتخاب کرده — درخواست براش می‌فرسته."""
    _, mentee_id_s, mentor_id_s = cb.data.split(":")
    mentee_id, mentor_id = int(mentee_id_s), int(mentor_id_s)
    if cb.from_user.id != mentee_id:
        await cb.answer("❌ این دکمه مالِ تو نیست.", show_alert=True)
        return

    mentee = await aget_player(mentee_id)
    mentor = await aget_player(mentor_id)
    if not mentee or not mentor:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    if not ms.eligible_mentee(mentee):
        await cb.answer("❌ دیگه واجد شرایط شاگردی نیستی.", show_alert=True)
        return
    if ms.mentor_slots_left(mentor) <= 0:
        await cb.answer("❌ ظرفیتِ این استاد پر شده.", show_alert=True)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ قبول", callback_data=f"mentor_reqacc:{mentor_id}:{mentee_id}", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="❌ رد", callback_data=f"mentor_reqdec:{mentor_id}:{mentee_id}", style=ButtonStyle.DANGER)],
    ])
    await cb.answer("✅ درخواست فرستاده شد!")
    await cb.message.edit_text(f"📩 درخواستِ شاگردی برای **{mentor.get('name','—')}** فرستاده شد.")
    try:
        from bot import bot as _bot
        await _bot.send_message(
            mentor_id,
            f"📩 **{mentee.get('name','—')}** (Lv.{mentee.get('level',1)}) می‌خواد شاگردت بشه!\n\n"
            f"اگه قبول کنی: خودت +{int(ms.MENTOR_XP_BONUS*100)}٪ XP اضافه می‌گیری، و هر {ms.BOND_MILESTONE_EVERY} "
            f"سطحی که پیشرفت کنه هردوتون یه پاداشِ مشترک می‌گیرین.",
            reply_markup=kb
        )
    except Exception:
        await cb.message.answer("⚠️ نتونستم به استاد پیام بدم (شاید ربات رو استارت نکرده).")


async def cb_mentor_reqaccept(cb: CallbackQuery):
    _, mentor_id_s, mentee_id_s = cb.data.split(":")
    mentor_id, mentee_id = int(mentor_id_s), int(mentee_id_s)
    if cb.from_user.id != mentor_id:
        await cb.answer("❌ این درخواست مالِ تو نیست.", show_alert=True)
        return

    mentor = await aget_player(mentor_id)
    mentee = await aget_player(mentee_id)
    if not mentor or not mentee:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    if not ms.eligible_mentee(mentee):
        await cb.answer("❌ این بازیکن دیگه واجدشرایط نیست.", show_alert=True)
        return
    if ms.mentor_slots_left(mentor) <= 0:
        await cb.answer("❌ ظرفیتت پر شده.", show_alert=True)
        return

    ms.start_mentorship(mentor, mentee)
    await asave_player(mentor_id, mentor)
    await asave_player(mentee_id, mentee)

    log_sync(
        f"🎓 **MENTORSHIP STARTED (mentee-initiated)**\n👨‍🏫 استاد: {mentor.get('name','—')} (`{mentor_id}`)\n"
        f"🎓 شاگرد: {mentee.get('name','—')} (`{mentee_id}`)", "MENTOR"
    )
    await cb.answer("✅ قبول شد!")
    await cb.message.edit_text(f"🎓 حالا استادِ **{mentee.get('name','—')}** هستی!")
    try:
        from bot import bot as _bot
        await _bot.send_message(mentee_id, f"🎉 **{mentor.get('name','—')}** درخواستِ شاگردیت رو قبول کرد! +{int(ms.MENTEE_XP_BONUS*100)}٪ XP اضافه می‌گیری.")
    except Exception:
        pass


async def cb_mentor_reqdecline(cb: CallbackQuery):
    _, mentor_id_s, mentee_id_s = cb.data.split(":")
    mentor_id = int(mentor_id_s)
    if cb.from_user.id != mentor_id:
        await cb.answer("❌ این درخواست مالِ تو نیست.", show_alert=True)
        return
    await cb.answer("رد شد.")
    await cb.message.edit_text("❌ درخواستِ شاگردی رد شد.")


async def cmd_mentor_end(msg: Message):
    """قطع‌کردنِ رابطه‌ی استادی (توسط استاد یا شاگرد)."""
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        return
    if player.get("mentee_of"):
        mentor_id = player["mentee_of"]
        mentor = await aget_player(mentor_id)
        ms.end_mentorship(mentor, player)
        await asave_player(uid, player)
        if mentor:
            await asave_player(mentor_id, mentor)
        await msg.answer("👋 رابطه‌ی استادیت قطع شد.")
    elif player.get("mentor_of"):
        for mid in list(player["mentor_of"]):
            mentee = await aget_player(mid)
            if mentee:
                ms.end_mentorship(player, mentee)
                await asave_player(mid, mentee)
        player["mentor_of"] = []
        await asave_player(uid, player)
        await msg.answer("👋 همه‌ی شاگردات آزاد شدن.")
    else:
        await msg.answer("ℹ️ الان تو هیچ رابطه‌ی استادی‌ای نیستی.")


async def cmd_mentor_pass(msg: Message):
    """🎫 نمایش/دریافتِ جوایزِ مسیرِ مشترکِ استاد/شاگرد."""
    import battle_pass as bp
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return

    pairs = []  # لیستِ (mentor, mentee, mentor_id, mentee_id)
    if player.get("mentee_of"):
        mentor = await aget_player(player["mentee_of"])
        if mentor:
            pairs.append((mentor, player, player["mentee_of"], uid))
    for mid in player.get("mentor_of", []):
        mentee = await aget_player(mid)
        if mentee:
            pairs.append((player, mentee, uid, mid))

    if not pairs:
        await msg.answer("ℹ️ تو الان تو هیچ رابطه‌ی استادی‌ای نیستی — این مسیرِ مشترک فقط برای استاد/شاگردهای فعاله.")
        return

    lines = ["🎫 **مسیرِ مشترکِ پس نبرد**\n"]
    buttons = []
    for mentor, mentee, mentor_id, mentee_id in pairs:
        other_name = mentee.get("name", "—") if mentor_id == uid else mentor.get("name", "—")
        tier = bp.pair_tier(mentor, mentee)
        bar = bp.pair_progress_bar(mentor, mentee)
        left = bp.pair_points_to_next_tier(mentor, mentee)
        lines.append(f"👥 با **{other_name}**: {bar} تایر {tier}/{bp.PAIR_MAX_TIER}")
        if left:
            lines.append(f"   ({left:,} امتیاز تا تایر بعدی)")
        for t in bp.pair_claimable_tiers(mentor, mentee):
            buttons.append([InlineKeyboardButton(
                text=f"🎁 دریافتِ تایر {t} (با {other_name})",
                callback_data=f"mpass_claim:{mentor_id}:{mentee_id}:{t}",
                style=ButtonStyle.SUCCESS,
            )])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    await msg.answer("\n".join(lines), reply_markup=kb)


async def cb_mentor_pass_claim(cb: CallbackQuery):
    import battle_pass as bp
    _, mentor_id_s, mentee_id_s, tier_s = cb.data.split(":")
    mentor_id, mentee_id, tier = int(mentor_id_s), int(mentee_id_s), int(tier_s)
    if cb.from_user.id not in (mentor_id, mentee_id):
        await cb.answer("❌ این مالِ تو نیست.", show_alert=True)
        return
    mentor = await aget_player(mentor_id)
    mentee = await aget_player(mentee_id)
    if not mentor or not mentee:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    result = bp.claim_pair_tier(mentor, mentee, tier)
    if not result:
        await cb.answer("❌ این جایزه قبلاً گرفته شده یا هنوز باز نشده.", show_alert=True)
        return
    await asave_player(mentor_id, mentor)
    await asave_player(mentee_id, mentee)
    msg = f"🎁 هردوتون +{result['zen']:,} Zen گرفتین!"
    if result.get("title"):
        msg += f"\n🏅 عنوانِ جدید: {result['title']}"
    await cb.answer(msg, show_alert=True)
    try:
        other_id = mentee_id if cb.from_user.id == mentor_id else mentor_id
        await cb.bot.send_message(other_id, f"🎉 جایزه‌ی مسیرِ مشترکِ استاد/شاگرد گرفته شد!\n{msg}")
    except Exception:
        pass


def register_mentor_handlers(dp, bot):
    dp.message.register(cmd_mentor, Command("mentor"))
    dp.message.register(cmd_mentor_end, Command("unmentor"))
    dp.message.register(cmd_mentor_pass, Command("mentorpass"))
    dp.callback_query.register(cb_mentor_accept,  F.data.startswith("mentor_acc:"))
    dp.callback_query.register(cb_mentor_decline, F.data.startswith("mentor_dec:"))
    dp.callback_query.register(cb_mentor_reqsend,     F.data.startswith("mentor_req:"))
    dp.callback_query.register(cb_mentor_reqaccept,   F.data.startswith("mentor_reqacc:"))
    dp.callback_query.register(cb_mentor_reqdecline,  F.data.startswith("mentor_reqdec:"))
    dp.callback_query.register(cb_mentor_pass_claim,  F.data.startswith("mpass_claim:"))
