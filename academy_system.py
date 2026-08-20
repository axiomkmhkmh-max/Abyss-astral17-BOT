# ============================================================
#  ASTRAL ABYSS — Academy Arc 🎓 (فصلِ آکادمی)
# ------------------------------------------------------------
#  یه فصلِ محدود و اختیاری شبیهِ آکادمی‌های جادوگریِ ایسکای‌ها:
#  بازیکن ثبت‌نام می‌کنه، کلاس‌های درسی می‌ره (پسیوِ کول‌داون‌دار،
#  بونوسِ استتِ کوچیکِ تدریجی می‌ده)، امتیازِ آکادمی جمع می‌کنه
#  (رقابتِ دانش‌آموزی/لیدربورد)، و آخرِ هر سال یه امتحانِ نهایی
#  می‌ده. ۳ سال تمومه — فارغ‌التحصیلی یه عنوانِ دائمی می‌ده.
#
#  دیتا: player["academy"] = {
#      "enrolled": bool, "year": int, "subjects": {id:int},
#      "academy_points": int, "graduated": bool,
#  }
#  player["academy_last_class_ts"] — کول‌داونِ کلاسِ بعدی.
# ============================================================
import random
import time

ENROLL_LEVEL_REQ = 8
CLASS_COOLDOWN = 3 * 3600   # هر ۳ ساعت یه کلاس
YEARS_TOTAL = 3

SUBJECTS = {
    "combat": {"name": "⚔️ نبردِ کاربردی", "stat": "atk", "bonus_per_point": 0.6},
    "magic":  {"name": "🔮 نظریه‌ی آرکین",  "stat": "def", "bonus_per_point": 0.6},
    "lore":   {"name": "📚 تاریخِ Abyss",   "stat": "max_hp", "bonus_per_point": 2.0},
}

EXAM_REQ_PER_YEAR = {1: 15, 2: 35, 3: 60}   # مجموعِ امتیازِ سه‌تا درس، لازم برای امتحانِ اون سال
EXAM_BASE_CHANCE = 0.55
EXAM_CHANCE_PER_EXTRA_POINT = 0.01  # هر امتیازِ اضافه روی حداقل، شانس رو کمی بیشتر می‌کنه

GRADUATION_TITLE = "🎓 فارغ‌التحصیلِ آکادمی"


def _academy(player: dict) -> dict:
    a = player.get("academy")
    if not a:
        a = {"enrolled": False, "year": 1, "subjects": {s: 0 for s in SUBJECTS}, "academy_points": 0, "graduated": False}
        player["academy"] = a
    return a


def can_enroll(player: dict) -> tuple[bool, str]:
    a = _academy(player)
    if a["enrolled"]:
        return False, "❌ قبلاً ثبت‌نام کردی."
    if player.get("level", 1) < ENROLL_LEVEL_REQ:
        return False, f"❌ برای ثبت‌نام باید سطح {ENROLL_LEVEL_REQ} باشی."
    return True, ""


def enroll(player: dict) -> tuple[bool, str]:
    ok, err = can_enroll(player)
    if not ok:
        return False, err
    a = _academy(player)
    a["enrolled"] = True
    return True, (
        "🎓 **به آکادمی خوش اومدی!**\n\n"
        "سه سالِ سخت در پیشه — سه تا درس، امتحانِ پایانِ هر سال، و اگه دووم بیاری، "
        "یه عنوانِ دائمی که همیشه همراهته."
    )


def can_attend_class(player: dict) -> tuple[bool, int]:
    last = player.get("academy_last_class_ts", 0)
    remaining = CLASS_COOLDOWN - (time.time() - last)
    return remaining <= 0, max(0, int(remaining))


def attend_class(player: dict, subject_id: str) -> tuple[bool, str]:
    a = _academy(player)
    if not a["enrolled"]:
        return False, "❌ اول باید تو آکادمی ثبت‌نام کنی."
    if a["graduated"]:
        return False, "❌ قبلاً فارغ‌التحصیل شدی — دیگه کلاسی نمونده."
    if subject_id not in SUBJECTS:
        return False, "❌ درسِ نامعتبر."
    ok, remaining = can_attend_class(player)
    if not ok:
        mins = remaining // 60
        return False, f"⏳ خسته‌ای — {mins} دقیقه‌ی دیگه دوباره سرِ کلاس برگرد."

    subj = SUBJECTS[subject_id]
    gained = random.randint(2, 5)
    a["subjects"][subject_id] = a["subjects"].get(subject_id, 0) + gained
    a["academy_points"] = a.get("academy_points", 0) + gained
    player["academy_last_class_ts"] = time.time()

    stat_gain = round(gained * subj["bonus_per_point"], 1)
    stats = player.setdefault("stats", {})
    stat_key = subj["stat"]
    stats[stat_key] = stats.get(stat_key, 0) + stat_gain
    if stat_key == "max_hp":
        player["max_hp"] = player.get("max_hp", 100) + stat_gain
        player["hp"] = player.get("hp", player["max_hp"]) + stat_gain
        stats["hp"] = stats.get("hp", stats.get("max_hp", 100)) + stat_gain

    return True, (
        f"📖 سرِ کلاسِ {subj['name']} حاضر شدی.\n"
        f"+{gained} امتیازِ {subj['name']} | +{stat_gain} {stat_key}"
    )


def exam_progress(player: dict) -> tuple[int, int]:
    a = _academy(player)
    total = sum(a["subjects"].values())
    req = EXAM_REQ_PER_YEAR.get(a["year"], 999)
    return total, req


def can_take_exam(player: dict) -> tuple[bool, str]:
    a = _academy(player)
    if not a["enrolled"]:
        return False, "❌ اول باید ثبت‌نام کنی."
    if a["graduated"]:
        return False, "❌ قبلاً فارغ‌التحصیل شدی."
    total, req = exam_progress(player)
    if total < req:
        return False, f"❌ هنوز آماده نیستی — {total}/{req} امتیازِ لازم."
    return True, ""


def take_exam(player: dict) -> tuple[bool, str]:
    ok, err = can_take_exam(player)
    if not ok:
        return False, err

    a = _academy(player)
    total, req = exam_progress(player)
    extra = total - req
    chance = min(0.95, EXAM_BASE_CHANCE + extra * EXAM_CHANCE_PER_EXTRA_POINT)
    passed = random.random() < chance

    if not passed:
        return False, (
            f"📝 **امتحانِ سالِ {a['year']} رو رد شدی...**\n"
            f"شانس: {int(chance*100)}٪ — دوباره درس بخون و دوباره امتحان بده."
        )

    a["subjects"] = {s: 0 for s in SUBJECTS}  # امتیازها برای سالِ بعد صفر می‌شن
    if a["year"] >= YEARS_TOTAL:
        a["graduated"] = True
        titles = player.setdefault("titles_unlocked", [])
        if GRADUATION_TITLE not in titles:
            titles.append(GRADUATION_TITLE)
        bonus_hp = 100
        player["max_hp"] = player.get("max_hp", 100) + bonus_hp
        player["hp"] = player.get("hp", player["max_hp"]) + bonus_hp
        stats = player.setdefault("stats", {})
        stats["max_hp"] = stats.get("max_hp", 100) + bonus_hp
        stats["hp"] = stats.get("hp", stats.get("max_hp", 100)) + bonus_hp
        return True, (
            f"🎉 **قبول شدی! و فارغ‌التحصیل شدی!** 🎓\n\n"
            f"عنوانِ «{GRADUATION_TITLE}» بهت داده شد.\n"
            f"❤️ +{bonus_hp} HP دائمی به‌عنوانِ هدیه‌ی فارغ‌التحصیلی."
        )

    a["year"] += 1
    return True, f"✅ **امتحانِ سالِ {a['year']-1} رو قبول شدی!** حالا وارد سالِ {a['year']} شدی."


def academy_power_bonus(player: dict) -> float:
    """سهمِ گذروندنِ سال‌های آکادمی برای Combat Power."""
    a = player.get("academy")
    if not a:
        return 0.0
    return (a.get("year", 1) - 1) * 60 + (150 if a.get("graduated") else 0)


def top_students(all_players_dict: dict, limit: int = 10) -> list[tuple[str, dict]]:
    ranked = [
        (uid, p) for uid, p in all_players_dict.items()
        if p.get("academy", {}).get("enrolled")
    ]
    ranked.sort(key=lambda kv: kv[1]["academy"].get("academy_points", 0), reverse=True)
    return ranked[:limit]


def status_text(player: dict) -> str:
    a = _academy(player)
    if not a["enrolled"]:
        req_ok, msg = can_enroll(player)
        return (
            "🎓 **آکادمی**\n\n"
            "یه فصلِ محدود — سه سالِ درس و امتحان، با یه عنوانِ دائمی در انتها.\n\n"
            + (f"✅ می‌تونی ثبت‌نام کنی!" if req_ok else msg)
        )
    if a["graduated"]:
        return f"🎓 **فارغ‌التحصیلِ آکادمی هستی!**\n\nمجموعِ امتیازِ کسب‌شده: {a['academy_points']:,}"

    total, req = exam_progress(player)
    lines = [
        f"🎓 **آکادمی — سالِ {a['year']}/{YEARS_TOTAL}**\n",
        f"📊 پیشرفتِ امتحان: {total}/{req}",
    ]
    for sid, s in SUBJECTS.items():
        lines.append(f"  {s['name']}: {a['subjects'].get(sid,0)}")
    lines.append(f"\n🏆 امتیازِ کلِ آکادمی: {a['academy_points']:,}")
    return "\n".join(lines)
