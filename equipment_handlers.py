# ============================================================
#  ASTRAL ABYSS — Equipment Handlers (Equip / Unequip)
# ------------------------------------------------------------
#  player["equipped"] از قبل تو database.py هست و combat_power.py
#  ازش می‌خونه، ولی تا الان هیچ دکمه/هندلری برای اکیپ کردن نبود.
#  این فایل همون الگوی progression_handlers.py رو دنبال می‌کنه:
#  یه register_equipment_handlers(dp, bot) که تو main() صدا زده می‌شه.
#
#  دستورات جدید:
#    /equipment یا دکمه‌ی «🎽 تجهیزات» → نمایش ۸ اسلات + آیتم اکیپ‌شده
#    از تو کوله‌پشتی هم می‌شه مستقیم آیتم رو اکیپ کرد (دکمه‌ی eq_pick:
#    که تو bot.py کنار هر آیتمِ قابل‌اکیپ اضافه می‌شه و همینجا هندل می‌شه).
# ============================================================
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from item_system import EQUIP_SLOTS, calculate_item_score, format_item_card, migrate_legacy_item

SLOT_LABELS = {
    "weapon": "⚔️ سلاح",
    "helmet": "⛑️ کلاه",
    "armor":  "🛡️ زره",
    "gloves": "🧤 دستکش",
    "boots":  "🥾 چکمه",
    "ring":   "💍 حلقه",
    "amulet": "📿 گردنبند",
    "relic":  "🔮 مصنوعه",
}

PAGE_SIZE = 6


def _equipped(player: dict) -> dict:
    eq = player.setdefault("equipped", {s: None for s in EQUIP_SLOTS})
    for s in EQUIP_SLOTS:
        eq.setdefault(s, None)
    return eq


def _total_equipment_score(player: dict) -> int:
    eq = _equipped(player)
    return sum(item.get("item_score", calculate_item_score(item)) for item in eq.values() if item)


def _slots_kb(player: dict, uid: int) -> InlineKeyboardMarkup:
    eq = _equipped(player)
    rows = []
    row = []
    for i, slot in enumerate(EQUIP_SLOTS):
        item = eq.get(slot)
        mark = "✅" if item else "➖"
        row.append(InlineKeyboardButton(
            text=f"{mark} {SLOT_LABELS[slot]}",
            callback_data=f"eq_view:{slot}:{uid}",
            style=ButtonStyle.PRIMARY,
        ))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _equipment_text(player: dict) -> str:
    eq = _equipped(player)
    lines = [f"🎽 **تجهیزات** — مجموع Item Score: **{_total_equipment_score(player):,}**\n"]
    for slot in EQUIP_SLOTS:
        item = eq.get(slot)
        if item:
            lines.append(f"{SLOT_LABELS[slot]}: {item.get('emoji','📦')} {item['name']} ⭐{item.get('item_score', calculate_item_score(item))}")
        else:
            lines.append(f"{SLOT_LABELS[slot]}: — خالی —")

    from item_system import combat_bonus_stats
    b = combat_bonus_stats(player)
    bonus_lines = []
    if b.get("dmg_pct"):        bonus_lines.append(f"⚔️ دمیج: +{b['dmg_pct']*100:.1f}٪")
    if b.get("crit_pct"):       bonus_lines.append(f"🎯 شانسِ کریت: +{b['crit_pct']*100:.1f}٪")
    if b.get("crit_dmg_bonus"): bonus_lines.append(f"💥 دمیجِ کریت: +{b['crit_dmg_bonus']*100:.1f}٪")
    if b.get("lifesteal_pct"):  bonus_lines.append(f"🩸 لایف‌استیل: +{b['lifesteal_pct']*100:.1f}٪")
    if b.get("defense_pct"):    bonus_lines.append(f"🛡️ کاهشِ دمیجِ ورودی: -{b['defense_pct']*100:.1f}٪")
    if b.get("reflect_pct"):    bonus_lines.append(f"🌵 بازتابِ دمیج: {b['reflect_pct']*100:.1f}٪")
    if b.get("max_hp_flat"):    bonus_lines.append(f"❤️ HP اضافه: +{int(b['max_hp_flat'])}")
    if b.get("gold_find_pct"):  bonus_lines.append(f"💰 شانسِ طلا: +{b['gold_find_pct']*100:.1f}٪")
    if b.get("xp_pct"):         bonus_lines.append(f"✨ XP: +{b['xp_pct']*100:.1f}٪")
    if b.get("accuracy_pct"):   bonus_lines.append(f"🏹 دقت: +{b['accuracy_pct']*100:.1f}٪")
    if bonus_lines:
        lines.append("\n📊 **بونوسِ فعال از افیکس‌ها:**")
        lines.extend(bonus_lines)

    lines.append("\nروی هر اسلات بزن تا مدیریتش کنی.")
    return "\n".join(lines)


# ─── /equipment ─────────────────────────────────────────────
async def cmd_equipment(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    await asave_player(uid, player)  # اگه equipped تازه‌ست، ذخیره‌ش کن
    await msg.answer(_equipment_text(player), reply_markup=_slots_kb(player, uid))


async def cb_eq_view(cb: CallbackQuery):
    parts = cb.data.split(":")
    slot, uid = parts[1], int(parts[2])
    if cb.from_user.id != uid:
        await cb.answer("❌", show_alert=True); return
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return

    eq = _equipped(player)
    item = eq.get(slot)
    buttons = []
    if item:
        text = f"{SLOT_LABELS[slot]}\n\n{format_item_card(item)}"
        buttons.append([InlineKeyboardButton(text="🔁 عوض کردن", callback_data=f"eq_list:{slot}:0:{uid}", style=ButtonStyle.PRIMARY)])
        buttons.append([InlineKeyboardButton(text="❌ درآوردن", callback_data=f"eq_unequip:{slot}:{uid}", style=ButtonStyle.DANGER)])
    else:
        text = f"{SLOT_LABELS[slot]}\n\n— هیچی اکیپ نشده —"
        buttons.append([InlineKeyboardButton(text="➕ اکیپ کردن", callback_data=f"eq_list:{slot}:0:{uid}", style=ButtonStyle.SUCCESS)])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به تجهیزات", callback_data=f"eq_home:{uid}", style=ButtonStyle.DANGER)])

    try:
        await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    except Exception:
        await cb.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await cb.answer()


async def cb_eq_home(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if cb.from_user.id != uid:
        await cb.answer("❌", show_alert=True); return
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return
    try:
        await cb.message.edit_text(_equipment_text(player), reply_markup=_slots_kb(player, uid))
    except Exception:
        await cb.message.answer(_equipment_text(player), reply_markup=_slots_kb(player, uid))
    await cb.answer()


async def cb_eq_list(cb: CallbackQuery):
    """لیستِ آیتم‌های قابل‌اکیپِ اون اسلات، از تو کوله‌پشتی."""
    parts = cb.data.split(":")
    slot, page, uid = parts[1], int(parts[2]), int(parts[3])
    if cb.from_user.id != uid:
        await cb.answer("❌", show_alert=True); return
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return

    inv = player.get("inventory", [])
    candidates = [(i, it) for i, it in enumerate(inv) if it.get("slot") == slot]
    if not candidates:
        await cb.answer("🎒 هیچ آیتمِ قابل‌اکیپی برای این اسلات تو کوله‌پشتیت نیست.", show_alert=True)
        return

    candidates.sort(key=lambda pair: pair[1].get("item_score", calculate_item_score(pair[1])), reverse=True)
    total_pages = max(1, (len(candidates) - 1) // PAGE_SIZE + 1)
    page = max(0, min(page, total_pages - 1))
    page_items = candidates[page * PAGE_SIZE: page * PAGE_SIZE + PAGE_SIZE]

    lines = [f"{SLOT_LABELS[slot]} — کدوم رو اکیپ کنم؟ (صفحه {page+1}/{total_pages})\n"]
    buttons = []
    for real_idx, item in page_items:
        score = item.get("item_score", calculate_item_score(item))
        lines.append(f"{item.get('emoji','📦')} {item['name']} — ⭐{score}")
        buttons.append([InlineKeyboardButton(
            text=f"✅ {item['name']} (⭐{score})",
            callback_data=f"eq_pick:{slot}:{real_idx}:{uid}",
            style=ButtonStyle.SUCCESS,
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"eq_list:{slot}:{page-1}:{uid}", style=ButtonStyle.PRIMARY))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"eq_list:{slot}:{page+1}:{uid}", style=ButtonStyle.PRIMARY))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"eq_view:{slot}:{uid}", style=ButtonStyle.DANGER)])

    text = "\n".join(lines)
    try:
        await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    except Exception:
        await cb.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await cb.answer()


async def cb_eq_pick(cb: CallbackQuery):
    """هم از منوی تجهیزات صدا زده می‌شه، هم مستقیم از دکمه‌ی «🎽 اکیپ» تو کوله‌پشتی."""
    parts = cb.data.split(":")
    slot, idx, uid = parts[1], int(parts[2]), int(parts[3])
    if cb.from_user.id != uid:
        await cb.answer("❌", show_alert=True); return
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return

    inv = player.get("inventory", [])
    if idx >= len(inv) or inv[idx].get("slot") != slot:
        await cb.answer("❌ این آیتم دیگه تو کوله‌پشتی نیست یا اسلاتش عوض شده!", show_alert=True)
        return

    item = migrate_legacy_item(inv.pop(idx))
    eq = _equipped(player)
    old = eq.get(slot)
    eq[slot] = item
    if old:
        inv.append(old)
    player["inventory"] = inv
    player["equipped"] = eq
    await asave_player(uid, player)

    swap_note = f"\n(آیتمِ قبلی — {old['name']} — برگشت تو کوله‌پشتی)" if old else ""
    await cb.answer(f"✅ {item['name']} اکیپ شد!", show_alert=True)
    text = f"{SLOT_LABELS[slot]}\n\n{format_item_card(item)}{swap_note}"
    buttons = [
        [InlineKeyboardButton(text="🔁 عوض کردن", callback_data=f"eq_list:{slot}:0:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="❌ درآوردن", callback_data=f"eq_unequip:{slot}:{uid}", style=ButtonStyle.DANGER)],
        [InlineKeyboardButton(text="🔙 بازگشت به تجهیزات", callback_data=f"eq_home:{uid}", style=ButtonStyle.DANGER)],
    ]
    try:
        await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    except Exception:
        await cb.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


async def cb_eq_unequip(cb: CallbackQuery):
    parts = cb.data.split(":")
    slot, uid = parts[1], int(parts[2])
    if cb.from_user.id != uid:
        await cb.answer("❌", show_alert=True); return
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True); return

    eq = _equipped(player)
    item = eq.get(slot)
    if not item:
        await cb.answer("این اسلات از قبل خالیه.", show_alert=True)
        return
    eq[slot] = None
    player.setdefault("inventory", []).append(item)
    player["equipped"] = eq
    await asave_player(uid, player)

    await cb.answer(f"↩️ {item['name']} از اکیپ درآمد و رفت تو کوله‌پشتی.", show_alert=True)
    try:
        await cb.message.edit_text(_equipment_text(player), reply_markup=_slots_kb(player, uid))
    except Exception:
        await cb.message.answer(_equipment_text(player), reply_markup=_slots_kb(player, uid))


# ─── Register ────────────────────────────────────────────────
def register_equipment_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_equipment, Command("equipment"))
    dp.message.register(cmd_equipment, F.text == "🎽 تجهیزات")

    dp.callback_query.register(cb_eq_home,     F.data.startswith("eq_home:"))
    dp.callback_query.register(cb_eq_view,     F.data.startswith("eq_view:"))
    dp.callback_query.register(cb_eq_list,     F.data.startswith("eq_list:"))
    dp.callback_query.register(cb_eq_pick,     F.data.startswith("eq_pick:"))
    dp.callback_query.register(cb_eq_unequip,  F.data.startswith("eq_unequip:"))
