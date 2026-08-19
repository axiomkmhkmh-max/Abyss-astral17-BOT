# ============================================================
#  ASTRAL ABYSS RPG — Land & Construction 🗺️  (v1)
#  زیرسیستمِ اولِ فیچرِ خونه/مزرعه/زمین/شهر.
#
#  مدل: خونه (house_system.py) شخصیه و همیشه همراهته — این سیستم
#  یه لایه‌ی جداست: یه «زمین» (deed) رو یه نقشه‌ی مشخص می‌خری. زمین:
#    • سایز داره (کوچیک/متوسط/بزرگ) که سقفِ سطحِ خونه‌ای که می‌تونی
#      بسازی رو تعیین می‌کنه (گیت — تو house_system.upgrade_house چک می‌شه)
#    • قابلِ بزرگ‌کردنه (expand) با هزینه‌ی صعودی
#    • قابلِ اجاره‌دادن به بازیکنِ دیگه‌ست (درآمدِ غیرفعالِ جدا از خونه)
#    • قابلِ فروش/انتقالِ مالکیت به بازیکنِ دیگه‌ست
#  هر بازیکن حداکثر یه زمین می‌تونه داشته باشه (ضدِ احتکار). هر نقشه
#  تعدادِ محدودی پلاک داره — یعنی زمین‌های خوب تموم می‌شن و باید
#  بری نقشه‌های دیگه یا صبر کنی یکی بفروشه/رها کنه.
# ============================================================
import time
from database import get_db

PLOTS_PER_MAP = 4  # هر نقشه ۴ پلاک ثابت داره: کوچیک، کوچیک، متوسط، بزرگ

LAND_SIZES = {
    "small":  {"name": "🌱 پلاکِ کوچیک",  "order": 0, "cost": 2000,   "max_house_tier": 2, "expand_cost": 8000,   "rent_base": 15},
    "medium": {"name": "🌾 پلاکِ متوسط",  "order": 1, "cost": 8000,   "max_house_tier": 3, "expand_cost": 30000,  "rent_base": 45},
    "large":  {"name": "🏞 پلاکِ بزرگ",   "order": 2, "cost": 30000,  "max_house_tier": 4, "expand_cost": 0,      "rent_base": 120},
}
LAND_SIZE_ORDER = ["small", "medium", "large"]
# الگوی سایزِ ۴ پلاکِ هر نقشه (اندیس = plot_id)
PLOT_SIZE_PATTERN = ["small", "small", "medium", "large"]

RENT_DURATION = 24 * 3600          # هر اجاره ۲۴ ساعت پوششه
RENT_MAX_ACCRUAL_HOURS = 20        # سقفِ انباشتِ درآمدِ اجاره (مثلِ house_system)
LAND_ABANDON_REFUND_PCT = 0.30     # رهاکردنِ زمین فقط ۳۰٪ هزینه‌ی خریدش رو برمی‌گردونه (ضدِ سوءاستفاده)


def land_col():
    return get_db()["land_plots"]


def _plot_key(map_name: str, plot_id: int) -> str:
    return f"{map_name}::{plot_id}"


def ensure_plots_seeded(map_name: str) -> None:
    """اولین باری که یه نقشه لمس می‌شه، ۴ پلاکش رو تو دیتابیس می‌سازه (idempotent)."""
    col = land_col()
    for plot_id in range(PLOTS_PER_MAP):
        key = _plot_key(map_name, plot_id)
        if col.find_one({"_id": key}):
            continue
        col.insert_one({
            "_id": key,
            "map": map_name,
            "plot_id": plot_id,
            "size": PLOT_SIZE_PATTERN[plot_id],
            "owner": None,
            "owner_name": None,
            "bought_at": 0,
            "listed_price": None,
            "rent_price": 0,          # 0 یعنی اجاره نداده
            "rent_vault": 0,
            "rent_income_since": 0,
            "renter": None,
            "renter_until": 0,
        })


def list_plots(map_name: str) -> list[dict]:
    ensure_plots_seeded(map_name)
    return list(land_col().find({"map": map_name}).sort("plot_id", 1))


def get_my_land(uid: int) -> dict | None:
    return land_col().find_one({"owner": uid})


def size_data(size_key: str) -> dict:
    return LAND_SIZES[size_key]


def max_house_tier_for_player(uid: int) -> int | None:
    """اگه بازیکن زمین داره، سقفِ سطحِ خونه‌ای که مجازه بسازه رو برمی‌گردونه.
    None یعنی هیچ محدودیتی نیست (بازیکن هنوز زمینی نخریده — این حالتِ گذار
    برای بازیکن‌های قدیمی‌ایه که خونه از قبل داشتن، پس گیر نمی‌افتن)."""
    doc = get_my_land(uid)
    if not doc:
        return None
    return LAND_SIZES[doc["size"]]["max_house_tier"]


def buy_land(uid: int, player: dict, map_name: str, plot_id: int) -> tuple[bool, str]:
    if get_my_land(uid):
        return False, "❌ همین الان یه زمین داری — اول باید بفروشیش یا رهاش کنی."
    ensure_plots_seeded(map_name)
    doc = land_col().find_one({"_id": _plot_key(map_name, plot_id)})
    if not doc:
        return False, "❌ پلاکِ نامعتبر."
    if doc["owner"] is not None:
        return False, "❌ این پلاک قبلاً خریده شده."
    size = LAND_SIZES[doc["size"]]
    cost = size["cost"]
    if player.get("zen", 0) < cost:
        return False, f"❌ برای خریدِ {size['name']} به {cost:,} Zen نیاز داری."
    player["zen"] -= cost
    land_col().update_one({"_id": doc["_id"]}, {"$set": {
        "owner": uid, "owner_name": player.get("name", "—"), "bought_at": time.time(),
        "rent_income_since": time.time(),
    }})
    return True, f"🗺️ **{size['name']}** رو تو {map_name} خریدی! حالا می‌تونی روش بسازی (منوی 🏠 ملک)."


def expand_land(uid: int, player: dict) -> tuple[bool, str]:
    doc = get_my_land(uid)
    if not doc:
        return False, "❌ هنوز زمینی نداری."
    cur = LAND_SIZES[doc["size"]]
    idx = LAND_SIZE_ORDER.index(doc["size"])
    if idx + 1 >= len(LAND_SIZE_ORDER):
        return False, "🏞 زمینت از قبل تو بزرگ‌ترین سایزه!"
    next_size_key = LAND_SIZE_ORDER[idx + 1]
    next_size = LAND_SIZES[next_size_key]
    cost = cur["expand_cost"]
    if player.get("zen", 0) < cost:
        return False, f"❌ برای بزرگ‌کردنِ زمین به {next_size['name']} به {cost:,} Zen نیاز داری."
    player["zen"] -= cost
    land_col().update_one({"_id": doc["_id"]}, {"$set": {"size": next_size_key}})
    return True, f"🎉 زمینت بزرگ شد: **{next_size['name']}**! سقفِ خونه‌ات هم بالاتر رفت."


def abandon_land(uid: int, player: dict) -> tuple[bool, str]:
    doc = get_my_land(uid)
    if not doc:
        return False, "❌ هنوز زمینی نداری."
    if doc.get("renter"):
        return False, "❌ زمینت الان اجاره‌ست — اول اجاره رو تموم کن."
    refund = int(LAND_SIZES[doc["size"]]["cost"] * LAND_ABANDON_REFUND_PCT)
    player["zen"] = player.get("zen", 0) + refund
    land_col().update_one({"_id": doc["_id"]}, {"$set": {
        "owner": None, "owner_name": None, "bought_at": 0, "listed_price": None,
        "rent_price": 0, "rent_vault": 0, "renter": None, "renter_until": 0,
    }})
    return True, f"👋 زمینت رو رها کردی و {refund:,} Zen (۳۰٪ هزینه‌ی خرید) پس گرفتی."


# ─── فروش/انتقالِ مالکیت ────────────────────────────────────────
def list_for_sale(uid: int, price: int) -> tuple[bool, str]:
    doc = get_my_land(uid)
    if not doc:
        return False, "❌ هنوز زمینی نداری."
    if doc.get("renter"):
        return False, "❌ زمینِ اجاره‌داده‌شده رو نمی‌شه فروخت — اول اجاره رو تموم کن."
    if price <= 0:
        return False, "❌ قیمت باید مثبت باشه."
    land_col().update_one({"_id": doc["_id"]}, {"$set": {"listed_price": price}})
    return True, f"🏷️ زمینت به قیمتِ {price:,} Zen گذاشته شد رو بازار."


def cancel_listing(uid: int) -> tuple[bool, str]:
    doc = get_my_land(uid)
    if not doc or not doc.get("listed_price"):
        return False, "❌ زمینت الان رو بازار نیست."
    land_col().update_one({"_id": doc["_id"]}, {"$set": {"listed_price": None}})
    return True, "✅ زمینت از بازار برداشته شد."


def list_for_sale_all() -> list[dict]:
    return list(land_col().find({"listed_price": {"$ne": None}}))


def buy_listed_land(buyer_uid: int, buyer_player: dict, map_name: str, plot_id: int) -> tuple[bool, str]:
    if get_my_land(buyer_uid):
        return False, "❌ همین الان یه زمین داری — اول باید بفروشیش یا رهاش کنی."
    doc = land_col().find_one({"_id": _plot_key(map_name, plot_id)})
    if not doc or not doc.get("listed_price"):
        return False, "❌ این زمین رو بازار نیست."
    if doc["owner"] == buyer_uid:
        return False, "❌ این زمینِ خودته!"
    price = doc["listed_price"]
    if buyer_player.get("zen", 0) < price:
        return False, f"❌ برای این زمین به {price:,} Zen نیاز داری."
    seller_uid = doc["owner"]
    buyer_player["zen"] -= price
    # فروشنده پول رو مستقیم تو دیتابیس می‌گیره (آنلاین نیست لزوماً)
    from database import players_col
    players_col().update_one({"_id": seller_uid}, {"$inc": {"zen": price}})
    land_col().update_one({"_id": doc["_id"]}, {"$set": {
        "owner": buyer_uid, "owner_name": buyer_player.get("name", "—"),
        "bought_at": time.time(), "listed_price": None, "rent_income_since": time.time(),
    }})
    return True, f"🗺️ زمینِ {doc['map']} (پلاک {doc['plot_id']+1}) رو به {price:,} Zen خریدی!"


# ─── اجاره‌ی زمین ────────────────────────────────────────────────
def _accrue_rent(doc: dict) -> int:
    if not doc.get("renter"):
        return 0
    elapsed = time.time() - doc.get("rent_income_since", time.time())
    hours = min(elapsed / 3600, RENT_MAX_ACCRUAL_HOURS)
    earned = int(hours * doc.get("rent_price", 0) / 24)  # rent_price هزینه‌ی هر ۲۴ساعته، پس تقسیم بر ۲۴
    if earned > 0:
        land_col().update_one({"_id": doc["_id"]}, {
            "$inc": {"rent_vault": earned},
            "$set": {"rent_income_since": time.time()},
        })
        doc["rent_vault"] = doc.get("rent_vault", 0) + earned
    return earned


def set_rent_price(uid: int, price_per_day: int) -> tuple[bool, str]:
    doc = get_my_land(uid)
    if not doc:
        return False, "❌ هنوز زمینی نداری."
    if doc.get("listed_price"):
        return False, "❌ زمینی که رو بازارِ فروشه رو نمی‌شه اجاره داد — اول از بازار بردار."
    if price_per_day <= 0:
        return False, "❌ قیمتِ اجاره باید مثبت باشه."
    land_col().update_one({"_id": doc["_id"]}, {"$set": {"rent_price": price_per_day}})
    return True, f"🔑 زمینت با قیمتِ {price_per_day:,} Zen/روز آماده‌ی اجاره‌ست."


def rent_land(renter_uid: int, renter_player: dict, map_name: str, plot_id: int) -> tuple[bool, str]:
    doc = land_col().find_one({"_id": _plot_key(map_name, plot_id)})
    if not doc or not doc.get("rent_price"):
        return False, "❌ این زمین اجاره‌ای نیست."
    if doc["owner"] == renter_uid:
        return False, "❌ این زمینِ خودته!"
    if doc.get("renter") and doc.get("renter_until", 0) > time.time():
        return False, "❌ این زمین همین الان اجاره‌ی یه بازیکنِ دیگه‌ست."
    price = doc["rent_price"]
    if renter_player.get("zen", 0) < price:
        return False, f"❌ برای اجاره‌ی این زمین (۲۴ ساعت) به {price:,} Zen نیاز داری."
    renter_player["zen"] -= price
    land_col().update_one({"_id": doc["_id"]}, {"$set": {
        "renter": renter_uid, "renter_until": time.time() + RENT_DURATION,
        "rent_income_since": time.time(),
    }, "$inc": {"rent_vault": price}})
    return True, f"🔑 زمینِ {map_name} (پلاک {plot_id+1}) رو برای ۲۴ ساعت اجاره کردی."


def is_renting(uid: int, map_name: str) -> bool:
    """چک می‌کنه بازیکن الان تو map_name یه زمینِ اجاره‌ایِ فعال داره یا نه."""
    doc = land_col().find_one({"map": map_name, "renter": uid})
    return bool(doc and doc.get("renter_until", 0) > time.time())


def collect_rent_income(uid: int) -> tuple[bool, str]:
    doc = get_my_land(uid)
    if not doc:
        return False, "❌ هنوز زمینی نداری."
    _accrue_rent(doc)
    doc = land_col().find_one({"_id": doc["_id"]})
    vault = doc.get("rent_vault", 0)
    if vault <= 0:
        return False, "💤 صندوقِ اجاره‌ی زمینت خالیه."
    land_col().update_one({"_id": doc["_id"]}, {"$set": {"rent_vault": 0}})
    from database import players_col
    players_col().update_one({"_id": uid}, {"$inc": {"zen": vault}})
    return True, f"💰 {vault:,} Zen از درآمدِ اجاره‌ی زمینت برداشت کردی."


def land_summary_text(uid: int) -> str:
    doc = get_my_land(uid)
    if not doc:
        return "🗺️ هنوز هیچ زمینی نداری. از منوی زمین‌های هر نقشه یکی بخر."
    _accrue_rent(doc)
    doc = land_col().find_one({"_id": doc["_id"]})
    size = LAND_SIZES[doc["size"]]
    lines = [
        f"🗺️ **زمینت:** {doc['map']} — پلاکِ {doc['plot_id']+1} ({size['name']})",
        f"🏗 سقفِ سطحِ خونه‌ی مجاز: {size['max_house_tier']+1}/{len(LAND_SIZES)+2}",
    ]
    if doc.get("listed_price"):
        lines.append(f"🏷️ رو بازارِ فروش: {doc['listed_price']:,} Zen")
    if doc.get("rent_price"):
        renter_txt = "❌ فعلاً مستأجر نداره"
        if doc.get("renter") and doc.get("renter_until", 0) > time.time():
            remain_h = int((doc["renter_until"] - time.time()) // 3600) + 1
            renter_txt = f"✅ مستأجر داره ({remain_h}h مونده)"
        lines.append(f"🔑 اجاره: {doc['rent_price']:,} Zen/روز — {renter_txt}")
        lines.append(f"💼 صندوقِ اجاره: {doc.get('rent_vault', 0):,} Zen")
    return "\n".join(lines)
