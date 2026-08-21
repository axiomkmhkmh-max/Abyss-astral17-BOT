# ============================================================
#  ASTRAL ABYSS — Admin Panel 
# ============================================================
import asyncio
import time
from functools import wraps

from aiogram import Dispatcher, Bot, F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import (
    Message, CallbackQuery, TelegramObject,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from characters import ALL_CHARACTERS, SPECIAL_CHARACTERS, MYTHIC_CHARACTERS
from divine_seals import DIVINE_SEALS, SEAL_EMOJI, find_seal_id
from database import (
    get_player, save_player, all_players,
    get_boss, save_boss, assign_random_char, assign_special_char,
    get_seal_holder, assign_seal_holder, full_reset_player, release_char,
    aget_player, asave_player,
)
from economy import bz_to_display
from game_data import xp_for_level
from logger import log_sync

import os as _os


def _parse_id_list(env_name: str) -> set[int]:
    raw = _os.getenv(env_name, "")
    out = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


ADMIN_IDS = {
    8344095451,
    8262319046,
} | _parse_id_list("ADMIN_EXTRA_IDS")
OWNER_IDS = {
    8262319046,
    8344095451,
} | _parse_id_list("OWNER_EXTRA_IDS") | _parse_id_list("ADMIN_EXTRA_IDS")

ADMIN_USERNAMES = {"ruinedbara"} | {
    u.strip().lstrip("@").lower()
    for u in _os.getenv("ADMIN_EXTRA_USERNAMES", "").split(",") if u.strip()
}

_pending_reset: dict[int, tuple[int, bool]] = {}  # admin_id -> (target_id, want_new_char)
_pending_reset_all: dict[int, bool] = {}

# ─── پنل یکپارچه‌ی ویرایش پلیر: {admin_id: {"action": str, "target_id": int}} ───
# وقتی ادمین روی دکمه‌ای مثل «➕ XP بده» می‌زنه، اینجا ثبت می‌شه که منتظرِ چه
# ورودی‌ای از همون ادمینه؛ پیام متنیِ بعدی‌ای که همون ادمین می‌فرسته (و کوماند
# نیست) به‌عنوان مقدار همون اکشن مصرف می‌شه.
_pending_action: dict[int, dict] = {}


def is_admin(event) -> bool:
    # ─── باگ‌فیکس امنیتی: قبلاً اگه یوزرنیمِ کاربر با ADMIN_USERNAMES
    # یکی می‌بود، ادمین حساب می‌شد. یوزرنیمِ تلگرام قابل‌تغییره و بعد از
    # رها شدن توسطِ صاحبِ اصلی، هر کسِ دیگه‌ای می‌تونه بگیرتش — یعنی اگه
    # یه ادمین یوزرنیمش رو عوض می‌کرد، هر کاربرِ دیگه‌ای که بعداً همون
    # یوزرنیم رو می‌گرفت خودکار دسترسیِ ادمین پیدا می‌کرد. الان فقط
    # آیدیِ عددی (که تغییر نمی‌کنه) ملاکِ ادمین‌بودنه.
    user = getattr(event, "from_user", None)
    if user is None:
        return False
    return user.id in ADMIN_IDS


def is_owner(event) -> bool:
    user = getattr(event, "from_user", None)
    return bool(user and user.id in OWNER_IDS)


def admin_only(func):
    @wraps(func)
    async def wrapper(event, *args, **kwargs):
        if not is_admin(event):
            if isinstance(event, CallbackQuery):
                return await event.answer("❌ فقط ادمین", show_alert=True)
            return await event.answer("❌ فقط ادمین")
        return await func(event, *args, **kwargs)
    return wrapper


class BanMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = getattr(event, "from_user", None)
        if user is None or is_admin(event):
            return await handler(event, data)
        player = await aget_player(user.id)
        if player and player.get("banned"):
            return
        return await handler(event, data)


def resolve_target_id(arg: str) -> int | None:
    try:
        return int(arg.strip().lstrip("@"))
    except (ValueError, AttributeError):
        return None


def find_character_name(query: str) -> str | None:
    if query in ALL_CHARACTERS:
        return query
    q = query.lower()
    for name in ALL_CHARACTERS:
        if name.lower() == q:
            return name
    return None


def _format_last_seen(target_id: int) -> str:
    try:
        from bot import last_seen, OFFLINE_THRESHOLD
    except Exception:
        return "—"
    ts = last_seen.get(target_id)
    if not ts:
        return "نامشخص"
    delta = time.time() - ts
    if delta < OFFLINE_THRESHOLD:
        return "🟢 آنلاین"
    mins = int(delta // 60)
    if mins < 60:
        return f"🔴 {mins} دقیقه پیش"
    hours = mins // 60
    if hours < 48:
        return f"🔴 {hours} ساعت پیش"
    return f"🔴 {hours // 24} روز پیش"


def player_summary(target_id: int, player: dict) -> str:
    char_name = player.get("character", "—")
    banned    = "🚫 بله" if player.get("banned") else "✅ خیر"
    seal_id   = player.get("divine_seal")
    seal_line = f"🔱 مُهر: **{DIVINE_SEALS[seal_id]['name']}**\n" if seal_id in DIVINE_SEALS else ""
    note      = player.get("admin_note")
    note_line = f"📝 یادداشت: _{note}_\n" if note else ""
    return (
        f"👤 **{player.get('name','—')}** (`{target_id}`)\n"
        f"{'─'*22}\n"
        f"🎴 کاراکتر: **{char_name}**\n"
        f"{seal_line}"
        f"⭐ سطح: **{player.get('level',1)}** | ✨ XP: {player.get('xp',0):,}\n"
        f"❤️ HP: {player.get('hp',100)}/{player.get('max_hp',100)}\n"
        f"💰 Zen: **{bz_to_display(player.get('zen',0))}**\n"
        f"🗡 کاتانا Lv.{player.get('katana_level',1)}\n"
        f"💀 کشته: {player.get('kills',0)} | 🆚 PvP: {player.get('pvp_wins',0)}\n"
        f"🎒 آیتم‌ها: {len(player.get('inventory',[]))}\n"
        f"🕒 وضعیت: {_format_last_seen(target_id)}\n"
        f"{note_line}"
        f"🚫 بن: {banned}"
    )


def player_editor_kb(target_id: int, banned: bool) -> InlineKeyboardMarkup:
    ban_btn = (
        InlineKeyboardButton(text="✅ آنبن", callback_data=f"padm:unban:{target_id}", style=ButtonStyle.SUCCESS)
        if banned else
        InlineKeyboardButton(text="🚫 بن", callback_data=f"padm:ban:{target_id}", style=ButtonStyle.DANGER)
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✨ XP", callback_data=f"padm:xp:{target_id}", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton(text="💰 Zen", callback_data=f"padm:zen:{target_id}", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton(text="❤️ HP", callback_data=f"padm:hp:{target_id}", style=ButtonStyle.PRIMARY),
        ],
        [
            InlineKeyboardButton(text="🎴 کاراکتر", callback_data=f"padm:char:{target_id}", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton(text="🎒 آیتم‌ها", callback_data=f"padm:items:{target_id}", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton(text="📝 یادداشت", callback_data=f"padm:note:{target_id}", style=ButtonStyle.PRIMARY),
        ],
        [ban_btn, InlineKeyboardButton(text="🔄 ریست", callback_data=f"padm:reset:{target_id}", style=ButtonStyle.DANGER)],
        [InlineKeyboardButton(text="❌ بستن", callback_data="padm:close", style=ButtonStyle.DANGER)],
    ])


def admin_dashboard_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 آمار کلی",        callback_data="admin:stats", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="💹 سلامت اقتصاد",     callback_data="admin:econ", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🏠 نظارتِ بر املاک",   callback_data="admin:houses", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="📈 بورسِ آبیس",         callback_data="admin:exchange", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🏛 نظارتِ بر گیلدها",   callback_data="admin:guilds", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="⚡ ضربانِ آبیس",       callback_data="admin:pulse", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🚫 لیست بن‌شده‌ها",   callback_data="admin:banlist", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🔔 آی‌دی‌های ادمین",   callback_data="admin:whoisadmin", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="📋 راهنمای کامندها", callback_data="admin:help", style=ButtonStyle.PRIMARY)],
    ])


HELP_TEXT = (
    "📋 **لیست کامندهای ادمین**\n\n"
    "👤 **مدیریت پلیر**\n"
    "`/info <id>` — اطلاعات کامل + پنل دکمه‌ای ویرایش (XP/Zen/HP/کاراکتر/آیتم/یادداشت/بن/ریست)\n"
    "`/find <متن>` — جست‌وجوی پلیر با نام یا یوزرنیم\n"
    "`/note <id> [متن]` — یادداشتِ ادمین روی پروفایل پلیر (`-` برای پاک‌کردن)\n"
    "`/ban <id> [دلیل]` — بن کردن\n"
    "`/unban <id>` — آنبن کردن\n"
    "`/banlist` — لیست بن‌شده‌ها\n"
    "`/playerreset <id> [newchar]` — ریستِ **کاملِ** یه بازیکن (سطح/XP/Zen/کوله‌پشتی/گیلد/بانک/کازینو/"
    "بتل‌پس/PvP/دستاورد و همه‌چی صفر می‌شه؛ کاراکتر و کاتانا حفظ می‌مونن — مگه اینکه `newchar` بدی)\n"
    "`/resetall` — همینِ بالا ولی برای **همه‌ی** بازیکن‌ها با هم (کاراکتر و کاتانای همه حفظ می‌مونه)\n"
    "⚠️ `/resetplayer` و `/softreset` منسوخ شدن — به‌جاشون از `/playerreset` استفاده کن.\n\n"
    "🎁 **دادن آیتم / پاداش**\n"
    "`/chargrant <id> <نام کاراکتر>` — دادن کاراکتر\n"
    "`/blessgrant <id> <seal_id>` — دادن مُهرِ الهی (Divine Seal)\n"
    "`/blessrevoke <id>` — گرفتنِ مُهرِ الهی از بازیکن\n"
    "`/givexp <id> <عدد>` — دادن XP\n"
    "`/setlevel <id> <لول> [تعداد لوت=3]` — تنظیمِ مستقیمِ لول (مثلِ لول‌آپِ طبیعی: HP/امتیازِ مهارت/لوتِ رندوم هم می‌ده و به بازیکن هم پیام می‌فرسته)\n"
    "`/sethp <id> <عدد>` — تنظیم HP فعلی\n"
    "`/remitem <id>` — حذف آیتم از کوله‌پشتی (پنل ۳×۳)\n\n"
    "👥 **اکشن‌های گروهی**\n"
    "`/massgivezen <عدد> [حداقل‌سطح] [حداکثرسطح]` — دادن Zen به گروهی از پلیرها\n"
    "`/massgivexp <عدد> [حداقل‌سطح] [حداکثرسطح]` — دادن XP به گروهی از پلیرها\n\n"
    "📢 **همگانی**\n"
    "`/broadcast <پیام>` — ارسال پیامِ خصوصی به همه‌ی بازیکن‌ها (تو خصوصیِ خودِ ربات)\n"
    "`/gbroadcast <پیام>` — پستِ مستقیمِ اعلان تو همه‌ی گروه‌هایی که ربات توشونه\n\n"
    "👹 **باس جهانی**\n"
    "برای اسپان/ریست باس از `/spawnboss` و `/killboss` تو منوی اصلی استفاده کن.\n\n"
    "💰 برای دادن Zen یا کاراکتر ساده از `/givezen` و `/givechar` تو منوی اصلی هم می‌تونی استفاده کنی.\n"
    "💸 `/remgold <id> <عدد>` — کم‌کردنِ Zen (تو منوی اصلی)\n\n"
    "🛡 **ضدفارم**\n"
    "`/suspects` — اسکنِ دستی الگوهای مشکوک (یه اسکنِ خودکار هم هر ۶ ساعت به کانالِ لاگ می‌فرسته)\n\n"
    "⚡ **ضربانِ آبیس**\n"
    "۴ لایه‌ی ایونتِ یهویی داره: 🔹 معمولی، 🔶 نادر، ⭐ ویژه (فقط تو آستانه‌ی افراطیِ فساد) و 💣 بمب "
    "(خیلی کمیاب، اثرِ چندگانه‌ی خطرناک/پرسود هم‌زمان + یه هشدارِ «لرزش» قبل از انفجارِ واقعی). "
    "از دکمه‌ی «⚡ ضربانِ آبیس» تو پنل: دیدنِ گیجِ فسادِ جهان + تاریخچه، فورس‌کردنِ دستیِ هر ایونتی از هر لایه، "
    "فورسِ یه بمبِ رندوم، دستکاریِ دستیِ فساد برای تستِ ایونتِ ویژه، پاز/رزیوم‌کردنِ لوپِ خودکار، یا خاموش‌کردنِ ایونتِ فعلی. "
    "`/pulse` هم همون گیج رو برای بازیکن‌ها نشون می‌ده.\n\n"
    "🏠 **ملکِ شخصی (سطح ۲۰+)**\n"
    "بازیکن‌ها از `/house` درآمدِ غیرفعال جمع می‌کنن و از `/rob <هدف>` سعی می‌کنن ملکِ همدیگه رو بدزدن. "
    "از دکمه‌ی «🏠 نظارتِ بر املاک» تو پنل، وضعیتِ faucet/sink و برترین ملک‌ها دیده می‌شه.\n\n"
    "📈 **بورسِ آبیس (سطح ۱۵+)**\n"
    "بازیکن‌ها از `/exchange` می‌تونن Zenِ نقدشون رو تبدیل به سهم کنن (نور/فساد/صندوقِ پایدار) — قیمتِ نور و فساد "
    "مستقیماً به گیجِ فسادِ world_pulse وصله. از دکمه‌ی «📈 بورسِ آبیس» تو پنل می‌شه قیمت‌ها رو دید و دستی کرش/پامپ کرد.\n\n"
    "🏛 **گیلدها**\n"
    "از دکمه‌ی «🏛 نظارتِ بر گیلدها» تو پنل: صندوق/سطحِ زیرساختِ دائمی/وضعیتِ روحیه‌ی گروهی/امتیازِ جنگِ هفتگی/HPِ رئیسِ "
    "هر ۶ گیلد رو یه‌جا می‌بینی، و می‌تونی رئیسِ هر گیلد رو دستی ریست کنی.\n\n"
    "🔧 **دیباگ**\n"
    "`/whoami` — نمایش آیدی و وضعیت ادمین خودت (برای همه کار میکنه)\n"
    "`/cancel` — لغوِ یه اکشنِ نیمه‌کارهٔ پنل ویرایش (وقتی منتظرِ ورودیِ متنی مونده)\n\n"
    "🧾 **آدیتِ اقتصادی (بازار سیاه/حراجی)**\n"
    "`/audit` — آخرین ۲۵ تراکنشِ حساسِ کل سرور (خرید/فروش بازار سیاه، بید/تسویه/لغو حراجی)\n"
    "`/audit <uid>` — تاریخچه‌ی تراکنش‌های یه بازیکنِ خاص\n"
    "`/audit <kind>` — فیلتر بر اساسِ نوع (مثلاً `bm_buy`, `auction_settle`, `auction_bid`)\n"
    "`/audit <uid> <kind>` — هردو فیلتر با هم — برای ردیابیِ دقیقِ Exploit/باگ"
)


def register_admin_handlers(dp: Dispatcher, bot: Bot):

    dp.message.outer_middleware(BanMiddleware())
    dp.callback_query.outer_middleware(BanMiddleware())

    @dp.message(Command("whoami"))
    async def cmd_whoami(msg: Message):
        u = msg.from_user
        uname = f"@{u.username}" if u.username else "—"
        status = "✅ ادمین" if is_admin(msg) else "❌ ادمین نیست"
        owner_status = "\n👑 نقش: **مالک**" if is_owner(msg) else ""
        await msg.answer(
            f"🔔 آیدی تلگرام تو: `{u.id}`\n"
            f"👤 یوزرنیم: {uname}\n"
            f"🛠 وضعیت: {status}{owner_status}"
        )

    @dp.message(Command("helpadm"))
    @admin_only
    async def cmd_helpadm(msg: Message):
        await msg.answer(HELP_TEXT)

    @dp.message(Command("admin"))
    @admin_only
    async def cmd_admin(msg: Message):
        await msg.answer("🛠 **پنل ادمین**\nیه گزینه انتخاب کن:", reply_markup=admin_dashboard_kb())

    @dp.message(Command("audit"))
    @admin_only
    async def cmd_audit(msg: Message):
        """🧾 آدیتِ تراکنش‌های حساس (بازار سیاه/حراجی):
        /audit                → آخرین ۲۵ تراکنشِ کل سرور
        /audit <uid>           → آخرین ۲۵ تراکنشِ همون بازیکن
        /audit <kind>          → فیلتر بر اساسِ نوعِ تراکنش (مثلاً bm_buy)
        /audit <uid> <kind>    → هردو فیلتر با هم
        """
        from economy_ledger import get_recent_transactions, get_user_transactions
        parts = msg.text.split(maxsplit=2)
        uid_filter = None
        kind_filter = None
        if len(parts) >= 2:
            if parts[1].lstrip("-").isdigit():
                uid_filter = int(parts[1])
                if len(parts) >= 3:
                    kind_filter = parts[2].strip()
            else:
                kind_filter = parts[1].strip()

        if uid_filter is not None:
            txs = get_user_transactions(uid_filter, limit=50)
            if kind_filter:
                txs = [t for t in txs if t.get("kind") == kind_filter]
            txs = txs[:25]
            title = f"🧾 **آدیتِ تراکنش‌های** `{uid_filter}`" + (f" — نوع: `{kind_filter}`" if kind_filter else "")
        else:
            txs = get_recent_transactions(kind=kind_filter, limit=25)
            title = "🧾 **آخرین تراکنش‌های اقتصادی (بازار سیاه/حراجی)**" + (f" — نوع: `{kind_filter}`" if kind_filter else "")

        if not txs:
            await msg.answer(f"{title}\n\nهیچ تراکنشی پیدا نشد.")
            return

        lines = [title, ""]
        for t in txs:
            ts = time.strftime("%m/%d %H:%M", time.localtime(t.get("ts", 0)))
            amt = t.get("amount", 0)
            fee_note = f" (کارمزد {bz_to_display(t.get('fee'))})" if t.get("fee") else ""
            cp_note = f" ↔ `{t.get('counterparty_id')}`" if t.get("counterparty_id") else ""
            note_note = f" — {t.get('note')}" if t.get("note") else ""
            lines.append(
                f"`{ts}` **{t.get('kind')}** uid=`{t.get('user_id')}`{cp_note}\n"
                f"   📦 {t.get('item_name') or '—'} × {t.get('quantity',1)} — 💰 {bz_to_display(amt)}{fee_note}\n"
                f"   💵 {t.get('balance_before')} → {t.get('balance_after')}{note_note}"
            )
        text = "\n".join(lines)
        if len(text) > 3800:
            text = text[:3800] + "\n… (بریده شد — با `/audit <uid>` یا `/audit <kind>` دقیق‌تر فیلتر کن)"
        await msg.answer(text)

    @admin_only
    async def cb_admin_help(cb: CallbackQuery):
        await cb.message.edit_text(HELP_TEXT, reply_markup=admin_dashboard_kb())
        await cb.answer()

    @admin_only
    async def cb_admin_stats(cb: CallbackQuery):
        players = all_players()
        total   = len(players)
        banned  = sum(1 for p in players.values() if p.get("banned"))
        total_zen = sum(p.get("zen", 0) for p in players.values())
        avg_level = (sum(p.get("level", 1) for p in players.values()) / total) if total else 0

        active_24h = 0
        try:
            from bot import last_seen
            cutoff = time.time() - 86400
            active_24h = sum(1 for ts in last_seen.values() if ts >= cutoff)
        except Exception:
            pass

        top_zen = sorted(players.items(), key=lambda x: -x[1].get("zen", 0))[:5]
        top_lvl = sorted(players.items(), key=lambda x: -x[1].get("level", 1))[:5]
        zen_lines = "\n".join(f"  {i+1}. {p.get('name','—')} — {bz_to_display(p.get('zen',0))}" for i, (_, p) in enumerate(top_zen))
        lvl_lines = "\n".join(f"  {i+1}. {p.get('name','—')} — Lv.{p.get('level',1)}" for i, (_, p) in enumerate(top_lvl))

        await cb.message.edit_text(
            f"📊 **آمار کلی سرور**\n\n"
            f"👥 کل بازیکن‌ها: **{total}**\n"
            f"🟢 فعال در ۲۴ ساعت اخیر: **{active_24h}**\n"
            f"🚫 بن‌شده: **{banned}**\n"
            f"⭐ میانگین سطح: **{avg_level:.1f}**\n"
            f"💰 مجموع Zen در گردش: **{bz_to_display(total_zen)}**\n"
            f"💵 میانگین Zen هر پلیر: **{bz_to_display(int(total_zen/total) if total else 0)}**\n\n"
            f"💰 **پولدارترین‌ها:**\n{zen_lines or '—'}\n\n"
            f"⭐ **بالاترین سطح:**\n{lvl_lines or '—'}",
            reply_markup=admin_dashboard_kb()
        )
        await cb.answer()

    @admin_only
    async def cb_admin_banlist(cb: CallbackQuery):
        players = all_players()
        banned  = [(pid, p) for pid, p in players.items() if p.get("banned")]
        if not banned:
            text = "✅ هیچ بازیکن بن‌شده‌ای نیست."
        else:
            lines = ["🚫 **لیست بن‌شده‌ها:**\n"]
            for pid, p in banned[:30]:
                lines.append(f"• {p.get('name','—')} (`{pid}`)")
            if len(banned) > 30:
                lines.append(f"\n... و {len(banned)-30} نفر دیگه")
            text = "\n".join(lines)
        await cb.message.edit_text(text, reply_markup=admin_dashboard_kb())
        await cb.answer()

    @admin_only
    async def cb_admin_econ(cb: CallbackQuery):
        players = all_players()
        total_zen = sum(p.get("zen", 0) for p in players.values())
        total_savings = sum(p.get("savings_zen", 0) for p in players.values())
        active_loans = [(pid, p) for pid, p in players.items() if p.get("loan_principal", 0) > 0]
        loans_outstanding = sum(p.get("loan_principal", 0) for _, p in active_loans)

        try:
            from economy_engine import get_tax_pool
            tax_pool = get_tax_pool()
        except Exception:
            tax_pool = 0

        try:
            from economy_ledger import get_ledger
            ledger = get_ledger()
        except Exception:
            ledger = {}

        try:
            from database import get_jackpot
            jackpot = get_jackpot()
        except Exception:
            jackpot = 0

        faucet = ledger.get("total_interest_paid", 0) + ledger.get("total_loans_issued", 0)
        sink = tax_pool + ledger.get("total_loan_interest", 0)
        balance_note = "🟢 متعادل" if sink >= faucet * 0.5 else "🟡 faucet بیشتر از sink — مراقب تورم باش"

        await cb.message.edit_text(
            f"💹 **سلامتِ اقتصاد سرور**\n\n"
            f"💰 Zen در گردش (حساب جاری): **{bz_to_display(total_zen)}**\n"
            f"🏺 Zen تو سپرده‌ها: **{bz_to_display(total_savings)}**\n"
            f"🎰 جکپاتِ کازینو: **{bz_to_display(jackpot)}**\n\n"
            f"🧾 **صندوقِ مالیاتِ سراسری (sink):** {bz_to_display(tax_pool)}\n\n"
            f"💳 **وام‌ها**\n"
            f"  فعال: {len(active_loans)} نفر | مانده: {bz_to_display(loans_outstanding)}\n"
            f"  مجموعِ صادرشده (faucet): {bz_to_display(ledger.get('total_loans_issued',0))}\n"
            f"  مجموعِ بازپرداخت‌شده: {bz_to_display(ledger.get('total_loans_repaid',0))}\n"
            f"  بهره‌ی جمع‌آوری‌شده (sink): {bz_to_display(ledger.get('total_loan_interest',0))}\n"
            f"  نکول‌شده: {ledger.get('total_loan_defaults',0)} مورد\n\n"
            f"🏺 **سود سپرده پرداختی (faucet):** {bz_to_display(ledger.get('total_interest_paid',0))}\n"
            f"🏛 **کمک به صندوق‌های گیلد:** {bz_to_display(ledger.get('treasury_contributions',0))}\n\n"
            f"⚖️ وضعیت: {balance_note}",
            reply_markup=admin_dashboard_kb()
        )
        await cb.answer()

    @admin_only
    async def cb_admin_houses(cb: CallbackQuery):
        import house_system as hs
        players = all_players()
        rows = []
        for pid, p in players.items():
            house = p.get("house")
            if not house:
                continue
            hs.accrue_income(house)
            rows.append((
                p.get("name", "—"), pid,
                hs.tier_data(house)["name"], house.get("vault", 0),
                hs.security_score(house), hs.prestige_score(house),
            ))
        rows.sort(key=lambda r: r[5], reverse=True)

        try:
            from economy_ledger import get_ledger
            ledger = get_ledger()
        except Exception:
            ledger = {}

        lines = ["🏠 **نظارتِ بر املاک**\n"]
        lines.append(f"💰 مجموعِ درآمدِ برداشت‌شده (faucet): {bz_to_display(ledger.get('total_house_income_paid',0))}")
        lines.append(f"🧾 مجموعِ نگه‌داریِ سوزونده‌شده (sink): {bz_to_display(ledger.get('total_house_upkeep_sink',0))}\n")
        lines.append(
            f"🗡 دزدی‌ها: {ledger.get('total_robbery_attempts',0)} تلاش | "
            f"{ledger.get('total_robbery_success',0)} موفق\n"
            f"   بُرده‌شده: {bz_to_display(ledger.get('total_robbery_stolen',0))} | "
            f"سوزونده‌شده (sink): {bz_to_display(ledger.get('total_robbery_burned',0))}\n"
        )
        try:
            import house_system as hs
            pool = hs.get_insurance_pool()
        except Exception:
            pool = 0
        lines.append(
            f"🛡 بیمه: صندوقِ فعلی {bz_to_display(pool)} | "
            f"حق‌بیمه‌های جمع‌شده: {bz_to_display(ledger.get('total_insurance_premiums',0))} | "
            f"خسارتِ پرداختی: {bz_to_display(ledger.get('total_insurance_payouts',0))}\n"
        )
        lines.append("🏆 **برترین ملک‌ها (پرستیژ):**")
        for name, pid, tier_name, vault, sec, prestige in rows[:10]:
            lines.append(f"• {tier_name} — {name} (`{pid}`) | صندوق: {vault:,} | امنیت: {sec} | پرستیژ: {prestige}")
        if not rows:
            lines.append("هنوز هیچ بازیکنی ملک نداره.")
        await cb.message.edit_text("\n".join(lines), reply_markup=admin_dashboard_kb())
        await cb.answer()

    @admin_only
    async def cb_admin_whoisadmin(cb: CallbackQuery):
        lines = ["🔔 **آیدی‌های ادمین ثبت‌شده:**\n"]
        for aid in ADMIN_IDS:
            role = "👑 مالک" if aid in OWNER_IDS else "🛠 ادمین"
            lines.append(f"• `{aid}` — {role}")
        if ADMIN_USERNAMES:
            lines.append("\n👤 **یوزرنیم‌های بک‌آپ:**")
            for un in ADMIN_USERNAMES:
                lines.append(f"• @{un}")
        await cb.message.edit_text("\n".join(lines), reply_markup=admin_dashboard_kb())
        await cb.answer()

    # ─── ⚡ ضربانِ آبیس ────────────────────────────────────────
    def _pulse_kb() -> InlineKeyboardMarkup:
        from world_pulse import _doc
        paused = _doc().get("paused", False)
        pause_label = "▶️ ازسرگیریِ لوپِ خودکار" if paused else "⏸ توقفِ لوپِ خودکار"
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎯 فورس‌کردنِ یه ایونتِ خاص", callback_data="admin:pulse_forcemenu", style=ButtonStyle.PRIMARY)],
            [InlineKeyboardButton(text="💣 فورسِ یه بمبِ رندوم",       callback_data="admin:pulse_bombforce", style=ButtonStyle.DANGER)],
            [
                InlineKeyboardButton(text="🌑 فساد +۱۵", callback_data="admin:pulse_corr:15", style=ButtonStyle.DANGER),
                InlineKeyboardButton(text="✨ فساد −۱۵", callback_data="admin:pulse_corr:-15", style=ButtonStyle.SUCCESS),
            ],
            [InlineKeyboardButton(text="🔕 خاموش‌کردنِ ایونتِ فعلی",  callback_data="admin:pulse_clear", style=ButtonStyle.DANGER)],
            [InlineKeyboardButton(text=pause_label,                    callback_data="admin:pulse_pausetoggle", style=ButtonStyle.PRIMARY)],
            [InlineKeyboardButton(text="⬅️ بازگشت",                    callback_data="admin:pulse_back_dash", style=ButtonStyle.PRIMARY)],
        ])

    def _pulse_text() -> str:
        from world_pulse import pulse_status_text, _doc, TIER_BADGE
        doc = _doc()
        text = pulse_status_text()
        hist = doc.get("history", [])[-5:]
        if hist:
            text += "\n\n📜 **۵ ایونتِ آخر:**\n"
            icon_map = {"common": "🔹", "rare": "🔶", "special": "⭐", "bomb": "💣"}
            for h in reversed(hist):
                ago_min = int((time.time() - h["at"]) / 60)
                icon = icon_map.get(h.get("tier", "common"), "🔹")
                text += f"{icon} {h['name']} — {ago_min} دقیقه پیش (فساد: {h['corruption']:.0f})\n"
        if doc.get("paused"):
            text += "\n⏸ لوپِ خودکار الان متوقفه (ادمین دستی خاموشش کرده)."
        return text

    @admin_only
    async def cb_admin_pulse(cb: CallbackQuery):
        await cb.message.edit_text(_pulse_text(), reply_markup=_pulse_kb())
        await cb.answer()

    @admin_only
    async def cb_admin_pulse_back_dash(cb: CallbackQuery):
        await cb.message.edit_text("🛠 **پنل ادمین**\nیه گزینه انتخاب کن:", reply_markup=admin_dashboard_kb())
        await cb.answer()

    @admin_only
    async def cb_admin_pulse_pausetoggle(cb: CallbackQuery):
        from world_pulse import _doc, set_paused
        currently_paused = _doc().get("paused", False)
        set_paused(not currently_paused)
        await cb.message.edit_text(_pulse_text(), reply_markup=_pulse_kb())
        await cb.answer("⏸ لوپِ خودکار متوقف شد." if not currently_paused else "▶️ لوپِ خودکار از سر گرفته شد.")

    @admin_only
    async def cb_admin_pulse_clear(cb: CallbackQuery):
        from world_pulse import clear_active
        clear_active()
        await cb.message.edit_text(_pulse_text(), reply_markup=_pulse_kb())
        await cb.answer("🔕 ایونتِ فعلی خاموش شد.")

    @admin_only
    async def cb_admin_pulse_forcemenu(cb: CallbackQuery):
        from world_pulse import COMMON_EVENTS, RARE_EVENTS, SPECIAL_EVENTS, BOMB_EVENTS
        rows = []
        rows.append([InlineKeyboardButton(text="── 🔹 معمولی ──", callback_data="admin:noop", style=ButtonStyle.PRIMARY)])
        for e in COMMON_EVENTS:
            rows.append([InlineKeyboardButton(text=e["name"], callback_data=f"admin:pulse_force:{e['id']}", style=ButtonStyle.PRIMARY)])
        rows.append([InlineKeyboardButton(text="── 🔶 نادر ──", callback_data="admin:noop", style=ButtonStyle.PRIMARY)])
        for e in RARE_EVENTS:
            rows.append([InlineKeyboardButton(text=e["name"], callback_data=f"admin:pulse_force:{e['id']}", style=ButtonStyle.PRIMARY)])
        rows.append([InlineKeyboardButton(text="── ⭐ ویژه ──", callback_data="admin:noop", style=ButtonStyle.PRIMARY)])
        for e in SPECIAL_EVENTS.values():
            rows.append([InlineKeyboardButton(text=e["name"], callback_data=f"admin:pulse_force:{e['id']}", style=ButtonStyle.PRIMARY)])
        rows.append([InlineKeyboardButton(text="── 💣 بمب ──", callback_data="admin:noop", style=ButtonStyle.PRIMARY)])
        for e in BOMB_EVENTS:
            rows.append([InlineKeyboardButton(text=e["name"], callback_data=f"admin:pulse_force:{e['id']}", style=ButtonStyle.DANGER)])
        rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin:pulse", style=ButtonStyle.PRIMARY)])
        await cb.message.edit_text(
            "🎯 کدوم ایونت رو فورس کنیم؟ (به همه‌ی بازیکن‌ها اعلام می‌شه — بمب‌ها اول یه هشدار می‌فرستن، بعد منفجر می‌شن)",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
        )
        await cb.answer()

    @admin_only
    async def cb_admin_pulse_noop(cb: CallbackQuery):
        await cb.answer()

    @admin_only
    async def cb_admin_pulse_force(cb: CallbackQuery):
        from world_pulse import force_trigger
        event_id = cb.data.split(":", 2)[2]
        await cb.answer("⏳ در حال فورس‌کردن...")
        event = await force_trigger(bot, event_id)
        if event:
            await cb.message.edit_text(_pulse_text(), reply_markup=_pulse_kb())
        else:
            await cb.message.answer("❌ ایونت پیدا نشد.")

    @admin_only
    async def cb_admin_pulse_bombforce(cb: CallbackQuery):
        from world_pulse import force_trigger, BOMB_EVENTS
        import random as _r
        bomb = _r.choice(BOMB_EVENTS)
        await cb.answer("💣 در حال فورس‌کردنِ بمب...")
        event = await force_trigger(bot, bomb["id"])
        if event:
            await cb.message.edit_text(_pulse_text(), reply_markup=_pulse_kb())

    @admin_only
    async def cb_admin_pulse_corr(cb: CallbackQuery):
        from world_pulse import adjust_corruption
        delta = float(cb.data.split(":")[2])
        new_val = adjust_corruption(delta)
        await cb.message.edit_text(_pulse_text(), reply_markup=_pulse_kb())
        await cb.answer(f"فسادِ جهان الان: {new_val:.0f}/100")

    # ─── 📈 بورسِ آبیس ────────────────────────────────────────
    def _exchange_kb() -> InlineKeyboardMarkup:
        import exchange_system as ex
        rows = []
        for inst in ex.INSTRUMENTS:
            rows.append([
                InlineKeyboardButton(text=f"📉 کرش {inst['name']}", callback_data=f"admin:exch_shock:{inst['id']}:0.7", style=ButtonStyle.DANGER),
                InlineKeyboardButton(text=f"📈 پامپ {inst['name']}", callback_data=f"admin:exch_shock:{inst['id']}:1.4", style=ButtonStyle.SUCCESS),
            ])
        rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin:pulse_back_dash", style=ButtonStyle.PRIMARY)])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def _exchange_text() -> str:
        import exchange_system as ex
        try:
            from economy_ledger import get_ledger
            fees = get_ledger().get("total_exchange_fees", 0)
        except Exception:
            fees = 0
        prices = ex.get_prices()
        lines = ["📈 **بورسِ آبیس — نظارتِ ادمین**\n"]
        for inst in ex.INSTRUMENTS:
            p = prices[inst["id"]]
            lines.append(f"{p['name']}: **{p['price']:,.2f} Zen** (قبلی: {p['prev']:,.2f})")
        lines.append(f"\n🧾 مجموعِ کارمزدِ جمع‌شده (sink): {bz_to_display(fees)}")
        return "\n".join(lines)

    @admin_only
    async def cb_admin_exchange(cb: CallbackQuery):
        await cb.message.edit_text(_exchange_text(), reply_markup=_exchange_kb())
        await cb.answer()

    @admin_only
    async def cb_admin_exch_shock(cb: CallbackQuery):
        import exchange_system as ex
        _, inst_id, mult_s = cb.data.split(":")
        new_price = ex.force_shock(inst_id, float(mult_s))
        if new_price is None:
            await cb.answer("❌ سهم پیدا نشد.", show_alert=True)
            return
        await cb.message.edit_text(_exchange_text(), reply_markup=_exchange_kb())
        await cb.answer(f"✅ قیمتِ جدید: {new_price:,.2f} Zen")

    # ─── 🏛 نظارتِ بر گیلدها ────────────────────────────────────
    def _guilds_kb() -> InlineKeyboardMarkup:
        import guild_system as gsys
        rows = []
        for gid in gsys.GUILD_IDS:
            g = gsys.GUILDS[gid]
            rows.append([InlineKeyboardButton(text=f"💀 ریست رئیسِ {g['name']}", callback_data=f"admin:gb_reset:{gid}", style=ButtonStyle.DANGER)])
        rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin:pulse_back_dash", style=ButtonStyle.PRIMARY)])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def _guilds_text() -> str:
        import guild_system as gsys
        war = gsys.get_war_state()
        lines = ["🏛 **نظارتِ بر گیلدها**\n"]
        for gid in gsys.GUILD_IDS:
            g = gsys.GUILDS[gid]
            treasury = gsys.get_treasury(gid)
            infra = gsys.get_infra_level(gid)
            infra_bonus = gsys.get_infra_bonus_pct(gid)
            rally = "🔥 فعال" if gsys.get_rally_bonus_pct(gid) else "خاموش"
            boss = gsys.get_guild_boss(gid)
            war_score = war.get("scores", {}).get(gid, 0)
            boss_status = f"{boss['hp']:,}/{boss['max_hp']:,} HP" if boss.get("alive") else "مرده (منتظرِ اسپاونِ بعدی)"
            lines.append(
                f"{g['emoji']} **{g['name']}**\n"
                f"   🏺 صندوق: {treasury.get('zen',0):,} Zen | 🏛 زیرساخت: سطح {infra} (+{infra_bonus}٪) | روحیه: {rally}\n"
                f"   ⚔️ امتیازِ جنگِ این هفته: {war_score:,} | 👹 رئیس: {boss_status}\n"
            )
        if war.get("last_winner"):
            wg = gsys.GUILDS[war["last_winner"]]
            lines.append(f"👑 برنده‌ی هفته‌ی قبل: {wg['emoji']} {wg['name']} ({war['last_winner_score']:,} امتیاز)")
        return "\n".join(lines)

    @admin_only
    async def cb_admin_guilds(cb: CallbackQuery):
        await cb.message.edit_text(_guilds_text(), reply_markup=_guilds_kb())
        await cb.answer()

    @admin_only
    async def cb_admin_gb_reset(cb: CallbackQuery):
        import guild_system as gsys
        gid = cb.data.split(":")[2]
        if gid not in gsys.GUILD_IDS:
            await cb.answer("❌ گیلد پیدا نشد.", show_alert=True)
            return
        gsys.reset_guild_boss(gid)
        await cb.message.edit_text(_guilds_text(), reply_markup=_guilds_kb())
        await cb.answer(f"💀 رئیسِ {gsys.GUILDS[gid]['name']} ریست شد — دفعه‌ی بعد از نو اسپان می‌شه.", show_alert=True)

    dp.callback_query.register(cb_admin_help,       F.data == "admin:help")
    dp.callback_query.register(cb_admin_stats,      F.data == "admin:stats")
    dp.callback_query.register(cb_admin_econ,       F.data == "admin:econ")
    dp.callback_query.register(cb_admin_houses,     F.data == "admin:houses")
    dp.callback_query.register(cb_admin_exchange,   F.data == "admin:exchange")
    dp.callback_query.register(cb_admin_exch_shock, F.data.startswith("admin:exch_shock:"))
    dp.callback_query.register(cb_admin_guilds,     F.data == "admin:guilds")
    dp.callback_query.register(cb_admin_gb_reset,   F.data.startswith("admin:gb_reset:"))
    dp.callback_query.register(cb_admin_banlist,    F.data == "admin:banlist")
    dp.callback_query.register(cb_admin_whoisadmin, F.data == "admin:whoisadmin")
    dp.callback_query.register(cb_admin_pulse,             F.data == "admin:pulse")
    dp.callback_query.register(cb_admin_pulse_back_dash,   F.data == "admin:pulse_back_dash")
    dp.callback_query.register(cb_admin_pulse_pausetoggle, F.data == "admin:pulse_pausetoggle")
    dp.callback_query.register(cb_admin_pulse_clear,       F.data == "admin:pulse_clear")
    dp.callback_query.register(cb_admin_pulse_forcemenu,   F.data == "admin:pulse_forcemenu")
    dp.callback_query.register(cb_admin_pulse_force,       F.data.startswith("admin:pulse_force:"))
    dp.callback_query.register(cb_admin_pulse_bombforce,   F.data == "admin:pulse_bombforce")
    dp.callback_query.register(cb_admin_pulse_corr,        F.data.startswith("admin:pulse_corr:"))
    dp.callback_query.register(cb_admin_pulse_noop,        F.data == "admin:noop")

    @dp.message(Command("ban"))
    @admin_only
    async def cmd_ban(msg: Message):
        parts = msg.text.split(maxsplit=2)
        if len(parts) < 2:
            return await msg.answer("❌ استفاده: `/ban <telegram_id> [دلیل]`\nمثال: `/ban 123456789 تقلب`")
        target_id = resolve_target_id(parts[1])
        if target_id is None:
            return await msg.answer("❌ آیدی باید عدد باشه")
        player = await aget_player(target_id)
        if not player:
            return await msg.answer("❌ بازیکن پیدا نشد")
        reason = parts[2].strip() if len(parts) > 2 else None
        player["banned"]      = True
        player["ban_reason"]  = reason
        await asave_player(target_id, player)
        reason_txt = f"\n📝 دلیل: {reason}" if reason else ""
        
        log_sync(
            f"🚫 **BAN**\n"
            f"👤 {player.get('name', target_id)} (`{target_id}`)\n"
            f"🛠 ادمین: `{msg.from_user.id}`\n"
            f"📝 دلیل: {reason or 'نامشخص'}",
            "BAN"
        )
        
        await msg.answer(f"✅ **{player.get('name', target_id)}** (`{target_id}`) بن شد{reason_txt}")
        try:
            note = f"🚫 اکانت تو توسط ادمین بن شد.{(' دلیل: ' + reason) if reason else ''}"
            await bot.send_message(target_id, note)
        except Exception:
            pass

    @dp.message(Command("unban"))
    @admin_only
    async def cmd_unban(msg: Message):
        parts = msg.text.split()
        if len(parts) < 2:
            return await msg.answer("❌ استفاده: `/unban <telegram_id>`\nمثال: `/unban 123456789`")
        target_id = resolve_target_id(parts[1])
        if target_id is None:
            return await msg.answer("❌ آیدی باید عدد باشه")
        player = await aget_player(target_id)
        if not player:
            return await msg.answer("❌ بازیکن پیدا نشد")
        player["banned"]     = False
        player["ban_reason"] = None
        await asave_player(target_id, player)
        
        log_sync(
            f"✅ **UNBAN**\n"
            f"👤 {player.get('name', target_id)} (`{target_id}`)\n"
            f"🛠 ادمین: `{msg.from_user.id}`",
            "BAN"
        )
        
        await msg.answer(f"✅ **{player.get('name', target_id)}** (`{target_id}`) آنبن شد")
        try:
            await bot.send_message(target_id, "✅ اکانت تو توسط ادمین آنبن شد. خوش برگشتی!")
        except Exception:
            pass

    @dp.message(Command("banlist"))
    @admin_only
    async def cmd_banlist(msg: Message):
        players = all_players()
        banned  = [(pid, p) for pid, p in players.items() if p.get("banned")]
        if not banned:
            return await msg.answer("✅ هیچ بازیکن بن‌شده‌ای نیست.")
        lines = ["🚫 **لیست بن‌شده‌ها:**\n"]
        for pid, p in banned[:50]:
            reason = f" — {p['ban_reason']}" if p.get("ban_reason") else ""
            lines.append(f"• {p.get('name','—')} (`{pid}`){reason}")
        if len(banned) > 50:
            lines.append(f"\n... و {len(banned)-50} نفر دیگه")
        await msg.answer("\n".join(lines))

    @dp.message(Command("info"))
    @admin_only
    async def cmd_info(msg: Message):
        parts = msg.text.split()
        if len(parts) < 2:
            return await msg.answer("❌ استفاده: `/info <telegram_id>`\nمثال: `/info 123456789`")
        target_id = resolve_target_id(parts[1])
        if target_id is None:
            return await msg.answer("❌ آیدی باید عدد باشه")
        player = await aget_player(target_id)
        if not player:
            return await msg.answer("❌ بازیکن پیدا نشد")
        await msg.answer(player_summary(target_id, player), reply_markup=player_editor_kb(target_id, bool(player.get("banned"))))

    @dp.message(Command("find"))
    @admin_only
    async def cmd_find(msg: Message):
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2:
            return await msg.answer("❌ استفاده: `/find <بخشی از نام یا یوزرنیم>`\nمثال: `/find hosein`")
        query = parts[1].strip().lower()
        players = all_players()
        matches = []
        for pid, p in players.items():
            name = str(p.get("name", "")).lower()
            uname = str(p.get("username", "")).lower()
            if query in name or query in uname:
                matches.append((pid, p))
        if not matches:
            return await msg.answer(f"❌ هیچ بازیکنی با «{parts[1].strip()}» پیدا نشد.")
        matches.sort(key=lambda x: -x[1].get("level", 1))
        keyboard = []
        for pid, p in matches[:20]:
            uname = f"@{p['username']}" if p.get("username") else "—"
            label = f"👤 {p.get('name','—')} ({uname}) Lv.{p.get('level',1)}"
            keyboard.append([InlineKeyboardButton(text=label[:64], callback_data=f"padm:open:{pid}", style=ButtonStyle.PRIMARY)])
        extra = f"\n\n... و {len(matches)-20} نتیجه‌ی دیگه (دقیق‌تر جست‌وجو کن)" if len(matches) > 20 else ""
        await msg.answer(
            f"🔎 **{len(matches)} نتیجه برای «{parts[1].strip()}»:**{extra}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )

    @dp.message(Command("chargrant", "katanagrant"))
    @admin_only
    async def cmd_chargrant(msg: Message):
        # 🆕 /katanagrant یه نام‌مستعارِ عمدیه برای همین دستور: چون کاتانا
        # (اسم/عنصر/تایر/روح) صددرصد از روی character مشتق می‌شه، «دادنِ
        # کاتانای دیگه» دقیقاً یعنی «دادنِ کاراکترِ دیگه» — یه دستورِ جدا و
        # موازی فقط باعثِ دریفتِ منطق می‌شد.
        cmd_used = msg.text.split()[0].lstrip("/").split("@")[0]
        parts = msg.text.split(maxsplit=2)
        if len(parts) < 3:
            hint = "\n".join(f"• {n}" for n in SPECIAL_CHARACTERS)
            mythic_hint = "\n".join(f"• {n}" for n in MYTHIC_CHARACTERS)
            return await msg.answer(
                f"❌ استفاده: `/{cmd_used} <telegram_id> <نام کاراکتر>`\n"
                f"مثال: `/{cmd_used} 123456789 Vaelthryx`\n\n"
                "ℹ️ چون هر کاراکتر یه کاتانای اختصاصی داره (اسم/عنصر/تایر/روح)، "
                "این دستور همون «تعویضِ کاتانا»ست — کافیه کاراکترِ جدید رو بدی.\n\n"
                f"کاراکترهای ویژه:\n{hint}\n\n"
                f"کاراکترهای Mythic:\n{mythic_hint}"
            )
        target_id = resolve_target_id(parts[1])
        if target_id is None:
            return await msg.answer("❌ آیدی باید عدد باشه")
        player = await aget_player(target_id)
        if not player:
            return await msg.answer("❌ بازیکن پیدا نشد")
        char_name = find_character_name(parts[2].strip())
        if not char_name:
            close = [n for n in ALL_CHARACTERS if parts[2].strip().lower() in n.lower()]
            hint = ("\nشاید:\n" + "\n".join(f"• {n}" for n in close[:5])) if close else ""
            return await msg.answer(f"❌ کاراکتر **{parts[2].strip()}** وجود نداره!{hint}")
        old_char = player.get("character")
        player["character"] = char_name
        assign_special_char(char_name)
        # 🆕 باگ‌فیکس: کاتانا ۱۰۰٪ از روی character مشتق می‌شه (اسم/عنصر/تایر/روح —
        # katana_core.get_katana_identity)، یعنی /chargrant همون «تعویضِ کاتانا»یِ
        # واقعیه. ولی katana_bond/katana_bond_level/katana_awakening/katana_deaths
        # برخلافِ لور/ابعاد/شخصیت/کوئست (که per-character ذخیره می‌شن) فلَتن —
        # قبلاً با تعویضِ کاراکتر، پیوند/بیداریِ کاتانای قبلی به‌اشتباه رو کاتانای
        # جدید می‌موند. الان با تغییرِ واقعیِ کاراکتر، این‌ها صفر می‌شن (katana_level
        # عمداً دست‌نخورده می‌مونه — طبقِ کامنتِ katana_dimensions.py اون «مهارتِ
        # آهنگریِ» کلیِ بازیکنه، نه چیزی مختصِ یه کاتانای خاص).
        if old_char and old_char != char_name:
            player["katana_bond"] = 0
            player["katana_bond_level"] = 1
            player["katana_awakening"] = 0
            player["katana_deaths"] = 0
        # 🆕 باگ‌فیکس: قبلاً کاراکترِ قبلیِ پلیر هیچ‌وقت به pool برنمی‌گشت
        # (release_char هیچ‌جا صدا زده نمی‌شد) — یعنی هر بار /chargrant
        # می‌زدی، کاراکترِ قدیمی برای همیشه «تصرف‌شده» می‌موند و دیگه هیچ‌وقت
        # نه به‌صورتِ رندوم به کسی داده می‌شد، نه به خودِ این پلیر برمی‌گشت.
        if old_char and old_char != char_name:
            release_char(old_char)
        # 🆕 باگ‌فیکس: /chargrant برخلافِ /givechar (نسخه‌ی قدیمیِ bot.py که
        # الان منسوخ شده) هیچ‌وقت mark_character_seen رو صدا نمی‌زد، یعنی این
        # کاراکتر تو کدکس/اپیلوگ‌های character_lore.py هیچ‌وقت «دیده‌شده»
        # ثبت نمی‌شد.
        from character_lore import mark_character_seen
        mark_character_seen(player, char_name)
        await asave_player(target_id, player)
        
        from katana_core import get_katana_identity
        katana_name = get_katana_identity(char_name).get("katana_name", "بی‌نام")

        log_sync(
            f"🎴 **CHARGGRANT**\n"
            f"👤 {player.get('name', target_id)} (`{target_id}`)\n"
            f"🎴 کاراکتر: {char_name} | 🗡 کاتانا: {katana_name}\n"
            f"🛠 ادمین: `{msg.from_user.id}`",
            "ADMIN"
        )

        await msg.answer(
            f"✅ **{char_name}** به **{player.get('name', target_id)}** داده شد!\n"
            f"🗡 کاتانای جدید: **{katana_name}**"
        )
        try:
            await bot.send_message(
                target_id,
                f"👑 ادمین یه کاراکتر و کاتانای جدید بهت داد: **{char_name}** — 🗡 **{katana_name}**!"
            )
        except Exception:
            pass

    @dp.message(Command("blessgrant"))
    @admin_only
    async def cmd_blessgrant(msg: Message):
        parts = msg.text.split(maxsplit=2)
        if len(parts) < 3:
            lines = []
            for tier in ("common", "rare", "divine_mandate"):
                names = [f"{SEAL_EMOJI[tier]} `{sid}` — {d['name']}"
                         for sid, d in DIVINE_SEALS.items() if d["tier"] == tier]
                if names:
                    lines.append(f"**{tier}**\n" + "\n".join(names))
            return await msg.answer(
                "❌ استفاده: `/blessgrant <telegram_id> <seal_id>`\n"
                "مثال: `/blessgrant 123456789 vaelthorian_wrath`\n\n"
                + "\n\n".join(lines)
            )
        target_id = resolve_target_id(parts[1])
        if target_id is None:
            return await msg.answer("❌ آیدی باید عدد باشه")
        player = await aget_player(target_id)
        if not player:
            return await msg.answer("❌ بازیکن پیدا نشد")

        seal_id = find_seal_id(parts[2].strip())
        if not seal_id:
            return await msg.answer(f"❌ مُهرِ **{parts[2].strip()}** وجود نداره! برای دیدنِ لیست فقط `/blessgrant` بزن.")

        seal = DIVINE_SEALS[seal_id]
        prev_holder = None
        if seal["tier"] == "divine_mandate":
            prev_holder = assign_seal_holder(seal_id, target_id)
            if prev_holder:
                prev_player = await aget_player(prev_holder)
                if prev_player and prev_player.get("divine_seal") == seal_id:
                    prev_player["divine_seal"] = None
                    await asave_player(prev_holder, prev_player)
                    try:
                        await bot.send_message(
                            prev_holder,
                            f"🌘 **{seal['name']}** ازت گرفته شد — یه Bearerِ دیگه انتخاب شده."
                        )
                    except Exception:
                        pass

        player["divine_seal"] = seal_id
        await asave_player(target_id, player)

        log_sync(
            f"👑 **BLESSGRANT**\n"
            f"👤 {player.get('name', target_id)} (`{target_id}`)\n"
            f"🔱 مُهر: {seal['name']} ({seal['tier']})\n"
            f"🛠 ادمین: `{msg.from_user.id}`",
            "ADMIN"
        )
        await msg.answer(f"✅ **{seal['name']}** به **{player.get('name', target_id)}** داده شد!")

        # ── رونمایی سینمایی برای خودِ بازیکن ──────────────────────
        try:
            await bot.send_message(target_id, "✨ یه چیزی... حست کرد.")
            await asyncio.sleep(1.6)
            await bot.send_message(target_id, "جهان، برای یه لحظه، نفسشو نگه داشت.")
            await asyncio.sleep(1.6)
            title_line = f"\n🏷️ عنوانِ جدید: {seal['title']}" if seal.get("title") else ""
            await bot.send_message(
                target_id,
                f"{SEAL_EMOJI[seal['tier']]} **{seal['name']}** بهت داده شد.{title_line}\n\n"
                f"_{seal['lore']}_"
            )
        except Exception:
            pass

    @dp.message(Command("blessrevoke"))
    @admin_only
    async def cmd_blessrevoke(msg: Message):
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2:
            return await msg.answer("❌ استفاده: `/blessrevoke <telegram_id>`")
        target_id = resolve_target_id(parts[1])
        if target_id is None:
            return await msg.answer("❌ آیدی باید عدد باشه")
        player = await aget_player(target_id)
        if not player:
            return await msg.answer("❌ بازیکن پیدا نشد")
        old_seal = player.get("divine_seal")
        if not old_seal:
            return await msg.answer("ℹ️ این بازیکن اصلاً مُهری نداره.")
        player["divine_seal"] = None
        await asave_player(target_id, player)
        log_sync(
            f"🌘 **BLESSREVOKE**\n👤 {player.get('name', target_id)} (`{target_id}`)\n"
            f"🔱 مُهرِ پس‌گرفته‌شده: {old_seal}\n🛠 ادمین: `{msg.from_user.id}`",
            "ADMIN"
        )
        await msg.answer(f"✅ مُهرِ **{DIVINE_SEALS.get(old_seal, {}).get('name', old_seal)}** ازش گرفته شد.")
        try:
            await bot.send_message(target_id, "🌘 یه مُهر ازت گرفته شد.")
        except Exception:
            pass

    @dp.message(Command("givexp"))
    @admin_only
    async def cmd_givexp(msg: Message):
        parts = msg.text.split()
        if len(parts) < 3:
            return await msg.answer("❌ استفاده: `/givexp <telegram_id> <عدد>`\nمثال: `/givexp 123456789 500`")
        target_id = resolve_target_id(parts[1])
        try:
            amount = int(parts[2])
        except ValueError:
            return await msg.answer("❌ مقدار XP باید عدد باشه")
        if target_id is None:
            return await msg.answer("❌ آیدی باید عدد باشه")
        player = await aget_player(target_id)
        if not player:
            return await msg.answer("❌ بازیکن پیدا نشد")

        player["xp"] = max(0, player.get("xp", 0) + amount)
        old_level = player["level"]
        await asave_player(target_id, player)
        player = await aget_player(target_id)
        leveled = player["level"] > old_level

        log_sync(
            f"✨ **GIVEXP**\n"
            f"👤 {player.get('name', target_id)} (`{target_id}`)\n"
            f"📊 +{amount:,} XP\n"
            f"🛠 ادمین: `{msg.from_user.id}`",
            "ADMIN"
        )

        lvl_txt = f"\n🎉 لول‌آپ! → سطح {player['level']}" if leveled else ""
        await msg.answer(f"✅ {amount:+,} XP به **{player.get('name', target_id)}** داده شد.{lvl_txt}")

    @dp.message(Command("sethp"))
    @admin_only
    async def cmd_sethp(msg: Message):
        parts = msg.text.split()
        if len(parts) < 3:
            return await msg.answer("❌ استفاده: `/sethp <telegram_id> <عدد>`\nمثال: `/sethp 123456789 100`")
        target_id = resolve_target_id(parts[1])
        try:
            amount = int(parts[2])
        except ValueError:
            return await msg.answer("❌ مقدار HP باید عدد باشه")
        if target_id is None:
            return await msg.answer("❌ آیدی باید عدد باشه")
        player = await aget_player(target_id)
        if not player:
            return await msg.answer("❌ بازیکن پیدا نشد")
        max_hp = player.get("max_hp", 100)
        player["hp"] = max(0, min(max_hp, amount))
        await asave_player(target_id, player)
        
        log_sync(
            f"❤️ **SETHP**\n"
            f"👤 {player.get('name', target_id)} (`{target_id}`)\n"
            f"HP: {player['hp']}/{max_hp}\n"
            f"🛠 ادمین: `{msg.from_user.id}`",
            "ADMIN"
        )
        
        await msg.answer(f"✅ HP **{player.get('name', target_id)}** روی {player['hp']}/{max_hp} تنظیم شد.")

    @dp.message(Command("setlevel"))
    @admin_only
    async def cmd_setlevel(msg: Message):
        """
        لولِ یه بازیکن رو مستقیم روی یه عدد می‌ذاره — انگار خودش تا اون لول
        گرایند کرده: XP/HP/امتیازِ مهارت هماهنگ می‌شن، چندتا لوتِ رندوم
        (بر اساسِ نقشه‌ی فعلی‌ش) بهش می‌رسه، و خودِ بازیکن هم پیام می‌گیره.
        استفاده: /setlevel <telegram_id> <لول> [تعداد لوت رندوم=3]
        """
        parts = msg.text.split()
        if len(parts) < 3:
            return await msg.answer(
                "❌ استفاده: `/setlevel <telegram_id> <لول> [تعداد لوت=3]`\n"
                "مثال: `/setlevel 123456789 7`\n"
                "مثال با لوت بیشتر: `/setlevel 123456789 7 5`"
            )
        target_id = resolve_target_id(parts[1])
        if target_id is None:
            return await msg.answer("❌ آیدی باید عدد باشه")
        try:
            target_level = int(parts[2])
        except ValueError:
            return await msg.answer("❌ لول باید عدد باشه")

        loot_count = 3
        if len(parts) >= 4:
            try:
                loot_count = max(0, min(10, int(parts[3])))
            except ValueError:
                pass

        player = await aget_player(target_id)
        if not player:
            return await msg.answer("❌ بازیکن پیدا نشد")
        if not player.get("character"):
            return await msg.answer("❌ این بازیکن هنوز کاراکتر نگرفته")

        from game_data import effective_max_level, xp_for_level
        cap = effective_max_level(player)
        target_level = max(1, min(target_level, cap))
        old_level = player["level"]

        if target_level == old_level:
            return await msg.answer(f"ℹ️ **{player.get('name', target_id)}** از قبل لول {old_level} هست — تغییری ندادم.")

        # ─── هماهنگ‌سازیِ HP/XP مثلِ لول‌آپِ طبیعی (همون فرمولِ level_up_check) ───
        diff = target_level - old_level
        player["level"] = target_level
        player["max_hp"] = max(100, player.get("max_hp", 100) + 5 * diff)
        player["xp"] = (xp_for_level(target_level) - 1) if target_level < cap else player.get("xp", 0)

        from skill_tree import effective_max_hp, grant_levelup_points
        player["hp"] = effective_max_hp(player)

        pts = 0
        if target_level > old_level:
            pts = grant_levelup_points(player, old_level, target_level)

        # ─── لوتِ رندوم — انگار خودش تو نقشه‌ی فعلیش گشته ───
        from economy import roll_loot
        map_name = player.get("map") or "Sands of Eternity"
        loot = roll_loot(map_name, loot_count, player_level=player.get("level", 1))
        for item in loot:
            player.setdefault("inventory", []).append(item.copy())

        await asave_player(target_id, player)

        loot_lines = "\n".join(f"  • {it.get('emoji','🎁')} {it['name']}" for it in loot) if loot else "  (چیزی گیر نیومد)"
        direction_admin = "🎉 لول‌آپ" if target_level > old_level else "🔽 لول‌داون"

        log_sync(
            f"⭐ **ADMIN SETLEVEL**\n"
            f"👤 {player.get('name', target_id)} (`{target_id}`)\n"
            f"📊 سطح: {old_level} → {target_level}\n"
            f"🌟 امتیاز مهارت: +{pts}\n"
            f"🎁 لوت: {len(loot)} آیتم\n"
            f"🛠 ادمین: `{msg.from_user.id}`",
            "ADMIN"
        )

        await msg.answer(
            f"✅ **{player.get('name', target_id)}** {direction_admin}: سطح {old_level} → {target_level}\n"
            f"🌟 امتیاز مهارت: +{pts}\n"
            f"❤️ Max HP: {player['max_hp']}\n"
            f"🎁 لوت گرفته‌شده:\n{loot_lines}"
        )

        # ─── اطلاع به خودِ بازیکن ───
        try:
            player_msg = (
                f"⭐ **لول‌آپ!**\n"
                f"📊 سطح: {old_level} → {target_level}\n"
                f"🌟 امتیاز مهارت: +{pts}\n"
                f"❤️ Max HP: {player['max_hp']}\n"
            )
            if loot:
                player_msg += f"\n🎁 **لوتِ اضافی رسید:**\n{loot_lines}"
            await bot.send_message(target_id, player_msg)
        except Exception:
            pass

    @dp.message(Command("remitem"))
    @admin_only
    async def cmd_remitem(msg: Message):
        parts = msg.text.split()
        if len(parts) < 2:
            return await msg.answer("❌ استفاده: `/remitem <telegram_id>`\nمثال: `/remitem 123456789`")
        target_id = resolve_target_id(parts[1])
        if target_id is None:
            return await msg.answer("❌ آیدی باید عدد باشه")
        player = await aget_player(target_id)
        if not player:
            return await msg.answer("❌ بازیکن پیدا نشد")

        inv = player.get("inventory", [])
        if not inv:
            return await msg.answer(f"🎒 **{player.get('name', target_id)}** هیچ آیتمی تو کوله‌پشتیش نداره!")

        await _show_remitem_page(msg, target_id, player, inv, page=0)

    async def _show_remitem_page(msg_or_cb, target_id: int, player: dict, inv: list, page: int = 0):
        PAGE_SIZE = 9
        total_pages = max(1, (len(inv) - 1) // PAGE_SIZE + 1)
        start = page * PAGE_SIZE
        end   = start + PAGE_SIZE
        page_items = inv[start:end]
        
        text = (
            f"🎒 **کوله‌پشتی {player.get('name', target_id)}** (`{target_id}`)\n"
            f"📦 {len(inv)} آیتم | صفحه {page+1}/{total_pages}\n"
            f"{'─'*22}\n"
            f"برای حذف، روی آیتم کلیک کن:"
        )

        keyboard = []
        row = []
        for i, item in enumerate(page_items):
            real_idx = start + i
            btn_text = f"{item.get('emoji','📦')} {item['name'][:8]}"
            row.append(InlineKeyboardButton(
                text=btn_text,
                callback_data=f"admin_remitem_select:{target_id}:{real_idx}"
            , style=ButtonStyle.PRIMARY))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            while len(row) < 3:
                row.append(InlineKeyboardButton(text="⬜", callback_data="admin_remitem_empty", style=ButtonStyle.PRIMARY))
            keyboard.append(row)

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"admin_remitem_page:{target_id}:{page-1}", style=ButtonStyle.PRIMARY))
        nav.append(InlineKeyboardButton(text="❌ بستن", callback_data="admin_remitem_close", style=ButtonStyle.DANGER))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"admin_remitem_page:{target_id}:{page+1}", style=ButtonStyle.PRIMARY))
        keyboard.append(nav)

        kb = InlineKeyboardMarkup(inline_keyboard=keyboard)

        if isinstance(msg_or_cb, Message):
            await msg_or_cb.answer(text, reply_markup=kb)
        else:
            try:
                await msg_or_cb.message.edit_text(text, reply_markup=kb)
            except Exception:
                await msg_or_cb.answer(text, reply_markup=kb)

    @dp.callback_query(F.data == "admin_remitem_empty")
    async def cb_remitem_empty(cb: CallbackQuery):
        await cb.answer("⬜ جای خالی", show_alert=False)

    @dp.callback_query(F.data == "admin_remitem_close")
    async def cb_remitem_close(cb: CallbackQuery):
        try:
            await cb.message.edit_text("❌ حذف آیتم بسته شد.")
        except Exception:
            pass
        await cb.answer()

    @dp.callback_query(F.data.startswith("admin_remitem_page:"))
    async def cb_remitem_page(cb: CallbackQuery):
        parts = cb.data.split(":")
        target_id = int(parts[1])
        page = int(parts[2])
        
        if cb.from_user.id not in ADMIN_IDS:
            await cb.answer("❌ فقط ادمین!", show_alert=True)
            return
        
        player = await aget_player(target_id)
        if not player:
            await cb.answer("❌ بازیکن پیدا نشد!", show_alert=True)
            return
        
        inv = player.get("inventory", [])
        await _show_remitem_page(cb, target_id, player, inv, page)
        await cb.answer()

    @dp.callback_query(F.data.startswith("admin_remitem_select:"))
    async def cb_remitem_select(cb: CallbackQuery):
        parts = cb.data.split(":")
        target_id = int(parts[1])
        item_idx = int(parts[2])
        
        if cb.from_user.id not in ADMIN_IDS:
            await cb.answer("❌ فقط ادمین!", show_alert=True)
            return
        
        player = await aget_player(target_id)
        if not player:
            await cb.answer("❌ بازیکن پیدا نشد!", show_alert=True)
            return
        
        inv = player.get("inventory", [])
        if item_idx >= len(inv):
            await cb.answer("❌ آیتم پیدا نشد!", show_alert=True)
            return
        
        item = inv[item_idx]
        
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ آره، حذف کن", callback_data=f"admin_remitem_confirm:{target_id}:{item_idx}", style=ButtonStyle.DANGER),
            InlineKeyboardButton(text="❌ نه، لغو", callback_data="admin_remitem_cancel", style=ButtonStyle.DANGER),
        ]])
        
        await cb.message.edit_text(
            f"⚠️ **تایید حذف آیتم**\n\n"
            f"👤 **{player.get('name', target_id)}** (`{target_id}`)\n"
            f"📦 آیتم: {item.get('emoji','📦')} **{item.get('name','—')}**\n"
            f"💰 ارزش: {bz_to_display(item.get('sell',0))}\n\n"
            f"مطمئنی می‌خوای این آیتم رو حذف کنی؟",
            reply_markup=kb
        )
        await cb.answer()

    @dp.callback_query(F.data.startswith("admin_remitem_confirm:"))
    async def cb_remitem_confirm(cb: CallbackQuery):
        parts = cb.data.split(":")
        target_id = int(parts[1])
        item_idx = int(parts[2])
        
        if cb.from_user.id not in ADMIN_IDS:
            await cb.answer("❌ فقط ادمین!", show_alert=True)
            return
        
        player = await aget_player(target_id)
        if not player:
            await cb.answer("❌ بازیکن پیدا نشد!", show_alert=True)
            return
        
        inv = player.get("inventory", [])
        if item_idx >= len(inv):
            await cb.answer("❌ آیتم پیدا نشد!", show_alert=True)
            return
        
        removed = inv.pop(item_idx)
        player["inventory"] = inv
        await asave_player(target_id, player)
        
        log_sync(
            f"🗑️ **REMITEM**\n"
            f"👤 {player.get('name', target_id)} (`{target_id}`)\n"
            f"📦 حذف شد: {removed.get('name', 'نامشخص')}\n"
            f"🛠 ادمین: `{cb.from_user.id}`",
            "ADMIN"
        )
        
        await cb.message.edit_text(
            f"✅ **آیتم با موفقیت حذف شد!**\n\n"
            f"👤 **{player.get('name', target_id)}** (`{target_id}`)\n"
            f"📦 حذف شده: {removed.get('emoji','📦')} **{removed.get('name','—')}**"
        )
        
        await cb.answer("✅ حذف شد!", show_alert=True)

    @dp.callback_query(F.data == "admin_remitem_cancel")
    async def cb_remitem_cancel(cb: CallbackQuery):
        await cb.message.edit_text("❌ **حذف آیتم متوقف شد.**")
        await cb.answer("❌ لغو شد", show_alert=True)

    @dp.message(Command("playerreset"))
    @admin_only
    async def cmd_playerreset(msg: Message):
        parts = msg.text.split()
        if len(parts) < 2:
            return await msg.answer(
                "❌ استفاده: `/playerreset <telegram_id> [newchar]`\n"
                "مثال: `/playerreset 123456789` — ریستِ کامل (کاتانا هم صفر می‌شه)، فقط کاراکتر حفظ می‌مونه\n"
                "مثال: `/playerreset 123456789 newchar` — ریستِ کامل + یه کاراکترِ رندومِ جدید هم می‌گیره"
            )
        target_id = resolve_target_id(parts[1])
        if target_id is None:
            return await msg.answer("❌ آیدی باید عدد باشه")
        player = await aget_player(target_id)
        if not player:
            return await msg.answer("❌ بازیکن پیدا نشد")

        want_new_char = len(parts) > 2 and parts[2].strip().lower() == "newchar"
        _pending_reset[msg.from_user.id] = (target_id, want_new_char)
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ تایید ریست", callback_data="admin:reset_confirm", style=ButtonStyle.SUCCESS),
            InlineKeyboardButton(text="❌ لغو",        callback_data="admin:reset_cancel", style=ButtonStyle.DANGER),
        ]])
        char_line = (
            "🎲 یه کاراکترِ رندومِ **جدید** می‌گیره (کاراکترِ فعلی از دست می‌ره)."
            if want_new_char else
            "🛡 **فقط کاراکتر حفظ می‌مونه — کاتانا (لول/بوند/کیل/...) هم صفر می‌شه.**"
        )
        await msg.answer(
            f"⚠️ مطمئنی می‌خوای **{player.get('name', target_id)}** (`{target_id}`) رو کامل ریست کنی؟\n"
            f"سطح، XP، Zen، کوله‌پشتی، مهارت‌ها، گیلد، بانک، کازینو، PvP، دستاوردها و همه‌ی پیشرفت صفر می‌شه.\n"
            f"{char_line}\n"
            f"این کار برگشت‌پذیر نیست!",
            reply_markup=kb
        )

    @admin_only
    async def cb_reset_confirm(cb: CallbackQuery):
        admin_id = cb.from_user.id
        pending  = _pending_reset.pop(admin_id, None)
        if pending is None:
            return await cb.answer("⏰ درخواست منقضی شد!", show_alert=True)
        target_id, want_new_char = pending

        player = await aget_player(target_id)
        if not player:
            return await cb.answer("❌ بازیکن پیدا نشد", show_alert=True)

        name = player.get("name", target_id)
        old_char = player.get("character")
        new_char = assign_random_char() if want_new_char else None
        # 🆕 باگ‌فیکس: همینجا هم کاراکترِ قبلی هیچ‌وقت release نمی‌شد.
        if want_new_char and old_char and old_char != new_char:
            release_char(old_char)
        fresh = full_reset_player(target_id, new_character=new_char)
        if fresh is None:
            return await cb.answer("❌ بازیکن پیدا نشد", show_alert=True)

        log_sync(
            f"🔄 **PLAYERRESET**\n"
            f"👤 {name} (`{target_id}`)\n"
            f"🎴 کاراکتر: {fresh['character']}{' (جدید)' if want_new_char else ' (حفظ شد)'}\n"
            f"🗡 کاتانا هم ریست شد\n"
            f"🛠 ادمین: `{cb.from_user.id}`",
            "ADMIN"
        )

        await cb.answer("✅ ریست شد!", show_alert=True)
        await cb.message.edit_text(
            f"✅ **{name}** (`{target_id}`) کاملاً ریست شد (کاتانا هم صفر شد)!\n"
            f"🎴 کاراکتر: **{fresh['character']}**{' (جدید)' if want_new_char else ' (حفظ شد)'}"
        )
        try:
            await bot.send_message(target_id, "⚠️ اکانت تو توسط ادمین ریست شد! (فقط کاراکترت حفظ شده، کاتانا و بقیه‌ی پیشرفت صفر شد)")
        except Exception:
            pass

    async def cb_reset_cancel(cb: CallbackQuery):
        _pending_reset.pop(cb.from_user.id, None)
        await cb.answer("لغو شد.")
        await cb.message.edit_text("❌ ریست لغو شد.")

    dp.callback_query.register(cb_reset_confirm, F.data == "admin:reset_confirm")
    dp.callback_query.register(cb_reset_cancel,  F.data == "admin:reset_cancel")

    @dp.message(Command("resetall"))
    @admin_only
    async def cmd_resetall(msg: Message):
        players = all_players()
        _pending_reset_all[msg.from_user.id] = True
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ تایید ریست همه", callback_data="admin:resetall_confirm", style=ButtonStyle.SUCCESS),
            InlineKeyboardButton(text="❌ لغو",            callback_data="admin:resetall_cancel", style=ButtonStyle.DANGER),
        ]])
        await msg.answer(
            f"⚠️⚠️ **ریست کامل همه‌ی بازیکن‌ها ({len(players)} نفر)!** ⚠️⚠️\n\n"
            f"سطح، XP، Zen، کوله‌پشتی، مهارت‌ها، گیلد، بانک/وام/سهام، کازینو، بتل‌پس، PvP، 🗡 کاتانا "
            f"(لول/بوند/کیل/...) و همه‌ی آمار و دستاوردها صفر می‌شه.\n"
            f"✅ فقط کاراکترِ فعلیِ هر بازیکن حفظ می‌مونه.\n"
            f"✅ وضعیتِ بن، یادداشتِ ادمین و مُهرِ الهی هم دست‌نخورده می‌مونه.\n"
            f"این کار برگشت‌پذیر نیست. مطمئنی؟",
            reply_markup=kb
        )

    @admin_only
    async def cb_resetall_confirm(cb: CallbackQuery):
        admin_id = cb.from_user.id
        if not _pending_reset_all.pop(admin_id, False):
            return await cb.answer("⏰ درخواست منقضی شد!", show_alert=True)

        players = all_players()
        await cb.answer("⏳ شروعِ ریست...", show_alert=True)
        await cb.message.edit_text(f"⏳ در حال ریستِ {len(players)} بازیکن...")

        done, failed = 0, 0
        for pid in players:
            try:
                fresh = full_reset_player(int(pid))
                if fresh is not None:
                    done += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

        log_sync(
            f"🔄 **RESETALL**\n"
            f"👥 {done} بازیکن ریست شدند" + (f" ({failed} خطا)" if failed else "") + "\n"
            f"🛠 ادمین: `{cb.from_user.id}`",
            "ADMIN"
        )

        fail_line = f"\n⚠️ {failed} بازیکن با خطا مواجه شدن (لاگ رو چک کن)." if failed else ""
        await cb.message.edit_text(
            f"✅ **{done} بازیکن کاملاً ریست شدن.**\n"
            f"فقط کاراکترِ همه حفظ موند — کاتانا و بقیه‌ی پیشرفت (شاملِ بانک/کازینو/بتل‌پس) صفر شد.{fail_line}"
        )
        for pid in players:
            try:
                await bot.send_message(int(pid), "⚠️ سرور یه ریست کامل خورد — پیشرفتِ عمومیت و کاتانات صفر شد، ولی کاراکترت دست‌نخورده موند!")
            except Exception:
                pass
            await asyncio.sleep(0.05)

    async def cb_resetall_cancel(cb: CallbackQuery):
        _pending_reset_all.pop(cb.from_user.id, None)
        await cb.answer("لغو شد.")
        await cb.message.edit_text("❌ ریست‌آل لغو شد.")

    dp.callback_query.register(cb_resetall_confirm, F.data == "admin:resetall_confirm")
    dp.callback_query.register(cb_resetall_cancel,  F.data == "admin:resetall_cancel")

    @dp.message(Command("broadcast"))
    @admin_only
    async def cmd_broadcast(msg: Message):
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2:
            return await msg.answer("❌ استفاده: `/broadcast <پیام>`\nمثال: `/broadcast تعمیرات امشب ساعت ۱۲!`")

        text = f"📢 **پیام همگانی از ادمین:**\n\n{parts[1]}"
        players = all_players()
        await msg.answer(f"📨 در حال ارسال به {len(players)} بازیکن...")

        log_sync(
            f"📢 **BROADCAST**\n"
            f"🛠 ادمین: `{msg.from_user.id}`\n"
            f"📝 متن: {parts[1][:200]}{'...' if len(parts[1]) > 200 else ''}",
            "ADMIN"
        )

        sent, failed = 0, 0
        for pid in players:
            try:
                await bot.send_message(int(pid), text)
                sent += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.05)

        await msg.answer(f"✅ ارسال شد به {sent} نفر" + (f" | ❌ ناموفق برای {failed} نفر" if failed else ""))

    @dp.message(Command("gbroadcast"))
    @admin_only
    async def cmd_gbroadcast(msg: Message):
        """مثلِ /broadcast ولی به‌جای پیامِ خصوصی به تک‌تکِ بازیکن‌ها، پیام رو
        مستقیم تو خودِ همه‌ی گروه‌هایی که ربات توشونه پست می‌کنه — یه اعلانِ
        عمومی که همه‌ی اعضای گروه (حتی کسایی که هنوز /start نزدن) می‌بینن."""
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2:
            return await msg.answer("❌ استفاده: `/gbroadcast <پیام>`\nمثال: `/gbroadcast رِیدِ باسِ ویژه امشب ساعت ۲۲!`")

        from group_system import known_group_chat_ids
        text = f"📢 **اعلانِ همگانی**\n\n{parts[1]}"
        chat_ids = known_group_chat_ids()
        await msg.answer(f"📨 در حال ارسال به {len(chat_ids)} گروه...")

        log_sync(
            f"📢 **GROUP BROADCAST**\n"
            f"🛠 ادمین: `{msg.from_user.id}`\n"
            f"👥 تعدادِ گروه‌ها: {len(chat_ids)}\n"
            f"📝 متن: {parts[1][:200]}{'...' if len(parts[1]) > 200 else ''}",
            "ADMIN"
        )

        sent, failed = 0, 0
        for chat_id in chat_ids:
            try:
                await bot.send_message(int(chat_id), text)
                sent += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.08)

        await msg.answer(f"✅ تو {sent} گروه پست شد" + (f" | ❌ ناموفق برای {failed} گروه" if failed else ""))

    @dp.message(Command("suspects"))
    @admin_only
    async def cmd_suspects(msg: Message):
        """🆕 ضد-فارم: چند تا الگوی ساده و ابتدایی برای پیدا کردنِ بازیکن‌های مشکوک (چند‌اکانتی/تقلب)."""
        flags = _scan_suspects()
        if not flags:
            await msg.answer("✅ فعلاً هیچ الگوی مشکوکی پیدا نشد.")
            return
        text = "🚨 **گزارشِ ناهنجاری** (فقط هشدار — لزوماً تقلب نیست)\n\n" + "\n".join(flags[:30])
        if len(flags) > 30:
            text += f"\n\n_...و {len(flags)-30} موردِ دیگه_"
        await msg.answer(text)

    def _scan_suspects() -> list[str]:
        players = all_players()
        flags = []
        for pid, p in players.items():
            level = p.get("level", 1)
            zen = p.get("zen", 0)
            kills = p.get("kills", 0)
            expected_zen_cap = max(2000, level * 800 + kills * 60)
            if zen > expected_zen_cap * 3:
                flags.append(f"💰 `{pid}` ({p.get('name','—')}) — Zen={zen:,} ولی سطح={level}, کشتار={kills} (انتظار: زیرِ {expected_zen_cap*3:,})")
            if level > 10 and kills < level * 2:
                flags.append(f"⚡ `{pid}` ({p.get('name','—')}) — سطح={level} با فقط {kills} کشتار (رشدِ غیرعادی)")
        return flags

    async def _auto_suspects_loop():
        """هر ۶ ساعت یه بار خودکار اسکن می‌کنه و اگه چیزی پیدا شد به کانالِ لاگ می‌فرسته."""
        while True:
            await asyncio.sleep(6 * 3600)
            try:
                flags = _scan_suspects()
                if flags:
                    text = "🚨 **اسکنِ خودکارِ ضدفارم**\n\n" + "\n".join(flags[:25])
                    if len(flags) > 25:
                        text += f"\n\n_...و {len(flags)-25} موردِ دیگه_"
                    from logger import send_log
                    await send_log(text, "WARN")
            except Exception:
                pass

    asyncio.create_task(_auto_suspects_loop())

    # ═══════════════════════════════════════════════════════════
    #  پنل یکپارچه‌ی ویرایش پلیر (دکمه‌های زیر /info و /find)
    # ═══════════════════════════════════════════════════════════

    _ACTION_PROMPTS = {
        "xp":   "✨ چند XP اضافه/کم بشه؟ (عدد منفی هم می‌تونی بفرستی، مثلاً `-200`)",
        "zen":  "💰 چقدر Zen اضافه/کم بشه؟ (عدد منفی برای کم‌کردن، مثلاً `-500`)",
        "hp":   "❤️ HP رو روی چند تنظیم کنم؟",
        "char": "🎴 اسم دقیقِ کاراکترِ جدید رو بفرست.",
        "note": "📝 متنِ یادداشتِ ادمین رو بفرست. (برای پاک‌کردن، بنویس `-`)",
    }

    @dp.callback_query(F.data.startswith("padm:"))
    @admin_only
    async def cb_player_editor(cb: CallbackQuery):
        parts = cb.data.split(":")
        action = parts[1]

        if action == "close":
            try:
                await cb.message.edit_text("❌ پنل بسته شد.")
            except Exception:
                pass
            return await cb.answer()

        if action == "open":
            target_id = int(parts[2])
            player = await aget_player(target_id)
            if not player:
                return await cb.answer("❌ بازیکن پیدا نشد", show_alert=True)
            await cb.message.edit_text(
                player_summary(target_id, player),
                reply_markup=player_editor_kb(target_id, bool(player.get("banned")))
            )
            return await cb.answer()

        target_id = int(parts[2])
        player = await aget_player(target_id)
        if not player:
            return await cb.answer("❌ بازیکن پیدا نشد", show_alert=True)

        if action in ("xp", "zen", "hp", "char", "note"):
            _pending_action[cb.from_user.id] = {"action": action, "target_id": target_id}
            await cb.answer()
            return await cb.message.answer(
                f"{_ACTION_PROMPTS[action]}\n\n👤 هدف: **{player.get('name', target_id)}** (`{target_id}`)\n"
                f"برای لغو، `/cancel` رو بفرست."
            )

        if action == "items":
            inv = player.get("inventory", [])
            if not inv:
                return await cb.answer("🎒 کوله‌پشتیش خالیه!", show_alert=True)
            await cb.answer()
            return await _show_remitem_page(cb, target_id, player, inv, page=0)

        if action == "ban":
            player["banned"] = True
            await asave_player(target_id, player)
            log_sync(f"🚫 **BAN** (پنل)\n👤 {player.get('name', target_id)} (`{target_id}`)\n🛠 ادمین: `{cb.from_user.id}`", "BAN")
            await cb.answer("🚫 بن شد", show_alert=True)
            try:
                await bot.send_message(target_id, "🚫 اکانت تو توسط ادمین بن شد.")
            except Exception:
                pass
            return await cb.message.edit_text(player_summary(target_id, player), reply_markup=player_editor_kb(target_id, True))

        if action == "unban":
            player["banned"] = False
            player["ban_reason"] = None
            await asave_player(target_id, player)
            log_sync(f"✅ **UNBAN** (پنل)\n👤 {player.get('name', target_id)} (`{target_id}`)\n🛠 ادمین: `{cb.from_user.id}`", "BAN")
            await cb.answer("✅ آنبن شد", show_alert=True)
            return await cb.message.edit_text(player_summary(target_id, player), reply_markup=player_editor_kb(target_id, False))

        if action == "reset":
            _pending_reset[cb.from_user.id] = target_id
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ تایید ریست", callback_data="admin:reset_confirm", style=ButtonStyle.SUCCESS),
                InlineKeyboardButton(text="❌ لغو",        callback_data="admin:reset_cancel", style=ButtonStyle.DANGER),
            ]])
            await cb.answer()
            return await cb.message.answer(
                f"⚠️ مطمئنی می‌خوای **{player.get('name', target_id)}** (`{target_id}`) رو کامل ریست کنی؟\n"
                f"🛡 کاراکتر حفظ میشه! برگشت‌پذیر نیست.",
                reply_markup=kb
            )

    @dp.message(Command("cancel"))
    @admin_only
    async def cmd_cancel_pending(msg: Message):
        if _pending_action.pop(msg.from_user.id, None) is not None:
            await msg.answer("❌ لغو شد.")
        else:
            await msg.answer("چیزی برای لغو‌کردن نبود.")

    async def _pending_action_filter(msg: Message) -> bool:
        return (
            msg.from_user is not None
            and msg.from_user.id in _pending_action
            and msg.from_user.id in ADMIN_IDS
            and bool(msg.text)
            and not msg.text.startswith("/")
        )

    @dp.message(_pending_action_filter)
    async def handle_pending_action(msg: Message):
        state = _pending_action.pop(msg.from_user.id, None)
        if state is None:
            return
        action, target_id = state["action"], state["target_id"]
        player = await aget_player(target_id)
        if not player:
            return await msg.answer("❌ بازیکن دیگه پیدا نشد.")
        text = msg.text.strip()

        if action == "xp":
            try:
                amount = int(text)
            except ValueError:
                return await msg.answer("❌ باید یه عدد باشه.")
            player["xp"] = max(0, player.get("xp", 0) + amount)
            old_level = player["level"]
            await asave_player(target_id, player)
            player = await aget_player(target_id)
            leveled = player["level"] > old_level
            log_sync(f"✨ **GIVEXP** (پنل)\n👤 {player.get('name', target_id)} (`{target_id}`)\n📊 {amount:+,} XP\n🛠 ادمین: `{msg.from_user.id}`", "ADMIN")
            lvl_txt = f"\n🎉 لول‌آپ! → سطح {player['level']}" if leveled else ""
            await msg.answer(f"✅ {amount:+,} XP برای **{player.get('name', target_id)}** ثبت شد.{lvl_txt}")

        elif action == "zen":
            try:
                amount = int(text)
            except ValueError:
                return await msg.answer("❌ باید یه عدد باشه.")
            player["zen"] = max(0, player.get("zen", 0) + amount)
            await asave_player(target_id, player)
            log_sync(f"💰 **ZEN-EDIT** (پنل)\n👤 {player.get('name', target_id)} (`{target_id}`)\n💰 {amount:+,} Zen → موجودی: {player['zen']:,}\n🛠 ادمین: `{msg.from_user.id}`", "ADMIN")
            await msg.answer(f"✅ {amount:+,} Zen ثبت شد. موجودیِ فعلی: **{bz_to_display(player['zen'])}**")

        elif action == "hp":
            try:
                amount = int(text)
            except ValueError:
                return await msg.answer("❌ باید یه عدد باشه.")
            max_hp = player.get("max_hp", 100)
            player["hp"] = max(0, min(max_hp, amount))
            await asave_player(target_id, player)
            log_sync(f"❤️ **SETHP** (پنل)\n👤 {player.get('name', target_id)} (`{target_id}`)\nHP: {player['hp']}/{max_hp}\n🛠 ادمین: `{msg.from_user.id}`", "ADMIN")
            await msg.answer(f"✅ HP روی {player['hp']}/{max_hp} تنظیم شد.")

        elif action == "char":
            char_name = find_character_name(text)
            if not char_name:
                close = [n for n in ALL_CHARACTERS if text.lower() in n.lower()]
                hint = ("\nشاید:\n" + "\n".join(f"• {n}" for n in close[:5])) if close else ""
                return await msg.answer(f"❌ کاراکتر **{text}** وجود نداره!{hint}")
            player["character"] = char_name
            assign_special_char(char_name)
            await asave_player(target_id, player)
            log_sync(f"🎴 **CHARGGRANT** (پنل)\n👤 {player.get('name', target_id)} (`{target_id}`)\n🎴 {char_name}\n🛠 ادمین: `{msg.from_user.id}`", "ADMIN")
            await msg.answer(f"✅ **{char_name}** داده شد!")
            try:
                await bot.send_message(target_id, f"👑 ادمین یه کاراکتر جدید بهت داد: **{char_name}**!")
            except Exception:
                pass

        elif action == "note":
            note = None if text == "-" else text[:300]
            player["admin_note"] = note
            await asave_player(target_id, player)
            await msg.answer("✅ یادداشت ذخیره شد." if note else "✅ یادداشت پاک شد.")

        await msg.answer(player_summary(target_id, player), reply_markup=player_editor_kb(target_id, bool(player.get("banned"))))

    # ═══════════════════════════════════════════════════════════
    #  اکشن‌های گروهی (Mass Actions)
    # ═══════════════════════════════════════════════════════════

    @dp.message(Command("massgivezen"))
    @admin_only
    async def cmd_massgivezen(msg: Message):
        parts = msg.text.split()
        if len(parts) < 2:
            return await msg.answer(
                "❌ استفاده: `/massgivezen <عدد> [حداقل‌سطح] [حداکثر‌سطح]`\n"
                "مثال: `/massgivezen 1000` (به همه)\n"
                "مثال: `/massgivezen 1000 1 10` (فقط سطح ۱ تا ۱۰)"
            )
        try:
            amount = int(parts[1])
        except ValueError:
            return await msg.answer("❌ مقدار باید عدد باشه")
        min_lvl = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        max_lvl = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 10_000

        players = all_players()
        targets = [(pid, p) for pid, p in players.items() if min_lvl <= p.get("level", 1) <= max_lvl]
        if not targets:
            return await msg.answer("❌ هیچ بازیکنی تو این بازه‌ی سطح نیست.")

        await msg.answer(f"⏳ در حال دادن {amount:+,} Zen به {len(targets)} بازیکن...")
        for pid, p in targets:
            p["zen"] = max(0, p.get("zen", 0) + amount)
            await asave_player(int(pid), p)
        log_sync(f"💰 **MASSGIVEZEN**\n👥 {len(targets)} بازیکن (سطح {min_lvl}-{max_lvl})\n💰 {amount:+,} Zen\n🛠 ادمین: `{msg.from_user.id}`", "ADMIN")
        await msg.answer(f"✅ {amount:+,} Zen به {len(targets)} بازیکن داده شد.")

    @dp.message(Command("massgivexp"))
    @admin_only
    async def cmd_massgivexp(msg: Message):
        parts = msg.text.split()
        if len(parts) < 2:
            return await msg.answer(
                "❌ استفاده: `/massgivexp <عدد> [حداقل‌سطح] [حداکثر‌سطح]`\n"
                "مثال: `/massgivexp 500`"
            )
        try:
            amount = int(parts[1])
        except ValueError:
            return await msg.answer("❌ مقدار باید عدد باشه")
        min_lvl = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        max_lvl = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 10_000

        players = all_players()
        targets = [(pid, p) for pid, p in players.items() if min_lvl <= p.get("level", 1) <= max_lvl]
        if not targets:
            return await msg.answer("❌ هیچ بازیکنی تو این بازه‌ی سطح نیست.")

        await msg.answer(f"⏳ در حال دادن {amount:+,} XP به {len(targets)} بازیکن...")
        for pid, p in targets:
            p["xp"] = max(0, p.get("xp", 0) + amount)
            await asave_player(int(pid), p)
        log_sync(f"✨ **MASSGIVEXP**\n👥 {len(targets)} بازیکن (سطح {min_lvl}-{max_lvl})\n📊 {amount:+,} XP\n🛠 ادمین: `{msg.from_user.id}`", "ADMIN")
        await msg.answer(f"✅ {amount:+,} XP به {len(targets)} بازیکن داده شد. (لول‌آپ‌ها دفعه‌ی بعد که وارد بشن اعمال می‌شه)")

    @dp.message(Command("note"))
    @admin_only
    async def cmd_note(msg: Message):
        parts = msg.text.split(maxsplit=2)
        if len(parts) < 2:
            return await msg.answer("❌ استفاده: `/note <telegram_id> [متن]`\nبدون متن یعنی نمایش یادداشتِ فعلی. `-` یعنی پاک‌کردن.")
        target_id = resolve_target_id(parts[1])
        if target_id is None:
            return await msg.answer("❌ آیدی باید عدد باشه")
        player = await aget_player(target_id)
        if not player:
            return await msg.answer("❌ بازیکن پیدا نشد")
        if len(parts) < 3:
            note = player.get("admin_note")
            return await msg.answer(f"📝 یادداشتِ فعلی: {note or '—'}")
        note = None if parts[2].strip() == "-" else parts[2].strip()[:300]
        player["admin_note"] = note
        await asave_player(target_id, player)
        await msg.answer("✅ یادداشت ذخیره شد." if note else "✅ یادداشت پاک شد.")

    print("✅ Admin Panel Loaded Successfully")
