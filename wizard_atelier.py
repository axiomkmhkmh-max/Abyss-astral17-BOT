# ============================================================
#  ASTRAL ABYSS RPG — 🔮 مشتری‌های اتلیه (Wizard Atelier Customers)
#  (wizard_atelier.py) — منطقِ خالص، بدون UI
# ------------------------------------------------------------
#  «🛠 کارگاه» (crafting_system.py) یه سیستمِ لولِ کرفتِ مجزا داره
#  (forge_level/alchemy_level) که هیچ‌وقت به لولِ اصلیِ کاراکتر
#  (player["xp"]/level) وصل نمی‌شه. این ماژول همون حلقه‌ای که خواسته
#  شده رو می‌سازه: هر نوبت یه مشتریِ NPC یه سفارشِ پوشن/الکسیر (از
#  همون POTION_RECIPES کارگاه) می‌ده. اگه از قبل تو کوله‌پشتی داری،
#  فوری تحویل می‌دی؛ وگرنه همون‌جا با موادت می‌سازیش (craft_potion) —
#  هردو حالت هم XPِ کیمیاگری (کارگاه) می‌دن هم XP/Zenِ اصلیِ کاراکتر
#  (از طریقِ class_activity_engine، طبقِ همون اقتصادِ سراسری).
#
#  گاهی (۱ از ۵) سفارش یه «کمیسیونِ واقعی»ه: باید پوشن رو واقعاً
#  بسازی و به یه بازیکنِ واقعیِ دیگه (اینونتوریش) تحویل بدی — پاداشِ
#  بیشتر، چون واقعاً یه بازیکنِ دیگه از کارِ تو سود می‌بره.
# ============================================================
from __future__ import annotations

import random
import time

from database import get_player, save_player, asave_player, aget_player
import class_activity_engine as cae
import crafting_system as cs

ACTIVITY_KEY  = "wizard_atelier"
MAX_ACTIONS   = 5
BATCH_RESET   = 600
DAILY_MAX     = 40
DAILY_RESET   = 86400

MANA_COST_QUICK_BREW = 18  # ساختِ فوری بدونِ مواد، فقط با مانا (پوشن ضعیف‌تر ولی سریع)

CUSTOMER_NAMES = [
    "پیرمردِ گیاه‌شناس", "شاگردِ کیمیاگر", "زائرِ خسته از راه", "سوارکارِ زخمی",
    "کاهنه‌ی جوان", "شکارچیِ حرفه‌ای", "بازرگانِ عبوس", "کودکِ کنجکاو",
]

# فقط از دستورهای واقعیِ کارگاه (crafting_system.POTION_RECIPES) استفاده می‌کنیم
# تا هیچ داده‌ی موازی/ناهماهنگی با کارگاه نداشته باشیم.
ORDER_RECIPE_KEYS = list(cs.POTION_RECIPES.keys())

TIER_XP_ZEN = {
    1: {"zen": (50, 110), "xp": (16, 30)},
    2: {"zen": (110, 240), "xp": (28, 50)},
    3: {"zen": (240, 480), "xp": (46, 82)},
}


def _tier_of(req_level: int) -> int:
    if req_level <= 2:
        return 1
    if req_level <= 5:
        return 2
    return 3


def get_state(uid: int) -> dict:
    return cae.get_state(ACTIVITY_KEY, uid, max_actions=MAX_ACTIONS, batch_reset=BATCH_RESET, daily_reset=DAILY_RESET)


def roll_customer(player: dict) -> dict:
    recipe_key = random.choice(ORDER_RECIPE_KEYS)
    recipe = cs.POTION_RECIPES[recipe_key]
    tier = _tier_of(recipe["req_level"])
    name = random.choice(CUSTOMER_NAMES)

    commission = None
    if random.random() < 0.20:
        commission = cae.pick_random_other_player(player.get("id") or player.get("_id") or 0)

    return {
        "recipe_key": recipe_key, "recipe": recipe, "tier": tier,
        "customer_name": name, "commission": commission, "rolled_at": time.time(),
    }


def _has_ready_potion(player: dict, recipe_key: str) -> bool:
    return cs.material_qty(player, recipe_key, item_type="potion") > 0


async def fulfill_order(uid: int, player: dict, order: dict, *, method: str) -> dict:
    """method: 'have' (از قبل تو کوله داری) | 'craft' (همین‌جا با موادت بساز) | 'quick' (فقط با مانا، ضعیف‌تر)"""
    recipe_key = order["recipe_key"]
    recipe = order["recipe"]
    tier = order["tier"]

    if method == "have":
        if not _has_ready_potion(player, recipe_key):
            return {"ok": False, "msg": "❌ این پوشن رو تو کوله‌پشتیت نداری."}
        entry = next((it for it in player.get("inventory", [])
                      if it.get("type") == "potion" and it.get("material_id") == recipe_key), None)
        if entry:
            entry["qty"] -= 1
            if entry["qty"] <= 0:
                player["inventory"].remove(entry)
        xp_mult, zen_mult = 1.15, 1.15  # بونوس چون از قبل آماده داشتی

    elif method == "craft":
        ok, craft_msg = cs.craft_potion(uid, player, recipe_key)
        if not ok:
            return {"ok": False, "msg": craft_msg}
        entry = next((it for it in player.get("inventory", [])
                      if it.get("type") == "potion" and it.get("material_id") == recipe_key), None)
        if entry:
            entry["qty"] -= 1
            if entry["qty"] <= 0:
                player["inventory"].remove(entry)
        xp_mult, zen_mult = 1.0, 1.0

    elif method == "quick":
        csd = player.setdefault("class_system_data", {})
        if csd.get("mana", 0) < MANA_COST_QUICK_BREW:
            return {"ok": False, "msg": f"❌ مانای کافی نداری! ({csd.get('mana',0)}/{MANA_COST_QUICK_BREW})"}
        csd["mana"] -= MANA_COST_QUICK_BREW
        xp_mult, zen_mult = 0.55, 0.55  # جایگزینِ سریع ولی کم‌ارزش‌تر — موادِ واقعی مصرف نمی‌شه

    else:
        return {"ok": False, "msg": "❌ روشِ نامعتبر."}

    base = TIER_XP_ZEN[tier]
    base_zen = random.randint(*base["zen"])
    base_xp = random.randint(*base["xp"])

    commission = order.get("commission")
    delivered_to = None
    if commission and method in ("craft", "have"):
        try:
            t_uid = commission["_uid"]
            t_player = await aget_player(t_uid)
            if t_player:
                cs.add_material(t_player, recipe_key, 1, item_type="potion")
                await asave_player(t_uid, t_player)
                delivered_to = commission.get("name", "یه بازیکنِ دیگه")
                zen_mult *= 1.35
                xp_mult *= 1.35
        except Exception:
            delivered_to = None

    result = cae.grant_rewards(player, uid, base_zen=base_zen, base_xp=base_xp,
                                source="wizard_atelier", zen_mult=zen_mult, xp_mult=xp_mult)

    return {"ok": True, "delivered_to": delivered_to, "method": method, **result}
