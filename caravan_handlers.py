# ============================================================
#  ASTRAL ABYSS RPG — Caravan Handlers (Telegram UI)
#  (caravan_handlers.py)
# ------------------------------------------------------------
#  دکمه‌ی «🚶 سفر» تو پنلِ تاجر به cmd_caravan وصله. منطقِ خالص تو
#  caravan_system.py هست.
# ============================================================

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
import caravan_system as cs


def _fmt_time(seconds: int) -> str:
    m, s = divmod(max(0, seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h} ساعت و {m} دقیقه"
    if m:
        return f"{m} دقیقه"
    return f"{s} ثانیه"


def _route_kb() -> InlineKeyboardMarkup:
    rows = []
    for r in cs.ROUTES:
        rows.append([InlineKeyboardButton(
            text=f"{r['name_fa']} — {r['cost']:,} Zen ({_fmt_time(r['duration_sec'])})",
            callback_data=f"car:start:{r['id']}",
            style=ButtonStyle.PRIMARY,
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _route_text() -> str:
    lines = ["🚶 **سفرِ کاروان** — سرمایه‌گذاری کن، منتظر بمون، سود کن\n"]
    lines.append("_هر مزدورِ اجیرشده (از «⚜️ قدرت‌های کلاس») ریسکِ غارت‌شدنِ کاروان رو کم می‌کنه._\n")
    for r in cs.ROUTES:
        lines.append(
            f"{r['name_fa']}\n"
            f"  💰 هزینه: {r['cost']:,} Zen | ⏱ {_fmt_time(r['duration_sec'])} | ⚠️ ریسک: {r['risk_pct']}٪\n"
            f"  {r['desc']}\n"
        )
    lines.append("کدوم مسیر رو می‌خوای بری؟")
    return "\n".join(lines)


def _status_kb(claimable: bool) -> InlineKeyboardMarkup:
    if claimable:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🎁 دریافتِ نتیجه‌ی کاروان", callback_data="car:claim", style=ButtonStyle.SUCCESS),
        ]])
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔄 بررسیِ دوباره", callback_data="car:claim", style=ButtonStyle.PRIMARY),
    ]])


def _status_text(caravan: dict) -> str:
    route = cs.get_route(caravan["route"]) or cs.ROUTES[0]
    remaining = cs.caravan_time_left(caravan)
    if remaining <= 0:
        return f"🚶 کاروانت از **{route['name_fa']}** برگشته! می‌تونی نتیجه رو بگیری."
    return (
        f"🚶 کاروانت الان تو مسیرِ **{route['name_fa']}**ه.\n"
        f"⏱ زمانِ باقی‌مونده: {_fmt_time(remaining)}"
    )


async def cmd_caravan(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player or not player.get("class"):
        await msg.answer("❌ اول باید کاراکترت رو بسازی! /start رو بزن.")
        return
    if player.get("class") != "merchant":
        await msg.answer("❌ سفرِ کاروان مخصوصِ کلاسِ تاجره.")
        return
    caravan = cs.active_caravan(player)
    if caravan:
        await msg.answer(_status_text(caravan), reply_markup=_status_kb(cs.caravan_time_left(caravan) <= 0))
        return
    await msg.answer(_route_text(), reply_markup=_route_kb())


async def cb_car_start(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    route_id = cb.data.split(":")[2]
    r = cs.start_caravan(player, route_id)
    if not r["ok"]:
        await cb.answer(r["msg"], show_alert=True)
        return
    save_player(uid, player)
    route = r["route"]
    await cb.answer(f"🚶 کاروان به سمتِ {route['name_fa']} راه افتاد!", show_alert=True)
    try:
        await cb.message.edit_text(
            f"🚶 کاروانت به سمتِ **{route['name_fa']}** راه افتاد.\n"
            f"⏱ برمی‌گرده تا {_fmt_time(route['duration_sec'])}ِ دیگه.",
            reply_markup=_status_kb(False),
        )
    except Exception:
        pass


async def cb_car_claim(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    r = cs.claim_caravan(player)
    if not r["ok"]:
        if r.get("waiting"):
            caravan = cs.active_caravan(player)
            try:
                await cb.message.edit_text(_status_text(caravan), reply_markup=_status_kb(False))
            except Exception:
                pass
            await cb.answer(f"⏳ هنوز {_fmt_time(r['remaining'])} مونده.", show_alert=True)
            return
        await cb.answer(r["msg"], show_alert=True)
        return

    save_player(uid, player)
    route = r["route"]
    if r["ambushed"]:
        text = (
            f"⚠️ **کاروان غارت شد!**\n"
            f"مسیر: {route['name_fa']}\n"
            f"💸 {r['loss']:,} Zen از سودِ سرمایه‌گذاری‌شده از دست رفت."
        )
        await cb.answer(f"⚠️ کاروانت غارت شد! -{r['loss']:,} Zen", show_alert=True)
    else:
        text = (
            f"✅ **کاروان با موفقیت برگشت!**\n"
            f"مسیر: {route['name_fa']}\n"
            f"💰 سود: +{r['reward']:,} Zen\n"
            f"📈 نفوذِ بازار: +{r['influence_gain']}"
        )
        await cb.answer(f"✅ سود: +{r['reward']:,} Zen", show_alert=True)
    try:
        await cb.message.edit_text(text + "\n\nمی‌خوای یه کاروانِ جدید بفرستی؟", reply_markup=_route_kb())
    except Exception:
        await cb.message.answer(text + "\n\nمی‌خوای یه کاروانِ جدید بفرستی؟", reply_markup=_route_kb())


def register_caravan_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_caravan, F.text == "🚶 سفر")
    dp.callback_query.register(cb_car_start, F.data.startswith("car:start:"))
    dp.callback_query.register(cb_car_claim, F.data == "car:claim")
