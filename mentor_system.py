# ============================================================
#  ASTRAL ABYSS RPG — Mentor System 🎓
#  بازیکن‌های باتجربه (Lv.12+) می‌تونن یه تازه‌وارد (Lv.5-) رو شاگرد
#  خودشون کنن. تا وقتی فعاله: شاگرد +۱۵٪ XP، استاد +۵٪ XP.
#  وقتی شاگرد به Lv.12 برسه، «فارغ‌التحصیل» می‌شه و هردو یه پاداش
#  یک‌باره‌ی بزرگ می‌گیرن.
# ============================================================
MENTOR_MIN_LEVEL   = 12
MENTEE_MAX_LEVEL   = 5
GRADUATE_LEVEL      = 12
MAX_MENTEES         = 2

MENTEE_XP_BONUS = 0.15
MENTOR_XP_BONUS = 0.05

GRADUATE_MENTOR_ZEN = 5000
GRADUATE_MENTOR_XP  = 1500
GRADUATE_MENTEE_ZEN = 2000


def eligible_mentor(player: dict) -> bool:
    return player.get("level", 1) >= MENTOR_MIN_LEVEL


def eligible_mentee(player: dict) -> bool:
    return player.get("level", 1) <= MENTEE_MAX_LEVEL and not player.get("mentee_of")


def mentor_slots_left(mentor: dict) -> int:
    return MAX_MENTEES - len(mentor.get("mentor_of", []))


def start_mentorship(mentor: dict, mentee: dict):
    mentor.setdefault("mentor_of", [])
    if mentee["id"] not in mentor["mentor_of"]:
        mentor["mentor_of"].append(mentee["id"])
    mentee["mentee_of"] = mentor["id"]
    mentee["mentor_start_level"] = mentee.get("level", 1)


def end_mentorship(mentor: dict, mentee: dict):
    if mentor and mentee["id"] in mentor.get("mentor_of", []):
        mentor["mentor_of"].remove(mentee["id"])
    mentee["mentee_of"] = None
    mentee.pop("mentor_start_level", None)


def is_ready_to_graduate(mentee: dict) -> bool:
    return bool(mentee.get("mentee_of")) and mentee.get("level", 1) >= GRADUATE_LEVEL


def mentee_xp_bonus(player: dict) -> float:
    return MENTEE_XP_BONUS if player.get("mentee_of") else 0.0


def mentor_xp_bonus(player: dict) -> float:
    return MENTOR_XP_BONUS if player.get("mentor_of") else 0.0


# ============================================================
#  🔗 لحظه‌های باندینگ — قبلاً کل رابطه فقط یه بافِ XP بی‌صدا بود و
#  تنها لحظه‌ی «واقعی»‌ش فارغ‌التحصیلیِ نهایی بود. الان هر چند سطح
#  که شاگرد پیشرفت می‌کنه (نه فقط سطحِ آخر)، یه پاداشِ کوچیکِ مشترک
#  می‌گیرن — تا رابطه حسِ زنده‌بودن داشته باشه، نه فقط یه ضریب.
# ============================================================
BOND_MILESTONE_EVERY = 3     # هر ۳ سطح که شاگرد بالا بره یه لحظه‌ی باند فعال می‌شه
BOND_MENTOR_ZEN = 800
BOND_MENTEE_ZEN = 400
BOND_MENTOR_XP  = 150
BOND_MENTEE_XP  = 100

BOND_MOMENT_LINES = [
    "استادت یه‌بار دیگه بهت افتخار کرد.",
    "این پیشرفت رو استادت هم حس کرد.",
    "یه قدمِ دیگه به فارغ‌التحصیلی نزدیک‌تر شدی.",
]


def check_bond_milestone(mentor: dict, mentee: dict) -> list[str]:
    """بعدِ هر level-upِ شاگردی که استاد داره صدا زده می‌شه. اگه از آخرین
    مایل‌استون BOND_MILESTONE_EVERY سطح گذشته باشه، به هردو پاداشِ کوچیک
    می‌ده و متنِ نمایشی برمی‌گردونه؛ وگرنه لیستِ خالی."""
    if not mentor or not mentee.get("mentee_of"):
        return []
    start = mentee.get("mentor_start_level", mentee.get("level", 1))
    last_milestone = mentee.get("mentor_last_milestone_level", start)
    level = mentee.get("level", 1)
    if level - last_milestone < BOND_MILESTONE_EVERY:
        return []

    mentee["mentor_last_milestone_level"] = level
    mentor["zen"] = mentor.get("zen", 0) + BOND_MENTOR_ZEN
    mentor["xp"]  = mentor.get("xp", 0) + BOND_MENTOR_XP
    mentee["zen"] = mentee.get("zen", 0) + BOND_MENTEE_ZEN
    mentee["xp"]  = mentee.get("xp", 0) + BOND_MENTEE_XP
    import random
    line = random.choice(BOND_MOMENT_LINES)
    return [
        f"🔗 **لحظه‌ی باند!** {line}",
        f"👨‍🏫 استاد: +{BOND_MENTOR_ZEN:,} Zen | +{BOND_MENTOR_XP} XP",
        f"🎓 شاگرد: +{BOND_MENTEE_ZEN:,} Zen | +{BOND_MENTEE_XP} XP",
    ]


# ─── عنوانِ استادی — بر اساسِ تعدادِ شاگردهایی که فارغ‌التحصیل کردی ───
MENTOR_TITLES = [
    (10, "🏆 استادِ افسانه‌ای"),
    (5,  "🌟 استادِ کاردان"),
    (2,  "🎓 استادِ باتجربه"),
    (1,  "🎓 استادِ نوپا"),
]


def mentor_title(player: dict) -> str | None:
    count = player.get("graduated_mentee_count", 0)
    for threshold, title in MENTOR_TITLES:
        if count >= threshold:
            return title
    return None


def available_mentors(exclude_uid: int, limit: int = 8) -> list[dict]:
    """برای شاگردهای بالقوه: لیستِ استادهای واجدشرایط که هنوز جا دارن،
    مرتب‌شده بر اساسِ سطح (بالاترین اول). فقط تو mentor_handlers صدا
    زده می‌شه (نه اینجا import می‌شه، تا وابستگیِ چرخه‌ای پیش نیاد)."""
    from database import all_players
    players = all_players()
    out = []
    for pid, p in players.items():
        if int(pid) == exclude_uid:
            continue
        if eligible_mentor(p) and mentor_slots_left(p) > 0:
            out.append(p)
    out.sort(key=lambda p: p.get("level", 1), reverse=True)
    return out[:limit]
