# ============================================================
#  ASTRAL ABYSS RPG — همراه (Pet / Companion) 🐾
# ------------------------------------------------------------
#  یه لایه‌ی جدیدِ progression: بازیکن‌ها می‌تونن همراه جمع کنن،
#  بهشون غذا بدن (پیوند/bond بالا بره) و باهاشون تو نبرد لول بگیرن.
#  همراهِ فعال یه بونوسِ کوچیکِ دائمی می‌ده — دقیقاً با همون کلیدهایی
#  که item_system.combat_bonus_stats می‌ده (dmg_pct, crit_pct, ...)
#  تا قاطیِ همون مسیرِ ترکیبِ باف‌ها تو combat.py/economy_engine.py بشه.
# ============================================================
import random
import time
import uuid

PET_SPECIES = {
    "ember_fox":     {"name": "روباهِ اخگر",         "emoji": "🦊", "rarity": "common",    "bonus_stat": "dmg_pct",       "base_value": 0.020},
    "frost_owl":     {"name": "جغدِ یخی",            "emoji": "🦉", "rarity": "common",    "bonus_stat": "crit_pct",      "base_value": 0.015},
    "mud_turtle":    {"name": "لاک‌پشتِ گِلی",        "emoji": "🐢", "rarity": "common",    "bonus_stat": "defense_pct",   "base_value": 0.015},
    "shadow_cat":    {"name": "گربه‌ی سایه",         "emoji": "🐈‍⬛", "rarity": "uncommon", "bonus_stat": "lifesteal_pct", "base_value": 0.018},
    "storm_hawk":    {"name": "بازِ طوفان",          "emoji": "🦅", "rarity": "uncommon",  "bonus_stat": "accuracy_pct",  "base_value": 0.030},
    "coin_rat":      {"name": "موشِ سکه‌جو",         "emoji": "🐀", "rarity": "uncommon",  "bonus_stat": "gold_find_pct", "base_value": 0.035},
    "void_wisp":     {"name": "شبحِ خلأ",            "emoji": "👻", "rarity": "rare",      "bonus_stat": "gold_find_pct", "base_value": 0.050, "secondary_stat": "xp_pct"},
    "spark_wolf":    {"name": "گرگِ جرقه",           "emoji": "🐺", "rarity": "rare",      "bonus_stat": "dmg_pct",       "base_value": 0.040, "secondary_stat": "crit_pct"},
    "scholar_owl":   {"name": "جغدِ فرزانه",         "emoji": "🦜", "rarity": "rare",      "bonus_stat": "xp_pct",        "base_value": 0.045, "secondary_stat": "gold_find_pct"},
    "abyss_whelp":   {"name": "بچه‌اژدهای آبیس",     "emoji": "🐲", "rarity": "epic",      "bonus_stat": "dmg_pct",       "base_value": 0.060, "secondary_stat": "crit_pct"},
    "phantom_lynx":  {"name": "سیاهگوشِ روح",        "emoji": "🐆", "rarity": "epic",      "bonus_stat": "crit_pct",      "base_value": 0.045, "secondary_stat": "dmg_pct"},
    "celestial_kit": {"name": "کیتِ آسمانی",         "emoji": "✨", "rarity": "legendary", "bonus_stat": "xp_pct",        "base_value": 0.090, "secondary_stat": "gold_find_pct"},
    "abyssal_heart": {"name": "قلبِ آبیس",           "emoji": "💜", "rarity": "legendary", "bonus_stat": "lifesteal_pct", "base_value": 0.070, "secondary_stat": "defense_pct"},
}

RARITY_LABEL = {
    "common": "⚪ معمولی", "uncommon": "🟢 غیرعادی", "rare": "🔵 نادر",
    "epic": "🟣 حماسی", "legendary": "🟡 لجندری",
}

STAT_LABELS = {
    "dmg_pct": "⚔️ دمیج", "crit_pct": "🎯 شانسِ کریت", "lifesteal_pct": "🩸 لایف‌استیل",
    "accuracy_pct": "🏹 دقت", "gold_find_pct": "💰 شانسِ طلا", "xp_pct": "✨ XP",
    "defense_pct": "🛡️ کاهشِ دمیجِ ورودی",
}

RARITY_WEIGHTS = {"common": 100, "uncommon": 45, "rare": 18, "epic": 6, "legendary": 1.5}
SECONDARY_STAT_RATIO = {"common": 0, "uncommon": 0, "rare": 0.4, "epic": 0.5, "legendary": 0.6}

EGG_PRICE = 3000

# ─── محدودیتِ روزانه‌ی شکوندنِ تخم ──────────────────────────────
DAILY_EGG_MAX = 48

def daily_eggs_remaining(player: dict) -> int:
    now = time.time()
    if now >= player.get("daily_egg_reset_at", 0):
        player["daily_egg_used"] = 0
        player["daily_egg_reset_at"] = now + 86400
    return DAILY_EGG_MAX - player.get("daily_egg_used", 0)

def use_daily_egg(player: dict) -> bool:
    if daily_eggs_remaining(player) <= 0:
        return False
    player["daily_egg_used"] = player.get("daily_egg_used", 0) + 1
    return True
FEED_COST = 200
FEED_BOND_GAIN = 8
MAX_BOND = 100
XP_SHARE_FROM_COMBAT = 0.12   # همراه این‌قدر از XPِ کسب‌شده‌ی بازیکن رو می‌گیره
PET_XP_PER_LEVEL = 60
MAX_PET_LEVEL = 50

# ─── تعامل رایگان — یه راهِ روزانه/غیرپولی برای بالا بردنِ پیوند ───
PLAY_COOLDOWN_SEC = 4 * 3600
PLAY_BOND_GAIN = 4

# ─── تکامل — رشدِ همراه با سطح، فقط یه ضربِ عددی نیست، جهش‌های واقعی داره ───
EVOLUTION_LEVELS = [1, 15, 35]           # از این سطح‌ها به بعد وارد مرحله‌ی بعدی می‌شه
EVOLUTION_LABELS = ["", "🌟 بالغ", "👑 اسطوره‌ای"]
EVOLUTION_MULT   = [1.0, 1.3, 1.7]

# ─── توانایی‌های فعال — از این سطح به بعد، همراه گاهی تو نبرد/جایزه کمک می‌کنه ───
ABILITY_UNLOCK_LEVEL = 10
ABILITY_PROC_CHANCE = 0.18

# ─── عنوان‌های دائمیِ پیوند/مجموعه — قاطیِ titles_system می‌شن ───
BOND_MAX_TITLE = "🐾 دوستِ واقعیِ همراه"
LEGENDARY_PET_TITLE = "🐾 خوش‌شانسِ همراه‌ها"
COLLECTOR_TITLE = "🐾 جمع‌آورِ همراه‌ها"
COLLECTOR_THRESHOLD = 5

# ─── فروش — همراهِ اضافه/تکراری رو نقد کن ───
SELL_VALUE_BY_RARITY = {
    "common": 150, "uncommon": 300, "rare": 700, "epic": 1800, "legendary": 5000,
}
SELL_LEVEL_BONUS = 0.15   # هر لول بالاتر از ۱، این‌قدر به قیمتِ پایه اضافه می‌شه

# ─── ادغام (Fuse) — یه همراه رو خوراکِ همراهِ دیگه کن تا اون یکی XP بگیره ───
FUSE_XP_RATIO = 0.6              # چند درصد از XPِ سرمایه‌گذاری‌شده‌ی خوراک منتقل می‌شه
FUSE_SAME_SPECIES_BONUS = 1.5    # اگه خوراک هم‌گونه‌ی هدف باشه، این ضریب اضافه می‌شه
FUSE_XP_MIN = 20
# ارزشِ پایه‌ی هر خوراک بر اساسِ رریتیش — بدونِ این، یه پتِ لجندریِ تازه‌هچ‌شده
# (سطح ۱، صفر XP سرمایه‌گذاری‌شده) دقیقاً هم‌ارزِ یه پتِ معمولیِ تازه بود و
# ادغامش عملاً هیچ سطحی بالا نمی‌برد.
FUSE_RARITY_BASE_XP = {
    "common": 10, "uncommon": 30, "rare": 90, "epic": 250, "legendary": 700,
}


def roll_species() -> str:
    ids = list(PET_SPECIES.keys())
    weights = [RARITY_WEIGHTS[PET_SPECIES[i]["rarity"]] for i in ids]
    return random.choices(ids, weights=weights, k=1)[0]


def _new_pet(species_id: str) -> dict:
    sp = PET_SPECIES[species_id]
    return {
        "pet_id": uuid.uuid4().hex[:10],
        "species": species_id,
        "name": sp["name"], "emoji": sp["emoji"], "rarity": sp["rarity"],
        "level": 1, "xp": 0, "bond": 20,
        "obtained_at": time.time(),
    }


def hatch_egg(player: dict) -> dict:
    """یه همراهِ جدید می‌سازه، به مجموعه‌ی بازیکن اضافه می‌کنه و اگه اولین
    همراهش باشه، خودکار فعالش می‌کنه. اگه این کار باعثِ باز شدنِ یه عنوانِ
    دائمی بشه (اولین لجندری، ۵ همراه)، تو pet["_new_titles"] برمی‌گرده."""
    species_id = roll_species()
    pet = _new_pet(species_id)
    pets = player.setdefault("pets", [])
    pets.append(pet)
    if not player.get("active_pet_id"):
        player["active_pet_id"] = pet["pet_id"]

    titles = player.setdefault("pet_titles", [])
    new_titles = []
    if pet["rarity"] == "legendary" and LEGENDARY_PET_TITLE not in titles:
        titles.append(LEGENDARY_PET_TITLE)
        new_titles.append(LEGENDARY_PET_TITLE)
    if len(pets) >= COLLECTOR_THRESHOLD and COLLECTOR_TITLE not in titles:
        titles.append(COLLECTOR_TITLE)
        new_titles.append(COLLECTOR_TITLE)
    pet["_new_titles"] = new_titles
    return pet


def active_pet(player: dict) -> dict | None:
    pets = player.get("pets", [])
    if not pets:
        return None
    active_id = player.get("active_pet_id")
    for p in pets:
        if p["pet_id"] == active_id:
            return p
    return pets[0]


def set_active_pet(player: dict, pet_id: str) -> bool:
    pets = player.get("pets", [])
    if not any(p["pet_id"] == pet_id for p in pets):
        return False
    player["active_pet_id"] = pet_id
    return True


def xp_for_level(level: int) -> int:
    return level * PET_XP_PER_LEVEL


def evolution_stage(pet: dict) -> int:
    level = pet.get("level", 1)
    stage = 0
    for i, threshold in enumerate(EVOLUTION_LEVELS):
        if level >= threshold:
            stage = i
    return stage


def add_pet_xp(player: dict, player_xp_gain: int) -> dict | None:
    """موقعِ هر کشتار صدا زده می‌شه. اگه همراهِ فعال لول‌آپ کرد، جزئیاتش
    (و اگه مرحله‌ی تکاملش هم عوض شده باشه) رو برمی‌گردونه، وگرنه None."""
    pet = active_pet(player)
    if not pet or pet.get("level", 1) >= MAX_PET_LEVEL or player_xp_gain <= 0:
        return None
    old_stage = evolution_stage(pet)
    gain = max(1, int(player_xp_gain * XP_SHARE_FROM_COMBAT))
    pet["xp"] = pet.get("xp", 0) + gain
    leveled = False
    while pet["level"] < MAX_PET_LEVEL and pet["xp"] >= xp_for_level(pet["level"]):
        pet["xp"] -= xp_for_level(pet["level"])
        pet["level"] += 1
        leveled = True
    if not leveled:
        return None
    new_stage = evolution_stage(pet)
    return {
        "leveled": True, "level": pet["level"], "name": pet["name"], "emoji": pet["emoji"],
        "evolved": new_stage > old_stage,
        "evolution_label": EVOLUTION_LABELS[new_stage] if new_stage > old_stage else None,
    }


def _check_bond_title(player: dict, pet: dict) -> str | None:
    if pet.get("bond", 0) < MAX_BOND:
        return None
    titles = player.setdefault("pet_titles", [])
    if BOND_MAX_TITLE in titles:
        return None
    titles.append(BOND_MAX_TITLE)
    return BOND_MAX_TITLE


def feed_pet(player: dict, pet_id: str) -> dict:
    pets = player.get("pets", [])
    pet = next((p for p in pets if p["pet_id"] == pet_id), None)
    if not pet:
        return {"error": "not_found"}
    if pet.get("bond", 20) >= MAX_BOND:
        return {"error": "max_bond"}
    if player.get("zen", 0) < FEED_COST:
        return {"error": "not_enough_zen"}
    player["zen"] -= FEED_COST
    pet["bond"] = min(MAX_BOND, pet.get("bond", 20) + FEED_BOND_GAIN)
    new_title = _check_bond_title(player, pet)
    return {"bond": pet["bond"], "new_title": new_title}


def play_with_pet(player: dict, pet_id: str) -> dict:
    """راهِ رایگانِ بالا بردنِ پیوند — کول‌داون داره ولی هزینه‌ای نداره،
    تا نیازِ به غذا دادنِ پولی نباشه و بازی سخت‌گیرانه حس نشه."""
    pet = next((p for p in player.get("pets", []) if p["pet_id"] == pet_id), None)
    if not pet:
        return {"error": "not_found"}
    if pet.get("bond", 20) >= MAX_BOND:
        return {"error": "max_bond"}
    now = time.time()
    last = pet.get("last_played_at", 0)
    if now - last < PLAY_COOLDOWN_SEC:
        return {"error": "cooldown", "remain": int(PLAY_COOLDOWN_SEC - (now - last))}
    pet["last_played_at"] = now
    pet["bond"] = min(MAX_BOND, pet.get("bond", 20) + PLAY_BOND_GAIN)
    new_title = _check_bond_title(player, pet)
    return {"bond": pet["bond"], "new_title": new_title}


def rename_pet(player: dict, pet_id: str, new_name: str) -> bool:
    new_name = (new_name or "").strip()[:24]
    if not new_name:
        return False
    pet = next((p for p in player.get("pets", []) if p["pet_id"] == pet_id), None)
    if not pet:
        return False
    pet["name"] = new_name
    return True


def sell_price(pet: dict) -> int:
    base = SELL_VALUE_BY_RARITY.get(pet.get("rarity"), 100)
    level_mult = 1 + (pet.get("level", 1) - 1) * SELL_LEVEL_BONUS
    return int(base * level_mult)


def sell_pet(player: dict, pet_id: str) -> dict:
    """همراه رو نقد می‌کنه و از مجموعه حذفش می‌کنه. اگه همراهِ فعال بود،
    خودکار یه همراهِ دیگه (اگه مونده باشه) رو فعال می‌کنه."""
    pets = player.get("pets", [])
    pet = next((p for p in pets if p["pet_id"] == pet_id), None)
    if not pet:
        return {"error": "not_found"}
    price = sell_price(pet)
    pets.remove(pet)
    player["zen"] = player.get("zen", 0) + price
    if player.get("active_pet_id") == pet_id:
        player["active_pet_id"] = pets[0]["pet_id"] if pets else None
    return {"sold": True, "gold": price, "name": pet["name"], "emoji": pet["emoji"]}


def total_xp_invested(pet: dict) -> int:
    """کلِ XPـی که تا این سطح روی این همراه سرمایه‌گذاری شده (برای محاسبه‌ی
    ارزشِ ادغام)."""
    lvl = pet.get("level", 1)
    total = sum(xp_for_level(l) for l in range(1, lvl))
    return total + pet.get("xp", 0)


def fuse_pet(player: dict, target_pet_id: str, fodder_pet_id: str) -> dict:
    """همراهِ fodder رو مصرف می‌کنه (حذفش می‌کنه) و XPِ حاصل رو به همراهِ
    target می‌ده — یعنی نسخه‌ی اولت رو با تکراری‌هات لول ببر بالا."""
    if target_pet_id == fodder_pet_id:
        return {"error": "same_pet"}
    pets = player.get("pets", [])
    target = next((p for p in pets if p["pet_id"] == target_pet_id), None)
    fodder = next((p for p in pets if p["pet_id"] == fodder_pet_id), None)
    if not target or not fodder:
        return {"error": "not_found"}
    if target.get("level", 1) >= MAX_PET_LEVEL:
        return {"error": "target_max_level"}

    same_species = fodder["species"] == target["species"]
    bonus = FUSE_SAME_SPECIES_BONUS if same_species else 1.0
    rarity_base = FUSE_RARITY_BASE_XP.get(fodder.get("rarity"), 0)
    fodder_value = total_xp_invested(fodder) + rarity_base
    xp_gain = max(FUSE_XP_MIN, int(fodder_value * FUSE_XP_RATIO * bonus))

    pets.remove(fodder)
    if player.get("active_pet_id") == fodder_pet_id:
        player["active_pet_id"] = target_pet_id

    old_stage = evolution_stage(target)
    old_level = target["level"]
    target["xp"] = target.get("xp", 0) + xp_gain
    while target["level"] < MAX_PET_LEVEL and target["xp"] >= xp_for_level(target["level"]):
        target["xp"] -= xp_for_level(target["level"])
        target["level"] += 1
    new_stage = evolution_stage(target)

    return {
        "fused": True, "xp_gain": xp_gain, "same_species": same_species,
        "levels_gained": target["level"] - old_level, "new_level": target["level"],
        "name": target["name"], "emoji": target["emoji"], "fodder_name": fodder["name"],
        "evolved": new_stage > old_stage,
        "evolution_label": EVOLUTION_LABELS[new_stage] if new_stage > old_stage else None,
    }


def pet_bonus_value(pet: dict) -> float:
    sp = PET_SPECIES.get(pet["species"], {})
    base = sp.get("base_value", 0)
    level_mult = 1 + (pet.get("level", 1) - 1) * 0.04
    bond_mult = 1 + (pet.get("bond", 20) / 100) * 0.5
    evo_mult = EVOLUTION_MULT[evolution_stage(pet)]
    return base * level_mult * bond_mult * evo_mult


def pet_combat_bonus(player: dict) -> dict:
    """دقیقاً هم‌شکلِ item_system.combat_bonus_stats — کلیدهایی که
    combat.py/economy_engine.py/mob_combat.py مستقیم می‌فهمن. همراه‌های
    نادر+ یه استتِ فرعی هم (با ضریبِ کمتر) اضافه می‌کنن."""
    pet = active_pet(player)
    if not pet:
        return {}
    sp = PET_SPECIES.get(pet["species"], {})
    result = {}
    stat = sp.get("bonus_stat")
    if stat:
        result[stat] = pet_bonus_value(pet)
    sec_stat = sp.get("secondary_stat")
    ratio = SECONDARY_STAT_RATIO.get(pet.get("rarity"), 0)
    if sec_stat and ratio > 0:
        result[sec_stat] = result.get(sec_stat, 0) + pet_bonus_value(pet) * ratio
    return result


# ────────────────────────────────────────────────────────────
# توانایی‌های فعال — از سطح ۱۰ به بعد، همراه گاهی تو نبرد یا موقعِ
# جمع‌کردنِ جایزه دستِ بازیکن رو می‌گیره. شانس/قدرت با سطح بالا می‌ره.
# ────────────────────────────────────────────────────────────
def _ability_power(pet: dict) -> float:
    return min(2.0, 1 + max(0, pet.get("level", 1) - ABILITY_UNLOCK_LEVEL) * 0.02)


def pet_ability_proc(player: dict) -> dict | None:
    """برای همراه‌های نوعِ دمیج/کریت/لایف‌استیل/دفاع/دقت — یه کمکِ فعالِ
    لحظه‌ای تو خودِ نبرد (combat.py صدا می‌زنه)."""
    pet = active_pet(player)
    if not pet or pet.get("level", 1) < ABILITY_UNLOCK_LEVEL:
        return None
    sp = PET_SPECIES.get(pet["species"], {})
    stat = sp.get("bonus_stat")
    if stat not in ("dmg_pct", "crit_pct", "lifesteal_pct", "defense_pct", "accuracy_pct"):
        return None
    if random.random() >= ABILITY_PROC_CHANCE:
        return None
    return {"stat": stat, "power": _ability_power(pet), "name": pet["name"], "emoji": pet["emoji"]}


def pet_reward_proc(player: dict) -> dict | None:
    """برای همراه‌های نوعِ طلا/XP — یه بونوسِ یک‌باره موقعِ جمع‌کردنِ جایزه‌ی
    کشتار (mob_combat.py صدا می‌زنه)."""
    pet = active_pet(player)
    if not pet or pet.get("level", 1) < ABILITY_UNLOCK_LEVEL:
        return None
    sp = PET_SPECIES.get(pet["species"], {})
    stat = sp.get("bonus_stat")
    if stat not in ("gold_find_pct", "xp_pct"):
        return None
    if random.random() >= ABILITY_PROC_CHANCE:
        return None
    return {"stat": stat, "power": _ability_power(pet), "name": pet["name"], "emoji": pet["emoji"]}


def format_pet_card(pet: dict) -> str:
    next_xp = xp_for_level(pet["level"])
    sp = PET_SPECIES.get(pet["species"], {})
    stat = sp.get("bonus_stat", "")
    sec_stat = sp.get("secondary_stat")
    ratio = SECONDARY_STAT_RATIO.get(pet.get("rarity"), 0)
    bonus_val = pet_bonus_value(pet)
    stat_label = STAT_LABELS.get(stat, stat)
    lvl_txt = "MAX" if pet["level"] >= MAX_PET_LEVEL else f"{pet['xp']}/{next_xp} XP"
    stage = evolution_stage(pet)
    evo_label = f" {EVOLUTION_LABELS[stage]}" if stage else ""

    lines = [
        f"{pet['emoji']} **{pet['name']}**{evo_label}",
        f"{RARITY_LABEL.get(pet['rarity'], '')}",
        f"📊 سطح {pet['level']} ({lvl_txt})",
        f"❤️ پیوند: {pet.get('bond', 20)}/{MAX_BOND}",
        f"{stat_label}: +{bonus_val*100:.1f}٪",
    ]
    if sec_stat and ratio > 0:
        sec_label = STAT_LABELS.get(sec_stat, sec_stat)
        lines.append(f"{sec_label} (فرعی): +{bonus_val*ratio*100:.1f}٪")
    if pet["level"] >= ABILITY_UNLOCK_LEVEL:
        lines.append(f"✨ توانایی فعال: {int(ABILITY_PROC_CHANCE*100)}٪ شانسِ کمکِ ویژه تو نبرد/جایزه")
    else:
        lines.append(f"🔒 توانایی فعال از سطح {ABILITY_UNLOCK_LEVEL} باز می‌شه")
    return "\n".join(lines)
