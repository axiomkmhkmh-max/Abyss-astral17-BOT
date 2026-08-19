# ============================================================
#  ASTRAL ABYSS RPG — Crafting System  (v1)
# ------------------------------------------------------------
#  دو میزِ کرفت:
#    🔨 میزِ آهنگری (forge)   → تجهیزاتِ واقعی (weapon/armor/...) با
#                                رریتیِ تضمین‌شده (بهتر از شانسِ خامِ لوت)
#    🧪 میزِ کیمیاگری (alchemy) → پوشن/الکسیر/جم/سنگ‌روح
#
#  موادِ خام (MATERIALS) از سه راه به دستِ بازیکن می‌رسه:
#    ۱) کشتنِ هیولا/باس — شانسِ کوچیکِ دراپ (هوکِ loot_engine.process_kill_rewards)
#    ۲) تجزیه‌ی (Salvage) تجهیزاتِ ناخواسته رو همین‌جا
#    ۳) (بعداً) مغازه/کوئست — به‌راحتی قابلِ افزونه
#
#  این ماژول کاملاً خودکفاست — فقط از item_system (برای ساختِ خودِ
#  تجهیزِ کرفت‌شده و افیکس‌ها) استفاده می‌کنه و هیچ فایلِ قدیمی رو
#  خراب نمی‌کنه. اتصال به combat از طریقِ item_system.equipment_stats
#  (جم‌های سوکت‌شده) و combat_bonus_stats (بافِ الکسیر) انجام می‌شه.
# ============================================================
from __future__ import annotations

import time
import random
import uuid

import item_system as isy

# ============================================================
#  ۱) موادِ خام — ۴ دسته × ۵ تیر = ۲۰ ماده + ۱ ماده‌ی جهانیِ کمیاب
# ============================================================
TIER_LABELS = {1: "I ° پایه", 2: "II ° متوسط", 3: "III ° پیشرفته", 4: "IV ° نخبه", 5: "V ° اسطوره‌ای"}

ORE_TIERS    = ["ore_iron", "ore_silver", "ore_mythril", "ore_voidsteel", "ore_starforged"]
BEAST_TIERS  = ["beast_fang", "beast_horn", "beast_core", "beast_scale", "beast_heart"]
HERB_TIERS   = ["herb_sun", "herb_frost", "herb_ember", "herb_void", "herb_astral"]
ESSENCE_TIERS = ["essence_spark", "essence_flow", "essence_shadow", "essence_radiant", "essence_chaos"]

MATERIALS = {
    # ── سنگِ‌معدن (آهنگری) ──
    "ore_iron":       {"name": "سنگِ‌آهن",         "emoji": "🪨", "tier": 1, "cat": "ore",     "sell": 8},
    "ore_silver":      {"name": "سنگِ‌نقره",        "emoji": "⛰️", "tier": 2, "cat": "ore",     "sell": 22},
    "ore_mythril":     {"name": "سنگِ‌میتریل",      "emoji": "💠", "tier": 3, "cat": "ore",     "sell": 60},
    "ore_voidsteel":   {"name": "فولادِ‌خلأ",       "emoji": "🖤", "tier": 4, "cat": "ore",     "sell": 160},
    "ore_starforged":  {"name": "سنگِ‌ستاره‌کوب",   "emoji": "🌠", "tier": 5, "cat": "ore",     "sell": 420},
    # ── اجزای هیولا (آهنگری) ──
    "beast_fang":      {"name": "دندانِ‌گرگ",       "emoji": "🦷", "tier": 1, "cat": "beast",   "sell": 10},
    "beast_horn":      {"name": "شاخِ‌دیو",         "emoji": "😈", "tier": 2, "cat": "beast",   "sell": 26},
    "beast_core":      {"name": "هسته‌ی‌روحِ‌سرگردان","emoji": "👻", "tier": 3, "cat": "beast",   "sell": 65},
    "beast_scale":     {"name": "فلسِ‌اژدها",       "emoji": "🐉", "tier": 4, "cat": "beast",   "sell": 175},
    "beast_heart":     {"name": "قلبِ‌پوچی",        "emoji": "💀", "tier": 5, "cat": "beast",   "sell": 450},
    # ── گیاه (کیمیاگری) ──
    "herb_sun":        {"name": "برگِ‌خورشید",      "emoji": "🌿", "tier": 1, "cat": "herb",    "sell": 7},
    "herb_frost":      {"name": "ریشه‌ی‌یخ",        "emoji": "❄️", "tier": 2, "cat": "herb",    "sell": 20},
    "herb_ember":      {"name": "خزه‌ی‌اخگر",       "emoji": "🔥", "tier": 3, "cat": "herb",    "sell": 55},
    "herb_void":       {"name": "نیلوفرِ‌خلأ",      "emoji": "🌑", "tier": 4, "cat": "herb",    "sell": 150},
    "herb_astral":      {"name": "زنبقِ‌اختری",      "emoji": "🌌", "tier": 5, "cat": "herb",    "sell": 400},
    # ── جوهر/عصاره (کیمیاگری) ──
    "essence_spark":   {"name": "جوهرِ‌جرقه",       "emoji": "⚡", "tier": 1, "cat": "essence", "sell": 9},
    "essence_flow":    {"name": "جوهرِ‌جریان",      "emoji": "🌊", "tier": 2, "cat": "essence", "sell": 24},
    "essence_shadow":  {"name": "جوهرِ‌سایه",       "emoji": "🌫️", "tier": 3, "cat": "essence", "sell": 62},
    "essence_radiant":  {"name": "جوهرِ‌تابان",      "emoji": "✨", "tier": 4, "cat": "essence", "sell": 165},
    "essence_chaos":   {"name": "جوهرِ‌آشوب",       "emoji": "🌀", "tier": 5, "cat": "essence", "sell": 430},
    # ── جهانیِ کمیاب ──
    "astral_dust":     {"name": "غبارِ‌اختری",      "emoji": "🌟", "tier": 5, "cat": "rare",    "sell": 500},
}


def _mat(mat_id: str) -> dict:
    return MATERIALS.get(mat_id, {"name": mat_id, "emoji": "📦", "tier": 1, "cat": "?", "sell": 1})


# ─── کمکی‌های عمومیِ اینونتوری (موادِ استک‌شونده) ──────────────────
def material_qty(player: dict, mat_id: str, item_type: str = "material") -> int:
    for it in player.get("inventory", []):
        if it.get("type") == item_type and it.get("material_id") == mat_id:
            return it.get("qty", 0)
    return 0


def add_material(player: dict, mat_id: str, qty: int = 1, item_type: str = "material", extra: dict | None = None):
    if qty <= 0:
        return
    inv = player.setdefault("inventory", [])
    for it in inv:
        if it.get("type") == item_type and it.get("material_id") == mat_id:
            it["qty"] = it.get("qty", 0) + qty
            return
    m = _mat(mat_id)
    entry = {
        "id": f"{item_type}_{mat_id}_{int(time.time()*1000)}_{uuid.uuid4().hex[:4]}",
        "material_id": mat_id, "name": m["name"], "emoji": m["emoji"],
        "type": item_type, "qty": qty, "sell": m.get("sell", 1),
    }
    if extra:
        entry.update(extra)
    inv.append(entry)


def _consume_materials(player: dict, costs: dict, item_type: str = "material") -> None:
    inv = player.setdefault("inventory", [])
    for mat_id, need in costs.items():
        for it in inv:
            if it.get("type") == item_type and it.get("material_id") == mat_id:
                it["qty"] = it.get("qty", 0) - need
                break
    inv[:] = [it for it in inv if not (it.get("type") in ("material", "gem", "potion") and it.get("qty", 0) <= 0)]


def missing_materials_text(player: dict, costs: dict, item_type: str = "material") -> str:
    parts = []
    for mat_id, need in costs.items():
        have = material_qty(player, mat_id, item_type)
        m = _mat(mat_id)
        mark = "✅" if have >= need else "❌"
        parts.append(f"{mark}{m['emoji']}{m['name']}:{have}/{need}")
    return " | ".join(parts)


def has_materials(player: dict, costs: dict, item_type: str = "material") -> bool:
    return all(material_qty(player, mid, item_type) >= need for mid, need in costs.items())


# ============================================================
#  ۲) مهارتِ کرفت (Mastery) — هر میز جدا لول می‌گیره
# ============================================================
CRAFT_LEVEL_CAP = 10


def _default_crafting() -> dict:
    return {"forge_level": 1, "forge_xp": 0, "alchemy_level": 1, "alchemy_xp": 0}


def get_crafting(player: dict) -> dict:
    c = player.setdefault("crafting", _default_crafting())
    for k, v in _default_crafting().items():
        c.setdefault(k, v)
    return c


def xp_needed(level: int) -> int:
    return 120 * level * level


def _gain_xp(player: dict, table: str, amount: int) -> list[str]:
    c = get_crafting(player)
    logs = []
    lvl_key, xp_key = f"{table}_level", f"{table}_xp"
    if c[lvl_key] >= CRAFT_LEVEL_CAP:
        return logs
    c[xp_key] += amount
    while c[lvl_key] < CRAFT_LEVEL_CAP and c[xp_key] >= xp_needed(c[lvl_key]):
        c[xp_key] -= xp_needed(c[lvl_key])
        c[lvl_key] += 1
        title = "🔨 آهنگری" if table == "forge" else "🧪 کیمیاگری"
        logs.append(f"📈 مهارتِ {title} به سطح {c[lvl_key]} رسید!")
    return logs


# ============================================================
#  ۳) میزِ آهنگری (Forge) — تجهیزات، ۸ اسلات × ۵ تیر = ۴۰ دستور
# ============================================================
SLOT_LABELS = {
    "weapon": "⚔️ سلاح", "helmet": "⛑️ کلاهخود", "armor": "🛡️ زره", "gloves": "🧤 دستکش",
    "boots": "🥾 چکمه", "ring": "💍 حلقه", "amulet": "📿 گردنبند", "relic": "🔮 مصنوعه",
}
CRAFT_RARITY_BY_TIER = {1: "uncommon", 2: "rare", 3: "epic", 4: "mythic", 5: "legendary"}


def _build_forge_recipes() -> dict:
    recipes = {}
    for slot in isy.EQUIP_SLOTS:
        for tier in range(1, 6):
            key = f"{slot}_t{tier}"
            ore = ORE_TIERS[tier - 1]
            beast = BEAST_TIERS[tier - 1]
            recipes[key] = {
                "slot": slot, "tier": tier,
                "rarity": CRAFT_RARITY_BY_TIER[tier],
                "materials": {ore: 2 + tier, beast: 1 + tier},
                "zen_cost": 120 * tier * tier + 80 * tier,
                "req_level": tier * 2 - 1,
                "label": f"{SLOT_LABELS[slot]} — تیر {TIER_LABELS[tier]}",
            }
    return recipes


FORGE_RECIPES = _build_forge_recipes()


def craft_forge(uid: int, player: dict, recipe_key: str) -> tuple[bool, str, dict | None]:
    recipe = FORGE_RECIPES.get(recipe_key)
    if not recipe:
        return False, "❌ دستورِ آهنگریِ نامعتبر.", None
    c = get_crafting(player)
    if c["forge_level"] < recipe["req_level"]:
        return False, f"❌ به سطحِ آهنگریِ {recipe['req_level']} نیاز داری (الان: {c['forge_level']}).", None
    if not has_materials(player, recipe["materials"]):
        return False, f"❌ موادِ کافی نداری:\n{missing_materials_text(player, recipe['materials'])}", None
    if player.get("zen", 0) < recipe["zen_cost"]:
        return False, f"❌ به {recipe['zen_cost']:,} Zen نیاز داری.", None

    _consume_materials(player, recipe["materials"])
    player["zen"] -= recipe["zen_cost"]

    template = random.choice(isy.EQUIPMENT_TEMPLATES[recipe["slot"]])
    template = {**template, "slot": recipe["slot"]}
    lvl = player.get("level", 1)

    item_a = isy.generate_item(template, lvl, forced_rarity=recipe["rarity"], drop_source="craft:forge")
    crit = random.random() < 0.15
    if crit:
        item_b = isy.generate_item(template, lvl, forced_rarity=recipe["rarity"], drop_source="craft:forge")
        item = item_a if item_a["item_score"] >= item_b["item_score"] else item_b
    else:
        item = item_a

    player.setdefault("inventory", []).append(item)
    logs = _gain_xp(player, "forge", recipe["tier"] * 25)  # باگ‌فیکس: XP آهنگری خیلی کند بالا می‌رفت

    tag = " 🌟 **کرفتِ کریتیکال!** (بهترین رولِ ممکن)" if crit else ""
    msg = f"🔨 ساختی: {item['emoji']} **{item['name']}** ({isy.RARITY_DATA[item['rarity']]['label']}){tag}"
    if logs:
        msg += "\n" + "\n".join(logs)
    return True, msg, item


# ============================================================
#  ۴) میزِ کیمیاگری (Alchemy) — پوشن/الکسیر/جم/سنگ‌روح
# ============================================================
POTION_RECIPES = {
    "potion_minor_heal": {
        "name": "🧪 پوشنِ کوچکِ درمان", "kind": "heal", "heal_pct": 0.35,
        "materials": {"herb_sun": 3}, "zen_cost": 60, "req_level": 1,
        "desc": "درمانِ آنیِ ۳۵٪ از HP",
    },
    "potion_major_heal": {
        "name": "🧪 پوشنِ بزرگِ درمان", "kind": "heal", "heal_pct": 1.0,
        "materials": {"herb_frost": 3, "herb_ember": 2}, "zen_cost": 220, "req_level": 4,
        "desc": "درمانِ کاملِ HP",
    },
    "elixir_power": {
        "name": "🥃 الکسیرِ قدرت", "kind": "buff", "buff_stat": "dmg_pct", "buff_value": 0.10,
        "duration": 2700, "materials": {"essence_spark": 3, "herb_sun": 2}, "zen_cost": 180, "req_level": 2,
        "desc": "۱۰٪ دمیجِ بیشتر — ۴۵ دقیقه",
    },
    "elixir_fortune": {
        "name": "🥃 الکسیرِ اقبال", "kind": "buff", "buff_stat": "gold_find_pct", "buff_value": 0.15,
        "duration": 3600, "materials": {"essence_flow": 3, "herb_frost": 2}, "zen_cost": 260, "req_level": 3,
        "desc": "۱۵٪ شانسِ بیشترِ طلا — ۱ ساعت",
    },
    "elixir_wisdom": {
        "name": "🥃 الکسیرِ خرد", "kind": "buff", "buff_stat": "xp_pct", "buff_value": 0.15,
        "duration": 3600, "materials": {"essence_shadow": 2, "herb_ember": 2}, "zen_cost": 300, "req_level": 5,
        "desc": "۱۵٪ تجربه‌ی بیشتر — ۱ ساعت",
    },
    "elixir_titan": {
        "name": "🥃 الکسیرِ تایتان", "kind": "buff", "buff_stat": "max_hp_flat", "buff_value": 80,
        "duration": 5400, "materials": {"essence_radiant": 3, "herb_void": 3}, "zen_cost": 500, "req_level": 7,
        "desc": "۸۰ HPِ بیشتر — ۹۰ دقیقه",
    },
    # 🆕 راهِ سریعِ افزایشِ ضریبِ ضعفِ عنصری — قبلاً فقط از درختِ مهارت
    # (کند) و سطحِ ۷۲+ کاتانا (خیلی دیررس) قابلِ‌افزایش بود. این الکسیر
    # یه بونوسِ موقتِ قابل‌توجه می‌ده، بدونِ اینکه به اون دو مسیر دست بزنه.
    "elixir_elemental": {
        "name": "🥃 الکسیرِ تشدیدِ عنصری", "kind": "buff", "buff_stat": "elem_amp", "buff_value": 0.20,
        "duration": 3600, "materials": {"essence_chaos": 2, "herb_astral": 2}, "zen_cost": 450, "req_level": 6,
        "desc": "۲۰٪ ضریبِ ضعفِ عنصری بیشتر — ۱ ساعت (فقط وقتی حمله‌ت دقیقاً به ضعفِ دشمن می‌خوره اثر داره)",
    },
}

GEM_DEFS = [
    ("ruby",      "🔴 یاقوتِ‌آتشین",   "dmg_pct",     (0.02, 0.035, 0.06)),
    ("sapphire",  "🔵 یاقوت‌کبودِاستوار", "armor",     (3, 6, 11)),
    ("emerald",   "🟢 زمردِ‌جان‌گیر",  "lifesteal",   (0.008, 0.016, 0.028)),
    ("topaz",     "🟡 توپازِ‌تیزبین",  "crit_chance", (0.01, 0.02, 0.035)),
    ("amethyst",  "🟣 آمیتیستِ‌سرسخت", "max_hp",      (15, 30, 55)),
]


def _build_gem_recipes() -> dict:
    recipes = {}
    for stone, label, stat, values in GEM_DEFS:
        for power in (1, 2, 3):
            mat_tier = min(5, power * 2 - 1)
            herb = HERB_TIERS[mat_tier - 1]
            essence = ESSENCE_TIERS[mat_tier - 1]
            key = f"gem_{stone}_{power}"
            recipes[key] = {
                "gem_id": key, "label": f"{label} (توانِ {power})",
                "stat": stat, "value": values[power - 1],
                "materials": {herb: 1 + power, essence: 1 + power},
                "zen_cost": 150 * power * power,
                "req_level": power * 3 - 2,
            }
    return recipes


GEM_RECIPES = _build_gem_recipes()

SOUL_STONE_RECIPE = {
    "name": "🔮 سنگِ‌روح", "materials": {"essence_chaos": 5, "herb_astral": 5, "astral_dust": 3},
    "zen_cost": 5000, "req_level": 10,
    "desc": "بازغلتوندنِ کاملِ افیکس‌های یه تجهیز (Reroll) — کاربردش تو 🔨آهنگری",
}


def craft_potion(uid: int, player: dict, recipe_key: str) -> tuple[bool, str]:
    recipe = POTION_RECIPES.get(recipe_key)
    if not recipe:
        return False, "❌ دستورِ نامعتبر."
    c = get_crafting(player)
    if c["alchemy_level"] < recipe["req_level"]:
        return False, f"❌ به سطحِ کیمیاگریِ {recipe['req_level']} نیاز داری (الان: {c['alchemy_level']})."
    if not has_materials(player, recipe["materials"]):
        return False, f"❌ موادِ کافی نداری:\n{missing_materials_text(player, recipe['materials'])}"
    if player.get("zen", 0) < recipe["zen_cost"]:
        return False, f"❌ به {recipe['zen_cost']:,} Zen نیاز داری."
    _consume_materials(player, recipe["materials"])
    player["zen"] -= recipe["zen_cost"]
    add_material(player, recipe_key, 1, item_type="potion")
    logs = _gain_xp(player, "alchemy", recipe["req_level"] * 12)
    msg = f"🧪 ساختی: {recipe['name']} — {recipe['desc']}"
    if logs:
        msg += "\n" + "\n".join(logs)
    return True, msg


def craft_gem(uid: int, player: dict, gem_key: str) -> tuple[bool, str]:
    recipe = GEM_RECIPES.get(gem_key)
    if not recipe:
        return False, "❌ دستورِ نامعتبر."
    c = get_crafting(player)
    if c["alchemy_level"] < recipe["req_level"]:
        return False, f"❌ به سطحِ کیمیاگریِ {recipe['req_level']} نیاز داری (الان: {c['alchemy_level']})."
    if not has_materials(player, recipe["materials"]):
        return False, f"❌ موادِ کافی نداری:\n{missing_materials_text(player, recipe['materials'])}"
    if player.get("zen", 0) < recipe["zen_cost"]:
        return False, f"❌ به {recipe['zen_cost']:,} Zen نیاز داری."
    _consume_materials(player, recipe["materials"])
    player["zen"] -= recipe["zen_cost"]
    add_material(player, gem_key, 1, item_type="gem",
                 extra={"gem_stat": recipe["stat"], "gem_value": recipe["value"], "gem_label": recipe["label"]})
    logs = _gain_xp(player, "alchemy", recipe["req_level"] * 12)
    msg = f"💎 تراش دادی: {recipe['label']}"
    if logs:
        msg += "\n" + "\n".join(logs)
    return True, msg


def craft_soul_stone(uid: int, player: dict) -> tuple[bool, str]:
    recipe = SOUL_STONE_RECIPE
    c = get_crafting(player)
    if c["alchemy_level"] < recipe["req_level"]:
        return False, f"❌ به سطحِ کیمیاگریِ {recipe['req_level']} (بیشینه) نیاز داری."
    if not has_materials(player, recipe["materials"]):
        return False, f"❌ موادِ کافی نداری:\n{missing_materials_text(player, recipe['materials'])}"
    if player.get("zen", 0) < recipe["zen_cost"]:
        return False, f"❌ به {recipe['zen_cost']:,} Zen نیاز داری."
    _consume_materials(player, recipe["materials"])
    player["zen"] -= recipe["zen_cost"]
    add_material(player, "soul_stone", 1, item_type="material")
    return True, "🔮 یه **سنگِ‌روح** ساختی! می‌تونی باهاش افیکسِ یه تجهیز رو بازغلتونی."


# ─── مصرفِ پوشن ────────────────────────────────────────────────
def drink_potion(uid: int, player: dict, recipe_key: str) -> tuple[bool, str]:
    recipe = POTION_RECIPES.get(recipe_key)
    if not recipe:
        return False, "❌ پوشنِ نامعتبر."
    inv = player.setdefault("inventory", [])
    entry = next((it for it in inv if it.get("type") == "potion" and it.get("material_id") == recipe_key), None)
    if not entry or entry.get("qty", 0) <= 0:
        return False, f"❌ {recipe['name']} نداری — اول بسازش."
    entry["qty"] -= 1
    if entry["qty"] <= 0:
        inv.remove(entry)

    if recipe["kind"] == "heal":
        max_hp = player.get("max_hp", 100)
        heal = int(max_hp * recipe["heal_pct"])
        player["hp"] = min(max_hp, player.get("hp", 0) + heal)
        return True, f"💚 {recipe['name']} رو خوردی — {heal} HP درمان شدی. (HP: {player['hp']}/{max_hp})"

    clean_expired_potion_buffs(player)
    buffs = player.setdefault("active_potion_buffs", {})
    stat = recipe["buff_stat"]
    was_active = stat in buffs
    buffs[stat] = {"value": recipe["buff_value"], "expires_at": time.time() + recipe["duration"], "name": recipe["name"]}
    verb = "تازه شد" if was_active else "فعال شد"
    return True, f"🥃 {recipe['name']} رو خوردی — باف {verb}: {recipe['desc']}"


def clean_expired_potion_buffs(player: dict) -> bool:
    buffs = player.get("active_potion_buffs", {})
    now = time.time()
    changed = False
    for stat in list(buffs.keys()):
        if buffs[stat].get("expires_at", 0) <= now:
            del buffs[stat]
            changed = True
    return changed


def get_potion_bonus_stats(player: dict) -> dict:
    """مثلِ get_food_bonus_stats — item_system.combat_bonus_stats صداش می‌زنه."""
    clean_expired_potion_buffs(player)
    out: dict = {}
    for stat, b in player.get("active_potion_buffs", {}).items():
        out[stat] = out.get(stat, 0) + b.get("value", 0)
    return out


def active_potion_buffs_text(player: dict) -> str:
    clean_expired_potion_buffs(player)
    buffs = player.get("active_potion_buffs", {})
    if not buffs:
        return "— هیچ الکسیرِ فعالی نداری —"
    now = time.time()
    lines = []
    for stat, b in buffs.items():
        remain = int(b["expires_at"] - now)
        m, s = divmod(max(0, remain), 60)
        val = b["value"]
        val_txt = f"{val:+.0%}" if isinstance(val, float) else f"{val:+d}"
        lines.append(f"  {b['name']} {val_txt} ({m}m مونده)")
    return "\n".join(lines)


# ============================================================
#  ۵) سوکت/جم — پرکردنِ سوکتِ خالیِ تجهیزات
# ============================================================
def _find_item(player: dict, item_id: str) -> dict | None:
    for it in player.get("inventory", []):
        if it.get("item_id") == item_id or it.get("id") == item_id:
            return it
    for it in (player.get("equipped", {}) or {}).values():
        if it and (it.get("item_id") == item_id or it.get("id") == item_id):
            return it
    return None


def insert_gem(uid: int, player: dict, item_id: str, gem_key: str) -> tuple[bool, str]:
    item = _find_item(player, item_id)
    if not item:
        return False, "❌ اون تجهیز رو پیدا نکردم."
    sockets = item.get("sockets", [])
    empty = next((s for s in sockets if not s.get("gem")), None)
    if not empty:
        return False, "❌ این تجهیز سوکتِ خالی نداره."
    inv = player.setdefault("inventory", [])
    gem_entry = next((it for it in inv if it.get("type") == "gem" and it.get("material_id") == gem_key), None)
    if not gem_entry or gem_entry.get("qty", 0) <= 0:
        return False, "❌ این جم رو نداری."
    gem_entry["qty"] -= 1
    if gem_entry["qty"] <= 0:
        inv.remove(gem_entry)
    empty["gem"] = {
        "id": gem_key, "stat": gem_entry.get("gem_stat"), "value": gem_entry.get("gem_value"),
        "label": gem_entry.get("gem_label"),
    }
    item["item_score"] = isy.calculate_item_score(item)
    return True, f"💠 {gem_entry.get('gem_label', gem_key)} رو تو {item['emoji']} **{item['name']}** سوکت کردی."


# ============================================================
#  ۶) بازغلتوندنِ افیکس (Soul Stone) — کاربردِ واقعیِ سنگِ‌روح
# ============================================================
def reroll_affixes(uid: int, player: dict, item_id: str) -> tuple[bool, str]:
    if material_qty(player, "soul_stone") < 1:
        return False, "❌ سنگِ‌روح نداری — اول تو 🧪کیمیاگری بسازش."
    item = _find_item(player, item_id)
    if not item:
        return False, "❌ اون تجهیز رو پیدا نکردم."
    _consume_materials(player, {"soul_stone": 1})
    item["affixes"] = isy.generate_affixes(item.get("rarity", "common"))
    item["item_score"] = isy.calculate_item_score(item)
    return True, f"🔮 افیکس‌های {item['emoji']} **{item['name']}** بازغلتوند شد!\n" + isy.format_item_card(item)


# ============================================================
#  ۷) تجزیه (Salvage) — تبدیلِ تجهیزِ ناخواسته به موادِ خام
# ============================================================
def salvage_item(uid: int, player: dict, item_id: str) -> tuple[bool, str]:
    equipped = player.get("equipped", {}) or {}
    if any(it and (it.get("item_id") == item_id or it.get("id") == item_id) for it in equipped.values()):
        return False, "❌ این تجهیز الان روته — اول درش بیار."
    inv = player.setdefault("inventory", [])
    item = next((it for it in inv if it.get("item_id") == item_id or it.get("id") == item_id), None)
    if not item or item.get("slot") not in isy.EQUIP_SLOTS:
        return False, "❌ این آیتم قابلِ تجزیه نیست."

    ridx = isy.rarity_index(item.get("rarity", "common"))
    tier = min(5, ridx // 2 + 1)
    ore, beast = ORE_TIERS[tier - 1], BEAST_TIERS[tier - 1]
    ore_qty = 1 + ridx // 3
    beast_qty = 1 + ridx // 4

    inv.remove(item)
    add_material(player, ore, ore_qty)
    add_material(player, beast, beast_qty)
    gained = [f"{ore_qty}×{_mat(ore)['emoji']}{_mat(ore)['name']}", f"{beast_qty}×{_mat(beast)['emoji']}{_mat(beast)['name']}"]
    if ridx >= 6 and random.random() < 0.35:
        add_material(player, "astral_dust", 1)
        gained.append(f"1×{_mat('astral_dust')['emoji']}{_mat('astral_dust')['name']}")

    return True, f"♻️ {item['emoji']} **{item['name']}** رو تجزیه کردی و گرفتی: " + " | ".join(gained)


# ============================================================
#  ۸) هوکِ دراپِ مواد از کشتنِ هیولا (loot_engine صداش می‌زنه)
# ============================================================
DROP_CHANCE = 0.06          # شانسِ خامِ افتادنِ یه ماده به‌ازای هر کشتار — کوچیک و مکمل؛
                             # منبعِ اصلیِ مواد الان gathering_system.py (کاوشِ فعال) ـه
BOSS_DROP_MULT = 3.0


def maybe_drop_material(player: dict, is_boss: bool, player_level: int) -> dict | None:
    chance = DROP_CHANCE * (BOSS_DROP_MULT if is_boss else 1.0)
    if random.random() > chance:
        return None
    max_tier = min(5, 1 + player_level // 15) if not is_boss else min(5, 2 + player_level // 12)
    tier = random.randint(1, max_tier)
    pool = random.choice([ORE_TIERS, BEAST_TIERS, HERB_TIERS, ESSENCE_TIERS])
    mat_id = pool[tier - 1]
    qty = random.randint(1, 2)
    add_material(player, mat_id, qty)
    m = _mat(mat_id)
    return {"mat_id": mat_id, "qty": qty, "name": m["name"], "emoji": m["emoji"]}


# ============================================================
#  ۹) متن‌های نمایشی برای هندلرها
# ============================================================
def crafting_summary_text(player: dict) -> str:
    c = get_crafting(player)
    lines = [
        "🛠 **کارگاهِ کرفت**",
        f"🔨 آهنگری: سطح {c['forge_level']}/{CRAFT_LEVEL_CAP}  ({c['forge_xp']}/{xp_needed(c['forge_level']) if c['forge_level']<CRAFT_LEVEL_CAP else '—'} XP)",
        f"🧪 کیمیاگری: سطح {c['alchemy_level']}/{CRAFT_LEVEL_CAP}  ({c['alchemy_xp']}/{xp_needed(c['alchemy_level']) if c['alchemy_level']<CRAFT_LEVEL_CAP else '—'} XP)",
        "",
        "🔥 **الکسیرِ فعال:**", active_potion_buffs_text(player), "",
        "🎒 **موادِ خام:**",
    ]
    seen = set()
    any_mat = False
    for mid in MATERIALS:
        if mid in seen:
            continue
        seen.add(mid)
        have = material_qty(player, mid)
        if have > 0:
            any_mat = True
            m = _mat(mid)
            lines.append(f"  {m['emoji']} {m['name']}: {have}")
    if not any_mat:
        lines.append("  — چیزی نداری؛ هیولا بکش یا تجهیز تجزیه کن —")
    return "\n".join(lines)


def forge_slot_menu_text(player: dict, slot: str) -> str:
    c = get_crafting(player)
    lines = [f"🔨 **{SLOT_LABELS[slot]}** — انتخابِ تیر:", ""]
    for tier in range(1, 6):
        recipe = FORGE_RECIPES[f"{slot}_t{tier}"]
        lock = "🔒" if c["forge_level"] < recipe["req_level"] else "🔓"
        lines.append(
            f"{lock} تیر {tier} ({isy.RARITY_DATA[recipe['rarity']]['label']}) — "
            f"نیازِ سطح {recipe['req_level']} | 💰{recipe['zen_cost']:,} | "
            f"{missing_materials_text(player, recipe['materials'])}"
        )
    return "\n".join(lines)
