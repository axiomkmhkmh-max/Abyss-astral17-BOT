# ============================================================
#  ASTRAL ABYSS — Dynamic Economy Engine
#  قیمت‌گذاری واقعی (عرضه/تقاضا + نویز بازار) + مالیات چندلایه
#  + رویدادهای اقتصادی موقت (فرنزی/کرش/معافیت مالیاتی)
# ============================================================
"""
این فایل جدا از economy.py است و هیچ importِ قدیمی رو خراب نمی‌کند.
اقتصادِ قبلی: قیمت هر آیتم فقط با یه رندوم ±۱۵٪ در لحظه‌ی لوت مشخص می‌شد،
یه‌بار خریداری/فروخته می‌شد و هیچ ردی از خودش باقی نمی‌گذاشت.

اقتصادِ جدید:
  • هر آیتم توی هر «بازار» (map یا یه بازار منطقی مثل بازار سیاه) یه
    ضریب قیمت زنده (mult) دارد که با خرید/فروش بازیکن‌ها جابه‌جا می‌شود
    (تقاضا ↑ قیمت، عرضه ↑ قیمت ↓) و به‌مرور با گذشت زمان به ۱.۰ برمی‌گردد
    (mean-reversion) — دقیقاً رفتار یک بازار واقعی.
  • هر بار قیمت خونده می‌شود، یه نویز تصادفی دوره‌ای (drift) هم روی مقدار
    اعمال می‌شود، پس حتی بدون هیچ معامله‌ای بازار «زنده» به‌نظر می‌رسد.
  • مالیات چندلایه: مالیات ناحیه (safe/contested/danger) + مالیات نهنگ
    (تراکنش‌های سنگین) − تخفیف رپیوتیشن بازار سیاه بازیکن.
  • رویدادهای اقتصادی موقت که خودشون هم می‌تونن رندوم اسپاون بشن (بدون
    نیاز به scheduler جدا — روی همون الگوی lazy-refresh کدِ فعلی).
  • یه صندوق مالیات سراسری (tax pool) که می‌تونه بعداً خرج جایزه‌ی باس
    جهانی/ایونت بشه.

نحوه‌ی اتصال به handlerهای موجود:
  به‌جای:
      price = item.get("market_price", item.get("buy", 0))
  بنویس:
      buy_price, sell_price, trend, mult = get_dynamic_price(market_id, item)
  و بعد از هر خرید/فروش واقعی:
      register_trade(market_id, item, "buy" | "sell")

  market_id فقط یه رشته‌ی کلید بازار است؛ می‌تونه اسم واقعی مپ باشه
  (مثلاً "Frostheim") یا یه بازار منطقی مثل "blackmarket_shop" یا
  "global_loot" برای فروش عمومی کوله‌پشتی.
"""

import time
import random
import math

from database import market_col, tax_col, events_col

# ─── Tunables ──────────────────────────────────────────────────
# حالت سخت: مالیات فروش ثابت ۵۰٪ و مالیات خرید ثابت ۳۰٪ شد
# (صرف‌نظر از ناحیه — طبق درخواست بند ۱۳/۷). فیلدهای per-zone قدیمی
# برای سازگاری نگه داشته شدن ولی get_zone_tax_rate/get_buy_vat پایین
# دیگه ازشون استفاده نمی‌کنن.
ZONE_TAX = {"safe": 0.50, "contested": 0.50, "danger": 0.50}
HARDCORE_SELL_TAX = 0.50

# مالیاتِ فروشِ لوت (کوله‌پشتیِ نقشه‌ها؛ market_id == "global_loot") به‌طور
# جداگانه کمتر شد — طبق درخواستِ حسین، از ۵۰٪ به ۱۵٪. مالیاتِ بقیه‌ی
# بازارها (مثل فروشگاهِ بازار سیاه) دست‌نخورده موند.
LOOT_SELL_TAX = 0.15

# مالیات بر ارزش‌افزوده روی خرید (VAT)
BUY_VAT = {"safe": 0.30, "contested": 0.30, "danger": 0.30}
HARDCORE_BUY_VAT = 0.30

# مالیات نهنگ: تراکنش‌های سنگین مالیات پلکانی اضافه می‌گیرن تا تلمبه کردن
# پول یا دستکاری بازار برای بازیکن‌های خیلی پول‌دار جذاب نباشه
WHALE_BRACKETS = [
    (500_000, 0.10),
    (100_000, 0.06),
    (20_000, 0.03),
]

# هر چقدر آیتم نادرتر، نوسان قیمتش (به‌ازای هر معامله) شدیدتره
VOLATILITY = {
    "common": 0.025, "uncommon": 0.04, "rare": 0.06,
    "epic": 0.09, "mythic": 0.11, "legendary": 0.15, "special": 0.18,
}

MULT_MIN, MULT_MAX = 0.4, 3.2          # کف/سقف مطلق ضریب قیمت هر آیتم
REVERSION_HALFLIFE_H = 5.0             # هر ~۵ ساعت نصفِ فاصله از ۱.۰ جبران می‌شه
DRIFT_TICK_SEC = 20 * 60               # هر ۲۰ دقیقه یک نوسان تصادفی کوچک
MAX_CAUGHT_UP_TICKS = 12               # سقف نوسان‌های جمع‌شده بعد از غیبت طولانی
HISTORY_LEN = 10

MAX_REPUTATION = 100
REP_DISCOUNT_PER_POINT = 0.005         # هر امتیاز رپیوتیشن = ۰.۵٪ تخفیف مالیات (سقف ۵۰٪)


# ─── Market state (per item per market) ─────────────────────────
def _key(market_id: str, item_name: str) -> str:
    return f"{market_id}::{item_name}"


def _default_state(now: float) -> dict:
    return {
        "mult": 1.0,
        "last_update": now,
        "last_drift": now,
        "history": [(now, 1.0)],
        "volume_buy": 0,
        "volume_sell": 0,
    }


def _load_state(market_id: str, item_name: str) -> dict:
    key = _key(market_id, item_name)
    doc = market_col().find_one({"_id": key})
    if not doc:
        doc = _default_state(time.time())
        doc["_id"] = key
        market_col().insert_one(doc)
    return doc


def _save_state(market_id: str, item_name: str, doc: dict):
    key = _key(market_id, item_name)
    data = {k: v for k, v in doc.items() if k != "_id"}
    market_col().update_one({"_id": key}, {"$set": data}, upsert=True)


def _apply_time_effects(doc: dict) -> dict:
    """برگشت به میانگین (mean-reversion) + نویز تصادفی دوره‌ای (drift)."""
    now = time.time()
    elapsed_h = max(0.0, (now - doc.get("last_update", now)) / 3600.0)
    if elapsed_h > 0:
        decay = math.exp(-elapsed_h / REVERSION_HALFLIFE_H * math.log(2))
        doc["mult"] = 1.0 + (doc["mult"] - 1.0) * decay

    since_drift = now - doc.get("last_drift", now)
    ticks = int(since_drift // DRIFT_TICK_SEC)
    if ticks > 0:
        for _ in range(min(ticks, MAX_CAUGHT_UP_TICKS)):
            doc["mult"] += random.gauss(0, 0.03)
        doc["last_drift"] = now

    doc["mult"] = max(MULT_MIN, min(MULT_MAX, doc["mult"]))
    doc["last_update"] = now
    return doc


def _push_history(doc: dict) -> dict:
    hist = doc.get("history", [])
    hist.append((doc["last_update"], doc["mult"]))
    doc["history"] = hist[-HISTORY_LEN:]
    return doc


def _trend_arrow(doc: dict) -> str:
    hist = doc.get("history", [])
    if len(hist) < 2:
        return "➖"
    old_mult = hist[0][1]
    delta = (doc["mult"] - old_mult) / max(old_mult, 0.01)
    if delta > 0.03:
        return "📈"
    if delta < -0.03:
        return "📉"
    return "➖"


# ─── Active economic events ──────────────────────────────────────
def _active_events() -> list[dict]:
    doc = events_col().find_one({"_id": "active"}) or {"events": []}
    now = time.time()
    events = [e for e in doc.get("events", []) if e.get("ends_at", 0) > now]
    if len(events) != len(doc.get("events", [])):
        events_col().update_one({"_id": "active"}, {"$set": {"events": events}}, upsert=True)
    return events


def trigger_market_event(kind: str, scope_market: str | None, factor: float,
                          hours: float, label: str):
    """
    kind: 'frenzy' (تقاضای جنون‌وار، factor>1) | 'crash' (سقوط، factor<1)
          | 'tax_holiday' (معافیت مالیاتی موقت، factor نادیده گرفته می‌شه)
    scope_market: کلید یک بازار خاص، یا None برای اثر سراسری روی همه‌ی بازارها
    """
    doc = events_col().find_one({"_id": "active"}) or {"events": []}
    events = doc.get("events", [])
    events.append({
        "kind": kind, "market": scope_market, "factor": factor,
        "ends_at": time.time() + hours * 3600, "label": label,
    })
    events_col().update_one({"_id": "active"}, {"$set": {"events": events}}, upsert=True)


def _event_effect(market_id: str) -> tuple[float, bool]:
    """(ضریب قیمت اضافی از رویدادها, آیا الان معافیت مالیاتی فعاله)"""
    mult = 1.0
    tax_free = False
    for e in _active_events():
        if e.get("market") not in (None, market_id):
            continue
        if e["kind"] in ("frenzy", "crash"):
            mult *= e["factor"]
        elif e["kind"] == "tax_holiday":
            tax_free = True
    return mult, tax_free


def get_active_events_display() -> list[str]:
    out = []
    for e in _active_events():
        rem_min = int((e["ends_at"] - time.time()) / 60)
        scope = e["market"] or "🌍 سراسری"
        out.append(f"{e['label']} — {scope} — {rem_min} دقیقه مانده")
    return out


# ─── Spontaneous random events (بدون نیاز به scheduler) ─────────
_last_spawn_check = {"t": 0.0}
SPAWN_CHECK_INTERVAL = 900     # هر ۱۵ دقیقه یک بار شانس رو چک کن
SPAWN_CHANCE = 0.12            # ۱۲٪ شانس در هر چک

RANDOM_EVENTS = [
    ("frenzy", 1.6, 2.0, "📈 تقاضای جنون‌وار! قیمت‌ها ۶۰٪ رفت بالا"),
    ("crash", 0.55, 1.5, "📉 سقوط بازار! قیمت‌ها ۴۵٪ ریخت"),
    ("tax_holiday", 1.0, 3.0, "🎉 معافیت مالیاتی موقت اعلام شد!"),
]


def maybe_spawn_random_event(market_id: str | None = None) -> str | None:
    """این رو داخل هر هندلری که کاربر باز می‌کنه (مثلاً صفحه‌ی فروشگاه) صدا بزن.
    خودش rate-limit می‌شه، پس صدا زدنش زیادی هزینه‌ای ندارد."""
    now = time.time()
    if now - _last_spawn_check["t"] < SPAWN_CHECK_INTERVAL:
        return None
    _last_spawn_check["t"] = now
    if random.random() > SPAWN_CHANCE:
        return None
    kind, factor, hours, label = random.choice(RANDOM_EVENTS)
    trigger_market_event(kind, market_id, factor, hours, label)
    return label


# ─── Public pricing API ──────────────────────────────────────────
def get_dynamic_price(market_id: str, item: dict) -> tuple[int, int, str, float]:
    """
    item: دیکشنری آیتم با کلیدهای name/sell/buy/rarity.
    خروجی: (buy_price, sell_price, trend_arrow, effective_multiplier)
    """
    doc = _load_state(market_id, item["name"])
    doc = _apply_time_effects(doc)
    doc = _push_history(doc)

    event_mult, _ = _event_effect(market_id)
    effective_mult = doc["mult"] * event_mult
    effective_mult = max(MULT_MIN * 0.5, min(MULT_MAX * 1.5, effective_mult))

    base_buy = item.get("buy", item.get("sell", 10) * 2)
    base_sell = item.get("sell", 10)
    buy_price = max(1, int(base_buy * effective_mult))
    sell_price = max(1, int(base_sell * effective_mult))

    _save_state(market_id, item["name"], doc)
    return buy_price, sell_price, _trend_arrow(doc), round(effective_mult, 2)


def register_trade(market_id: str, item: dict, side: str, qty: int = 1):
    """side: 'buy' یا 'sell' — روی قیمتِ آینده‌ی همون آیتم توی همون بازار اثر می‌گذاره.
    خرید = تقاضا ↑ قیمت، فروش = عرضه ↑ قیمت ↓ (نامتقارن، شبیه بازار واقعی)."""
    rarity = item.get("rarity", "common")
    vol = VOLATILITY.get(rarity, 0.03)
    doc = _load_state(market_id, item["name"])
    doc = _apply_time_effects(doc)
    if side == "buy":
        doc["mult"] += vol * qty
        doc["volume_buy"] = doc.get("volume_buy", 0) + qty
    else:
        doc["mult"] -= vol * 0.8 * qty
        doc["volume_sell"] = doc.get("volume_sell", 0) + qty
    doc["mult"] = max(MULT_MIN, min(MULT_MAX, doc["mult"]))
    doc = _push_history(doc)
    _save_state(market_id, item["name"], doc)


# ─── Tax API ──────────────────────────────────────────────────────
def get_zone_tax_rate(zone: str, market_id: str | None = None) -> float:
    if market_id == "global_loot":
        return LOOT_SELL_TAX
    return HARDCORE_SELL_TAX


def get_buy_vat(zone: str) -> float:
    return HARDCORE_BUY_VAT


def _whale_tax(amount: int) -> float:
    for threshold, rate in WHALE_BRACKETS:
        if amount >= threshold:
            return rate
    return 0.0


def get_reputation_discount(player: dict) -> float:
    """تخفیف کل مالیات = تخفیف رپیوتیشن بازار سیاه + تخفیف مسیر اقبال درخت مهارت (سقف ۵۰٪)."""
    rep = min(MAX_REPUTATION, player.get("bm_reputation", 0))
    rep_discount = rep * REP_DISCOUNT_PER_POINT
    try:
        from skill_tree import get_skill_bonuses
        skill_discount = get_skill_bonuses(player).get("tax_discount", 0)
    except ImportError:
        skill_discount = 0.0
    return min(0.5, rep_discount + skill_discount)


import os as _os
# حالت سخت: طلای لوت/کشتار ۵۰٪ کمتر شد (طبق درخواست بند ۴/۱۳)
HARDCORE_LOOT_GOLD_MULT = 0.5
# حالت سخت: درآمد فروش آیتم ۷۰٪ کمتر شد (یعنی فقط ۳۰٪ ارزش پایه، قبل از مالیات)
HARDCORE_SELL_VALUE_MULT = 0.3

def apply_gold_find(player: dict, amount: int) -> int:
    """درآمد Zen (لوت/کشتار/باس/...) رو با باف gold_find_pct مسیر اقبال ضرب می‌کنه.
    همه‌جا که به بازیکن Zen داده می‌شه باید از این رد بشه تا مسیر اقبال واقعاً حس بشه."""
    if amount <= 0:
        return amount
    try:
        from skill_tree import get_skill_bonuses
        bonus = get_skill_bonuses(player).get("gold_find_pct", 0)
    except ImportError:
        bonus = 0.0
    try:
        # 🔗 Item System v2 — افیکسِ gold_find_pct («اقبال») تا الان جایی مصرف نمی‌شد.
        from item_system import equipment_stats
        bonus += equipment_stats(player).get("gold_find_pct", 0)
    except ImportError:
        pass
    try:
        # 🐾 بونوسِ همراه (Pet/Companion)
        from pet_system import pet_combat_bonus
        bonus += pet_combat_bonus(player).get("gold_find_pct", 0)
    except ImportError:
        pass

    result = int(amount * (1 + bonus) * HARDCORE_LOOT_GOLD_MULT)

    # 💳 بدهیِ بانک (سیستمِ تحت‌تعقیبِ روزانه) — هرچی بدهی بیشتر باشه
    # درآمد کمتر می‌شه، ولی هیچ‌وقت زیرِ کفِ مشخص‌شده نمی‌ره.
    try:
        from daily_wanted import debt_income_multiplier
        result = int(result * debt_income_multiplier(player))
    except ImportError:
        pass

    return result


def compute_sell_tax(player: dict, amount: int, zone: str, market_id: str | None = None) -> dict:
    """مالیات فروش = مالیات ناحیه + مالیات نهنگ − تخفیف رپیوتیشن.
    حالت سخت: قبل از هر چیز، ارزش پایه‌ی آیتم ۷۰٪ کم می‌شه (فقط ۳۰٪ باقی می‌مونه)."""
    amount = int(amount * HARDCORE_SELL_VALUE_MULT)
    _, tax_free = _event_effect(market_id) if market_id else (1.0, False)
    if tax_free:
        return {"gross": amount, "tax_rate": 0.0, "tax_amount": 0,
                "net": amount, "tax_free_event": True}

    base_rate = get_zone_tax_rate(zone, market_id) + _whale_tax(amount)
    discount = get_reputation_discount(player)
    final_rate = max(0.0, base_rate * (1 - discount))
    tax_amount = int(amount * final_rate)
    return {
        "gross": amount, "tax_rate": round(final_rate, 4),
        "tax_amount": tax_amount, "net": amount - tax_amount,
        "tax_free_event": False,
    }


def compute_buy_total(player: dict, base_price: int, zone: str, market_id: str | None = None) -> dict:
    """قیمت نهایی خرید = قیمت پایه + مالیات بر ارزش‌افزوده (با تخفیف رپیوتیشن)."""
    _, tax_free = _event_effect(market_id) if market_id else (1.0, False)
    if tax_free:
        return {"base": base_price, "vat_rate": 0.0, "vat_amount": 0,
                "total": base_price, "tax_free_event": True}

    vat_rate = get_buy_vat(zone)
    discount = get_reputation_discount(player)
    final_rate = max(0.0, vat_rate * (1 - discount))
    vat_amount = int(base_price * final_rate)
    return {
        "base": base_price, "vat_rate": round(final_rate, 4),
        "vat_amount": vat_amount, "total": base_price + vat_amount,
        "tax_free_event": False,
    }


def add_reputation(player: dict, amount: int):
    player["bm_reputation"] = min(MAX_REPUTATION, player.get("bm_reputation", 0) + amount)


def deposit_tax_pool(amount: int, uid: int | None = None):
    if amount <= 0:
        return
    tax_col().update_one(
        {"_id": "pool"},
        {
            "$inc": {"total": amount},
            "$push": {"log": {"$each": [{"uid": uid, "amount": amount, "t": time.time()}],
                               "$slice": -200}},
        },
        upsert=True,
    )


def get_tax_pool() -> int:
    doc = tax_col().find_one({"_id": "pool"})
    return doc.get("total", 0) if doc else 0


def withdraw_tax_pool(amount: int) -> bool:
    """برای مصرفِ صندوق مالیات روی جایزه‌ی باس جهانی/ایونت — اگه کافی نبود False برمی‌گردونه."""
    if get_tax_pool() < amount:
        return False
    tax_col().update_one({"_id": "pool"}, {"$inc": {"total": -amount}})
    return True


# ─── Market overview (برای پنل «📊 وضعیت بازار») ─────────────────
def get_market_overview(market_id: str, items: list[dict], top_n: int = 5) -> dict:
    rows = []
    for item in items:
        buy_p, sell_p, arrow, mult = get_dynamic_price(market_id, item)
        rows.append({
            "name": item["name"], "emoji": item.get("emoji", "📦"),
            "buy": buy_p, "sell": sell_p, "arrow": arrow, "mult": mult,
        })
    rows.sort(key=lambda r: r["mult"], reverse=True)
    gainers = [r for r in rows if r["arrow"] == "📈"][:top_n]
    losers = [r for r in rows if r["arrow"] == "📉"][:top_n]
    return {"gainers": gainers, "losers": losers, "all": rows}
