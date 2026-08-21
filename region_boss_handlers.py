# ============================================================
#  ASTRAL ABYSS — REGION BOSS HANDLERS
# ------------------------------------------------------------
#  هر مپ یه باسِ چندنفره‌ی مستقل داره که هرکسی (تو هر چتی، حتی
#  خصوصی) می‌تونه بهش ملحق شه و باهم بزننش — لوت هم دقیقاً با
#  همون فرمولِ رتبه‌ایِ boss_engine (سهم بر اساسِ دمیج) بینِ همه‌ی
#  شرکت‌کننده‌ها عادلانه تقسیم می‌شه.
#
#  دکمه‌ی «👑 چالش باس منطقه» تو loot_handlers دیگه به یه فایتِ
#  تک‌نفره نمی‌ره — یا به باسِ زنده‌ی همون مپ ملحق می‌شه، یا اگه
#  زنده‌ای نبود، یکی تازه اسپان می‌کنه که بقیه هم می‌تونن بیان کمک.
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
from logger import log_sync

from region_boss_system import (
    get_region_boss, save_region_boss, spawn_region_boss, mark_region_boss_killed,
    region_boss_cooldown_remaining, list_active_region_bosses, top_contributors,
)

REGION_ATTACK_COOLDOWN_SEC = 8


def _map_list() -> list[str]:
    from economy import MAPS_DATA
    return list(MAPS_DATA.keys())


def _map_idx(map_name: str) -> int:
    return _map_list().index(map_name)


def _name_lookup_factory():
    cache: dict[int, str] = {}
    async def _name_of(uid: int) -> str:
        if uid not in cache:
            p = await aget_player(uid)
            cache[uid] = p.get("name", "یه بازیکن") if p else "یه بازیکن"
        return cache[uid]
    return _name_of


async def _status_with_top(map_name: str, boss: dict) -> str:
    text = be.build_status_text(boss)
    top = top_contributors(boss, 3)
    header = f"🗺 **مپ: {map_name}**\n\n"
    if not top:
        return header + text
    medals = ["🥇", "🥈", "🥉"]
    lines = ["", "📊 **بیشترین دمیج تا الان:**"]
    for i, (uid, dmg) in enumerate(top):
        p = await aget_player(uid)
        name = p.get("name", "یه بازیکن") if p else "یه بازیکن"
        lines.append(f"{medals[i]} {name}: {dmg:,}")
    return header + text + "\n" + "\n".join(lines)


def build_region_kb(map_idx: int, boss: dict) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text="⚔️ ضربه به باسِ منطقه!", callback_data=f"rbhit:{map_idx}", style=ButtonStyle.DANGER,
    )]]
    if boss.get("mechanic") == "area" and boss.get("area_active"):
        rows.append([InlineKeyboardButton(
            text="🛡 دفاع کن!", callback_data=f"rbdef:{map_idx}", style=ButtonStyle.PRIMARY,
        )])
    rows.append([InlineKeyboardButton(
        text="📨 دعوت یه دوست", callback_data=f"binv:region:{map_idx}", style=ButtonStyle.PRIMARY,
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── ورود/شروعِ باسِ منطقه — صدا زده می‌شه از دکمه‌ی «چالش باس منطقه» ──

async def enter_region_boss(msg, uid: int, map_name: str):
    """اگه باسِ این مپ زنده‌ست بهش ملحق می‌شه، وگرنه یکی تازه اسپان می‌کنه."""
    map_idx = _map_idx(map_name)
    boss = get_region_boss(map_name)

    if boss and boss.get("alive"):
        be.tick_shield_regen(boss)
        save_region_boss(map_name, boss)
        await msg.edit_text(
            f"👥 **یه باسِ منطقه‌ای اینجا در جریانه!** به بقیه ملحق شو:\n\n"
            + await _status_with_top(map_name, boss),
            reply_markup=build_region_kb(map_idx, boss),
        )
        return

    cooldown = region_boss_cooldown_remaining(map_name)
    if cooldown > 0:
        mins, secs = divmod(cooldown, 60)
        await msg.edit_text(
            f"😴 باسِ قبلیِ این مپ تازه شکست خورده — {mins} دقیقه و {secs} ثانیه تا باسِ بعدی این مپ صبر کن.\n\n"
            f"می‌تونی از دکمه‌ی «🔙 برگشت به نقشه» بری قسمتِ دیگه‌ای رو بگردی."
        )
        return

    boss = spawn_region_boss(map_name)
    tpl = be.WORLD_BOSS_TEMPLATES[boss["template_id"]]
    log_sync(
        f"🗺👹 **REGION BOSS SPAWNED**\n📍 مپ: {map_name}\n🏷️ {tpl['name']}\n🚀 شروع‌کننده: `{uid}`",
        "REGION_BOSS"
    )
    from map_activity import log_event
    p = await aget_player(uid)
    log_event(map_name, p.get("name", "یه بازیکن") if p else "یه بازیکن", "boss", map_name, actor_id=uid)

    await msg.edit_text(
        f"👑 **باسِ منطقه‌ای در این مپ ظاهر شد!**\n"
        f"هرکی (تو هر چتی، حتی خصوصی) اومد سراغِ این مپ می‌تونه ملحق شه و لوت رو با بقیه‌ی ضربه‌زن‌ها به‌نسبتِ دمیج‌شون شریک بشه.\n"
        f"می‌تونی با دکمه‌ی «📨 دعوت یه دوست» یه بازیکنِ دیگه رو مستقیم صدا کنی.\n\n"
        + tpl["intro"] + "\n\n" + await _status_with_top(map_name, boss),
        reply_markup=build_region_kb(map_idx, boss),
    )


# ─── حمله ────────────────────────────────────────────────────────

async def cb_region_boss_hit(cb: CallbackQuery):
    uid = cb.from_user.id
    try:
        map_idx = int(cb.data.split(":")[1])
        map_name = _map_list()[map_idx]
    except Exception:
        await cb.answer("❌ خطا!", show_alert=True)
        return

    player = await aget_player(uid)
    if not player or not player.get("class"):
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return

    boss = get_region_boss(map_name)
    if not boss or not boss.get("alive"):
        await cb.answer("😴 این باس دیگه زنده نیست!", show_alert=True)
        return

    now = time.time()
    since = now - player.get("last_region_hit", 0)
    if since < REGION_ATTACK_COOLDOWN_SEC:
        await cb.answer(f"⏳ {int(REGION_ATTACK_COOLDOWN_SEC - since)} ثانیه صبر کن!", show_alert=True)
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
    raw_dmg = int((base + player["level"] * 2.5 + k_bonus + random.randint(-3, 12)) * combo_mult)
    raw_dmg = int(raw_dmg * _pulse_val("boss_dmg_mult"))

    crit_chance = 0.15 + crit_bonus(k_level) + skb["crit_chance"] + _pulse_val("crit_add")
    crit_chance = max(0.0, crit_chance)
    crit = random.random() < crit_chance
    if crit:
        raw_dmg = int(raw_dmg * (2.0 + skb["crit_dmg_bonus"]))

    amplify = element_amplify_bonus(k_level) + skb["elem_amp"]
    result = be.process_attack(boss, uid, char_name, raw_dmg, amplify_bonus=amplify)

    ls = lifesteal_bonus(k_level) + skb["lifesteal"]
    healed = 0
    if ls > 0 and (result["hp_dmg"] > 0 or result["shield_dmg"] > 0):
        healed = int((result["hp_dmg"] + result["shield_dmg"]) * ls)
        if healed > 0:
            player["hp"] = min(player.get("max_hp", 100), player.get("hp", 100) + healed)

    player["last_region_hit"] = now
    player["combo"] = combo + 1
    player["boss_hits_total"] = player.get("boss_hits_total", 0) + 1
    from economy_engine import apply_gold_find
    from game_data import XP_GAIN_MULTIPLIER, ZEN_GAIN_MULTIPLIER
    zen_gain = apply_gold_find(player, int((random.randint(15, 40) + player["level"] // 2) * ZEN_GAIN_MULTIPLIER))
    xp_gain = int((random.randint(12, 25) + player["level"] // 3) * XP_GAIN_MULTIPLIER)
    player["zen"] += zen_gain
    player["xp"] += xp_gain

    from game_data import xp_for_level, effective_max_level
    leveled = False
    old_level = player["level"]
    while player["xp"] >= xp_for_level(player["level"]) and player["level"] < effective_max_level(player):
        player["level"] += 1
        player["max_hp"] += 5
        from skill_tree import effective_max_hp
        player["hp"] = effective_max_hp(player)
        leveled = True
    if leveled:
        from skill_tree import grant_levelup_points
        grant_levelup_points(player, old_level, player["level"])

    await asave_player(uid, player)

    log_sync(
        f"⚔️ **REGION BOSS HIT**\n👤 {player.get('name','—')} (`{uid}`)\n📍 مپ: {map_name}\n"
        f"💥 آسیب: {result['hp_dmg'] + result['shield_dmg']:,}",
        "REGION_BOSS"
    )

    if result["boss_killed"]:
        rewards, speed_kill = be.distribute_rewards(boss)
        for ruid, r in rewards.items():
            rp = await aget_player(ruid)
            if not rp:
                continue
            rp["zen"] += r["zen"]
            if r["titles"]:
                rp.setdefault("boss_titles", [])
                rp["boss_titles"].extend(r["titles"])
            if r.get("items"):
                rp.setdefault("inventory", []).extend(r["items"])
            await asave_player(ruid, rp)

        summary = be.build_kill_summary(boss, rewards, speed_kill, _name_lookup_factory())
        boss["alive"] = False
        save_region_boss(map_name, boss)
        mark_region_boss_killed(map_name)
        _verify = get_region_boss(map_name)
        log_sync(
            f"🩺 **REGION BOSS KILL-SAVE CHECK**\n📍 مپ: {map_name}\n"
            f"alive بعدِ سیو: {_verify.get('alive') if _verify else 'DOC NOT FOUND'}",
            "REGION_BOSS"
        )

        try:
            from map_activity import log_event
            log_event(map_name, player.get("name", "یه بازیکن"), "boss_kill", map_name, actor_id=uid)
        except Exception:
            pass

        log_sync(
            f"💀 **REGION BOSS DEFEATED**\n📍 مپ: {map_name}\n👥 شرکت‌کنندگان: {len(boss['contributors'])}",
            "REGION_BOSS"
        )

        await cb.answer("💀 باسِ منطقه شکست خورد!")
        try:
            await cb.message.edit_text(f"🗺 **مپ: {map_name}**\n\n{summary}", reply_markup=None)
        except Exception:
            await cb.message.answer(f"🗺 **مپ: {map_name}**\n\n{summary}")

        # به بقیه‌ی شرکت‌کننده‌ها (که هرکدوم تو چتِ خودشون بودن) هم پی‌وی نتیجه رو بفرست
        for ruid_str in boss["contributors"]:
            ruid = int(ruid_str)
            if ruid == uid:
                continue
            try:
                await cb.message.bot.send_message(ruid, f"🗺 **مپ: {map_name}**\n\n{summary}")
            except Exception:
                pass
        return

    save_region_boss(map_name, boss)

    crit_txt = " 💥 **CRITICAL!**" if crit else ""
    elem_note = ""
    if result["mult"] > 1.0:
        elem_note = f" ⚡ ضعف عنصری! ({result['mult']:.1f}x)"
    elif result["mult"] < 1.0:
        elem_note = f" 🛡 مقاومت! ({result['mult']:.1f}x)"

    if result["shield_dmg"] > 0:
        dmg_line = f"⚔️ **{player['name']}** {result['shield_dmg']:,} آسیب به سپر زد!{crit_txt}{elem_note}"
        if result["shield_broken"]:
            dmg_line += "\n💥 **سپر شکست!**"
    else:
        dmg_line = f"⚔️ **{player['name']}** {result['hp_dmg']:,} آسیب زد!{crit_txt}{elem_note}"

    heal_txt = f"\n❤️ +{healed} HP (لایف‌استیل)" if healed > 0 else ""
    reply = f"{dmg_line}\n🌀 عنصر تو: {be.element_tag(result['element'])}{heal_txt}\n\n"
    if result["phase_enter_msg"]:
        reply += result["phase_enter_msg"] + "\n\n"
    reply += await _status_with_top(map_name, boss)
    reply += f"\n\n✨ +{xp_gain} XP | 💰 +{zen_gain} BZ"
    if leveled:
        reply += f"\n\n🎉 **Level Up! → {player['level']}**"

    kb = build_region_kb(map_idx, boss)
    await cb.answer(f"💥 {result['hp_dmg'] + result['shield_dmg']:,} آسیب!" + (" CRIT!" if crit else ""))
    try:
        await cb.message.edit_text(reply, reply_markup=kb)
    except Exception:
        await cb.message.answer(reply, reply_markup=kb)


# ─── دفاع ─────────────────────────────────────────────────────────

async def cb_region_boss_defend(cb: CallbackQuery):
    uid = cb.from_user.id
    try:
        map_idx = int(cb.data.split(":")[1])
        map_name = _map_list()[map_idx]
    except Exception:
        await cb.answer("❌ خطا!", show_alert=True)
        return

    boss = get_region_boss(map_name)
    if not boss or not boss.get("alive") or not boss.get("area_active"):
        await cb.answer("الان چیزی برای دفاع نیست!", show_alert=True)
        return
    be.register_area_defense(boss, uid)
    save_region_boss(map_name, boss)
    await cb.answer("🛡 دفاع ثبت شد! امن موندی.")


# ─── واچرِ پس‌زمینه (سپر/ناحیه/خشم) — به همه‌ی شرکت‌کننده‌های فعلی پی‌وی می‌ده ──

def _dmg_penalty_player(player: dict, pct: float) -> int:
    max_hp = player.get("max_hp", 100)
    dmg = max(1, int(max_hp * pct))
    player["hp"] = max(1, player.get("hp", max_hp) - dmg)
    return dmg


async def _process_region_boss_tick(bot: Bot, map_name: str):
    """پردازشِ tick یه مپِ خاص — جدا از بقیه‌ی مپ‌ها، تا اگه یه استثنا
    وسطِ کارِ این مپ بیفته (مثلاً یه send_message که fail می‌شه)، بقیه‌ی
    مپ‌ها رو متوقف نکنه و از اول لوپ نندازتشون.
    🐛 باگ‌فیکس: قبلاً وضعیتِ tick‌شده (last_enrage_tick و غیره) فقط
    بعدِ فرستادنِ همه‌ی پیام‌ها ذخیره می‌شد. اگه وسطِ فرستادنِ پیام‌ها
    (برای هر مپی، نه لزوماً همین) یه استثنا می‌افتاد، کل حلقه از اول
    شروع می‌شد و این مپ با last_enrage_tick کهنه دوباره پردازش می‌شد —
    یعنی همون تیکِ خشمِ قبلی دوباره (و دوباره، و دوباره...) اجرا می‌شد،
    چون وضعیتش هیچ‌وقت واقعاً پیش نمی‌رفت. الان وضعیت بلافاصله بعدِ
    تصمیم‌گیری ذخیره می‌شه، قبل از هر await برای فرستادنِ پیام."""
    boss = get_region_boss(map_name)
    if not boss or not boss.get("alive"):
        return

    changed = be.tick_shield_regen(boss)
    area_action = be.tick_area_attack(boss)
    area_penalties = be.resolve_area_attack(boss) if area_action == "resolve" else None
    if area_action:
        changed = True
    enrage_action = be.tick_enrage(boss)
    enrage_target = be.pick_random_contributor(boss) if enrage_action == "tick" else None
    if enrage_action:
        changed = True

    # وضعیت رو همین‌جا سیو کن — قبل از هر await ارسالِ پیام — تا اگه
    # پایین‌تر استثنا افتاد، دفعه‌ی بعد دوباره از همینجا شروع نشه.
    if changed:
        save_region_boss(map_name, boss)

    if area_action == "open":
        phase = be.WORLD_BOSS_TEMPLATES[boss["template_id"]]["phases"][boss["phase_index"]]
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
            text="🛡 دفاع کن!", callback_data=f"rbdef:{_map_idx(map_name)}", style=ButtonStyle.PRIMARY,
        )]])
        for uid_str in boss["contributors"]:
            try:
                await bot.send_message(
                    int(uid_str),
                    f"🌊 **حمله ناحیه‌ای در {map_name}!** {phase['area_window_sec']} ثانیه فرصت داری «🛡 دفاع کن» رو بزنی!",
                    reply_markup=kb,
                )
            except Exception:
                pass
    elif area_action == "resolve" and area_penalties:
        for puid, pct in area_penalties:
            p = await aget_player(puid)
            if not p:
                continue
            dmg = _dmg_penalty_player(p, pct)
            await asave_player(puid, p)
            try:
                await bot.send_message(puid, f"💥 **حمله ناحیه‌ای فرود اومد!** -{dmg} HP")
            except Exception:
                pass

    if enrage_action == "start":
        for uid_str in boss["contributors"]:
            try:
                await bot.send_message(int(uid_str), f"💢 **باسِ منطقه‌ی {map_name} خشمگین شد!**")
            except Exception:
                pass
    elif enrage_action == "tick" and enrage_target:
        p = await aget_player(enrage_target)
        if p:
            dmg = _dmg_penalty_player(p, be.enrage_dmg_pct(boss))
            await asave_player(enrage_target, p)
            try:
                await bot.send_message(enrage_target, f"💢 باسِ خشمگینِ {map_name} به تو {dmg} آسیب زد!")
            except Exception:
                pass


async def region_boss_watcher_loop(bot: Bot):
    while True:
        try:
            for stale_boss in list_active_region_bosses():
                map_name = stale_boss["map_name"]
                try:
                    await _process_region_boss_tick(bot, map_name)
                except Exception as e:
                    log_sync(f"🔴 region boss watcher error (map={map_name}): {e}", "ERROR")
        except Exception as e:
            log_sync(f"🔴 region boss watcher error: {e}", "ERROR")
        await asyncio.sleep(15)


def register_region_boss_handlers(dp: Dispatcher, bot: Bot):
    dp.callback_query.register(cb_region_boss_hit, F.data.startswith("rbhit:"))
    dp.callback_query.register(cb_region_boss_defend, F.data.startswith("rbdef:"))
    asyncio.create_task(region_boss_watcher_loop(bot))
