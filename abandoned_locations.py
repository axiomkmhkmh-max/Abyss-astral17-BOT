# ============================================================
#  ASTRAL ABYSS — Abandoned Location Engines (مکانیک کاملاً جدید)
# ------------------------------------------------------------
#  اسم هر لوکیشن (economy.MAP_LOCATIONS) به یکی از ۴ تیپ نگاشت شده
#  (economy.classify_location_type). این فایل برای هرکدوم یه
#  موتورِ عمیقِ مستقل داره:
#
#   🏚️ house    → visit_house()    لوت سریع کم‌ریسک + شانس تله
#   🏥 hospital → visit_hospital() آیتم دارویی نادر + شانس «بیماری»
#   🏦 bank     → visit_bank()     بیشترین Zen خام، نیازمند کلید، شانس آلارم
#   🏢 building → run_building_*() چندطبقه، push-your-luck (خارج شو یا ادامه بده)
#
#  house/hospital/bank همگی سینک‌ان و مستقیم قبل از رفتن سراغِ
#  مبارزه‌ی معمولیِ نقشه (mob_combat.start_encounter) صدا زده می‌شن؛
#  building یه فلوی جداگانه‌ی چندمرحله‌ایه با کیبورد اینلاینِ خودش.
# ============================================================
import random
import time

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from economy import roll_loot
from logger import log_sync

# ═══════════════════════ 🏚️ خونه‌ی متروکه ═══════════════════
HOUSE_TRAP_CHANCE   = 0.18
HOUSE_TRAP_DMG_PCT  = (0.05, 0.09)
HOUSE_STASH_CHANCE  = 0.32
HOUSE_STASH_ZEN     = (40, 220)


def visit_house(player: dict, map_name: str) -> dict:
    lines = []
    if random.random() < HOUSE_TRAP_CHANCE:
        pct = random.uniform(*HOUSE_TRAP_DMG_PCT)
        dmg = max(1, int(player.get("max_hp", 100) * pct))
        player["hp"] = max(0, player.get("hp", 100) - dmg)
        lines.append(f"🪤 **تله!** یه تخته‌ی کف اتاق شکست زیر پات — {dmg} دمیج خوردی.")
    if random.random() < HOUSE_STASH_CHANCE:
        zen = random.randint(*HOUSE_STASH_ZEN)
        player["zen"] = player.get("zen", 0) + zen
        lines.append(f"💰 یه ذخیره‌ی کوچیکِ فراموش‌شده پیدا کردی: **+{zen:,} Zen**")
    if not lines:
        lines.append("🏚️ خونه خالیه، چیز خاصی پیدا نکردی — ولی حداقل بی‌خطر بود.")
    return {"text": "\n".join(lines)}


# ═══════════════════════ 🏥 بیمارستان متروکه ═════════════════
HOSPITAL_MED_CHANCE  = 0.24
HOSPITAL_SICK_CHANCE = 0.22
SICKNESS_DURATION    = 20 * 60   # ۲۰ دقیقه‌ی واقعی
SICKNESS_REWARD_MULT = 0.85      # -۱۵٪ Zen/XP تا وقتی بیماری فعاله

MED_ITEMS = [
    {"name": "سرم شفابخش",     "emoji": "💉", "kind": "heal_potion", "heal_pct": 0.35, "sell": 180},
    {"name": "قرص ضدسم",       "emoji": "💊", "kind": "cure_potion", "sell": 140},
    {"name": "باند زخم‌بندی",   "emoji": "🩹", "kind": "heal_potion", "heal_pct": 0.15, "sell": 60},
    {"name": "ماسک محافظ",     "emoji": "😷", "kind": "protection",  "sell": 220},
]


def _has_protection(player: dict) -> bool:
    inv = player.get("inventory", [])
    return any(("ماسک" in i.get("name", "")) or ("پادزهر" in i.get("name", "")) for i in inv)


def visit_hospital(player: dict, map_name: str) -> dict:
    lines = []
    if random.random() < HOSPITAL_MED_CHANCE:
        item = dict(random.choice(MED_ITEMS))
        player.setdefault("inventory", []).append(item)
        lines.append(f"{item['emoji']} یه آیتمِ دارویی نادر پیدا کردی: **{item['name']}**")

    if random.random() < HOSPITAL_SICK_CHANCE:
        if _has_protection(player):
            lines.append("😷 هوای اینجا آلوده‌ست ولی چون محافظت داشتی، سالم موندی.")
        else:
            player["sickness_until"] = time.time() + SICKNESS_DURATION
            lines.append(
                "🤢 **بیمار شدی!** تا ۲۰ دقیقه‌ی دیگه Zen/XP کمتری از نبرد می‌گیری.\n"
                "💡 دفعه‌ی بعد با یه 😷ماسک محافظ یا آیتمِ «پادزهر» وارد شو تا مصون بمونی."
            )

    if not lines:
        lines.append("🏥 راهروهای خالی و ساکت... چیزی گیرت نیومد.")
    return {"text": "\n".join(lines)}


def sickness_active(player: dict) -> bool:
    return time.time() < player.get("sickness_until", 0)


def sickness_mult(player: dict) -> float:
    """هوکِ عمومی: تو mob_combat.py و combat_handlers.py صدا زده می‌شه تا
    پاداشِ Zen/XP رو وقتی بیماری فعاله کم کنه."""
    return SICKNESS_REWARD_MULT if sickness_active(player) else 1.0


# ═══════════════════════ 🏦 بانک متروکه ══════════════════════
# ابزارِ لازم رو از همون سیستمِ کلیدهای loot_engine.py قرض می‌گیریم
# (golden_key / void_key) — چیزی تکراری تعریف نمی‌کنیم.
BANK_REQUIRED_KEYS   = ("golden_key", "void_key")
BANK_BASE_ZEN         = (1200, 4200)
BANK_ALARM_WITH_KEY   = 0.22
BANK_ALARM_NO_KEY     = 0.48
BANK_NOKEY_SUCCESS    = 0.30
BANK_NOKEY_ZEN        = (150, 500)
BANK_COOLDOWN_SEC     = 3600     # هر نقشه هر ۱ ساعت یه‌بار (ضدفارم)


def _find_key(player: dict):
    inv = player.get("inventory", [])
    for i, it in enumerate(inv):
        if it.get("type") == "key" and it.get("key_id") in BANK_REQUIRED_KEYS:
            return i, it
    return None, None


def visit_bank(player: dict, map_name: str) -> dict:
    now = time.time()
    cds = player.setdefault("bank_heist_cooldowns", {})
    remaining = cds.get(map_name, 0) - now
    if remaining > 0:
        m = max(1, int(remaining // 60))
        return {"text": f"🏦 گاوصندوق‌های این بانک هنوز خالیه از دفعه‌ی قبل — {m} دقیقه‌ی دیگه دوباره سر بزن.",
                "spawn_alarm": False}

    idx, key_item = _find_key(player)

    if key_item is not None:
        if random.random() < BANK_ALARM_WITH_KEY:
            player["inventory"].pop(idx)
            cds[map_name] = now + BANK_COOLDOWN_SEC
            return {
                "text": f"🚨 **آلارم فعال شد!** {key_item['emoji']} {key_item['name']} تو قفل شکست "
                        f"و یه نگهبانِ امنیتیِ سطح‌بالا سررسید!",
                "spawn_alarm": True,
            }
        zen = random.randint(*BANK_BASE_ZEN)
        player["inventory"].pop(idx)
        player["zen"] = player.get("zen", 0) + zen
        cds[map_name] = now + BANK_COOLDOWN_SEC
        return {
            "text": f"🔓 با {key_item['emoji']} {key_item['name']} گاوصندوقِ اصلی رو باز کردی! **+{zen:,} Zen**",
            "spawn_alarm": False,
        }

    # بدون کلید — تلاش برای دستکاریِ قفل
    if random.random() < BANK_ALARM_NO_KEY:
        cds[map_name] = now + BANK_COOLDOWN_SEC
        return {"text": "🚨 **موقع دستکاریِ قفل، آلارم زدی!** یه نگهبانِ امنیتی سررسید.", "spawn_alarm": True}
    if random.random() < BANK_NOKEY_SUCCESS:
        zen = random.randint(*BANK_NOKEY_ZEN)
        player["zen"] = player.get("zen", 0) + zen
        cds[map_name] = now + BANK_COOLDOWN_SEC
        return {
            "text": f"🔧 بدون ابزار فقط تونستی یه گاوصندوقِ کوچیک رو باز کنی. **+{zen:,} Zen**\n"
                    f"💡 با یه 🔐کلید طلایی یا 🕳️کلید خلأ (از صندوق‌ها/بازار سیاه) دفعه‌ی بعد کامل خالیش کن.",
            "spawn_alarm": False,
        }
    return {
        "text": "🔒 بدون کلید نتونستی قفلِ اصلی رو باز کنی. یه 🔐کلید طلایی یا 🕳️کلید خلأ لازم داری.",
        "spawn_alarm": False,
    }


# ═══════════════════════ 🏢 ساختمون متروکه (push-your-luck) ═
BUILDING_MAX_FLOOR  = 6
BUILDING_BASE_RISK  = 0.10
BUILDING_RISK_STEP  = 0.07
BUILDING_DMG_PCT    = (0.06, 0.16)
BUILDING_ZEN_PER_FLOOR = (25, 75)

_building_runs: dict[int, dict] = {}   # uid -> {"map":..., "floor":0, "zen":0, "items":[]}


def _floor_risk(floor: int) -> float:
    return min(0.85, BUILDING_BASE_RISK + (floor - 1) * BUILDING_RISK_STEP)


def _advance_floor(uid: int, player: dict) -> dict:
    run = _building_runs.get(uid)
    if not run:
        return {"text": "❌ سفری در این ساختمون در جریان نیست.", "busted": True, "can_continue": False}

    run["floor"] += 1
    floor = run["floor"]
    risk = _floor_risk(floor)

    loot = roll_loot(run["map"], count=2, player_level=player.get("level", 1))
    run["items"].extend(loot)
    zen_found = random.randint(*BUILDING_ZEN_PER_FLOOR) * floor
    run["zen"] += zen_found

    lines = [f"🏢 **طبقه‌ی {floor}/{BUILDING_MAX_FLOOR}**"]
    for it in loot:
        lines.append(f"  {it.get('emoji','📦')} {it.get('name','آیتم')}")
    lines.append(f"💰 +{zen_found:,} Zen (تجمعیِ این سفر: {run['zen']:,})")

    busted = random.random() < risk
    if busted:
        pct = random.uniform(*BUILDING_DMG_PCT)
        dmg = max(1, int(player.get("max_hp", 100) * pct))
        player["hp"] = max(1, player.get("hp", 100) - dmg)
        lines.append(
            f"💥 **کف طبقه ریخت پایین!** {dmg} دمیج خوردی و با دست خالی فرار کردی — "
            f"همه‌ی غنایمِ این سفر ({run['zen']:,} Zen + {len(run['items'])} آیتم) از دست رفت."
        )
        _building_runs.pop(uid, None)
        return {"text": "\n".join(lines), "busted": True, "can_continue": False, "risk": risk, "floor": floor}

    can_continue = floor < BUILDING_MAX_FLOOR
    if not can_continue:
        lines.append("🏁 به آخرین طبقه رسیدی — دیگه بالاتر نمی‌شه رفت. الان خارج شو تا همه‌چی رو نگه داری!")
    else:
        lines.append(f"⚠️ ریسکِ طبقه‌ی بعد: **{int(_floor_risk(floor+1)*100)}٪**")
    return {"text": "\n".join(lines), "busted": False, "can_continue": can_continue, "risk": risk, "floor": floor}


def start_building_run(uid: int, player: dict, map_name: str) -> dict:
    _building_runs[uid] = {"map": map_name, "floor": 0, "zen": 0, "items": []}
    return _advance_floor(uid, player)


def _building_kb(can_continue: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_continue:
        rows.append([InlineKeyboardButton(text="⬆️ برو طبقه‌ی بالاتر (ریسک بیشتر)",
                                           callback_data="bld:continue", style=ButtonStyle.DANGER)])
    rows.append([InlineKeyboardButton(text="🚪 خارج شو با غنایم فعلی",
                                       callback_data="bld:leave", style=ButtonStyle.SUCCESS)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _cash_out(uid: int, player: dict) -> dict:
    run = _building_runs.pop(uid, None)
    if not run:
        return {"text": "❌ سفری در جریان نبود."}
    player["zen"] = player.get("zen", 0) + run["zen"]
    player.setdefault("inventory", []).extend(run["items"])
    return {
        "text": f"🚪 با **{run['zen']:,} Zen** و **{len(run['items'])} آیتم** سالم از ساختمون بیرون اومدی!",
    }


async def cb_building_continue(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    if uid not in _building_runs:
        await cb.answer("⏰ این سفر دیگه معتبر نیست!", show_alert=True)
        return
    res = _advance_floor(uid, player)
    await asave_player(uid, player)
    kb = _building_kb(res.get("can_continue", False))
    try:
        await cb.message.edit_text(res["text"], reply_markup=kb)
    except Exception:
        await cb.message.answer(res["text"], reply_markup=kb)
    await cb.answer("💥 بوم!" if res.get("busted") else "⬆️ طبقه‌ی جدید!")


async def cb_building_leave(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    res = _cash_out(uid, player)
    await asave_player(uid, player)
    log_sync(f"🏢 **BUILDING RUN CASHED OUT**\n👤 {cb.from_user.first_name} (`{uid}`)\n{res['text']}", "LOOT")
    try:
        await cb.message.edit_text(res["text"], reply_markup=None)
    except Exception:
        await cb.message.answer(res["text"])
    await cb.answer("🚪 خارج شدی!")


def register_abandoned_location_handlers(dp: Dispatcher, bot: Bot):
    dp.callback_query.register(cb_building_continue, F.data == "bld:continue")
    dp.callback_query.register(cb_building_leave, F.data == "bld:leave")


# ═══════════════════════ Dispatcher عمومی ════════════════════
def visit_location(player: dict, loc: dict, map_name: str) -> dict:
    """برای house/hospital/bank صدا زده می‌شه (سینک، قبل از رفتن سراغِ مبارزه‌ی معمولی)."""
    loc_type = loc.get("type", "building")
    if loc_type == "house":
        return visit_house(player, map_name)
    if loc_type == "hospital":
        return visit_hospital(player, map_name)
    if loc_type == "bank":
        return visit_bank(player, map_name)
    return {"text": ""}
