# ============================================================
#  ASTRAL ABYSS — PvP Handlers (v2) (با لاگ‌گذاری کامل)
# ============================================================
import asyncio
import time

from gap_dispatcher import GapDispatcher, gap_is_online
from gap_types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, gap_only_players

from pvp import (
    FighterState, FightSession, build_fighter,
    active_fights, player_in_fight, pending_duels, last_opponent,
    get_fight_by_uid, get_self, get_opponent,
    fight_status_text, fighter_block_text, hp_bar, resolve_turn,
    league_for_points, next_league_gap, points_for_win, LOSE_POINTS,
    FIGHT_TIMEOUT, TURN_TIMEOUT, FIGHT_MAX_TURNS,
    season_reward_for_league,
    battle_epithet, battle_headline,
)
from characters import ALL_CHARACTERS
from database import get_player, save_player, all_players
from logger import log_sync

STAKE_OPTIONS = [1000, 5000, 25000, 100000]


# ────────────────────────────────────────────────────────────
# /arena — لابی
# ────────────────────────────────────────────────────────────
def _lobby_text_and_kb(uid: int) -> tuple[str, InlineKeyboardMarkup]:
    # نکته‌ی گپ: all_players() بینِ تلگرام و گپ مشترکه، پس فیلتر می‌کنیم؛
    # is_online هم معادلِ گپیِ خودش (gap_is_online) رو می‌گیره، نه نسخه‌ی
    # تلگرامیِ bot.py رو (که اصلاً برای uidِ منفی چیزی نداره).
    players = gap_only_players(all_players())
    others = []
    for pid, p in players.items():
        pid_int = int(pid)
        if pid_int == uid or not p.get("character"):
            continue
        others.append((pid_int, p))
    others.sort(key=lambda x: -x[1].get("pvp_wins", 0))

    lines = ["👥 **سالن مبارزه — آرنا**\n"]
    buttons = []
    shown = 0
    for pid, p in others[:25]:
        online = gap_is_online(pid)
        busy = get_fight_by_uid(pid) is not None
        dot = "🟢" if (online and not busy) else "🔴"
        status = "" if (online and not busy) else " (در حال مبارزه)" if busy else " (آفلاین)"
        shown += 1
        lines.append(f"{dot} {shown}. {p['name']} | {p.get('character','?')} | Lv.{p.get('level',1)} | 🏆 {p.get('pvp_wins',0)} برد{status}")
        if online and not busy:
            buttons.append([InlineKeyboardButton(text=f"⚔️ چالش {p['name']}", callback_data=f"pvp_challenge:{pid}")])

    if shown == 0:
        lines.append("\n😔 هیچ بازیکنی پیدا نشد!")

    lines.append(f"\n📝 `/duel @username` یا `/duel random` هم کار می‌کنه.")
    buttons.append([InlineKeyboardButton(text="🔙 بستن", callback_data="pvp_close")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)


async def cmd_arena(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    from level_gate import check_level
    ok, why = check_level(player, "pvp")
    if not ok:
        await msg.answer(why)
        return
    text, kb = _lobby_text_and_kb(uid)
    await msg.answer(text, reply_markup=kb)


async def cb_pvp_menu_back(cb: CallbackQuery, bot):
    text, kb = _lobby_text_and_kb(cb.from_user.id)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()

async def cb_pvp_close(cb: CallbackQuery):
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.answer()


# ────────────────────────────────────────────────────────────
# /duel — چالش
# ────────────────────────────────────────────────────────────
def _find_closest_cp_opponent(uid: int, players: dict) -> int | None:
    """به‌جای انتخابِ کاملاً تصادفی، نزدیک‌ترین حریف‌ها از نظرِ Combat Power رو
    پیدا می‌کنه و از بینشون یکی رو انتخاب می‌کنه."""
    import random as _r
    from combat_power import calculate_combat_power

    me = get_player(uid)
    if not me:
        return None
    my_cp = max(1, calculate_combat_power(me))

    scored = []
    for pid, p in players.items():
        pid_int = int(pid)
        if pid_int == uid or not p.get("character") or get_fight_by_uid(pid_int):
            continue
        cp = max(1, calculate_combat_power(p))
        scored.append((abs(cp - my_cp), pid_int))

    if not scored:
        return None
    scored.sort(key=lambda x: x[0])
    pool_size = min(5, len(scored))
    pool = [pid for _, pid in scored[:pool_size]]
    return _r.choice(pool)


def _resolve_target(text: str, uid: int) -> int | None:
    """/duel @username یا /duel random رو به یه uid تبدیل می‌کنه."""
    parts = text.split()
    if len(parts) < 2:
        return None
    arg = parts[1]
    players = gap_only_players(all_players())
    if arg.lower() == "random":
        return _find_closest_cp_opponent(uid, players)
    uname = arg.lstrip("@").lower()
    for pid, p in players.items():
        if (p.get("username") or "").lower() == uname:
            return int(pid)
    return None


# ────────────────────────────────────────────────────────────
# /track — ردیابی بازیکن (این فیچر قبلاً هیچ‌جا پیاده نشده بود؛
# فقط دکمه‌ی «🔍 ردیابی» یه متنِ راهنما نشون می‌داد که به /track
# اشاره می‌کرد، ولی خودِ دستور اصلاً وجود نداشت)
# ────────────────────────────────────────────────────────────
def _resolve_track_target(arg: str, uid: int) -> int | None:
    """/track @username یا /track user_id یا /track نام_بازیکن رو به یه uid تبدیل می‌کنه."""
    arg = arg.strip()
    if not arg:
        return None
    players = gap_only_players(all_players())

    # 1) عددی → user_id مستقیم
    if arg.lstrip("-").isdigit():
        pid_int = int(arg)
        return pid_int if str(pid_int) in players else None

    # 2) @username
    uname = arg.lstrip("@").lower()
    for pid, p in players.items():
        if (p.get("username") or "").lower() == uname:
            return int(pid)

    # 3) اسم بازیکن (اول تطبیق کامل، بعد جزئی اگه فقط یه نتیجه بود)
    name_lower = arg.lower()
    exact = [int(pid) for pid, p in players.items() if (p.get("name") or "").lower() == name_lower]
    if exact:
        return exact[0]
    partial = [int(pid) for pid, p in players.items() if name_lower in (p.get("name") or "").lower()]
    if len(partial) == 1:
        return partial[0]
    return None


async def cmd_track(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    from level_gate import check_level
    ok, why = check_level(player, "track")
    if not ok:
        await msg.answer(why)
        return

    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await msg.answer(
            "🔍 **ردیابی جنگجو**\n\n"
            "• `/track @username`\n"
            "• `/track user_id`\n"
            "• `/track نام_بازیکن`"
        )
        return

    target_id = _resolve_track_target(parts[1], uid)
    if not target_id:
        await msg.answer("❌ همچین بازیکنی پیدا نشد!")
        return
    if target_id == uid:
        await msg.answer("❌ خودت رو که نمی‌تونی ردیابی کنی!")
        return

    target = get_player(target_id)
    if not target or not target.get("character"):
        await msg.answer("❌ این بازیکن پیدا نشد!")
        return

    from economy import MAPS_DATA, ZONE_E

    online = gap_is_online(target_id)
    target_busy = get_fight_by_uid(target_id) is not None
    self_busy = get_fight_by_uid(uid) is not None

    map_name = target.get("map", "Verdant Vale")
    map_info = MAPS_DATA.get(map_name, {})
    map_emoji = map_info.get("emoji", "🗺️")
    zone_e = ZONE_E.get(map_info.get("zone", "contested"), "🟡")

    status = "🟢 آنلاین" if online else "🔴 آفلاین"
    if target_busy:
        status += " (در حال مبارزه)"

    text = (
        f"🔍 **ردیابی: {target['name']}**\n\n"
        f"🎭 کاراکتر: {target.get('character','?')}\n"
        f"⭐ سطح: {target.get('level',1)}\n"
        f"📍 موقعیت: {map_emoji} {map_name} {zone_e}\n"
        f"📶 وضعیت: {status}\n"
        f"🏆 برد PvP: {target.get('pvp_wins',0)}"
    )

    buttons = []
    if online and not target_busy and not self_busy:
        buttons.append([InlineKeyboardButton(
            text=f"⚔️ چالش {target['name']}",
            callback_data=f"pvp_challenge:{target_id}"
        )])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    await msg.answer(text, reply_markup=kb)


async def cmd_duel(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    from level_gate import check_level
    ok, why = check_level(player, "pvp")
    if not ok:
        await msg.answer(why)
        return
    if get_fight_by_uid(uid):
        await msg.answer("⚔️ الان توی یه فایتی!")
        return
    if uid in pending_duels:
        await msg.answer("⏳ یه درخواستِ دیگه هنوز بازه. صبر کن یا `/duel` رو دوباره بزن.")
        return

    target_id = _resolve_target(msg.text or "", uid)
    if not target_id:
        await msg.answer("📝 استفاده: `/duel @username` یا `/duel random`")
        return
    if target_id == uid:
        await msg.answer("❌ نمی‌تونی خودت رو چالش بدی!")
        return
    if get_fight_by_uid(target_id):
        await msg.answer("❌ اون بازیکن الان توی یه فایته!")
        return

    target = get_player(target_id)
    if not target or not target.get("character"):
        await msg.answer("❌ این بازیکن پیدا نشد!")
        return

    await _send_stake_prompt(msg, uid, target_id, is_challenger=True)


async def cb_pvp_challenge(cb: CallbackQuery, bot):
    uid = cb.from_user.id
    target_id = int(cb.data.split(":")[1])
    player = get_player(uid)
    target = get_player(target_id)
    if not player or not target:
        await cb.answer("❌ بازیکن پیدا نشد!", show_alert=True)
        return
    if get_fight_by_uid(uid):
        await cb.answer("⚔️ الان توی فایتی!", show_alert=True)
        return
    if get_fight_by_uid(target_id):
        await cb.answer("❌ حریف الان توی فایته!", show_alert=True)
        return
    await _send_stake_prompt(cb.message, uid, target_id, is_challenger=True, edit=True)
    await cb.answer()


async def _send_stake_prompt(msg: Message, uid: int, target_id: int, is_challenger: bool, edit: bool = False):
    target = get_player(target_id)
    text = f"⚔️ چالش دادن به **{target['name']}**\n\n💰 شرط رو انتخاب کن:"
    buttons = [
        [InlineKeyboardButton(text=f"💰 {amt:,}", callback_data=f"pvp_stakeset:{target_id}:{amt}")]
        for amt in STAKE_OPTIONS
    ]
    buttons.append([InlineKeyboardButton(text="🚫 بدون شرط", callback_data=f"pvp_stakeset:{target_id}:0")])
    buttons.append([InlineKeyboardButton(text="🔙 برگشت", callback_data="pvp_menu_back")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    if edit:
        await msg.edit_text(text, reply_markup=kb)
    else:
        await msg.answer(text, reply_markup=kb)


async def cb_pvp_stakeset(cb: CallbackQuery, bot):
    # 🔎 دیباگ موقت: تأیید می‌کنه که هندلر واقعاً صدا زده شده
    log_sync(f"🔎 DEBUG cb_pvp_stakeset ENTER | uid={cb.from_user.id} | data={cb.data}", "PVP")
    try:
        await _cb_pvp_stakeset_body(cb, bot)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log_sync(f"🔴 **cb_pvp_stakeset CRASH**\n`{type(e).__name__}: {e}`\n```{tb[-1500:]}```", "ERROR")
        try:
            await cb.answer("⚠️ خطا تو ثبت شرط! لاگ شد.", show_alert=True)
        except Exception:
            pass


async def _cb_pvp_stakeset_body(cb: CallbackQuery, bot):
    uid = cb.from_user.id
    _, target_id_s, amt_s = cb.data.split(":")
    target_id, stake = int(target_id_s), int(amt_s)

    player = get_player(uid)
    target = get_player(target_id)
    if not player or not target:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    if stake > player.get("zen", 0):
        await cb.answer("❌ Zen کافی نداری!", show_alert=True)
        return

    pending_duels[uid] = {
        "target_id": target_id, "chat_id": cb.message.chat.id,
        "expires": time.time() + FIGHT_TIMEOUT, "stake": stake,
        "challenger_name": player["name"],
    }
    stake_txt = f"💰 شرط: {stake:,} Zen" if stake else "🚫 بدون شرط"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ قبول مبارزه", callback_data=f"pvp_accept:{uid}"),
        InlineKeyboardButton(text="❌ رد کن", callback_data=f"pvp_reject:{uid}"),
    ]])
    
    log_sync(
        f"⚔️ **PVP DUEL SENT**\n"
        f"👤 چالش‌دهنده: {player.get('name','—')} (`{uid}`)\n"
        f"👤 حریف: {target.get('name','—')} (`{target_id}`)\n"
        f"💰 شرط: {stake:,} Zen",
        "PVP"
    )
    
    try:
        # نکته‌ی گپ: target_id یه uid داخلیه (منفی) → chat_id واقعی abs()
        await bot.send_message(
            abs(target_id),
            f"⏰ **چالش جدید!**\n\n**{player['name']}** بهت چالش داده!\n"
            f"🗡️ کاراکتر: {player.get('character','?')} (Lv.{player.get('level',1)})\n"
            f"{stake_txt}\n\n⏳ {FIGHT_TIMEOUT} ثانیه وقت داری!",
            reply_markup=kb,
        )
        await cb.message.edit_text(f"✅ چالش به **{target['name']}** فرستاده شد! ({stake_txt})\n\n⏳ منتظر جواب باش...")
    except Exception:
        await cb.message.edit_text(f"❌ نتونستم به **{target['name']}** پیام بدم (شاید ربات رو استارت نکرده).")
        pending_duels.pop(uid, None)
        await cb.answer()
        return

    await cb.answer("✅ چالش فرستاده شد!")
    asyncio.create_task(_expire_duel(uid, bot))


async def _expire_duel(challenger_uid: int, bot):
    await asyncio.sleep(FIGHT_TIMEOUT)
    duel = pending_duels.get(challenger_uid)
    if not duel:
        return
    pending_duels.pop(challenger_uid, None)
    
    log_sync(
        f"⏰ **PVP DUEL EXPIRED**\n"
        f"👤 چالش‌دهنده: `{challenger_uid}`\n"
        f"👤 حریف: `{duel['target_id']}`",
        "PVP"
    )
    
    for tid in (challenger_uid, duel["target_id"]):
        try:
            await bot.send_message(abs(tid), "⏰ **درخواستِ دوئل منقضی شد!** جواب داده نشد.")
        except Exception:
            pass


async def cb_pvp_reject(cb: CallbackQuery, bot):
    challenger_uid = int(cb.data.split(":")[1])
    duel = pending_duels.get(challenger_uid)
    if not duel or duel["target_id"] != cb.from_user.id:
        await cb.answer("⏰ این چالش دیگه معتبر نیست.", show_alert=True)
        return
    pending_duels.pop(challenger_uid, None)
    
    log_sync(
        f"❌ **PVP DUEL REJECTED**\n"
        f"👤 چالش‌دهنده: `{challenger_uid}`\n"
        f"👤 حریف: `{cb.from_user.id}`",
        "PVP"
    )
    
    try:
        await cb.message.edit_text("❌ چالش رو رد کردی.")
    except Exception:
        pass
    try:
        await bot.send_message(abs(challenger_uid), "❌ **درخواستِ دوئلت رد شد!** حریفت نمی‌خواد بجنگه.")
    except Exception:
        pass
    await cb.answer()


async def cb_pvp_accept(cb: CallbackQuery, bot):
    uid = cb.from_user.id
    challenger_uid = int(cb.data.split(":")[1])
    duel = pending_duels.get(challenger_uid)
    if not duel or duel["target_id"] != uid:
        await cb.answer("⏰ چالش منقضی شده!", show_alert=True)
        try:
            await cb.message.edit_text("⏰ چالش منقضی شده!")
        except Exception:
            pass
        return

    pending_duels.pop(challenger_uid, None)
    p1_data = get_player(challenger_uid)
    p2_data = get_player(uid)
    if not p1_data or not p2_data:
        await cb.answer("❌ خطا!", show_alert=True)
        return

    stake = duel.get("stake", 0)
    if stake > p1_data.get("zen", 0) or stake > p2_data.get("zen", 0):
        await cb.answer("❌ یکی از دو طرف دیگه Zen کافی نداره!", show_alert=True)
        try:
            await cb.message.edit_text("❌ شرط دیگه معتبر نیست (Zen کافی نیست).")
        except Exception:
            pass
        return

    log_sync(
        f"✅ **PVP DUEL ACCEPTED**\n"
        f"👤 چالش‌دهنده: {p1_data.get('name','—')} (`{challenger_uid}`)\n"
        f"👤 حریف: {p2_data.get('name','—')} (`{uid}`)\n"
        f"💰 شرط: {stake:,} Zen",
        "PVP"
    )

    await _start_fight(bot, duel["chat_id"], challenger_uid, uid, p1_data, p2_data, stake)
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.answer("⚔️ مبارزه شروع شد!")


# ────────────────────────────────────────────────────────────
# شروعِ فایت
# ────────────────────────────────────────────────────────────
async def _start_fight(bot, chat_id: int, uid1: int, uid2: int, p1_data: dict, p2_data: dict, stake: int):
    char1 = ALL_CHARACTERS.get(p1_data.get("character"), {})
    char2 = ALL_CHARACTERS.get(p2_data.get("character"), {})
    f1 = build_fighter(uid1, p1_data, char1)
    f2 = build_fighter(uid2, p2_data, char2)

    fight_id = f"{uid1}_{uid2}_{int(time.time())}"
    fight = FightSession(fight_id=fight_id, chat_id=chat_id, p1=f1, p2=f2, stake_zen=stake)
    active_fights[fight_id] = fight
    player_in_fight[uid1] = fight_id
    player_in_fight[uid2] = fight_id
    last_opponent[uid1] = uid2
    last_opponent[uid2] = uid1

    intro = (
        f"🎬 **⚔️ آرنا فعال شد — نبرد آغاز می‌شه! ⚔️**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔴 {fighter_block_text(f1)}\n\n"
        f"          🆚\n\n"
        f"🔵 {fighter_block_text(f2)}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        + (f"💰 شرط: {stake:,} Zen\n" if stake else "🚫 بدون شرط\n")
        + "🎲 مکانیک‌های زنده: 🔗کومبو · 🔥مومنتوم/اوردرایو · 👻شانسِ جاخالی · 🔪فینیشینگ‌بلو نزدیکِ مرگ\n\n"
        + f"🎯 **نوبت ۱ — بجنگید!**"
    )
    try:
        await bot.send_message(chat_id, intro)
    except Exception:
        pass

    await _send_turn_prompt(fight, f1, bot)
    await _send_turn_prompt(fight, f2, bot)
    asyncio.create_task(_turn_timeout_watcher(fight_id, fight.turn, bot))


def _action_kb(fight: FightSession, fighter: FighterState) -> InlineKeyboardMarkup:
    rows = []
    ab_row = []
    for i, ab in enumerate(fighter.abilities):
        locked = fighter.energy < ab["cost"]
        label = f"{'🔒' if locked else ''}{ab['name']} ({ab['cost']}⚡)"
        ab_row.append(InlineKeyboardButton(text=label, callback_data=f"pvpfight_ab:{fight.fight_id}:{fighter.uid}:{i}"))
        if len(ab_row) == 2:
            rows.append(ab_row)
            ab_row = []
    if ab_row:
        rows.append(ab_row)
    rows.append([
        InlineKeyboardButton(text="⚔️ حمله معمولی", callback_data=f"pvpfight_atk:{fight.fight_id}:{fighter.uid}"),
        InlineKeyboardButton(text="🛡 دفاع", callback_data=f"pvpfight_def:{fight.fight_id}:{fighter.uid}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _send_turn_prompt(fight: FightSession, fighter: FighterState, bot):
    # نکته‌ی گپ: fighter.uid داخلیه (منفی) → chat_id واقعی abs()
    if fighter.stunned_turns > 0:
        try:
            await bot.send_message(
                abs(fighter.uid),
                f"⏳ **نوبت {fight.turn} — متوقف شدی!**\n\nحریفت باید صبر کنه تا تو دوباره حرکت کنی."
            )
        except Exception:
            pass
        return
    text = (
        f"🎯 **نوبت {fight.turn} — انتخابِ اکشن:**\n\n"
        f"🔋 انرژی: {fighter.energy}/100\n\n"
        f"⏳ {TURN_TIMEOUT} ثانیه وقت داری!"
    )
    kb = _action_kb(fight, fighter)
    try:
        # نکته‌ی گپ: GapBotAdapter.send_message مستقیم آی‌دیِ پیام (نه یه
        # آبجکتِ Message با .message_id مثلِ aiogram) رو برمی‌گردونه.
        mid = await bot.send_message(abs(fighter.uid), text, reply_markup=kb)
        fight.prompt_msgs[fighter.uid] = mid
    except Exception as e:
        # باگِ اصلی همینجا بود: وقتی پیامِ خصوصی (چت با ربات) نمی‌رسید،
        # این خطا بی‌صدا قورت داده می‌شد، هیچ دکمه‌ای هیچ‌جا دیده نمی‌شد
        # و نوبتِ بازیکن با تایم‌اوتِ خودکار «حمله‌ی معمولی» پر می‌شد —
        # دقیقاً انگار ربات به‌جاش تصمیم گرفته. حالا لاگ می‌شه و به‌جاش
        # دکمه‌ها تو خودِ گروهِ فایت فرستاده می‌شن.
        log_sync(
            f"⚠️ **PVP(Gap) DM FAILED** — نتونستم به `{fighter.uid}` ({fighter.name}) پیامِ خصوصیِ نوبت رو بدم: `{e}`. فال‌بک به گروه.",
            "PVP"
        )
        try:
            mid = await bot.send_message(
                fight.chat_id,
                f"⚠️ **{fighter.name}** چون نتونستم بهت پیامِ خصوصی بدم، فعلاً نوبتت رو همینجا انتخاب کن:\n\n{text}",
                reply_markup=kb,
            )
            fight.prompt_msgs[fighter.uid] = mid
        except Exception:
            pass


async def _register_action(fight: FightSession, uid: int, action: dict, bot):
    if fight.phase == "ended" or uid not in (fight.p1.uid, fight.p2.uid):
        return
    if uid in fight.pending:
        return  # قبلاً انتخاب کرده
    fight.pending[uid] = action

    opp = get_opponent(fight, uid)
    if opp.uid not in fight.pending and opp.stunned_turns == 0:
        return  # هنوز منتظرِ حریفیم

    await _resolve_and_advance(fight, bot)


SUSPENSE_LINES = [
    "⏳ هر دو حریف حرکتشون رو انتخاب کردن... در حال محاسبه‌ی نبرد...",
    "⏳ ضربه‌ها تو راهن... چند لحظه صبر کن...",
    "⏳ سکوت قبل از طوفان...",
]

async def _resolve_and_advance(fight: FightSession, bot):
    if fight.phase == "ended":
        return
    turn_before = fight.turn
    try:
        import random as _r
        await bot.send_message(fight.chat_id, _r.choice(SUSPENSE_LINES))
        await asyncio.sleep(1.2)
    except Exception:
        pass
    logs = resolve_turn(fight)

    p1, p2 = fight.p1, fight.p2
    if p1.hp <= 0 or p2.hp <= 0 or fight.turn > FIGHT_MAX_TURNS:
        try:
            await bot.send_message(fight.chat_id, "\n".join(logs) + f"\n\n{fight_status_text(fight)}")
        except Exception:
            pass
        await _end_fight(fight, bot)
        return

    try:
        await bot.send_message(fight.chat_id, "\n".join(logs) + f"\n\n{fight_status_text(fight)}")
    except Exception:
        pass

    await _send_turn_prompt(fight, p1, bot)
    await _send_turn_prompt(fight, p2, bot)
    asyncio.create_task(_turn_timeout_watcher(fight.fight_id, fight.turn, bot))


async def _turn_timeout_watcher(fight_id: str, turn_at_spawn: int, bot):
    await asyncio.sleep(TURN_TIMEOUT)
    fight = active_fights.get(fight_id)
    if not fight or fight.phase == "ended" or fight.turn != turn_at_spawn:
        return  # نوبت قبلاً حل شده
    # هرکسی که انتخاب نکرده، به‌طورِ خودکار حمله‌ی معمولی می‌زنه
    for f in (fight.p1, fight.p2):
        if f.uid not in fight.pending:
            fight.pending[f.uid] = {"type": "attack"}
    await _resolve_and_advance(fight, bot)


# ────────────────────────────────────────────────────────────
# دکمه‌های نوبت
# ────────────────────────────────────────────────────────────
def _check_actor(cb: CallbackQuery, parts: list[str]) -> bool:
    """اگه دکمه (فال‌بکِ گروهی) برای این کاربر نبود، رد می‌کنه — جلوگیری از
    این‌که حریف یا کسِ دیگه به‌جای بازیکنِ واقعی نوبتش رو انتخاب کنه."""
    if len(parts) > 2:
        try:
            expected_uid = int(parts[2])
        except ValueError:
            return True
        return cb.from_user.id == expected_uid
    return True  # فرمتِ قدیمی — سازگاری

async def cb_fight_attack(cb: CallbackQuery, bot):
    parts = cb.data.split(":")
    fight_id = parts[1]
    fight = active_fights.get(fight_id)
    if not fight:
        await cb.answer("⏰ فایت تموم شده!", show_alert=True)
        return
    if not _check_actor(cb, parts):
        await cb.answer("❌ این نوبتِ تو نیست!", show_alert=True)
        return
    await _register_action(fight, cb.from_user.id, {"type": "attack"}, bot)
    try:
        await cb.message.edit_text("✅ انتخاب شد! (حمله‌ی معمولی)")
    except Exception:
        pass
    await cb.answer()

async def cb_fight_defend(cb: CallbackQuery, bot):
    parts = cb.data.split(":")
    fight_id = parts[1]
    fight = active_fights.get(fight_id)
    if not fight:
        await cb.answer("⏰ فایت تموم شده!", show_alert=True)
        return
    if not _check_actor(cb, parts):
        await cb.answer("❌ این نوبتِ تو نیست!", show_alert=True)
        return
    await _register_action(fight, cb.from_user.id, {"type": "defend"}, bot)
    try:
        await cb.message.edit_text("✅ انتخاب شد! (دفاع)")
    except Exception:
        pass
    await cb.answer()

async def cb_fight_ability(cb: CallbackQuery, bot):
    parts = cb.data.split(":")
    fight_id = parts[1]
    idx_s = parts[-1]
    fight = active_fights.get(fight_id)
    if not fight:
        await cb.answer("⏰ فایت تموم شده!", show_alert=True)
        return
    if not _check_actor(cb, parts):
        await cb.answer("❌ این نوبتِ تو نیست!", show_alert=True)
        return
    uid = cb.from_user.id
    fighter = get_self(fight, uid)
    idx = int(idx_s)
    ab = fighter.abilities[idx]
    if fighter.energy < ab["cost"]:
        await cb.answer(f"❌ انرژیِ کافی نداری! ({fighter.energy}/{ab['cost']})", show_alert=True)
        return
    await _register_action(fight, uid, {"type": "ability", "ability_idx": idx}, bot)
    try:
        await cb.message.edit_text(f"✅ انتخاب شد! ({ab['name']})")
    except Exception:
        pass
    await cb.answer()


# ────────────────────────────────────────────────────────────
# پایانِ فایت + جوایز + رنکینگ
# ────────────────────────────────────────────────────────────
async def _end_fight(fight: FightSession, bot):
    """محکم‌سازی: مثلِ نسخه‌ی تلگرامِ pvp_handlers.py — هرچی وسطِ محاسبه‌ی
    جایزه/رنک بترکه، فایت بازم قطعاً پاک می‌شه تا بازیکن‌ها تو PvP قفل
    نمونن (باگِ اصلیِ «فقط نوبتِ ۱ رو نشون می‌ده» همینجا بود)."""
    p1, p2 = fight.p1, fight.p2
    try:
        await _end_fight_body(fight, bot)
    except Exception as e:
        log_sync(
            f"🔴 **GAP PVP END-FIGHT CRASH** — محاسبه‌ی نتیجه‌ی فایت `{fight.fight_id}` "
            f"با خطا شکست خورد: `{e}`. فایت به‌صورتِ اضطراری بسته شد.",
            "ERROR",
        )
        try:
            await bot.send_message(
                fight.chat_id,
                "⚠️ یه خطای غیرمنتظره تو محاسبه‌ی نتیجه‌ی این مبارزه پیش اومد.\n"
                "مبارزه بسته شد تا بتونید دوباره وارد PvP بشید؛ اگه جایزه/رنکتون "
                "آپدیت نشد به ادمین خبر بدید.",
            )
        except Exception:
            pass
        for f in (p1, p2):
            try:
                d = get_player(f.uid)
                if d:
                    d["hp"] = max(1, d.get("max_hp", 100) // 2)
                    save_player(f.uid, d)
            except Exception:
                pass
    finally:
        fight.phase = "ended"
        player_in_fight.pop(p1.uid, None)
        player_in_fight.pop(p2.uid, None)
        active_fights.pop(fight.fight_id, None)


async def _end_fight_body(fight: FightSession, bot):
    p1, p2 = fight.p1, fight.p2
    is_draw = p1.hp <= 0 and p2.hp <= 0
    if is_draw:
        winner, loser = None, None
    else:
        winner = p1 if p2.hp <= 0 else p2
        loser  = p2 if p2.hp <= 0 else p1

    w_data = get_player(winner.uid) if winner else None
    l_data = get_player(loser.uid) if loser else None

    result_lines = [f"🏆 **DUEL OVER!**\n"]

    if is_draw:
        result_lines.append("🤝 **مساوی شد!** (سقفِ نوبت‌ها رسید)")
        for uid, data in ((p1.uid, get_player(p1.uid)), (p2.uid, get_player(p2.uid))):
            if data:
                data["hp"] = max(1, data.get("max_hp", 100) // 2)
                save_player(uid, data)
    else:
        zen_reward = 500 + winner.level * 10
        xp_reward  = 50 + winner.level * 5

        w_data["zen"] = w_data.get("zen", 0) + zen_reward + fight.stake_zen
        w_data["xp"]  = w_data.get("xp", 0) + xp_reward

        # 🎯 اگه بازنده جایزه رو سرش بود، برنده کل جایزه رو می‌بره
        import bounty_system as bounty_sys
        bounty_won = bounty_sys.claim_bounty(loser.uid)
        if bounty_won > 0:
            w_data["zen"] = w_data.get("zen", 0) + bounty_won

        w_data["pvp_wins"] = w_data.get("pvp_wins", 0) + 1
        w_data["pvp_streak"] = w_data.get("pvp_streak", 0) + 1
        w_data["pvp_best_streak"] = max(w_data.get("pvp_best_streak", 0), w_data["pvp_streak"])
        pts = points_for_win(w_data["pvp_streak"])
        old_pts = w_data.get("pvp_points", 0)
        w_data["pvp_points"] = old_pts + pts
        w_data["pvp_season_points"] = w_data.get("pvp_season_points", 0) + pts
        w_data["pvp_total_dmg_dealt"] = w_data.get("pvp_total_dmg_dealt", 0) + fight.total_dmg.get(winner.uid, 0)
        w_data["pvp_total_dmg_taken"] = w_data.get("pvp_total_dmg_taken", 0) + fight.total_dmg.get(loser.uid, 0)
        w_data["pvp_biggest_hit"] = max(w_data.get("pvp_biggest_hit", 0), fight.biggest_hit.get(winner.uid, 0))
        au = w_data.setdefault("pvp_ability_usage", {})
        for name, cnt in winner.used_ability_count.items():
            au[name] = au.get(name, 0) + cnt
        hist = w_data.setdefault("pvp_history", [])
        hist.insert(0, {"opponent": loser.name, "result": "win", "turns": fight.turn - 1, "ts": time.time()})
        w_data["pvp_history"] = hist[:10]
        w_data["hp"] = w_data.get("max_hp", 100)
        if fight.stake_p1_item and winner.uid == p1.uid:
            w_data.setdefault("inventory", []).append(fight.stake_p1_item)
        if fight.stake_p2_item and winner.uid == p2.uid:
            w_data.setdefault("inventory", []).append(fight.stake_p2_item)
        l_data["zen"] = max(0, l_data.get("zen", 0) - fight.stake_zen)
        l_data["xp"]  = max(0, l_data.get("xp", 0) - 20)
        l_data["pvp_losses"] = l_data.get("pvp_losses", 0) + 1
        l_data["pvp_streak"] = 0
        l_data["pvp_points"] = max(0, l_data.get("pvp_points", 0) + LOSE_POINTS)
        l_data["pvp_season_points"] = max(0, l_data.get("pvp_season_points", 0) + LOSE_POINTS)
        l_data["pvp_total_dmg_dealt"] = l_data.get("pvp_total_dmg_dealt", 0) + fight.total_dmg.get(loser.uid, 0)
        l_data["pvp_total_dmg_taken"] = l_data.get("pvp_total_dmg_taken", 0) + fight.total_dmg.get(winner.uid, 0)
        au = l_data.setdefault("pvp_ability_usage", {})
        for name, cnt in loser.used_ability_count.items():
            au[name] = au.get(name, 0) + cnt
        hist = l_data.setdefault("pvp_history", [])
        hist.insert(0, {"opponent": winner.name, "result": "loss", "turns": fight.turn - 1, "ts": time.time()})
        l_data["pvp_history"] = hist[:10]
        l_data["hp"] = max(1, l_data.get("max_hp", 100) // 2)

        # 🎯 سیستمِ تحت‌تعقیبِ خودکارِ روزانه — اگه برنده/بازنده امروز
        # هدفِ بانک بودن، جایزه/بدهی رو همینجا حساب می‌کنیم (قبل از سیوِ نهایی)
        from daily_wanted import resolve_pvp_result
        wanted_lines = await resolve_pvp_result(bot, w_data, winner.uid, l_data, loser.uid)

        from achievements import check_achievements
        winner_new_titles = check_achievements(w_data)
        save_player(winner.uid, w_data)
        save_player(loser.uid, l_data)

        new_league = league_for_points(w_data["pvp_points"])
        old_league = league_for_points(old_pts)

        epi_w = battle_epithet(winner, fight)
        epi_l = battle_epithet(loser, fight)

        result_lines += [
            battle_headline(fight, winner),
            "",
            f"👑 **برنده: {winner.name}** (Lv.{winner.level} | {winner.character})"
            + (f" — 🎖️ {epi_w}" if epi_w else ""),
            f"💀 بازنده: {loser.name} (Lv.{loser.level} | {loser.character})"
            + (f" — 🎖️ {epi_l}" if epi_l else ""),
            "",
            "📊 **آمارِ نبرد:**",
            f"• نوبت‌ها: {fight.turn - 1}" + (f" | ⚔️💥 کلش: {fight.clash_count}" if fight.clash_count else ""),
            f"• آسیبِ کلِ {winner.name}: {fight.total_dmg.get(winner.uid,0)}",
            f"• آسیبِ کلِ {loser.name}: {fight.total_dmg.get(loser.uid,0)}",
            f"• بیشترین ضربه: {fight.biggest_hit.get(winner.uid,0)}",
            f"• کریتیکال‌ها: {winner.name} {fight.crit_count.get(winner.uid,0)} — {loser.name} {fight.crit_count.get(loser.uid,0)}",
            f"• بیشترین کومبو: {winner.name} x{winner.max_combo} — {loser.name} x{loser.max_combo}",
        ]
        if winner.overdrive_count:
            result_lines.append(f"• اوردرایو: {winner.name} {winner.overdrive_count} بار")
        if winner.finisher_count:
            result_lines.append(f"• فینیشینگ‌بلو: {winner.name} {winner.finisher_count} بار")
        if loser.dodge_count:
            result_lines.append(f"• جاخالی‌های {loser.name}: {loser.dodge_count}")
        result_lines += [
            "",
            "🎁 **جوایز:**",
            f"💰 {winner.name}: +{zen_reward:,} Zen" + (f" + {fight.stake_zen:,} (شرط)" if fight.stake_zen else ""),
            f"✨ {winner.name}: +{xp_reward} XP",
            f"🏆 {winner.name}: +{pts} رنک‌پوینت",
            f"📈 برد #{w_data['pvp_wins']} (Streak: {w_data['pvp_streak']})",
        ] + ([f"🎯 **جایزه‌ی سرِ {loser.name} رو هم بردی: +{bounty_won:,} Zen!**"] if bounty_won > 0 else []) + [
            "",
            f"💀 {loser.name}: -{fight.stake_zen:,} Zen (شرط) | -20 XP | {LOSE_POINTS} رنک‌پوینت" if fight.stake_zen
            else f"💀 {loser.name}: -20 XP | {LOSE_POINTS} رنک‌پوینت",
        ]
        if new_league != old_league:
            result_lines.append(f"\n🏅 رنکِ جدیدِ {winner.name}: {old_league} → **{new_league}**")
        for t in winner_new_titles:
            result_lines.append(f"\n🏅 **{winner.name} یه عنوان جدید باز کرد: {t}**")
        result_lines += wanted_lines

        log_sync(
            f"🏆 **PVP FIGHT END**\n"
            f"👑 برنده: {winner.name} (`{winner.uid}`)\n"
            f"💀 بازنده: {loser.name} (`{loser.uid}`)\n"
            f"📊 نوبت‌ها: {fight.turn - 1}\n"
            f"💰 شرط: {fight.stake_zen:,}\n"
            f"🏅 رنک جدید برنده: {new_league}",
            "PVP"
        )

    result_lines.append("\n📊 برای دیدن آمارِ کامل: `/stats`")
    result_text = "\n".join(result_lines)

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔄 انتقام", callback_data="pvp_revenge_btn"),
        InlineKeyboardButton(text="📊 آمار کامل", callback_data="pvp_stats_btn"),
    ]])
    try:
        await bot.send_message(fight.chat_id, result_text, reply_markup=kb)
    except Exception:
        pass
    for uid in (p1.uid, p2.uid):
        try:
            # نکته‌ی گپ: uid داخلیه (منفی) → chat_id واقعی abs()
            await bot.send_message(abs(uid), result_text)
        except Exception:
            pass

    if new_league != old_league:
        try:
            import tempfile, os
            from profile_card import generate_moment_card
            out_path = os.path.join(tempfile.gettempdir(), f"leagueup_{winner.uid}.png")
            generate_moment_card(
                winner.name, "ارتقاءِ رنک!",
                f"{old_league} → {new_league}",
                out_path, accent=(120, 170, 240),
                footer=f"سطح {winner.level} · {w_data.get('pvp_wins',0)} برد PvP"
            )
            # نکته‌ی گپ: GapBotAdapter.send_photo مسیرِ فایل رو مستقیم می‌گیره
            # (نه یه آبجکتِ FSInputFile مثل تلگرام)
            await bot.send_photo(fight.chat_id, out_path)
        except Exception as e:
            log_sync(f"🔴 league-up moment card error: {e}", "ERROR")


# ────────────────────────────────────────────────────────────
# تسلیم‌شدن
# ────────────────────────────────────────────────────────────
async def cmd_forfeit(msg: Message, bot):
    uid = msg.from_user.id
    fight = get_fight_by_uid(uid)
    if not fight:
        await msg.answer("❌ الان توی هیچ فایتی نیستی.")
        return
    me = get_self(fight, uid)
    me.hp = 0
    
    log_sync(
        f"🏳️ **PVP FORFEIT**\n"
        f"👤 {msg.from_user.first_name} (`{uid}`)",
        "PVP"
    )
    
    await msg.answer("🏳️ تسلیم شدی...")
    await _end_fight(fight, bot)


# ────────────────────────────────────────────────────────────
# انتقام
# ────────────────────────────────────────────────────────────
async def cmd_revenge(msg: Message):
    uid = msg.from_user.id
    opp_id = last_opponent.get(uid)
    if not opp_id:
        await msg.answer("❌ هنوز با کسی مبارزه نکردی که ازش انتقام بگیری.")
        return
    if get_fight_by_uid(uid):
        await msg.answer("⚔️ الان توی یه فایتی!")
        return
    if get_fight_by_uid(opp_id):
        await msg.answer("❌ حریفِ قبلیت الان توی یه فایتِ دیگه‌ست.")
        return
    opp = get_player(opp_id)
    if not opp:
        await msg.answer("❌ اون بازیکن دیگه پیدا نشد.")
        return
    await _send_stake_prompt(msg, uid, opp_id, is_challenger=True)

async def cb_pvp_revenge_btn(cb: CallbackQuery):
    uid = cb.from_user.id
    opp_id = last_opponent.get(uid)
    if not opp_id:
        await cb.answer("❌ حریفی برای انتقام پیدا نشد.", show_alert=True)
        return
    if get_fight_by_uid(uid) or get_fight_by_uid(opp_id):
        await cb.answer("❌ یکی از دو طرف الان توی فایته.", show_alert=True)
        return
    await _send_stake_prompt(cb.message, uid, opp_id, is_challenger=True)
    await cb.answer()


# ────────────────────────────────────────────────────────────
# رنکینگ
# ────────────────────────────────────────────────────────────
async def cmd_rank(msg: Message):
    uid = msg.from_user.id
    players = gap_only_players(all_players())
    ranked = sorted(
        ((int(pid), p) for pid, p in players.items() if p.get("pvp_wins", 0) or p.get("pvp_points", 0)),
        key=lambda x: -x[1].get("pvp_points", 0)
    )
    lines = ["🏆 **رنکینگِ PvP — TOP ۱۰**\n"]
    medals = ["👑", "💎", "🌟", "🥇", "🥇", "🥈", "🥉", "🏅", "🏅", "🏅"]
    my_rank = None
    for i, (pid, p) in enumerate(ranked[:10]):
        pts = p.get("pvp_points", 0)
        league = league_for_points(pts)
        lines.append(f"{medals[i]} {i+1}. {p['name']} — {p.get('pvp_wins',0)} برد (Lv.{p.get('level',1)}) — {league}")
    for i, (pid, p) in enumerate(ranked):
        if pid == uid:
            my_rank = i + 1
            break
    if my_rank:
        lines.append(f"\n📊 تو رتبه: #{my_rank}")
        if my_rank > 1:
            gap = ranked[my_rank-2][1].get("pvp_points", 0) - ranked[my_rank-1][1].get("pvp_points", 0)
            lines.append(f"🎯 امتیازِ لازم برای رتبه‌ی بعدی: +{gap+1}")
    else:
        lines.append("\n📊 هنوز تو رنکینگ نیستی — یه دوئل ببر!")
    await msg.answer("\n".join(lines))


# ────────────────────────────────────────────────────────────
# آمار شخصی
# ────────────────────────────────────────────────────────────
async def _stats_text(uid: int) -> str:
    player = get_player(uid)
    if not player:
        return "❌ اول /start بزن!"
    wins   = player.get("pvp_wins", 0)
    losses = player.get("pvp_losses", 0)
    total  = wins + losses
    wr     = (wins / total * 100) if total else 0
    pts    = player.get("pvp_points", 0)
    league = league_for_points(pts)
    next_league, gap = next_league_gap(pts)

    au = player.get("pvp_ability_usage", {})
    au_lines = "\n".join(f"• {name}: {cnt} بار" for name, cnt in sorted(au.items(), key=lambda x: -x[1])[:5]) or "—"

    return (
        f"📊 **آمار PvP — {player['name']}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 **کلی:**\n"
        f"• کل مبارزات: {total}\n"
        f"• برد: {wins} ({wr:.1f}٪)\n"
        f"• باخت: {losses}\n"
        f"• Streak فعلی: {player.get('pvp_streak',0)} برد\n"
        f"• Best Streak: {player.get('pvp_best_streak',0)} برد\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💥 **آسیب:**\n"
        f"• کل آسیبِ زده: {player.get('pvp_total_dmg_dealt',0):,}\n"
        f"• بیشترین آسیب در یه ضربه: {player.get('pvp_biggest_hit',0):,}\n"
        f"• کل آسیبِ خورده: {player.get('pvp_total_dmg_taken',0):,}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🗡️ **Abilityهای پرکاربرد:**\n{au_lines}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 **رنکِ فعلی:** {league} ({pts} امتیاز)\n"
        + (f"📈 تا {next_league}: {gap} امتیاز مونده" if next_league else "📈 بالاترین رنک رو داری!")
        + (f"\n🏁 **بجِ فصلِ قبل:** {player['pvp_last_season_league']} (رتبه #{player.get('pvp_last_season_rank') or '—'})"
           if player.get("pvp_last_season_league") else "")
        + "\n\nاز /pvpseason وضعیتِ فصلِ فعلی رو ببین."
    )

async def cmd_stats(msg: Message):
    await msg.answer(await _stats_text(msg.from_user.id))

async def cb_pvp_stats_btn(cb: CallbackQuery):
    await cb.message.answer(await _stats_text(cb.from_user.id))
    await cb.answer()


# ────────────────────────────────────────────────────────────
# تاریخچه
# ────────────────────────────────────────────────────────────
async def cmd_history(msg: Message):
    player = get_player(msg.from_user.id)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    hist = player.get("pvp_history", [])
    if not hist:
        await msg.answer("📭 هنوز هیچ مبارزه‌ای نکردی.")
        return
    lines = ["📜 **تاریخچه‌ی ۱۰ مبارزه‌ی آخر:**\n"]
    for h in hist:
        icon = "✅" if h["result"] == "win" else "❌"
        lines.append(f"{icon} در برابرِ {h['opponent']} — {h['turns']} نوبت")
    await msg.answer("\n".join(lines))


# ────────────────────────────────────────────────────────────
# سیزن‌پسِ PvP — /pvpseason
# ────────────────────────────────────────────────────────────
async def cmd_pvpseason(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return

    from database import system_col

    season_doc = system_col().find_one({"_id": "pvp_season_meta"}) or {"season_num": 0}
    season_num = season_doc.get("season_num", 0) + 1  # فصلِ در حالِ اجرا

    season_pts = player.get("pvp_season_points", 0)
    league = league_for_points(season_pts)
    projected = season_reward_for_league(league)

    lines = [
        f"🗓️ **فصلِ #{season_num} PvP در حالِ اجراست**\n",
        f"⚔️ امتیازِ این فصل: {season_pts:,}",
        f"👑 لیگِ فعلی: {league}",
        f"🎁 جایزه‌ی تخمینیِ پایانِ فصل (اگه الان تموم بشه): +{projected:,} Zen",
    ]

    hist = player.get("pvp_season_history", [])
    if hist:
        lines.append("\n📜 **۳ فصلِ آخر:**")
        for h in reversed(hist[-3:]):
            lines.append(
                f"• فصل #{h['season']} — رتبه #{h['rank']} — {h['league']} "
                f"({h['points']:,} امتیاز) — +{h['reward']:,} Zen"
            )
    else:
        lines.append("\n📭 هنوز هیچ فصلی تموم نکردی.")

    await msg.answer("\n".join(lines))


# ────────────────────────────────────────────────────────────
# Register
# ────────────────────────────────────────────────────────────
def register_gap_pvp_handlers(dp: GapDispatcher):
    # bot اینجا یه‌بار از dp گرفته می‌شه و به همون شکلِ قبلی (closure) به
    # تابع‌های داخلی پاس داده می‌شه — چون این توابع پس‌زمینه‌ای‌ن (تایمرها،
    # حل‌شدنِ نوبت) و مستقیم به یه cb/msg وصل نیستن که bot رو از توش دربیارن.
    bot = dp.bot

    dp.register_message(cmd_arena, commands=["arena", "pvp"], text="PvP")
    dp.register_message(cmd_duel,      commands=["duel"])
    dp.register_message(cmd_track,     commands=["track"])
    dp.register_message(cmd_rank,      commands=["rank"])
    dp.register_message(cmd_stats,     commands=["stats"])
    dp.register_message(cmd_history,   commands=["history"])
    dp.register_message(cmd_pvpseason, commands=["pvpseason"])
    dp.register_message(cmd_revenge,   commands=["revenge"])

    async def _w_forfeit(m): await cmd_forfeit(m, bot)
    dp.register_message(_w_forfeit, commands=["forfeit"])

    async def _w_pvp_challenge(c): await cb_pvp_challenge(c, bot)
    async def _w_pvp_stakeset(c): await cb_pvp_stakeset(c, bot)
    async def _w_pvp_accept(c): await cb_pvp_accept(c, bot)
    async def _w_pvp_reject(c): await cb_pvp_reject(c, bot)
    async def _w_pvp_menu_back(c): await cb_pvp_menu_back(c, bot)
    async def _w_fight_attack(c): await cb_fight_attack(c, bot)
    async def _w_fight_defend(c): await cb_fight_defend(c, bot)
    async def _w_fight_ability(c): await cb_fight_ability(c, bot)

    dp.register_callback(_w_pvp_challenge, data_startswith="pvp_challenge:")
    dp.register_callback(_w_pvp_stakeset,  data_startswith="pvp_stakeset:")
    dp.register_callback(_w_pvp_accept,    data_startswith="pvp_accept:")
    dp.register_callback(_w_pvp_reject,    data_startswith="pvp_reject:")
    dp.register_callback(_w_pvp_menu_back, data="pvp_menu_back")
    dp.register_callback(cb_pvp_close,        data="pvp_close")
    dp.register_callback(cb_pvp_revenge_btn,  data="pvp_revenge_btn")
    dp.register_callback(cb_pvp_stats_btn,    data="pvp_stats_btn")

    dp.register_callback(_w_fight_attack,  data_startswith="pvpfight_atk:")
    dp.register_callback(_w_fight_defend,  data_startswith="pvpfight_def:")
    dp.register_callback(_w_fight_ability, data_startswith="pvpfight_ab:")
