# ============================================================
#  ASTRAL ABYSS — 🤝 معامله‌ی روزانه — UI (merchant_deals_handlers.py)
# ============================================================
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
import merchant_deals as md
import class_activity_engine as cae

BTN_TEXT = "🤝 معامله‌ی روزانه"

_pending_deal: dict[int, dict] = {}  # uid -> آخرین دیلِ رول‌شده که هنوز مذاکره نشده


def _deal_kb(deal: dict) -> InlineKeyboardMarkup:
    cost_txt = f" — سرمایه: {deal['cost']:,} Zen" if deal["cost"] else " — بدونِ سرمایه‌گذاری"
    rows = [[InlineKeyboardButton(text=f"🤝 مذاکره کن{cost_txt}", callback_data="mdeal:go", style=ButtonStyle.SUCCESS)]]
    rows.append([InlineKeyboardButton(text="↩️ رد کن، یکی دیگه بیار", callback_data="mdeal:skip", style=ButtonStyle.DANGER)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _deal_text(player: dict, deal: dict, s: dict) -> str:
    npc = deal["npc"]
    zmin, zmax = deal["zen_range"]
    xmin, xmax = deal["xp_range"]
    partner_line = ""
    if deal.get("partner"):
        partner_line = f"\n🎭 شنیدی که **{deal['partner'].get('name','یه تاجرِ دیگه')}** هم رو همین کالا سرمایه‌گذاری کرده — اگه خوب دربیاد، نفوذش هم بالا می‌ره."
    return (
        f"🤝 **معامله‌ی جدید**\n{'─'*22}\n"
        f"👤 طرفِ معامله: {npc['name']}\n"
        f"📦 کالا: {npc['good']} (تیر {deal['tier']})\n"
        f"💰 سودِ احتمالی: {zmin:,}–{zmax:,} Zen | ✨ {xmin}–{xmax} XP\n"
        f"{partner_line}\n\n"
        f"{cae.status_line(s, max_actions=md.MAX_ACTIONS, daily_max=md.DAILY_MAX)}"
    )


async def cmd_merchant_deals(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player or player.get("class") != "merchant":
        await msg.answer("❌ این بخش مخصوصِ تاجره.")
        return
    s = md.get_state(uid)
    if s["actions"] <= 0 or s.get("daily_used", 0) >= md.DAILY_MAX:
        await msg.answer(
            "📵 **اقدامِ معامله‌ت تموم شده!**\n\n" + cae.status_line(s, max_actions=md.MAX_ACTIONS, daily_max=md.DAILY_MAX)
        )
        return
    deal = md.roll_deal(player)
    _pending_deal[uid] = deal
    await msg.answer(_deal_text(player, deal, s), reply_markup=_deal_kb(deal))


async def cb_mdeal_skip(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player or player.get("class") != "merchant":
        await cb.answer("❌ مخصوصِ تاجره.", show_alert=True)
        return
    s = md.get_state(uid)
    if s["actions"] <= 0 or s.get("daily_used", 0) >= md.DAILY_MAX:
        await cb.answer("📵 اقدامِ معامله‌ت تموم شده!", show_alert=True)
        return
    deal = md.roll_deal(player)
    _pending_deal[uid] = deal
    await cb.message.edit_text(_deal_text(player, deal, s), reply_markup=_deal_kb(deal))
    await cb.answer("طرفِ جدید پیدا کردی 🔄")


async def cb_mdeal_go(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player or player.get("class") != "merchant":
        await cb.answer("❌ مخصوصِ تاجره.", show_alert=True)
        return
    deal = _pending_deal.get(uid)
    if not deal:
        await cb.answer("❌ اول یه معامله رول کن (/معامله‌ی روزانه).", show_alert=True)
        return

    from class_activity_engine import use_action as _use_action
    used, s = _use_action(md.ACTIVITY_KEY, uid, max_actions=md.MAX_ACTIONS, batch_reset=md.BATCH_RESET,
                           daily_max=md.DAILY_MAX, daily_reset=md.DAILY_RESET)
    if not used:
        await cb.answer("📵 اقدامِ معامله‌ت تموم شده!", show_alert=True)
        return

    r = await md.negotiate(uid, player, deal)
    if not r["ok"]:
        await cb.answer(r["msg"], show_alert=True)
        return

    await asave_player(uid, player)
    _pending_deal.pop(uid, None)

    if r["outcome"] == "ambush":
        text = (
            f"🥷 **کمین شدی!** کاروانِ {deal['npc']['name']} تو راه غارت شد.\n"
            f"💸 -{r['loss']:,} Zen\n\n"
            f"_مزدور اجیر کن (از «⚜️ قدرت‌های کلاس») تا دفعه‌ی بعد ریسکش کمتر بشه._"
        )
    else:
        tag = "🌟 معامله‌ی عالی!" if r["outcome"] == "great" else "🤏 معامله‌ی متوسط (می‌تونستی بهتر چانه بزنی)"
        lvl_txt = f"\n\n🎉 **لول‌آپ! سطح {r['new_level']}** 🎉" if r["leveled"] else ""
        partner_txt = f"\n🤝 نفوذِ {r['partner_note']} هم کمی بالا رفت." if r.get("partner_note") else ""
        text = (
            f"{tag}\n"
            f"💰 +{r['zen']:,} Zen | ✨ +{r['xp']} XP | 📈 نفوذِ بازار +{r['influence_gain']}"
            f"{partner_txt}{lvl_txt}"
        )

    text += f"\n\n{cae.status_line(s, max_actions=md.MAX_ACTIONS, daily_max=md.DAILY_MAX)}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🤝 معامله‌ی بعدی", callback_data="mdeal:next", style=ButtonStyle.PRIMARY)
    ]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


async def cb_mdeal_next(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player or player.get("class") != "merchant":
        await cb.answer("❌ مخصوصِ تاجره.", show_alert=True)
        return
    s = md.get_state(uid)
    if s["actions"] <= 0 or s.get("daily_used", 0) >= md.DAILY_MAX:
        await cb.message.edit_text(
            "📵 **اقدامِ معامله‌ت تموم شده!**\n\n" + cae.status_line(s, max_actions=md.MAX_ACTIONS, daily_max=md.DAILY_MAX)
        )
        await cb.answer()
        return
    deal = md.roll_deal(player)
    _pending_deal[uid] = deal
    await cb.message.edit_text(_deal_text(player, deal, s), reply_markup=_deal_kb(deal))
    await cb.answer()


def register_merchant_deals_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_merchant_deals, F.text == BTN_TEXT)
    dp.callback_query.register(cb_mdeal_go, F.data == "mdeal:go")
    dp.callback_query.register(cb_mdeal_skip, F.data == "mdeal:skip")
    dp.callback_query.register(cb_mdeal_next, F.data == "mdeal:next")
