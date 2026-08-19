# ============================================================
#  ASTRAL ABYSS — Class Active-Ability Handlers (Stage 3)
#  (class_ability_handlers.py)
# ============================================================
#
# لایه‌ی UI/دکمه‌های چهار سیستمِ فعالِ کلاس (منطقِ خالص تو
# class_abilities.py هست). یه پنلِ واحد («⚜️ قدرت‌های کلاس») که بسته
# به player["class"] محتوای متفاوت نشون می‌ده:
#
#   🧙‍♂️ جادوگر  → طلسمِ ترکیبی / سپرِ مانا / طوفانِ ناحیه‌ای
#   💰 تاجر    → اجیر/اخراجِ مزدور / چانه‌زنی / رشوه به دشمن
#   ✨ درمانگر → نورِ مقدس / سپرِ الهی / پاکسازی
#   🗺️ ماجراجو → کاوشِ دخمه + لیستِ رلیک‌های جمع‌شده
# ============================================================

import time

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
import class_abilities as ca

BACK_ATK_BTN = InlineKeyboardButton(text="🔙 منوی حمله", callback_data="atk:menu", style=ButtonStyle.PRIMARY)
BACK_CLASS_BTN = InlineKeyboardButton(text="🔙 برگشت", callback_data="class_panel", style=ButtonStyle.PRIMARY)


def _get_fight(player: dict) -> dict | None:
    # همون فیلدی که combat_handlers.py برای نبردِ جاری (از منوی /attack) استفاده می‌کنه.
    fight = player.get("current_fight")
    if fight:
        return fight
    # 🩹 باگ‌فیکس: نبردهای شروع‌شده از /loot (mob_combat.py — مواجهه‌های
    # نقشه/باسِ نقشه) اصلاً رو current_fight ذخیره نمی‌شن؛ دشمن‌شون رو
    # player["_active_encounter"]["enemy"] هست. تا الان قدرت‌های کلاس
    # (مخصوصاً طوفانِ ناحیه‌ای جادوگر) این فیلد رو چک نمی‌کردن، پس با
    # این‌که بازیکن دقیقاً وسط یه نبردِ فعال بود، پیام «باید وارد نبرد
    # بشی» می‌گرفت. حالا این فالبک هم چک می‌شه.
    enc = player.get("_active_encounter")
    if enc and enc.get("enemy"):
        return enc["enemy"]
    return None


def _sync_active_encounter_session(uid: int, player: dict) -> None:
    """بعد از این‌که یه قدرتِ کلاس (مثلاً طوفانِ ناحیه‌ای) مستقیم روی
    enemy["hp"] یه نبردِ /loot اثر گذاشت، سشنِ حافظه‌ایِ mob_combat.py
    (encounter_sessions) هم باید هم‌گام بشه — وگرنه چون get_player هر بار
    یه دیکشنریِ تازه از دیتابیس می‌ده (نه همون آبجکتِ تو حافظه)، ضربه‌ی
    نوواً روی HP دیتابیس می‌مونه ولی دفعه‌ی بعد که بازیکن رو دکمه‌ی حمله‌ی
    همون مواجهه بزنه، mob_combat.py هنوز HP قدیمی (از حافظه) رو می‌بینه."""
    enc = player.get("_active_encounter")
    if not enc:
        return
    try:
        import mob_combat
        if uid in mob_combat.encounter_sessions:
            mob_combat.encounter_sessions[uid] = enc
    except ImportError:
        pass
    try:
        import gap_mob_combat
        if uid in gap_mob_combat.encounter_sessions:
            gap_mob_combat.encounter_sessions[uid] = enc
    except ImportError:
        pass


def _max_hp(player: dict) -> int:
    try:
        from skill_tree import effective_max_hp
        return effective_max_hp(player)
    except Exception:
        return player.get("max_hp", 100)


# ─── رندرِ پنل بر اساسِ کلاس ────────────────────────────────────

def _render_wizard_panel(player: dict) -> tuple[str, InlineKeyboardMarkup]:
    csd = player.get("class_system_data", {})
    known = csd.get("elements_known", [])
    known_fa = "، ".join(ca._WIZARD_ELEMENT_FA.get(e, e) for e in known) or "—"
    fight = _get_fight(player)
    text = (
        f"🧙‍♂️ **قدرت‌های جادوگر**\n{'─'*22}\n"
        f"🔹 مانا: {csd.get('mana',0)}/{csd.get('max_mana',0)}\n"
        f"🔹 عناصرِ بازشده: {known_fa}\n"
        f"🔹 شارژِ سپرِ مانا: {csd.get('mana_shield_charges',0)}\n"
        f"🔹 تعدادِ طلسمِ ترکیبی: {csd.get('synergy_combos_used',0)}\n\n"
        f"🔥 **طلسمِ ترکیبی** ({ca.WIZARD_SPELL_COST} مانا) — ضربه‌ی بعدیِ نبردت تضمینی به ضعفِ دشمن می‌خوره + دمیجِ اضافه\n"
        f"🛡 **سپرِ مانا** ({ca.WIZARD_SHIELD_COST} مانا) — یه شارژ که ۶۰٪ از ضدحملهٔ بعدی رو جذب می‌کنه\n"
        f"🌀 **طوفانِ ناحیه‌ای** ({ca.WIZARD_NOVA_COST} مانا) — دمیجِ مستقیم به دشمنِ فعلی، بدونِ ضدحمله"
        + ("" if fight else "\n⚠️ برای طوفانِ ناحیه‌ای اول باید وارد نبرد بشی.")
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 طلسمِ ترکیبی", callback_data="wiz:spell", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🛡 سپرِ مانا", callback_data="wiz:shield", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🌀 طوفانِ ناحیه‌ای", callback_data="wiz:nova", style=ButtonStyle.DANGER)],
        [BACK_ATK_BTN],
    ])
    return text, kb


def _render_merchant_panel(player: dict) -> tuple[str, InlineKeyboardMarkup]:
    csd = player.get("class_system_data", {})
    mercs = csd.get("mercenaries_hired", [])
    merc_lines = "\n".join(f"  {i+1}. {m}" for i, m in enumerate(mercs)) or "  —"
    hire_cost = ca.merchant_hire_cost(player)
    fight = _get_fight(player)
    haggle_remaining = int(ca.HAGGLE_COOLDOWN_SEC - (time.time() - csd.get("_last_haggle_ts", 0)))
    haggle_txt = "آماده ✅" if haggle_remaining <= 0 else f"⏳ {haggle_remaining//60} دقیقه‌ی دیگه"
    text = (
        f"💰 **قدرت‌های تاجر**\n{'─'*22}\n"
        f"🔹 نفوذِ بازار: {csd.get('market_influence',0)}\n"
        f"🔹 ضریبِ درآمدِ طلا: ×{csd.get('gold_multiplier',1.0):.2f}\n"
        f"🔹 مزدورهای اجیرشده ({len(mercs)}/{ca.MAX_MERCS}):\n{merc_lines}\n"
        f"🔹 وضعیتِ چانه‌زنی: {haggle_txt}\n\n"
        f"⚔️ **اجیرِ مزدور** ({hire_cost:,} Zen) — تو نبرد دمیجِ فلتِ اضافه می‌ده\n"
        f"🤝 **چانه‌زنی** (رایگان، کولداون ۱ ساعته) — شانسیِ ضریبِ درآمدِ طلا رو بالا می‌بره\n"
        f"💸 **رشوه به دشمن** — دشمنِ فعلی رو بدونِ جایزه/باخت فراری می‌ده"
        + ("" if fight else "\n⚠️ برای رشوه اول باید وارد نبرد بشی.")
    )
    rows = [
        [InlineKeyboardButton(text=f"⚔️ اجیرِ مزدور ({hire_cost:,} Zen)", callback_data="merch:hire", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🤝 چانه‌زنی", callback_data="merch:haggle", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="💸 رشوه به دشمن", callback_data="merch:bribe", style=ButtonStyle.DANGER)],
    ]
    if mercs:
        rows.append([InlineKeyboardButton(text="🗑 اخراجِ یه مزدور", callback_data="merch:dismiss_menu", style=ButtonStyle.PRIMARY)])
    rows.append([BACK_ATK_BTN])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def _render_merchant_dismiss_menu(player: dict) -> tuple[str, InlineKeyboardMarkup]:
    mercs = player.get("class_system_data", {}).get("mercenaries_hired", [])
    rows = [[InlineKeyboardButton(text=f"🗑 {m}", callback_data=f"merch:dismiss:{i}", style=ButtonStyle.DANGER)]
            for i, m in enumerate(mercs)]
    rows.append([BACK_CLASS_BTN])
    return "🗑 **کدوم مزدور رو اخراج کنم؟**", InlineKeyboardMarkup(inline_keyboard=rows)


def _render_healer_panel(player: dict) -> tuple[str, InlineKeyboardMarkup]:
    csd = player.get("class_system_data", {})
    fight = _get_fight(player)
    text = (
        f"✨ **قدرت‌های درمانگر**\n{'─'*22}\n"
        f"🔹 فیض: {csd.get('faith',0)}/{csd.get('max_faith',0)}\n"
        f"🔹 شارژِ سپرِ الهی: {csd.get('divine_shield_charges',0)}\n"
        f"🔹 Self-Revive در دسترس: {csd.get('revives_available',0)}\n"
        f"🔹 مرده‌های متحرکِ پاکسازی‌شده: {csd.get('undead_purged',0)}\n\n"
        f"🌟 **نورِ مقدس** ({ca.HOLY_LIGHT_COST} فیض) — خودت رو هیل می‌کنه؛ اگه دشمنِ فعلی مرده‌ی متحرکه، بهش دمیج هم می‌زنه\n"
        f"🛡 **سپرِ الهی** ({ca.DIVINE_SHIELD_COST} فیض) — یه شارژ که ۷۰٪ از ضدحملهٔ بعدی رو جذب می‌کنه\n"
        f"💧 **پاکسازی** ({ca.PURIFY_COST} فیض) — هیلِ مستقیمِ متوسط، همیشه در دسترس"
        + ("" if fight else "\n💡 اگه تو نبرد نیستی، نورِ مقدس فقط خودتو هیل می‌کنه.")
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌟 نورِ مقدس", callback_data="heal:light", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🛡 سپرِ الهی", callback_data="heal:shield", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="💧 پاکسازی", callback_data="heal:purify", style=ButtonStyle.PRIMARY)],
        [BACK_ATK_BTN],
    ])
    return text, kb


def _render_adventurer_panel(player: dict) -> tuple[str, InlineKeyboardMarkup]:
    csd = player.get("class_system_data", {})
    relics = csd.get("relics_collected", [])
    counts: dict[str, int] = {}
    for r in relics:
        r = ca._canonical_relic_name(r)
        counts[r] = counts.get(r, 0) + 1
    relic_lines = "\n".join(
        f"  • {name} ×{n}" + (f" (تکمیل — سقفِ اثر پره)" if n >= ca.RELIC_CAP_FOR_BONUS else "")
        for name, n in counts.items()
    ) or "  —"
    text = (
        f"🗺️ **کاوشِ دخمه**\n{'─'*22}\n"
        f"🔹 استامینا: {csd.get('stamina',0)}/{csd.get('max_stamina',0)}\n"
        f"🔹 شانسِ اکتشاف: {csd.get('exploration_luck',5)}\n"
        f"🔹 دخمه‌های تکمیل‌شده: {csd.get('dungeons_cleared',0)}\n"
        f"🔹 رلیک‌های جمع‌شده ({len(relics)}):\n{relic_lines}\n\n"
        f"🧭 **کاوش کن** ({ca.DUNGEON_STAMINA_COST} استامینا) — شانسِ رلیک/تله/طلا"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧭 کاوشِ دخمه", callback_data="adv:explore", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="❓ راهنمای رلیک‌ها", callback_data="adv:help", style=ButtonStyle.PRIMARY)],
        [BACK_ATK_BTN],
    ])
    return text, kb


ADVENTURER_HELP_TEXT = (
    "🗺️ **راهنمای کاوشِ دخمه**\n" + "─"*22 + "\n\n"
    "هر بار که وارد یه دخمه می‌شی، ۲۵ استامینا مصرف می‌کنی و یکی از این سه اتفاق می‌افته:\n\n"
    "🔹 پیداکردنِ یه رلیکِ باستانی\n"
    "🔹 خوردن به یه تله (مگراینکه evade کنی)\n"
    "🔹 یه دخمه‌ی خالی با کمی زن\n\n"
    "شانسِ هرکدوم به استاتِ «شانسِ اکتشاف»ت بستگی داره — هرچی بیشتر باشه، "
    "احتمالِ پیداکردنِ رلیک بیشتر و احتمالِ خوردنِ تله کمتر می‌شه.\n\n"
    "💎 **رلیک‌ها چیکار می‌کنن؟**\n"
    "هر رلیک اثرِ مخصوصِ خودشو داره — هرچی از یه نوع بیشتر جمع کنی، اثرش قوی‌تر "
    "می‌شه، تا سقفِ ۱۰ تا از هر نوع (بعدش دیگه رشد نمی‌کنه):\n\n"
    "⚔️ *بونوسِ نبرد*\n"
    "🗽 پیکرکِ فراموش‌شده — دمیجِ فلت (+۲ به‌ازای هر تا)\n"
    "🔱 سه‌شاخه‌ی اعماقِ تاریک — شانسِ کریت (+۰.۵٪ به‌ازای هر تا)\n"
    "📿 تسبیحِ روحِ باستانی — لایف‌استیل (+۰.۴٪ به‌ازای هر تا)\n"
    "⚱️ خاکسترِ محافظِ دخمه — کاهشِ دمیجِ ضدحمله (+۰.۵٪ به‌ازای هر تا)\n\n"
    "🧭 *بونوسِ کاوش*\n"
    "🕯️ چراغِ ابدیِ گورستان — شانسِ اکتشاف (+۱ به‌ازای هر تا)\n"
    "📜 طومارِ زبانِ فراموش‌شده — شانسِ جاخالی‌دادنِ تله (+۳٪ به‌ازای هر تا)\n"
    "🏺 کوزه‌ی رازآلودِ اعماق — طلای دخمه‌های خالی (+۵٪ به‌ازای هر تا)\n"
    "💍 حلقه‌ی گمشده‌ی پادشاهِ کهن — شانسِ پیداکردنِ رلیکِ بعدی (+۲٪ به‌ازای هر تا)\n\n"
    "پس بهتره تنوع جمع کنی — چون هر نوع تا ۱۰ تا سقف داره، بعد از اون دیگه فایده‌ای نداره."
)


async def cb_adventurer_help(cb: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 برگشت", callback_data="class_panel", style=ButtonStyle.PRIMARY)],
    ])
    await cb.message.edit_text(ADVENTURER_HELP_TEXT, reply_markup=kb)
    await cb.answer()


_PANEL_RENDERERS = {
    "wizard": _render_wizard_panel,
    "merchant": _render_merchant_panel,
    "healer": _render_healer_panel,
    "adventurer": _render_adventurer_panel,
}


async def _show_class_panel(target, player: dict, edit: bool):
    cls = player.get("class")
    renderer = _PANEL_RENDERERS.get(cls)
    if not renderer:
        text, kb = "❌ اول باید کاراکترت رو بسازی! /start رو بزن.", None
    else:
        text, kb = renderer(player)
    if edit:
        await target.message.edit_text(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


# ─── Command / Entry Points ────────────────────────────────────

async def cmd_class_panel(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player or not player.get("class"):
        await msg.answer("❌ اول باید کاراکترت رو بسازی! /start رو بزن.")
        return
    ca.tick_regen(player)
    save_player(uid, player)
    await _show_class_panel(msg, player, edit=False)


async def cb_class_panel(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    if not player or not player.get("class"):
        await cb.answer("❌ اول باید کاراکترت رو بسازی!", show_alert=True)
        return
    ca.tick_regen(player)
    save_player(uid, player)
    await _show_class_panel(cb, player, edit=True)
    await cb.answer()


# ─── 🧙‍♂️ Wizard ────────────────────────────────────────────────

async def cb_wizard_spell(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    r = ca.wizard_cast_synergy(player)
    if not r["ok"]:
        await cb.answer(r["msg"], show_alert=True)
        return
    save_player(uid, player)
    msg = f"🔮 طلسمِ ترکیبی آماده‌ست! ضربه‌ی بعدیِ نبردت تضمینی به ضعفِ دشمن می‌خوره."
    if r.get("unlocked"):
        msg += f"\n✨ یه عنصرِ جدید باز شد: {ca._WIZARD_ELEMENT_FA.get(r['unlocked'], r['unlocked'])}"
    await cb.answer(msg, show_alert=True)
    await _show_class_panel(cb, player, edit=True)


async def cb_wizard_shield(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    r = ca.wizard_mana_shield(player)
    if not r["ok"]:
        await cb.answer(r["msg"], show_alert=True)
        return
    save_player(uid, player)
    await cb.answer(f"🛡 سپرِ مانا فعال شد! (شارژ: {r['charges']})", show_alert=True)
    await _show_class_panel(cb, player, edit=True)


async def cb_wizard_nova(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    enemy = _get_fight(player)  # 🩹 هم current_fight (/attack) هم _active_encounter (/loot)
    r = ca.wizard_arcane_nova(player, enemy)
    if not r["ok"]:
        await cb.answer(r["msg"], show_alert=True)
        return
    save_player(uid, player)
    _sync_active_encounter_session(uid, player)  # 🩹 هم‌گام‌سازی سشنِ حافظه‌ایِ mob_combat.py
    txt = f"🌀 طوفانِ ناحیه‌ای {r['dmg']} آسیب زد!"
    if r["killed"]:
        if player.get("current_fight"):
            txt += "\n💀 دشمن نابود شد! برو منوی حمله تا کشتنش رو نهایی کنی."
        else:
            txt += "\n💀 دشمن نابود شد! برگرد به پیامِ نبرد و یه ضربه‌ی دیگه بزن تا نهایی بشه."
    await cb.answer(txt, show_alert=True)
    await _show_class_panel(cb, player, edit=True)


# ─── 💰 Merchant ────────────────────────────────────────────────

async def cb_merchant_hire(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    r = ca.merchant_hire_mercenary(player)
    if not r["ok"]:
        await cb.answer(r["msg"], show_alert=True)
        return
    save_player(uid, player)
    await cb.answer(f"⚔️ {r['name']} رو اجیر کردی! ({r['cost']:,} Zen)", show_alert=True)
    await _show_class_panel(cb, player, edit=True)


async def cb_merchant_dismiss_menu(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    text, kb = _render_merchant_dismiss_menu(player)
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


async def cb_merchant_dismiss(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    idx = int(cb.data.split(":")[2])
    r = ca.merchant_dismiss_mercenary(player, idx)
    if not r["ok"]:
        await cb.answer(r.get("msg", "❌ خطا"), show_alert=True)
        return
    save_player(uid, player)
    await cb.answer(f"🗑 {r['removed']} اخراج شد.", show_alert=True)
    await _show_class_panel(cb, player, edit=True)


async def cb_merchant_haggle(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    r = ca.merchant_haggle(player)
    if not r["ok"]:
        mins = max(1, r["cooldown"] // 60)
        await cb.answer(f"⏳ هنوز {mins} دقیقه‌ی دیگه باید صبر کنی.", show_alert=True)
        return
    save_player(uid, player)
    if r["success"]:
        await cb.answer(f"🤝 چانه‌زنی موفق بود! ضریبِ طلا رفت رو ×{r['mult']:.2f}", show_alert=True)
    else:
        await cb.answer("🤝 این‌بار فروشنده زیرِ بار نرفت. دوباره امتحان کن.", show_alert=True)
    await _show_class_panel(cb, player, edit=True)


async def cb_merchant_bribe(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    enemy = player.get("current_fight")
    r = ca.merchant_bribe(player, enemy)
    if not r["ok"]:
        await cb.answer(r["msg"], show_alert=True)
        return
    player["current_fight"] = None
    save_player(uid, player)
    await cb.answer(f"💸 با {r['cost']:,} Zen دشمن رو فراری دادی!", show_alert=True)
    await _show_class_panel(cb, player, edit=True)


# ─── ✨ Healer ───────────────────────────────────────────────────

async def cb_healer_light(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    enemy = player.get("current_fight")
    r = ca.healer_holy_light(player, enemy)
    if not r["ok"]:
        await cb.answer(r["msg"], show_alert=True)
        return
    save_player(uid, player)
    txt = f"🌟 نورِ مقدس {r['heal']} HP بهت داد!"
    if r["undead_hit"]:
        txt += f"\n💥 {r['dmg']} آسیبِ اضافه به مرده‌ی متحرک زدی!"
        if r["killed"]:
            txt += "\n💀 دشمن نابود شد! برو منوی حمله تا کشتنش رو نهایی کنی."
    await cb.answer(txt, show_alert=True)
    await _show_class_panel(cb, player, edit=True)


async def cb_healer_shield(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    r = ca.healer_divine_shield(player)
    if not r["ok"]:
        await cb.answer(r["msg"], show_alert=True)
        return
    save_player(uid, player)
    await cb.answer(f"🛡 سپرِ الهی فعال شد! (شارژ: {r['charges']})", show_alert=True)
    await _show_class_panel(cb, player, edit=True)


async def cb_healer_purify(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    r = ca.healer_purify(player)
    if not r["ok"]:
        await cb.answer(r["msg"], show_alert=True)
        return
    save_player(uid, player)
    await cb.answer(f"💧 پاکسازی {r['heal']} HP بهت داد!", show_alert=True)
    await _show_class_panel(cb, player, edit=True)


# ─── 🗺️ Adventurer ──────────────────────────────────────────────

async def cb_adventurer_explore(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    r = ca.adventurer_explore(player)
    if not r["ok"]:
        await cb.answer(r["msg"], show_alert=True)
        return
    save_player(uid, player)
    outcome = r["outcome"]
    if outcome == "relic":
        txt = f"✨ رلیکِ جدید پیدا کردی: {r['relic']}"
    elif outcome == "trap_evaded":
        txt = "💨 یه تله بود ولی جاخالی دادی!"
    elif outcome == "trap_hit":
        txt = f"💥 تو تله افتادی! {r['dmg']} آسیب خوردی."
    else:
        txt = f"🪙 دخمه خالی بود ولی {r['zen']} Zen پیدا کردی."
    await cb.answer(txt, show_alert=True)
    await _show_class_panel(cb, player, edit=True)


# ─── Registration ───────────────────────────────────────────────

def register_class_ability_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_class_panel, Command("class"))
    dp.callback_query.register(cb_class_panel, F.data == "class_panel")

    dp.callback_query.register(cb_wizard_spell, F.data == "wiz:spell")
    dp.callback_query.register(cb_wizard_shield, F.data == "wiz:shield")
    dp.callback_query.register(cb_wizard_nova, F.data == "wiz:nova")

    dp.callback_query.register(cb_merchant_hire, F.data == "merch:hire")
    dp.callback_query.register(cb_merchant_dismiss_menu, F.data == "merch:dismiss_menu")
    dp.callback_query.register(cb_merchant_dismiss, F.data.startswith("merch:dismiss:"))
    dp.callback_query.register(cb_merchant_haggle, F.data == "merch:haggle")
    dp.callback_query.register(cb_merchant_bribe, F.data == "merch:bribe")

    dp.callback_query.register(cb_healer_light, F.data == "heal:light")
    dp.callback_query.register(cb_healer_shield, F.data == "heal:shield")
    dp.callback_query.register(cb_healer_purify, F.data == "heal:purify")

    dp.callback_query.register(cb_adventurer_explore, F.data == "adv:explore")
    dp.callback_query.register(cb_adventurer_help, F.data == "adv:help")
