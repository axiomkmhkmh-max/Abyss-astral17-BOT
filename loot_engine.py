# ============================================================
#  ASTRAL ABYSS — Loot Engine 2.0
#  استریک لوت، پیتی‌سیستم، ست‌آیتم‌ها، صندوق قفل‌شده + کلید
# ============================================================
import random
from economy import MAP_LOOT, MAPS_DATA

RARITY_ORDER = ["common", "uncommon", "rare", "epic", "mythic", "legendary"]

# ─── Streak ──────────────────────────────────────────────────
# هر ۵ استریک یه "تیر" (tier) جدید = بونوس بیشتر. تا تیر ۱۰ (استریک ۵۰) کلاه داره.
STREAK_TIER_CAP      = 10
ZEN_BONUS_PER_TIER   = 0.04      # +4% zen به ازای هر تیر
RARITY_SHIFT_PER_TIER = 0.025    # +2.5% شانس ارتقای رریتی به ازای هر تیر

STREAK_TITLES = {
    5:  "🔥 شانس داغ",
    10: "⚡ زنجیره‌ی شکست‌ناپذیر",
    20: "👑 محبوب سرنوشت",
    35: "🌌 برکت آبیس",
    50: "💫 افسانه‌ی شانس",
}

def get_streak_title(streak: int) -> str:
    title = ""
    for th in sorted(STREAK_TITLES):
        if streak >= th:
            title = STREAK_TITLES[th]
    return title

def streak_tier(streak: int) -> int:
    return min(streak // 5, STREAK_TIER_CAP)

def guard_streak_loss(player: dict) -> bool:
    """
    وقتی بازیکن می‌میره یا فرار می‌کنه صدا زده می‌شه.
    اولویت محافظت: ۱) طلسم استریک روزانه‌ی مسیر اقبال (رایگان، یک‌بار در روز)
    ۲) طلسم شانس خریداری‌شده (fortune ward، مصرفی)
    خروجی True یعنی استریک نجات پیدا کرد.
    """
    import time
    streak = player.get("loot_streak", 0)
    if streak <= 0:
        return False

    try:
        from skill_tree import get_skill_bonuses
        has_skill_shield = get_skill_bonuses(player).get("streak_shield_charge", 0) > 0
    except ImportError:
        has_skill_shield = False

    if has_skill_shield:
        today = int(time.time() // 86400)
        if player.get("streak_shield_used_day") != today:
            player["streak_shield_used_day"] = today
            return True

    wards = player.get("fortune_ward_count", 0)
    if wards > 0:
        player["fortune_ward_count"] = wards - 1
        return True
    player["loot_streak"] = 0
    return False

FORTUNE_WARD_PRICE = 8000

# ─── Pity System ─────────────────────────────────────────────
# اگه X کشتار پشت‌سرهم بدون آیتم epic+ بگذره، کشتار بعدی تضمینی جبران می‌شه.
PITY_THRESHOLD = 15

def _rarity_idx(rarity: str) -> int:
    return RARITY_ORDER.index(rarity) if rarity in RARITY_ORDER else 0

def maybe_upgrade_rarity(item: dict | None, chance: float) -> dict | None:
    if not item or chance <= 0:
        return item
    if random.random() < chance:
        idx = _rarity_idx(item.get("rarity", "common"))
        new_idx = min(idx + 1, len(RARITY_ORDER) - 1)
        if new_idx > idx:
            item["rarity"] = RARITY_ORDER[new_idx]
            item["sell"] = int(item.get("sell", 0) * 1.6)
            item["upgraded"] = True
            if "item_id" in item:  # آیتم واقعیِ item_system.py — score رو دوباره حساب کن
                from item_system import calculate_item_score
                item["item_score"] = calculate_item_score(item)
    return item

# ─── آیتمِ ضربان — بونوسِ لوتِ وصل‌شده به مپِ هدفِ ضربانِ فعال ─────
def pulse_bonus_drop(map_name: str) -> dict | None:
    """اگه ضربانِ فعال از نوعِ blessing باشه و دقیقاً روی همین نقشه (map_name)
    متمرکز باشه، شانسِ کمی هست که یه آیتمِ کمیاب (rare+) از پولِ لوتِ همون
    نقشه، جدا از لوتِ عادی، به بازیکن بدیم — یه دلیلِ واقعی برای رفتن به
    نقشه‌ای که ضربان روشه، نه هرجایی."""
    try:
        from world_pulse import pulse_loot_bonus_chance, get_active_pulse
    except ImportError:
        return None
    chance = pulse_loot_bonus_chance(map_name)
    if chance <= 0 or random.random() > chance:
        return None
    pulse = get_active_pulse()
    pool = MAP_LOOT.get(map_name, [])
    candidates = [i for i in pool if i.get("rarity") in ("rare", "epic", "mythic", "legendary")] or pool
    if not candidates:
        return None
    item = random.choice(candidates).copy()
    item["sell"] = int(item.get("sell", 0) * random.uniform(1.3, 1.8))
    item["pulse_drop"] = True
    item["pulse_event_name"] = pulse.get("name") if pulse else None
    return item


def force_epic_item(map_name: str, fallback_item: dict | None) -> dict:
    pool = MAP_LOOT.get(map_name, [])
    epics = [i for i in pool if i.get("rarity") in ("epic", "legendary")]
    if epics:
        item = random.choice(epics).copy()
        item["sell"] = int(item["sell"] * random.uniform(1.0, 1.3))
        item["pity"] = True
        return item
    if fallback_item:
        fallback_item = dict(fallback_item)
        fallback_item["rarity"] = "epic"
        fallback_item["sell"] = int(fallback_item.get("sell", 100) * 3)
        fallback_item["pity"] = True
        return fallback_item
    return {"name": "Fragment of Fate", "emoji": "🍀", "rarity": "epic", "sell": 1200, "pity": True}

# ─── Set Items ───────────────────────────────────────────────
# ۶ ست، هرکدوم ۳ قطعه، مخصوص نقشه‌های خاص. بونوس‌ها فعلاً توصیفی/اطلاعاتی‌ن
# (هوک آماده برای فاز بعدی: اتصال به combat.py برای اعمال باف واقعی).
SET_ITEMS = {
    "voidwalker": {
        "display": "🌑 ست ویدواکر",
        "maps": ["Voidbreak Wastes", "Abyssal Black Market", "Dreadgate Citadel"],
        "pieces": {
            "vw_cloak": {"name": "Voidwalker Cloak", "emoji": "🖤"},
            "vw_blade": {"name": "Voidwalker Blade", "emoji": "🗡️"},
            "vw_sigil": {"name": "Voidwalker Sigil", "emoji": "🔮"},
        },
        "bonus": {
            2: {"dmg_pct": 0.08, "desc": "+8% آسیب"},
            3: {"dmg_pct": 0.15, "lifesteal_pct": 0.05, "desc": "+15% آسیب و +5% لایف‌استیل"},
        },
    },
    "emberlord": {
        "display": "🔥 ست امبرلورد",
        "maps": ["Emberhollow", "Dragonnest Peaks"],
        "pieces": {
            "el_gauntlet": {"name": "Emberlord Gauntlet", "emoji": "🧤"},
            "el_scale":    {"name": "Emberlord Scale",    "emoji": "🐉"},
            "el_crown":    {"name": "Emberlord Crown",    "emoji": "👑"},
        },
        "bonus": {
            2: {"crit_pct": 0.06, "desc": "+6% شانس کریتیکال"},
            3: {"crit_pct": 0.12, "elem_amp": 0.15, "desc": "+12% کریتیکال و +15% آسیب عنصر آتش"},
        },
    },
    "frostbound": {
        "display": "❄️ ست فراست‌باند",
        "maps": ["Frostheim"],
        "pieces": {
            "fb_shard":  {"name": "Frostbound Shard",  "emoji": "🔷"},
            "fb_plate":  {"name": "Frostbound Plate",  "emoji": "🛡️"},
            "fb_heart":  {"name": "Frostbound Heart",  "emoji": "💙"},
        },
        "bonus": {
            2: {"defense_pct": 0.10, "desc": "+10% دفاع"},
            3: {"defense_pct": 0.18, "counter_pct": 0.10, "desc": "+18% دفاع و +10% شانس کانتر"},
        },
    },
    "stormcaller": {
        "display": "⚡ ست استورم‌کالر",
        "maps": ["Stormward Archipelago", "Azure Tides Empire"],
        "pieces": {
            "sc_charm": {"name": "Stormcaller Charm", "emoji": "📿"},
            "sc_wing":  {"name": "Stormcaller Wing",   "emoji": "🪽"},
            "sc_core":  {"name": "Stormcaller Core",   "emoji": "⚡"},
        },
        "bonus": {
            2: {"speed_pct": 0.08, "desc": "+8% شانس ضربه‌ی اول در PvP"},
            3: {"speed_pct": 0.15, "combo_gain": 1, "desc": "+15% سرعت و کومبوی اضافه‌ی شروع"},
        },
    },
    "sunken_sovereign": {
        "display": "🐚 ست حاکم غرق‌شده",
        "maps": ["The Sunken City"],
        "pieces": {
            "ss_trident": {"name": "Sovereign Trident", "emoji": "🔱"},
            "ss_pearl":   {"name": "Sovereign Pearl",   "emoji": "🫧"},
            "ss_crown":   {"name": "Sovereign Crown",   "emoji": "👑"},
        },
        "bonus": {
            2: {"heal_pct": 0.10, "desc": "+10% اثر درمان"},
            3: {"heal_pct": 0.20, "hp_pct": 0.08, "desc": "+20% اثر درمان و +8% HP ماکسیمم"},
        },
    },
    "celestial_ascendant": {
        "display": "✨ ست صعود آسمانی",
        "maps": ["Celestial Spire", "Holy Luminarchy"],
        "pieces": {
            "ca_halo":   {"name": "Ascendant Halo",   "emoji": "😇"},
            "ca_relic":  {"name": "Ascendant Relic",  "emoji": "📜"},
            "ca_wing":   {"name": "Ascendant Wing",   "emoji": "🕊️"},
        },
        "bonus": {
            2: {"xp_pct": 0.10, "desc": "+10% XP دریافتی"},
            3: {"xp_pct": 0.20, "zen_pct": 0.10, "desc": "+20% XP و +10% Zen دریافتی"},
        },
    },
}

SET_DROP_BASE = 0.02  # شانس پایه‌ی دراپ قطعه‌ی ست به ازای هر کشتار (فقط تو نقشه‌های مرتبط)

def maybe_drop_set_piece(player: dict, map_name: str, chance: float) -> dict | None:
    if random.random() > chance:
        return None
    eligible = [(sid, s) for sid, s in SET_ITEMS.items() if map_name in s["maps"]]
    if not eligible:
        return None
    sid, sdata = random.choice(eligible)
    owned = player.setdefault("set_collection", {})
    piece_ids = list(sdata["pieces"].keys())
    not_owned = [p for p in piece_ids if p not in owned]
    piece_id = random.choice(not_owned) if not_owned else random.choice(piece_ids)
    owned[piece_id] = True
    piece = sdata["pieces"][piece_id]
    return {
        "emoji": piece["emoji"], "name": piece["name"],
        "set_id": sid, "set_display": sdata["display"], "piece_id": piece_id,
        "rarity": "epic", "sell": 0,  # قطعات ست فروختنی نیستن، فقط جمع‌آوری میشن
    }

def get_owned_set_summary(player: dict) -> list[str]:
    owned = player.get("set_collection", {})
    lines = []
    for sid, sdata in SET_ITEMS.items():
        count = sum(1 for p in sdata["pieces"] if p in owned)
        if count == 0:
            continue
        applicable = [th for th in sdata["bonus"] if count >= th]
        bonus_desc = sdata["bonus"][max(applicable)]["desc"] if applicable else "هنوز فعال نشده (بیشتر جمع کن)"
        lines.append(f"{sdata['display']}: {count}/{len(sdata['pieces'])} — {bonus_desc}")
    return lines

def get_set_bonus_stats(player: dict) -> dict:
    """جمع تمام بونوس‌های ست فعال — آماده برای فاز بعدی (اتصال به combat.py)."""
    owned = player.get("set_collection", {})
    total = {}
    for sid, sdata in SET_ITEMS.items():
        count = sum(1 for p in sdata["pieces"] if p in owned)
        applicable = [th for th in sdata["bonus"] if count >= th]
        if not applicable:
            continue
        best = sdata["bonus"][max(applicable)]
        for k, v in best.items():
            if k == "desc":
                continue
            total[k] = total.get(k, 0) + v
    return total

# ─── Lockboxes & Keys ────────────────────────────────────────
LOCKBOXES = {
    "common_chest": {"name": "صندوق چوبی",       "emoji": "📦", "key": "rusty_key",  "guaranteed_rarity": "uncommon", "bonus_rolls": 1, "sell": 0, "set_chance": 0.0},
    "rare_vault":   {"name": "گاوصندوق نقره‌ای",   "emoji": "🗄️", "key": "silver_key", "guaranteed_rarity": "rare",     "bonus_rolls": 2, "sell": 0, "set_chance": 0.05},
    "epic_vault":   {"name": "طاق حماسی",          "emoji": "🏺", "key": "golden_key", "guaranteed_rarity": "epic",     "bonus_rolls": 2, "sell": 0, "set_chance": 0.15},
    "mythic_vault": {"name": "صندوقچه‌ی اسطوره‌ای", "emoji": "🪬", "key": "void_key",   "guaranteed_rarity": "legendary","bonus_rolls": 3, "sell": 0, "set_chance": 0.35},
}

KEYS = {
    "rusty_key":  {"name": "کلید زنگ‌زده",  "emoji": "🔑", "buy_price": 300},
    "silver_key": {"name": "کلید نقره‌ای",   "emoji": "🗝️", "buy_price": 1500},
    "golden_key": {"name": "کلید طلایی",    "emoji": "🔐", "buy_price": 6000},
    "void_key":   {"name": "کلید خلأ",      "emoji": "🕳️", "buy_price": 25000},
}

_LOCKBOX_WEIGHTS_BY_TIER = {
    "common": ["common_chest", "common_chest", "rare_vault"],
    "rare":   ["common_chest", "rare_vault", "rare_vault", "epic_vault"],
    "epic":   ["rare_vault", "epic_vault", "epic_vault", "mythic_vault"],
}
_KEY_WEIGHTS = ["rusty_key", "rusty_key", "rusty_key", "silver_key", "silver_key", "golden_key"]

def maybe_drop_lockbox(map_name: str, is_boss: bool, tier: int) -> dict | None:
    base = 0.035 + tier * 0.004 + (0.15 if is_boss else 0.0)
    if random.random() > base:
        return None
    map_tier = MAPS_DATA.get(map_name, {}).get("tier", "common")
    pool = list(_LOCKBOX_WEIGHTS_BY_TIER.get(map_tier, _LOCKBOX_WEIGHTS_BY_TIER["common"]))
    if is_boss:
        pool += ["epic_vault", "mythic_vault"]
    box_id = random.choice(pool)
    b = LOCKBOXES[box_id]
    return {"name": b["name"], "emoji": b["emoji"], "type": "lockbox", "box_id": box_id,
            "sell": b.get("sell", 0), "rarity": b.get("guaranteed_rarity", "rare")}

def maybe_drop_key(map_name: str, is_boss: bool, tier: int) -> dict | None:
    base = 0.02 + tier * 0.002 + (0.08 if is_boss else 0.0)
    if random.random() > base:
        return None
    pool = list(_KEY_WEIGHTS)
    if is_boss:
        pool += ["golden_key", "void_key"]
    key_id = random.choice(pool)
    k = KEYS[key_id]
    return {"name": k["name"], "emoji": k["emoji"], "type": "key", "key_id": key_id,
            "sell": int(k["buy_price"] * 0.3)}

def open_lockbox(player: dict, map_name_hint: str | None, box_id: str) -> list[dict]:
    b = LOCKBOXES[box_id]
    rolls = b.get("bonus_rolls", 1)
    min_idx = _rarity_idx(b["guaranteed_rarity"])
    pool_source = map_name_hint if map_name_hint in MAP_LOOT else random.choice(list(MAP_LOOT.keys()))
    pool = MAP_LOOT.get(pool_source, [])
    results = []
    for _ in range(rolls):
        candidates = [i for i in pool if _rarity_idx(i.get("rarity", "common")) >= min_idx] or pool
        if candidates:
            item = random.choice(candidates).copy()
            item["sell"] = int(item["sell"] * random.uniform(1.1, 1.5))
            results.append(item)
    if random.random() < b.get("set_chance", 0.0):
        piece = maybe_drop_set_piece(player, pool_source, 1.0)
        if piece:
            results.append(piece)
    return results

# ─── Main Hook: called after every kill ──────────────────────
def process_kill_rewards(player: dict, enemy: dict, map_name: str, is_boss: bool, base_item: dict | None):
    """
    استریک/پیتی/ست/صندوق/کلید رو اعمال می‌کنه، آیتم‌ها رو مستقیم به player["inventory"]
    اضافه می‌کنه (base_item, لوت‌باکس، کلید — قطعه‌ی ست فقط تو set_collection ثبت میشه)
    و اطلاعات لازم برای نمایش پیام رو برمی‌گردونه.

    خروجی: (item, extras, zen_mult, logs, streak, streak_title)
    """
    logs = []

    streak = player.get("loot_streak", 0) + 1
    player["loot_streak"] = streak
    player["loot_best_streak"] = max(player.get("loot_best_streak", 0), streak)
    tier = streak_tier(streak)
    zen_mult = 1 + tier * ZEN_BONUS_PER_TIER
    try:
        from skill_tree import get_skill_bonuses
        skill_rarity_bonus = get_skill_bonuses(player).get("loot_rarity_chance", 0)
    except ImportError:
        skill_rarity_bonus = 0.0
    try:
        from guild_system import get_perk
        guild_rarity_bonus = get_perk(player, "rare_loot_pct")
    except ImportError:
        guild_rarity_bonus = 0.0
    try:
        from world_pulse import pulse_value
        pulse_rarity_bonus = pulse_value("loot_luck", map_name)
    except ImportError:
        pulse_rarity_bonus = 0.0
    # 🆕 تایرِ باس (guardian/warlord/harbinger — از map_boss_pool.py) هم رو
    # شانسِ رریتی اثر می‌ذاره؛ باسِ نادرِ harbinger (فقط از دانجن) واقعاً
    # ارزششو داره.
    _boss_tier_bonus = {"guardian": 0.0, "warlord": 0.04, "harbinger": 0.10}.get(enemy.get("boss_tier"), 0.0) if is_boss else 0.0
    rarity_chance = tier * RARITY_SHIFT_PER_TIER + (0.05 if is_boss else 0.0) + _boss_tier_bonus + skill_rarity_bonus + guild_rarity_bonus + pulse_rarity_bonus
    title = get_streak_title(streak)
    if title and streak % 5 == 0:
        logs.append(f"{title} — استریک لوت {streak}x! (+{int(tier*ZEN_BONUS_PER_TIER*100)}% Zen)")

    item = maybe_upgrade_rarity(base_item, rarity_chance)

    pity = player.get("pity_counter", 0) + 1
    if item and item.get("rarity") in ("epic", "mythic", "legendary"):
        pity = 0
    elif pity >= PITY_THRESHOLD:
        item = force_epic_item(map_name, item)
        pity = 0
        logs.append(f"🍀 **شانس پیتی فعال شد!** بعد از {PITY_THRESHOLD} کشتار بدون آیتم کمیاب، جبرانش گرفتی.")
    player["pity_counter"] = pity

    extras = []
    _boss_set_mult = {"guardian": 1.0, "warlord": 1.25, "harbinger": 1.6}.get(enemy.get("boss_tier"), 1.0) if is_boss else 1.0
    set_chance = SET_DROP_BASE * (1 + tier * 0.2) * (3 if is_boss else 1) * _boss_set_mult
    piece = maybe_drop_set_piece(player, map_name, set_chance)
    if piece:
        extras.append(piece)

    box = maybe_drop_lockbox(map_name, is_boss, tier)
    if box:
        player.setdefault("inventory", []).append(box)
        extras.append(box)

    key = maybe_drop_key(map_name, is_boss, tier)
    if key:
        player.setdefault("inventory", []).append(key)
        extras.append(key)

    pulse_item = pulse_bonus_drop(map_name)
    if pulse_item:
        player.setdefault("inventory", []).append(pulse_item)
        extras.append(pulse_item)
        logs.append(
            f"⚡ **آیتمِ ضربان!** ضربانِ فعال دقیقاً رو همین نقشه متمرکزه — "
            f"یه آیتمِ اضافه گرفتی: {pulse_item['emoji']} {pulse_item['name']}"
        )

    try:
        from crafting_system import maybe_drop_material
        mat = maybe_drop_material(player, is_boss, player.get("level", 1))
        if mat:
            logs.append(f"🧵 ماده‌ی کرفت: {mat['emoji']} {mat['name']} ×{mat['qty']} (🛠 /craft)")
    except ImportError:
        pass

    if item:
        player.setdefault("inventory", []).append(item)

    return item, extras, zen_mult, logs, streak, title
