# ============================================================
#  ASTRAL ABYSS RPG — Loop Shard Handlers (Telegram UI) 🔁
# ============================================================
from aiogram.filters import Command
from aiogram.types import Message

from database import get_player
import loop_system as ls


async def cmd_loop(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    await msg.answer(ls.status_text(player))


def register_loop_handlers(dp, bot):
    dp.message.register(cmd_loop, Command("loop"))
