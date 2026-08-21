# ============================================================
#  ASTRAL ABYSS RPG — Casino 🎰  (v2)
#  چهار بازی: 🪙 شیر یا خط | 🎲 تاس شانس | 🎰 اسلات (+ جکپاتِ تجمعی)
#  | 🃏 بلک‌جک — به‌علاوه‌ی VIP tier (بر اساسِ حجمِ شرط) و
#  لیدربوردِ بردِ هفتگی. همه با Zen شرط‌بندی می‌شن. مثل بقیه‌ی
#  سیستم‌های اقتصادی بازی، یه Zen sink طراحی‌شده‌ست (RTP زیر ۱۰۰٪)
#  نه یه دستگاه چاپ پول.
# ============================================================
import random, time
from datetime import datetime, timezone

from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, casino_col, get_jackpot, add_to_jackpot, reset_jackpot, asave_player, aget_player
from logger import log_sync

STAKES = [500, 2000, 10000, 50000]
CASINO_COOLDOWN = 3  # ثانیه بین هر بازی — جلوگیری از اسپم دکمه
JACKPOT_CONTRIBUTION_PCT = 0.01   # ۱٪ از هر شرط می‌ره تو جکپاتِ سراسری
JACKPOT_TRIGGER_CHANCE = 0.15     # شرطِ لازم: سه‌تا 7️⃣ آوردن؛ روی اون یه شانسِ اضافه برای بردنِ کلِ جکپات


def _week_id() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.isocalendar().year}-W{now.isocalendar().week}"


def _cooldown_left(player: dict) -> int:
    return int(player.get("_casino_cd", 0) - time.time())


def _set_cooldown(player: dict):
    player["_casino_cd"] = time.time() + CASINO_COOLDOWN


# ─── 💎 VIP Tier ─────────────────────────────────────────────────
VIP_TIERS = [
    ("💠 برنزی",   0,          0.00),
    ("🥈 نقره‌ای",  100_000,    0.02),
    ("🥇 طلایی",   500_000,    0.05),
    ("💎 پلاتینیوم", 2_000_000, 0.08),
    ("👑 الماسی",  10_000_000, 0.12),
]


def _vip_tier(player: dict) -> tuple[str, float, int, float | None]:
    """برمی‌گردونه: (نامِ tier، بونوسِ فعلی، آستانه‌ی فعلی، آستانه‌ی بعدی یا None)."""
    wagered = player.get("casino_total_wagered", 0)
    current = VIP_TIERS[0]
    nxt = None
    for i, t in enumerate(VIP_TIERS):
        if wagered >= t[1]:
            current = t
            nxt = VIP_TIERS[i + 1][1] if i + 1 < len(VIP_TIERS) else None
    return current[0], current[2], current[1], nxt


def _ensure_weekly(player: dict):
    wid = _week_id()
    if player.get("casino_week_id") != wid:
        player["casino_week_id"] = wid
        player["casino_weekly_net"] = 0


def _record_wager(player: dict, uid: int, stake: int, net: int):
    """آمارِ کازینو رو (حجمِ کل، خالص هفتگی) هم رو خودِ پروفایل و هم تو
    casino_col (برای لیدربوردِ سراسری بدون نیاز به اسکن کل بازیکن‌ها) ثبت می‌کنه."""
    _ensure_weekly(player)
    player["casino_total_wagered"] = player.get("casino_total_wagered", 0) + stake
    player["casino_weekly_net"] = player.get("casino_weekly_net", 0) + net
    wid = player["casino_week_id"]
    casino_col().update_one(
        {"_id": uid},
        {"$set": {
            "name": player.get("name", "—"),
            "week_id": wid,
            "weekly_net": player["casino_weekly_net"],
            "total_wagered": player["casino_total_wagered"],
        }},
        upsert=True,
    )


# ─── 🏠 منوی اصلی کازینو ────────────────────────────────────────
def _casino_home_kb(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪙 شیر یا خط  (×1.9)", callback_data=f"casino_menu:coin:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🎲 تاس شانس  (×5)",    callback_data=f"casino_menu:dice:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🎰 اسلات + جکپات",     callback_data=f"casino_menu:slot:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🃏 بلک‌جک",            callback_data=f"casino_menu:blackjack:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🏆 لیدربورد هفتگی",    callback_data=f"casino_lb:{uid}", style=ButtonStyle.PRIMARY)],
    ])


def _home_text(player: dict) -> str:
    tier_name, tier_bonus, _, nxt = _vip_tier(player)
    jackpot = get_jackpot()
    vip_line = f"💎 VIP: **{tier_name}**" + (f" (+{int(tier_bonus*100)}٪ به بردها)" if tier_bonus else "")
    if nxt:
        vip_line += f" — {nxt:,} Zen شرط تا سطحِ بعدی"
    return (
        "🎰 **کازینوی آبیس** 🎰\n\n"
        f"💰 موجودی تو: {player.get('zen',0):,} Zen\n"
        f"{vip_line}\n"
        f"💰 **جکپاتِ تجمعی فعلی: {jackpot:,} Zen** 🎉\n\n"
        "🪙 **شیر یا خط** — حدس بزن، برد = ۱.۹ برابر شرط\n"
        "🎲 **تاس شانس** — عدد ۱ تا ۶ رو حدس بزن، برد = ۵ برابر شرط\n"
        "🎰 **اسلات** — سه تا نماد بچرخون؛ سه‌تا 7️⃣ شانسِ بردنِ کلِ جکپات رو هم داره\n"
        "🃏 **بلک‌جک** — در برابر خانه بازی کن، نزدیک‌تر به ۲۱ شو بدون رد کردن\n\n"
        "⚠️ شانس همیشه یه‌کم به نفع خونه‌ست — مسئولانه بازی کن."
    )


async def cmd_casino(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    from level_gate import check_level
    ok, why = check_level(player, "casino")
    if not ok:
        await msg.answer(why)
        return
    await msg.answer(_home_text(player), reply_markup=_casino_home_kb(uid))


def _owner_ok(cb: CallbackQuery, uid: int) -> bool:
    return cb.from_user.id == uid


async def cb_casino_home(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    await cb.answer()
    await cb.message.edit_text(_home_text(player), reply_markup=_casino_home_kb(uid))


# ─── 🏆 لیدربورد هفتگی ──────────────────────────────────────────
async def cb_casino_leaderboard(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    await cb.answer()
    wid = _week_id()
    top = list(casino_col().find({"week_id": wid}).sort("weekly_net", -1).limit(10))
    if not top:
        text = "🏆 **لیدربورد هفتگی کازینو**\n\nهنوز این هفته کسی بازی نکرده."
    else:
        lines = ["🏆 **لیدربورد هفتگی کازینو** (خالصِ برد این هفته)\n"]
        medals = ["🥇", "🥈", "🥉"]
        for i, doc in enumerate(top):
            medal = medals[i] if i < 3 else f"{i+1}."
            net = doc.get("weekly_net", 0)
            sign = "+" if net >= 0 else ""
            lines.append(f"{medal} {doc.get('name','—')} — {sign}{net:,} Zen")
        text = "\n".join(lines)
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"casino_home:{uid}", style=ButtonStyle.PRIMARY)]
    ]))


# ─── انتخاب شرط ─────────────────────────────────────────────────
def _stake_kb(game: str, uid: int, extra: str = "") -> InlineKeyboardMarkup:
    rows = []
    for s in STAKES:
        rows.append([InlineKeyboardButton(
            text=f"💰 {s:,}", callback_data=f"casino_stake:{game}:{extra}:{s}:{uid}"
        , style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"casino_home:{uid}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_casino_menu(cb: CallbackQuery):
    _, game, uid_s = cb.data.split(":")
    uid = int(uid_s)
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    await cb.answer()
    if game == "coin":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌕 شیر", callback_data=f"casino_pick:coin:heads:{uid}", style=ButtonStyle.PRIMARY)],
            [InlineKeyboardButton(text="🌑 خط",  callback_data=f"casino_pick:coin:tails:{uid}", style=ButtonStyle.PRIMARY)],
            [InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"casino_home:{uid}", style=ButtonStyle.PRIMARY)],
        ])
        await cb.message.edit_text("🪙 **شیر یا خط**\n\nاول طرفت رو انتخاب کن:", reply_markup=kb)
    elif game == "dice":
        rows = [[InlineKeyboardButton(text=str(n), callback_data=f"casino_pick:dice:{n}:{uid}", style=ButtonStyle.PRIMARY) for n in (1, 2, 3)],
                [InlineKeyboardButton(text=str(n), callback_data=f"casino_pick:dice:{n}:{uid}", style=ButtonStyle.PRIMARY) for n in (4, 5, 6)],
                [InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"casino_home:{uid}", style=ButtonStyle.PRIMARY)]]
        kb = InlineKeyboardMarkup(inline_keyboard=rows)
        await cb.message.edit_text("🎲 **تاس شانس**\n\nیه عدد بین ۱ تا ۶ حدس بزن:", reply_markup=kb)
    elif game == "slot":
        await cb.message.edit_text("🎰 **اسلات**\n\nمبلغ شرطت رو انتخاب کن:", reply_markup=_stake_kb("slot", uid))
    elif game == "blackjack":
        await cb.message.edit_text("🃏 **بلک‌جک**\n\nمبلغ شرطت رو انتخاب کن:", reply_markup=_stake_kb("blackjack", uid))


async def cb_casino_pick(cb: CallbackQuery):
    _, game, choice, uid_s = cb.data.split(":")
    uid = int(uid_s)
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    await cb.answer()
    label = "🪙 شیر یا خط" if game == "coin" else "🎲 تاس شانس"
    await cb.message.edit_text(
        f"{label}\n\nانتخابت: **{'🌕 شیر' if choice=='heads' else '🌑 خط' if choice=='tails' else choice}**\n\nحالا شرطت رو انتخاب کن:",
        reply_markup=_stake_kb(game, uid, choice)
    )


# ─── منطق بازی‌های آنی ───────────────────────────────────────────
SLOT_SYMBOLS = ["🍒", "🍋", "🍇", "💎", "7️⃣"]
SLOT_WEIGHTS = [38, 27, 19, 12, 4]


def _spin_slot() -> list[str]:
    return random.choices(SLOT_SYMBOLS, weights=SLOT_WEIGHTS, k=3)


def _slot_payout(reels: list[str]) -> float:
    if reels[0] == reels[1] == reels[2]:
        return {"7️⃣": 20.0, "💎": 10.0, "🍇": 6.0, "🍋": 4.0, "🍒": 3.0}[reels[0]]
    if reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        return 1.3
    return 0.0


async def cb_casino_stake(cb: CallbackQuery):
    parts = cb.data.split(":")
    _, game, extra, stake_s, uid_s = parts
    stake, uid = int(stake_s), int(uid_s)
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return

    player = await aget_player(uid)
    remain = _cooldown_left(player)
    if remain > 0:
        await cb.answer(f"⏳ {remain} ثانیه صبر کن.", show_alert=True)
        return
    if player.get("zen", 0) < stake:
        await cb.answer("❌ Zen کافی نداری!", show_alert=True)
        return

    if game == "blackjack":
        await _start_blackjack(cb, player, uid, stake)
        return

    _set_cooldown(player)
    player["zen"] -= stake
    win_zen = 0
    result_text = ""
    jackpot_won = 0

    if game == "coin":
        outcome = random.choices(["heads", "tails"], weights=[49, 51] if extra == "heads" else [51, 49])[0]
        won = outcome == extra
        if won:
            win_zen = int(stake * 1.9)
        emoji = "🌕" if outcome == "heads" else "🌑"
        result_text = f"🪙 سکه: {emoji} ({'شیر' if outcome=='heads' else 'خط'})\n"

    elif game == "dice":
        guess = int(extra)
        roll = random.randint(1, 6)
        won = roll == guess
        if won:
            win_zen = int(stake * 5)
        result_text = f"🎲 تاس: **{roll}**\n"

    elif game == "slot":
        reels = _spin_slot()
        mult = _slot_payout(reels)
        won = mult > 0
        win_zen = int(stake * mult)
        result_text = f"🎰 {' | '.join(reels)}\n"
        # ─── جکپاتِ تجمعی: هر شرطی یه سهمِ کوچیک بهش اضافه می‌کنه ───
        pool = add_to_jackpot(int(stake * JACKPOT_CONTRIBUTION_PCT))
        if reels[0] == reels[1] == reels[2] == "7️⃣" and random.random() < JACKPOT_TRIGGER_CHANCE:
            jackpot_won = pool
            win_zen += jackpot_won
            reset_jackpot()

    else:
        await cb.answer("❌ خطا!", show_alert=True)
        return

    # ─── بونوسِ VIP روی بردها ────────────────────────────────────
    _, tier_bonus, _, _ = _vip_tier(player)
    if win_zen > 0 and tier_bonus > 0:
        win_zen = int(win_zen * (1 + tier_bonus))

    player["zen"] += win_zen
    net = win_zen - stake
    _record_wager(player, uid, stake, net)
    await asave_player(uid, player)

    if jackpot_won:
        result_text += f"\n🎉🎉 **جکپاتِ تجمعی رو بردی!! +{jackpot_won:,} Zen** 🎉🎉\n"
    if net > 0:
        result_text += f"\n🎉 **بردی!** +{net:,} Zen (شرط: {stake:,} → گرفتی: {win_zen:,})"
    elif net == 0:
        result_text += f"\n😐 مساوی. شرطت برگشت."
    else:
        result_text += f"\n💸 **باختی.** {stake:,} Zen از دست دادی."

    result_text += f"\n\n💰 موجودی فعلی: {player['zen']:,} Zen"

    log_sync(
        f"🎰 **CASINO** {game.upper()} | 👤 {player.get('name','—')} (`{uid}`)\n"
        f"💰 شرط: {stake:,} | نتیجه: {net:+,} Zen" + (f" | 🎉 جکپات: {jackpot_won:,}" if jackpot_won else ""),
        "CASINO"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 دوباره", callback_data=f"casino_menu:{game}:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"casino_home:{uid}", style=ButtonStyle.PRIMARY)],
    ])
    await cb.answer()
    await cb.message.edit_text(result_text, reply_markup=kb)


# ─── 🃏 بلک‌جک ───────────────────────────────────────────────────
_bj_sessions: dict[int, dict] = {}  # uid -> {stake, player_hand, dealer_hand}

CARD_RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
CARD_SUITS = ["♠️", "♥️", "♦️", "♣️"]


def _draw_card() -> tuple[str, str]:
    return random.choice(CARD_RANKS), random.choice(CARD_SUITS)


def _hand_value(hand: list[tuple[str, str]]) -> int:
    total = 0
    aces = 0
    for rank, _ in hand:
        if rank == "A":
            total += 11
            aces += 1
        elif rank in ("J", "Q", "K"):
            total += 10
        else:
            total += int(rank)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def _hand_str(hand: list[tuple[str, str]]) -> str:
    return " ".join(f"{r}{s}" for r, s in hand)


def _bj_kb(uid: int, can_hit: bool = True) -> InlineKeyboardMarkup:
    rows = []
    if can_hit:
        rows.append([
            InlineKeyboardButton(text="🃏 کارت بگیر (Hit)", callback_data=f"bj_hit:{uid}", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton(text="✋ بایست (Stand)", callback_data=f"bj_stand:{uid}", style=ButtonStyle.PRIMARY),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _start_blackjack(cb: CallbackQuery, player: dict, uid: int, stake: int):
    _set_cooldown(player)
    player["zen"] -= stake
    await asave_player(uid, player)

    player_hand = [_draw_card(), _draw_card()]
    dealer_hand = [_draw_card(), _draw_card()]
    _bj_sessions[uid] = {"stake": stake, "player": player_hand, "dealer": dealer_hand}

    p_val = _hand_value(player_hand)
    text = (
        f"🃏 **بلک‌جک** — شرط: {stake:,} Zen\n\n"
        f"👤 دستِ تو: {_hand_str(player_hand)} (مجموع: {p_val})\n"
        f"🏦 دستِ خانه: {dealer_hand[0][0]}{dealer_hand[0][1]} 🂠\n"
    )

    if p_val == 21:
        await _resolve_blackjack(cb, uid, player, forced_stand=True)
        return

    await cb.message.edit_text(text, reply_markup=_bj_kb(uid))


async def cb_bj_hit(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if cb.from_user.id != uid:
        await cb.answer("❌", show_alert=True)
        return
    session = _bj_sessions.get(uid)
    if not session:
        await cb.answer("⏰ این بازی دیگه فعال نیست.", show_alert=True)
        return
    session["player"].append(_draw_card())
    p_val = _hand_value(session["player"])
    await cb.answer()

    if p_val > 21:
        player = await aget_player(uid)
        await _resolve_blackjack(cb, uid, player, busted=True)
        return

    text = (
        f"🃏 **بلک‌جک** — شرط: {session['stake']:,} Zen\n\n"
        f"👤 دستِ تو: {_hand_str(session['player'])} (مجموع: {p_val})\n"
        f"🏦 دستِ خانه: {session['dealer'][0][0]}{session['dealer'][0][1]} 🂠\n"
    )
    await cb.message.edit_text(text, reply_markup=_bj_kb(uid))


async def cb_bj_stand(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if cb.from_user.id != uid:
        await cb.answer("❌", show_alert=True)
        return
    if uid not in _bj_sessions:
        await cb.answer("⏰ این بازی دیگه فعال نیست.", show_alert=True)
        return
    await cb.answer()
    player = await aget_player(uid)
    await _resolve_blackjack(cb, uid, player, forced_stand=True)


async def _resolve_blackjack(cb: CallbackQuery, uid: int, player: dict, busted: bool = False, forced_stand: bool = False):
    session = _bj_sessions.pop(uid, None)
    if not session:
        return
    stake = session["stake"]
    player_hand = session["player"]
    dealer_hand = session["dealer"]
    p_val = _hand_value(player_hand)

    win_zen = 0
    outcome_line = ""

    if busted:
        outcome_line = f"💥 **رد کردی (Bust)!** مجموعت {p_val} شد."
        win_zen = 0
    else:
        # خانه تا ۱۷ کارت می‌گیره
        while _hand_value(dealer_hand) < 17:
            dealer_hand.append(_draw_card())
        d_val = _hand_value(dealer_hand)
        p_bj = p_val == 21 and len(player_hand) == 2
        d_bj = d_val == 21 and len(dealer_hand) == 2

        if p_bj and not d_bj:
            win_zen = int(stake * 2.5)
            outcome_line = "🃏🎉 **بلک‌جک! (۲۱ با دو کارت)**"
        elif p_bj and d_bj:
            win_zen = stake
            outcome_line = "😐 هر دو بلک‌جک — مساوی."
        elif d_val > 21:
            win_zen = int(stake * 2)
            outcome_line = f"🎉 **خانه رد کرد ({d_val})! بردی.**"
        elif p_val > d_val:
            win_zen = int(stake * 2)
            outcome_line = f"🎉 **بردی!** ({p_val} در برابر {d_val})"
        elif p_val == d_val:
            win_zen = stake
            outcome_line = f"😐 مساوی ({p_val})."
        else:
            win_zen = 0
            outcome_line = f"💸 **باختی.** ({p_val} در برابر {d_val})"

    _, tier_bonus, _, _ = _vip_tier(player)
    if win_zen > stake and tier_bonus > 0:
        win_zen = int(win_zen * (1 + tier_bonus))

    player["zen"] = player.get("zen", 0) + win_zen
    net = win_zen - stake
    _record_wager(player, uid, stake, net)
    await asave_player(uid, player)

    text = (
        f"🃏 **بلک‌جک** — نتیجه\n\n"
        f"👤 دستِ تو: {_hand_str(player_hand)} (مجموع: {p_val})\n"
        f"🏦 دستِ خانه: {_hand_str(dealer_hand)} (مجموع: {_hand_value(dealer_hand) if not busted else '—'})\n\n"
        f"{outcome_line}\n\n"
        f"💰 موجودی فعلی: {player['zen']:,} Zen"
    )

    log_sync(
        f"🃏 **CASINO BLACKJACK** | 👤 {player.get('name','—')} (`{uid}`)\n"
        f"💰 شرط: {stake:,} | نتیجه: {net:+,} Zen",
        "CASINO"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 دوباره", callback_data=f"casino_menu:blackjack:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"casino_home:{uid}", style=ButtonStyle.PRIMARY)],
    ])
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)


# ─── registration ────────────────────────────────────────────
def register_casino_handlers(dp, bot):
    dp.message.register(cmd_casino, Command("casino"))
    dp.callback_query.register(cb_casino_home,        F.data.startswith("casino_home:"))
    dp.callback_query.register(cb_casino_menu,        F.data.startswith("casino_menu:"))
    dp.callback_query.register(cb_casino_pick,        F.data.startswith("casino_pick:"))
    dp.callback_query.register(cb_casino_stake,       F.data.startswith("casino_stake:"))
    dp.callback_query.register(cb_casino_leaderboard, F.data.startswith("casino_lb:"))
    dp.callback_query.register(cb_bj_hit,             F.data.startswith("bj_hit:"))
    dp.callback_query.register(cb_bj_stand,           F.data.startswith("bj_stand:"))
