# ============================================================
#  ASTRAL ABYSS RPG — Persistent Shop 🏪  (v2 — عمیق‌سازی‌شده)
#  هر بازیکن یه مغازه‌ی دائمیِ زیرِ پروفایلش داره. برخلاف حراجی
#  (که موقتیه)، این همیشه سرِ جاشه؛ بقیه با /visit @username
#  می‌تونن ببیننش و بخرن. روایت: تو دنیایی که Abyss داره می‌بلعتش،
#  هرچی معامله بشه یعنی هنوز یه رگِ زندگی باقی مونده.
#
#  v2 اضافه کرد:
#   • استوک/دسته‌ای — چند کالای هم‌اسم رو با یه قیمت با هم می‌ذاری،
#     یه‌جایگاه مصرف می‌کنن ولی تک‌تک فروخته می‌شن تا موجودی صفر شه.
#   • چانه‌زنی — بازدیدکننده می‌تونه زیرِ قیمت پیشنهاد بده؛ شانسِ
#     قبولی به درصدِ تخفیف و اعتبارِ مغازه بستگی داره (حداکثر ۳ تلاش
#     رو هر کالا، بعدش فروشنده «رنجیده» می‌شه و قفل می‌کنه).
#   • تخصصی‌سازی — سقفِ ریرتیِ قابل‌فروش بر اساس سطحِ مالک؛ جلوی
#     سیل‌شدنِ بازار با آیتم‌های خیلی بالاتر از پیشرفتِ واقعیِ بازیکن
#     رو می‌گیره.
# ============================================================
import time, random, uuid

from item_system import RARITY_ORDER, RARITY_DATA, rarity_index

SHOP_TIERS = [
    {"name": "🪵 بساطِ کنارِ جاده", "cost": 0,      "slots": 4,  "fee_pct": 0.08},
    {"name": "🏪 غرفه‌ی ثابت",      "cost": 4000,  "slots": 8,  "fee_pct": 0.06},
    {"name": "🏬 مغازه‌ی سرپوشیده", "cost": 15000, "slots": 14, "fee_pct": 0.04},
    {"name": "🏛️ بازارگاهِ اختصاصی", "cost": 50000, "slots": 22, "fee_pct": 0.02},
]

REPUTATION_TITLES = [
    (0,   "🌱 مغازه‌دارِ گمنام"),
    (10,  "🤝 مغازه‌دارِ قابل‌اعتماد"),
    (30,  "⭐ مغازه‌دارِ محبوب"),
    (60,  "💎 افسانه‌ی بازارِ آبیس"),
]

# پناهنده‌های آبیس — NPCهایی که هرروز ممکنه سر بزنن و خرید کنن
REFUGEE_NAMES = [
    "یه پناهنده‌ی خسته از Verdant Vale",
    "یه بازمانده از Frostheim",
    "یه سیاح گمشده از Dragonnest Peaks",
    "یه روحِ سرگردانِ Shadow Rift",
    "یه تاجرِ دوره‌گردِ Emberhollow",
]

# ─── تخصصی‌سازی — سقفِ ریرتیِ قابل‌فروش بر اساسِ سطحِ مالک ─────────
# (min_level, max_rarity) — صعودی؛ آخرین آستانه‌ی رد‌شده اعمال می‌شه.
SHOP_LEVEL_RARITY_CAP = [
    (1,   "rare"),
    (20,  "epic"),
    (40,  "mythic"),
    (70,  "legendary"),
    (100, "ancient"),
    (140, "astral"),
    (170, "void"),
    (190, "celestial"),
    (200, "transcendent"),
]

# ─── چانه‌زنی — تیونیبل‌ها ──────────────────────────────────────
MIN_HAGGLE_PCT      = 0.6       # نمی‌شه زیرِ ۶۰٪ قیمتِ پایه چانه زد
MAX_HAGGLE_ATTEMPTS = 3
HAGGLE_LOCKOUT_SEC  = 6 * 3600  # بعدِ ۳ شکست، ۶ ساعت قفل
HAGGLE_ANNOY_STEP   = 0.04      # هر شکست ۴٪ به قیمتِ مؤثر اضافه می‌کنه
HAGGLE_ANNOY_CAP    = 0.20


def ensure_shop(player: dict) -> dict:
    shop = player.setdefault("shop", {
        "name": f"مغازه‌ی {player.get('name','ناشناس')}",
        "tier": 0, "listings": [], "reputation": 0, "ratings": [],
        "total_sales": 0, "last_refugee_visit": 0,
    })
    _normalize_shop(shop)
    return shop


def _normalize_shop(shop: dict) -> None:
    """listingهای قدیمی (schema تک‌آیتمیِ v1: {'item':..,'price':..}) رو
    به schema جدیدِ استوکی ({'items':[...], 'listing_id':.., ...}) تبدیل
    می‌کنه. یه‌بار برای هر listing انجام می‌شه و بعدش دیگه دست نمی‌خوره."""
    for l in shop.get("listings", []):
        if "items" not in l:
            it = l.pop("item", None)
            l["items"] = [it] if it else []
            l["listing_id"] = (it or {}).get("id") or uuid.uuid4().hex[:10]
            l["name"]   = (it or {}).get("name", "—")
            l["emoji"]  = (it or {}).get("emoji", "📦")
            l["rarity"] = (it or {}).get("rarity", "common")
        l.setdefault("listing_id", uuid.uuid4().hex[:10])
        l.setdefault("haggle", {})


def tier_data(shop: dict) -> dict:
    return SHOP_TIERS[shop.get("tier", 0)]


def reputation_title(shop: dict) -> str:
    rep = shop.get("reputation", 0)
    title = REPUTATION_TITLES[0][1]
    for threshold, t in REPUTATION_TITLES:
        if rep >= threshold:
            title = t
    return title


def max_listable_rarity(player: dict) -> str:
    lvl = player.get("level", 1)
    cap = SHOP_LEVEL_RARITY_CAP[0][1]
    for min_lvl, rarity in SHOP_LEVEL_RARITY_CAP:
        if lvl >= min_lvl:
            cap = rarity
    return cap


def max_listable_rarity_label(player: dict) -> str:
    cap = max_listable_rarity(player)
    data = RARITY_DATA.get(cap, {})
    return f"{data.get('emoji','⚪')} {data.get('label', cap)}"


def can_list_item(player: dict, item: dict) -> tuple[bool, str]:
    cap = max_listable_rarity(player)
    if rarity_index(item.get("rarity", "common")) > rarity_index(cap):
        return False, (
            f"🔒 سطحت هنوز کافی نیست! با سطحِ فعلیت فقط تا ریرتیِ "
            f"{max_listable_rarity_label(player)} می‌تونی تو مغازه‌ت بفروشی."
        )
    return True, ""


def rename_shop(player: dict, new_name: str) -> tuple[bool, str]:
    if len(new_name) < 2 or len(new_name) > 30:
        return False, "❌ اسم باید بین ۲ تا ۳۰ کاراکتر باشه."
    shop = ensure_shop(player)
    shop["name"] = new_name
    return True, f"✅ اسم مغازه‌ت شد: **{new_name}**"


def upgrade_shop(player: dict) -> tuple[bool, str]:
    shop = ensure_shop(player)
    cur = shop.get("tier", 0)
    if cur + 1 >= len(SHOP_TIERS):
        return False, "🏛️ مغازه‌ت از قبل بالاترین سطحه!"
    nxt = SHOP_TIERS[cur + 1]
    if player.get("zen", 0) < nxt["cost"]:
        return False, f"❌ برای ارتقا به {nxt['name']} به {nxt['cost']:,} Zen نیاز داری."
    player["zen"] -= nxt["cost"]
    shop["tier"] = cur + 1
    return True, f"🎉 مغازه‌ت شد: **{nxt['name']}**! ({nxt['slots']} جایگاه، کارمزد {int(nxt['fee_pct']*100)}٪)"


def list_items(player: dict, items: list, price: int) -> tuple[bool, str]:
    """یه یا چند آیتمِ هم‌اسم رو (یه استوک) با یه قیمتِ واحد تو مغازه می‌ذاره.
    کل استوک فقط یه جایگاه از مغازه مصرف می‌کنه."""
    if price < 50:
        return False, "❌ حداقل قیمت ۵۰ Zenه."
    if not items:
        return False, "❌ آیتمی انتخاب نشده."
    ok, why = can_list_item(player, items[0])
    if not ok:
        return False, why
    shop = ensure_shop(player)
    tier = tier_data(shop)
    if len(shop["listings"]) >= tier["slots"]:
        return False, f"❌ مغازه‌ت پره ({tier['slots']} جایگاه). ارتقا بده یا یه چیزی رو بردار."
    inv = player.get("inventory", [])
    picked = []
    for it in items:
        idx = next((i for i, x in enumerate(inv) if x.get("id") == it.get("id")), None)
        if idx is None:
            continue
        picked.append(inv.pop(idx))
    if not picked:
        return False, "❌ این آیتم‌ها دیگه تو کوله‌پشتیت نیستن."
    listing = {
        "listing_id": uuid.uuid4().hex[:10],
        "name":   picked[0].get("name", "—"),
        "emoji":  picked[0].get("emoji", "📦"),
        "rarity": picked[0].get("rarity", "common"),
        "items":  picked,
        "price":  price,
        "listed_at": time.time(),
        "haggle": {},
    }
    shop["listings"].append(listing)
    qty_note = f" ×{len(picked)}" if len(picked) > 1 else ""
    unit_note = "/عدد" if len(picked) > 1 else ""
    return True, f"✅ **{listing['name']}**{qty_note} با قیمت {price:,} Zen{unit_note} تو مغازه‌ت گذاشته شد."


def remove_listing(player: dict, listing_id: str) -> tuple[bool, str]:
    shop = ensure_shop(player)
    idx = next((i for i, l in enumerate(shop["listings"]) if l.get("listing_id") == listing_id), None)
    if idx is None:
        return False, "❌ این کالا تو مغازه‌ت نیست."
    listing = shop["listings"].pop(idx)
    inv = player.setdefault("inventory", [])
    inv.extend(listing["items"])
    qty_note = f" ({len(listing['items'])} عدد)" if len(listing["items"]) > 1 else ""
    return True, f"↩️ **{listing['name']}**{qty_note} به کوله‌پشتیت برگشت."


def get_shop(owner: dict) -> dict:
    return ensure_shop(owner)


def _find_listing(shop: dict, listing_id: str):
    return next((l for l in shop["listings"] if l.get("listing_id") == listing_id), None)


def buy_from_shop(buyer: dict, owner: dict, listing_id: str, unit_price: int = None) -> tuple[bool, str, dict]:
    """یه واحد از یه استوک می‌خره. اگه unit_price داده بشه (نتیجه‌ی یه
    چانه‌زنیِ موفق) به‌جای قیمتِ لیست‌شده همون به کار می‌ره."""
    if buyer.get("id") == owner.get("id"):
        return False, "❌ نمی‌تونی از خودت بخری!", None
    shop = ensure_shop(owner)
    listing = _find_listing(shop, listing_id)
    if not listing or not listing["items"]:
        return False, "❌ این آیتم دیگه موجود نیست.", None
    price = unit_price if unit_price is not None else listing["price"]
    if buyer.get("zen", 0) < price:
        return False, "❌ Zen کافی نداری.", None

    item = listing["items"].pop(0)
    buyer["zen"] -= price
    buyer.setdefault("inventory", []).append(item)
    sold_out = not listing["items"]
    if sold_out:
        shop["listings"].remove(listing)
    fee_pct = tier_data(shop)["fee_pct"]
    owner_gain = int(price * (1 - fee_pct))
    shop["total_sales"] = shop.get("total_sales", 0) + 1
    return True, f"✅ **{item['name']}** رو خریدی!", {
        "owner_gain": owner_gain, "item_name": item["name"], "sold_out": sold_out,
    }


def haggle_offer(buyer_uid: int, owner: dict, listing_id: str, offer_price: int) -> tuple[bool, str, dict]:
    """بازدیدکننده زیرِ قیمتِ لیست‌شده پیشنهاد می‌ده. شانسِ قبولی به
    درصدِ تخفیفِ درخواستی و اعتبارِ مغازه بستگی داره. حداکثر ۳ تلاش
    رو هر کالا؛ بعدِ شکست، قیمتِ مؤثر برای همون خریدار کمی بالا
    می‌ره (فروشنده «رنجیده») و بعدِ ۳اُمین شکست تا ۶ ساعت قفل می‌شه."""
    shop = ensure_shop(owner)
    listing = _find_listing(shop, listing_id)
    if not listing or not listing["items"]:
        return False, "❌ این آیتم دیگه موجود نیست.", None

    base_price = listing["price"]
    key = str(buyer_uid)
    hag = listing.setdefault("haggle", {}).setdefault(
        key, {"attempts": 0, "locked_until": 0, "annoy": 0.0}
    )
    now = time.time()
    if now < hag["locked_until"]:
        mins = max(1, int((hag["locked_until"] - now) / 60))
        return False, f"😤 فروشنده دیگه حالِ چونه‌زدن نداره. {mins} دقیقه‌ی دیگه امتحان کن.", None
    if hag["attempts"] >= MAX_HAGGLE_ATTEMPTS:
        return False, "😤 دیگه تلاشِ چانه‌زنی برای این کالا نداری.", None

    effective_price = int(base_price * (1 + hag["annoy"]))
    min_price = int(base_price * MIN_HAGGLE_PCT)
    if offer_price < min_price:
        return False, f"❌ فروشنده زیرِ {min_price:,} Zen قبول نمی‌کنه.", None
    if offer_price >= effective_price:
        return False, "🤨 همین‌جوری با همون قیمت بخر، نیازی به چانه‌زنی نیست.", None

    discount_pct = 1 - (offer_price / effective_price)
    rep = min(60, owner.get("shop", {}).get("reputation", 0))
    chance = 0.85 - discount_pct * 2.0 + rep * 0.003
    chance = max(0.05, min(0.9, chance))

    hag["attempts"] += 1
    if random.random() < chance:
        hag["locked_until"] = 0
        return True, f"🤝 قبول کرد! قیمتِ نهایی: {offer_price:,} Zen.", {"price": offer_price}

    hag["annoy"] = min(HAGGLE_ANNOY_CAP, hag["annoy"] + HAGGLE_ANNOY_STEP)
    if hag["attempts"] >= MAX_HAGGLE_ATTEMPTS:
        hag["locked_until"] = now + HAGGLE_LOCKOUT_SEC
        return False, "❌ رد کرد. دیگه حالِ چونه نداره — قیمت هم یه‌کم بالا رفت. (۶ ساعت قفل)", None
    left = MAX_HAGGLE_ATTEMPTS - hag["attempts"]
    return False, f"❌ رد کرد. {left} تلاشِ دیگه داری (قیمتِ مؤثر یه‌کم بالا رفت).", None


def rate_shop(owner: dict, rater_uid: int, stars: int) -> tuple[bool, str]:
    if stars < 1 or stars > 5:
        return False, "❌ امتیاز باید بین ۱ تا ۵ باشه."
    shop = ensure_shop(owner)
    ratings = shop.setdefault("ratings", [])
    ratings[:] = [r for r in ratings if r.get("uid") != rater_uid]
    ratings.append({"uid": rater_uid, "stars": stars})
    shop["reputation"] = sum(r["stars"] for r in ratings)
    return True, "✅ امتیازت ثبت شد."


def maybe_refugee_visit(owner: dict):
    """یه‌بار در روز، شانس داره یه پناهنده‌ی آبیس یه واحد از یکی از
    استوک‌های مغازه رو بخره (درآمد غیرفعال)."""
    shop = ensure_shop(owner)
    if not shop["listings"]:
        return None
    last = shop.get("last_refugee_visit", 0)
    if time.time() - last < 20 * 3600:
        return None
    if random.random() > 0.5:
        shop["last_refugee_visit"] = time.time()
        return None
    listing = random.choice(shop["listings"])
    item = listing["items"].pop(0)
    if not listing["items"]:
        shop["listings"].remove(listing)
    fee_pct = tier_data(shop)["fee_pct"]
    gain = int(listing["price"] * (1 - fee_pct))
    owner["zen"] = owner.get("zen", 0) + gain
    shop["total_sales"] = shop.get("total_sales", 0) + 1
    shop["last_refugee_visit"] = time.time()
    return {"buyer": random.choice(REFUGEE_NAMES), "item_name": item["name"], "gain": gain}
