# ============================================================
#  ASTRAL ABYSS RPG — Underground Fight Club Handlers
# ============================================================
import random
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, all_players, asave_player, aget_player
from logger import log_sync
import underground_system as us

STAKES = [1000, 5000, 20000]


async def cmd_hall_of_shame(msg: Message):
    """🩸 تالار ننگ — لیدربوردِ جداگانه‌ی حلقه‌ی سایه، بر اساسِ باخت."""
    uid = msg.from_user.id
    players = all_players()
    ranked = sorted(
        (
            (int(pid), p) for pid, p in players.items()
            if p.get("underground_losses", 0) > 0
        ),
        key=lambda x: (-x[1].get("underground_losses", 0), -x[1].get("underground_wins", 0))
    )
    if not ranked:
        await msg.answer("🩸 **تالار ننگ**\n\nهنوز کسی تو حلقه به‌اندازه‌ی کافی نباخته... اولین قربانی تو باش؟")
        return

    medals = ["💀", "☠️", "🩸", "🥀", "🥀", "⚰️", "⚰️", "🕸️", "🕸️", "🕸️"]
    lines = ["🩸 **تالار ننگ — حلقه‌ی سایه**\n_داور همه‌ی اینا رو یادشه..._\n"]
    my_rank = None
    for i, (pid, p) in enumerate(ranked[:10]):
        w, l = p.get("underground_wins", 0), p.get("underground_losses", 0)
        lines.append(f"{medals[i]} {i+1}. {p.get('name','—')} — {l} باخت / {w} برد")
    for i, (pid, p) in enumerate(ranked):
        if pid == uid:
            my_rank = i + 1
            break
    if my_rank:
        lines.append(f"\n📊 رتبه‌ی ننگِ تو: #{my_rank}")
    await msg.answer("\n".join(lines))


async def cmd_underground(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    from level_gate import check_level
    ok, why = check_level(player, "underground")
    if not ok:
        await msg.answer(why)
        return

    args = msg.text.split() if msg.text.startswith("/underground") else []
    if len(args) < 2:
        ok, why = us.can_fight(player)
        text = (
            "🩸 **حلقه‌ی سایه**\n\n"
            "_یه جای تاریک، دور از قوانینِ رسمیِ PvP. اینجا فقط برد و باخت مهمه — "
            "بازنده علاوه بر Zen، شاید یه آیتم هم از دست بده._\n\n"
            f"{random.choice(us.REFEREE_LINES)}\n\n"
            "📖 `/underground @username مبلغ` بزن تا چالش بدی.\n"
            "🩸 `/hallofshame` رو بزن و تالارِ ننگِ رسواترین بازنده‌های حلقه رو ببین."
        )
        if not ok:
            text += f"\n\n{why}"
        await msg.answer(text)
        return

    await _send_challenge(msg, player, args)


async def _send_challenge(msg: Message, player: dict, args: list[str]):
    uid = msg.from_user.id
    ok, why = us.can_fight(player)
    if not ok:
        await msg.answer(why)
        return
    if len(args) < 3 or not args[2].isdigit():
        await msg.answer("📖 فرمت: `/underground @username مبلغ`")
        return
    stake = int(args[2])
    if stake < 500:
        await msg.answer("❌ حداقل شرط ۵۰۰ Zenه.")
        return
    if player.get("zen", 0) < stake:
        await msg.answer("❌ Zen کافی نداری.")
        return

    from pvp_handlers import _resolve_track_target
    target_id = _resolve_track_target(args[1], uid)
    if not target_id or target_id == uid:
        await msg.answer("❌ هدف نامعتبره.")
        return
    target = await aget_player(target_id)
    if not target or target.get("zen", 0) < stake:
        await msg.answer("❌ این بازیکن یا وجود نداره یا Zen کافی نداره.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🩸 قبول می‌کنم", callback_data=f"ug_acc:{uid}:{target_id}:{stake}", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="❌ نه، فرار می‌کنم", callback_data=f"ug_dec:{uid}:{target_id}", style=ButtonStyle.DANGER)],
    ])
    await msg.answer(f"🩸 چالش تو حلقه‌ی سایه برای **{target.get('name','—')}** فرستاده شد.")
    try:
        from bot import bot as _bot
        await _bot.send_message(
            target_id,
            f"🩸 **{player.get('name','—')}** تو رو به حلقه‌ی سایه دعوت کرده!\n\n"
            f"💰 شرط: {stake:,} Zen\n⚠️ اگه ببازی، ممکنه یه آیتم رندوم هم از دست بدی!",
            reply_markup=kb
        )
    except Exception:
        await msg.answer("⚠️ نتونستم بهش پیام بدم.")


async def cb_ug_accept(cb: CallbackQuery):
    _, challenger_id_s, target_id_s, stake_s = cb.data.split(":")
    challenger_id, target_id, stake = int(challenger_id_s), int(target_id_s), int(stake_s)
    if cb.from_user.id != target_id:
        await cb.answer("❌ این چالش مالِ تو نیست.", show_alert=True)
        return

    challenger = await aget_player(challenger_id)
    target = await aget_player(target_id)
    if not challenger or not target:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    if challenger.get("zen", 0) < stake or target.get("zen", 0) < stake:
        await cb.answer("❌ یکیتون دیگه Zen کافی ندارید.", show_alert=True)
        return

    challenger["id"] = challenger_id
    target["id"] = target_id
    result = us.resolve_fight(challenger, target, stake)
    await asave_player(challenger_id, challenger)
    await asave_player(target_id, target)

    winner = await aget_player(result["winner_id"])
    loser_name = await aget_player(result["loser_id"]).get("name", "—")
    winner_name = winner.get("name", "—")
    item_txt = f"\n💀 آیتمِ **{result['lost_item']['name']}** هم از دست رفت!" if result["lost_item"] else ""

    bonus_txt = ""
    if result.get("bonus_zen"):
        bonus_txt = f"\n😡 **آبیس عصبانیه!** +{result['bonus_zen']:,} Zen بونوسِ اضافه از خشمِ آبیس!"

    text = (
        f"🩸 **نتیجه‌ی حلقه‌ی سایه**\n\n"
        f"🏆 برنده: **{winner_name}**\n💀 بازنده: **{loser_name}**\n"
        f"💰 {result['stake']:,} Zen جابه‌جا شد.{item_txt}{bonus_txt}\n\n"
        f"{result['judge_line']}"
    )
    log_sync(
        f"🩸 **UNDERGROUND FIGHT**\n🏆 {winner_name} (`{result['winner_id']}`) vs 💀 {loser_name} (`{result['loser_id']}`)\n"
        f"💰 {result['stake']:,} | آیتم رفت: {result['lost_item']['name'] if result['lost_item'] else '—'}",
        "UNDERGROUND"
    )
    await cb.answer()
    await cb.message.edit_text(text)
    try:
        await cb.bot.send_message(challenger_id, text)
    except Exception:
        pass


async def cb_ug_decline(cb: CallbackQuery):
    _, challenger_id_s, target_id_s = cb.data.split(":")
    if cb.from_user.id != int(target_id_s):
        await cb.answer("❌", show_alert=True)
        return
    await cb.answer("فرار کردی.")
    await cb.message.edit_text("❌ از حلقه‌ی سایه فرار کردی. داور یادش می‌مونه...")


def register_underground_handlers(dp, bot):
    dp.message.register(cmd_underground, Command("underground"))
    dp.message.register(cmd_hall_of_shame, Command("hallofshame"))
    dp.callback_query.register(cb_ug_accept,  F.data.startswith("ug_acc:"))
    dp.callback_query.register(cb_ug_decline, F.data.startswith("ug_dec:"))
