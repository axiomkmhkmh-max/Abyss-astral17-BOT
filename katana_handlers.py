# ============================================================
#  ASTRAL ABYSS — Katana Soul Handlers (katana_handlers.py)
# ============================================================
# دستورات: /katana  /awaken  /bond  /katanas
# + دکمه‌ی «🗡️ کاتانا» که با کال‌بک kt_menu باز میشه (برای منوی اصلی
#   فقط کافیه دکمه‌ای با callback_data="kt_menu" بسازید، این فایل جوابش رو می‌ده)
# ============================================================

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
from characters import ALL_CHARACTERS
from katana_core import (
    get_katana_identity, get_katana_soul, calc_katana_bonus, display_katana_full,
    attempt_awaken, add_bond_xp, apply_death_penalty,
    TIER_CONFIG, AWAKENING_STAGE_NAMES, MATERIALS_INFO,
    awaken_cost, awaken_material_need, awaken_success_chance,
    bond_level_from_xp, get_bond_bonus, BOND_MAX_LEVEL, BOND_LEVEL_DESC,
    RARITY_TO_TIER,
)


# ─── کمکی‌های موجودی (سازگار با ساختار inventory فعلی شما: لیست دیکشنری‌ها) ───

def _inventory_as_counts(player: dict) -> dict:
    counts = {}
    for it in player.get("inventory", []):
        n = it.get("name", "")
        key = "protection_scroll" if n == "Protection Scroll" else n
        counts[key] = counts.get(key, 0) + 1
    return counts


def _remove_items(player: dict, name_variants: set, qty: int) -> int:
    inv = player.get("inventory", [])
    removed = 0
    new_inv = []
    for it in inv:
        n = it.get("name", "")
        key = "protection_scroll" if n == "Protection Scroll" else n
        if key in name_variants and removed < qty:
            removed += 1
            continue
        new_inv.append(it)
    player["inventory"] = new_inv
    return removed


def _ensure_katana_fields(player: dict):
    player.setdefault("katana_awakening", 0)
    player.setdefault("katana_bond", 0)
    player.setdefault("katana_bond_level", 1)
    player.setdefault("katana_kills", 0)
    player.setdefault("katana_deaths", 0)
    player.setdefault("katana_skills", {})


# ─── /katana ──────────────────────────────────────────────────

async def cmd_katana(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player or not player.get("character"):
        await msg.answer("⚠️ اول باید یه کاراکتر انتخاب کنی!")
        return
    _ensure_katana_fields(player)
    save_player(uid, player)

    text = display_katana_full(player)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌙 بیداری کاتانا", callback_data="kt_awaken_menu", style=ButtonStyle.PRIMARY),
         InlineKeyboardButton(text="🔗 پیوند روحی", callback_data="kt_bond", style=ButtonStyle.PRIMARY)],
    ])
    await msg.answer(text, reply_markup=kb, parse_mode="Markdown")


async def cb_kt_menu(cb: CallbackQuery):
    """اگه دکمه‌ی '🗡️ کاتانا' تو منوی اصلی به این callback وصل بشه."""
    uid = cb.from_user.id
    player = get_player(uid)
    if not player or not player.get("character"):
        await cb.answer("⚠️ اول باید یه کاراکتر انتخاب کنی!", show_alert=True)
        return
    _ensure_katana_fields(player)
    save_player(uid, player)
    text = display_katana_full(player)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌙 بیداری کاتانا", callback_data="kt_awaken_menu", style=ButtonStyle.PRIMARY),
         InlineKeyboardButton(text="🔗 پیوند روحی", callback_data="kt_bond", style=ButtonStyle.PRIMARY)],
    ])
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await cb.answer()


# ─── /bond ────────────────────────────────────────────────────

def _bond_text(player: dict) -> str:
    bond_xp = player.get("katana_bond", 0)
    bond_level = player.get("katana_bond_level", bond_level_from_xp(bond_xp))
    bonus = get_bond_bonus(bond_level)

    ident = get_katana_identity(player.get("character", ""))
    soul = get_katana_soul(player.get("character", ""))

    lines = [
        f"🔗 **پیوند روحی — {soul['katana_name']}**",
        f"سطح: **{bond_level}/{BOND_MAX_LEVEL}**  ({bond_xp} XP از تعداد کشته‌ها)",
        f"_{BOND_LEVEL_DESC.get(bond_level, '')}_",
        "",
        "📜 نردبان پیوند:",
    ]
    for lvl in sorted(BOND_LEVEL_DESC.keys()):
        mark = "✅" if bond_level >= lvl else "⬜"
        lines.append(f"{mark} سطح {lvl}: {BOND_LEVEL_DESC[lvl]}")

    lines.append("")
    lines.append("🎁 بونوس‌های فعال الان:")
    active = []
    if bonus["lifesteal"]: active.append(f"+{int(bonus['lifesteal']*100)}٪ لایف‌استیل")
    if bonus["crit"]: active.append(f"+{int(bonus['crit']*100)}٪ کریت")
    if bonus["dmg_mult"]: active.append(f"+{int(bonus['dmg_mult']*100)}٪ آسیب کلی")
    if bonus["awaken_echo"]: active.append("پژواک بیداری (شانس فعال‌سازی زودهنگام اثر ویژه‌ی تایر)")
    if bonus["soulbound"]: active.append("🔗 پیوند ابدی (کاتانا از مرگ آسیب نمی‌بینه)")
    lines.append("، ".join(active) if active else "هنوز هیچ بونوسی باز نشده — بیشتر بجنگ!")

    if bond_level < BOND_MAX_LEVEL:
        need = (bond_level) * 50 - bond_xp
        lines.append("")
        lines.append(f"⏳ تا سطح بعد: {max(0, need)} کشته‌ی دیگه")

    return "\n".join(lines)


async def cmd_bond(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player or not player.get("character"):
        await msg.answer("⚠️ اول باید یه کاراکتر انتخاب کنی!")
        return
    _ensure_katana_fields(player)
    await msg.answer(_bond_text(player), parse_mode="Markdown")


async def cb_kt_bond(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    if not player:
        await cb.answer("خطا!", show_alert=True)
        return
    _ensure_katana_fields(player)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗡️ برگشت به کاتانا", callback_data="kt_menu", style=ButtonStyle.PRIMARY)]
    ])
    await cb.message.edit_text(_bond_text(player), reply_markup=kb, parse_mode="Markdown")
    await cb.answer()


# ─── /awaken ──────────────────────────────────────────────────

def _awaken_preview_text(player: dict) -> tuple[str, int, int]:
    """برمی‌گردونه: (متن, target_stage یا -1 اگه ماکس شده, chance*100)"""
    char_name = player.get("character", "")
    ident = get_katana_identity(char_name)
    soul = get_katana_soul(char_name)
    tier = ident["tier"]
    cfg = TIER_CONFIG[tier]
    stage = player.get("katana_awakening", 0)

    if stage >= cfg["max_awaken"]:
        text = (f"🏆 کاتانای **{soul['katana_name']}** ({cfg['name_fa']}) به اوج بیداریش رسیده "
                f"— مرحله‌ی {AWAKENING_STAGE_NAMES[stage]}!\nچیزی بالاتر از این براش نیست.")
        return text, -1, 0

    target = stage + 1
    from economy import bz_to_display
    cost = awaken_cost(tier, target)
    mat, qty = awaken_material_need(tier, target)
    chance = awaken_success_chance(tier, target)
    info = MATERIALS_INFO[mat]

    counts = _inventory_as_counts(player)
    have_mat = counts.get(mat, 0)
    have_gold = player.get("zen", 0)

    text = (
        f"🌙 **بیداری کاتانا — {soul['katana_name']}**\n"
        f"مرحله‌ی فعلی: {AWAKENING_STAGE_NAMES[stage]} → هدف: **{AWAKENING_STAGE_NAMES[target]}**\n\n"
        f"💰 هزینه: {bz_to_display(cost)}  (موجودی تو: {bz_to_display(have_gold)})\n"
        f"📦 نیاز: {qty}x {info['emoji']} {info['name_fa']}  (موجودی تو: {have_mat})\n"
        f"🎲 شانس موفقیت: **{int(chance*100)}٪**\n\n"
        f"🛡️ اگه طومار محافظت داشته باشی و ازش استفاده کنی، شکست باعث پس‌رفتِ سطح نمی‌شه.\n"
        f"در غیر این‌صورت، شکست یعنی یک مرحله پس‌رفت (اگه بیشتر از خفته باشه)."
    )
    return text, target, int(chance * 100)


async def cmd_awaken(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player or not player.get("character"):
        await msg.answer("⚠️ اول باید یه کاراکتر انتخاب کنی!")
        return
    _ensure_katana_fields(player)
    text, target, _ = _awaken_preview_text(player)
    if target == -1:
        await msg.answer(text, parse_mode="Markdown")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ تلاش (بدون طومار)", callback_data="kt_awk_go:0", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🛡️ تلاش با طومار محافظت", callback_data="kt_awk_go:1", style=ButtonStyle.PRIMARY)],
    ])
    await msg.answer(text, reply_markup=kb, parse_mode="Markdown")


async def cb_kt_awaken_menu(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    if not player:
        await cb.answer("خطا!", show_alert=True)
        return
    _ensure_katana_fields(player)
    text, target, _ = _awaken_preview_text(player)
    if target == -1:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗡️ برگشت به کاتانا", callback_data="kt_menu", style=ButtonStyle.PRIMARY)]
        ])
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await cb.answer()
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ تلاش (بدون طومار)", callback_data="kt_awk_go:0", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🛡️ تلاش با طومار محافظت", callback_data="kt_awk_go:1", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🗡️ برگشت", callback_data="kt_menu", style=ButtonStyle.PRIMARY)],
    ])
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await cb.answer()


async def cb_kt_awaken_go(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    if not player or not player.get("character"):
        await cb.answer("خطا!", show_alert=True)
        return
    _ensure_katana_fields(player)

    use_protection = cb.data.endswith(":1")
    char_name = player.get("character", "")
    stage = player.get("katana_awakening", 0)
    counts = _inventory_as_counts(player)
    gold = player.get("zen", 0)

    result = attempt_awaken(char_name, stage, counts, gold, use_protection=use_protection)

    # کم کردن واقعی طلا/مواد فقط اگه واقعاً تلاش انجام شده باشه (نه رد شده بابت کمبود منابع)
    attempted = not any(k in result["message"] for k in ["کافی نداری", "نداری!", "اوج بیداری"])
    if attempted:
        player["zen"] = player.get("zen", 0) - result["gold_spent"]
        if result["material"] and result["material_spent"]:
            _remove_items(player, {result["material"]}, result["material_spent"])
        if result["protection_used"]:
            _remove_items(player, {"protection_scroll"}, 1)
        player["katana_awakening"] = result["new_stage"]
        from katana_core import sync_soul_capacity
        sync_soul_capacity(player)  # 🆕 ظرفیت روح با هر تغییرِ مرحله‌ی بیداری آپدیت می‌شه

    save_player(uid, player)

    if attempted and result["success"]:
        from katana_core import katana_awaken_flavor
        flavor = katana_awaken_flavor(char_name, result["new_stage"])
        result["message"] += f"\n\n{flavor}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗡️ برگشت به کاتانا", callback_data="kt_menu", style=ButtonStyle.PRIMARY)]
    ])
    await cb.message.edit_text(result["message"], reply_markup=kb, parse_mode="Markdown")
    await cb.answer("✅" if result["success"] else "💥")


# ─── /katanas — راهنمای کامل رتبه‌بندی کاتاناها ─────────────────

def _katanas_overview_text() -> str:
    by_tier = {"mythic": [], "legendary": [], "rare": [], "common": []}
    for name, data in ALL_CHARACTERS.items():
        tier = RARITY_TO_TIER.get(data.get("rarity", "common"), "common")
        by_tier[tier].append((name, data.get("katana", "?"), data.get("element", "")))

    lines = ["🗡️ **راهنمای رتبه‌بندی کاتاناها**\n"]
    for tier in ["mythic", "legendary", "rare", "common"]:
        cfg = TIER_CONFIG[tier]
        items = by_tier[tier]
        lines.append(f"\n{cfg['emoji']} **{cfg['name_fa'].upper()} ({tier})** — {len(items)} کاتانا")
        lines.append(f"   سقف بیداری: {cfg['max_awaken']} | بونوس آسیب تا ×{cfg['dmg_max']}")
        if cfg["special"]:
            eff = "ضربه‌ی دوبل ۱۵٪ (Legendary)" if cfg["special"] == "double_strike" else "جذب ۱۰٪ HP دشمن با هر کشتن (Mythic)"
            lines.append(f"   اثر ویژه: {eff}")
        if tier in ("mythic", "legendary"):
            for char_name, katana_name, elem in items:
                lines.append(f"   • {katana_name} ({char_name}) — {elem}")
        else:
            lines.append(f"   برای دیدن اسم دقیق کاتانای خودت: /katana")

    lines.append("\n💡 رتبه‌ی کاتانای تو بر اساس رارتیتی کاراکترت تعیین می‌شه:")
    lines.append("   special→MYTHIC 👑 | legendary→LEGENDARY 🌟 | rare→RARE 💠 | common→COMMON ⚔️")
    return "\n".join(lines)


async def cmd_katanas(msg: Message):
    await msg.answer(_katanas_overview_text(), parse_mode="Markdown")


# ─── ثبت هندلرها ──────────────────────────────────────────────

def register_katana_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_katana, Command("katana"))
    dp.message.register(cmd_awaken, Command("awaken"))
    dp.message.register(cmd_bond, Command("bond"))
    dp.message.register(cmd_katanas, Command("katanas"))

    dp.callback_query.register(cb_kt_menu, F.data == "kt_menu")
    dp.callback_query.register(cb_kt_bond, F.data == "kt_bond")
    dp.callback_query.register(cb_kt_awaken_menu, F.data == "kt_awaken_menu")
    dp.callback_query.register(cb_kt_awaken_go, F.data.startswith("kt_awk_go:"))
