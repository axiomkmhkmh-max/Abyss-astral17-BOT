# ============================================================
#  ASTRAL ABYSS — Stand Handlers (تلگرام) v3
# ------------------------------------------------------------
#  /stand یا دکمه‌ی «👻 استند من» → کارتِ استند + دکمه‌های:
#    - ارتقای هر ability با Zen (تک‌تک)
#    - evolve کردنِ ability‌هایی که سطح‌ماکس شدن (با فرگمنت)
#    - «🤝 تمرینِ استند» — کولداونی، رایگان، منبعِ Bond XP + فرگمنت
# ============================================================
from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
from stand_system import (
    get_stand, format_stand_card, upgrade_stand_ability, evolve_ability,
    ultimate_unlocked, ability_upgrade_cost, get_ability_levels,
    is_ability_evolved, ULTIMATE_KEY, MAX_ABILITY_LEVEL,
)
from stand_bond import train_bond
from codex_system import format_codex_card


def _ability_slots(player: dict, stand: dict):
    """[(callback_key, ability_name), ...] برای core + (در صورتِ باز بودن) اولتیمیت."""
    slots = [(str(i), a) for i, a in enumerate(stand["core_abilities"])]
    if ultimate_unlocked(player, stand):
        slots.append(("u", ULTIMATE_KEY))
    return slots


def _stand_kb(player: dict) -> InlineKeyboardMarkup:
    char_name = player.get("character", "")
    stand = get_stand(char_name)
    levels = get_ability_levels(player, stand)

    rows = []
    for key, ability in _ability_slots(player, stand):
        lvl = levels[ability]
        evolved = is_ability_evolved(player, ability)
        if evolved:
            continue
        label = ("🌟 اولتیمیت" if ability == ULTIMATE_KEY else ability)
        if lvl >= MAX_ABILITY_LEVEL:
            rows.append([InlineKeyboardButton(
                text=f"🧬 اوولوشنِ {label} (12 🧩)",
                callback_data=f"stand:evo:{key}",
            )])
        else:
            cost = ability_upgrade_cost(lvl)
            rows.append([InlineKeyboardButton(
                text=f"⬆️ {label} ({cost:,} Zen)",
                callback_data=f"stand:up:{key}",
            )])

    rows.append([InlineKeyboardButton(text="🤝 تمرینِ استند", callback_data="stand:train")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _resolve_ability(player: dict, stand: dict, key: str) -> str | None:
    if key == "u":
        return ULTIMATE_KEY
    try:
        return stand["core_abilities"][int(key)]
    except (ValueError, IndexError):
        return None


def register_stand_handlers(dp, bot):

    @dp.message(F.text == "👻 استند من")
    @dp.message(Command("stand"))
    async def cmd_stand(msg: Message):
        uid = msg.from_user.id
        player = get_player(uid)
        if not player:
            await msg.answer("❌ اول /start بزن!")
            return
        if not player.get("character"):
            await msg.answer("❌ اول باید کاراکترت رو بگیری!")
            return
        await msg.answer(format_stand_card(player), reply_markup=_stand_kb(player))

    @dp.message(F.text == "📖 کدکس")
    @dp.message(Command("codex"))
    async def cmd_codex(msg: Message):
        uid = msg.from_user.id
        player = get_player(uid)
        if not player:
            await msg.answer("❌ اول /start بزن!")
            return
        await msg.answer(format_codex_card(player))

    @dp.callback_query(F.data == "stand:train")
    async def cb_stand_train(query: CallbackQuery):
        uid = query.from_user.id
        player = get_player(uid)
        if not player or not player.get("character"):
            await query.answer("❌ اول /start بزن!", show_alert=True)
            return

        ok, message = train_bond(player)
        if ok:
            save_player(uid, player)
        try:
            await query.message.edit_text(format_stand_card(player), reply_markup=_stand_kb(player))
        except Exception:
            pass
        await query.answer(message, show_alert=not ok)

    @dp.callback_query(F.data.startswith("stand:up:") | F.data.startswith("stand:evo:"))
    async def cb_stand_upgrade(query: CallbackQuery):
        uid = query.from_user.id
        player = get_player(uid)
        if not player or not player.get("character"):
            await query.answer("❌ اول /start بزن!", show_alert=True)
            return

        stand = get_stand(player["character"])
        _, action, key = query.data.split(":")
        ability_name = _resolve_ability(player, stand, key)
        if ability_name is None:
            await query.answer("❌ توانایی نامعتبر.", show_alert=True)
            return

        if action == "evo":
            ok, message = evolve_ability(player, ability_name)
        else:
            ok, message = upgrade_stand_ability(player, ability_name)

        if not ok:
            await query.answer(message, show_alert=True)
            return

        save_player(uid, player)
        try:
            await query.message.edit_text(format_stand_card(player), reply_markup=_stand_kb(player))
        except Exception:
            pass
        await query.answer(message)
