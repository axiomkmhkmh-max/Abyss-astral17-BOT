# ============================================================
#  ASTRAL ABYSS — Map Recipes Handlers (Gap UI)
# ------------------------------------------------------------
#  پورتِ map_recipes_handlers.py (تلگرام) برای گپ. منطقِ خالص
#  (map_recipes.py) عیناً importه. برخلافِ نسخه‌ی تلگرام، uid داخلِ
#  callback_data نیست — رو گپ owner همیشه از cb.from_user.id میاد
#  (همون الگویی که gap_loot_handlers.py استفاده می‌کنه)، پس نیازی
#  به چکِ جداگانه‌ی owner نیست.
# ============================================================
from gap_dispatcher import GapDispatcher
from gap_types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from logger import log_sync
import map_recipes as mrc

WORKSHOP_BACK_CB = "wsp:home"
PAGE_SIZE = 6


def _list_text() -> str:
    return ("🗺️ **دستورهای ویژه‌ی نقشه**\n\n"
            "هر نقشه یه دستورِ مخصوصِ خودش داره — یه‌دونه از هر ۵ تا متریالِ "
            "اون نقشه رو بده، یه تجهیزِ تضمین‌شده بگیر (هرچی نقشه سخت‌تر، رریتیِ بهتر).\n\n"
            "یه نقشه رو انتخاب کن:")


def _list_kb(page: int) -> InlineKeyboardMarkup:
    names = list(mrc.MAP_RECIPES.keys())
    total_pages = max(1, (len(names) - 1) // PAGE_SIZE + 1)
    page = max(0, min(page, total_pages - 1))
    page_names = names[page * PAGE_SIZE: page * PAGE_SIZE + PAGE_SIZE]

    rows = []
    for name in page_names:
        recipe = mrc.MAP_RECIPES[name]
        rows.append([InlineKeyboardButton(text=f"{recipe['emoji']} {name}", callback_data=f"mrc_view:{name}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"mrc_page:{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"mrc_page:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🔙 بازگشت به کارگاه", callback_data=WORKSHOP_BACK_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _view_text(player: dict, map_name: str) -> str:
    from item_system import RARITY_DATA
    recipe = mrc.MAP_RECIPES[map_name]
    rlabel = RARITY_DATA[recipe["forced_rarity"]]["label"]
    lines = [
        f"{recipe['emoji']} **{map_name}**\n",
        f"🎁 خروجی: یه تجهیزِ تصادفی — رریتیِ تضمین‌شده: {rlabel}",
        f"📏 حداقل سطح: {recipe['req_level']}",
        f"💰 هزینه: {recipe['zen_cost']:,} Zen\n",
        "📦 موادِ لازم (۱ عدد از هرکدوم):",
        mrc.missing_map_materials_text(player, map_name),
    ]
    return "\n".join(lines)


def _view_kb(player: dict, map_name: str) -> InlineKeyboardMarkup:
    recipe = mrc.MAP_RECIPES[map_name]
    can = (mrc.has_map_materials(player, map_name)
           and player.get("zen", 0) >= recipe["zen_cost"]
           and player.get("level", 1) >= recipe["req_level"])
    rows = []
    if can:
        rows.append([InlineKeyboardButton(text="🔨 بساز", callback_data=f"mrc_craft:{map_name}")])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت به لیست", callback_data="mrc_page:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_mrc_home(cb: CallbackQuery):
    try:
        await cb.message.edit_text(_list_text(), reply_markup=_list_kb(0))
    except Exception:
        await cb.message.answer(_list_text(), reply_markup=_list_kb(0))
    await cb.answer()


async def cb_mrc_page(cb: CallbackQuery):
    page = int(cb.data.split(":", 1)[1])
    try:
        await cb.message.edit_text(_list_text(), reply_markup=_list_kb(page))
    except Exception:
        await cb.message.answer(_list_text(), reply_markup=_list_kb(page))
    await cb.answer()


async def cb_mrc_view(cb: CallbackQuery):
    uid = cb.from_user.id
    map_name = cb.data.split(":", 1)[1]
    player = await aget_player(uid)
    if not player or map_name not in mrc.MAP_RECIPES:
        await cb.answer("❌", show_alert=True)
        return
    try:
        await cb.message.edit_text(_view_text(player, map_name), reply_markup=_view_kb(player, map_name))
    except Exception:
        await cb.message.answer(_view_text(player, map_name), reply_markup=_view_kb(player, map_name))
    await cb.answer()


async def cb_mrc_craft(cb: CallbackQuery):
    uid = cb.from_user.id
    map_name = cb.data.split(":", 1)[1]
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    ok, msg, item = mrc.craft_map_item(player, map_name)
    if not ok:
        await cb.answer(msg, show_alert=True)
        return
    await asave_player(uid, player)
    log_sync(
        f"🗺️ **MAP RECIPE CRAFT (GAP)** | {player.get('name','—')} (`{uid}`)\n"
        f"🗺️ {map_name} → {item['emoji']} {item['name']} ({item['rarity']})",
        "ECONOMY"
    )
    await cb.answer("✅ ساخته شد!", show_alert=True)
    try:
        await cb.message.edit_text(_view_text(player, map_name), reply_markup=_view_kb(player, map_name))
    except Exception:
        await cb.message.answer(msg)


def register_gap_map_recipes_handlers(dp: GapDispatcher):
    dp.register_callback(cb_mrc_home, data="mrc_home")
    dp.register_callback(cb_mrc_page, data_startswith="mrc_page:")
    dp.register_callback(cb_mrc_view, data_startswith="mrc_view:")
    dp.register_callback(cb_mrc_craft, data_startswith="mrc_craft:")
