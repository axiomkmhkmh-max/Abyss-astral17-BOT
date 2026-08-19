# ============================================================
#  ASTRAL ABYSS RPG — Auction House 🏛️  (v2 — مزایده‌ی زنده)
#  بازیکنا آیتم از کوله‌پشتیشون رو با یه قیمتِ شروع می‌ذارن حراج؛
#  بقیه روی هم پیشنهاد می‌دن. امکاناتِ این نسخه:
#   • نوتیفِ مستقیم به بازیکنِ قبلی وقتی از پیشنهادش جلو می‌زنن
#   • auto-bid با یه سقفِ مخفی (proxy bidding به سبکِ eBay)
#   • تمدیدِ خودکارِ زمان اگه پیشنهادِ جدید تو ۳۰ ثانیه‌ی آخر بیاد (ضدِ اسنایپ)
#  Zenِ هر پیشنهاد بلافاصله بلوکه (escrow) می‌شه؛ اگه جلو زده بشی
#  همون لحظه بهت برمی‌گرده. مالیاتِ فروش = Zen sink.
# ============================================================
import time, uuid
from database import auction_col, get_player, save_player
from logger import notify_user_sync
from economy_ledger import record_transaction

LISTING_FEE_PCT   = 0.03      # هزینه‌ی درج آگهی — از موجودی کسر و غیرقابل‌استرداده
SALE_TAX_PCT      = 0.10      # مالیات فروشِ موفق (از سهمِ فروشنده کسر می‌شه)
LISTING_DURATION  = 24 * 3600
MAX_ACTIVE_LISTINGS = 5
MIN_PRICE = 100

ANTI_SNIPE_WINDOW = 30    # اگه کمتر از این مونده به پایان، پیشنهادِ جدید زمان رو تمدید می‌کنه
ANTI_SNIPE_EXTEND = 30    # مقدارِ تمدید (ثانیه)

MIN_INCREMENT_PCT = 0.05  # حداقلِ افزایشِ هر پیشنهاد نسبت به پیشنهادِ فعلی
MIN_INCREMENT_FLOOR = 50  # کفِ مطلقِ افزایش


def _increment(current: int) -> int:
    return max(MIN_INCREMENT_FLOOR, int(current * MIN_INCREMENT_PCT))


def create_listing(player: dict, item: dict, starting_price: int) -> tuple[bool, str]:
    if starting_price < MIN_PRICE:
        return False, f"❌ حداقل قیمتِ شروع {MIN_PRICE:,} Zenه."
    uid = player.get("id")
    active = list(auction_col().find({"seller_id": uid, "status": "active"}))
    if len(active) >= MAX_ACTIVE_LISTINGS:
        return False, f"❌ حداکثر {MAX_ACTIVE_LISTINGS} آگهی هم‌زمان می‌تونی داشته باشی."

    fee = int(starting_price * LISTING_FEE_PCT)
    if player.get("zen", 0) < fee:
        return False, f"❌ برای درج آگهی {fee:,} Zen هزینه لازمه (نداری)."

    inv = player.get("inventory", [])
    idx = next((i for i, it in enumerate(inv) if it.get("id") == item.get("id")), None)
    if idx is None:
        return False, "❌ این آیتم دیگه تو کوله‌پشتیت نیست."
    if inv[idx].get("shop_exclusive"):
        return False, "🔒 این آیتم مخصوصِ مغازه‌ی شخصیته — تو حراجی قابلِ فروش نیست."

    player["zen"] -= fee
    listed_item = inv.pop(idx)
    doc = {
        "_id": uuid.uuid4().hex[:10],
        "seller_id": uid,
        "seller_name": player.get("name", "—"),
        "item": listed_item,
        "starting_price": starting_price,
        "current_bid": None,
        "current_bidder_id": None,
        "current_bidder_name": None,
        "leader_auto_cap": None,
        "bid_count": 0,
        "listed_at": time.time(),
        "expires_at": time.time() + LISTING_DURATION,
        "status": "active",
    }
    auction_col().insert_one(doc)
    record_transaction(
        "auction_list", uid, username=player.get("name"),
        item_name=listed_item.get("name"), item_id=listed_item.get("id"), rarity=listed_item.get("rarity"),
        amount=fee, balance_before=player["zen"] + fee, balance_after=player["zen"],
        extra={"listing_id": doc["_id"], "starting_price": starting_price},
    )
    return True, f"✅ **{listed_item.get('name')}** با قیمتِ شروعِ {starting_price:,} Zen تو حراجی گذاشته شد."


def get_active_listings(exclude_uid: int | None = None, limit: int = 20) -> list[dict]:
    settle_expired_listings()
    q = {"status": "active"}
    if exclude_uid is not None:
        q["seller_id"] = {"$ne": exclude_uid}
    return list(auction_col().find(q).sort("listed_at", -1).limit(limit))


def get_my_listings(uid: int) -> list[dict]:
    settle_expired_listings()
    return list(auction_col().find({"seller_id": uid, "status": "active"}))


def get_my_bids(uid: int) -> list[dict]:
    settle_expired_listings()
    return list(auction_col().find({"status": "active", "current_bidder_id": uid}))


def get_listing(listing_id: str) -> dict | None:
    return auction_col().find_one({"_id": listing_id})


def min_next_bid(doc: dict) -> int:
    if doc.get("current_bid"):
        return doc["current_bid"] + _increment(doc["current_bid"])
    return doc["starting_price"]


def place_bid(bidder: dict, listing_id: str, bid_amount: int, auto_cap: int | None = None) -> tuple[bool, str]:
    """یه پیشنهاد رو ثبت می‌کنه. bidder باید از قبل تو دیتابیس save بشه بعدِ این تابع
    (چون خودِ تابع فقط شیءِ دیکشنریِ bidder رو تغییر می‌ده، مثلِ بقیه‌ی سیستم‌ها)."""
    doc = get_listing(listing_id)
    if not doc or doc.get("status") != "active":
        return False, "❌ این آگهی دیگه فعال نیست."
    if doc["seller_id"] == bidder.get("id"):
        return False, "❌ نمی‌تونی رو جنسِ خودت پیشنهاد بدی!"
    if doc["expires_at"] < time.time():
        return False, "⏰ زمانِ این آگهی تموم شده."

    need = min_next_bid(doc)
    if bid_amount < need:
        return False, f"❌ حداقلِ پیشنهادِ لازم {need:,} Zenه."
    if auto_cap is not None and auto_cap < bid_amount:
        auto_cap = None
    if bidder.get("zen", 0) < bid_amount:
        return False, f"❌ Zen کافی نداری (لازم: {bid_amount:,})."

    bidder_id = bidder.get("id")
    leader_id = doc.get("current_bidder_id")
    leader_cap = doc.get("leader_auto_cap")
    leader_bid = doc.get("current_bid")
    item_name = doc["item"].get("name", "آیتم")

    # ─── سناریو ۱: رقیبِ فعلی auto-bid فعال داره و سقفش از پیشنهادِ جدید بیشتره ──
    if leader_id and leader_id != bidder_id and leader_cap and leader_cap >= bid_amount:
        new_price = min(leader_cap, bid_amount + _increment(bid_amount))
        leader_player = get_player(leader_id)
        needed_extra = new_price - leader_bid
        if leader_player and leader_player.get("zen", 0) >= needed_extra:
            zen_before_leader = leader_player["zen"]
            leader_player["zen"] -= needed_extra
            save_player(leader_id, leader_player)
            auction_col().update_one({"_id": listing_id}, {"$set": {
                "current_bid": new_price,
            }, "$inc": {"bid_count": 1}})
            _maybe_extend(listing_id, doc)
            record_transaction(
                "auction_autobid_charge", leader_id, username=leader_player.get("name"),
                item_name=item_name, amount=needed_extra,
                balance_before=zen_before_leader, balance_after=leader_player["zen"],
                counterparty_id=bidder_id, counterparty_name=bidder.get("name"),
                extra={"listing_id": listing_id, "new_price": new_price},
            )
            notify_user_sync(
                leader_id,
                f"🤖 **auto-bid فعال شد!** یه نفر رو **{item_name}** پیشنهادِ {bid_amount:,} Zen داد؛ "
                f"سیستم به‌جای تو خودکار تا {new_price:,} Zen بالا برد."
            )
            return False, f"🤖 یه نفرِ دیگه auto-bid فعال داره — پیشنهاد به‌طورِ خودکار رفت رو {new_price:,} Zen. Zenت بهت برنگشته چون هنوز چیزی ازت کم نشده بود."
        else:
            # رقیبِ قبلی دیگه نمی‌تونه از پسِ سقفِ خودش بربیاد — کامل ریفاند و از میدون خارج می‌شه
            if leader_player:
                zen_before_leader = leader_player.get("zen", 0)
                leader_player["zen"] = leader_player.get("zen", 0) + leader_bid
                save_player(leader_id, leader_player)
                record_transaction(
                    "auction_bid_refund", leader_id, username=leader_player.get("name"),
                    item_name=item_name, amount=leader_bid,
                    balance_before=zen_before_leader, balance_after=leader_player["zen"],
                    note="auto-bid cap insufficient", extra={"listing_id": listing_id},
                )
                notify_user_sync(leader_id, f"⚠️ auto-bidِ تو رو **{item_name}** دیگه قابلِ اجرا نبود (Zen کافی نداشتی) — {leader_bid:,} Zen بهت برگشت.")
            # ادامه می‌ره به سناریوی ۲ (این پیشنهاددهنده لیدرِ جدید می‌شه)

    # ─── سناریو ۲: پیشنهاددهنده‌ی جدید لیدرِ جدید می‌شه ─────────────
    if leader_id and leader_id != bidder_id and leader_bid:
        prev_player = get_player(leader_id)
        if prev_player:
            zen_before_prev = prev_player.get("zen", 0)
            prev_player["zen"] = prev_player.get("zen", 0) + leader_bid
            save_player(leader_id, prev_player)
            record_transaction(
                "auction_bid_refund", leader_id, username=prev_player.get("name"),
                item_name=item_name, amount=leader_bid,
                balance_before=zen_before_prev, balance_after=prev_player["zen"],
                note="outbid", extra={"listing_id": listing_id},
            )
            notify_user_sync(
                leader_id,
                f"⚠️ از پیشنهادت رو **{item_name}** جلو زدن! پیشنهادِ جدید: {bid_amount:,} Zen. "
                f"{leader_bid:,} Zen بهت برگشت."
            )

    zen_before_bidder = bidder.get("zen", 0)
    bidder["zen"] -= bid_amount
    auction_col().update_one({"_id": listing_id}, {"$set": {
        "current_bid": bid_amount,
        "current_bidder_id": bidder_id,
        "current_bidder_name": bidder.get("name", "—"),
        "leader_auto_cap": auto_cap,
    }, "$inc": {"bid_count": 1}})
    extended = _maybe_extend(listing_id, doc)
    record_transaction(
        "auction_bid", bidder_id, username=bidder.get("name"),
        item_name=item_name, amount=bid_amount,
        balance_before=zen_before_bidder, balance_after=bidder["zen"],
        extra={"listing_id": listing_id, "auto_cap": auto_cap},
    )
    msg = f"✅ پیشنهادِ {bid_amount:,} Zen رو **{item_name}** ثبت شد — الان بالاترین پیشنهادِ فعالی!"
    if auto_cap:
        msg += f"\n🤖 auto-bid تا سقفِ {auto_cap:,} Zen فعال شد."
    if extended:
        msg += f"\n⏱ چون تو {ANTI_SNIPE_WINDOW} ثانیه‌ی آخر بود، زمانِ آگهی {ANTI_SNIPE_EXTEND} ثانیه تمدید شد (ضدِ اسنایپ)."
    return True, msg


def _maybe_extend(listing_id: str, doc: dict) -> bool:
    remain = doc["expires_at"] - time.time()
    if remain < ANTI_SNIPE_WINDOW:
        new_expiry = time.time() + ANTI_SNIPE_EXTEND
        auction_col().update_one({"_id": listing_id}, {"$set": {"expires_at": new_expiry}})
        return True
    return False


def cancel_listing(player: dict, listing_id: str) -> tuple[bool, str]:
    doc = get_listing(listing_id)
    if not doc or doc.get("status") != "active":
        return False, "❌ این آگهی دیگه فعال نیست."
    if doc["seller_id"] != player.get("id"):
        return False, "❌ این آگهی مالِ تو نیست."
    if doc.get("current_bidder_id"):
        return False, "❌ این آگهی از قبل پیشنهاد گرفته — دیگه نمی‌شه لغوش کرد."
    player.setdefault("inventory", []).append(doc["item"])
    auction_col().update_one({"_id": listing_id}, {"$set": {"status": "cancelled"}})
    record_transaction(
        "auction_cancel", player.get("id"), username=player.get("name"),
        item_name=doc["item"].get("name"), item_id=doc["item"].get("id"),
        amount=0, extra={"listing_id": listing_id, "starting_price": doc.get("starting_price")},
    )
    return True, f"↩️ **{doc['item'].get('name')}** به کوله‌پشتیت برگشت."


def settle_expired_listings():
    """آگهی‌های منقضی‌شده رو می‌بنده. اگه پیشنهادی داشتن، برنده‌ی مزایده تعیین
    می‌شه، آیتم مستقیم به کوله‌ی خریدار می‌ره، فروشنده Zenِ سهمش رو (منهایِ
    مالیات) می‌گیره و هر دو نفر نوتیف می‌گیرن. اگه پیشنهادی نداشتن، برای
    برگشتِ آیتم به فروشنده «expired» علامت می‌خوره (با claim_expired)."""
    now = time.time()
    due = list(auction_col().find({"status": "active", "expires_at": {"$lt": now}}))
    for doc in due:
        item_name = doc["item"].get("name", "آیتم")
        if doc.get("current_bidder_id"):
            buyer_id = doc["current_bidder_id"]
            price = doc["current_bid"]
            buyer = get_player(buyer_id)
            if buyer:
                buyer.setdefault("inventory", []).append(doc["item"])
                save_player(buyer_id, buyer)
                notify_user_sync(buyer_id, f"🏛️ مزایده‌ی **{item_name}** تموم شد و تو برنده شدی! به کوله‌پشتیت اضافه شد.")
            seller = get_player(doc["seller_id"])
            seller_gain = int(price * (1 - SALE_TAX_PCT))
            if seller:
                zen_before_seller = seller.get("zen", 0)
                seller["zen"] = seller.get("zen", 0) + seller_gain
                save_player(doc["seller_id"], seller)
                record_transaction(
                    "auction_settle", doc["seller_id"], username=seller.get("name"),
                    item_name=item_name, item_id=doc["item"].get("id"), rarity=doc["item"].get("rarity"),
                    amount=seller_gain, fee=price - seller_gain,
                    balance_before=zen_before_seller, balance_after=seller["zen"],
                    counterparty_id=buyer_id, counterparty_name=doc.get("current_bidder_name"),
                    extra={"listing_id": doc["_id"], "final_price": price},
                )
                notify_user_sync(doc["seller_id"], f"🏛️ **{item_name}** تو مزایده به {price:,} Zen فروخته شد — {seller_gain:,} Zen (بعدِ مالیات) گرفتی.")
            auction_col().update_one({"_id": doc["_id"]}, {"$set": {
                "status": "sold", "buyer_id": buyer_id, "sold_at": now,
            }})
        else:
            auction_col().update_one({"_id": doc["_id"]}, {"$set": {"status": "expired"}})


# سازگاری با نامِ قدیمی که بقیه‌ی فایل‌ها ممکنه صداش بزنن
expire_listings = settle_expired_listings


def claim_expired(player: dict) -> list[str]:
    """موقع باز کردن حراجی صدا زده می‌شه — آیتم‌های بی‌خریدارِ خودِ بازیکن رو برمی‌گردونه به کوله‌پشتی."""
    uid = player.get("id")
    expired = list(auction_col().find({"seller_id": uid, "status": "expired"}))
    names = []
    for doc in expired:
        player.setdefault("inventory", []).append(doc["item"])
        auction_col().update_one({"_id": doc["_id"]}, {"$set": {"status": "returned"}})
        names.append(doc["item"].get("name", "؟"))
    return names
