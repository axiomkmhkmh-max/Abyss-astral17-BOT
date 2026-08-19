# ============================================================
#  ASTRAL ABYSS RPG — Bounty Handlers (Telegram UI)
# ============================================================
from aiogram.filters import Command
from aiogram.types import Message

from database import get_player, save_player
from logger import log_sync
import bounty_system as bs


async def cmd_bounty(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    from level_gate import check_level
    ok, why = check_level(player, "bounty")
    if not ok:
        await msg.answer(why)
        return

    args = msg.text.split(maxsplit=2) if msg.text.startswith("/bounty") else [msg.text]
    # فقط /bounty → لیست جایزه‌های فعال
    if len(args) == 1:
        from daily_wanted import ensure_daily_wanted, get_today_entries
        wanted_today = await ensure_daily_wanted(msg.bot)

        lines = ["🎯 **تابلوی تحت‌تعقیب‌ها**\n"]

        if wanted_today:
            lines.append("🏦 **تحت‌تعقیبِ امروزِ بانک:**")
            for e in wanted_today:
                t = get_player(int(e["uid"]))
                name = t.get("name", f"#{e['uid']}") if t else f"#{e['uid']}"
                status = ""
                if e.get("resolved"):
                    status = " ✅ برد" if e.get("outcome") == "won" else " 💀 باخت"
                mark = " ← خودتی!" if str(uid) == e["uid"] else ""
                lines.append(f"• {name} — 💰 {e['bounty']:,} Zen{status}{mark}")
            lines.append("")

        top = bs.top_bounties(10)
        my_bounty = bs.get_bounty(uid)
        lines.append("💸 **جایزه‌های دستیِ بازیکنا:**")
        if not top:
            lines.append("فعلاً هیچ جایزه‌ی دستی‌ای فعال نیست.")
        else:
            medals = ["🥇", "🥈", "🥉"]
            for i, doc in enumerate(top):
                target = get_player(int(doc["_id"]))
                name = target.get("name", f"#{doc['_id']}") if target else f"#{doc['_id']}"
                medal = medals[i] if i < 3 else f"{i+1}."
                lines.append(f"{medal} {name} — 💰 {doc['amount']:,} Zen")
        if my_bounty.get("amount", 0) > 0:
            lines.append(f"\n⚠️ **رو سرِ خودت {my_bounty['amount']:,} Zen جایزه‌ی دستی‌ست!** مراقب دوئل‌ها باش.")

        my_debt = player.get("bank_debt", 0)
        if my_debt > 0:
            lines.append(f"\n⚖️ بدهیِ تحت‌تعقیبِ خودت به بانک: **{my_debt:,} Zen** (از 🏦 بانک قابلِ پرداخته)")

        lines.append(
            "\n📖 برای گذاشتن جایزه‌ی دستی:\n`/bounty @username مبلغ`\n"
            "هرکی تو PvP اون بازیکن رو شکست بده، کل جایزه رو می‌بره!"
        )
        await msg.answer("\n".join(lines))
        return

    # /bounty @username amount
    target_arg = args[1]
    if len(args) < 3 or not args[2].isdigit():
        await msg.answer("📖 فرمت درست:\n`/bounty @username مبلغ`\nمثلاً: `/bounty @Ali 5000`")
        return
    amount = int(args[2])

    from pvp_handlers import _resolve_target
    target_id = _resolve_target(msg.text, uid)
    if not target_id:
        await msg.answer("❌ این بازیکن پیدا نشد. باید حداقل یه‌بار با ربات شروع کرده باشه.")
        return

    ok, result_msg = bs.place_bounty(player, target_id, amount)
    if ok:
        save_player(uid, player)
        target = get_player(target_id)
        log_sync(
            f"🎯 **BOUNTY PLACED**\n👤 گذارنده: {player.get('name','—')} (`{uid}`)\n"
            f"🎯 هدف: {target.get('name','—') if target else target_id} (`{target_id}`)\n"
            f"💰 مبلغ: {amount:,}",
            "BOUNTY"
        )
    await msg.answer(result_msg)


def register_bounty_handlers(dp, bot):
    dp.message.register(cmd_bounty, Command("bounty"))
