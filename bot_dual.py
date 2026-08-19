# ============================================================
#  ASTRAL ABYSS — Dual Platform Entrypoint (Telegram + Gap)
# ------------------------------------------------------------
#  این فایل جایگزینِ نقطه‌ی ورودِ Railway می‌شه (Procfile → web).
#  دو تا کار رو هم‌زمان تو یه process انجام می‌ده:
#    1) ربات تلگرام (aiogram) دقیقاً مثل قبل، با long polling
#       — از خودِ bot.py با import (هیچ منطقِ تلگرام کپی نشده)
#    2) وب‌سرور گپ (aiohttp) که روی $PORT گوش می‌ده، چون Railway
#       فقط به process از نوع web پورتِ عمومی می‌ده
#
#  متغیرهای محیطی موردنیاز (علاوه بر همونایی که قبلاً داشتی):
#     BOT_TOKEN_GAP        → توکنِ ربات گپ (از my.gap.im)
#     GAP_WEBHOOK_SECRET   → یه رشته‌ی رندومِ دلخواه (امنیتِ مسیر webhook)
#     GAP_ADMIN_IDS        → chat_id عددیِ ادمین‌های گپ، با کاما جدا
#     PORT                 → Railway خودش ست می‌کنه؛ نیازی به دستکاری نیست
#
#  آدرسِ callback که باید تو پنلِ my.gap.im وارد کنی:
#     https://<your-app>.up.railway.app/gap/webhook/<GAP_WEBHOOK_SECRET>
# ============================================================
import asyncio
import logging
import os
import sys

from gap_client import GapClient
from gap_types import GapBotAdapter, gap_only_players
from gap_dispatcher import GapDispatcher
from database import all_players
from logger import log_sync
from gap_webhook import run_gap_webhook
from gap_core_handlers import register_gap_core_handlers
from gap_admin_panel import register_gap_admin_handlers
from gap_combat_handlers import register_gap_combat_handlers
from gap_class_ability_handlers import register_gap_class_ability_handlers
from gap_hunt_handlers import register_gap_hunt_handlers
from gap_shop_handlers import register_gap_shop_handlers
from gap_bank_handlers import register_gap_bank_handlers
from gap_casino_handlers import register_gap_casino_handlers
from gap_loot_handlers import register_gap_loot_handlers
from gap_team_handlers import register_gap_team_handlers
from gap_guild_handlers import register_gap_guild_handlers
from gap_trade_handlers import register_gap_trade_handlers
from gap_pvp_handlers import register_gap_pvp_handlers
from gap_zen_shop import register_gap_zen_shop_handlers
from gap_workshop_handlers import register_gap_workshop_handlers
from gap_skill_handlers import register_gap_skill_handlers

# همون فیکسِ bot.py: INFO می‌ره stdout، فقط WARNING به بالا می‌ره stderr
# — تا Railway لاگ‌های سالم رو اشتباهی error نشون نده.
_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setLevel(logging.DEBUG)
_stdout_handler.addFilter(lambda record: record.levelno < logging.WARNING)

_stderr_handler = logging.StreamHandler(sys.stderr)
_stderr_handler.setLevel(logging.WARNING)

logging.basicConfig(level=logging.INFO, handlers=[_stdout_handler, _stderr_handler])
log = logging.getLogger("bot_dual")


async def notify_gap_players_restart(bot_adapter: GapBotAdapter):
    """معادلِ notify_players_restart تو bot.py، برای بازیکن‌های گپ (uid منفی):
    بعد از هر بالا اومدنِ سمتِ گپ، بهشون می‌گه یه بار /start بزنن."""
    text = "🔄 **ربات ری‌استارت شد!**\nلطفاً یه بار /start رو بزن تا همه‌چی درست آپدیت بشه."
    players = gap_only_players(all_players())
    sent = failed = 0
    for pid in players:
        chat_id = -int(pid)  # برگردوندنِ uid منفی به chat_id واقعیِ گپ
        try:
            await bot_adapter.send_message(chat_id, text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # rate-limit ملایم
    log_sync(f"🔄 **RESTART NOTICE (GAP)** ارسال شد به {sent} بازیکن ({failed} ناموفق).", "START")


async def run_gap_side():
    token = os.getenv("BOT_TOKEN_GAP", "")
    if not token:
        log.warning("BOT_TOKEN_GAP ست نشده — سمتِ گپ غیرفعاله.")
        return
    client = await GapClient(token).start()
    bot_adapter = GapBotAdapter(client)
    dp = GapDispatcher(bot_adapter)

    register_gap_core_handlers(dp)
    register_gap_admin_handlers(dp)
    register_gap_combat_handlers(dp)
    register_gap_class_ability_handlers(dp)  # 🩹 باگ‌فیکس: قدرت‌های کلاس (طوفانِ ناحیه‌ای و بقیه) رو گپ اصلاً پورت نشده بودن
    register_gap_hunt_handlers(dp)
    register_gap_shop_handlers(dp)
    register_gap_bank_handlers(dp)
    register_gap_casino_handlers(dp)
    register_gap_loot_handlers(dp)
    register_gap_team_handlers(dp)
    register_gap_guild_handlers(dp)
    register_gap_trade_handlers(dp)
    register_gap_pvp_handlers(dp)
    register_gap_zen_shop_handlers(dp)
    register_gap_workshop_handlers(dp)  # 🔄 صرافیِ متریال | 🗺️ دستورهای نقشه | 📯 کدکسِ کالکشن
    register_gap_skill_handlers(dp)  # 🩹 باگ‌فیکس: /skills و خرجِ امتیازِ مهارت روی گپ اصلاً پورت نشده بود
    # ─── بقیه‌ی هندلرها (auction, boss, katana, quest, ...) رو همینجا
    # به همین شکل اضافه کن، هر کدوم تو فایلِ gap_<system>_handlers.py
    # خودشون register_gap_xxx_handlers(dp) رو expose می‌کنن.

    asyncio.create_task(notify_gap_players_restart(bot_adapter))

    port = int(os.getenv("PORT", "8080"))
    runner = await run_gap_webhook(dp, port)
    try:
        await asyncio.Event().wait()  # تا ابد زنده بمون
    finally:
        await runner.cleanup()
        await client.close()


async def run_telegram_side():
    import bot as telegram_bot  # bot.py موجودِ پروژه، بدون تغییر
    await telegram_bot.main()


async def main():
    tasks = []
    if os.getenv("BOT_TOKEN", ""):
        tasks.append(asyncio.create_task(run_telegram_side()))
    else:
        log.warning("BOT_TOKEN ست نشده — سمتِ تلگرام غیرفعاله.")
    tasks.append(asyncio.create_task(run_gap_side()))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
