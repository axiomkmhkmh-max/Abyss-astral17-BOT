# ============================================================
#  ASTRAL ABYSS — 🔮 مشتری‌های اتلیه — UI (wizard_atelier_handlers.py)
# ============================================================
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
import wizard_atelier as wa
import class_activity_engine as cae
import crafting_system as cs

BTN_TEXT = "🔮 مشتری‌ها"

_pending_order: dict[int, dict] = {}


def _order_kb(player: dict, order: dict) -> InlineKeyboardMarkup:
    recipe_key = order["recipe_key"]
    rows = []
    if wa._has_ready_potion(player, recipe_key):
        rows.append([InlineKeyboardButton(text="📦 از کوله‌پشتی تحویل بده", callback_data="wtl:have", style=ButtonStyle.SUCCESS)])
    rows.append([InlineKeyboardButton(text="🧪 همین‌جا بساز و تحویل بده", callback_data="wtl:craft", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text=f"⚡ سرهم‌بندیِ سریع ({wa.MANA_COST_QUICK_BREW} مانا)", callback_data="wtl:quick", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="↩️ مشتریِ بعدی", callback_data="wtl:skip", style=ButtonStyle.DANGER)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _order_text(player: dict, order: dict, s: dict) -> str:
    recipe = order["recipe"]
    have = wa._has_ready_potion(player, order["recipe_key"])
    have_txt = "✅ همین الان تو کوله داری" if have else "❌ نداری — باید بسازی"
    miss = "" if cs.has_materials(player, recipe["materials"]) else f"\n🔸 مواد: {cs.missing_materials_text(player, recipe['materials'])}"
    commission_line = ""
    if order.get("commission"):
        commission_line = f"\n📮 این یه **کمیسیونِ واقعیه** — اگه بسازیش، مستقیم می‌ره تو کوله‌پشتیِ **{order['commission'].get('name','یه بازیکنِ دیگه')}** (پاداشِ بیشتر)."
    return (
        f"🔮 **مشتریِ جدید**\n{'─'*22}\n"
        f"👤 {order['customer_name']}\n"
        f"📜 سفارش: {recipe['name']} — {recipe['desc']}\n"
        f"🎒 وضعیتِ کوله: {have_txt}{miss}"
        f"{commission_line}\n\n"
        f"{cae.status_line(s, max_actions=wa.MAX_ACTIONS, daily_max=wa.DAILY_MAX)}"
    )


async def cmd_wizard_atelier(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player or player.get("class") != "wizard":
        await msg.answer("❌ این بخش مخصوصِ جادوگره.")
        return
    from class_abilities import tick_regen
    tick_regen(player)
    await asave_player(uid, player)

    s = wa.get_state(uid)
    if s["actions"] <= 0 or s.get("daily_used", 0) >= wa.DAILY_MAX:
        await msg.answer("📵 **مشتری‌های امروزت تموم شده!**\n\n" + cae.status_line(s, max_actions=wa.MAX_ACTIONS, daily_max=wa.DAILY_MAX))
        return

    order = wa.roll_customer(player)
    _pending_order[uid] = order
    await msg.answer(_order_text(player, order, s), reply_markup=_order_kb(player, order))


async def _reroll(uid: int, player: dict, edit_target) -> None:
    s = wa.get_state(uid)
    if s["actions"] <= 0 or s.get("daily_used", 0) >= wa.DAILY_MAX:
        await edit_target.edit_text("📵 **مشتری‌های امروزت تموم شده!**\n\n" + cae.status_line(s, max_actions=wa.MAX_ACTIONS, daily_max=wa.DAILY_MAX))
        return
    order = wa.roll_customer(player)
    _pending_order[uid] = order
    await edit_target.edit_text(_order_text(player, order, s), reply_markup=_order_kb(player, order))


async def cb_wtl_skip(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player or player.get("class") != "wizard":
        await cb.answer("❌ مخصوصِ جادوگره.", show_alert=True)
        return
    await _reroll(uid, player, cb.message)
    await cb.answer("مشتریِ بعدی رسید 🔄")


async def cb_wtl_next(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player or player.get("class") != "wizard":
        await cb.answer("❌ مخصوصِ جادوگره.", show_alert=True)
        return
    await _reroll(uid, player, cb.message)
    await cb.answer()


async def _fulfill(cb: CallbackQuery, method: str):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player or player.get("class") != "wizard":
        await cb.answer("❌ مخصوصِ جادوگره.", show_alert=True)
        return
    order = _pending_order.get(uid)
    if not order:
        await cb.answer("❌ اول یه مشتری بیار (🔮 مشتری‌ها).", show_alert=True)
        return

    used, s = cae.use_action(wa.ACTIVITY_KEY, uid, max_actions=wa.MAX_ACTIONS, batch_reset=wa.BATCH_RESET,
                              daily_max=wa.DAILY_MAX, daily_reset=wa.DAILY_RESET)
    if not used:
        await cb.answer("📵 مشتری‌های امروزت تموم شده!", show_alert=True)
        return

    r = await wa.fulfill_order(uid, player, order, method=method)
    if not r["ok"]:
        await cb.answer(r["msg"], show_alert=True)
        return

    await asave_player(uid, player)
    _pending_order.pop(uid, None)

    method_tag = {"have": "📦 از کوله تحویل دادی", "craft": "🧪 همون‌جا ساختی و تحویل دادی", "quick": "⚡ سرهم‌بندیِ سریع تحویل دادی"}[r["method"]]
    delivered_txt = f"\n📮 مستقیم رفت تو کوله‌پشتیِ **{r['delivered_to']}**!" if r.get("delivered_to") else ""
    lvl_txt = f"\n\n🎉 **لول‌آپ! سطح {r['new_level']}** 🎉" if r["leveled"] else ""
    text = f"{method_tag}{delivered_txt}\n💰 +{r['zen']:,} Zen | ✨ +{r['xp']} XP{lvl_txt}"
    text += f"\n\n{cae.status_line(s, max_actions=wa.MAX_ACTIONS, daily_max=wa.DAILY_MAX)}"

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔮 مشتریِ بعدی", callback_data="wtl:next", style=ButtonStyle.PRIMARY)
    ]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


async def cb_wtl_have(cb: CallbackQuery):
    await _fulfill(cb, "have")


async def cb_wtl_craft(cb: CallbackQuery):
    await _fulfill(cb, "craft")


async def cb_wtl_quick(cb: CallbackQuery):
    await _fulfill(cb, "quick")


def register_wizard_atelier_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_wizard_atelier, F.text == BTN_TEXT)
    dp.callback_query.register(cb_wtl_have, F.data == "wtl:have")
    dp.callback_query.register(cb_wtl_craft, F.data == "wtl:craft")
    dp.callback_query.register(cb_wtl_quick, F.data == "wtl:quick")
    dp.callback_query.register(cb_wtl_skip, F.data == "wtl:skip")
    dp.callback_query.register(cb_wtl_next, F.data == "wtl:next")
