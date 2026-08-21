# ============================================================
#  ASTRAL ABYSS RPG — Crafting Handlers (Telegram UI)  — v1
#  دو میز: 🔨 آهنگری (crafting_system.FORGE_RECIPES)
#           🧪 کیمیاگری (POTION_RECIPES / GEM_RECIPES / SOUL_STONE)
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from logger import log_sync
import item_system as isy
import crafting_system as cfs


def _owner_ok(cb: CallbackQuery, uid: int) -> bool:
    return cb.from_user.id == uid


# ─── منوی اصلیِ کارگاه ─────────────────────────────────────────
def _workshop_kb(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔨 میزِ آهنگری", callback_data=f"cft_forge:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🧪 میزِ کیمیاگری", callback_data=f"cft_alch:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🪓 کاوش/استخراجِ مواد", callback_data=f"gth_home:{uid}", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="♻️ تجزیه‌ی تجهیز (Salvage)", callback_data=f"cft_salv_menu:{uid}", style=ButtonStyle.DANGER)],
        [InlineKeyboardButton(text="💠 سوکت‌کردنِ جم", callback_data=f"cft_gemsock_menu:{uid}", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="🔮 بازغلتوندنِ افیکس", callback_data=f"cft_reroll_menu:{uid}", style=ButtonStyle.SUCCESS)],
        # ─── متریال‌های نقشه‌ای (economy.MAP_LOOT) قبلاً هیچ مصرفی
        # نداشتن — فقط قابل‌فروش بودن. این سه گزینه بهشون مصرف می‌ده:
        [InlineKeyboardButton(text="🔄 صرافیِ متریال", callback_data=f"mex_home:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🗺️ دستورهای ویژه‌ی نقشه", callback_data=f"mrc_home:{uid}", style=ButtonStyle.PRIMARY)],
        # 🆕 مسیرِ کرفتِ اختصاصیِ ۱۴ آیتمِ legendaryِ نقشه‌ای (تکی، نه کلِ ست)
        [InlineKeyboardButton(text="🏺 کورهٔ مصنوعات", callback_data=f"arf_home:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="📯 کدکسِ کالکشن", callback_data=f"cdx_home:{uid}", style=ButtonStyle.PRIMARY)],
    ])


async def cmd_craft(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    await msg.answer(cfs.crafting_summary_text(player), reply_markup=_workshop_kb(uid))


async def cb_workshop_home(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    await cb.answer()
    await cb.message.edit_text(cfs.crafting_summary_text(player), reply_markup=_workshop_kb(uid))


# ─── میزِ آهنگری ────────────────────────────────────────────────
def _forge_slots_kb(uid: int) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for slot in isy.EQUIP_SLOTS:
        row.append(InlineKeyboardButton(text=cfs.SLOT_LABELS[slot], callback_data=f"cft_fslot:{uid}:{slot}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data=f"cft_home:{uid}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_forge_menu(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    c = cfs.get_crafting(player)
    text = f"🔨 **میزِ آهنگری** — سطح {c['forge_level']}/{cfs.CRAFT_LEVEL_CAP}\n\nکدوم اسلات؟"
    await cb.answer()
    await cb.message.edit_text(text, reply_markup=_forge_slots_kb(uid))


def _forge_tier_kb(uid: int, slot: str) -> InlineKeyboardMarkup:
    rows = []
    for tier in range(1, 6):
        rows.append([InlineKeyboardButton(
            text=f"تیر {tier} — {isy.RARITY_DATA[cfs.CRAFT_RARITY_BY_TIER[tier]]['label']}",
            callback_data=f"cft_fmake:{uid}:{slot}:{tier}", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data=f"cft_forge:{uid}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_forge_slot(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid, slot = int(parts[1]), parts[2]
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    await cb.answer()
    await cb.message.edit_text(cfs.forge_slot_menu_text(player, slot), reply_markup=_forge_tier_kb(uid, slot))


async def cb_forge_make(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid, slot, tier = int(parts[1]), parts[2], int(parts[3])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    ok, msg, item = cfs.craft_forge(uid, player, f"{slot}_t{tier}")
    if ok:
        await asave_player(uid, player)
        log_sync(f"🔨 **CRAFT FORGE**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "CRAFT")
    await cb.answer(msg[:200], show_alert=True)
    player = await aget_player(uid)
    await cb.message.edit_text(cfs.forge_slot_menu_text(player, slot), reply_markup=_forge_tier_kb(uid, slot))


# ─── میزِ کیمیاگری ──────────────────────────────────────────────
def _alch_home_kb(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧪 ساختِ پوشن/الکسیر", callback_data=f"cft_potlist:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="😋 نوشیدن از کوله‌پشتی", callback_data=f"cft_drinklist:{uid}", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="💎 تراشِ جم", callback_data=f"cft_gemlist:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🔮 ساختِ سنگِ‌روح", callback_data=f"cft_soulmake:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="⬅️ برگشت", callback_data=f"cft_home:{uid}", style=ButtonStyle.PRIMARY)],
    ])


async def cb_alch_menu(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    c = cfs.get_crafting(player)
    text = (f"🧪 **میزِ کیمیاگری** — سطح {c['alchemy_level']}/{cfs.CRAFT_LEVEL_CAP}\n\n"
            f"🔥 الکسیرِ فعال:\n{cfs.active_potion_buffs_text(player)}")
    await cb.answer()
    await cb.message.edit_text(text, reply_markup=_alch_home_kb(uid))


def _potion_list_kb(uid: int, player: dict) -> InlineKeyboardMarkup:
    c = cfs.get_crafting(player)
    rows = []
    for key, r in cfs.POTION_RECIPES.items():
        lock = "🔒" if c["alchemy_level"] < r["req_level"] else "✅"
        rows.append([InlineKeyboardButton(
            text=f"{lock} {r['name']} — {r['zen_cost']:,}Zen", callback_data=f"cft_pmake:{uid}:{key}")])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data=f"cft_alch:{uid}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_potion_list(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    lines = ["🧪 **دستورهای کیمیاگری:**", ""]
    for key, r in cfs.POTION_RECIPES.items():
        lines.append(f"{r['name']} — {r['desc']}")
        lines.append(f"  {cfs.missing_materials_text(player, r['materials'])}")
    await cb.answer()
    await cb.message.edit_text("\n".join(lines), reply_markup=_potion_list_kb(uid, player))


async def cb_potion_make(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid, key = int(parts[1]), parts[2]
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    ok, msg = cfs.craft_potion(uid, player, key)
    if ok:
        await asave_player(uid, player)
        log_sync(f"🧪 **CRAFT POTION**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "CRAFT")
    await cb.answer(msg[:200], show_alert=True)
    player = await aget_player(uid)
    await cb.message.edit_text("\n".join(
        [f"{r['name']} — {r['desc']}\n  {cfs.missing_materials_text(player, r['materials'])}" for r in cfs.POTION_RECIPES.values()]
    ), reply_markup=_potion_list_kb(uid, player))


def _drink_list_kb(uid: int, player: dict) -> InlineKeyboardMarkup:
    rows = []
    owned = [it for it in player.get("inventory", []) if it.get("type") == "potion"]
    for it in owned:
        r = cfs.POTION_RECIPES.get(it["material_id"])
        if not r:
            continue
        rows.append([InlineKeyboardButton(
            text=f"😋 {r['name']} ({it['qty']}×)", callback_data=f"cft_drink:{uid}:{it['material_id']}", style=ButtonStyle.SUCCESS)])
    if not owned:
        rows.append([InlineKeyboardButton(text="— چیزی نداری —", callback_data=f"cft_alch:{uid}")])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data=f"cft_alch:{uid}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_drink_list(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    await cb.answer()
    await cb.message.edit_text("😋 **کدوم پوشن/الکسیر رو بخوریم؟**", reply_markup=_drink_list_kb(uid, player))


async def cb_drink_make(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid, key = int(parts[1]), parts[2]
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    ok, msg = cfs.drink_potion(uid, player, key)
    if ok:
        await asave_player(uid, player)
    await cb.answer(msg[:200], show_alert=True)
    player = await aget_player(uid)
    await cb.message.edit_text("😋 **کدوم پوشن/الکسیر رو بخوریم؟**", reply_markup=_drink_list_kb(uid, player))


def _gem_list_kb(uid: int, player: dict) -> InlineKeyboardMarkup:
    c = cfs.get_crafting(player)
    rows = []
    for key, r in cfs.GEM_RECIPES.items():
        lock = "🔒" if c["alchemy_level"] < r["req_level"] else "✅"
        rows.append([InlineKeyboardButton(
            text=f"{lock} {r['label']} — {r['zen_cost']:,}Zen", callback_data=f"cft_gmake:{uid}:{key}")])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data=f"cft_alch:{uid}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_gem_list(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    await cb.answer()
    await cb.message.edit_text("💎 **کدوم جم رو بتراشیم؟**\n(بعداً از منوی 💠سوکت‌کردنِ جم رو تجهیزت بذار)",
                                reply_markup=_gem_list_kb(uid, player))


async def cb_gem_make(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid, key = int(parts[1]), parts[2]
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    ok, msg = cfs.craft_gem(uid, player, key)
    if ok:
        await asave_player(uid, player)
        log_sync(f"💎 **CRAFT GEM**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "CRAFT")
    await cb.answer(msg[:200], show_alert=True)
    player = await aget_player(uid)
    await cb.message.edit_text("💎 **کدوم جم رو بتراشیم؟**", reply_markup=_gem_list_kb(uid, player))


async def cb_soul_make(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    ok, msg = cfs.craft_soul_stone(uid, player)
    if ok:
        await asave_player(uid, player)
        log_sync(f"🔮 **CRAFT SOUL STONE**\n👤 {player.get('name','—')} (`{uid}`)", "CRAFT")
    await cb.answer(msg[:200], show_alert=True)
    player = await aget_player(uid)
    r = cfs.SOUL_STONE_RECIPE
    text = f"🔮 **{r['name']}**\n{r['desc']}\n💰 {r['zen_cost']:,}Zen\n{cfs.missing_materials_text(player, r['materials'])}"
    await cb.message.edit_text(text, reply_markup=_alch_home_kb(uid))


# ─── تجزیه (Salvage) ────────────────────────────────────────────
def _salvage_kb(uid: int, player: dict) -> InlineKeyboardMarkup:
    equipped_ids = {it.get("item_id") for it in (player.get("equipped", {}) or {}).values() if it}
    rows = []
    gear = [it for it in player.get("inventory", []) if it.get("slot") in isy.EQUIP_SLOTS and it.get("item_id") not in equipped_ids]
    for it in gear[:20]:
        rows.append([InlineKeyboardButton(
            text=f"♻️ {it['emoji']} {it['name']} ({isy.RARITY_DATA.get(it.get('rarity','common'),{}).get('label','')})",
            callback_data=f"cft_salv:{uid}:{it['item_id']}", style=ButtonStyle.DANGER)])
    if not gear:
        rows.append([InlineKeyboardButton(text="— چیزِ قابلِ‌تجزیه نداری —", callback_data=f"cft_home:{uid}")])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data=f"cft_home:{uid}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_salvage_menu(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    await cb.answer()
    await cb.message.edit_text("♻️ **کدوم تجهیز رو تجزیه کنیم؟** (غیرقابلِ بازگشت!)", reply_markup=_salvage_kb(uid, player))


async def cb_salvage_do(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid, item_id = int(parts[1]), parts[2]
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    ok, msg = cfs.salvage_item(uid, player, item_id)
    if ok:
        await asave_player(uid, player)
    await cb.answer(msg[:200], show_alert=True)
    player = await aget_player(uid)
    await cb.message.edit_text("♻️ **کدوم تجهیز رو تجزیه کنیم؟** (غیرقابلِ بازگشت!)", reply_markup=_salvage_kb(uid, player))


# ─── سوکت‌کردنِ جم ──────────────────────────────────────────────
def _gemsock_item_kb(uid: int, player: dict) -> InlineKeyboardMarkup:
    rows = []
    all_items = list(player.get("inventory", [])) + [it for it in (player.get("equipped", {}) or {}).values() if it]
    for it in all_items:
        if "sockets" not in it:
            continue
        empty = sum(1 for s in it["sockets"] if not s.get("gem"))
        if empty <= 0:
            continue
        rows.append([InlineKeyboardButton(
            text=f"💠 {it['emoji']} {it['name']} ({empty} سوکتِ خالی)",
            callback_data=f"cft_gsi:{uid}:{it['item_id']}")])
    if not rows:
        rows.append([InlineKeyboardButton(text="— تجهیزِ سوکت‌دارِ خالی نداری —", callback_data=f"cft_home:{uid}")])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data=f"cft_home:{uid}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_gemsock_menu(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    await cb.answer()
    await cb.message.edit_text("💠 **رو کدوم تجهیز جم بذاریم؟**", reply_markup=_gemsock_item_kb(uid, player))


def _gemsock_gem_kb(uid: int, player: dict, item_id: str) -> InlineKeyboardMarkup:
    rows = []
    owned = [it for it in player.get("inventory", []) if it.get("type") == "gem" and it.get("qty", 0) > 0]
    for it in owned:
        rows.append([InlineKeyboardButton(
            text=f"💎 {it.get('gem_label', it['material_id'])} ({it['qty']}×)",
            callback_data=f"cft_gsdo:{uid}:{item_id}:{it['material_id']}")])
    if not owned:
        rows.append([InlineKeyboardButton(text="— جمی نداری؛ اول تو 🧪کیمیاگری بتراش —", callback_data=f"cft_gemsock_menu:{uid}")])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data=f"cft_gemsock_menu:{uid}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_gemsock_item(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid, item_id = int(parts[1]), parts[2]
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    await cb.answer()
    await cb.message.edit_text("💎 **کدوم جم رو سوکت کنیم؟**", reply_markup=_gemsock_gem_kb(uid, player, item_id))


async def cb_gemsock_do(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid, item_id, gem_key = int(parts[1]), parts[2], parts[3]
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    ok, msg = cfs.insert_gem(uid, player, item_id, gem_key)
    if ok:
        await asave_player(uid, player)
        log_sync(f"💠 **SOCKET GEM**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "CRAFT")
    await cb.answer(msg[:200], show_alert=True)
    player = await aget_player(uid)
    await cb.message.edit_text("💠 **رو کدوم تجهیز جم بذاریم؟**", reply_markup=_gemsock_item_kb(uid, player))


# ─── بازغلتوندنِ افیکس (سنگِ‌روح) ────────────────────────────────
def _reroll_kb(uid: int, player: dict) -> InlineKeyboardMarkup:
    rows = []
    all_items = list(player.get("inventory", [])) + [it for it in (player.get("equipped", {}) or {}).values() if it]
    for it in all_items:
        if "affixes" not in it:
            continue
        rows.append([InlineKeyboardButton(
            text=f"🔮 {it['emoji']} {it['name']}", callback_data=f"cft_rrdo:{uid}:{it['item_id']}")])
    if not rows:
        rows.append([InlineKeyboardButton(text="— تجهیزی نداری —", callback_data=f"cft_home:{uid}")])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data=f"cft_home:{uid}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_reroll_menu(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    have = cfs.material_qty(player, "soul_stone")
    await cb.answer()
    await cb.message.edit_text(
        f"🔮 **بازغلتوندنِ افیکس** — {have} سنگِ‌روح داری\n(از 🧪کیمیاگری ساخته می‌شه)",
        reply_markup=_reroll_kb(uid, player))


async def cb_reroll_do(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid, item_id = int(parts[1]), parts[2]
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    ok, msg = cfs.reroll_affixes(uid, player, item_id)
    if ok:
        await asave_player(uid, player)
        log_sync(f"🔮 **REROLL AFFIXES**\n👤 {player.get('name','—')} (`{uid}`)", "CRAFT")
    await cb.answer(msg[:200], show_alert=True)
    player = await aget_player(uid)
    have = cfs.material_qty(player, "soul_stone")
    await cb.message.edit_text(f"🔮 **بازغلتوندنِ افیکس** — {have} سنگِ‌روح داری", reply_markup=_reroll_kb(uid, player))


# ─── ثبت‌نام ─────────────────────────────────────────────────────
def register_crafting_handlers(dp, bot):
    dp.message.register(cmd_craft, Command("craft"))
    dp.callback_query.register(cb_workshop_home, F.data.startswith("cft_home:"))

    dp.callback_query.register(cb_forge_menu, F.data.startswith("cft_forge:"))
    dp.callback_query.register(cb_forge_slot, F.data.startswith("cft_fslot:"))
    dp.callback_query.register(cb_forge_make, F.data.startswith("cft_fmake:"))

    dp.callback_query.register(cb_alch_menu, F.data.startswith("cft_alch:"))
    dp.callback_query.register(cb_potion_list, F.data.startswith("cft_potlist:"))
    dp.callback_query.register(cb_potion_make, F.data.startswith("cft_pmake:"))
    dp.callback_query.register(cb_drink_list, F.data.startswith("cft_drinklist:"))
    dp.callback_query.register(cb_drink_make, F.data.startswith("cft_drink:"))
    dp.callback_query.register(cb_gem_list, F.data.startswith("cft_gemlist:"))
    dp.callback_query.register(cb_gem_make, F.data.startswith("cft_gmake:"))
    dp.callback_query.register(cb_soul_make, F.data.startswith("cft_soulmake:"))

    dp.callback_query.register(cb_salvage_menu, F.data.startswith("cft_salv_menu:"))
    dp.callback_query.register(cb_salvage_do, F.data.startswith("cft_salv:"))

    dp.callback_query.register(cb_gemsock_menu, F.data.startswith("cft_gemsock_menu:"))
    dp.callback_query.register(cb_gemsock_item, F.data.startswith("cft_gsi:"))
    dp.callback_query.register(cb_gemsock_do, F.data.startswith("cft_gsdo:"))

    dp.callback_query.register(cb_reroll_menu, F.data.startswith("cft_reroll_menu:"))
    dp.callback_query.register(cb_reroll_do, F.data.startswith("cft_rrdo:"))
