# ============================================================
#  ASTRAL ABYSS — Gap Zen Shop (پرداختِ واقعیِ گپ)
# ------------------------------------------------------------
#  این فایل پورتِ چیزی نیست — یه فیچرِ کاملاً جدیده، چون تلگرام
#  (بدونِ Stars) معادلِ این رو نداره. از قابلیتِ «دکمه‌ی پرداخت»یِ
#  خودِ گپ استفاده می‌کنه (amount/currency/ref_id/desc رو
#  gap_types.InlineKeyboardButton از قبل پشتیبانی می‌کنه).
#
#  جریانِ کار:
#   ۱) /buyzen → منوی پک‌ها؛ هر دکمه یه ref_id منحصربه‌فرد داره که
#      قبلش تو system_col ذخیره شده (وضعیت=pending).
#   ۲) کاربر تو اپِ گپ پرداخت می‌کنه؛ گپ webhookِ ما رو با
#      type="paycallback"/"invoicecallback" صدا می‌زنه.
#   ۳) ما هرگز به بدنه‌ی خودِ webhook اعتماد نمی‌کنیم — با
#      client.verify_payment/verify_invoice از خودِ گپ تأییدِ
#      رسمی می‌گیریم، بعد Zen رو واریز می‌کنیم.
#   ۴) idempotent: هر ref_id فقط یه‌بار می‌تونه Zen واریز کنه
#      (چون webhookها گاهی تکراری می‌رسن).
#   ۵) یه دکمه‌ی «بررسیِ دستی» هم هست برای وقتی webhook گم شد.
#
#  ⚠️ نکته‌ی مهم: مبلغ‌ها (amount) اینجا به ریال فرض شدن — قبل از
#  رفتن رو پروداکشن، حتماً با مستنداتِ my.gap.im چک کن که واحدِ
#  amount ریاله یا تومن، و اعداد رو مطابقش تنظیم کن.
# ============================================================
from __future__ import annotations

import secrets
import time

from gap_dispatcher import GapDispatcher
from gap_types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, system_col
from logger import log_sync

CURRENCY = "IRR"

ZEN_PACKAGES = [
    {"id": "small",  "price": 50_000,  "zen": 5_000,  "label": "📦 پکِ کوچیک",  "desc": "۵,۰۰۰ Zen"},
    {"id": "medium", "price": 100_000, "zen": 12_000, "label": "📦 پکِ متوسط",  "desc": "۱۲,۰۰۰ Zen (٪۲۰ بونوس)"},
    {"id": "large",  "price": 250_000, "zen": 35_000, "label": "💎 پکِ بزرگ",   "desc": "۳۵,۰۰۰ Zen (٪۴۰ بونوس)"},
    {"id": "mega",   "price": 500_000, "zen": 80_000, "label": "👑 پکِ ویژه",   "desc": "۸۰,۰۰۰ Zen (٪۶۰ بونوس)"},
]
_PKG_BY_ID = {p["id"]: p for p in ZEN_PACKAGES}

PENDING_TTL = 3600  # یه ساعت — بعدش رکوردِ pending دیگه معتبر نیست


def _new_ref_id(uid: int, pkg_id: str) -> str:
    # خودِ ref_id هم uid و pkg رو تو خودش داره (self-describing) تا
    # حتی اگه رکوردِ system_col به هر دلیلی گم شد (مثلاً قبل از این
    # فیچر ساخته شده یا پاک شده)، بازم بشه از رو خودِ ref_id بازسازیش کرد.
    return f"zenshop-{abs(uid)}-{pkg_id}-{secrets.token_hex(4)}"


def _parse_ref_id(ref_id: str) -> tuple[int, str] | None:
    try:
        _, uid_s, pkg_id, _ = ref_id.split("-", 3)
        uid = -int(uid_s)  # uidِ داخلیِ گپ همیشه منفیه
        if pkg_id not in _PKG_BY_ID:
            return None
        return uid, pkg_id
    except Exception:
        return None


def _shop_kb(uid: int) -> InlineKeyboardMarkup:
    rows = []
    for pkg in ZEN_PACKAGES:
        ref_id = _new_ref_id(uid, pkg["id"])
        system_col().update_one(
            {"_id": f"zenpay:{ref_id}"},
            {"$set": {
                "uid": uid, "pkg_id": pkg["id"], "zen": pkg["zen"],
                "price": pkg["price"], "status": "pending", "created_at": time.time(),
            }},
            upsert=True,
        )
        price_txt = f"{pkg['price']:,} ریال"
        rows.append([InlineKeyboardButton(
            text=f"{pkg['label']} — {pkg['desc']} ({price_txt})",
            amount=pkg["price"],
            currency=CURRENCY,
            ref_id=ref_id,
            desc=f"خریدِ {pkg['desc']} — Astral Abyss",
        )])
    rows.append([InlineKeyboardButton(text="🔙 برگشت", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _recheck_kb(ref_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 بررسیِ وضعیتِ پرداخت", callback_data=f"zencheck:{ref_id}")],
    ])


async def _credit_if_verified(bot, ref_id: str, chat_id: int | None = None) -> str:
    """
    منطقِ مرکزیِ واریز — هم از هندلرِ paycallback صدا زده می‌شه، هم از
    دکمه‌ی «بررسیِ دستی». همیشه اول از خودِ گپ تأییدِ رسمی می‌گیره،
    بعد فقط یه‌بار (idempotent) Zen واریز می‌کنه.
    برمی‌گردونه: متنِ پیامی که باید به کاربر نشون داده بشه.
    """
    doc = system_col().find_one({"_id": f"zenpay:{ref_id}"})
    parsed = _parse_ref_id(ref_id)

    if not doc:
        if not parsed:
            return "❌ این تراکنش پیدا نشد."
        uid, pkg_id = parsed
        pkg = _PKG_BY_ID[pkg_id]
        doc = {"uid": uid, "pkg_id": pkg_id, "zen": pkg["zen"], "price": pkg["price"], "status": "pending"}
        system_col().update_one({"_id": f"zenpay:{ref_id}"}, {"$set": doc}, upsert=True)

    if doc.get("status") == "credited":
        return f"✅ این پرداخت قبلاً تأیید و {doc['zen']:,} Zen واریز شده بود."

    uid = doc["uid"]
    target_chat_id = chat_id if chat_id is not None else abs(uid)

    verified = False
    try:
        res = await bot.client.verify_payment(target_chat_id, ref_id)
        verified = _looks_successful(res)
    except Exception as e:
        log_sync(f"🟡 zenshop verify_payment error ({ref_id}): {e}", "ECONOMY")

    if not verified:
        try:
            res = await bot.client.verify_invoice(target_chat_id, ref_id)
            verified = _looks_successful(res)
        except Exception as e:
            log_sync(f"🟡 zenshop verify_invoice error ({ref_id}): {e}", "ECONOMY")

    if not verified:
        return "⏳ هنوز تأییدِ پرداخت از گپ نیومده. چند لحظه دیگه دوباره امتحان کن."

    player = get_player(uid)
    if not player:
        return "❌ کاراکترت پیدا نشد؛ اول /start بزن، بعد دوباره دکمه‌ی بررسی رو بزن."

    player["zen"] = player.get("zen", 0) + doc["zen"]
    save_player(uid, player)
    system_col().update_one({"_id": f"zenpay:{ref_id}"}, {"$set": {"status": "credited", "credited_at": time.time()}})

    log_sync(
        f"💎 **ZEN SHOP**\n👤 {player.get('name','—')} (`{uid}`)\n"
        f"💰 +{doc['zen']:,} Zen (پرداختِ {doc['price']:,} ریال) | ref: `{ref_id}`",
        "ECONOMY",
    )
    return f"✅ پرداخت تأیید شد! **{doc['zen']:,} Zen** به حسابت اضافه شد.\n💰 موجودیِ فعلی: {player['zen']:,} Zen"


def _looks_successful(res) -> bool:
    """
    نکته: من مستنداتِ دقیقِ فرمتِ پاسخِ verify_payment/verify_invoice
    رو ندارم، پس چندتا کلید/مقدارِ محتمل رو با احتیاط چک می‌کنم. قبل
    از پروداکشن حتماً با یه پرداختِ تستی خروجیِ واقعی رو لاگ بگیر و
    این تابع رو دقیق‌تر کن.
    """
    if not isinstance(res, dict):
        return False
    status = str(res.get("status", "")).lower()
    if status in ("success", "paid", "ok", "verified", "completed", "1", "true"):
        return True
    if res.get("success") is True or res.get("paid") is True or res.get("verified") is True:
        return True
    return False


def register_gap_zen_shop_handlers(dp: GapDispatcher):
    bot = dp.bot

    @dp.message(commands=["buyzen", "zenshop"], text="💎 فروشگاه Zen")
    async def cmd_buyzen(msg: Message):
        uid = msg.from_user.id
        player = get_player(uid)
        if not player:
            await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
            return
        await msg.answer(
            f"💎 **فروشگاهِ Zen**\n\n"
            f"موجودیِ فعلیت: **{player.get('zen',0):,} Zen**\n\n"
            f"یکی از پک‌ها رو انتخاب کن؛ پرداخت مستقیم تو خودِ گپ انجام می‌شه:",
            reply_markup=_shop_kb(uid),
        )

    @dp.on_payment
    async def handle_payment(user, data):
        # فرمتِ دقیقِ data مستند نیست؛ چندتا کلیدِ محتمل رو امتحان می‌کنیم.
        ref_id = None
        if isinstance(data, dict):
            ref_id = data.get("ref_id") or data.get("id") or data.get("invoice_id") or data.get("refId")
        if not ref_id:
            log_sync(f"🔴 zenshop: paycallback بدونِ ref_id قابل‌تشخیص: {data}", "ERROR")
            return

        result_text = await _credit_if_verified(bot, ref_id, chat_id=user.chat_id)
        try:
            await bot.send_message(user.chat_id, result_text)
        except Exception:
            pass

    @dp.callback_query(data_startswith="zencheck:")
    async def cb_zen_check(cb: CallbackQuery):
        ref_id = cb.data.split(":", 1)[1]
        result_text = await _credit_if_verified(bot, ref_id, chat_id=cb.from_user.chat_id)
        await cb.answer(result_text, show_alert=True)
