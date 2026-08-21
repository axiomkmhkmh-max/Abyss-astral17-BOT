# ============================================================
#  ASTRAL ABYSS — بازار سیاه: حراجیِ سایه (نسخه‌ی واقعاً کاربردی)
# ------------------------------------------------------------
#  این فایل زیرمنوی «💎 حراجی سایه» (bm:auction) رو از نو می‌سازه و
#  دکمه‌های قدیمیِ «bm:auction» / «bm_auction_buy:» رو (که تو
#  loot_handlers.py ثبت شدن) override می‌کنه — چون
#  register_black_market_shadow_handlers زودتر از اون‌ها صدا زده
#  می‌شه (تو register_loot_handlers).
#
#  قبلاً: هر ۴ آیتمِ SHADOW_AUCTION فقط یه ردیفِ تزئینی تو انبار
#  می‌ذاشتن و به هیچ سیستمِ دیگه‌ای وصل نبودن:
#
#    💎 Soul Stone   → الان مستقیم ماده‌ی واقعیِ crafting_system
#                       ("soul_stone") رو می‌ده که کاتانای Transcendent
#                       و بازغلتوندنِ افیکس بهش نیاز دارن (میان‌بُرِ
#                       گرون‌قیمت به‌جای گرایندِ کیمیاگری).
#    💜 Void Heart    → یه آیتمِ مصرفی می‌شه: اقداماتِ لوتِ فعلیت رو
#                       پر می‌کنه و ۱۰ سهمیه‌ی روزانه‌ی اضافه می‌ده.
#    ⌛/✨ Chrono-Hourglass و Essence of Decider → قیمت‌شون None ـه،
#       یعنی اصلاً از این پنل خریدنی نیستن (فقط رویدادِ خاص) — دست
#       نمی‌خوریم بهشون، فقط نمایش داده می‌شن.
# ============================================================
from __future__ import annotations

from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from economy import SHADOW_AUCTION, bz_to_display
from logger import log_sync
from economy_ledger import record_transaction
import crafting_system as craft

try:
    from loot_handlers import home_button
except Exception:  # جلوگیری از circular import در زمان بارگذاری اولیه
    home_button = lambda: [InlineKeyboardButton(text="🏠 خانه", callback_data="menu:home")]

VOID_HEART_REFILL_BONUS_ACTIONS = 10
SHADOW_ITEM_BY_NAME = {i["name"]: i for i in SHADOW_AUCTION}


def _owned_void_hearts(player: dict) -> int:
    return sum(1 for it in player.get("inventory", [])
               if it.get("name") == "Void Heart" and it.get("type") == "energy_cell")


def _render_auction(player: dict) -> tuple[str, InlineKeyboardMarkup]:
    zen = player.get("zen", 0)
    lines = ["💎 **حراجی سایه — Shadow Brokers**\n"]
    buttons = []
    for i, item in enumerate(SHADOW_AUCTION):
        price_txt = bz_to_display(item["cost"]) if item["cost"] else "قیمت متغیر (فقط رویداد)"
        lines.append(f"{item['emoji']} **{item['name']}** 🟡\n   {item['effect']}\n   💰 {price_txt}\n")
        if item["cost"]:
            buttons.append([InlineKeyboardButton(
                text=f"{item['emoji']} خرید {item['name']} ({price_txt})",
                callback_data=f"bm_auction_buy:{i}", style=ButtonStyle.SUCCESS)])

    vh = _owned_void_hearts(player)
    if vh > 0:
        lines.append(f"\n💜 Void Heartِ مصرف‌نشده: **{vh}**")
        buttons.append([InlineKeyboardButton(
            text=f"🔋 مصرفِ Void Heart (+{VOID_HEART_REFILL_BONUS_ACTIONS} سهمیه‌ی روزانه)",
            callback_data="bm_shadow_use_void_heart", style=ButtonStyle.PRIMARY)])

    lines.append(f"\n💰 موجودی: **{bz_to_display(zen)}**")
    buttons.append([InlineKeyboardButton(text="🔙 برگشت", callback_data="bm:back", style=ButtonStyle.DANGER)])
    buttons.append(home_button())
    return "".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)


async def cb_bm_auction(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    text, kb = _render_auction(player)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        try:
            await cb.message.edit_caption(caption=text, reply_markup=kb)
        except Exception:
            await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


async def cb_bm_auction_buy(cb: CallbackQuery):
    uid = cb.from_user.id
    idx = int(cb.data.split(":")[1])
    player = await aget_player(uid)
    if not player or idx >= len(SHADOW_AUCTION):
        await cb.answer("❌", show_alert=True)
        return
    item = SHADOW_AUCTION[idx]
    cost = item.get("cost", 0)
    if not cost:
        await cb.answer("❌ این آیتم فقط از طریق رویداد خاص در دسترسه!", show_alert=True)
        return
    if player.get("zen", 0) < cost:
        await cb.answer(f"❌ Zen کافی نداری! {bz_to_display(player['zen'])} / {bz_to_display(cost)}", show_alert=True)
        return

    zen_before = player.get("zen", 0)
    player["zen"] -= cost

    if item["name"] == "Soul Stone":
        craft.add_material(player, "soul_stone", 1, item_type="material")
        result_note = "🔮 یه سنگِ‌روحِ واقعی به انبارِ موادت اضافه شد — قابلِ استفاده تو بازغلتوندنِ افیکس / بیداریِ کاتانا."
    elif item["name"] == "Void Heart":
        player.setdefault("inventory", []).append({
            "name": "Void Heart", "emoji": "💜", "type": "energy_cell",
            "effect": item["effect"], "sell": int(cost * 0.4),
        })
        result_note = "💜 Void Heart تو انبارته — از همین پنل مصرفش کن تا اقداماتت پر بشه."
    else:
        player.setdefault("inventory", []).append({
            "name": item["name"], "emoji": item["emoji"], "type": "legendary",
            "effect": item["effect"], "sell": int(cost * 0.7),
        })
        result_note = "✅ به انبارت اضافه شد."

    await asave_player(uid, player)
    record_transaction(
        "bm_shadow_auction_buy", uid, username=player.get("name"),
        item_name=item.get("name"),
        amount=cost, balance_before=zen_before, balance_after=player["zen"],
        note=f"idx={idx}",
    )
    log_sync(
        f"💎 **BM AUCTION BUY**\n👤 {player.get('name','—')} (`{uid}`)\n"
        f"📦 آیتم: {item['name']}\n💰 هزینه: {bz_to_display(cost)}",
        "ECONOMY"
    )
    await cb.answer(f"✅ {item['name']} خریدی!\n{result_note}", show_alert=True)
    await cb_bm_auction(cb)


async def cb_bm_shadow_use_void_heart(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    inv = player.get("inventory", [])
    idx = next((i for i, it in enumerate(inv)
                if it.get("name") == "Void Heart" and it.get("type") == "energy_cell"), None)
    if idx is None:
        await cb.answer("❌ Void Heart نداری.", show_alert=True)
        return
    del inv[idx]

    try:
        from loot_handlers import get_ls, MAX_ACTIONS
        s = get_ls(uid)
        s["actions"] = MAX_ACTIONS
        s["daily_used"] = max(0, s.get("daily_used", 0) - VOID_HEART_REFILL_BONUS_ACTIONS)
        msg = (f"💜 Void Heart مصرف شد! اقداماتِ فعلیت پر شد و "
               f"{VOID_HEART_REFILL_BONUS_ACTIONS} سهمیه‌ی روزانه‌ی اضافه گرفتی.")
    except Exception:
        msg = "💜 Void Heart مصرف شد!"

    await asave_player(uid, player)
    log_sync(f"💜 **VOID HEART USE**\n👤 {player.get('name','—')} (`{uid}`)", "ECONOMY")
    await cb.answer(msg, show_alert=True)
    await cb_bm_auction(cb)


# ─── Register (باید قبلِ ثبتِ bm:auction قدیمیِ پایین صدا زده بشه) ─
def register_black_market_shadow_handlers(dp, bot):
    dp.callback_query.register(cb_bm_auction,              F.data == "bm:auction")
    dp.callback_query.register(cb_bm_auction_buy,           F.data.startswith("bm_auction_buy:"))
    dp.callback_query.register(cb_bm_shadow_use_void_heart, F.data == "bm_shadow_use_void_heart")
