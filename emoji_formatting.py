# -*- coding: utf-8 -*-
"""
emoji_formatting.py

⚠️ محتوای این فایل منتقل شد به core/emoji_manager.py — این‌جا فقط
یک shim نازک (thin re-export) باقی مانده تا:

  from emoji_formatting import premiumize

که در bot.py و هرجای دیگری از پروژه استفاده می‌شود، بدون هیچ تغییری
کار کند. منطق واقعی (VS16 aliasing، تبدیل Markdown→HTML، جایگزینی
ایموجی) اکنون در core/emoji_manager.py متمرکز است — رفتار خروجی
بایت‌به‌بایت با نسخه‌ی قبلی این فایل یکسان است (تست شد).

اگر می‌خواهی مستقیم به هستهٔ جدید دسترسی داشته باشی:
    from Core.emoji_manager import emoji_manager, premiumize
    from Core.premium_emojis import EMOJI
"""

from Core.emoji_manager import premiumize, emoji_manager, EMOJI_MAP  # noqa: F401

__all__ = ["premiumize", "emoji_manager", "EMOJI_MAP"]
