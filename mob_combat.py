# ============================================================
#  ASTRAL ABYSS — Mob Encounters & Map Bosses
#  Wires the existing "Ultra Combat System" (combat.py) into
#  the /loot flow, and adds a dedicated boss per map.
# ============================================================
import asyncio
import random
import secrets
from aiogram import Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
from logger import log_sync
from action_lock import no_double_tap
from combat import (
    ENEMIES, MAP_ENEMIES, get_map_enemies, calc_combat,
    get_drop, hp_bar, ATTACK_TYPES,
    maybe_ambush, maybe_deadly_blow,
)
from game_data import xp_for_level, effective_max_level, rebirth_bonuses
from isekai_theme import rank_up_announcement
from economy import bz_to_display

# ─── حالت سخت وحشتناک: خودترمیمی باس منطقه (تشدید شد) ───────────
BOSS_SELF_HEAL_EVERY_N_TURNS = 3  # قبلاً هر ۴ راند
BOSS_SELF_HEAL_PCT = 0.08          # قبلاً ۵٪
BOSS_SELF_HEAL_CAP = 100_000       # 🩹 باگ‌فیکس: با باس‌های HP خیلی بالا (میلیونی)
                                    # ۸٪ درصدی می‌شد چند صدهزار HP در هر ترمیم؛
                                    # الان هرچی کمتر بین (۸٪ از max_hp) و این سقف حساب می‌شه.

# ─── حالت سخت: تعقیب بعد از فرار ────────────────────────────────
# اگه از یه مواجهه فرار کنی، ۵۰٪ شانس هست دشمن دنبالت بیاد و تو
# اولین مواجهه‌ی بعدی (تو هر مپی که بری) بی‌مقدمه بهت حمله کنه.
PURSUE_CHANCE_ON_FLEE = 0.5

# 🆕 باگ‌فیکس: فرار از باس حالا همیشه ممکنه (قبلاً دکمه‌ش اصلاً نبود).
# فقط یه شانس هست که قبل از در رفتن یه ضربه از باس بخوری — بدون این
# که هیچ‌وقت واقعاً "گیر" بیفتی و مجبور به ادامه‌ی جنگ باشی.
BOSS_FLEE_HIT_CHANCE = 0.6
BOSS_FLEE_HIT_DMG_PCT = 0.25   # درصدی از دمیجِ باس

# ─── Map Bosses ────────────────────────────────────────────────
# 🆕 استخرِ باس‌های هر مپ (guardian/warlord/harbinger) حالا تو
# map_boss_pool.py متمرکز شده — ۴۵ باسِ متمایز جمعاً، به‌جای یکی
# ثابت به‌ازای هر مپ. build_boss_enemy() خودش انتخاب/وزن‌دهی می‌کنه.
from map_boss_pool import build_boss_enemy, awaken_message

BOSS_AMBUSH_CHANCE = 0.05   # شانس ظاهر شدن ناگهانی باس حین لوت عادی
BOSS_ACTION_COST   = 2      # هزینه اقدام برای چالش مستقیم باس (دیگه استفاده نمی‌شه، فقط برای سازگاری)
MIN_HP_PCT_FOR_BOSS_CHALLENGE = 0.5  # حداقل ۵۰٪ HP برای رفتن سراغ باس

# 🆕 حالت بقای پلیرِ تازه‌وارد: باس‌های مپ ۴۵ تا ۲۵۵ دمیج می‌زنن، در حالی
# که یه کاراکترِ تازه‌ساز فقط ۱۰۰ HP داره و هیچ تجهیزاتی نداره. قبلاً
# BOSS_AMBUSH_CHANCE بدونِ هیچ شرطی رو هر لوکیشنی چک می‌شد — یعنی حتی تو
# اولین لوتِ بعدِ تیوتوریال هم ممکن بود بدونِ هشدار به یه باس بخوره و
# یک‌ضربه‌ای (یا نزدیک به اون) بمیره. الان تا سطح BOSS_AMBUSH_MIN_LEVEL
# نرسیده، کمینِ باس اصلاً رول نمی‌شه — چالشِ مستقیمِ باس (دکمه‌ی جدا، با
# گیتِ HP بالا) همچنان همیشه در دسترسه، این فقط جلوی سورپرایزِ ناخواسته رو می‌گیره.
BOSS_AMBUSH_MIN_LEVEL = 3

encounter_sessions: dict[int, dict] = {}

# ─── Dungeon Discovery ───────────────────────────────────────
# باس دیگه با یه دکمه مستقیم قابل چالش نیست؛ فقط با پیدا کردن یه
# دروازه‌ی دانجن حین لوت معمولی (شانسی یا بعد از N بار لوت موفق تو
# همون مپ) و رد کردن چند مرحله‌ی ریسک/لوت می‌شه بهش رسید.
dungeon_progress: dict[int, dict] = {}   # uid -> {"map":str,"count":int,"threshold":int}
dungeon_state:    dict[int, dict] = {}   # uid -> {"map":str,"stage":int,"total":int}

DUNGEON_FIND_CHANCE  = 0.12   # شانس پیدا شدن دروازه بعد از هر لوت موفق
DUNGEON_PROGRESS_MIN = 3      # حداقل تعداد لوت موفق تا تضمین پیدا شدن دروازه
DUNGEON_PROGRESS_MAX = 5
DUNGEON_STAGES_MIN   = 2      # تعداد مراحل ریسک/لوت داخل دانجن قبل از باس
DUNGEON_STAGES_MAX   = 3

# ─── Helpers ─────────────────────────────────────────────────
def _build_wild_enemy(map_name: str) -> dict:
    picked = get_map_enemies(map_name, count=1)
    if picked:
        e = picked[0]
    else:
        name, e = random.choice(list(ENEMIES.items()))
        e = e.copy()
        e["name"] = name
    e["max_hp"] = e.get("hp", 100)
    e["is_boss"] = False

    # 🌟 شانسِ کمی هست به‌جاش Apex Mob امضادارِ همین مپ ظاهر بشه
    from apex_mobs import maybe_spawn_apex
    e = maybe_spawn_apex(map_name, e)
    return e

def _encounter_kb(uid: int, is_boss: bool, token: str, player: dict | None = None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=ATTACK_TYPES["quick"]["name"],   callback_data=f"mob:quick:{uid}:{token}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text=ATTACK_TYPES["heavy"]["name"],   callback_data=f"mob:heavy:{uid}:{token}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text=ATTACK_TYPES["element"]["name"], callback_data=f"mob:element:{uid}:{token}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text=ATTACK_TYPES["combo"]["name"],   callback_data=f"mob:combo:{uid}:{token}", style=ButtonStyle.PRIMARY)],
    ]
    # 🔍 مهارتِ تشخیص (appraisal_system.py) — فقط اگه باز شده باشه
    if player is not None:
        try:
            import appraisal_system as aps
            if aps.is_unlocked(player):
                rows.append([InlineKeyboardButton(text="🔍 آنالیز", callback_data=f"mob:appraise:{uid}:{token}", style=ButtonStyle.SECONDARY)])
        except Exception:
            pass
    # 🆕 باگ‌فیکس: قبلاً از باس/نمسیس اصلاً نمی‌شد فرار کرد (دکمه‌ش نبود).
    # حالا همیشه هست — فقط فرار از باس ریسک داره (ممکنه یه ضربه بخوری).
    flee_label = "🏃 فرار (ریسکی از باس!)" if is_boss else "🏃 فرار"
    rows.append([InlineKeyboardButton(text=flee_label, callback_data=f"mob:flee:{uid}:{token}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def _render(player: dict, enemy: dict, is_boss: bool, logs: list[str] | None = None) -> str:
    from loot_engine import get_streak_title
    from elite_mobs import elite_intro_line
    from apex_mobs import apex_intro_line
    from mob_abilities import ability_intro_line
    boss_tier = enemy.get("boss_tier")
    if enemy.get("is_apex"):
        title = "🌟 **مواجهه با یک Apex نایاب!**"
    elif is_boss and boss_tier == "harbinger":
        title = "👑💀 **باسِ نادرِ دانجن!**"
    elif is_boss and boss_tier == "warlord":
        title = "👑 **باسِ سنگینِ مپ!**"
    elif is_boss:
        title = "👑 **مبارزه با باس مپ!**"
    else:
        title = "⚔️ **مواجهه با موجود وحشی!**"
    streak = player.get("loot_streak", 0)
    streak_title = get_streak_title(streak)
    epithet_line = f"_{enemy['epithet']}_\n" if enemy.get("epithet") else ""
    body = (
        f"{title}\n\n"
        f"{apex_intro_line(enemy)}"
        f"{elite_intro_line(enemy)}"
        f"{ability_intro_line(enemy)}"
        f"**{enemy['name']}**\n"
        f"{epithet_line}"
        f"🔴 HP: {enemy['hp']}/{enemy['max_hp']}\n{hp_bar(enemy['hp'], enemy['max_hp'])}\n\n"
        f"❤️ تو: {player.get('hp',100)}/{player.get('max_hp',100)}\n{hp_bar(player.get('hp',100), player.get('max_hp',100))}\n"
        f"⚡ Combo: {player.get('combo',0)}x\n"
        f"🔥 استریک لوت: {streak}x" + (f" {streak_title}" if streak_title else "") + "\n"
    )
    if logs:
        body += "\n" + "\n".join(logs)
    return body

# ─── Start Encounter ─────────────────────────────────────────
async def start_encounter(msg: Message, uid: int, map_name: str, force_boss: bool = False):
    player = get_player(uid)
    if not player:
        return

    is_boss = force_boss or (
        player.get("level", 1) >= BOSS_AMBUSH_MIN_LEVEL and random.random() < BOSS_AMBUSH_CHANCE
    )
    nemesis_enemy = None
    if not is_boss:
        from nemesis_system import maybe_spawn_nemesis
        nemesis_enemy = maybe_spawn_nemesis(player)
    enemy = nemesis_enemy or (
        build_boss_enemy(map_name, "dungeon" if force_boss else "ambush") if is_boss else _build_wild_enemy(map_name)
    )
    if not is_boss and not nemesis_enemy:
        from elite_mobs import maybe_elevate
        enemy = maybe_elevate(enemy, player, map_name)

    session_data = {"enemy": enemy, "map": map_name, "is_boss": is_boss, "turn": 0, "token": secrets.token_hex(4),
                     "enemy_snapshot": dict(enemy)}  # 🔁 برای loop_system.py — حالتِ اولیهٔ دشمن برای ریست
    encounter_sessions[uid] = session_data
    # 🆕 علاوه بر حافظه، رو خودِ رکورد بازیکن هم ذخیره‌ش می‌کنیم — اگه ربات
    # وسط مبارزه ری‌استارت بشه (دیپلوی/کرش)، دیگه مبارزه گم نمی‌شه.
    player["_active_encounter"] = session_data

    text = _render(player, enemy, is_boss)
    if enemy.get("is_nemesis"):
        text = f"⚠️ **{enemy['name']}** دوباره پیدات کرده! این‌بار قوی‌تره...\n\n" + text
    elif is_boss and force_boss and enemy.get("boss_tier") == "harbinger":
        text = "👑💀 **دانجن، یه باسِ نادر و کشنده رو تحویلت داد!** آماده باش...\n\n" + text
    elif is_boss and force_boss:
        text = "👑 **باس مپ ظاهر شد!** آماده باش...\n\n" + text
    elif is_boss:
        text = "⚠️ **این یه موجود معمولی نبود... باس مپ کمین کرده بود!**\n\n" + text

    # ─── حالت سخت: دشمنی که از فرار قبلی دنبالت اومده بود ──────
    if player.pop("_pursuing_enemy", False) and not force_boss:
        text = "🏃‍♂️➡️ **دشمنی که ازش فرار کرده بودی دنبالت اومد و بی‌مقدمه بهت حمله کرد!**\n\n" + text

    # ─── حالت سخت: کمین ──────────────────────────────────────────
    amb = None if is_boss else maybe_ambush(player, enemy)
    if amb:
        player["hp"] = max(0, player.get("hp", 100) - amb["dmg"])
        text = f"{amb['msg']}\n\n" + text

    # 🔍 مهارتِ تشخیص — چکِ باز شدنِ خودکار (سطح ۵)
    import appraisal_system as aps
    if aps.check_auto_unlock(player):
        text = f"{aps.unlock_announcement()}\n\n" + text

    save_player(uid, player)

    kb = _encounter_kb(uid, is_boss, session_data["token"], player)
    try:
        await msg.edit_text(text, reply_markup=kb)
    except Exception:
        await msg.answer(text, reply_markup=kb)

# ─── Resolve a Round ─────────────────────────────────────────
@no_double_tap()
async def handle_mob_attack(cb: CallbackQuery):
    parts = cb.data.split(":")
    if len(parts) < 3:
        await cb.answer("❌ خطا!", show_alert=True); return
    attack_type, cb_uid = parts[1], int(parts[2])
    msg_token = parts[3] if len(parts) > 3 else None
    uid = cb.from_user.id
    if cb_uid != uid:
        await cb.answer("❌ این مبارزه برای تو نیست!", show_alert=True); return

    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return

    session = encounter_sessions.get(uid)
    if not session:
        # 🆕 بازیابیِ مبارزه بعد از ری‌استارت ربات: قبلاً این سشن فقط تو
        # حافظه‌ی پروسه بود و با هر ری‌استارت (دیپلوی/کرش/خواب رفتنِ هاست)
        # گم می‌شد — حتی اگه دشمن نزدیک مرگ بود. حالا از رو خودِ رکوردِ
        # بازیکن (که هر تِرن ذخیره می‌شه) بازیابی می‌شه.
        recovered = player.get("_active_encounter")
        if recovered:
            session = recovered
            encounter_sessions[uid] = session
        else:
            await cb.answer("⏰ مبارزه منقضی شد!", show_alert=True); return

    # 🆕 باگ‌فیکس: اگه این پیام مالِ یه مبارزه‌ی قدیمی‌تره (مثلاً رفتی لوت
    # جدید زدی و یه مبارزه‌ی تازه شروع شده)، این دکمه دیگه به مبارزه‌ی
    # فعلی وصل نیست — نذار روی مبارزه‌ی الان اثر بذاره (این دقیقاً همون
    # باگی بود که «برمی‌گردی بالا، به پیامِ باسِ قبلی حمله می‌زنی» می‌شد).
    if session.get("token") and msg_token != session.get("token"):
        await cb.answer("⏰ این پیام مالِ یه مبارزه‌ی قدیمیه که تموم شده! پیامِ جدیدترو نگاه کن.", show_alert=True)
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    # 🆕 باگ‌فیکس: سشن‌هایی که از رکوردِ قدیمیِ بازیکن (player["_active_encounter"])
    # بازیابی می‌شن، اگه مالِ قبل از اضافه‌شدنِ فیلدِ "token" باشن، اون کلید رو
    # ندارن — و session["token"] با subscript مستقیم یه KeyError کرش‌کننده
    # می‌داد (دقیقاً همون popup «یه مشکلی پیش اومد» رو نشون می‌داد). حالا
    # اگه token غایب باشه، همون‌جا یکی می‌سازیم و ذخیره می‌کنیم.
    if "token" not in session:
        session["token"] = secrets.token_hex(4)

    enemy   = session["enemy"]
    is_boss = session["is_boss"]
    map_name = session["map"]

    if attack_type == "appraise":
        # 🔍 مهارتِ تشخیص — فقط اطلاعات نشون می‌ده، نوبت مصرف نمی‌شه
        import appraisal_system as aps
        if aps.is_unlocked(player):
            await cb.answer(aps.appraise_enemy(enemy), show_alert=True)
        else:
            await cb.answer(f"🔒 مهارتِ تشخیص هنوز باز نشده (سطح {aps.UNLOCK_LEVEL}).", show_alert=True)
        return

    if attack_type == "flee":
        from loot_engine import guard_streak_loss
        del encounter_sessions[uid]
        player.pop("_active_encounter", None)
        saved = guard_streak_loss(player)
        from nemesis_system import handle_nemesis_on_loss
        nemesis_msg = handle_nemesis_on_loss(player, enemy)

        # 🆕 باگ‌فیکس: قبلاً از باس اصلاً نمی‌شد فرار کرد (دکمه نبود).
        # حالا می‌شه — همیشه موفق می‌شی فرار کنی، فقط اگه حریف باس/نمسیس
        # باشه یه شانسی هست که قبل از فرار یه ضربه بخوری.
        hit_text = ""
        if is_boss and random.random() < BOSS_FLEE_HIT_CHANCE:
            dmg = max(1, int(enemy.get("dmg", 20) * BOSS_FLEE_HIT_DMG_PCT))
            player["hp"] = max(1, player.get("hp", 100) - dmg)
            hit_text = f"\n🩸 قبل از اینکه در بری، {enemy['name']} یه ضربه‌ی {dmg} بهت زد."

        # ─── حالت سخت: شانس دشمن دنبالت بیاد (فقط دشمن‌های معمولی) ──
        pursued = (not is_boss) and random.random() < PURSUE_CHANCE_ON_FLEE
        if pursued:
            player["_pursuing_enemy"] = True
        save_player(uid, player)
        text = "🏃 فرار کردی! دست‌خالی برگشتی." + hit_text
        text += "\n🍀 طلسم شانس فعال شد و استریک لوتت حفظ موند!" if saved else "\n💔 استریک لوتت صفر شد."
        if nemesis_msg:
            text += f"\n\n{nemesis_msg}"
        if pursued:
            text += "\n⚠️ **حس می‌کنی یه چیزی داره دنبالت میاد...**"
        await cb.message.edit_text(text, reply_markup=None)
        await cb.answer()
        return

    result = calc_combat(player, enemy, attack_type)
    enemy["hp"] = max(0, enemy["hp"] - result["dmg"])
    if not result["miss"]:
        player["combo"] = player.get("combo", 0) + 1
    else:
        player["combo"] = 0

    # ─── باگ‌فیکس: لایف‌استیل قبلاً محاسبه می‌شد ولی هیچ‌جا به HP اضافه نمی‌شد ─
    if result.get("lifesteal_heal", 0) > 0:
        player["hp"] = min(player.get("max_hp", 100), player.get("hp", 100) + result["lifesteal_heal"])

    if result.get("enemy_dmg", 0) > 0:
        player["hp"] = max(0, player.get("hp", 100) - result["enemy_dmg"])
        if result.get("reflect_dmg", 0) > 0:
            enemy["hp"] = max(0, enemy["hp"] - result["reflect_dmg"])

    # ─── حالت سخت: ضربه مرگبار دشمنان سطح‌بالا ─────────────────
    if player.get("hp", 100) > 0:
        deadly = maybe_deadly_blow(player, enemy)
        if deadly:
            player["hp"] = max(0, player.get("hp", 100) - deadly["dmg"])
            result["logs"].append(deadly["msg"])

    # 💫 بیداریِ استتِ مخفی (hidden_awakening.py) — یه‌بار در کل بازی،
    # وقتی خیلی نزدیکِ مرگی یه شانسِ کوچیک هست یه استتِ نهفته بیدار بشه.
    if player.get("hp", 100) > 0:
        from hidden_awakening import maybe_awaken
        awakening = maybe_awaken(player)
        if awakening:
            result["logs"].append(awakening["msg"])

    # 👑 فازِ بیداری — زیرِ یه درصدِ مشخص از HP، باس واقعاً قوی‌تر می‌شه
    # (فقط یه‌بار در طولِ کل مبارزه فعال می‌شه)
    if is_boss and enemy["hp"] > 0 and not enemy.get("_awakened"):
        awaken_pct = enemy.get("awaken_pct", 0.35)
        if enemy["hp"] <= enemy.get("max_hp", enemy["hp"]) * awaken_pct:
            enemy["_awakened"] = True
            enemy["dmg"] = int(enemy.get("dmg", 20) * enemy.get("awaken_mult", 1.35))
            result["logs"].append(awaken_message(enemy))

    # ─── حالت سخت: خودترمیمی باس منطقه (اثر ویژه) ───────────────
    session["turn"] = session.get("turn", 0) + 1
    if is_boss and enemy["hp"] > 0 and session["turn"] % BOSS_SELF_HEAL_EVERY_N_TURNS == 0:
        heal = min(int(enemy.get("max_hp", enemy["hp"]) * BOSS_SELF_HEAL_PCT), BOSS_SELF_HEAL_CAP)
        enemy["hp"] = min(enemy.get("max_hp", enemy["hp"]), enemy["hp"] + heal)
        result["logs"].append(f"💫 **باس خودش رو {heal} HP ترمیم کرد!**")

    # 💫 خودترمیم‌گر (mob ability) — موب‌های وحشی/Apex با این ability هم ترمیم می‌شن
    if not is_boss and enemy["hp"] > 0:
        from mob_abilities import regen_tick
        heal = regen_tick(enemy)
        if heal:
            enemy["hp"] = min(enemy.get("max_hp", enemy["hp"]), enemy["hp"] + heal)
            result["logs"].append(f"💫 **{enemy.get('name','دشمن')} {heal} HP خودش رو ترمیم کرد!**")

    # ─── نمسیس: توانایی ویژه (جدا از ضربِ سادهٔ آمار) ────────────
    if enemy.get("is_nemesis") and enemy["hp"] > 0 and player.get("hp", 100) > 0:
        from nemesis_system import maybe_trigger_ability
        ability = maybe_trigger_ability(enemy)
        if ability:
            player["hp"] = max(0, player.get("hp", 100) - ability["dmg"])
            if ability.get("heal", 0) > 0:
                enemy["hp"] = min(enemy.get("max_hp", enemy["hp"]), enemy["hp"] + ability["heal"])
            if ability.get("combo_break"):
                player["combo"] = 0
            result["logs"].append(ability["msg"])

    player["_active_encounter"] = session
    save_player(uid, player)

    # ── دشمن شکست خورد ──
    if enemy["hp"] <= 0:
        del encounter_sessions[uid]
        player.pop("_active_encounter", None)
        await _resolve_victory(cb, uid, player, enemy, is_boss, map_name, result["logs"])
        # 🔁 حلقه‌ی زمان — شانسِ کوچیکِ دراپ بعدِ پیروزیِ باس (loop_system.py)
        if is_boss:
            from loop_system import maybe_drop_loop_charge
            fresh_player = get_player(uid)
            drop_text = maybe_drop_loop_charge(fresh_player, is_boss)
            if drop_text:
                save_player(uid, fresh_player)
                try:
                    await cb.message.answer(drop_text)
                except Exception:
                    pass
        return

    # ── بازیکن باخت (HP خیلی کم شد) ──
    if player.get("hp", 100) <= 0:
        # 🔁 حلقه‌ی زمان (loop_system.py) — اگه شارژ داره، به‌جای باختِ قطعی
        # نبرد از اول (با HPِ دشمن/بازیکنِ بازنشانی‌شده) دوباره شروع می‌شه.
        from loop_system import has_loop_charge, consume_loop_charge, LOOP_FLAVOR
        if is_boss and has_loop_charge(player):
            consume_loop_charge(player)
            snap = session.get("enemy_snapshot")
            if snap:
                enemy.clear()
                enemy.update(dict(snap))
            player["max_hp"] = player.get("max_hp", 100)
            from loop_system import REVIVE_HP_PCT
            player["hp"] = max(1, int(player["max_hp"] * REVIVE_HP_PCT))
            session["turn"] = 0
            player["_active_encounter"] = session
            save_player(uid, player)
            text = f"{LOOP_FLAVOR}\n\n" + _render(player, enemy, is_boss)
            kb = _encounter_kb(uid, is_boss, session["token"], player)
            await cb.message.edit_text(text, reply_markup=kb)
            await cb.answer("🔁 حلقه زدی!")
            return

        from loot_engine import guard_streak_loss
        del encounter_sessions[uid]
        player["hp"] = 1
        player.pop("_active_encounter", None)
        saved = guard_streak_loss(player)
        from nemesis_system import handle_nemesis_on_loss
        nemesis_msg = handle_nemesis_on_loss(player, enemy)
        save_player(uid, player)
        text = f"💀 **شکست خوردی!**\n{enemy['name']} تقریباً بی‌هوشت کرد.\nبا HP=1 فرار کردی، دست‌خالی."
        text += "\n🍀 طلسم شانس فعال شد و استریک لوتت حفظ موند!" if saved else "\n💔 استریک لوتت صفر شد."
        if nemesis_msg:
            text += f"\n\n{nemesis_msg}"
        if is_boss:
            text += "\n\n_(اگه یه حلقه‌ی زمان داشتی، می‌تونستی این باخت رو ریست کنی.)_"
        await cb.message.edit_text(text, reply_markup=None)
        await cb.answer("💀 نزدیک بود!", show_alert=False)
        return

    # ── مبارزه ادامه داره ──
    text = _render(player, enemy, is_boss, result["logs"])
    kb = _encounter_kb(uid, is_boss, session["token"], player)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await cb.answer(f"{result['dmg']} آسیب زدی!" if not result["miss"] else "میس زدی!")

# ─── Victory: XP / Zen / Loot ────────────────────────────────
async def _resolve_victory(cb: CallbackQuery, uid: int, player: dict, enemy: dict, is_boss: bool, map_name: str, logs: list[str]):
    from loot_engine import process_kill_rewards

    # ─── تعلیقِ کوتاه قبل از فاش شدنِ غنیمت — حسِ باز شدنِ جعبه‌ی شانس ───
    try:
        await cb.message.edit_text(
            f"🎉 **{enemy['name']} شکست خورد!**\n\n🎲 در حال شمارشِ غنائم...",
            reply_markup=None,
        )
        await asyncio.sleep(1.1)
    except Exception:
        pass

    xp_gain  = enemy.get("xp", 30)
    base_zen = enemy.get("zen", 25)
    player["kills"] = player.get("kills", 0) + 1

    # ─── باگ‌فیکس: Bond XP کاتانا فقط تو مسیرِ /attack جمع می‌شد،
    # نه تو /loot (که اکثر بازیکن‌ها ازش استفاده می‌کنن) — یعنی پیوندِ
    # روحیِ کاتانا برای اکثر بازیکن‌ها اصلاً رشد نمی‌کرد.
    player["katana_kills"] = player.get("katana_kills", 0) + 1
    from katana_core import add_bond_xp
    bond_result = add_bond_xp(player, amount=1)
    from character_lore import check_epilogue
    epilogue_text = check_epilogue(player, bond_result)

    # برای ماموریت‌های فرعی («۵ تا فلان دشمن رو بکش») — quest_engine.py
    kl = player.setdefault("kill_log", {})
    kl[enemy.get("name", "?")] = kl.get(enemy.get("name", "?"), 0) + 1

    # ─── حالت سخت: ثبت کشتنِ باس منطقه برای باز شدن تیر بعدی نقشه‌ها ─
    boss_title_gained = None
    if is_boss:
        killed_list = player.setdefault("area_bosses_killed", [])
        if map_name not in killed_list:
            killed_list.append(map_name)

        # 🆕 ثبتِ کشتنِ باسِ خاص (نه فقط مپ) — اولین بار که یه harbinger
        # (نادرترین تایرِ باس، فقط از دانجن قابل‌دسترسه) کشته می‌شه، یه
        # عنوانِ دائمی باز می‌شه.
        boss_key = enemy.get("boss_key")
        if boss_key:
            bk_list = player.setdefault("boss_kill_log", [])
            if boss_key not in bk_list:
                bk_list.append(boss_key)
                if enemy.get("boss_tier") == "harbinger":
                    bt_list = player.setdefault("boss_titles", [])
                    title_str = f"👑 فاتحِ {enemy['name'].split(' ', 1)[-1]}"
                    if title_str not in bt_list:
                        bt_list.append(title_str)
                        boss_title_gained = title_str

    try:
        from map_activity import log_event
        actor_name = getattr(cb.from_user, "first_name", None)
        if is_boss:
            ev_kind = "boss_kill"
        elif enemy.get("is_elite"):
            ev_kind = "elite_kill"
        elif enemy.get("tier") == "legendary":
            ev_kind = "legendary_kill"
        else:
            ev_kind = "kill"
        log_event(map_name, actor_name, ev_kind, map_name, actor_id=uid)
    except Exception:
        pass

    try:
        from elite_mobs import apply_elite_kill_bonus
        apply_elite_kill_bonus(player, enemy)
    except Exception:
        pass

    base_item = get_drop(enemy, player)
    if is_boss and not base_item:
        # باس همیشه یه چیز خفن جا می‌ذاره — تایرِ بالاتر یعنی غنیمتِ بهتر
        _trophy_mult = {"guardian": 1.0, "warlord": 1.4, "harbinger": 2.0}.get(enemy.get("boss_tier"), 1.0)
        base_item = {"name": "Boss Trophy", "emoji": "🏆", "sell": int(5000 * _trophy_mult), "rarity": "legendary"}

    item, extras, zen_mult, streak_logs, streak, streak_title = process_kill_rewards(
        player, enemy, map_name, is_boss, base_item
    )

    from economy_engine import apply_gold_find
    from loot_engine import get_set_bonus_stats
    from guild_system import get_perk, get_war_xp_buff
    import mentor_system as ms
    from world_pulse import pulse_value
    from seasonal_arc import zen_mult as season_zen_mult, xp_mult as season_xp_mult
    from item_system import equipment_stats as _eq_stats
    from pet_system import pet_combat_bonus as _pet_stats
    import anti_farm as af
    from combat_handlers import fatigue_reward_mult
    setb = get_set_bonus_stats(player)
    eqb = _eq_stats(player)  # 🔗 Item System v2 — افیکسِ xp_pct/gold_find_pct
    petb = _pet_stats(player)  # 🐾 بونوسِ همراه
    rb = rebirth_bonuses(player)
    # 🎯 کوئست‌لاینِ حمله — zen_pct/xp_pct از توانایی‌های بازشده هم قاطیِ setb می‌شه
    try:
        from hunt_questline import get_hunt_bonuses
        for _k, _v in get_hunt_bonuses(player).items():
            setb[_k] = setb.get(_k, 0) + _v
    except ImportError:
        pass
    from game_data import XP_GAIN_MULTIPLIER, ZEN_GAIN_MULTIPLIER
    zen_gain = apply_gold_find(player, int(base_zen * zen_mult * ZEN_GAIN_MULTIPLIER * pulse_value("zen_mult") * season_zen_mult() * (1 + setb.get("zen_pct", 0))))
    stacked_bonus = af.cap_bonus(get_perk(player, "zen_gain_pct"))
    zen_gain = int(zen_gain * (1 + stacked_bonus))
    xp_gain  = int(xp_gain * XP_GAIN_MULTIPLIER * pulse_value("xp_mult") * season_xp_mult() * (1 + setb.get("xp_pct", 0) + rb["xp_pct"] + eqb.get("xp_pct", 0) + petb.get("xp_pct", 0)))
    stacked_xp_bonus = af.cap_bonus(get_perk(player, "xp_gain_pct") + get_war_xp_buff(player)
                                     + ms.mentee_xp_bonus(player) + ms.mentor_xp_bonus(player))
    xp_gain  = int(xp_gain * (1 + stacked_xp_bonus))

    # 🆕 ضد-فارم: پنالتیِ خستگی + سقفِ نرمِ روزانه
    zen_gain = int(zen_gain * fatigue_reward_mult(player) * af.daily_mult(player, "zen"))
    xp_gain  = int(xp_gain  * fatigue_reward_mult(player) * af.daily_mult(player, "xp"))

    # 🆕 بیماریِ بیمارستان متروکه (abandoned_locations.py): تا وقتی فعاله، غنیمت کمتره
    from abandoned_locations import sickness_mult
    sick_mult = sickness_mult(player)
    zen_gain = int(zen_gain * sick_mult)
    xp_gain  = int(xp_gain * sick_mult)

    # 🐾 توانایی فعالِ همراه (طلا/XP) — یه بونوسِ یک‌باره‌ی موقعِ جایزه.
    pet_reward_line = None
    try:
        from pet_system import pet_reward_proc
        rproc = pet_reward_proc(player)
        if rproc:
            tag = f"{rproc['emoji']} {rproc['name']}"
            if rproc["stat"] == "gold_find_pct":
                bonus = max(1, int(zen_gain * 0.4 * rproc["power"]))
                zen_gain += bonus
                pet_reward_line = f"🐾 {tag} یه گنجِ اضافه پیدا کرد! +{bonus:,} Zen"
            else:
                bonus = max(1, int(xp_gain * 0.4 * rproc["power"]))
                xp_gain += bonus
                pet_reward_line = f"🐾 {tag} یه بینشِ اضافه بهت داد! +{bonus} XP"
    except ImportError:
        pass

    af.register_daily_gain(player, "zen", zen_gain)
    af.register_daily_gain(player, "xp", xp_gain)
    af.log_if_suspicious(uid, player.get("name", "—"), zen_gain, xp_gain, "mob_combat")
    af.register_action_time(player, uid, player.get("name", "—"), "mob_combat")

    import battle_pass as bp
    bp.add_points(player, xp_gain)
    if player.get("mentee_of"):
        bp.add_mentee_pair_points(player, xp_gain)
    for _mentee_id in player.get("mentor_of", []):
        bp.add_pair_points(player, _mentee_id, xp_gain)

    player["xp"]  = player.get("xp", 0) + xp_gain
    player["zen"] = player.get("zen", 0) + zen_gain

    from pet_system import add_pet_xp
    pet_levelup = add_pet_xp(player, xp_gain)

    leveled = False
    old_level = player["level"]
    from game_data import is_level_wall
    while player["xp"] >= xp_for_level(player["level"]) and player["level"] < effective_max_level(player):
        # حالت سخت: دیوار سختی — همون قانونِ combat_handlers.py، اینجا هم رعایت می‌شه
        if is_level_wall(player["level"]) and player["level"] not in player.get("walls_cleared", []):
            break
        player["level"]  += 1
        player["max_hp"] += 5   # حالت سخت: یکسان با combat_handlers.py (قبلاً اینجا +۱۰ بود — باگ)
        from skill_tree import effective_max_hp
        player["hp"]      = effective_max_hp(player)  # باگ‌فیکس: باف max_hp_pct هم لحاظ بشه
        leveled = True
    if leveled:
        from skill_tree import grant_levelup_points
        grant_levelup_points(player, old_level, player["level"])

    # 🔗 لحظه‌ی باند (هر چند سطح، نه فقط سطحِ فارغ‌التحصیلی) — فقط وقتی هنوز شاگرده
    if leveled and player.get("mentee_of"):
        _bond_mentor = get_player(player["mentee_of"])
        bond_lines = ms.check_bond_milestone(_bond_mentor, player) if _bond_mentor else []
        if bond_lines:
            save_player(player["mentee_of"], _bond_mentor)
            try:
                await cb.bot.send_message(player["mentee_of"], "\n".join(bond_lines))
            except Exception:
                pass

    # 🎓 چک فارغ‌التحصیلی از سیستم استادی
    if ms.is_ready_to_graduate(player):
        mentor_id = player["mentee_of"]
        mentor = get_player(mentor_id)
        if mentor:
            ms.end_mentorship(mentor, player)
            mentor["zen"] = mentor.get("zen", 0) + ms.GRADUATE_MENTOR_ZEN
            mentor["xp"]  = mentor.get("xp", 0) + ms.GRADUATE_MENTOR_XP
            mentor["graduated_mentee_count"] = mentor.get("graduated_mentee_count", 0) + 1
            save_player(mentor_id, mentor)
            player["zen"] = player.get("zen", 0) + ms.GRADUATE_MENTEE_ZEN
            log_sync(
                f"🎓 **MENTORSHIP GRADUATED**\n👨‍🏫 استاد: {mentor.get('name','—')} (`{mentor_id}`)\n"
                f"🎓 شاگرد: {player.get('name','—')} (`{uid}`) رسید به Lv.{player['level']}",
                "MENTOR"
            )
            try:
                await cb.bot.send_message(
                    mentor_id,
                    f"🎉 شاگردت **{player.get('name','—')}** فارغ‌التحصیل شد!\n"
                    f"💰 +{ms.GRADUATE_MENTOR_ZEN:,} Zen | ✨ +{ms.GRADUATE_MENTOR_XP} XP پاداش گرفتی."
                )
            except Exception:
                pass

    from achievements import check_achievements
    new_titles = check_achievements(player)
    if boss_title_gained:
        new_titles = [*new_titles, boss_title_gained]

    save_player(uid, player)

    # ─── باگ‌فیکس واقعی: update_quest قبلاً *قبل از* این save_player صدا زده
    # می‌شد. چون update_quest خودش جدا player رو از دیتابیس می‌خونه/می‌نویسه،
    # و این save_player بعدی با نسخه‌ی قدیمیِ (قبل از آپدیت ماموریت) player
    # کل رکورد رو overwrite می‌کرد، هر پیشرفتی که update_quest نوشته بود
    # بلافاصله پاک می‌شد. حالا update_quest بعد از save_player صدا زده می‌شه
    # (دقیقاً مثل ترتیبِ درستش تو combat_handlers.py).
    from combat_handlers import update_quest
    update_quest(uid, "kill", 1)
    update_quest(uid, "earn", zen_gain)
    if enemy.get("tier") == "legendary" or is_boss:
        update_quest(uid, "legend", 1)
    if any("CRITICAL" in l or "کریتیکال" in l for l in logs):
        update_quest(uid, "crit", 1)
    if player.get("combo", 0) >= 10:
        update_quest(uid, "combo", 1)

    lines = [
        f"🎉 **{enemy['name']} شکست خورد!**\n",
        *[f"{l}\n" for l in logs],
    ]
    lines += [f"{l}\n" for l in streak_logs]

    if pet_reward_line:
        lines.append(f"\n{pet_reward_line}")

    if pet_levelup:
        if pet_levelup.get("evolved"):
            lines.append(f"\n🐾✨ **{pet_levelup['emoji']} {pet_levelup['name']} تکامل پیدا کرد!** حالا {pet_levelup['evolution_label']}ه (سطح {pet_levelup['level']})")
        else:
            lines.append(f"\n🐾 {pet_levelup['emoji']} **{pet_levelup['name']}** به سطح {pet_levelup['level']} رسید!")

    from nemesis_system import clear_nemesis_on_defeat
    nemesis_revenge_msg = clear_nemesis_on_defeat(player, enemy)
    if nemesis_revenge_msg:
        bonus_zen = int(enemy.get("zen", 25) * 0.5)
        player["zen"] = player.get("zen", 0) + bonus_zen
        lines.append(f"\n{nemesis_revenge_msg}\n💰 پاداشِ انتقام: +{bonus_zen} BZ اضافه\n")
        # 🆕 باگ‌فیکس: قبلاً save_player بالاتر (قبل از این بلوک) صدا زده می‌شد
        # و دیگه بعدش دوباره ذخیره نمی‌شد — یعنی پاداشِ Zen، عنوانِ دائمیِ
        # نمسیس و ثبتِ تاریخچه‌ش هیچ‌وقت واقعاً تو دیتابیس ذخیره نمی‌شدن.
        save_player(uid, player)

        try:
            from seasonal_arc import register_nemesis_kill
            if register_nemesis_kill():
                from database import all_players
                announce = (
                    "📜 **هدفِ سراسریِ فصل رسید!**\n\n"
                    "کل سرور، دست‌به‌دست، به هدفِ شکارِ نمسیسِ این فصل رسید. "
                    "تا آخرِ فصل، یه بافِ همگانی فعاله: +XP و +Zen برای همه!\n"
                    "با `/season` جزئیات رو ببین."
                )
                for pid in all_players():
                    try:
                        await cb.bot.send_message(int(pid), announce)
                    except Exception:
                        pass
                    await asyncio.sleep(0.03)
        except Exception:
            pass

    if epilogue_text:
        lines.append(epilogue_text)

    zen_bonus_txt = f" (شامل بونوس استریک +{int((zen_mult-1)*100)}%)" if zen_mult > 1 else ""
    lines.append(f"\n✨ +{xp_gain} XP | 💰 +{zen_gain} BZ{zen_bonus_txt}\n")
    lines.append(f"🔥 استریک لوت: {streak}x" + (f" {streak_title}" if streak_title else "") + "\n")

    gamble_idx = None
    highlight_item = None
    if item:
        tag = " 🍀پیتی" if item.get("pity") else (" ⬆️ارتقایافته" if item.get("upgraded") else "")
        lines.append(f"🎁 لوت: {item['emoji']} **{item['name']}** ({item.get('rarity','common')}){tag} — {bz_to_display(item.get('sell',0))}\n")
        if item.get("sell", 0) > 0:
            gamble_idx = len(player.get("inventory", [])) - 1
        if item.get("rarity") in ("mythic", "legendary"):
            highlight_item = item
    for ex in extras:
        if ex.get("type") == "lockbox":
            lines.append(f"📦 صندوق: {ex['emoji']} **{ex['name']}** — تو 🖤بازار سیاه ›› 🗝️ صندوق‌ها بازش کن\n")
        elif ex.get("type") == "key":
            lines.append(f"🔑 کلید: {ex['emoji']} **{ex['name']}**\n")
        elif "set_id" in ex:
            lines.append(f"🧩 قطعه‌ی ست: {ex['emoji']} **{ex['name']}** ({ex['set_display']})\n")
    if leveled:
        lines.append(f"\n🆙 **LEVEL UP! (レベルアップ！) → {player['level']}**\n")
        _rk = rank_up_announcement(old_level, player["level"], player.get("rebirth_count", 0))
        if _rk:
            lines.append(f"\n{_rk}\n")
    for t in new_titles:
        lines.append(f"\n🏅 **عنوان جدید باز شد: {t}**\n")

    kb_rows = []
    dungeon_found = False
    if not is_boss:
        # ── چک کردن پیدا شدن دروازه‌ی دانجن ──
        dp = dungeon_progress.get(uid)
        if not dp or dp.get("map") != map_name:
            dp = {"map": map_name, "count": 0, "threshold": random.randint(DUNGEON_PROGRESS_MIN, DUNGEON_PROGRESS_MAX)}
        dp["count"] += 1
        dungeon_found = dp["count"] >= dp["threshold"] or random.random() < DUNGEON_FIND_CHANCE

        if dungeon_found:
            dungeon_progress.pop(uid, None)
            lines.append(
                "\n🌀 **یک دروازه‌ی دانجن مرموز پیدا کردی!**\n"
                "از پشتش صدای غرش میاد... می‌ری تو یا فرار می‌کنی؟\n"
            )
            kb_rows.append([
                InlineKeyboardButton(text="🚪 برو تو", callback_data=f"dg_yes:{map_name}:{uid}", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton(text="🏃 فرار کن", callback_data=f"dg_no:{map_name}:{uid}", style=ButtonStyle.PRIMARY),
            ])
        else:
            dungeon_progress[uid] = dp
            # بعد از رد کردن موب معمولی، وارد رویداد ریسک/لوت مرحله‌ی بعد میشیم
            kb_rows.append([InlineKeyboardButton(text="🔍 جستجوی منطقه (ادامه لوت)", callback_data=f"mobcontinue:{map_name}:{uid}", style=ButtonStyle.PRIMARY)])

    if gamble_idx is not None:
        kb_rows.append([InlineKeyboardButton(text="🎲 دابل یا هیچ (این آیتم)", callback_data=f"loot:gamble:{gamble_idx}", style=ButtonStyle.PRIMARY)])

    kb_rows.append([InlineKeyboardButton(text="🏠 پنل اصلی", callback_data="menu:home", style=ButtonStyle.PRIMARY)])

    await cb.message.edit_text("".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await cb.answer("🌀 دروازه‌ی دانجن پیدا شد!" if dungeon_found else "🎉 برد!")

    if highlight_item:
        try:
            await cb.message.answer(
                f"🌟🌟🌟 **دراپ نایاب!!** 🌟🌟🌟\n\n"
                f"{highlight_item['emoji']} **{highlight_item['name']}**\n"
                f"🏷 رریتی: **{highlight_item.get('rarity','—').upper()}**\n"
                f"💰 ارزش: {bz_to_display(highlight_item.get('sell',0))}\n\n"
                f"👤 **{player.get('name','—')}** همین الان این رو تو **{map_name}** پیدا کرد! 🎉"
            )
        except Exception:
            pass

async def cb_dungeon_yes(cb: CallbackQuery):
    """رفتن داخل دانجن — چند مرحله‌ی ریسک/لوت تا رسیدن به باس"""
    parts = cb.data.split(":")
    if len(parts) < 3:
        await cb.answer("❌ خطا!", show_alert=True); return
    map_name, cb_uid = parts[1], int(parts[2])
    uid = cb.from_user.id
    if cb_uid != uid:
        await cb.answer("❌ این برای تو نیست!", show_alert=True); return

    total = random.randint(DUNGEON_STAGES_MIN, DUNGEON_STAGES_MAX)
    dungeon_state[uid] = {"map": map_name, "stage": 0, "total": total}
    await cb.answer(f"🌀 وارد دانجن شدی! {total} مرحله تا باس نهایی...")

    from raid_handlers import start_raid_event
    await start_raid_event(cb.message, uid, map_name)

async def cb_dungeon_no(cb: CallbackQuery):
    """فرار از دانجن — ادامه‌ی لوت عادی"""
    parts = cb.data.split(":")
    if len(parts) < 3:
        await cb.answer("❌ خطا!", show_alert=True); return
    map_name, cb_uid = parts[1], int(parts[2])
    uid = cb.from_user.id
    if cb_uid != uid:
        await cb.answer("❌ این برای تو نیست!", show_alert=True); return

    dungeon_state.pop(uid, None)
    await cb.answer("🏃 از دانجن فرار کردی.")
    from raid_handlers import start_raid_event
    await start_raid_event(cb.message, uid, map_name)

async def cb_mob_continue(cb: CallbackQuery):
    parts = cb.data.split(":")
    if len(parts) < 3:
        await cb.answer("❌", show_alert=True); return
    map_name = parts[1]
    cb_uid   = int(parts[2])
    if cb_uid != cb.from_user.id:
        await cb.answer("❌ این برای تو نیست!", show_alert=True); return

    from raid_handlers import start_raid_event
    await start_raid_event(cb.message, cb.from_user.id, map_name)
    await cb.answer()

# ─── Register ────────────────────────────────────────────────
def register_mob_combat_handlers(dp: Dispatcher):
    dp.callback_query.register(handle_mob_attack, F.data.startswith("mob:"))
    dp.callback_query.register(cb_mob_continue,   F.data.startswith("mobcontinue:"))
    dp.callback_query.register(cb_dungeon_yes,    F.data.startswith("dg_yes:"))
    dp.callback_query.register(cb_dungeon_no,     F.data.startswith("dg_no:"))
