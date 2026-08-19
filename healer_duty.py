# ============================================================
#  ASTRAL ABYSS RPG — 🩺 نوبت‌دهی بیمارستان (Healer Duty Rounds)
#  (healer_duty.py) — منطقِ خالص، بدون UI
# ------------------------------------------------------------
#  «بیمارستان» (hospital_handlers.py) قبلاً فقط یه شاپِ خودـ‌درمانی
#  بود — درمانگر خودش رو درمان می‌کرد، نه بیمارهای دیگه رو، و هیچ XPی
#  نمی‌گرفت. این ماژول همون حلقه‌ای که بازیکن ازش می‌خواست رو می‌سازه:
#  هر نوبت یه بیمارِ NPC با یه بیماریِ رندوم میاد، درمانگر با فیض
#  درمانش می‌کنه → Zen + XP + (اگه بیمار مرده‌ی متحرک بود) undead_purged.
#
#  علاوه‌براین، یه بخشِ واقعاً بین‌بازیکنی هم داره: اگه بازیکنِ واقعیِ
#  دیگه‌ای «زخمِ دائمی» (injury) داشته باشه (از combat_handlers.py)،
#  درمانگر می‌تونه با هزینه‌ی فیضِ خودش، رایگان (یا خیلی ارزون‌تر از
#  بیمارستانِ معمولی) درمانش کنه — و این واقعاً از پروفایلِ همون
#  بازیکن injury رو پاک می‌کنه، نه صرفاً فلیور.
# ============================================================
from __future__ import annotations

import random
import time

from database import get_player, save_player
import class_activity_engine as cae

ACTIVITY_KEY  = "healer_duty"
MAX_ACTIONS   = 5
BATCH_RESET   = 600
DAILY_MAX     = 40
DAILY_RESET   = 86400

FAITH_COST_PER_PATIENT = 10

# ─── انواعِ بیمار ────────────────────────────────────────────
AILMENTS = [
    {"key": "cut",     "name": "🩸 بریدگیِ سطحی",        "tier": 1, "undead": False},
    {"key": "fever",   "name": "🤒 تبِ شدید",             "tier": 1, "undead": False},
    {"key": "poison",  "name": "☠️ مسمومیت",              "tier": 2, "undead": False},
    {"key": "fracture","name": "🦴 شکستگیِ استخوان",       "tier": 2, "undead": False},
    {"key": "curse",   "name": "👻 نفرینِ خفیف",          "tier": 3, "undead": False},
    {"key": "undead",  "name": "🧟 گازِ مرده‌ی متحرک",     "tier": 3, "undead": True},
]

PATIENT_NAMES = [
    "دهقانِ پیر", "سربازِ زخمی", "کودکِ گمشده", "زائرِ خسته", "کاروانِ‌سالارِ صدمه‌دیده",
    "کماندارِ جوان", "بازرگانِ سیاح", "جنگجوی نامی", "راهبِ سرگردان",
]

TIER_BASE = {
    1: {"zen": (40, 90),  "xp": (14, 26)},
    2: {"zen": (90, 200), "xp": (24, 44)},
    3: {"zen": (200, 420),"xp": (40, 75)},
}


def get_state(uid: int) -> dict:
    return cae.get_state(ACTIVITY_KEY, uid, max_actions=MAX_ACTIONS, batch_reset=BATCH_RESET, daily_reset=DAILY_RESET)


def roll_patient(player: dict) -> dict:
    ailment = random.choice(AILMENTS)
    name = random.choice(PATIENT_NAMES)
    return {"ailment": ailment, "patient_name": name, "rolled_at": time.time()}


def treat_patient(uid: int, player: dict, patient: dict) -> dict:
    csd = player.setdefault("class_system_data", {})
    if csd.get("faith", 0) < FAITH_COST_PER_PATIENT:
        return {"ok": False, "msg": f"❌ فیضِ کافی نداری! ({csd.get('faith',0)}/{FAITH_COST_PER_PATIENT}) — کمی صبر کن تا ریجن بشه."}

    csd["faith"] -= FAITH_COST_PER_PATIENT
    ailment = patient["ailment"]
    tier = ailment["tier"]
    base = TIER_BASE[tier]

    hp_bonus = csd.get("hp_regen_bonus_pct", 10) / 100
    success_chance = min(0.97, 0.75 + hp_bonus)
    success = random.random() < success_chance

    zmin, zmax = base["zen"]
    xmin, xmax = base["xp"]
    zen_mult = 1.0 if success else 0.4
    xp_mult = 1.0 if success else 0.5

    base_zen = random.randint(zmin, zmax)
    base_xp = random.randint(xmin, xmax)

    result = cae.grant_rewards(player, uid, base_zen=base_zen, base_xp=base_xp,
                                source="healer_duty", zen_mult=zen_mult, xp_mult=xp_mult)

    purged = False
    if ailment["undead"] and success:
        csd["undead_purged"] = csd.get("undead_purged", 0) + 1
        purged = True

    return {"ok": True, "success": success, "patient": patient, "purged": purged, **result}


# ─── درمانِ یه بازیکنِ واقعیِ زخمی ────────────────────────────────
INJURY_LABELS = {
    "old_wound": "🩸 زخمِ کهنه", "fracture": "🦴 شکستگی", "curse_perm": "☠️ نفرینِ دائمی",
}
REAL_PLAYER_FAITH_COST = 25


def find_injured_player(exclude_uid: int) -> dict | None:
    return cae.pick_random_other_player(exclude_uid, require_field="injuries")


def treat_real_player(uid: int, player: dict, target_doc: dict) -> dict:
    csd = player.setdefault("class_system_data", {})
    if csd.get("faith", 0) < REAL_PLAYER_FAITH_COST:
        return {"ok": False, "msg": f"❌ فیضِ کافی نداری! ({csd.get('faith',0)}/{REAL_PLAYER_FAITH_COST})"}

    target_uid = target_doc.get("_uid")
    target_player = get_player(target_uid) if target_uid else None
    if not target_player or not target_player.get("injuries"):
        return {"ok": False, "msg": "❌ این بیمار دیگه زخمی نداره — یکی دیگه رو امتحان کن."}

    injuries = target_player.get("injuries", [])
    cured = injuries.pop(random.randrange(len(injuries)))
    target_player["injuries"] = injuries
    save_player(target_uid, target_player)

    csd["faith"] -= REAL_PLAYER_FAITH_COST
    result = cae.grant_rewards(player, uid, base_zen=250, base_xp=70, source="healer_duty_real")
    csd["undead_purged"] = csd.get("undead_purged", 0)  # no-op, keeps schema consistent

    return {
        "ok": True, "target_name": target_player.get("name", "یه بازیکن"),
        "cured": INJURY_LABELS.get(cured, cured), **result,
    }
