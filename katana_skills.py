# ============================================================
#  ASTRAL ABYSS RPG — Katana Skills System
#  (katana_skills.py)  —  فاز ۲ / بخش الف
# ============================================================
#
# فایل کاملاً جدید و مستقل. ۷ مهارت فعال + ۷ مهارت غیرفعال تعریف می‌کنه؛
# بازیکن حداکثر ۵ فعال + ۵ غیرفعال رو می‌تونه باز کنه (۱۰ اسلات جمعاً).
#
# باز کردن مهارت → با «نقطه‌ی مهارت» (هر ۵ سطح کاتانا = ۱ نقطه، مستقل از
# skill_tree.py که مال کاراکتره نه کاتانا).
# ارتقاء مهارت (سطح ۱→۲→۳) → با «شکستن مهر» (Seal Break): طلا + آیتم نادر
# «سنگ مهر» (seal_stone)، بدون نیاز به نقطه‌ی مهارتِ اضافه.
#
# ── ساختار ذخیره‌سازی (per-character) ──
#   player["katana_skills"] = {
#       "<character_name>": {
#           "active":  {"slash_wave": 2, "soul_drain": 1},   # skill_key -> level(1..3)
#           "passive": {"sharp_edge": 1, "blood_thirst": 3},
#           "cooldowns": {"slash_wave": 1720000000.0},        # skill_key -> epoch آخرین استفاده
#           "phoenix_used_this_battle": False,
#       }
#   }
#
# این فایل مستقیم save_player صدا نمی‌زنه.
# ============================================================

import random
import time

# ────────────────────────────────────────────────────────────
# ۱) مهارت‌های فعال (۷ تا، هر کدوم کول‌داون مخصوص خودش)
# ────────────────────────────────────────────────────────────

ACTIVE_SKILLS = {
    "slash_wave":      {"name": "موج برش",              "emoji": "🌊", "cooldown": 60,
                         "desc": "آسیب به همه‌ی دشمنان", "kind": "aoe"},
    "shadow_step":     {"name": "گام سایه",              "emoji": "🌑", "cooldown": 90,
                         "desc": "فرار کامل از ۱ حمله‌ی دشمن", "kind": "dodge_next"},
    "soul_drain":      {"name": "مکش روح",               "emoji": "🩸", "cooldown": 120,
                         "desc": "۳۰٪ لایف‌استیل برای ۳ ضربه‌ی بعدی", "kind": "lifesteal_boost"},
    "elemental_fury":  {"name": "خشم عنصری",             "emoji": "🔥", "cooldown": 150,
                         "desc": "ضعف عنصری ۵۰٪ قوی‌تر", "kind": "elem_boost"},
    "void_strike":     {"name": "ضربه‌ی خلأ",            "emoji": "🌌", "cooldown": 180,
                         "desc": "نادیده گرفتن ۵۰٪ دفاع دشمن", "kind": "defense_ignore"},
    "time_warp":       {"name": "پیچش زمان",             "emoji": "⏳", "cooldown": 200,
                         "desc": "۲ ضربه‌ی پشت‌سرهم", "kind": "double_hit"},
    "phoenix_rebirth": {"name": "تولد دوباره‌ی ققنوس",   "emoji": "🐦‍🔥", "cooldown": 300,
                         "desc": "با مرگ، ۳۰٪ HP برمی‌گردی (یک‌بار در هر نبرد)", "kind": "revive",
                         "once_per_battle": True},
}
ACTIVE_SKILL_KEYS = list(ACTIVE_SKILLS.keys())
MAX_ACTIVE_SLOTS = 5

# ضریب قدرت/کاهش کول‌داون بر اساس سطح مهر (۱..۳)
_SEAL_POWER_MULT = {1: 1.0, 2: 1.3, 3: 1.6}
_SEAL_CD_MULT = {1: 1.0, 2: 0.9, 3: 0.8}
SEAL_MAX_LEVEL = 3

_ACTIVE_BASE_VALUE = {
    "slash_wave": 1.0,          # ضریب دمیج AOE نسبت به ضربه‌ی اصلی
    "shadow_step": None,        # بولین، مقیاس‌پذیر نیست
    "soul_drain": 0.30,
    "elemental_fury": 0.50,
    "void_strike": 0.50,
    "time_warp": None,          # بولین
    "phoenix_rebirth": 0.30,
}

BASE_PROC_CHANCE = 0.10  # شانس پایه‌ی فعال‌سازی خودکار در هر ضربه (وقتی مهارت آماده باشه)


def get_active_skill_effect(skill_key: str, level: int) -> dict:
    """اثر مقیاس‌شده‌ی یه مهارت فعال در سطح مهرِ مشخص + کول‌داون موثرش."""
    info = ACTIVE_SKILLS[skill_key]
    mult = _SEAL_POWER_MULT.get(level, 1.0)
    cd_mult = _SEAL_CD_MULT.get(level, 1.0)
    base_val = _ACTIVE_BASE_VALUE[skill_key]
    effect = {"kind": info["kind"], "cooldown": info["cooldown"] * cd_mult}
    if base_val is not None:
        effect["value"] = round(base_val * mult, 3)
    return effect


# ────────────────────────────────────────────────────────────
# ۲) مهارت‌های غیرفعال (۷ تا، همیشه فعال)
# ────────────────────────────────────────────────────────────

PASSIVE_SKILLS = {
    "sharp_edge":    {"name": "تیغه‌ی تیز",   "emoji": "🗡️", "desc": "+۵٪ دمیج دائمی",       "field": "dmg_mult_flat", "base": 0.05},
    "light_foot":    {"name": "پای سبک",      "emoji": "🍃", "desc": "+۱۰٪ سرعت حمله",       "field": "atk_speed_mult", "base": 0.10},
    "eagle_eye":     {"name": "چشم عقاب",     "emoji": "🦅", "desc": "+۱۰٪ کریت",            "field": "crit", "base": 0.10},
    "iron_will":     {"name": "اراده‌ی آهنین", "emoji": "🛡️", "desc": "۱۰٪ مقاومت اثرات منفی", "field": "status_resist", "base": 0.10},
    "blood_thirst":  {"name": "خون‌خواهی",    "emoji": "💉", "desc": "هر کشته +۵٪ HP بازیابی", "field": "hp_on_kill_pct", "base": 0.05},
    "shadow_cloak":  {"name": "شنل سایه",     "emoji": "👤", "desc": "۱۵٪ شانس فرار از حمله", "field": "dodge", "base": 0.15},
    "soul_bond":     {"name": "پیوند روح",    "emoji": "💜", "desc": "+۱۰٪ لایف‌استیل دائمی", "field": "lifesteal", "base": 0.10},
}
PASSIVE_SKILL_KEYS = list(PASSIVE_SKILLS.keys())
MAX_PASSIVE_SLOTS = 5

SEAL_STONE_MATERIAL = "seal_stone"
MATERIALS_INFO = {
    "seal_stone": {"emoji": "🔱", "name_fa": "سنگ مهر", "rarity": "legendary"},
}


def get_passive_skill_value(skill_key: str, level: int) -> float:
    info = PASSIVE_SKILLS[skill_key]
    return round(info["base"] * _SEAL_POWER_MULT.get(level, 1.0), 4)


# ────────────────────────────────────────────────────────────
# ۳) نقاط مهارت
# ────────────────────────────────────────────────────────────

def skill_points_total(katana_level: int) -> int:
    return katana_level // 5


def skill_points_spent(entry: dict) -> int:
    return len(entry.get("active", {})) + len(entry.get("passive", {}))


def skill_points_available(entry: dict, katana_level: int) -> int:
    return max(0, skill_points_total(katana_level) - skill_points_spent(entry))


# ────────────────────────────────────────────────────────────
# ۴) API اصلی
# ────────────────────────────────────────────────────────────

def get_skills(player: dict, character_name: str) -> dict:
    store = player.setdefault("katana_skills", {})
    entry = store.get(character_name)
    if entry is None:
        entry = {"active": {}, "passive": {}, "cooldowns": {}, "phoenix_used_this_battle": False}
        store[character_name] = entry
    return entry


def unlock_skill(player: dict, character_name: str, skill_key: str, kind: str) -> dict:
    """kind: 'active' | 'passive'"""
    entry = get_skills(player, character_name)
    katana_level = player.get("katana_level", 1)
    pool = ACTIVE_SKILLS if kind == "active" else PASSIVE_SKILLS
    slot_cap = MAX_ACTIVE_SLOTS if kind == "active" else MAX_PASSIVE_SLOTS
    bucket = entry[kind]

    if skill_key not in pool:
        return {"success": False, "message": "مهارت نامعتبره."}
    if skill_key in bucket:
        return {"success": False, "message": f"{pool[skill_key]['name']} از قبل باز شده."}
    if len(bucket) >= slot_cap:
        return {"success": False, "message": f"همه‌ی {slot_cap} اسلاتِ مهارت‌های {kind} پره."}
    if skill_points_available(entry, katana_level) < 1:
        return {"success": False, "message": "نقطه‌ی مهارت کافی نداری (هر ۵ سطحِ کاتانا = ۱ نقطه)."}

    bucket[skill_key] = 1
    return {"success": True, "message": f"✅ مهارت **{pool[skill_key]['name']}** باز شد!"}


def seal_break_cost(target_level: int) -> tuple[int, int]:
    """(gold, qty seal_stone) برای رسیدن به target_level (۲ یا ۳)."""
    gold = int(4000 * (target_level ** 2.1))
    qty = target_level * 2
    return gold, qty


def seal_break(player: dict, character_name: str, skill_key: str, kind: str,
               gold: int, inventory: dict) -> dict:
    entry = get_skills(player, character_name)
    bucket = entry[kind]
    if skill_key not in bucket:
        return {"success": False, "message": "اول باید این مهارت رو باز کنی."}
    cur = bucket[skill_key]
    if cur >= SEAL_MAX_LEVEL:
        return {"success": False, "message": "این مهارت به حداکثر سطح مهر رسیده (۳/۳)."}

    target = cur + 1
    cost, qty = seal_break_cost(target)
    if gold < cost:
        return {"success": False, "message": f"💰 طلای کافی نداری! به {cost:,} Zen نیاز داری."}
    if inventory.get(SEAL_STONE_MATERIAL, 0) < qty:
        info = MATERIALS_INFO[SEAL_STONE_MATERIAL]
        return {"success": False,
                "message": f"📦 {info['emoji']} {info['name_fa']} کافی نداری! ({inventory.get(SEAL_STONE_MATERIAL,0)}/{qty})"}

    bucket[skill_key] = target
    pool = ACTIVE_SKILLS if kind == "active" else PASSIVE_SKILLS
    return {"success": True, "gold_spent": cost, "material_spent": qty,
            "message": f"🔱 مهر شکسته شد! **{pool[skill_key]['name']}** حالا سطح {target}/{SEAL_MAX_LEVEL}‌ست."}


# ────────────────────────────────────────────────────────────
# ۵) بونوس غیرفعال جمع‌شده (برای ترکیب با combat)
# ────────────────────────────────────────────────────────────

def calc_skills_passive_bonus(player: dict, character_name: str) -> dict:
    entry = get_skills(player, character_name)
    out = {"dmg_mult_flat": 0.0, "atk_speed_mult": 0.0, "crit": 0.0, "status_resist": 0.0,
           "hp_on_kill_pct": 0.0, "dodge": 0.0, "lifesteal": 0.0}
    for skill_key, level in entry.get("passive", {}).items():
        info = PASSIVE_SKILLS.get(skill_key)
        if not info:
            continue
        val = get_passive_skill_value(skill_key, level)
        out[info["field"]] = out.get(info["field"], 0.0) + val
    return out


# ────────────────────────────────────────────────────────────
# ۶) کول‌داون و فعال‌سازی خودکار مهارت‌های فعال در نبرد
# ────────────────────────────────────────────────────────────

def _effective_cooldown(skill_key: str, level: int, speed_cd_reduction: float = 0.0) -> float:
    eff = get_active_skill_effect(skill_key, level)
    return max(5.0, eff["cooldown"] - speed_cd_reduction)


def skill_ready(entry: dict, skill_key: str, level: int, speed_cd_reduction: float = 0.0) -> bool:
    if skill_key == "phoenix_rebirth" and entry.get("phoenix_used_this_battle"):
        return False
    last = entry.get("cooldowns", {}).get(skill_key, 0)
    cd = _effective_cooldown(skill_key, level, speed_cd_reduction)
    return (time.time() - last) >= cd


def reset_battle_flags(player: dict, character_name: str):
    """در ابتدای هر نبرد جدید صدا زده بشه (توسط هندلر) — فقط پرچم یک‌بار-در-نبرد رو ریست می‌کنه."""
    entry = get_skills(player, character_name)
    entry["phoenix_used_this_battle"] = False


def maybe_trigger_active_skill(player: dict, character_name: str,
                                extra_chance: float = 0.0,
                                speed_cd_reduction: float = 0.0) -> dict | None:
    """با شانسِ BASE_PROC_CHANCE + extra_chance، یکی از مهارت‌های فعالِ آماده رو رندوم
    شلیک می‌کنه. اگه هیچی آماده نبود یا شانس نیفتاد → None."""
    entry = get_skills(player, character_name)
    active = entry.get("active", {})
    if not active:
        return None

    ready = [k for k, lvl in active.items()
             if skill_ready(entry, k, lvl, speed_cd_reduction) and k != "phoenix_rebirth"]
    if not ready:
        return None

    if random.random() >= (BASE_PROC_CHANCE + extra_chance):
        return None

    skill_key = random.choice(ready)
    level = active[skill_key]
    effect = get_active_skill_effect(skill_key, level)
    entry.setdefault("cooldowns", {})[skill_key] = time.time()
    return {"key": skill_key, "level": level, "name": ACTIVE_SKILLS[skill_key]["name"],
            "emoji": ACTIVE_SKILLS[skill_key]["emoji"], "effect": effect}


def try_phoenix_rebirth(player: dict, character_name: str) -> dict | None:
    """صدا زده می‌شه وقتی HP بازیکن به ≤۰ می‌رسه. اگه مهارت باز و آماده باشه، جلوی مرگ رو می‌گیره."""
    entry = get_skills(player, character_name)
    active = entry.get("active", {})
    if "phoenix_rebirth" not in active:
        return None
    if entry.get("phoenix_used_this_battle"):
        return None
    level = active["phoenix_rebirth"]
    effect = get_active_skill_effect("phoenix_rebirth", level)
    entry["phoenix_used_this_battle"] = True
    entry.setdefault("cooldowns", {})["phoenix_rebirth"] = time.time()
    max_hp = player.get("max_hp", 100)
    revive_hp = max(1, int(max_hp * effect["value"]))
    return {"revive_hp": revive_hp, "name": ACTIVE_SKILLS["phoenix_rebirth"]["name"]}


# ────────────────────────────────────────────────────────────
# ۷) نمایش
# ────────────────────────────────────────────────────────────

def display_skills(player: dict, character_name: str) -> str:
    entry = get_skills(player, character_name)
    katana_level = player.get("katana_level", 1)
    pts = skill_points_available(entry, katana_level)

    lines = ["🧬 **مهارت‌های کاتانا** 🧬", "", f"⭐ نقطه‌ی مهارتِ آزاد: {pts}", ""]

    lines.append(f"⚔️ **فعال ({len(entry['active'])}/{MAX_ACTIVE_SLOTS})**")
    if entry["active"]:
        for k, lvl in entry["active"].items():
            info = ACTIVE_SKILLS[k]
            ready = skill_ready(entry, k, lvl) if k != "phoenix_rebirth" else not entry.get("phoenix_used_this_battle")
            state = "🟢 آماده" if ready else "🔴 در کول‌داون"
            lines.append(f"   {info['emoji']} {info['name']} (مهر {lvl}/3) — {info['desc']} [{state}]")
    else:
        lines.append("   هنوز چیزی باز نشده.")
    lines.append("")

    lines.append(f"🛡️ **غیرفعال ({len(entry['passive'])}/{MAX_PASSIVE_SLOTS})**")
    if entry["passive"]:
        for k, lvl in entry["passive"].items():
            info = PASSIVE_SKILLS[k]
            val = get_passive_skill_value(k, lvl)
            lines.append(f"   {info['emoji']} {info['name']} (مهر {lvl}/3) — فعلی: {val*100:.1f}٪")
    else:
        lines.append("   هنوز چیزی باز نشده.")

    lines.append("")
    lines.append("📋 مهارت‌های فعال قابل باز شدن:")
    for k, info in ACTIVE_SKILLS.items():
        if k not in entry["active"]:
            lines.append(f"   {info['emoji']} {info['name']} (CD {info['cooldown']}s) — {info['desc']}")
    lines.append("📋 مهارت‌های غیرفعال قابل باز شدن:")
    for k, info in PASSIVE_SKILLS.items():
        if k not in entry["passive"]:
            lines.append(f"   {info['emoji']} {info['name']} — {info['desc']}")

    return "\n".join(lines)
