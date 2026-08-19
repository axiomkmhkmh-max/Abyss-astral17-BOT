"""
ارسال پیام حاوی ایموجی‌های پرمیوم (سفارشی) با ربات پایتون
پیش‌نیاز: pip install python-telegram-bot --upgrade

⚠️ توکن قبلی که این‌جا هاردکد شده بود از فایل حذف شد چون توکن یک
کلید امنیتی محرمانه‌ست — هرکسی که این فایل رو ببینه می‌تونه کنترل
کامل ربات رو بگیره. توکن قبلی رو از BotFather (دستور /revoke یا
/token) رجنریت کن و دیگه هیچ‌وقت توکن رو مستقیم تو کد ننویس؛ همیشه
از متغیر محیطی (env var) بخون — دقیقاً مثل bot.py که با
os.getenv("BOT_TOKEN") این کار رو می‌کنه.

نکته: توی خودِ ربات (bot.py) دیگه لازم نیست از این فایل استفاده
کنی — یک middleware سراسری هست که خودکار همه‌جای ربات رو پرمیوم
می‌کنه (نگاه کن به emoji_formatting.py). این فایل فقط یک اسکریپت
تست/دمو مستقل برای ارسال دستی یک پیام نمونه‌ست.

فقط کافیه CHAT_ID رو پر کنی، و BOT_TOKEN رو به‌صورت متغیر محیطی
ست کنی، مثلاً:
    export BOT_TOKEN="توکن-جدیدت"
    python send_premium_emoji.py
"""

import asyncio
import os

from telegram import Bot, MessageEntity
from telegram.constants import ParseMode

# ---- تنظیمات ----
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "5841629239")

# ID های ایموجی پرمیومی که قبلاً گرفتی
GAME_EMOJI_ID = "5465465194056525619"   # از پک GameEmoji
NEWS_EMOJI_ID = "5210956306952758910"   # از پک NewsEmoji

# fallback هر کدوم رو با ایموجی معمولی متناظرش عوض کن
GAME_EMOJI_FALLBACK = "🎮"
NEWS_EMOJI_FALLBACK = "📰"


async def send_with_html():
    """روش اول: با تگ HTML (ساده‌تر)"""
    bot = Bot(token=BOT_TOKEN)
    text = (
        f'<tg-emoji emoji-id="{GAME_EMOJI_ID}">{GAME_EMOJI_FALLBACK}</tg-emoji> '
        f"یه بازی جدید اضافه شد! "
        f'<tg-emoji emoji-id="{NEWS_EMOJI_ID}">{NEWS_EMOJI_FALLBACK}</tg-emoji>'
    )
    await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.HTML)
    print("✅ پیام با HTML ارسال شد.")


async def send_with_entities():
    """روش دوم: با entities خام (بدون نیاز به parse_mode)"""
    bot = Bot(token=BOT_TOKEN)
    text = f"{GAME_EMOJI_FALLBACK} یه خبر مهم! {NEWS_EMOJI_FALLBACK}"

    entities = [
        MessageEntity(
            type="custom_emoji",
            offset=0,
            length=len(GAME_EMOJI_FALLBACK),
            custom_emoji_id=GAME_EMOJI_ID,
        ),
        MessageEntity(
            type="custom_emoji",
            offset=len(text) - len(NEWS_EMOJI_FALLBACK),
            length=len(NEWS_EMOJI_FALLBACK),
            custom_emoji_id=NEWS_EMOJI_ID,
        ),
    ]

    await bot.send_message(chat_id=CHAT_ID, text=text, entities=entities)
    print("✅ پیام با entities ارسال شد.")


async def main():
    if not BOT_TOKEN:
        print("❌ متغیر محیطی BOT_TOKEN ست نشده. اول export BOT_TOKEN=... رو بزن.")
        return
    await send_with_html()
    # اگه خواستی روش دوم رو هم تست کنی، این خط رو از کامنت دربیار:
    # await send_with_entities()


if __name__ == "__main__":
    asyncio.run(main())
