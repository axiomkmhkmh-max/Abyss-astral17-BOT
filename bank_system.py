# ============================================================
#  ASTRAL ABYSS — عابربانک (Bank / Card Transfer System)
# ------------------------------------------------------------
#  هر بازیکن یه شماره‌کارتِ ۱۶ رقمیِ یکتا داره (اولین بار که وارد
#  بانک می‌شه ساخته می‌شه). انتقال با شماره‌کارت انجام می‌شه (نه فقط
#  یوزرنیم) — کارمزدِ کوچیک می‌ره تو صندوق مالیاتِ سراسری (همون
#  tax_col که economy_engine.py ازش استفاده می‌کنه)، یه سقفِ روزانه
#  داره (ضدفارم/ضدترید مشکوک)، تاریخچه‌ی چند تراکنشِ آخر رو نگه
#  می‌داره، و PIN اختیاری برای امنیتِ بیشتر داره.
# ============================================================
import random
import time

from database import get_player, save_player, bank_cards_col, bank_tx_col, player_lock_pair, asave_player, aget_player

CARD_LENGTH = 16
PIN_LENGTH = 4

TRANSFER_FEE_PCT = 0.02          # ۲٪ کارمزد — می‌ره تو صندوق مالیاتِ سراسری
MIN_TRANSFER = 50
DAILY_TRANSFER_CAP = 25_000      # سقفِ نرمِ روزانه‌ی انتقال (ضدفارم/ضدترید مشکوک)
DAILY_RESET_SEC = 86400

MAX_PIN_FAILS = 5
PIN_LOCKOUT_SEC = 900            # ۱۵ دقیقه قفل بعد از ۵ تلاشِ ناموفق

HISTORY_MAX = 15


# ─── شماره‌کارت ────────────────────────────────────────────────
def _gen_card_number() -> str:
    # پیش‌شماره‌ی ثابت "8991" (کاملاً تخیلی، شبیه یه کارتِ بانکی) + ۱۲ رقمِ رندوم
    return "8991" + "".join(str(random.randint(0, 9)) for _ in range(CARD_LENGTH - 4))


async def get_or_create_card(uid: int, player: dict) -> str:
    """اگه بازیکن از قبل کارت داره همونو برمی‌گردونه، وگرنه یه کارتِ یکتای جدید می‌سازه."""
    existing = player.get("bank_card")
    if existing:
        return existing
    for _ in range(30):
        card = _gen_card_number()
        if bank_cards_col().find_one({"_id": card}):
            continue
        bank_cards_col().insert_one({"_id": card, "uid": uid, "created_at": time.time()})
        player["bank_card"] = card
        await asave_player(uid, player)
        return card
    # اگه به هر دلیلی ۳۰ بار تصادفاً برخورد کرد (عملاً ناممکنه)، از uid مشتق کن
    card = "8991" + str(uid).rjust(CARD_LENGTH - 4, "0")[-(CARD_LENGTH - 4):]
    bank_cards_col().update_one({"_id": card}, {"$set": {"uid": uid}}, upsert=True)
    player["bank_card"] = card
    await asave_player(uid, player)
    return card


def format_card(card: str) -> str:
    return " ".join(card[i:i + 4] for i in range(0, len(card), 4))


def resolve_card_to_uid(card_number: str) -> int | None:
    card_number = card_number.replace(" ", "").strip()
    doc = bank_cards_col().find_one({"_id": card_number})
    return doc.get("uid") if doc else None


def resolve_target(arg: str, requester_uid: int) -> int | None:
    """ورودی می‌تونه شماره‌کارت (۱۶ رقمی)، @username، user_id یا اسمِ بازیکن باشه."""
    arg = arg.strip()
    digits = arg.replace(" ", "")
    if digits.isdigit() and len(digits) == CARD_LENGTH:
        return resolve_card_to_uid(digits)
    try:
        from pvp_handlers import _resolve_track_target
        return _resolve_track_target(arg, requester_uid)
    except Exception:
        return None


# ─── PIN ─────────────────────────────────────────────────────
def has_pin(player: dict) -> bool:
    return bool(player.get("bank_pin"))


def set_pin(player: dict, pin: str) -> bool:
    if not (pin.isdigit() and len(pin) == PIN_LENGTH):
        return False
    player["bank_pin"] = pin
    player["bank_pin_fails"] = 0
    player["bank_pin_locked_until"] = 0
    return True


def clear_pin(player: dict):
    player["bank_pin"] = None
    player["bank_pin_fails"] = 0
    player["bank_pin_locked_until"] = 0


def pin_locked_remaining(player: dict) -> int:
    return max(0, int(player.get("bank_pin_locked_until", 0) - time.time()))


def check_pin(player: dict, pin: str) -> bool:
    """True اگه درست بود (یا اصلاً PIN فعال نبود). فیل‌شدن رو خودش ثبت می‌کنه."""
    if not has_pin(player):
        return True
    if pin_locked_remaining(player) > 0:
        return False
    if player.get("bank_pin") == pin:
        player["bank_pin_fails"] = 0
        return True
    player["bank_pin_fails"] = player.get("bank_pin_fails", 0) + 1
    if player["bank_pin_fails"] >= MAX_PIN_FAILS:
        player["bank_pin_locked_until"] = time.time() + PIN_LOCKOUT_SEC
        player["bank_pin_fails"] = 0
    return False


# ─── سقفِ روزانه ────────────────────────────────────────────────
def _ensure_daily(player: dict):
    now = time.time()
    if now >= player.get("bank_transfer_reset_at", 0):
        player["bank_transfer_today"] = 0
        player["bank_transfer_reset_at"] = now + DAILY_RESET_SEC


def daily_remaining(player: dict) -> int:
    _ensure_daily(player)
    return max(0, DAILY_TRANSFER_CAP - player.get("bank_transfer_today", 0))


def _register_daily(player: dict, amount: int):
    _ensure_daily(player)
    player["bank_transfer_today"] = player.get("bank_transfer_today", 0) + amount


# ─── تاریخچه ─────────────────────────────────────────────────
def _push_history(player: dict, entry: dict):
    hist = player.setdefault("bank_history", [])
    hist.append(entry)
    if len(hist) > HISTORY_MAX:
        del hist[0: len(hist) - HISTORY_MAX]


def get_history(player: dict) -> list[dict]:
    return list(reversed(player.get("bank_history", [])))


# ─── انتقال ─────────────────────────────────────────────────
async def transfer(sender_uid: int, target_input: str, amount: int, pin: str | None = None) -> dict:
    """
    خروجی: {"ok": bool, "msg": str, "fee": int, "net": int, "target_name": str}

    باگ‌فیکس ریس‌کاندیشن: کلِ خوندن+تغییر+ذخیره‌ی هر دو طرف (فرستنده و
    گیرنده) حالا زیرِ player_lock_pair اتمیکه — یعنی اگه دو تا انتقالِ
    هم‌زمان به یه گیرنده‌ی مشترک برسه (یا فرستنده هم‌زمان یه اکشنِ
    دیگه هم انجام بده)، دومی صبر می‌کنه تا اولی کامل تموم بشه، نه اینکه
    رویِ دیتای هم بنویسن. resolve_target قبل از گرفتنِ قفل انجام می‌شه
    (فقط خوندنه)، ولی خودِ sender/target *بعدِ* گرفتنِ قفل تازه از دیتابیس
    خونده می‌شن تا هیچ دیتای بیات (stale) استفاده نشه.
    """
    if amount < MIN_TRANSFER:
        return {"ok": False, "msg": f"❌ حداقلِ انتقال {MIN_TRANSFER:,} Zen هست."}

    target_uid = resolve_target(target_input, sender_uid)
    if not target_uid or target_uid == sender_uid:
        return {"ok": False, "msg": "❌ گیرنده پیدا نشد (یا داری برای خودت می‌فرستی)!"}

    async with player_lock_pair(sender_uid, target_uid):
        sender = await aget_player(sender_uid)
        if not sender:
            return {"ok": False, "msg": "❌ خطا: بازیکن پیدا نشد."}

        if has_pin(sender):
            if pin_locked_remaining(sender) > 0:
                await asave_player(sender_uid, sender)
                m = pin_locked_remaining(sender) // 60
                return {"ok": False, "msg": f"🔒 حسابت به‌خاطرِ تلاش‌های ناموفقِ زیاد قفله. {m+1} دقیقه‌ی دیگه دوباره امتحان کن."}
            if pin is None or not check_pin(sender, pin):
                await asave_player(sender_uid, sender)
                fails_left = MAX_PIN_FAILS - sender.get("bank_pin_fails", 0)
                await asave_player(sender_uid, sender)
                return {"ok": False, "msg": f"❌ PIN اشتباهه! ({fails_left} تلاشِ دیگه مونده)"}

        target = await aget_player(target_uid)
        if not target:
            return {"ok": False, "msg": "❌ این بازیکن حسابِ بانکی نداره!"}

        if sender.get("zen", 0) < amount:
            return {"ok": False, "msg": "❌ Zen کافی نداری!"}

        remaining_cap = daily_remaining(sender)
        if amount > remaining_cap:
            return {"ok": False, "msg": f"📵 سقفِ روزانه‌ی انتقال رو رد می‌کنی! امروز فقط {remaining_cap:,} Zen دیگه می‌تونی بفرستی."}

        fee = int(amount * TRANSFER_FEE_PCT)
        net = amount - fee

        sender["zen"] = sender.get("zen", 0) - amount
        target["zen"] = target.get("zen", 0) + net
        _register_daily(sender, amount)

        now = time.time()
        sender_card = await get_or_create_card(sender_uid, sender)
        target_card = await get_or_create_card(target_uid, target)

        _push_history(sender, {"t": now, "dir": "out", "amount": amount, "fee": fee,
                                "peer": target.get("name", "?"), "peer_card": target_card})
        _push_history(target, {"t": now, "dir": "in", "amount": net, "fee": 0,
                                "peer": sender.get("name", "?"), "peer_card": sender_card})

        await asave_player(sender_uid, sender)
        await asave_player(target_uid, target)

        try:
            from economy_engine import deposit_tax_pool
            deposit_tax_pool(fee, sender_uid)
        except Exception:
            pass

        bank_tx_col().insert_one({
            "t": now, "from_uid": sender_uid, "to_uid": target_uid,
            "amount": amount, "fee": fee, "net": net,
        })

        return {
            "ok": True,
            "msg": f"✅ **{net:,} Zen** به {target.get('name','?')} منتقل شد. (کارمزد: {fee:,} Zen)",
            "fee": fee, "net": net, "target_name": target.get("name", "?"), "target_uid": target_uid,
        }


# ============================================================
#  حساب سپرده (Savings) — سودِ روزانه‌ی ساده
# ------------------------------------------------------------
#  بازیکن Zen رو از حساب جاری به سپرده منتقل می‌کنه؛ هر روزی که تو
#  سپرده بمونه سود ساده (نه ترکیبی) بهش تعلق می‌گیره. سود موقع
#  هر بارِ باز کردنِ بانک به‌صورت lazy محاسبه و ثبت می‌شه — نیازی به
#  scheduler یا background job نیست.
# ============================================================
SAVINGS_DAILY_RATE = 0.015          # 1.5٪ در روز
SAVINGS_MAX_ACCRUAL_DAYS = 14        # سقفِ روزهایی که یه‌جا محاسبه می‌شه (جلوگیری از باگ در قطعی طولانی)
MIN_SAVINGS_DEPOSIT = 100
MIN_SAVINGS_WITHDRAW = 1


def accrue_interest(player: dict) -> int:
    """سودِ انباشته رو حساب و به موجودیِ سپرده اضافه می‌کنه. خروجی: مقدارِ سودِ تازه‌اضافه‌شده."""
    savings = player.get("savings_zen", 0)
    if savings <= 0:
        player["savings_since"] = time.time()
        return 0
    last = player.get("savings_since", time.time())
    elapsed_days = min(SAVINGS_MAX_ACCRUAL_DAYS, (time.time() - last) / 86400)
    if elapsed_days < (1 / 24):  # کمتر از یه ساعت — صرف‌نظر (جلوگیری از نویزِ محاسباتی)
        return 0
    interest = int(savings * SAVINGS_DAILY_RATE * elapsed_days)
    if interest > 0:
        player["savings_zen"] = savings + interest
        try:
            from economy_ledger import record_interest_paid
            record_interest_paid(interest)
        except Exception:
            pass
    player["savings_since"] = time.time()
    return interest


def deposit_savings(player: dict, amount: int) -> dict:
    if amount < MIN_SAVINGS_DEPOSIT:
        return {"ok": False, "msg": f"❌ حداقلِ واریز به سپرده {MIN_SAVINGS_DEPOSIT:,} Zen هست."}
    if player.get("zen", 0) < amount:
        return {"ok": False, "msg": "❌ Zen کافی تو حسابِ جاریت نیست!"}
    accrue_interest(player)
    player["zen"] -= amount
    player["savings_zen"] = player.get("savings_zen", 0) + amount
    return {"ok": True, "msg": f"✅ **{amount:,} Zen** به سپرده منتقل شد. سود روزانه: {SAVINGS_DAILY_RATE*100:.1f}٪"}


def withdraw_savings(player: dict, amount: int) -> dict:
    accrue_interest(player)
    savings = player.get("savings_zen", 0)
    if amount < MIN_SAVINGS_WITHDRAW:
        return {"ok": False, "msg": "❌ مقدار نامعتبره."}
    if amount > savings:
        return {"ok": False, "msg": f"❌ فقط {savings:,} Zen تو سپرده داری."}
    player["savings_zen"] = savings - amount
    player["zen"] = player.get("zen", 0) + amount
    return {"ok": True, "msg": f"✅ **{amount:,} Zen** از سپرده به حسابِ جاری برگشت."}


def savings_summary(player: dict) -> dict:
    interest = accrue_interest(player)
    return {"balance": player.get("savings_zen", 0), "new_interest": interest}


# ============================================================
#  وام (Loan) — قرض از صرافِ سراسری
# ------------------------------------------------------------
#  فقط یه وامِ فعال در هر لحظه. سقفِ وام بر اساسِ سطحِ بازیکن و
#  اعتبار (credit_score، پیش‌فرض ۵۰ از ۱۰۰) محاسبه می‌شه. اگه سرِ
#  موعد بازپرداخت نشه، جریمه (روی اصلِ باقی‌مونده) اضافه می‌شه و
#  اعتبار افت می‌کنه؛ افتادنِ اعتبار زیرِ آستانه یعنی وامِ بعدی
#  رد می‌شه تا اعتبارش رو جبران کنه.
# ============================================================
LOAN_TERM_SEC = 48 * 3600           # ۴۸ ساعت مهلت
LOAN_INTEREST_RATE = 0.15           # ۱۵٪ کلِ دوره (نه روزانه)
LOAN_LATE_PENALTY_RATE = 0.25       # ۲۵٪ جریمه روی موجودیِ باقی‌مونده اگه دیر بشه
LOAN_MIN_CREDIT_TO_BORROW = 25
LOAN_CREDIT_DEFAULT = 50
LOAN_CREDIT_ON_REPAY = 5
LOAN_CREDIT_ON_LATE = -20

# 🏠 وثیقه‌ی ملک: درآمدِ غیرفعالِ خونه به‌عنوانِ وثیقه‌ی اضافه رو سقفِ وام
# حساب می‌شه — ملکِ پردرآمد یعنی بازیکن توانِ بازپرداختِ بهتری داره.
HOUSE_COLLATERAL_HOURS = 30   # معادلِ این‌قدر ساعت درآمدِ ملک به سقفِ وام اضافه می‌شه


def _house_collateral(player: dict) -> int:
    house = player.get("house")
    if not house:
        return 0
    try:
        from house_system import income_per_hour
        return int(income_per_hour(house) * HOUSE_COLLATERAL_HOURS)
    except Exception:
        return 0


def _credit(player: dict) -> int:
    return player.get("credit_score", LOAN_CREDIT_DEFAULT)


def max_loan_amount(player: dict) -> int:
    level = player.get("level", 1)
    credit = _credit(player)
    base = level * 400
    credit_mult = 0.4 + (credit / 100) * 1.2   # اعتبار ۰ → ۰.۴×  |  اعتبار ۱۰۰ → ۱.۶×
    return max(0, int(base * credit_mult) + _house_collateral(player))


def has_active_loan(player: dict) -> bool:
    return bool(player.get("loan_principal", 0) > 0)


def _settle_if_overdue(player: dict) -> str | None:
    """اگه وامِ فعلی سرِ موعدش نرسیده باشه هیچی؛ اگه گذشته، جریمه می‌زنه و پیام برمی‌گردونه."""
    if not has_active_loan(player):
        return None
    due = player.get("loan_due_at", 0)
    if time.time() <= due:
        return None
    if player.get("loan_penalized", False):
        return None  # فقط یه‌بار جریمه می‌زنیم، نه هر بار که پروفایل لود میشه
    penalty = int(player["loan_principal"] * LOAN_LATE_PENALTY_RATE)
    player["loan_principal"] += penalty
    player["loan_penalized"] = True
    player["credit_score"] = max(0, _credit(player) + LOAN_CREDIT_ON_LATE)
    return (
        f"⚠️ **وامت سرِ موعد بازپرداخت نشد!**\n"
        f"💸 جریمه‌ی {penalty:,} Zen به اصلِ وام اضافه شد.\n"
        f"📉 اعتبارت افت کرد: {_credit(player)}/100"
    )


def loan_status(player: dict) -> dict:
    late_msg = _settle_if_overdue(player)
    principal = player.get("loan_principal", 0)
    return {
        "active": principal > 0,
        "principal": principal,
        "due_at": player.get("loan_due_at", 0),
        "credit_score": _credit(player),
        "late_msg": late_msg,
        "max_loan": max_loan_amount(player),
        "house_collateral": _house_collateral(player),
    }


def borrow(player: dict, amount: int) -> dict:
    if has_active_loan(player):
        return {"ok": False, "msg": "❌ فعلاً یه وامِ بازپرداخت‌نشده داری — اول اونو تسویه کن."}
    if _credit(player) < LOAN_MIN_CREDIT_TO_BORROW:
        return {"ok": False, "msg": f"❌ اعتبارت خیلی پایینه ({_credit(player)}/100) — صراف بهت اعتماد نداره."}
    cap = max_loan_amount(player)
    if amount <= 0 or amount > cap:
        return {"ok": False, "msg": f"❌ می‌تونی حداکثر **{cap:,} Zen** وام بگیری."}

    total_due = int(amount * (1 + LOAN_INTEREST_RATE))
    player["loan_principal"] = total_due
    player["loan_taken_at"] = time.time()
    player["loan_due_at"] = time.time() + LOAN_TERM_SEC
    player["loan_penalized"] = False
    player["zen"] = player.get("zen", 0) + amount

    try:
        from economy_ledger import record_loan_issued
        record_loan_issued(amount)
    except Exception:
        pass

    return {
        "ok": True,
        "msg": (
            f"✅ **{amount:,} Zen** وام گرفتی!\n"
            f"💳 باید بازپرداخت کنی: **{total_due:,} Zen** (شامل {int(LOAN_INTEREST_RATE*100)}٪ بهره)\n"
            f"⏰ مهلت: ۴۸ ساعت — وگرنه {int(LOAN_LATE_PENALTY_RATE*100)}٪ جریمه می‌خوری."
        ),
    }


def repay(player: dict, amount: int) -> dict:
    late_msg = _settle_if_overdue(player)
    principal = player.get("loan_principal", 0)
    if principal <= 0:
        return {"ok": False, "msg": "❌ وامِ فعالی نداری."}
    if amount <= 0:
        return {"ok": False, "msg": "❌ مقدار نامعتبره."}
    if player.get("zen", 0) < amount:
        return {"ok": False, "msg": "❌ Zen کافی نداری!"}

    pay = min(amount, principal)
    player["zen"] -= pay
    player["loan_principal"] = principal - pay

    fully_paid = player["loan_principal"] <= 0
    if fully_paid:
        # تخمینِ سرانگشتی برای تفکیکِ اصل/بهره جهتِ ثبت در لجر
        original_principal = int(pay / (1 + LOAN_INTEREST_RATE)) if pay == principal else pay
        try:
            from economy_ledger import record_loan_repaid
            record_loan_repaid(original_principal, max(0, pay - original_principal))
        except Exception:
            pass
        player["loan_principal"] = 0
        player["loan_due_at"] = 0
        player["loan_penalized"] = False
        player["credit_score"] = min(100, _credit(player) + LOAN_CREDIT_ON_REPAY)
        msg = f"✅ وامت رو کامل تسویه کردی! اعتبارت رفت بالا: {_credit(player)}/100"
    else:
        msg = f"✅ **{pay:,} Zen** پرداخت شد. مانده: **{player['loan_principal']:,} Zen**"

    if late_msg:
        msg = late_msg + "\n\n" + msg
    return {"ok": True, "msg": msg}
