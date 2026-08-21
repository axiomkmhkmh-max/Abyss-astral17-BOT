# ============================================================
#  ASTRAL ABYSS — Combat & Daily Event Handlers 
# ============================================================
import asyncio, time, random, datetime
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from economy import bz_to_display, KATANA_LEVELS
from combat import (
    ATTACK_TYPES, ENEMIES, MAP_ENEMIES, get_map_enemies, calc_combat,
    get_drop, hp_bar, STATUSES, ELEMENT_STATUS,
    get_today_event, get_today_quests, get_event_multiplier,
    maybe_ambush, maybe_deadly_blow, get_combat_stats_summary,
)
from characters import ALL_CHARACTERS
from game_data import xp_for_level, is_level_wall, next_level_wall, wall_boss_stats, effective_max_level, rebirth_ready, rebirth_bonuses, do_rebirth
from isekai_theme import rank_up_announcement
from skill_tree import effective_max_hp
from logger import log_sync

# 🆕 لایه‌ی عمیقِ نبرد: combat_v3 (شخصیت/بعد/مهارتِ کاتانا) که قبلاً نوشته
# شده بود ولی هیچ‌جا صدا زده نمی‌شد — از این‌جا رسماً وصل می‌شه.
from combat_v3 import calc_combat_v3, on_kill as katana_on_kill, on_death as katana_on_death, start_new_battle

# 🆕 استنس نبرد (تهاجمی/متعادل/دفاعی) — مکانیک کاملاً جدید
import combat_stance as stance

# 🆕 زنجیره‌ی حمله / فینیشر — مکانیک کاملاً جدید
import combat_chain as chain

# 🆕 نقطه‌ضعف/شکست (weak point / break) — مکانیک کاملاً جدید
import combat_break as brk

# 🆕 پری/کانترِ تایمینگ‌محور — مکانیک کاملاً جدید
import combat_parry as parry

# همون لیست نقشه‌هایی که تو bot.py برای اسپان اولیه استفاده می‌شه —
# اینجا هم لازممون میشه برای اسپان رندوم بعد از مرگ.
SPAWN_MAPS = [
    "Verdant Vale", "Frostheim", "Sands of Eternity",
    "Azure Tides Empire", "Ruins of Orion-7", "Clockwork Depths",
    "Holy Luminarchy", "The Sunken City", "Stormward Archipelago",
]

# ─── Cooldown Tracking ───────────────────────────────────────
last_attacks: dict[int, dict[str, float]] = {}

def check_cooldown(uid: int, atk_type: str) -> int:
    """Returns remaining cooldown seconds, 0 if ready"""
    now = time.time()
    last = last_attacks.get(uid, {}).get(atk_type, 0)
    cd = ATTACK_TYPES[atk_type]["cooldown"]
    remaining = int(cd - (now - last))
    return max(0, remaining)

def set_cooldown(uid: int, atk_type: str):
    if uid not in last_attacks:
        last_attacks[uid] = {}
    last_attacks[uid][atk_type] = time.time()

# Active combat sessions: uid → {atk_type, enemies}  (فقط برای مرحله‌ی انتخاب دشمن — کوتاه‌مدته، مهم نیست RAM باشه)
combat_sessions: dict[int, dict] = {}

# ─── Active Fight State ───────────────────────────────────────
# قبلاً نبرد جاری (active_fights) فقط توی یه دیکشنری تو RAM سرور نگه داشته می‌شد.
# مشکل: هر بار که ربات ری‌استارت می‌شد (دیپلوی جدید، خواب رفتن سرور روی Railway، کرش و ری‌استارت خودکار و ...)
# این دیکشنری کامل خالی می‌شد و HP دشمن انگار "ریست به صد" به نظر می‌رسید.
# الان به‌جاش نبرد جاری رو مستقیم روی خود پروفایل بازیکن (که با save_player دائم ذخیره میشه) نگه می‌داریم
# پس با ری‌استارت سرور هم از بین نمی‌ره.

def get_fight(player: dict) -> dict | None:
    return player.get("current_fight")

def set_fight(player: dict, enemy: dict | None):
    player["current_fight"] = enemy

# ─── باگ‌فیکس: پیشرفتِ ماموریت‌های روزانه قبلاً فقط تو یه دیکشنریِ
# داخلِ حافظه (quest_progress) نگه‌داری می‌شد — یعنی با هر ری‌استارتِ
# ربات (دیپلوی/کرش/آپدیت) کاملاً پاک می‌شد. حالا رو خودِ پروفایلِ
# بازیکن تو دیتابیس ذخیره می‌شه و با تاریخِ امروز مقایسه می‌شه، پس
# هم survive می‌کنه بین ری‌استارت‌ها و هم خودش هر روز صفر می‌شه.
async def get_qp(uid: int) -> dict:
    player = await aget_player(uid)
    if not player:
        return {}
    today = datetime.date.today().isoformat()
    dq = player.get("daily_quest_progress")
    if not dq or dq.get("date") != today:
        dq = {"date": today, "progress": {}}
        player["daily_quest_progress"] = dq
        await asave_player(uid, player)
    return dq["progress"]

async def update_quest(uid: int, q_type: str, amount: int = 1):
    quests = get_today_quests()
    player = await aget_player(uid)
    if not player:
        return
    qp = await get_qp(uid)  # مطمئن میشه امروزه و از دیتابیس تازه‌ست
    changed = False
    for q in quests:
        if q["type"] == q_type:
            qp[q["id"]] = qp.get(q["id"], 0) + amount
            changed = True
    if changed:
        player["daily_quest_progress"]["progress"] = qp
        await asave_player(uid, player)

# ═══════════════════════════════════════════════════════════════
#  حالت سخت (Hardcore Mode) — مرگ/مجازات، نفرین، جراحت دائمی، خستگی
# ═══════════════════════════════════════════════════════════════

DEATH_CURSE_DAYS      = 3
DEATH_CURSE_DMG_PEN   = 0.20   # -20% دمیج
DEATH_CURSE_DEF_PEN   = 0.20   # -20% دفاع (کاهش اضافی به دمیج ورودی)
DEATH_CURSE_HEAL_PEN  = 0.50   # +50% هزینه درمان
HEAL_LOCKOUT_SECONDS  = 3600   # ۱ ساعت قفل درمان بعد از مرگ

INJURY_THRESHOLDS = {
    5:  ("old_wound",  "🩸 زخم کهنه: همیشه -۵ Max HP"),
    10: ("fracture",   "🦴 شکستگی: همیشه -۵٪ دمیج"),
    20: ("curse_perm", "☠️ نفرین دائمی: همیشه -۱۰٪ تمام آمار"),
    50: ("annihilated","💀 نابودی: کاراکترت برای همیشه می‌میره!"),
}
INJURY_DMG_PENALTY = {"fracture": 0.05, "curse_perm": 0.10}

def curse_active(player: dict) -> bool:
    return time.time() < player.get("death_curse_until", 0)

def heal_locked(player: dict) -> bool:
    return time.time() < player.get("heal_lockout_until", 0)

def total_injury_dmg_penalty(player: dict) -> float:
    injuries = set(player.get("injuries", []))
    return sum(INJURY_DMG_PENALTY.get(i, 0) for i in injuries)

def outgoing_dmg_penalty_mult(player: dict) -> float:
    """ضریب کاهش دمیج خروجی بازیکن، ناشی از نفرین مرگ فعال + جراحت‌های دائمی."""
    mult = 1.0
    if curse_active(player):
        mult -= DEATH_CURSE_DMG_PEN
    mult -= total_injury_dmg_penalty(player)
    return max(0.2, mult)

def incoming_dmg_penalty_mult(player: dict) -> float:
    """ضریب افزایش دمیج ورودی به بازیکن (چون دفاعش پایین اومده)."""
    mult = 1.0
    if curse_active(player):
        mult += DEATH_CURSE_DEF_PEN
    return mult

def apply_hardcore_death_penalty(player: dict, penalty_mult: float = 1.0) -> list[str]:
    """طبق بند ۱ درخواست: مرگ باید خیلی گرون تموم بشه. این تابع همه‌ی
    مجازات‌های مرگ (بجز بخش کاتانا که تو katana_core.py هندل می‌شه) رو
    اعمال می‌کنه و متن‌های نمایشی رو برمی‌گردونه.
    penalty_mult=2 برای مرگ حین خستگی شدید یا چالش (طبق بند ۵/۹)."""
    lines = []

    # ۱) ۲۰٪ کل Zen
    zen = player.get("zen", 0)
    lost_zen = int(zen * min(1.0, 0.20 * penalty_mult))
    player["zen"] = zen - lost_zen
    if lost_zen > 0:
        lines.append(f"💸 -{bz_to_display(lost_zen)} (۲۰٪×{penalty_mult:g} کل Zen)")

    # ۲) ۵٪ کل XP شخصیت (می‌تونه سطح رو پایین بیاره)
    old_level = player.get("level", 1)
    xp = player.get("xp", 0)
    lost_xp = int(xp * min(1.0, 0.05 * penalty_mult))
    player["xp"] = max(0, xp - lost_xp)
    while player["level"] > 1 and player["xp"] < xp_for_level(player["level"] - 1):
        player["level"]  -= 1
        player["max_hp"]  = max(50, player["max_hp"] - 5)
    if lost_xp > 0:
        lines.append(f"📉 -{lost_xp} XP (۵٪ کل XP)")
    if player["level"] < old_level:
        lines.append(f"⬇️ سطحت افتاد: {old_level} → {player['level']}!")

    # ۳) یه آیتم تصادفی از کوله‌پشتی
    inv = player.get("inventory", [])
    if inv:
        idx = random.randrange(len(inv))
        lost_item = inv.pop(idx)
        lines.append(f"🎒 آیتم از دست رفت: {lost_item.get('emoji','📦')} {lost_item.get('name','آیتم ناشناس')}")

    # ۴) نفرین مرگ ۳ روزه
    player["death_curse_until"] = time.time() + DEATH_CURSE_DAYS * 86400
    lines.append(f"👻 **نفرین مرگ** {DEATH_CURSE_DAYS} روز: -۲۰٪ دمیج، -۲۰٪ دفاع، +۵۰٪ هزینه درمان")

    # ۵) ۱ ساعت قفل درمان
    player["heal_lockout_until"] = time.time() + HEAL_LOCKOUT_SECONDS
    lines.append("⏳ تا ۱ ساعت نمی‌تونی درمان بشی")

    # ۶) شمارش مرگ + جراحت دائمی
    player["death_count"] = player.get("death_count", 0) + 1
    dc = player["death_count"]
    for threshold, (flag, desc) in INJURY_THRESHOLDS.items():
        if dc >= threshold and flag not in player.get("injuries", []):
            player.setdefault("injuries", []).append(flag)
            if flag == "old_wound":
                player["max_hp"] = max(50, player["max_hp"] - 5)
            if flag == "annihilated":
                # نابودی کامل — کاراکتر از صفر شروع می‌شه (نگه‌داشتن کاتانا/id طبق قانون بازی)
                player["level"]  = 1
                player["xp"]     = 0
                player["max_hp"] = 100
                player["hp"]     = 100
                player["zen"]    = 0
                player["inventory"] = []
                player["injuries"]  = []
                player["death_count"] = 0
            lines.append(f"⚠️ **جراحت جدید!** {desc}")

    log_sync(
        f"💀 **DEATH PENALTY**\n"
        f"👤 {player.get('name','—')} (`{player.get('id','—')}`)\n"
        f"📊 مرگ شماره: {dc}\n"
        f"💸 Zen از دست رفته: {lost_zen:,}\n"
        f"📉 XP از دست رفته: {lost_xp:,}\n"
        f"👻 نفرین فعال: {'بله' if curse_active(player) else 'خیر'}",
        "DEATH"
    )

    return lines

# ─── حالت سخت وحشتناک: خستگی و استراحت (زودتر شروع می‌شه) ───────
FATIGUE_MILD_AT    = 7    # قبلاً ۱۰
FATIGUE_SEVERE_AT  = 14   # قبلاً ۲۰
FATIGUE_LOCKOUT_AT = 25   # 🆕 ضد-فارم: بعد این تعداد، تا استراحت نکنی اصلاً نمی‌تونی بجنگی
FATIGUE_MILD_PEN   = 0.10
FATIGUE_SEVERE_PEN = 0.25
FATIGUE_REWARD_PEN_MILD   = 0.15   # 🆕 ضد-فارم: پاداشِ Zen/XP هم مثلِ دمیج افت می‌کنه
FATIGUE_REWARD_PEN_SEVERE = 0.40
FATIGUE_FAINT_CHANCE = 0.08  # قبلاً ۵٪
REST_SECONDS = 1800  # ۳۰ دقیقه

def is_resting(player: dict) -> bool:
    """اگه دوره‌ی استراحتِ ست‌شده (با /rest یا آیتم) کامل تموم شده باشه، این
    خودش به‌عنوانِ عوارضِ جانبی خستگی رو صفر می‌کنه — چون قبلاً
    battles_since_rest فقط وقتی صفر می‌شد که دقیقاً وسطِ بازه‌ی استراحت یه
    نبردِ جدید شروع می‌شد؛ اگه کسی صبر می‌کرد و ۳۰ دقیقه تموم می‌شد بدونِ
    اینکه تو همون بازه حمله کنه، خستگی هیچ‌وقت واقعاً صفر نمی‌شد و پیامِ
    قفل برای همیشه تکرار می‌شد."""
    ru = player.get("resting_until", 0)
    if ru and time.time() >= ru:
        player["battles_since_rest"] = 0
        player["resting_until"] = 0
        return False
    return time.time() < ru

def fatigue_level(player: dict) -> int:
    """۰=خسته نیست، ۱=خستگی، ۲=خستگی شدید."""
    if is_resting(player):
        return 0
    n = player.get("battles_since_rest", 0)
    if n >= FATIGUE_SEVERE_AT:
        return 2
    if n >= FATIGUE_MILD_AT:
        return 1
    return 0

def is_fatigue_locked(player: dict) -> bool:
    """🆕 ضد-فارم: بعد از یه حدِ خیلی بالا، اصلاً اجازه‌ی نبرد نمی‌ده تا استراحت کنی."""
    if is_resting(player):
        return False
    return player.get("battles_since_rest", 0) >= FATIGUE_LOCKOUT_AT

def fatigue_stat_mult(player: dict) -> float:
    lvl = fatigue_level(player)
    if lvl == 2:
        return 1 - FATIGUE_SEVERE_PEN
    if lvl == 1:
        return 1 - FATIGUE_MILD_PEN
    return 1.0

def fatigue_reward_mult(player: dict) -> float:
    """🆕 ضد-فارم: هرچی بدونِ استراحت بیشتر بجنگی، Zen/XP کمتری می‌گیری."""
    lvl = fatigue_level(player)
    if lvl == 2:
        return 1 - FATIGUE_REWARD_PEN_SEVERE
    if lvl == 1:
        return 1 - FATIGUE_REWARD_PEN_MILD
    return 1.0

def register_battle_for_fatigue(player: dict):
    if is_resting(player):
        player["battles_since_rest"] = 0
        player["resting_until"] = 0
    player["battles_since_rest"] = player.get("battles_since_rest", 0) + 1

# ─── حالت سخت: محدودیت نبرد روزانه ──────────────────────────────
DAILY_BATTLE_MAX = 68

def daily_battles_remaining(player: dict) -> int:
    now = time.time()
    if now >= player.get("daily_battle_reset_at", 0):
        player["daily_battle_used"] = 0
        player["daily_battle_reset_at"] = now + 86400
    return DAILY_BATTLE_MAX - player.get("daily_battle_used", 0)

def use_daily_battle(player: dict) -> bool:
    if daily_battles_remaining(player) <= 0:
        return False
    player["daily_battle_used"] = player.get("daily_battle_used", 0) + 1
    return True

async def cmd_rebirth(msg: Message):
    """طبق درخواست: وقتی به سقفِ سطح رسیدی، می‌تونی ریبرث کنی — سطح می‌ره ۱،
    ولی باف دائمی می‌گیری و سقفِ سطح ۵۰ تا بالاتر می‌ره. بازی هیچ‌وقت واقعاً تموم نمی‌شه."""
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return

    cap = effective_max_level(player)
    rb_now = rebirth_bonuses(player)
    if not rebirth_ready(player):
        await msg.answer(
            f"🔒 هنوز به سقفِ سطحت (**{cap}**) نرسیدی. الان سطح **{player.get('level',1)}** هستی.\n\n"
            f"وقتی به {cap} برسی، می‌تونی Rebirth کنی: سطح می‌ره ۱، ولی باف دائمی می‌گیری و سقف "
            f"سطح می‌ره **{cap + 50}**."
        )
        return

    rb_next = player.get("rebirth_count", 0) + 1
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔄 آره، Rebirth کن!", callback_data="rebirth_go", style=ButtonStyle.PRIMARY),
        InlineKeyboardButton(text="❌ بی‌خیال", callback_data="rebirth_cancel", style=ButtonStyle.DANGER),
    ]])
    await msg.answer(
        f"🌀 **آماده‌ی Rebirth #{rb_next} هستی!**\n\n"
        f"با Rebirth کردن:\n"
        f"• سطحت می‌ره به **۱** (XP هم صفر می‌شه)\n"
        f"• سقفِ سطح از {cap} می‌ره به **{cap + 50}**\n"
        f"• باف دائمیِ جدید می‌گیری (تجمعی، برای همیشه):\n"
        f"   ⚔️ دمیج: +{int((rb_next*10))}٪ (الان: +{int(rb_now['dmg_pct']*100)}٪)\n"
        f"   🎁 شانسِ لوت: +{int(rb_next*8)}٪ (الان: +{int(rb_now['loot_pct']*100)}٪)\n"
        f"   ✨ XP: +{int(rb_next*6)}٪ (الان: +{int(rb_now['xp_pct']*100)}٪)\n"
        f"   ❤️ Max HP پایه: +{rb_next*15} (الان: +{rb_now['max_hp']})\n\n"
        f"💾 چیزهایی که از دست نمی‌ری: Zen، کوله‌پشتی، کاتانا، گیلدها، ست‌ها، پیشرفتِ داستان.\n\n"
        f"مطمئنی؟"
    )
    await msg.answer("👇", reply_markup=kb)

async def cb_rebirth_go(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player or not rebirth_ready(player):
        await cb.answer("❌ هنوز آماده نیستی!", show_alert=True)
        return
    do_rebirth(player)
    await asave_player(uid, player)
    
    log_sync(
        f"🌀 **REBIRTH**\n"
        f"👤 {player.get('name','—')} (`{uid}`)\n"
        f"📊 Rebirth #{player['rebirth_count']}\n"
        f"🎯 سقف جدید: {effective_max_level(player)}",
        "LEVELUP"
    )
    
    new_cap = effective_max_level(player)
    await cb.message.edit_text(
        f"🌀✨ **Rebirth #{player['rebirth_count']} انجام شد!**\n\n"
        f"سطحت رفت به ۱، ولی حالا قوی‌تر از همیشه‌ای. سقفِ جدید: **{new_cap}**.\n"
        f"وقت شروعِ دوباره‌ست — این‌بار سریع‌تر می‌ری بالا. 🔥"
    )
    await cb.answer("🌀 Rebirth شدی!")

async def cb_rebirth_cancel(cb: CallbackQuery):
    await cb.message.edit_text("❌ Rebirth لغو شد. هروقت خواستی، دوباره /rebirth بزن.")
    await cb.answer()

# ─── راهنمای حملات: فرقِ ۶ سبک حمله رو شفاف نشون می‌ده ────────
def _attack_help_text() -> str:
    lines = ["📖 **فرقِ ۶ سبکِ حمله چیه؟**\n"]
    order = ["quick", "heavy", "element", "combo", "ultimate", "parry"]
    for key in order:
        atk = ATTACK_TYPES[key]
        lines.append(
            f"{atk['name']}\n"
            f"  💢 دمیج: ×{atk['dmg_mult']}  ⏳ کول‌داون: {atk['cooldown']}s\n"
            f"  📌 {atk['desc']}\n"
        )
    lines.append(
        "───────────\n"
        "🎭 **استنس‌ها** (زیرِ دکمه‌های حمله، همیشه فعاله و مستقل از نوعِ حمله‌ست):\n"
    )
    for key in stance.STANCE_ORDER:
        s = stance.STANCES[key]
        lines.append(f"{s['name']} — {s['desc']}")
    lines.append(
        "\n💡 **جمع‌بندی:** نوعِ حمله تعیین می‌کنه *چطور* بزنی (سریع/قوی/کومبو/…)، "
        "استنس تعیین می‌کنه *چقدر* ریسک کنی (تهاجمی/متعادل/دفاعی). می‌تونی هر نوع حمله رو با هر استنسی ترکیب کنی."
    )
    return "\n".join(lines)

async def cb_atk_help(cb: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 برگشت به حمله", callback_data="atk:menu", style=ButtonStyle.PRIMARY)]
    ])
    await cb.message.answer(_attack_help_text(), reply_markup=kb)
    await cb.answer()

# ─── 📊 آمار مبارزه ────────────────────────────────────────────
def _combat_stats_text(player: dict) -> str:
    s = get_combat_stats_summary(player)
    lines = ["📊 **آمارِ مبارزه — خلاصه‌ی کاملِ بونوس‌ها**\n"]
    lines.append(f"⚔️ دمیج: **+{s['dmg_pct']*100:.1f}٪**")
    lines.append(f"🎯 شانسِ کریت: **{s['crit_pct']*100:.1f}٪**")
    lines.append(f"🩸 لایف‌استیل: **{s['lifesteal_pct']*100:.1f}٪**")
    lines.append(f"🛡️ دفاع (کاهشِ دمیجِ ورودی): **{s['defense_pct']*100:.1f}٪**")
    if s["is_adventurer"]:
        lines.append(f"🗡️ سطحِ کاتانا: **{s['katana_level']}** (دمیجِ فلت +{s['katana_bonus_dmg']}, ضریبِ روح ×{s['katana_soul_dmg_mult']:.2f})")
    if s["has_element_access"]:
        lines.append(
            f"\n🌪️ **ضریبِ ضعفِ عنصری:** ×{s['elem_mult_active']:.2f}  "
            f"(پایه ×1.5 + بونوسِ اضافه {s['elem_amp']*100:.0f}٪)\n"
            f"_فقط وقتی حمله‌ت دقیقاً به عنصرِ ضعفِ دشمن بخوره فعال می‌شه._"
        )
    else:
        lines.append("\n🌪️ ضریبِ ضعفِ عنصری: — (این کلاس دسترسیِ عنصری نداره)")
    if s["gold_find_pct"] or s["xp_pct"]:
        lines.append(f"\n💰 Zenِ بیشتر: +{s['gold_find_pct']*100:.1f}٪   ✨ XPِ بیشتر: +{s['xp_pct']*100:.1f}٪")
    lines.append(
        "\n\n💡 راهِ سریعِ بالابردنِ ضریبِ عنصری: **الکسیرِ تشدیدِ عنصری** "
        "(میزِ کیمیاگری) — +۲۰٪ برای ۱ ساعت.\n"
        "راهِ دائمی: مسیرِ 🌪️ الیمنتال تو درختِ مهارت، یا رسیدنِ کاتانا به تیرِ Ascended (سطحِ ۷۲+)."
    )
    return "\n".join(lines)

async def cb_atk_stats(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 برگشت به حمله", callback_data="atk:menu", style=ButtonStyle.PRIMARY)]
    ])
    await cb.answer()
    await cb.message.answer(_combat_stats_text(player), reply_markup=kb)

async def cmd_combat_stats(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    await msg.answer(_combat_stats_text(player))

# ─── Attack Menu ─────────────────────────────────────────────

async def _render_attack_panel(uid: int, player: dict) -> tuple[str, InlineKeyboardMarkup]:
    combo = player.get("combo", 0)
    map_name = player.get("map", "Verdant Vale")
    event = get_today_event()
    fight = get_fight(player)

    rage = player.get("rage", 0)
    buttons = []
    for key, atk in ATTACK_TYPES.items():
        cd = check_cooldown(uid, key)
        if key == "combo" and combo < 3:
            btn_text = f"{atk['name']} (combo {combo}/3 ❌)"
            cb = "atk:locked"
        elif key == "ultimate" and rage < 100:
            btn_text = f"{atk['name']} (rage {rage}/100 ❌)"
            cb = "atk:locked"
        elif cd > 0:
            btn_text = f"{atk['name']} ⏳{cd}s"
            cb = "atk:locked"
        else:
            btn_text = f"{atk['name']}"
            # اگه در حال نبرد با یه دشمن هستی، حمله باید همون دشمنو دوباره بزنه
            # نه اینکه یه دشمن جدید رندوم انتخاب کنه
            cb = f"atkc:{key}" if fight else f"atk:{key}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=cb, style=ButtonStyle.PRIMARY)])

    # 🆕 ردیفِ سوییچِ استنس (تهاجمی/متعادل/دفاعی)
    cur_stance = stance.get_stance(player)
    st_cd = stance.stance_switch_cooldown(player)
    stance_buttons = []
    for key in stance.STANCE_ORDER:
        s = stance.STANCES[key]
        mark = "🔘" if key == cur_stance else ""
        label = f"{mark}{s['name']}" if key != cur_stance else f"✅{s['name']}"
        stance_buttons.append(InlineKeyboardButton(
            text=label,
            callback_data=f"stance:{key}" if key != cur_stance and st_cd == 0 else "atk:locked",
            style=ButtonStyle.PRIMARY,
        ))
    buttons.append(stance_buttons)
    buttons.append([InlineKeyboardButton(text="❓ فرقِ حملات چیه؟", callback_data="atk_help", style=ButtonStyle.PRIMARY)])
    buttons.append([InlineKeyboardButton(text="📊 آمار مبارزه", callback_data="atk_stats", style=ButtonStyle.PRIMARY)])
    buttons.append([InlineKeyboardButton(text="📜 کوئست حمله", callback_data="hunt:panel", style=ButtonStyle.PRIMARY)])

    # ✨ Stage 3: دسترسیِ سریع به پنلِ فعالِ کلاس (طلسم/مزدور/نورِ مقدس/دخمه)
    from class_system import CLASSES as _CLS_MAP
    _cls_info = _CLS_MAP.get(player.get("class"), {})
    if _cls_info:
        buttons.append([InlineKeyboardButton(
            text=f"{_cls_info.get('emoji','⚜️')} قدرت‌های {_cls_info.get('name_fa','کلاس')}",
            callback_data="class_panel", style=ButtonStyle.PRIMARY,
        )])

    if fight:
        enemy = fight
        tier_emoji = {"common":"⚪","rare":"🔵","epic":"🟣","legendary":"🟡"}.get(enemy.get("tier","common"),"⚪")
        buttons.append([InlineKeyboardButton(text="🏃 فرار از نبرد", callback_data="atk_flee", style=ButtonStyle.DANGER)])
        st_txt = ""
        active_st = enemy.get("_status")
        if active_st and active_st.get("turns_left", 0) > 0:
            sdef = STATUSES.get(active_st.get("key"), {})
            st_txt = f"\n{sdef.get('emoji','')} دشمن دچار **{sdef.get('name','')}**ه ({active_st['turns_left']} نوبتِ دیگه)"
        fight_txt = (
            f"\n\n🩸 **در حال نبرد با {enemy['name']} {tier_emoji}**\n"
            f"❤️ {enemy['hp']}/{enemy['max_hp']} {hp_bar(enemy['hp'], enemy['max_hp'])}"
            f"{st_txt}\n"
            f"🔗 زنجیره: {chain.chain_display(player)}"
        )
    else:
        # 🆕 وضوح‌بخشی: قبلاً اینجا هیچی نشون داده نمی‌شد و معلوم نبود اصلاً
        # داری به چی حمله می‌کنی. الان صریح می‌گیم هنوز به هیچی حمله نکردی
        # و لیستِ دشمن‌های احتمالیِ همین نقشه رو پیش‌نمایش می‌دیم.
        pool = MAP_ENEMIES.get(map_name, [])
        preview_lines = []
        for name in pool:
            base = ENEMIES.get(name, {})
            t_e = {"common":"⚪","rare":"🔵","epic":"🟣","legendary":"🟡"}.get(base.get("tier","common"),"⚪")
            preview_lines.append(f"{name} {t_e}")
        preview_txt = "\n".join(preview_lines) if preview_lines else "—"
        fight_txt = (
            f"\n\n🎯 **هنوز به هیچی حمله نمی‌کنی!**\n"
            f"با زدن یکی از دکمه‌های حمله پایین، ۳ تا از دشمن‌های همین نقشه ({map_name}) میاد "
            f"که خودت یکیشو برای حمله انتخاب کنی. دشمن‌های این نقشه:\n{preview_txt}"
        )

    # Event bonus indicator
    event_txt = f"\n\n🎉 **ایونت امروز:** {event['name']}\n_{event['desc']}_"

    emax_hp = effective_max_hp(player)
    hp_txt = hp_bar(player.get("hp",100), emax_hp)
    fl = fatigue_level(player)
    fatigue_txt = ""
    if fl == 2:
        fatigue_txt = "\n😩 **خستگی شدید!** -۲۵٪ تمام آمار — با /rest استراحت کن."
    elif fl == 1:
        fatigue_txt = "\n😓 **خسته‌ای.** -۱۰٪ تمام آمار — با /rest استراحت کن."
    if curse_active(player):
        remaining_h = int((player.get("death_curse_until",0) - time.time()) // 3600)
        fatigue_txt += f"\n👻 **نفرین مرگ فعاله** ({max(0,remaining_h)}h مونده)"
    battles_left = daily_battles_remaining(player)
    stance_txt = f"\n🎭 استنس: {stance.STANCES[cur_stance]['name']} — {stance.STANCES[cur_stance]['desc']}"
    if st_cd > 0:
        stance_txt += f" (سوییچ بعدی: ⏳{st_cd}s)"
    parry.mark_panel_shown(player)   # 🆕 پری: لحظه‌ی نمایشِ پنل رو ثبت کن
    await asave_player(uid, player)

    event_hint = ""
    if event.get("map") == map_name:
        event_hint = f"\n🔥 **ایونتِ امروز ({event['name']}) همینجا فعاله!**"

    hunt_hint_txt = ""
    try:
        from hunt_questline import next_hunt_hint
        hh = next_hunt_hint(player)
        if hh:
            hunt_hint_txt = f"\n\n{hh}"
    except ImportError:
        pass

    text = (
        f"⚔️ **انتخاب نوع حمله**\n\n"
        f"❤️ {player.get('hp',100)}/{emax_hp} {hp_txt}\n"
        f"⚡ Combo: **{combo}x**\n"
        f"☄️ Rage: **{rage}/100**" + (" (آماده‌ی ضربه‌ی نهایی!)" if rage >= 100 else "") + "\n"
        f"📍 مپ: **{map_name}**{event_hint}\n"
        f"🗡️ نبرد امروز: {DAILY_BATTLE_MAX - battles_left}/{DAILY_BATTLE_MAX}"
        f"{stance_txt}"
        f"{fatigue_txt}"
        f"{fight_txt}"
        f"{event_txt}"
        f"{hunt_hint_txt}"
    )
    return text, InlineKeyboardMarkup(inline_keyboard=buttons)

async def cmd_attack(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    if player.get("hp", 100) <= 0:
        await msg.answer("💀 HP تو صفره! اول HP بگیر.\nاز /heal استفاده کن.")
        return
    text, kb = await _render_attack_panel(uid, player)
    await msg.answer(text, reply_markup=kb)

async def cmd_rest(msg: Message):
    """حالت سخت: استراحت ۳۰ دقیقه‌ای برای رفع خستگی."""
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    if is_resting(player):
        rem = int(player["resting_until"] - time.time())
        await msg.answer(f"😴 داری استراحت می‌کنی... {rem//60}:{rem%60:02d} مونده.")
        return
    if fatigue_level(player) == 0:
        await msg.answer("✅ خسته نیستی، نیازی به استراحت نداری.")
        return
    player["resting_until"] = time.time() + REST_SECONDS
    await asave_player(uid, player)
    await msg.answer(f"😴 داری استراحت می‌کنی... {REST_SECONDS//60} دقیقه طول می‌کشه و بعدش خستگیت کامل رفع می‌شه.")

async def cb_atk_locked(cb: CallbackQuery):
    await cb.answer("❌ این حمله الان در دسترس نیست!", show_alert=True)

# 🆕 سوییچ استنسِ نبرد از پنلِ حمله
async def cb_set_stance(cb: CallbackQuery):
    uid = cb.from_user.id
    key = cb.data.split(":")[1]
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    ok = stance.set_stance(player, key)
    if not ok:
        cd = stance.stance_switch_cooldown(player)
        await cb.answer(f"⏳ {cd} ثانیه دیگه می‌تونی استنس عوض کنی!", show_alert=True)
        return
    await asave_player(uid, player)
    await cb.answer(f"✅ استنس عوض شد: {stance.STANCES[key]['name']}")
    text, kb = await _render_attack_panel(uid, player)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass

async def cb_atk_select(cb: CallbackQuery):
    uid = cb.from_user.id
    atk_type = cb.data.split(":")[1]
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    cd = check_cooldown(uid, atk_type)
    if cd > 0:
        await cb.answer(f"⏳ {cd} ثانیه صبر کن!", show_alert=True)
        return

    # ─── حالت سخت: محدودیت نبرد روزانه ─────────────────────────
    if not use_daily_battle(player):
        await cb.answer(f"🚫 امروز {DAILY_BATTLE_MAX} نبرد انجام دادی! فردا دوباره تلاش کن.", show_alert=True)
        await asave_player(uid, player)
        return

    # ─── حالت سخت: ورشکستگی ─────────────────────────────────────
    from economy import is_bankrupt, BANKRUPTCY_MSG
    if is_bankrupt(player):
        await cb.answer(BANKRUPTCY_MSG, show_alert=True)
        return

    # 🆕 ضد-فارم: بعد از یه حدِ خیلی بالا، اصلاً نمی‌تونی بجنگی تا استراحت کنی
    if is_fatigue_locked(player):
        rest_min = REST_SECONDS // 60
        await cb.answer(
            f"😴 خیلی خسته‌ای! باید استراحت کنی (۳۰ دقیقه صبر کن یا از آیتمِ استراحت استفاده کن)"
            f" تا بتونی دوباره بجنگی.",
            show_alert=True
        )
        return

    register_battle_for_fatigue(player)
    await asave_player(uid, player)

    map_name = player.get("map", "Verdant Vale")
    enemies = get_map_enemies(map_name, 3)

    # ─── نخبه‌ها تو /attack هم ممکنه ظاهر بشن — ولی نه تو همون اولین
    # نبردِ تیوتوریال (اونجا باید تضمینی راحت باشه) ─────────────────
    import onboarding
    if not onboarding.is_in_tutorial(player):
        from elite_mobs import maybe_elevate
        enemies = [maybe_elevate(e, player, map_name) for e in enemies]

    # ─── تکمیلِ ایونتِ روزانه: «❄️ توفان یخ» (ice_enemy_weak) ─────────
    # قبلاً این بونوس فقط تو توضیحاتِ متنی بود و هیچ‌جا اجرا نمی‌شد.
    # الان، فقط رو مپِ همون ایونت (Frostheim)، HP دشمن‌ها واقعاً کم می‌شه.
    today_event = get_today_event()
    if today_event.get("bonus") == "ice_enemy_weak" and today_event.get("map") == map_name:
        for _e in enemies:
            _e["hp"] = max(1, int(_e["hp"] * 0.65))
            _e["max_hp"] = _e["hp"]

    combat_sessions[uid] = {"atk_type": atk_type, "enemies": enemies}

    atk = ATTACK_TYPES[atk_type]
    buttons = []
    lines = [f"{atk['name']} رو انتخاب کردی — حالا بگو 🎯 **به کدوم دشمن بزنم؟**\n\n"]

    for i, enemy in enumerate(enemies):
        tier_emoji = {"common":"⚪","rare":"🔵","epic":"🟣","legendary":"🟡"}.get(enemy.get("tier","common"),"⚪")
        lines.append(
            f"{enemy['name']} {tier_emoji}\n"
            f"   ❤️{enemy['hp']} | 💥{enemy['dmg']} | "
            f"⚡ضعف:{enemy.get('weak','—')} | 🎁{int(enemy['drop_chance']*100)}%\n"
        )
        buttons.append([InlineKeyboardButton(
            text=f"{enemy['name']} {tier_emoji} (HP:{enemy['hp']})",
            callback_data=f"atk_enemy:{i}"
        , style=ButtonStyle.PRIMARY)])

    buttons.append([InlineKeyboardButton(text="❌ لغو", callback_data="atk:cancel", style=ButtonStyle.DANGER)])
    await cb.message.edit_text("".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await cb.answer()

async def cb_atk_cancel(cb: CallbackQuery):
    uid = cb.from_user.id
    combat_sessions.pop(uid, None)
    await cb.message.delete()
    await cb.answer("❌ لغو شد!")

from action_lock import no_double_tap


@no_double_tap()
async def cb_atk_enemy(cb: CallbackQuery):
    uid = cb.from_user.id
    idx = int(cb.data.split(":")[1])
    session = combat_sessions.get(uid)
    if not session:
        await cb.answer("❌ session منقضی شد!", show_alert=True)
        return

    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    enemy = session["enemies"][idx].copy()
    enemy["max_hp"] = enemy["hp"]           # نقطه‌ی شروع HP این دشمن مشخص رو ثابت نگه می‌داریم
    atk_type = session["atk_type"]

    set_fight(player, enemy)   # از این لحظه این دشمن «فعال»ه؛ روی خود پروفایل ذخیره می‌شه
    chain.reset_chain(player)        # 🆕 شروعِ نبردِ جدید = زنجیره‌ی حمله از صفر
    start_new_battle(player)         # 🆕 ریست پرچم‌های نبردیِ کاتانا (مثلاً phoenix_rebirth یک‌بار در نبرد)

    # ─── حالت سخت: کمین دشمن ───────────────────────────────────
    # قبل از این‌که بازیکن اولین ضربه رو بزنه، شانس داره دشمن غافلگیرش کنه.
    amb = maybe_ambush(player, enemy)
    if amb:
        player["hp"] = max(0, player.get("hp", 100) - amb["dmg"])
        player["_ambush_msg"] = amb["msg"]

    await asave_player(uid, player)
    combat_sessions.pop(uid, None)

    await resolve_hit(cb, player, atk_type)

@no_double_tap()
async def cb_atk_continue(cb: CallbackQuery):
    """ضربه‌ی بعدی به همون دشمنی که از قبل در حال نبرد باهاش هستیم (HP حفظ می‌شه)"""
    uid = cb.from_user.id
    atk_type = cb.data.split(":")[1]
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    if player.get("hp", 100) <= 0:
        await cb.answer("💀 HP تو صفره! اول با /heal درمان شو.", show_alert=True)
        return

    fight = get_fight(player)
    if not fight:
        await cb.answer("❌ نبردی در جریان نیست! از منوی حمله شروع کن.", show_alert=True)
        return

    cd = check_cooldown(uid, atk_type)
    if cd > 0:
        await cb.answer(f"⏳ {cd} ثانیه صبر کن!", show_alert=True)
        return

    await resolve_hit(cb, player, atk_type)

async def cb_atk_flee(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if player:
        set_fight(player, None)
        chain.reset_chain(player)   # 🆕 فرار = پایانِ زنجیره
        await asave_player(uid, player)
    await cb.answer("🏃 از نبرد فرار کردی!", show_alert=True)
    try:
        await cb.message.delete()
    except Exception:
        pass

async def resolve_hit(cb: CallbackQuery, player: dict, atk_type: str):
    """
    یه ضربه به دشمن فعلی (active_fights) می‌زنه:
    - HP دشمن کم می‌شه و ذخیره می‌مونه (نه صفر/ریست)
    - اگه دشمن نمرده باشه، دکمه‌ی «ادامه نبرد» میاد تا بعد از کول‌داون دوباره بزنی
    - اگه دشمن بمیره، پاداش کامل داده می‌شه و نبرد تموم می‌شه
    """
    uid = cb.from_user.id
    fight = get_fight(player)
    if not fight:
        await cb.answer("❌ نبردی در جریان نیست!", show_alert=True)
        return
    enemy = fight
    map_name = player.get("map", "Verdant Vale")

    # 🆕 combat_v3: روی calc_combat قدیمی، لایه‌ی شخصیت/بعد/مهارتِ کاتانا رو
    # هم اعمال می‌کنه (اگه بازیکن کاراکتر نداشته باشه، دقیقاً مثل قبل رفتار می‌کنه)
    result = calc_combat_v3(player, enemy, atk_type)

    # ─── 🆕 نقطه‌ضعف/شکست: اگه دقیقاً از عنصرِ ضعفِ دشمن استفاده کردی ────
    brk_note = brk.apply_break(result, player, enemy, atk_type)
    if brk_note:
        result.setdefault("logs", []).append(brk_note)

    # ─── 🆕 پری/کانترِ تایمینگ‌محور: فقط وقتی اتک‌تایپ parry باشه ──────
    if atk_type == "parry":
        result.setdefault("logs", []).append(parry.resolve_parry(result, player, enemy))

    # ─── حالت سخت: نفرین مرگ + جراحت دائمی + خستگی روی دمیج ────
    fmult = fatigue_stat_mult(player)
    result["dmg"] = int(result["dmg"] * outgoing_dmg_penalty_mult(player) * fmult)
    if result.get("enemy_dmg", 0) > 0:
        result["enemy_dmg"] = int(result["enemy_dmg"] * incoming_dmg_penalty_mult(player) / max(0.5, fmult))

    # ─── 🆕 استنسِ نبرد: دمیجِ خروجی/ورودی رو بر اساس استنسِ فعلی تعدیل می‌کنه ───
    result["dmg"] = stance.apply_stance_outgoing(result["dmg"], player)
    if result.get("enemy_dmg", 0) > 0:
        result["enemy_dmg"] = stance.apply_stance_incoming(result["enemy_dmg"], player)
    # استنسِ دفاعی یه شانسِ کریتِ اضافه هم داره (اگه از قبل کریت نخورده باشی)
    cbonus = stance.stance_crit_bonus(player)
    if cbonus > 0 and not result.get("crit") and result["dmg"] > 0 and random.random() < cbonus:
        result["dmg"] = int(result["dmg"] * 2.0)
        result["crit"] = True
        result.setdefault("logs", []).append("🛡️✨ **کریتِ استنسِ دفاعی!**")
    # گیجِ Rage هم زیرِ تاثیرِ استنسه (تهاجمی خنثی، متعادل بیشتر، دفاعی کمتر)
    if result["dmg"] > 0 and not result.get("miss"):
        from combat_engine import RAGE_PER_HIT
        rage_delta = stance.stance_rage_delta(player, RAGE_PER_HIT)
        if rage_delta:
            player["rage"] = max(0, min(100, player.get("rage", 0) + int(rage_delta)))

    # ─── 🆕 زنجیره‌ی حمله: اگه الگوی فینیشر کامل شده باشه، بونوسِ ویژه بده ───
    finisher = chain.track_chain(player, atk_type)
    if finisher and result["dmg"] > 0:
        result["dmg"] = int(result["dmg"] * finisher["dmg_mult"])
        result.setdefault("logs", []).append(finisher["msg"])
        if finisher.get("force_status"):
            status_key = ELEMENT_STATUS.get(ALL_CHARACTERS.get(player.get("character", ""), {}).get("element", ""))
            if status_key:
                result["status"] = status_key
        if finisher.get("bonus_rage"):
            player["rage"] = max(0, min(100, player.get("rage", 0) + finisher["bonus_rage"]))

    # ─── حالت سخت: غش کردن با خستگی شدید (۵٪ شانس) ─────────────
    fainted = fatigue_level(player) == 2 and random.random() < FATIGUE_FAINT_CHANCE
    if fainted:
        result["dmg"] = 0
        result["miss"] = True
        result["logs"] = result.get("logs", []) + ["😵 **از فرط خستگی غش کردی و ضربه‌ات به‌کل رد شد!**"]
        result["enemy_dmg"] = int(enemy.get("dmg", 10) * 1.2)
        result["counter"] = True

    # Event multipliers
    # ─── تکمیلِ «نقشه‌ی زنده»: بعضی ایونت‌های روزانه یه فیلدِ "map"
    # دارن (مثلاً dragon_raid → فقط Dragonnest Peaks) که قرار بوده
    # فقط رو همون مپ اثر کنه، ولی این چک هیچ‌وقت انجام نمی‌شد و
    # بونوسِ Zen/XP رو کلِ دنیا می‌گرفت — حتی کسی که اصلاً پاش رو
    # اونجا نذاشته بود. حالا فقط وقتی player["map"] با event["map"]
    # یکی باشه (یا event["map"] خالی/None باشه، یعنی سراسریه) اعمال
    # می‌شه.
    event = get_today_event()
    bonus = event.get("bonus", "")
    event_map = event.get("map")
    on_event_map = (event_map is None) or (map_name == event_map)
    if on_event_map:
        zen_mult = get_event_multiplier(bonus, "zen")
        xp_mult  = get_event_multiplier(bonus, "xp")
    else:
        zen_mult = 1.0
        xp_mult  = 1.0

    # Apply damage to player if counter
    if result["counter"] and result["enemy_dmg"] > 0:
        player["hp"] = max(0, player.get("hp", 100) - result["enemy_dmg"])
        if result.get("reflect_dmg", 0) > 0:
            enemy["hp"] = max(0, enemy.get("hp", enemy.get("max_hp", 1)) - result["reflect_dmg"])

    # ─── حالت سخت: ضربه مرگبار دشمنان سطح‌بالا ─────────────────
    deadly = maybe_deadly_blow(player, enemy) if player.get("hp", 100) > 0 else None
    if deadly:
        player["hp"] = max(0, player.get("hp", 100) - deadly["dmg"])
        result["logs"].append(deadly["msg"])

    dmg = 0 if result["miss"] else result["dmg"]

    # ─── تکمیلِ ایونتِ روزانه: «🌋 روز آتشفشان» (fire_dmg_x2) ──────────
    # قبلاً این بونوس هم فقط تو توضیحاتِ متنی بود. الان، فقط رو مپِ
    # همون ایونت (Emberhollow) و فقط برای کاراکترهایی که عنصرشون
    # دقیقاً «آتش»ه، دمیج واقعاً ۲ برابر می‌شه.
    if on_event_map and bonus == "fire_dmg_x2" and dmg > 0:
        char_data = ALL_CHARACTERS.get(player.get("character", ""), {})
        if char_data.get("element") == "آتش":
            dmg = int(dmg * get_event_multiplier(bonus, "dmg"))

    enemy["hp"] = max(0, enemy.get("hp", enemy.get("max_hp", 1)) - dmg)
    killed = enemy["hp"] <= 0
    if killed:
        # برای ماموریت‌های فرعی («۵ تا فلان دشمن رو بکش») — quest_engine.py
        kl = player.setdefault("kill_log", {})
        kl[enemy.get("name", "?")] = kl.get(enemy.get("name", "?"), 0) + 1

    # ─── باگ‌فیکس: لایف‌استیل قبلاً محاسبه می‌شد ولی هیچ‌جا به HP اضافه نمی‌شد ─
    if result.get("lifesteal_heal", 0) > 0:
        player["hp"] = min(effective_max_hp(player), player.get("hp", 100) + result["lifesteal_heal"])

    # Combo
    if not result["miss"]:
        player["combo"] = player.get("combo", 0) + 1
    else:
        player["combo"] = 0

    zen_gain = 0
    xp_gain  = 0
    drop     = None
    leveled  = False
    epilogue_text = None
    katana_kill_msgs = []

    if killed:
        base_zen = enemy["zen"] + random.randint(0, 10)
        base_xp  = enemy["xp"]  + random.randint(0, 8)
        from economy_engine import apply_gold_find
        from guild_system import get_perk, get_war_xp_buff
        from game_data import XP_GAIN_MULTIPLIER, ZEN_GAIN_MULTIPLIER
        import mentor_system as ms
        from world_pulse import pulse_value
        import anti_farm as af

        # ─── باگ‌فیکس: مسیرِ «حمله» بر خلافِ مسیرِ لوت، ست‌ها/آیتم‌ها/همراه/
        # کوئست‌لاینِ شکار رو تو Zen/XP حساب نمی‌کرد — همینه که حمله همیشه
        # ضعیف‌تر از لوت به‌نظر می‌رسید با اینکه دشمن‌ها یکی‌ان.
        setb = {}
        try:
            from loot_engine import get_set_bonus_stats
            setb = get_set_bonus_stats(player)
        except ImportError:
            pass
        try:
            from divine_seals import get_seal_bonus_stats
            for _k, _v in get_seal_bonus_stats(player).items():
                setb[_k] = setb.get(_k, 0) + _v
        except ImportError:
            pass
        try:
            from item_system import equipment_stats as _atk_eq_stats
            eqb = _atk_eq_stats(player)
        except ImportError:
            eqb = {}
        try:
            from pet_system import pet_combat_bonus as _atk_pet_stats
            petb = _atk_pet_stats(player)
        except ImportError:
            petb = {}
        try:
            from hunt_questline import get_hunt_bonuses
            for _k, _v in get_hunt_bonuses(player).items():
                setb[_k] = setb.get(_k, 0) + _v
        except ImportError:
            pass
        rb = rebirth_bonuses(player)

        zen_gain = apply_gold_find(player, int(base_zen * zen_mult * ZEN_GAIN_MULTIPLIER * pulse_value("zen_mult") * (1 + setb.get("zen_pct", 0))))
        stacked_bonus = af.cap_bonus(get_perk(player, "zen_gain_pct"))
        zen_gain = int(zen_gain * (1 + stacked_bonus))
        # 💰 تاجر: gold_multiplier کلاسش رو صرفِ درآمدِ Zen می‌کنه (نه XP)
        if player.get("class") == "merchant":
            gold_mult = player.get("class_system_data", {}).get("gold_multiplier", 1.0)
            zen_gain = int(zen_gain * gold_mult)
        xp_gain  = int(base_xp  * xp_mult * XP_GAIN_MULTIPLIER * pulse_value("xp_mult") * (1 + setb.get("xp_pct", 0) + rb["xp_pct"] + eqb.get("xp_pct", 0) + petb.get("xp_pct", 0)))
        stacked_xp_bonus = af.cap_bonus(get_perk(player, "xp_gain_pct") + get_war_xp_buff(player)
                                         + ms.mentee_xp_bonus(player) + ms.mentor_xp_bonus(player))
        xp_gain  = int(xp_gain * (1 + stacked_xp_bonus))

        # 🆕 ضد-فارم: پنالتیِ خستگی + سقفِ نرمِ روزانه
        zen_gain = int(zen_gain * fatigue_reward_mult(player) * af.daily_mult(player, "zen"))
        xp_gain  = int(xp_gain  * fatigue_reward_mult(player) * af.daily_mult(player, "xp"))

        # 🆕 بیماریِ بیمارستان متروکه (abandoned_locations.py)
        from abandoned_locations import sickness_mult
        sick_mult = sickness_mult(player)
        zen_gain = int(zen_gain * sick_mult)
        xp_gain  = int(xp_gain * sick_mult)

        af.register_daily_gain(player, "zen", zen_gain)
        af.register_daily_gain(player, "xp", xp_gain)
        af.log_if_suspicious(uid, player.get("name", "—"), zen_gain, xp_gain, "combat_handlers")
        af.register_action_time(player, uid, player.get("name", "—"), "combat_handlers")

        import battle_pass as bp
        bp.add_points(player, xp_gain)
        if player.get("mentee_of"):
            bp.add_mentee_pair_points(player, xp_gain)
        for _mentee_id in player.get("mentor_of", []):
            bp.add_pair_points(player, _mentee_id, xp_gain)

        player["zen"]   = player.get("zen", 0) + zen_gain
        player["xp"]    = player.get("xp", 0)  + xp_gain
        player["kills"] = player.get("kills", 0) + 1

        # ─── Katana Soul: Bond XP + katana_kills (katana_core.py) ───
        # فقط ماجراجو کاتانا داره — سه کلاسِ دیگه نباید Bond/Awakening/
        # Epilogue بگیرن (چیزی که کلاً ندارن).
        if player.get("character"):
            from katana_core import add_bond_xp, unlocked_skills, calc_katana_bonus
            player["katana_kills"] = player.get("katana_kills", 0) + 1
            bond_result = add_bond_xp(player, amount=1)
            from character_lore import check_epilogue
            epilogue_text = check_epilogue(player, bond_result)
            # مهارت soul_reap (بیداری مرحله‌ی ۳) با هر کشتن HP بازیابی می‌کنه
            kcore = calc_katana_bonus(player)
            if kcore["skills"].get("soul_reap"):
                heal = int(effective_max_hp(player) * 0.04)
                player["hp"] = min(effective_max_hp(player), player.get("hp", 0) + heal)

            # 🆕 combat_v3: پاداش‌های شخصیتی/حافظه‌ای کاتانا با هر کشتن
            katana_kill_msgs = katana_on_kill(player, enemy)
        elif player.get("class") == "healer":
            # ✨ درمانگر: به‌جای پاداشِ کاتانا، با هر کشتن کمی فیض/HP برمی‌گردونه
            csd = player.setdefault("class_system_data", {})
            csd["faith"] = min(csd.get("max_faith", 40), csd.get("faith", 0) + 2)
            heal = int(effective_max_hp(player) * 0.03)
            player["hp"] = min(effective_max_hp(player), player.get("hp", 0) + heal)

        drop = get_drop(enemy, player) if not result["miss"] else None
        if drop:
            player.setdefault("inventory", []).append(drop)

        old_level = player["level"]
        while player["xp"] >= xp_for_level(player["level"]) and player["level"] < effective_max_level(player):
            # ─── حالت سخت: دیوار سختی هر ۱۰ سطح ────────────────
            # اگه سطح فعلی روی یه دیواره و هنوز باسش رو نزدی، همینجا
            # می‌مونی — XP جمع می‌شه ولی سطحت بالاتر نمی‌ره.
            if is_level_wall(player["level"]) and player["level"] not in player.get("walls_cleared", []):
                break
            player["level"]  += 1
            player["max_hp"] += 5   # حالت سخت: قبلاً +۱۵ بود
            player["hp"]      = effective_max_hp(player)  # باگ‌فیکس: باف max_hp_pct هم لحاظ بشه
            leveled = True
        if leveled:
            from skill_tree import grant_levelup_points
            grant_levelup_points(player, old_level, player["level"])
            log_sync(
                f"⭐ **LEVEL UP**\n"
                f"👤 {player.get('name','—')} (`{uid}`)\n"
                f"🎴 {player.get('character','—')}\n"
                f"📊 سطح: {old_level} → {player['level']}",
                "LEVELUP"
            )

        set_fight(player, None)   # نبرد تموم شد

        # 🔗 لحظه‌ی باند (هر چند سطح، نه فقط سطحِ فارغ‌التحصیلی) — فقط وقتی هنوز شاگرده
        if leveled and player.get("mentee_of"):
            _bond_mentor = await aget_player(player["mentee_of"])
            bond_lines = ms.check_bond_milestone(_bond_mentor, player) if _bond_mentor else []
            if bond_lines:
                await asave_player(player["mentee_of"], _bond_mentor)
                try:
                    await cb.bot.send_message(player["mentee_of"], "\n".join(bond_lines))
                except Exception:
                    pass

        # 🎓 چک فارغ‌التحصیلی از سیستم استادی
        if ms.is_ready_to_graduate(player):
            mentor_id = player["mentee_of"]
            mentor = await aget_player(mentor_id)
            if mentor:
                ms.end_mentorship(mentor, player)
                mentor["zen"] = mentor.get("zen", 0) + ms.GRADUATE_MENTOR_ZEN
                mentor["xp"]  = mentor.get("xp", 0) + ms.GRADUATE_MENTOR_XP
                mentor["graduated_mentee_count"] = mentor.get("graduated_mentee_count", 0) + 1
                await asave_player(mentor_id, mentor)
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
    else:
        set_fight(player, enemy)  # HP باقیمانده‌ی دشمن رو روی پروفایل ذخیره کن (survive می‌کنه بین ری‌استارت‌ها)

    # ─── مرگ و اسپان مجدد (حالت سخت) ─────────────────────────
    # اگه HP پلیر صفر شد: نبرد جاری قطع می‌شه، به یه نقشه‌ی رندوم منتقل می‌شه
    # و با نیمی از HP کاملش برمی‌گرده (نه صفر، که گیر نکنه).
    respawned_map = None
    katana_death_msg = None
    hardcore_death_lines = []
    revive_msg = None
    revived = False
    if player["hp"] <= 0:
        # 🆕 combat_v3: قبل از قطعی‌کردنِ مرگ، چک کن ققنوس (یا مهارتِ مشابه) فعاله یا نه
        revive = katana_on_death(player)
        revived = revive.get("revived", False)
        if revive.get("messages"):
            revive_msg = "\n".join(revive["messages"])
        # ✨ Stage 3: درمانگر — اگه ققنوس/کاتانا نجاتش نداد، Self-Revive
        # خودشو چک کن (class_abilities.healer_try_revive؛ سقفِ ۱، هر ۲۴ ساعت ریجن می‌شه)
        if not revived and player.get("class") == "healer":
            from class_abilities import healer_try_revive
            hrevive = healer_try_revive(player)
            revived = hrevive.get("revived", False)
            if hrevive.get("messages"):
                revive_msg = ((revive_msg + "\n") if revive_msg else "") + "\n".join(hrevive["messages"])
    if player["hp"] <= 0 and not revived:
        set_fight(player, None)
        chain.reset_chain(player)   # 🆕 مرگ = پایانِ زنجیره
        respawned_map   = random.choice(SPAWN_MAPS)
        player["map"]   = respawned_map
        player["hp"]    = max(1, int(effective_max_hp(player) * 0.5))
        player["combo"] = 0

        # ─── رفع باگ: پاک کردن حالت سفر بعد از مرگ ───────────
        try:
            from loot_handlers import get_ls
            ls = get_ls(uid)
            ls["traveling"] = None
            ls["arrive"] = 0
        except Exception:
            pass

        # ─── Katana Soul: اثر مرگ روی پیوند روحی (katana_core.py) ───
        from katana_core import apply_death_penalty, katana_talk
        death_result = apply_death_penalty(player)
        katana_death_msg = f"🗡️ «{katana_talk(player, 'death')}»\n{death_result['message']}"

        # ─── حالت سخت: مجازات کامل مرگ (۲ برابر اگه با خستگی شدید مُردی) ─
        death_penalty_mult = 2.0 if fatigue_level(player) == 2 else 1.0
        hardcore_death_lines = apply_hardcore_death_penalty(player, death_penalty_mult)

    set_cooldown(uid, atk_type)
    from achievements import check_achievements
    new_titles = check_achievements(player)
    await asave_player(uid, player)

    # Quest updates
    if killed:
        await update_quest(uid, "kill", 1)
        await update_quest(uid, "earn", zen_gain)
        if enemy.get("tier") == "legendary": await update_quest(uid, "legend", 1)
        try:
            from map_activity import log_event
            kind = "elite_kill" if enemy.get("is_elite") else ("legendary_kill" if enemy.get("tier") == "legendary" else "kill")
            log_event(player.get("map", ""), cb.from_user.first_name, kind, player.get("map", ""), actor_id=uid)
        except Exception:
            pass
        try:
            from elite_mobs import apply_elite_kill_bonus
            apply_elite_kill_bonus(player, enemy)
            await asave_player(uid, player)  # save at line 989 already ran before this block, so save again
        except Exception:
            pass
    if atk_type == "heavy": await update_quest(uid, "heavy", 1)
    if result["crit"]:      await update_quest(uid, "crit", 1)
    if player["combo"] >= 10: await update_quest(uid, "combo", 1)
    await update_quest(uid, "survive", 1)

    # ─── آنبوردینگ: پیشرفتِ تیوتوریالِ پلیرِ جدید (onboarding.py) ─────
    import onboarding
    tutorial_hint = onboarding.on_attack_resolved(player, killed)
    tutorial_graduated = bool(tutorial_hint and tutorial_hint.startswith(onboarding.GRADUATION_MARK))
    tutorial_loot_step = bool(tutorial_hint and tutorial_hint.startswith(onboarding.LOOT_STEP_MARK))
    if tutorial_hint:
        tutorial_hint = onboarding.strip_graduation_mark(tutorial_hint)
        await asave_player(uid, player)  # tutorial_step/tutorial_done تغییر کرد، جداگونه ذخیره‌ش کن

    # Build result text
    char = ALL_CHARACTERS.get(player.get("character",""), {})
    elem = char.get("element", "")
    tier_emoji = {"common":"⚪","rare":"🔵","epic":"🟣","legendary":"🟡"}.get(enemy.get("tier","common"),"⚪")

    lines = []
    ambush_msg = player.pop("_ambush_msg", None)
    if ambush_msg:
        lines.append(f"{ambush_msg}\n\n")
    lines += [
        f"⚔️ **{ATTACK_TYPES[atk_type]['name']}**\n\n",
        f"**دشمن:** {enemy['name']} {tier_emoji}\n",
        f"{'─'*20}\n",
    ]

    if result["crit"]:  lines.append("💥 **CRITICAL HIT! ×2**\n")
    if result["miss"]:  lines.append("💨 **Miss!** دشمن dodge کرد!\n")
    if result["elem_bonus"]: lines.append(f"🎯 **ضعف عنصری {elem}! ×1.5**\n")

    for log in result["logs"]:
        lines.append(f"{log}\n")

    lines.append(f"\n💥 آسیب وارد شده: **{dmg}**\n")
    lines.append(f"❤️ HP دشمن: {enemy['hp']}/{enemy['max_hp']} {hp_bar(enemy['hp'], enemy['max_hp'])}\n")
    lines.append(f"{'─'*20}\n")

    if killed:
        lines.append(f"\n💀 **{enemy['name']} نابود شد!**\n")
        if drop:
            r_e = {"common":"⚪","rare":"🔵","epic":"🟣","legendary":"🟡"}.get(drop.get("rarity","common"),"⚪")
            lines.append(f"🎁 **Drop:** {drop['emoji']} {drop['name']} {r_e}\n")
        lines.append(f"\n✨ XP +{xp_gain}")
        if xp_mult > 1: lines.append(f" (×{xp_mult:.0f} ایونت!)")
        lines.append(f"\n💰 Zen +{bz_to_display(zen_gain)}")
        if zen_mult > 1: lines.append(f" (×{zen_mult:.0f} ایونت!)")
        
        log_sync(
            f"⚔️ **COMBAT KILL**\n"
            f"👤 {player.get('name','—')} (`{uid}`)\n"
            f"💀 {enemy.get('name','—')}\n"
            f"🎴 {player.get('character','—')}\n"
            f"💥 دمیج: {dmg:,}\n"
            f"✨ XP: +{xp_gain}\n"
            f"💰 Zen: +{zen_gain}",
            "COMBAT"
        )
    else:
        lines.append(f"\n🩸 دشمن هنوز زندست! بعد از کول‌داون دوباره بزن تا نابودش کنی.")

    lines.append(f"\n⚡ Combo: **{player['combo']}x**")
    lines.append(f"\n❤️ HP: {player['hp']}/{player['max_hp']} {hp_bar(player['hp'], player['max_hp'])}")

    if leveled:
        lines.append(f"\n\n🎉 **LEVEL UP! (レベルアップ！) → {player['level']}**\n❤️ HP کامل شد!")
        _rk = rank_up_announcement(old_level, player["level"], player.get("rebirth_count", 0))
        if _rk:
            lines.append(f"\n\n{_rk}")
        try:
            from quest_engine import story_new_chapter_available
            _new_ch = story_new_chapter_available(player)
        except Exception:
            _new_ch = None
        if _new_ch:
            lines.append(
                f"\n\n📖 **فصل جدید باز شد: {_new_ch['title']}** ({_new_ch['map']}) — "
                f"بزن رو «📖 داستان اصلی» تا ادامه بدی!"
            )

    for t in new_titles:
        lines.append(f"\n\n🏅 **عنوان جدید باز شد: {t}**")

    if epilogue_text:
        lines.append(epilogue_text)

    for kmsg in katana_kill_msgs:
        lines.append(f"\n\n{kmsg}")

    if tutorial_hint:
        lines.append(tutorial_hint)

    if revived:
        lines.append(f"\n\n{revive_msg}\n❤️ HP: {player['hp']}/{player['max_hp']} {hp_bar(player['hp'], player['max_hp'])}")
    elif player["hp"] <= 0 and not respawned_map:
        # حالت غیرمنتظره (نباید پیش بیاد چون بالاتر همیشه respawn می‌کنیم) — صرفاً برای اطمینان
        lines.append(f"\n\n💀 **HP صفر شد!** از /heal استفاده کن.")
    elif respawned_map:
        lines.append(
            f"\n\n💀 **مُردی!**\n"
            f"🌀 فقط کاتانات همراهته... دوباره در نقشه‌ی **{respawned_map}** به هوش اومدی.\n"
            + (f"{katana_death_msg}\n" if katana_death_msg else "")
            + f"❤️ HP: {player['hp']}/{player['max_hp']} {hp_bar(player['hp'], player['max_hp'])}"
        )
        if hardcore_death_lines:
            lines.append("\n\n" + "\n".join(hardcore_death_lines))

    if killed:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⚔️ دشمن بعدی",   callback_data=f"atk:{atk_type}", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton(text="🔙 منوی حمله",   callback_data="atk:menu", style=ButtonStyle.PRIMARY),
        ]])
    elif respawned_map:
        # پلیر مُرده و نبرد قطع شده — دیگه چیزی برای «ادامه» نیست
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 منوی حمله", callback_data="atk:menu", style=ButtonStyle.PRIMARY),
        ]])
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⚔️ ادامه نبرد", callback_data=f"atkc:{atk_type}", style=ButtonStyle.DANGER),
            InlineKeyboardButton(text="🏃 فرار",        callback_data="atk_flee", style=ButtonStyle.PRIMARY),
        ]])

    await cb.message.edit_text("".join(lines), reply_markup=kb)
    await cb.answer()

    if tutorial_graduated:
        from bot import main_kb, _is_group_chat
        is_group = _is_group_chat(cb.message.chat.type)
        await cb.message.answer("🔓 پنلِ کامل باز شد — از پایینِ صفحه استفاده کن:", reply_markup=main_kb(is_group=is_group, player=player))
    elif tutorial_loot_step:
        await cb.message.answer("🗺 دکمه‌ی «لوت» هم الان اضافه شد — بزنش!", reply_markup=onboarding.tutorial_kb_loot())

async def cb_atk_menu(cb: CallbackQuery):
    await cb.message.delete()
    await cb.answer()

# ─── Heal ────────────────────────────────────────────────────

# ─── حالت سخت (تعدیل‌شده طبق فیدبک): درمان هر ۱۰ دقیقه یک‌بار ────
# قبلاً محدودیت «فقط ۳ بار در روز» بود که خیلی سخت‌گیرانه و گیج‌کننده بود
# (و باگِ ریست‌نشدن هم داشت). الان به‌جاش یه کول‌داونِ ساده‌ست: هر ۱۰ دقیقه
# یه بار می‌تونی درمان بشی — قابل پیش‌بینی‌تره و طبیعی‌تر حس می‌شه.
HEAL_COOLDOWN_SECONDS = 600

def heal_on_cooldown(player: dict) -> bool:
    return time.time() < player.get("heal_cooldown_until", 0)

def heal_cooldown_remaining(player: dict) -> int:
    return max(0, int(player.get("heal_cooldown_until", 0) - time.time()))

def start_heal_cooldown(player: dict):
    player["heal_cooldown_until"] = time.time() + HEAL_COOLDOWN_SECONDS

# نکته: DAILY_HEAL_MAX/daily_heals_remaining/use_daily_heal برای سازگاری با
# کدهای قدیمی نگه داشته شدن ولی دیگه جایی صدا زده نمی‌شن — کول‌داون جایگزینشون شد.
DAILY_HEAL_MAX = 3

def daily_heals_remaining(player: dict) -> int:
    now = time.time()
    if now >= player.get("daily_heal_reset_at", 0):
        player["daily_heal_used"] = 0
        player["daily_heal_reset_at"] = now + 86400
    return DAILY_HEAL_MAX - player.get("daily_heal_used", 0)

def use_daily_heal(player: dict) -> bool:
    if daily_heals_remaining(player) <= 0:
        return False
    player["daily_heal_used"] = player.get("daily_heal_used", 0) + 1
    return True

async def cmd_heal(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return

    if heal_locked(player):
        rem = int(player["heal_lockout_until"] - time.time())
        await msg.answer(f"⏳ به‌خاطر نفرین مرگ، تا {rem//60}:{rem%60:02d} دیگه نمی‌تونی درمان بشی.")
        return
    if daily_heals_remaining(player) <= 0:
        await msg.answer(f"🚫 امروز {DAILY_HEAL_MAX} بار درمان شدی! فردا دوباره تلاش کن.")
        await asave_player(uid, player)
        return

    hp     = player.get("hp", 100)
    max_hp = player.get("max_hp", 100)

    if hp >= max_hp:
        await msg.answer(f"❤️ HP تو کامله! ({hp}/{max_hp})")
        return

    missing   = max_hp - hp
    from skill_tree import get_skill_bonuses
    discount  = get_skill_bonuses(player).get("heal_cost_discount", 0)
    per_hp    = 15 * (1 - discount)  # حالت سخت: هزینه درمان ۳ برابر شد
    if curse_active(player):
        per_hp *= (1 + DEATH_CURSE_HEAL_PEN)  # حالت سخت: نفرین مرگ +۵۰٪ هزینه درمان
    heal_cost = int(missing * per_hp)

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"💊 درمان کامل ({bz_to_display(heal_cost)})",
            callback_data="heal:full"
        , style=ButtonStyle.SUCCESS),
        InlineKeyboardButton(
            text=f"💉 درمان ۵۰HP ({bz_to_display(int(min(50,missing)*per_hp))})",
            callback_data="heal:half"
        , style=ButtonStyle.SUCCESS),
    ]])

    await msg.answer(
        f"💊 **درمانگاه**\n\n"
        f"❤️ HP فعلی: {hp}/{max_hp} {hp_bar(hp, max_hp)}\n"
        f"💰 هزینه درمان کامل: **{bz_to_display(heal_cost)}**\n"
        f"_(هر HP = 5 BZ)_",
        reply_markup=kb
    )

async def cb_heal(cb: CallbackQuery):
    uid = cb.from_user.id
    heal_type = cb.data.split(":")[1]
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    if heal_locked(player):
        rem = int(player["heal_lockout_until"] - time.time())
        await cb.answer(f"⏳ به‌خاطر نفرین مرگ، تا {rem//60}:{rem%60:02d} دیگه نمی‌تونی درمان بشی.", show_alert=True)
        return
    if daily_heals_remaining(player) <= 0:
        await cb.answer(f"🚫 امروز {DAILY_HEAL_MAX} بار درمان شدی!", show_alert=True)
        return

    hp     = player.get("hp", 100)
    max_hp = player.get("max_hp", 100)
    zen    = player.get("zen", 0)

    from skill_tree import get_skill_bonuses
    discount = get_skill_bonuses(player).get("heal_cost_discount", 0)
    per_hp   = 15 * (1 - discount)  # حالت سخت: هزینه درمان ۳ برابر شد
    if curse_active(player):
        per_hp *= (1 + DEATH_CURSE_HEAL_PEN)  # حالت سخت: نفرین مرگ +۵۰٪ هزینه درمان

    if heal_type == "full":
        missing = max_hp - hp
        cost    = int(missing * per_hp)
    else:
        missing = min(50, max_hp - hp)
        cost    = int(missing * per_hp)

    if zen < cost:
        await cb.answer(f"❌ Zen کافی نداری! {bz_to_display(zen)} / {bz_to_display(cost)}", show_alert=True)
        return

    use_daily_heal(player)
    player["zen"] -= cost
    player["hp"]  = min(max_hp, hp + missing)
    await asave_player(uid, player)

    log_sync(
        f"💊 **HEAL**\n"
        f"👤 {player.get('name','—')} (`{uid}`)\n"
        f"❤️ +{missing} HP\n"
        f"💰 هزینه: {bz_to_display(cost)}",
        "ECONOMY"
    )

    await cb.answer(f"💊 +{missing} HP درمان شدی!", show_alert=True)
    await cb.message.edit_text(
        f"💊 **درمان شدی!**\n\n"
        f"❤️ HP: {player['hp']}/{max_hp} {hp_bar(player['hp'], max_hp)}\n"
        f"💰 هزینه: {bz_to_display(cost)}\n"
        f"موجودی: {bz_to_display(player['zen'])}"
    )

# ─── Daily Event ─────────────────────────────────────────────

async def cmd_event(msg: Message):
    event  = get_today_event()
    quests = get_today_quests()
    uid    = msg.from_user.id
    qp     = await get_qp(uid)

    quest_lines = []
    for q in quests:
        prog  = qp.get(q["id"], 0)
        done  = prog >= q["target"]
        check = "✅" if done else f"{prog}/{q['target']}"
        quest_lines.append(
            f"{'✅' if done else '🔸'} **{q['name']}** [{check}]\n"
            f"   {q['desc']}\n"
            f"   🎁 {bz_to_display(q['reward_zen'])} + ✨{q['reward_xp']} XP\n"
        )

    from world_pulse import pulse_status_text
    map_note = f"📍 مپ ویژه: **{event['map']}** _(بونوسِ Zen/XP این ایونت فقط همون‌جا فعاله — باید بری اونجا)_" if event.get("map") else "🌍 سراسری — همه‌جای دنیا فعاله"
    await msg.answer(
        f"🎉 **ایونت امروز:**\n\n"
        f"**{event['name']}**\n"
        f"_{event['desc']}_\n"
        f"{map_note}\n\n"
        f"{'─'*20}\n"
        f"📋 **ماموریت‌های روزانه:**\n\n"
        + "".join(quest_lines) +
        f"\n{'─'*20}\n"
        f"{pulse_status_text()}\n"
        f"⏰ ریست در: **نیمه شب**"
    )

async def cmd_quests(msg: Message):
    await cmd_event(msg)

async def cmd_wall(msg: Message):
    """حالت سخت: چالش دیوار سختی — وقتی بازیکن رو یه دیوار (سطح ۱۰،۲۰،...) گیر کرده."""
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    lvl = player.get("level", 1)
    if not (is_level_wall(lvl) and lvl not in player.get("walls_cleared", [])):
        await msg.answer("✅ الان رو هیچ دیوار سختی‌ای گیر نکردی.")
        return

    boss = wall_boss_stats(lvl)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⚔️ شروع چالش", callback_data=f"wallch:{lvl}", style=ButtonStyle.DANGER)
    ]])
    await msg.answer(
        f"🚧 **دیوار سختی سطح {lvl}**\n\n"
        f"برای رد شدن باید {boss['name']} رو شکست بدی.\n"
        f"❤️ HP باس: {boss['hp']}   💥 دمیج باس: {boss['dmg']}\n\n"
        f"⚠️ اگه ببازی، هیچ جریمه‌ای نمی‌گیری ولی باید دوباره تلاش کنی.",
        reply_markup=kb
    )

async def cb_wall_challenge(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    try:
        lvl = int(cb.data.split(":")[1])
    except Exception:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    if lvl != player.get("level", 1) or lvl in player.get("walls_cleared", []):
        await cb.answer("این چالش دیگه براش معتبر نیست.", show_alert=True)
        return

    boss = wall_boss_stats(lvl)
    # ─── جنگ ساده‌ی سریع (چند راند خودکار) بر پایه‌ی دمیج پایه‌ی بازیکن ─
    # نکته: قبلاً این‌جا `for c in ALL_CHARACTERS if c["name"]==...` بود که
    # چون ALL_CHARACTERS یه dict به‌کلید‌اسمه (نه لیستِ آبجکت)، همیشه با
    # TypeError کرش می‌کرد. حالا هم فیکس شده هم کلاس‌محور: ماجراجو از
    # base_dmg هویتِ کاتانا، سه کلاسِ دیگه از atk کلاسِ خودشون.
    if player.get("character"):
        from characters import ALL_CHARACTERS
        char = ALL_CHARACTERS.get(player["character"])
        p_base_dmg = char["base_dmg"] if char else 10
    else:
        p_base_dmg = (player.get("stats") or {}).get("atk", 10)
    p_dmg = max(5, int(p_base_dmg + player.get("level", 1) * 1.5))
    p_hp  = player.get("hp", player.get("max_hp", 100))
    boss_hp, rounds = boss["hp"], 0
    while boss_hp > 0 and p_hp > 0 and rounds < 200:
        boss_hp -= p_dmg * random.uniform(0.8, 1.2)
        if boss_hp <= 0:
            break
        p_hp -= boss["dmg"] * random.uniform(0.7, 1.1)
        rounds += 1

    if p_hp > 0:
        player.setdefault("walls_cleared", []).append(lvl)
        player["hp"] = max(1, int(p_hp))
        await asave_player(uid, player)
        
        log_sync(
            f"🚧 **WALL CLEARED**\n"
            f"👤 {player.get('name','—')} (`{uid}`)\n"
            f"📊 سطح دیوار: {lvl}",
            "LEVELUP"
        )
        
        await cb.message.edit_text(
            f"🎉 **دیوار سختی سطح {lvl} شکسته شد!**\n"
            f"👑 {boss['name']} شکست خورد!\n"
            f"❤️ HP باقی‌مونده: {player['hp']}\n"
            f"🎁 +{boss['xp']} XP، +{boss['zen']} Zen\n\n"
            f"حالا می‌تونی به سطح‌های بعدی بری."
        )
        player["xp"] = player.get("xp", 0) + boss["xp"]
        player["zen"] = player.get("zen", 0) + boss["zen"]
        await asave_player(uid, player)
    else:
        player["hp"] = max(1, player.get("max_hp", 100) // 4)
        await asave_player(uid, player)
        await cb.message.edit_text(
            f"💀 **شکست خوردی!**\n{boss['name']} خیلی قوی بود...\n"
            f"دوباره تلاش کن (با /wall)."
        )
    await cb.answer()

# ─── Register ────────────────────────────────────────────────

def register_combat_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_attack, Command("attack"))
    dp.message.register(cmd_combat_stats, Command("combatstats"))
    # نکته: /heal و کال‌بک‌های "heal:*" اینجا حذف شدن چون team_handlers.py یه نسخه‌ی
    # کامل‌تر داره (شامل هیل هم‌تیمی و آیتم‌های هیل) که همون چیزیه که دکمه‌ی
    # «💊 درمان» تو bot.py صداش می‌زنه. قبلاً هر دو ماژول هم‌زمان روی Command("heal")
    # و callback_data شروع‌شونده با "heal:" ثبت می‌شدن؛ چون combat_handlers زودتر از
    # team_handlers ثبت می‌شد، نسخه‌ی team_handlers (heal:full و بقیه) هیچ‌وقت اجرا نمی‌شد
    # و /heal یه منوی ساده‌تر و ناهماهنگ با دکمه نشون می‌داد. cmd_heal/cb_heal این فایل
    # برای ارجاع نگه داشته شدن ولی دیگه ثبت نمی‌شن.
    dp.message.register(cmd_event,  Command("event"))
    dp.message.register(cmd_quests, Command("quests"))
    dp.message.register(cmd_wall,   Command("wall"))
    dp.message.register(cmd_rest,   Command("rest"))
    dp.message.register(cmd_rebirth, Command("rebirth"))
    dp.callback_query.register(cb_rebirth_go, F.data == "rebirth_go")
    dp.callback_query.register(cb_rebirth_cancel, F.data == "rebirth_cancel")
    dp.callback_query.register(cb_wall_challenge, F.data.startswith("wallch:"))

    dp.callback_query.register(cb_atk_locked,  F.data == "atk:locked")
    dp.callback_query.register(cb_atk_cancel,  F.data == "atk:cancel")
    dp.callback_query.register(cb_atk_menu,    F.data == "atk:menu")
    dp.callback_query.register(cb_atk_select,  F.data.startswith("atk:") & ~F.data.in_({"atk:locked","atk:cancel","atk:menu"}))
    dp.callback_query.register(cb_atk_enemy,   F.data.startswith("atk_enemy:"))
    dp.callback_query.register(cb_atk_continue, F.data.startswith("atkc:"))
    dp.callback_query.register(cb_atk_flee,    F.data == "atk_flee")
    dp.callback_query.register(cb_set_stance,  F.data.startswith("stance:"))
    dp.callback_query.register(cb_atk_help,    F.data == "atk_help")
    dp.callback_query.register(cb_atk_stats,   F.data == "atk_stats")
