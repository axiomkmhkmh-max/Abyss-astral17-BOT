# ============================================================
#  ASTRAL ABYSS — Battle Pass (فصلی)
# ------------------------------------------------------------
#  یه مسیرِ پاداشِ فصلی: هر نبرد (حمله/لوت) که XP می‌گیری، همون مقدار
#  «امتیازِ پس» هم می‌گیری. هر چند تا امتیاز یه «تایر» باز می‌شه و
#  هر تایر یه جایزه‌ی Zen (+ گاهی عنوان) داره. فصل هر ۳۰ روز عوض
#  می‌شه و امتیاز صفر می‌شه.
#
#  ردِ پرمیوم فعلاً به پرداخت واقعی وصل نیست (تو requirements.txt
#  درگاهِ پرداخت نیست) — با فلگِ player["bp_premium"] کار می‌کنه که
#  فعلاً فقط ادمین با /grantpass می‌تونه فعالش کنه. هر وقت درگاهِ
#  پرداخت (مثل Telegram Stars) وصل شد، همون‌جا کافیه بعد از پرداختِ
#  موفق grant_premium(player) صدا زده بشه.
# ============================================================
import time

SEASON_SECONDS = 30 * 86400          # هر فصل ۳۰ روزه
BP_EPOCH = 1750000000                # نقطه‌ی مرجعِ ثابت برای شماره‌گذاریِ فصل‌ها — تغییرش نده

MAX_TIER = 20
POINTS_PER_TIER = 600                # هر تایر ~۶۰۰ امتیاز (تقریباً هم‌ارزِ XPِ چند ده نبرد)


def current_season() -> int:
    return int((time.time() - BP_EPOCH) // SEASON_SECONDS) + 1


def season_seconds_left() -> int:
    elapsed = (time.time() - BP_EPOCH) % SEASON_SECONDS
    return int(SEASON_SECONDS - elapsed)


def _ensure_season(player: dict):
    s = current_season()
    if player.get("bp_season") != s:
        player["bp_season"] = s
        player["bp_points"] = 0
        player["bp_claimed_free"] = []
        player["bp_claimed_premium"] = []


def add_points(player: dict, amount: int):
    """هر بار XP از نبرد می‌گیری، همون مقدار امتیازِ پس هم بگیر."""
    if amount <= 0:
        return
    _ensure_season(player)
    player["bp_points"] = player.get("bp_points", 0) + amount


def current_tier(player: dict) -> int:
    _ensure_season(player)
    return min(MAX_TIER, player.get("bp_points", 0) // POINTS_PER_TIER)


def points_to_next_tier(player: dict) -> int:
    _ensure_season(player)
    tier = current_tier(player)
    if tier >= MAX_TIER:
        return 0
    next_threshold = (tier + 1) * POINTS_PER_TIER
    return max(0, next_threshold - player.get("bp_points", 0))


def has_premium(player: dict) -> bool:
    _ensure_season(player)
    return bool(player.get("bp_premium"))


def grant_premium(player: dict):
    """ردِ پرمیومِ همین فصل رو برای بازیکن فعال می‌کنه."""
    _ensure_season(player)
    player["bp_premium"] = True


def free_reward(tier: int) -> int:
    """جایزه‌ی Zenِ ردِ رایگان برای یه تایرِ مشخص."""
    return 300 + tier * 150


def premium_reward(tier: int) -> int:
    """جایزه‌ی Zenِ ردِ پرمیوم (اضافه بر رایگان) برای یه تایرِ مشخص."""
    return free_reward(tier)  # پرمیوم دو برابر می‌شه (رایگان + این)


def tier_title(tier: int) -> str | None:
    """بعضی تایرها یه عنوانِ فصلی هم به titles_unlocked اضافه می‌کنن."""
    if tier == MAX_TIER:
        return f"🏆 قهرمانِ فصل {current_season()}"
    if tier == 10:
        return f"🎖 کهنه‌کارِ فصل {current_season()}"
    return None


def claimable_free_tiers(player: dict) -> list[int]:
    _ensure_season(player)
    tier = current_tier(player)
    claimed = set(player.get("bp_claimed_free", []))
    return [t for t in range(1, tier + 1) if t not in claimed]


def claimable_premium_tiers(player: dict) -> list[int]:
    _ensure_season(player)
    if not has_premium(player):
        return []
    tier = current_tier(player)
    claimed = set(player.get("bp_claimed_premium", []))
    return [t for t in range(1, tier + 1) if t not in claimed]


def claim_free(player: dict, tier: int) -> dict | None:
    """جایزه‌ی تایرِ رایگان رو می‌ده و claimed علامت می‌زنه. اگه نامعتبر باشه None."""
    _ensure_season(player)
    if tier < 1 or tier > current_tier(player):
        return None
    claimed = player.setdefault("bp_claimed_free", [])
    if tier in claimed:
        return None
    claimed.append(tier)
    zen = free_reward(tier)
    player["zen"] = player.get("zen", 0) + zen
    result = {"zen": zen, "title": None}
    title = tier_title(tier)
    if title:
        titles = player.setdefault("titles_unlocked", [])
        if title not in titles:
            titles.append(title)
            result["title"] = title
    return result


def claim_premium(player: dict, tier: int) -> dict | None:
    """جایزه‌ی تایرِ پرمیوم رو می‌ده و claimed علامت می‌زنه. اگه نامعتبر/بدونِ پرمیوم باشه None."""
    _ensure_season(player)
    if not has_premium(player):
        return None
    if tier < 1 or tier > current_tier(player):
        return None
    claimed = player.setdefault("bp_claimed_premium", [])
    if tier in claimed:
        return None
    claimed.append(tier)
    zen = premium_reward(tier)
    player["zen"] = player.get("zen", 0) + zen
    return {"zen": zen}


def progress_bar(player: dict, length: int = 10) -> str:
    _ensure_season(player)
    tier = current_tier(player)
    filled = int(length * tier / MAX_TIER)
    return "🟩" * filled + "⬜" * (length - filled)


# ============================================================
#  🎓 مسیرِ مشترکِ استاد/شاگرد — Battle Pass مشترک
# ------------------------------------------------------------
#  تا وقتی رابطه‌ی مربی‌گری فعاله، هر طرف سهمِ خودشو تو یه مسیرِ
#  مشترک جمع می‌کنه (هرکدوم فقط رو داکیومنتِ خودش، بدون نیاز به
#  لودِ متقابل تو حلقه‌ی داغِ نبرد). امتیازِ نهایی و تایرش فقط
#  وقتی هردو داکیومنت با‌همن (مثلاً تو /mentor) محاسبه می‌شه.
# ============================================================
PAIR_MAX_TIER = 8
PAIR_POINTS_PER_TIER = 500
PAIR_GRADUATE_TITLE = "🎓 دوگانه‌ی افسانه‌ای"


def add_pair_points(player: dict, mentee_id: int, amount: int):
    """مربی، سهمِ خودش رو از مسیرِ مشترک با یه شاگردِ خاص جمع می‌کنه."""
    if amount <= 0:
        return
    contrib = player.setdefault("mentor_pair_contrib", {})
    key = str(mentee_id)
    contrib[key] = contrib.get(key, 0) + amount


def add_mentee_pair_points(player: dict, amount: int):
    """شاگرد، سهمِ خودش رو از مسیرِ مشترک جمع می‌کنه."""
    if amount <= 0:
        return
    player["mentor_pair_points"] = player.get("mentor_pair_points", 0) + amount


def pair_points(mentor: dict, mentee: dict) -> int:
    """جمعِ سهمِ هردو طرف برای مسیرِ مشترکِ همین رابطه‌ی خاص."""
    mentor_share = mentor.get("mentor_pair_contrib", {}).get(str(mentee.get("id")), 0)
    mentee_share = mentee.get("mentor_pair_points", 0)
    return mentor_share + mentee_share


def pair_tier(mentor: dict, mentee: dict) -> int:
    return min(PAIR_MAX_TIER, pair_points(mentor, mentee) // PAIR_POINTS_PER_TIER)


def pair_points_to_next_tier(mentor: dict, mentee: dict) -> int:
    tier = pair_tier(mentor, mentee)
    if tier >= PAIR_MAX_TIER:
        return 0
    return max(0, (tier + 1) * PAIR_POINTS_PER_TIER - pair_points(mentor, mentee))


def pair_reward(tier: int) -> int:
    return 500 + tier * 250


def pair_claimable_tiers(mentor: dict, mentee: dict) -> list[int]:
    tier = pair_tier(mentor, mentee)
    claimed = set(mentee.get("mentor_pair_claimed", []))
    return [t for t in range(1, tier + 1) if t not in claimed]


def claim_pair_tier(mentor: dict, mentee: dict, tier: int) -> dict | None:
    """جایزه‌ی مشترکِ این تایر رو به هردو طرف می‌ده. وضعیتِ claimed رو
    داکیومنتِ شاگرد نگه می‌داره (چون هر شاگرد فقط یه مربی داره، ولی
    هر مربی می‌تونه چند شاگرد داشته باشه)."""
    if tier < 1 or tier > pair_tier(mentor, mentee):
        return None
    claimed = mentee.setdefault("mentor_pair_claimed", [])
    if tier in claimed:
        return None
    claimed.append(tier)
    zen = pair_reward(tier)
    mentor["zen"] = mentor.get("zen", 0) + zen
    mentee["zen"] = mentee.get("zen", 0) + zen
    result = {"zen": zen, "title": None}
    if tier == PAIR_MAX_TIER:
        for p in (mentor, mentee):
            titles = p.setdefault("titles_unlocked", [])
            if PAIR_GRADUATE_TITLE not in titles:
                titles.append(PAIR_GRADUATE_TITLE)
        result["title"] = PAIR_GRADUATE_TITLE
    return result


def pair_progress_bar(mentor: dict, mentee: dict, length: int = 8) -> str:
    tier = pair_tier(mentor, mentee)
    filled = int(length * tier / PAIR_MAX_TIER)
    return "🟦" * filled + "⬜" * (length - filled)
