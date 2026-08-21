# ============================================================
#  ASTRAL ABYSS — Loop Shard 🔁 (حلقه‌ی زمان، الهام‌گرفته از Re:Zero)
# ------------------------------------------------------------
#  یه آیتمِ نایاب که وقتی داریش، به‌جای باختنِ قطعی به یه باس،
#  می‌تونی «حلقه بزنی» — زمان یه‌کم برمی‌گرده، HP‌ت ترمیم می‌شه و
#  دشمن دقیقاً همون‌جوریه که اولِ نبرد بود. یه فلیورِ تلخ‌وشیرین:
#  یادت می‌مونه، ولی هیچ‌کس دیگه نمی‌فهمه.
#
#  دیتا: player["loop_charges"] (int, پیش‌فرض ۰).
#  خالص/بدون aiogram — قلاب‌ها تو mob_combat.py.
# ============================================================
import random

BOSS_DROP_CHANCE = 0.03    # ۳٪ شانسِ افتادنِ یه حلقه بعدِ هر پیروزیِ باس
MAX_CHARGES = 3            # نمی‌تونه بیشتر از ۳ تا نگه داره

REVIVE_HP_PCT = 0.5        # وقتی حلقه می‌زنی، HP تا این درصد از max_hp برمی‌گرده

DROP_FLAVOR = (
    "✨ یه بلورِ کوچیکِ نقره‌ای از جسدِ باس جدا می‌شه و تویِ دستت فرود می‌آد.\n"
    "_یه حسِ عجیب — انگار این لحظه رو قبلاً هم تجربه کرده بودی._\n"
    "🔁 **یه حلقه‌ی زمان به دست آوردی!**"
)

LOOP_FLAVOR = (
    "🔁💫 **زمان می‌شکنه...**\n\n"
    "_«این دفعه فرق می‌کنه.» یه صدا تو سرت این رو زمزمه می‌کنه —_ "
    "_هرچند نمی‌تونی مطمئن باشی که واقعاً صداییه که شنیدی، یا فقط یادآوریِ یه حلقه‌ی قبلیه._\n\n"
    "لحظه برمی‌گرده به شروعِ نبرد. این بار بهتر می‌جنگی."
)


def has_loop_charge(player: dict) -> bool:
    return player.get("loop_charges", 0) > 0


def consume_loop_charge(player: dict) -> bool:
    if not has_loop_charge(player):
        return False
    player["loop_charges"] -= 1
    return True


def maybe_drop_loop_charge(player: dict, is_boss: bool) -> str | None:
    """صدا زده می‌شه بعدِ پیروزی رو باس. اگه رول ببره، یه شارژ اضافه
    می‌کنه (تا سقفِ MAX_CHARGES) و متنِ فلیورِ دراپ رو برمی‌گردونه."""
    if not is_boss:
        return None
    if player.get("loop_charges", 0) >= MAX_CHARGES:
        return None
    if random.random() > BOSS_DROP_CHANCE:
        return None
    player["loop_charges"] = player.get("loop_charges", 0) + 1
    return DROP_FLAVOR


def status_text(player: dict) -> str:
    n = player.get("loop_charges", 0)
    if n <= 0:
        return "🔁 هیچ حلقه‌ی زمانی نداری. فقط با شکستِ باس‌ها، به‌ندرت پیدا می‌شه."
    return f"🔁 **{n}** حلقه‌ی زمان داری — وقتی به یه باس ببازی، می‌تونی ازش استفاده کنی تا نبرد از اول شروع بشه."
