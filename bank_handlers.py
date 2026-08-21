# ============================================================
#  ASTRAL ABYSS — عابربانک: Handlers
# ============================================================
import time

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.enums import ButtonStyle
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from logger import log_sync
import bank_system as bs

_awaiting_text: dict[int, tuple[str, float]] = {}   # uid -> (mode, ttl)
BANK_TTL = 120


def _bank_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="💸 انتقال Zen", callback_data="bank:transfer", style=ButtonStyle.PRIMARY)],
        [
            InlineKeyboardButton(text="🏺 واریز به سپرده", callback_data="bank:dep_sav", style=ButtonStyle.SUCCESS),
            InlineKeyboardButton(text="💵 برداشت از سپرده", callback_data="bank:wd_sav", style=ButtonStyle.PRIMARY),
        ],
        [InlineKeyboardButton(text="💳 وام", callback_data="bank:loan", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="⚖️ پرداختِ بدهیِ تحت‌تعقیب", callback_data="bank:wanted_repay", style=ButtonStyle.DANGER)],
        [InlineKeyboardButton(text="📜 تاریخچه‌ی تراکنش‌ها", callback_data="bank:history", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🔐 تنظیم/تغییرِ PIN", callback_data="bank:setpin", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🚫 غیرفعال‌کردنِ PIN", callback_data="bank:clearpin", style=ButtonStyle.DANGER)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _panel_text(player: dict, uid: int) -> str:
    card = await bs.get_or_create_card(uid, player)
    pin_status = "🔐 فعال" if bs.has_pin(player) else "🔓 غیرفعال"
    remaining = bs.daily_remaining(player)

    sav = bs.savings_summary(player)
    sav_line = f"🏺 سپرده: **{sav['balance']:,} Zen**"
    if sav["new_interest"] > 0:
        sav_line += f" (+{sav['new_interest']:,} سود جدید 🎉)"

    loan = bs.loan_status(player)
    if loan["late_msg"]:
        loan_line = f"💳 وام: 🔴 **{loan['principal']:,} Zen** — دیرکرد داشت، جریمه خورد!"
    elif loan["active"]:
        remain_h = max(0, int((loan["due_at"] - time.time()) / 3600))
        loan_line = f"💳 وام: **{loan['principal']:,} Zen** — {remain_h} ساعت تا موعد"
    else:
        loan_line = f"💳 وام: نداری (سقفِ مجاز: {loan['max_loan']:,} Zen | اعتبار: {loan['credit_score']}/100)"

    debt = player.get("bank_debt", 0)
    debt_line = ""
    if debt > 0:
        try:
            from daily_wanted import debt_income_multiplier
            mult = int(debt_income_multiplier(player) * 100)
        except ImportError:
            mult = 100
        debt_line = f"⚖️ بدهیِ تحت‌تعقیب: 🔴 **{debt:,} Zen** — درآمدت الان {mult}٪ شده!\n"

    await asave_player(uid, player)
    return (
        f"🏦 **عابربانکِ Astral Abyss**\n\n"
        f"💳 شماره‌کارت: `{bs.format_card(card)}`\n"
        f"💰 موجودی: **{player.get('zen', 0):,} Zen**\n"
        f"{sav_line}\n"
        f"{loan_line}\n"
        f"{debt_line}"
        f"🛡️ PIN: {pin_status}\n"
        f"📊 سقفِ باقی‌مانده‌ی امروز: **{remaining:,} Zen**\n\n"
        f"برای انتقال، شماره‌کارتِ گیرنده (یا @یوزرنیم/آیدی) رو لازم داری.\n"
        f"کارمزدِ هر تراکنش: {int(bs.TRANSFER_FEE_PCT*100)}٪ (می‌ره تو صندوقِ مالیاتِ سراسری)."
    )


async def cmd_bank(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    await msg.answer(await _panel_text(player, uid), reply_markup=_bank_kb())


async def cb_bank_transfer(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    _awaiting_text[uid] = ("transfer", time.time() + BANK_TTL)
    extra = " سپس PIN رو هم با فاصله بنویس." if bs.has_pin(player) else ""
    await cb.message.answer(
        "💸 **انتقالِ Zen**\n\n"
        "پیامتو به این شکل بفرست:\n"
        "`شماره‌کارت مبلغ`" + (" `پین`" if bs.has_pin(player) else "") + "\n\n"
        "مثال: `8991123456781234 500`" + (" `1234`" if bs.has_pin(player) else "") + "\n"
        "می‌تونی به‌جای شماره‌کارت، @یوزرنیم یا آیدیِ عددی هم بفرستی." + extra
    )
    await cb.answer()


async def cb_bank_history(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    hist = bs.get_history(player)
    if not hist:
        await cb.message.answer("📜 هنوز هیچ تراکنشی نداری.")
        await cb.answer()
        return
    lines = ["📜 **آخرین تراکنش‌ها:**\n"]
    for h in hist[:15]:
        ts = time.strftime("%m/%d %H:%M", time.localtime(h.get("t", 0)))
        if h.get("dir") == "out":
            lines.append(f"🔴 {ts} — ارسال {h['amount']:,} Zen به {h.get('peer','?')} (کارمزد {h.get('fee',0):,})")
        else:
            lines.append(f"🟢 {ts} — دریافتِ {h['amount']:,} Zen از {h.get('peer','?')}")
    await cb.message.answer("\n".join(lines))
    await cb.answer()


async def cb_bank_setpin(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    _awaiting_text[uid] = ("setpin", time.time() + BANK_TTL)
    await cb.message.answer(f"🔐 یه PIN {bs.PIN_LENGTH} رقمی بفرست (فقط عدد، مثلاً `1234`):")
    await cb.answer()


async def cb_bank_clearpin(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    if not bs.has_pin(player):
        await cb.answer("PIN از قبل غیرفعاله.", show_alert=True)
        return
    bs.clear_pin(player)
    await asave_player(uid, player)
    await cb.message.answer("🚫 PIN غیرفعال شد.")
    await cb.answer()


async def cb_bank_dep_sav(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    _awaiting_text[uid] = ("dep_sav", time.time() + BANK_TTL)
    await cb.message.answer(
        f"🏺 **واریز به سپرده**\nچقدر Zen بذاری کنار؟ (حداقل {bs.MIN_SAVINGS_DEPOSIT:,})\n"
        f"سود روزانه: **{bs.SAVINGS_DAILY_RATE*100:.1f}٪** — فقط عددشو بفرست."
    )
    await cb.answer()


async def cb_bank_wd_sav(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    _awaiting_text[uid] = ("wd_sav", time.time() + BANK_TTL)
    bal = bs.savings_summary(player)["balance"]
    await asave_player(uid, player)
    await cb.message.answer(f"💵 **برداشت از سپرده**\nموجودیِ سپرده: **{bal:,} Zen**\nچقدر برداشت کنم؟")
    await cb.answer()


def _loan_kb(has_loan: bool) -> InlineKeyboardMarkup:
    if has_loan:
        rows = [[InlineKeyboardButton(text="💳 بازپرداختِ وام", callback_data="bank:loan_repay", style=ButtonStyle.SUCCESS)]]
    else:
        rows = [[InlineKeyboardButton(text="💰 گرفتنِ وام", callback_data="bank:loan_borrow", style=ButtonStyle.PRIMARY)]]
    rows.append([InlineKeyboardButton(text="◀️ بازگشت به بانک", callback_data="bank:home", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_bank_loan(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    status = bs.loan_status(player)
    await asave_player(uid, player)
    if status["late_msg"]:
        await cb.message.answer(status["late_msg"])
    if status["active"]:
        remain_h = max(0, int((status["due_at"] - time.time()) / 3600))
        text = (
            f"💳 **وضعیتِ وام**\n\n"
            f"مانده‌ی بدهی: **{status['principal']:,} Zen**\n"
            f"⏰ {remain_h} ساعت تا موعد\n"
            f"📊 اعتبار: {status['credit_score']}/100"
        )
    else:
        collateral_line = (
            f"🏠 وثیقه‌ی ملک: +{status['house_collateral']:,} Zen (از درآمدِ غیرفعالِ خونه)\n"
            if status.get("house_collateral", 0) > 0 else ""
        )
        text = (
            f"💳 **صرافِ سراسری**\n\n"
            f"سقفِ مجازِ وام: **{status['max_loan']:,} Zen**\n"
            f"📊 اعتبارِ فعلی: {status['credit_score']}/100\n"
            f"{collateral_line}"
            f"بهره: {int(bs.LOAN_INTEREST_RATE*100)}٪ | مهلت: ۴۸ ساعت | جریمه‌ی دیرکرد: {int(bs.LOAN_LATE_PENALTY_RATE*100)}٪"
        )
    await cb.message.answer(text, reply_markup=_loan_kb(status["active"]))
    await cb.answer()


async def cb_bank_loan_borrow(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    cap = bs.max_loan_amount(player)
    _awaiting_text[uid] = ("loan_borrow", time.time() + BANK_TTL)
    await cb.message.answer(f"💰 چقدر وام بگیرم؟ (حداکثر **{cap:,} Zen**)")
    await cb.answer()


async def cb_bank_loan_repay(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    principal = player.get("loan_principal", 0)
    _awaiting_text[uid] = ("loan_repay", time.time() + BANK_TTL)
    await cb.message.answer(f"💳 مانده‌ی بدهی: **{principal:,} Zen**\nچقدر پرداخت کنم؟")
    await cb.answer()


async def cb_bank_wanted_repay(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    debt = player.get("bank_debt", 0)
    if debt <= 0:
        await cb.answer("✅ الان هیچ بدهیِ تحت‌تعقیبی نداری!", show_alert=True)
        return
    _awaiting_text[uid] = ("wanted_repay", time.time() + BANK_TTL)
    await cb.message.answer(
        f"⚖️ مانده‌ی بدهیِ تحت‌تعقیب: **{debt:,} Zen**\nچقدر پرداخت کنم؟"
    )
    await cb.answer()


async def cb_bank_home(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    await cb.message.answer(await _panel_text(player, uid), reply_markup=_bank_kb())
    await cb.answer()


async def handle_bank_text(msg: Message):
    uid = msg.from_user.id
    entry = _awaiting_text.get(uid)
    if not entry:
        return
    mode, expires = entry
    if time.time() > expires:
        del _awaiting_text[uid]
        await msg.answer("⏰ زمان تموم شد، دوباره از منوی بانک شروع کن.")
        return
    del _awaiting_text[uid]

    text = (msg.text or "").strip()

    if mode == "setpin":
        if not (text.isdigit() and len(text) == bs.PIN_LENGTH):
            await msg.answer(f"❌ PIN باید دقیقاً {bs.PIN_LENGTH} رقم باشه!")
            return
        player = await aget_player(uid)
        bs.set_pin(player, text)
        await asave_player(uid, player)
        await msg.answer("✅ PIN فعال شد. از این به بعد برای انتقال بهش نیاز داری.")
        return

    if mode == "transfer":
        parts = text.split()
        if len(parts) < 2:
            await msg.answer("❌ فرمت اشتباهه! به این شکل بفرست: `شماره‌کارت مبلغ [پین]`")
            return
        target_input = parts[0]
        amount_s = parts[1]
        pin = parts[2] if len(parts) > 2 else None
        if not (amount_s.isdigit() and int(amount_s) > 0):
            await msg.answer("❌ مبلغ باید یه عددِ مثبت باشه!")
            return
        amount = int(amount_s)
        res = await bs.transfer(uid, target_input, amount, pin)
        await msg.answer(res["msg"])
        if res.get("ok"):
            log_sync(
                f"🏦 **BANK TRANSFER**\n👤 از `{uid}` → {res.get('target_name','?')} (`{res.get('target_uid','?')}`)\n"
                f"💰 {amount:,} Zen (کارمزد {res.get('fee',0):,})",
                "ECONOMY",
            )
        return

    if mode in ("dep_sav", "wd_sav", "loan_borrow", "loan_repay"):
        if not (text.isdigit() and int(text) > 0):
            await msg.answer("❌ باید یه عددِ مثبت بفرستی!")
            return
        amount = int(text)
        player = await aget_player(uid)

        if mode == "dep_sav":
            res = bs.deposit_savings(player, amount)
        elif mode == "wd_sav":
            res = bs.withdraw_savings(player, amount)
        elif mode == "loan_borrow":
            res = bs.borrow(player, amount)
        else:
            res = bs.repay(player, amount)

        await asave_player(uid, player)
        await msg.answer(res["msg"])
        if res.get("ok") and mode in ("loan_borrow", "loan_repay"):
            log_sync(
                f"💳 **{'LOAN BORROW' if mode=='loan_borrow' else 'LOAN REPAY'}**\n"
                f"👤 {player.get('name', uid)} (`{uid}`)\n💰 {amount:,} Zen",
                "ECONOMY",
            )
        return

    if mode == "wanted_repay":
        if not (text.isdigit() and int(text) > 0):
            await msg.answer("❌ باید یه عددِ مثبت بفرستی!")
            return
        amount = int(text)
        player = await aget_player(uid)
        from daily_wanted import repay_debt
        paid = repay_debt(player, amount)
        await asave_player(uid, player)
        if paid <= 0:
            await msg.answer("❌ Zenِ کافی نداری یا بدهی‌ای نمونده.")
        else:
            remaining = player.get("bank_debt", 0)
            await msg.answer(
                f"✅ **{paid:,} Zen** از بدهیت پرداخت شد.\n"
                f"⚖️ بدهیِ باقی‌مونده: **{remaining:,} Zen**" if remaining > 0
                else f"✅ **{paid:,} Zen** پرداخت شد — بدهیت کامل صاف شد! 🎉"
            )
            log_sync(
                f"⚖️ **WANTED DEBT REPAY**\n👤 {player.get('name', uid)} (`{uid}`)\n💰 {paid:,} Zen",
                "ECONOMY",
            )
        return


def register_bank_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_bank, Command("bank"))
    dp.message.register(cmd_bank, F.text == "بانک")
    dp.callback_query.register(cb_bank_transfer, F.data == "bank:transfer")
    dp.callback_query.register(cb_bank_history, F.data == "bank:history")
    dp.callback_query.register(cb_bank_setpin, F.data == "bank:setpin")
    dp.callback_query.register(cb_bank_clearpin, F.data == "bank:clearpin")
    dp.callback_query.register(cb_bank_dep_sav, F.data == "bank:dep_sav")
    dp.callback_query.register(cb_bank_wd_sav, F.data == "bank:wd_sav")
    dp.callback_query.register(cb_bank_loan, F.data == "bank:loan")
    dp.callback_query.register(cb_bank_loan_borrow, F.data == "bank:loan_borrow")
    dp.callback_query.register(cb_bank_loan_repay, F.data == "bank:loan_repay")
    dp.callback_query.register(cb_bank_wanted_repay, F.data == "bank:wanted_repay")
    dp.callback_query.register(cb_bank_home, F.data == "bank:home")
    dp.message.register(handle_bank_text, lambda m: m.from_user.id in _awaiting_text)
