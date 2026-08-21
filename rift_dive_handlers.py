# ============================================================
#  ASTRAL ABYSS RPG — Rift Dive Handlers (Telegram UI) 🌀
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from logger import log_sync
from action_lock import no_double_tap
import rift_dive_system as rd

ROOM_LABELS = {
    "combat":   "⚔️ راهرو — دشمن!",
    "elite":    "👹 اتاقِ نخبه!",
    "treasure": "📦 اتاقِ گنج",
    "shrine":   "🕍 معبدِ انتخاب",
    "rest":     "🕯 اتاقِ استراحت",
}


def _hp_bar(run: dict, length: int = 10) -> str:
    pct = max(0.0, run["rift_hp"] / max(1.0, run["rift_hp_max"]))
    filled = round(pct * length)
    return "🟥" * filled + "⬛" * (length - filled)


def _status_text(player: dict) -> str:
    run = player.get("rift_run")
    if not run or not run.get("active"):
        best = player.get("rift_best_depth", 0)
        best_wk = player.get("rift_best_depth_week", 0)
        shards = player.get("rift_shards", 0)
        return (
            "🌀 **شکافِ Abyss (Rift Dive)**\n\n"
            "یه شکاف باز می‌شه، اتاق‌به‌اتاق پیش می‌ری. هر چند اتاق یه دروازه‌ی\n"
            "خروج داری: یا پاداش رو **بردار** یا ریسک کن و **عمیق‌تر برو**.\n"
            "اگه بین دو دروازه بمیری، فقط چیزی که آخرین بار برداشتی می‌مونه.\n\n"
            f"🏆 رکوردِ کلی: عمقِ {best}\n"
            f"📅 رکوردِ این هفته: عمقِ {best_wk}\n"
            f"🔹 Echo Shard: {shards:,}\n"
        )
    depth = run["depth"]
    text = (
        f"🌀 **شکافِ Abyss** — عمقِ {depth}\n"
        f"❤️ {_hp_bar(run)} ({run['rift_hp']:.0f}/{run['rift_hp_max']:.0f})\n"
        f"💰 در انتظار: {run['pending_zen']:,} Zen | 🔹{run['pending_shards']} | 📦{len(run['pending_items'])}\n"
        f"🏦 بانک‌شده: {run['banked_zen']:,} Zen | 🔹{run['banked_shards']} | 📦{len(run['banked_items'])}\n"
    )
    if run.get("blessings"):
        names = [rd.SHRINE_OPTIONS[b]["name"] for b in run["blessings"] if b in rd.SHRINE_OPTIONS]
        text += "✨ " + " | ".join(names) + "\n"
    if run.get("log"):
        text += "\n" + "\n".join(run["log"])
    return text


def _kb(player: dict) -> InlineKeyboardMarkup:
    run = player.get("rift_run")
    if not run or not run.get("active"):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌀 ورود به شکاف", callback_data="rift_start", style=ButtonStyle.SUCCESS)],
            [InlineKeyboardButton(text="🏆 لیدربوردِ هفتگی", callback_data="rift_board", style=ButtonStyle.PRIMARY)],
        ])

    room = run.get("room")
    rows = []
    if room and room["type"] == "shrine" and not room.get("resolved"):
        for opt_id in room["options"]:
            opt = rd.SHRINE_OPTIONS[opt_id]
            rows.append([InlineKeyboardButton(
                text=f"{opt['name']} — {opt['desc']}",
                callback_data=f"rift_shrine:{opt_id}", style=ButtonStyle.PRIMARY)])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    if room is None or room.get("resolved"):
        rows.append([InlineKeyboardButton(text="➡️ اتاقِ بعدی", callback_data="rift_next", style=ButtonStyle.SUCCESS)])
        if rd.is_extraction_gate(player):
            rows.append([InlineKeyboardButton(text="💰 برداشتِ پاداش (بمون)", callback_data="rift_extract", style=ButtonStyle.PRIMARY)])
        rows.append([InlineKeyboardButton(text="🚪 خروج و ذخیره (پایانِ ران)", callback_data="rift_cashout", style=ButtonStyle.DANGER)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cmd_riftdive(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    await msg.answer(_status_text(player), reply_markup=_kb(player))


@no_double_tap()
async def cb_rift_start(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    ok, why = rd.can_start(player)
    if not ok:
        await cb.answer(why, show_alert=True)
        return
    rd.start_run(player)
    await asave_player(uid, player)
    await cb.answer("🌀 شکاف باز شد! برو داخل...")
    await cb.message.edit_text(_status_text(player), reply_markup=_kb(player))


@no_double_tap()
async def cb_rift_next(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    run = player.get("rift_run")
    if not run or not run.get("active"):
        await cb.answer("❌ ران فعالی نداری.", show_alert=True)
        return

    room = rd.enter_next_room(player)
    if room["type"] == "shrine":
        await asave_player(uid, player)
        await cb.answer(ROOM_LABELS["shrine"])
        await cb.message.edit_text(_status_text(player), reply_markup=_kb(player))
        return

    result = rd.resolve_current_room(player)
    header = ROOM_LABELS.get(room["type"], "اتاق")

    if result["dead"]:
        summary = rd.finalize_run(player, died=True)
        await asave_player(uid, player)
        log_sync(
            f"🌀 **RIFT DIVE — DEATH**\n👤 {player.get('name','—')} (`{uid}`)\n"
            f"📉 عمق: {summary['depth_reached']} | 💰 نجات‌یافته: {summary['zen_gain']:,} Zen | "
            f"❌ ازدست‌رفته: {summary['lost_pending_zen']:,} Zen",
            "RIFT"
        )
        text = (
            f"{header}\n\n" + "\n".join(result["log"]) + "\n\n"
            f"☠️ **رانت تموم شد.**\n"
            f"عمقِ رسیده: {summary['depth_reached']}\n"
            f"💰 نجات‌یافته (بانک‌شده): {summary['zen_gain']:,} Zen | 🔹{summary['shard_gain']}\n"
            f"❌ ازدست‌رفته: {summary['lost_pending_zen']:,} Zen | 🔹{summary['lost_pending_shards']}\n"
            f"📦 تجهیزاتِ دریافتی: {summary['items_gained']}"
        )
        await cb.answer("☠️ مردی!", show_alert=True)
        await cb.message.edit_text(text, reply_markup=_kb(player))
        return

    await asave_player(uid, player)
    await cb.answer(header)
    await cb.message.edit_text(_status_text(player), reply_markup=_kb(player))


@no_double_tap()
async def cb_rift_shrine(cb: CallbackQuery):
    uid = cb.from_user.id
    opt_id = cb.data.split(":")[1]
    player = await aget_player(uid)
    if not player.get("rift_run"):
        await cb.answer("❌ ران فعالی نداری.", show_alert=True)
        return
    log = rd.choose_shrine(player, opt_id)
    await asave_player(uid, player)
    await cb.answer(log[0] if log else "")
    await cb.message.edit_text(_status_text(player), reply_markup=_kb(player))


@no_double_tap()
async def cb_rift_extract(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    run = player.get("rift_run")
    if not run or not rd.is_extraction_gate(player):
        await cb.answer("❌ الان دروازه‌ی خروج فعال نیست.", show_alert=True)
        return
    banked = rd.extract_at_gate(player)
    await asave_player(uid, player)
    await cb.answer(f"🏦 بانک شد: +{banked['zen']:,} Zen | +{banked['shards']} 🔹", show_alert=True)
    await cb.message.edit_text(_status_text(player), reply_markup=_kb(player))


@no_double_tap()
async def cb_rift_cashout(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    run = player.get("rift_run")
    if not run or not run.get("active"):
        await cb.answer("❌ ران فعالی نداری.", show_alert=True)
        return
    summary = rd.finalize_run(player, died=False)
    await asave_player(uid, player)
    log_sync(
        f"🌀 **RIFT DIVE — CASH OUT**\n👤 {player.get('name','—')} (`{uid}`)\n"
        f"📉 عمق: {summary['depth_reached']} | 💰 {summary['zen_gain']:,} Zen | 🔹{summary['shard_gain']} | 📦{summary['items_gained']}",
        "RIFT"
    )
    text = (
        f"✅ **با موفقیت از شکاف خارج شدی!**\n\n"
        f"عمقِ رسیده: {summary['depth_reached']}\n"
        f"💰 +{summary['zen_gain']:,} Zen | 🔹+{summary['shard_gain']} Shard | 📦+{summary['items_gained']} آیتم"
    )
    await cb.answer("✅ ذخیره شد!")
    await cb.message.edit_text(text, reply_markup=_kb(player))


async def cb_rift_board(cb: CallbackQuery):
    top = rd.get_leaderboard(10)
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    lines = ["🏆 **لیدربوردِ هفتگیِ شکاف:**\n"]
    for i, p in enumerate(top):
        lines.append(f"{medals[i]} **{p.get('name','—')}** — عمقِ {p.get('rift_best_depth_week',0)}")
    if not top:
        lines.append("هنوز کسی این هفته وارد شکاف نشده — اولین نفر باش!")
    await cb.answer()
    await cb.message.answer("\n".join(lines))


def register_rift_dive_handlers(dp, bot):
    dp.message.register(cmd_riftdive, Command("riftdive"))
    dp.callback_query.register(cb_rift_start, F.data == "rift_start")
    dp.callback_query.register(cb_rift_next, F.data == "rift_next")
    dp.callback_query.register(cb_rift_shrine, F.data.startswith("rift_shrine:"))
    dp.callback_query.register(cb_rift_extract, F.data == "rift_extract")
    dp.callback_query.register(cb_rift_cashout, F.data == "rift_cashout")
    dp.callback_query.register(cb_rift_board, F.data == "rift_board")
