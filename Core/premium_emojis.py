# -*- coding: utf-8 -*-
"""
core/premium_emojis.py

⚠️ این فایل قبلاً گم شده بود (وجود نداشت) — دلیل کرش دیپلوی:
    ModuleNotFoundError: No module named 'core'
که در واقع دو تا مشکل تو در تو بود:
  ۱. چهار فایلی که قرار بود داخل پوشه‌ی core/ باشن (__init__.py،
     emoji_cache.json، emoji_loader.py، emoji_manager.py) همه فلت تو
     ریشه‌ی ریپو بودن — الان منتقل شدن به core/.
  ۲. خودِ این فایل (core/premium_emojis.py) — لایه‌ی نام‌گذاری معنایی
     EMOJI.SWORD و توابع سازگاری قدیمی (get_emoji_id، as_html و...) —
     اصلاً تو ریپو وجود نداشت، نه فلت نه تو core/.

این نسخه از داده‌ی خام core/emoji_cache.json (که واقعی و کامله —
۵۴۸ ایموجی یکتا، ۷۴۵ آی‌دی) ساخته شده. چیزی که بازسازی *نشده*:
نگاشت نام‌های معنایی مثل EMOJI.SWORD/EMOJI.GOLD — چون هیچ‌جای این
ریپو (بررسی شد) واقعاً از این نام‌ها استفاده نمی‌کنه؛ تنها مصرف‌کننده‌ی
EMOJI، متدهای خودِ emoji_manager.py بودن (render/by_category/
report_missing) که خودشون هم جایی صدا زده نمی‌شن. کلاسِ EMOJI پایین
یه پیاده‌سازیِ سبک و واقعی‌ست (نه دیتای ساختگی) که با کلید = خودِ
کاراکترِ ایموجی کار می‌کنه، تا اگه بعداً خواستی نام‌گذاری معنایی واقعی
اضافه کنی، ساختار آماده باشه.

چیزی که کاملاً واقعی و زنده‌ست: GAME_EMOJI / NEWS_EMOJI (و بقیه‌ی
API زیر) — این‌ها مستقیم از emoji_cache.json می‌آن، یعنی premiumize()
دقیقاً با همون ۵۴۸ آی‌دی واقعی که قبلاً از تلگرام استخراج شده بود کار
می‌کنه. هیچ آی‌دی جعلی/ساختگی این‌جا نیست.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

_CACHE_PATH = Path(__file__).parent / "emoji_cache.json"


def _load_raw() -> dict:
    if not _CACHE_PATH.exists():
        return {"_meta": {}, "emojis": {}}
    with open(_CACHE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


_RAW = _load_raw()
_EMOJIS: Dict[str, List[dict]] = _RAW.get("emojis", {})

# پک "GameEmoji" -> GAME_EMOJI، پک "RestrictedEmoji" -> NEWS_EMOJI.
# اگه یک کاراکتر تو هر دو پک بود، هر دو دیکشنری آی‌دیِ خودشون رو
# می‌گیرن (emoji_manager.py موقع merge، GAME رو برنده می‌کنه).
GAME_EMOJI: Dict[str, str] = {}
NEWS_EMOJI: Dict[str, str] = {}

for _char, _entries in _EMOJIS.items():
    for _entry in _entries:
        _pack = _entry.get("pack", "")
        _eid = _entry.get("id", "")
        if not _eid:
            continue
        if _pack == "GameEmoji" and _char not in GAME_EMOJI:
            GAME_EMOJI[_char] = _eid
        elif _pack == "RestrictedEmoji" and _char not in NEWS_EMOJI:
            NEWS_EMOJI[_char] = _eid
        else:
            # پک ناشناخته یا بدون‌نام: هر دو رو پر کن که چیزی از دست نره.
            GAME_EMOJI.setdefault(_char, _eid)
            NEWS_EMOJI.setdefault(_char, _eid)

GAME_EMOJI_ALL: List[Tuple[str, str]] = sorted(GAME_EMOJI.items())
NEWS_EMOJI_ALL: List[Tuple[str, str]] = sorted(NEWS_EMOJI.items())

_ALL_MERGED: Dict[str, str] = {**NEWS_EMOJI, **GAME_EMOJI}


def get_emoji_id(char: str) -> str | None:
    """آی‌دی custom_emoji متناظر یک کاراکتر ایموجی (یا None اگه نبود)."""
    return _ALL_MERGED.get(char)


def get_all_ids() -> List[str]:
    """لیست یکتای همه‌ی custom_emoji_id های موجود تو کش."""
    return sorted({eid for eid in _ALL_MERGED.values()})


def as_html(char: str) -> str:
    """
    یک کاراکتر رو به تگ <tg-emoji> تبدیل می‌کنه. اگه آی‌دی نداشت،
    خودِ کاراکتر خام برگردونده می‌شه (بدون کرش).
    """
    eid = get_emoji_id(char)
    if not eid:
        return char
    return f'<tg-emoji emoji-id="{eid}">{char}</tg-emoji>'


class _EmojiRegistry:
    """
    پیاده‌سازیِ سبکِ EMOJI. چون هیچ نگاشتِ نامِ معناییِ واقعی
    (SWORD/GOLD/...) تو ریپو پیدا نشد، اینجا کلید = خودِ کاراکترِ
    ایموجی‌ست. یعنی EMOJI["⚔️"] کار می‌کنه؛ EMOJI["SWORD"] فعلاً نه —
    اگه بعداً نگاشتِ نام واقعی رو داشتی/خواستی، همینجا اضافه کن.
    """

    def __getitem__(self, key: str) -> str:
        if key in _ALL_MERGED:
            return key
        raise KeyError(
            f"'{key}' تو core/emoji_cache.json نیست و نگاشتِ نامِ معنایی "
            "(EMOJI.SWORD-style) هنوز بازسازی نشده."
        )

    def by_category(self, category: str) -> List[str]:
        if category in ("game", "GameEmoji"):
            return list(GAME_EMOJI.keys())
        if category in ("news", "restricted", "RestrictedEmoji"):
            return list(NEWS_EMOJI.keys())
        return []

    def categories(self) -> List[str]:
        return ["game", "news"]

    def missing_ids(self) -> Iterable:
        # همه‌ی چیزی که تو کش هست آی‌دی داره؛ چیزی برای گزارش نیست.
        return []


EMOJI = _EmojiRegistry()

__all__ = [
    "EMOJI",
    "GAME_EMOJI",
    "NEWS_EMOJI",
    "GAME_EMOJI_ALL",
    "NEWS_EMOJI_ALL",
    "get_emoji_id",
    "get_all_ids",
    "as_html",
]
