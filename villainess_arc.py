# ============================================================
#  ASTRAL ABYSS — Reincarnated Villainess Path 🌹 (فرار از سرنوشتِ بد)
# ------------------------------------------------------------
#  مسیرِ روایی‌ِ جایگزینِ زنانه، مکملِ تمِ «Evil Overlord/مائو»: بازیکن
#  کشف می‌کنه که تو یه داستان، نقشِ «دخترِ شرور»ی رو بازی می‌کنه که
#  قراره سرنوشتِ بدی (اعدام/تبعید/مرگ) در انتظارشه. با انجامِ
#  کارهای مشخص («فرار از سرنوشت») می‌تونه مسیرش رو عوض کنه.
#  بدونِ فشارِ زمانی/پنالتی سخت — صرفاً یه مینی‌گیمِ روایی با پاداشِ
#  دائمی در پایان.
#
#  دیتا: player["villainess_arc"] = {
#      "active": bool, "escape_progress": int, "escaped": bool,
#  }
#  player["villainess_last_action_ts"] — کول‌داونِ اکشنِ بعدی.
# ============================================================
import random
import time

START_LEVEL_REQ = 6
ACTION_COOLDOWN = 2 * 3600
ESCAPE_THRESHOLD = 100

INTRO_TEXT = (
    "🌹 **یه چیزی درموردِ این دنیا آشناست...**\n\n"
    "_یه لحظه‌ی گنگ — انگار یه‌جا این داستان رو خونده بودی. تو نقشِ «دخترِ شرورِ» یه رمان افتادی: "
    "کسی که تو پایانِ داستان، یا اعدام می‌شه، یا تبعید، یا بدتر.\n\n"
    "ولی هنوز وقت داری. اگه مسیرت رو عوض کنی، شاید بشه از این سرنوشت فرار کرد._"
)

DOOM_FLAVORS = ["⚔️ اعدام", "🏚 تبعید", "💀 مرگِ مرموز"]

ESCAPE_ACTIONS = {
    "kindness": {
        "name": "🤝 یه کارِ خیر", "points": (8, 14),
        "flavor": "به‌جای نقشه‌کشیدنِ بد، به یه غریبه کمک کردی. حسِ عجیبی داره.",
    },
    "confront": {
        "name": "💬 روبه‌رو شدن با حقیقت", "points": (10, 18),
        "flavor": "به‌جای فرار از سرنوشتت، مستقیم قبولش کردی — و همین باعث شد کنترلش دستِ تو بیفته.",
    },
    "rival": {
        "name": "🌸 دوستی به‌جای رقابت", "points": (6, 12),
        "flavor": "به‌جای دشمنی با «قهرمانِ داستان»، باهاش دوست شدی. خط‌داستان یه‌کم می‌لرزه.",
    },
}

REDEMPTION_TITLE = "🌹 فراری از سرنوشت"


def _arc(player: dict) -> dict:
    a = player.get("villainess_arc")
    if not a:
        a = {"active": False, "escape_progress": 0, "escaped": False, "doom": random.choice(DOOM_FLAVORS)}
        player["villainess_arc"] = a
    return a


def can_start(player: dict) -> tuple[bool, str]:
    a = _arc(player)
    if a["active"] or a["escaped"]:
        return False, "❌ قبلاً وارد این مسیر شدی."
    if player.get("level", 1) < START_LEVEL_REQ:
        return False, f"❌ باید سطح {START_LEVEL_REQ} باشی."
    return True, ""


def start_arc(player: dict) -> tuple[bool, str]:
    ok, err = can_start(player)
    if not ok:
        return False, err
    a = _arc(player)
    a["active"] = True
    return True, f"{INTRO_TEXT}\n\n💀 سرنوشتِ در انتظارت: **{a['doom']}**"


def can_act(player: dict) -> tuple[bool, int]:
    last = player.get("villainess_last_action_ts", 0)
    remaining = ACTION_COOLDOWN - (time.time() - last)
    return remaining <= 0, max(0, int(remaining))


def perform_action(player: dict, action_id: str) -> tuple[bool, str]:
    a = _arc(player)
    if not a["active"]:
        return False, "❌ اول باید وارد این مسیر بشی."
    if a["escaped"]:
        return False, "❌ قبلاً از سرنوشتت فرار کردی — دیگه اکشنی نمونده."
    if action_id not in ESCAPE_ACTIONS:
        return False, "❌ اکشنِ نامعتبر."
    ok, remaining = can_act(player)
    if not ok:
        mins = remaining // 60
        return False, f"⏳ {mins} دقیقه‌ی دیگه دوباره امتحان کن."

    action = ESCAPE_ACTIONS[action_id]
    gained = random.randint(*action["points"])
    a["escape_progress"] = min(ESCAPE_THRESHOLD, a["escape_progress"] + gained)
    player["villainess_last_action_ts"] = time.time()

    text = f"{action['name']}\n_{action['flavor']}_\n+{gained} پیشرفتِ فرار ({a['escape_progress']}/{ESCAPE_THRESHOLD})"

    if a["escape_progress"] >= ESCAPE_THRESHOLD and not a["escaped"]:
        a["escaped"] = True
        titles = player.setdefault("titles_unlocked", [])
        if REDEMPTION_TITLE not in titles:
            titles.append(REDEMPTION_TITLE)
        bonus = 25
        stats = player.setdefault("stats", {})
        stats["def"] = stats.get("def", 5) + bonus
        stats["atk"] = stats.get("atk", 10) + bonus // 2
        text += (
            f"\n\n🎉 **از سرنوشتت فرار کردی!**\n"
            f"دیگه {a['doom']} در انتظارت نیست — خودت نویسنده‌ی داستانِ خودت شدی.\n"
            f"🌹 عنوانِ «{REDEMPTION_TITLE}» گرفتی.\n"
            f"🛡 +{bonus} دفاع | ⚔️ +{bonus//2} حمله (دائمی)"
        )
    return True, text


def villainess_power_bonus(player: dict) -> float:
    a = player.get("villainess_arc")
    if not a:
        return 0.0
    if a.get("escaped"):
        return 260.0
    return a.get("escape_progress", 0) * 1.2


def status_text(player: dict) -> str:
    a = _arc(player)
    if not a["active"] and not a["escaped"]:
        ok, err = can_start(player)
        return (
            "🌹 **مسیرِ زنانه‌ی جایگزین**\n\n"
            "یه داستانِ فرعی درموردِ فرار از سرنوشتِ ازپیش‌نوشته‌شده.\n\n"
            + ("✅ می‌تونی این مسیر رو شروع کنی!" if ok else err)
        )
    if a["escaped"]:
        return f"🌹 **از سرنوشتت فرار کردی!**\nپیشرفت: {a['escape_progress']}/{ESCAPE_THRESHOLD} ✅"
    return (
        f"🌹 **مسیرِ زنانه‌ی جایگزین**\n\n"
        f"💀 سرنوشتِ در انتظار: {a['doom']}\n"
        f"📊 پیشرفتِ فرار: {a['escape_progress']}/{ESCAPE_THRESHOLD}"
    )
