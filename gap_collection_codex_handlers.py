# ============================================================
#  ASTRAL ABYSS — Collection Codex Handlers (Gap UI)
# ------------------------------------------------------------
#  پورتِ collection_codex_handlers.py (تلگرام) برای گپ. منطقِ خالص
#  (collection_codex.py) عیناً importه.
# ============================================================
from gap_dispatcher import GapDispatcher
from gap_types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from logger import log_sync
from game_data import xp_for_level, effective_max_level
import collection_codex as cdx

WORKSHOP_BACK_CB = "wsp:home"
PAGE_SIZE = 6


def _level_up(player: dict) -> bool:
    """کپیِ همون الگویی که collection_codex_handlers.py (تلگرام) استفاده
    می‌کنه — تا این ماژول وابسته به bot.py نشه (جلوگیری از importِ حلقوی).
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
            f"⭐ **LEVEL UP** (کدکس، گپ)\n👤 {player.get('name','—')} (`{player.get('id','—')}`)\n"
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


def _list_kb(page: int) -> InlineKeyboardMarkup:
    from economy import MAPS_DATA
    names = _maps()
    total_pages = max(1, (len(names) - 1) // PAGE_SIZE + 1)
    page = max(0, min(page, total_pages - 1))
    page_names = names[page * PAGE_SIZE: page * PAGE_SIZE + PAGE_SIZE]
    rows = []
    for name in page_names:
        emoji = MAPS_DATA.get(name, {}).get("emoji", "🗺️")
        rows.append([InlineKeyboardButton(text=f"{emoji} {name}", callback_data=f"cdx_view:{name}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"cdx_page:{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"cdx_page:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🔙 بازگشت به کارگاه", callback_data=WORKSHOP_BACK_CB)])
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


def _view_kb(player: dict, map_name: str) -> InlineKeyboardMarkup:
    can = cdx.has_full_set(player, map_name) and cdx.cooldown_remaining(player, map_name) == 0
    rows = []
    if can:
        rows.append([InlineKeyboardButton(text="📯 تحویل بده", callback_data=f"cdx_turn:{map_name}")])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت به لیست", callback_data="cdx_page:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_cdx_home(cb: CallbackQuery):
    try:
        await cb.message.edit_text(_list_text(), reply_markup=_list_kb(0))
    except Exception:
        await cb.message.answer(_list_text(), reply_markup=_list_kb(0))
    await cb.answer()


async def cb_cdx_page(cb: CallbackQuery):
    page = int(cb.data.split(":", 1)[1])
    try:
        await cb.message.edit_text(_list_text(), reply_markup=_list_kb(page))
    except Exception:
        await cb.message.answer(_list_text(), reply_markup=_list_kb(page))
    await cb.answer()


async def cb_cdx_view(cb: CallbackQuery):
    uid = cb.from_user.id
    map_name = cb.data.split(":", 1)[1]
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    try:
        await cb.message.edit_text(_view_text(player, map_name), reply_markup=_view_kb(player, map_name))
    except Exception:
        await cb.message.answer(_view_text(player, map_name), reply_markup=_view_kb(player, map_name))
    await cb.answer()


async def cb_cdx_turn(cb: CallbackQuery):
    uid = cb.from_user.id
    map_name = cb.data.split(":", 1)[1]
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    ok, msg, reward = cdx.turn_in(player, map_name)
    if not ok:
        await cb.answer(msg, show_alert=True)
        return
    leveled = _level_up(player)
    await asave_player(uid, player)
    log_sync(
        f"📯 **CODEX TURN-IN (GAP)** | {player.get('name','—')} (`{uid}`)\n"
        f"🗺️ {map_name} → +{reward['zen']:,} Zen, +{reward['xp']} XP" + (" (LEVEL UP!)" if leveled else ""),
        "ECONOMY"
    )
    await cb.answer("✅ تحویل داده شد!", show_alert=True)
    try:
        await cb.message.edit_text(_view_text(player, map_name), reply_markup=_view_kb(player, map_name))
    except Exception:
        await cb.message.answer(msg)


def register_gap_collection_codex_handlers(dp: GapDispatcher):
    dp.register_callback(cb_cdx_home, data="cdx_home")
    dp.register_callback(cb_cdx_page, data_startswith="cdx_page:")
    dp.register_callback(cb_cdx_view, data_startswith="cdx_view:")
    dp.register_callback(cb_cdx_turn, data_startswith="cdx_turn:")
