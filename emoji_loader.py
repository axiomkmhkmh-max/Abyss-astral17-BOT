# -*- coding: utf-8 -*-
"""
core/emoji_loader.py

مسئولیت این فایل فقط یک چیز است: ارتباط با core/emoji_cache.json
(خواندن، نوشتن، و پر کردنش با استخراج از پک‌های Premium Emoji تلگرام
از طریق Telethon/MTProto).

منطق نام‌گذاری (EMOJI.SWORD و ...) این‌جا نیست — آن در
core/premium_emojis.py است. این جدا‌سازی عمداً است: premium_emojis.py
فقط باید بدونه "اسم X یعنی ایموجی Y با فلان دسته"، و اصلاً لازم نیست
بدونه آی‌دی‌ها از کجا اومدن یا چطور به‌روز می‌شن.

---------------------------------------------------------------------
نحوه‌ی استخراج آی‌دی‌های جدید از یک پک Premium Emoji
---------------------------------------------------------------------

    export TELEGRAM_API_ID="..."
    export TELEGRAM_API_HASH="..."
    python -m core.emoji_loader --pack GameEmoji
    python -m core.emoji_loader --pack RestrictedEmoji
    python -m core.emoji_loader --pack SomeNewPackName   # هر پک جدیدی در آینده

هر بار اجرا: پک را با Telethon resolve می‌کند (GetStickerSet)، تمام
custom_emoji_id های داخلش را می‌گیرد، با دیتای فعلی emoji_cache.json
merge (dedup) می‌کند و فایل را بازنویسی می‌کند. چیزی هرگز حذف
نمی‌شود — فقط اضافه.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

_CACHE_PATH = Path(__file__).parent / "emoji_cache.json"

# پک‌هایی که پروژه با آن‌ها کار می‌کند. برای افزودن پک جدید در آینده،
# فقط اسمش را این‌جا اضافه کن — نیازی به تغییر جای دیگری نیست.
KNOWN_PACKS: Dict[str, str] = {
    "GameEmoji": "https://t.me/addemoji/GameEmoji",
    "RestrictedEmoji": "https://t.me/addemoji/RestrictedEmoji",
}


def load_cache() -> dict:
    """کش را از دیسک می‌خواند. اگر فایل نبود، ساختار خالی سالم برمی‌گرداند."""
    if not _CACHE_PATH.exists():
        return {"_meta": {}, "emojis": {}}
    with open(_CACHE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cache(cache: dict) -> None:
    with open(_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def merge_entries(cache: dict, pack_name: str, extracted: List[Dict[str, str]]) -> int:
    """
    extracted: [{"emoji": "⚔️", "id": "123..."}, ...]
    آی‌دی‌های تکراری نادیده گرفته می‌شوند (dedup). برمی‌گرداند: تعداد
    ورودی‌های *جدید* اضافه‌شده.
    """
    emojis = cache.setdefault("emojis", {})
    added = 0
    for item in extracted:
        char, emoji_id = item["emoji"], item["id"]
        existing = emojis.setdefault(char, [])
        if not any(e["id"] == emoji_id for e in existing):
            existing.append({"id": emoji_id, "pack": pack_name})
            added += 1
    meta = cache.setdefault("_meta", {})
    meta["unique_emoji"] = len(emojis)
    meta["total_ids"] = sum(len(v) for v in emojis.values())
    packs = set(meta.get("source_packs", []))
    packs.add(KNOWN_PACKS.get(pack_name, pack_name))
    meta["source_packs"] = sorted(packs)
    return added


async def extract_pack_via_telethon(pack_short_name: str) -> List[Dict[str, str]]:
    """
    یک پک Premium Emoji را از تلگرام می‌خواند و لیست
    [{"emoji": ..., "id": ...}, ...] برمی‌گرداند.

    نیازمند این متغیرهای محیطی است:
        TELEGRAM_API_ID، TELEGRAM_API_HASH
    و یک session قبلاً لاگین‌شده (چون گرفتن استیکرست از GetStickerSet
    نیاز به MTProto دارد، نه Bot API).
    """
    from telethon import TelegramClient
    from telethon.tl.functions.messages import GetStickerSetRequest
    from telethon.tl.types import InputStickerSetShortName

    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    if not api_id or not api_hash:
        raise RuntimeError(
            "TELEGRAM_API_ID و TELEGRAM_API_HASH ست نشده‌اند. این‌ها را از "
            "https://my.telegram.org گرفته و export کن."
        )

    session_name = os.getenv("TELEGRAM_SESSION_NAME", "core/.emoji_loader_session")
    async with TelegramClient(session_name, int(api_id), api_hash) as client:
        result = await client(
            GetStickerSetRequest(
                stickerset=InputStickerSetShortName(short_name=pack_short_name),
                hash=0,
            )
        )
        out: List[Dict[str, str]] = []
        for doc, pack in zip(result.documents, result.packs):
            for char in pack.emoticon:
                out.append({"emoji": char, "id": str(doc.id)})
        return out


async def sync_pack(pack_name: str) -> int:
    """پک را استخراج و با کش merge می‌کند. برمی‌گرداند: تعداد ورودی جدید."""
    cache = load_cache()
    extracted = await extract_pack_via_telethon(pack_name)
    added = merge_entries(cache, pack_name, extracted)
    save_cache(cache)
    return added


def _cli() -> None:
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Sync a Premium Emoji pack into core/emoji_cache.json")
    parser.add_argument("--pack", required=True, help="نام کوتاه پک (مثلاً GameEmoji) یا لینک t.me/addemoji/...")
    args = parser.parse_args()

    pack_name = args.pack.rstrip("/").split("/")[-1]
    added = asyncio.run(sync_pack(pack_name))
    print(f"✅ پک '{pack_name}' سینک شد — {added} custom_emoji_id جدید اضافه شد.")
    print(f"   کل ایموجی‌های یکتا در کش: {load_cache()['_meta'].get('unique_emoji')}")


if __name__ == "__main__":
    _cli()
