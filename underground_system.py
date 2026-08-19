# ============================================================
#  ASTRAL ABYSS RPG — Underground Fight Club 🩸 (حلقه‌ی سایه)
#  یه فرمِ غیررسمی و پرریسکِ PvP، جدا از رنکینگِ رسمی. یه شبح
#  به‌اسم «داور» این حلقه رو اداره می‌کنه — شایعه‌ست که خودش قبلاً
#  قربانیِ Abyss بوده و حالا رنجِ بقیه رو تماشا می‌کنه.
#  فرقش با PvP رسمی: به‌جای چند راند نبرد، یه مقایسه‌ی سریعِ قدرته،
#  و بازنده (علاوه بر Zen) ممکنه یه آیتمِ رندوم هم از دست بده.
# ============================================================
import random, time

COOLDOWN_SEC = 180
ITEM_LOSS_CHANCE = 0.5   # بازنده ۵۰٪ احتمال داره یه آیتمِ رندوم هم ببازه
VARIANCE = 0.35           # هرچقدر بیشتر، شانسِ بردِ ضعیف‌تر بیشتره (فرمول زیر)

REFEREE_LINES = [
    "🥷 داور با صدای خش‌دار می‌گه: «حلقه امشب گرسنه‌ست...»",
    "🥷 داور زمزمه می‌کنه: «آبیس هرچی رو که اینجا بریزه، فراموش می‌کنه...»",
    "🥷 داور با یه پوزخند: «قوانین اینجا رو خودِ بازنده‌ها می‌نویسن.»",
]

# ────────────────────────────────────────────────────────────
# حافظه‌ی داور — رقابت‌های شخصی + طعنه‌ی اختصاصی
# ────────────────────────────────────────────────────────────
REFEREE_REMATCH_LINES = [
    "🥷 داور می‌خنده: «باز شما دوتا؟ فکر کردم درس گرفتین...»",
    "🥷 داور با تعجب: «حلقه یادشه — این چندمین دورِ همینِ داستانه.»",
]

REFEREE_REVENGE_LINES = [
    "🥷 داور زمزمه می‌کنه: «بالاخره یکی جبران کرد... حلقه امشب یادش می‌مونه.»",
]

REFEREE_DOMINANT_LINES = [
    "🥷 داور با پوزخند به بازنده: «باز تو؟ داور دیگه اسمتو حفظ کرده...»",
]

REFEREE_STREAK_LOSS_LINES = [
    "🥷 داور با ترحم: «حلقه بهت عادت کرده، ولی نه به‌خاطرِ بردات...»",
    "🥷 داور: «شایدم وقتشه یه مدت پاتو از حلقه بکشی بیرون...»",
]

# ────────────────────────────────────────────────────────────
# عمیق‌سازیِ داور — استریکِ کلی، رکوردهای Zen، لقب‌های دائمیِ حلقه
# ────────────────────────────────────────────────────────────
STREAK_HOT_THRESHOLD = 3     # از این تعداد بردِ پیاپی، داور به «فرمِ داغ» اشاره می‌کنه
STREAK_COLD_THRESHOLD = 3    # از این تعداد باختِ پیاپی، داور با ترحم/طعنه واکنش نشون می‌ده

# لقب‌های دائمی — یه‌بار باز می‌شن و برای همیشه می‌مونن (قاطیِ titles_system می‌شن)
WIN_MILESTONES = {
    10: "🩸 تازه‌کارِ حلقه",
    25: "⚔️ جنگجوی حلقه",
    50: "🗡️ کهنه‌کارِ حلقه",
    100: "👑 افسانه‌ی حلقه‌ی سایه",
}
LOSS_MILESTONES = {
    10: "🥀 طعمه‌ی حلقه",
    25: "💀 مهمانِ همیشگیِ حلقه",
    50: "⚰️ روحِ سرگردانِ حلقه",
}

REFEREE_HOT_STREAK_LINES = [
    "🥷 داور با تحسینِ اجباری: «امشب انگار کسی نمی‌تونه جلوشو بگیره...»",
    "🥷 داور زیرِ لب: «حلقه داره یاد می‌گیره از این یکی بترسه...»",
]

REFEREE_COLD_STREAK_LINES = [
    "🥷 داور با ترحمِ ساختگی: «حلقه امشب باهات مهربون نیست...»",
    "🥷 داور: «شاید وقتشه یه نفس بکشی، قبل از این‌که حلقه چیزِ بیشتری ازت بگیره...»",
]

REFEREE_RECORD_WIN_LINES = [
    "🥷 داور با تعجبِ واقعی: «این بزرگ‌ترین چیزیه که تا حالا اینجا از یکی بردی...»",
]

REFEREE_RECORD_LOSS_LINES = [
    "🥷 داور آروم سوت می‌زنه: «این بزرگ‌ترین باختیه که تا حالا اینجا داشتی... یادش می‌مونه.»",
]

REFEREE_MILESTONE_WIN_LINES = [
    "🥷 داور با یه تعظیمِ کوچیک: «حلقه امشب یه اسمِ جدید یاد گرفت...»",
]

REFEREE_MILESTONE_LOSS_LINES = [
    "🥷 داور با یه آه: «حلقه دیگه رسماً تو رو می‌شناسه... متأسفانه نه به‌خاطرِ بردات.»",
]

REFEREE_NICKNAME_LINES = [
    "🥷 داور رو به {nick} می‌کنه: «باز اومدی؟»",
    "🥷 داور با شناخت: «{nick}... حلقه دلش برات تنگ شده بود.»",
]


def _update_streak(player: dict, won: bool) -> int:
    """استریکِ کلیِ این بازیکن تو حلقه رو به‌روز می‌کنه (مثبت=برد، منفی=باخت)
    و مقدارِ جدید رو برمی‌گردونه."""
    cur = player.get("_ug_streak", 0)
    if won:
        cur = cur + 1 if cur >= 0 else 1
    else:
        cur = cur - 1 if cur <= 0 else -1
    player["_ug_streak"] = cur
    return cur


def _check_milestone(player: dict, won: bool) -> str | None:
    """اگه همین نبرد باعثِ رسیدن به یه نقطه‌عطفِ دائمی شده، عنوانِ جدید رو
    تو underground_titles ثبت می‌کنه و برمی‌گردونه، وگرنه None."""
    table = WIN_MILESTONES if won else LOSS_MILESTONES
    count = player.get("underground_wins" if won else "underground_losses", 0)
    title = table.get(count)
    if not title:
        return None
    titles = player.setdefault("underground_titles", [])
    if title in titles:
        return None
    titles.append(title)
    return title


def _check_record_stake(player: dict, won: bool, amount: int) -> bool:
    """اگه این بزرگ‌ترین بردِ/باختِ Zenِ این بازیکن تو حلقه بوده، رکورد رو
    به‌روز می‌کنه و True برمی‌گردونه (فقط اگه رکوردِ قبلی هم واقعاً وجود
    داشته — تا اولین نبردِ هرکسی «رکورد» حساب نشه)."""
    if amount <= 0:
        return False
    key = "_ug_biggest_win" if won else "_ug_biggest_loss"
    prev = player.get(key, 0)
    player[key] = max(prev, amount)
    return amount > prev and prev > 0


def best_underground_title(player: dict) -> str | None:
    titles = player.get("underground_titles", [])
    return titles[-1] if titles else None


def _record_rivalry(challenger: dict, target: dict, challenger_won: bool):
    """حافظه‌ی دوطرفه‌ی رقابت رو بین این دو نفر به‌روز می‌کنه."""
    c_hist = challenger.setdefault("_ug_rivalry", {})
    t_hist = target.setdefault("_ug_rivalry", {})
    c_key, t_key = str(target["id"]), str(challenger["id"])
    c_rec = c_hist.setdefault(c_key, {"wins": 0, "losses": 0})
    t_rec = t_hist.setdefault(t_key, {"wins": 0, "losses": 0})
    if challenger_won:
        c_rec["wins"] += 1
        t_rec["losses"] += 1
    else:
        c_rec["losses"] += 1
        t_rec["wins"] += 1
    return c_rec, t_rec


def judge_taunt(winner: dict, loser: dict, ctx: dict) -> str:
    """بر اساسِ تاریخچه‌ی رقابت، استریک، رکوردها و نقطه‌عطف‌های دائمیِ این
    دو نفر، یه طعنه‌ی شخصی‌سازی‌شده از زبونِ داور انتخاب می‌کنه. اولویت با
    اتفاق‌های بزرگ‌تره (لقبِ دائمی > رکورد > رقابتِ شخصی > استریک > عمومی)."""
    winner_vs_loser = ctx["winner_vs_loser"]
    total_between = winner_vs_loser["wins"] + winner_vs_loser["losses"]
    loser_total_losses = loser.get("underground_losses", 0)
    wname, lname = winner.get("name", "—"), loser.get("name", "—")

    if ctx.get("loser_milestone"):
        line = random.choice(REFEREE_MILESTONE_LOSS_LINES)
        return f"{line}\n🏅 لقبِ جدیدِ **{lname}**: {ctx['loser_milestone']}"

    if ctx.get("winner_milestone"):
        line = random.choice(REFEREE_MILESTONE_WIN_LINES)
        return f"{line}\n🏅 لقبِ جدیدِ **{wname}**: {ctx['winner_milestone']}"

    if winner_vs_loser["losses"] >= 2 and winner_vs_loser["wins"] == 1:
        line = random.choice(REFEREE_REVENGE_LINES)
        return f"{line}\n🗡️ **{wname}** بالاخره جلوی **{lname}** جبران کرد."

    if winner_vs_loser["wins"] >= 3 and winner_vs_loser["losses"] == 0:
        line = random.choice(REFEREE_DOMINANT_LINES)
        return f"{line}\n💀 این {winner_vs_loser['wins']}اُمین باختِ **{lname}** جلوی همین حریفه."

    if ctx.get("winner_record"):
        line = random.choice(REFEREE_RECORD_WIN_LINES)
        return f"{line}\n💰 بزرگ‌ترین بردِ Zenِ **{wname}** تو حلقه تا الان."

    if ctx.get("loser_record"):
        line = random.choice(REFEREE_RECORD_LOSS_LINES)
        return f"{line}\n💸 بزرگ‌ترین باختِ Zenِ **{lname}** تو حلقه تا الان."

    if ctx.get("winner_streak", 0) >= STREAK_HOT_THRESHOLD:
        line = random.choice(REFEREE_HOT_STREAK_LINES)
        return f"{line}\n🔥 **{wname}** الان {ctx['winner_streak']} برد پشتِ‌سرِ همه."

    if ctx.get("loser_streak", 0) <= -STREAK_COLD_THRESHOLD:
        line = random.choice(REFEREE_COLD_STREAK_LINES)
        return f"{line}\n🧊 **{lname}** الان {-ctx['loser_streak']} باختِ پشتِ‌سرِهم داره."

    if total_between >= 2:
        line = random.choice(REFEREE_REMATCH_LINES)
        return f"{line}\n📜 رکوردِ این دو تو حلقه: {winner_vs_loser['wins']}-{winner_vs_loser['losses']}"

    if loser_total_losses >= 5:
        line = random.choice(REFEREE_STREAK_LOSS_LINES)
        return f"{line}\n📉 مجموع باخت‌های **{lname}** تو حلقه: {loser_total_losses}"

    loser_nick = best_underground_title(loser)
    if loser_nick and random.random() < 0.4:
        return random.choice(REFEREE_NICKNAME_LINES).format(nick=loser_nick)

    return random.choice(REFEREE_LINES)


def can_fight(player: dict) -> tuple[bool, str]:
    remain = int(player.get("_underground_cd", 0) - time.time())
    if remain > 0:
        return False, f"⏳ {remain} ثانیه‌ی دیگه دوباره وارد حلقه شو."
    return True, ""


def _set_cooldown(player: dict):
    player["_underground_cd"] = time.time() + COOLDOWN_SEC


def resolve_fight(challenger: dict, target: dict, stake: int) -> dict:
    """مقایسه‌ی سریعِ قدرت — برنده رو با شانسِ نسبی به قدرت تعیین می‌کنه."""
    from combat_power import calculate_combat_power
    _set_cooldown(challenger)

    p1 = max(1, calculate_combat_power(challenger))
    p2 = max(1, calculate_combat_power(target))
    # شانسِ بردِ چالش‌دهنده — با کمی واریانس تا ضعیف‌تر هم شانس داشته باشه
    base_prob = p1 / (p1 + p2)
    win_prob = base_prob * (1 - VARIANCE) + 0.5 * VARIANCE
    win_prob = max(0.1, min(0.9, win_prob))

    challenger_wins = random.random() < win_prob
    winner, loser = (challenger, target) if challenger_wins else (target, challenger)

    # Zen
    stake = min(stake, loser.get("zen", 0))
    winner["zen"] = winner.get("zen", 0) + stake
    loser["zen"] = loser.get("zen", 0) - stake

    # 😡 آبیس عصبانیه — اگه زنجیره‌ی underground_surge فعال باشه، داور
    # یه بونوسِ اضافه (از خودِ آبیس، نه از جیبِ بازنده) به برنده می‌ده.
    bonus_zen = 0
    try:
        from world_pulse import underground_stake_bonus
        bonus_pct = underground_stake_bonus()
        if bonus_pct > 0:
            bonus_zen = int(stake * bonus_pct)
            winner["zen"] = winner.get("zen", 0) + bonus_zen
    except Exception:
        pass

    # آیتم
    lost_item = None
    if random.random() < ITEM_LOSS_CHANCE:
        inv = loser.get("inventory", [])
        if inv:
            idx = random.randrange(len(inv))
            lost_item = inv.pop(idx)
            winner.setdefault("inventory", []).append(lost_item)

    winner["underground_wins"] = winner.get("underground_wins", 0) + 1
    loser["underground_losses"] = loser.get("underground_losses", 0) + 1

    winner_streak = _update_streak(winner, won=True)
    loser_streak = _update_streak(loser, won=False)

    winner_milestone = _check_milestone(winner, won=True)
    loser_milestone = _check_milestone(loser, won=False)

    total_payout = stake + bonus_zen
    winner_record = _check_record_stake(winner, won=True, amount=total_payout)
    loser_record = _check_record_stake(loser, won=False, amount=stake)

    c_rec, t_rec = _record_rivalry(challenger, target, challenger_wins)
    winner_vs_loser = c_rec if challenger_wins else t_rec

    ctx = {
        "winner_vs_loser": winner_vs_loser,
        "winner_streak": winner_streak, "loser_streak": loser_streak,
        "winner_milestone": winner_milestone, "loser_milestone": loser_milestone,
        "winner_record": winner_record, "loser_record": loser_record,
    }
    judge_line = judge_taunt(winner, loser, ctx)

    return {
        "winner_id": winner["id"], "loser_id": loser["id"],
        "challenger_won": challenger_wins,
        "stake": stake, "lost_item": lost_item,
        "win_prob": win_prob,
        "judge_line": judge_line,
        "bonus_zen": bonus_zen,
        "winner_milestone": winner_milestone,
        "loser_milestone": loser_milestone,
    }
