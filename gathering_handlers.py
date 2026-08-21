# ============================================================
#  ASTRAL ABYSS RPG — Gathering Handlers (Telegram UI)  v1
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from logger import log_sync
import gathering_system as gs


def _owner_ok(cb: CallbackQuery, uid: int) -> bool:
    return cb.from_user.id == uid


def _sites_kb(uid: int, player: dict) -> InlineKeyboardMarkup:
    rows = []
    for site_id, site in gs.SITES.items():
        st = gs.site_status(player, site_id)
        if not st["unlocked"]:
            text, style = f"🔒 {site['name']}", ButtonStyle.DANGER
        elif st["ready"]:
            text, style = f"✅ {site['name']}", ButtonStyle.SUCCESS
        else:
            m, _ = divmod(st["remaining"], 60)
            text, style = f"⏳ {site['name']} ({m}m)", ButtonStyle.PRIMARY
        rows.append([InlineKeyboardButton(text=text, callback_data=f"gth_site:{uid}:{site_id}", style=style)])
    rows.append([InlineKeyboardButton(text="🛠 برو کارگاهِ کرفت", callback_data=f"cft_home:{uid}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cmd_gather(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    await msg.answer(gs.gather_menu_text(player), reply_markup=_sites_kb(uid, player))


async def cb_gather_home(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    await cb.answer()
    await cb.message.edit_text(gs.gather_menu_text(player), reply_markup=_sites_kb(uid, player))


def _choice_kb(uid: int, site_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪶 ملایم", callback_data=f"gth_hit:{uid}:{site_id}:gentle", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="⚖️ متعادل", callback_data=f"gth_hit:{uid}:{site_id}:balanced", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="💥 تهاجمی", callback_data=f"gth_hit:{uid}:{site_id}:aggressive", style=ButtonStyle.DANGER)],
        [InlineKeyboardButton(text="⬅️ برگشت", callback_data=f"gth_home:{uid}", style=ButtonStyle.PRIMARY)],
    ])


async def cb_gather_site(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid, site_id = int(parts[1]), parts[2]
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    st = gs.site_status(player, site_id)
    await cb.answer()
    if st["unlocked"] and st["ready"]:
        await cb.message.edit_text(gs.site_detail_text(player, site_id), reply_markup=_choice_kb(uid, site_id))
    else:
        await cb.message.edit_text(gs.site_detail_text(player, site_id), reply_markup=_sites_kb(uid, player))


async def cb_gather_hit(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid, site_id, choice_key = int(parts[1]), parts[2], parts[3]
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    ok, msg = gs.resolve_gather(uid, player, site_id, choice_key)
    if ok:
        await asave_player(uid, player)
        log_sync(f"🪓 **GATHER**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "CRAFT")
    await cb.answer(msg[:200], show_alert=True)
    player = await aget_player(uid)
    await cb.message.edit_text(gs.gather_menu_text(player), reply_markup=_sites_kb(uid, player))


def register_gathering_handlers(dp, bot):
    dp.message.register(cmd_gather, Command("gather"))
    dp.callback_query.register(cb_gather_home, F.data.startswith("gth_home:"))
    dp.callback_query.register(cb_gather_site, F.data.startswith("gth_site:"))
    dp.callback_query.register(cb_gather_hit, F.data.startswith("gth_hit:"))
