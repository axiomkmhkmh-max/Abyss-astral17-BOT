# ============================================================
#  ASTRAL ABYSS RPG — Guild Handlers (Telegram UI) v2 (با لاگ‌گذاری کامل)
#  گیلدها با کوئست‌های چندمرحله‌ای روایی، آزمون ارتقای رتبه، اکشن یکتا
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
import time, random

from database import get_player, save_player
from logger import log_sync
import guild_system as gs

BOSS_ATK_COOLDOWN = 20  # ثانیه بین هر ضربه به رئیس گیلد

# ─── helpers ─────────────────────────────────────────────────
def _owner_ok(cb: CallbackQuery, uid: int) -> bool:
    return cb.from_user.id == uid

async def _edit_or_send(cb: CallbackQuery, text: str, kb: InlineKeyboardMarkup):
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)

def _check_levelup(player: dict) -> str:
    """باگ‌فیکس: XP گیلد (پاداش کوئست/آزمون رتبه) هیچ‌وقت چک لول‌آپ رو صدا نمی‌زد.
    این تابع بعد از هر جایی که guild_system مستقیم به player['xp'] اضافه می‌کنه صدا زده می‌شه."""
    from bot import level_up_check
    player, leveled = level_up_check(player)
    if leveled:
        log_sync(
            f"⭐ **LEVEL UP (GUILD)**\n"
            f"👤 {player.get('name','—')} (`{player.get('id','—')}`)\n"
            f"📊 سطح: {player['level']}",
            "LEVELUP"
        )
        return f"\n\n🎉 **LEVEL UP! → {player['level']}**"
    return ""


def _guild_list_text_kb(player: dict, uid: int):
    lines = ["🏛 **گیلدهای Astral Abyss**\nهر گیلد یه دنیای جداست: رتبه‌بندی، آزمون ارتقا، کوئست‌های روایی و یه اکشن یکتا.\n"]
    buttons = []
    for gid, g in gs.GUILDS.items():
        joined = gid in player.get("guilds", {})
        if joined:
            rank = player["guilds"][gid].get("rank", "G")
            tag = f"✅ رتبه {rank}"
        else:
            tag = "🔓 پیوستن"
        lines.append(f"{g['emoji']} **{g['name']}** — {g['desc']}\n")
        buttons.append([InlineKeyboardButton(
            text=f"{g['emoji']} {g['name']} ({tag})",
            callback_data=f"guild_open:{gid}:{uid}"
        , style=ButtonStyle.PRIMARY)])
    buttons.append([InlineKeyboardButton(text="🪪 کارت شناسایی گیلدی", callback_data=f"guild_card:{uid}", style=ButtonStyle.PRIMARY)])
    return "".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)


def _fmt_seconds(s: int) -> str:
    m = s // 60
    return f"{m} دقیقه" if m > 0 else f"{s} ثانیه"


def _guild_home_text_kb(player: dict, uid: int, gid: str):
    g = gs.GUILDS[gid]
    joined = gid in player.get("guilds", {})

    if not joined:
        text = f"{g['emoji']} **{g['name']}**\n\n{g['desc']}\n\nهنوز عضو این گیلد نیستی."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔓 پیوستن به گیلد", callback_data=f"guild_join:{gid}:{uid}", style=ButtonStyle.SUCCESS)],
            [InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"guild_back:{uid}", style=ButtonStyle.PRIMARY)],
        ])
        return text, kb

    gdata = player["guilds"][gid]
    rank = gdata.get("rank", "G")
    next_idx = gs.RANKS.index(rank) + 1
    next_rank = gs.RANKS[next_idx] if next_idx < len(gs.RANKS) else None
    if next_rank:
        need = max(0, gs.RANK_UP_CONTRIB[next_rank] - gdata.get("contribution", 0))
        cur_need, next_need = gs.RANK_UP_CONTRIB[rank], gs.RANK_UP_CONTRIB[next_rank]
        pct = (gdata.get("contribution", 0) - cur_need) / max(1, next_need - cur_need)
        prog_txt = f"{gs.bar(pct)}\n📈 امتیاز: {gdata.get('contribution',0):,} (تا رتبه بعد: {need:,} کم داره)"
    else:
        prog_txt = f"{gs.bar(1.0)}\n📈 امتیاز: {gdata.get('contribution',0):,} — رتبه ماکسیمم!"

    text = (
        f"{g['emoji']} **{g['name']}**\n{g['desc']}\n\n"
        f"🎖 رتبه: **{rank}** — {gs.RANK_NAMES_FA[rank]} (بونوس: +{gs.RANK_BONUS_PCT[rank]}%)\n"
        f"{prog_txt}\n"
        f"✅ کوئست‌های تکمیل‌شده: {gdata.get('quests_done',0)}\n"
        f"{gs.perks_summary_text(player)}\n"
    )

    buttons = []
    active_q = gdata.get("active_quest")
    if active_q:
        stage = gs.current_stage(player, gid)
        text += f"\n📜 **کوئست فعال:** {active_q['title']}\n➡️ {stage['narrative']}"
        if stage["kind"] == "choice":
            for i, opt in enumerate(stage["options"]):
                buttons.append([InlineKeyboardButton(text=opt["label"], callback_data=f"guild_choice:{gid}:{i}:{uid}", style=ButtonStyle.PRIMARY)])
        elif stage["kind"] in ("kill", "gather", "zen", "level"):
            cur, target, ready = gs.stage_progress(player, gid)
            text += f"\n➡️ پیشرفت: {cur}/{target}"
            btxt = "🎁 تحویل و دریافت پاداش" if ready else "🔄 بررسی پیشرفت"
            buttons.append([InlineKeyboardButton(text=btxt, callback_data=f"guild_advance:{gid}:{uid}", style=ButtonStyle.PRIMARY)])
        else:
            buttons.append([InlineKeyboardButton(text="▶️ ادامه", callback_data=f"guild_advance:{gid}:{uid}", style=ButtonStyle.PRIMARY)])
        buttons.append([InlineKeyboardButton(text="🗑 لغو کوئست", callback_data=f"guild_cancel:{gid}:{uid}", style=ButtonStyle.DANGER)])
    else:
        text += "\nهیچ کوئست فعالی نداری."
        buttons.append([InlineKeyboardButton(text="📋 تابلوی کوئست", callback_data=f"guild_board:{gid}:{uid}", style=ButtonStyle.PRIMARY)])

    ready, reason = gs.trial_ready(player, gid)
    if ready:
        buttons.append([InlineKeyboardButton(text="🎖 آزمون ارتقای رتبه!", callback_data=f"guild_trial:{gid}:{uid}", style=ButtonStyle.SUCCESS)])
    elif next_rank:
        text += f"\n\n🔒 آزمون رتبه {next_rank}: {reason}"

    act_ready, remain = gs.action_ready(player, gid)
    act = g["action"]
    act_label = f"{act['emoji']} {act['name']}" if act_ready else f"{act['emoji']} {act['name']} ({_fmt_seconds(remain)})"
    buttons.append([InlineKeyboardButton(text=act_label, callback_data=f"guild_action:{gid}:{uid}", style=ButtonStyle.PRIMARY)])
    buttons.append([InlineKeyboardButton(text="🏪 فروشگاه گیلد", callback_data=f"guild_shop:{gid}:{uid}", style=ButtonStyle.DANGER)])
    buttons.append([InlineKeyboardButton(text="🏺 صندوق مشترک گیلد", callback_data=f"guild_treasury:{gid}:{uid}", style=ButtonStyle.SUCCESS)])
    if gs.guild_boss_unlocked(player, gid):
        buttons.append([InlineKeyboardButton(text="👹 رئیس گیلد", callback_data=f"guild_boss:{gid}:{uid}", style=ButtonStyle.PRIMARY)])
    else:
        buttons.append([InlineKeyboardButton(
            text=f"🔒 رئیس گیلد (رتبه {gs.GUILD_BOSS_MIN_RANK} لازمه)", callback_data=f"guild_boss_locked:{uid}", style=ButtonStyle.PRIMARY)])
    buttons.append([InlineKeyboardButton(text="⚔️ جنگ هفتگی گیلدها", callback_data=f"guild_war:{gid}:{uid}", style=ButtonStyle.DANGER)])

    buttons.append([InlineKeyboardButton(text="👋 خروج از گیلد", callback_data=f"guild_leave:{gid}:{uid}", style=ButtonStyle.DANGER)])
    buttons.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"guild_back:{uid}", style=ButtonStyle.PRIMARY)])
    return text, InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── entry points ────────────────────────────────────────────
async def cmd_guilds(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    from level_gate import check_level
    ok, why = check_level(player, "guilds")
    if not ok:
        await msg.answer(why)
        return
    gs.ensure_guild_data(player)
    save_player(uid, player)
    text, kb = _guild_list_text_kb(player, uid)
    await msg.answer(text, reply_markup=kb)


async def cmd_guildcard(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    await msg.answer(gs.guild_card_text(player))


# ─── callbacks ───────────────────────────────────────────────
async def cb_guild_open(cb: CallbackQuery):
    gid, uid = cb.data.split(":")[1], int(cb.data.split(":")[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌ این گیلد مال تو نیست!", show_alert=True)
        return
    player = get_player(uid)
    if not player:
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return
    gs.ensure_guild_data(player)
    save_player(uid, player)
    text, kb = _guild_home_text_kb(player, uid, gid)
    await _edit_or_send(cb, text, kb)
    await cb.answer()

async def cb_guild_back(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    gs.ensure_guild_data(player)
    save_player(uid, player)
    text, kb = _guild_list_text_kb(player, uid)
    await _edit_or_send(cb, text, kb)
    await cb.answer()

async def cb_guild_card(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    await cb.message.answer(gs.guild_card_text(player))
    await cb.answer()

async def cb_guild_join(cb: CallbackQuery):
    gid, uid = cb.data.split(":")[1], int(cb.data.split(":")[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    ok, msg = gs.join_guild(player, gid)
    save_player(uid, player)
    
    if ok:
        log_sync(
            f"🏛 **GUILD JOIN**\n"
            f"👤 {player.get('name','—')} (`{uid}`)\n"
            f"🏛 گیلد: {gs.GUILDS[gid]['name']}",
            "GUILD"
        )
    
    await cb.answer("عضو شدی!" if ok else msg.replace("*", ""), show_alert=True)
    if ok:
        await cb.message.answer(msg)
        text, kb = _guild_home_text_kb(player, uid, gid)
        await _edit_or_send(cb, text, kb)

async def cb_guild_leave(cb: CallbackQuery):
    gid, uid = cb.data.split(":")[1], int(cb.data.split(":")[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    ok, msg = gs.leave_guild(player, gid)
    save_player(uid, player)
    
    if ok:
        log_sync(
            f"🏛 **GUILD LEAVE**\n"
            f"👤 {player.get('name','—')} (`{uid}`)\n"
            f"🏛 گیلد: {gs.GUILDS[gid]['name']}",
            "GUILD"
        )
    
    await cb.answer(msg, show_alert=True)
    if ok:
        text, kb = _guild_home_text_kb(player, uid, gid)
        await _edit_or_send(cb, text, kb)

async def cb_guild_board(cb: CallbackQuery):
    gid, uid = cb.data.split(":")[1], int(cb.data.split(":")[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    if gid not in player.get("guilds", {}):
        await cb.answer("❌ اول عضو گیلد شو!", show_alert=True)
        return
    quests = gs.offer_quests(player, gid, n=3)
    g = gs.GUILDS[gid]
    lines = [f"📋 **تابلوی کوئست {g['name']}**\n🗣 *{g['npc']}*: «یکی از این‌ها رو بردار:»\n\n"]
    buttons = []
    for q in quests:
        n_stages = len(q["stages"])
        lines.append(f"**{q['title']}**\n📖 {n_stages} مرحله‌ی روایی\n\n")
        buttons.append([InlineKeyboardButton(text=q["title"][:40], callback_data=f"guild_accept:{gid}:{q['id']}:{uid}", style=ButtonStyle.PRIMARY)])
    buttons.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"guild_open:{gid}:{uid}", style=ButtonStyle.PRIMARY)])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    player.setdefault("_guild_quest_offers", {})[gid] = {q["id"]: q for q in quests}
    save_player(uid, player)
    await _edit_or_send(cb, "".join(lines), kb)
    await cb.answer()

async def cb_guild_accept(cb: CallbackQuery):
    parts = cb.data.split(":")
    gid, qid, uid = parts[1], parts[2], int(parts[3])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    offers = player.get("_guild_quest_offers", {}).get(gid, {})
    quest = offers.get(qid)
    if not quest:
        await cb.answer("❌ این پیشنهاد منقضی شده، تابلو رو دوباره باز کن.", show_alert=True)
        return
    ok, msg = gs.accept_quest(player, gid, quest)
    if gid in player.get("_guild_quest_offers", {}):
        del player["_guild_quest_offers"][gid]
    save_player(uid, player)
    
    if ok:
        log_sync(
            f"📋 **GUILD QUEST ACCEPT**\n"
            f"👤 {player.get('name','—')} (`{uid}`)\n"
            f"🏛 گیلد: {gs.GUILDS[gid]['name']}\n"
            f"📋 کوئست: {quest['title']}",
            "GUILD"
        )
    
    await cb.answer("پذیرفته شد!" if ok else msg, show_alert=True)
    if ok:
        text, kb = _guild_home_text_kb(player, uid, gid)
        await _edit_or_send(cb, text, kb)

async def cb_guild_choice(cb: CallbackQuery):
    parts = cb.data.split(":")
    gid, opt_idx, uid = parts[1], int(parts[2]), int(parts[3])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    ok, msg = gs.choose_option(player, gid, opt_idx)
    save_player(uid, player)
    
    if ok:
        log_sync(
            f"🎯 **GUILD CHOICE**\n"
            f"👤 {player.get('name','—')} (`{uid}`)\n"
            f"🏛 گیلد: {gs.GUILDS[gid]['name']}\n"
            f"📋 انتخاب: {msg[:50]}...",
            "GUILD"
        )
    
    await cb.answer()
    if ok:
        await cb.message.answer(msg)
    text, kb = _guild_home_text_kb(player, uid, gid)
    await _edit_or_send(cb, text, kb)

async def cb_guild_advance(cb: CallbackQuery):
    gid, uid = cb.data.split(":")[1], int(cb.data.split(":")[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    ok, msg, done = gs.advance_quest(player, gid)
    if done:
        msg += _check_levelup(player)
    save_player(uid, player)
    
    if done:
        log_sync(
            f"✅ **GUILD QUEST COMPLETE**\n"
            f"👤 {player.get('name','—')} (`{uid}`)\n"
            f"🏛 گیلد: {gs.GUILDS[gid]['name']}\n"
            f"📋 پاداش: {msg[:100]}...",
            "GUILD"
        )
    
    if done:
        await cb.message.answer(msg)
        await cb.answer("🎉 تموم شد!", show_alert=True)
    elif ok:
        await cb.answer(msg[:190], show_alert=True)
    else:
        await cb.answer(msg, show_alert=True)
    text, kb = _guild_home_text_kb(player, uid, gid)
    await _edit_or_send(cb, text, kb)

async def cb_guild_cancel(cb: CallbackQuery):
    gid, uid = cb.data.split(":")[1], int(cb.data.split(":")[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    ok, msg = gs.cancel_quest(player, gid)
    save_player(uid, player)
    
    if ok:
        log_sync(
            f"🗑 **GUILD QUEST CANCEL**\n"
            f"👤 {player.get('name','—')} (`{uid}`)\n"
            f"🏛 گیلد: {gs.GUILDS[gid]['name']}",
            "GUILD"
        )
    
    await cb.answer(msg, show_alert=True)
    text, kb = _guild_home_text_kb(player, uid, gid)
    await _edit_or_send(cb, text, kb)

async def cb_guild_trial(cb: CallbackQuery):
    """اولین بار: نمایش پیش‌نمایش آزمون + دکمه‌ی تأیید."""
    gid, uid = cb.data.split(":")[1], int(cb.data.split(":")[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    ready, reason = gs.trial_ready(player, gid)
    if not ready:
        await cb.answer(f"❌ {reason}", show_alert=True)
        return
    prev = gs.trial_preview(player, gid)
    g = gs.GUILDS[gid]
    text = (
        f"🎖 **آزمون ارتقا به رتبه {prev['next_rank']}**\n\n"
        f"🗣 *{g['npc']}*: «{prev['narrative']}»\n\n"
        f"🎲 شانس موفقیت تخمینی: **{prev['chance']}%**\n"
        f"در صورت شکست، باید کمی صبر کنی و دوباره تلاش کنی.\n\n"
        f"آماده‌ای وارد آزمون بشی؟"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ شروع آزمون!", callback_data=f"guild_trial_go:{gid}:{uid}", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="◀️ بی‌خیال", callback_data=f"guild_open:{gid}:{uid}", style=ButtonStyle.PRIMARY)],
    ])
    await _edit_or_send(cb, text, kb)
    await cb.answer()

async def cb_guild_trial_go(cb: CallbackQuery):
    gid, uid = cb.data.split(":")[1], int(cb.data.split(":")[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    ok, msg = gs.attempt_trial(player, gid)
    if ok:
        msg += _check_levelup(player)
    save_player(uid, player)
    
    log_sync(
        f"🎖 **GUILD TRIAL**\n"
        f"👤 {player.get('name','—')} (`{uid}`)\n"
        f"🏛 گیلد: {gs.GUILDS[gid]['name']}\n"
        f"📊 نتیجه: {'✅ موفق' if ok else '❌ شکست'}\n"
        f"📋 {msg[:100]}...",
        "GUILD"
    )
    
    await cb.message.answer(msg)
    await cb.answer("🎉 قبول شدی!" if ok else "💥 شکست خوردی...", show_alert=True)
    text, kb = _guild_home_text_kb(player, uid, gid)
    await _edit_or_send(cb, text, kb)

async def cb_guild_action(cb: CallbackQuery):
    gid, uid = cb.data.split(":")[1], int(cb.data.split(":")[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    ok, msg = gs.do_guild_action(player, gid)
    save_player(uid, player)
    
    log_sync(
        f"⚡ **GUILD ACTION**\n"
        f"👤 {player.get('name','—')} (`{uid}`)\n"
        f"🏛 گیلد: {gs.GUILDS[gid]['name']}\n"
        f"📋 اکشن: {msg[:100]}...",
        "GUILD"
    )
    
    await cb.message.answer(msg)
    await cb.answer()
    text, kb = _guild_home_text_kb(player, uid, gid)
    await _edit_or_send(cb, text, kb)


# ─── 🏪 فروشگاه گیلد ───────────────────────────────────────────
def _shop_text_kb(player: dict, gid: str, uid: int):
    gdata = player["guilds"][gid]
    g = gs.GUILDS[gid]
    items = gs.get_shop_items(gid)
    lines = [
        f"🏪 **فروشگاه {g['name']}**\n"
        f"📈 امتیاز مشارکت تو: {gdata.get('contribution',0):,}\n"
    ]
    buttons = []
    for it in items:
        afford = "✅" if gdata.get("contribution", 0) >= it["cost"] else "🔒"
        lines.append(f"\n{afford} **{it['name']}** — {it['cost']} امتیاز\n   {it['desc']}")
        buttons.append([InlineKeyboardButton(
            text=f"{it['name']} ({it['cost']})", callback_data=f"guild_shop_buy:{gid}:{it['id']}:{uid}"
        , style=ButtonStyle.PRIMARY)])
    buttons.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"guild_open:{gid}:{uid}", style=ButtonStyle.PRIMARY)])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)


async def cb_guild_shop(cb: CallbackQuery):
    gid, uid = cb.data.split(":")[1], int(cb.data.split(":")[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    if gid not in player.get("guilds", {}):
        await cb.answer("❌ عضو این گیلد نیستی.", show_alert=True)
        return
    text, kb = _shop_text_kb(player, gid, uid)
    await cb.answer()
    await _edit_or_send(cb, text, kb)


async def cb_guild_shop_buy(cb: CallbackQuery):
    parts = cb.data.split(":")
    gid, item_id, uid = parts[1], parts[2], int(parts[3])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    ok, msg = gs.buy_shop_item(player, gid, item_id)
    save_player(uid, player)
    if ok:
        log_sync(
            f"🏪 **GUILD SHOP BUY**\n👤 {player.get('name','—')} (`{uid}`)\n"
            f"🏛 گیلد: {gs.GUILDS[gid]['name']}\n🛒 {item_id}", "GUILD"
        )
    await cb.answer(msg if not ok else "✅ خریداری شد!", show_alert=True)
    text, kb = _shop_text_kb(player, gid, uid)
    await _edit_or_send(cb, text, kb)


# ─── 🏺 صندوق مشترک گیلد ────────────────────────────────────────
_awaiting_donation: dict[int, tuple[str, float]] = {}   # uid -> (guild_id, ttl)
DONATE_TTL = 120


def _treasury_text_kb(gid: str, uid: int):
    g = gs.GUILDS[gid]
    doc = gs.get_treasury(gid)
    top = gs.treasury_top_contributors(gid, 5)
    infra_level = gs.get_infra_level(gid)
    infra_bonus = gs.get_infra_bonus_pct(gid)
    lines = [
        f"🏺 **صندوقِ مشترکِ {g['name']}**\n",
        f"💰 موجودیِ فعلی: **{doc.get('zen',0):,} Zen**",
        f"📈 مجموعِ کمک‌های تاریخی: {doc.get('total_alltime',0):,} Zen",
        f"🏛 زیرساخت: سطح {infra_level}/{gs.INFRA_MAX_LEVEL} (بونوسِ دائمی: +{infra_bonus}٪)\n",
    ]
    rally_bonus = gs.get_rally_bonus_pct(gid)
    if rally_bonus:
        lines.append(f"🔥 روحیه‌ی گروهی الان فعاله: **+{rally_bonus}٪** به کامبت/لوت/تجارت/فورج/درمان همه‌ی اعضا!\n")
    else:
        lines.append(f"با رسیدنِ صندوق به **{gs.RALLY_COST:,} Zen**، هر عضوی می‌تونه «روحیه‌ی گروهی» رو فعال کنه:\n"
                      f"+{gs.RALLY_BONUS_PCT}٪ بونوس برای همه‌ی اعضا به‌مدتِ {gs.RALLY_DURATION_SEC//3600} ساعت.\n")
    if infra_level < gs.INFRA_MAX_LEVEL:
        next_cost = gs.infra_cost(infra_level + 1)
        next_name = gs.INFRA_LEVEL_NAMES[infra_level]
        lines.append(
            f"🏛 ارتقای بعدیِ زیرساخت («{next_name}»): {next_cost:,} Zen — "
            f"**دائمی** و برای همیشه (برخلافِ روحیه‌ی گروهی که موقتیه).\n"
        )
    if top:
        lines.append("🏆 **بزرگ‌ترین کمک‌کننده‌ها:**")
        for i, (uid_s, amt) in enumerate(top):
            lines.append(f"  {i+1}. `{uid_s}` — {amt:,} Zen")

    buttons = [[InlineKeyboardButton(text="💝 کمک به صندوق", callback_data=f"guild_treasury_donate:{gid}:{uid}", style=ButtonStyle.SUCCESS)]]
    ready, _reason = gs.rally_ready(gid)
    if ready:
        buttons.append([InlineKeyboardButton(text=f"🔥 فعال‌کردنِ روحیه‌ی گروهی ({gs.RALLY_COST:,})", callback_data=f"guild_treasury_rally:{gid}:{uid}", style=ButtonStyle.DANGER)])
    infra_ready, _ = gs.infra_upgrade_ready(gid)
    if infra_ready:
        next_cost = gs.infra_cost(infra_level + 1)
        buttons.append([InlineKeyboardButton(text=f"🏛 ارتقای دائمیِ زیرساخت ({next_cost:,})", callback_data=f"guild_treasury_infra:{gid}:{uid}", style=ButtonStyle.DANGER)])
    buttons.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"guild_open:{gid}:{uid}", style=ButtonStyle.PRIMARY)])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)


async def cb_guild_treasury(cb: CallbackQuery):
    gid, uid = cb.data.split(":")[1], int(cb.data.split(":")[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    if gid not in player.get("guilds", {}):
        await cb.answer("❌ عضو این گیلد نیستی.", show_alert=True)
        return
    text, kb = _treasury_text_kb(gid, uid)
    await cb.answer()
    await _edit_or_send(cb, text, kb)


async def cb_guild_treasury_donate(cb: CallbackQuery):
    gid, uid = cb.data.split(":")[1], int(cb.data.split(":")[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    _awaiting_donation[uid] = (gid, time.time() + DONATE_TTL)
    await cb.message.answer("💝 چقدر Zen به صندوق کمک می‌کنی؟ فقط عددشو بفرست.")
    await cb.answer()


async def handle_treasury_donation_text(msg: Message):
    uid = msg.from_user.id
    entry = _awaiting_donation.get(uid)
    if not entry:
        return
    gid, expires = entry
    if time.time() > expires:
        del _awaiting_donation[uid]
        await msg.answer("⏰ زمان تموم شد، دوباره از منوی صندوق شروع کن.")
        return
    del _awaiting_donation[uid]

    text = (msg.text or "").strip()
    if not (text.isdigit() and int(text) > 0):
        await msg.answer("❌ باید یه عددِ مثبت بفرستی!")
        return
    amount = int(text)
    player = get_player(uid)
    ok, res_msg = gs.contribute_treasury(player, gid, amount)
    save_player(uid, player)
    await msg.answer(res_msg)
    if ok:
        log_sync(
            f"🏺 **GUILD TREASURY DONATE**\n👤 {player.get('name','—')} (`{uid}`)\n"
            f"🏛 گیلد: {gs.GUILDS[gid]['name']}\n💰 {amount:,} Zen", "GUILD"
        )


async def cb_guild_treasury_rally(cb: CallbackQuery):
    gid, uid = cb.data.split(":")[1], int(cb.data.split(":")[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    if gid not in player.get("guilds", {}):
        await cb.answer("❌ عضو این گیلد نیستی.", show_alert=True)
        return
    ok, res_msg = gs.start_rally(gid)
    if ok:
        log_sync(f"🔥 **GUILD RALLY**\n👤 {player.get('name','—')} (`{uid}`)\n🏛 گیلد: {gs.GUILDS[gid]['name']}", "GUILD")
    await cb.answer(res_msg if not ok else "🔥 فعال شد!", show_alert=True)
    text, kb = _treasury_text_kb(gid, uid)
    await _edit_or_send(cb, text, kb)


async def cb_guild_treasury_infra(cb: CallbackQuery):
    gid, uid = cb.data.split(":")[1], int(cb.data.split(":")[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    if gid not in player.get("guilds", {}):
        await cb.answer("❌ عضو این گیلد نیستی.", show_alert=True)
        return
    ok, res_msg = gs.buy_infra_upgrade(player, gid)
    if ok:
        log_sync(
            f"🏛 **GUILD INFRA UPGRADE**\n👤 {player.get('name','—')} (`{uid}`)\n"
            f"🏛 گیلد: {gs.GUILDS[gid]['name']} → سطح {gs.get_infra_level(gid)}", "GUILD"
        )
    await cb.answer(res_msg[:200], show_alert=True)
    text, kb = _treasury_text_kb(gid, uid)
    await _edit_or_send(cb, text, kb)


# ─── ⚔️ جنگ هفتگی گیلدها ───────────────────────────────────────
async def cmd_guildwar(msg: Message):
    await msg.answer(gs.war_status_text())


async def cb_guild_war(cb: CallbackQuery):
    gid, uid = cb.data.split(":")[1], int(cb.data.split(":")[2])
    text = gs.war_status_text()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺 نقشه‌ی جنگ (حمله/گاریزون)", callback_data=f"gw_map:{uid}", style=ButtonStyle.DANGER)],
        [InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"guild_open:{gid}:{uid}", style=ButtonStyle.PRIMARY)]
    ])
    await cb.answer()
    await _edit_or_send(cb, text, kb)


# ─── 👹 رئیس اختصاصی گیلد ───────────────────────────────────────
async def cb_guild_boss_locked(cb: CallbackQuery):
    await cb.answer(f"🔒 برای جنگ با رئیس گیلد، حداقل رتبه {gs.GUILD_BOSS_MIN_RANK} لازمه.", show_alert=True)


def _boss_kb(gid: str, uid: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ ضربه بزن", callback_data=f"guild_boss_hit:{gid}:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"guild_open:{gid}:{uid}", style=ButtonStyle.PRIMARY)],
    ])


async def cb_guild_boss(cb: CallbackQuery):
    gid, uid = cb.data.split(":")[1], int(cb.data.split(":")[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    if not gs.guild_boss_unlocked(player, gid):
        await cb.answer(f"🔒 حداقل رتبه {gs.GUILD_BOSS_MIN_RANK} لازمه.", show_alert=True)
        return
    text = gs.guild_boss_status_text(gid)
    await cb.answer()
    await _edit_or_send(cb, text, _boss_kb(gid, uid))


async def cb_guild_boss_hit(cb: CallbackQuery):
    gid, uid = cb.data.split(":")[1], int(cb.data.split(":")[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    if not gs.guild_boss_unlocked(player, gid):
        await cb.answer(f"🔒 حداقل رتبه {gs.GUILD_BOSS_MIN_RANK} لازمه.", show_alert=True)
        return

    gdata = player["guilds"][gid]
    remain = int(gdata.get("boss_atk_cooldown", 0) - time.time())
    if remain > 0:
        await cb.answer(f"⏳ {remain} ثانیه‌ی دیگه دوباره ضربه بزن.", show_alert=True)
        return
    gdata["boss_atk_cooldown"] = time.time() + BOSS_ATK_COOLDOWN

    from characters import ALL_CHARACTERS
    from economy import KATANA_LEVELS
    char = ALL_CHARACTERS.get(player.get("character", ""), {})
    base_dmg = char.get("base_dmg", 12)
    katana_bonus = KATANA_LEVELS.get(player.get("katana_level", 1), {}).get("dmg", 0)
    dmg_pct = gs.get_perk(player, "pve_dmg_pct")
    dmg = int((base_dmg + player.get("level", 1) * 3 + katana_bonus + random.randint(0, 15)) * (1 + dmg_pct))

    boss, killed = gs.guild_boss_attack(player, gid, dmg)
    save_player(uid, player)

    log_sync(
        f"👹 **GUILD BOSS HIT**\n👤 {player.get('name','—')} (`{uid}`)\n"
        f"🏛 گیلد: {gs.GUILDS[gid]['name']}\n💥 دمیج: {dmg:,}\n❤️ HP باس: {boss['hp']:,}/{boss['max_hp']:,}",
        "GUILD"
    )

    if killed:
        rewards = gs.guild_boss_rewards(gid, boss)
        for p_uid_s, r in rewards["per_player"].items():
            p_uid = int(p_uid_s)
            p = get_player(p_uid)
            if not p:
                continue
            p["zen"] = p.get("zen", 0) + r["zen"]
            p["xp"] = p.get("xp", 0) + r["xp"]
            pgdata = p.get("guilds", {}).get(gid)
            if pgdata:
                pgdata["contribution"] = pgdata.get("contribution", 0) + r["contribution"]
            if p_uid_s == rewards["top_uid"]:
                from item_system import generate_item
                loot = generate_item(
                    {"name": rewards["loot_name"], "emoji": "👑", "slot": rewards["loot_slot"], "sell": 4000},
                    p.get("level", 1), forced_rarity="legendary", drop_source="guild_boss",
                )
                p.setdefault("inventory", []).append(loot)
            save_player(p_uid, p)
        log_sync(
            f"🎉 **GUILD BOSS KILLED**\n🏛 گیلد: {gs.GUILDS[gid]['name']}\n"
            f"👥 {len(rewards['per_player'])} نفر مشارکت داشتن\n"
            f"👑 برترین ضربه‌زن: `{rewards['top_uid']}` → {rewards['loot_name']}",
            "GUILD"
        )
        await cb.answer(f"🎉 رئیس گیلد شکست خورد! پاداشت واریز شد.", show_alert=True)
        text = f"🎉 **{gs.GUILDS[gid]['name']} رئیسشو شکست داد!**\n\nپاداش بین همه‌ی مشارکت‌کننده‌ها تقسیم شد. 👑 برترین ضربه‌زن یه آیتم افسانه‌ای گرفت."
        await _edit_or_send(cb, text, _boss_kb(gid, uid))
        return

    await cb.answer(f"💥 {dmg:,} دمیج زدی!")
    await _edit_or_send(cb, gs.guild_boss_status_text(gid), _boss_kb(gid, uid))


# ─── registration ────────────────────────────────────────────
def register_guild_handlers(dp, bot):
    dp.message.register(cmd_guilds, Command("guilds"))
    dp.message.register(cmd_guilds, F.text == "گیلدها")
    dp.message.register(cmd_guildcard, Command("guildcard"))

    dp.callback_query.register(cb_guild_open, F.data.startswith("guild_open:"))
    dp.callback_query.register(cb_guild_back, F.data.startswith("guild_back:"))
    dp.callback_query.register(cb_guild_card, F.data.startswith("guild_card:"))
    dp.callback_query.register(cb_guild_join, F.data.startswith("guild_join:"))
    dp.callback_query.register(cb_guild_leave, F.data.startswith("guild_leave:"))
    dp.callback_query.register(cb_guild_board, F.data.startswith("guild_board:"))
    dp.callback_query.register(cb_guild_accept, F.data.startswith("guild_accept:"))
    dp.callback_query.register(cb_guild_choice, F.data.startswith("guild_choice:"))
    dp.callback_query.register(cb_guild_advance, F.data.startswith("guild_advance:"))
    dp.callback_query.register(cb_guild_cancel, F.data.startswith("guild_cancel:"))
    dp.callback_query.register(cb_guild_trial_go, F.data.startswith("guild_trial_go:"))
    dp.callback_query.register(cb_guild_trial, F.data.startswith("guild_trial:"))
    dp.callback_query.register(cb_guild_action, F.data.startswith("guild_action:"))

    dp.message.register(cmd_guildwar, Command("guildwar"))
    dp.callback_query.register(cb_guild_shop, F.data.startswith("guild_shop:"))
    dp.callback_query.register(cb_guild_shop_buy, F.data.startswith("guild_shop_buy:"))
    dp.callback_query.register(cb_guild_war, F.data.startswith("guild_war:"))
    dp.callback_query.register(cb_guild_boss_locked, F.data.startswith("guild_boss_locked:"))
    dp.callback_query.register(cb_guild_boss_hit, F.data.startswith("guild_boss_hit:"))
    dp.callback_query.register(cb_guild_boss, F.data.startswith("guild_boss:"))

    dp.callback_query.register(cb_guild_treasury, F.data.startswith("guild_treasury:"))
    dp.callback_query.register(cb_guild_treasury_donate, F.data.startswith("guild_treasury_donate:"))
    dp.callback_query.register(cb_guild_treasury_rally, F.data.startswith("guild_treasury_rally:"))
    dp.callback_query.register(cb_guild_treasury_infra, F.data.startswith("guild_treasury_infra:"))
    dp.message.register(handle_treasury_donation_text, lambda m: m.from_user.id in _awaiting_donation)
