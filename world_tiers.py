# ============================================================
#  ASTRAL ABYSS — World Tier & Ascension System
# ------------------------------------------------------------
#  Level به تنهایی کافی نیست. برای رفتن به تیر بالاتر باید هم لول
#  کافی داشته باشی و هم Ascension Trial قبلی رو رد کرده باشی.
#
#  این ماژول با economy.MAPS_DATA (که از قبل هست) هماهنگه — هر
#  مپ فعلی به یه World Tier نسبت داده شده تا هیچ مپی بی‌صاحب نمونه.
# ============================================================
import time

# ─── World Tiers ────────────────────────────────────────────────
WORLD_TIERS = {
    1: {"name": "Tier 1 — آغاز",        "level_range": (1, 20),   "ascension_required": None},
    2: {"name": "Tier 2 — بیداری",      "level_range": (20, 40),  "ascension_required": "trial_1"},
    3: {"name": "Tier 3 — آشوب",        "level_range": (40, 70),  "ascension_required": "trial_2"},
    4: {"name": "Tier 4 — سقوط",        "level_range": (70, 100), "ascension_required": "trial_3"},
    5: {"name": "Tier 5 — استعلا",      "level_range": (100, 130),"ascension_required": "trial_4"},
    6: {"name": "Tier 6 — ابدیت",       "level_range": (130, 150),"ascension_required": "trial_5"},
}

# ─── نگاشت مپ‌های فعلی به World Tier ─────────────────────────────
# بر اساس زون/تیر فعلیِ economy.MAPS_DATA (safe/common پایین‌تر، danger/epic بالاتر)
MAP_WORLD_TIER = {
    "Verdant Vale":          1,
    "Sands of Eternity":     1,
    "Azure Tides Empire":    2,
    "Holy Luminarchy":       2,
    "Clockwork Depths":      2,
    "The Sunken City":       3,
    "Ruins of Orion-7":      3,
    "Frostheim":             3,
    "Celestial Spire":       4,
    "Stormward Archipelago": 4,
    "Emberhollow":           4,
    "Dreadgate Citadel":     5,
    "Voidbreak Wastes":      5,
    "Dragonnest Peaks":      6,
    "Abyssal Black Market":  1,   # بازار همیشه در دسترسه
    "Throne of Oblivion":    6,   # 🆕 مپِ جدید — به‌شدت سخت، هم‌سطحِ سخت‌ترین تیر بازی
}

def get_map_tier(map_name: str) -> int:
    return MAP_WORLD_TIER.get(map_name, 1)

# ─── Ascension Trials ────────────────────────────────────────────
ASCENSION_TRIALS = {
    "trial_1": {"name": "🌀 آزمون بیداری",   "min_level": 20,  "retry_cooldown": 3600,   "fail_hp_penalty": 0.3},
    "trial_2": {"name": "🔥 آزمون آشوب",     "min_level": 40,  "retry_cooldown": 7200,   "fail_hp_penalty": 0.35},
    "trial_3": {"name": "🌑 آزمون سقوط",     "min_level": 70,  "retry_cooldown": 14400,  "fail_hp_penalty": 0.4},
    "trial_4": {"name": "✨ آزمون استعلا",   "min_level": 100, "retry_cooldown": 28800,  "fail_hp_penalty": 0.45},
    "trial_5": {"name": "👑 آزمون ابدیت",    "min_level": 130, "retry_cooldown": 43200,  "fail_hp_penalty": 0.5},
}

TRIAL_ORDER = ["trial_1", "trial_2", "trial_3", "trial_4", "trial_5"]

def get_player_ascensions(player: dict) -> set:
    return set(player.get("ascensions_passed", []))

def get_current_world_tier(player: dict) -> int:
    """بالاترین تیری که بازیکن الان واقعاً واردش می‌تونه بشه (لول + ascension)."""
    level = player.get("level", 1)
    passed = get_player_ascensions(player)
    reached = 1
    for tier_num in sorted(WORLD_TIERS.keys()):
        tdata = WORLD_TIERS[tier_num]
        lo, hi = tdata["level_range"]
        req = tdata["ascension_required"]
        if level < lo:
            break
        if req is not None and req not in passed:
            break
        reached = tier_num
    return reached

def can_access_tier(player: dict, tier_num: int) -> tuple[bool, str]:
    """(آیا اجازه داره, دلیل رد در صورت نه)"""
    tdata = WORLD_TIERS.get(tier_num)
    if not tdata:
        return False, "❌ Tier نامعتبر."
    level = player.get("level", 1)
    lo, hi = tdata["level_range"]
    if level < lo:
        return False, f"❌ برای {tdata['name']} حداقل باید Lv.{lo} باشی (الان Lv.{level})."
    req = tdata["ascension_required"]
    if req and req not in get_player_ascensions(player):
        trial_name = ASCENSION_TRIALS[req]["name"]
        return False, f"❌ اول باید **{trial_name}** رو رد کنی تا وارد {tdata['name']} بشی."
    return True, ""

def can_access_map(player: dict, map_name: str) -> tuple[bool, str]:
    tier_num = get_map_tier(map_name)
    return can_access_tier(player, tier_num)

def next_trial_for_player(player: dict) -> str | None:
    """اسم اولین Trial ای که بازیکن هنوز رد نکرده و لولش کافیه."""
    passed = get_player_ascensions(player)
    level = player.get("level", 1)
    for trial_id in TRIAL_ORDER:
        if trial_id in passed:
            continue
        if level >= ASCENSION_TRIALS[trial_id]["min_level"]:
            return trial_id
        return None  # لول کافی نیست، بقیه هم که بالاترن
    return None  # همه رد شده

def can_attempt_trial(player: dict, trial_id: str) -> tuple[bool, str]:
    trial = ASCENSION_TRIALS.get(trial_id)
    if not trial:
        return False, "❌ Trial نامعتبر."
    if trial_id in get_player_ascensions(player):
        return False, "✅ این آزمون رو قبلاً رد کردی."
    if player.get("level", 1) < trial["min_level"]:
        return False, f"❌ حداقل لول لازم: {trial['min_level']}"
    cooldowns = player.get("ascension_cooldowns", {})
    until = cooldowns.get(trial_id, 0)
    if time.time() < until:
        remain = int(until - time.time())
        return False, f"⏳ باید {remain//60} دقیقه دیگه صبر کنی."
    return True, ""

def resolve_trial_attempt(player: dict, trial_id: str, success: bool) -> dict:
    """نتیجه‌ی تلاش برای رد کردن Trial رو روی پروفایل اعمال می‌کنه.
    فراخوان (handler) مسئوله که success رو از منطق نبرد/مکانیک واقعی محاسبه کنه —
    این تابع فقط عواقب/جوایز رو اعمال می‌کنه."""
    trial = ASCENSION_TRIALS[trial_id]
    result = {"success": success, "trial": trial_id}

    if success:
        passed = player.setdefault("ascensions_passed", [])
        if trial_id not in passed:
            passed.append(trial_id)
        player["max_hp"] = player.get("max_hp", 100) + 30
        from skill_tree import effective_max_hp
        player["hp"] = effective_max_hp(player)  # باگ‌فیکس: باف max_hp_pct هم لحاظ بشه
        result["reward"] = "🎉 +30 Max HP دائمی، دسترسی به تیر بعدی باز شد!"
    else:
        cooldowns = player.setdefault("ascension_cooldowns", {})
        cooldowns[trial_id] = time.time() + trial["retry_cooldown"]
        penalty_hp = int(player.get("max_hp", 100) * trial["fail_hp_penalty"])
        player["hp"] = max(1, player.get("hp", 100) - penalty_hp)
        result["reward"] = f"💀 شکست خوردی! {penalty_hp} HP از دست دادی. باید {trial['retry_cooldown']//60} دقیقه صبر کنی."

    return result

def format_tier_status(player: dict) -> str:
    current = get_current_world_tier(player)
    lines = [f"🌍 **World Tier فعلی: {WORLD_TIERS[current]['name']}**\n"]
    for tier_num, tdata in sorted(WORLD_TIERS.items()):
        lo, hi = tdata["level_range"]
        ok, _ = can_access_tier(player, tier_num)
        mark = "✅" if ok else ("🔒" if tier_num != current + 1 else "🔸")
        lines.append(f"{mark} {tdata['name']} (Lv.{lo}-{hi})")
    nxt = next_trial_for_player(player)
    if nxt:
        lines.append(f"\n⚡ آزمون بعدی: **{ASCENSION_TRIALS[nxt]['name']}** — `/ascend` رو بزن!")
    return "\n".join(lines)
