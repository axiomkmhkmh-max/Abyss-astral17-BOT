# ============================================================
#  ASTRAL ABYSS RPG — House Handlers (Telegram UI)  — v2
# ============================================================
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
from logger import log_sync
import house_system as hs
import house_defense_traps as dtraps


def _owner_ok(cb: CallbackQuery, uid: int) -> bool:
    return cb.from_user.id == uid


def _home_text(player: dict) -> str:
    house = hs.ensure_house(player)
    tier = hs.tier_data(house)
    cozy = hs.cozy_score(house)
    income_hr = hs.income_per_hour(house)
    pending = hs.pending_income(house)
    security = hs.security_score(house)
    chance = hs.robbery_chance(house)
    prestige = hs.prestige_score(house)
    insured = hs.is_insured(house)

    lines = [
        f"{tier['name']}\n",
        f"📦 انباری: {len(house.get('storage', []))}/{tier['storage']}",
        f"❤️ بونوس درمان (موقع مصرف آیتم/معجون): +{int(tier['hp_regen_pct']*100)}٪",
        f"🛋 امتیاز دنجی: {cozy}",
        f"🏆 پرستیژِ ملک: {prestige}",
        "",
        f"💰 درآمد: {income_hr:,} Zen/ساعت | 💼 صندوق (برداشت‌نشده): **{pending:,} Zen**",
        f"🛡 امنیت: {security} امتیاز (شانسِ دزدها برای موفقیت: {int(chance*100)}٪)",
        f"🪤 {dtraps.traps_text(house)} — امتیازِ تله‌ها فقط تو لحظه‌ی حمله فعال می‌شه، جدا از امنیتِ بالاست.",
    ]
    if insured:
        remain_h = int((house["insured_until"] - hs.time.time()) // 3600) + 1
        lines.append(f"🛡 بیمه: ✅ فعال ({remain_h} ساعتِ دیگه)")
    else:
        lines.append(f"🛡 بیمه: ❌ غیرفعال (حق‌بیمه: {hs.insurance_premium(house):,} Zen برای ۲۴ ساعت)")
    if house.get("furniture"):
        names = [FURNITURE_NAME.get(it["id"], "؟") for it in house["furniture"]]
        lines.append(f"\n🪑 وسایل: {', '.join(names)}")
    return "\n".join(lines)


FURNITURE_NAME = {f["id"]: f["name"] for f in hs.FURNITURE}


def _home_kb(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 برداشتِ درآمدِ ملک", callback_data=f"house_collect:{uid}", style=ButtonStyle.SUCCESS)],
        [
            InlineKeyboardButton(text="⬆️ ارتقای ملک (نقد)", callback_data=f"house_upgrade:{uid}", style=ButtonStyle.SUCCESS),
            InlineKeyboardButton(text="🏦 ارتقا با رهنِ بانکی", callback_data=f"house_mortgage:{uid}", style=ButtonStyle.PRIMARY),
        ],
        [InlineKeyboardButton(text="🛋 خرید وسیله", callback_data=f"house_furn:{uid}", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="🛡 خریدِ بیمه‌ی ملک", callback_data=f"house_insure:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🪤 مدیریتِ تله‌ها", callback_data=f"house_traps:{uid}", style=ButtonStyle.DANGER)],
        [InlineKeyboardButton(text="📦 انباری (جابه‌جایی آیتم)", callback_data=f"house_storage:{uid}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🗺 زمین من", callback_data=f"land_home:{uid}", style=ButtonStyle.PRIMARY)],
    ])


async def cmd_house(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    from level_gate import check_level
    ok, why = check_level(player, "house")
    if not ok:
        await msg.answer(why)
        return
    hs.ensure_house(player)
    save_player(uid, player)
    await msg.answer("🏠 **ملک شخصی**\n\n" + _home_text(player), reply_markup=_home_kb(uid))


async def cb_house_home(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    await cb.answer()
    await cb.message.edit_text("🏠 **ملک شخصی**\n\n" + _home_text(player), reply_markup=_home_kb(uid))


async def cb_house_collect(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    player["_uid"] = uid
    ok, msg = hs.collect_income(player)
    if ok:
        save_player(uid, player)
        log_sync(f"💰 **HOUSE INCOME**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "HOUSE")
    await cb.answer(msg if ok else msg, show_alert=True)
    await cb.message.edit_text("🏠 **ملک شخصی**\n\n" + _home_text(player), reply_markup=_home_kb(uid))


async def cb_house_upgrade(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    ok, msg = hs.upgrade_house(player, uid)
    if ok:
        save_player(uid, player)
        log_sync(f"🏠 **HOUSE UPGRADE**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "HOUSE")
    await cb.answer(msg, show_alert=True)
    await cb.message.edit_text("🏠 **ملک شخصی**\n\n" + _home_text(player), reply_markup=_home_kb(uid))


async def cb_house_mortgage(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    ok, msg = hs.mortgage_upgrade(player, uid)
    if ok:
        save_player(uid, player)
        log_sync(f"🏦 **HOUSE MORTGAGE**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "HOUSE")
    await cb.answer(msg[:200], show_alert=True)
    await cb.message.edit_text("🏠 **ملک شخصی**\n\n" + _home_text(player), reply_markup=_home_kb(uid))


async def cb_house_insure(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    ok, msg = hs.buy_insurance(player)
    if ok:
        save_player(uid, player)
        log_sync(f"🛡 **HOUSE INSURANCE**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "HOUSE")
    await cb.answer(msg, show_alert=True)
    await cb.message.edit_text("🏠 **ملک شخصی**\n\n" + _home_text(player), reply_markup=_home_kb(uid))


_TYPE_LABEL = {"cozy": "🛋 دنجی", "income": "💰 درآمدزا", "security": "🛡 امنیتی"}


async def _render_furn_menu(cb: CallbackQuery, uid: int):
    """فقط ساختِ منو و ادیتِ پیام — بدونِ cb.answer()، چون ممکنه صدازننده
    قبلش یه‌بار دیگه answer داده باشه (خرید که پیامِ نتیجه رو با alert نشون می‌ده)."""
    player = get_player(uid)
    house = hs.ensure_house(player)
    owned = {f["id"] for f in house.get("furniture", [])}
    buttons = []
    for ftype in ("cozy", "income", "security"):
        buttons.append([InlineKeyboardButton(text=f"── {_TYPE_LABEL[ftype]} ──", callback_data=f"house_furn:{uid}", style=ButtonStyle.PRIMARY)])
        for f in hs.FURNITURE:
            if f["type"] != ftype:
                continue
            if f["id"] in owned:
                label = f"✅ {f['name']}"
                cb_data = f"house_furn:{uid}"
            else:
                stat = f.get("cozy") or f.get("income") or f.get("security")
                label = f"{f['name']} — {f['cost']:,} Zen (+{stat})"
                cb_data = f"house_buy_furn:{f['id']}:{uid}"
            buttons.append([InlineKeyboardButton(text=label, callback_data=cb_data, style=ButtonStyle.PRIMARY)])
    buttons.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"house_home:{uid}", style=ButtonStyle.PRIMARY)])
    await cb.message.edit_text(
        "🛋 **فروشگاه وسایل خونه**\nدنجی = امتیازِ آسایش | درآمدزا = Zen/ساعت بیشتر | امنیتی = دفاع در برابر دزدی",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


async def cb_house_furn(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    await cb.answer()
    await _render_furn_menu(cb, uid)


async def cb_house_buy_furn(cb: CallbackQuery):
    _, furn_id, uid_s = cb.data.split(":")
    uid = int(uid_s)
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    ok, msg = hs.buy_furniture(player, furn_id)
    if ok:
        save_player(uid, player)
    # ⚠️ باگ‌فیکس: قبلاً اینجا cb.answer() صدا زده می‌شد و بعد cb_house_furn(cb)
    # هم دوباره cb.answer() صدا می‌زد — تلگرام روی همون کالبک‌کوئری دوبار
    # answerCallbackQuery رو رد می‌کنه («query is too old / already answered»)،
    # هندلر کرش می‌کرد و کلاینت «یه مشکلی پیش اومد» نشون می‌داد، ولی خریدِ
    # وسیله در واقع قبلش انجام و ذخیره شده بود. حالا فقط یه‌بار answer می‌شه.
    await cb.answer(msg, show_alert=True)
    await _render_furn_menu(cb, uid)


# ─── 🪤 تله‌های دفاعی (آیتم‌های خریداری‌شده از 🏰 دفاعِ پایگاه) ────
async def _render_trap_menu(cb: CallbackQuery, uid: int):
    player = get_player(uid)
    house = hs.ensure_house(player)
    lines = [
        f"🪤 **مدیریتِ تله‌های خونه**\n",
        f"{dtraps.traps_text(house)}\n",
        "_هر تله فقط یه‌بار، تو یه حمله‌ی دزدی فعال می‌شه و بعدش مصرف می‌شه._\n",
    ]
    buttons = []
    owned = dtraps.owned_uninstalled(player)
    if owned:
        lines.append("\n📦 **تو انبارت (نصب‌نشده):**")
        for name, cnt in owned.items():
            item = dtraps.DEFENSE_ITEM_MAP.get(name, {})
            lines.append(f"{item.get('emoji','🪤')} {name} ×{cnt} — {item.get('effect','')}")
            buttons.append([InlineKeyboardButton(
                text=f"🪤 نصبِ {name}", callback_data=f"house_trap_install:{name}:{uid}", style=ButtonStyle.SUCCESS)])
    else:
        lines.append("\n_هیچ تله‌ی نصب‌نشده‌ای تو انبارت نیست — از 🖤 بازارِ سیاه ›› 🏰 دفاعِ پایگاه بخر._")

    installed = house.get("traps", {})
    if installed:
        lines.append("\n🪤 **نصب‌شده (برداشتن = از دست دادنِ تله):**")
        for name, cnt in installed.items():
            buttons.append([InlineKeyboardButton(
                text=f"↩️ برداشتنِ {name} ({cnt})", callback_data=f"house_trap_uninstall:{name}:{uid}", style=ButtonStyle.DANGER)])

    buttons.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"house_home:{uid}", style=ButtonStyle.PRIMARY)])
    await cb.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


async def cb_house_traps(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    await cb.answer()
    await _render_trap_menu(cb, uid)


async def cb_house_trap_install(cb: CallbackQuery):
    _, name, uid_s = cb.data.split(":", 2)
    uid = int(uid_s)
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    house = hs.ensure_house(player)
    ok, msg = dtraps.install_trap(player, house, name)
    if ok:
        save_player(uid, player)
        log_sync(f"🪤 **TRAP INSTALL**\n👤 {player.get('name','—')} (`{uid}`)\n{msg}", "HOUSE")
    await cb.answer(msg, show_alert=True)
    await _render_trap_menu(cb, uid)


async def cb_house_trap_uninstall(cb: CallbackQuery):
    _, name, uid_s = cb.data.split(":", 2)
    uid = int(uid_s)
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    house = hs.ensure_house(player)
    ok, msg = dtraps.uninstall_trap(house, name)
    if ok:
        save_player(uid, player)
    await cb.answer(msg, show_alert=True)
    await _render_trap_menu(cb, uid)


# ─── 📦 انباری (صفحه‌بندی‌شده) ───────────────────────────────────
STORAGE_PAGE_SIZE = 8


def _storage_kb(uid: int, house: dict, inv: list, mode: str, page: int) -> tuple[InlineKeyboardMarkup, int, int]:
    items = house.get("storage", []) if mode == "s" else inv
    total_pages = max(1, (len(items) - 1) // STORAGE_PAGE_SIZE + 1) if items else 1
    page = max(0, min(page, total_pages - 1))
    start = page * STORAGE_PAGE_SIZE
    page_items = items[start:start + STORAGE_PAGE_SIZE]

    buttons = []
    for it in page_items:
        if mode == "s":
            buttons.append([InlineKeyboardButton(
                text=f"🎒 برگردون {it.get('emoji','📦')} {it['name']}",
                callback_data=f"house_retrieve:{it['id']}:{uid}", style=ButtonStyle.PRIMARY)])
        else:
            buttons.append([InlineKeyboardButton(
                text=f"📦 ذخیره {it.get('emoji','📦')} {it['name']}",
                callback_data=f"house_store:{it['id']}:{uid}", style=ButtonStyle.PRIMARY)])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"house_stpage:{mode}:{page-1}:{uid}", style=ButtonStyle.PRIMARY))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"house_stpage:{mode}:{page+1}:{uid}", style=ButtonStyle.PRIMARY))
    if nav:
        buttons.append(nav)

    tabs = [
        InlineKeyboardButton(
            text=("📦 انباری ✅" if mode == "s" else "📦 انباری"),
            callback_data=f"house_stpage:s:0:{uid}", style=ButtonStyle.SUCCESS if mode == "s" else ButtonStyle.PRIMARY),
        InlineKeyboardButton(
            text=("🎒 کوله‌پشتی ✅" if mode == "i" else "🎒 کوله‌پشتی"),
            callback_data=f"house_stpage:i:0:{uid}", style=ButtonStyle.SUCCESS if mode == "i" else ButtonStyle.PRIMARY),
    ]
    buttons.append(tabs)
    buttons.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data=f"house_home:{uid}", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=buttons), page, total_pages


def _storage_text(house: dict, inv: list, mode: str, page: int, total_pages: int) -> str:
    cap = hs.storage_capacity(house)
    stor = house.get("storage", [])
    header = f"📦 **انباری** ({len(stor)}/{cap})\n"
    if mode == "s":
        body = f"صفحه‌ی {page+1}/{total_pages} از انباری — برای برگردوندن به کوله‌پشتی رو یه آیتم بزن."
        if not stor:
            body = "انباری خالیه."
    else:
        body = f"صفحه‌ی {page+1}/{total_pages} از کوله‌پشتی — برای انتقال به انباری رو یه آیتم بزن."
        if not inv:
            body = "کوله‌پشتیت خالیه."
    return header + "\n" + body


async def _render_storage_menu(cb: CallbackQuery, uid: int, mode: str = "s", page: int = 0):
    player = get_player(uid)
    house = hs.ensure_house(player)
    inv = player.get("inventory", [])
    kb, page, total_pages = _storage_kb(uid, house, inv, mode, page)
    text = _storage_text(house, inv, mode, page, total_pages)
    await cb.message.edit_text(text, reply_markup=kb)


async def cb_house_storage(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    await cb.answer()
    await _render_storage_menu(cb, uid, mode="s", page=0)


async def cb_house_stpage(cb: CallbackQuery):
    _, mode, page_s, uid_s = cb.data.split(":")
    uid = int(uid_s)
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    await cb.answer()
    await _render_storage_menu(cb, uid, mode=mode, page=int(page_s))


async def cb_house_store(cb: CallbackQuery):
    _, item_id, uid_s = cb.data.split(":")
    uid = int(uid_s)
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    ok, msg = hs.store_item(player, item_id)
    if ok:
        save_player(uid, player)
    await cb.answer(msg, show_alert=True)
    await _render_storage_menu(cb, uid, mode="i", page=0)


async def cb_house_retrieve(cb: CallbackQuery):
    _, item_id, uid_s = cb.data.split(":")
    uid = int(uid_s)
    if not _owner_ok(cb, uid):
        await cb.answer("❌", show_alert=True)
        return
    player = get_player(uid)
    ok, msg = hs.retrieve_item(player, item_id)
    if ok:
        save_player(uid, player)
    await cb.answer(msg, show_alert=True)
    await _render_storage_menu(cb, uid, mode="s", page=0)


# ─── 🗡 دزدی از ملکِ بازیکن‌های دیگه ────────────────────────────
async def cmd_rob(msg: Message):
    uid = msg.from_user.id
    attacker = get_player(uid)
    if not attacker:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    from level_gate import check_level
    ok, why = check_level(attacker, "house")
    if not ok:
        await msg.answer(why)
        return

    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        await msg.answer(
            "🗡 **دزدی از ملکِ یه بازیکنِ دیگه**\n\n"
            "استفاده: `/rob <شماره‌کارت یا یوزرنیم یا آیدی>`\n\n"
            f"⏳ کول‌داون: هر {hs.ROBBERY_ATTACKER_COOLDOWN//3600} ساعت یه‌بار.\n"
            f"⚠️ اگه لو بری، {int(hs.ROBBERY_FAIL_PENALTY_PCT*100)}٪ از Zenِ نقدت جریمه می‌شی."
        )
        return

    from bank_system import resolve_target
    target_uid = resolve_target(parts[1], uid)
    if not target_uid or target_uid == uid:
        await msg.answer("❌ این بازیکن پیدا نشد (یا داری خودتو هدف می‌گیری).")
        return
    defender = get_player(target_uid)
    if not defender:
        await msg.answer("❌ این بازیکن هنوز بازی رو شروع نکرده.")
        return

    result = hs.attempt_robbery(uid, attacker, target_uid, defender)
    if not result["ok"]:
        await msg.answer(result["msg"])
        return

    save_player(uid, attacker)
    save_player(target_uid, defender)
    await msg.answer(result["msg"])
    log_sync(
        f"🗡 **ROBBERY** — {'✅ موفق' if result['success'] else '❌ ناموفق'}\n"
        f"👤 دزد: {attacker.get('name','—')} (`{uid}`) ← 🏠 قربانی: {defender.get('name','—')} (`{target_uid}`)",
        "HOUSE",
    )
    try:
        await msg.bot.send_message(target_uid, result["victim_msg"])
    except Exception:
        pass


def register_house_handlers(dp, bot):
    dp.message.register(cmd_house, Command("house"))
    dp.message.register(cmd_rob, Command("rob"))
    dp.callback_query.register(cb_house_home,      F.data.startswith("house_home:"))
    dp.callback_query.register(cb_house_collect,   F.data.startswith("house_collect:"))
    dp.callback_query.register(cb_house_upgrade,   F.data.startswith("house_upgrade:"))
    dp.callback_query.register(cb_house_mortgage,  F.data.startswith("house_mortgage:"))
    dp.callback_query.register(cb_house_insure,    F.data.startswith("house_insure:"))
    dp.callback_query.register(cb_house_buy_furn,  F.data.startswith("house_buy_furn:"))
    dp.callback_query.register(cb_house_furn,      F.data.startswith("house_furn:"))
    dp.callback_query.register(cb_house_store,     F.data.startswith("house_store:"))
    dp.callback_query.register(cb_house_retrieve,  F.data.startswith("house_retrieve:"))
    dp.callback_query.register(cb_house_storage,   F.data.startswith("house_storage:"))
    dp.callback_query.register(cb_house_stpage,    F.data.startswith("house_stpage:"))
    dp.callback_query.register(cb_house_traps,          F.data.startswith("house_traps:"))
    dp.callback_query.register(cb_house_trap_install,   F.data.startswith("house_trap_install:"))
    dp.callback_query.register(cb_house_trap_uninstall, F.data.startswith("house_trap_uninstall:"))
