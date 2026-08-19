# ============================================================
#  ASTRAL ABYSS RPG — 🤝 معامله‌ی روزانه (Merchant Trade Deals)
#  (merchant_deals.py) — منطقِ خالص، بدون UI
# ------------------------------------------------------------
#  چرخه‌ی پیشرفتِ روزانه‌ی تاجر: هرکاروانِ سفر (caravan_system.py) فقط
#  Zen/نفوذ می‌داد و هیچ XPی نداشت — تاجر هیچ‌وقت لول بالا نمی‌رفت.
#  این ماژول یه اکشنِ سریع‌تر و مکرر (مثلِ لوتِ ماجراجو) اضافه می‌کنه:
#  هر بار یه تاجرِ NPC یه معامله پیشنهاد می‌ده، بازیکن مذاکره می‌کنه —
#  نتیجه بسته به haggle_discount_pct/market_influence/mercenaries_hired
#  فرق می‌کنه و Zen + XP + نفوذِ بازار می‌ده.
#
#  گاهی (۱ از ۵) طرفِ معامله یه تاجرِ واقعیِ دیگه‌ست (از دیتابیس) —
#  در این حالت هم به بازیکنِ فعلی، هم (کمی) به همون بازیکنِ واقعی
#  نفوذِ بازار می‌ده: یه همکاریِ واقعیِ کوچیک، نه صرفاً فلیور.
# ============================================================
from __future__ import annotations

import random
import time

from database import get_player, save_player
import class_activity_engine as cae

ACTIVITY_KEY  = "merchant_deals"
MAX_ACTIONS   = 5
BATCH_RESET   = 600
DAILY_MAX     = 40
DAILY_RESET   = 86400

# ─── تاجرهای NPC ─────────────────────────────────────────────
NPC_TRADERS = [
    {"name": "حاجی‌رستم، تاجرِ ادویه",     "good": "ادویه‌ی نایاب",   "tier": 1},
    {"name": "بانو نسرین، پارچه‌فروش",      "good": "پارچه‌ی ابریشمی", "tier": 1},
    {"name": "اوستا کیوان، فلزکار",         "good": "شمشِ فلز",       "tier": 2},
    {"name": "دلارام، جواهرفروش",           "good": "جواهرِ خام",     "tier": 3},
    {"name": "سرگردِ سیاوش، واردکننده",     "good": "کالای قاچاق",    "tier": 3},
    {"name": "پیرمردِ کاروان، تاجرِ کهنه‌کار", "good": "نقشه‌ی گنج",   "tier": 2},
]

TIER_BASE = {
    1: {"zen": (60, 140), "xp": (18, 34), "cost": 0},
    2: {"zen": (150, 320), "xp": (30, 55), "cost": 80},
    3: {"zen": (320, 650), "xp": (50, 90), "cost": 200},
}

AMBUSH_BASE_CHANCE = 0.16  # شانسِ خامِ کمین‌شدنِ معامله (بدونِ مزدور)


def get_state(uid: int) -> dict:
    return cae.get_state(ACTIVITY_KEY, uid, max_actions=MAX_ACTIONS, batch_reset=BATCH_RESET, daily_reset=DAILY_RESET)


def _merc_risk_reduction(player: dict) -> float:
    mercs = len(player.get("class_system_data", {}).get("mercenaries_hired", []))
    return min(0.5, mercs * 0.08)  # هر مزدور ۸٪ ریسکِ کمین رو کم می‌کنه، سقف ۵۰٪


def roll_deal(player: dict) -> dict:
    """یه معامله‌ی جدید تولید می‌کنه (بدونِ مصرفِ اکشن — فقط پیش‌نمایش)."""
    npc = random.choice(NPC_TRADERS)
    tier = npc["tier"]
    base = TIER_BASE[tier]

    partner = None
    if random.random() < 0.20:
        partner = cae.pick_random_other_player(player.get("id") or player.get("_id") or 0, class_filter="merchant")

    return {
        "npc": npc, "tier": tier, "cost": base["cost"],
        "zen_range": base["zen"], "xp_range": base["xp"],
        "partner": partner,
        "rolled_at": time.time(),
    }


def negotiate(uid: int, player: dict, deal: dict) -> dict:
    """مذاکره روی معامله‌ی فعلی — هزینه (اگه تیرش داشته باشه) کسر می‌شه،
    بعد بر اساسِ چانه‌زنی/نفوذ، شانسِ موفقیت/کمین محاسبه می‌شه."""
    cost = deal["cost"]
    if player.get("zen", 0) < cost:
        return {"ok": False, "msg": f"❌ برای این معامله به {cost:,} Zen سرمایه نیاز داری! ({player.get('zen',0):,}/{cost:,})"}

    csd = player.setdefault("class_system_data", {})
    haggle_pct = csd.get("haggle_discount_pct", 5) / 100
    influence_bonus = min(0.25, csd.get("market_influence", 0) * 0.004)

    player["zen"] -= cost

    ambush_chance = max(0.0, AMBUSH_BASE_CHANCE - _merc_risk_reduction(player) - influence_bonus * 0.3)
    if random.random() < ambush_chance:
        loss = int(cost * random.uniform(0.3, 0.7)) if cost else random.randint(20, 60)
        player["zen"] = max(0, player.get("zen", 0) - loss)
        return {"ok": True, "outcome": "ambush", "loss": loss, "deal": deal}

    success_chance = min(0.95, 0.55 + haggle_pct + influence_bonus)
    great = random.random() < success_chance

    zmin, zmax = deal["zen_range"]
    xmin, xmax = deal["xp_range"]
    zen_mult = 1.0 if great else 0.5
    xp_mult = 1.0 if great else 0.6

    base_zen = random.randint(zmin, zmax)
    base_xp = random.randint(xmin, xmax)

    result = cae.grant_rewards(player, uid, base_zen=base_zen, base_xp=base_xp,
                                source="merchant_deals", zen_mult=zen_mult, xp_mult=xp_mult)

    influence_gain = deal["tier"] + (1 if great else 0)
    csd["market_influence"] = csd.get("market_influence", 0) + influence_gain

    partner_note = None
    partner = deal.get("partner")
    if partner and great:
        try:
            p_uid = partner["_uid"]
            p_doc = get_player(p_uid)
            if p_doc:
                p_csd = p_doc.setdefault("class_system_data", {})
                p_csd["market_influence"] = p_csd.get("market_influence", 0) + 1
                save_player(p_uid, p_doc)
                partner_note = partner.get("name", "یه تاجرِ دیگه")
        except Exception:
            partner_note = None

    return {
        "ok": True, "outcome": "great" if great else "partial", "deal": deal,
        "influence_gain": influence_gain, "partner_note": partner_note,
        **result,
    }
