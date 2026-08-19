# ============================================================
#  ASTRAL ABYSS RPG — Merchant Caravan / Travel System
#  (caravan_system.py) — منطقِ خالص، بدون UI
# ------------------------------------------------------------
#  جایگزینِ «سفر» برای تاجر: به‌جای بازدید از مغازه‌ی بازیکنِ دیگه،
#  حالا تاجر یه کاروانِ واقعی رو به یکی از مسیرهای تجاری می‌فرسته —
#  سرمایه‌گذاری می‌کنه، منتظرِ برگشتنِ کاروان می‌مونه، و یا سود می‌بره
#  یا (با شانسِ کم‌تر اگه مزدور اجیر کرده باشه) کاروان غارت می‌شه.
#
#  فیلدِ ذخیره‌سازی: player["class_system_data"]["caravans"] — یه
#  لیست (فعلاً حداکثر ۱ کاروانِ هم‌زمان) از دیکشنری‌های:
#     {"route": route_id, "cost": int, "start_ts": float, "ready_ts": float}
# ============================================================

import random
import time

# ─── مسیرهای تجاری ──────────────────────────────────────────────
ROUTES: list[dict] = [
    {
        "id": "silk",
        "name_fa": "🏜 جاده‌ی ابریشم",
        "duration_sec": 1800,          # ۳۰ دقیقه
        "cost": 200,
        "reward_mult": (1.6, 2.2),
        "risk_pct": 18,
        "desc": "کوتاه و امن‌تر — سودِ متوسط، ریسکِ کم.",
    },
    {
        "id": "coast",
        "name_fa": "🌊 بندرِ سواحلِ آبی",
        "duration_sec": 3600,          # ۱ ساعت
        "cost": 450,
        "reward_mult": (1.8, 2.6),
        "risk_pct": 25,
        "desc": "مسیرِ میان‌مدت — سودِ خوب، ریسکِ متوسط.",
    },
    {
        "id": "mountain",
        "name_fa": "⛰ گذرگاهِ کوهستان",
        "duration_sec": 7200,          # ۲ ساعت
        "cost": 900,
        "reward_mult": (2.0, 3.0),
        "risk_pct": 35,
        "desc": "طولانی و خطرناک — بیشترین سود، بیشترین ریسک.",
    },
]
ROUTES_BY_ID: dict[str, dict] = {r["id"]: r for r in ROUTES}

# هر مزدورِ اجیرشده ۴٪ از ریسکِ کاروان رو کم می‌کنه (سقف ۲۰٪ کاهش)
MERC_RISK_REDUCTION_PER_UNIT = 4
MERC_RISK_REDUCTION_CAP = 20


def get_route(route_id: str) -> dict | None:
    return ROUTES_BY_ID.get(route_id)


def active_caravan(player: dict) -> dict | None:
    caravans = player.get("class_system_data", {}).get("caravans", [])
    return caravans[0] if caravans else None


def caravan_time_left(caravan: dict) -> int:
    return max(0, int(caravan["ready_ts"] - time.time()))


def effective_risk_pct(player: dict, route: dict) -> int:
    mercs = len(player.get("class_system_data", {}).get("mercenaries_hired", []))
    reduction = min(MERC_RISK_REDUCTION_CAP, mercs * MERC_RISK_REDUCTION_PER_UNIT)
    return max(0, route["risk_pct"] - reduction)


def start_caravan(player: dict, route_id: str) -> dict:
    """کاروان رو به یه مسیر می‌فرسته — یه‌بار در آنِ‌واحد بیشتر از یه
    کاروانِ فعال نمی‌شه داشت (طبقِ فیلدِ caravans)."""
    if player.get("class") != "merchant":
        return {"ok": False, "msg": "❌ این قابلیت مخصوصِ تاجره."}
    csd = player.setdefault("class_system_data", {})
    if csd.get("caravans"):
        return {"ok": False, "msg": "❌ یه کاروان همین الان تو راهه — اول باید تمومش کنی."}
    route = ROUTES_BY_ID.get(route_id)
    if not route:
        return {"ok": False, "msg": "❌ مسیرِ نامعتبر."}
    cost = route["cost"]
    if player.get("zen", 0) < cost:
        return {"ok": False, "msg": f"❌ طلای کافی نداری! ({player.get('zen', 0):,}/{cost:,})"}
    player["zen"] -= cost
    caravan = {
        "route": route_id,
        "cost": cost,
        "start_ts": time.time(),
        "ready_ts": time.time() + route["duration_sec"],
    }
    csd.setdefault("caravans", []).append(caravan)
    return {"ok": True, "route": route, "ready_ts": caravan["ready_ts"]}


def claim_caravan(player: dict) -> dict:
    """اگه کاروان رسیده باشه، نتیجه رو (سود یا غارت) اعمال می‌کنه و
    از لیستِ caravans حذفش می‌کنه. اگه هنوز نرسیده، waiting=True برمی‌گردونه."""
    if player.get("class") != "merchant":
        return {"ok": False, "msg": "❌ این قابلیت مخصوصِ تاجره."}
    csd = player.setdefault("class_system_data", {})
    caravans = csd.get("caravans", [])
    if not caravans:
        return {"ok": False, "msg": "❌ کاروانی در حال سفر نیست."}
    caravan = caravans[0]
    remaining = int(caravan["ready_ts"] - time.time())
    if remaining > 0:
        return {"ok": False, "waiting": True, "remaining": remaining}

    route = ROUTES_BY_ID.get(caravan["route"], ROUTES[0])
    risk = effective_risk_pct(player, route)
    caravans.pop(0)

    if random.uniform(0, 100) < risk:
        loss = int(caravan["cost"] * random.uniform(0.4, 0.8))
        return {"ok": True, "ambushed": True, "loss": loss, "route": route}

    mult = random.uniform(*route["reward_mult"]) * csd.get("gold_multiplier", 1.0)
    reward = int(caravan["cost"] * mult)
    influence_gain = max(1, route["duration_sec"] // 1800)
    player["zen"] = player.get("zen", 0) + reward
    csd["market_influence"] = csd.get("market_influence", 0) + influence_gain
    return {"ok": True, "ambushed": False, "reward": reward, "influence_gain": influence_gain, "route": route}
