# -*- coding: utf-8 -*-
"""
core/emoji_manager.py

لایه‌ی runtime سیستم Premium Emoji. سه کاربرد:

۱. EmojiManager.premiumize(text) / تابع سطح-ماژول premiumize(text) —
   جایگزین دقیق emoji_formatting.premiumize() قدیمی. منطق داخلی‌اش
   (VS16 aliasing، ترتیب تبدیل Markdown→HTML، پرهیز از nested
   <tg-emoji>) عیناً از نسخه‌ی قبلی که در پروژه تست و جواب داده بود
   کپی شده — چیزی در رفتار خروجی تغییر نکرده، فقط منبع داده‌اش
   (GAME_EMOJI/NEWS_EMOJI) حالا از core.premium_emojis می‌آید.

۲. EmojiManager.render(name) — برای کد جدید/بازنویسی‌شده که می‌خواهد
   صریحاً EMOJI.SWORD را داخل متن بگذارد.

۳. EmojiManager.report_missing() — گزارش نام‌های EMOJI.X که هنوز
   custom_emoji_id ندارند (جایگزین معنایی‌تر missing_emojis.txt).
"""

from __future__ import annotations

import html
import re
from typing import Dict, List

from .premium_emojis import EMOJI, GAME_EMOJI, NEWS_EMOJI

# اگه یک ایموجی هم تو GAME و هم تو NEWS بود، نسخهٔ GAME برنده می‌شه
# (چون ربات یک RPG/گیم هست) — همون قاعده‌ی نسخه‌ی قبلی.
_RAW_MAP: Dict[str, str] = {**NEWS_EMOJI, **GAME_EMOJI}

_VS16 = "\ufe0f"  # Variation Selector-16


def _with_vs16_aliases(mapping: Dict[str, str]) -> Dict[str, str]:
    """
    خیلی از هندلرها از نسخهٔ با VS16 (مثلاً 🗡️) استفاده می‌کنن ولی تو
    داده فقط نسخهٔ بدون VS16 (🗡) ثبت شده (یا برعکس). این دو از نظر
    پایتون دو رشتهٔ کاملاً متفاوتن، پس بدون این تابع جایگزینی برای
    یکی از دو نسخه اصلاً اتفاق نمی‌افته. برای هر ایموجی که فقط یک
    نسخه‌ش ثبت شده، نسخهٔ دیگه رو هم (با همون آی‌دی) اضافه می‌کنیم.
    """
    extra: Dict[str, str] = {}
    for emoji, emoji_id in mapping.items():
        if emoji.endswith(_VS16):
            bare = emoji[:-1]
            if bare not in mapping and bare not in extra:
                extra[bare] = emoji_id
        else:
            with_vs = emoji + _VS16
            if with_vs not in mapping and with_vs not in extra:
                extra[with_vs] = emoji_id
    mapping.update(extra)
    return mapping


EMOJI_MAP: Dict[str, str] = _with_vs16_aliases(dict(_RAW_MAP))

# طولانی‌ترین‌ها اول، تا ایموجی‌های چندکاراکتری قبل از زیرمجموعه‌های
# کوتاه‌ترشون match بشن.
_SORTED_EMOJIS = sorted(EMOJI_MAP.keys(), key=len, reverse=True)

# یک regex واحد که همهٔ ایموجی‌های شناخته‌شده رو با هم match می‌کنه —
# با یه re.sub تک‌مرحله‌ای روی متن اصلی، تا جایگزینی یک ایموجی باعث
# nested <tg-emoji> برای زیررشته‌ی خودش نشه.
_EMOJI_PATTERN = (
    re.compile("|".join(re.escape(e) for e in _SORTED_EMOJIS))
    if _SORTED_EMOJIS
    else None
)

# ---------------------------------------------------------------------------
# تبدیل Markdown سبک به HTML — دقیقاً همون الگوهای قدیمی
# ---------------------------------------------------------------------------
_CODE = re.compile(r"`([^`]+?)`")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
_BOLD_DOUBLE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_BOLD_SINGLE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", re.DOTALL)
_ITALIC = re.compile(r"(?<!\w)_(.+?)(?<!\w)_(?!\w)", re.DOTALL)


def _markdown_to_html(text: str) -> str:
    text = html.escape(text, quote=False)
    text = _CODE.sub(lambda m: f"<code>{m.group(1)}</code>", text)
    text = _LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
    text = _BOLD_DOUBLE.sub(lambda m: f"<b>{m.group(1)}</b>", text)
    text = _BOLD_SINGLE.sub(lambda m: f"<b>{m.group(1)}</b>", text)
    text = _ITALIC.sub(lambda m: f"<i>{m.group(1)}</i>", text)
    return text


def _apply_premium_emojis(text: str) -> str:
    if not _EMOJI_PATTERN:
        return text

    def _replace(match: "re.Match[str]") -> str:
        emoji = match.group(0)
        emoji_id = EMOJI_MAP[emoji]
        return f'<tg-emoji emoji-id="{emoji_id}">{emoji}</tg-emoji>'

    return _EMOJI_PATTERN.sub(_replace, text)


class EmojiManager:
    """
    نمونهٔ singleton این کلاس در پایین همین فایل به اسم
    `emoji_manager` ساخته شده — همه‌جای پروژه از همان استفاده کن.
    """

    def render(self, name: str) -> str:
        """EMOJI.SWORD معادل emoji_manager.render('SWORD')."""
        return str(EMOJI[name])

    def by_category(self, category: str) -> List[str]:
        return [str(ref) for ref in EMOJI.by_category(category)]

    def categories(self) -> List[str]:
        return EMOJI.categories()

    def report_missing(self) -> List[str]:
        """نام‌های EMOJI.X که هنوز custom_emoji_id ندارند."""
        return [f"{ref.category}.{ref.name} ({ref.fallback})" for ref in EMOJI.missing_ids()]

    @staticmethod
    def premiumize(text: str, raw_html: bool = False) -> str:
        """
        ورودی: متن ساده یا Markdown سبک.
        خروجی: همون متن به‌صورت HTML، با ایموجی‌های پرمیوم جایگزین‌شده.

        raw_html=True یعنی متن از قبل HTML کامل هست (مثلاً از قبل <b>
        یا <tg-emoji> توش هست) — فقط جایگزینی ایموجی انجام می‌شه،
        escape/تبدیل Markdown انجام نمی‌شه.
        """
        if not text:
            return text
        if raw_html:
            return _apply_premium_emojis(text)
        converted = _markdown_to_html(text)
        return _apply_premium_emojis(converted)


emoji_manager = EmojiManager()


def premiumize(text: str, raw_html: bool = False) -> str:
    """شیم سازگاری: امضای دقیقاً برابر با emoji_formatting.premiumize() قدیمی."""
    return emoji_manager.premiumize(text, raw_html=raw_html)
