# ============================================================
#  ASTRAL ABYSS — Home Defense Traps (سیستمِ واقعیِ آیتم‌های دفاعیِ بازارِ سیاه)
# ------------------------------------------------------------
#  قبلاً: خریدِ economy.DEFENSE_ITEMS فقط یه آیتمِ تزئینی با
#  type="defense" تو انبار می‌ذاشت که هیچ‌جای بازی خونده نمی‌شد —
#  امنیتِ واقعیِ خونه فقط از house_system.FURNITURE (وسایلِ دائمی)
#  می‌اومد. این فایل اون آیتم‌ها رو تبدیل به «تله»های نصب‌شدنی می‌کنه:
#
#    🪤 نصب: آیتمِ خریداری‌شده رو از انبار برمی‌داری و رو خونه نصب می‌کنی.
#    ⚡ فعال‌سازی: هر بار کسی سعیِ دزدی می‌کنه، یکی از تله‌های نصب‌شده
#       به‌صورتِ تصادفی فعال می‌شه (یه‌بارمصرف) و یه بونوسِ امنیتیِ
#       بزرگ فقط برای همون یه حمله می‌ده — جدا از امتیازِ دائمیِ وسایل.
#
#  فقط از رویِ economy.DEFENSE_ITEMS و player["house"] کار می‌کنه؛
#  هیچ فایلِ قدیمی رو نمی‌شکنه (فقط house_system یه هوکِ اختیاری می‌گیره).
# ============================================================
from __future__ import annotations

import random

from economy import DEFENSE_ITEMS

DEFENSE_ITEM_MAP: dict[str, dict] = {i["name"]: i for i in DEFENSE_ITEMS}

# هر بار فعال شدن، این‌قدر امتیازِ امنیتِ موقت (فقط برای همون حمله) می‌ده
RARITY_TRIGGER_BONUS = {"rare": 10, "epic": 18}
BASE_TRAP_SLOTS = 2
TRAP_SLOTS_PER_TIER = 2


def ensure_traps(house: dict) -> dict:
    return house.setdefault("traps", {})


def max_trap_slots(house: dict) -> int:
    return BASE_TRAP_SLOTS + house.get("tier", 0) * TRAP_SLOTS_PER_TIER


def installed_count(house: dict) -> int:
    return sum(ensure_traps(house).values())


def owned_uninstalled(player: dict) -> dict[str, int]:
    """آیتم‌های دفاعیِ خریداری‌شده که هنوز تو انبارن (نصب‌نشده)."""
    counts: dict[str, int] = {}
    for it in player.get("inventory", []):
        if it.get("type") == "defense" and it.get("name") in DEFENSE_ITEM_MAP:
            counts[it["name"]] = counts.get(it["name"], 0) + 1
    return counts


def install_trap(player: dict, house: dict, item_name: str) -> tuple[bool, str]:
    if item_name not in DEFENSE_ITEM_MAP:
        return False, "❌ این تله شناخته‌شده نیست."

    inv = player.get("inventory", [])
    idx = next((i for i, it in enumerate(inv)
                if it.get("name") == item_name and it.get("type") == "defense"), None)
    if idx is None:
        return False, "❌ این تله رو تو انبارت نداری (اول از 🖤 بازارِ سیاه ›› 🏰 دفاعِ پایگاه بخر)."

    if installed_count(house) >= max_trap_slots(house):
        return False, (f"❌ ظرفیتِ نصبِ خونه‌ت پره ({max_trap_slots(house)} تله). "
                        f"یا خونه رو ارتقا بده تا ظرفیت بیشتر شه، یا یکی از تله‌های نصب‌شده رو بردار.")

    del inv[idx]
    traps = ensure_traps(house)
    traps[item_name] = traps.get(item_name, 0) + 1
    item = DEFENSE_ITEM_MAP[item_name]
    return True, f"✅ {item['emoji']} {item_name} رو نصب کردی. دفعه‌ی بعد که کسی بخواد ملکت رو بدزده، یه تله فعال می‌شه."


def uninstall_trap(house: dict, item_name: str) -> tuple[bool, str]:
    traps = ensure_traps(house)
    if traps.get(item_name, 0) <= 0:
        return False, "❌ این تله نصب نیست."
    traps[item_name] -= 1
    if traps[item_name] <= 0:
        del traps[item_name]
    return True, f"↩️ {item_name} از خونه برداشته شد (تله‌ها یک‌بارمصرفن، به انبار برنمی‌گرده)."


def trigger_defense(house: dict) -> tuple[int, str | None]:
    """یه تله‌ی نصب‌شده رو تصادفی فعال و مصرف می‌کنه.
    خروجی: (بونوسِ امنیتِ موقت برای همین حمله, نامِ تله یا None اگه تله‌ای نصب نبود)."""
    traps = ensure_traps(house)
    pool: list[str] = []
    for name, cnt in traps.items():
        if cnt > 0 and name in DEFENSE_ITEM_MAP:
            pool.extend([name] * cnt)
    if not pool:
        return 0, None

    pick = random.choice(pool)
    traps[pick] -= 1
    if traps[pick] <= 0:
        del traps[pick]

    item = DEFENSE_ITEM_MAP[pick]
    bonus = RARITY_TRIGGER_BONUS.get(item.get("rarity"), 8)
    return bonus, pick


def traps_text(house: dict) -> str:
    traps = ensure_traps(house)
    if not traps:
        return "🪤 هیچ تله‌ای نصب نیست."
    parts = []
    for name, cnt in traps.items():
        item = DEFENSE_ITEM_MAP.get(name, {})
        parts.append(f"{item.get('emoji','🪤')} {name} ×{cnt}")
    return f"🪤 تله‌های نصب‌شده ({installed_count(house)}/{max_trap_slots(house)}): " + "، ".join(parts)
