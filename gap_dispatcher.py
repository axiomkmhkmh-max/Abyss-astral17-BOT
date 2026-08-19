# ============================================================
#  ASTRAL ABYSS — Gap Dispatcher
# ------------------------------------------------------------
#  چون گپ کتابخونه‌ای مثل aiogram (Router, F filters, FSM) نداره،
#  این فایل یه دیسپچرِ سبک می‌سازه که رفتارِ لازم رو پوشش می‌ده:
#   • message handlers (بر اساس /command یا متن آزاد)
#   • callback handlers (بر اساس cb_data دقیق یا startswith)
#   • state ساده به‌ازای هر کاربر (جایگزینِ FSM aiogram) — برای
#     چیزهایی مثل «منتظرِ واردکردنِ عددِ XP توسط ادمین»
#   • میدل‌ورها (لیست از async func(update, data) -> bool ادامه/قطع)
#
#  استفاده تقریباً شبیه aiogram قدیمیه:
#     dp = GapDispatcher(bot)
#     dp.message(commands=["start"])(cmd_start)
#     dp.callback_query(data_startswith="menu:")(on_menu)
#     await dp.feed_update(raw_json_from_webhook)
# ============================================================
from __future__ import annotations

import inspect
import logging
import traceback
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from gap_types import CallbackQuery, GapUser, Message, gap_uid

log = logging.getLogger("gap.dispatcher")

Handler = Callable[..., Awaitable[Any]]

# ─── حضورِ آنلاین (معادلِ last_seen/is_online تو bot.py برای تلگرام) ───
# اونجا هر آپدیت (پیام/کال‌بک/...) لحظه‌ی last_seen رو آپدیت می‌کرد؛
# اینجا هم دقیقاً همون کارو تو _dispatch (پایین‌تر) برای هر آپدیتِ گپ
# انجام می‌دیم، مستقل از این‌که کدوم هندلر نهایی صداش می‌زنه.
GAP_LAST_SEEN: dict[int, float] = {}
GAP_OFFLINE_THRESHOLD = 300  # ۵ دقیقه، هم‌ارزِ OFFLINE_THRESHOLD تو bot.py


def touch_gap_presence(uid: int):
    import time
    GAP_LAST_SEEN[uid] = time.time()


def gap_is_online(uid: int) -> bool:
    import time
    return time.time() - GAP_LAST_SEEN.get(uid, 0) < GAP_OFFLINE_THRESHOLD


@dataclass
class _MsgRule:
    handler: Handler
    commands: Optional[list[str]] = None
    text_equals: Optional[list[str]] = None
    text_startswith: Optional[str] = None
    catch_all: bool = False


@dataclass
class _CbRule:
    handler: Handler
    data_equals: Optional[list[str]] = None
    data_startswith: Optional[str] = None


class _SimpleStateStore:
    """جایگزینِ سبکِ FSM aiogram — یک دیکشنری به‌ازای هر uid."""

    def __init__(self):
        self._data: dict[int, dict] = {}

    def get(self, uid: int) -> dict:
        return self._data.setdefault(uid, {})

    def set_state(self, uid: int, state: Optional[str]):
        self.get(uid)["_state"] = state

    def get_state(self, uid: int) -> Optional[str]:
        return self._data.get(uid, {}).get("_state")

    def clear(self, uid: int):
        self._data.pop(uid, None)


class GapDispatcher:
    def __init__(self, bot):
        self.bot = bot  # GapBotAdapter
        self._msg_rules: list[_MsgRule] = []
        self._cb_rules: list[_CbRule] = []
        self._join_handlers: list[Handler] = []
        self._leave_handlers: list[Handler] = []
        self._form_handlers: list[Handler] = []
        self._pay_handlers: list[Handler] = []
        self._state_rules: dict[str, Handler] = {}
        self.state = _SimpleStateStore()
        self.error_handler: Optional[Callable[[Exception, Any], Awaitable[None]]] = None

    # ─── دکوریتورها / رجیستر ────────────────────────────────
    def message(self, commands: Optional[list[str]] = None,
                text: Optional[list[str] | str] = None,
                text_startswith: Optional[str] = None,
                catch_all: bool = False):
        def deco(fn: Handler) -> Handler:
            self.register_message(fn, commands=commands, text=text,
                                   text_startswith=text_startswith, catch_all=catch_all)
            return fn
        return deco

    def register_message(self, fn: Handler, commands=None, text=None,
                          text_startswith=None, catch_all=False):
        if isinstance(text, str):
            text = [text]
        self._msg_rules.append(_MsgRule(
            handler=fn, commands=commands, text_equals=text,
            text_startswith=text_startswith, catch_all=catch_all,
        ))

    def callback_query(self, data: Optional[list[str] | str] = None,
                        data_startswith: Optional[str] = None):
        def deco(fn: Handler) -> Handler:
            self.register_callback(fn, data=data, data_startswith=data_startswith)
            return fn
        return deco

    def register_callback(self, fn: Handler, data=None, data_startswith=None):
        if isinstance(data, str):
            data = [data]
        self._cb_rules.append(_CbRule(handler=fn, data_equals=data, data_startswith=data_startswith))

    def on_join(self, fn: Handler):
        self._join_handlers.append(fn)
        return fn

    def on_leave(self, fn: Handler):
        self._leave_handlers.append(fn)
        return fn

    def on_form(self, fn: Handler):
        self._form_handlers.append(fn)
        return fn

    # ─── حالت (state) روی متنِ آزاد ──────────────────────────────
    # چند سیستم (shop, bank, ...) هرکدوم می‌خوان یه مرحله‌ی «منتظرِ متنِ
    # آزاد» داشته باشن (مثلاً «قیمت رو بفرست»، «شماره‌کارت و مبلغ رو بفرست»).
    # چون فقط یه catch_all سراسری معنی نداره (اولین‌ثبت‌شده همیشه برنده
    # می‌شد و بقیه‌ی سیستم‌ها اصلاً پیام رو نمی‌دیدن)، به‌جاش هر سیستم یه
    # state منحصربه‌فرد ثبت می‌کنه (dp.state.set_state(uid, "shop:price"))
    # و یه هندلر برای همون state:
    #     @dp.on_state("shop:price")
    #     async def handle_price(msg): ...
    # وقتی کاربری تو یه state باشه، پیامِ متنیِ بعدیش مستقیم به همون
    # هندلر می‌ره (قبل از قوانینِ عادیِ command/text و قبل از catch_all).
    def on_state(self, state: str):
        def deco(fn: Handler) -> Handler:
            self.register_state(state, fn)
            return fn
        return deco

    def register_state(self, state: str, fn: Handler):
        self._state_rules[state] = fn

    def on_payment(self, fn: Handler):
        self._pay_handlers.append(fn)
        return fn

    # ─── ورودیِ اصلی: یک آپدیت خام از webhook گپ ────────────
    async def feed_update(self, payload: dict):
        try:
            await self._dispatch(payload)
        except Exception as e:  # noqa: BLE001 — هیچ کرشی نباید کل وب‌هوک رو بخوابونه
            log.error("Unhandled dispatch error: %s\n%s", e, traceback.format_exc())
            if self.error_handler:
                try:
                    await self.error_handler(e, payload)
                except Exception:
                    log.error("error_handler خودش هم خطا داد:\n%s", traceback.format_exc())

    async def _dispatch(self, payload: dict):
        msg_type = payload.get("type")
        chat_id = payload.get("chat_id")
        raw_from = payload.get("from") or {}
        if isinstance(raw_from, str):
            import json as _json
            try:
                raw_from = _json.loads(raw_from)
            except Exception:
                raw_from = {}

        # ─── 🔴 نکته‌ی حیاتی: تویِ گروه‌های گپ، chat_id مالِ خودِ
        # گروهه (بینِ همه‌ی اعضا مشترکه)، نه مالِ یه بازیکنِ خاص! اگه
        # اینجا هویتِ کاربر (user.id) رو فقط از chat_id می‌ساختیم،
        # همه‌ی اعضای یه گروه به یه uid یکسان می‌رسیدن — یعنی همه یه
        # کاراکترِ مشترک می‌داشتن و هر چک‌ِ «فقط صاحبش بزنه» هم خودبه‌خود
        # برای همه پاس می‌شد (این همون باگیه که گزارش شد).
        #
        # برای همین، اول دنبالِ یه شناسه‌ی واقعیِ per-user تو raw_from
        # می‌گردیم (چون تو اکثرِ پلتفرم‌های پیام‌رسان، از جمله ظاهراً
        # گپ، فیلدِ from همیشه شناسه‌ی خودِ فرستنده رو داره، چه پیام
        # تو چتِ خصوصی باشه چه تو گروه) و اگه پیدا شد، هویت رو از
        # روی همون می‌سازیم، نه از chat_id.
        #
        # ⚠️ چون مستنداتِ رسمیِ فرمتِ دقیقِ این فیلد رو نداریم، چندتا
        # اسمِ محتمل رو امتحان می‌کنیم. اگه بعدِ این فیکس هنوز باگ تو
        # گروه هست، یعنی حدسِ اسمِ فیلد اشتباهه — لاگِ هشدارِ پایین رو
        # چک کن، اونجا کلیدهای واقعیِ raw_from رو می‌بینی و می‌شه اسمِ
        # درست رو جایگزین کرد.
        sender_id = None
        for key in ("id", "user_id", "sender_id", "from_id", "uid"):
            v = raw_from.get(key)
            if v not in (None, "", 0):
                try:
                    sender_id = int(v)
                    break
                except (TypeError, ValueError):
                    continue

        if sender_id is not None:
            internal_id = gap_uid(sender_id)
        elif chat_id is not None:
            internal_id = gap_uid(chat_id)
            if raw_from:
                log.warning(
                    "هیچ فیلدِ شناسه‌ی per-user تو raw_from پیدا نشد؛ برگشتیم به "
                    "chat_id (تو گروه‌ها یعنی همه یه uid یکسان می‌گیرن). "
                    "کلیدهای موجود تو raw_from: %s", list(raw_from.keys()),
                )
        else:
            internal_id = 0

        user = GapUser(
            id=internal_id,
            chat_id=chat_id,
            first_name=raw_from.get("name") or raw_from.get("username") or "",
            username=raw_from.get("username"),
        )

        if msg_type != "leave":
            touch_gap_presence(user.id)

        if msg_type == "join":
            for h in self._join_handlers:
                await h(user)
            return

        if msg_type == "leave":
            for h in self._leave_handlers:
                await h(user)
            return

        if msg_type == "triggerButton":
            data = payload.get("data")
            cb_data, message_id, callback_id = _unpack_trigger(data)
            cbq = CallbackQuery(self.bot, callback_id, chat_id, message_id, cb_data, user)
            for rule in self._cb_rules:
                if rule.data_equals and cb_data in rule.data_equals:
                    return await rule.handler(cbq)
                if rule.data_startswith and cb_data.startswith(rule.data_startswith):
                    return await rule.handler(cbq)
            log.info("cb_data بدون هندلر: %s", cb_data)
            return

        if msg_type == "submitForm":
            for h in self._form_handlers:
                await h(user, payload.get("data"))
            return

        if msg_type in ("paycallback", "invoicecallback"):
            for h in self._pay_handlers:
                await h(user, payload.get("data"))
            return

        if msg_type == "text":
            text = payload.get("data") or ""
            msg = Message(self.bot, chat_id, None, text, user, raw=payload)
            await self._dispatch_message(msg, text)
            return

        # image / video / audio / voice / file / contact / location →
        # فعلاً فقط لاگ می‌شه؛ هر هندلرِ خاص می‌تونه بعداً روی msg_type چک کنه
        log.info("نوع پیامِ پوشش‌داده‌نشده: %s", msg_type)

    async def _dispatch_message(self, msg: Message, text: str):
        stripped = text.strip()

        # اگه کاربر تو یه state هست و پیامش کامند نیست (کامندها همیشه باید
        # بتونن از یه state خارج کنن، مثلاً /shop یا /bank دوباره)، مستقیم
        # به هندلرِ همون state بفرست — قبل از قوانینِ عادیِ متن.
        if not stripped.startswith("/"):
            st = self.state.get_state(msg.from_user.id)
            if st and st in self._state_rules:
                return await self._state_rules[st](msg)

        # ─── 🐛 فیکس: کامندهای گروهی با @یوزرنیم ────────────────────
        # وقتی یه گروه چندتا ربات داره، کاربرا عادت دارن کامند رو با
        # منشن ربات بزنن (مثلاً /characters@AbyssAstralbot) تا مطمئن
        # بشن به همون ربات می‌رسه — دقیقاً مثل تلگرام. قبلاً اینجا فقط
        # تطبیقِ دقیقِ "/characters" یا "/characters " چک می‌شد، پس هر
        # کامندی که این @یوزرنیم رو داشت با هیچ rule ای مچ نمی‌شد و بی‌صدا
        # (یا با فالبکِ نامشخص) شکست می‌خورد — همون باگی که تقریباً همه‌ی
        # کامندهای تو گپ باهاش دست‌وپنجه نرم می‌کردن.
        # این‌جا کامند رو جدا از آرگومان‌ها و از @منشن پاک می‌کنیم و فقط
        # با اسمِ خالصِ کامند مقایسه می‌کنیم.
        first_token = stripped.split(maxsplit=1)[0] if stripped else ""
        cmd_part = None
        if first_token.startswith("/"):
            cmd_part = first_token[1:].split("@", 1)[0].lower()

        for rule in self._msg_rules:
            if rule.commands and cmd_part is not None:
                if cmd_part in (c.lower() for c in rule.commands):
                    return await rule.handler(msg)
            if rule.text_equals and stripped in rule.text_equals:
                return await rule.handler(msg)
            if rule.text_startswith and stripped.startswith(rule.text_startswith):
                return await rule.handler(msg)
        for rule in self._msg_rules:
            if rule.catch_all:
                return await rule.handler(msg)


def _unpack_trigger(data) -> tuple[str, Optional[int], str]:
    """
    payload["data"] برای triggerButton طبق مستندات یه dict/JSON با
    کلیدهای data (=cb_data واقعی)، message_id، callback_id هست.
    """
    if isinstance(data, str):
        import json as _json
        try:
            data = _json.loads(data)
        except Exception:
            return data, None, ""
    if isinstance(data, dict):
        return data.get("data", ""), data.get("message_id"), data.get("callback_id", "")
    return "", None, ""
