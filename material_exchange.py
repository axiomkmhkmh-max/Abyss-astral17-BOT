# ============================================================
#  ASTRAL ABYSS — Material Exchange (صرافیِ متریال)
# ------------------------------------------------------------
#  متریال‌های نقشه‌ای (economy.MAP_LOOT — Sand Crystal، Divine Shard،
#  Dragon Heart و امثالش) از اول قرار بوده فقط قابل‌فروش باشن —
#  هیچ‌جای کد مصرفشون نمی‌کنه. این ماژول یه صرافی می‌سازه که این
#  آیتم‌ها رو تبدیل می‌کنه به موادِ خامِ crafting_system.py (که واقعاً
#  تو Forge/Alchemy مصرف می‌شن).
#
#  هیچ فایلِ قدیمی رو خراب نمی‌کنه: فقط از economy (برای اسم‌ها) و
#  crafting_system (برای mat_id/add_material) می‌خونه.
# ============================================================
from __future__ import annotations

import crafting_system as cfs

# رریتیِ نقشه‌ای (economy.MAP_LOOT فقط از این ۵ تا استفاده می‌کنه) → تیرِ کرفت
RARITY_TO_TIER = {"common": 1, "uncommon": 2, "rare": 3, "epic": 4, "legendary": 5}
# هرچی رریتیِ آیتمِ ورودی پایین‌تر باشه، تعدادِ خروجی بیشتره (جبرانِ کمیابی)
RARITY_YIELD = {"common": 3, "uncommon": 2, "rare": 2, "epic": 2, "legendary": 2}

CATEGORY_LABELS = {
    "ore":     "🪨 سنگِ‌معدن (آهنگری)",
    "beast":   "🦴 اجزای‌هیولا (آهنگری)",
    "herb":    "🌿 گیاه (کیمیاگری)",
    "essence": "💧 جوهر/عصاره (کیمیاگری)",
}
CATEGORY_TIERS = {
    "ore": cfs.ORE_TIERS, "beast": cfs.BEAST_TIERS,
    "herb": cfs.HERB_TIERS, "essence": cfs.ESSENCE_TIERS,
}

_MAP_NAMES_CACHE: set[str] | None = None


def map_material_names() -> set[str]:
    """اسمِ همه‌ی آیتم‌های نقشه‌ای (از economy.MAP_LOOT) — کش می‌شه چون تغییر نمی‌کنه."""
    global _MAP_NAMES_CACHE
    if _MAP_NAMES_CACHE is None:
        from economy import MAP_LOOT
        names = set()
        for items in MAP_LOOT.values():
            for it in items:
                names.add(it["name"])
        _MAP_NAMES_CACHE = names
    return _MAP_NAMES_CACHE


def is_exchangeable(item: dict) -> bool:
    """آیتمِ نقشه‌ایِ خامه — نه متریالِ کرفتِ استک‌شده، نه تجهیزِ قابل‌اکیپ."""
    if item.get("type") in ("material", "gem", "potion"):
        return False
    if item.get("slot"):
        return False
    return item.get("name") in map_material_names()


def exchangeable_items(player: dict) -> list[tuple[int, dict]]:
    inv = player.get("inventory", [])
    return [(i, it) for i, it in enumerate(inv) if is_exchangeable(it)]


def preview_output(item: dict, category: str) -> tuple[str, str, int]:
    """(mat_id, برچسبِ نمایشی, تعداد) که این آیتم اگه تبدیل بشه بهش می‌رسه."""
    rarity = item.get("rarity", "common")
    tier = RARITY_TO_TIER.get(rarity, 1)
    qty = RARITY_YIELD.get(rarity, 1)
    mat_id = CATEGORY_TIERS[category][tier - 1]
    m = cfs.MATERIALS.get(mat_id, {"name": mat_id, "emoji": "📦"})
    return mat_id, f"{m['emoji']} {m['name']}", qty


def convert_one(player: dict, inv_index: int, category: str) -> tuple[bool, str]:
    inv = player.setdefault("inventory", [])
    if inv_index >= len(inv) or not is_exchangeable(inv[inv_index]):
        return False, "❌ این آیتم دیگه قابل‌تبدیل نیست."
    item = inv.pop(inv_index)
    mat_id, mat_label, qty = preview_output(item, category)
    cfs.add_material(player, mat_id, qty)
    return True, f"🔄 {item.get('emoji','📦')} {item['name']} ← {qty}x {mat_label}"


def convert_all(player: dict, category: str) -> tuple[int, dict]:
    """همه‌ی آیتم‌های نقشه‌ایِ کوله‌پشتی رو یک‌جا تبدیل می‌کنه.
    برمی‌گردونه (تعدادِ آیتمِ تبدیل‌شده, {برچسبِ‌متریال: تعدادِ‌کل})."""
    inv = list(player.get("inventory", []))
    keep = []
    gained_ids: dict[str, int] = {}
    count = 0
    for it in inv:
        if is_exchangeable(it):
            mat_id, _label, qty = preview_output(it, category)
            gained_ids[mat_id] = gained_ids.get(mat_id, 0) + qty
            count += 1
        else:
            keep.append(it)
    player["inventory"] = keep

    gained_labels: dict[str, int] = {}
    for mat_id, qty in gained_ids.items():
        cfs.add_material(player, mat_id, qty)
        m = cfs.MATERIALS.get(mat_id, {"name": mat_id, "emoji": "📦"})
        gained_labels[f"{m['emoji']} {m['name']}"] = qty
    return count, gained_labels
