# ============================================================
#  ASTRAL ABYSS — Gap Core Handlers (فاز اول پورت)
# ------------------------------------------------------------
#  این فایل نسخه‌ی «هسته‌ی گپ»ِ چیزیه که تو bot.py برای تلگرام
#  هست: /start، گرفتنِ کاراکترِ تصادفی، انتخابِ جنسیت، پنلِ اصلی،
#  و پروفایل. منطقِ خالص (database, characters, character_lore,
#  onboarding.start_tutorial/is_in_tutorial, profile_card) عیناً
#  از پروژه‌ی موجود import می‌شه — فقط کیبورد/پیام‌رسانی برای گپ
#  بازنویسی شده (چون onboarding.tutorial_kb() و بقیه‌ی کیبوردهای
#  bot.py مستقیماً کلاس‌های aiogram رو با آرگومان‌های اختصاصیِ آن
#  فورک (مثل style=) می‌سازن که برای گپ معنی نداره).
#
#  سیستم‌های باقی‌مونده (combat, shop, casino, guild, bank, ...)
#  با همین الگو پورت می‌شن — نگاه کن به ROADMAP.md
# ============================================================
from __future__ import annotations

import os
import random
import tempfile

from gap_dispatcher import GapDispatcher
from gap_types import (
    CallbackQuery, InlineKeyboardBuilder, InlineKeyboardButton,
    InlineKeyboardMarkup, Message,
)

from database import get_player, save_player, create_player, assign_random_char, asave_player, aget_player
from characters import ALL_CHARACTERS
from game_data import RARITY_COLOR
from logger import log_sync
from account_link import generate_link_code, redeem_link_code, link_status_text

SPAWN_MAPS = [
    "Verdant Vale", "Frostheim", "Sands of Eternity",
    "Azure Tides Empire", "Ruins of Orion-7", "Clockwork Depths",
    "Holy Luminarchy", "The Sunken City", "Stormward Archipelago",
]

RARITY_EMOJI = {
    "common": "⚔️", "rare": "🔷", "epic": "🟣",
    "legendary": "🟡", "special": "🌟",
}


def char_card(char_name: str) -> str:
    c = ALL_CHARACTERS.get(char_name, {})
    rarity = RARITY_COLOR.get(c.get("rarity", "common"), "⚔️")
    emoji = RARITY_EMOJI.get(c.get("rarity", "common"), "⚔️")
    powers = "\n".join(f"  • {p}" for p in c.get("powers", []))
    return (
        f"{emoji} **{char_name}**\n"
        f"🏷 ندرت: {rarity}\n"
        f"🌀 عنصر: {c.get('element','—')}\n"
        f"🗡 کاتانا: *{c.get('katana','—')}*\n"
        f"⚡ قدرت پایه: {c.get('base_dmg',0)}\n"
        f"✨ ابیلیتی‌ها:\n{powers}"
    )


def main_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="👤 پروفایل", callback_data="menu:profile")
    b.button(text="🎴 کاراکتر", callback_data="menu:character")
    b.row(InlineKeyboardButton(text="⚔️ حمله (به‌زودی روی گپ)", callback_data="menu:soon"))
    b.row(InlineKeyboardButton(text="🛠️ کارگاه", callback_data="wsp:home"))
    b.row(InlineKeyboardButton(text="🔗 اتصال حساب", callback_data="menu:link"))
    b.adjust(2, 1, 1, 1)
    return b.as_markup()


def gender_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🙋‍♂️ پسر", callback_data="set_gender:male"),
        InlineKeyboardButton(text="🙋‍♀️ دختر", callback_data="set_gender:female"),
    ]])


def char_pick_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🎲 دریافت کاراکتر تصادفی", callback_data="pick_random_char"),
    ]])


WELCOME_TEXT = (
    "🌑 *به Astral Abyss خوش اومدی...*\n\n"
    "یه زمانی، جهان یکپارچه بود. تو و دوقلوت، **کیارَش**، داشتید سفر می‌کردید — "
    "تا اینکه **Abyss** ظهور کرد و واقعیت رو به ۱۴ قلمروی جدا از هم شکافت.\n\n"
    "حالا، بیا کاراکترت رو بسازیم."
)


def register_gap_core_handlers(dp: GapDispatcher):

    # ─── 🐛 فیکس: /characters اصلاً تو سمتِ گپ ثبت نشده بود ───────────
    # تو bot.py (تلگرام) این کامند وجود داره ولی موقعِ پورت‌کردنِ
    # gap_core_handlers.py جا افتاده بود؛ برای همینه که تو گپ همیشه
    # شکست می‌خورد (چه با @یوزرنیم چه بدون اون).
    @dp.message(commands=["characters"])
    async def cmd_characters(msg: Message):
        lines = ["📖 **لیست کاراکترهای ASTRAL ABYSS:**\n"]
        for name, d in ALL_CHARACTERS.items():
            e = RARITY_EMOJI.get(d.get("rarity", "common"), "⚔️")
            lines.append(f"{e} **{name}** — {d.get('element', '—')}")
        await msg.answer("\n".join(lines))

    @dp.message(commands=["start"])
    async def cmd_start(msg: Message):
        uid = msg.from_user.id
        player = await aget_player(uid)

        if not player:
            player = create_player(uid, msg.from_user.username or "", msg.from_user.first_name or "بازیکن")
            log_sync(f"👤 **NEW PLAYER (GAP)**\n🆔 `{uid}` | {msg.from_user.first_name}", "PLAYER")
            await msg.answer(WELCOME_TEXT, reply_markup=char_pick_kb())
            return

        if not player.get("character"):
            await msg.answer("🎲 هنوز کاراکترت رو نگرفتی! دکمه‌ی زیر رو بزن:", reply_markup=char_pick_kb())
            return

        await msg.answer(f"🌑 بازگشتی، {player['name']}...\nآبیس منتظرت بود.", reply_markup=main_menu_kb())

    @dp.callback_query(data="pick_random_char")
    async def cb_pick_random_char(query: CallbackQuery):
        uid = query.from_user.id
        player = await aget_player(uid)
        if not player:
            await query.answer("❌ اول /start بزن!", show_alert=True)
            return
        if player.get("character"):
            await query.answer("✅ قبلاً کاراکترت رو گرفتی!", show_alert=True)
            return

        char = assign_random_char()
        spawn = random.choice(SPAWN_MAPS)
        player["character"] = char
        player["map"] = spawn
        player["_awaiting_gender"] = True
        try:
            from character_lore import mark_character_seen
            mark_character_seen(player, char)
        except Exception:
            pass
        await asave_player(uid, player)

        log_sync(f"👤 **NEW PLAYER (GAP)**\n🆔 `{uid}`\n🎴 کاراکتر: {char}\n📍 مپ: {spawn}", "PLAYER")

        await query.message.edit_text(
            f"🎴 کاراکتر تو:\n\n{char_card(char)}\n\nیه قدم مونده — جنسیتِ کاراکترت رو انتخاب کن:",
            reply_markup=gender_kb(),
        )
        await query.answer()

    @dp.callback_query(data_startswith="set_gender:")
    async def cb_set_gender(query: CallbackQuery):
        uid = query.from_user.id
        player = await aget_player(uid)
        if not player or not player.get("character"):
            await query.answer("❌ اول کاراکترت رو بگیر!", show_alert=True)
            return
        if player.get("_awaiting_gender") is not True:
            await query.answer("✅ قبلاً ثبت شده!", show_alert=True)
            return

        gender = query.data.split(":", 1)[1]
        player["gender"] = gender
        player["gender_chosen"] = True
        player.pop("_awaiting_gender", None)

        try:
            import onboarding
            onboarding.start_tutorial(player)
        except Exception:
            pass
        await asave_player(uid, player)

        await query.message.edit_text(
            f"🌑 حالا وارد Abyss شدی، {player['name']}!\n\n"
            f"💰 Zen: {player.get('zen',0)} | ❤️ HP: {player.get('hp',100)}/{player.get('max_hp',100)}",
            reply_markup=main_menu_kb(),
        )
        await query.answer("✅ ثبت شد!")

    @dp.callback_query(data="menu:character")
    async def cb_menu_character(query: CallbackQuery):
        uid = query.from_user.id
        player = await aget_player(uid)
        if not player or not player.get("character"):
            await query.answer("❌ کاراکتر نداری!", show_alert=True)
            return
        await query.message.edit_text(char_card(player["character"]), reply_markup=main_menu_kb())
        await query.answer()

    @dp.callback_query(data="menu:profile")
    async def cb_menu_profile(query: CallbackQuery):
        uid = query.from_user.id
        chat_id = query.message.chat.id
        player = await aget_player(uid)
        if not player or not player.get("character"):
            await query.answer("❌ کاراکتر نداری!", show_alert=True)
            return
        try:
            from profile_card import generate_profile_card
            char_data = ALL_CHARACTERS.get(player["character"], {})
            out_path = os.path.join(tempfile.gettempdir(), f"gap_profile_{uid}.png")
            generate_profile_card(player, char_data, out_path)
            uploaded = await query.bot.client.upload_file(chat_id, "image", out_path)
            await query.bot.client.send_media(
                chat_id, "image", uploaded,
                inline_keyboard=main_menu_kb().to_gap(),
            )
            await query.answer()
        except Exception as e:
            await query.answer(f"⚠️ خطا در ساخت پروفایل: {e}", show_alert=True)

    @dp.callback_query(data="menu:soon")
    async def cb_menu_soon(query: CallbackQuery):
        await query.answer("⏳ این سیستم داره برای گپ پورت می‌شه — به‌زودی!", show_alert=True)

    @dp.callback_query(data="menu:link")
    async def cb_menu_link(query: CallbackQuery):
        uid = query.from_user.id
        if not await aget_player(uid):
            await query.answer("❌ اول /start بزن!", show_alert=True)
            return
        await query.message.answer(
            link_status_text(uid) + "\n\n(برای گرفتنِ کد بزن: /link)"
        )
        await query.answer()

    # ─── اتصالِ حساب (تلگرام ⇄ گپ) ──────────────────────────────
    # /link          → کد می‌سازه (این حساب گپ = اصلی)
    # /link CODE     → کدِ ساخته‌شده تو تلگرام رو وارد می‌کنه (وصل می‌شه)
    @dp.message(commands=["link"])
    async def cmd_link(msg: Message):
        uid = msg.from_user.id
        if not await aget_player(uid):
            await msg.answer("❗️ اول باید /start بزنی.")
            return

        parts = (msg.text or "").split(maxsplit=1)
        if len(parts) < 2:
            ok, result = generate_link_code(uid)
            if not ok:
                await msg.answer(result)
                return
            await msg.answer(
                f"🔗 کدِ اتصالِ حساب: {result}\n\n"
                f"این کد ۱۰ دقیقه معتبره. برو تو تلگرام و بزن:\n/link {result}"
            )
            return

        code = parts[1].strip()
        ok, result = await redeem_link_code(code, uid)
        await msg.answer(result)

    @dp.on_join
    async def on_user_join(user):
        uid = user.id
        if not await aget_player(uid):
            create_player(uid, user.username or "", user.first_name or "بازیکن")
            log_sync(f"👤 **JOIN (GAP)**\n🆔 `{uid}` | {user.first_name}", "PLAYER")
