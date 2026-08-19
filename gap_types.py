# ============================================================
#  ASTRAL ABYSS — Gap Type Shims
# ------------------------------------------------------------
#  هدف این فایل: شبیه‌سازیِ سطحِ رابطِ کلاس‌های پرکاربردِ aiogram
#  (Message, CallbackQuery, InlineKeyboardMarkup/Button,
#  ReplyKeyboardMarkup/Button) تا وقتی handlerهای موجودِ تلگرام
#  رو برای گپ پورت می‌کنیم، فقط خطِ import عوض بشه، نه بدنه‌ی
#  تابع. یعنی جای:
#     from aiogram.types import Message, InlineKeyboardMarkup, ...
#  می‌نویسیم:
#     from gap_types import Message, InlineKeyboardMarkup, ...
#  و بدنه‌ی هندلر (message.answer(...), callback.message.edit_text(...),
#  builder.add(InlineKeyboardButton(text=..., callback_data=...)))
#  دست‌نخورده می‌مونه.
#
#  نکته‌ی مهمِ شناسه‌ها: چون get_player/save_player تو database.py
#  انتظار uid عددی (int) دارن و شناسه‌های عددیِ تلگرام همیشه مثبت‌ن،
#  برای این‌که پلیرهای گپ با پلیرهای تلگرام تصادم نکنن، uid داخلیِ
#  هر کاربرِ گپ رو منفی می‌کنیم:
#     internal_uid = -abs(gap_chat_id)
#  این یعنی یک نفر که هم تو تلگرام هم تو گپ بازی می‌کنه، دو کاراکترِ
#  جداگانه داره (فعلاً tied کردنِ اکانت‌ها scope این فاز نیست).
# ============================================================
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


def gap_uid(chat_id: int) -> int:
    """تبدیل chat_id گپ به uid داخلیِ غیرقابل‌تصادم با تلگرام."""
    return -abs(int(chat_id))


# ─── کیبورد شیشه‌ای (Inline) ────────────────────────────────
@dataclass
class InlineKeyboardButton:
    text: str
    callback_data: Optional[str] = None
    url: Optional[str] = None
    open_in: Optional[str] = None
    amount: Optional[int] = None
    currency: Optional[str] = None
    ref_id: Optional[str] = None
    desc: Optional[str] = None

    def to_gap(self) -> dict:
        d: dict[str, Any] = {"text": self.text}
        if self.callback_data is not None:
            d["cb_data"] = self.callback_data
        if self.url is not None:
            d["url"] = self.url
            d["open_in"] = self.open_in or "webview_with_header"
        if self.amount is not None:
            d["amount"] = self.amount
            d["currency"] = self.currency or "IRR"
            d["ref_id"] = self.ref_id or ""
            d["desc"] = self.desc or self.text
        return d


@dataclass
class InlineKeyboardMarkup:
    inline_keyboard: list[list[InlineKeyboardButton]] = field(default_factory=list)

    def to_gap(self) -> list:
        return [[btn.to_gap() for btn in row] for row in self.inline_keyboard]


class InlineKeyboardBuilder:
    """معادل ساده‌ی aiogram.utils.keyboard.InlineKeyboardBuilder"""

    def __init__(self):
        self._rows: list[list[InlineKeyboardButton]] = [[]]

    def button(self, **kwargs) -> "InlineKeyboardBuilder":
        self._rows[-1].append(InlineKeyboardButton(**kwargs))
        return self

    def add(self, btn: InlineKeyboardButton) -> "InlineKeyboardBuilder":
        self._rows[-1].append(btn)
        return self

    def row(self, *btns: InlineKeyboardButton) -> "InlineKeyboardBuilder":
        self._rows.append(list(btns))
        return self

    def adjust(self, *sizes: int) -> "InlineKeyboardBuilder":
        flat = [b for row in self._rows for b in row]
        out, i = [], 0
        sizes = sizes or (len(flat),)
        for n in sizes:
            out.append(flat[i:i + n])
            i += n
        if i < len(flat):
            out.append(flat[i:])
        self._rows = [r for r in out if r]
        return self

    def as_markup(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[r for r in self._rows if r])


# ─── کیبورد پاسخ (Reply) ────────────────────────────────────
@dataclass
class KeyboardButton:
    text: str
    request_contact: bool = False
    request_location: bool = False


@dataclass
class ReplyKeyboardMarkup:
    keyboard: list[list[KeyboardButton]] = field(default_factory=list)
    resize_keyboard: bool = True
    one_time_keyboard: bool = False

    def to_gap(self) -> dict:
        rows = []
        for row in self.keyboard:
            gap_row = []
            for btn in row:
                if btn.request_contact:
                    gap_row.append({"$contact": btn.text})
                elif btn.request_location:
                    gap_row.append({"$location": btn.text})
                else:
                    gap_row.append({btn.text: btn.text})
            rows.append(gap_row)
        return {"keyboard": rows}


class ReplyKeyboardRemove:
    def to_gap(self):
        return {"keyboard": []}


# ─── کاربر / پیام / کالبک ───────────────────────────────────
@dataclass
class GapUser:
    id: int          # uid داخلی (منفی) — همون چیزی که get_player می‌خواد
    chat_id: int      # chat_id واقعیِ گپ (مثبت) — برای ارسال پیام لازمه
    first_name: str = ""
    username: Optional[str] = None
    is_bot: bool = False

    @property
    def full_name(self) -> str:
        return self.first_name or (self.username or str(self.chat_id))


class Message:
    """شبیه‌ساز aiogram.types.Message برای پیام‌های واردشده از گپ."""

    def __init__(self, bot: "GapBotAdapter", chat_id: int, message_id: Optional[int],
                 text: str, from_user: GapUser, raw: Optional[dict] = None):
        self.bot = bot
        self.chat = _Chat(chat_id)
        self.message_id = message_id
        self.text = text
        self.caption = text
        self.from_user = from_user
        self.raw = raw or {}

    async def answer(self, text: str, reply_markup=None, parse_mode=None, **kw) -> "Message":
        kb, rk = _split_markup(reply_markup)
        mid = await self.bot.client.send_message(
            self.chat.id, text, inline_keyboard=kb, reply_keyboard=rk,
        )
        return Message(self.bot, self.chat.id, mid, text, self.from_user)

    async def edit_text(self, text: str, reply_markup=None, **kw) -> "Message":
        kb, _ = _split_markup(reply_markup)
        await self.bot.client.edit_message(self.chat.id, self.message_id, text, inline_keyboard=kb)
        self.text = text
        return self

    async def delete(self):
        await self.bot.client.delete_message(self.chat.id, self.message_id)

    async def answer_photo(self, photo_path: str, caption: str = "", reply_markup=None, **kw):
        kb, _ = _split_markup(reply_markup)
        uploaded = await self.bot.client.upload_file(self.chat.id, "image", photo_path, desc=caption)
        mid = await self.bot.client.send_media(self.chat.id, "image", uploaded, inline_keyboard=kb)
        return Message(self.bot, self.chat.id, mid, caption, self.from_user)


@dataclass
class _Chat:
    id: int


class CallbackQuery:
    """شبیه‌ساز aiogram.types.CallbackQuery برای triggerButton گپ."""

    def __init__(self, bot: "GapBotAdapter", callback_id: str, chat_id: int,
                 message_id: Optional[int], data: str, from_user: GapUser):
        self.bot = bot
        self.id = callback_id
        self.data = data
        self.from_user = from_user
        self.message = Message(bot, chat_id, message_id, "", from_user)

    async def answer(self, text: str = "", show_alert: bool = False):
        if text:
            await self.bot.client.answer_callback(
                self.message.chat.id, self.id, text, show_alert=show_alert,
            )


def _split_markup(reply_markup):
    """ورودی می‌تونه InlineKeyboardMarkup یا ReplyKeyboardMarkup/Remove باشه."""
    if reply_markup is None:
        return None, None
    if isinstance(reply_markup, InlineKeyboardMarkup):
        return reply_markup.to_gap(), None
    if isinstance(reply_markup, (ReplyKeyboardMarkup, ReplyKeyboardRemove)):
        return None, reply_markup.to_gap()
    return None, None


class GapBotAdapter:
    """
    نقشِ این کلاس معادلِ شیءِ `bot` تو aiogram‌ه: بعضی هندلرهای قدیمی
    مستقیم bot.send_message(...) صدا می‌زنن؛ این متدها رو هم پوشش می‌دیم.
    """

    def __init__(self, client):
        self.client = client

    async def send_message(self, chat_id: int, text: str, reply_markup=None, **kw):
        kb, rk = _split_markup(reply_markup)
        return await self.client.send_message(chat_id, text, inline_keyboard=kb, reply_keyboard=rk)

    async def edit_message_text(self, text: str, chat_id: int, message_id: int, reply_markup=None, **kw):
        kb, _ = _split_markup(reply_markup)
        await self.client.edit_message(chat_id, message_id, text, inline_keyboard=kb)

    async def delete_message(self, chat_id: int, message_id: int):
        await self.client.delete_message(chat_id, message_id)

    async def send_photo(self, chat_id: int, photo, caption: str = "", reply_markup=None, **kw):
        kb, _ = _split_markup(reply_markup)
        path = photo if isinstance(photo, str) else getattr(photo, "path", None)
        uploaded = await self.client.upload_file(chat_id, "image", path, desc=caption)
        return await self.client.send_media(chat_id, "image", uploaded, inline_keyboard=kb)


# ─── ابزار مشترک: فیلترکردنِ فقط-بازیکن‌های-گپ ─────────────────
# دیتابیس بینِ تلگرام و گپ مشترکه؛ uid داخلیِ گپ همیشه منفیه (تلگرام
# مثبته)، پس هر سیستمی که با all_players() کارِ لیست/جستجو می‌کنه
# (دعوتِ تیم، لابیِ آرنا، مرورِ گیلدها، ...) باید از این فیلتر استفاده
# کنه، وگرنه یه بازیکنِ تلگرامی هم تو نتایجِ گپ ظاهر می‌شه.
def gap_only_players(all_docs: dict) -> dict:
    return {pid: p for pid, p in all_docs.items() if str(pid).lstrip("-").isdigit() and int(pid) < 0}
