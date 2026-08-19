# ============================================================
#  ASTRAL ABYSS — Collection Codex (تحویلِ متریال به NPC)
# ------------------------------------------------------------
#  برای هر نقشه، اگه یه‌دونه از هر ۵ تا آیتمِ متریالِ اون نقشه رو
#  داشته باشی، می‌تونی تحویلِ نگهبانِ اون منطقه بدی و یه پاداشِ
#  یک‌جای Zen/XP بگیری. برخلافِ map_recipes (که موادو صرفِ ساختِ
#  یه تجهیز می‌کنه)، این مسیر قابلِ‌تکراره — چون این متریال‌ها
#  به‌وفور از نقشه‌ها دراپ می‌شن و نباید فقط یه‌بار مصرف باشن.
#  هر نقشه جدا کول‌داون داره.
# ============================================================
from __future__ import annotations

import time

COOLDOWN_SECONDS = 4 * 3600  # هر نقشه هر ۴ ساعت یه‌بار قابلِ تحویله

TIER_REWARD = {
    "common": {"zen": 800,  "xp": 40},
    "rare":   {"zen": 2000, "xp": 100},
    "epic":   {"zen": 5000, "xp": 220},
}


def _cooldowns(player: dict) -> dict:
    return player.setdefault("codex_cooldowns", {})


def _count_named(player: dict, name: str) -> int:
    return sum(1 for it in player.get("inventory", []) if it.get("name") == name)


def _map_set(map_name: str) -> dict:
    from economy import MAP_LOOT
    return {it["name"]: 1 for it in MAP_LOOT.get(map_name, [])}


def has_full_set(player: dict, map_name: str) -> bool:
    materials = _map_set(map_name)
    if not materials:
        return False
    return all(_count_named(player, name) >= need for name, need in materials.items())


def missing_set_text(player: dict, map_name: str) -> str:
    materials = _map_set(map_name)
    parts = []
    for name, need in materials.items():
        have = _count_named(player, name)
        mark = "✅" if have >= need else "❌"
        parts.append(f"{mark} {name}")
    return "\n".join(parts)


def cooldown_remaining(player: dict, map_name: str) -> int:
    ready_at = _cooldowns(player).get(map_name, 0)
    return max(0, int(ready_at - time.time()))


def _consume_set(player: dict, materials: dict) -> None:
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


def turn_in(player: dict, map_name: str) -> tuple[bool, str, dict | None]:
    from economy import MAPS_DATA
    materials = _map_set(map_name)
    if not materials:
        return False, "❌ این نقشه ستِ کالکشن نداره.", None

    remaining = cooldown_remaining(player, map_name)
    if remaining > 0:
        h, m = divmod(remaining // 60, 60)
        return False, f"⏳ این نقشه {h} ساعت و {m} دقیقه‌ی دیگه دوباره قابلِ تحویله.", None

    if not has_full_set(player, map_name):
        return False, f"❌ ستِ کامل نداری:\n{missing_set_text(player, map_name)}", None

    _consume_set(player, materials)

    map_tier = MAPS_DATA.get(map_name, {}).get("tier", "common")
    reward = TIER_REWARD.get(map_tier, TIER_REWARD["common"])
    player["zen"] = player.get("zen", 0) + reward["zen"]
    player["xp"] = player.get("xp", 0) + reward["xp"]

    _cooldowns(player)[map_name] = time.time() + COOLDOWN_SECONDS

    emoji = MAPS_DATA.get(map_name, {}).get("emoji", "🗺️")
    msg = (f"📯 ستِ **{map_name}** {emoji} رو تحویل دادی!\n"
           f"💰 +{reward['zen']:,} Zen | ✨ +{reward['xp']} XP")
    return True, msg, reward
