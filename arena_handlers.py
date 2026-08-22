# ============================================================
#  ASTRAL ABYSS RPG — Arena Hub 🏟 (روی سیستمِ لیگِ فصلیِ pvp.py)
# ------------------------------------------------------------
#  سیستمِ امتیاز/لیگ/جایزه‌ی فصلی از قبل تو pvp.py + weekly_rewards.py
#  کامل پیاده‌ست (هر هفته فصل تموم می‌شه، بر اساسِ لیگِ نهایی جایزه
#  می‌گیری، تاریخچه ذخیره می‌شه). این فایل فقط یه هابِ زنده روش
#  می‌سازه: رتبه‌ی واقعیِ خودت بینِ کل بازیکن‌ها، نوارِ پیشرفت تا
#  لیگِ بعدی، و شمارش‌معکوسِ فصل — چیزی که قبلاً نبود.
# ============================================================
import time
import asyncio
from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, all_players, system_col, aget_player
from pvp import league_for_points, next_league_gap, season_reward_for_league

WEEK_SECONDS = 7 * 86400


def _progress_bar(points: int, length: int = 10) -> str:
    next_league, gap = next_league_gap(points)
    if next_league is None:
        return "🟩" * length + "  (سقفِ لیگ)"
    # فاصله‌ی نسبی تا لیگِ بعد رو تخمین می‌زنیم (صرفاً بصری)
    span = max(gap + 50, 50)
    filled = max(0, min(length, round((1 - gap / span) * length)))
    return "🟩" * filled + "⬜" * (length - filled)


def _season_time_left() -> str:
    doc = system_col().find_one({"_id": "weekly_reward"})
    if not doc or not doc.get("last_run"):
        return "نامشخص"
    remaining = (doc["last_run"] + WEEK_SECONDS) - time.time()
    if remaining <= 0:
        return "به‌زودی تموم می‌شه ⏳"
    days = int(remaining // 86400)
    hours = int((remaining % 86400) // 3600)
    if days > 0:
        return f"{days} روز و {hours} ساعت"
    return f"{hours} ساعت"


def _live_rank(uid: int) -> tuple[int, int]:
    """(رتبه، تعدادِ کلِ شرکت‌کننده‌ها) بر اساسِ pvp_season_points زنده."""
    players = all_players()
    ranked = sorted(
        ((int(u), p) for u, p in players.items() if p.get("pvp_season_points", 0) > 0),
        key=lambda kv: kv[1].get("pvp_season_points", 0),
        reverse=True,
    )
    total = len(ranked)
    for i, (u, _) in enumerate(ranked):
        if u == uid:
            return i + 1, total
    return 0, total


def _arena_text(player: dict, uid: int) -> str:
    pts = player.get("pvp_season_points", 0)
    league = league_for_points(pts)
    next_league, gap = next_league_gap(pts)
    projected = season_reward_for_league(league)
    rank, total = _live_rank(uid)

    lines = [
        "🏟 **آرنا — فصلِ جاریِ PvP**\n",
        f"👑 لیگ: {league}",
        f"⚔️ امتیاز: {pts:,}",
        f"📊 پیشرفت: {_progress_bar(pts)}",
    ]
    if next_league:
        lines.append(f"   ↳ {gap:,} امتیاز تا {next_league}")
    if rank:
        lines.append(f"🏅 رتبه‌ی زنده: #{rank} از {total} شرکت‌کننده")
    else:
        lines.append("🏅 هنوز تو رنکینگِ این فصل نیستی — یه دوئل ببر!")
    lines.append(f"⏳ زمان تا پایانِ فصل: {_season_time_left()}")
    lines.append(f"\n🎁 جایزه‌ی تخمینیِ پایانِ فصل: +{projected:,} Zen (تاپ ۳ سرور بونوسِ اضافه هم می‌گیرن)")

    hist = player.get("pvp_season_history", [])
    if hist:
        h = hist[-1]
        lines.append(f"\n📜 فصلِ قبل: رتبه #{h['rank']} — {h['league']} — +{h['reward']:,} Zen")
    return "\n".join(lines)


def _kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏆 لیدربوردِ کاملِ فصل", callback_data="arena_board")],
        [InlineKeyboardButton(text="⚔️ برو دوئل بده", callback_data="arena_to_pvp")],
    ])


async def cmd_arena(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    await msg.answer(_arena_text(player, uid), reply_markup=_kb())


async def cb_arena_board(cb: CallbackQuery):
    players = await asyncio.to_thread(all_players)
    ranked = sorted(
        ((int(u), p) for u, p in players.items() if p.get("pvp_season_points", 0) > 0),
        key=lambda kv: kv[1].get("pvp_season_points", 0),
        reverse=True,
    )[:10]
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    lines = ["🏆 **لیدربوردِ کاملِ فصلِ آرنا:**\n"]
    for i, (u, p) in enumerate(ranked):
        pts = p.get("pvp_season_points", 0)
        league = league_for_points(pts)
        lines.append(f"{medals[i]} **{p.get('name','—')}** — {league} ({pts:,} امتیاز)")
    if not ranked:
        lines.append("هنوز کسی این فصل امتیاز نگرفته — اولین نفر باش!")
    await cb.answer()
    await cb.message.answer("\n".join(lines))


async def cb_arena_to_pvp(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer("⚔️ از دکمه‌ی «PvP» تو منوی اصلی می‌تونی چالش بدی یا لابی بسازی.")


def register_arena_handlers(dp, bot):
    dp.message.register(cmd_arena, Command("arena"))
    dp.callback_query.register(cb_arena_board, F.data == "arena_board")
    dp.callback_query.register(cb_arena_to_pvp, F.data == "arena_to_pvp")
