# ============================================================
#  ASTRAL ABYSS — INLINE MODE (رشدِ ویروسی)
# ------------------------------------------------------------
#  با تایپِ  @AbyssAstralbot  تویِ ANY چت (حتی چتی که ربات توش
#  عضو نیست)، کاربر می‌تونه:
#    • کارتِ کاراکترِ خودش رو شیر کنه
#    • یه چالشِ دوئل بفرسته
#    • خودِ ربات رو دعوت کنه
#  هر نتیجه یه دکمه‌ی شیشه‌ای «🎮 بازی کن» داره که با deep-link
#  کاربرِ کلیک‌کننده رو می‌بره به PV ربات (referral_system.py).
#
#  این فایل هیچ فایلِ دیگه‌ای رو تغییر نمی‌ده. برای فعال‌شدن فقط
#  باید تو bot.py:
#       from inline_handlers import register_inline_handlers
#       register_inline_handlers(dp, bot)
#  و مهم‌تر: تو @BotFather → Bot Settings → Inline Mode → Turn on
#  (وگرنه تلگرام اصلاً این نوع پیام رو برای ربات نمی‌فرسته).
# ============================================================
from aiogram import Bot, Dispatcher
from aiogram.types import (
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent,
    InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultsButton,
)

from database import get_player, aget_player
from characters import ALL_CHARACTERS
from combat_power import calculate_combat_power, get_cp_label
from referral_system import card_ref_link, duel_ref_link, BOT_LINK

CACHE_TIME = 5  # ثانیه — نتایج زود کهنه می‌شن چون CP/سطح مدام تغییر می‌کنه


def _play_kb(url: str, label: str = "🎮 بازی کن") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=label, url=url)]])


def _card_result(player: dict) -> InlineQueryResultArticle:
    char_name = player.get("character")
    char_data = ALL_CHARACTERS.get(char_name, {})
    cp = calculate_combat_power(player)
    cp_label = get_cp_label(cp)
    name = player.get("name", "یه بازیکن")

    text = (
        f"🃏 **کارتِ کاراکترِ {name}**\n\n"
        f"👤 {char_name}\n"
        f"📊 سطح {player.get('level', 1)} · 💪 {cp:,} CP ({cp_label})\n"
        f"⚔️ {player.get('pvp_wins', 0)} برد PvP · 👹 {player.get('kills', 0)} کیل\n\n"
        f"از Astral Abyss اومدم سراغت — بیا خودتم یه کاراکتر بگیر 👇"
    )
    link = card_ref_link(player["id"])
    return InlineQueryResultArticle(
        id=f"card_{player['id']}",
        title=f"🃏 کارتِ کاراکترِ من — {char_name} (سطح {player.get('level',1)})",
        description=f"{cp:,} CP · {player.get('pvp_wins',0)} برد PvP — بفرست تو این چت",
        input_message_content=InputTextMessageContent(message_text=text),
        reply_markup=_play_kb(link),
        thumbnail_url="https://em-content.zobj.net/source/telegram/386/dagger_1f5e1-fe0f.png",
    )


def _duel_result(player: dict) -> InlineQueryResultArticle:
    name = player.get("name", "یه بازیکن")
    text = (
        f"⚔️ **{name}** به دوئل دعوتت کرد!\n\n"
        f"سطح {player.get('level', 1)} · {player.get('pvp_wins', 0)} برد PvP\n\n"
        f"اگه تو Astral Abyss کاراکتر داری، رو این پیام ریپلای کن و `/gduel` بزن "
        f"(تو گروه). اگه هنوز نداری، اول بزن رو دکمه‌ی زیر 👇"
    )
    link = duel_ref_link(player["id"])
    return InlineQueryResultArticle(
        id=f"duel_{player['id']}",
        title="⚔️ فرستادنِ چالشِ دوئل",
        description="یه دعوت‌نامه‌ی دوئل بفرست تو این چت",
        input_message_content=InputTextMessageContent(message_text=text),
        reply_markup=_play_kb(link, "🎮 من می‌خوام بازی کنم"),
        thumbnail_url="https://em-content.zobj.net/source/telegram/386/crossed-swords_2694-fe0f.png",
    )


def _invite_result() -> InlineQueryResultArticle:
    text = (
        "🌑 **Astral Abyss** — یه RPG متنیِ حماسی تو تلگرام\n\n"
        "کاراکتر بساز، وارد گیلد شو، با باس‌های جهانی بجنگ، تو بازارِ سیاه معامله کن "
        "و رازِ Abyss رو کشف کن. بزن بریم 👇"
    )
    return InlineQueryResultArticle(
        id="invite_generic",
        title="🌑 دعوت به Astral Abyss",
        description="لینکِ دعوت به بازی رو بفرست تو این چت",
        input_message_content=InputTextMessageContent(message_text=text),
        reply_markup=_play_kb(BOT_LINK, "🌑 شروع ماجراجویی"),
        thumbnail_url="https://em-content.zobj.net/source/telegram/386/crescent-moon_1f319.png",
    )


async def handle_inline_query(iq: InlineQuery):
    uid = iq.from_user.id
    player = await aget_player(uid)

    results = []
    if player and player.get("character"):
        results.append(_card_result(player))
        results.append(_duel_result(player))
    results.append(_invite_result())

    button = None
    if not player or not player.get("character"):
        button = InlineQueryResultsButton(
            text="❗️ اول تو خصوصیِ ربات /start بزن",
            start_parameter="from_inline",
        )

    await iq.answer(results, cache_time=CACHE_TIME, is_personal=True, button=button)


def register_inline_handlers(dp: Dispatcher, bot: Bot):
    dp.inline_query.register(handle_inline_query)
