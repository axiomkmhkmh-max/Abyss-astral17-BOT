# ============================================================
#  ASTRAL ABYSS RPG BOT — Main (Final Clean Version)
#  Python 3.11+ | aiogram 3.x
# ============================================================
import asyncio
import logging
import os
import random
import re
import sys
import time

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode, ButtonStyle
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, ErrorEvent, FSInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats,
)
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup

from characters import ALL_CHARACTERS, RANDOM_CHAR_NAMES, RARITY_EMOJI, SPECIAL_CHARACTERS
from game_data import (
    xp_for_level, RARITY_COLOR, effective_max_level,
)
from database import (
    get_player, save_player, create_player, all_players,
    assign_random_char, assign_special_char,
)
from class_system import (
    CLASSES, CLASS_ADVENTURER, CLASS_MERCHANT, CLASS_HEALER, CLASS_WIZARD,
    class_selection_kb, class_selection_text,
    apply_class_to_player, class_card_text,
)
from isekai_theme import map_label, rank_line


# ─── FSM: فلوی ساختِ کاراکترِ جدید (اسم → کلاس) ─────────────────
class CharCreation(StatesGroup):
    waiting_name = State()
from account_link import generate_link_code, redeem_link_code, link_status_text
from admin_panel import is_admin, ADMIN_IDS
from logger import set_bot, send_log, log_sync
from emoji_formatting import premiumize

# ─── Config ──────────────────────────────────────────────────
TOKEN = os.getenv("BOT_TOKEN", "")

# ─── لیست دستورات برای منوی «/» تلگرام ─────────────────────────
# این لیست همون چیزیه که وقتی کاربر تو یه گروه یا PV با ربات، "/"
# رو تایپ می‌کنه، زیرِ باکس پیام بهش نشون داده می‌شه (اسم دستور +
# توضیح کوتاه). دستورات ادمین (ban, broadcast, givechar, ...) عمداً
# این‌جا نیستن چون این منو برای همه‌ی کاربرا (حتی غریبه‌ها تو گروه)
# دیده می‌شه.
GROUP_COMMANDS = [
    BotCommand(command="start", description="🌌 شروع ماجراجویی"),
    BotCommand(command="help", description="❓ راهنمای دستورات"),
    BotCommand(command="status", description="📊 وضعیت شخصیت"),
    BotCommand(command="class", description="⚜️ قدرت‌های فعالِ کلاس"),
    BotCommand(command="inventory", description="🎒 کوله‌پشتی"),
    BotCommand(command="characters", description="🃏 شخصیت‌ها"),
    BotCommand(command="stand", description="👻 استند من"),
    BotCommand(command="codex", description="📖 کدکس"),
    BotCommand(command="loot", description="🗺️ سفر و غارت"),
    BotCommand(command="boss", description="👹 نبرد با باس"),
    BotCommand(command="pvp", description="⚔️ نبرد PvP"),
    BotCommand(command="teampvp", description="🛡️ PvP تیمی (۲به۲ تا ۵به۵)"),
    BotCommand(command="warmap", description="🗺️ نقشه‌ی جنگِ گیلدها"),
    BotCommand(command="shop", description="🛒 فروشگاه"),
    BotCommand(command="bazaar", description="🏮 بازارِ بزرگ"),
    BotCommand(command="quests", description="📜 ماموریت‌ها"),
    BotCommand(command="guilds", description="🏰 گیلدها"),
    BotCommand(command="top", description="🏆 رده‌بندی برترین‌ها"),
    BotCommand(command="pulse", description="💓 ضربان زندهٔ سرور"),
    BotCommand(command="link", description="🔗 اتصال حساب (تلگرام ⇄ گپ)"),
]

# تو PV می‌تونیم چند تا دستورِ شخصی‌تر رو هم اضافه کنیم که تو گروه
# لازم نیست همه ببینن (مثل bank/house که خصوصی‌ترن).
PRIVATE_COMMANDS = GROUP_COMMANDS + [
    BotCommand(command="bank", description="🏦 بانک"),
    BotCommand(command="house", description="🏠 خانه"),
    BotCommand(command="stats", description="📈 آمار کامل"),
    BotCommand(command="skills", description="✨ مهارت‌ها"),
]

# لاگ‌های سطحِ INFO رو به stdout هدایت می‌کنیم و فقط WARNING به بالا
# می‌ره به stderr — چون basicConfig پیش‌فرض همه‌چی رو (حتی INFO) روی
# stderr می‌نویسه، و Railway هر خطِ stderr رو با severity="error"
# نشون می‌ده، حتی اگه خودِ متنش بگه "INFO". این باعث می‌شه لاگ‌های
# عادیِ aiogram (مثلِ "Update id=... is handled") اشتباهی قرمز و
# error دیده بشن، درحالی‌که ربات کاملاً سالمه.
_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setLevel(logging.DEBUG)
_stdout_handler.addFilter(lambda record: record.levelno < logging.WARNING)

_stderr_handler = logging.StreamHandler(sys.stderr)
_stderr_handler.setLevel(logging.WARNING)

logging.basicConfig(level=logging.INFO, handlers=[_stdout_handler, _stderr_handler])
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

# ─── نگه‌داشتنِ رفرنسِ تسک‌های پس‌زمینه ────────────────────────────
# 🆕 باگ‌فیکس: قبلاً همه‌جا مستقیم asyncio.create_task(...) صدا زده
# می‌شد بدونِ اینکه نتیجه‌ش (Task) جایی نگه داشته بشه. طبقِ مستندِ خودِ
# asyncio: «event loop فقط weak reference به تسک‌ها نگه می‌داره — تسکی
# که رفرنسِ دیگه‌ای بهش نباشه، ممکنه هر لحظه (حتی وسطِ اجرا) گاربیج‌کالکت
# بشه». دقیقاً همین باعث می‌شد notify_players_restart بعضی وقت‌ها اصلاً
# پیام نفرسته — نه ارور می‌داد نه لاگ می‌کرد، چون خودِ تسک قبل از تمومِ
# حلقه از بین می‌رفت. حالا هر تسکِ پس‌زمینه با _spawn_task ساخته می‌شه
# که یه رفرنسِ زنده تو _background_tasks نگه می‌داره تا تسک تمومِ کارش
# رو انجام بده.
_background_tasks: set = set()

def _spawn_task(coro):
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task
dp  = Dispatcher(storage=MemoryStorage())

# ─── ایموجی‌های پرمیوم در کل ربات (سراسری) ──────────────────────
# این middleware روی سطح session نصب می‌شه، یعنی جلوی هر درخواستی
# که به تلگرام می‌ره (send_message, edit_message_text, caption عکس/
# ویدیو، و ...) رو می‌گیره و متن رو از تابع premiumize() رد می‌کنه:
#   ۱) هر ایموجی معمولی که تو premium_emojis.py ثبت شده، خودکار به
#      ایموجی پرمیوم (custom emoji) تبدیل می‌شه.
#   ۲) فرمت Markdown سبک قدیمی (*bold*, _italic_, `code`, [متن](لینک))
#      به HTML تبدیل می‌شه، چون custom emoji فقط با parse_mode=HTML کار می‌کنه.
# نتیجه: هیچ هندلری (combat, shop, quest, guild, katana, و ...) لازم
# نیست چیزی رو دستی صدا بزنه — همه‌جای ربات خودکار پرمیوم می‌شه.
# Premium emoji support: aiogram 3 compatible
_EDIT_METHOD_NAMES = {
    "EditMessageText", "EditMessageCaption", "EditMessageReplyMarkup", "EditMessageMedia",
}


@bot.session.middleware()
async def premium_emoji_middleware(make_request, bot_, method):
    if hasattr(method, "parse_mode"):
        for field in ("text", "caption"):
            value = getattr(method, field, None)
            if isinstance(value, str) and value:
                setattr(method, field, premiumize(value))
        method.parse_mode = ParseMode.HTML
    try:
        return await make_request(bot_, method)
    except TelegramBadRequest as e:
        # وقتی هندلری می‌خواد پیام رو edit کنه ولی متن/دکمه‌ها دقیقاً همونیه
        # که الان رو صفحه‌ست (مثلاً بازیکن دوباره رو همون نبرد باخت، یا دوباره
        # رو یه دکمه‌ی «رفرش» زد)، تلگرام ارور «message is not modified» می‌ده.
        # قبلاً این ارور کلِ هندلر رو می‌ترکوند و چون کدِ بعدِ edit (از جمله
        # cb.answer()) هیچ‌وقت اجرا نمی‌شد، از دیدِ بازیکن دکمه «کار نمی‌کرد».
        # این‌جا سراسری (برای هر هندلری، الان یا آینده) بی‌خطر نادیده‌اش
        # می‌گیریم؛ بقیه‌ی ارورهای تلگرام عادی raise می‌شن.
        if type(method).__name__ in _EDIT_METHOD_NAMES and "message is not modified" in str(e):
            return True
        raise
    except TelegramNetworkError as e:
        # قطعی/افت لحظه‌ای شبکه (SSL, timeout, connection reset و ...) بین ما و
        # تلگرام. برای AnswerCallbackQuery (همون toastِ بالای صفحه) این خطا
        # بی‌اهمیته — نه دیتایی از دست می‌ره نه چیزی به کاربر دیده نمی‌شه اگه
        # toast نره؛ ولی قبلاً چون raise می‌شد، کل هندلر (از جمله edit_text
        # بعدش که نتیجه‌ی واقعی نبرد رو نشون می‌ده) کرش می‌کرد. حالا فقط لاگ
        # می‌کنیم و بی‌خطر رد می‌شیم؛ برای بقیه‌ی متدها (پیام فرستادن/edit)
        # چون واقعاً چیزی به کاربر نرسیده، همچنان raise می‌کنیم.
        if type(method).__name__ == "AnswerCallbackQuery":
            logging.warning(f"⚠️ Network error on AnswerCallbackQuery (ignored): {e}")
            return None
        raise

# ─── هندلر خطای سراسری ──────────────────────────────────────────
# قبلاً هیچ‌جای کد یه catch سراسری برای خطاهای هندلرها نبود — یعنی
# هر باگی که تو یه هندلر (پیام یا دکمه‌ی شیشه‌ای) کرش می‌کرد، کاربر
# فقط سکوت می‌دید (نه پیام خطا، نه توست) و خودمون هم چیزی تو لاگ
# نمی‌دیدیم. حالا هر کرش هم لاگ می‌شه هم یه پیام/توستِ خطا به کاربر
# نشون داده می‌شه، تا این‌جور باگ‌ها دیگه «بی‌صدا» نمونن.
# ─── گیتِ سراسریِ «جنسیتِ کاراکتر» ────────────────────────────────
# قبلاً پلیرهای قدیمی که از قبل کاراکتر داشتن، خاموش روی "male" ست
# می‌شدن و هیچ‌وقت ازشون پرسیده نمی‌شد. حالا با این middleware، هر
# پیامی که از یه پلیرِ دارایِ کاراکتر ولی gender_chosen=False بیاد،
# قبل از رسیدن به هندلرِ اصلی گیر می‌افته و کیبوردِ انتخابِ جنسیت
# نشون داده می‌شه — چه پلیر قدیمی باشه چه وسطِ مسیرِ ساختِ کاراکترِ
# جدید. بعدِ یه‌بار پرسیدن (پرچمِ _awaiting_gender) دیگه هر پیام
# اسپم نمی‌شه؛ منتظرِ تپ‌زدن رو دکمه می‌مونه.
@dp.message.middleware()
async def gender_gate_middleware(handler, event: Message, data: dict):
    uid = event.from_user.id if event.from_user else None
    if uid:
        player = get_player(uid)
        if (
            player
            and player.get("character")
            and not player.get("gender_chosen", False)
            and not player.get("_awaiting_gender")
        ):
            player["_awaiting_gender"] = True
            player["_gender_retro"] = True  # علامتِ «این یه گیتِ عقب‌گردیه، نه ساختِ کاراکترِ جدید»
            save_player(uid, player)
            await event.answer(
                "🆕 یه فیچرِ جدید اضافه شده: جنسیتِ کاراکترِ خودت رو مشخص کن\n\n"
                f"🎴 {player['character']}",
                reply_markup=GENDER_KB,
            )
            return
    return await handler(event, data)


@dp.errors()
async def global_error_handler(event: ErrorEvent):
    exc = event.exception
    update = event.update
    # 🆕 باگ‌فیکس: قبلاً لاگ فقط نوعِ خطا + پیامش رو نشون می‌داد
    # («KeyError: 'token'») و هیچ traceback‌ای نبود — یعنی معلوم نمی‌شد
    # دقیقاً کدوم فایل/خط/تابع باعثِ کرش شده. الان کل traceback + آیدیِ
    # کاربر + دیتاِیِ callback (اگه بود) لاگ می‌شه تا دفعه‌ی بعد این‌جور
    # خطاها بلافاصله قابلِ ردیابی باشن.
    try:
        import traceback
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        uid = None
        extra = ""
        if update.callback_query:
            uid = update.callback_query.from_user.id
            extra = f"\n🔘 callback_data: `{update.callback_query.data}`"
        elif update.message:
            uid = update.message.from_user.id
            extra = f"\n💬 text: `{update.message.text}`"
        # تلگرام هر پیام رو تا ۴۰۹۶ کاراکتر قبول می‌کنه — traceback رو کوتاه نگه می‌داریم
        if len(tb) > 3000:
            tb = tb[-3000:]
        log_sync(f"🔴 **UNHANDLED ERROR** (uid: `{uid}`){extra}\n```\n{tb}\n```", "ERROR")
    except Exception:
        pass
    try:
        if update.callback_query:
            await update.callback_query.answer("⚠️ یه مشکلی پیش اومد، دوباره امتحان کن!", show_alert=True)
        elif update.message:
            await update.message.answer("⚠️ یه مشکلی پیش اومد، دوباره امتحان کن!")
    except Exception:
        pass
    return True

# ─── Spawn Maps ──────────────────────────────────────────────
SPAWN_MAPS = [
    "Verdant Vale", "Frostheim", "Sands of Eternity",
    "Azure Tides Empire", "Ruins of Orion-7", "Clockwork Depths",
    "Holy Luminarchy", "The Sunken City", "Stormward Archipelago",
]

SPAWN_MESSAGES = [
    "🌟 از اعماق تاریکی ظاهر شدی در **{map}**!\nجنگجو، آماده باش...",
    "⚡ پورتالی باز شد و تو رو به **{map}** انداخت!\nدنیای Astral Abyss منتظرته!",
    "🌀 گرداب سرنوشت تو رو به **{map}** کشید!\nکاتانات رو محکم بگیر...",
    "🔮 نیروهای باستانی تو رو در **{map}** اسپان کردن!\nسرنوشتت اینجاست!",
]

# ─── Online Tracking ─────────────────────────────────────────
last_seen: dict[int, float] = {}
OFFLINE_THRESHOLD = 300  # 5 minutes

def update_last_seen(uid: int):
    last_seen[uid] = time.time()

def is_online(uid: int) -> bool:
    return time.time() - last_seen.get(uid, 0) < OFFLINE_THRESHOLD

# ─── جایزه‌ی ورودِ روزانه (Login Streak) ───────────────────────
# پاداشِ کوچیک برای واردشدنِ پشت‌سرهم هر روز — جدا از ماموریت‌های
# روزانه‌ی موجود (که برای انجام‌دادن کار داخل بازیه، نه صرفِ سربزدن).
DAILY_LOGIN_REWARDS = [0, 200, 300, 400, 500, 700, 900, 1500]  # ایندکس ۱..۷ (روز هفته)

def grant_daily_login(player: dict) -> str | None:
    """اگه امروز اولین ورودِ بازیکنه، Zen بهش می‌ده و متنِ پیام رو برمی‌گردونه؛
    وگرنه None (یعنی امروز قبلاً گرفته)."""
    today = int(time.time() // 86400)
    last_day = player.get("last_login_day", -1)
    if today == last_day:
        return None
    if today == last_day + 1:
        player["login_streak"] = player.get("login_streak", 0) + 1
    else:
        player["login_streak"] = 1
    player["last_login_day"] = today
    day_in_cycle = ((player["login_streak"] - 1) % 7) + 1
    reward = DAILY_LOGIN_REWARDS[day_in_cycle]
    player["zen"] = player.get("zen", 0) + reward
    return (
        f"📅 **پاداش ورود روزانه (روز {day_in_cycle}/۷)**\n"
        f"💰 +{reward:,} Zen — استریک: {player['login_streak']} روز 🔥"
    )

# ─── Keyboards ───────────────────────────────────────────────

# دسته‌بندیِ پنل‌ها — هر دسته یه زیرمنو داره؛ عنوانِ هر دسته بالای زیرمنو نشون داده می‌شه
#
# ─── نقشه‌ی کلاس ↔ پنل (طبقِ درخواستِ پروژه) ────────────────────
#   🗺️ ماجراجو → نبرد/باس/استند/کاتانا/کوئست/لوت/کوئست‌لاینِ شکار +
#                PvP و رده‌بندی و ایونت (این سه‌تا هم فقط مخصوصِ ماجراجوئن)
#   💰 تاجر    → سفر (بازدید از مغازه‌ی بقیه)/فروش (مغازه‌ی من)/بازار سیاه
#   ✨ درمانگر → بیمارستان/درمان
#   🧙 جادوگر  → کارگاه (کرفتینگ/آلکمی + صرافیِ متریال از همون‌جا)
#                نبردِ جادوگر از طریقِ «⚜️ قدرت‌های کلاس» (Spell Synergy) هست،
#                نه کاتانا/سیستمِ ماجراجو.
#   🏰 گیلد    → مشترک بینِ همه‌ی کلاس‌ها
#
# دسته‌های "من"/"اجتماعی"/"اقتصاد"/"اطلاعات"/"زندگی" هم مشترک موندن
# (طبقِ تأییدِ پروژه) — فقط بیمارستان/استندِ من/بازارِ سیاه/مغازه‌ی من/
# PvP/رده‌بندی/ایونت که کلاس‌محور شدن، ازشون درآورده شدن.
#
# کلیدِ "class_only" اگه None باشه یعنی دسته برای همه‌ی کلاس‌ها نشون
# داده می‌شه؛ وگرنه فقط برای همون کلاس (از class_system.CLASS_*).
CATEGORIES: dict[str, dict] = {
    "ماجراجو": {
        "title": "🗺️ *ماجراجو*",
        "class_only": CLASS_ADVENTURER,
        "buttons": [
            "حمله", "لوت", "باس جهانی", "شکار جایزه", "حلقه‌ی سایه", "نمسیس من",
            "👻 استند من", "🗡 کاتانا", "📜 کوئست‌های جانبی", "🏹 کوئست‌لاینِ شکار",
            "⚜️ قدرت‌های کلاس", "PvP", "🏟 آرنا", "رده‌بندی", "ایونت", "🌀 شکاف Abyss",
            "🐎 مونت‌ها", "🌌 هم‌گرایی", "🕊 الهه",
        ],
    },
    "تاجر": {
        "title": "💰 *تاجر*",
        "class_only": CLASS_MERCHANT,
        "buttons": ["🚶 سفر", "🤝 معامله‌ی روزانه", "مغازه‌ی من", "بازار سیاه", "⚜️ قدرت‌های کلاس"],
    },
    "درمانگر": {
        "title": "✨ *درمانگر*",
        "class_only": CLASS_HEALER,
        "buttons": ["بیمارستان", "🩺 نوبت‌دهی", "💊 درمان", "⚜️ قدرت‌های کلاس"],
    },
    "جادوگر": {
        "title": "🧙 *جادوگر*",
        "class_only": CLASS_WIZARD,
        "buttons": ["🛠 کارگاه", "🔮 مشتری‌ها", "⚜️ قدرت‌های کلاس"],
    },
    "گیلد": {
        "title": "🏰 *گیلد*",
        "class_only": None,
        "buttons": ["گیلدها"],
    },
    "من": {
        "title": "📊 *شخصیتِ من*",
        "class_only": None,
        "buttons": ["وضعیت", "کوله‌پشتی", "🎽 تجهیزات", "🎴 کارت من", "📖 کدکس", "مهارت‌ها", "دستاوردها", "تیر جهان", "🔗 اتصال حساب"],
    },
    "اجتماعی": {
        "title": "🏛 *اجتماعی*",
        "class_only": None,
        "buttons": ["تیم", "معامله", "ردیابی"],
    },
    "اقتصاد": {
        "title": "💰 *اقتصاد و بازار*",
        "class_only": None,
        "buttons": ["حراجی", "کازینو", "📜 تابلوی کارگزار", "بانک"],
    },
    "اطلاعات": {
        "title": "📖 *اطلاعات*",
        "class_only": None,
        "buttons": ["کدکس", "پس نبرد"],
    },
    "زندگی": {
        "title": "🏠 *زندگی در Abyss*",
        "class_only": None,
        "buttons": ["ملک شخصی", "استادی"],
    },
}


def visible_categories_for(player: dict | None) -> list[str]:
    """اسمِ اون دسته‌هایی که با کلاسِ بازیکن سازگارن (یا مشترکن) رو
    به همون ترتیبِ تعریف‌شده تو CATEGORIES برمی‌گردونه."""
    cls = (player or {}).get("class")
    return [key for key, cat in CATEGORIES.items() if cat.get("class_only") in (None, cls)]


# حداقل سطحِ لازم برای هر دکمه — پیش‌فرض‌های قابلِ تنظیم؛ هرچی نیاز داری تغییرشون بده
LEVEL_REQUIREMENTS: dict[str, int] = {
    "حمله": 1, "لوت": 1, "باس جهانی": 5, "شکار جایزه": 5, "حلقه‌ی سایه": 12, "نمسیس من": 1,
    "👻 استند من": 1, "🗡 کاتانا": 1, "📜 کوئست‌های جانبی": 1, "🏹 کوئست‌لاینِ شکار": 1,
    "⚜️ قدرت‌های کلاس": 1, "PvP": 5, "🏟 آرنا": 5, "رده‌بندی": 1, "ایونت": 1, "🌀 شکاف Abyss": 15,
    "🐎 مونت‌ها": 1, "🌌 هم‌گرایی": 1, "🕊 الهه": 1,
    "🚶 سفر": 1, "🤝 معامله‌ی روزانه": 1, "مغازه‌ی من": 12, "بازار سیاه": 1,
    "بیمارستان": 1, "🩺 نوبت‌دهی": 1, "💊 درمان": 1,
    "🛠 کارگاه": 1, "🔮 مشتری‌ها": 1,
    "گیلدها": 10,
    "وضعیت": 1, "کوله‌پشتی": 1, "🎽 تجهیزات": 1, "🎴 کارت من": 1, "📖 کدکس": 1, "مهارت‌ها": 1, "دستاوردها": 1, "تیر جهان": 1, "🔗 اتصال حساب": 1,
    "تیم": 5, "معامله": 10, "ردیابی": 5,
    "حراجی": 12, "کازینو": 10, "📜 تابلوی کارگزار": 12, "بانک": 1,
    "کدکس": 1, "پس نبرد": 1,
    "ملک شخصی": 12, "استادی": 1,
}

# ─── آیکونِ ایموجیِ پرمیوم برای دکمه‌ها ─────────────────────────
# هر دکمه (چه Reply Keyboard چه Inline) که با یکی از این ایموجی‌های
# یونیکد شروع بشه، آیدیِ Custom Emoji متناظرش (از premium_emojis.py)
# به‌عنوانِ icon_custom_emoji_id بهش اضافه می‌شه — این فیلد از
# Bot API 9.4 هست و فقط وقتی مالکِ ربات تلگرام پرمیوم داره کار می‌کنه.
# اگه ایموجیِ دکمه‌ای این‌جا نباشه یعنی توی premium_emojis.py آیدیِ
# متناظرش پیدا نشد — دکمه بدون آیکون (ولی با همون ایموجیِ یونیکد
# داخلِ متنش) نمایش داده می‌شه.
BUTTON_ICON_IDS: dict[str, str] = {
    "⚔️": "5454014806950429357",
    "📊": "5231200819986047254",
    "📖": "5226512880362332956",
    "👹": "5372951839018850336",
    "🎯": "5310278924616356636",
    "🗡️": "5373342608028352831",
    "🏥": "5264827875588077689",
    "🌟": "5458799228719472718",
    "🏅": "5334644364280866007",
    "🌍": "5399898266265475100",
    "👥": "5453957997418004470",
    "🤝": "5372957680174384345",
    "🔍": "5188217332748527444",
    "🏦": "5264895611517300926",
    "🏆": "5226431245918942763",
    "🎫": "5418010521309815154",
    "🏠": "5465226866321268133",
    "🎓": "5375163339154399459",
    "🔙": "5253997076169115797",
    "🔒": "5296369303661067030",
    "💰": "5375312095346704820",
    "🗺": "5391032818111363540",
    "🩸": "5463250708918711044",
    "🎒": "5240114075421149047",
    "🆚": "5909260380886014884",
    "🖤": "5465384878168102994",
    "🏛": "5359778044745622115",
    "🏛️": "5359778044745622115",
    "🎰": "5875360259853263196",
    "🏪": "5278702045883292456",
    "📅": "5413879192267805083",
}


def btn_icon(text: str) -> str | None:
    """آیدیِ ایموجیِ پرمیومِ متناظر با شروعِ متنِ دکمه رو برمی‌گردونه (یا None)."""
    for prefix, icon_id in BUTTON_ICON_IDS.items():
        if text.startswith(prefix):
            return icon_id
    return None


_LOCKED_BTN_RE = re.compile(r".*\(سطح \d+\)$")


def is_locked_button_text(text: str) -> bool:
    """چون آیکونِ 🔒 دیگه توی متنِ خودِ دکمه نیست (فقط icon_custom_emoji_id هست)،
    دکمه‌ی قفل رو با الگوی «(سطح N)» در انتهای متن تشخیص می‌دیم."""
    return bool(text and _LOCKED_BTN_RE.match(text))


BACK_TO_MAIN = "بازگشت به پنل اصلی"

# دکمه‌ی «داستان اصلی» — دو حالتِ متن (عادی / بج جدید) برای همون شورتکات
STORY_BUTTON_TEXT     = "📖 داستان اصلی"
STORY_BUTTON_TEXT_NEW = "📖 داستان اصلی 🆕"

# شورتکاتِ بالای صفحه — پرتکرارترین اکشن‌ها، بدون نیاز به وارد شدن به زیرمنو
SHORTCUT_BUTTONS = ["حمله", "وضعیت", STORY_BUTTON_TEXT]

# ─── پنلِ گروه vs پنلِ پیوی ────────────────────────────────────
# قبلاً گروه فقط دسته‌های «گروهی/نمایشی» رو نشون می‌داد و دسته‌های
# شخصی (شخصیتِ من، اقتصاد، زندگی در Abyss) مخصوصِ پیوی بودن. حالا
# طبقِ درخواست، پنلِ گروه دقیقاً همونِ پنلِ پیویه — همه‌ی دسته‌ها و
# شورتکات‌ها تو گروه هم در دسترسن. علاوه‌براین
# هر دو پنل حالا بر اساسِ کلاسِ بازیکن فیلتر می‌شن (visible_categories_for).
GROUP_SHORTCUT_BUTTONS = SHORTCUT_BUTTONS


def _is_group_chat(chat_type: str) -> bool:
    return chat_type != "private"


def main_kb(is_group: bool = False, story_badge: bool = False, player: dict | None = None) -> ReplyKeyboardMarkup:
    shortcuts = list(GROUP_SHORTCUT_BUTTONS if is_group else SHORTCUT_BUTTONS)
    cat_names = visible_categories_for(player)

    if story_badge:
        shortcuts = [STORY_BUTTON_TEXT_NEW if b == STORY_BUTTON_TEXT else b for b in shortcuts]

    rows = []
    if len(shortcuts) <= 3:
        rows.append([KeyboardButton(text=b, style=ButtonStyle.SUCCESS, icon_custom_emoji_id=btn_icon(b)) for b in shortcuts])
    else:
        for i in range(0, len(shortcuts), 2):
            chunk = shortcuts[i:i+2]
            rows.append([KeyboardButton(text=b, style=ButtonStyle.SUCCESS, icon_custom_emoji_id=btn_icon(b)) for b in chunk])
    for i in range(0, len(cat_names), 2):
        pair = cat_names[i:i+2]
        rows.append([KeyboardButton(text=c, style=ButtonStyle.PRIMARY, icon_custom_emoji_id=btn_icon(c)) for c in pair])
    # selective=True یعنی این کیبورد فقط برای همون کاربری که پیامش
    # جواب داده شده نشون داده می‌شه — نه کل گروه. برای اینکه واقعاً
    # اثر کنه، پیامی که این کیبورد رو حمل می‌کنه باید reply روی پیام
    # همون کاربر باشه (به‌جای msg.answer از msg.reply استفاده کن).
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, selective=True)


def _story_badge_for(player: dict | None) -> bool:
    """آیا دکمه‌ی «داستان اصلی» باید بج «🆕» بگیره؟ (یه فصلِ نوشته‌شده‌ی
    جدید باز شده که بازیکن هنوز شروعش نکرده)."""
    if not player:
        return False
    try:
        from quest_engine import story_new_chapter_available
        return story_new_chapter_available(player) is not None
    except Exception:
        return False


def _story_panel_reminder(player: dict | None) -> str:
    """متنِ یادآوریِ کوتاه که موقعِ بازکردنِ پنل اصلی، اگه فصلِ جدیدی باز
    شده باشه، به پیام اضافه می‌شه."""
    if not player:
        return ""
    try:
        from quest_engine import story_new_chapter_available
        ch = story_new_chapter_available(player)
    except Exception:
        ch = None
    if not ch:
        return ""
    return f"\n\n📖 فصل جدید باز شده: **{ch['title']}** ({ch['map']}) — بزن رو «{STORY_BUTTON_TEXT}»!"


def category_kb(category_key: str, player_level: int) -> ReplyKeyboardMarkup:
    buttons = CATEGORIES[category_key]["buttons"]
    rows = []
    for i in range(0, len(buttons), 2):
        row = []
        for b in buttons[i:i+2]:
            req = LEVEL_REQUIREMENTS.get(b, 1)
            if player_level >= req:
                row.append(KeyboardButton(text=b, style=ButtonStyle.PRIMARY, icon_custom_emoji_id=btn_icon(b)))
            else:
                locked_text = f"🔒 {b} (سطح {req})"
                row.append(KeyboardButton(text=f"{b} (سطح {req})", style=ButtonStyle.DANGER, icon_custom_emoji_id=btn_icon(locked_text)))
        rows.append(row)
    rows.append([KeyboardButton(text=BACK_TO_MAIN, style=ButtonStyle.DANGER, icon_custom_emoji_id=btn_icon(BACK_TO_MAIN))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, selective=True)

# ─── ناوبریِ پنل‌ها (باز کردنِ زیرمنو، بازگشت، دکمه‌ی قفل) ───────
@dp.message(F.text.in_(CATEGORIES.keys()))
async def cmd_category_menu(msg: Message, state: FSMContext):
    await state.clear()
    uid = msg.from_user.id
    update_last_seen(uid)
    player = get_player(uid)
    if not player or not player.get("class"):
        await msg.answer("❌ اول باید کاراکترت رو بسازی! /start رو بزن.")
        return
    cat = CATEGORIES[msg.text]
    only = cat.get("class_only")
    if only is not None and only != player.get("class"):
        # این دسته مخصوصِ یه کلاسِ دیگه‌ست — کیبورد رو با پنلِ درستِ خودش تازه می‌کنیم
        await msg.reply(
            "🔒 این پنل مخصوصِ کلاسِ دیگه‌ایه — این‌جا پنلِ خودتُ داری:",
            reply_markup=main_kb(is_group=_is_group_chat(msg.chat.type), player=player),
        )
        return
    await msg.reply(cat["title"], reply_markup=category_kb(msg.text, player.get("level", 1)))

@dp.message(F.text == BACK_TO_MAIN)
async def cmd_back_to_main(msg: Message, state: FSMContext):
    await state.clear()
    uid = msg.from_user.id
    update_last_seen(uid)
    is_group = _is_group_chat(msg.chat.type)
    player = get_player(uid)
    badge = _story_badge_for(player)
    text = "🌑 پنل اصلی:" + _story_panel_reminder(player)
    await msg.reply(text, reply_markup=main_kb(is_group=is_group, story_badge=badge, player=player))

def _locked_button_filter(msg: Message) -> bool:
    return is_locked_button_text(msg.text or "")


@dp.message(_locked_button_filter)
async def cmd_locked_button(msg: Message):
    await msg.answer("🔒 این قابلیت هنوز باز نشده — با بالا رفتنِ سطحت باز می‌شه.")

# ─── 📖 محتوای راهنما (داده‌ی خام) ──────────────────────────────
# پنلِ «آموزش» (دکمه + منوی inline) حذف شده؛ این دیکشنری فقط به‌عنوانِ
# داده باقی مونده چون توسطِ آموزشِ خودکارِ پنل (پایین‌تر در همین فایل)
# استفاده می‌شه که اولین‌باری که بازیکنِ کم‌سطح یه پنل رو باز می‌کنه
# توضیحش رو خودکار می‌فرسته.
TUTORIAL_SECTIONS: dict[str, dict] = {
    "status": {
        "title": "وضعیت",
        "text": (
            "📊 **دکمه‌ی وضعیت**\n\n"
            "با این دکمه (یا /status) وضعیتِ فعلیِ کاراکترت رو می‌بینی:\n"
            "• ⭐ سطح و XP فعلی\n"
            "• ❤️ مقدار جون (HP)\n"
            "• 💰 مقدار پول (Zen)\n"
            "• 🗺 نقشه‌ای که الان توشی — برای PvP مهمه، چون فقط کسایی که تو یه نقشه‌ن می‌تونن به هم حمله کنن\n"
            "• 💀 تعداد کشته‌ها\n"
            "• 🌟 امتیازِ مهارت — با هر لول‌آپ می‌گیری و توی «🌟 مهارت‌ها» خرجش می‌کنی تا باف باز کنی\n\n"
            "این صفحه بهترین جا برای چک کردنِ سریعِ اوضاعته."
        ),
    },
    "attack": {
        "title": "حمله",
        "text": (
            "⚔️ **دکمه‌ی حمله**\n\n"
            "برای کشتنِ انمی‌های عادی از این دکمه استفاده می‌کنی. وقتی می‌زنیش، اول باید"
            " سبکِ حمله رو انتخاب کنی و بعد اینکه با کدوم موجود بجنگی:\n\n"
            "⚡ **سریع** — دمیج کمتر ولی کول‌داونِ کوتاه (۱۰ ثانیه)؛ برای ضربه‌های پشتِ‌سرهم خوبه.\n"
            "💥 **قوی** — دمیج بالاتر و سپرِ دشمن رو می‌شکنه، ولی کول‌داونش بیشتره (۳۰ ثانیه).\n"
            "🌀 **عنصری** — اثرِ خاصِ عنصری می‌زنه (مثل سوختگی، زهر، بیهوشی...)، کول‌داون ۲۰ ثانیه.\n"
            "🔥 **کومبو** — دمیجِ خیلی بالا، ولی فقط وقتی combo (تویِ 📊 وضعیت دیده می‌شه) بالا باشه فعاله.\n"
            "☄️ **ضربه‌ی نهایی** — بیشترین دمیج و بخشی از دفاعِ دشمن رو نادیده می‌گیره؛ فقط وقتی گیجِ خشمت پره فعال می‌شه.\n"
            "🛡️ **پری/کانتر** — دمیجِ پایه‌ش کمه ولی اگه تایمینگش درست باشه، ضدحمله‌ی دشمن رو خنثی می‌کنه و کانترِ قوی می‌زنی؛ ریسکِ بالا-پاداشِ بالا.\n\n"
            "هر سبک حمله کول‌داونِ جدا داره، پس می‌تونی بینشون بچرخی."
        ),
    },
    "me": {
        "title": "من",
        "text": (
            "📊 **منوی «من»**\n\n"
            "همه‌چیزهایی که به شخصِ تو مربوطه اینجاست:\n"
            "🎒 **کوله‌پشتی** — لوت‌ها و آیتم‌هایی که تو نبرد/لوت گرفتی رو نشون می‌ده.\n"
            "📊 **وضعیت من** — همون صفحه‌ی وضعیت.\n"
            "🎽 **تجهیزات** — آیتم‌هایی که الان اکیپ کردی.\n"
            "🎴 **کارت من** — کارتِ نمایشیِ کاراکترت.\n"
            "📖 **کدکس** — اطلاعاتِ کلیِ بازی (کاراکترها و امثالِ اون).\n"
            "🏅 **دستاوردها** — تروفی‌های بازی؛ خودشون باف نمی‌دن، فقط برای نمایشن.\n"
            "🌟 **مهارت‌ها** — درختِ مهارتِ تو؛ با امتیازِ مهارتی که از لول‌آپ می‌گیری، باف‌های دائمی باز می‌کنی.\n"
            "🌍 **تیر جهان** — سطح/رده‌ی جهانیِ کاراکترت.\n"
            "🔗 **اتصال حساب** — وصل‌کردنِ اکانتت به یه شماره/حسابِ دیگه.\n\n"
            "💡 بیمارستان الان زیرِ دسته‌ی «✨ درمانگر»ه، نه اینجا."
        ),
    },
    "war": {
        "title": "نبرد",
        "text": (
            "⚔️ **منوی «نبرد»** — بخشِ اصلیِ لول‌آپ و درآمد\n\n"
            "🗺 **لوت** — هر ۱۰ دقیقه ۵ بار می‌تونی لوت کنی (سقفِ روزانه ۵۰ بار). یه شهر از لیست انتخاب می‌کنی،"
            " می‌ری اونجا و از بینِ ۵ مکانِ اون شهر یکی رو انتخاب می‌کنی. ممکنه سرِ راهت انمی سبز بشه"
            " (اگه لولت مناسبِ اون شهر نباشه ممکنه بکشتت)، و گاهی هم با باسِ همون منطقه رو‌به‌رو می‌شی.\n"
            "⚔️ **حمله** — همون دکمه‌ی حمله (بالاتر توضیح داده شد).\n"
            "👹 **باس جهانی** — باس‌هایی که ادمین‌ها اسپان می‌کنن و همه می‌تونن باهاشون بجنگن.\n"
            "🎯 **شکار جایزه** — روی سرِ بعضی از بازیکن‌ها/انمی‌ها جایزه گذاشته می‌شه؛ اینجا دنبالشون می‌گردی.\n"
            "🗡️ **نمسیس من** — انمی‌هایی که فرار کردن و نکشتیشون؛ حالا برگشتن برای انتقام.\n\n"
            "🩸 **حلقه‌ی سایه** — یه PvP غیررسمی و پرریسک، جدا از رنکینگِ رسمی:\n"
            "  • با `/underground @یوزرنیم مبلغ` چالش می‌دی (حداقلِ شرط ۵۰۰ Zen).\n"
            "  • نتیجه با مقایسه‌ی «قدرتِ نبرد»ِ دو طرف تعیین می‌شه (شانسِ برد متناسب با قدرت، ولی همیشه یه‌کم شانس برای ضعیف‌تر هم هست).\n"
            "  • بازنده Zenِ شرط رو می‌ده و ۵۰٪ احتمال داره یه آیتمِ رندوم از کوله‌پشتیش رو هم از دست بده.\n"
            "  • بعد از هر چالش باید ۳ دقیقه صبر کنی.\n\n"
            "💡 بقیه‌ی این دسته: 👻 استند من، 🗡 کاتانا، 📜 کوئست‌های جانبی، 🏹 کوئست‌لاینِ شکار، "
            "⚜️ قدرت‌های کلاس، 🆚 PvP، 🏆 رده‌بندی و 📅 ایونت — از پایینِ صفحه در دسترسن."
        ),
    },
    "auction": {
        "title": "حراجی",
        "text": (
            "🏛️ **حراجی** — مزایده‌ی زنده بینِ بازیکن‌ها (نه فروشِ آنیِ ثابت)\n\n"
            "چهار بخش داره:\n"
            "🛒 **مرور آگهی‌ها** — آگهی‌های فعالِ بقیه رو می‌بینی و پیشنهاد می‌دی.\n"
            "📦 **آگهی‌های من** — آگهی‌هایی که خودت گذاشتی.\n"
            "💰 **پیشنهادهای من** — مزایده‌هایی که روشون پیشنهاد دادی.\n"
            "➕ **فروش آیتم جدید** — یه آیتم از کوله‌پشتیت رو با قیمتِ شروع می‌ذاری حراج.\n\n"
            "نکاتِ مهم:\n"
            "• حداقلِ قیمتِ شروع ۱۰۰ Zen و حداکثر ۵ آگهیِ هم‌زمان.\n"
            "• واریزِ آگهی ۳٪ از قیمتِ شروع (غیرقابلِ‌استرداد) + مالیاتِ فروشِ موفق ۱۰٪ از سهمِ فروشنده.\n"
            "• هر آگهی ۲۴ ساعت بازه؛ اگه تو ۳۰ ثانیه‌ی آخر پیشنهادِ جدید بیاد، زمان ۳۰ ثانیه تمدید می‌شه (ضدِ اسنایپ).\n"
            "• Zenِ هر پیشنهاد بلافاصله بلوکه می‌شه و اگه یکی جلوتون بزنه، فوراً برمی‌گرده."
        ),
    },
    "casino": {
        "title": "کازینو",
        "text": (
            "🎰 **کازینو** — چهار بازیِ شانسی + لیدربوردِ هفتگی\n\n"
            "🪙 **شیر یا خط** — روی شیر یا خط شرط می‌بندی، بردِ ۱.۹ برابر.\n"
            "🎲 **تاسِ شانس** — بردِ ۵ برابر.\n"
            "🎰 **اسلات + جکپات** — دستگاهِ اسلات با شانسِ جکپات.\n"
            "🃏 **بلک‌جک** — بازیِ کارتیِ کلاسیک (Hit / Stand در برابرِ دیلر).\n"
            "🏆 **لیدربوردِ هفتگی** — رتبه‌بندیِ بردهای هفته.\n\n"
            "همه‌ی بازی‌ها شرط‌بندیِ Zenِ خودتونه — ممکنه ببازی، پس فقط با پولی که براش نگرانی نداری بازی کن."
        ),
    },
    "myshop": {
        "title": "مغازه‌ی من",
        "text": (
            "🏪 **مغازه‌ی من** — یه مغازه‌ی دائمی زیرِ پروفایلت (برخلافِ حراجی که موقتیه)\n\n"
            "بقیه با `/visit @یوزرنیم` می‌تونن سر بزنن و از مغازه‌ت بخرن؛ حتی وقتی آفلاینی هم"
            " ممکنه NPCهای «پناهنده» سر بزنن و ازت خرید کنن.\n\n"
            "امکاناتِ منو:\n"
            "➕ **افزودنِ کالا** / ➖ **برداشتنِ کالا**\n"
            "✏️ **تغییرِ اسمِ مغازه**\n"
            "⬆️ **ارتقایِ مغازه** — ۴ سطح داره؛ هرچی بالاتر بری، جایگاهِ بیشتر و کارمزدِ کمتر می‌گیری"
            " (از کارمزدِ ۸٪ تو سطحِ اول تا ۲٪ تو بالاترین سطح).\n\n"
            "یه سیستمِ **اعتبار/ریپوتیشن** هم داره که با فروشِ بیشتر بالا می‌ره و لقب می‌گیری."
        ),
    },
    "contracts": {
        "title": "📜 تابلوی کارگزار",
        "text": (
            "📜 **تابلوی کارگزارِ کیارَش** — یه کارگزارِ مرموز که دنبالِ سرنخ‌هایی از کیارَشه\n\n"
            "هر ساعت ۳ قراردادِ کوتاه‌مدتِ جدید رو تابلو می‌ذاره. رقابتیه: فقط ۳ نفرِ اول که تحویل بدن"
            " جایزه‌ی کامل می‌گیرن، بقیه یه جایزه‌ی تسلی‌بخشِ کوچیک‌تر (٪۳۵ جایزه).\n"
            "می‌تونی حداکثر ۲ قرارداد رو هم‌زمان قبول کنی.\n\n"
            "نوعِ قراردادها:\n"
            "🗡 **کشتار** — تعدادِ مشخصی دشمن بکش.\n"
            "💰 **تقدیمِ Zen** — مقدارِ مشخصی Zen بده.\n"
            "📦 **تحویلِ آیتم** — یه آیتمِ نادر (rare) یا حماسی (epic) به‌بالا تحویل بده.\n\n"
            "پاداش‌ها ترکیبی از Zen و XP هستن."
        ),
    },
    "riftdive": {
        "title": "🌀 شکاف Abyss",
        "text": (
            "🌀 **شکافِ Abyss (Rift Dive)** — یه غارِ روگ‌لایکِ بی‌پایان (حداقل سطح ۱۵)\n\n"
            "وارد یه شکاف می‌شی و اتاق‌به‌اتاق پیش می‌ری: نبرد، گنج، معبدِ انتخاب، استراحت.\n"
            "یه نوارِ HPِ مخصوصِ همین ران داری — هیچ ربطی به HPِ واقعیِ کاراکترت نداره.\n\n"
            "⚠️ **نکته‌ی مهم:** پاداشی که تو یه اتاق می‌گیری اول «در انتظار»ه، نه مالِ تو.\n"
            "هر ۳ اتاق یه **دروازه‌ی خروج** باز می‌شه: یا پاداش رو بانک کن (مطمئن) یا\n"
            "ریسک کن و عمیق‌تر برو (پاداشِ بزرگ‌تر). اگه بینِ دو دروازه بمیری، فقط چیزی\n"
            "که آخرین بار بانک کردی می‌مونه — بقیه از دست می‌ره.\n\n"
            "🔹 **Echo Shard** ارزِ مخصوصِ این حالته — بعداً برای چیزهای ویژه (مثلِ مونت) قابلِ خرجه."
        ),
    },
    "mounts": {
        "title": "🐎 مونت‌ها",
        "text": (
            "🐎 **مونت‌ها** — یه سواریِ نبردی که مستقیم رو Combat Power ات اثر می‌ذاره\n\n"
            "فقط یه مونت هم‌زمان می‌تونی سوار باشی. مونت‌ها رو با **🔹Echo Shard**\n"
            "(از 🌀 شکافِ Abyss به دست میاد) از فروشگاه می‌خری. هرچی نایاب‌تر، قدرتِ\n"
            "بیشتری به CP ات اضافه می‌کنه."
        ),
    },
    "arena": {
        "title": "🏟 آرنا",
        "text": (
            "🏟 **آرنا** — هابِ زنده‌ی فصلِ PvP\n\n"
            "امتیازِ فصلی (از بردنِ دوئل‌ها) تو رو تو یه لیگ (Bronze تا Eternal) قرار\n"
            "می‌ده. هر هفته فصل تموم می‌شه: بر اساسِ لیگِ نهایی‌ت Zen می‌گیری، و ۳ نفرِ\n"
            "برترِ سرور یه بونوسِ اضافه هم می‌گیرن. از اینجا رتبه‌ی زنده و پیشرفتت تا\n"
            "لیگِ بعدی رو می‌بینی."
        ),
    },
    "convergence": {
        "title": "🌌 هم‌گرایی",
        "text": (
            "🌌 **رخدادِ هم‌گرایی** — یه شکافِ سراسری که کلِ سرور باید با هم ببندتش\n\n"
            "وقتی فعاله، هرکسی می‌تونه Zen یا 🔹Echo Shard تقدیم کنه تا نوارِ سراسری\n"
            "پر بشه. تو ۲۵٪/۵۰٪/۷۵٪ اعلانِ سراسری میاد؛ وقتی به ۱۰۰٪ برسه، پاداشِ Zen\n"
            "به‌نسبتِ سهمِ مشارکتِ هرکس تقسیم می‌شه و ۱۰ نفرِ برترِ مشارکت‌کننده یه\n"
            "تجهیزاتِ افسانه‌ای/اسطوره‌ای هم می‌گیرن."
        ),
    },
    "goddess": {
        "title": "🕊 الهه",
        "text": (
            "🕊 **الهه‌ی آغازها** — همون کسی که تو رو به Abyss فرستاد\n\n"
            "هر ۶ ساعت یه‌بار می‌تونی **دعا کنی** و یه هدیه‌ی رندومِ کوچیک (Zen/XP/\n"
            "Echo Shard) بگیری. هرچی بیشتر باهاش تعامل کنی، «لطف»ش بیشتر می‌شه و\n"
            "دیالوگ‌های جدید باز می‌شن.\n\n"
            "⚡ فقط **یه‌بار تو کل حساب** می‌تونی یه **چیت‌اسکیل** ازش بخوای — یه\n"
            "بونوسِ دائمیِ Combat Power که با لولِ خودت رشد می‌کنه. با دقت انتخاب کن،\n"
            "قابلِ تغییر نیست!"
        ),
    },
    "bank": {
        "title": "بانک",
        "text": (
            "🏦 **بانک** — سه بخشِ جدا داره\n\n"
            "💳 **کارت و انتقال** — یه شماره‌کارتِ ۱۶ رقمیِ یکتا داری؛ با شماره‌کارت (نه فقط یوزرنیم)"
            " برای بقیه پول می‌فرستی. کارمزدِ انتقال ۲٪، حداقلِ انتقال ۵۰ Zen، سقفِ روزانه ۲۵٬۰۰۰ Zen،"
            " و می‌تونی روی حسابت PIN هم بذاری.\n\n"
            "🏦 **حسابِ سپرده** — Zen رو می‌ذاری تو سپرده و سودِ سادهٔ روزانه ۱.۵٪ می‌گیری"
            " (حداقلِ واریز ۱۰۰ Zen، برداشت هر وقت بخوای آزاده).\n\n"
            "💸 **وام** — سقفِ وام بر اساسِ سطح و اعتبارِ توئه؛ کلِ دوره ۱۵٪ سود داره و ۴۸ ساعت مهلت داری."
            " اگه دیر بازپرداخت کنی، ۲۵٪ جریمه رو اصلِ باقی‌مونده می‌خوره و اعتبارت افت می‌کنه."
            " فقط یه وامِ فعال در هر لحظه مجازه."
        ),
    },
    "blackmarket": {
        "title": "بازار سیاه",
        "text": (
            "🖤 **بازار سیاه** — جزئیاتِ کامل\n\n"
            "🏪 **فروشگاه** — خریدِ وسایلِ عمومی.\n"
            "🕵️ **تجهیزات جاسوسی** — وسایلی با ابیلیتیِ خاص.\n"
            "🗡️ **آپگرید کاتانا** — با پول، کاتاناتُ قوی‌تر می‌کنی.\n"
            "🛡️ **دفاعِ پایگاه** — وسایلِ مربوط به دفاع از پایگاه/ملکِ شخصیِ خودت.\n"
            "🕯️ **حراجیِ سایه** — آیتم‌های خاص و کمیاب.\n"
            "🔑 **صندوق‌ها و کلیدها** — تویِ لوت‌کردن ممکنه صندوق پیدا کنی؛ کلیدش رو اینجا می‌خری و صندوق رو با لوتِ داخلش باز می‌کنی.\n"
            "🎽 **مجموعه‌های ست** — تو بعضی شهرها ست‌های خاصی هست که با کامل‌کردنشون باف می‌گیری.\n"
            "💱 **فروشِ آیتم** — آیتم‌های اضافه‌ت رو نقد می‌کنی.\n"
            "📈 **وضعیتِ بازار** — نشون می‌ده چی الان گرون شده و چی ارزون."
        ),
    },
    "social": {
        "title": "اجتماعی",
        "text": (
            "🏛 **منوی «اجتماعی»**\n\n"
            "👥 **تیم** — با یه نفرِ دیگه یار می‌شی و از کارِ گروهی باف می‌گیرید.\n"
            "🤝 **معامله** — رد و بدل کردنِ پول/آیتم مستقیم با بازیکنِ دیگه.\n"
            "🔍 **ردیابی** — با یوزرنیمِ یه بازیکن، اطلاعاتش رو پیدا می‌کنی.\n\n"
            "💡 گیلدها یه دسته‌ی جداست («🏰 گیلد») و PvP/رده‌بندی/ایونت الان "
            "زیرِ دسته‌ی «🗺️ ماجراجو»ن."
        ),
    },
    "life": {
        "title": "زندگی",
        "text": (
            "🏠 **منوی «زندگی در Abyss»**\n\n"
            "🎓 **استادی** — از سطح ۱۵ به بعد، می‌تونی استادِ یه نفرِ کم‌سطح‌تر بشی یا شاگردِ یه نفرِ بالاسطح.\n"
            "🏠 **ملکِ شخصی** — خونه‌ی خودت؛ قابلِ ارتقا و دفاع (بخشِ «دفاعِ پایگاه» تو بازار سیاه بهش مربوطه)."
        ),
    },
    "info": {
        "title": "اطلاعات",
        "text": (
            "📖 **منوی «اطلاعات»**\n\n"
            "📖 **کدکس** — اطلاعاتِ کلیِ بازی (کاراکترها و امثالِ اون).\n"
            "🎫 **پس نبرد (Battle Pass)** — مسیرِ جایزه‌ی فصلی.\n\n"
            "💡 رده‌بندی و ایونت الان زیرِ دسته‌ی «🗺️ ماجراجو»ن، نه اینجا."
        ),
    },
}

# نکته: TUTORIAL_SECTIONS بالاتر (خودِ محتوا) حذف نشده — چون توسطِ
# «آموزشِ خودکارِ پنل» پایین‌تر (تیک‌آفِ اولین‌بار) خونده می‌شه.
# فقط خودِ دکمه‌ی «آموزش» و منوی دستی‌اش حذف شدن.

# ─── آموزشِ خودکارِ پنل — برای همه‌ی بازیکن‌ها (قدیمی/جدید) تا لولِ ۵ ─────
# قبلاً بازیکنِ تازه‌کار باید خودش می‌رفت رو دکمه‌ی «آموزش» می‌زد تا
# توضیحِ یه پنل رو ببینه — خیلی‌ها اصلاً نمی‌دونستن اون دکمه هست. حالا
# هر پنلی (چه دسته‌ی اصلی مثلِ «نبرد»، چه یه دکمه‌ی خاص مثلِ «بازار
# سیاه») که یه بازیکنِ سطح ≤ ۵ برای اولین‌بار باز می‌کنه، قبل از
# نمایشِ خودِ پنل، همون توضیحِ آماده‌ی TUTORIAL_SECTIONS براش فرستاده
# می‌شه. هر بخش فقط یه‌بار برای هر بازیکن نشون داده می‌شه (تویِ
# player["seen_panel_tutorials"] ذخیره می‌شه) تا اسپم نشه.
PANEL_TUTORIAL_LEVEL_CAP = 5

PANEL_TUTORIAL_MAP: dict[str, str] = {
    "ماجراجو": "war", "من": "me", "اجتماعی": "social", "اطلاعات": "info", "زندگی": "life",
    "حمله": "attack", "وضعیت": "status",
    "بازار سیاه": "blackmarket", "حراجی": "auction", "کازینو": "casino",
    "مغازه‌ی من": "myshop", "📜 تابلوی کارگزار": "contracts", "بانک": "bank",
    "🌀 شکاف Abyss": "riftdive",
    "🐎 مونت‌ها": "mounts", "🏟 آرنا": "arena", "🌌 هم‌گرایی": "convergence",
    "🕊 الهه": "goddess",
}


@dp.message.middleware()
async def panel_tutorial_middleware(handler, event: Message, data: dict):
    try:
        text = (event.text or "").strip()
        uid = event.from_user.id if event.from_user else None

        # چک سبکِ عنوان‌های ایسکای — هر پیام (فقط دیکشنری‌گردی، سنگین نیست)
        if uid:
            player_for_persona = get_player(uid)
            if player_for_persona:
                from isekai_personas import check_and_grant_personas
                newly = check_and_grant_personas(player_for_persona)
                if newly:
                    save_player(uid, player_for_persona)
                    try:
                        await event.reply("🏅 عنوانِ جدید باز شد: " + " | ".join(newly))
                    except Exception:
                        pass

        key = PANEL_TUTORIAL_MAP.get(text)
        if key:
            player = get_player(uid) if uid else None
            if player and player.get("level", 1) <= PANEL_TUTORIAL_LEVEL_CAP:
                seen = player.setdefault("seen_panel_tutorials", [])
                if key not in seen:
                    section = TUTORIAL_SECTIONS.get(key)
                    if section:
                        await event.reply(
                            f"📖 **قبل از ورودت به «{section['title']}»، این رو بخون:**\n\n{section['text']}"
                        )
                    seen.append(key)
                    save_player(uid, player)
    except Exception:
        pass
    return await handler(event, data)

# ─── Helpers ─────────────────────────────────────────────────
def hp_bar(current: int, maximum: int, length: int = 10) -> str:
    filled = int((current / maximum) * length) if maximum else 0
    return "🟥" * filled + "⬛" * (length - filled)

def char_card(char_name: str, player: dict | None = None) -> str:
    c = ALL_CHARACTERS.get(char_name, {})
    rarity = RARITY_COLOR.get(c.get("rarity", "common"), "⚔️")
    emoji  = RARITY_EMOJI.get(c.get("rarity", "common"), "⚔️")
    powers = "\n".join(f"  • {p}" for p in c.get("powers", []))
    locked = "\n".join(f"  🔒 ???" for _ in range(5)) if c.get("rarity") in ["special","legendary"] else ""
    locked_txt = f"\n🔒 **ابیلیتی‌های قفل شده:**\n{locked}" if locked else ""
    lore_txt = ""
    if player is not None:
        try:
            from character_lore import get_character_lore_text
            lore_txt = f"\n\n{get_character_lore_text(char_name, c, player)}"
        except ImportError:
            lore_txt = ""
    return (
        f"{emoji} **{char_name}**\n"
        f"🏷 ندرت: {rarity}\n"
        f"🌀 عنصر: {c.get('element','—')}\n"
        f"🗡 کاتانا: *{c.get('katana','—')}*\n"
        f"⚡ قدرت پایه: {c.get('base_dmg',0)}\n"
        f"✨ ابیلیتی‌ها:\n{powers}"
        f"{locked_txt}"
        f"{lore_txt}"
    )

def level_up_check(player: dict) -> tuple[dict, bool]:
    from skill_tree import grant_levelup_points
    from game_data import is_level_wall
    leveled = False
    old_level = player["level"]
    while player["xp"] >= xp_for_level(player["level"]) and player["level"] < effective_max_level(player):
        # حالت سخت: دیوار سختی — همون قانونِ combat_handlers.py، اینجا هم رعایت می‌شه
        if is_level_wall(player["level"]) and player["level"] not in player.get("walls_cleared", []):
            break
        player["level"]  += 1
        player["max_hp"] += 5   # حالت سخت: یکسان با combat_handlers.py (قبلاً اینجا +۱۰ بود — باگ)
        from skill_tree import effective_max_hp
        player["hp"]      = effective_max_hp(player)  # باگ‌فیکس: باف max_hp_pct هم لحاظ بشه
        leveled = True
    if leveled:
        pts = grant_levelup_points(player, old_level, player["level"])
        log_sync(
            f"⭐ **LEVEL UP**\n"
            f"👤 {player.get('name','—')} (`{player.get('id','—')}`)\n"
            f"🎴 {player.get('character','—')}\n"
            f"📊 سطح: {old_level} → {player['level']}\n"
            f"🌟 امتیاز مهارت: +{pts}",
            "LEVELUP"
        )
    return player, leveled

# ─── /start ──────────────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    uid   = msg.from_user.id
    uname = msg.from_user.username or ""
    update_last_seen(uid)
    player = get_player(uid)

    is_group = msg.chat.type != "private"
    BOT_LINK = "https://t.me/AbyssAstralbot"

    # ─── payload بعدِ /start (دیپ‌لینک از گروه یا اینلاین) ─────────
    _parts = (msg.text or "").split(maxsplit=1)
    start_payload = _parts[1].strip() if len(_parts) > 1 else None

    if not player:
        if is_group:
            await msg.answer(
                f"❗️ اول باید تو خودِ ربات شروع کنی!\n\n"
                f"برو به [@AbyssAstralbot]({BOT_LINK}) پیام بده، اونجا /start رو بزن و "
                f"کاراکترت رو بگیر — بعدش برگرد همینجا تا با بقیه بازی کنی. ⚔️"
            )
            return

        player = create_player(uid, uname, None)

        log_sync(
            f"👤 **NEW PLAYER (پیش‌ثبت‌نام)**\n"
            f"🆔 `{uid}` | {msg.from_user.first_name}",
            "PLAYER"
        )

        # ─── ردیابیِ رفرال — از کجا اومد؟ (گروه/کارتِ اینلاین/دوئل) ──
        try:
            from referral_system import track_referral
            ref = track_referral(start_payload, uid)
            if ref and ref["kind"] == "group":
                log_sync(
                    f"🔗 **REFERRAL** (گروه)\n📍 چت: `{ref['source']}`\n🆕 کاربرِ جدید: `{uid}`",
                    "GROUP",
                )
                try:
                    await bot.send_message(
                        ref["source"],
                        f"🎉 یه بازیکنِ جدید از همین گروه به Astral Abyss ملحق شد!",
                    )
                except Exception:
                    pass  # ربات ممکنه دیگه تو اون گروه نباشه یا سکوت‌شده باشه
            elif ref:
                log_sync(
                    f"🔗 **REFERRAL** ({ref['kind']})\n👤 دعوت‌کننده: `{ref['source']}`\n🆕 کاربرِ جدید: `{uid}`",
                    "GROUP",
                )
        except Exception as e:
            log_sync(f"🔴 referral tracking error: {e}", "ERROR")

        await msg.answer(
            "🌑 *به Astral Abyss خوش اومدی...*\n\n"
            "آخرین چیزی که یادته، یه لحظه‌ی تاریکی بود — بعدش چشم باز کردی و دیگه "
            "همون جهانِ قبلی نبود. تو و دوقلوت، **کیارَش**، داشتید سفر می‌کردید که "
            "**Abyss** ظهور کرد، واقعیت رو پاره کرد و شما رو — مثلِ همه‌ی کسایی که "
            "لحظه‌ی شکافتن اونجا بودن — به این دنیای شکسته «احضار» کرد؛ واقعیتی که "
            "به ۱۴ قلمروی جدا از هم تکه‌تکه شده. تو از کیارَش جدا افتادی، و از همون "
            "لحظه، این جهانِ ایزکایی‌گونه خونه‌ی جدیدته.\n\n"
            "🏯 هرکسی که تازه به این دنیا می‌رسه، اول سر از **میکیو (迷宮の街)** درمیاره — "
            "شهری که مستقیم دورِ دهانه‌ی یه دخمه‌ی بی‌انتها ساخته شده و مقرِ **گیلدِ "
            "ماجراجوییه**. اونجا با رتبه‌ی **F** ثبت‌نام می‌شی و قدم‌به‌قدم — با هر لِوِل، "
            "هر شکار، هر پیروزی — بالاتر می‌ری، تا یه‌روز به رتبه‌ی افسانه‌ای **S** برسی.\n\n"
            "👹 پشتِ همه‌ی این هرج‌ومرج یه **مائو (魔王 / لردِ شیطانی)** هست که هرچی قوی‌تر "
            "بشه، فسادِ این دنیا (ضربانِ آبیس) بیشتر می‌شه. هر قلمرو یه خدای منطقه‌ای خودش "
            "رو داره، هر مبارزه یه قدم به جلو. لِوِل بگیر، تجهیزات و ست‌آیتم‌های نادر جمع "
            "کن، وارد گیلد شو، بازار سیاه رو بگرد، و قدم‌به‌قدم رازِ **آرکان نال** و "
            "سرنوشتِ کیارَش رو کشف کن. یه داستانِ ۲۰ فصلی در انتظارته — و رسیدن به ته‌ش "
            "هم پایان نیست.\n\n"
            "حالا، بیا شروع کنیم — **اسمِ کاراکترت** رو بفرست (حداکثر ۲۰ حرف):",
        )
        await state.set_state(CharCreation.waiting_name)
        return

    if not player.get("class"):
        if is_group:
            await msg.answer(
                f"❗️ هنوز کاراکترت رو نساختی!\n\n"
                f"برو به [@AbyssAstralbot]({BOT_LINK}) پیام بده و کاراکترت رو بساز — "
                f"بعدش برگرد همینجا تا با بقیه بازی کنی. ⚔️"
            )
            return
        if not player.get("name"):
            await msg.answer("📝 اول اسمِ کاراکترت رو بفرست (حداکثر ۲۰ حرف):")
            await state.set_state(CharCreation.waiting_name)
        else:
            await msg.answer(class_selection_text(), reply_markup=class_selection_kb())
        return

    update_last_seen(uid)
    from achievements import check_achievements
    new_titles = check_achievements(player)
    login_msg = grant_daily_login(player)
    save_player(uid, player)
    extra = (f"\n\n{login_msg}" if login_msg else "")
    for t in new_titles:
        extra += f"\n\n🏅 **عنوان جدید باز شد: {t}**"

    import onboarding
    if onboarding.is_in_tutorial(player):
        await msg.reply(
            f"🌑 *بازگشتی، {player['name']}...*\nآبیس منتظرت بود.{extra}\n\n{onboarding.resume_text(player)}",
            reply_markup=onboarding.resume_kb(player)
        )
    else:
        await msg.reply(
            f"🌑 *بازگشتی، {player['name']}...*\nآبیس منتظرت بود.{extra}{_story_panel_reminder(player)}",
            reply_markup=main_kb(is_group=is_group, story_badge=_story_badge_for(player), player=player)
        )
    if login_msg:
        try:
            import tempfile, os
            from profile_card import generate_login_calendar
            out_path = os.path.join(tempfile.gettempdir(), f"calendar_{uid}.png")
            generate_login_calendar(player.get("login_streak", 1), out_path)
            await msg.answer_photo(FSInputFile(out_path))
        except Exception as e:
            log_sync(f"🔴 login calendar error: {e}", "ERROR")

# ─── دریافتِ اسمِ کاراکتر (قدمِ اولِ ساختِ کاراکتر) ──────────────
@dp.message(CharCreation.waiting_name, F.text)
async def on_character_name(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    name = (msg.text or "").strip()

    if not name or name.startswith("/"):
        await msg.answer("❌ یه اسمِ معتبر بفرست (نه یه دستور خالی).")
        return
    if len(name) > 20:
        await msg.answer("❌ اسم نباید بیشتر از ۲۰ حرف باشه. دوباره امتحان کن:")
        return

    player = get_player(uid)
    if not player:
        player = create_player(uid, msg.from_user.username or "", None)
    if player.get("class"):
        await msg.answer("✅ تو قبلاً کاراکترت رو ساختی!")
        await state.clear()
        return

    player["name"] = name
    save_player(uid, player)
    await state.clear()

    await msg.answer(
        f"✅ اسمت ثبت شد: **{name}**\n\n{class_selection_text()}",
        reply_markup=class_selection_kb(),
    )


# ─── انتخابِ کلاس (قدمِ دومِ ساختِ کاراکتر) ──────────────────────
@dp.callback_query(F.data.startswith("set_class:"))
async def cb_set_class(query: CallbackQuery):
    uid = query.from_user.id
    player = get_player(uid)

    if not player or not player.get("name"):
        await query.answer("❌ اول اسمِ کاراکترت رو بفرست! /start رو بزن.", show_alert=True)
        return
    if player.get("class"):
        await query.answer("✅ قبلاً کلاست رو انتخاب کردی!", show_alert=True)
        return

    class_id = query.data.split(":", 1)[1]
    if class_id not in CLASSES:
        await query.answer("❌ کلاسِ نامعتبر.", show_alert=True)
        return

    apply_class_to_player(player, class_id)

    spawn = random.choice(SPAWN_MAPS)
    player["map"] = spawn

    # 🆕 محدودیتِ «فقط ماجراجو کاتانا می‌گیره» برداشته شد — الان همه‌ی
    # کلاس‌ها grants_katana=True دارن، پس هر کلاسی موقعِ ساختِ کاراکتر یه
    # هویتِ کاتانای رندوم می‌گیره. این هویت هنوز به بازیکن به‌عنوانِ
    # «انتخابِ کرکتر» نشون داده نمی‌شه — صرفاً موتورِ داخلیِ کاتاناست.
    if CLASSES[class_id].get("grants_katana"):
        char = assign_random_char()
        player["character"] = char
        try:
            from character_lore import mark_character_seen
            mark_character_seen(player, char)
        except Exception:
            pass

    player["_awaiting_gender"] = True
    save_player(uid, player)

    log_sync(
        f"👤 **NEW PLAYER**\n"
        f"🆔 `{uid}` | {query.from_user.first_name}\n"
        f"📛 اسم: {player['name']}\n"
        f"⚜️ کلاس: {CLASSES[class_id]['name_fa']}\n"
        f"📍 مپ: {spawn}",
        "PLAYER"
    )

    await query.message.edit_text(
        f"⚜️ کلاست رو انتخاب کردی: **{CLASSES[class_id]['emoji']} {CLASSES[class_id]['name_fa']}**\n\n"
        f"یه قدم مونده — جنسیتِ کاراکترت رو انتخاب کن:",
        reply_markup=GENDER_KB
    )
    await query.answer()


# ─── انتخاب جنسیتِ کاراکتر (قدمِ آخرِ ساختِ کاراکتر) ────────────
GENDER_KB = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="🙋‍♂️ پسر", callback_data="set_gender:male", style=ButtonStyle.PRIMARY),
    InlineKeyboardButton(text="🙋‍♀️ دختر", callback_data="set_gender:female", style=ButtonStyle.PRIMARY),
]])


async def _finish_character_setup(chat_send, uid: int, player: dict):
    """بعدِ انتخابِ جنسیت صدا زده می‌شه: تیوتوریال رو شروع می‌کنه و پیامِ
    ورود به Abyss + کارتِ کلاس رو می‌فرسته. chat_send یه تابعِ async با
    امضای (text, reply_markup) هست (query.message.answer یا msg.answer)."""
    import onboarding
    onboarding.start_tutorial(player)  # فقط فیلدها رو done علامت می‌زنه، تیوتوریال غیرفعاله
    save_player(uid, player)

    spawn = player.get("map", random.choice(SPAWN_MAPS))
    spawn_msg = random.choice(SPAWN_MESSAGES).format(map=spawn)
    try:
        from character_lore import SIBLING_LORE
        sibling_teaser = f"\n\n💔 {SIBLING_LORE['intro_blurb']}\n\n📖 هروقت آماده بودی، `/story` رو بزن تا خطِ داستانی شروع بشه."
    except Exception:
        sibling_teaser = ""

    katana_line = ""
    if player.get("character"):
        katana_line = f"\n\n🗡 هویتِ کاتانا: {player['character']}"

    await chat_send(
        f"{spawn_msg}\n\n"
        f"کاراکتر تو:\n\n{class_card_text(player)}{katana_line}\n\n"
        f"💰 Zen: {player.get('zen', 1125)}"
        f"{sibling_teaser}",
        None,
    )
    await chat_send(
        f"🌑 حالا وارد Abyss شدی.\n\n"
        f"⚔️ برای شروع رو «حمله» بزن — بقیه‌ی پنلِ کلاست (و گیلد که مشترکه) "
        f"از همین الان از پایینِ صفحه در دسترسه.",
        main_kb(is_group=False, player=player),
    )


@dp.callback_query(F.data.startswith("set_gender:"))
async def cb_set_gender(query: CallbackQuery):
    uid = query.from_user.id
    player = get_player(uid)

    if not player or not player.get("class"):
        await query.answer("❌ اول کاراکترت رو بساز!", show_alert=True)
        return
    if player.get("_awaiting_gender") is not True:
        await query.answer("✅ قبلاً ثبت شده!", show_alert=True)
        return

    gender = query.data.split(":", 1)[1]
    player["gender"] = gender
    player["gender_chosen"] = True
    player.pop("_awaiting_gender", None)
    is_retro = player.pop("_gender_retro", False)

    await query.message.edit_reply_markup(reply_markup=None)

    if is_retro:
        # پلیرِ قدیمی که فقط داشت جنسیتش رو عقب‌گردی مشخص می‌کرد —
        # نباید تیوتوریال دوباره براش شروع بشه یا پنلش عوض بشه.
        save_player(uid, player)
        label = "🙋‍♀️ دختر" if gender == "female" else "🙋‍♂️ پسر"
        await query.message.answer(f"✅ ثبت شد! کاراکترت: {label}")
        await query.answer("✅ ثبت شد!")
        return

    async def _send(text, kb):
        await query.message.answer(text, reply_markup=kb)

    await _finish_character_setup(_send, uid, player)
    await query.answer("✅ ثبت شد!")


# ─── /create ─────────────────────────────────────────────────
# نکته: با موتورِ کلاسِ جدید، ساختِ کاراکتر همیشه از فلوی /start (اسم →
# کلاس → جنسیت) انجام می‌شه. /create برای بازیکن‌هایی که از قبل کلاس
# دارن فقط تغییرِ اسم می‌ده؛ برای بازیکنِ بدونِ کلاس، هدایتش می‌کنه به /start.
@dp.message(Command("create"))
async def cmd_create(msg: Message, state: FSMContext):
    uid  = msg.from_user.id
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        await msg.answer("📝 استفاده: `/create نام`")
        return
    name   = args[1].strip()[:20]
    player = get_player(uid)
    if player and player.get("class"):
        old_name = player.get("name", "—")
        player["name"] = name
        save_player(uid, player)
        await msg.answer(f"✅ نام تغییر کرد به: **{name}**")
        log_sync(f"👤 **NAME CHANGE** | {old_name} → {name} (`{uid}`)", "PLAYER")
    else:
        if not player:
            player = create_player(uid, msg.from_user.username or "", None)
        player["name"] = name
        save_player(uid, player)
        await state.clear()
        await msg.reply(
            f"✅ اسمت ثبت شد: **{name}**\n\n{class_selection_text()}",
            reply_markup=class_selection_kb(),
        )

# ─── Status ──────────────────────────────────────────────────
@dp.message(F.text == "وضعیت")
@dp.message(Command("status"))
async def cmd_status(msg: Message):
    uid = msg.from_user.id
    update_last_seen(uid)
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    if not player.get("class"):
        await msg.answer("❌ اول باید کاراکترت رو بسازی! /start رو بزن.")
        return

    from class_system import CLASSES as _CLASSES
    cls_info  = _CLASSES.get(player.get("class"), {})
    char_name = player.get("character", "—")
    c         = ALL_CHARACTERS.get(char_name, {})
    rarity    = RARITY_COLOR.get(c.get("rarity","common"), "⚔️")
    next_xp   = xp_for_level(player["level"])
    # 🐛 باگ‌فیکس: player["xp"] یه مقدارِ *تجمعی* (cumulative) از کلِ بازیه —
    # هیچ‌وقت بعدِ لول‌آپ صفر نمی‌شه. قبلاً نوارِ پیشرفت مستقیم xp/next_xp
    # حساب می‌شد که باعث می‌شد تو لول‌های بالا همیشه تقریباً پر نشون بده
    # (چون فاصله‌ی دو آستانه‌ی پیاپی نسبت به خودِ xp تجمعی خیلی کوچیکه).
    # حالا فقط پیشرفتِ *داخلِ همین لول* حساب می‌شه.
    at_cap    = player["level"] >= effective_max_level(player)
    prev_xp   = xp_for_level(player["level"] - 1) if player["level"] > 1 else 0
    xp_span   = next_xp - prev_xp
    xp_into   = max(0, player["xp"] - prev_xp)
    xp_pct    = 8 if at_cap or not xp_span else int((xp_into / xp_span) * 8)
    xp_bar    = "🟦" * xp_pct + "⬛" * (8 - xp_pct)
    katana_lv = player.get("katana_level", 1)
    online    = "🟢" if is_online(uid) else "🔴"
    from skill_tree import effective_max_hp
    disp_max_hp = effective_max_hp(player)

    from achievements import check_achievements
    new_titles = check_achievements(player)
    login_msg = grant_daily_login(player)
    if new_titles or login_msg:
        save_player(uid, player)
    extra_txt = (f"\n\n{login_msg}" if login_msg else "")
    for t in new_titles:
        extra_txt += f"\n\n🏅 **عنوان جدید باز شد: {t}**"

    # خطِ کاتانا فقط برای ماجراجو نشون داده می‌شه؛ بقیه‌ی کلاس‌ها به‌جاش
    # منبعِ اختصاصیِ خودشون رو می‌بینن.
    if player.get("character"):
        katana_line = f"🗡 کاتانا: *{c.get('katana','—')}* Lv.{katana_lv}\n"
    else:
        csd = player.get("class_system_data", {})
        res = csd.get(cls_info.get("resource_key"), "—")
        katana_line = f"🔹 {cls_info.get('resource_label_fa','منبع')}: {res}\n"

    await msg.answer(
        f"📊 ステータス (Status Window)\n"
        f"👤 **{player['name']}** {online}\n{'─'*22}\n"
        f"{cls_info.get('emoji','⚜️')} **{cls_info.get('name_fa','—')}**\n"
        f"{katana_line}"
        f"{'─'*22}\n"
        f"⭐ سطح: **{player['level']}** / {effective_max_level(player)}"
        + (f" 🌀 (Rebirth #{player['rebirth_count']})" if player.get('rebirth_count', 0) > 0 else "") + "\n"
        f"✨ XP: {'MAX' if at_cap else f'{xp_into:,}/{xp_span:,}'}\n{xp_bar}\n"
        f"❤️ HP: {player['hp']}/{disp_max_hp}\n"
        f"{hp_bar(player['hp'], disp_max_hp)}\n"
        f"💰 Zen: **{player['zen']:,}**\n"
        f"{'─'*22}\n"
        f"📍 مپ: **{player.get('map','—')}** ({map_label(player.get('map',''))})\n"
        f"{rank_line(player)}\n"
        f"⚡ Combo: **{player.get('combo',0)}x**\n"
        f"💀 کشته: {player.get('kills',0)} | 🆚 PvP: {player.get('pvp_wins',0)}\n"
        f"🌟 امتیاز مهارت آزاد: **{player.get('skill_points',0)}**" +
        (" (با /skills خرجش کن!)" if player.get('skill_points',0) > 0 else "")
        + f"\n\n{cls_info.get('emoji','⚜️')} قدرت‌های فعالِ کلاست رو با /class ببین."
        + extra_txt
    )
    if login_msg:
        try:
            import tempfile, os
            from profile_card import generate_login_calendar
            out_path = os.path.join(tempfile.gettempdir(), f"calendar_{uid}.png")
            generate_login_calendar(player.get("login_streak", 1), out_path)
            await msg.answer_photo(FSInputFile(out_path))
        except Exception as e:
            log_sync(f"🔴 login calendar error: {e}", "ERROR")

# ─── کارتِ کاراکتر (متنی) ──────────────────────────────────────
@dp.message(F.text == "🎴 کارت")
@dp.message(Command("charcard"))
async def cmd_card(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player or not player.get("class"):
        await msg.answer("❌ اول یه کاراکتر بساز (/start)!")
        return

    if player.get("character"):
        # ماجراجو — کارتِ متنیِ قدیمی که به هویتِ کاتانا وابسته‌ست
        char_data = ALL_CHARACTERS.get(player["character"], {})
        from text_card import generate_character_card_text
        card_text = generate_character_card_text(player, char_data)
        await msg.answer(f"<pre>{card_text}</pre>")
    else:
        # سه کلاسِ دیگه — کارتِ کلاسِ جدید (تا وقتی text_card برای کلاس‌های
        # جدید هم آپدیت بشه، مرحله‌ی بعدی)
        await msg.answer(class_card_text(player))

# ─── Inventory ───────────────────────────────────────────────
@dp.message(F.text == "کوله‌پشتی")
@dp.message(Command("inventory"))
async def cmd_inventory(msg: Message):
    uid    = msg.from_user.id
    update_last_seen(uid)
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    inv = player.get("inventory", [])
    if not inv:
        await msg.answer("🎒 کوله‌پشتیت خالیه!\nبرو لوت کن یا از بازار سیاه بخر.")
        return
    await show_inventory_page(msg, uid, inv, page=0, edit=False)

async def show_inventory_page(msg, uid: int, inv: list, page: int = 0, edit: bool = True):
    from economy import bz_to_display
    from item_system import EQUIP_SLOTS, group_inventory

    groups = group_inventory(inv)
    PAGE_SIZE   = 8
    total_pages = max(1, (len(groups) - 1) // PAGE_SIZE + 1)
    start = page * PAGE_SIZE
    end   = start + PAGE_SIZE
    page_groups = groups[start:end]
    total_val   = sum(g["total_sell"] for g in groups if not g["item"].get("locked"))

    r_map = {"common":"⚪","uncommon":"🟢","rare":"🔵","epic":"🟣","mythic":"🟠","legendary":"🟡"}
    lines = [f"🎒 **کوله‌پشتی** ({len(inv)} آیتم | {len(groups)} ردیف | صفحه {page+1}/{total_pages})\n\n"]
    buttons = []

    for gi, g in enumerate(page_groups):
        item = g["item"]
        qty  = g["qty"]
        locked = bool(item.get("locked"))
        r = r_map.get(item.get("rarity","common"),"⚪")
        tag = f" ×{qty}" if qty > 1 else ""
        lock_tag = " 🔒" if locked else ""
        lines.append(f"{item.get('emoji','📦')} **{item['name']}**{tag}{lock_tag} {r} — {bz_to_display(g['total_sell'])}\n")
        if item.get("desc"):
            lines.append(f"   _{item['desc']}_\n")
        row = []
        slot = item.get("slot")
        real_idx = g["indices"][0]
        if slot in EQUIP_SLOTS and qty == 1:
            row.append(InlineKeyboardButton(
                text="🎽 اکیپ",
                callback_data=f"eq_pick:{slot}:{real_idx}:{uid}"
            , style=ButtonStyle.SUCCESS))
        if item.get("usable"):
            row.append(InlineKeyboardButton(
                text="✨ مصرف" + (" (۱تا)" if qty > 1 else ""),
                callback_data=f"inv_use:{page}:{gi}:{uid}"
            , style=ButtonStyle.SUCCESS))
        if not item.get("shop_exclusive"):
            if locked:
                row.append(InlineKeyboardButton(
                    text="🔒 قفله (فروش بسته)",
                    callback_data=f"inv_lock:{page}:{gi}:{uid}"
                , style=ButtonStyle.PRIMARY))
            else:
                row.append(InlineKeyboardButton(
                    text=f"💰 فروش همه ({bz_to_display(g['total_sell'])})" if qty > 1 else f"💰 فروش ({bz_to_display(g['total_sell'])})",
                    callback_data=f"inv_sell:{page}:{gi}:{uid}"
                , style=ButtonStyle.DANGER))
                row.append(InlineKeyboardButton(
                    text="🔓 قفل کن",
                    callback_data=f"inv_lock:{page}:{gi}:{uid}"
                , style=ButtonStyle.PRIMARY))
        buttons.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"inv_page:{page-1}:{uid}", style=ButtonStyle.PRIMARY))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"inv_page:{page+1}:{uid}", style=ButtonStyle.PRIMARY))
    if nav:
        buttons.append(nav)
    # 🐛 باگ‌فیکس: قبلاً همینجا یه دکمه‌ی «فروش همه» بود که بدونِ هیچ تاییدی
    # کلِ کوله‌پشتی رو (به‌جز shop_exclusive) می‌فروخت — خیلی راحت می‌شد
    # اشتباهی روش زد (مثلاً وقتی کاربر می‌خواست فقط لوتِ یه ماموریت رو بفروشه)
    # و کلِ اینونتوری خالی می‌شد. الان این دکمه فقط می‌بره به یه صفحه‌ی
    # تاییدِ جدا (inv_sell_all_confirm)، و آیتم‌های قفل‌شده هم از فروشِ
    # گروهی مستثنی‌ان.
    buttons.append([InlineKeyboardButton(
        text=f"💰 فروش همه (~{bz_to_display(total_val)})",
        callback_data=f"inv_sell_all_confirm:{uid}"
    , style=ButtonStyle.DANGER)])

    lines.append(f"\n💰 ارزش کل (بدونِ قفل‌شده‌ها): **{bz_to_display(total_val)}**")
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    if edit:
        try: await msg.edit_text("".join(lines), reply_markup=kb)
        except: await msg.answer("".join(lines), reply_markup=kb)
    else:
        await msg.answer("".join(lines), reply_markup=kb)

@dp.callback_query(F.data.startswith("inv_page:"))
async def cb_inv_page(cb: CallbackQuery):
    parts = cb.data.split(":")
    page, uid = int(parts[1]), int(parts[2])
    if cb.from_user.id != uid:
        await cb.answer("❌", show_alert=True); return
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    await show_inventory_page(cb.message, uid, player.get("inventory",[]), page)
    await cb.answer()

@dp.callback_query(F.data.startswith("inv_lock:"))
async def cb_inv_lock(cb: CallbackQuery):
    """قفل‌زدن/بازکردنِ قفلِ یه ردیف از کوله‌پشتی — آیتمِ قفل‌شده نه با دکمه‌ی
    فروشِ تکی، نه با «فروش همه»، فروخته نمی‌شه (تا اشتباهی از دست نره)."""
    from item_system import group_inventory
    _, page_s, gi_s, uid_s = cb.data.split(":")
    page, gi, uid = int(page_s), int(gi_s), int(uid_s)
    if cb.from_user.id != uid:
        await cb.answer("❌", show_alert=True); return
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    inv = player.get("inventory", [])
    groups = group_inventory(inv)
    flat_gi = page * 8 + gi
    if flat_gi >= len(groups):
        await cb.answer("❌ آیتم پیدا نشد!", show_alert=True); return
    g = groups[flat_gi]
    new_locked = not bool(g["item"].get("locked"))
    for idx in g["indices"]:
        inv[idx]["locked"] = new_locked
    player["inventory"] = inv
    save_player(uid, player)
    await cb.answer("🔒 قفل شد!" if new_locked else "🔓 قفل باز شد!", show_alert=False)
    await show_inventory_page(cb.message, uid, inv, page)

@dp.callback_query(F.data.startswith("inv_sell:"))
async def cb_inv_sell_one(cb: CallbackQuery):
    from economy import bz_to_display
    from item_system import group_inventory
    parts = cb.data.split(":")
    page, gi, uid = int(parts[1]), int(parts[2]), int(parts[3])
    if cb.from_user.id != uid:
        await cb.answer("❌", show_alert=True); return
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    inv = player.get("inventory", [])
    groups = group_inventory(inv)
    flat_gi = page * 8 + gi
    if flat_gi >= len(groups):
        await cb.answer("❌ آیتم پیدا نشد!", show_alert=True); return
    g = groups[flat_gi]
    if g["item"].get("locked"):
        await cb.answer("🔒 این آیتم قفله! اول قفلش رو باز کن.", show_alert=True); return
    item, qty, sell = g["item"], g["qty"], g["total_sell"]
    for idx in sorted(g["indices"], reverse=True):
        inv.pop(idx)
    player["inventory"] = inv
    player["zen"] = player.get("zen", 0) + sell
    save_player(uid, player)

    tag = f" ×{qty}" if qty > 1 else ""
    log_sync(
        f"💰 **SELL ITEM** | {player.get('name','—')} (`{uid}`)\n"
        f"📦 {item.get('name','—')}{tag} — +{bz_to_display(sell)}",
        "ECONOMY"
    )

    await cb.answer(f"💰 {item['name']}{tag} فروخته شد! +{bz_to_display(sell)}", show_alert=True)
    if inv:
        new_groups = group_inventory(inv)
        page = min(page, max(0, (len(new_groups)-1)//8))
        await show_inventory_page(cb.message, uid, inv, page)
    else:
        await cb.message.edit_text("🎒 کوله‌پشتیت خالی شد!")

@dp.callback_query(F.data.startswith("inv_sell_all_confirm:"))
async def cb_inv_sell_all_confirm(cb: CallbackQuery):
    """صفحه‌ی جداگانه‌ی تاییدِ «فروش همه» — از لیستِ اصلیِ کوله‌پشتی و دکمه‌های
    فروشِ تکی کاملاً جداست، تا اشتباهی کل کیف خالی نشه."""
    from economy import bz_to_display
    uid = int(cb.data.split(":")[1])
    if cb.from_user.id != uid:
        await cb.answer("❌", show_alert=True); return
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    inv = player.get("inventory", [])
    sellable = [i for i in inv if not i.get("shop_exclusive") and not i.get("locked")]
    locked_n = sum(1 for i in inv if i.get("locked"))
    total = sum(i.get("sell", 0) * i.get("qty", 1) for i in sellable)
    await cb.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ بله، همه رو بفروش (+{bz_to_display(total)})", callback_data=f"inv_sell_all:{uid}", style=ButtonStyle.DANGER)],
        [InlineKeyboardButton(text="❌ انصراف", callback_data=f"inv_page:0:{uid}", style=ButtonStyle.PRIMARY)],
    ])
    lock_note = f"\n🔒 {locked_n} آیتمِ قفل‌شده فروخته نمی‌شه." if locked_n else ""
    await cb.message.edit_text(
        f"⚠️ **فروشِ کاملِ کوله‌پشتی**\n\n"
        f"داری **{len(sellable)}** آیتم رو به مبلغِ **{bz_to_display(total)}** می‌فروشی.\n"
        f"این کار قابلِ برگشت نیست!{lock_note}\n\nمطمئنی؟",
        reply_markup=kb,
    )

@dp.callback_query(F.data.startswith("inv_sell_all:"))
async def cb_inv_sell_all(cb: CallbackQuery):
    from economy import bz_to_display
    uid = int(cb.data.split(":")[1])
    if cb.from_user.id != uid:
        await cb.answer("❌", show_alert=True); return
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    inv   = player.get("inventory", [])
    sellable = [i for i in inv if not i.get("shop_exclusive") and not i.get("locked")]
    kept  = [i for i in inv if i.get("shop_exclusive") or i.get("locked")]
    total = sum(i.get("sell", 0) * i.get("qty", 1) for i in sellable)
    player["inventory"] = kept
    player["zen"] = player.get("zen", 0) + total
    save_player(uid, player)
    
    log_sync(
        f"💰 **SELL ALL** | {player.get('name','—')} (`{uid}`)\n"
        f"📦 {len(sellable)} آیتم — +{bz_to_display(total)}",
        "ECONOMY"
    )
    
    await cb.answer(f"💰 +{bz_to_display(total)}", show_alert=True)
    await cb.message.edit_text(
        f"💰 **همه فروخته شد!**\n\nدریافتی: **{bz_to_display(total)}**\nموجودی: **{bz_to_display(player['zen'])}**"
    )


@dp.callback_query(F.data.startswith("inv_use:"))
async def cb_inv_use(cb: CallbackQuery):
    """مصرفِ آیتم‌های ویژه‌ی «اعتمادِ بازار» (مُهرِ احضارِ باس / اکسیرِ آبیس) —
    یا یه واحد از یه استکِ آیتمِ مصرفی (بقیه‌ی استک دست‌نخورده می‌مونه)."""
    from item_system import group_inventory
    _, page_s, gi_s, uid_s = cb.data.split(":")
    page, gi, uid = int(page_s), int(gi_s), int(uid_s)
    if cb.from_user.id != uid:
        await cb.answer("❌", show_alert=True); return
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    inv = player.get("inventory", [])
    groups = group_inventory(inv)
    flat_gi = page * 8 + gi
    if flat_gi >= len(groups):
        await cb.answer("❌ این آیتم دیگه نیست.", show_alert=True); return
    idx = groups[flat_gi]["indices"][0]  # همیشه یه واحد از اولین entryِ گروه مصرف می‌شه
    item = inv[idx]
    special_id = item.get("special_id")

    if special_id == "boss_seal":
        from market_questline import use_boss_seal
        ok, msg_txt = use_boss_seal(player, item["id"])
        if ok and msg_txt == "PENDING_SPAWN":
            save_player(uid, player)
            from boss_handlers import auto_spawn_daily_boss
            await auto_spawn_daily_boss(cb.bot)
            await cb.answer("🔮 باس احضار شد!", show_alert=True)
        else:
            await cb.answer(msg_txt, show_alert=True)
        return

    if special_id == "abyss_elixir":
        from market_questline import ELIXIR_STAT_OPTIONS
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"inv_elixir:{key}:{idx}:{uid}")]
            for key, (_, label) in ELIXIR_STAT_OPTIONS.items()
        ])
        await cb.message.answer("🧬 کدوم استت رو می‌خوای +1% دائمی کنی؟", reply_markup=kb)
        await cb.answer()
        return

    # ─── آیتم‌های مصرفیِ عمومی (دراپ لوت: پوشن/طومار/کیسه‌طلا) ─────
    if item.get("consumable"):
        from item_system import use_consumable
        ok, res_msg = use_consumable(uid, player, item)
        if ok:
            if item.get("qty", 1) > 1:
                item["qty"] -= 1
            else:
                inv.pop(idx)
            player["inventory"] = inv
            save_player(uid, player)
            log_sync(
                f"✨ **USE ITEM** | {player.get('name','—')} (`{uid}`)\n"
                f"📦 {item.get('name','—')}",
                "ECONOMY"
            )
            await cb.answer(res_msg, show_alert=True)
            if inv:
                new_groups = group_inventory(inv)
                page = min(page, max(0, (len(new_groups) - 1) // 8))
                await show_inventory_page(cb.message, uid, inv, page)
            else:
                try:
                    await cb.message.edit_text("🎒 کوله‌پشتیت خالی شد!")
                except Exception:
                    pass
        else:
            await cb.answer(res_msg, show_alert=True)
        return

    await cb.answer("❌ این آیتم قابلِ مصرف نیست.", show_alert=True)


@dp.callback_query(F.data.startswith("inv_elixir:"))
async def cb_inv_elixir_choose(cb: CallbackQuery):
    _, stat_choice, idx_s, uid_s = cb.data.split(":")
    idx, uid = int(idx_s), int(uid_s)
    if cb.from_user.id != uid:
        await cb.answer("❌", show_alert=True); return
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    inv = player.get("inventory", [])
    if idx >= len(inv):
        await cb.answer("❌ این اکسیر دیگه نیست.", show_alert=True); return
    from market_questline import use_abyss_elixir
    ok, msg_txt = use_abyss_elixir(player, inv[idx]["id"], stat_choice)
    save_player(uid, player)
    await cb.answer(msg_txt, show_alert=True)
    try:
        await cb.message.delete()
    except Exception:
        pass

# ─── Top ─────────────────────────────────────────────────────
LEADERBOARD_CATEGORIES = {
    "level": {
        "title": "🏆 برترین جنگجویان (سطح)",
        "key": lambda p: (p.get("level", 1), p.get("xp", 0)),
        "line": lambda p: f"Lv.{p.get('level',1)} | {p.get('character','—')} | 💰{p.get('zen',0):,}",
    },
    "zen": {
        "title": "💰 ثروتمندترین بازیکنا",
        "key": lambda p: p.get("zen", 0),
        "line": lambda p: f"💰{p.get('zen',0):,} | Lv.{p.get('level',1)}",
    },
    "pvp": {
        "title": "🆚 برترین‌های فصلِ PvP",
        "key": lambda p: p.get("pvp_season_points", 0),
        "line": lambda p: f"🆚 {p.get('pvp_season_points',0):,} امتیازِ فصلی | Lv.{p.get('level',1)}",
    },
    "stand": {
        "title": "👻 قوی‌ترین استندها",
        "key": lambda p: _leaderboard_stand_score(p),
        "line": lambda p: f"👻 {_leaderboard_stand_score(p):,} قدرتِ استند | {p.get('character','—')}",
    },
}


def _leaderboard_stand_score(player: dict) -> int:
    try:
        from stand_system import stand_power_bonus
        return int(stand_power_bonus(player))
    except Exception:
        return 0


def _leaderboard_text(category: str) -> str:
    cat = LEADERBOARD_CATEGORIES[category]
    players  = all_players()
    sorted_p = sorted(players.values(), key=cat["key"], reverse=True)[:10]
    medals   = ["🥇","🥈","🥉"] + ["🏅"]*7
    lines    = [f"{cat['title']}:\n"]
    for i, p in enumerate(sorted_p):
        online = "🟢" if is_online(p.get("id", 0)) else "🔴"
        lines.append(f"{medals[i]} {online} **{p.get('name','—')}** {cat['line'](p)}\n")
    if len(sorted_p) < 1:
        lines.append("هنوز کسی تو این رده‌بندی نیست.")
    return "".join(lines)


def _leaderboard_kb(active: str) -> InlineKeyboardMarkup:
    labels = {"level": "📊 سطح", "zen": "💰 ثروت", "pvp": "PvP", "stand": "👻 استند"}
    row = []
    for key, label in labels.items():
        text = f"• {label} •" if key == active else label
        row.append(InlineKeyboardButton(text=text, callback_data=f"top:{key}", style=ButtonStyle.PRIMARY))
    return InlineKeyboardMarkup(inline_keyboard=[row])


@dp.message(F.text == "رده‌بندی")
@dp.message(Command("top"))
async def cmd_top(msg: Message):
    update_last_seen(msg.from_user.id)
    await msg.answer(_leaderboard_text("level"), reply_markup=_leaderboard_kb("level"))


@dp.callback_query(F.data.startswith("top:"))
async def cb_top_category(cb: CallbackQuery):
    category = cb.data.split(":")[1]
    if category not in LEADERBOARD_CATEGORIES:
        await cb.answer("❌", show_alert=True)
        return
    await cb.message.edit_text(_leaderboard_text(category), reply_markup=_leaderboard_kb(category))
    await cb.answer()

# ─── PvP Button ──────────────────────────────────────────────
# باگ‌فیکس: قبلاً اینجا یه تابع به اسم send_pvp_menu صدا زده می‌شد که
# اصلاً توی pvp_handlers.py وجود نداشت (ImportError) — هر بار روی دکمه‌ی
# PvP می‌زدی این هندلر کرش می‌کرد و چون این handler زودتر از register_pvp_handlers
# رجیستر می‌شد (موقع import، قبل از اجرای main)، جلوی هندلر درستِ cmd_arena رو
# می‌گرفت و ربات هیچی جواب نمی‌داد. حالا مستقیم از تابع درست (cmd_arena) استفاده می‌کنیم.
@dp.message(F.text == "PvP")
async def btn_pvp(msg: Message):
    update_last_seen(msg.from_user.id)
    from pvp_handlers import cmd_arena
    await cmd_arena(msg)

# ─── Boss ────────────────────────────────────────────────────

# ─── Admin Commands ───────────────────────────────────────────
# ⚠️ منسوخ شده — دقیقاً هم‌پوشانِ /chargrant (تو admin_panel.py) بود ولی
# ناقص‌تر: کاراکترِ قبلیِ پلیر رو هیچ‌وقت به pool برنمی‌گردوند (release_char
# صدا زده نمی‌شد)، یعنی هر کاراکترِ قدیمی برای همیشه «تصرف‌شده» می‌موند.
# طبقِ همون الگویی که /resetplayer و /softreset با آن یکی شدن، این کامند هم
# غیرفعال شد؛ فقط /chargrant (نسخه‌ی کامل و درست) باقی می‌مونه.
@dp.message(Command("givechar"))
async def cmd_givechar(msg: Message):
    if not is_admin(msg): await msg.answer("❌ فقط ادمین!"); return
    await msg.answer(
        "⚠️ این کامند منسوخ شده (کاراکترِ قدیمی رو به pool برنمی‌گردوند).\n"
        "به‌جاش از `/chargrant <telegram_id> <نام کاراکتر>` استفاده کن."
    )

@dp.message(Command("givezen"))
async def cmd_givezen(msg: Message):
    if not is_admin(msg): await msg.answer("❌ فقط ادمین!"); return
    parts = msg.text.split()
    if len(parts) < 3: await msg.answer("📝 `/givezen user_id amount`"); return
    try: target_id, amount = int(parts[1]), int(parts[2])
    except: await msg.answer("❌ عدد وارد کن."); return
    player = get_player(target_id)
    if not player: await msg.answer("❌ بازیکن پیدا نشد."); return
    player["zen"] += amount
    save_player(target_id, player)
    await msg.answer(f"✅ {amount:,} Zen به {player['name']} داده شد.")
    
    log_sync(
        f"🛠️ **GIVEZEN** | ادمین: `{msg.from_user.id}`\n"
        f"👤 {player['name']} (`{target_id}`)\n"
        f"💰 +{amount:,} Zen",
        "ADMIN"
    )

@dp.message(Command("remgold"))
async def cmd_remgold(msg: Message):
    # نکته: این کامند اصلاً وجود نداشت — /givezen (اضافه‌کردن) بود ولی هیچ‌جا
    # کامندِ متقارنش برای کم‌کردن نبود. اضافه شد.
    if not is_admin(msg): await msg.answer("❌ فقط ادمین!"); return
    parts = msg.text.split()
    if len(parts) < 3: await msg.answer("📝 `/remgold user_id amount`"); return
    try: target_id, amount = int(parts[1]), int(parts[2])
    except: await msg.answer("❌ عدد وارد کن."); return
    if amount < 0: await msg.answer("❌ مقدار باید مثبت باشه (خودش کم می‌کنه)."); return
    player = get_player(target_id)
    if not player: await msg.answer("❌ بازیکن پیدا نشد."); return
    before = player.get("zen", 0)
    player["zen"] = max(0, before - amount)
    removed = before - player["zen"]
    save_player(target_id, player)
    await msg.answer(f"✅ {removed:,} Zen از {player['name']} کم شد. (موجودیِ فعلی: {player['zen']:,})")

    log_sync(
        f"🛠️ **REMGOLD** | ادمین: `{msg.from_user.id}`\n"
        f"👤 {player['name']} (`{target_id}`)\n"
        f"💰 -{removed:,} Zen",
        "ADMIN"
    )

# ⚠️ دیگه جایی صدا زده نمی‌شه (/resetplayer و /softreset منسوخ شدن —
# پایین‌تر رو ببین). نگه داشته شده فقط برای ارجاعِ تاریخی؛ منطقِ
# فعلیِ ریست تو database.full_reset_player هست.
def _reset_player_fields(player: dict, keep_character: bool = False) -> str | None:
    """همه‌ی فیلدهای پروفایل رو صفر می‌کنه. اگه keep_character=True باشه،
    کاراکترِ فعلی دست‌نخورده می‌مونه؛ وگرنه یه کاراکترِ رندومِ جدید می‌گیره.
    خروجی: اسمِ کاراکترِ نهایی (برای نمایش تو پیام)."""
    char = player.get("character") if keep_character else assign_random_char()
    player["level"]     = 1
    player["xp"]        = 0
    player["hp"]        = 100
    player["max_hp"]    = 100
    player["zen"]       = 1125
    player["inventory"] = []
    player["combo"]     = 0
    player["kills"]     = 0
    player["pvp_wins"]  = 0
    if not keep_character:
        player["character"] = char
        from character_lore import mark_character_seen; mark_character_seen(player, char)
    player["katana_level"] = 1
    player["skill_points"] = 0
    player["unlocked_skills"] = []
    player["loot_streak"]        = 0
    player["loot_best_streak"]   = 0
    player["pity_counter"]       = 0
    player["fortune_ward_count"] = 0
    player["set_collection"]     = {}
    player["streak_shield_used_day"] = None
    player["death_count"]           = 0
    player["death_curse_until"]     = 0
    player["heal_lockout_until"]    = 0
    player["heal_cooldown_until"]   = 0
    player["injuries"]              = []
    player["battles_since_rest"]    = 0
    player["resting_until"]         = 0
    player["walls_cleared"]         = []
    player["area_bosses_killed"]    = []
    player["daily_battle_used"]     = 0
    player["daily_battle_reset_at"] = 0
    player["daily_heal_used"]       = 0
    player["daily_heal_reset_at"]   = 0
    player["daily_bm_buy_used"]     = 0
    player["daily_bm_buy_reset_at"] = 0
    player["quest_node"]            = None
    player["quest_flags"]           = {}
    player["quest_riddle_tries"]    = 0
    player["quest_seq_progress"]    = []
    player["resonance"]             = 0
    player["main_chapter"]          = 0
    player["side_quests_done"]      = []
    player["side_quests_active"]    = {}
    player["kill_log"]              = {}
    player["guilds"]                = {}
    player["rebirth_count"]         = 0
    player["pvp_wins"]              = 0
    player["pvp_losses"]            = 0
    player["pvp_streak"]            = 0
    player["pvp_best_streak"]       = 0
    player["pvp_points"]            = 0
    player["pvp_total_dmg_dealt"]   = 0
    player["pvp_total_dmg_taken"]   = 0
    player["pvp_biggest_hit"]       = 0
    player["pvp_ability_usage"]     = {}
    player["pvp_history"]           = []
    return char


# ─── منسوخ شده ───────────────────────────────────────────────
# /resetplayer و /softreset قبلاً هرکدوم یه منطقِ ریستِ جداگونه (و
# ناقص — خیلی از فیلدهای زیرسیستم‌ها مثل بانک/کازینو/بتل‌پس رو
# اصلاً لمس نمی‌کردن) داشتن، هم‌زمان با /playerreset تو admin_panel.py
# که خودش هم یه پیاده‌سازیِ ناقصِ دیگه داشت — یعنی ۳ تا کامندِ
# هم‌پوشان با ۳ تا رفتارِ متفاوت و همه ناقص. حالا فقط یه نسخه‌ی
# کامل و درست هست: /playerreset (تو admin_panel.py) که هم تأییدِ
# دکمه‌ای داره، هم واقعاً *همه‌چیز* رو ریست می‌کنه، هم آپشنِ
# «کاراکترِ جدید» رو با /playerreset <id> newchar می‌ده.
@dp.message(Command("resetplayer"))
async def cmd_reset_player(msg: Message):
    if not is_admin(msg): await msg.answer("❌ فقط ادمین!"); return
    await msg.answer(
        "⚠️ این کامند منسوخ شده (ریستِ ناقص بود).\n"
        "به‌جاش از `/playerreset <telegram_id> newchar` استفاده کن — "
        "ریستِ کامل + کاراکترِ رندومِ جدید، با تأییدِ دکمه‌ای."
    )


@dp.message(Command("softreset"))
async def cmd_soft_reset_player(msg: Message):
    if not is_admin(msg): await msg.answer("❌ فقط ادمین!"); return
    await msg.answer(
        "⚠️ این کامند منسوخ شده (ریستِ ناقص بود).\n"
        "به‌جاش از `/playerreset <telegram_id>` استفاده کن — "
        "ریستِ کامل با حفظِ کاراکتر و کاتانا، با تأییدِ دکمه‌ای."
    )

@dp.message(Command("characters"))
async def cmd_characters(msg: Message):
    lines = ["📖 **لیست کاراکترهای ASTRAL ABYSS:**\n"]
    for name, d in ALL_CHARACTERS.items():
        e = RARITY_EMOJI.get(d.get("rarity", "common"), "⚔️")
        lines.append(f"{e} **{name}** — {d['element']}")
    await msg.answer("\n".join(lines))

# ⚠️ /help قدیمی به help_system.py منتقل شد (راهنمای کاملِ دسته‌بندی‌شده —
# پایین‌تر تو register_all_handlers، register_help_handlers صداش می‌کنه).


# ─── اتصالِ حساب (تلگرام ⇄ گپ) ──────────────────────────────
# /link          → کد می‌سازه (این حساب = اصلی)
# /link CODE     → کدِ ساخته‌شده تو پلتفرمِ دیگه رو وارد می‌کنه (وصل می‌شه)
@dp.message(F.text == "🔗 اتصال حساب")
async def btn_link_account(msg: Message):
    uid = msg.from_user.id
    if not get_player(uid):
        return
    await msg.answer(link_status_text(uid))


@dp.message(Command("link"))
async def cmd_link(msg: Message):
    uid = msg.from_user.id
    if not get_player(uid):
        await msg.answer("❗️ اول باید کاراکتر بسازی.")
        return

    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) < 2:
        ok, result = generate_link_code(uid)
        if not ok:
            await msg.answer(result)
            return
        await msg.answer(
            f"🔗 کدِ اتصالِ حساب: `{result}`\n\n"
            "این کد ۱۰ دقیقه معتبره. برو تو اون یکی پلتفرم (گپ/تلگرام) "
            f"و بزن:\n`/link {result}`"
        )
        return

    code = parts[1].strip()
    ok, result = redeem_link_code(code, uid)
    await msg.answer(result)


# ─── Button Handlers ─────────────────────────────────────────
@dp.message(F.text == "حمله")
async def btn_attack(msg: Message):
    update_last_seen(msg.from_user.id)
    from combat_handlers import cmd_attack
    await cmd_attack(msg)

@dp.message(F.text == "لوت")
async def btn_loot(msg: Message):
    update_last_seen(msg.from_user.id)
    from loot_handlers import cmd_loot
    await cmd_loot(msg)

# ─── 🗺️ دکمه‌های پنلِ ماجراجو ────────────────────────────────
@dp.message(F.text == "🗡 کاتانا")
async def btn_katana(msg: Message):
    update_last_seen(msg.from_user.id)
    from katana_handlers import cmd_katana
    await cmd_katana(msg)

@dp.message(F.text == "📜 کوئست‌های جانبی")
async def btn_sidequests(msg: Message):
    update_last_seen(msg.from_user.id)
    from quest_handlers import cmd_sidequests
    await cmd_sidequests(msg)

@dp.message(F.text == "🏹 کوئست‌لاینِ شکار")
async def btn_hunt_questline(msg: Message):
    update_last_seen(msg.from_user.id)
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول باید کاراکترت رو بسازی! /start رو بزن.")
        return
    from hunt_questline import hunt_progress
    from hunt_handlers import _hunt_text, _hunt_kb
    progress = hunt_progress(player)
    await msg.answer(_hunt_text(progress), reply_markup=_hunt_kb(progress))

# ─── ⚜️ دکمه‌ی مشترکِ «قدرت‌های کلاس» (وایر شده به پنلِ خودِ هر کلاس) ───
@dp.message(F.text == "⚜️ قدرت‌های کلاس")
async def btn_class_panel(msg: Message):
    update_last_seen(msg.from_user.id)
    from class_ability_handlers import cmd_class_panel
    await cmd_class_panel(msg)

# ─── 🧙 دکمه‌ی پنلِ جادوگر: کارگاه (کرفتینگ/آلکمی + صرافیِ متریال) ────
@dp.message(F.text == "🛠 کارگاه")
async def btn_workshop(msg: Message):
    update_last_seen(msg.from_user.id)
    from crafting_handlers import cmd_craft
    await cmd_craft(msg)

# ─── 💰 دکمه‌ی پنلِ تاجر: سفر — از bot.py درآورده شد، الان register_caravan_handlers
# (caravan_handlers.py) این دکمه رو مستقیماً وایر می‌کنه؛ سفر یعنی فرستادنِ
# کاروانِ تجاری واقعی (سرمایه‌گذاری + ریسک/سود)، نه بازدید از مغازه‌ی بقیه.

@dp.message(F.text.in_({STORY_BUTTON_TEXT, STORY_BUTTON_TEXT_NEW}))
async def btn_story(msg: Message):
    update_last_seen(msg.from_user.id)
    from quest_handlers import cmd_story
    await cmd_story(msg)

@dp.message(F.text == "بازار سیاه")
async def btn_blackmarket(msg: Message):
    update_last_seen(msg.from_user.id)
    from loot_handlers import cmd_blackmarket
    await cmd_blackmarket(msg)

@dp.message(F.text == "ایونت")
async def btn_event(msg: Message):
    update_last_seen(msg.from_user.id)
    from combat_handlers import cmd_event
    await cmd_event(msg)

@dp.message(F.text == "بیمارستان")
async def btn_hospital(msg: Message):
    update_last_seen(msg.from_user.id)
    from hospital_handlers import cmd_hospital
    await cmd_hospital(msg)

# ─── سازگاریِ عقب‌رو: دکمه‌ی قدیمیِ «💊 درمان» ────────────────────
# این دکمه قبلاً به‌جای «🏥 بیمارستان» بود و به منوی درمانِ HP می‌رفت.
# بازیکن‌هایی که کیبوردشون از قبل از این تغییر آپدیت نشده (تلگرام
# آخرین کیبوردِ فرستاده‌شده رو تا وقتی یه پیامِ جدید کیبورد رو عوض
# نکنه نگه می‌داره)، هنوز ممکنه رو همون دکمه‌ی قدیمی بزنن. بدونِ این
# هندلر، اون متن به‌هیچ‌جا نمی‌خورد و به‌جاش پیامِ فال/لورِ عمومیِ
# lore_chat جوابش می‌ده که برای بازیکن گیج‌کننده‌ست.
@dp.message(F.text == "💊 درمان")
async def btn_hospital_legacy(msg: Message):
    update_last_seen(msg.from_user.id)
    from hospital_handlers import cmd_hospital
    await msg.answer("🏥 این بخش الان اسمش «بیمارستان» شده — پنلت رو تازه می‌کنم:", reply_markup=main_kb(is_group=_is_group_chat(msg.chat.type), player=get_player(msg.from_user.id)))
    await cmd_hospital(msg)

@dp.message(F.text == "تیم")
async def btn_team(msg: Message):
    update_last_seen(msg.from_user.id)
    from team_handlers import cmd_team
    await cmd_team(msg)

@dp.message(F.text == "کازینو")
async def btn_casino(msg: Message):
    update_last_seen(msg.from_user.id)
    from casino_handlers import cmd_casino
    await cmd_casino(msg)

@dp.message(F.text == "شکار جایزه")
async def btn_bounty(msg: Message):
    update_last_seen(msg.from_user.id)
    from bounty_handlers import cmd_bounty
    await cmd_bounty(msg)

@dp.message(F.text == "حراجی")
async def btn_auction(msg: Message):
    update_last_seen(msg.from_user.id)
    from auction_handlers import cmd_auction
    await cmd_auction(msg)

@dp.message(F.text == "نمسیس من")
async def btn_nemesis(msg: Message):
    update_last_seen(msg.from_user.id)
    from nemesis_handlers import cmd_nemesis
    await cmd_nemesis(msg)

@dp.message(F.text == "استادی")
async def btn_mentor(msg: Message):
    update_last_seen(msg.from_user.id)
    from mentor_handlers import cmd_mentor
    await cmd_mentor(msg)

@dp.message(F.text == "ملک شخصی")
async def btn_house(msg: Message):
    update_last_seen(msg.from_user.id)
    from house_handlers import cmd_house
    await cmd_house(msg)

@dp.message(F.text == "مغازه‌ی من")
async def btn_shop(msg: Message):
    update_last_seen(msg.from_user.id)
    from shop_handlers import cmd_shop
    await cmd_shop(msg)

@dp.message(F.text == "حلقه‌ی سایه")
async def btn_underground(msg: Message):
    update_last_seen(msg.from_user.id)
    from underground_handlers import cmd_underground
    await cmd_underground(msg)

@dp.message(F.text == "📜 تابلوی کارگزار")
async def btn_contracts(msg: Message):
    update_last_seen(msg.from_user.id)
    from contract_handlers import cmd_contracts
    await cmd_contracts(msg)

@dp.message(F.text == "🌀 شکاف Abyss")
async def btn_riftdive(msg: Message):
    update_last_seen(msg.from_user.id)
    from rift_dive_handlers import cmd_riftdive
    await cmd_riftdive(msg)

@dp.message(F.text == "🐎 مونت‌ها")
async def btn_mounts(msg: Message):
    update_last_seen(msg.from_user.id)
    from mount_handlers import cmd_mounts
    await cmd_mounts(msg)

@dp.message(F.text == "🏟 آرنا")
async def btn_arena(msg: Message):
    update_last_seen(msg.from_user.id)
    from arena_handlers import cmd_arena
    await cmd_arena(msg)

@dp.message(F.text == "🌌 هم‌گرایی")
async def btn_convergence(msg: Message):
    update_last_seen(msg.from_user.id)
    from convergence_handlers import cmd_convergence
    await cmd_convergence(msg)

@dp.message(F.text == "🕊 الهه")
async def btn_goddess(msg: Message):
    update_last_seen(msg.from_user.id)
    from goddess_handlers import cmd_goddess
    await cmd_goddess(msg)

@dp.message(F.text == "ردیابی")
async def btn_track(msg: Message):
    update_last_seen(msg.from_user.id)
    await msg.answer(
        "🔍 **ردیابی جنگجو**\n\n"
        "• `/track @username`\n"
        "• `/track user_id`\n"
        "• `/track نام_بازیکن`"
    )

@dp.message(Command("pulse"))
async def cmd_pulse(msg: Message):
    from world_pulse import pulse_status_text
    await msg.answer(pulse_status_text())

@dp.callback_query(F.data == "pulse:status")
async def cb_pulse_status(cb: CallbackQuery):
    from world_pulse import pulse_status_text
    await cb.message.answer(pulse_status_text())
    await cb.answer()

@dp.message(F.text == "دستاوردها")
@dp.message(Command("achievements"))
async def cmd_achievements(msg: Message):
    uid = msg.from_user.id
    update_last_seen(uid)
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    from achievements import check_achievements, achievements_list_text
    new_titles = check_achievements(player)
    if new_titles:
        save_player(uid, player)
    text = achievements_list_text(player)
    for t in new_titles:
        text += f"\n\n🏅 **عنوان جدید باز شد: {t}**"
    await msg.answer(text)

@dp.message(F.text == "کدکس")
@dp.message(Command("codex"))
async def cmd_codex(msg: Message):
    uid = msg.from_user.id
    update_last_seen(uid)
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    from character_lore import codex_text
    await msg.answer(codex_text(player))

@dp.message(F.text == "🎴 کارت من")
@dp.message(Command("card"))
async def cmd_profile_card(msg: Message):
    uid = msg.from_user.id
    update_last_seen(uid)
    player = get_player(uid)
    if not player or not player.get("class"):
        await msg.answer("❌ اول /start بزن و کاراکترت رو بساز!")
        return

    # 🆕 باگ‌فیکس: این کارتِ تصویری فقط برای سیستمِ قدیمیِ کاتانا/کاراکتر
    # طراحی شده (ALL_CHARACTERS + katana_core). بازیکن‌هایی که از سیستمِ
    # جدیدِ کلاس (جادوگر/جنگجو/دزد و...) اومدن، اصلاً player["character"]
    # ندارن — قبلاً همین‌جا با KeyError کرش می‌کرد و کاربر به‌جای خطای
    # واقعی، یه پیامِ گمراه‌کننده می‌دید. الان اگه کاراکترِ کاتانایی نداره،
    # همون کارتِ متنیِ کلاس (مثلِ دستورِ «کارت») نشون داده می‌شه.
    if not player.get("character"):
        await msg.answer(class_card_text(player))
        return

    char_data = ALL_CHARACTERS.get(player["character"], {})
    try:
        import tempfile, os
        from profile_card import generate_profile_card
        out_path = os.path.join(tempfile.gettempdir(), f"card_{uid}.png")
        generate_profile_card(player, char_data, out_path)
        await msg.answer_photo(FSInputFile(out_path), caption=f"🎴 کارتِ {player['name']}")
    except Exception as e:
        log_sync(f"🔴 profile card error: {e}", "ERROR")
        await msg.answer("⚠️ ساختِ کارت با مشکل مواجه شد.")

@dp.message(Command("calendar"))
async def cmd_calendar(msg: Message):
    uid = msg.from_user.id
    update_last_seen(uid)
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    try:
        import tempfile, os
        from profile_card import generate_login_calendar
        out_path = os.path.join(tempfile.gettempdir(), f"calendar_{uid}.png")
        generate_login_calendar(player.get("login_streak", 0) or 1, out_path)
        await msg.answer_photo(FSInputFile(out_path))
    except Exception as e:
        log_sync(f"🔴 calendar error: {e}", "ERROR")
        await msg.answer("⚠️ ساختِ تقویم با مشکل مواجه شد.")

# ─── Lore Chat (no AI) ───────────────────────────────────────
LORE_RESPONSES = [
    "🌑 *در اعماق آبیس، صداها آرام می‌شوند...*\nانگار دنیا نفس می‌کشد، اما تو نمی‌توانی آن را بشنوی.",
    "👁️ *چشمانی در تاریکی تو را می‌نگرند...*\nاز کجا آمده‌ای، جنگجو؟",
    "⚔️ *کاتانا در دستت می‌لرزد...*\nنیروهای باستانی از عمق Void Rift بیدار می‌شوند.",
    "🌌 *ستاره‌ها در Lost Nebula خاموش می‌شوند...*\nتاریکی جایشان را می‌گیرد.",
    "🔥 *شعله‌های Emberhollow زمزمه می‌کنند...*\nقدرت واقعی در درون تو پنهان است.",
    "❄️ *یخ‌های Frostheim آب می‌شوند...*\nزمستان تمام شد. جنگ آغاز می‌شود.",
    "🐉 *غرش اژدها از Dragonnest Peaks می‌آید...*\nآنها بیدار شده‌اند. آیا جرأت داری؟",
    "💀 *از Dread Citadel صدای زنجیرها می‌آید...*\nکسی در آنجا زندانی است.",
    "🌑 *سایه‌های Shadow Rift حرکت می‌کنند...*\nهر قدمی که برمی‌داری، آنها دنبالت می‌آیند.",
]

BUTTONS = {
    "حمله","لوت","وضعیت","کوله‌پشتی",
    "بازار سیاه","PvP","باس جهانی","رده‌بندی",
    "ایونت","بیمارستان","💊 درمان","تیم","ردیابی","گیلدها","کازینو","شکار جایزه","حراجی","نمسیس من","استادی","ملک شخصی","مغازه‌ی من","حلقه‌ی سایه","📜 تابلوی کارگزار","بانک",
} | set(CATEGORIES.keys()) | set(LEVEL_REQUIREMENTS.keys()) | set(SHORTCUT_BUTTONS) | set(GROUP_SHORTCUT_BUTTONS) | {BACK_TO_MAIN}

# ─── باگ‌فیکس: بعضی کیبوردهای موبایل/فارسی، کاراکترهای نامرئیِ RTL/LTR
# (مثل U+200F یا U+200E) رو به‌صورتِ نامحسوس به ابتدا/انتهای متنِ تایپ‌شده
# اضافه می‌کنن. این کاراکترها با چشم دیده نمی‌شن ولی مقایسه‌ی == رو خراب
# می‌کنن، و همین باعث می‌شه دکمه‌هایی مثل «حمله»/«نبرد» به‌جای هندلرِ
# واقعی‌شون، به این fallback (لور) بیفتن. این‌جا قبل از مقایسه پاکشون می‌کنیم.
_INVISIBLE_MARKS_RE = re.compile(r"[\u200e\u200f\u061c\ufeff]")

def _clean_btn_text(text: str) -> str:
    return _INVISIBLE_MARKS_RE.sub("", text).strip()

async def lore_chat(msg: Message):
    if msg.chat.type != "private": return
    if not msg.text: return
    cleaned = _clean_btn_text(msg.text)
    if msg.text.startswith("/") or is_locked_button_text(cleaned) or cleaned in BUTTONS: return
    # ─── تشخیصِ کمکی: اگه این fallback برای متنی افتاد که به یه دکمه
    # شباهت داره (کوتاهه، فاصله نداره)، برای ادمین لاگ کن تا اگه دوباره
    # این باگ برگشت، بشه دقیقاً فهمید کدوم متن و با چه بایت‌هایی بوده.
    if cleaned and len(cleaned) <= 20 and " " not in cleaned:
        try:
            log_sync(
                f"⚠️ **lore_chat fallback triggered by button-like text**\n"
                f"👤 uid=`{msg.from_user.id}`\n"
                f"متن: `{cleaned!r}`\n"
                f"هگز: `{cleaned.encode('unicode_escape')}`",
                "WARN",
            )
        except Exception:
            pass
    update_last_seen(msg.from_user.id)
    await msg.answer(random.choice(LORE_RESPONSES))

# ─── اطلاع‌رسانیِ ری‌استارت به بازیکن‌ها ──────────────────────────
async def notify_players_restart(bot_: Bot):
    """بعد از هر بالا اومدنِ ربات، به همه‌ی بازیکن‌های تلگرام (uid مثبت —
    بازیکن‌های گپ uid منفی دارن و از سمتِ خودِ گپ نوتیف می‌شن) می‌گه یه
    بار /start بزنن."""
    text = "🔄 **ربات ری‌استارت شد!**\nلطفاً یه بار /start رو بزن تا همه‌چی درست آپدیت بشه."
    sent = failed = 0
    try:
        players = all_players()
        log_sync(f"🔄 **RESTART NOTICE شروع شد** — {len(players)} بازیکن پیدا شد.", "START")
        for pid in players:
            if not str(pid).lstrip("-").isdigit() or int(pid) <= 0:
                continue
            try:
                await bot_.send_message(int(pid), text)
                sent += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.05)  # rate-limit ملایم
        log_sync(f"🔄 **RESTART NOTICE** ارسال شد به {sent} بازیکن ({failed} ناموفق).", "START")
    except Exception as e:
        # 🆕 باگ‌فیکس: قبلاً اگه چیزی خارج از حلقه (مثلاً خودِ all_players)
        # کرش می‌کرد، کل تابع بی‌صدا می‌مرد و هیچ لاگی هم ثبت نمی‌شد — دقیقاً
        # همون حالتی که باعث می‌شد بگی «اصلاً نمی‌فرسته». حالا حتماً لاگ می‌شه.
        import traceback
        tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))[-2500:]
        log_sync(f"🔴 **RESTART NOTICE کرش کرد** (بعد از {sent} ارسالِ موفق)\n```\n{tb}\n```", "ERROR")


# ─── Main ────────────────────────────────────────────────────
async def main():
    set_bot(bot)

    # ─── جوینِ اجباریِ گپ/کانال ─────────────────────────────────
    from force_join import register_force_join
    register_force_join(dp, bot)

    # ─── بازیابیِ کرکترای پروسیجرالِ ساخته‌شده (بعد از تمومِ ۳۵۰ تای
    # دستی) از دیتابیس، تا بعد از هر ری‌استارت دوباره تو ALL_CHARACTERS
    # باشن و ترکیب/جنگ/پروفایلشون خراب نشه ──────────────────────
    from database import load_generated_characters
    load_generated_characters()

    # ─── ثبت منوی دستورات «/» تلگرام (برای گروه‌ها و PV) ──────
    try:
        await bot.set_my_commands(GROUP_COMMANDS, scope=BotCommandScopeAllGroupChats())
        await bot.set_my_commands(PRIVATE_COMMANDS, scope=BotCommandScopeAllPrivateChats())
    except Exception as e:
        logging.warning(f"set_my_commands failed: {e}")
    
    from pvp_handlers import register_pvp_handlers
    from loot_handlers import register_loot_handlers
    from combat_handlers import register_combat_handlers
    from hunt_handlers import register_hunt_handlers
    from team_handlers import register_team_handlers
    from boss_handlers import register_boss_handlers
    from skill_handlers import register_skill_handlers
    from guild_handlers import register_guild_handlers
    from admin_panel import register_admin_handlers
    from quest_handlers import register_quest_handlers
    # ─── باگ‌فیکس مهم: این سه ماژول کامل نوشته شده بودن ولی هیچ‌جا
    # صدا زده نمی‌شدن — یعنی کل سیستمِ عمیقِ کاتانا، کارتِ قدرتِ نبرد
    # (Combat Power) و سیستمِ رید عملاً تو رباتِ روشن هیچ دستوری نداشتن.
    from katana_handlers import register_katana_handlers
    from progression_handlers import register_progression_handlers
    from equipment_handlers import register_equipment_handlers
    from raid_handlers import register_raid_handlers
    from casino_handlers import register_casino_handlers
    from bounty_handlers import register_bounty_handlers
    # 🆕 Stage 3: سیستم‌های فعالِ کلاس (طلسمِ ترکیبیِ جادوگر، پنلِ مزدورِ
    # تاجر، نورِ مقدسِ درمانگر، کاوشِ دخمه‌ی ماجراجو)
    from class_ability_handlers import register_class_ability_handlers
    from help_system import register_help_handlers
    from isekai_theme import register_isekai_handlers
    from grand_bazaar_handlers import register_grand_bazaar_handlers
    from road_merchants_handlers import register_road_merchant_handlers
    # 🆕 پی‌وی‌پیِ تیمی (۲به۲..۵به۵) + نقشه‌ی جنگِ عمیقِ گیلدها
    from team_pvp_handlers import register_team_pvp_handlers
    from guild_war_handlers import register_guild_war_handlers

    register_help_handlers(dp, bot)
    register_team_pvp_handlers(dp, bot)
    register_guild_war_handlers(dp, bot)
    register_isekai_handlers(dp, bot)
    register_grand_bazaar_handlers(dp, bot)
    register_road_merchant_handlers(dp, bot)
    register_pvp_handlers(dp, bot)
    register_loot_handlers(dp, bot)
    register_combat_handlers(dp, bot)
    register_class_ability_handlers(dp, bot)
    register_hunt_handlers(dp, bot)
    register_team_handlers(dp, bot)
    from hospital_handlers import register_hospital_handlers
    register_hospital_handlers(dp, bot)
    register_boss_handlers(dp, bot)
    register_skill_handlers(dp, bot)
    register_guild_handlers(dp, bot)
    register_casino_handlers(dp, bot)
    register_bounty_handlers(dp, bot)
    register_quest_handlers(dp)
    register_katana_handlers(dp, bot)
    register_progression_handlers(dp, bot)
    register_equipment_handlers(dp, bot)
    register_raid_handlers(dp)
    register_admin_handlers(dp, bot)  # ← آخرین باشه
    
    from trade_handlers import register_trade_handlers
    register_trade_handlers(dp, bot)

    from auction_handlers import register_auction_handlers
    register_auction_handlers(dp, bot)

    from nemesis_handlers import register_nemesis_handlers
    register_nemesis_handlers(dp, bot)

    from mentor_handlers import register_mentor_handlers
    register_mentor_handlers(dp, bot)

    from house_handlers import register_house_handlers
    register_house_handlers(dp, bot)

    from land_handlers import register_land_handlers
    register_land_handlers(dp, bot)

    from farm_handlers import register_farm_handlers
    register_farm_handlers(dp, bot)

    from cooking_handlers import register_cooking_handlers
    register_cooking_handlers(dp, bot)

    from crafting_handlers import register_crafting_handlers
    register_crafting_handlers(dp, bot)

    # ─── 🚶 سفرِ کاروانِ تاجر (caravan_system.py) ────────────────────
    from caravan_handlers import register_caravan_handlers
    register_caravan_handlers(dp, bot)

    # ─── 🆕 سیستم‌های لول‌آپِ روزانه‌ی کلاس‌های غیرـ‌ماجراجو ─────────
    # تاجر → 🤝 معامله‌ی روزانه | درمانگر → 🩺 نوبت‌دهی | جادوگر → 🔮 مشتری‌ها
    # (هرسه از موتورِ مشترکِ class_activity_engine.py استفاده می‌کنن تا
    # Zen/XPِ گرنت‌شده با همون اقتصاد/سقفِ ضدـ‌فارمِ ماجراجو هم‌تراز بمونه.)
    from merchant_deals_handlers import register_merchant_deals_handlers
    register_merchant_deals_handlers(dp, bot)

    from healer_duty_handlers import register_healer_duty_handlers
    register_healer_duty_handlers(dp, bot)

    from wizard_atelier_handlers import register_wizard_atelier_handlers
    register_wizard_atelier_handlers(dp, bot)

    # ─── متریال‌های نقشه‌ای (economy.MAP_LOOT) قبلاً فقط قابل‌فروش
    # بودن و هیچ مصرفی نداشتن. این سه ماژول بهشون مصرف می‌ده — همه
    # از منوی کارگاه (/craft) در دسترسن:
    from material_exchange_handlers import register_material_exchange_handlers
    register_material_exchange_handlers(dp, bot)

    from map_recipes_handlers import register_map_recipes_handlers
    register_map_recipes_handlers(dp, bot)

    from artifact_forge_handlers import register_artifact_forge_handlers
    register_artifact_forge_handlers(dp, bot)

    from collection_codex_handlers import register_collection_codex_handlers
    register_collection_codex_handlers(dp, bot)

    from gathering_handlers import register_gathering_handlers
    register_gathering_handlers(dp, bot)

    from exchange_handlers import register_exchange_handlers
    register_exchange_handlers(dp, bot)

    from shop_handlers import register_shop_handlers
    register_shop_handlers(dp, bot)

    from underground_handlers import register_underground_handlers
    register_underground_handlers(dp, bot)

    from titles_handlers import register_titles_handlers
    register_titles_handlers(dp, bot)

    from seasonal_arc_handlers import register_seasonal_arc_handlers
    register_seasonal_arc_handlers(dp, bot)

    from stats_handlers import register_stats_handlers
    register_stats_handlers(dp, bot)

    from pet_handlers import register_pet_handlers
    register_pet_handlers(dp, bot)

    from contract_handlers import register_contract_handlers
    register_contract_handlers(dp, bot)

    from rift_dive_handlers import register_rift_dive_handlers
    register_rift_dive_handlers(dp, bot)

    from mount_handlers import register_mount_handlers
    register_mount_handlers(dp, bot)

    from arena_handlers import register_arena_handlers
    register_arena_handlers(dp, bot)

    from convergence_handlers import register_convergence_handlers
    register_convergence_handlers(dp, bot)

    from goddess_handlers import register_goddess_handlers
    register_goddess_handlers(dp, bot)

    from evolution_handlers import register_evolution_handlers
    register_evolution_handlers(dp, bot)

    from appraisal_handlers import register_appraisal_handlers
    register_appraisal_handlers(dp, bot)

    from battle_pass_handlers import register_battle_pass_handlers
    register_battle_pass_handlers(dp, bot)

    from abandoned_locations import register_abandoned_location_handlers
    register_abandoned_location_handlers(dp, bot)

    from bank_handlers import register_bank_handlers
    register_bank_handlers(dp, bot)

    from stand_handlers import register_stand_handlers
    register_stand_handlers(dp, bot)

    # ─── گروه (رِیدِ باسِ گروهی، رتبه‌بندیِ گروه، دوئلِ سریع، منشن) ──
    # باید تقریباً آخرین باشه چون handle_group_mention (داخلِ همین
    # register) رو هر پیامِ گروهی که منشن/ریپلای‌به‌ربات باشه رجیستر
    # می‌کنه و نباید جلوی هیچ کامندِ دیگه‌ای رو بگیره.
    from group_handlers import register_group_handlers
    register_group_handlers(dp, bot)

    from region_boss_handlers import register_region_boss_handlers
    register_region_boss_handlers(dp, bot)

    from boss_invite_handlers import register_boss_invite_handlers
    register_boss_invite_handlers(dp, bot)

    # ─── اینلاین‌مود (رشدِ ویروسی — @AbyssAstralbot تو هر چتی) ─────
    # یادت نره تو @BotFather → Bot Settings → Inline Mode رو Turn on کنی!
    from inline_handlers import register_inline_handlers
    register_inline_handlers(dp, bot)

    dp.message.register(lore_chat)

    # ─── جایزه‌ی هفتگیِ رده‌بندی + فصل PvP ────────────────────
    from weekly_rewards import weekly_rewards_loop
    _spawn_task(weekly_rewards_loop(bot))

    from convergence_system import convergence_loop
    _spawn_task(convergence_loop(bot))

    from isekai_flavor import isekai_flavor_loop
    _spawn_task(isekai_flavor_loop(bot))

    # ─── ضربانِ آبیس (رویدادهای همگانیِ سرور) ──────────────────
    from world_pulse import world_pulse_loop
    _spawn_task(world_pulse_loop(bot))

    # ─── تحت‌تعقیبِ خودکارِ روزانه (۳ نفر/روز) + رشدِ بدهیِ بانک ─────
    from daily_wanted import daily_wanted_loop
    _spawn_task(daily_wanted_loop(bot))

    log_sync("🟢 **ربات استارت شد!**", "START")
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "🟢 **Reloading the bot...**\nربات با موفقیت ری‌استارت شد و آماده به کاره!")
        except Exception:
            pass

    # ─── اطلاع‌رسانیِ ری‌استارت به همه‌ی بازیکن‌ها ──────────────────
    # بعد از هر روشن‌شدنِ ربات (دیپلوی، کرش، ری‌استارتِ دستی و ...)،
    # چیزهایی مثل last_seen و stateهای حافظه‌ای پاک می‌شن؛ برای اینکه
    # بازیکنا گیر نکنن، بهشون می‌گیم یه بار /start بزنن. تو یه تسکِ جدا
    # اجرا می‌شه تا استارت‌شدنِ خودِ polling معطل نمونه.
    _spawn_task(notify_players_restart(bot))

    # ─── حلقه‌ی polling با retry دستی ──────────────────────────────
    # 🆕 باگ‌فیکس: موقعِ دیپلویِ جدید (نه ری‌استارتِ ساده)، ریلوی یه
    # کانتینرِ تازه بالا می‌آره درحالی‌که کانتینرِ قبلی هنوز کاملاً
    # خاموش نشده — چند ثانیه هر دو پروسه هم‌زمان سعیِ getUpdates دارن و
    # تلگرام با «Conflict: terminated by other getUpdates request» رد
    # می‌کنه. قبلاً این خطا از start_polling بیرون می‌زد، کلِ main() کرش
    # می‌کرد، event loop بسته می‌شد و هر تسکِ پس‌زمینه‌ی نیمه‌کاره (مثلِ
    # notify_players_restart وسطِ فرستادنِ پیام‌ها) بی‌سروصدا cancel
    # می‌شد — دقیقاً همون حالتی که «موقعِ دیپلوی نمی‌فرسته، موقعِ
    # ری‌استارتِ دستی می‌فرسته» رو توضیح می‌ده (چون ری‌استارتِ دستی این
    # هم‌پوشانیِ دو-پروسه‌ای رو نداره). حالا به‌جایِ کرش‌کردن، همین‌جا
    # لاگ می‌شه، چند ثانیه صبر می‌شه و دوباره تلاش می‌شه — بدونِ اینکه
    # event loop و تسک‌های پس‌زمینه‌ش بسته بشن.
    try:
        while True:
            try:
                await dp.start_polling(bot)
                break  # start_polling عادی فقط با Ctrl+C/سیگنالِ توقف برمی‌گرده
            except Exception as e:
                log_sync(f"🔴 **polling کرش کرد، ۵ ثانیه دیگه دوباره امتحان می‌شه**\n`{e}`", "ERROR")
                await asyncio.sleep(5)
    finally:
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, "🔴 **Shutting down...**\nربات در حال خاموش شدنه!")
            except Exception:
                pass
        log_sync("🔴 **ربات خاموش شد!**", "STOP")

if __name__ == "__main__":
    asyncio.run(main())
