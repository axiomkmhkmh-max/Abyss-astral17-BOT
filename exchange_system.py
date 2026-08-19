# ============================================================
#  ASTRAL ABYSS — بورسِ آبیس (Exchange) 📈
# ------------------------------------------------------------
#  یه لایه‌ی جدیدِ اقتصادی، جدا از بانک (که سودش ثابته): این‌جا
#  بازیکن Zenِ نقدش رو تبدیل به «سهم» می‌کنه و قیمتش واقعاً نوسان
#  داره — یعنی هم می‌تونه سود کنه، هم ضرر. سه ابزار داریم:
#
#    🕊️ سهامِ نور     — وقتی گیجِ فسادِ آبیس (world_pulse) پایین
#                       باشه (دنیا روشن‌تره) گرون‌تر می‌شه.
#    🕳️ سهامِ فساد    — دقیقاً برعکس؛ وقتی فساد بالا بره گرون می‌شه.
#    🪙 صندوقِ پایدار  — کم‌نوسان، مثلِ یه صندوقِ شاخصی به‌آرومی رشد
#                       می‌کنه؛ گزینه‌ی امن‌ترِ سرمایه‌گذاری.
#
#  یعنی این سیستم مستقیماً به گیجِ فسادِ world_pulse وصله — بازیکن‌ها
#  می‌تونن با خوندنِ مسیرِ دنیا (Void/Light) رویِ سهامِ درست شرط ببندن.
#  قیمت‌ها با همون الگوی lazy-refresh (بدونِ نیاز به job جدا) هر بار
#  که کسی می‌خوندشون به‌روز می‌شن. هر خرید/فروش یه کارمزدِ کوچیک داره
#  که می‌ره تو صندوقِ مالیاتِ سراسری (sink واقعی).
# ============================================================
import time
import math
import random

INSTRUMENTS = [
    {
        "id": "light", "name": "🕊️ سهامِ نور",
        "desc": "وقتی آبیس رو به روشناییه ارزشش بالا می‌ره؛ وقتی فساد زیاد بشه می‌ریزه.",
        "volatility": 0.030,
    },
    {
        "id": "corrupt", "name": "🕳️ سهامِ فساد",
        "desc": "برعکسِ سهامِ نور — وقتی آبیس فاسدتر می‌شه پرارزش‌تر می‌شه.",
        "volatility": 0.035,
    },
    {
        "id": "stable", "name": "🪙 صندوقِ پایدارِ آبیس",
        "desc": "کم‌نوسان، به‌آرومی رشد می‌کنه — گزینه‌ی امن‌ترِ سرمایه‌گذاریِ بلندمدت.",
        "volatility": 0.008,
    },
]
INSTRUMENT_BY_ID = {i["id"]: i for i in INSTRUMENTS}

BASE_PRICE = 100.0
PRICE_MIN, PRICE_MAX = 20.0, 500.0
REVERSION_HALFLIFE_H = 6.0        # سهامِ نور/فساد چقدر سریع به سمتِ هدف برگردن
STABLE_HOURLY_GROWTH = 0.0004     # رشدِ آرومِ صندوقِ پایدار (~۱٪ در روز)
HISTORY_LEN = 20

TRADE_FEE_PCT = 0.02
MIN_TRADE_ZEN = 50


def _get_corruption() -> float:
    try:
        from world_pulse import _doc as pulse_doc
        return pulse_doc().get("corruption", 50.0)
    except Exception:
        return 50.0


def _target_price(inst_id: str, corruption: float) -> float:
    # فساد: 0 (روشن) .. 100 (فاسد)
    if inst_id == "light":
        return BASE_PRICE + (50 - corruption) * 1.6
    if inst_id == "corrupt":
        return BASE_PRICE + (corruption - 50) * 1.6
    return BASE_PRICE  # stable هدفِ ثابت نداره، جداگونه رشد می‌کنه


def _clamp(v: float) -> float:
    return max(PRICE_MIN, min(PRICE_MAX, v))


def _doc() -> dict:
    from database import system_col
    doc = system_col().find_one({"_id": "exchange"})
    if not doc:
        doc = {
            "_id": "exchange",
            "prices": {i["id"]: BASE_PRICE for i in INSTRUMENTS},
            "last_update": time.time(),
            "history": {i["id"]: [(time.time(), BASE_PRICE)] for i in INSTRUMENTS},
        }
        system_col().update_one({"_id": "exchange"}, {"$set": doc}, upsert=True)
    doc.setdefault("prices", {i["id"]: BASE_PRICE for i in INSTRUMENTS})
    doc.setdefault("history", {i["id"]: [] for i in INSTRUMENTS})
    for i in INSTRUMENTS:
        doc["prices"].setdefault(i["id"], BASE_PRICE)
        doc["history"].setdefault(i["id"], [])
    return doc


def _save(doc: dict):
    from database import system_col
    data = {k: v for k, v in doc.items() if k != "_id"}
    system_col().update_one({"_id": "exchange"}, {"$set": data}, upsert=True)


def _refresh(doc: dict):
    now = time.time()
    elapsed_h = max(0.0, (now - doc.get("last_update", now)) / 3600.0)
    if elapsed_h <= 0:
        return
    corruption = _get_corruption()
    for inst in INSTRUMENTS:
        iid = inst["id"]
        p = doc["prices"].get(iid, BASE_PRICE)
        if iid == "stable":
            p *= (1 + STABLE_HOURLY_GROWTH * elapsed_h)
        else:
            target = _target_price(iid, corruption)
            decay = math.exp(-elapsed_h / REVERSION_HALFLIFE_H * math.log(2))
            p = target + (p - target) * decay
        p += random.uniform(-1, 1) * inst["volatility"] * p * min(1.0, elapsed_h + 0.15)
        p = round(_clamp(p), 2)
        doc["prices"][iid] = p
        hist = doc["history"].setdefault(iid, [])
        hist.append((now, p))
        doc["history"][iid] = hist[-HISTORY_LEN:]
    doc["last_update"] = now
    _save(doc)


def get_prices() -> dict:
    """{"light": {"price":.., "prev":.., "name":.., "desc":..}, ...}"""
    doc = _doc()
    _refresh(doc)
    out = {}
    for inst in INSTRUMENTS:
        iid = inst["id"]
        hist = doc["history"].get(iid, [])
        prev = hist[-2][1] if len(hist) >= 2 else doc["prices"][iid]
        out[iid] = {
            "price": doc["prices"][iid], "prev": prev,
            "name": inst["name"], "desc": inst["desc"],
        }
    return out


def get_price(inst_id: str) -> float:
    return get_prices()[inst_id]["price"]


def holdings(player: dict) -> dict:
    return player.setdefault("exchange", {})


def portfolio_value(player: dict, prices: dict | None = None) -> float:
    prices = prices or get_prices()
    h = holdings(player)
    return sum(shares * prices[iid]["price"] for iid, shares in h.items() if iid in prices)


def buy(player: dict, inst_id: str, zen_amount: int) -> tuple[bool, str]:
    if inst_id not in INSTRUMENT_BY_ID:
        return False, "❌ این سهم وجود نداره."
    if zen_amount < MIN_TRADE_ZEN:
        return False, f"❌ حداقلِ خرید {MIN_TRADE_ZEN:,} Zen هست."
    if player.get("zen", 0) < zen_amount:
        return False, "❌ Zen کافی نداری."
    price = get_price(inst_id)
    fee = int(zen_amount * TRADE_FEE_PCT)
    net = zen_amount - fee
    shares = net / price
    player["zen"] -= zen_amount
    h = holdings(player)
    h[inst_id] = h.get(inst_id, 0.0) + shares

    if fee > 0:
        try:
            from economy_engine import deposit_tax_pool
            deposit_tax_pool(fee, player.get("_uid"))
        except Exception:
            pass
        try:
            from economy_ledger import record_exchange_fee
            record_exchange_fee(fee)
        except Exception:
            pass

    name = INSTRUMENT_BY_ID[inst_id]["name"]
    return True, (
        f"✅ **{shares:.2f}** واحد از {name} خریدی (قیمتِ هر واحد: {price:,.2f} Zen).\n"
        f"🧾 کارمزد: {fee:,} Zen"
    )


def sell(player: dict, inst_id: str, shares_amount: float | None = None) -> tuple[bool, str]:
    if inst_id not in INSTRUMENT_BY_ID:
        return False, "❌ این سهم وجود نداره."
    h = holdings(player)
    owned = h.get(inst_id, 0.0)
    if owned <= 0:
        return False, "❌ از این سهم چیزی نداری."
    sell_shares = owned if shares_amount is None else min(owned, max(0.0, shares_amount))
    if sell_shares <= 0:
        return False, "❌ مقدارِ نامعتبر."
    price = get_price(inst_id)
    gross = sell_shares * price
    fee = int(gross * TRADE_FEE_PCT)
    net = int(gross - fee)
    h[inst_id] = owned - sell_shares
    if h[inst_id] <= 1e-6:
        h.pop(inst_id, None)
    player["zen"] = player.get("zen", 0) + net

    if fee > 0:
        try:
            from economy_engine import deposit_tax_pool
            deposit_tax_pool(fee, player.get("_uid"))
        except Exception:
            pass
        try:
            from economy_ledger import record_exchange_fee
            record_exchange_fee(fee)
        except Exception:
            pass

    name = INSTRUMENT_BY_ID[inst_id]["name"]
    return True, (
        f"✅ **{sell_shares:.2f}** واحد از {name} رو به قیمتِ {price:,.2f} فروختی.\n"
        f"💰 دریافتی: **{net:,} Zen** (کارمزد: {fee:,} Zen)"
    )


# ─── ادمین: شوکِ دستیِ قیمت (برای ایونت/تعادل) ───────────────────
def force_shock(inst_id: str, mult: float) -> float | None:
    if inst_id not in INSTRUMENT_BY_ID:
        return None
    doc = _doc()
    _refresh(doc)
    new_price = round(_clamp(doc["prices"][inst_id] * mult), 2)
    doc["prices"][inst_id] = new_price
    hist = doc["history"].setdefault(inst_id, [])
    hist.append((time.time(), new_price))
    doc["history"][inst_id] = hist[-HISTORY_LEN:]
    _save(doc)
    return new_price
