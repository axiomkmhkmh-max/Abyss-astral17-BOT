# ============================================================
#  ASTRAL ABYSS — Account Linking (اتصالِ حساب بینِ تلگرام و گپ)
# ------------------------------------------------------------
#  مشکلی که حل می‌کنه: چون uidِ داخلیِ گپ همیشه منفیه (gap_types.py:
#  gap_uid = -abs(chat_id)) و uidِ تلگرام همیشه مثبت، دیتابیس هیچ
#  راهی نداره بفهمه «کاربرِ ۱۲۳۴ تو تلگرام» همون «کاربرِ ۵۶۷۸ تو گپ»‌ه.
#  نتیجه: یه نفر که هم تو تلگرام هم تو گپ بازی کنه، دو تا کاراکترِ
#  کاملاً جدا داره (دو پنل، دو اینونتوری، دو لول...). این عمداً یه
#  محدودیتِ شناخته‌شده بود (نگاه کن به کامنتِ بالای gap_uid تو
#  gap_types.py) — این فایل همون فازِ بعدیه: بستنِ این حفره.
#
#  چون هیچ شناسه‌ی مشترکی بینِ تلگرام و گپ وجود نداره (نه یوزرنیم، نه
#  شماره)، اتصال نمی‌تونه خودکار/بی‌صدا باشه — پلیر خودش باید تایید
#  کنه که این دو حساب مالِ خودشه. راهش: یه کدِ یک‌بارمصرفِ کوتاه.
#
# ─── جریانِ کار ────────────────────────────────────────────────
#   ۱) پلیر تو یکی از دو پلتفرم (مثلاً تلگرام) دستورِ «🔗 اتصال حساب»
#      رو می‌زنه → generate_link_code(uid) یه کدِ ۶ کاراکتری می‌سازه
#      که ۱۰ دقیقه معتبره؛ همون uid که کد رو ساخته، «حسابِ اصلی»
#      (primary) می‌مونه — یعنی بعدِ اتصال، پیشرفت زیرِ همین uid ذخیره
#      می‌شه.
#   ۲) همون کد رو تو پلتفرمِ دیگه (گپ) وارد می‌کنه → redeem_link_code.
#   ۳) اگه حسابِ دومی (که کد رو وارد کرده) پیشرفتِ واقعی نداشته باشه
#      (کاراکتر نساخته/تازه‌ساز)، فقط به‌عنوانِ الیاس به primary وصل
#      می‌شه — چیزی گم نمی‌شه چون چیزی نبود.
#   ۴) اگه پیشرفتِ واقعی داشته باشه، یه merge محافظه‌کارانه انجام
#      می‌شه (Zen/کیل/دمیج جمع می‌شن، لولِ بیشتر نگه داشته می‌شه،
#      اینونتوری‌ها ادغام می‌شن) و بعد الیاس می‌شه.
#   ۵) از اون به بعد database.get_player/save_player (که خودشون
#      resolve_uid رو صدا می‌زنن) خودکار هر دو uid رو به‌سمتِ primary
#      هدایت می‌کنن — نیازی به تغییرِ هیچ‌کدوم از بقیه‌ی فایل‌های
#      پروژه نیست.
# ============================================================
from __future__ import annotations

import random
import time

from database import (
    account_links_col,
    link_codes_col,
    resolve_uid,
    get_player_raw,
    save_player_raw,
)

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # بدونِ حروف/عددهای شبیهِ هم (I/1, O/0)
CODE_LENGTH = 6
CODE_TTL_SECONDS = 10 * 60  # ۱۰ دقیقه


def _new_code() -> str:
    return "".join(random.choices(CODE_ALPHABET, k=CODE_LENGTH))


def generate_link_code(requester_uid: int) -> tuple[bool, str]:
    """
    یه کدِ اتصال برای حسابِ requester_uid می‌سازه. این uid همون کسیه که
    بعدِ اتصال، «حسابِ اصلی» می‌مونه. برمی‌گردونه: (موفق؟, پیام/کد).
    """
    root = resolve_uid(requester_uid)

    # اگه خودِ این حساب از قبل الیاسِ یه حسابِ دیگه‌ست، معنی نداره کدِ
    # جدید بسازه براش — کدش باید مالِ ریشه‌ی واقعیش باشه.
    if root != requester_uid:
        return False, (
            "❌ این حساب از قبل به یه حسابِ دیگه وصل شده — دیگه لازم نیست "
            "دوباره وصلش کنی."
        )

    # کدهای قبلیِ استفاده‌نشده‌ی همین uid رو باطل کن تا تو دیتابیس تلنبار نشن.
    link_codes_col().delete_many({"primary": root, "used": False})

    code = _new_code()
    link_codes_col().insert_one({
        "_id": code,
        "primary": root,
        "created_at": time.time(),
        "expires_at": time.time() + CODE_TTL_SECONDS,
        "used": False,
    })
    return True, code


def _has_progress(doc: dict) -> bool:
    """آیا این سند پیشرفتِ واقعی داره؟ (برای تصمیم‌گیری: alias ساده یا merge)."""
    if not doc:
        return False
    if doc.get("character"):
        return True
    if doc.get("kills", 0) > 0 or doc.get("level", 1) > 1:
        return True
    if doc.get("inventory"):
        return True
    if doc.get("zen", 0) not in (0, 1125):  # ۱۱۲۵ = موجودیِ پیش‌فرضِ حسابِ تازه‌ساز
        return True
    return False


def _merge_into_primary(primary_doc: dict, alias_doc: dict) -> dict:
    """
    ادغامِ محافظه‌کارانه: هیچ‌وقت چیزی حذف نمی‌شه، فقط جمع/بزرگ‌ترش
    نگه داشته می‌شه. برای فیلدهایی که منطقِ «جمع‌شدن» توشون معنی نداره
    (مثلِ گیلد، خونه، اکتیو فایت) دستکاری نمی‌کنیم — اونا رو primary
    نگه می‌داره؛ اگه الیاس چیزِ مشابهی داشته، دستیه (پلیر باید خودش
    بعداً به ادمین بگه اگه چیزِ خاصی جا افتاد).
    """
    p, a = primary_doc, alias_doc

    for numeric_field in (
        "zen", "kills", "total_damage", "pvp_wins", "pvp_losses",
        "loot_streak", "loot_best_streak",
    ):
        p[numeric_field] = p.get(numeric_field, 0) + a.get(numeric_field, 0)

    # لول: بزرگ‌تره نگه داشته می‌شه (جمع‌کردنِ XP بینِ دو سیستمِ جداگونه
    # منطقی نیست)، ولی XP و max_hpِ همون لولِ بزرگ‌تر هم باهاش میاد.
    if a.get("level", 1) > p.get("level", 1):
        p["level"] = a["level"]
        p["xp"] = a.get("xp", 0)
        p["max_hp"] = a.get("max_hp", p.get("max_hp", 100))
        p["hp"] = a.get("hp", p.get("hp", 100))

    # اگه primary اصلاً کاراکتر نساخته ولی الیاس ساخته، کاراکترِ الیاس رو بگیر.
    if not p.get("character") and a.get("character"):
        for k in ("character", "gender", "gender_chosen", "map"):
            if k in a:
                p[k] = a[k]

    # اینونتوری‌ها رو بدونِ حذفِ چیزی به‌هم بچسبون.
    p["inventory"] = (p.get("inventory") or []) + (a.get("inventory") or [])

    # دستاورد/عنوان‌ها: یونیِ دو لیست (بدونِ تکراری).
    for list_field in ("titles_unlocked", "achievements_done", "characters_seen"):
        merged = list(p.get(list_field) or [])
        for item in (a.get(list_field) or []):
            if item not in merged:
                merged.append(item)
        p[list_field] = merged

    return p


def redeem_link_code(code: str, requester_uid: int) -> tuple[bool, str]:
    """
    کدِ اتصال رو با حسابِ requester_uid (که تو پلتفرمِ دیگه واردش کرده)
    وصل می‌کنه. برمی‌گردونه: (موفق؟, پیامِ نمایشی).
    """
    code = (code or "").strip().upper()
    if not code:
        return False, "❌ کد رو درست وارد کن."

    doc = link_codes_col().find_one({"_id": code})
    if not doc:
        return False, "❌ این کد معتبر نیست."
    if doc.get("used"):
        return False, "❌ این کد قبلاً استفاده شده — یه کدِ جدید بگیر."
    if time.time() > doc.get("expires_at", 0):
        return False, "❌ این کد منقضی شده — یه کدِ جدید بگیر (کدها فقط ۱۰ دقیقه معتبرن)."

    primary_root = resolve_uid(doc["primary"])
    requester_root = resolve_uid(requester_uid)

    if primary_root == requester_root:
        return False, "❌ نمی‌تونی یه حساب رو به خودش وصل کنی."

    # اگه خودِ درخواست‌کننده از قبل جایی الیاس شده.
    if account_links_col().find_one({"_id": requester_root}):
        return False, "❌ این حساب از قبل به یه حسابِ دیگه وصل شده."

    # اگه درخواست‌کننده خودش «اصلیِ» یه یا چند الیاسِ دیگه‌ست، باید اول
    # اونا رو جدا کنی (edge caseِ نادر — فعلاً فقط جلوشو می‌گیریم که
    # زنجیره‌ی لینک درست نشه).
    if account_links_col().find_one({"primary": requester_root}):
        return False, (
            "❌ این حساب خودش یه حسابِ اصلیه که یه حسابِ دیگه بهش وصله؛ "
            "نمی‌تونی به یه primaryِ دیگه وصلش کنی."
        )

    alias_doc = get_player_raw(requester_root) or {}
    primary_doc = get_player_raw(primary_root)
    if not primary_doc:
        return False, "❌ حسابِ اصلی پیدا نشد (شاید هنوز /start نزده)."

    merged_note = ""
    if _has_progress(alias_doc):
        primary_doc = _merge_into_primary(primary_doc, alias_doc)
        merged_note = " پیشرفتِ قبلیِ این حساب (Zen، کیل، اینونتوری و...) هم باهاش ادغام شد."

    save_player_raw(primary_root, primary_doc)

    account_links_col().insert_one({
        "_id": requester_root,
        "primary": primary_root,
        "linked_at": time.time(),
    })
    link_codes_col().update_one({"_id": code}, {"$set": {"used": True}})

    return True, (
        "✅ **حساب‌ها با موفقیت وصل شدن!**\n"
        "از الان به بعد، چه از تلگرام چه از گپ وارد بشی، دقیقاً همون یه "
        "کاراکتر و یه پیشرفت رو می‌بینی — دیگه دو پنلِ جدا نداری."
        f"{merged_note}"
    )


def is_linked(user_id: int) -> bool:
    """آیا این uid به یه حسابِ دیگه وصله (یعنی الیاسه، نه ریشه)؟"""
    return account_links_col().find_one({"_id": user_id}) is not None


def link_status_text(user_id: int) -> str:
    """متنِ وضعیتِ اتصال برای نمایش تو دکمه‌ی «🔗 اتصال حساب»."""
    root = resolve_uid(user_id)
    if root != user_id:
        return (
            "🔗 این حساب به یه حسابِ دیگه وصل شده — پیشرفتت اونجا ذخیره می‌شه، "
            "همینجا هم دقیقاً همونو می‌بینی."
        )
    linked_aliases = list(account_links_col().find({"primary": user_id}))
    if linked_aliases:
        return f"🔗 این حساب، حسابِ اصلیه — {len(linked_aliases)} حسابِ دیگه بهش وصله."
    return (
        "🔗 **اتصالِ حساب (تلگرام ⇄ گپ)**\n\n"
        "اگه هم تو تلگرام هم تو گپ بازی می‌کنی و می‌خوای هر دو یه کاراکترِ "
        "مشترک باشن (نه دو پنلِ جدا)، این‌طوری وصلشون کن:\n\n"
        "۱) همینجا `/link` رو بزن تا یه کد بگیری (۱۰ دقیقه معتبره).\n"
        "۲) برو تو اون یکی پلتفرم، `/link CODE` رو با همون کد بزن.\n\n"
        "تمام — از اون لحظه، هر دو حساب دقیقاً به یه کاراکتر اشاره می‌کنن."
    )
