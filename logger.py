# ============================================================
#  ASTRAL ABYSS — Logger
# ============================================================
import asyncio
from datetime import datetime, timezone, timedelta
from aiogram import Bot

LOG_CHAT_ID = -1003940160534

_bot: Bot = None

# تنظیم منطقه زمانی تهران
TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))

def _tehran_time():
    """زمان فعلی تهران رو برمی‌گردونه"""
    return datetime.now(timezone.utc).astimezone(TEHRAN_TZ)

def set_bot(bot: Bot):
    global _bot
    _bot = bot

async def send_log(text: str, level: str = "INFO"):
    if _bot is None:
        return
    now = _tehran_time().strftime("%Y-%m-%d %H:%M:%S")
    emoji = {
        "INFO": "ℹ️", "WARN": "⚠️", "ERROR": "❌", "ADMIN": "🛠️",
        "PLAYER": "👤", "LEVELUP": "⭐", "COMBAT": "⚔️", "ECONOMY": "💰",
        "BOSS": "👹", "PVP": "🆚", "LOOT": "🎒", "BAN": "🚫",
        "START": "🟢", "STOP": "🔴", "GUILD": "🏛", "SKILL": "🌟",
        "KATANA": "🗡️", "CRAFT": "🔨", "DEATH": "💀", "TRADE": "💱",
        "BOSS_PHASE": "🌀", "BOSS_DEATH": "💀", "BOSS_REWARD": "🎁"
    }.get(level, "📝")
    try:
        await _bot.send_message(
            LOG_CHAT_ID,
            f"{emoji} `[{now}]`\n{text}",
            disable_web_page_preview=True
        )
    except Exception:
        pass

def log_sync(text: str, level: str = "INFO"):
    if _bot is None:
        return
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(send_log(text, level))
        else:
            loop.run_until_complete(send_log(text, level))
    except Exception:
        pass


async def notify_user(telegram_id: int, text: str):
    """پیامِ مستقیم به یه بازیکن می‌فرسته (مثلاً وقتی تو حراجی از پیشنهادش جلو زده می‌شن).
    اگه بازیکن ربات رو بلاک کرده باشه یا هر خطای دیگه‌ای پیش بیاد، بی‌سروصدا نادیده گرفته می‌شه."""
    if _bot is None:
        return
    try:
        await _bot.send_message(telegram_id, text)
    except Exception:
        pass


def notify_user_sync(telegram_id: int, text: str):
    if _bot is None:
        return
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(notify_user(telegram_id, text))
        else:
            loop.run_until_complete(notify_user(telegram_id, text))
    except Exception:
        pass
