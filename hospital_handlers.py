# ============================================================
#  ASTRAL ABYSS — 🏥 بیمارستان (Hospital Hub) — hospital_handlers.py
# ------------------------------------------------------------
#  قبلاً دکمه‌ی «💊 درمان» فقط یه منویِ خریدِ پوشن (HP) بود. زخم‌های
#  دائمیِ combat_handlers.py (INJURY_THRESHOLDS: زخمِ کهنه/شکستگی/
#  نفرینِ دائمی) هیچ‌وقت قابل‌درمان نبودن — یه‌بار می‌گرفتیشون، برای
#  همیشه می‌موندن. این فایل دقیقاً همون خلأ رو پر می‌کنه:
#
#    🏥 بیمارستان (جایگزینِ دکمه‌ی درمانِ قبلی)
#      ├─ 💊 درمانِ سریعِ HP        → همون منوی قبلی (team_handlers)
#      ├─ 🩹 درمانِ زخم‌های دائمی    → جدید: هر injury با هزینه‌ی خودش قابل‌درمانه
#      └─ 👻 رفعِ زودهنگامِ نفرینِ مرگ → جدید: به‌جای صبرِ ۳ روزه، با هزینه فوراً پاک می‌شه
#
#  /heal قدیمی هم دست‌نخورده می‌مونه (شورتکاتِ مستقیم به تبِ HP)، ولی
#  دکمه‌ی اصلیِ منو الان اول میاره آدمو به همین هاب.
# ============================================================
import time
from aiogram import Dispatcher, F, Bot
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from economy import bz_to_display
from skill_tree import effective_max_hp
from combat_handlers import (
    curse_active, DEATH_CURSE_DAYS, DEATH_CURSE_DMG_PEN, DEATH_CURSE_DEF_PEN,
)

# ─── هزینه‌ی درمانِ هر زخمِ دائمی — هرچی جدی‌تر، گرون‌تر ───────────
# annihilated عمداً اینجا نیست: اون خودش قبلاً یه ریست کامله، «زخم» باقی‌مونده‌ای نداره که درمان بشه.
INJURY_CURE = {
    "old_wound":  {"name": "🩸 زخم کهنه",     "desc": "همیشه -۵ Max HP",        "cost": 25_000},
    "fracture":   {"name": "🦴 شکستگی",       "desc": "همیشه -۵٪ دمیج",         "cost": 60_000},
    "curse_perm": {"name": "☠️ نفرین دائمی",  "desc": "همیشه -۱۰٪ تمام آمار",   "cost": 150_000},
}

DEATH_CURSE_EARLY_CLEAR_PER_DAY = 12_000  # هزینه به ازای هر روزِ باقی‌مونده‌ی نفرینِ مرگ


def _hp_bar(hp: int, max_hp: int, length: int = 10) -> str:
    filled = int(length * max(0, min(hp, max_hp)) / max(1, max_hp))
    return "❤️" * filled + "🖤" * (length - filled)


def _hospital_kb(player: dict) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="💊 درمانِ سریعِ HP", callback_data="hosp:heal_hp", style=ButtonStyle.SUCCESS)]]
    if player.get("injuries"):
        rows.append([InlineKeyboardButton(text="🩹 درمانِ زخم‌های دائمی", callback_data="hosp:injuries", style=ButtonStyle.DANGER)])
    if curse_active(player):
        rows.append([InlineKeyboardButton(text="👻 رفعِ زودهنگامِ نفرینِ مرگ", callback_data="hosp:curse", style=ButtonStyle.SUCCESS)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _hospital_text(player: dict) -> str:
    hp, max_hp = player.get("hp", 100), effective_max_hp(player)
    injuries = player.get("injuries", [])

    lines = [
        "🏥 **بیمارستانِ Abyss**",
        "_برخلافِ بیمارستانِ متروکه‌ی تو نقشه‌ها، اینجا واقعاً درمانت می‌کنن — به قیمتش._\n",
        f"❤️ HP: **{hp}/{max_hp}**",
        f"{_hp_bar(hp, max_hp)}\n",
    ]

    if not injuries:
        lines.append("🩹 **زخمِ دائمی:** نداری — سالمی. ✅")
    else:
        lines.append("🩹 **زخم‌های دائمی:**")
        for inj_id in injuries:
            info = INJURY_CURE.get(inj_id)
            if info:
                lines.append(f"• {info['name']} — {info['desc']} (درمان: {bz_to_display(info['cost'])})")
            elif inj_id == "annihilated":
                lines.append("• 💀 نابودی — قبلاً کامل ریست شدی، چیزی برای درمان نمونده.")

    if curse_active(player):
        remain_days = max(0, (player.get("death_curse_until", 0) - time.time()) / 86400)
        cure_cost = int(remain_days * DEATH_CURSE_EARLY_CLEAR_PER_DAY) + 1
        lines.append(
            f"\n👻 **نفرینِ مرگ فعاله** — {remain_days:.1f} روزِ دیگه مونده "
            f"(-{int(DEATH_CURSE_DMG_PEN*100)}٪ دمیج، -{int(DEATH_CURSE_DEF_PEN*100)}٪ دفاع)\n"
            f"   رفعِ زودهنگام: {bz_to_display(cure_cost)}"
        )

    lines.append(f"\n💰 موجودی: **{bz_to_display(player.get('zen', 0))}**")
    return "\n".join(lines)


async def cmd_hospital(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    await msg.answer(_hospital_text(player), reply_markup=_hospital_kb(player))


async def cb_hospital_menu(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return
    await cb.message.edit_text(_hospital_text(player), reply_markup=_hospital_kb(player))
    await cb.answer()


async def cb_hospital_heal_hp(cb: CallbackQuery):
    from team_handlers import cmd_heal_for
    await cmd_heal_for(cb.from_user.id, cb.message)
    await cb.answer()


async def cb_hospital_injuries(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return

    injuries = [i for i in player.get("injuries", []) if i in INJURY_CURE]
    if not injuries:
        await cb.answer("زخمِ قابل‌درمانی نداری.", show_alert=True)
        return

    rows = []
    zen = player.get("zen", 0)
    for inj_id in injuries:
        info = INJURY_CURE[inj_id]
        can_afford = zen >= info["cost"]
        rows.append([InlineKeyboardButton(
            text=f"{'✅' if can_afford else '❌'} درمانِ {info['name']} ({bz_to_display(info['cost'])})",
            callback_data=f"hosp:cure:{inj_id}", style=ButtonStyle.SUCCESS)])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="hosp:menu", style=ButtonStyle.PRIMARY)])

    await cb.message.edit_text(
        "🩹 **درمانِ زخم‌های دائمی**\n\nهر زخم که درمانش کنی، دیگه هیچ‌وقت روت اثر نمی‌ذاره.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await cb.answer()


async def cb_hospital_cure(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return

    inj_id = cb.data.split(":", 2)[2]
    info = INJURY_CURE.get(inj_id)
    if not info or inj_id not in player.get("injuries", []):
        await cb.answer("❌ این زخم دیگه روت نیست.", show_alert=True)
        return

    zen = player.get("zen", 0)
    if zen < info["cost"]:
        await cb.answer(f"❌ کافی نیست! نیازه: {bz_to_display(info['cost'])}", show_alert=True)
        return

    player["zen"] = zen - info["cost"]
    player["injuries"].remove(inj_id)
    # اثرِ ثابتی که موقعِ گرفتنِ زخم اعمال شده بود رو برمی‌گردونیم
    if inj_id == "old_wound":
        player["max_hp"] = player.get("max_hp", 100) + 5
        player["hp"] = min(player["hp"], effective_max_hp(player))
    await asave_player(uid, player)

    from logger import log_sync
    log_sync(f"🩹 **درمانِ زخمِ دائمی**\n👤 {player.get('name','—')} (`{uid}`)\n💊 {info['name']} — {bz_to_display(info['cost'])}", "INFO")

    await cb.message.edit_text(_hospital_text(player), reply_markup=_hospital_kb(player))
    await cb.answer(f"✅ {info['name']} کامل درمان شد!")


async def cb_hospital_curse(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player or not curse_active(player):
        await cb.answer("❌ نفرینِ مرگی فعال نیست.", show_alert=True)
        return

    remain_days = max(0, (player.get("death_curse_until", 0) - time.time()) / 86400)
    cost = int(remain_days * DEATH_CURSE_EARLY_CLEAR_PER_DAY) + 1

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ آره، پاکش کن ({bz_to_display(cost)})", callback_data="hosp:curse_confirm", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="hosp:menu", style=ButtonStyle.PRIMARY)],
    ])
    await cb.message.edit_text(
        f"👻 **رفعِ زودهنگامِ نفرینِ مرگ**\n\n"
        f"{remain_days:.1f} روزِ دیگه از نفرین مونده.\n"
        f"هزینه‌ی پاک‌کردنِ فوری: **{bz_to_display(cost)}**\n\n"
        f"مطمئنی؟",
        reply_markup=kb
    )
    await cb.answer()


async def cb_hospital_curse_confirm(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player or not curse_active(player):
        await cb.answer("❌ نفرینِ مرگی فعال نیست.", show_alert=True)
        return

    remain_days = max(0, (player.get("death_curse_until", 0) - time.time()) / 86400)
    cost = int(remain_days * DEATH_CURSE_EARLY_CLEAR_PER_DAY) + 1
    zen = player.get("zen", 0)
    if zen < cost:
        await cb.answer(f"❌ کافی نیست! نیازه: {bz_to_display(cost)}", show_alert=True)
        return

    player["zen"] = zen - cost
    player["death_curse_until"] = 0
    player["heal_lockout_until"] = 0
    await asave_player(uid, player)

    from logger import log_sync
    log_sync(f"👻 **رفعِ زودهنگامِ نفرینِ مرگ**\n👤 {player.get('name','—')} (`{uid}`)\n💰 -{bz_to_display(cost)}", "INFO")

    await cb.message.edit_text(_hospital_text(player), reply_markup=_hospital_kb(player))
    await cb.answer("✅ نفرینِ مرگ پاک شد!")


def register_hospital_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_hospital, Command("hospital"))
    dp.callback_query.register(cb_hospital_menu,          F.data == "hosp:menu")
    dp.callback_query.register(cb_hospital_heal_hp,       F.data == "hosp:heal_hp")
    dp.callback_query.register(cb_hospital_injuries,      F.data == "hosp:injuries")
    dp.callback_query.register(cb_hospital_cure,          F.data.startswith("hosp:cure:"))
    dp.callback_query.register(cb_hospital_curse,         F.data == "hosp:curse")
    dp.callback_query.register(cb_hospital_curse_confirm, F.data == "hosp:curse_confirm")
