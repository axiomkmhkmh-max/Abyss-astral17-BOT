# ============================================================
#  ASTRAL ABYSS — Stand Bond System v2 (تمرینِ عمیق‌تر)
# ------------------------------------------------------------
#  محورِ دومِ پیشرفتِ استند — جدا از آپگرید با Zen، محورِ «زمان/
#  تعامل»ه. نسخه‌ی قبلی فقط یه رول ثابتِ XP/فرگمنت بود؛ این نسخه
#  عمیق‌تره:
#
#   ۱) **استریک** — اگه تویِ بازه‌ی ۱۲ ساعته (۲ برابرِ کول‌داون)
#      دوباره تمرین کنی، استریکت ادامه پیدا می‌کنه و پاداشت بیشتر
#      می‌شه؛ اگه دیر کنی، استریک صفر می‌شه (مثلِ استریکِ لوت).
#   ۲) **نتیجه‌ی متغیر** — هر تمرین یکی از ۴ نتیجه داره: شکست‌خفیف،
#      عادی، خوب، بحرانی — با شانسی که خودِ استریک بالاش می‌بره.
#   ۳) **بریک‌ثرو (Breakthrough)** — تو نتیجه‌ی بحرانی، شانس داره
#      یکی از توانایی‌های استندت یهو یه سطحِ رایگان بگیره (بدونِ
#      خرجِ Zen) — پلی بینِ محورِ «پیوند» و محورِ «Zen».
# ============================================================
from __future__ import annotations

import time
import random

TRAIN_COOLDOWN = 6 * 3600           # ۶ ساعت تا دوباره بشه تمرین کرد
STREAK_WINDOW = TRAIN_COOLDOWN * 2  # اگه تا ۱۲ ساعت بعدِ آماده‌شدن دوباره بزنی، استریک می‌مونه
STREAK_TIER_CAP = 6

BOND_XP_PER_TRAIN = (8, 15)
FRAGMENTS_PER_TRAIN = (1, 3)

# ─── سطحِ پیوند (Bond) — آستانه‌ی XP لازم برای هر سطح ─────────────
BOND_LEVEL_THRESHOLDS = [0, 40, 100, 200, 360, 600, 900, 1300, 1800, 2400, 3200]
MAX_BOND_LEVEL = len(BOND_LEVEL_THRESHOLDS) - 1

# ─── نتیجه‌های ممکنِ تمرین ────────────────────────────────────────
OUTCOME_SETBACK, OUTCOME_NORMAL, OUTCOME_GOOD, OUTCOME_CRITICAL = "setback", "normal", "good", "critical"
_OUTCOME_MULT = {OUTCOME_SETBACK: 0.5, OUTCOME_NORMAL: 1.0, OUTCOME_GOOD: 1.5, OUTCOME_CRITICAL: 2.5}
_OUTCOME_LABEL = {
    OUTCOME_SETBACK:  "😮‍💨 امروز هماهنگیت با استند کم بود",
    OUTCOME_NORMAL:   "🤝 یه تمرینِ معمولی",
    OUTCOME_GOOD:     "✨ هماهنگیِ خوبی با استندت داشتی",
    OUTCOME_CRITICAL: "🌟 هم‌آوایی کامل با استند!",
}
BASE_SETBACK_CHANCE = 0.05
BASE_CRITICAL_CHANCE = 0.06
CRITICAL_CHANCE_PER_TIER = 0.02
BREAKTHROUGH_CHANCE_ON_CRIT = 0.5  # تو نتیجه‌ی بحرانی، ۵۰٪ شانسِ بریک‌ثروی رایگان


def get_bond_xp(player: dict) -> int:
    return player.get("stand_bond_xp", 0)


def get_bond_level(player: dict) -> int:
    xp = get_bond_xp(player)
    lvl = 0
    for i, threshold in enumerate(BOND_LEVEL_THRESHOLDS):
        if xp >= threshold:
            lvl = i
    return lvl


def bond_xp_to_next(player: dict) -> tuple[int, int]:
    lvl = get_bond_level(player)
    if lvl >= MAX_BOND_LEVEL:
        return 0, 0
    cur = get_bond_xp(player) - BOND_LEVEL_THRESHOLDS[lvl]
    need = BOND_LEVEL_THRESHOLDS[lvl + 1] - BOND_LEVEL_THRESHOLDS[lvl]
    return cur, need


def bond_power_multiplier(player: dict) -> float:
    return 1.0 + (get_bond_level(player) * 0.04)   # هر سطح +۴٪


def get_fragments(player: dict) -> int:
    return player.get("stand_fragments", 0)


def seconds_until_train_ready(player: dict) -> int:
    last = player.get("stand_last_train", 0)
    remaining = TRAIN_COOLDOWN - (time.time() - last)
    return max(0, int(remaining))


def get_train_streak(player: dict) -> int:
    return player.get("stand_train_streak", 0)


def streak_tier(streak: int) -> int:
    return min(streak // 3, STREAK_TIER_CAP)


def _try_breakthrough(player: dict) -> str | None:
    """تو نتیجه‌ی بحرانی، یه شانس هست یکی از توانایی‌هایی که هنوز مکس
    نشده و evolve هم نشده، یه سطحِ رایگان بگیره. برمی‌گردونه اسمِ
    توانایی‌ای که آپ شد، یا None."""
    from stand_system import get_stand, MAX_ABILITY_LEVEL, is_ability_evolved

    char_name = player.get("character", "")
    if not char_name:
        return None
    stand = get_stand(char_name)
    levels = player.setdefault("stand_abilities", {})

    candidates = [
        a for a in stand["core_abilities"]
        if levels.get(a, 1) < MAX_ABILITY_LEVEL and not is_ability_evolved(player, a)
    ]
    if not candidates:
        return None

    chosen = random.choice(candidates)
    levels[chosen] = levels.get(chosen, 1) + 1
    return chosen


def train_bond(player: dict) -> tuple[bool, str]:
    """عملِ «تمرینِ استند» — رایگانه، کول‌داون داره، و حالا نتیجه‌ش
    متغیره (بستگی به استریک و شانس)."""
    remaining = seconds_until_train_ready(player)
    if remaining > 0:
        hrs, rem = divmod(remaining, 3600)
        mins = rem // 60
        return False, f"⏳ استندت خسته‌ست! {hrs} ساعت و {mins} دقیقه‌ی دیگه دوباره تمرین کن."

    # ─── محاسبه‌ی استریک ───
    now = time.time()
    last = player.get("stand_last_train", 0)
    if last and (now - last) <= STREAK_WINDOW:
        streak = get_train_streak(player) + 1
    else:
        streak = 1
    player["stand_train_streak"] = streak
    player["stand_train_best_streak"] = max(player.get("stand_train_best_streak", 0), streak)
    tier = streak_tier(streak)

    # ─── تعیینِ نتیجه ───
    setback_p = BASE_SETBACK_CHANCE
    critical_p = min(BASE_CRITICAL_CHANCE + tier * CRITICAL_CHANCE_PER_TIER, 0.30)
    good_p = 0.25
    normal_p = max(0.0, 1.0 - setback_p - critical_p - good_p)
    outcome = random.choices(
        [OUTCOME_SETBACK, OUTCOME_NORMAL, OUTCOME_GOOD, OUTCOME_CRITICAL],
        weights=[setback_p, normal_p, good_p, critical_p],
        k=1,
    )[0]

    reward_mult = _OUTCOME_MULT[outcome] * (1 + tier * 0.08)
    xp_gain = max(1, int(random.randint(*BOND_XP_PER_TRAIN) * reward_mult))
    frag_gain = max(0, round(random.randint(*FRAGMENTS_PER_TRAIN) * reward_mult))

    old_level = get_bond_level(player)
    player["stand_bond_xp"] = get_bond_xp(player) + xp_gain
    player["stand_fragments"] = get_fragments(player) + frag_gain
    player["stand_last_train"] = now

    lines = [f"{_OUTCOME_LABEL[outcome]}  (استریک: {streak}🔥، تیر {tier})"]
    lines.append(f"+{xp_gain} XP پیوند، +{frag_gain} 🧩 فرگمنت")

    if outcome == OUTCOME_CRITICAL and random.random() < BREAKTHROUGH_CHANCE_ON_CRIT:
        ability = _try_breakthrough(player)
        if ability:
            lines.append(f"⚡ بریک‌ثرو! «{ability}» یه سطحِ رایگان گرفت!")

    new_level = get_bond_level(player)
    if new_level > old_level:
        lines.append(f"🎉 پیوندِ استند به سطح {new_level} رسید!")

    return True, "\n".join(lines)
