# ============================================================
#  ASTRAL ABYSS RPG — Contract Board 📜 (تابلوی کارگزارِ کیارَش)
#  یه کارگزارِ مرموز، که ادعا می‌کنه داره دنبال سرنخ‌هایی از کیارَش
#  می‌گرده، هرساعت ۳ تا قرارداد کوتاه‌مدت رو تابلو می‌ذاره. رقابتیه:
#  فقط ۳ نفرِ اول که تحویل بدن، جایزه‌ی کامل می‌گیرن؛ بقیه یه
#  جایزه‌ی تسلی‌بخشِ کوچیک‌تر.
# ============================================================
import random, time

REFRESH_INTERVAL = 3600
MAX_FULL_CLAIMS = 3
CONSOLATION_MULT = 0.35

BROKER_LINES = [
    "🕵️ «هرکسی که سرنخ می‌آره، یه قدم به کیارَش نزدیک‌ترمون می‌کنه.»",
    "🕵️ «آبیس همه‌چیزو نمی‌بلعه... بعضی خاطره‌ها فرار می‌کنن. من دنبالِ همونام.»",
    "🕵️ «وقت کمه. هرچی سریع‌تر تحویل بدی، سهم بیشتری می‌بری.»",
]

CONTRACT_POOL = [
    {"id": "kills",       "kind": "kills",       "target": 6,    "title": "🗡 شکارِ ردپا",     "desc": "۶ تا دشمن بکش — شاید یکی‌شون یه خاطره از کیارَش داشته باشه.", "reward_zen": 700,  "reward_xp": 250},
    {"id": "kills_big",   "kind": "kills",       "target": 15,   "title": "🗡 پاک‌سازیِ منطقه", "desc": "۱۵ تا دشمن بکش — کارگزار به یه منطقه‌ی مشکوک اشاره کرده.",   "reward_zen": 2200, "reward_xp": 800},
    {"id": "zen_small",   "kind": "zen_tribute", "target": 1500, "title": "💰 رشوه‌ی کوچیک",    "desc": "۱۵۰۰ Zen بده — کارگزار یه نگهبان رو می‌خره.",                "reward_zen": 400,  "reward_xp": 500},
    {"id": "zen_big",     "kind": "zen_tribute", "target": 6000, "title": "💰 معامله‌ی بزرگ",   "desc": "۶۰۰۰ Zen بده — یه سرنخِ قطعی در ازاش.",                     "reward_zen": 1500, "reward_xp": 1800},
    {"id": "item_rare",   "kind": "item_rarity", "target": "rare",     "title": "📦 مدرکِ نایاب", "desc": "یه آیتمِ نایاب (rare) یا بهتر تحویل بده.",              "reward_zen": 1800, "reward_xp": 400},
    {"id": "item_epic",   "kind": "item_rarity", "target": "epic",     "title": "📦 مدرکِ حماسی", "desc": "یه آیتمِ حماسی (epic) یا بهتر تحویل بده.",              "reward_zen": 4500, "reward_xp": 900},
]


def _doc():
    from database import system_col
    doc = system_col().find_one({"_id": "contract_board"})
    if not doc or time.time() - doc.get("generated_at", 0) > REFRESH_INTERVAL:
        doc = _generate_board()
    return doc


def _generate_board() -> dict:
    from database import system_col
    picks = random.sample(CONTRACT_POOL, k=min(3, len(CONTRACT_POOL)))
    contracts = []
    for p in picks:
        c = dict(p)
        c["claims"] = []
        contracts.append(c)
    doc = {"_id": "contract_board", "generated_at": time.time(), "contracts": contracts}
    system_col().update_one({"_id": "contract_board"}, {"$set": {k: v for k, v in doc.items() if k != "_id"}}, upsert=True)
    return doc


def _save(doc: dict):
    from database import system_col
    system_col().update_one({"_id": "contract_board"}, {"$set": {k: v for k, v in doc.items() if k != "_id"}}, upsert=True)


def get_board() -> dict:
    return _doc()


def get_contract(contract_id: str) -> dict | None:
    doc = get_board()
    return next((c for c in doc["contracts"] if c["id"] == contract_id), None)


def _prune_stale_active(player: dict) -> bool:
    """🐛 فیکس: تابلو هر ساعت رفرش می‌شه و قراردادهای قدیمی از board["contracts"]
    حذف می‌شن، ولی active_contracts تو پروفایلِ بازیکن هیچ‌وقت پاک نمی‌شد —
    نتیجه: اگه بازیکن یه قرارداد رو قبول می‌کرد ولی قبل از رفرشِ بعدی تحویل
    نمی‌داد، اون قرارداد برای همیشه تو active_contracts گیر می‌کرد (چون
    get_contract دیگه پیداش نمی‌کرد) و یکی از ۲ جای‌خالیِ قرارداد رو برای
    همیشه اشغال می‌کرد — یعنی تابلو عملاً قفل می‌شد. این تابع همچین
    قراردادهایی رو موقعِ باز کردنِ تابلو/قبول‌کردن پاک می‌کنه."""
    active = player.get("active_contracts", {})
    if not active:
        return False
    doc = get_board()
    live_ids = {c["id"] for c in doc["contracts"]}
    stale = [cid for cid in active if cid not in live_ids]
    for cid in stale:
        active.pop(cid, None)
    return bool(stale)


def accept_contract(player: dict, contract_id: str) -> tuple[bool, str]:
    _prune_stale_active(player)
    contract = get_contract(contract_id)
    if not contract:
        return False, "❌ این قرارداد دیگه رو تابلو نیست (شاید عوض شده)."
    active = player.setdefault("active_contracts", {})
    if contract_id in active:
        return False, "⚠️ از قبل این قرارداد رو قبول کردی."
    if len(active) >= 2:
        return False, "❌ حداکثر ۲ قرارداد هم‌زمان می‌تونی داشته باشی."
    active[contract_id] = {"start_kills": player.get("kills", 0), "accepted_at": time.time()}
    return True, f"✅ قرارداد **{contract['title']}** پذیرفته شد."


def check_progress(player: dict, contract_id: str) -> tuple[bool, str]:
    contract = get_contract(contract_id)
    active = player.get("active_contracts", {})
    if not contract or contract_id not in active:
        return False, "❌ این قرارداد فعال نیست."

    if contract["kind"] == "kills":
        done = player.get("kills", 0) - active[contract_id].get("start_kills", 0)
        need = contract["target"]
        if done < need:
            return False, f"⏳ هنوز {need - done} کشتار دیگه لازمه ({done}/{need})."
        return True, "✅ آماده‌ی تحویله!"

    if contract["kind"] == "zen_tribute":
        if player.get("zen", 0) < contract["target"]:
            return False, f"❌ {contract['target']:,} Zen لازم داری (داری: {player.get('zen',0):,})."
        return True, "✅ آماده‌ی تحویله!"

    if contract["kind"] == "item_rarity":
        from item_system import rarity_index
        need_idx = rarity_index(contract["target"])
        has = any(rarity_index(it.get("rarity", "common")) >= need_idx for it in player.get("inventory", []))
        if not has:
            return False, f"❌ یه آیتمِ {contract['target']} یا بهتر لازم داری."
        return True, "✅ آماده‌ی تحویله!"

    return False, "❌ نوع قرارداد ناشناخته."


def turn_in(player: dict, contract_id: str) -> tuple[bool, str, dict | None]:
    ok, msg = check_progress(player, contract_id)
    if not ok:
        return False, msg, None
    contract = get_contract(contract_id)
    doc = get_board()

    # هزینه‌ی واقعی رو کسر کن
    if contract["kind"] == "zen_tribute":
        player["zen"] -= contract["target"]
    elif contract["kind"] == "item_rarity":
        from item_system import rarity_index
        need_idx = rarity_index(contract["target"])
        inv = player.get("inventory", [])
        idx = next((i for i, it in enumerate(inv) if rarity_index(it.get("rarity", "common")) >= need_idx), None)
        if idx is not None:
            inv.pop(idx)

    board_contract = next(c for c in doc["contracts"] if c["id"] == contract_id)
    is_full = len(board_contract["claims"]) < MAX_FULL_CLAIMS
    if is_full:
        zen_r, xp_r = contract["reward_zen"], contract["reward_xp"]
        board_contract["claims"].append(player.get("id"))
        _save(doc)
    else:
        zen_r = int(contract["reward_zen"] * CONSOLATION_MULT)
        xp_r = int(contract["reward_xp"] * CONSOLATION_MULT)

    player["zen"] = player.get("zen", 0) + zen_r
    player["xp"] = player.get("xp", 0) + xp_r
    player.get("active_contracts", {}).pop(contract_id, None)

    return True, "✅ تحویل داده شد!", {"zen": zen_r, "xp": xp_r, "full": is_full, "title": contract["title"]}
