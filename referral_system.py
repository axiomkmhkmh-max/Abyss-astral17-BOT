# ============================================================
#  ASTRAL ABYSS — REFERRAL / DEEP-LINK SYSTEM
# ------------------------------------------------------------
#  مسئولِ ساختن و پارس‌کردنِ لینک‌های عمیق (deep link) به PV ربات —
#  چه از تویِ گروه (دکمه‌ی «بازی کن» زیرِ پیام‌های /graid و /gtop)
#  چه از تویِ اینلاین‌مود (کارتِ کاراکتر/چالش که تو هر چتی شیر می‌شه).
#
#  فرمتِ payload (بعدِ /start در آدرس):
#     ref_group_<chat_id>      → از یه گروه اومده
#     ref_card_<uid>           → از رو کارتِ کاراکترِ یه بازیکن (اینلاین)
#     ref_duel_<uid>           → از رو دعوت‌نامه‌ی دوئل (اینلاین)
#
#  این فایل هیچ اسکیمای player رو دست نمی‌زنه؛ فقط یه کالکشنِ جدا
#  به اسمِ `referrals` تویِ Mongo داره (idempotent روی uid تازه‌وارد،
#  یعنی هر کاربر فقط یه‌بار به‌عنوانِ «رفرال» ثبت می‌شه).
# ============================================================
import time
import re
from pg_shim import Collection

from database import get_db

BOT_USERNAME = "AbyssAstralbot"
BOT_LINK = f"https://t.me/{BOT_USERNAME}"

_PAYLOAD_RE = re.compile(r"^ref_(group|card|duel)_(-?\d+)$")


def referrals_col() -> Collection:
    return get_db()["referrals"]


# ─── ساختِ لینک‌ها ──────────────────────────────────────────────

def group_ref_link(chat_id: int) -> str:
    return f"{BOT_LINK}?start=ref_group_{chat_id}"


def card_ref_link(uid: int) -> str:
    return f"{BOT_LINK}?start=ref_card_{uid}"


def duel_ref_link(uid: int) -> str:
    return f"{BOT_LINK}?start=ref_duel_{uid}"


# ─── پارس‌کردن ──────────────────────────────────────────────────

def parse_payload(payload: str | None) -> dict | None:
    """payload خامِ بعدِ /start رو می‌گیره و {kind, value} برمی‌گردونه، یا None."""
    if not payload:
        return None
    m = _PAYLOAD_RE.match(payload.strip())
    if not m:
        return None
    kind, raw = m.group(1), m.group(2)
    return {"kind": kind, "value": int(raw)}


# ─── ثبت + شمارش ────────────────────────────────────────────────

def track_referral(payload: str | None, new_uid: int) -> dict | None:
    """اگه new_uid تا الان به‌خاطرِ رفرال ثبت نشده باشه، ثبتش می‌کنه و
    اطلاعاتِ منبع رو برمی‌گردونه (برای مثلاً اطلاع‌رسانی به گروه).
    اگه قبلاً ثبت شده بود یا payload نامعتبر بود، None برمی‌گردونه."""
    parsed = parse_payload(payload)
    if not parsed:
        return None

    existing = referrals_col().find_one({"_id": new_uid})
    if existing:
        return None  # قبلاً یه‌بار ثبت شده — دوباره حساب نشه

    doc = {
        "_id": new_uid,
        "kind": parsed["kind"],
        "source": parsed["value"],
        "ts": time.time(),
    }
    referrals_col().insert_one(doc)
    return doc


def group_invite_count(chat_id: int) -> int:
    return referrals_col().count_documents({"kind": "group", "source": chat_id})


def top_inviting_groups(limit: int = 10) -> list[dict]:
    pipeline = [
        {"$match": {"kind": "group"}},
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    return list(referrals_col().aggregate(pipeline))
