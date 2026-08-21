# ============================================================
#  ASTRAL ABYSS RPG — Handlers همراه (Pet / Companion) 🐾
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
import pet_system as ps


# تلگرام روی حجمِ کلِ reply_markup محدودیت داره؛ اگه بازیکن پتِ زیاد جمع کرده
# باشه (مثلاً از شکستنِ تخمِ روزانه در طولِ زمان)، یه دکمه به‌ازای هر پت باعثِ
# خطای "reply markup is too long" می‌شه. برای همین لیست‌ها صفحه‌بندی شدن.
PET_PAGE_SIZE = 8


def _pet_menu_kb(player: dict, page: int = 0) -> InlineKeyboardMarkup:
    pets = player.get("pets", [])
    active_id = player.get("active_pet_id")
    total_pages = max(1, (len(pets) + PET_PAGE_SIZE - 1) // PET_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * PET_PAGE_SIZE
    page_pets = pets[start:start + PET_PAGE_SIZE]

    rows = []
    for p in page_pets:
        mark = "✅ " if p["pet_id"] == active_id else ""
        rows.append([
            InlineKeyboardButton(text=f"{mark}{p['emoji']} {p['name']} (Lv.{p['level']})", callback_data=f"pet_view:{p['pet_id']}"),
        ])

    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"pet_menu_page:{page-1}"))
        nav.append(InlineKeyboardButton(text=f"صفحه‌ی {page+1}/{total_pages}", callback_data="pet_noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"pet_menu_page:{page+1}"))
        rows.append(nav)

    rows.append([InlineKeyboardButton(text=f"🥚 خریدِ تخم ({ps.EGG_PRICE:,} Zen) — {ps.daily_eggs_remaining(player)}/{ps.DAILY_EGG_MAX} امروز", callback_data="pet_hatch", style=ButtonStyle.SUCCESS)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _pet_view_kb(player: dict, pet: dict) -> InlineKeyboardMarkup:
    is_active = player.get("active_pet_id") == pet["pet_id"]
    has_other_pets = len(player.get("pets", [])) > 1
    rows = [
        [InlineKeyboardButton(text=f"🍖 غذا دادن ({ps.FEED_COST:,} Zen)", callback_data=f"pet_feed:{pet['pet_id']}")],
        [InlineKeyboardButton(text="🎾 بازی کردن (رایگان)", callback_data=f"pet_play:{pet['pet_id']}")],
        [InlineKeyboardButton(text="✏️ تغییرِ اسم", callback_data=f"pet_rename:{pet['pet_id']}")],
    ]
    if not is_active:
        rows.append([InlineKeyboardButton(text="✅ فعال‌سازی", callback_data=f"pet_activate:{pet['pet_id']}", style=ButtonStyle.SUCCESS)])
    if has_other_pets:
        rows.append([InlineKeyboardButton(text="🔀 ادغامِ یه همراهِ دیگه تو این یکی", callback_data=f"pet_fuse_pick:{pet['pet_id']}")])
    rows.append([InlineKeyboardButton(text=f"💰 فروش ({ps.sell_price(pet):,} Zen)", callback_data=f"pet_sell_ask:{pet['pet_id']}", style=ButtonStyle.DANGER)])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="pet_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _fuse_pick_kb(player: dict, target_id: str, page: int = 0) -> InlineKeyboardMarkup:
    fodder_candidates = [p for p in player.get("pets", []) if p["pet_id"] != target_id]
    total_pages = max(1, (len(fodder_candidates) + PET_PAGE_SIZE - 1) // PET_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * PET_PAGE_SIZE
    page_pets = fodder_candidates[start:start + PET_PAGE_SIZE]

    rows = []
    for p in page_pets:
        rows.append([InlineKeyboardButton(
            text=f"{p['emoji']} {p['name']} (Lv.{p['level']}, {ps.RARITY_LABEL.get(p['rarity'], '')})",
            callback_data=f"pet_fuse_do:{target_id}:{p['pet_id']}",
        )])

    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"pet_fuse_page:{target_id}:{page-1}"))
        nav.append(InlineKeyboardButton(text=f"صفحه‌ی {page+1}/{total_pages}", callback_data="pet_noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"pet_fuse_page:{target_id}:{page+1}"))
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="🔙 لغو", callback_data=f"pet_view:{target_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cmd_pet(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    pets = player.get("pets", [])
    if not pets:
        await msg.answer(
            "🐾 **همراه‌ها**\n\n"
            "هنوز هیچ همراهی نداری. یه همراه، تو نبرد باهات لول می‌گیره و "
            "یه بونوسِ دائمیِ کوچیک بهت می‌ده (دمیج، کریت، لایف‌استیل، شانسِ طلا، XP یا دفاع).\n\n"
            f"🥚 یه تخم رو با {ps.EGG_PRICE:,} Zen باز کن و ببین چی نصیبت می‌شه!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=f"🥚 خریدِ تخم ({ps.EGG_PRICE:,} Zen)", callback_data="pet_hatch", style=ButtonStyle.SUCCESS)
            ]])
        )
        return
    active = ps.active_pet(player)
    text = f"🐾 **همراه‌های تو** ({len(pets)})\n\n"
    if active:
        text += f"فعال الان: {active['emoji']} {active['name']}\n\n"
    text += "روی یکی بزن تا جزئیاتشو ببینی."
    await msg.answer(text, reply_markup=_pet_menu_kb(player))


async def cb_pet_menu(cb: CallbackQuery):
    player = await aget_player(cb.from_user.id)
    if not player:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    pets = player.get("pets", [])
    active = ps.active_pet(player)
    text = f"🐾 **همراه‌های تو** ({len(pets)})\n\n"
    if active:
        text += f"فعال الان: {active['emoji']} {active['name']}\n\n"
    text += "روی یکی بزن تا جزئیاتشو ببینی."
    await cb.message.edit_text(text, reply_markup=_pet_menu_kb(player))
    await cb.answer()


async def cb_pet_menu_page(cb: CallbackQuery):
    player = await aget_player(cb.from_user.id)
    if not player:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    page = int(cb.data.split(":")[1])
    pets = player.get("pets", [])
    active = ps.active_pet(player)
    text = f"🐾 **همراه‌های تو** ({len(pets)})\n\n"
    if active:
        text += f"فعال الان: {active['emoji']} {active['name']}\n\n"
    text += "روی یکی بزن تا جزئیاتشو ببینی."
    await cb.message.edit_text(text, reply_markup=_pet_menu_kb(player, page))
    await cb.answer()


async def cb_pet_noop(cb: CallbackQuery):
    await cb.answer()


async def cb_pet_hatch(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    if ps.daily_eggs_remaining(player) <= 0:
        await cb.answer(f"❌ سقفِ روزانه‌ی شکوندنِ تخم ({ps.DAILY_EGG_MAX} تا) پر شده! فردا دوباره سر بزن.", show_alert=True)
        return
    if player.get("zen", 0) < ps.EGG_PRICE:
        await cb.answer(f"❌ {ps.EGG_PRICE:,} Zen لازم داری.", show_alert=True)
        return
    player["zen"] -= ps.EGG_PRICE
    ps.use_daily_egg(player)
    pet = ps.hatch_egg(player)
    new_titles = pet.pop("_new_titles", [])
    await asave_player(uid, player)
    rarity_label = ps.RARITY_LABEL.get(pet["rarity"], "")
    await cb.answer()
    title_txt = ""
    if new_titles:
        title_txt = "\n\n🏅 لقبِ جدید: " + "، ".join(new_titles)
    remaining = ps.daily_eggs_remaining(player)
    await cb.message.answer(
        f"🥚 تخم شکست...\n\n{pet['emoji']} **{pet['name']}** به دنیا اومد!\n{rarity_label}\n\n"
        + ps.format_pet_card(pet) + title_txt
        + f"\n\n📅 شانسِ باقی‌مونده‌ی امروز: {remaining}/{ps.DAILY_EGG_MAX}"
    )


async def cb_pet_view(cb: CallbackQuery):
    player = await aget_player(cb.from_user.id)
    if not player:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    pet_id = cb.data.split(":")[1]
    pet = next((p for p in player.get("pets", []) if p["pet_id"] == pet_id), None)
    if not pet:
        await cb.answer("❌ این همراه دیگه پیدا نشد.", show_alert=True)
        return
    await cb.message.edit_text(ps.format_pet_card(pet), reply_markup=_pet_view_kb(player, pet))
    await cb.answer()


async def cb_pet_activate(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    pet_id = cb.data.split(":")[1]
    if not ps.set_active_pet(player, pet_id):
        await cb.answer("❌ این همراه دیگه پیدا نشد.", show_alert=True)
        return
    await asave_player(uid, player)
    pet = ps.active_pet(player)
    await cb.answer(f"✅ {pet['name']} الان همراهِ فعالته!")
    await cb.message.edit_text(ps.format_pet_card(pet), reply_markup=_pet_view_kb(player, pet))


async def cb_pet_feed(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    pet_id = cb.data.split(":")[1]
    result = ps.feed_pet(player, pet_id)
    if result.get("error") == "not_enough_zen":
        await cb.answer(f"❌ {ps.FEED_COST:,} Zen لازم داری.", show_alert=True)
        return
    if result.get("error") == "max_bond":
        await cb.answer("❌ پیوندِ این همراه از قبل کامله.", show_alert=True)
        return
    if result.get("error") == "not_found":
        await cb.answer("❌ این همراه دیگه پیدا نشد.", show_alert=True)
        return
    await asave_player(uid, player)
    pet = next(p for p in player["pets"] if p["pet_id"] == pet_id)
    await cb.answer(f"🍖 پیوند رفت رو {result['bond']}/{ps.MAX_BOND}!")
    if result.get("new_title"):
        await cb.message.answer(f"🏅 لقبِ جدید باز شد: {result['new_title']}")
    await cb.message.edit_text(ps.format_pet_card(pet), reply_markup=_pet_view_kb(player, pet))


async def cb_pet_play(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    pet_id = cb.data.split(":")[1]
    result = ps.play_with_pet(player, pet_id)
    if result.get("error") == "cooldown":
        hrs = result["remain"] // 3600
        mins = (result["remain"] % 3600) // 60
        await cb.answer(f"⏰ باید {hrs} ساعت و {mins} دقیقه صبر کنی تا دوباره بشه باهاش بازی کرد.", show_alert=True)
        return
    if result.get("error") == "max_bond":
        await cb.answer("❌ پیوندِ این همراه از قبل کامله.", show_alert=True)
        return
    if result.get("error") == "not_found":
        await cb.answer("❌ این همراه دیگه پیدا نشد.", show_alert=True)
        return
    await asave_player(uid, player)
    pet = next(p for p in player["pets"] if p["pet_id"] == pet_id)
    await cb.answer(f"🎾 پیوند رفت رو {result['bond']}/{ps.MAX_BOND}!")
    if result.get("new_title"):
        await cb.message.answer(f"🏅 لقبِ جدید باز شد: {result['new_title']}")
    await cb.message.edit_text(ps.format_pet_card(pet), reply_markup=_pet_view_kb(player, pet))


async def cb_pet_sell_ask(cb: CallbackQuery):
    player = await aget_player(cb.from_user.id)
    if not player:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    pet_id = cb.data.split(":")[1]
    pet = next((p for p in player.get("pets", []) if p["pet_id"] == pet_id), None)
    if not pet:
        await cb.answer("❌ این همراه دیگه پیدا نشد.", show_alert=True)
        return
    price = ps.sell_price(pet)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ آره، بفروش ({price:,} Zen)", callback_data=f"pet_sell_do:{pet_id}", style=ButtonStyle.DANGER)],
        [InlineKeyboardButton(text="🔙 نه، بی‌خیال", callback_data=f"pet_view:{pet_id}")],
    ])
    await cb.message.edit_text(
        f"⚠️ مطمئنی می‌خوای {pet['emoji']} **{pet['name']}** رو به {price:,} Zen بفروشی؟\n"
        "این کار برگشت‌ناپذیره.",
        reply_markup=kb,
    )
    await cb.answer()


async def cb_pet_sell_do(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    pet_id = cb.data.split(":")[1]
    result = ps.sell_pet(player, pet_id)
    if result.get("error") == "not_found":
        await cb.answer("❌ این همراه دیگه پیدا نشد.", show_alert=True)
        return
    await asave_player(uid, player)
    await cb.answer(f"💰 {result['name']} فروخته شد، {result['gold']:,} Zen گرفتی!", show_alert=True)
    await cb.message.edit_text(
        f"💰 {result['emoji']} **{result['name']}** فروخته شد و {result['gold']:,} Zen بهت اضافه شد.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 بازگشت به همراه‌ها", callback_data="pet_menu")
        ]]),
    )


async def cb_pet_fuse_pick(cb: CallbackQuery):
    player = await aget_player(cb.from_user.id)
    if not player:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    target_id = cb.data.split(":")[1]
    target = next((p for p in player.get("pets", []) if p["pet_id"] == target_id), None)
    if not target:
        await cb.answer("❌ این همراه دیگه پیدا نشد.", show_alert=True)
        return
    if len(player.get("pets", [])) < 2:
        await cb.answer("❌ برای ادغام حداقل به ۲ تا همراه نیاز داری.", show_alert=True)
        return
    await cb.message.edit_text(
        f"🔀 کدوم همراه رو به عنوانِ خوراک بدیم به {target['emoji']} **{target['name']}**؟\n"
        "همراهِ خوراک برای همیشه مصرف می‌شه و به جاش این یکی XP می‌گیره (اگه هم‌گونه باشن، بونوس هم می‌گیره).",
        reply_markup=_fuse_pick_kb(player, target_id),
    )
    await cb.answer()


async def cb_pet_fuse_page(cb: CallbackQuery):
    player = await aget_player(cb.from_user.id)
    if not player:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    _, target_id, page_str = cb.data.split(":")
    target = next((p for p in player.get("pets", []) if p["pet_id"] == target_id), None)
    if not target:
        await cb.answer("❌ این همراه دیگه پیدا نشد.", show_alert=True)
        return
    await cb.message.edit_text(
        f"🔀 کدوم همراه رو به عنوانِ خوراک بدیم به {target['emoji']} **{target['name']}**؟\n"
        "همراهِ خوراک برای همیشه مصرف می‌شه و به جاش این یکی XP می‌گیره (اگه هم‌گونه باشن، بونوس هم می‌گیره).",
        reply_markup=_fuse_pick_kb(player, target_id, int(page_str)),
    )
    await cb.answer()


async def cb_pet_fuse_do(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    _, target_id, fodder_id = cb.data.split(":")
    result = ps.fuse_pet(player, target_id, fodder_id)
    if result.get("error") == "not_found":
        await cb.answer("❌ یکی از همراه‌ها دیگه پیدا نشد.", show_alert=True)
        return
    if result.get("error") == "same_pet":
        await cb.answer("❌ نمی‌تونی یه همراه رو خوراکِ خودش کنی.", show_alert=True)
        return
    if result.get("error") == "target_max_level":
        await cb.answer("❌ این همراه از قبل سطحش ماکسه.", show_alert=True)
        return
    await asave_player(uid, player)
    pet = next(p for p in player["pets"] if p["pet_id"] == target_id)
    bonus_txt = " (بونوسِ هم‌گونه!)" if result.get("same_species") else ""
    await cb.answer(f"🔀 {result['fodder_name']} ادغام شد! +{result['xp_gain']:,} XP{bonus_txt}", show_alert=True)
    extra = ""
    if result.get("levels_gained"):
        extra += f"\n\n📈 {result['levels_gained']} لول رفت بالا! (الان لول {result['new_level']})"
    if result.get("evolved"):
        extra += f"\n🌟 تکامل پیدا کرد: {result['evolution_label']}"
    await cb.message.edit_text(
        f"🔀 **{result['fodder_name']}** ادغام شد تو {pet['emoji']} **{pet['name']}**!\n"
        f"+{result['xp_gain']:,} XP{bonus_txt}{extra}\n\n" + ps.format_pet_card(pet),
        reply_markup=_pet_view_kb(player, pet),
    )


_awaiting_rename: dict[int, tuple[str, float]] = {}   # uid -> (pet_id, expires_at)


async def cb_pet_rename(cb: CallbackQuery):
    uid = cb.from_user.id
    pet_id = cb.data.split(":")[1]
    _awaiting_rename[uid] = (pet_id, __import__("time").time() + 120)
    await cb.answer()
    await cb.message.answer("✏️ اسمِ جدیدِ همراهت رو بفرست (حداکثر ۲۴ کاراکتر):")


async def handle_pet_rename_text(msg: Message):
    uid = msg.from_user.id
    state = _awaiting_rename.get(uid)
    if not state:
        return
    pet_id, expires_at = state
    import time as _t
    del _awaiting_rename[uid]
    if _t.time() > expires_at:
        await msg.answer("⏰ وقتِ تغییرِ اسم تموم شد، دوباره امتحان کن.")
        return
    player = await aget_player(uid)
    if not player or not ps.rename_pet(player, pet_id, msg.text or ""):
        await msg.answer("❌ اسم نامعتبر بود یا این همراه دیگه پیدا نشد.")
        return
    await asave_player(uid, player)
    pet = next(p for p in player["pets"] if p["pet_id"] == pet_id)
    await msg.answer(f"✅ اسمش شد: {pet['emoji']} **{pet['name']}**", reply_markup=_pet_view_kb(player, pet))


def _handle_pet_rename_filter(m: Message) -> bool:
    return m.from_user.id in _awaiting_rename


def register_pet_handlers(dp, bot):
    dp.message.register(cmd_pet, Command("pet"))
    dp.callback_query.register(cb_pet_menu, F.data == "pet_menu")
    dp.callback_query.register(cb_pet_menu_page, F.data.startswith("pet_menu_page:"))
    dp.callback_query.register(cb_pet_noop, F.data == "pet_noop")
    dp.callback_query.register(cb_pet_hatch, F.data == "pet_hatch")
    dp.callback_query.register(cb_pet_view, F.data.startswith("pet_view:"))
    dp.callback_query.register(cb_pet_activate, F.data.startswith("pet_activate:"))
    dp.callback_query.register(cb_pet_feed, F.data.startswith("pet_feed:"))
    dp.callback_query.register(cb_pet_play, F.data.startswith("pet_play:"))
    dp.callback_query.register(cb_pet_rename, F.data.startswith("pet_rename:"))
    dp.callback_query.register(cb_pet_sell_ask, F.data.startswith("pet_sell_ask:"))
    dp.callback_query.register(cb_pet_sell_do, F.data.startswith("pet_sell_do:"))
    dp.callback_query.register(cb_pet_fuse_page, F.data.startswith("pet_fuse_page:"))
    dp.callback_query.register(cb_pet_fuse_pick, F.data.startswith("pet_fuse_pick:"))
    dp.callback_query.register(cb_pet_fuse_do, F.data.startswith("pet_fuse_do:"))
    dp.message.register(handle_pet_rename_text, _handle_pet_rename_filter)
