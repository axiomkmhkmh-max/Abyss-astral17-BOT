# ============================================================
#  ASTRAL ABYSS — GROUP HANDLERS
# ------------------------------------------------------------
#  دستورهای مخصوصِ گپ‌های گروهی/سوپرگروه. تو چتِ خصوصی این دستورها
#  کار نمی‌کنن (پیام می‌ده که باید تو گروه زده بشن) — دقیقاً برعکسِ
#  خیلی از دستورهای دیگه‌ی ربات که فقط تو خصوصی جواب می‌دن.
#
#   /graid           → شروع/نمایشِ رِیدِ باسِ همین گروه
#   /graidhit        → ضربه به باسِ همین گروه (یا دکمه‌ی شیشه‌ای)
#   /gtop            → رتبه‌بندیِ فقط اعضایی که تو همین گروه فعالن
#   /gduel           → با ریپلای رو پیامِ یه نفر، مستقیم چالشش بده
#                       (اگه ریپلای نکنی، مثلِ /duel @username کار می‌کنه)
#
#  این فایل هیچ فایلِ دیگه‌ای رو عوض نمی‌کنه؛ فقط باید تو bot.py،
#  جایی که بقیه‌ی register_*_handlers صدا زده می‌شن، این خط‌ها اضافه شه:
#
#       from group_handlers import register_group_handlers
#       register_group_handlers(dp, bot)
# ============================================================
import asyncio
import random
import time

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import boss_engine as be
from database import get_player, save_player, asave_player, aget_player
from characters import ALL_CHARACTERS
from katana_system import dmg_bonus, crit_bonus, lifesteal_bonus, element_amplify_bonus
from admin_panel import is_admin
from logger import log_sync

from group_system import (
    get_group_boss, save_group_boss, spawn_group_boss, mark_group_boss_killed,
    group_boss_cooldown_remaining, list_active_group_bosses,
    touch_group_member, get_group_leaderboard, top_contributors,
)
from referral_system import group_ref_link

GROUP_ATTACK_COOLDOWN_SEC = 8
NOT_GROUP_MSG = "👥 این دستور فقط داخلِ یه گروه معنی داره — تو خصوصی نمی‌شه ازش استفاده کرد."
NEED_START_MSG = "❌ اول تو خصوصیِ ربات /start بزن، بعد بیا تو گروه!"


# ─── Helpers ────────────────────────────────────────────────────

def _chat_id_of(event) -> int:
    if isinstance(event, CallbackQuery):
        return event.message.chat.id
    return event.chat.id


def _target_chat_id(event) -> int:
    """چت‌آیدیِ باسی که باید بهش ضربه بزنه رو برمی‌گردونه. برای دکمه‌های
    شیشه‌ای، این آیدی تو خودِ callback_data (`graidhit:{chat_id}`) جاسازی
    شده — لازمه، چون یه بازیکنِ دعوت‌شده ممکنه از پی‌وی خودش (نه از خودِ
    گروه) رو دکمه بزنه؛ اونجا event.message.chat.id چتِ خصوصیِ خودشه، نه
    گروهی که باس توشه."""
    if isinstance(event, CallbackQuery) and event.data:
        parts = event.data.split(":")
        if len(parts) >= 2:
            try:
                return int(parts[1])
            except ValueError:
                pass
    return _chat_id_of(event)


def _is_group_event(event) -> bool:
    chat = event.message.chat if isinstance(event, CallbackQuery) else event.chat
    return chat.type != "private"


async def _reply(event, text: str, kb: InlineKeyboardMarkup | None = None, edit: bool = False):
    if isinstance(event, CallbackQuery):
        if edit:
            try:
                await event.message.edit_text(text, reply_markup=kb)
                return
            except Exception:
                pass
        await event.message.answer(text, reply_markup=kb)
    else:
        await event.answer(text, reply_markup=kb)


def _invite_row(chat_id: int) -> list[InlineKeyboardButton]:
    """دکمه‌ی دیپ‌لینک — زیرِ تقریباً هر پیامِ گروهی می‌شینه تا هرکی از
    اعضای گروه که هنوز /start نزده، یه‌راست بره به PV و شروع کنه."""
    return [InlineKeyboardButton(text="🎮 منم می‌خوام بازی کنم", url=group_ref_link(chat_id))]


def _build_kb(chat_id: int, boss: dict) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text="⚔️ ضربه به باسِ گروه!", callback_data=f"graidhit:{chat_id}", style=ButtonStyle.DANGER,
    )]]
    if boss.get("mechanic") == "area" and boss.get("area_active"):
        rows.append([InlineKeyboardButton(
            text="🛡 دفاع کن!", callback_data=f"graiddef:{chat_id}", style=ButtonStyle.PRIMARY,
        )])
    rows.append([InlineKeyboardButton(
        text="📨 دعوت یه بازیکنِ دیگه", callback_data=f"binv:group:{chat_id}", style=ButtonStyle.PRIMARY,
    )])
    rows.append(_invite_row(chat_id))
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _status_with_top(chat_id: int, boss: dict) -> str:
    text = be.build_status_text(boss)
    top = top_contributors(boss, 3)
    if not top:
        return text
    medals = ["🥇", "🥈", "🥉"]
    lines = ["", "📊 **بیشترین دمیج تا الان:**"]
    for i, (uid, dmg) in enumerate(top):
        p = await aget_player(uid)
        name = p.get("name", "یه بازیکن") if p else "یه بازیکن"
        lines.append(f"{medals[i]} {name}: {dmg:,}")
    return text + "\n" + "\n".join(lines)


def _name_lookup_factory():
    cache: dict[int, str] = {}
    async def _name_of(uid: int) -> str:
        if uid not in cache:
            p = await aget_player(uid)
            cache[uid] = p.get("name", "یه بازیکن") if p else "یه بازیکن"
        return cache[uid]
    return _name_of


# ─── /graid — شروع یا نمایشِ وضعیتِ رِید ─────────────────────────

async def cmd_graid(msg: Message):
    if not _is_group_event(msg):
        await msg.answer(NOT_GROUP_MSG)
        return
    touch_group_member(msg.chat.id, msg.from_user.id)
    player = await aget_player(msg.from_user.id)
    if not player or not player.get("character"):
        await msg.answer(NEED_START_MSG)
        return

    chat_id = msg.chat.id
    parts = (msg.text or "").split(maxsplit=1)
    arg = parts[1].strip() if len(parts) > 1 else None

    boss = get_group_boss(chat_id)

    # ─── `/graid force` (فقط ادمین) — برای وقتی رِید گیر کرده یا کسی
    # فراموش کرده تمومش کنه؛ باسِ فعلی رو (بدون پاداش) کنسل می‌کنه و
    # کول‌داون رو هم دور می‌زنه.
    if arg == "force":
        if not is_admin(msg):
            await msg.answer("❌ فقط ادمین می‌تونه رِید رو force کنه!")
            return
        boss = spawn_group_boss(chat_id)
        log_sync(f"👥👹 **GROUP RAID FORCE-RESTARTED**\n📍 چت: `{chat_id}`\n🛠 ادمین: `{msg.from_user.id}`", "GROUP")
        await msg.answer(
            f"🛠 ادمین رِید رو دوباره شروع کرد!\n\n{await _status_with_top(chat_id, boss)}",
            reply_markup=_build_kb(chat_id, boss),
        )
        return

    if boss and boss.get("alive"):
        be.tick_shield_regen(boss)
        save_group_boss(chat_id, boss)
        await msg.answer(await _status_with_top(chat_id, boss), reply_markup=_build_kb(chat_id, boss))
        return

    cooldown = group_boss_cooldown_remaining(chat_id)
    if cooldown > 0:
        mins, secs = divmod(cooldown, 60)
        await msg.answer(f"😴 باسِ قبلیِ این گروه تازه شکست خورده — {mins} دقیقه و {secs} ثانیه تا رِیدِ بعدی صبر کن.")
        return

    template_id = arg if arg and arg in be.WORLD_BOSS_TEMPLATES else None

    boss = spawn_group_boss(chat_id, template_id)
    log_sync(f"👥👹 **GROUP RAID STARTED**\n📍 چت: `{chat_id}`\n🏷️ {boss['name']}\n🚀 شروع‌کننده: `{msg.from_user.id}`", "GROUP")
    await msg.answer(
        f"👥 **رِیدِ باسِ این گروه شروع شد!**\nهرکی تو این گروه هست می‌تونه با دکمه‌ی زیر (یا `/graidhit`) بزنتش.\n\n"
        + await _status_with_top(chat_id, boss),
        reply_markup=_build_kb(chat_id, boss),
    )


# ─── ضربه به باسِ گروه ────────────────────────────────────────────

async def cb_graid_hit(event):
    is_cb = isinstance(event, CallbackQuery)
    uid = event.from_user.id
    chat_id = _target_chat_id(event) if is_cb else _chat_id_of(event)

    # ─── قابلیتِ دعوت: اگه این ضربه از پی‌وی خصوصی میاد (نه از خودِ
    # گروه)، فقط وقتی مجازه که قبلاً با /binvite برای همینا باسِ همین
    # گروه دعوت شده باشه — وگرنه مثلِ قبل باید تو خودِ گروه باشه.
    if not _is_group_event(event):
        boss_peek = get_group_boss(chat_id) if is_cb else None
        invited = bool(boss_peek and uid in (boss_peek.get("invited_uids") or []))
        if not invited:
            txt = NOT_GROUP_MSG
            if is_cb:
                await event.answer(txt, show_alert=True)
            else:
                await event.answer(txt)
            return

    player = await aget_player(uid)
    if not player or not player.get("character"):
        txt = NEED_START_MSG
        if is_cb:
            await event.answer(txt, show_alert=True)
        else:
            await event.answer(txt)
        return

    boss = get_group_boss(chat_id)
    if not boss or not boss.get("alive"):
        txt = "😴 الان تو این گروه هیچ رِیدی فعال نیست. با `/graid` یکی شروع کن!"
        if is_cb:
            await event.answer(txt, show_alert=True)
        else:
            await event.answer(txt)
        return

    now = time.time()
    since = now - player.get("last_graid_hit", 0)
    if since < GROUP_ATTACK_COOLDOWN_SEC:
        txt = f"⏳ {int(GROUP_ATTACK_COOLDOWN_SEC - since)} ثانیه صبر کن!"
        if is_cb:
            await event.answer(txt, show_alert=True)
        else:
            await event.answer(txt)
        return

    be.tick_shield_regen(boss)

    char_name = player.get("character", "")
    char = ALL_CHARACTERS.get(char_name, {})
    k_level = player.get("katana_level", 1)

    from skill_tree import get_skill_bonuses
    skb = get_skill_bonuses(player)

    base = char.get("base_dmg", 12)
    k_bonus = dmg_bonus(k_level)
    combo = player.get("combo", 0)
    from world_pulse import pulse_value as _pulse_val
    combo_mult = 1 + (combo * 0.05) + skb["dmg_pct"]
    raw_dmg = int((base + player.get("level", 1) * 2.5 + k_bonus + random.randint(-3, 12)) * combo_mult)
    raw_dmg = int(raw_dmg * _pulse_val("boss_dmg_mult"))

    crit_chance = max(0.0, 0.15 + crit_bonus(k_level) + skb["crit_chance"] + _pulse_val("crit_add"))
    crit = random.random() < crit_chance
    if crit:
        raw_dmg = int(raw_dmg * (2.0 + skb["crit_dmg_bonus"]))

    amplify = element_amplify_bonus(k_level) + skb["elem_amp"]
    result = be.process_attack(boss, uid, char_name, raw_dmg, amplify_bonus=amplify)

    ls = lifesteal_bonus(k_level) + skb["lifesteal"]
    if ls > 0 and (result["hp_dmg"] > 0 or result["shield_dmg"] > 0):
        healed = int((result["hp_dmg"] + result["shield_dmg"]) * ls)
        player["hp"] = min(player.get("max_hp", 100), player.get("hp", 100) + healed)

    player["last_graid_hit"] = now
    player["combo"] = combo + 1
    from economy_engine import apply_gold_find
    from game_data import xp_for_level
    zen_gain = apply_gold_find(player, random.randint(15, 40) + player.get("level", 1) // 2)
    xp_gain = random.randint(12, 25) + player.get("level", 1) // 3
    player["zen"] = player.get("zen", 0) + zen_gain
    player["xp"] = player.get("xp", 0) + xp_gain

    from skill_tree import grant_levelup_points
    old_level = player.get("level", 1)
    while player.get("xp", 0) >= xp_for_level(player.get("level", 1)) and player.get("level", 1) < 150:
        player["level"] += 1
        player["max_hp"] = player.get("max_hp", 100) + 10
        from skill_tree import effective_max_hp
        player["hp"] = effective_max_hp(player)
    leveled_up = player.get("level", 1) != old_level
    if leveled_up:
        grant_levelup_points(player, old_level, player["level"])
    await asave_player(uid, player)

    dmg_total = result["hp_dmg"] + result["shield_dmg"]
    hit_line = f"💥 {player.get('name','یه بازیکن')} {dmg_total:,} دمیج زد" + (" (کریت! 💥)" if crit else "") + f" +{zen_gain:,} Zen"

    if leveled_up:
        level_up_text = f"🎉 **{player.get('name','یه بازیکن')}** توی همین رِید رسید به سطح **{player['level']}**!"
        try:
            if is_cb:
                await event.message.answer(level_up_text)
            else:
                await event.answer(level_up_text)
        except Exception:
            pass

    if result["boss_killed"]:
        rewards, speed_kill = be.distribute_rewards(boss, is_weekly_featured=False)
        for ruid, r in rewards.items():
            rp = await aget_player(ruid)
            if not rp:
                continue
            rp["zen"] = rp.get("zen", 0) + r["zen"]
            if r["titles"]:
                rp.setdefault("boss_titles", [])
                rp["boss_titles"].extend(r["titles"])
            if r.get("items"):
                rp.setdefault("inventory", []).extend(r["items"])
            await asave_player(ruid, rp)

        summary = be.build_kill_summary(boss, rewards, speed_kill, _name_lookup_factory())
        mark_group_boss_killed(chat_id)
        log_sync(f"👥👹 **GROUP RAID CLEARED**\n📍 چت: `{chat_id}`\n🏷️ {boss['name']}\n👥 {len(boss['contributors'])} نفر شرکت کردن", "GROUP")
        await _reply(event, f"{hit_line}\n\n{summary}", kb=InlineKeyboardMarkup(inline_keyboard=[_invite_row(chat_id)]))
        return

    save_group_boss(chat_id, boss)
    if is_cb:
        await event.answer(f"💥 {dmg_total:,} دمیج زدی!" + (" کریت! 💥" if crit else ""))
    else:
        await event.answer(f"{hit_line}\n\n{await _status_with_top(chat_id, boss)}", reply_markup=_build_kb(chat_id, boss))


# ─── دفاع در برابرِ حمله‌ی ناحیه‌ای (هم دکمه، هم کامند) ───────────
# قبلاً دکمه‌ی «🛡 دفاع کن!» توی گروه اصلاً هندلری نداشت (`graiddef:`
# هیچ‌جا register نشده بود) — یعنی زدنش عملاً هیچ کاری نمی‌کرد و همه
# همیشه از حمله‌ی ناحیه‌ای آسیب می‌دیدن. الان هم دکمه کار می‌کنه، هم
# کامندِ `/graiddef`.

async def cb_graid_defend(event):
    is_cb = isinstance(event, CallbackQuery)
    uid = event.from_user.id
    chat_id = _target_chat_id(event) if is_cb else _chat_id_of(event)

    if not _is_group_event(event):
        boss_peek = get_group_boss(chat_id) if is_cb else None
        invited = bool(boss_peek and uid in (boss_peek.get("invited_uids") or []))
        if not invited:
            txt = NOT_GROUP_MSG
            if is_cb:
                await event.answer(txt, show_alert=True)
            else:
                await event.answer(txt)
            return

    player = await aget_player(uid)
    if not player or not player.get("character"):
        txt = NEED_START_MSG
        if is_cb:
            await event.answer(txt, show_alert=True)
        else:
            await event.answer(txt)
        return

    boss = get_group_boss(chat_id)
    if not boss or not boss.get("alive"):
        txt = "😴 الان تو این گروه هیچ رِیدی فعال نیست. با `/graid` یکی شروع کن!"
        if is_cb:
            await event.answer(txt, show_alert=True)
        else:
            await event.answer(txt)
        return
    if boss.get("mechanic") != "area" or not boss.get("area_active"):
        txt = "🛡 الان چیزی برای دفاع نیست."
        if is_cb:
            await event.answer(txt, show_alert=True)
        else:
            await event.answer(txt)
        return

    be.register_area_defense(boss, uid)
    save_group_boss(chat_id, boss)
    log_sync(f"🛡 **GROUP RAID DEFEND**\n📍 چت: `{chat_id}`\n👤 {player.get('name','—')} (`{uid}`)", "GROUP")
    txt = "🛡 دفاع ثبت شد! امن موندی."
    if is_cb:
        await event.answer(txt, show_alert=False)
    else:
        await event.answer(txt)


# ─── /gtop — رتبه‌بندیِ فقط همین گروه ─────────────────────────────

SORT_LABELS = {"level": "🏅 سطح", "zen": "💰 ثروت", "pvp": "⚔️ PvP"}


def _gtop_kb(chat_id: int, active: str) -> InlineKeyboardMarkup:
    row = []
    for key, label in SORT_LABELS.items():
        text = f"• {label} •" if key == active else label
        row.append(InlineKeyboardButton(text=text, callback_data=f"gtop:{chat_id}:{key}"))
    return InlineKeyboardMarkup(inline_keyboard=[row, _invite_row(chat_id)])


def _gtop_text(chat_title: str, rows: list[dict], sort_by: str) -> str:
    if not rows:
        return "📊 هنوز کسی تو این گروه فعالیتِ ثبت‌شده نداره. چند تا پیام/دستور بزنید تا رتبه‌بندی پر شه!"
    lines = [f"🏆 **رتبه‌بندیِ این گروه** ({chat_title or 'گروه'}) — بر اساسِ {SORT_LABELS[sort_by]}", ""]
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i+1}."
        tag = f" [{r['guild']}]" if r["guild"] else ""
        league = f" · {r['league']}" if r["league"] else ""
        lines.append(f"{medal} {r['name']}{tag} — سطح {r['level']} · 💰 {r['zen']:,} · ⚔️ {r['pvp_wins']} برد{league}")
    return "\n".join(lines)


async def cmd_gtop(msg: Message):
    if not _is_group_event(msg):
        await msg.answer(NOT_GROUP_MSG)
        return
    touch_group_member(msg.chat.id, msg.from_user.id)

    rows = await get_group_leaderboard(msg.chat.id, limit=10, sort_by="level")
    await msg.answer(
        _gtop_text(msg.chat.title, rows, "level"),
        reply_markup=_gtop_kb(msg.chat.id, "level"),
    )


async def cb_gtop_switch(cb: CallbackQuery):
    _, chat_id_str, sort_by = cb.data.split(":")
    chat_id = int(chat_id_str)
    rows = await get_group_leaderboard(chat_id, limit=10, sort_by=sort_by)
    try:
        await cb.message.edit_text(
            _gtop_text(cb.message.chat.title, rows, sort_by),
            reply_markup=_gtop_kb(chat_id, sort_by),
        )
    except Exception:
        pass
    await cb.answer()


# ─── /gduel — چالشِ سریع با ریپلای ────────────────────────────────

async def cmd_gduel(msg: Message):
    if not _is_group_event(msg):
        await msg.answer(NOT_GROUP_MSG)
        return
    touch_group_member(msg.chat.id, msg.from_user.id)

    from pvp_handlers import _resolve_target, _send_stake_prompt
    from pvp import pending_duels, get_fight_by_uid

    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player or not player.get("character"):
        await msg.answer(NEED_START_MSG)
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
        await msg.answer("⏳ یه درخواستِ دیگه هنوز بازه. صبر کن یا `/gduel` رو دوباره بزن.")
        return

    target_id = None
    if msg.reply_to_message and msg.reply_to_message.from_user:
        target_id = msg.reply_to_message.from_user.id
    if not target_id:
        target_id = _resolve_target(msg.text or "", uid)
    if not target_id:
        await msg.answer("📝 استفاده: رو پیامِ یه نفر ریپلای کن و `/gduel` بزن، یا `/gduel @username`")
        return
    if target_id == uid:
        await msg.answer("❌ نمی‌تونی خودت رو چالش بدی!")
        return
    if get_fight_by_uid(target_id):
        await msg.answer("❌ اون بازیکن الان توی یه فایته!")
        return

    target = await aget_player(target_id)
    if not target or not target.get("character"):
        await msg.answer("❌ این بازیکن هنوز /start نزده!")
        return

    await _send_stake_prompt(msg, uid, target_id, is_challenger=True)


# ─── منشن/ریپلای به ربات تو گروه ──────────────────────────────
#  طبق قوانینِ ضدِ اسپم: ربات تو گروه به هیچ پیامِ معمولی‌ای واکنش
#  نشون نمی‌ده — فقط وقتی: (۱) دستور بزنن، (۲) منشنش کنن، یا
#  (۳) رو پیامِ خودش ریپلای کنن. این هندلر فقط اون دو تای آخر رو
#  می‌گیره (کامندها جای خودشون رو دارن).

_ME_CACHE: dict = {}  # یه‌بار get_me() می‌گیره و کش می‌کنه — نه رو هر پیامِ گروهی


async def _cached_me(bot: Bot):
    if "me" not in _ME_CACHE:
        _ME_CACHE["me"] = await bot.get_me()
    return _ME_CACHE["me"]


async def handle_group_mention(msg: Message, bot: Bot):
    if msg.chat.type == "private" or not msg.text or msg.text.startswith("/"):
        return  # کامندها جای خودشون رو دارن؛ این فقط برای منشن/ریپلایِ خالی
    # فیلترِ ارزون قبلِ هر API-callی: یا باید ریپلای باشه یا تو متن @ باشه
    if not msg.reply_to_message and "@" not in msg.text:
        return

    me = await _cached_me(bot)
    is_reply_to_bot = bool(
        msg.reply_to_message and msg.reply_to_message.from_user
        and msg.reply_to_message.from_user.id == me.id
    )
    is_mentioned = bool(me.username) and f"@{me.username}".lower() in msg.text.lower()
    if not (is_reply_to_bot or is_mentioned):
        return

    touch_group_member(msg.chat.id, msg.from_user.id)

    # کسی که قبلاً تو خصوصی /start زده (یعنی پلیرش تو دیتابیس ساخته شده)
    # دیگه لازم نیست این پیامِ معرفی رو هر بار که ریپلای/منشن می‌کنه ببینه.
    if await aget_player(msg.from_user.id):
        return

    await msg.reply(
        "👋 سلام! تو این گروه می‌تونی با `/graid` رِیدِ باسِ گروه رو شروع کنی، "
        "با `/gtop` رتبه‌بندیِ گروه رو ببینی، یا با ریپلای‌رو‌پیامِ کسی `/gduel` بزنی.\n\n"
        "برای بازیِ کامل (لوت، PvP، گیلد، ...) باید تو خصوصیِ من باشیم 👇",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[_invite_row(msg.chat.id)]),
    )


# ─── واچرِ پس‌زمینه — مکانیک‌های وابسته‌به‌زمانِ باس‌های گروهی ─────
# (سپر/حمله‌ی ناحیه‌ای/خشم رو، حتی وقتی کسی تو چند دقیقه چیزی نمی‌زنه،
#  به‌روز نگه می‌داره — دقیقاً مثلِ واچرِ باسِ سراسری تو boss_handlers.py)

async def group_boss_watcher_loop(bot: Bot):
    while True:
        try:
            for boss in list_active_group_bosses():
                chat_id = boss["chat_id"]
                changed = be.tick_shield_regen(boss)
                area_msg = be.tick_area_attack(boss)
                enrage_msg = be.tick_enrage(boss)
                if area_msg or enrage_msg:
                    changed = True
                    try:
                        await bot.send_message(chat_id, area_msg or enrage_msg)
                    except Exception:
                        pass
                if changed:
                    save_group_boss(chat_id, boss)
        except Exception as e:
            log_sync(f"🔴 group boss watcher error: {e}", "ERROR")
        await asyncio.sleep(15)


# ─── ثبتِ عضویتِ گروه رو هر پیامِ متنی (برای /gtop) ───────────────

async def _membership_middleware(handler, event: Message, data: dict):
    if event.chat.type != "private" and event.from_user:
        try:
            touch_group_member(event.chat.id, event.from_user.id)
        except Exception:
            pass
    return await handler(event, data)


def register_group_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_graid, Command("graid"))
    dp.message.register(cb_graid_hit, Command("graidhit"))
    dp.callback_query.register(cb_graid_hit, F.data.startswith("graidhit:"))
    dp.message.register(cb_graid_defend, Command("graiddef"))
    dp.callback_query.register(cb_graid_defend, F.data.startswith("graiddef:"))
    dp.message.register(cmd_gtop, Command("gtop"))
    dp.callback_query.register(cb_gtop_switch, F.data.startswith("gtop:"))
    dp.message.register(cmd_gduel, Command("gduel"))

    # این باید بعدِ همه‌ی کامندهای دیگه ثبت بشه (هم تو همین فایل هم
    # کلِ ربات) تا هیچ‌وقت جلوی یه کامندِ واقعی رو نگیره — به همینه که
    # register_group_handlers(dp, bot) باید تو bot.py نزدیکِ آخرِ لیستِ
    # register_*_handlers صدا زده بشه.
    dp.message.register(handle_group_mention, F.chat.type.in_({"group", "supergroup"}))

    dp.message.middleware()(_membership_middleware)

    asyncio.create_task(group_boss_watcher_loop(bot))
