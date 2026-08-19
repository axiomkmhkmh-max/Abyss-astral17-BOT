# ============================================================
#  ASTRAL ABYSS RPG — Bounty System 🎯
#  هر بازیکن می‌تونه رو سرِ یه بازیکن دیگه جایزه Zen بذاره.
#  هرکی تو دوئل PvP اون هدف رو شکست بده، کل جایزه رو می‌بره.
# ============================================================
import time
from database import bounty_col

MIN_BOUNTY = 1000
MAX_ACTIVE_BOUNTY = 200_000  # سقف جمعِ جایزه‌ی روی سرِ یه نفر (جلوگیری از تورم/سوءاستفاده)


def get_bounty(target_uid: int) -> dict:
    doc = bounty_col().find_one({"_id": str(target_uid)})
    if not doc:
        doc = {"_id": str(target_uid), "amount": 0, "contributors": {}, "placed_at": 0}
    return doc


def _save_bounty(target_uid: int, doc: dict):
    data = {k: v for k, v in doc.items() if k != "_id"}
    bounty_col().update_one({"_id": str(target_uid)}, {"$set": data}, upsert=True)


def place_bounty(player: dict, target_uid: int, amount: int) -> tuple[bool, str]:
    uid = player.get("id")
    if amount < MIN_BOUNTY:
        return False, f"❌ حداقل جایزه {MIN_BOUNTY:,} Zenه."
    if target_uid == uid:
        return False, "❌ نمی‌تونی رو سرِ خودت جایزه بذاری، رفیق!"
    if player.get("zen", 0) < amount:
        return False, "❌ Zen کافی نداری."

    doc = get_bounty(target_uid)
    if doc.get("amount", 0) + amount > MAX_ACTIVE_BOUNTY:
        return False, f"❌ سقفِ جایزه‌ی این هدف پره (حداکثر {MAX_ACTIVE_BOUNTY:,})."

    player["zen"] -= amount
    doc["amount"] = doc.get("amount", 0) + amount
    contributors = doc.setdefault("contributors", {})
    contributors[str(uid)] = contributors.get(str(uid), 0) + amount
    doc["placed_at"] = time.time()
    _save_bounty(target_uid, doc)
    return True, f"🎯 جایزه‌ی **{amount:,} Zen** رو سرِ هدف گذاشته شد!\n💰 جمع کل جایزه‌ی این هدف الان: {doc['amount']:,} Zen"


def claim_bounty(target_uid: int) -> int:
    """وقتی صاحبِ این جایزه تو PvP می‌بازه صدا زده می‌شه. جایزه رو صفر و مقدارش رو برمی‌گردونه."""
    doc = get_bounty(target_uid)
    amt = doc.get("amount", 0)
    if amt > 0:
        _save_bounty(target_uid, {"amount": 0, "contributors": {}, "placed_at": 0})
    return amt


def top_bounties(n: int = 10) -> list[dict]:
    return list(bounty_col().find({"amount": {"$gt": 0}}).sort("amount", -1).limit(n))
