# ============================================================
#  ASTRAL ABYSS — Map Recipes (دستورهای ویژه‌ی نقشه)
# ------------------------------------------------------------
#  هر نقشه ۵ تا آیتمِ متریالِ خودش رو داره (economy.MAP_LOOT) که
#  قبلاً هیچ مصرفی نداشتن. این ماژول یه دستورِ کرفتِ مخصوصِ هر نقشه
#  می‌سازه: یه‌دونه از هر ۵ تا آیتمِ اون نقشه رو بده + یه هزینه‌ی Zen،
#  یه تجهیزِ تصادفیِ تضمین‌شده بگیر — رریتی بر اساسِ تیرِ نقشه
#  (common→epic, rare→mythic, epic→legendary).
# ============================================================
from __future__ import annotations

import random
import item_system as isy

TIER_RARITY    = {"common": "epic", "rare": "mythic", "epic": "legendary"}
TIER_REQ_LEVEL = {"common": 8, "rare": 18, "epic": 30}


def _build_map_recipes() -> dict:
    from economy import MAP_LOOT, MAPS_DATA
    recipes = {}
    for map_name, items in MAP_LOOT.items():
        map_tier = MAPS_DATA.get(map_name, {}).get("tier", "common")
        materials = {it["name"]: 1 for it in items}
        zen_cost = sum(it["sell"] for it in items) // 3
        recipes[map_name] = {
            "materials": materials,
            "forced_rarity": TIER_RARITY.get(map_tier, "epic"),
            "req_level": TIER_REQ_LEVEL.get(map_tier, 8),
            "zen_cost": zen_cost,
            "emoji": MAPS_DATA.get(map_name, {}).get("emoji", "🗺️"),
        }
    return recipes


MAP_RECIPES = _build_map_recipes()


def _count_named(player: dict, name: str) -> int:
    return sum(1 for it in player.get("inventory", []) if it.get("name") == name)


def has_map_materials(player: dict, map_name: str) -> bool:
    recipe = MAP_RECIPES.get(map_name)
    if not recipe:
        return False
    return all(_count_named(player, name) >= need for name, need in recipe["materials"].items())


def missing_map_materials_text(player: dict, map_name: str) -> str:
    recipe = MAP_RECIPES[map_name]
    parts = []
    for name, need in recipe["materials"].items():
        have = _count_named(player, name)
        mark = "✅" if have >= need else "❌"
        parts.append(f"{mark} {name}: {have}/{need}")
    return "\n".join(parts)


def _consume_named(player: dict, materials: dict) -> None:
    inv = player.get("inventory", [])
    for name, need in materials.items():
        removed = 0
        new_inv = []
        for it in inv:
            if removed < need and it.get("name") == name:
                removed += 1
                continue
            new_inv.append(it)
        inv = new_inv
    player["inventory"] = inv


def craft_map_item(player: dict, map_name: str) -> tuple[bool, str, dict | None]:
    recipe = MAP_RECIPES.get(map_name)
    if not recipe:
        return False, "❌ این نقشه دستورِ ویژه نداره.", None
    if player.get("level", 1) < recipe["req_level"]:
        return False, f"❌ به سطحِ {recipe['req_level']} نیاز داری (الان: {player.get('level',1)}).", None
    if not has_map_materials(player, map_name):
        return False, f"❌ موادِ کافی نداری:\n{missing_map_materials_text(player, map_name)}", None
    if player.get("zen", 0) < recipe["zen_cost"]:
        return False, f"❌ به {recipe['zen_cost']:,} Zen نیاز داری.", None

    _consume_named(player, recipe["materials"])
    player["zen"] -= recipe["zen_cost"]

    slot = random.choice(isy.EQUIP_SLOTS)
    template = {**random.choice(isy.EQUIPMENT_TEMPLATES[slot]), "slot": slot}
    item = isy.generate_item(template, player.get("level", 1), forced_rarity=recipe["forced_rarity"],
                              drop_source=f"maprecipe:{map_name}")
    player.setdefault("inventory", []).append(item)

    msg = (f"{recipe['emoji']} با موادِ **{map_name}** ساختی:\n"
           f"{item['emoji']} **{item['name']}** ({isy.RARITY_DATA[item['rarity']]['label']}) "
           f"⭐ Item Score: {item['item_score']}")
    return True, msg, item
