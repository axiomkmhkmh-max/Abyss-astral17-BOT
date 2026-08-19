# ============================================================
#  ASTRAL ABYSS — Battle Pass Handlers
# ============================================================
from aiogram import Dispatcher, Bot, F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from database import get_player, save_player
import battle_pass as bp


def _days_left() -> int:
    return max(1, bp.season_seconds_left() // 86400)


def _bp_text(player: dict) -> str:
    tier = bp.current_tier(player)
    bar = bp.progress_bar(player)
    left = bp.points_to_next_tier(player)
    prem = "💎 فعال" if bp.has_premium(player) else "🔒 غیرفعال"
    lines = [
        f"🎫 **پس نبرد — فصل {bp.current_season()}**\n",
        f"{bar}  تایر {tier}/{bp.MAX_TIER}\n",
        f"✨ امتیاز: {player.get('bp_points', 0):,}",
    ]
    if left:
        lines.append(f"({left:,} امتیاز تا تایر بعدی)")
    lines.append(f"\n💎 ردِ پرمیوم: {prem}")
    lines.append(f"⏳ پایانِ فصل: حدوداً {_days_left()} روز دیگه")
    free_claimable = bp.claimable_free_tiers(player)
    prem_claimable = bp.claimable_premium_tiers(player)
    if free_claimable or prem_claimable:
        lines.append(f"\n🎁 {len(free_claimable) + len(prem_claimable)} جایزه‌ی آماده‌ی دریافت داری!")
    return "\n".join(lines)


def _bp_kb(player: dict) -> InlineKeyboardMarkup:
    rows = []
    if bp.claimable_free_tiers(player) or bp.claimable_premium_tiers(player):
        rows.append([InlineKeyboardButton(text="🎁 دریافت جوایز", callback_data="bp:claim_menu", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _claim_kb(player: dict) -> InlineKeyboardMarkup:
    rows = []
    for t in bp.claimable_free_tiers(player):
        rows.append([InlineKeyboardButton(text=f"🎁 تایر {t} (رایگان)", callback_data=f"bp:free:{t}", style=ButtonStyle.SUCCESS)])
    for t in bp.claimable_premium_tiers(player):
        rows.append([InlineKeyboardButton(text=f"💎 تایر {t} (پرمیوم)", callback_data=f"bp:prem:{t}", style=ButtonStyle.SUCCESS)])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="bp:back", style=ButtonStyle.DANGER)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cmd_battle_pass(msg: Message):
    player = get_player(msg.from_user.id)
    if not player:
        await msg.answer("❌ اول باید شخصیت بسازی!")
        return
    save_player(msg.from_user.id, player)
    await msg.answer(_bp_text(player), reply_markup=_bp_kb(player))


async def cb_bp_claim_menu(cb: CallbackQuery):
    player = get_player(cb.from_user.id)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    if not (bp.claimable_free_tiers(player) or bp.claimable_premium_tiers(player)):
        await cb.answer("چیزی برای دریافت نیست!", show_alert=True)
        return
    await cb.message.edit_text("🎁 **جوایزِ آماده‌ی دریافت:**", reply_markup=_claim_kb(player))
    await cb.answer()


async def cb_bp_back(cb: CallbackQuery):
    player = get_player(cb.from_user.id)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    await cb.message.edit_text(_bp_text(player), reply_markup=_bp_kb(player))
    await cb.answer()


async def cb_bp_claim_free(cb: CallbackQuery):
    uid = cb.from_user.id
    tier = int(cb.data.split(":")[2])
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    result = bp.claim_free(player, tier)
    save_player(uid, player)
    if not result:
        await cb.answer("❌ این جایزه قبلاً گرفته شده یا هنوز باز نشده!", show_alert=True)
        return
    msg = f"🎁 +{result['zen']:,} Zen"
    if result.get("title"):
        msg += f"\n🏅 عنوانِ جدید: {result['title']}"
    await cb.answer(msg, show_alert=True)
    await cb.message.edit_text(_bp_text(player), reply_markup=_bp_kb(player))


async def cb_bp_claim_premium(cb: CallbackQuery):
    uid = cb.from_user.id
    tier = int(cb.data.split(":")[2])
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    result = bp.claim_premium(player, tier)
    save_player(uid, player)
    if not result:
        await cb.answer("❌ این جایزه قبلاً گرفته شده یا نیاز به پس پرمیوم داره!", show_alert=True)
        return
    await cb.answer(f"💎 +{result['zen']:,} Zen", show_alert=True)
    await cb.message.edit_text(_bp_text(player), reply_markup=_bp_kb(player))


# ─── دستورِ ادمین برای فعال‌کردنِ دستیِ پرمیوم (تا وقتی درگاهِ پرداخت وصل بشه) ──
async def cmd_grant_pass(msg: Message):
    from admin_panel import is_admin
    if not is_admin(msg):
        await msg.answer("❌ فقط ادمین!")
        return
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        await msg.answer("📝 استفاده: `/grantpass user_id`")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await msg.answer("❌ آیدی عددی وارد کن.")
        return
    player = get_player(target_id)
    if not player:
        await msg.answer("❌ بازیکن پیدا نشد.")
        return
    bp.grant_premium(player)
    save_player(target_id, player)
    await msg.answer(f"✅ پسِ پرمیوم برای {target_id} فعال شد.")


def register_battle_pass_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_battle_pass, F.text == "پس نبرد")
    dp.message.register(cmd_battle_pass, Command("battlepass"))
    dp.message.register(cmd_grant_pass, Command("grantpass"))
    dp.callback_query.register(cb_bp_claim_menu, F.data == "bp:claim_menu")
    dp.callback_query.register(cb_bp_back, F.data == "bp:back")
    dp.callback_query.register(cb_bp_claim_free, F.data.startswith("bp:free:"))
    dp.callback_query.register(cb_bp_claim_premium, F.data.startswith("bp:prem:"))
