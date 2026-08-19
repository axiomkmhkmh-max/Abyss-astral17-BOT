# ============================================================
#  ASTRAL ABYSS — GROUP SYSTEM
# ------------------------------------------------------------
#  سیستمِ مخصوصِ گپ‌های گروهی، جدا از هر فایلِ دیگه‌ای — هیچ فایلِ
#  قبلی رو تغییر نمی‌ده. دو تیکه‌ست:
#
#   ۱) رِیدِ باسِ گروهی: هر گروه/سوپرگروه یه باسِ مستقل و مالِ خودش
#      داره (نه باسِ جهانیِ سراسری‌ای که تو boss_system هست). از
#      خودِ boss_engine.py (فرمول‌ها، فازها، پاداش‌ها) استفاده می‌کنه
#      — فقط ذخیره‌سازیش به‌جای یه سند سراسری، به‌ازای هر chat_id
#      جداست. یعنی هم‌زمان تو ۵۰ گروه مختلف می‌تونه ۵۰ باسِ متفاوت
#      زنده باشه، هرکدوم مستقل از بقیه.
#
#   ۲) عضویتِ گروه + رتبه‌بندیِ مخصوصِ گروه: هر بار یه بازیکن تو یه
#      گروه پیام می‌ده، حضورش ثبت می‌شه (بدون هیچ دیتای اضافه یا
#      حساسی — فقط chat_id + user_id + آخرین‌باری که دیده شده).
#      این باعث می‌شه /gtop بتونه فقط اعضایی که واقعاً تو همون گروه
#      فعالن رو رتبه‌بندی کنه، نه کلِ بازیکن‌های ربات رو.
# ============================================================
import time
from pymongo.collection import Collection

from database import get_db, get_player

GROUP_BOSS_RESPAWN_COOLDOWN = 600  # بعد کشتنِ باسِ یه گروه، ۱۰ دقیقه صبر تا رِیدِ بعدی
GROUP_MEMBER_MAX_AGE_DAYS = 90      # اعضایی که بیش از ۹۰ روزه تو گروه پیام ندادن، تو /gtop حساب نمی‌شن


def group_boss_col() -> Collection:
    return get_db()["group_bosses"]


def group_members_col() -> Collection:
    return get_db()["group_members"]


# ────────────────────────────────────────────────────────────
# رِیدِ باسِ گروهی
# ────────────────────────────────────────────────────────────

def get_group_boss(chat_id: int) -> dict | None:
    doc = group_boss_col().find_one({"_id": chat_id})
    if not doc:
        return None
    doc.pop("_id", None)
    return doc


def save_group_boss(chat_id: int, boss: dict):
    data = {k: v for k, v in boss.items() if k != "_id"}
    group_boss_col().update_one({"_id": chat_id}, {"$set": data}, upsert=True)


def mark_group_boss_killed(chat_id: int):
    group_boss_col().update_one(
        {"_id": chat_id},
        {"$set": {"alive": False, "_last_killed_at": time.time()}},
        upsert=True,
    )


def group_boss_cooldown_remaining(chat_id: int) -> int:
    """اگه گروه هنوز تو کول‌داونِ بعدِ کشتنِ باسِ قبلیشه، ثانیه‌ی باقیمونده رو می‌ده؛ وگرنه ۰."""
    doc = group_boss_col().find_one({"_id": chat_id})
    if not doc:
        return 0
    last_killed = doc.get("_last_killed_at")
    if not last_killed:
        return 0
    remain = int(last_killed + GROUP_BOSS_RESPAWN_COOLDOWN - time.time())
    return max(0, remain)


def spawn_group_boss(chat_id: int, template_id: str | None = None) -> dict:
    """یه باسِ تازه مخصوصِ این چت می‌سازه (با همون موتور/فرمول‌های boss_engine)."""
    import random
    import boss_engine as be
    if not template_id or template_id not in be.WORLD_BOSS_TEMPLATES:
        template_id = random.choice(list(be.WORLD_BOSS_TEMPLATES.keys()))
    boss = be.spawn_boss(template_id, chat_id)
    boss["invited_uids"] = []  # کسانی که با /binvite از بیرونِ گروه دعوت شدن و اجازه‌ی زدن از پی‌وی خودشون رو دارن
    save_group_boss(chat_id, boss)
    return boss


def list_active_group_bosses() -> list[dict]:
    """برای واچرِ پس‌زمینه (سپر/حمله‌ی ناحیه‌ای/خشم) — همه‌ی باس‌های گروهیِ زنده."""
    out = []
    for doc in group_boss_col().find({"alive": True}):
        chat_id = doc.pop("_id")
        doc["chat_id"] = chat_id
        out.append(doc)
    return out


# ────────────────────────────────────────────────────────────
# عضویتِ گروه + رتبه‌بندی
# ────────────────────────────────────────────────────────────

def touch_group_member(chat_id: int, user_id: int):
    group_members_col().update_one(
        {"_id": f"{chat_id}:{user_id}"},
        {"$set": {"chat_id": chat_id, "user_id": user_id, "last_seen": time.time()}},
        upsert=True,
    )


def get_group_member_ids(chat_id: int, max_age_days: int = GROUP_MEMBER_MAX_AGE_DAYS) -> list[int]:
    cutoff = time.time() - max_age_days * 86400
    docs = group_members_col().find({"chat_id": chat_id, "last_seen": {"$gte": cutoff}})
    return [d["user_id"] for d in docs]


def known_group_chat_ids(max_age_days: int = GROUP_MEMBER_MAX_AGE_DAYS) -> list[int]:
    """لیستِ chat_idِ همه‌ی گروه‌هایی که ربات توش دیده شده (برای /gbroadcast).
    منبعش همون رکوردهایی‌ه که touch_group_member هر بار یه نفر تو گروه فعالیت
    می‌کنه می‌سازه — نیازی به هندلرِ جدا برای my_chat_member نیست."""
    cutoff = time.time() - max_age_days * 86400
    return group_members_col().distinct("chat_id", {"last_seen": {"$gte": cutoff}})


def _guild_tag(p: dict) -> str:
    """اسمِ اولین گیلدی که پلیر توش عضوه (اگه عضو هیچ گیلدی نباشه، رشته‌ی خالی)."""
    guilds = p.get("guilds") or {}
    if not guilds:
        return ""
    try:
        from guild_system import GUILDS
        gid = next(iter(guilds))
        return GUILDS.get(gid, {}).get("name", "")
    except Exception:
        return ""


def _league_name(p: dict) -> str:
    try:
        from pvp import league_for_points
        return league_for_points(p.get("pvp_season_points", 0))
    except Exception:
        return ""


SORT_KEYS = {
    "level": lambda r: (-r["level"], -r["zen"]),
    "zen": lambda r: (-r["zen"], -r["level"]),
    "pvp": lambda r: (-r["pvp_wins"], -r["level"]),
}


def get_group_leaderboard(chat_id: int, limit: int = 10, sort_by: str = "level") -> list[dict]:
    """رتبه‌بندیِ اعضایی که تو همین گروه فعالن (نه کلِ سرور)."""
    rows = []
    for uid in get_group_member_ids(chat_id):
        p = get_player(uid)
        if not p or not p.get("character"):
            continue
        rows.append({
            "user_id": uid,
            "name": p.get("name", "—"),
            "level": p.get("level", 1),
            "zen": p.get("zen", 0),
            "kills": p.get("kills", 0),
            "pvp_wins": p.get("pvp_wins", 0),
            "guild": _guild_tag(p),
            "league": _league_name(p),
        })
    rows.sort(key=SORT_KEYS.get(sort_by, SORT_KEYS["level"]))
    return rows[:limit]


def top_contributors(boss: dict, n: int = 3) -> list[tuple[int, int]]:
    """(uid, dmg) — بیشترین‌ ضربه‌زن‌های همین لحظه‌ی رِید، برای نمایشِ زنده حینِ نبرد."""
    contributors = boss.get("contributors", {})
    ranked = sorted(contributors.items(), key=lambda kv: kv[1].get("dmg", 0), reverse=True)
    return [(int(uid), c.get("dmg", 0)) for uid, c in ranked[:n]]
