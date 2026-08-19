# -*- coding: utf-8 -*-
"""
core/

هستهٔ متمرکز Premium Emoji پروژه.

    from Core.premium_emojis import EMOJI
    from Core.emoji_manager import emoji_manager, premiumize

فایل‌ها:
- emoji_cache.json   داده‌ی خام استخراج‌شده از پک‌های تلگرام (منبع حقیقت)
- emoji_loader.py     خواندن/نوشتن کش + استخراج از تلگرام با Telethon
- premium_emojis.py   نگاشت نام‌های معنایی (EMOJI.SWORD) + سازگاری با API قدیمی
- emoji_manager.py    لایه‌ی runtime: premiumize(text)، render(name)، گزارش‌ها
"""

from .premium_emojis import EMOJI  # noqa: F401
from .emoji_manager import emoji_manager, premiumize  # noqa: F401

__all__ = ["EMOJI", "emoji_manager", "premiumize"]
