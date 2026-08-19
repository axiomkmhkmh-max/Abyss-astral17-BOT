# ============================================================
#  ASTRAL ABYSS — Progression Handlers
#  (Combat Power + World Tier + Ascension Trials)
# ------------------------------------------------------------
#  همون الگوی فایل‌های دیگه (combat_handlers.py, team_handlers.py):
#  یه register_progression_handlers(dp, bot) که تو main() صدا زده می‌شه.
#
#  دستورات جدید:
#    /power     یا دکمه‌ی «⚔️ Combat Power»  → نمایش CP و منابع قدرت
#    /worldtier یا دکمه‌ی «🌍 تیر جهان»       → وضعیت تیرهای دنیا
#    /ascend                                  → تلاش برای رد کردن Trial بعدی
# ============================================================
import random
import time

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
from combat_power import calculate_combat_power, format_cp_card, recommended_cp_for_tier
from world_tiers import (
    format_tier_status, next_trial_for_player, can_attempt_trial,
    resolve_trial_attempt, ASCENSION_TRIALS, get_current_world_tier, WORLD_TIERS,
)

# ─── /power ──────────────────────────────────────────────────
async def cmd_power(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    await msg.answer(format_cp_card(player))

# ─── /worldtier ──────────────────────────────────────────────
async def cmd_worldtier(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return

    text = format_tier_status(player)
    nxt = next_trial_for_player(player)
    buttons = []
    if nxt:
        buttons.append([InlineKeyboardButton(
            text=f"⚡ تلاش برای {ASCENSION_TRIALS[nxt]['name']}",
            callback_data=f"ascend_try:{nxt}"
        , style=ButtonStyle.PRIMARY)])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    await msg.answer(text, reply_markup=kb)

# ─── /ascend ─────────────────────────────────────────────────
async def cmd_ascend(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return

    trial_id = next_trial_for_player(player)
    if not trial_id:
        level = player.get("level", 1)
        current_tier = get_current_world_tier(player)
        if current_tier >= 6:
            await msg.answer("👑 تو همه‌ی آزمون‌های Ascension رو رد کردی! بالاترین تیر دنیا در اختیار توئه.")
        else:
            needed = min(t["min_level"] for tid, t in ASCENSION_TRIALS.items())
            await msg.answer(f"⏳ هنوز لولت برای هیچ Trial جدیدی کافی نیست. (Lv.{level})")
        return

    await _offer_trial(msg, player, trial_id)

async def _offer_trial(msg_or_cb, player: dict, trial_id: str):
    ok, reason = can_attempt_trial(player, trial_id)
    trial = ASCENSION_TRIALS[trial_id]
    target = msg_or_cb.answer if isinstance(msg_or_cb, Message) else msg_or_cb.message.answer
    if not ok:
        await target(reason)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⚔️ شروع آزمون", callback_data=f"ascend_start:{trial_id}", style=ButtonStyle.SUCCESS),
        InlineKeyboardButton(text="❌ فعلاً نه", callback_data="ascend_cancel", style=ButtonStyle.DANGER),
    ]])
    await target(
        f"⚡ **{trial['name']}**\n\n"
        f"📏 حداقل لول: {trial['min_level']}\n"
        f"⚠️ اگه شکست بخوری: {int(trial['fail_hp_penalty']*100)}٪ از Max HP کم می‌شه "
        f"و {trial['retry_cooldown']//60} دقیقه باید صبر کنی.\n\n"
        f"آماده‌ای؟",
        reply_markup=kb
    )

async def cb_ascend_try(cb: CallbackQuery):
    trial_id = cb.data.split(":")[1]
    player = get_player(cb.from_user.id)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    await cb.answer()
    await _offer_trial(cb, player, trial_id)

async def cb_ascend_cancel(cb: CallbackQuery):
    await cb.answer("لغو شد.")
    try:
        await cb.message.delete()
    except Exception:
        pass

async def cb_ascend_start(cb: CallbackQuery):
    """
    شبیه‌سازی نبردِ Trial:
    شانس موفقیت بر اساس Combat Power نسبت‌به CP توصیه‌شده‌ی این Tier محاسبه می‌شه
    (فاز فعلی — می‌تونه بعداً با یه نبرد چندفازی واقعی جایگزین بشه، دقیقاً مثل World Boss).
    """
    uid = cb.from_user.id
    trial_id = cb.data.split(":")[1]
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    ok, reason = can_attempt_trial(player, trial_id)
    if not ok:
        await cb.answer(reason, show_alert=True)
        return

    # تیر بعدی که این Trial قفلش رو باز می‌کنه
    next_tier_num = min(
        (n for n, t in WORLD_TIERS.items() if t["ascension_required"] == trial_id),
        default=None
    )
    rec_cp = recommended_cp_for_tier(next_tier_num) if next_tier_num else 1000
    player_cp = calculate_combat_power(player)

    # شانس پایه ۴۰٪، هرچی CP بازیکن به CP توصیه‌شده نزدیک‌تر/بیشتر باشه شانس بالاتر می‌ره
    ratio = player_cp / max(1, rec_cp)
    success_chance = max(0.1, min(0.95, 0.4 + (ratio - 0.5) * 0.5))
    success = random.random() < success_chance

    result = resolve_trial_attempt(player, trial_id, success)
    save_player(uid, player)

    trial_name = ASCENSION_TRIALS[trial_id]["name"]
    header = "🎉 **موفق شدی!**" if success else "💀 **شکست خوردی!**"
    await cb.message.edit_text(
        f"{header}\n\n"
        f"⚡ {trial_name}\n"
        f"⚔️ Combat Power تو: {player_cp:,} (پیشنهادی: {rec_cp:,})\n\n"
        f"{result['reward']}"
    )
    await cb.answer()

# ─── Register ────────────────────────────────────────────────
def register_progression_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_power,     Command("power"))
    dp.message.register(cmd_power,     F.text == "⚔️ Combat Power")
    dp.message.register(cmd_worldtier, Command("worldtier"))
    dp.message.register(cmd_worldtier, F.text == "تیر جهان")
    dp.message.register(cmd_ascend,    Command("ascend"))

    dp.callback_query.register(cb_ascend_try,    F.data.startswith("ascend_try:"))
    dp.callback_query.register(cb_ascend_start,  F.data.startswith("ascend_start:"))
    dp.callback_query.register(cb_ascend_cancel, F.data == "ascend_cancel")
