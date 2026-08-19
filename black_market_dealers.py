# ============================================================
#  ASTRAL ABYSS — Roaming Black Market Dealers (دیلرهای گردشی)
# ------------------------------------------------------------
#  هر ساعت، رو یه زیرمجموعه‌ی تصادفی از نقشه‌ها یه دیلرِ گردشی اسپان
#  می‌شه با موجودیِ محدود (هر آیتم فقط چندتا — وقتی تموم شد، تمومه تا
#  دیلرِ بعدی). خریدِ ازشون یه ریسکِ «گیرافتادن» داره — هرچی نقشه
#  خطرناک‌تر باشه و رتبه‌ی بازارت پایین‌تر، احتمالِ گیرافتادن بیشتره.
#  گیرافتادن یعنی: آیتم مصادره می‌شه + یه جریمه‌ی نقدی.
#
#  فقط از رویِ economy.MAPS_DATA/MAP_LOOT، item_system (ساختِ تجهیز)
#  و black_market_reputation (قفلِ دسترسی + کاهشِ ریسک) می‌خونه.
#  هیچ فایلِ قدیمی رو تغییر نمی‌ده.
# ============================================================
from __future__ import annotations

import random
import time
import uuid

import item_system as isy
import black_market_reputation as bmrep

REFRESH_INTERVAL = 3600          # هر دیلر ۱ ساعت زنده‌ست
ACTIVE_DEALER_COUNT = 3          # هم‌زمان فقط رو ۳ نقشه دیلر هست
STOCK_SIZE_RANGE = (3, 5)        # تعدادِ ردیفِ کالای هر دیلر
STOCK_QTY_RANGE = (1, 3)         # موجودیِ هر ردیف

ZONE_BASE_RISK = {"safe": 0.05, "contested": 0.12, "danger": 0.22}
CAUGHT_FINE_PCT = 0.5            # جریمه = ۵۰٪ قیمتِ همون آیتم (علاوه بر از دست دادنِ آیتم)
REP_PENALTY_ON_CATCH = 3
REP_GAIN_ON_SUCCESS = 2

DEALER_ARCHETYPES = [
    {"id": "smuggler",  "name": "کاراوانِ آهنگری", "emoji": "🛻", "flavor": "قاچاقچیِ فلزاتِ نایاب و تجهیزاتِ جنگی.", "kind": "gear"},
    {"id": "alchemist", "name": "کاروانسرای زهرآگین", "emoji": "🧪", "flavor": "کیمیاگرِ دوره‌گرد با موادِ کمیاب.",   "kind": "gear"},
    {"id": "fence",      "name": "واسطه‌ی سایه",        "emoji": "🥷", "flavor": "هرچی گیرش بیاد رو با تخفیف می‌فروشه.", "kind": "mixed"},
]


def _rng_for(map_name: str, salt: float) -> random.Random:
    return random.Random(f"{map_name}:{int(salt)}")


def _gen_stock(map_name: str, seed_t: float) -> list[dict]:
    """موجودیِ یه دیلر رو می‌سازه: ترکیبی از تجهیزِ تصادفی (rare-mythic)
    + موادِ خامِ SPY_ITEMS/DEFENSE_ITEMS‑مانند با قیمتِ ویژه."""
    from economy import MAPS_DATA
    rng = _rng_for(map_name, seed_t)
    tier = MAPS_DATA.get(map_name, {}).get("tier", "common")
    rarity_pool = {"common": ["rare", "epic"], "rare": ["epic", "mythic"], "epic": ["mythic", "legendary"]}
    rarities = rarity_pool.get(tier, ["rare", "epic"])

    n = rng.randint(*STOCK_SIZE_RANGE)
    stock = []
    for _ in range(n):
        slot = rng.choice(isy.EQUIP_SLOTS)
        template = {**rng.choice(isy.EQUIPMENT_TEMPLATES[slot]), "slot": slot}
        forced = rng.choice(rarities)
        item = isy.generate_item(template, 30, forced_rarity=forced, drop_source=f"dealer:{map_name}")
        base_price = int(item.get("sell", 500) * rng.uniform(2.2, 3.4))
        stock.append({
            "row_id": uuid.uuid4().hex[:8],
            "item": item,
            "price": base_price,
            "qty_total": rng.randint(*STOCK_QTY_RANGE),
            "qty_left": None,  # زیر پر می‌شه
        })
    for row in stock:
        row["qty_left"] = row["qty_total"]
    return stock


def _spawn_round(now: float) -> None:
    from database import dealer_col
    from economy import MAPS_DATA
    col = dealer_col()
    col.delete_many({"expires_at": {"$lte": now}})
    active_maps = {d["_id"] for d in col.find({}, {"_id": 1})}
    all_maps = list(MAPS_DATA.keys())
    candidates = [m for m in all_maps if m not in active_maps]
    need = max(0, ACTIVE_DEALER_COUNT - len(active_maps))
    if need == 0 or not candidates:
        return
    random.shuffle(candidates)
    picks = candidates[:need]
    for map_name in picks:
        arche = random.choice(DEALER_ARCHETYPES)
        doc = {
            "_id": map_name,
            "dealer_id": arche["id"],
            "name": arche["name"],
            "emoji": arche["emoji"],
            "flavor": arche["flavor"],
            "spawned_at": now,
            "expires_at": now + REFRESH_INTERVAL,
            "stock": _gen_stock(map_name, now),
        }
        col.replace_one({"_id": map_name}, doc, upsert=True)


def active_dealers() -> list[dict]:
    from database import dealer_col
    now = time.time()
    _spawn_round(now)
    return list(dealer_col().find({"expires_at": {"$gt": now}}))


# ─── Architect Key — بونوسِ «peek»ِ اختصاصی ─────────────────────
# قبلاً: مصرفِ Architect Key فقط یه flag رو روشن می‌کرد که هیچ‌جا
# خونده نمی‌شد. الان: دفعه‌ی بعد که بازیکنی که این فلگ رو داره یه
# دیلر رو باز کنه، یه ردیفِ کالای اختصاصیِ رتبه‌ی بالاتر (legendary+)
# فقط برای خودش تولید می‌شه — تو دیتابیسِ مشترکِ دیلر ذخیره نمی‌شه
# (چون دیلرها بینِ همه‌ی بازیکن‌ها مشترکن)، فقط تو یه کشِ حافظه‌ای
# سبک نگه داشته می‌شه تا خریدش هم کار کنه.
_exclusive_offers: dict[tuple[int, str], dict] = {}


def _gen_exclusive_row(map_name: str) -> dict:
    import item_system as isy
    slot = random.choice(isy.EQUIP_SLOTS)
    template = {**random.choice(isy.EQUIPMENT_TEMPLATES[slot]), "slot": slot}
    forced = random.choice(["legendary", "mythic"])
    item = isy.generate_item(template, 30, forced_rarity=forced, drop_source=f"architect_key:{map_name}")
    base_price = int(item.get("sell", 800) * random.uniform(3.5, 5.0))
    return {
        "row_id": f"exclusive:{uuid.uuid4().hex[:8]}",
        "item": item,
        "price": base_price,
        "qty_total": 1,
        "qty_left": 1,
        "exclusive": True,
    }


def get_dealer(map_name: str, player: dict | None = None, uid: int | None = None) -> dict | None:
    from database import dealer_col
    now = time.time()
    _spawn_round(now)
    doc = dealer_col().find_one({"_id": map_name, "expires_at": {"$gt": now}})
    if not doc or player is None or uid is None:
        return doc

    import spy_loadout_system as spy
    key = (uid, map_name)

    # فلگِ Architect Key فقط یه‌بار مصرف می‌شه — همون‌جا که مصرفش می‌کنیم
    if spy.pop_utility_flag(player, "dealer_exclusive_peek"):
        _exclusive_offers[key] = _gen_exclusive_row(map_name)

    doc = dict(doc)  # کپیِ سطحی تا stockِ دیتابیس دستکاری نشه
    doc["stock"] = list(doc["stock"])
    if key in _exclusive_offers:
        doc["stock"].append(_exclusive_offers[key])
    return doc


def catch_risk(player: dict, map_name: str) -> float:
    from economy import MAPS_DATA
    import spy_loadout_system as spy
    zone = MAPS_DATA.get(map_name, {}).get("zone", "contested")
    base = ZONE_BASE_RISK.get(zone, 0.12)
    reduced = base - bmrep.heat_reduction(player)
    # لودآوتِ جاسوسیِ تجهیزشده (نه فقط داشتنِ خام تو انبار) ریسک رو کم می‌کنه —
    # مصرفِ چارج واقعی تو buy_from_dealer انجام می‌شه، اینجا فقط پیش‌نمایشه
    lo = spy.ensure_loadout(player)
    if lo.get("recon"):
        reduced -= spy.RECON_RISK_REDUCTION_PER_ITEM
    return max(0.02, min(0.9, reduced))


def buy_from_dealer(player: dict, map_name: str, row_id: str, uid: int | None = None) -> tuple[bool, str, dict | None]:
    """(موفق؟, پیام, {'caught': bool} یا None اگه اصلاً خرید انجام نشد)"""
    from database import dealer_col
    from economy_engine import add_reputation

    if not bmrep.has_unlock(player, "dealers"):
        return False, "🔒 رتبه‌ی «آشنا» یا بالاتر لازمه تا دیلرهای گردشی رو ببینی.", None

    exclusive_key = (uid, map_name) if uid is not None else None
    exclusive_row = _exclusive_offers.get(exclusive_key) if exclusive_key else None

    if exclusive_row and exclusive_row["row_id"] == row_id:
        row = exclusive_row
        doc = {"stock": []}  # فقط برای هماهنگیِ منطقِ زیر — آپدیتِ دیتابیس رو رد می‌کنیم
    else:
        doc = get_dealer(map_name)
        if not doc:
            return False, "❌ الان دیلری تو این نقشه نیست.", None
        row = next((r for r in doc["stock"] if r["row_id"] == row_id), None)

    if not row or row["qty_left"] <= 0:
        return False, "❌ این کالا دیگه موجود نیست.", None

    if player.get("zen", 0) < row["price"]:
        return False, f"❌ Zen کافی نداری! ({row['price']:,} لازمه)", None

    import spy_loadout_system as spy
    risk = catch_risk(player, map_name)
    recon_broken = None
    if spy.ensure_loadout(player).get("recon"):
        _, recon_broken = spy.recon_risk_reduction(player)  # مصرفِ چارج

    void_pass_used = spy.pop_utility_flag(player, "void_pass")
    caught = False if void_pass_used else (random.random() < risk)

    player["zen"] -= row["price"]
    if exclusive_row and exclusive_row["row_id"] == row_id:
        _exclusive_offers.pop(exclusive_key, None)
    else:
        dealer_col().update_one(
            {"_id": map_name, "stock.row_id": row_id},
            {"$inc": {"stock.$.qty_left": -1}},
        )

    item = row["item"]
    if caught:
        if spy.pop_utility_flag(player, "guaranteed_escape"):
            player.setdefault("inventory", []).append(item.copy())
            msg = (f"💨 نگهبان‌ها {item['emoji']} {item['name']} رو دیدن ولی دودِ بنفش کمکت کرد بدونِ ردی فرار کنی! "
                   f"آیتم موند تو کوله‌پشتیت.")
            return True, msg, {"caught": False, "item": item, "escaped_with_smoke": True}

        fine = int(row["price"] * CAUGHT_FINE_PCT)
        player["zen"] = max(0, player.get("zen", 0) - fine)
        player["bm_reputation"] = max(0, player.get("bm_reputation", 0) - REP_PENALTY_ON_CATCH)
        msg = (f"🚨 **گیر افتادی!** نگهبان‌های {map_name} {item['emoji']} {item['name']} رو مصادره کردن "
               f"و {fine:,} Zen هم جریمه شدی.\n📉 رپیوتیشن: -{REP_PENALTY_ON_CATCH}")
        if recon_broken:
            msg += f"\n💔 {recon_broken}ت هم شکست — باید دوباره تجهیزش کنی."
        return True, msg, {"caught": True, "item": item, "fine": fine}

    player.setdefault("inventory", []).append(item.copy())
    add_reputation(player, REP_GAIN_ON_SUCCESS)
    extra = " 🎫 (Void Pass مصرف شد — این خرید ۱۰۰٪ امن بود)" if void_pass_used else ""
    msg = (f"✅ {item['emoji']} **{item['name']}** رو بی‌سروصدا خریدی. "
           f"(-{row['price']:,} Zen | +{REP_GAIN_ON_SUCCESS} رپیوتیشن){extra}")
    if recon_broken:
        msg += f"\n💔 {recon_broken}ت شکست — تو انبارت جدید بخر و دوباره تجهیزش کن."
    return True, msg, {"caught": False, "item": item}
