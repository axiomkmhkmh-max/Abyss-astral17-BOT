# ============================================================
#  ASTRAL ABYSS RPG — پنل «🗡️ نمسیسِ من»
#  نمایشِ نمسیسِ فعلی (اگه باشه) با آمار و تواناییِ ویژه‌ش، به‌علاوه
#  تاریخچه‌ی نمسیس‌هایی که تا حالا شکست دادی و عنوان‌های دائمی‌شون.
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, aget_player
from nemesis_system import NEMESIS_TITLES, NEMESIS_ABILITIES

HISTORY_PAGE_SIZE = 5


def _home_kb(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 تاریخچه‌ی نمسیس‌ها", callback_data=f"nem_hist:0:{uid}", style=ButtonStyle.PRIMARY)],
    ])


def _render_home(player: dict) -> str:
    nem = player.get("nemesis")
    lines = ["🗡️ **نمسیسِ من** 🗡️\n"]
    if not nem:
        lines.append(
            "👁️ فعلاً هیچ نمسیسی دنبالت نیست.\n\n"
            "اگه از یه دشمنِ معمولی فرار کنی یا ازش شکست بخوری، یه شانسی هست "
            "که اون دشمن رو «به یاد بسپاری» — بعداً قوی‌تر برمی‌گرده سراغت."
        )
    else:
        tier = nem.get("tier", 0)
        title = NEMESIS_TITLES[tier] if tier < len(NEMESIS_TITLES) else NEMESIS_TITLES[-1]
        mult = 1 + 0.25 * (tier + 1)
        hp = int(nem.get("hp", 100) * mult)
        dmg = int(nem.get("dmg", 10) * mult)
        lines.append(
            f"⚔️ **{nem.get('base_name','؟')} {title}**\n\n"
            f"🎚 تشدید: {tier + 1}/{len(NEMESIS_TITLES)}\n"
            f"🔴 HP تخمینی دفعه‌ی بعد: {hp:,}\n"
            f"💥 دمیج تخمینی: {dmg:,}\n"
            f"🔁 تعداد مواجهه: {nem.get('encounters', 1)}\n"
            f"🧪 نقطه‌ضعف: {nem.get('weak','—')}\n"
        )
        if tier >= 1:
            possible = [n for n, a in NEMESIS_ABILITIES.items() if tier >= a["min_tier"]]
            if possible:
                lines.append(f"\n👁️‍🗨️ ممکنه یکی از این توانایی‌های ویژه رو (وقتی HPش زیرِ ۵۰٪ بره) فعال کنه: "
                              + "، ".join(possible))
        lines.append("\n⚠️ شانسی هست که تو نقشه‌ها دوباره ظاهر بشه. شکستش بده تا این دشمنی تموم شه و یه عنوانِ دائمی بگیری.")
    return "\n".join(lines)


async def cmd_nemesis(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    await msg.answer(_render_home(player), reply_markup=_home_kb(uid))


async def cb_nem_home(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if cb.from_user.id != uid:
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    await cb.answer()
    await cb.message.edit_text(_render_home(player), reply_markup=_home_kb(uid))


async def cb_nem_history(cb: CallbackQuery):
    _, page_s, uid_s = cb.data.split(":")
    page, uid = int(page_s), int(uid_s)
    if cb.from_user.id != uid:
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    history = list(reversed(player.get("nemesis_history", [])))
    await cb.answer()

    if not history:
        await cb.message.edit_text(
            "📜 هنوز هیچ نمسیسی رو شکست ندادی.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"nem_home:{uid}", style=ButtonStyle.PRIMARY)]
            ])
        )
        return

    chunk = history[page * HISTORY_PAGE_SIZE:(page + 1) * HISTORY_PAGE_SIZE]
    lines = [f"📜 **تاریخچه‌ی نمسیس‌ها** (صفحه {page + 1})\n"]
    for h in chunk:
        tier = h.get("tier", 0)
        title = NEMESIS_TITLES[tier] if tier < len(NEMESIS_TITLES) else NEMESIS_TITLES[-1]
        lines.append(
            f"\n🩸 **{h.get('name','؟')} {title}** — {h.get('encounters',1)} مواجهه\n"
            f"   🏅 عنوان: شکارچیِ {h.get('name','؟')}"
        )

    buttons = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ قبلی", callback_data=f"nem_hist:{page-1}:{uid}", style=ButtonStyle.PRIMARY))
    if (page + 1) * HISTORY_PAGE_SIZE < len(history):
        nav.append(InlineKeyboardButton(text="➡️ بعدی", callback_data=f"nem_hist:{page+1}:{uid}", style=ButtonStyle.PRIMARY))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"nem_home:{uid}", style=ButtonStyle.PRIMARY)])

    await cb.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


def register_nemesis_handlers(dp, bot):
    dp.message.register(cmd_nemesis, Command("nemesis"))
    dp.callback_query.register(cb_nem_home, F.data.startswith("nem_home:"))
    dp.callback_query.register(cb_nem_history, F.data.startswith("nem_hist:"))
