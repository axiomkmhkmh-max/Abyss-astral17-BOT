# ============================================================
#  ASTRAL ABYSS — Artifact Forge Handlers (Telegram UI)
# ------------------------------------------------------------
#  دکمه‌ی «🏺 کورهٔ مصنوعات» تو منوی کارگاه. هرکدوم از ۱۴ آیتمِ
#  legendaryِ نقشه‌ای رو انتخاب کن، اگه شرایط جور بود بسازش.
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
from logger import log_sync
import artifact_forge as arf
import crafting_system as cfs
from item_system import RARITY_DATA

PAGE_SIZE = 6


def _owner_ok(cb: CallbackQuery, uid: int) -> bool:
    return cb.from_user.id == uid


def _list_text() -> str:
    return ("🏺 **کورهٔ مصنوعات**\n\n"
            "۱۴ آیتمِ legendaryِ نقشه‌ای (Divine Shard، Dragon Heart، Abyss Heart و امثالش) "
            "علاوه‌بر فروش/تبدیل، حالا یه مسیرِ کرفتِ اختصاصیِ خودشون رو دارن — "
            "با فقط ۱ دونه از خودشون یه تجهیزِ **ancient** (بالاترِ سقفِ آهنگریِ عادی) می‌سازن.\n\n"
            "یه مصنوعه رو انتخاب کن:")


def _list_kb(uid: int, page: int) -> InlineKeyboardMarkup:
    names = list(arf.ARTIFACT_RECIPES.keys())
    total_pages = max(1, (len(names) - 1) // PAGE_SIZE + 1)
    page = max(0, min(page, total_pages - 1))
    page_names = names[page * PAGE_SIZE: page * PAGE_SIZE + PAGE_SIZE]

    rows = []
    for name in page_names:
        recipe = arf.ARTIFACT_RECIPES[name]
        rows.append([InlineKeyboardButton(
            text=f"{recipe['emoji']} {recipe['result_name']} (از {name})",
            callback_data=f"arf_view:{name}:{uid}",
        )])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"arf_page:{page-1}:{uid}", style=ButtonStyle.PRIMARY))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"arf_page:{page+1}:{uid}", style=ButtonStyle.PRIMARY))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🔙 بازگشت به کارگاه", callback_data=f"cft_home:{uid}", style=ButtonStyle.DANGER)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _view_text(player: dict, legendary_name: str) -> str:
    recipe = arf.ARTIFACT_RECIPES[legendary_name]
    have_mat = "✅" if arf.has_legendary_material(player, legendary_name) else "❌"
    dust_have = cfs.material_qty(player, "astral_dust")
    c = cfs.get_crafting(player)
    return (
        f"{recipe['emoji']} **{recipe['result_name']}**\n"
        f"_{recipe['result_desc']}_\n\n"
        f"🗺️ ماده: {legendary_name} ({recipe['map']}) — {have_mat} داری\n"
        f"🌟 غبارِ‌اختری: {dust_have}/{arf.ASTRAL_DUST_COST}\n"
        f"🔨 سطحِ آهنگریِ لازم: {recipe['req_forge_level']} (الان: {c['forge_level']})\n"
        f"💰 هزینه: {recipe['zen_cost']:,} Zen\n\n"
        f"🎁 خروجی: تجهیزِ **{RARITY_DATA['ancient']['label']}** تضمین‌شده"
    )


def _view_kb(player: dict, legendary_name: str, uid: int) -> InlineKeyboardMarkup:
    ok, _ = arf.can_craft_artifact(player, legendary_name)
    rows = []
    if ok:
        rows.append([InlineKeyboardButton(text="🏺 بساز", callback_data=f"arf_craft:{legendary_name}:{uid}", style=ButtonStyle.SUCCESS)])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت به لیست", callback_data=f"arf_page:0:{uid}", style=ButtonStyle.DANGER)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_arf_home(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True); return
    try:
        await cb.message.edit_text(_list_text(), reply_markup=_list_kb(uid, 0))
    except Exception:
        await cb.message.answer(_list_text(), reply_markup=_list_kb(uid, 0))
    await cb.answer()


async def cb_arf_page(cb: CallbackQuery):
    parts = cb.data.split(":")
    page, uid = int(parts[1]), int(parts[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True); return
    try:
        await cb.message.edit_text(_list_text(), reply_markup=_list_kb(uid, page))
    except Exception:
        await cb.message.answer(_list_text(), reply_markup=_list_kb(uid, page))
    await cb.answer()


async def cb_arf_view(cb: CallbackQuery):
    parts = cb.data.split(":")
    legendary_name, uid = parts[1], int(parts[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True); return
    player = get_player(uid)
    if not player or legendary_name not in arf.ARTIFACT_RECIPES:
        await cb.answer("❌", show_alert=True); return
    try:
        await cb.message.edit_text(_view_text(player, legendary_name), reply_markup=_view_kb(player, legendary_name, uid))
    except Exception:
        await cb.message.answer(_view_text(player, legendary_name), reply_markup=_view_kb(player, legendary_name, uid))
    await cb.answer()


async def cb_arf_craft(cb: CallbackQuery):
    parts = cb.data.split(":")
    legendary_name, uid = parts[1], int(parts[2])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True); return
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return

    ok, msg, item = arf.craft_artifact(uid, player, legendary_name)
    if not ok:
        await cb.answer(msg, show_alert=True)
        return
    save_player(uid, player)
    log_sync(
        f"🏺 **ARTIFACT FORGE** | {player.get('name','—')} (`{uid}`)\n"
        f"🗺️ {legendary_name} → {item['emoji']} {item['name']} ({item['rarity']})",
        "ECONOMY"
    )
    await cb.answer("✅ مصنوعه ساخته شد!", show_alert=True)
    try:
        await cb.message.edit_text(_view_text(player, legendary_name), reply_markup=_view_kb(player, legendary_name, uid))
    except Exception:
        await cb.message.answer(msg)


def register_artifact_forge_handlers(dp, bot):
    dp.callback_query.register(cb_arf_home,  F.data.startswith("arf_home:"))
    dp.callback_query.register(cb_arf_page,  F.data.startswith("arf_page:"))
    dp.callback_query.register(cb_arf_view,  F.data.startswith("arf_view:"))
    dp.callback_query.register(cb_arf_craft, F.data.startswith("arf_craft:"))
