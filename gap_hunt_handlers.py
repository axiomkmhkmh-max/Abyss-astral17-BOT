# ============================================================
#  ASTRAL ABYSS — Hunt Questline Handlers (Gap) 🎯
#  معادلِ hunt_handlers.py برای پلتفرمِ Gap Messenger
# ============================================================
from gap_dispatcher import GapDispatcher
from gap_types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from hunt_questline import hunt_progress, claim_hunt_reward


def _hunt_kb(progress: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for q in progress:
        if q["claimable"]:
            buttons.append([InlineKeyboardButton(
                text=f"🎁 کلایم: {q['title']}",
                callback_data=f"hunt_claim:{q['id']}",
            )])
    buttons.append([InlineKeyboardButton(text="⬅️ برگشت به حمله", callback_data="hunt:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _hunt_text(progress: list[dict]) -> str:
    lines = ["📜 **کوئست‌لاینِ حمله — شکارِ هدف‌دار**\n"]
    lines.append("_با کشتنِ تعدادِ مشخصی از یه دشمنِ خاص (هرجا که پیداش کنی)، پاداشِ اختصاصیِ Zen/XP + یه توانایی دائمی باز می‌کنی._\n")
    for q in progress:
        if q["claimed"]:
            mark = "✅"
        elif q["claimable"]:
            mark = "🎁"
        else:
            mark = "🔒"
        lines.append(
            f"{mark} **{q['title']}**\n"
            f"   🎯 {q['enemy']} — {min(q['have'], q['need'])}/{q['need']}\n"
            f"   💰 {q['zen']:,} Zen | ✨ {q['xp']:,} XP\n"
            f"   {q['ability_label']}\n"
        )
    return "\n".join(lines)


async def cb_hunt_panel(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    progress = hunt_progress(player)
    try:
        await cb.message.edit_text(_hunt_text(progress), reply_markup=_hunt_kb(progress))
    except Exception:
        await cb.message.answer(_hunt_text(progress), reply_markup=_hunt_kb(progress))
    await cb.answer()


async def cb_hunt_claim(cb: CallbackQuery):
    uid = cb.from_user.id
    quest_id = cb.data.split(":")[1]
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    reward = claim_hunt_reward(player, quest_id)
    if not reward:
        await cb.answer("❌ هنوز آماده‌ی کلایم نیست!", show_alert=True)
        return
    await asave_player(uid, player)
    await cb.answer(f"🎉 {reward['title']} تکمیل شد! +{reward['zen']:,} Zen | +{reward['xp']:,} XP", show_alert=True)
    progress = hunt_progress(player)
    try:
        await cb.message.edit_text(_hunt_text(progress), reply_markup=_hunt_kb(progress))
    except Exception:
        pass


async def cb_hunt_back(cb: CallbackQuery):
    from gap_combat_handlers import _render_attack_panel
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    text, kb = _render_attack_panel(uid, player)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


def register_gap_hunt_handlers(dp: GapDispatcher):
    dp.register_callback(cb_hunt_panel, data="hunt:panel")
    dp.register_callback(cb_hunt_claim, data_startswith="hunt_claim:")
    dp.register_callback(cb_hunt_back, data="hunt:back")
