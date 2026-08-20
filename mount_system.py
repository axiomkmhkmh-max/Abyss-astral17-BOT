# ============================================================
#  ASTRAL ABYSS — Mount System 🐎 (سیستمِ سواری)
# ------------------------------------------------------------
#  مونت‌ها جدا از pet_system هستن: pet یه همراهِ کمکیه، mount یه
#  سلاح/ابزارِ نبردیه که سوار می‌شی و مستقیم به Combat Power اضافه
#  می‌کنه. فقط یه مونت هم‌زمان فعال می‌تونه باشه (player["active_mount"]).
#  کسب: فروشگاهِ Echo Shard (خروجیِ Rift Dive)، یا Zen، یا دراپِ نادر
#  از باس‌های جهانی (بعداً با mount_id تو لوت‌تیبل قابلِ اتصاله).
# ============================================================
import random

RARITY_ORDER = ["common", "rare", "epic", "legendary", "mythic"]
RARITY_LABELS = {
    "common": "⚪ معمولی", "rare": "🔵 نادر", "epic": "🟣 حماسی",
    "legendary": "🟠 افسانه‌ای", "mythic": "🔴 اسطوره‌ای",
}

# ─── کاتالوگِ مونت‌ها ────────────────────────────────────────────
# power: سهمِ خام برای combat_power (بعد از ضرب‌شدن در WEIGHTS["mount"])
# price_shards / price_zen: یکی از این دو برای خریدِ فروشگاهی پر می‌شه
MOUNTS = {
    "dust_hound":     {"name": "🐕 سگِ گردوغبار",      "rarity": "common",    "power": 40,   "price_shards": 15},
    "ash_wolf":       {"name": "🐺 گرگِ خاکستر",        "rarity": "common",    "power": 55,   "price_shards": 22},
    "iron_boar":      {"name": "🐗 گرازِ آهنین",         "rarity": "rare",      "power": 120,  "price_shards": 45},
    "storm_falcon":   {"name": "🦅 شاهینِ توفان",        "rarity": "rare",      "power": 150,  "price_shards": 60},
    "obsidian_ram":   {"name": "🐏 قوچِ ابسیدینی",       "rarity": "rare",      "power": 170,  "price_shards": 70},
    "spectral_steed": {"name": "🐴 اسبِ روح",           "rarity": "epic",      "power": 320,  "price_shards": 140},
    "void_panther":   {"name": "🐆 پلنگِ خلاء",          "rarity": "epic",      "power": 360,  "price_shards": 160},
    "cinder_drake":   {"name": "🐉 اژدهاکِ خاکستر",      "rarity": "epic",      "power": 400,  "price_shards": 180},
    "abyssal_wyrm":   {"name": "🐲 کرمِ آبیس",           "rarity": "legendary", "power": 750,  "price_shards": 380},
    "seraph_charger": {"name": "🕊 توسنِ سرافیم",        "rarity": "legendary", "power": 820,  "price_shards": 420},
    "eclipse_tiger":  {"name": "🐅 ببرِ خسوف",           "rarity": "legendary", "power": 880,  "price_shards": 460},
    "kiarash_shade":  {"name": "👤 سایه‌ی کیارَش",       "rarity": "mythic",    "power": 1600, "price_shards": 900},
}

def get_mount(mount_id: str) -> dict | None:
    return MOUNTS.get(mount_id)

def owned_mounts(player: dict) -> list[str]:
    return player.get("owned_mounts", [])

def active_mount_id(player: dict) -> str | None:
    return player.get("active_mount")

def mount_power_bonus(player: dict) -> float:
    mid = player.get("active_mount")
    if not mid:
        return 0.0
    m = MOUNTS.get(mid)
    return float(m["power"]) if m else 0.0

def owns(player: dict, mount_id: str) -> bool:
    return mount_id in owned_mounts(player)

def grant_mount(player: dict, mount_id: str) -> bool:
    """یه مونت رو به‌صورت مستقیم (دراپ/جایزه) به بازیکن می‌ده. اگه از قبل
    داشت False برمی‌گردونه (برای پرهیز از پیامِ تکراری)."""
    if mount_id not in MOUNTS:
        return False
    owned = player.setdefault("owned_mounts", [])
    if mount_id in owned:
        return False
    owned.append(mount_id)
    return True

def equip_mount(player: dict, mount_id: str) -> tuple[bool, str]:
    if not owns(player, mount_id):
        return False, "❌ این مونت رو نداری."
    player["active_mount"] = mount_id
    m = MOUNTS[mount_id]
    return True, f"✅ {m['name']} رو سوار شدی."

def unequip_mount(player: dict) -> str:
    player["active_mount"] = None
    return "✅ از مونت پیاده شدی."

def buy_with_shards(player: dict, mount_id: str) -> tuple[bool, str]:
    m = MOUNTS.get(mount_id)
    if not m:
        return False, "❌ مونتِ نامعتبر."
    if owns(player, mount_id):
        return False, "❌ این مونت رو از قبل داری."
    price = m.get("price_shards")
    if price is None:
        return False, "❌ این مونت تو فروشگاهِ Shard موجود نیست."
    if player.get("rift_shards", 0) < price:
        return False, f"❌ Echo Shard کافی نداری (نیاز: {price:,} 🔹 — الان: {player.get('rift_shards',0):,})."
    player["rift_shards"] -= price
    grant_mount(player, mount_id)
    return True, f"✅ {m['name']} خریداری شد! (-{price:,} 🔹)"

def shop_listing(player: dict) -> list[dict]:
    """برای نمایشِ فروشگاه — هرکدوم رو با وضعیتِ owned/lock نشون می‌ده."""
    rows = []
    for mid, m in MOUNTS.items():
        rows.append({
            "id": mid, "name": m["name"], "rarity": m["rarity"],
            "power": m["power"], "price_shards": m.get("price_shards"),
            "owned": owns(player, mid),
        })
    order = {r: i for i, r in enumerate(RARITY_ORDER)}
    rows.sort(key=lambda r: (order.get(r["rarity"], 9), r["price_shards"] or 0))
    return rows

def collection_text(player: dict) -> str:
    owned = owned_mounts(player)
    active = active_mount_id(player)
    lines = [f"🐎 **کالکشنِ مونت‌ها** ({len(owned)}/{len(MOUNTS)})\n"]
    if not owned:
        lines.append("هنوز هیچ مونتی نداری — از فروشگاه با Echo Shard بخر.")
        return "\n".join(lines)
    order = {r: i for i, r in enumerate(RARITY_ORDER)}
    for mid in sorted(owned, key=lambda x: order.get(MOUNTS[x]["rarity"], 9)):
        m = MOUNTS[mid]
        tag = " 🟢 (سوار)" if mid == active else ""
        lines.append(f"{RARITY_LABELS[m['rarity']]} {m['name']} — قدرت {m['power']}{tag}")
    return "\n".join(lines)
