# ============================================================
#  ASTRAL ABYSS — Team PvP Handlers (۲به۲ / ۳به۳ / ۴به۴ / ۵به۵)
#  لابیِ دوستانه + صفِ سریعِ متچ‌میکینگ + نبردِ راندیِ هم‌زمان
# ============================================================
import asyncio
import time

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import team_pvp_system as tp
from characters import ALL_CHARACTERS
from database import get_player, save_player, all_players
from logger import log_sync

_queue_watchers: dict[int, bool] = {}   # size -> watcher running?


# ────────────────────────────────────────────────────────────
# /teampvp — منو
# ────────────────────────────────────────────────────────────
def _menu_text_and_kb() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "⚔️ **پی‌وی‌پیِ تیمی — نبردِ اسکوادها**\n\n"
        "🌀 گیج‌بارِ تیمی جمع می‌شه و اولتیمیتِ تیمی رها می‌کنه\n"
        "🎯 آتشِ متمرکز روی یه هدف، دمیجِ اضافه می‌ده\n"
        "🤝 با گارد از هم‌تیمیت محافظت کن\n\n"
        "یه سایزِ اسکواد رو انتخاب کن:"
    )
    rows = []
    for n in tp.SQUAD_SIZES:
        rows.append([
            InlineKeyboardButton(text=f"🏠 لابی {n}به{n}", callback_data=f"tp_mk:{n}"),
            InlineKeyboardButton(text=f"⚡ صفِ سریع {n}به{n}", callback_data=f"tp_q:{n}"),
        ])
    rows.append([InlineKeyboardButton(text="🔙 بستن", callback_data="tp_close", style=ButtonStyle.PRIMARY)])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def cmd_teampvp(msg: Message):
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
    text, kb = _menu_text_and_kb()
    await msg.answer(text, reply_markup=kb)


async def cb_tp_close(cb: CallbackQuery):
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.answer()


# ────────────────────────────────────────────────────────────
# ساختِ لابی
# ────────────────────────────────────────────────────────────
def _lobby_kb(lobby: dict) -> InlineKeyboardMarkup:
    lid = lobby["id"]
    rows = [
        [
            InlineKeyboardButton(text="🔴 پیوستن به A", callback_data=f"tp_j:{lid}:A"),
            InlineKeyboardButton(text="🔵 پیوستن به B", callback_data=f"tp_j:{lid}:B"),
        ],
        [InlineKeyboardButton(text="🚪 خروج از لابی", callback_data=f"tp_lv:{lid}")],
    ]
    if tp.lobby_is_full(lobby):
        rows.append([InlineKeyboardButton(text="🚀 شروعِ نبرد", callback_data=f"tp_st:{lid}", style=ButtonStyle.DANGER)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_tp_make(cb: CallbackQuery, bot: Bot):
    size = int(cb.data.split(":")[1])
    uid = cb.from_user.id
    player = get_player(uid)
    if not player:
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return
    if uid in tp.player_in_lobby or tp.get_fight_by_uid(uid) or uid in tp.player_in_queue:
        await cb.answer("⚠️ همین الان تو یه لابی/صف/نبردِ دیگه‌ای.", show_alert=True)
        return
    lobby = tp.create_lobby(uid, player.get("name", "Bearer"), size, cb.message.chat.id)
    try:
        await cb.message.edit_text(tp.lobby_text(lobby), reply_markup=_lobby_kb(lobby))
    except Exception:
        await cb.message.answer(tp.lobby_text(lobby), reply_markup=_lobby_kb(lobby))
    await cb.answer("✅ لابی ساخته شد — این پیام رو به بقیه هم بفرست تا بپیوندن!")


async def cb_tp_join(cb: CallbackQuery, bot: Bot):
    _, lid, team = cb.data.split(":")
    uid = cb.from_user.id
    player = get_player(uid)
    if not player:
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return
    ok, note = tp.lobby_join(lid, uid, player.get("name", "Bearer"), team)
    if not ok:
        await cb.answer(note, show_alert=True)
        return
    lobby = tp.lobbies.get(lid)
    try:
        await cb.message.edit_text(tp.lobby_text(lobby), reply_markup=_lobby_kb(lobby))
    except Exception:
        pass
    await cb.answer(note)


async def cb_tp_leave_lobby(cb: CallbackQuery):
    lid = cb.data.split(":")[1]
    tp.lobby_leave(cb.from_user.id)
    lobby = tp.lobbies.get(lid)
    if lobby:
        try:
            await cb.message.edit_text(tp.lobby_text(lobby), reply_markup=_lobby_kb(lobby))
        except Exception:
            pass
    else:
        try:
            await cb.message.edit_text("🚪 لابی خالی شد و بسته شد.")
        except Exception:
            pass
    await cb.answer("خارج شدی.")


async def cb_tp_start(cb: CallbackQuery, bot: Bot):
    lid = cb.data.split(":")[1]
    lobby = tp.lobbies.get(lid)
    if not lobby:
        await cb.answer("❌ این لابی دیگه وجود نداره.", show_alert=True)
        return
    if cb.from_user.id != lobby["host"]:
        await cb.answer("⛔ فقط سازنده‌ی لابی می‌تونه شروع کنه.", show_alert=True)
        return
    if not tp.lobby_is_full(lobby):
        await cb.answer("⏳ هنوز هر دو تیم پُر نشدن.", show_alert=True)
        return

    team_a_data, team_b_data = [], []
    for m in lobby["team_a"]:
        p = get_player(m["uid"])
        if p:
            team_a_data.append((m["uid"], p, ALL_CHARACTERS.get(p.get("character"), {})))
    for m in lobby["team_b"]:
        p = get_player(m["uid"])
        if p:
            team_b_data.append((m["uid"], p, ALL_CHARACTERS.get(p.get("character"), {})))

    for m in lobby["team_a"] + lobby["team_b"]:
        tp.player_in_lobby.pop(m["uid"], None)
    tp.lobbies.pop(lid, None)

    try:
        await cb.message.edit_text("🚀 نبرد شروع شد! به چتِ خصوصیِ ربات نگاه کن.")
    except Exception:
        pass
    await cb.answer()

    fight = tp.start_fight(lobby["size"], team_a_data, team_b_data)
    log_sync(f"⚔️ **TEAM PVP STARTED** {tp._elig_size_label(lobby['size'])} | fight `{fight.fight_id}`", "PVP")
    await _broadcast_new_round(fight, bot, intro=True)
    asyncio.create_task(_round_timeout_watcher(fight.fight_id, fight.round_no, bot))


# ────────────────────────────────────────────────────────────
# صفِ سریع
# ────────────────────────────────────────────────────────────
async def cb_tp_queue(cb: CallbackQuery, bot: Bot):
    size = int(cb.data.split(":")[1])
    uid = cb.from_user.id
    player = get_player(uid)
    if not player:
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return
    ok, note = tp.queue_join(uid, size)
    await cb.answer(note, show_alert=not ok)
    if not ok:
        return
    try:
        await cb.message.answer(f"⏳ تو صفِ {tp._elig_size_label(size)} منتظرِ حریفی — با /teampvp_leave می‌تونی از صف خارج شی.")
    except Exception:
        pass
    await _try_start_from_queue(size, bot)


async def cmd_teampvp_leave(msg: Message):
    uid = msg.from_user.id
    if uid in tp.player_in_queue:
        tp.queue_leave(uid)
        await msg.answer("🚪 از صف خارج شدی.")
    elif uid in tp.player_in_lobby:
        tp.lobby_leave(uid)
        await msg.answer("🚪 از لابی خارج شدی.")
    else:
        await msg.answer("تو الان تو هیچ صف یا لابی‌ای نیستی.")


async def _try_start_from_queue(size: int, bot: Bot):
    pool = tp.queue_try_match(size)
    if not pool:
        return
    from combat_power import calculate_combat_power
    cps = {}
    players = {}
    for uid in pool:
        p = get_player(uid)
        players[uid] = p
        cps[uid] = calculate_combat_power(p) if p else 0
    team_a_uids, team_b_uids = tp.balance_teams_by_cp(pool, cps)

    team_a_data = [(u, players[u], ALL_CHARACTERS.get(players[u].get("character"), {})) for u in team_a_uids if players.get(u)]
    team_b_data = [(u, players[u], ALL_CHARACTERS.get(players[u].get("character"), {})) for u in team_b_uids if players.get(u)]
    if len(team_a_data) != size or len(team_b_data) != size:
        return  # یه پروفایل خراب بود — بی‌خیال، دفعه‌ی بعد دوباره تلاش می‌شه

    fight = tp.start_fight(size, team_a_data, team_b_data)
    log_sync(f"⚡ **QUICK TEAM PVP MATCHED** {tp._elig_size_label(size)} | fight `{fight.fight_id}`", "PVP")
    await _broadcast_new_round(fight, bot, intro=True, matched=True)
    asyncio.create_task(_round_timeout_watcher(fight.fight_id, fight.round_no, bot))


# ────────────────────────────────────────────────────────────
# اکشن‌های راند
# ────────────────────────────────────────────────────────────
def _action_kb(fight: tp.SquadFight, w: tp.Warrior) -> InlineKeyboardMarkup:
    fid = fight.fight_id
    rows = [[InlineKeyboardButton(text="⚔️ حمله", callback_data=f"tp_a:{fid}"),
             InlineKeyboardButton(text="🛡 دفاع", callback_data=f"tp_d:{fid}")]]
    ab_row = []
    for i, ab in enumerate(w.abilities):
        affordable = "✅" if w.energy >= ab["cost"] else "🔒"
        ab_row.append(InlineKeyboardButton(text=f"{affordable}{ab['label']}({ab['cost']})", callback_data=f"tp_b:{fid}:{i}"))
        if len(ab_row) == 2:
            rows.append(ab_row)
            ab_row = []
    if ab_row:
        rows.append(ab_row)
    allies = [a for a in fight.own_team(w.team) if a.alive and a.uid != w.uid]
    if allies:
        rows.append([InlineKeyboardButton(text="🤝 گارد از هم‌تیمی", callback_data=f"tp_g:{fid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _target_kb(fight: tp.SquadFight, w: tp.Warrior, kind: str, ab_idx: str = "-") -> InlineKeyboardMarkup:
    fid = fight.fight_id
    if kind == "guard":
        pool = [a for a in fight.own_team(w.team) if a.alive and a.uid != w.uid]
    else:
        pool = [e for e in fight.enemy_team(w.team) if e.alive]
    rows = []
    for t in pool:
        hp_pct = int(t.hp / t.max_hp * 100) if t.max_hp else 0
        rows.append([InlineKeyboardButton(text=f"{t.name} ({hp_pct}٪ HP)", callback_data=f"tp_t:{fid}:{kind}:{ab_idx}:{t.uid}")])
    rows.append([InlineKeyboardButton(text="🔙 برگشت", callback_data=f"tp_back:{fid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _check_owner(cb: CallbackQuery, fight: tp.SquadFight | None) -> tuple[bool, tp.Warrior | None]:
    if not fight:
        return False, None
    w = fight.find(cb.from_user.id)
    if not w or not w.alive:
        return False, None
    return True, w


async def cb_tp_attack(cb: CallbackQuery):
    fid = cb.data.split(":")[1]
    fight = tp.active_fights.get(fid)
    ok, w = _check_owner(cb, fight)
    if not ok:
        await cb.answer("⛔ نمی‌تونی الان این کار رو بکنی.", show_alert=True)
        return
    try:
        await cb.message.edit_text("🎯 هدفت رو انتخاب کن:", reply_markup=_target_kb(fight, w, "atk"))
    except Exception:
        pass
    await cb.answer()


async def cb_tp_ability(cb: CallbackQuery):
    _, fid, idx = cb.data.split(":")
    fight = tp.active_fights.get(fid)
    ok, w = _check_owner(cb, fight)
    if not ok:
        await cb.answer("⛔ نمی‌تونی الان این کار رو بکنی.", show_alert=True)
        return
    ab = w.abilities[int(idx)]
    if w.energy < ab["cost"]:
        await cb.answer(f"🔋 انرژیت کافی نیست ({w.energy}/{ab['cost']})", show_alert=True)
        return
    try:
        await cb.message.edit_text(f"🎯 هدف برای «{ab['name']}» رو انتخاب کن:", reply_markup=_target_kb(fight, w, "ab", idx))
    except Exception:
        pass
    await cb.answer()


async def cb_tp_guard(cb: CallbackQuery):
    fid = cb.data.split(":")[1]
    fight = tp.active_fights.get(fid)
    ok, w = _check_owner(cb, fight)
    if not ok:
        await cb.answer("⛔ نمی‌تونی الان این کار رو بکنی.", show_alert=True)
        return
    try:
        await cb.message.edit_text("🤝 از کدوم هم‌تیمی محافظت کنی؟", reply_markup=_target_kb(fight, w, "guard"))
    except Exception:
        pass
    await cb.answer()


async def cb_tp_back(cb: CallbackQuery):
    fid = cb.data.split(":")[1]
    fight = tp.active_fights.get(fid)
    ok, w = _check_owner(cb, fight)
    if not ok:
        await cb.answer()
        return
    try:
        await cb.message.edit_text("چیکار می‌کنی؟", reply_markup=_action_kb(fight, w))
    except Exception:
        pass
    await cb.answer()


async def cb_tp_defend(cb: CallbackQuery, bot: Bot):
    fid = cb.data.split(":")[1]
    fight = tp.active_fights.get(fid)
    ok, w = _check_owner(cb, fight)
    if not ok:
        await cb.answer("⛔ نمی‌تونی الان این کار رو بکنی.", show_alert=True)
        return
    fight.pending[w.uid] = {"type": "defend"}
    try:
        await cb.message.edit_text("🛡 منتظرِ بقیه‌ی جنگجوها هستیم...")
    except Exception:
        pass
    await cb.answer("ثبت شد.")
    await _maybe_resolve(fight, bot)


async def cb_tp_target(cb: CallbackQuery, bot: Bot):
    _, fid, kind, ab_idx, target_uid = cb.data.split(":")
    fight = tp.active_fights.get(fid)
    ok, w = _check_owner(cb, fight)
    if not ok:
        await cb.answer("⛔ نمی‌تونی الان این کار رو بکنی.", show_alert=True)
        return
    target_uid = int(target_uid)
    if kind == "guard":
        fight.pending[w.uid] = {"type": "guard", "target": target_uid}
    elif kind == "ab":
        fight.pending[w.uid] = {"type": "ability", "ability_idx": int(ab_idx), "target": target_uid}
    else:
        fight.pending[w.uid] = {"type": "attack", "target": target_uid}
    try:
        await cb.message.edit_text("✅ ثبت شد — منتظرِ بقیه‌ی جنگجوها هستیم...")
    except Exception:
        pass
    await cb.answer("ثبت شد.")
    await _maybe_resolve(fight, bot)


# ────────────────────────────────────────────────────────────
# جریانِ راند
# ────────────────────────────────────────────────────────────
async def _broadcast_new_round(fight: tp.SquadFight, bot: Bot, intro: bool = False, matched: bool = False):
    header = ""
    if intro:
        note = "⚡ حریف پیدا شد!\n\n" if matched else ""
        header = (
            f"{note}🎬 **نبردِ تیمی {tp._elig_size_label(fight.size)} آغاز شد!**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
    status = tp.team_status_text(fight)
    body = f"{header}{status}\n\n🎯 **راند {fight.round_no}**"
    for w in fight.all_warriors():
        if not w.alive:
            continue
        try:
            await bot.send_message(w.uid, body, reply_markup=_action_kb(fight, w))
        except Exception:
            pass


async def _maybe_resolve(fight: tp.SquadFight, bot: Bot):
    alive_uids = {w.uid for w in fight.all_warriors() if w.alive}
    if not alive_uids.issubset(set(fight.pending.keys())) or not alive_uids:
        return
    if fight.fight_id not in tp.active_fights:
        return
    await _resolve_and_advance(fight, bot)


async def _resolve_and_advance(fight: tp.SquadFight, bot: Bot):
    logs = tp.resolve_round(fight)
    log_text = "\n".join(logs) if logs else "…"
    if fight.phase == "ended":
        await _end_fight(fight, bot, log_text)
        return
    body = f"📜 **گزارشِ راند:**\n{log_text}\n\n{tp.team_status_text(fight)}\n\n🎯 **راند {fight.round_no}**"
    for w in fight.all_warriors():
        if not w.alive:
            continue
        try:
            await bot.send_message(w.uid, body, reply_markup=_action_kb(fight, w))
        except Exception:
            pass
    asyncio.create_task(_round_timeout_watcher(fight.fight_id, fight.round_no, bot))


async def _round_timeout_watcher(fight_id: str, round_at_spawn: int, bot: Bot):
    await asyncio.sleep(tp.ROUND_TIMEOUT)
    fight = tp.active_fights.get(fight_id)
    if not fight or fight.round_no != round_at_spawn or fight.phase == "ended":
        return
    for w in fight.all_warriors():
        if w.alive and w.uid not in fight.pending:
            enemies = [e for e in fight.enemy_team(w.team) if e.alive]
            if enemies:
                import random as _r
                fight.pending[w.uid] = {"type": "attack", "target": _r.choice(enemies).uid}
    await _resolve_and_advance(fight, bot)


async def _end_fight(fight: tp.SquadFight, bot: Bot, log_text: str):
    """محکم‌سازی: مثلِ pvp_handlers.py — اگه محاسبه‌ی جایزه بترکه، بازم
    فایتِ تیمی قطعاً cleanup می‌شه تا بازیکن‌ها تو PvP تیمی قفل نمونن."""
    try:
        await _end_fight_body(fight, bot, log_text)
    except Exception as e:
        log_sync(
            f"🔴 **TEAM PVP END-FIGHT CRASH** — فایت `{fight.fight_id}` با خطا "
            f"تموم شد: `{e}`. به‌صورتِ اضطراری بسته شد.",
            "ERROR",
        )
        for w in fight.all_warriors():
            try:
                await bot.send_message(
                    w.uid,
                    "⚠️ یه خطای غیرمنتظره تو محاسبه‌ی نتیجه‌ی این نبردِ تیمی پیش اومد.\n"
                    "نبرد بسته شد تا بتونید دوباره وارد PvP تیمی بشید.",
                )
            except Exception:
                pass
    finally:
        tp.cleanup_fight(fight)


async def _end_fight_body(fight: tp.SquadFight, bot: Bot, log_text: str):
    report, mvp = tp.apply_rewards(fight, get_player, save_player)
    if fight.winner == "draw":
        headline = "🤝 **نبرد مساوی شد!**"
    else:
        win_names = ", ".join(w.name for w in fight.own_team(fight.winner))
        headline = f"🏆 **تیمِ {fight.winner} برنده شد!** ({win_names})"
    mvp_line = f"\n\n👑 **MVP نبرد: {mvp.name}** (+250 Zen)" if mvp else ""

    for w in fight.all_warriors():
        r = report.get(w.uid, {})
        outcome = "🤝 مساوی" if r.get("draw") else ("✅ برد" if r.get("won") else "❌ باخت")
        personal = (
            f"\n\n📊 نتیجه‌ی تو: {outcome} | 💰 {r.get('zen',0):,} Zen | "
            f"🏅 {r.get('points',0):+d} امتیازِ لیگِ تیمی"
        )
        if r.get("mvp"):
            personal += "\n👑 تو MVP این نبرد بودی!"
        body = f"📜 **گزارشِ راندِ آخر:**\n{log_text}\n\n{headline}{mvp_line}{personal}"
        try:
            await bot.send_message(w.uid, body)
        except Exception:
            pass

    log_sync(
        f"⚔️ **TEAM PVP ENDED** | fight `{fight.fight_id}` | winner: {fight.winner}\n"
        f"👥 A: {[w.name for w in fight.team_a]}\n👥 B: {[w.name for w in fight.team_b]}",
        "PVP"
    )


# ────────────────────────────────────────────────────────────
# لیگ/آمار
# ────────────────────────────────────────────────────────────
async def cmd_teampvp_stats(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    sp = player.get("squad_pvp", {"wins": 0, "losses": 0, "points": 0, "mvp_count": 0})
    total = sp.get("wins", 0) + sp.get("losses", 0)
    wr = int(sp.get("wins", 0) / total * 100) if total else 0
    await msg.answer(
        f"📊 **آمارِ پی‌وی‌پیِ تیمیِ تو**\n\n"
        f"✅ برد: {sp.get('wins',0)} | ❌ باخت: {sp.get('losses',0)} | 📈 نرخ برد: {wr}٪\n"
        f"🏅 امتیازِ لیگ: {sp.get('points',0):,}\n"
        f"👑 دفعاتِ MVP: {sp.get('mvp_count',0)}"
    )


# ────────────────────────────────────────────────────────────
def register_team_pvp_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_teampvp, Command("teampvp"))
    dp.message.register(cmd_teampvp, F.text == "PvP تیمی")
    dp.message.register(cmd_teampvp_leave, Command("teampvp_leave"))
    dp.message.register(cmd_teampvp_stats, Command("teampvp_stats"))

    dp.callback_query.register(cb_tp_close, F.data == "tp_close")
    dp.callback_query.register(cb_tp_make, F.data.startswith("tp_mk:"))
    dp.callback_query.register(cb_tp_join, F.data.startswith("tp_j:"))
    dp.callback_query.register(cb_tp_leave_lobby, F.data.startswith("tp_lv:"))
    dp.callback_query.register(lambda cb: cb_tp_start(cb, bot), F.data.startswith("tp_st:"))
    dp.callback_query.register(lambda cb: cb_tp_queue(cb, bot), F.data.startswith("tp_q:"))

    dp.callback_query.register(cb_tp_attack, F.data.startswith("tp_a:"))
    dp.callback_query.register(cb_tp_ability, F.data.startswith("tp_b:"))
    dp.callback_query.register(cb_tp_guard, F.data.startswith("tp_g:"))
    dp.callback_query.register(cb_tp_back, F.data.startswith("tp_back:"))
    dp.callback_query.register(lambda cb: cb_tp_defend(cb, bot), F.data.startswith("tp_d:"))
    dp.callback_query.register(lambda cb: cb_tp_target(cb, bot), F.data.startswith("tp_t:"))
