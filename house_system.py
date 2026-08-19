# ============================================================
#  ASTRAL ABYSS RPG — Player Housing 🏠  (v2 — عمقِ اقتصادی)
#  بازیکن یه ملک می‌خره، ارتقاش می‌ده (انباری بیشتر + پرک کوچیک)،
#  باهاش تزئین می‌کنه (دنجی)، ازش درآمدِ غیرفعال می‌گیره (اجاره/رانت)
#  و باید در برابرِ دزدیِ بازیکن‌های دیگه ازش محافظت کنه (امنیت).
#
#  v2 چه اضافه کرده؟
#    • 💰 درآمدِ غیرفعال: هر ملک به‌ازای زمان، Zen تو «صندوقِ ملک»
#      جمع می‌کنه (مثلِ سودِ بانکی، lazy-accrual — نیازی به job نیست).
#      برداشتش یه «نگه‌داری» (upkeep) کم می‌کنه که می‌ره تو صندوقِ
#      مالیاتِ سراسری (sink واقعی، نه فقط جابه‌جاییِ عدد).
#    • 🛡 امنیت: وسایلِ جدید (گاوصندوق/سگ‌نگهبان/طلسم) یه «امتیازِ
#      امنیت» می‌سازن که شانسِ موفقیتِ دزدیِ بازیکن‌های دیگه رو کم
#      می‌کنه؛ فقط رویِ صندوقِ برداشت‌نشده ریسکه، نه رویِ کلِ Zen یا
#      سپرده‌ی بانکی بازیکن.
#    • 🏆 پرستیژ: یه امتیازِ ترکیبی از سطحِ ملک + دنجی + وسایل که
#      نشونِ جایگاهِ ملکِ بازیکنه (برای پنل/رنکینگ).
#    • وسایلِ خونه الان سه دسته‌ن: دنجی (cozy) / درآمدزا (income) /
#      امنیتی (security) — هرکدوم اثرِ واقعی رویِ گیم‌پلی دارن.
# ============================================================
import time

HOUSE_TIERS = [
    {"name": "🏕 چادر",  "cost": 0,      "storage": 5,  "hp_regen_pct": 0.00, "income_hr": 0,   "upkeep_pct": 0.00},
    {"name": "🏠 کلبه",  "cost": 3000,   "storage": 12, "hp_regen_pct": 0.03, "income_hr": 40,  "upkeep_pct": 0.05},
    {"name": "🏡 خونه",  "cost": 12000,  "storage": 24, "hp_regen_pct": 0.06, "income_hr": 120, "upkeep_pct": 0.06},
    {"name": "🏰 عمارت", "cost": 40000,  "storage": 40, "hp_regen_pct": 0.10, "income_hr": 320, "upkeep_pct": 0.08},
    {"name": "🏯 قلعه",  "cost": 120000, "storage": 70, "hp_regen_pct": 0.15, "income_hr": 800, "upkeep_pct": 0.10},
]

# نوع: cozy (امتیاز دنجی) | income (Zen اضافه در ساعت) | security (٪ دفاع در برابر دزدی)
FURNITURE = [
    {"id": "rug",        "name": "🧶 قالیچه‌ی آبیس",          "cost": 500,   "type": "cozy",     "cozy": 2},
    {"id": "fireplace",  "name": "🔥 شومینه",                  "cost": 1500,  "type": "cozy",     "cozy": 4},
    {"id": "bookshelf",  "name": "📚 قفسه‌ی کتاب باستانی",     "cost": 2500,  "type": "cozy",     "cozy": 5},
    {"id": "gallery",    "name": "🖼 گالریِ آثارِ نادر",        "cost": 9000,  "type": "cozy",     "cozy": 10},
    {"id": "statue",     "name": "🗿 مجسمه‌ی اژدها",           "cost": 6000,  "type": "cozy",     "cozy": 8},
    {"id": "fountain",   "name": "⛲ فواره‌ی جادویی",           "cost": 15000, "type": "cozy",     "cozy": 12},
    {"id": "throne",     "name": "👑 تخت شاهی",                "cost": 35000, "type": "cozy",     "cozy": 20},

    {"id": "workshop",   "name": "🛠 کارگاهِ ملکی",             "cost": 8000,  "type": "income",   "income": 25},
    {"id": "garden",     "name": "🌿 باغِ گیاهانِ کمیاب",       "cost": 20000, "type": "income",   "income": 60},
    {"id": "treasury",   "name": "🏦 خزانه‌ی شخصی",             "cost": 45000, "type": "income",   "income": 150},

    {"id": "guard_dogs", "name": "🐺 سگ‌های نگهبان",           "cost": 6000,  "type": "security", "security": 5},
    {"id": "vault_room", "name": "🔒 اتاقِ گاوصندوق",           "cost": 10000, "type": "security", "security": 8},
    {"id": "ward",       "name": "🧿 طلسمِ محافظِ ملک",         "cost": 25000, "type": "security", "security": 10},
]
FURNITURE_BY_ID = {f["id"]: f for f in FURNITURE}

# ─── تنظیماتِ درآمدِ غیرفعال ────────────────────────────────────
INCOME_MAX_ACCRUAL_HOURS = 20     # سقفِ ساعت‌هایی که یک‌جا انباشته می‌شه (ضدِ غیبتِ طولانی)

# ─── تنظیماتِ دزدی (Robbery) ────────────────────────────────────
ROBBERY_MIN_VAULT_ZEN = 200             # کف: اگه صندوقِ طرف کمتر از این باشه اصلاً ارزشِ ریسک نداره
ROBBERY_BASE_CHANCE = 0.45              # شانسِ پایه (بدون هیچ امنیتی)
ROBBERY_SECURITY_REDUCTION = 0.02       # هر ۱ امتیازِ امنیت، ۲٪ از شانسِ دزد کم می‌کنه
ROBBERY_MIN_CHANCE = 0.05
ROBBERY_STEAL_PCT_RANGE = (0.35, 0.65)  # چند درصد از صندوقِ قربانی برده می‌شه
ROBBERY_ATTACKER_CUT = 0.70             # از مالِ دزدی‌شده، این‌قدرش به دزد می‌رسه؛ بقیه سوزونده می‌شه (sink)
ROBBERY_FAIL_PENALTY_PCT = 0.10         # اگه دزدی لو بره، دزد این‌قدر از Zenِ نقدِ خودش جریمه می‌شه
ROBBERY_ATTACKER_COOLDOWN = 2 * 3600    # هر دزد هر ۲ ساعت یه‌بار می‌تونه دست به کار بشه
ROBBERY_VICTIM_COOLDOWN = 6 * 3600      # هر ملک حداکثر هر ۶ ساعت یه‌بار قربانیِ دزدی می‌شه (هرکی باشه)

# ─── تنظیماتِ بیمه‌ی ملک (Insurance) ────────────────────────────
#  حق‌بیمه می‌ره تو یه صندوقِ مشترکِ سراسری (house_insurance_pool)؛
#  خسارت هم از همون صندوق پرداخت می‌شه — یعنی بیمه یه اقتصادِ خودگردانه،
#  نه یه faucetِ بی‌پایان (اگه صندوق خالی باشه، خسارتِ کمتری می‌گیری).
INSURANCE_COVERAGE_PCT = 0.5      # چند درصدِ ضررِ دزدی جبران می‌شه
INSURANCE_PREMIUM_HOURS = 4       # حق‌بیمه ≈ معادلِ این‌قدر ساعت درآمدِ ملک
INSURANCE_MIN_PREMIUM = 100
INSURANCE_DURATION = 24 * 3600    # هر خریدِ بیمه ۲۴ ساعت پوشش می‌ده


def ensure_house(player: dict) -> dict:
    house = player.setdefault("house", {"tier": 0, "storage": [], "furniture": []})
    house.setdefault("vault", 0)
    house.setdefault("income_since", time.time())
    house.setdefault("last_robbed_at", 0)
    house.setdefault("insured_until", 0)
    house.setdefault("traps", {})
    return house


def tier_data(house: dict) -> dict:
    return HOUSE_TIERS[house.get("tier", 0)]


def storage_capacity(house: dict) -> int:
    return tier_data(house)["storage"]


def hp_regen_bonus(player: dict) -> float:
    house = player.get("house")
    if not house:
        return 0.0
    return tier_data(house)["hp_regen_pct"]


def _furniture_sum(house: dict, ftype: str, key: str) -> int:
    owned = {f["id"] for f in house.get("furniture", [])}
    return sum(f.get(key, 0) for f in FURNITURE if f["id"] in owned and f["type"] == ftype)


def cozy_score(house: dict) -> int:
    return _furniture_sum(house, "cozy", "cozy")


def income_per_hour(house: dict) -> int:
    return tier_data(house)["income_hr"] + _furniture_sum(house, "income", "income")


def security_score(house: dict) -> int:
    return _furniture_sum(house, "security", "security")


def robbery_chance(house: dict, defender: dict | None = None, extra_security: int = 0) -> float:
    sec = security_score(house) + extra_security
    if defender is not None:
        try:
            import spy_loadout_system as spy
            sec += spy.stealth_security_bonus(defender)
        except Exception:
            pass
    chance = ROBBERY_BASE_CHANCE - sec * ROBBERY_SECURITY_REDUCTION
    return max(ROBBERY_MIN_CHANCE, min(ROBBERY_BASE_CHANCE, chance))


def prestige_score(house: dict) -> int:
    tier_pts = house.get("tier", 0) * 15
    return tier_pts + cozy_score(house) + income_per_hour(house) // 10 + security_score(house)


def _land_gate(uid: int, cur_tier: int) -> str | None:
    """اگه بازیکن زمین داره ولی سایزِ زمینش اجازه‌ی این سطحِ خونه رو نمی‌ده، پیامِ خطا برمی‌گردونه؛ وگرنه None."""
    try:
        from land_system import max_house_tier_for_player
    except ImportError:
        return None
    cap = max_house_tier_for_player(uid)
    if cap is not None and cur_tier + 1 > cap:
        return "❌ سایزِ زمینت اجازه‌ی این سطح از خونه رو نمی‌ده — اول زمینت رو بزرگ کن (🗺 زمین)."
    return None


def upgrade_house(player: dict, uid: int | None = None) -> tuple[bool, str]:
    house = ensure_house(player)
    accrue_income(house)
    cur_tier = house.get("tier", 0)
    if cur_tier + 1 >= len(HOUSE_TIERS):
        return False, "🏯 ملکت از قبل بالاترین سطحه!"
    if uid is not None:
        gate_msg = _land_gate(uid, cur_tier)
        if gate_msg:
            return False, gate_msg
    next_tier = HOUSE_TIERS[cur_tier + 1]
    cost = next_tier["cost"]
    if player.get("zen", 0) < cost:
        return False, f"❌ برای ارتقا به {next_tier['name']} به {cost:,} Zen نیاز داری."
    player["zen"] -= cost
    house["tier"] = cur_tier + 1
    return True, (
        f"🎉 ملکت ارتقا پیدا کرد: **{next_tier['name']}**!\n"
        f"📦 انباری: {next_tier['storage']} اسلات | 💰 درآمد: {next_tier['income_hr']:,} Zen/ساعت"
    )


def mortgage_upgrade(player: dict, uid: int | None = None) -> tuple[bool, str]:
    """مثلِ upgrade_house، ولی اگه Zenِ نقد کم بود، کمبودش رو از همون سیستمِ
    وامِ بانکِ موجود (bank_system) قرض می‌گیره — یعنی رهنِ ملک، نه یه سیستمِ
    وامِ جدا. توجه: چون بانک فقط یه وامِ فعال در آنِ واحد مجاز می‌کنه، گرفتنِ
    رهن یعنی اسلاتِ وامِ عادیِ بازیکن هم اشغال می‌شه."""
    house = ensure_house(player)
    accrue_income(house)
    cur_tier = house.get("tier", 0)
    if cur_tier + 1 >= len(HOUSE_TIERS):
        return False, "🏯 ملکت از قبل بالاترین سطحه!"
    if uid is not None:
        gate_msg = _land_gate(uid, cur_tier)
        if gate_msg:
            return False, gate_msg
    next_tier = HOUSE_TIERS[cur_tier + 1]
    cost = next_tier["cost"]
    have = player.get("zen", 0)
    if have >= cost:
        return upgrade_house(player, uid)

    shortfall = cost - have
    import bank_system as bs
    if bs.has_active_loan(player):
        return False, "❌ یه وامِ بانکیِ بازپرداخت‌نشده داری — اول اونو از /bank تسویه کن، بعد رهنِ ملک بگیر."
    cap = bs.max_loan_amount(player)
    if shortfall > cap:
        credit = bs.loan_status(player)["credit_score"]
        return False, (
            f"❌ اعتبارِ بانکیت برای این ارتقا کافی نیست.\n"
            f"کمبود: {shortfall:,} Zen | سقفِ وامِ مجازت: {cap:,} Zen (اعتبار: {credit}/100)."
        )
    borrow_res = bs.borrow(player, shortfall)
    if not borrow_res["ok"]:
        return False, borrow_res["msg"]
    ok, msg = upgrade_house(player)
    if not ok:
        return False, msg
    return True, (
        f"🏦 **رهنِ ملک گرفتی!** {shortfall:,} Zen از بانک وام شد تا ارتقا کامل بشه.\n\n{msg}\n\n"
        f"💳 وامِ بانکیت رو فراموش نکن — از /bank قابلِ پیگیری و بازپرداخته."
    )



def buy_furniture(player: dict, furn_id: str) -> tuple[bool, str]:
    house = ensure_house(player)
    furn = FURNITURE_BY_ID.get(furn_id)
    if not furn:
        return False, "❌ این وسیله وجود نداره."
    owned = {f["id"] for f in house.get("furniture", [])}
    if furn_id in owned:
        return False, "❌ این وسیله رو از قبل داری."
    if player.get("zen", 0) < furn["cost"]:
        return False, f"❌ {furn['cost']:,} Zen لازم داری."
    player["zen"] -= furn["cost"]
    house.setdefault("furniture", []).append({"id": furn["id"]})
    if furn["type"] == "cozy":
        extra = f"+{furn['cozy']} امتیاز دنجی"
    elif furn["type"] == "income":
        extra = f"+{furn['income']:,} Zen/ساعت درآمد"
    else:
        extra = f"+{furn['security']} امتیاز امنیت"
    return True, f"✅ **{furn['name']}** به ملکت اضافه شد! ({extra})"


def store_item(player: dict, item_id: str) -> tuple[bool, str]:
    house = ensure_house(player)
    if len(house.get("storage", [])) >= storage_capacity(house):
        return False, "❌ انباریت پره! اول ارتقاش بده یا یه چیزی رو خارج کن."
    inv = player.get("inventory", [])
    idx = next((i for i, it in enumerate(inv) if it.get("id") == item_id), None)
    if idx is None:
        return False, "❌ این آیتم تو کوله‌پشتیت نیست."
    item = inv.pop(idx)
    house.setdefault("storage", []).append(item)
    return True, f"📦 **{item['name']}** به انباری منتقل شد."


def retrieve_item(player: dict, item_id: str) -> tuple[bool, str]:
    house = ensure_house(player)
    storage = house.get("storage", [])
    idx = next((i for i, it in enumerate(storage) if it.get("id") == item_id), None)
    if idx is None:
        return False, "❌ این آیتم تو انباریت نیست."
    item = storage.pop(idx)
    player.setdefault("inventory", []).append(item)
    return True, f"🎒 **{item['name']}** به کوله‌پشتیت برگشت."


# ============================================================
#  💰 درآمدِ غیرفعال (اجاره/رانتِ ملک) — lazy accrual
# ============================================================
def accrue_income(house: dict) -> int:
    """صندوقِ ملک رو بر اساسِ زمانِ سپری‌شده آپدیت می‌کنه. خروجی: مقدارِ تازه‌اضافه‌شده."""
    rate = income_per_hour(house)
    last = house.get("income_since", time.time())
    elapsed_h = min(INCOME_MAX_ACCRUAL_HOURS, max(0.0, (time.time() - last) / 3600.0))
    house["income_since"] = time.time()
    if rate <= 0 or elapsed_h <= 0:
        return 0
    added = int(rate * elapsed_h)
    if added > 0:
        house["vault"] = house.get("vault", 0) + added
    return added


def pending_income(house: dict) -> int:
    """فقط برای نمایش — بدونِ ثبتِ نهایی، تخمینِ الانِ صندوق رو می‌ده."""
    rate = income_per_hour(house)
    last = house.get("income_since", time.time())
    elapsed_h = min(INCOME_MAX_ACCRUAL_HOURS, max(0.0, (time.time() - last) / 3600.0))
    return house.get("vault", 0) + int(rate * elapsed_h)


def collect_income(player: dict) -> tuple[bool, str]:
    house = ensure_house(player)
    accrue_income(house)
    gross = house.get("vault", 0)
    if gross <= 0:
        return False, "❌ فعلاً چیزی تو صندوقِ ملک جمع نشده."
    upkeep_pct = tier_data(house)["upkeep_pct"]
    upkeep = int(gross * upkeep_pct)
    net = gross - upkeep
    house["vault"] = 0
    player["zen"] = player.get("zen", 0) + net

    if upkeep > 0:
        try:
            from economy_engine import deposit_tax_pool
            deposit_tax_pool(upkeep, player.get("_uid"))
        except Exception:
            pass
        try:
            from economy_ledger import record_house_upkeep
            record_house_upkeep(upkeep)
        except Exception:
            pass
    try:
        from economy_ledger import record_house_income_paid
        record_house_income_paid(net)
    except Exception:
        pass

    return True, (
        f"💰 **{net:,} Zen** از درآمدِ ملک برداشت شد.\n"
        f"🧾 نگه‌داری (upkeep): {upkeep:,} Zen ({int(upkeep_pct*100)}٪ — رفت تو صندوقِ مالیاتِ سراسری)"
    )


# ============================================================
#  🛡 بیمه‌ی ملک — صندوقِ مشترکِ خودگردان (نه faucet بی‌پایان)
# ============================================================
def _insurance_pool_doc() -> dict:
    from database import system_col
    doc = system_col().find_one({"_id": "house_insurance_pool"})
    if not doc:
        doc = {"_id": "house_insurance_pool", "total": 0}
        system_col().update_one({"_id": "house_insurance_pool"}, {"$set": doc}, upsert=True)
    return doc


def get_insurance_pool() -> int:
    return _insurance_pool_doc().get("total", 0)


def _insurance_pool_add(amount: int):
    from database import system_col
    system_col().update_one({"_id": "house_insurance_pool"}, {"$inc": {"total": amount}}, upsert=True)


def _insurance_pool_take(amount: int) -> int:
    """حداکثرِ چیزی که تو صندوق موجوده رو برمی‌داره؛ خروجی: مقدارِ واقعاً برداشت‌شده."""
    from database import system_col
    avail = get_insurance_pool()
    taken = max(0, min(avail, amount))
    if taken > 0:
        system_col().update_one({"_id": "house_insurance_pool"}, {"$inc": {"total": -taken}})
    return taken


def is_insured(house: dict) -> bool:
    return house.get("insured_until", 0) > time.time()


def insurance_premium(house: dict) -> int:
    rate = income_per_hour(house)
    return max(INSURANCE_MIN_PREMIUM, int(rate * INSURANCE_PREMIUM_HOURS))


def buy_insurance(player: dict) -> tuple[bool, str]:
    house = ensure_house(player)
    if is_insured(house):
        remain_h = int((house["insured_until"] - time.time()) // 3600) + 1
        return False, f"🛡 بیمه‌ت همین الان فعاله — {remain_h} ساعتِ دیگه باقیه."
    premium = insurance_premium(house)
    if player.get("zen", 0) < premium:
        return False, f"❌ {premium:,} Zen برای حق‌بیمه لازم داری."
    player["zen"] -= premium
    house["insured_until"] = time.time() + INSURANCE_DURATION
    _insurance_pool_add(premium)
    try:
        from economy_ledger import record_insurance_premium
        record_insurance_premium(premium)
    except Exception:
        pass
    return True, (
        f"🛡 **ملکت بیمه شد!** تا ۲۴ ساعتِ آینده، اگه دزدی شدی "
        f"{int(INSURANCE_COVERAGE_PCT*100)}٪ از ضررت (تا سقفِ موجودیِ صندوقِ بیمه) برمی‌گرده.\n"
        f"💳 حق‌بیمه: {premium:,} Zen (رفت تو صندوقِ مشترکِ بیمه)"
    )


# ============================================================
#  🛡 دزدی (Robbery) — فقط صندوقِ برداشت‌نشده در خطره
# ============================================================
def robbery_precheck(attacker: dict, defender: dict) -> tuple[bool, str]:
    now = time.time()
    a_cd = attacker.get("rob_last_at", 0) + ROBBERY_ATTACKER_COOLDOWN - now
    if a_cd > 0:
        m = int(a_cd // 60) + 1
        return False, f"⏳ هنوز {m} دقیقه‌ی دیگه باید صبر کنی تا دوباره بتونی دزدی کنی."
    d_house = ensure_house(defender)
    d_cd = d_house.get("last_robbed_at", 0) + ROBBERY_VICTIM_COOLDOWN - now
    if d_cd > 0:
        m = int(d_cd // 60) + 1
        return False, f"🛡 این ملک اخیراً دزدی شده — {m} دقیقه‌ی دیگه دوباره قابلِ حمله‌ست."
    accrue_income(d_house)
    if d_house.get("vault", 0) < ROBBERY_MIN_VAULT_ZEN:
        return False, "❌ صندوقِ این ملک به‌قدرِ کافی پر نیست که ارزشِ ریسک داشته باشه."
    return True, ""


def attempt_robbery(attacker_uid: int, attacker: dict, defender_uid: int, defender: dict) -> dict:
    """خروجی: {"ok": bool پیش‌شرط, "success": bool|None, "msg": str}"""
    import random
    ok, why = robbery_precheck(attacker, defender)
    if not ok:
        return {"ok": False, "success": None, "msg": why}

    d_house = ensure_house(defender)
    attacker["rob_last_at"] = time.time()
    d_house["last_robbed_at"] = time.time()

    trap_bonus, trap_name = 0, None
    try:
        import house_defense_traps as traps
        trap_bonus, trap_name = traps.trigger_defense(d_house)
    except Exception:
        pass

    chance = robbery_chance(d_house, defender, extra_security=trap_bonus)
    success = random.random() < chance

    sabotage_bonus = 0.0
    sabotage_broken = None
    try:
        import spy_loadout_system as spy
        sabotage_bonus, sabotage_broken = spy.sabotage_attacker_bonus(attacker)
    except Exception:
        pass

    if success:
        vault = d_house.get("vault", 0)
        pct = min(0.95, random.uniform(*ROBBERY_STEAL_PCT_RANGE) + sabotage_bonus)
        stolen = int(vault * pct)
        d_house["vault"] = vault - stolen
        gain = int(stolen * ROBBERY_ATTACKER_CUT)
        burned = stolen - gain
        attacker["zen"] = attacker.get("zen", 0) + gain

        payout = 0
        if is_insured(d_house):
            claim = int(stolen * INSURANCE_COVERAGE_PCT)
            payout = _insurance_pool_take(claim)
            if payout > 0:
                defender["zen"] = defender.get("zen", 0) + payout
                try:
                    from economy_ledger import record_insurance_payout
                    record_insurance_payout(payout)
                except Exception:
                    pass

        try:
            from economy_ledger import record_robbery_attempt
            record_robbery_attempt(True, stolen=stolen, burned=burned)
        except Exception:
            pass

        victim_msg = f"🚨 ملکت دزدی شد! **{stolen:,} Zen** از صندوقت رفت."
        if trap_name:
            victim_msg += f"\n🪤 {trap_name}ت فعال شد ولی کافی نبود — بازم دزد رد شد. تله مصرف شد، دوباره نصب کن."
        if payout > 0:
            victim_msg += f" 🛡 بیمه‌ت **{payout:,} Zen**ش رو جبران کرد."
        else:
            victim_msg += " برای درزدنِ بعدی امنیت/بیمه‌ی ملکت رو بالا ببر."

        atk_msg = (
            f"🗡 **دزدی موفق!** از صندوقِ ملکِ {defender.get('name','؟')} "
            f"**{gain:,} Zen** بردی. (بخشی هم به‌عنوانِ غرامت سوخت: {burned:,} Zen)"
        )
        if trap_name:
            atk_msg += f"\n🪤 یه {trap_name} فعال شد ولی نتونست جلوت رو بگیره!"
        if sabotage_broken:
            atk_msg += f"\n💔 {sabotage_broken}ت مصرف و شکست."
        return {
            "ok": True, "success": True,
            "msg": atk_msg,
            "victim_msg": victim_msg,
            "stolen": stolen, "gain": gain, "payout": payout,
        }
    else:
        penalty = int(attacker.get("zen", 0) * ROBBERY_FAIL_PENALTY_PCT)
        attacker["zen"] = max(0, attacker.get("zen", 0) - penalty)
        try:
            from economy_ledger import record_robbery_attempt
            record_robbery_attempt(False)
        except Exception:
            pass
        stealth_broken = None
        try:
            import spy_loadout_system as spy
            stealth_broken = spy.stealth_consume_on_robbery_defense(defender)
        except Exception:
            pass
        victim_defense_msg = "🛡 یه نفر سعی کرد ملکت رو بدزده ولی امنیتِ ملکت جلوش رو گرفت!"
        if trap_name:
            victim_defense_msg += f"\n🪤 {trap_name}ت فعال شد و دزد رو گرفت! (تله مصرف شد — دوباره نصبش کن)"
        if stealth_broken:
            victim_defense_msg += f"\n💔 {stealth_broken}ت تو این دفاع مصرف شد — دوباره تجهیزش کن."
        atk_fail_msg = f"🚔 **دزدی لو رفت!** سگ‌های نگهبان/طلسمِ ملک گرفتنت — {penalty:,} Zen جریمه شدی."
        if trap_name:
            atk_fail_msg += f"\n🪤 یه {trap_name} فعال شد و لو دادت!"
        return {
            "ok": True, "success": False,
            "msg": atk_fail_msg,
            "victim_msg": victim_defense_msg,
            "stolen": 0, "gain": 0,
        }
