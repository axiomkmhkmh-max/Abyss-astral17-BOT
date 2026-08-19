# -*- coding: utf-8 -*-
"""
get_emoji_id.py

ابزار کمکی برای گرفتن custom_emoji_id ایموجی‌های پرمیوم.

چرا لازمه؟
premium_emojis.py فقط برای بخشی از ایموجی‌های استفاده‌شده تو ربات
آی‌دی داره (لیست کامل مابقی رو تو missing_emojis.txt ببین). برای
هر کدوم از این ایموجی‌ها که می‌خوای پرمیوم بشه، باید custom_emoji_id
واقعیش رو از تلگرام بگیری — نمی‌شه از خود کد ساختش.

روش استفاده:
1. یه پیام بساز که همون ایموجی معمولی (مثلاً ⭐) رو با کیبورد
   ایموجی‌های *پرمیوم* تلگرام (نه ایموجی معمولی گوشی) وارد کرده باشه
   — یعنی از پک‌های Premium Emoji که تو اپ تلگرام (نسخهٔ رسمی، با
   اشتراک Premium) در دسترسن انتخابش کنی. یا یه پیام حاوی همون
   ایموجی پرمیوم رو از یه کانال/ربات دیگه به این ربات فوروارد کن.
2. این اسکریپت رو اجرا کن:
       export BOT_TOKEN="توکن ربات"
       python get_emoji_id.py
3. همون پیام رو مستقیم به ربات بفرست (یا فوروارد کن).
4. تو ترمینال، برای هر ایموجی سفارشی تو اون پیام یه خط چاپ می‌شه:
       ⭐  ->  custom_emoji_id = 5443...
   این خط آماده‌ست که مستقیم به GAME_EMOJI_ALL یا NEWS_EMOJI_ALL
   تو premium_emojis.py اضافه کنی:
       ("⭐", "5443..."),

نکته: این اسکریپت مستقل از bot.py اصلیه (پولینگ جدا)، پس اجراش
تداخلی با ربات اصلی نداره؛ فقط یادت باشه بعد از تموم شدن کارت
Ctrl+C بزنی و ببندیش.
"""

import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.types import Message

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

dp = Dispatcher()


@dp.message()
async def on_message(message: Message):
    if not message.entities:
        await message.answer(
            "این پیام هیچ ایموجی سفارشی (custom_emoji) نداشت. "
            "یادت باشه باید از کیبورد ایموجی‌های پرمیوم تلگرام انتخابش کنی، "
            "نه فقط تایپ ایموجی معمولی."
        )
        return

    found = False
    lines = []
    for ent in message.entities:
        if ent.type == "custom_emoji":
            found = True
            emoji_char = message.text[ent.offset: ent.offset + ent.length]
            line = f'{emoji_char}  ->  ("{emoji_char}", "{ent.custom_emoji_id}"),'
            print(line)
            lines.append(line)

    if found:
        await message.answer("پیدا شد:\n" + "\n".join(lines))
    else:
        await message.answer("هیچ custom_emoji توی این پیام نبود.")


async def main():
    if not BOT_TOKEN:
        print("❌ متغیر محیطی BOT_TOKEN ست نشده. اول export BOT_TOKEN=... رو بزن.")
        return
    bot = Bot(token=BOT_TOKEN)
    print("در حال گوش دادن... یه پیام حاوی ایموجی پرمیوم به ربات بفرست.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
