# ============================================================
#  ASTRAL ABYSS — Onboarding (تیوتوریالِ گام‌به‌گامِ پلیرِ جدید)
# ------------------------------------------------------------
#  مشکلی که حل می‌کنه: بلافاصله بعد از گرفتنِ کاراکتر، پلیرِ جدید با
#  یه پنلِ ۶ دسته‌ای / ۲۸ دکمه‌ای روبه‌رو می‌شد و هیچ راهنمایی نداشت
#  دقیقاً چیکار کنه. نتیجه: گیجی تو همون اولین دقیقه = ریزش.
#
#  راه‌حل: یه مسیرِ خطیِ خیلی کوتاه —
#     ساختِ کاراکتر → «⚔️ حمله» → اولین کشتن (+ لوتِ احتمالی) → پنلِ کامل باز می‌شه
#  در طولِ این مسیر، به‌جای کیبوردِ کاملِ ۶‌دسته‌ای، فقط یه کیبوردِ
#  دوتا-دکمه‌ای (حمله/وضعیت) نشون داده می‌شه — نمی‌شه گم شد.
#
#  وضعیتِ تیوتوریال مستقیم رو خودِ سندِ بازیکن ذخیره می‌شه:
#     tutorial_done : bool  — وقتی True شد، از این ماژول دیگه کاری
#                             لازم نیست؛ پنلِ کامل (main_kb) نشون داده می‌شه.
#     tutorial_step : str   — STEP_AWAIT_ATTACK → STEP_AWAIT_KILL → STEP_DONE
#
#  نکته‌ی مهم درباره‌ی پلیرهای قدیمی: تو database.py، apply_player_defaults
#  اگه ببینه یه سندِ قدیمی از قبل کاراکتر داره (یعنی این فیچر جدیده و اون
#  بازیکن قبلاً بازی کرده)، خودکار tutorial_done=True می‌ذاره — این تیوتوریال
#  هیچ‌وقت جلوی کسی که وسطِ بازیه سبز نمی‌شه.
# ============================================================
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ButtonStyle

STEP_AWAIT_ATTACK = "await_attack"
STEP_AWAIT_KILL   = "await_kill"
STEP_AWAIT_LOOT   = "await_loot"
STEP_DONE         = "done"


def is_in_tutorial(player: dict) -> bool:
    """سیستمِ تیوتوریال غیرفعال شده — همیشه False برمی‌گردونه، یعنی
    هیچ پلیری (نه قدیمی، نه جدید) وارد مسیرِ تیوتوریال نمی‌شه و از
    همون اول پنلِ کامل (main_kb) رو می‌بینه."""
    return False


def tutorial_kb() -> ReplyKeyboardMarkup:
    """کیبوردِ ساده‌شده‌ی دورانِ تیوتوریال — فقط حمله + وضعیت، نه کل پنل."""
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text="حمله", style=ButtonStyle.SUCCESS),
            KeyboardButton(text="وضعیت", style=ButtonStyle.SUCCESS),
        ]],
        resize_keyboard=True,
        selective=True,
    )


def tutorial_kb_loot() -> ReplyKeyboardMarkup:
    """کیبوردِ گامِ سوم — بعدِ اولین کیل، دکمه‌ی 🗺 لوت هم اضافه می‌شه."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="لوت", style=ButtonStyle.PRIMARY)],
            [
                KeyboardButton(text="حمله", style=ButtonStyle.SUCCESS),
                KeyboardButton(text="وضعیت", style=ButtonStyle.SUCCESS),
            ],
        ],
        resize_keyboard=True,
        selective=True,
    )


def start_tutorial(player: dict) -> None:
    """غیرفعال شده — دیگه هیچ پلیری وارد تیوتوریال نمی‌شه، پس این تابع
    فقط مطمئن می‌شه فیلدها روی حالتِ «تموم‌شده» بمونن."""
    player["tutorial_done"] = True
    player["tutorial_step"] = STEP_DONE


def resume_kb(player: dict) -> ReplyKeyboardMarkup:
    """کیبوردِ درستِ «برگشت به تیوتوریال» رو بر اساسِ قدمِ فعلیِ بازیکن
    برمی‌گردونه — نه همیشه کیبوردِ دوتا-دکمه‌ای.

    باگی که این تابع رفعش می‌کنه: قبلاً /start (چه تو گپ، چه پیوی)
    برای هر پلیرِ تو-تیوتوریال، بدونِ توجه به قدمش، همیشه tutorial_kb()
    (فقط حمله/وضعیت) رو می‌فرستاد. پس پلیری که اولین کیلش رو زده بود و
    دکمه‌ی «🗺 لوت» رو گرفته بود، اگه دوباره /start می‌زد (ری‌استارتِ
    اپ، ری‌استارتِ ربات، هر چیزی)، همون دکمه‌ی لوت از دستش می‌رفت و
    برمی‌گشت به کیبوردِ ابتداییِ دوتا-دکمه‌ای — با اینکه هیچ راهِ واضحی
    برای گرفتنِ دوباره‌ی دکمه‌ی لوت نداشت (چون تو قدمِ AWAIT_LOOTه، نه
    AWAIT_ATTACK، پس ضربه‌زدن دیگه چیزی رو تریگر نمی‌کنه). عملاً یه
    قفلِ دائمی می‌شد — دقیقاً همون علامتی که پلیرها گزارش می‌کردن."""
    if player.get("tutorial_step") == STEP_AWAIT_LOOT:
        return tutorial_kb_loot()
    return tutorial_kb()


def welcome_text() -> str:
    return (
        "🧭 **قدمِ اول:** پایینِ صفحه رو «⚔️ حمله» بزن.\n"
        "یه لیستِ دشمن می‌بینی — یکی رو انتخاب کن و بهش ضربه بزن. "
        "بقیه‌ی پنل (گیلد، بازار، PvP و...) بعداً باز می‌شه؛ فعلاً فقط "
        "همینو امتحان کن."
    )


def resume_text(player: dict) -> str:
    """متنِ راهنمای «برگشت به تیوتوریال» بر اساسِ قدمِ فعلی — تا پلیرِ
    قدمِ‌سوم دوباره راهنمایِ قدمِ‌اول رو نبینه."""
    if player.get("tutorial_step") == STEP_AWAIT_LOOT:
        return (
            "🧭 **قدمِ سوم:** رو «🗺 لوت» بزن (یا تو گپ دستورِ /loot رو) "
            "— برو تو نقشه، یه لوکیشن بگرد تا کل پنل باز شه."
        )
    if player.get("tutorial_step") == STEP_AWAIT_KILL:
        return (
            "🧭 **قدمِ دوم:** دشمنی که زدی هنوز زندست! رو «⚔️ ادامه نبرد» "
            "بزن تا کارش رو تموم کنی."
        )
    return welcome_text()


def on_attack_resolved(player: dict, killed: bool) -> str | None:
    """
    بعدِ حلِ هر ضربه (چه دشمن کشته شده باشه چه نه) از resolve_hit
    (combat_handlers.py) صدا زده می‌شه. اگه بازیکن تو مسیرِ تیوتوریاله،
    متنِ راهنمای قدمِ بعدی رو برمی‌گردونه تا به پیامِ نتیجه‌ی نبرد
    اضافه بشه؛ وگرنه None (یعنی این بازیکن اصلاً تو تیوتوریال نیست).

    خروجی، وقتی این مرحله (STEP_AWAIT_KILL) همین‌جا تموم بشه، شاملِ یه
    علامتِ مخصوص تو ابتداش هست (LOOT_STEP_MARK) تا caller بفهمه باید
    کیبورد رو به tutorial_kb_loot (سه‌دکمه‌ای) عوض کنه.
    """
    if not is_in_tutorial(player):
        return None
    step = player.get("tutorial_step", STEP_AWAIT_ATTACK)

    if step in (STEP_AWAIT_ATTACK, STEP_AWAIT_KILL):
        if killed:
            player["tutorial_step"] = STEP_AWAIT_LOOT
            return LOOT_STEP_MARK + _first_kill_text()
        if step == STEP_AWAIT_ATTACK:
            player["tutorial_step"] = STEP_AWAIT_KILL
            return (
                "\n\n🧭 **قدمِ دوم:** دشمن هنوز زندست! رو «⚔️ ادامه نبرد» "
                "بزن تا کارش رو تموم کنی."
            )
        return "\n\n🧭 یه ضربه‌ی دیگه بزن، نزدیکه!"

    return None


def on_loot_visited(player: dict) -> str | None:
    """
    وقتی بازیکن اولین‌بار وارد یه لوکیشن رو نقشه می‌شه (cb_loot_location
    تو loot_handlers.py) صدا زده می‌شه. اگه تو قدمِ STEP_AWAIT_LOOT
    باشه، تیوتوریال رو کامل می‌کنه و پنلِ کامل رو باز می‌کنه.
    خروجی، وقتی تیوتوریال همین‌جا تموم بشه، با GRADUATION_MARK شروع
    می‌شه تا caller بفهمه باید main_kb کامل رو دوباره بفرسته.
    """
    if not is_in_tutorial(player):
        return None
    if player.get("tutorial_step") != STEP_AWAIT_LOOT:
        return None
    player["tutorial_step"] = STEP_DONE
    player["tutorial_done"] = True
    return GRADUATION_MARK + _graduation_text()


# پیام‌هایی که با این پیشوند شروع بشن یعنی «تیوتوریال همین الان تموم شد» —
# caller (combat_handlers.py) باید بعدِ نمایشِ نتیجه، main_kb رو هم بفرسته.
GRADUATION_MARK = "\u2063"  # یه کاراکترِ نامرئی (invisible separator) — تو UI دیده نمی‌شه

# پیام‌هایی که با این پیشوند شروع بشن یعنی «قدمِ کیل تموم شد، برو سراغِ
# لوت» — caller باید کیبورد رو به tutorial_kb_loot (سه‌دکمه‌ای) عوض کنه.
LOOT_STEP_MARK = "\u2064"


def strip_graduation_mark(text: str) -> str:
    for mark in (GRADUATION_MARK, LOOT_STEP_MARK):
        if text.startswith(mark):
            return text[len(mark):]
    return text


def _first_kill_text() -> str:
    return (
        "\n\n🎉 **آفرین، اولین کشتنت رو ثبت کردی!**\n"
        "🧭 **قدمِ سوم:** حالا رو «🗺 لوت» بزن — برو تو نقشه، یه مپ "
        "انتخاب کن، یه لوکیشن رو بگرد. اونجا غنیمتِ بیشتری هست."
    )


def _graduation_text() -> str:
    return (
        "\n\n🎉 **آفرین، اولین کشتنت رو ثبت کردی!**\n"
        "حالا کل پنل برات باز شد 🔓 — یه نقطه‌ی شروعِ خوب:\n"
        "🗺 لوت: برو تو نقشه بگرد، لوکیشن کشف کن، غنیمتِ بیشتر بگیر "
        "(بالای هر مپ می‌بینی این‌جا چه خبره — دنیا زنده‌ست).\n"
        "بقیه‌ی پنل (گیلد، بازار، PvP، کدکس...) هم از پایینِ صفحه در "
        "دسترسته، هروقت خواستی سراغشون برو.\n\n"
        "💌 اگه لذت بردی، یکی رو با /start دعوت کن — هرچی بیشتر باشیم، "
        "دنیا زنده‌تره."
    )
