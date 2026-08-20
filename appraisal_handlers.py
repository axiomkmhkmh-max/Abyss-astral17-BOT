# ============================================================
#  ASTRAL ABYSS RPG — Appraisal Handlers (Telegram UI) 🔍
# ============================================================
from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from database import get_player, save_player
import appraisal_system as aps


async def cmd_appraise(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    if not aps.is_unlocked(player):
        await msg.answer(f"🔒 مهارتِ تشخیص هنوز باز نشده — تو سطح {aps.UNLOCK_LEVEL} باز می‌شه.")
        return
    await msg.answer(aps.appraise_all_equipped(player))


async def cb_mob_appraise(cb: CallbackQuery):
    """این هندلر از خودِ mob_combat.py صدا زده می‌شه (نگاه کن به قلاب تو
    _encounter_kb / register_mob_combat_handlers)؛ اینجا فقط برای referenceه
    که اگه بعداً appraisal مستقل از mob_combat هم لازم شد، آماده باشه."""
    await cb.answer()


def register_appraisal_handlers(dp, bot):
    dp.message.register(cmd_appraise, Command("appraise"))
