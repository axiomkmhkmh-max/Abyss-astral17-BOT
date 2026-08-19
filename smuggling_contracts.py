# ============================================================
#  ASTRAL ABYSS — Smuggling Contracts (تابلوی قاچاقِ بازیکن‌محور)
# ------------------------------------------------------------
#  برخلافِ contract_system.py (که کارگزارِ NPC، سرنخِ کیارَش می‌ده) و
#  auction_system.py (مزایده‌ی زنده)، این یه تابلوی سفارشِ مستقیمه:
#  بازیکنِ A می‌گه «فلان آیتم رو با فلان تعداد بیار فلان نقشه، Zen
#  می‌دم». بازیکنِ B هرجا اون آیتم رو تو کوله‌پشتیش داشته باشه،
#  می‌تونه تحویل بده و پولو نقد بگیره. Zenِ سفارش‌دهنده همون لحظه‌ی
#  ثبت بلوکه (escrow) می‌شه؛ اگه کسی تحویل نده، بعد از انقضا خودکار
#  برمی‌گرده.
# ============================================================
from __future__ import annotations

import time
import uuid

import black_market_reputation as bmrep

CONTRACT_DURATION = 12 * 3600
MAX_ACTIVE_PER_PLAYER = 3
SMUGGLER_TAX_PCT = 0.08          # از پاداشِ تحویل‌دهنده کسر می‌شه (Zen sink)
BIG_CONTRACT_BOUNTY_CAP = 50_000
NORMAL_CONTRACT_BOUNTY_CAP = 15_000


def _col():
    from database import smuggling_col
    return smuggling_col()


def _bounty_cap(player: dict) -> int:
    return BIG_CONTRACT_BOUNTY_CAP if bmrep.has_unlock(player, "big_contracts") else NORMAL_CONTRACT_BOUNTY_CAP


def post_contract(player: dict, item_name: str, qty: int, dest_map: str, bounty: int) -> tuple[bool, str]:
    if not bmrep.has_unlock(player, "smuggling"):
        return False, "🔒 رتبه‌ی «معتمد» یا بالاتر لازمه تا رو تابلوی قاچاق سفارش بذاری."
    if qty <= 0 or bounty <= 0:
        return False, "❌ تعداد و پاداش باید مثبت باشن."
    cap = _bounty_cap(player)
    if bounty > cap:
        return False, f"❌ سقفِ پاداشِ رتبه‌ات {cap:,} Zenه."
    uid = player.get("id")
    active_count = _col().count_documents({"poster_id": uid, "status": "open"})
    if active_count >= MAX_ACTIVE_PER_PLAYER:
        return False, f"❌ حداکثر {MAX_ACTIVE_PER_PLAYER} قراردادِ باز هم‌زمان می‌تونی داشته باشی."
    if player.get("zen", 0) < bounty:
        return False, f"❌ {bounty:,} Zen برای escrow لازمه، نداری."

    player["zen"] -= bounty
    now = time.time()
    doc = {
        "_id": uuid.uuid4().hex[:10],
        "poster_id": uid,
        "poster_name": player.get("name", "—"),
        "item_name": item_name,
        "qty": qty,
        "dest_map": dest_map,
        "bounty": bounty,
        "status": "open",
        "created_at": now,
        "expires_at": now + CONTRACT_DURATION,
        "fulfilled_by": None,
    }
    _col().insert_one(doc)
    return True, (f"📦 قراردادِ قاچاق ثبت شد: {qty}x **{item_name}** → {dest_map}\n"
                  f"💰 پاداش: {bounty:,} Zen (بلوکه‌شده تا وقتی تحویل داده بشه)")


def open_contracts(dest_map: str | None = None, exclude_uid: int | None = None) -> list[dict]:
    _expire_old()
    q = {"status": "open"}
    if dest_map:
        q["dest_map"] = dest_map
    if exclude_uid is not None:
        q["poster_id"] = {"$ne": exclude_uid}
    return list(_col().find(q).sort("created_at", -1).limit(20))


def my_contracts(uid: int) -> list[dict]:
    _expire_old()
    return list(_col().find({"poster_id": uid}).sort("created_at", -1).limit(10))


def _expire_old() -> None:
    now = time.time()
    expired = list(_col().find({"status": "open", "expires_at": {"$lte": now}}))
    if not expired:
        return
    from database import get_player, save_player
    for c in expired:
        poster = get_player(c["poster_id"])
        if poster:
            poster["zen"] = poster.get("zen", 0) + c["bounty"]
            save_player(c["poster_id"], poster)
        _col().update_one({"_id": c["_id"]}, {"$set": {"status": "expired"}})


def _count_named(player: dict, name: str) -> int:
    return sum(1 for it in player.get("inventory", []) if it.get("name") == name)


def _consume_named(player: dict, name: str, need: int) -> None:
    inv = player.get("inventory", [])
    removed = 0
    new_inv = []
    for it in inv:
        if removed < need and it.get("name") == name:
            removed += 1
            continue
        new_inv.append(it)
    player["inventory"] = new_inv


def fulfill_contract(fulfiller: dict, contract_id: str) -> tuple[bool, str]:
    from database import get_player, save_player
    from economy_engine import add_reputation

    doc = _col().find_one({"_id": contract_id, "status": "open"})
    if not doc:
        return False, "❌ این قرارداد دیگه فعال نیست."
    if doc["poster_id"] == fulfiller.get("id"):
        return False, "❌ نمی‌تونی سفارشِ خودتو تحویل بدی."
    if fulfiller.get("map") != doc["dest_map"]:
        return False, f"❌ باید تو نقشه‌ی **{doc['dest_map']}** باشی تا تحویل بدی."
    if _count_named(fulfiller, doc["item_name"]) < doc["qty"]:
        return False, f"❌ {doc['qty']}x {doc['item_name']} تو کوله‌پشتیت نداری."

    # اتمیک: فقط اگه هنوز open بود claim کن (جلوگیری از دو نفر هم‌زمان)
    claimed = _col().find_one_and_update(
        {"_id": contract_id, "status": "open"},
        {"$set": {"status": "fulfilled", "fulfilled_by": fulfiller.get("id")}},
    )
    if not claimed:
        return False, "❌ یکی دیگه زودتر تحویل داد."

    _consume_named(fulfiller, doc["item_name"], doc["qty"])
    net = int(doc["bounty"] * (1 - SMUGGLER_TAX_PCT))
    fulfiller["zen"] = fulfiller.get("zen", 0) + net
    add_reputation(fulfiller, 4)

    poster = get_player(doc["poster_id"])
    if poster:
        poster.setdefault("inventory", []).append({
            "name": doc["item_name"], "emoji": "📦", "sell": 0,
            "note": f"تحویل‌شده از قاچاق (از طرفِ {fulfiller.get('name','—')})",
        })
        save_player(doc["poster_id"], poster)

    return True, (f"✅ تحویل دادی! {net:,} Zen گرفتی "
                  f"(از {doc['bounty']:,}، {int(SMUGGLER_TAX_PCT*100)}٪ مالیاتِ قاچاق کسر شد).\n"
                  f"📈 +4 رپیوتیشن")


def cancel_contract(player: dict, contract_id: str) -> tuple[bool, str]:
    doc = _col().find_one({"_id": contract_id, "status": "open"})
    if not doc or doc["poster_id"] != player.get("id"):
        return False, "❌ این قراردادِ تو نیست یا دیگه فعال نیست."
    player["zen"] = player.get("zen", 0) + doc["bounty"]
    _col().update_one({"_id": contract_id}, {"$set": {"status": "cancelled"}})
    return True, f"↩️ قرارداد لغو شد. {doc['bounty']:,} Zen برگشت."
