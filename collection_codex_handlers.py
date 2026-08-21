# ============================================================
#  ASTRAL ABYSS — Collection Codex Handlers (Telegram UI)
# ------------------------------------------------------------
#  دکمه‌ی «📯 کدکسِ کالکشن» تو منوی کارگاه. تحویلِ ستِ کاملِ متریالِ
#  یه نقشه به یه NPC، در ازاش Zen/XP یک‌جا — قابلِ تکرار با کول‌داونِ
#  هر نقشه (collection_codex.py).
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
from logger import log_sync
from game_data import xp_for_level, effective_max_level
import collection_codex as cdx

PAGE_SIZE = 6


def _owner_ok(cb: CallbackQuery, uid: int) -> bool:
    return cb.from_user.id == uid


def _level_up(player: dict) -> bool:
    """کپیِ همون الگویی که boss_handlers.py استفاده می‌کنه — برای این‌که
    این ماژول به bot.py وابسته نشه (جلوگیری از importِ حلقوی).
    🐛 باگ‌فیکس: سقفِ ثابتِ ۱۵۰ → effective_max_level(player)، و
    HP هر لول از ۱۰ به ۵ (هماهنگ با بقیه‌ی بازی)."""
    from skill_tree import grant_levelup_points, effective_max_hp
    leveled = False
    old_level = player["level"]
    while player["xp"] >= xp_for_level(player["level"]) and player["level"] < effective_max_level(player):
        player["level"] += 1
        player["max_hp"] += 5
        player["hp"] = effective_max_hp(player)
        leveled = True
    if leveled:
        from class_system import scale_class_resource_on_levelup
        scale_class_resource_on_levelup(player, old_level, player["level"])  # باگ‌فیکس: مانا/استامینا/فیض هم با لول بره بالا
        grant_levelup_points(player, old_level, player["level"])
        log_sync(
            f"⭐ **LEVEL UP** (کدکس)\n👤 {player.get('name','—')} (`{player.get('id','—')}`)\n"
            f"📊 سطح: {old_level} → {player['level']}",
            "LEVELUP"
        )
    return leveled


def _maps() -> list[str]:
    from economy import MAP_LOOT
    return list(MAP_LOOT.keys())


def _list_text() -> str:
    return ("📯 **کدکسِ کالکشن**\n\n"
            "یه‌دونه از هر ۵ تا متریالِ یه نقشه رو جمع کن و تحویلِ نگهبانِ اون منطقه بده — "
            "یه پاداشِ Zen/XP یک‌جا می‌گیری. هر نقشه هر ۴ ساعت یه‌بار قابلِ تحویله.\n\n"
            "یه نقشه رو انتخاب کن:")


def _list_kb(uid: int, page: int) -> InlineKeyboardMarkup:
    from economy import MAPS_DATA
    names = _maps()
    total_pages = max(1, (len(names) - 1) // PAGE_SIZE + 1)
    page = max(0, min(page, total_pages - 1))
    page_names = names[page * PAGE_SIZE: page * PAGE_SIZE + PAGE_SIZE]
    rows = []
    for name in page_names:
        emoji = MAPS_DATA.get(name, {}).get("emoji", "🗺️")
        rows.append([InlineKeyboardButton(text=f"{emoji} {name}", callback_data=f"cdx_view:{name}:{uid}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"cdx_page:{page-1}:{uid}", style=ButtonStyle.PRIMARY))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"cdx_page:{page+1}:{uid}", style=ButtonStyle.PRIMARY))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🔙 بازگشت به کارگاه", callback_data=f"cft_home:{uid}", style=ButtonStyle.DANGER)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _view_text(player: dict, map_name: str) -> str:
    from economy import MAPS_DATA
    emoji = MAPS_DATA.get(map_name, {}).get("emoji", "🗺️")
    tier = MAPS_DATA.get(map_name, {}).get("tier", "common")
    reward = cdx.TIER_REWARD.get(tier, cdx.TIER_REWARD["common"])
    remaining = cdx.cooldown_remaining(player, map_name)
    lines = [
        f"{emoji} **{map_name}**\n",
        f"🎁 پاداش: 💰 {reward['zen']:,} Zen | ✨ {reward['xp']} XP\n",
        "📦 ستِ لازم (۱ عدد از هرکدوم):",
        cdx.missing_set_text(player, map_name),
    ]
    if remaining > 0:
        h, m = divmod(remaining // 60, 60)
        lines.append(f"\n⏳ آماده‌ی تحویلِ بعدی: {h} ساعت و {m} دقیقه‌ی دیگه")
    return "\n".join(lines)


def _view_kb(player: dict, map_name: str, uid: int) -> InlineKeyboardMarkup:
    can = cdx.has_full_set(player, map_name) and cdx.cooldown_remaining(player, map_name) == 0
    rows = []
    if can:
        rows.append([InlineKeyboardButton(text="📯 تحویل بده", callback_data=f"cdx_turn:{map_name}:{uid}", style=ButtonStyle.SUCCESS)])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت به لیست", callback_data=f"cdx_page:0:{uid}", style=ButtonStyle.DANGER)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_cdx_home(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True); return
    try:
        await cb.message.edit_text(_list_text(), reply_markup=_list_kb(uid, 0))
    except Exception:
        await cb.message.answer(_list_text(), reply_markup=_list_kb(uid, 0))
    await cb.answer()


async def cb_cdx_page(cb: CallbackQuery):
    parts = cb.data.split(":")
    page, uid = int(parts[1]), int(parts[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True); return
    try:
        await cb.message.edit_text(_list_text(), reply_markup=_list_kb(uid, page))
    except Exception:
        await cb.message.answer(_list_text(), reply_markup=_list_kb(uid, page))
    await cb.answer()


async def cb_cdx_view(cb: CallbackQuery):
    parts = cb.data.split(":")
    map_name, uid = parts[1], int(parts[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True); return
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    try:
        await cb.message.edit_text(_view_text(player, map_name), reply_markup=_view_kb(player, map_name, uid))
    except Exception:
        await cb.message.answer(_view_text(player, map_name), reply_markup=_view_kb(player, map_name, uid))
    await cb.answer()


async def cb_cdx_turn(cb: CallbackQuery):
    parts = cb.data.split(":")
    map_name, uid = parts[1], int(parts[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True); return
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return

    ok, msg, reward = cdx.turn_in(player, map_name)
    if not ok:
        await cb.answer(msg, show_alert=True)
        return
    leveled = _level_up(player)
    save_player(uid, player)
    log_sync(
        f"📯 **CODEX TURN-IN** | {player.get('name','—')} (`{uid}`)\n"
        f"🗺️ {map_name} → +{reward['zen']:,} Zen, +{reward['xp']} XP" + (" (LEVEL UP!)" if leveled else ""),
        "ECONOMY"
    )
    await cb.answer("✅ تحویل داده شد!", show_alert=True)
    try:
        await cb.message.edit_text(_view_text(player, map_name), reply_markup=_view_kb(player, map_name, uid))
    except Exception:
        await cb.message.answer(msg)


def register_collection_codex_handlers(dp, bot):
    dp.callback_query.register(cb_cdx_home, F.data.startswith("cdx_home:"))
    dp.callback_query.register(cb_cdx_page, F.data.startswith("cdx_page:"))
    dp.callback_query.register(cb_cdx_view, F.data.startswith("cdx_view:"))
    dp.callback_query.register(cb_cdx_turn, F.data.startswith("cdx_turn:"))
