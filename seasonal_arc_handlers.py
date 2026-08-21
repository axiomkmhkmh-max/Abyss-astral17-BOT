# ============================================================
#  ASTRAL ABYSS RPG — Handlers آرکِ فصلی 📜
# ============================================================
from aiogram.filters import Command
from aiogram.types import Message

from database import get_player, aget_player
import seasonal_arc as sa


async def cmd_season(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    await msg.answer(sa.status_text())


def register_seasonal_arc_handlers(dp, bot):
    dp.message.register(cmd_season, Command("season"))
