# ============================================================
#  ASTRAL ABYSS RPG — Fog of War 🗺️
#  هر نقشه ۴ زیرمنطقه‌ی نام‌دار داره (economy.MAP_LOCATIONS). تا وقتی
#  بازیکن اولین‌بار وارد یه زیرمنطقه نشده، به‌جای اسم واقعیش یه
#  سایه‌ی مه‌آلود («🌫️ ???») نشون داده می‌شه. اولین ورود = کشف
#  + یه پاداش کوچیکِ یه‌باره‌ی اکتشاف.
# ============================================================
import random

DISCOVERY_ZEN = (80, 200)
DISCOVERY_XP = (30, 80)


def _explored_set(player: dict, map_name: str) -> set:
    fog = player.setdefault("explored", {})
    return set(fog.setdefault(map_name, []))


def is_explored(player: dict, map_name: str, loc_idx: int) -> bool:
    return loc_idx in player.get("explored", {}).get(map_name, [])


def mark_explored(player: dict, map_name: str, loc_idx: int) -> bool:
    """اگه اولین‌باره، ثبتش می‌کنه و True برمی‌گردونه (یعنی باید پاداش داد)."""
    fog = player.setdefault("explored", {})
    lst = fog.setdefault(map_name, [])
    if loc_idx in lst:
        return False
    lst.append(loc_idx)
    return True


def explored_count(player: dict, map_name: str) -> int:
    return len(player.get("explored", {}).get(map_name, []))


def grant_discovery_reward(player: dict) -> dict:
    zen = random.randint(*DISCOVERY_ZEN)
    xp = random.randint(*DISCOVERY_XP)
    player["zen"] = player.get("zen", 0) + zen
    player["xp"] = player.get("xp", 0) + xp
    return {"zen": zen, "xp": xp}


def map_progress_text(player: dict, map_name: str, total: int) -> str:
    done = explored_count(player, map_name)
    filled = "🟩" * done + "⬛" * (total - done)
    return f"🗺️ اکتشاف: {filled} ({done}/{total})"
