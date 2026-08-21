# ============================================================
#  ASTRAL ABYSS — Daily Wanted System (تحت‌تعقیبِ خودکارِ روزانه) 🎯
# ------------------------------------------------------------
#  هر روز خودِ بات (نه بازیکن‌ها) رو سرِ ۳ بازیکنِ فعال جایزه می‌ذاره:
#    • اگه اون روز تو PvP ببرن → جایزه رو خودِ بانک بهشون می‌ده.
#    • اگه ببازن → مبلغِ جایزه از Zenِ خودشون کسر می‌شه (به حریفِ
#      برنده می‌رسه)؛ اگه کم بیارن، مابقی به‌صورتِ بدهی به بانک ثبت
#      می‌شه.
#    • بدهیِ پرداخت‌نشده بعد از یه مهلت، خودش رشد می‌کنه (روزی ۱۰٪).
#    • هرچی بدهی بیشتر بشه، درآمدِ Zenِ بازیکن (از apply_gold_find)
#      کمتر می‌شه — ولی هیچ‌وقت به صفر نمی‌رسه (کفِ ۴۰٪).
#
#  این ماژول کاملاً مستقل از bounty_system.py (جایزه‌ی دستیِ
#  بازیکن‌روی‌بازیکن) کار می‌کنه — اون سیستم دست‌نخورده باقی می‌مونه.
# ============================================================
import random
import time

from database import system_col, all_players, get_player, asave_player

WANTED_COUNT = 3
DAY_SECONDS = 86400

MIN_BOUNTY = 3_000
MAX_BOUNTY = 15_000
MIN_LEVEL_ELIGIBLE = 5

DEBT_GRACE_SECONDS = 24 * 3600       # ۲۴ ساعت مهلت قبل از این‌که بدهی شروع کنه به رشد
DEBT_GROWTH_PCT = 0.10               # هر دوره‌ی رشد، +۱۰٪
DEBT_GROWTH_INTERVAL = 24 * 3600     # هر ۲۴ ساعت یه بار رشد می‌کنه
DEBT_INCOME_PENALTY_PER_10K = 0.05   # هر ۱۰هزار Zen بدهی، ۵٪ از درآمد کم می‌کنه
DEBT_INCOME_FLOOR = 0.4              # حداقل ۴۰٪ درآمد همیشه می‌مونه (هیچ‌وقت صفر نمی‌شه)


# ─── ذخیره‌سازی ────────────────────────────────────────────────
def _today_key() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _doc() -> dict:
    doc = system_col().find_one({"_id": "daily_wanted"})
    if not doc:
        doc = {"_id": "daily_wanted", "date": "", "entries": []}
    return doc


def _save(doc: dict):
    data = {k: v for k, v in doc.items() if k != "_id"}
    system_col().update_one({"_id": "daily_wanted"}, {"$set": data}, upsert=True)


# ─── انتخابِ ۳ بازیکنِ روزِ جدید ─────────────────────────────────
def _pick_targets(exclude_recent: set) -> list:
    players = all_players()
    now = time.time()
    # فقط بازیکن‌های تلگرام (uid مثبت) — بازیکن‌های گپ uidِ منفی دارن و
    # این حلقه از bot تلگرام برای پیام‌دادن استفاده می‌کنه.
    pool = [
        (uid, p) for uid, p in players.items()
        if uid.lstrip("-").isdigit() and int(uid) > 0
        and p.get("level", 1) >= MIN_LEVEL_ELIGIBLE
        and uid not in exclude_recent
        and p.get("last_seen", now) > now - 7 * DAY_SECONDS  # فقط بازیکنایی که این هفته فعال بودن
    ]
    if len(pool) < WANTED_COUNT:
        # اگه بازیکنِ فعالِ کافی نبود، شرط سطح/فعالیت رو شل‌تر می‌کنیم
        pool = [
            (uid, p) for uid, p in players.items()
            if uid.lstrip("-").isdigit() and int(uid) > 0 and uid not in exclude_recent
        ] or [
            (uid, p) for uid, p in players.items()
            if uid.lstrip("-").isdigit() and int(uid) > 0
        ]

    random.shuffle(pool)
    picks = pool[:WANTED_COUNT]

    entries = []
    for uid, p in picks:
        bounty = random.randint(MIN_BOUNTY, MAX_BOUNTY) + p.get("level", 1) * 100
        entries.append({
            "uid": uid,
            "bounty": bounty,
            "resolved": False,
            "outcome": None,
            "placed_at": now,
        })
    return entries


async def ensure_daily_wanted(bot=None) -> list:
    """اگه روز عوض شده باشه، ۳ تحت‌تعقیبِ جدید انتخاب می‌کنه و (اگه bot داده
    شده باشه) بهشون پیام می‌ده. صدا زدنش idempotent-ه — اگه همون‌روزی
    که از قبل انتخاب شده دوباره صدا زده بشه، کاری نمی‌کنه."""
    doc = _doc()
    today = _today_key()
    if doc.get("date") == today and doc.get("entries"):
        return doc["entries"]

    prev_uids = {e["uid"] for e in doc.get("entries", [])}
    entries = _pick_targets(prev_uids)
    if not entries:
        return []

    new_doc = {"_id": "daily_wanted", "date": today, "entries": entries}
    _save(new_doc)

    if bot:
        for e in entries:
            try:
                await bot.send_message(
                    int(e["uid"]),
                    "🎯 **امروز تحت‌تعقیبی!**\n\n"
                    f"بانک {e['bounty']:,} Zen جایزه رو سرِ تو گذاشته!\n\n"
                    "⚔️ اگه امروز یه دوئل PvP ببری، این جایزه رو خودِ بانک بهت می‌ده.\n"
                    "💀 اگه ببازی، همین مبلغ از Zenِ خودت کسر و به حریفت داده می‌شه — "
                    "اگه کم بیاری، مابقی به‌صورتِ بدهی به بانک ثبت می‌شه.\n\n"
                    "مراقب باش، تا آخرِ امروز روی سرته! 🕒"
                )
            except Exception:
                pass

    return entries


def get_today_entries() -> list:
    doc = _doc()
    if doc.get("date") != _today_key():
        return []
    return doc.get("entries", [])


def get_wanted_entry(uid: int) -> dict:
    for e in get_today_entries():
        if e["uid"] == str(uid) and not e.get("resolved"):
            return e
    return None


def _mark_resolved(uid: int, outcome: str):
    doc = _doc()
    changed = False
    for e in doc.get("entries", []):
        if e["uid"] == str(uid) and not e.get("resolved"):
            e["resolved"] = True
            e["outcome"] = outcome
            changed = True
    if changed:
        _save(doc)


# ─── بدهیِ بانک ──────────────────────────────────────────────
def add_debt(player: dict, amount: int):
    if amount <= 0:
        return
    player["bank_debt"] = player.get("bank_debt", 0) + amount
    if not player.get("bank_debt_since"):
        player["bank_debt_since"] = time.time()


def repay_debt(player: dict, amount: int) -> int:
    """بازیکن مبلغی از بدهیش رو از Zenِ خودش پرداخت می‌کنه.
    مبلغِ واقعاً کسرشده رو برمی‌گردونه (ممکنه کمتر از amount باشه)."""
    debt = player.get("bank_debt", 0)
    if debt <= 0 or amount <= 0:
        return 0
    pay = min(amount, debt, player.get("zen", 0))
    if pay <= 0:
        return 0
    player["zen"] -= pay
    player["bank_debt"] = debt - pay
    if player["bank_debt"] <= 0:
        player["bank_debt"] = 0
        player["bank_debt_since"] = 0
        player["bank_debt_last_growth"] = 0
    return pay


def tick_debt_growth(player: dict) -> int:
    """اگه از شروعِ بدهی مهلتِ ۲۴ ساعته گذشته باشه و از آخرین رشد هم
    ۲۴ ساعت گذشته باشه، بدهی رو ۱۰٪ رشد می‌ده. مقدارِ رشد رو برمی‌گردونه
    (۰ اگه چیزی رشد نکرده). این تابع رو باید یه‌جای دوره‌ای (لوپ روزانه)
    برای همه‌ی بازیکن‌ها صدا زد."""
    debt = player.get("bank_debt", 0)
    since = player.get("bank_debt_since", 0)
    if debt <= 0 or not since:
        return 0
    now = time.time()
    if now - since < DEBT_GRACE_SECONDS:
        return 0
    last_growth = player.get("bank_debt_last_growth") or since
    if now - last_growth < DEBT_GROWTH_INTERVAL:
        return 0
    growth = int(debt * DEBT_GROWTH_PCT)
    if growth <= 0:
        growth = 1
    player["bank_debt"] = debt + growth
    player["bank_debt_last_growth"] = now
    return growth


def debt_income_multiplier(player: dict) -> float:
    """ضریبی که باید تو apply_gold_find رو درآمد ضرب بشه. هیچ‌وقت زیرِ
    DEBT_INCOME_FLOOR نمی‌ره."""
    debt = player.get("bank_debt", 0)
    if debt <= 0:
        return 1.0
    penalty = (debt / 10_000) * DEBT_INCOME_PENALTY_PER_10K
    return max(DEBT_INCOME_FLOOR, 1.0 - penalty)


# ─── قلاب به نتیجه‌ی PvP ────────────────────────────────────────
async def resolve_pvp_result(bot, winner_data: dict, winner_uid: int, loser_data: dict, loser_uid: int) -> list:
    """بعد از پایانِ هر دوئل PvP (فقط تویِ حالتِ برد/باخت، نه مساوی) صدا
    زده می‌شه. اگه برنده یا بازنده امروز تحت‌تعقیبِ خودکار بودن، حساب‌وکتابِ
    Zen/بدهی رو مستقیم رویِ دیکشنری‌هاشون اعمال می‌کنه (صداکننده باید
    خودش بعدش save_player کنه) و متنِ خط‌به‌خطِ نتیجه رو برمی‌گردونه."""
    lines = []

    w_entry = get_wanted_entry(winner_uid)
    if w_entry:
        bounty = w_entry["bounty"]
        winner_data["zen"] = winner_data.get("zen", 0) + bounty
        _mark_resolved(winner_uid, "won")
        lines.append(f"\n🎯 **تحت‌تعقیب بودی و امروز بردی!** بانک {bounty:,} Zen بهت داد.")

    l_entry = get_wanted_entry(loser_uid)
    if l_entry:
        bounty = l_entry["bounty"]
        have = loser_data.get("zen", 0)
        pay = min(have, bounty)
        shortfall = bounty - pay
        loser_data["zen"] = have - pay
        winner_data["zen"] = winner_data.get("zen", 0) + pay
        if shortfall > 0:
            add_debt(loser_data, shortfall)
            lines.append(
                f"\n💀 **تحت‌تعقیب بودی و باختی!** {pay:,} Zen پرداخت شد و چون کم آوردی، "
                f"{shortfall:,} Zenِ باقی‌مونده بدهکارِ بانک شدی (جمعِ بدهیِ فعلی: {loser_data['bank_debt']:,})."
            )
        else:
            lines.append(f"\n💀 **تحت‌تعقیب بودی و باختی!** {bounty:,} Zen جایزه پرداخت شد.")
        _mark_resolved(loser_uid, "lost")

    return lines


# ─── حلقه‌ی پس‌زمینه (انتخابِ روزانه + رشدِ بدهیِ همه) ─────────────
async def daily_wanted_loop(bot):
    import asyncio
    from database import save_player

    CHECK_INTERVAL = 1800  # هر نیم‌ساعت چک کن (روز عوض شده یا نه)
    while True:
        try:
            await ensure_daily_wanted(bot)

            # رشدِ بدهیِ همه‌ی بازیکن‌های بدهکار
            players = all_players()
            for uid_str, p in players.items():
                if p.get("bank_debt", 0) > 0:
                    grown = tick_debt_growth(p)
                    if grown > 0:
                        await asave_player(int(uid_str), p)
        except Exception:
            pass
        await asyncio.sleep(CHECK_INTERVAL)
