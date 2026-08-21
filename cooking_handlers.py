# ============================================================
#  ASTRAL ABYSS RPG — Cooking Handlers (Telegram UI)  — v1
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from logger import log_sync
import cooking_system as cks


def _owner_ok(cb: CallbackQuery, uid: int) -> bool:
    return cb.from_user.id == uid


def _kitchen_kb(uid: int, player: dict) -> InlineKeyboardMarkup:
    rows = []
    foods = [it for it in player.get("inventory", []) if it.get("type") == "food"]
    for f in foods:
        recipe = cks.RECIPES.get(f["food_id"])
        if not recipe:
            continue
        rows.append([InlineKeyboardButton(
            text=f"😋 خوردنِ {recipe['name']} ({f['qty']}×)",
            callback_data=f"cook_eat:{uid}:{f['food_id']}", style=ButtonStyle.SUCCESS)])
    rows.append([InlineKeyboardButton(text="🍳 پختنِ غذا", callback_data=f"cook_menu:{uid}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cmd_cook(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    changed = cks.clean_expired_buffs(player)
    if changed:
        await asave_player(uid, player)
    await msg.answer("🍲 **آشپزخانه**\n\n" + cks.kitchen_summary_text(uid, player), reply_markup=_kitchen_kb(uid, player))


async def cb_cook_home(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    cks.clean_expired_buffs(player)
    await asave_player(uid, player)
    await cb.answer()
    await cb.message.edit_text("🍲 **آشپزخانه**\n\n" + cks.kitchen_summary_text(uid, player), reply_markup=_kitchen_kb(uid, player))


def _cook_menu_kb(uid: int, player: dict) -> InlineKeyboardMarkup:
    rows = []
    for key, recipe in cks.RECIPES.items():
        ready = "✅" if cks.can_cook(player, key) else "❌"
        rows.append([InlineKeyboardButton(
            text=f"{ready} {recipe['name']} — {recipe['zen_cost']:,} Zen",
            callback_data=f"cook_make:{uid}:{key}", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data=f"cook_home:{uid}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_cook_menu(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    lines = ["🍳 **کدوم غذا رو بپزیم؟**", ""]
    for key, recipe in cks.RECIPES.items():
        lines.append(f"{recipe['name']} — {recipe['desc']}")
        lines.append(f"  موادِ لازم: {cks.missing_ingredients_text(player, key)}")
    await cb.answer()
    await cb.message.edit_text("\n".join(lines), reply_markup=_cook_menu_kb(uid, player))


async def cb_cook_make(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid, recipe_key = int(parts[1]), parts[2]
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    ok, msg = cks.cook_recipe(uid, player, recipe_key)
    if ok:
        await asave_player(uid, player)
        log_sync(f"🍳 **COOK**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "HOUSE")
    await cb.answer(msg, show_alert=True)
    player = await aget_player(uid)
    await cb.message.edit_text("🍲 **آشپزخانه**\n\n" + cks.kitchen_summary_text(uid, player), reply_markup=_kitchen_kb(uid, player))


async def cb_cook_eat(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid, food_key = int(parts[1]), parts[2]
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    ok, msg = cks.eat_food(uid, player, food_key)
    if ok:
        await asave_player(uid, player)
        log_sync(f"😋 **EAT FOOD**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "HOUSE")
    await cb.answer(msg, show_alert=True)
    player = await aget_player(uid)
    await cb.message.edit_text("🍲 **آشپزخانه**\n\n" + cks.kitchen_summary_text(uid, player), reply_markup=_kitchen_kb(uid, player))


def register_cooking_handlers(dp, bot):
    dp.message.register(cmd_cook, Command("cook"))
    dp.callback_query.register(cb_cook_home, F.data.startswith("cook_home:"))
    dp.callback_query.register(cb_cook_menu, F.data.startswith("cook_menu:"))
    dp.callback_query.register(cb_cook_make, F.data.startswith("cook_make:"))
    dp.callback_query.register(cb_cook_eat,  F.data.startswith("cook_eat:"))
