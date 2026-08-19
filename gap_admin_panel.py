# ============================================================
#  ASTRAL ABYSS — Gap Admin Panel
# ------------------------------------------------------------
#  ادمین‌های گپ با ادمین‌های تلگرام یکی نیستن (چون uid داخلیِ
#  پلیرهای گپ منفیه و از فضای ADMIN_IDS تلگرام جداست). آیدیِ
#  ادمین‌های گپ (همون chat_id واقعیِ گپ‌شون، عدد مثبت) رو تو
#  GAP_ADMIN_IDS بریز، مثلاً:
#     GAP_ADMIN_IDS=123456,654321
#
#  دستورها (تو چت گپ به ربات بفرست):
#     /admin                    → داشبورد
#     /stats                    → آمار کلی بازیکن‌ها
#     /broadcast <متن>          → پیام همگانی به همه‌ی پلیرهای گپ
#     /ban <chat_id> [دلیل]
#     /unban <chat_id>
#     /givezen <chat_id> <عدد>
#     /givexp <chat_id> <عدد>
#     /info <chat_id>
# ============================================================
from __future__ import annotations

import asyncio
import os

from gap_dispatcher import GapDispatcher
from gap_types import Message, gap_uid, gap_only_players

from database import get_player, save_player, all_players
from logger import log_sync

GAP_ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("GAP_ADMIN_IDS", "").split(",") if x.strip().isdigit()
}


def is_gap_admin(msg: Message) -> bool:
    return msg.from_user.chat_id in GAP_ADMIN_IDS


def _gap_players(all_docs: dict) -> dict:
    """فقط پلیرهایی که uidِ منفی دارن (یعنی از گپ اومدن) — الان از
    gap_types.gap_only_players میاد تا بینِ همه‌ی ماژول‌های گپ مشترک باشه."""
    return gap_only_players(all_docs)


def register_gap_admin_handlers(dp: GapDispatcher):

    @dp.message(commands=["admin"])
    async def cmd_admin(msg: Message):
        if not is_gap_admin(msg):
            return await msg.answer("❌ فقط ادمین.")
        await msg.answer(
            "🛠 **پنل ادمین گپ**\n\n"
            "/stats — آمار بازیکن‌ها\n"
            "/broadcast <متن> — پیام همگانی\n"
            "/ban <chat_id> [دلیل]\n"
            "/unban <chat_id>\n"
            "/givezen <chat_id> <عدد>\n"
            "/givexp <chat_id> <عدد>\n"
            "/info <chat_id>\n"
            "/audit [chat_id|kind] [kind] — آدیتِ تراکنش‌های بازار سیاه/حراجی"
        )

    @dp.message(commands=["audit"])
    async def cmd_audit(msg: Message):
        if not is_gap_admin(msg):
            return await msg.answer("❌ فقط ادمین.")
        from economy_ledger import get_recent_transactions, get_user_transactions
        from economy import bz_to_display
        import time as _time
        parts = msg.text.split(maxsplit=2)
        uid_filter = None
        kind_filter = None
        if len(parts) >= 2:
            if parts[1].isdigit():
                uid_filter = gap_uid(int(parts[1]))
                if len(parts) >= 3:
                    kind_filter = parts[2].strip()
            else:
                kind_filter = parts[1].strip()

        if uid_filter is not None:
            txs = get_user_transactions(uid_filter, limit=50)
            if kind_filter:
                txs = [t for t in txs if t.get("kind") == kind_filter]
            txs = txs[:25]
            title = f"🧾 **آدیتِ تراکنش‌های** `{parts[1]}`" + (f" — نوع: `{kind_filter}`" if kind_filter else "")
        else:
            txs = get_recent_transactions(kind=kind_filter, limit=25)
            title = "🧾 **آخرین تراکنش‌های اقتصادی (بازار سیاه/حراجی)**" + (f" — نوع: `{kind_filter}`" if kind_filter else "")

        if not txs:
            return await msg.answer(f"{title}\n\nهیچ تراکنشی پیدا نشد.")

        lines = [title, ""]
        for t in txs:
            ts = _time.strftime("%m/%d %H:%M", _time.localtime(t.get("ts", 0)))
            fee_note = f" (کارمزد {bz_to_display(t.get('fee'))})" if t.get("fee") else ""
            note_note = f" — {t.get('note')}" if t.get("note") else ""
            lines.append(
                f"`{ts}` **{t.get('kind')}** uid=`{t.get('user_id')}`\n"
                f"   📦 {t.get('item_name') or '—'} × {t.get('quantity',1)} — 💰 {bz_to_display(t.get('amount',0))}{fee_note}\n"
                f"   💵 {t.get('balance_before')} → {t.get('balance_after')}{note_note}"
            )
        text = "\n".join(lines)
        if len(text) > 3800:
            text = text[:3800] + "\n… (بریده شد)"
        await msg.answer(text)

    @dp.message(commands=["stats"])
    async def cmd_stats(msg: Message):
        if not is_gap_admin(msg):
            return await msg.answer("❌ فقط ادمین.")
        players = _gap_players(all_players())
        total = len(players)
        with_char = sum(1 for p in players.values() if p.get("character"))
        banned = sum(1 for p in players.values() if p.get("banned"))
        await msg.answer(
            f"📊 **آمار گپ**\n"
            f"👥 کل بازیکن‌ها: {total}\n"
            f"🎴 با کاراکتر: {with_char}\n"
            f"🚫 بن‌شده: {banned}"
        )

    @dp.message(commands=["broadcast"])
    async def cmd_broadcast(msg: Message):
        if not is_gap_admin(msg):
            return await msg.answer("❌ فقط ادمین.")
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2:
            return await msg.answer("❌ استفاده: `/broadcast متن پیام`")
        text = parts[1]
        players = _gap_players(all_players())
        sent = failed = 0
        for pid in players:
            chat_id = -int(pid)  # برگردوندنِ uid منفی به chat_id واقعیِ گپ
            try:
                await msg.bot.send_message(chat_id, f"📢 {text}")
                sent += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.05)  # rate-limit ملایم
        await msg.answer(f"✅ ارسال شد به {sent} نفر ({failed} ناموفق).")
        log_sync(f"📢 **BROADCAST (GAP)** توسط `{msg.from_user.chat_id}`\n{text}", "ADMIN")

    @dp.message(commands=["ban"])
    async def cmd_ban(msg: Message):
        if not is_gap_admin(msg):
            return await msg.answer("❌ فقط ادمین.")
        parts = msg.text.split(maxsplit=2)
        if len(parts) < 2 or not parts[1].isdigit():
            return await msg.answer("❌ استفاده: `/ban <chat_id> [دلیل]`")
        target = gap_uid(int(parts[1]))
        player = get_player(target)
        if not player:
            return await msg.answer("❌ بازیکن پیدا نشد.")
        player["banned"] = True
        player["ban_reason"] = parts[2].strip() if len(parts) > 2 else None
        save_player(target, player)
        await msg.answer(f"✅ {player.get('name', target)} بن شد.")
        log_sync(f"🚫 **BAN (GAP)** `{parts[1]}` توسط ادمین `{msg.from_user.chat_id}`", "BAN")

    @dp.message(commands=["unban"])
    async def cmd_unban(msg: Message):
        if not is_gap_admin(msg):
            return await msg.answer("❌ فقط ادمین.")
        parts = msg.text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            return await msg.answer("❌ استفاده: `/unban <chat_id>`")
        target = gap_uid(int(parts[1]))
        player = get_player(target)
        if not player:
            return await msg.answer("❌ بازیکن پیدا نشد.")
        player["banned"] = False
        player["ban_reason"] = None
        save_player(target, player)
        await msg.answer(f"✅ {player.get('name', target)} آنبن شد.")
        log_sync(f"✅ **UNBAN (GAP)** `{parts[1]}` توسط ادمین `{msg.from_user.chat_id}`", "BAN")

    @dp.message(commands=["givezen"])
    async def cmd_givezen(msg: Message):
        if not is_gap_admin(msg):
            return await msg.answer("❌ فقط ادمین.")
        parts = msg.text.split()
        if len(parts) < 3 or not parts[1].isdigit() or not parts[2].lstrip("-").isdigit():
            return await msg.answer("❌ استفاده: `/givezen <chat_id> <عدد>`")
        target = gap_uid(int(parts[1]))
        amount = int(parts[2])
        player = get_player(target)
        if not player:
            return await msg.answer("❌ بازیکن پیدا نشد.")
        player["zen"] = player.get("zen", 0) + amount
        save_player(target, player)
        await msg.answer(f"✅ {amount:+} Zen به {player.get('name', target)} داده شد. (موجودی: {player['zen']})")

    @dp.message(commands=["givexp"])
    async def cmd_givexp(msg: Message):
        if not is_gap_admin(msg):
            return await msg.answer("❌ فقط ادمین.")
        parts = msg.text.split()
        if len(parts) < 3 or not parts[1].isdigit() or not parts[2].lstrip("-").isdigit():
            return await msg.answer("❌ استفاده: `/givexp <chat_id> <عدد>`")
        target = gap_uid(int(parts[1]))
        amount = int(parts[2])
        player = get_player(target)
        if not player:
            return await msg.answer("❌ بازیکن پیدا نشد.")
        player["xp"] = player.get("xp", 0) + amount
        save_player(target, player)
        await msg.answer(f"✅ {amount:+} XP به {player.get('name', target)} داده شد.")

    @dp.message(commands=["info"])
    async def cmd_info(msg: Message):
        if not is_gap_admin(msg):
            return await msg.answer("❌ فقط ادمین.")
        parts = msg.text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            return await msg.answer("❌ استفاده: `/info <chat_id>`")
        target = gap_uid(int(parts[1]))
        player = get_player(target)
        if not player:
            return await msg.answer("❌ بازیکن پیدا نشد.")
        await msg.answer(
            f"👤 **{player.get('name','—')}**\n"
            f"🆔 chat_id: `{parts[1]}`\n"
            f"🎴 کاراکتر: {player.get('character','—')}\n"
            f"📊 سطح: {player.get('level',1)} | XP: {player.get('xp',0)}\n"
            f"💰 Zen: {player.get('zen',0)}\n"
            f"🚫 بن: {'بله — ' + str(player.get('ban_reason')) if player.get('banned') else 'خیر'}"
        )
