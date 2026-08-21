# ============================================================
#  ASTRAL ABYSS — WORLD BOSS HANDLERS (با لاگ‌گذاری کامل)
#  چندفازی + عنصری + مکانیک‌های سپر/حمله‌ ناحیه‌ای/خشم + پاداش رتبه‌ای
# ============================================================
import asyncio
import random
import time

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, get_boss, save_boss, asave_player, aget_player
from admin_panel import is_admin
from characters import ALL_CHARACTERS
from game_data import xp_for_level, effective_max_level
from katana_system import dmg_bonus, crit_bonus, lifesteal_bonus, element_amplify_bonus
from logger import log_sync

import boss_engine as be

ATTACK_COOLDOWN_SEC = 8

# ─── Helpers ────────────────────────────────────────────────────

def _level_up(player: dict) -> bool:
    # 🐛 باگ‌فیکس: سقفِ ثابتِ ۱۵۰ با effective_max_level(player) هماهنگ
    # نبود (اگه سقفِ واقعی بازی جای دیگه‌ای تغییر کنه، اینجا از قلم می‌افتاد)
    # و HP هر لول (+۱۰) با بقیه‌ی بازی (combat/mob_combat: +۵) ناهماهنگ بود.
    from skill_tree import grant_levelup_points
    leveled = False
    old_level = player["level"]
    while player["xp"] >= xp_for_level(player["level"]) and player["level"] < effective_max_level(player):
        player["level"] += 1
        player["max_hp"] += 5
        from skill_tree import effective_max_hp
        player["hp"] = effective_max_hp(player)
        leveled = True
    if leveled:
        from class_system import scale_class_resource_on_levelup
        scale_class_resource_on_levelup(player, old_level, player["level"])  # باگ‌فیکس: مانا/استامینا/فیض هم با لول بره بالا
        grant_levelup_points(player, old_level, player["level"])
        log_sync(
            f"⭐ **LEVEL UP**\n"
            f"👤 {player.get('name','—')} (`{player.get('id','—')}`)\n"
            f"🎴 {player.get('character','—')}\n"
            f"📊 سطح: {old_level} → {player['level']}",
            "LEVELUP"
        )
    return leveled

async def _name_of(uid: int) -> str:
    p = await aget_player(uid)
    return p["name"] if p else "نامشخص"

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

def _dmg_penalty_player(player: dict, pct: float):
    max_hp = player.get("max_hp", 100)
    dmg = max(1, int(max_hp * pct))
    player["hp"] = max(1, player.get("hp", max_hp) - dmg)
    return dmg

# ─── /boss status ───────────────────────────────────────────────

async def cmd_boss(event):
    uid = event.from_user.id
    from database import get_player
    from level_gate import check_level
    player = await aget_player(uid)
    if player:
        ok, why = check_level(player, "boss")
        if not ok:
            await _reply(event, why)
            return
    boss = get_boss()
    if not boss.get("alive"):
        text = (
            "👹 **باس جهانی**\n\n"
            "😴 الان هیچ باسی زنده نیست.\n"
            "منتظر فراخوان ادمین باش! (`/spawnboss`)"
        )
        await _reply(event, text)
        return
    text = be.build_status_text(boss)
    await _reply(event, text, be.build_attack_kb(boss))

# ─── Attack ──────────────────────────────────────────────────────

async def cb_boss_hit(event):
    uid = event.from_user.id
    player = await aget_player(uid)
    if not player:
        txt = "❌ اول /start بزن!"
        if isinstance(event, CallbackQuery):
            await event.answer(txt, show_alert=True)
        else:
            await event.answer(txt)
        return

    boss = get_boss()
    if not boss.get("alive"):
        txt = "😴 باس الان زنده نیست!"
        if isinstance(event, CallbackQuery):
            await event.answer(txt, show_alert=True)
        else:
            await event.answer(txt)
        return

    now = time.time()
    since = now - player.get("last_attack", 0)
    if since < ATTACK_COOLDOWN_SEC:
        txt = f"⏳ {int(ATTACK_COOLDOWN_SEC - since)} ثانیه صبر کن!"
        if isinstance(event, CallbackQuery):
            await event.answer(txt, show_alert=True)
        else:
            await event.answer(txt)
        return

    # هر تعامل، مکانیک‌های وابسته به زمان رو هم چک می‌کنیم (safety-net؛ حلقه‌ی watcher هم داره)
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

    # لایف‌استیل کاتانا + مسیر پایداری درخت مهارت: بخشی از دمیج واقعی رو HP برمی‌گردونه
    ls = lifesteal_bonus(k_level) + skb["lifesteal"]
    healed = 0
    if ls > 0 and (result["hp_dmg"] > 0 or result["shield_dmg"] > 0):
        healed = int((result["hp_dmg"] + result["shield_dmg"]) * ls)
        if healed > 0:
            player["hp"] = min(player.get("max_hp", 100), player.get("hp", 100) + healed)

    player["last_attack"] = now
    player["combo"] = combo + 1
    player["boss_hits_total"] = player.get("boss_hits_total", 0) + 1
    from economy_engine import apply_gold_find
    from game_data import XP_GAIN_MULTIPLIER, ZEN_GAIN_MULTIPLIER
    # 🐛 باگ‌فیکس: ضربه‌های باس هیچ‌وقت ضریبِ حالتِ سختِ اقتصاد
    # (XP_GAIN_MULTIPLIER/ZEN_GAIN_MULTIPLIER) رو نمی‌گرفتن، درحالی‌که
    # کول‌داونش (۸ ثانیه) تقریباً هم‌سطحِ حمله‌ی معمولیه — یعنی
    # اسپم‌زدنِ باس تقریباً ۳.۶ برابر حمله‌ی معمولی XP می‌داد. طبق
    # کامنتِ خودِ game_data.py («این ضریب روی هر منبعِ XP اعمال می‌شه»)
    # این باید هرجا XP گرفته می‌شه اعمال بشه.
    zen_gain = apply_gold_find(player, int((random.randint(15, 40) + player["level"] // 2) * ZEN_GAIN_MULTIPLIER))
    xp_gain = int((random.randint(12, 25) + player["level"] // 3) * XP_GAIN_MULTIPLIER)
    player["zen"] += zen_gain
    player["xp"] += xp_gain
    leveled = _level_up(player)
    await asave_player(uid, player)

    log_sync(
        f"⚔️ **BOSS HIT**\n"
        f"👤 {player.get('name','—')} (`{uid}`)\n"
        f"🎴 {char_name}\n"
        f"💥 آسیب: {result['hp_dmg'] + result['shield_dmg']:,}\n"
        f"{'💥 CRIT!' if crit else ''}\n"
        f"🌀 عنصر: {result['element']}\n"
        f"📊 دمیج ضرب‌کننده: {result['mult']:.1f}x",
        "BOSS"
    )

    if result["boss_killed"]:
        from weekly_rewards import get_weekly_featured_boss_id
        is_featured = boss["template_id"] == get_weekly_featured_boss_id()
        rewards, speed_kill = be.distribute_rewards(boss, is_weekly_featured=is_featured)
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
        summary = be.build_kill_summary(boss, rewards, speed_kill, _name_of)
        boss["alive"] = False
        save_boss(boss)
        await _reply(event, summary)

        if len(boss["contributors"]) == 1:
            solo_uid = int(next(iter(boss["contributors"])))
            solo_player = await aget_player(solo_uid)
            if solo_player:
                try:
                    import tempfile, os
                    from aiogram.types import FSInputFile
                    from profile_card import generate_moment_card
                    out_path = os.path.join(tempfile.gettempdir(), f"solo_{solo_uid}.png")
                    generate_moment_card(
                        solo_player["name"], "قهرمانِ تنها",
                        f"به‌تنهایی {boss['name']} رو شکست داد!",
                        out_path, accent=(240, 180, 60),
                        footer=f"سطح {solo_player.get('level',1)} · {solo_player.get('kills',0)} کشته"
                    )
                    target_msg = event.message if isinstance(event, CallbackQuery) else event
                    await target_msg.answer_photo(FSInputFile(out_path))
                except Exception as e:
                    log_sync(f"🔴 solo-kill moment card error: {e}", "ERROR")
        return

    save_boss(boss)

    crit_txt = " 💥 **CRITICAL!**" if crit else ""
    elem_note = ""
    if result["mult"] > 1.0:
        elem_note = f" ⚡ ضعف عنصری! ({result['mult']:.1f}x)"
    elif result["mult"] < 1.0:
        elem_note = f" 🛡 مقاومت! ({result['mult']:.1f}x)"

    if result["shield_dmg"] > 0:
        dmg_line = f"⚔️ **{player['name']}** {result['shield_dmg']:,} آسیب به سپر زد!{crit_txt}{elem_note}"
        if result["shield_broken"]:
            dmg_line += "\n💥 **سپر شکست!** حالا آسیب واقعی می‌زنی!"
    else:
        dmg_line = f"⚔️ **{player['name']}** {result['hp_dmg']:,} آسیب زد!{crit_txt}{elem_note}"

    heal_txt = f"\n❤️ +{healed} HP (لایف‌استیل)" if healed > 0 else ""
    reply = (
        f"{dmg_line}\n"
        f"🌀 عنصر تو: {be.element_tag(result['element'])}  |  ⚡ Combo: {player['combo']}x{heal_txt}\n\n"
    )
    if result["phase_enter_msg"]:
        reply += result["phase_enter_msg"] + "\n\n"
    reply += be.build_status_text(boss)
    reply += f"\n\n✨ +{xp_gain} XP | 💰 +{zen_gain} BZ"
    if leveled:
        reply += f"\n\n🎉 **Level Up! → {player['level']}**"

    kb = be.build_attack_kb(boss)
    if isinstance(event, CallbackQuery):
        try:
            await event.answer(f"💥 {result['hp_dmg'] + result['shield_dmg']:,} آسیب!" + (" CRIT!" if crit else ""))
        except Exception as e:
            # toastِ بالای صفحه صرفاً تزیینیه؛ اگه به‌خاطر یه قطعیِ لحظه‌ای
            # شبکه (SSL/timeout) نره، نباید کل هندلر کرش کنه و نتیجه‌ی واقعیِ
            # نبرد (که پایین با edit_text نشون داده می‌شه) از دست بره.
            log_sync(f"⚠️ boss hit toast answer failed (ignored): {e}", "WARN")
        try:
            await event.message.edit_text(reply, reply_markup=kb)
        except Exception:
            await event.message.answer(reply, reply_markup=kb)
    else:
        await event.answer(reply, reply_markup=kb)

# ─── Defend (area attack) ────────────────────────────────────────

async def cb_boss_defend(event):
    is_cb = isinstance(event, CallbackQuery)
    uid = event.from_user.id
    boss = get_boss()
    if not boss.get("alive") or not boss.get("area_active"):
        txt = "الان چیزی برای دفاع نیست!"
        if is_cb:
            await event.answer(txt, show_alert=True)
        else:
            await event.answer(f"🛡 {txt}")
        return
    be.register_area_defense(boss, uid)
    save_boss(boss)
    log_sync(
        f"🛡 **BOSS DEFEND**\n"
        f"👤 {event.from_user.first_name} (`{uid}`)\n"
        f"🛡 دفاع ثبت شد",
        "BOSS"
    )
    if is_cb:
        await event.answer("🛡 دفاع ثبت شد! امن موندی.", show_alert=False)
    else:
        await event.answer("🛡 دفاع ثبت شد! امن موندی.")

# ─── Admin: spawn / kill / list ──────────────────────────────────

async def cmd_spawn_boss(msg: Message):
    if not is_admin(msg):
        await msg.answer("❌ فقط ادمین!")
        return
    parts = msg.text.split(maxsplit=1)
    template_id = parts[1].strip() if len(parts) > 1 else None
    if template_id and template_id not in be.WORLD_BOSS_TEMPLATES:
        names = ", ".join(be.WORLD_BOSS_TEMPLATES.keys())
        await msg.answer(f"❌ باس نامعتبر! گزینه‌ها: {names}")
        return
    if not template_id:
        from weekly_rewards import get_weekly_featured_boss_id
        template_id = get_weekly_featured_boss_id() or random.choice(list(be.WORLD_BOSS_TEMPLATES.keys()))

    # 📍 چت‌ای که ادمین توش باس رو اسپان می‌کنه رو یادمون می‌مونه تا لوپِ
    # اسپانِ خودکارِ روزانه هم بدونه کجا باید باس بذاره
    try:
        from database import system_col
        system_col().update_one(
            {"_id": "boss_spawn_chat"}, {"$set": {"chat_id": msg.chat.id}}, upsert=True
        )
    except Exception:
        pass

    boss = be.spawn_boss(template_id, msg.chat.id)
    save_boss(boss)
    tpl = be.WORLD_BOSS_TEMPLATES[template_id]
    
    log_sync(
        f"👹 **BOSS SPAWN (ADMIN)**\n"
        f"🛠 ادمین: `{msg.from_user.id}`\n"
        f"🏷️ {tpl['name']}\n"
        f"❤️ HP: {tpl['total_hp']:,}",
        "ADMIN"
    )

    from weekly_rewards import get_weekly_featured_boss_id
    if template_id == get_weekly_featured_boss_id():
        try:
            import tempfile, os
            from aiogram.types import FSInputFile
            from profile_card import generate_boss_wanted_poster
            item = be.WEEKLY_BOSS_EXCLUSIVE_ITEM.get(template_id, "—")
            out_path = os.path.join(tempfile.gettempdir(), f"weeklyboss_{template_id}.png")
            generate_boss_wanted_poster(
                tpl["name"], tpl["title"], tpl["total_hp"], item, be.WEEKLY_BOSS_BONUS_ZEN, out_path
            )
            await msg.answer_photo(FSInputFile(out_path), caption="⭐ این باسِ هفته‌ست! جایزه‌ی اختصاصی داره!")
        except Exception as e:
            log_sync(f"🔴 weekly boss poster error: {e}", "ERROR")

    await msg.answer(
        tpl["intro"] + "\n\n" + be.build_status_text(boss),
        reply_markup=be.build_attack_kb(boss)
    )


async def auto_spawn_daily_boss(bot):
    """هر روز یه باسِ جهانیِ جدید رو خودکار اسپان می‌کنه (اگه باسِ زنده‌ای
    نباشه و یه چتِ ثبت‌شده از اسپانِ دستیِ قبلیِ ادمین وجود داشته باشه)."""
    boss = get_boss()
    if boss.get("alive"):
        return  # یه باسِ دیگه هنوز زنده‌ست، صبر کن تا تموم بشه

    from database import system_col
    chat_doc = system_col().find_one({"_id": "boss_spawn_chat"})
    chat_id = chat_doc.get("chat_id") if chat_doc else None
    if not chat_id:
        return  # هنوز هیچ ادمینی دستی باس اسپان نکرده — نمی‌دونیم کجا بفرستیم

    from weekly_rewards import get_weekly_featured_boss_id
    template_id = get_weekly_featured_boss_id() or random.choice(list(be.WORLD_BOSS_TEMPLATES.keys()))
    new_boss = be.spawn_boss(template_id, chat_id)
    save_boss(new_boss)
    tpl = be.WORLD_BOSS_TEMPLATES[template_id]

    try:
        await bot.send_message(
            chat_id,
            "👹 **باسِ جهانیِ روزانه ظاهر شد!**\n\n" + tpl["intro"] + "\n\n" + be.build_status_text(new_boss),
            reply_markup=be.build_attack_kb(new_boss)
        )
    except Exception:
        pass

    log_sync(
        f"👹 **BOSS SPAWN (AUTO/DAILY)**\n🏷️ {tpl['name']}\n❤️ HP: {tpl['total_hp']:,}",
        "BOSS"
    )


DAILY_BOSS_INTERVAL = 24 * 3600
DAILY_BOSS_CHECK_INTERVAL = 3600  # هر ساعت چک کن


async def daily_boss_spawn_loop(bot: Bot):
    """هر ۲۴ ساعت یه بار (اگه باسِ زنده‌ای نباشه) خودکار یه باسِ جهانیِ
    جدید اسپان می‌کنه — دقیقاً با همون الگویِ weekly_rewards_loop."""
    from database import system_col
    while True:
        try:
            doc = system_col().find_one({"_id": "daily_boss_spawn"})
            last = doc.get("last_spawn", 0) if doc else 0
            if last == 0:
                system_col().update_one(
                    {"_id": "daily_boss_spawn"}, {"$set": {"last_spawn": time.time()}}, upsert=True
                )
            elif time.time() - last >= DAILY_BOSS_INTERVAL:
                await auto_spawn_daily_boss(bot)
                system_col().update_one(
                    {"_id": "daily_boss_spawn"}, {"$set": {"last_spawn": time.time()}}, upsert=True
                )
        except Exception:
            pass
        await asyncio.sleep(DAILY_BOSS_CHECK_INTERVAL)


async def cmd_kill_boss(msg: Message):
    if not is_admin(msg):
        await msg.answer("❌ فقط ادمین!")
        return
    boss = get_boss()
    boss["alive"] = False
    save_boss(boss)
    
    log_sync(
        f"💀 **BOSS KILL (ADMIN)**\n"
        f"🛠 ادمین: `{msg.from_user.id}`\n"
        f"🏷️ {boss.get('name', 'نامشخص')}",
        "ADMIN"
    )
    
    await msg.answer("💀 باس ریست شد.")

async def cmd_boss_list(msg: Message):
    if not is_admin(msg):
        await msg.answer("❌ فقط ادمین!")
        return
    lines = ["📜 **لیست باس‌های قابل احضار:**\n"]
    for tid, tpl in be.WORLD_BOSS_TEMPLATES.items():
        lines.append(f"• `{tid}` — {tpl['name']} ({tpl['title']})")
    lines.append("\nاستفاده: `/spawnboss <id>` یا `/spawnboss` برای رندوم")
    await msg.answer("\n".join(lines))

# ─── Background watcher: shield regen / area attack / enrage ────

async def boss_watcher_loop(bot: Bot):
    while True:
        try:
            await asyncio.sleep(6)
            boss = get_boss()
            if not boss.get("alive"):
                continue
            chat_id = boss.get("chat_id")
            if not chat_id:
                continue

            # 🩹 باگ‌فیکس: قبلاً هر تیک (شیلد/ناحیه‌ای/خشم) توی همون try/except
            # مشترک بود و state فقط *بعد* از ارسالِ پیام‌ها save_boss می‌شد —
            # یعنی اگه ارسالِ یه پیام (هرچقدرم بی‌ربط) exception می‌داد، کل
            # تغییراتِ state (مثلاً area_active=True) هیچ‌وقت ذخیره نمی‌شد و
            # باس عملاً "گیر" می‌کرد و دیگه هیچ‌وقت به بازیکن آسیب نمی‌زد.
            # حالا هر تیک تو try/except جدای خودشه و هر تغییری فوراً
            # save_boss می‌شه — یه مکانیک خراب بقیه رو نمی‌خوابونه.

            try:
                if be.tick_shield_regen(boss):
                    save_boss(boss)
                    await bot.send_message(chat_id, "🛡 **سپر باس دوباره شارژ شد!** باید دوباره بشکنیدش!")
            except Exception as e:
                print(f"[boss_watcher_loop:shield] error: {e}")

            try:
                area_action = be.tick_area_attack(boss)
                if area_action == "open":
                    save_boss(boss)
                    phase = be.WORLD_BOSS_TEMPLATES[boss["template_id"]]["phases"][boss["phase_index"]]
                    await bot.send_message(
                        chat_id,
                        f"🌊 **حمله ناحیه‌ای!** {phase['area_window_sec']} ثانیه فرصت داری «🛡 دفاع کن» رو بزنی وگرنه آسیب می‌بینی!",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(text="🛡 دفاع کن!", callback_data="bossdef", style=ButtonStyle.PRIMARY)
                        ]])
                    )
                elif area_action == "resolve":
                    penalties = be.resolve_area_attack(boss)
                    save_boss(boss)
                    penalized_names = []
                    for puid, pct in penalties:
                        p = await aget_player(puid)
                        if not p:
                            continue
                        dmg = _dmg_penalty_player(p, pct)
                        await asave_player(puid, p)
                        penalized_names.append(f"{p['name']} (-{dmg} HP)")
                    if penalized_names:
                        await bot.send_message(
                            chat_id,
                            "💥 **حمله ناحیه‌ای فرود اومد!**\nآسیب دیدگان: " + "، ".join(penalized_names)
                        )
                    else:
                        await bot.send_message(chat_id, "🛡 همه دفاع کردن! کسی آسیب ندید.")
            except Exception as e:
                print(f"[boss_watcher_loop:area] error: {e}")

            try:
                enrage_action = be.tick_enrage(boss)
                if enrage_action == "start":
                    save_boss(boss)
                    await bot.send_message(chat_id, "💢 **باس خشمگین شد!** از الان هر چند ثانیه به یکی آسیب می‌زنه!")
                elif enrage_action == "tick":
                    save_boss(boss)
                    ruid = be.pick_random_contributor(boss)
                    if ruid:
                        p = await aget_player(ruid)
                        if p:
                            dmg = _dmg_penalty_player(p, be.enrage_dmg_pct(boss))
                            await asave_player(ruid, p)
                            await bot.send_message(chat_id, f"💢 باس خشمگین به **{p['name']}** {dmg} آسیب زد!")
            except Exception as e:
                print(f"[boss_watcher_loop:enrage] error: {e}")

            # 🆕 ضدحمله‌ی پایه‌ی تضمینی — مستقل از مکانیکِ فاز (shield/area/enrage)،
            # تا باس جهانی همیشه، تو هر فازی که باشه، واقعاً به یکی از مهاجم‌ها اتک بده.
            try:
                ruid = be.tick_passive_retaliation(boss)
                save_boss(boss)
                if ruid:
                    p = await aget_player(ruid)
                    if p:
                        dmg = _dmg_penalty_player(p, be.PASSIVE_RETALIATION_DMG_PCT)
                        await asave_player(ruid, p)
                        await bot.send_message(chat_id, f"👹 **{boss.get('name','باس')}** ضدحمله زد! به **{p['name']}** {dmg} آسیب خورد!")
            except Exception as e:
                print(f"[boss_watcher_loop:passive] error: {e}")

        except Exception as e:
            print(f"[boss_watcher_loop] error: {e}")

# ─── Registration ─────────────────────────────────────────────

async def cmd_weekly_boss(msg: Message):
    from weekly_rewards import get_weekly_featured_boss_id
    tid = get_weekly_featured_boss_id()
    if not tid:
        await msg.answer("❌ فعلاً باسِ هفته‌ای تعریف نشده.")
        return
    tpl = be.WORLD_BOSS_TEMPLATES[tid]
    item = be.WEEKLY_BOSS_EXCLUSIVE_ITEM.get(tid, "—")
    try:
        import tempfile, os
        from aiogram.types import FSInputFile
        from profile_card import generate_boss_wanted_poster
        out_path = os.path.join(tempfile.gettempdir(), f"weeklyboss_{tid}.png")
        generate_boss_wanted_poster(
            tpl["name"], tpl["title"], tpl["total_hp"], item, be.WEEKLY_BOSS_BONUS_ZEN, out_path
        )
        await msg.answer_photo(FSInputFile(out_path))
    except Exception as e:
        log_sync(f"🔴 weekly boss poster error: {e}", "ERROR")
        await msg.answer(
            f"📅 **باسِ این هفته:**\n\n"
            f"{tpl['name']} — {tpl['title']}\n"
            f"❤️ HP: {tpl['total_hp']:,}\n\n"
            f"🎁 **جایزه‌ی اختصاصی برای نفر اولِ دمیج:**\n"
            f"{item}\n"
            f"💰 +{be.WEEKLY_BOSS_BONUS_ZEN:,} Zen اضافه\n\n"
            f"⏰ فقط تا آخر همین هفته قابل‌کسب‌کردنه!"
        )


def register_boss_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_boss, F.text == "باس جهانی")
    dp.message.register(cmd_boss, Command("boss"))
    dp.message.register(cb_boss_hit, Command("bosshit"))
    dp.callback_query.register(cb_boss_hit, F.data == "bosshit")
    dp.message.register(cb_boss_defend, Command("bossdef"))
    dp.callback_query.register(cb_boss_defend, F.data == "bossdef")
    dp.message.register(cmd_spawn_boss, Command("spawnboss"))
    dp.message.register(cmd_kill_boss, Command("killboss"))
    dp.message.register(cmd_boss_list, Command("bosslist"))
    dp.message.register(cmd_weekly_boss, Command("weeklyboss"))

    asyncio.create_task(boss_watcher_loop(bot))
    asyncio.create_task(daily_boss_spawn_loop(bot))
