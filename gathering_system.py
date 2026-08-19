# ============================================================
#  ASTRAL ABYSS RPG — Gathering / Excavation  🪓  (v1)
# ------------------------------------------------------------
#  به‌جای دراپِ صرفاً شانسی از کشتار، این یه مینی‌گیمِ فعاله:
#  بازیکن می‌ره سراغِ یکی از ۵ «سایت»، و اگه سایت آماده باشه
#  (کول‌داونش تموم شده) باید یکی از ۳ روشِ ضربه‌زدن رو انتخاب کنه:
#
#    🪶 ملایم    → همیشه موفق، ولی تیرِ پایین‌تر و مقدارِ کمتر
#    ⚖️ متعادل   → ریسکِ کم (۵٪ شکست)، بازه‌ی متعادل
#    💥 تهاجمی   → ریسکِ بالا (۱۵٪ ریزشِ‌رگه = صفر مواد)، ولی
#                   شانسِ بیشتر برای رسیدن به بالاترین تیرِ ممکن
#
#  هر انتخاب واقعاً «تصمیم»ه، نه فقط دکمه‌ی تکراری — و چون هر
#  سایت کول‌داونِ واقعی داره، بازیکن باید دوره‌ای برگرده، درست
#  مثلِ مکانیزمِ مزرعه.
#
#  خروجی مستقیم می‌ره تو همون اینونتوریِ crafting_system (ORE/BEAST/
#  HERB/ESSENCE_TIERS + astral_dust)، پس بی‌درنگ قابلِ‌استفاده تو
#  🔨آهنگری و 🧪کیمیاگریه.
# ============================================================
from __future__ import annotations

import time
import random

import crafting_system as cfs

GATHER_LEVEL_CAP = 10

SITES = {
    "mine": {
        "name": "⛏️ معدن", "pool": cfs.ORE_TIERS, "cooldown": 25 * 60, "unlock_level": 1,
        "desc": "استخراجِ سنگِ‌معدن برای آهنگری",
    },
    "hunting_ground": {
        "name": "🐾 دشتِ‌شکار", "pool": cfs.BEAST_TIERS, "cooldown": 30 * 60, "unlock_level": 1,
        "desc": "ردیابیِ اجزای هیولا برای آهنگری",
    },
    "shadow_grove": {
        "name": "🌿 جنگلِ‌سایه", "pool": cfs.HERB_TIERS, "cooldown": 20 * 60, "unlock_level": 1,
        "desc": "چیدنِ گیاه برای کیمیاگری",
    },
    "ichor_whirl": {
        "name": "🌀 گردابِ‌جوهر", "pool": cfs.ESSENCE_TIERS, "cooldown": 35 * 60, "unlock_level": 3,
        "desc": "استخراجِ جوهر برای کیمیاگری",
    },
    "astral_ruins": {
        "name": "🌌 خرابه‌ی‌اختری", "pool": None, "cooldown": 90 * 60, "unlock_level": 7,
        "desc": "کاوشِ خرابه‌ی نایاب — شانسِ غبارِ‌اختری",
    },
}

CHOICES = {
    "gentle":     {"label": "🪶 ملایم",   "fail_chance": 0.0,  "tier_bias": -1, "qty": (2, 3)},
    "balanced":   {"label": "⚖️ متعادل",  "fail_chance": 0.05, "tier_bias": 0,  "qty": (2, 4)},
    "aggressive": {"label": "💥 تهاجمی",  "fail_chance": 0.15, "tier_bias": 2,  "qty": (3, 5)},
}


def _default_gathering() -> dict:
    return {"level": 1, "xp": 0, "sites": {}}


def get_gathering(player: dict) -> dict:
    g = player.setdefault("gathering", _default_gathering())
    g.setdefault("level", 1)
    g.setdefault("xp", 0)
    g.setdefault("sites", {})
    return g


def xp_needed(level: int) -> int:
    return 90 * level * level


def _gain_xp(player: dict, amount: int) -> list[str]:
    g = get_gathering(player)
    logs = []
    if g["level"] >= GATHER_LEVEL_CAP:
        return logs
    g["xp"] += amount
    while g["level"] < GATHER_LEVEL_CAP and g["xp"] >= xp_needed(g["level"]):
        g["xp"] -= xp_needed(g["level"])
        g["level"] += 1
        logs.append(f"📈 مهارتِ کاوش به سطح {g['level']} رسید!")
    return logs


def _max_tier(gather_level: int) -> int:
    return min(5, 1 + gather_level // 2)


def _cooldown_for(site_id: str, gather_level: int) -> int:
    base = SITES[site_id]["cooldown"]
    mult = max(0.75, 1 - 0.025 * gather_level)   # هر لول ۲.۵٪ کول‌داون کمتر، تا سقفِ ۲۵٪
    return int(base * mult)


def site_status(player: dict, site_id: str) -> dict:
    g = get_gathering(player)
    site = SITES[site_id]
    unlocked = g["level"] >= site["unlock_level"]
    next_ready_at = g["sites"].get(site_id, {}).get("next_ready_at", 0)
    now = time.time()
    ready = unlocked and now >= next_ready_at
    remaining = max(0, int(next_ready_at - now))
    return {"unlocked": unlocked, "ready": ready, "remaining": remaining}


def gather_menu_text(player: dict) -> str:
    g = get_gathering(player)
    lines = [
        "🪓 **کاوش / استخراج**",
        f"سطحِ کاوش: {g['level']}/{GATHER_LEVEL_CAP}  ({g['xp']}/{xp_needed(g['level']) if g['level']<GATHER_LEVEL_CAP else '—'} XP)",
        "",
    ]
    for site_id, site in SITES.items():
        st = site_status(player, site_id)
        if not st["unlocked"]:
            lines.append(f"🔒 {site['name']} — نیازِ سطحِ کاوشِ {site['unlock_level']}")
        elif st["ready"]:
            lines.append(f"✅ {site['name']} — آماده‌ست! ({site['desc']})")
        else:
            m, s = divmod(st["remaining"], 60)
            lines.append(f"⏳ {site['name']} — {m} دقیقه‌ی دیگه آماده می‌شه")
    return "\n".join(lines)


def site_detail_text(player: dict, site_id: str) -> str:
    site = SITES[site_id]
    st = site_status(player, site_id)
    g = get_gathering(player)
    if not st["unlocked"]:
        return f"🔒 **{site['name']}** — نیازِ سطحِ کاوشِ {site['unlock_level']} داری (الان: {g['level']})."
    if not st["ready"]:
        m, s = divmod(st["remaining"], 60)
        return f"⏳ **{site['name']}** هنوز آماده نیست — {m} دقیقه‌ی دیگه برگرد."
    max_tier = _max_tier(g["level"])
    return (
        f"✅ **{site['name']}** آماده‌ست! ({site['desc']})\n"
        f"بالاترین تیرِ قابلِ‌دسترس: {max_tier}\n\n"
        f"چطور ضربه بزنیم؟\n"
        f"🪶 ملایم: همیشه موفق، تیرِ پایین‌تر\n"
        f"⚖️ متعادل: ریسکِ کم (۵٪ شکست)، بازه‌ی متوسط\n"
        f"💥 تهاجمی: ریسکِ بالا (۱۵٪ ریزشِ‌رگه)، شانسِ تیرِ بالاتر"
    )


def resolve_gather(uid: int, player: dict, site_id: str, choice_key: str) -> tuple[bool, str]:
    site = SITES.get(site_id)
    choice = CHOICES.get(choice_key)
    if not site or not choice:
        return False, "❌ گزینه‌ی نامعتبر."
    st = site_status(player, site_id)
    if not st["unlocked"]:
        return False, f"❌ نیازِ سطحِ کاوشِ {site['unlock_level']} داری."
    if not st["ready"]:
        m, s = divmod(st["remaining"], 60)
        return False, f"⏳ هنوز آماده نیست — {m} دقیقه‌ی دیگه برگرد."

    g = get_gathering(player)
    now = time.time()
    g["sites"].setdefault(site_id, {})["next_ready_at"] = now + _cooldown_for(site_id, g["level"])

    xp_gain = 18
    if random.random() < choice["fail_chance"]:
        _gain_xp(player, xp_gain // 2)
        return True, f"💥 {choice['label']} تو {site['name']} — رگه ریخت و چیزی گیر نیومد؛ ولی تجربه گرفتی."

    max_tier = _max_tier(g["level"])

    if site_id == "astral_ruins":
        if random.random() < 0.12:
            cfs.add_material(player, "astral_dust", 1)
            got_txt = f"1×{cfs._mat('astral_dust')['emoji']}{cfs._mat('astral_dust')['name']}"
        else:
            pools = [cfs.ORE_TIERS, cfs.BEAST_TIERS, cfs.HERB_TIERS, cfs.ESSENCE_TIERS]
            mat_id = random.choice(pools)[4]
            cfs.add_material(player, mat_id, 1)
            got_txt = f"1×{cfs._mat(mat_id)['emoji']}{cfs._mat(mat_id)['name']}"
        logs = _gain_xp(player, xp_gain * 2)
        msg = f"🌌 {choice['label']} تو خرابه‌ی‌اختری — گرفتی: {got_txt}"
        if logs:
            msg += "\n" + "\n".join(logs)
        return True, msg

    tier = min(max_tier, max(1, random.randint(1, max_tier) + choice["tier_bias"]))
    tier = max(1, min(tier, max_tier))
    mat_id = site["pool"][tier - 1]
    qty = random.randint(*choice["qty"])
    cfs.add_material(player, mat_id, qty)
    logs = _gain_xp(player, xp_gain + tier * 4)

    m = cfs._mat(mat_id)
    msg = f"{choice['label']} تو {site['name']} — گرفتی: {qty}×{m['emoji']}{m['name']} (تیر {tier})"
    if logs:
        msg += "\n" + "\n".join(logs)
    return True, msg
