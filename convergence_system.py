# ============================================================
#  ASTRAL ABYSS — Convergence Event 🌌 (رخدادِ هم‌گراییِ جهانی)
# ------------------------------------------------------------
#  یه «شکافِ هم‌گرایی» سراسری باز می‌شه که تهدید می‌کنه کلِ Abyss رو
#  ببلعه. تنها راهِ بستنش اینه که همه‌ی بازیکن‌ها با هم Zen/Echo Shard
#  «تقدیم» کنن تا نوارِ سراسری پر بشه. این تنها حالتیه که موفقیتِ یه
#  نفر مستقیم به مشارکتِ بقیه‌ی سرور وابسته‌ست — حسِ زنده‌بودنِ سرور.
#
#  ۴ مایل‌استون (۲۵٪ ۵۰٪ ۷۵٪ ۱۰۰٪) هر کدوم یه اعلانِ سراسری دارن.
#  در ۱۰۰٪: پاداشِ Zen به‌نسبتِ سهمِ مشارکتِ هرکس تقسیم می‌شه + به
#  ۱۰ نفرِ برترِ مشارکت‌کننده یه تجهیزاتِ افسانه‌ای/اسطوره‌ای هدیه
#  داده می‌شه. اگه رخداد خیلی طول بکشه (MAX_DURATION) بدونِ رسیدن
#  به ۱۰۰٪، به‌صورتِ ناقص بسته می‌شه و جایزه‌ی نسبیِ کوچیک‌تری
#  پخش می‌شه — تا تلاش‌های مردم کاملاً هدر نره.
#
#  این فایل هم منطق و هم حلقه‌ی پس‌زمینه رو داره (هم‌الگو با
#  weekly_rewards.py).
# ============================================================
import asyncio
import time
from database import aget_player, asave_player

CHECK_INTERVAL = 1800            # هر ۳۰ دقیقه چک می‌شه
COOLDOWN_AFTER_CLOSE = 3 * 86400 # حداقل ۳ روز بینِ دو رخداد
MAX_DURATION = 10 * 86400        # اگه ۱۰ روزه تموم نشد، ناقص بسته می‌شه

TARGET_UNITS = 2_000_000         # هدفِ کلِ سرور
ZEN_UNIT = 1                     # هر ۱ Zen = ۱ واحد
SHARD_UNIT = 150                 # هر ۱ Echo Shard = ۱۵۰ واحد (کمیاب‌تره)

MILESTONES = [25, 50, 75, 100]

REWARD_POOL_FULL = 600_000       # کلِ Zenِ توزیع‌شونده اگه ۱۰۰٪ کامل بشه
REWARD_POOL_PARTIAL_RATIO = 0.4  # اگه ناقص بسته بشه، فقط این نسبت از استخر پخش می‌شه
TOP_CONTRIBUTOR_ITEM_COUNT = 10


def _state_col():
    from database import system_col
    return system_col()


def _default_state() -> dict:
    return {
        "_id": "convergence_event",
        "active": False,
        "event_num": 0,
        "progress": 0,
        "target": TARGET_UNITS,
        "contributors": {},       # {uid_str: units}
        "milestones_hit": [],
        "started_at": 0,
        "closed_at": 0,
    }


def get_state() -> dict:
    doc = _state_col().find_one({"_id": "convergence_event"})
    if not doc:
        doc = _default_state()
        _state_col().update_one({"_id": "convergence_event"}, {"$set": doc}, upsert=True)
    return doc


def _save_state(state: dict):
    _state_col().update_one({"_id": "convergence_event"}, {"$set": state}, upsert=True)


def is_active() -> bool:
    return get_state().get("active", False)


def start_event() -> dict:
    state = get_state()
    state["active"] = True
    state["event_num"] = state.get("event_num", 0) + 1
    state["progress"] = 0
    state["target"] = TARGET_UNITS
    state["contributors"] = {}
    state["milestones_hit"] = []
    state["started_at"] = time.time()
    state["closed_at"] = 0
    _save_state(state)
    return state


def can_contribute(player: dict, kind: str, amount: int) -> tuple[bool, str]:
    if amount <= 0:
        return False, "❌ مقدار باید بیشتر از صفر باشه."
    if kind == "zen":
        if player.get("zen", 0) < amount:
            return False, f"❌ Zen کافی نداری (داری: {player.get('zen',0):,})."
    elif kind == "shard":
        if player.get("rift_shards", 0) < amount:
            return False, f"❌ Echo Shard کافی نداری (داری: {player.get('rift_shards',0):,})."
    else:
        return False, "❌ نوعِ نامعتبر."
    return True, ""


def contribute(uid: int, player: dict, kind: str, amount: int) -> dict:
    """کسر از پلیر + اضافه‌کردن به نوارِ سراسری. خروجی شاملِ مایل‌استون‌های
    عبورشده و اینکه آیا رخداد کامل شد یا نه. player رو خودِ کالر باید save کنه."""
    ok, why = can_contribute(player, kind, amount)
    if not ok:
        return {"ok": False, "message": why}

    state = get_state()
    if not state.get("active"):
        return {"ok": False, "message": "❌ الان رخدادِ هم‌گراییِ فعالی وجود نداره."}

    if kind == "zen":
        player["zen"] -= amount
        units = amount * ZEN_UNIT
    else:
        player["rift_shards"] -= amount
        units = amount * SHARD_UNIT

    before_pct = int(state["progress"] / state["target"] * 100)
    state["progress"] = min(state["target"], state["progress"] + units)
    after_pct = int(state["progress"] / state["target"] * 100)

    uid_str = str(uid)
    state["contributors"][uid_str] = state["contributors"].get(uid_str, 0) + units

    crossed = [m for m in MILESTONES if before_pct < m <= after_pct and m not in state["milestones_hit"]]
    for m in crossed:
        state["milestones_hit"].append(m)

    completed = state["progress"] >= state["target"]
    _save_state(state)

    player.setdefault("convergence_stats", {"total_units": 0, "events_participated": 0})
    if player["convergence_stats"].get("last_event_num") != state["event_num"]:
        player["convergence_stats"]["events_participated"] = player["convergence_stats"].get("events_participated", 0) + 1
        player["convergence_stats"]["last_event_num"] = state["event_num"]
    player["convergence_stats"]["total_units"] = player["convergence_stats"].get("total_units", 0) + units

    return {
        "ok": True,
        "units": units,
        "progress": state["progress"],
        "target": state["target"],
        "pct": after_pct,
        "milestones_crossed": crossed,
        "completed": completed,
    }


def progress_bar(state: dict, length: int = 14) -> str:
    pct = state["progress"] / max(1, state["target"])
    filled = round(pct * length)
    return "🟪" * filled + "⬛" * (length - filled)


def status_text(player: dict | None = None) -> str:
    state = get_state()
    if not state.get("active"):
        return (
            "🌌 **رخدادِ هم‌گرایی**\n\n"
            "الان هیچ شکافِ سراسری‌ای باز نیست. رخدادِ بعدی به‌زودی خودش باز می‌شه —\n"
            "وقتی باز شد، همه‌ی بازیکن‌ها می‌تونن Zen یا 🔹Echo Shard تقدیم کنن تا\n"
            "قبل از بسته‌شدنِ زمانش، شکاف بسته بشه."
        )
    pct = int(state["progress"] / state["target"] * 100)
    lines = [
        f"🌌 **رخدادِ هم‌گراییِ #{state['event_num']}**",
        "یه شکافِ سراسری باز شده — همه با هم باید ببندیمش!\n",
        f"{progress_bar(state)} {pct}٪",
        f"📊 {state['progress']:,} / {state['target']:,}",
        f"👥 مشارکت‌کننده‌ها: {len(state['contributors'])}",
    ]
    remaining = MAX_DURATION - (time.time() - state["started_at"])
    if remaining > 0:
        days = int(remaining // 86400)
        lines.append(f"⏳ زمانِ باقی‌مونده: {days} روز")
    if player is not None:
        my_units = state["contributors"].get(str(player.get("id", 0)), 0)
        if my_units:
            lines.append(f"\n🙋 مشارکتِ من: {my_units:,} واحد")
    return "\n".join(lines)


def get_top_contributors(n: int = 10) -> list[tuple[str, int]]:
    state = get_state()
    ranked = sorted(state["contributors"].items(), key=lambda kv: kv[1], reverse=True)
    return ranked[:n]


async def close_event(bot, partial: bool = False):
    """رخداد رو می‌بنده: پاداش رو به‌نسبتِ سهمِ هرکس پخش می‌کنه، به تاپ‌ده
    آیتم می‌ده، همه رو مطلع می‌کنه، و رخداد رو inactive می‌کنه."""
    from database import get_player, save_player, player_lock
    from item_system import generate_random_equipment, merge_into_inventory

    state = get_state()
    if not state.get("active"):
        return
    contributors = state["contributors"]
    total_units = sum(contributors.values()) or 1
    pool = int(REWARD_POOL_FULL * (REWARD_POOL_PARTIAL_RATIO if partial else 1.0))

    ranked = sorted(contributors.items(), key=lambda kv: kv[1], reverse=True)

    for i, (uid_str, units) in enumerate(ranked):
        uid = int(uid_str)

        # ─── باگ‌فیکس: قبلاً get_player→تغییر→save_player اینجا بدونِ
        # player_lock بود — یعنی اگه دقیقاً همون لحظه‌ای که رخداد بسته
        # می‌شد، بازیکن داشت یه اکشنِ دیگه (حمله/لوت/...) هم می‌زد، اون
        # اکشنِ دیگه می‌تونست با یه کپیِ قدیمی از player، بعد از سیوِ
        # اینجا دوباره سیو کنه و پاداش/آیتمِ همین رخداد رو خاموش پاک کنه
        # (بازیکن پیامِ «آیتم گرفتی» رو می‌دید ولی تو اینونتوری نبود).
        # الان کلِ بلاک زیرِ player_lock(uid) رفته، دقیقاً مثلِ الگوی
        # bank_system.py — هیچ اکشنِ دیگه‌ای رو همین بازیکن نمی‌تونه
        # هم‌زمان بنویسه.
        async with player_lock(uid):
            player = await aget_player(uid)
            if not player:
                continue
            share = units / total_units
            reward = max(500, int(pool * share))
            player["zen"] = player.get("zen", 0) + reward

            got_item = False
            if i < TOP_CONTRIBUTOR_ITEM_COUNT:
                rarity = "mythic" if i < 3 else "legendary"
                try:
                    item = generate_random_equipment(player.get("level", 1), forced_rarity=rarity)
                    merge_into_inventory(player.setdefault("inventory", []), item)
                    got_item = True
                except Exception:
                    pass

            await asave_player(uid, player)
        try:
            status = "🎉 **رخداد با موفقیت بسته شد!**" if not partial else "⏳ **زمانِ رخداد تموم شد (ناقص بسته شد).**"
            txt = (
                f"{status}\n\n"
                f"مشارکتِ تو: {units:,} واحد (رتبه‌ی #{i+1})\n"
                f"🎁 پاداش: +{reward:,} Zen"
            )
            if got_item:
                txt += f"\n💠 یه تجهیزاتِ {'اسطوره‌ای' if rarity=='mythic' else 'افسانه‌ای'} هم گرفتی!"
            await bot.send_message(uid, txt)
        except Exception:
            pass

    state["active"] = False
    state["closed_at"] = time.time()
    _save_state(state)

    from logger import log_sync
    log_sync(
        f"🌌 **CONVERGENCE #{state['event_num']} CLOSED** ({'partial' if partial else 'full'})\n"
        f"مشارکت‌کننده‌ها: {len(contributors)} | مجموع واحد: {total_units:,}",
        "CONVERGENCE"
    )


async def _broadcast_milestone(bot, state: dict, pct: int):
    from database import all_players
    text = (
        f"🌌 **رخدادِ هم‌گرایی #{state['event_num']} — {pct}٪ بسته شد!**\n"
        f"{progress_bar(state)}\n"
        "به تقدیم‌کردن ادامه بدید، هر واحدی مهمه."
    )
    for uid_str in list(state["contributors"].keys()):
        try:
            await bot.send_message(int(uid_str), text)
        except Exception:
            pass


async def convergence_loop(bot):
    while True:
        try:
            state = get_state()
            if not state.get("active"):
                if time.time() - state.get("closed_at", 0) >= COOLDOWN_AFTER_CLOSE:
                    start_event()
            else:
                if state["progress"] >= state["target"]:
                    await close_event(bot, partial=False)
                elif time.time() - state["started_at"] >= MAX_DURATION:
                    await close_event(bot, partial=True)
        except Exception:
            pass
        await asyncio.sleep(CHECK_INTERVAL)
