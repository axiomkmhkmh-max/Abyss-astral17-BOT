# ============================================================
#  ASTRAL ABYSS — Economy Ledger (سلامتِ اقتصاد سراسری)
# ------------------------------------------------------------
#  یه سندِ سراسریِ سبک که چندتا شمارنده‌ی جمعی نگه می‌داره؛ فقط برای
#  دیدِ کلیِ ادمین از سلامتِ اقتصاد (faucet در برابرِ sink)، نه برای
#  منطقِ بازی. عمداً جدا از economy_engine.py نگه داشته شده که چیزی
#  رو خراب نکنه — فقط چندتا $inc ساده روی یه سندِ system_col.
# ============================================================
from database import system_col, ledger_col
import time
import uuid

_ID = "economy_ledger"

_DEFAULTS = {
    "total_interest_paid": 0,     # faucet — سودِ سپرده‌ی بانکی که پرداخت شده
    "total_loans_issued": 0,      # faucet — مجموعِ اصلِ وام‌هایی که داده شده
    "total_loans_repaid": 0,      # sink   — مجموعِ اصل+بهره‌ای که برگشته
    "total_loan_interest": 0,     # sink   — فقط بخشِ بهره‌ی وام‌های بازپرداخت‌شده
    "total_loan_defaults": 0,     # تعدادِ وام‌هایی که نکول شدن (اطلاعاتی)
    "loans_outstanding_zen": 0,   # مانده‌ی فعلیِ کلِ وام‌های بازنپرداخته
    "treasury_contributions": 0,  # sink (از دیدِ بازیکن) — واریزی به صندوقِ گیلدها

    # ─── اقتصادِ ملکِ شخصی (house) ──────────────────────────────
    "total_house_income_paid": 0,   # faucet — درآمدِ ملکی که بازیکن‌ها برداشت کردن
    "total_house_upkeep_sink": 0,   # sink   — نگه‌داریِ ملک که موقعِ برداشت کم می‌شه
    "total_robbery_attempts": 0,    # تعدادِ کلِ تلاش‌های دزدی (اطلاعاتی)
    "total_robbery_success": 0,     # تعدادِ دزدی‌های موفق (اطلاعاتی)
    "total_robbery_stolen": 0,      # مقداری که دزدها بردن (جابه‌جایی، نه faucet/sink خالص)
    "total_robbery_burned": 0,      # sink — بخشی از دزدی که به‌عنوانِ «غرامت/مالیات» سوزونده می‌شه

    # ─── بورسِ آبیس (Exchange) ──────────────────────────────────
    "total_exchange_fees": 0,       # sink — کارمزدِ خرید/فروشِ سهام

    # ─── بیمه‌ی ملک (پولش داخلِ صندوقِ مشترک می‌چرخه، faucet خالص نیست) ───
    "total_insurance_premiums": 0,  # حق‌بیمه‌های جمع‌شده
    "total_insurance_payouts": 0,   # خسارت‌های پرداخت‌شده
}


def _inc(field: str, amount: int):
    if amount == 0:
        return
    system_col().update_one({"_id": _ID}, {"$inc": {field: amount}}, upsert=True)


def record_interest_paid(amount: int):
    _inc("total_interest_paid", amount)


def record_loan_issued(amount: int):
    _inc("total_loans_issued", amount)
    _inc("loans_outstanding_zen", amount)


def record_loan_repaid(principal_part: int, interest_part: int):
    _inc("total_loans_repaid", principal_part + interest_part)
    _inc("total_loan_interest", interest_part)
    _inc("loans_outstanding_zen", -principal_part)


def record_loan_default(remaining_principal: int):
    _inc("total_loan_defaults", 1)
    _inc("loans_outstanding_zen", -remaining_principal)


def record_treasury_contribution(amount: int):
    _inc("treasury_contributions", amount)


def record_house_income_paid(amount: int):
    _inc("total_house_income_paid", amount)


def record_house_upkeep(amount: int):
    _inc("total_house_upkeep_sink", amount)


def record_robbery_attempt(success: bool, stolen: int = 0, burned: int = 0):
    _inc("total_robbery_attempts", 1)
    if success:
        _inc("total_robbery_success", 1)
        _inc("total_robbery_stolen", stolen)
        _inc("total_robbery_burned", burned)


def record_exchange_fee(amount: int):
    _inc("total_exchange_fees", amount)


def record_insurance_premium(amount: int):
    _inc("total_insurance_premiums", amount)


def record_insurance_payout(amount: int):
    _inc("total_insurance_payouts", amount)


def get_ledger() -> dict:
    doc = system_col().find_one({"_id": _ID}) or {}
    out = dict(_DEFAULTS)
    for k in _DEFAULTS:
        out[k] = doc.get(k, 0)
    return out


# ============================================================
#  Audit Trail — لاگِ دقیقِ تراکنش‌های حساس (بازار سیاه / حراجی)
# ------------------------------------------------------------
#  برخلافِ شمارنده‌های تجمعیِ بالا (که فقط یه عدد کلی نگه می‌دارن)،
#  اینجا برای هر تراکنش یه سندِ کامل و append-only تو یه کالکشنِ
#  جدا (database.ledger_col) ثبت می‌شه — طوری که اگه یه‌روز اکسپلویت
#  یا باگِ اقتصادی پیدا شد، بشه دقیقاً دنبال کرد کدوم بازیکن، کِی،
#  چه آیتمی، با چه قیمتی، و موجودی قبل/بعدش چقدر بوده.
#
#  هیچ‌جا این تابع نباید crash کنه و جلوی خودِ تراکنشِ بازی رو بگیره؛
#  اگه نوشتنِ لاگ به هر دلیلی خطا داد، فقط سایلنت لاگ می‌شه (لاگر
#  اصلیِ logger.py) و ادامه می‌ده.
# ============================================================

# انواعِ مجازِ kind — فقط برای مستندسازی/دیباگ، اجباری نیست:
#   bm_buy, bm_sell, bm_sell_all, bm_spy_buy, bm_katana_up, bm_def_buy,
#   bm_shadow_auction_buy,
#   auction_list, auction_bid, auction_buy_now, auction_settle,
#   auction_cancel, auction_expire_refund

def record_transaction(
    kind: str,
    user_id: int,
    *,
    username: str = None,
    item_name: str = None,
    item_id: str = None,
    rarity: str = None,
    quantity: int = 1,
    amount: int = 0,
    fee: int = 0,
    balance_before: int = None,
    balance_after: int = None,
    counterparty_id: int = None,
    counterparty_name: str = None,
    note: str = None,
    extra: dict = None,
) -> str:
    """یه ردیفِ کاملِ audit ثبت می‌کنه. amount همیشه مثبته (اندازه‌ی
    تراکنش)؛ جهتِ pul (خرج شده/گرفته شده) از رویِ kind مشخصه.
    خروجی: tx_id (رشته) برای رجوعِ بعدی — یا "" اگه ثبت شکست خورد."""
    tx_id = uuid.uuid4().hex[:12]
    doc = {
        "tx_id": tx_id,
        "ts": time.time(),
        "kind": kind,
        "user_id": user_id,
        "username": username,
        "item_name": item_name,
        "item_id": item_id,
        "rarity": rarity,
        "quantity": quantity,
        "amount": int(amount),
        "fee": int(fee),
        "balance_before": balance_before,
        "balance_after": balance_after,
        "counterparty_id": counterparty_id,
        "counterparty_name": counterparty_name,
        "note": note,
    }
    if extra:
        doc["extra"] = extra
    try:
        ledger_col().insert_one(doc)
    except Exception as e:
        try:
            from logger import log_sync
            log_sync(f"⚠️ [LEDGER-FAIL] ثبتِ تراکنش‌ِ {kind} برای uid={user_id} شکست خورد: {e}", "WARNING")
        except Exception:
            print(f"[LEDGER-FAIL] {kind} uid={user_id}: {e}")
        return ""
    return tx_id


def get_user_transactions(user_id: int, limit: int = 50) -> list:
    """آخرین تراکنش‌های یه بازیکنِ خاص — برای پیگیریِ شکایت/گزارش تخلف."""
    try:
        cur = ledger_col().find({"user_id": user_id}).sort("ts", -1).limit(limit)
        return list(cur)
    except Exception:
        return []


def get_recent_transactions(kind: str = None, limit: int = 100) -> list:
    """آخرین تراکنش‌ها (اختیاری: فیلترشده بر اساسِ kind) — برای پنلِ ادمین."""
    try:
        query = {"kind": kind} if kind else {}
        cur = ledger_col().find(query).sort("ts", -1).limit(limit)
        return list(cur)
    except Exception:
        return []


def get_large_transactions(min_amount: int, hours: int = 24, limit: int = 100) -> list:
    """تراکنش‌های سنگین تو N ساعتِ اخیر — برای اسکنِ سریعِ اکسپلویتِ احتمالی
    (مثلاً یه آیتم که ناگهان با قیمتِ عجیب جابه‌جا شده)."""
    try:
        since = time.time() - hours * 3600
        query = {"ts": {"$gte": since}, "amount": {"$gte": min_amount}}
        cur = ledger_col().find(query).sort("amount", -1).limit(limit)
        return list(cur)
    except Exception:
        return []
