# ============================================================
#  ASTRAL ABYSS — Guild War Handlers (نقشه‌ی جنگِ گیلدها)
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from logger import log_sync
import guild_system as gs
import guild_war_system as gws


async def _edit_or_send(cb: CallbackQuery, text: str, kb: InlineKeyboardMarkup):
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)


def _player_guild_ids(player: dict) -> list[str]:
    return list(player.get("guilds", {}).keys())


# ────────────────────────────────────────────────────────────
# نقشه‌ی جنگ
# ────────────────────────────────────────────────────────────
def _map_kb(uid: int) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for tid, t in gws.TERRITORIES.items():
        row.append(InlineKeyboardButton(text=f"{t['emoji']} {t['name']}", callback_data=f"gw_terr:{tid}:{uid}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🪙 فروشگاهِ جنگ", callback_data=f"gw_shop:{uid}")])
    rows.append([InlineKeyboardButton(text="📊 امتیازِ هفتگی", callback_data=f"gw_score:{uid}")])
    rows.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"gw_backmenu:{uid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cmd_warmap(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    await msg.answer(gws.war_map_text(), reply_markup=_map_kb(uid))


async def cb_gw_map(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    await cb.answer()
    await _edit_or_send(cb, gws.war_map_text(), _map_kb(uid))


async def cb_gw_backmenu(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    await cb.answer()
    text = gs.war_status_text()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺 نقشه‌ی جنگ", callback_data=f"gw_map:{uid}")],
    ])
    await _edit_or_send(cb, text, kb)


async def cb_gw_score(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    await cb.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺 نقشه‌ی جنگ", callback_data=f"gw_map:{uid}")],
    ])
    await _edit_or_send(cb, gs.war_status_text(), kb)


# ────────────────────────────────────────────────────────────
# جزئیاتِ یه قلمرو + حمله/گاریزون
# ────────────────────────────────────────────────────────────
def _terr_kb(tid: str, uid: int, guild_ids: list[str]) -> InlineKeyboardMarkup:
    rows = []
    if not guild_ids:
        rows.append([InlineKeyboardButton(text="⚠️ اول باید عضوِ یه گیلد بشی", callback_data=f"gw_map:{uid}")])
    elif len(guild_ids) == 1:
        gid = guild_ids[0]
        rows.append([
            InlineKeyboardButton(text="⚔️ حمله", callback_data=f"gw_raid:{tid}:{gid}:{uid}", style=ButtonStyle.DANGER),
            InlineKeyboardButton(text="🏕 گاریزون", callback_data=f"gw_garr:{tid}:{gid}:{uid}"),
        ])
    else:
        for gid in guild_ids:
            g = gs.GUILDS[gid]
            rows.append([
                InlineKeyboardButton(text=f"⚔️ حمله ({g['emoji']})", callback_data=f"gw_raid:{tid}:{gid}:{uid}", style=ButtonStyle.DANGER),
                InlineKeyboardButton(text=f"🏕 گاریزون ({g['emoji']})", callback_data=f"gw_garr:{tid}:{gid}:{uid}"),
            ])
    rows.append([InlineKeyboardButton(text="◀️ بازگشت به نقشه", callback_data=f"gw_map:{uid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_gw_terr(cb: CallbackQuery):
    _, tid, uid = cb.data.split(":")
    uid = int(uid)
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return
    await cb.answer()
    await _edit_or_send(cb, gws.territory_detail_text(tid), _terr_kb(tid, uid, _player_guild_ids(player)))


async def cb_gw_raid(cb: CallbackQuery):
    _, tid, gid, uid = cb.data.split(":")
    uid = int(uid)
    if cb.from_user.id != uid:
        await cb.answer("⛔ این دکمه‌ی تو نیست.", show_alert=True)
        return
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return
    ok, note = gws.raid_territory(player, gid, tid)
    await asave_player(uid, player)
    log_sync(f"⚔️ **GUILD WAR RAID** {'✅' if ok else '❌'}\n👤 {player.get('name')} (`{uid}`)\n🏳️ {gid} → {tid}", "GUILDWAR")
    await cb.answer(note[:200], show_alert=True)
    await _edit_or_send(cb, gws.territory_detail_text(tid), _terr_kb(tid, uid, _player_guild_ids(player)))


async def cb_gw_garrison(cb: CallbackQuery):
    _, tid, gid, uid = cb.data.split(":")
    uid = int(uid)
    if cb.from_user.id != uid:
        await cb.answer("⛔ این دکمه‌ی تو نیست.", show_alert=True)
        return
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return
    ok, note = gws.garrison_territory(player, gid, tid)
    await asave_player(uid, player)
    log_sync(f"🏕 **GUILD WAR GARRISON** {'✅' if ok else '❌'}\n👤 {player.get('name')} (`{uid}`)\n🏳️ {gid} → {tid}", "GUILDWAR")
    await cb.answer(note[:200], show_alert=True)
    await _edit_or_send(cb, gws.territory_detail_text(tid), _terr_kb(tid, uid, _player_guild_ids(player)))


# ────────────────────────────────────────────────────────────
# فروشگاهِ جنگی
# ────────────────────────────────────────────────────────────
def _shop_kb(uid: int) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"{i['name']} — {i['cost']}🪙", callback_data=f"gw_buy:{i['id']}:{uid}")] for i in gws.WAR_SHOP]
    rows.append([InlineKeyboardButton(text="◀️ بازگشت به نقشه", callback_data=f"gw_map:{uid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_gw_shop(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return
    await cb.answer()
    await _edit_or_send(cb, gws.war_shop_text(player), _shop_kb(uid))


async def cb_gw_buy(cb: CallbackQuery):
    _, item_id, uid = cb.data.split(":")
    uid = int(uid)
    if cb.from_user.id != uid:
        await cb.answer("⛔ این دکمه‌ی تو نیست.", show_alert=True)
        return
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return
    ok, note = gws.buy_war_item(player, item_id)
    if ok:
        await asave_player(uid, player)
        log_sync(f"🪙 **WAR SHOP BUY**\n👤 {player.get('name')} (`{uid}`)\n🛍 {item_id}", "GUILDWAR")
    await cb.answer(note[:200], show_alert=True)
    await _edit_or_send(cb, gws.war_shop_text(player), _shop_kb(uid))


# ────────────────────────────────────────────────────────────
def register_guild_war_handlers(dp, bot):
    dp.message.register(cmd_warmap, Command("warmap"))
    dp.callback_query.register(cb_gw_map, F.data.startswith("gw_map:"))
    dp.callback_query.register(cb_gw_backmenu, F.data.startswith("gw_backmenu:"))
    dp.callback_query.register(cb_gw_score, F.data.startswith("gw_score:"))
    dp.callback_query.register(cb_gw_terr, F.data.startswith("gw_terr:"))
    dp.callback_query.register(cb_gw_raid, F.data.startswith("gw_raid:"))
    dp.callback_query.register(cb_gw_garrison, F.data.startswith("gw_garr:"))
    dp.callback_query.register(cb_gw_shop, F.data.startswith("gw_shop:"))
    dp.callback_query.register(cb_gw_buy, F.data.startswith("gw_buy:"))
