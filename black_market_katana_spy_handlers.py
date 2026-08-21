# ============================================================
#  ASTRAL ABYSS — بازار سیاه: دلالِ بیداری + لودآوتِ جاسوسی
# ------------------------------------------------------------
#  این فایل دو تا از زیرمنوهای بازارِ سیاه رو از نو می‌سازه و
#  دکمه‌های قدیمیِ «bm:katana» و «bm:spy» رو (که تو loot_handlers.py
#  ثبت شدن) override می‌کنه — چون register_bm_katana_spy_handlers
#  زودتر از اون‌ها صدا زده می‌شه (تو register_loot_handlers).
#
#  🔮 دلال بیداری (bm:katana):
#    سیستمِ واقعیِ بیداریِ کاتانا (katana_core.py + katana_handlers.py،
#    قابلِ دسترس با /awaken) به مواد نایازی نیاز داره که تا الان هیچ‌جای
#    بازی به بازیکن داده نمی‌شد (katana_quests.py که قرار بود منبعش
#    باشه اصلاً وایر نشده بود). این پنل بازارِ سیاه رو تبدیل به تنها
#    منبعِ خریدِ این مواد می‌کنه — با سقفِ روزانه (تا گرایند حفظ بشه)
#    و تخفیفِ رتبه‌ی دیلر. دکمه‌ی قدیمیِ «ارتقای ساده با زن» (که یه
#    سیستمِ موازیِ بی‌ربط بود) کاملاً جایگزین می‌شه.
#
#  🕵️ تجهیزاتِ جاسوسی (bm:spy):
#    خرید مثلِ قبل از economy.SPY_ITEMS انجام می‌شه، ولی حالا بعدِ
#    خرید باید از پنلِ لودآوت (spy_loadout_system.py) تجهیزش کنی تا
#    اثر واقعی بذاره (ریسکِ دیلر / امنیتِ خونه / بونوسِ دزدی).
# ============================================================
from __future__ import annotations

import random
import time
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from economy import SPY_ITEMS, bz_to_display
from logger import log_sync
import spy_loadout_system as spy
import black_market_reputation as bmrep

from katana_core import MATERIALS_INFO, get_katana_identity, get_katana_soul

try:
    from loot_handlers import bm_main_kb, home_button
except Exception:  # جلوگیری از circular import در زمان بارگذاری اولیه
    bm_main_kb = None
    home_button = lambda: [InlineKeyboardButton(text="🏠 خانه", callback_data="menu:home")]


def _back_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="🔙 برگشت به بازار", callback_data="bm:back", style=ButtonStyle.PRIMARY)]]
    rows.append(home_button())
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ============================================================
#  🔮 دلال بیداری — Awakening Material Dealer
# ============================================================
AWAKEN_DEALER_PRICES = {
    # ── موادِ بیداریِ کاتانا (مثلِ قبل) ──────────────────────────
    "soul_shard":      {"kind": "awaken_material", "price": 8_000,  "daily_cap": 3, "emoji": "🔹", "name_fa": "تکه‌ی روح",
                         "desc": "برای بیداریِ کاتانا (/awaken)"},
    "void_core":       {"kind": "awaken_material", "price": 20_000, "daily_cap": 2, "emoji": "🌑", "name_fa": "هسته‌ی خلأ",
                         "desc": "برای بیداریِ کاتانا (/awaken)"},
    "dragon_scale":    {"kind": "awaken_material", "price": 22_000, "daily_cap": 2, "emoji": "🐉", "name_fa": "فلس اژدها",
                         "desc": "برای بیداریِ کاتانا (/awaken)"},
    "phoenix_feather": {"kind": "awaken_material", "price": 60_000, "daily_cap": 1, "emoji": "🔥", "name_fa": "پر ققنوس",
                         "desc": "برای بیداریِ کاتانا (/awaken)"},
    "soul_essence":    {"kind": "awaken_material", "price": 75_000, "daily_cap": 1, "emoji": "💜", "name_fa": "جوهر روح",
                         "desc": "برای بیداریِ کاتانا (/awaken)"},
    "Protection Scroll": {"kind": "awaken_material", "price": 15_000, "daily_cap": 3, "emoji": "🛡️", "name_fa": "طومار محافظت",
                         "desc": "موقعِ بیداری، شکست دیگه پس‌رفت نداره"},

    # 🆕 مادّه‌ی کیمیاگری — سنگِ‌روح تا الان فقط از کارگاه (🧪کیمیاگری)
    # به‌دست می‌اومد؛ حالا کیلث هم یه منبعِ کندتر ولی مستقیم‌ترشه.
    "soul_stone":      {"kind": "craft_material", "price": 14_000, "daily_cap": 2, "emoji": "🔮", "name_fa": "سنگِ‌روح",
                         "desc": "برای بازغلتوندنِ افیکسِ تجهیزات (🧪کیمیاگری)"},

    # 🆕 اکسیرهای فوریِ کیلث — نسخه‌ی «پولی و آماده»ی همون باف‌هایی که تو
    # کارگاهِ کیمیاگری هم می‌شه ساخت (crafting_system.POTION_RECIPES)؛
    # قوی‌تر و بی‌نیاز از موادِ خام، ولی گرون‌تر و سقفِ روزانه داره.
    "elixir_power_v":  {"kind": "consumable_buff", "price": 9_000,  "daily_cap": 2, "emoji": "🥃", "name_fa": "اکسیرِ قدرتِ کیلث",
                         "buff_stat": "dmg_pct", "buff_value": 0.15, "duration": 3600,
                         "desc": "+۱۵٪ دمیج به مدتِ ۱ ساعت"},
    "elixir_fortune_v": {"kind": "consumable_buff", "price": 9_000,  "daily_cap": 2, "emoji": "🍀", "name_fa": "اکسیرِ اقبالِ کیلث",
                         "buff_stat": "gold_find_pct", "buff_value": 0.20, "duration": 3600,
                         "desc": "+۲۰٪ شانسِ طلا به مدتِ ۱ ساعت"},
    "elixir_wisdom_v": {"kind": "consumable_buff", "price": 9_000,  "daily_cap": 2, "emoji": "📘", "name_fa": "اکسیرِ خردِ کیلث",
                         "buff_stat": "xp_pct", "buff_value": 0.20, "duration": 3600,
                         "desc": "+۲۰٪ تجربه به مدتِ ۱ ساعت"},
    "greater_potion":  {"kind": "consumable_heal", "price": 4_500,  "daily_cap": 3, "emoji": "💊", "name_fa": "معجونِ درمانِ کیلث",
                         "heal_pct": 0.6, "desc": "درمانِ آنیِ ۶۰٪ HP ماکزیمم"},
    "xp_tome":         {"kind": "consumable_xp",   "price": 16_000, "daily_cap": 2, "emoji": "📖", "name_fa": "کتابِ دانشِ کیلث",
                         "amount": 2_500, "desc": "+۲۵۰۰ XP فوری"},
}

# چند تا از کلیدها اسمِ نمایشی‌شون تو کوله‌پشتی با کلیدِ داخلی فرق داره
_INV_NAME_OVERRIDE = {"Protection Scroll": "Protection Scroll"}  # (نگه‌داشته شده برای سازگاری با katana_handlers._inventory_as_counts)

# 🆕 چرخشِ موجودی — هر چند ساعت یه بار فقط یه زیرمجموعه از آیتم‌ها موجودن
# (شبیهِ تابلوی کارگزار: یه سندِ مشترک تو system_col که همه‌ی بازیکن‌ها
# می‌بیننش، هر STOCK_ROTATE_HOURS ساعت رندوم می‌شه).
STOCK_ROTATE_HOURS = 4
STOCK_SIZE = 6  # از این‌همه آیتم، هر دوره فقط این تعداد موجودن


def _stock_doc() -> dict:
    from database import system_col
    doc = system_col().find_one({"_id": "kaelith_vault_stock"})
    if not doc or time.time() - doc.get("generated_at", 0) > STOCK_ROTATE_HOURS * 3600:
        doc = _generate_stock()
    return doc


def _generate_stock() -> dict:
    from database import system_col
    keys = list(AWAKEN_DEALER_PRICES.keys())
    # 🐛 باگ‌فیکس: قبلاً هر چرخش کاملاً مستقل و رندوم بود (random.sample از
    # کلِ ۱۱ کلید، ۶ تاشو انتخاب می‌کرد) — چون فقط ۱۱ آیتم داریم و هر بار
    # ۶ تاش نشون داده می‌شه، از نظرِ آماری معمولاً حدودِ نصفِ آیتم‌ها با
    # چرخشِ قبلی مشترک می‌موندن، پس به بازیکن حسِ «چیزی عوض نشد» می‌داد،
    # با این‌که واقعاً چرخش زده بود. الان اول از آیتم‌هایی که تو چرخشِ
    # قبلی نبودن پر می‌کنیم، و فقط اگه کم آوردیم (چون STOCK_SIZE به
    # تعدادِ کل کلیدها نزدیکه) از بقیه‌ی چرخشِ قبلی استفاده می‌کنیم —
    # این‌طوری هر چرخش واقعاً محسوس عوض می‌شه.
    prev_doc = system_col().find_one({"_id": "kaelith_vault_stock"})
    prev_stock = set(prev_doc.get("stock", [])) if prev_doc else set()
    fresh = [k for k in keys if k not in prev_stock]
    random.shuffle(fresh)
    stock = fresh[:STOCK_SIZE]
    if len(stock) < STOCK_SIZE:
        fillers = [k for k in keys if k not in stock]
        random.shuffle(fillers)
        stock += fillers[:STOCK_SIZE - len(stock)]
    doc = {"_id": "kaelith_vault_stock", "generated_at": time.time(), "stock": stock}
    system_col().update_one(
        {"_id": "kaelith_vault_stock"},
        {"$set": {k: v for k, v in doc.items() if k != "_id"}},
        upsert=True,
    )
    return doc


def _current_stock() -> list[str]:
    return _stock_doc()["stock"]


def _next_rotation_text(doc: dict) -> str:
    left = STOCK_ROTATE_HOURS * 3600 - (time.time() - doc.get("generated_at", 0))
    left = max(0, int(left))
    h, m = left // 3600, (left % 3600) // 60
    return f"{h} ساعت و {m} دقیقه" if h else f"{m} دقیقه"


def _today_key() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _ensure_daily(player: dict) -> dict:
    d = player.setdefault("bm_awaken_daily", {"date": _today_key(), "bought": {}})
    if d.get("date") != _today_key():
        d["date"] = _today_key()
        d["bought"] = {}
    return d


def _price_with_discount(player: dict, base: int) -> int:
    disc = bmrep.heat_reduction(player)  # از رتبه‌ی دیلر — همون تخفیفِ heat به‌عنوان تخفیفِ قیمت هم استفاده می‌شه
    return max(1, int(base * (1 - disc)))


def _katana_status_line(player: dict) -> str:
    char_name = player.get("character", "")
    if not char_name:
        return "⚠️ اول یه کاراکتر انتخاب کن تا وضعیتِ کاتانات دیده بشه.\n"
    try:
        ident = get_katana_identity(char_name)
        soul = get_katana_soul(char_name)
        stage = player.get("katana_awakening", 0)
        from katana_core import AWAKENING_STAGE_NAMES
        return f"🗡 **{soul['katana_name']}** — مرحله‌ی بیداری: **{AWAKENING_STAGE_NAMES[stage]}**\n"
    except Exception:
        return ""


def _render_katana_dealer(player: dict) -> tuple[str, InlineKeyboardMarkup]:
    daily = _ensure_daily(player)
    zen = player.get("zen", 0)
    stock_doc = _stock_doc()
    stock = stock_doc["stock"]

    lines = [
        "🔮 **دلال بیداری — Kaelith's Vault**\n",
        _katana_status_line(player),
        "_موادِ نایابِ بیداریِ کاتانا رو فقط این‌جا می‌شه پیدا کرد. سقفِ خریدِ روزانه داره._\n",
        f"_🔄 موجودیِ فروشگاه {STOCK_ROTATE_HOURS} ساعت یه بار عوض می‌شه — تا رفرشِ بعدی: {_next_rotation_text(stock_doc)}._\n\n",
    ]
    buttons = []
    for key, cfg in AWAKEN_DEALER_PRICES.items():
        if key not in stock:
            continue
        bought_today = daily["bought"].get(key, 0)
        left = cfg["daily_cap"] - bought_today
        price = _price_with_discount(player, cfg["price"])
        label = f"{cfg['emoji']} {cfg['name_fa']}"
        lines.append(
            f"{label} — {bz_to_display(price)} (باقیمانده امروز: {left}/{cfg['daily_cap']})\n"
            f"   _{cfg.get('desc','')}_\n"
        )
        if left > 0:
            buttons.append([InlineKeyboardButton(
                text=f"{cfg['emoji']} خرید {cfg['name_fa']} ({bz_to_display(price)})",
                callback_data=f"bm_awk_buy:{key}", style=ButtonStyle.SUCCESS)])
    lines.append(f"\n💰 موجودی: **{bz_to_display(zen)}**")
    buttons.append([InlineKeyboardButton(text="🌙 برو به معبدِ بیداری (/awaken)", callback_data="kt_menu", style=ButtonStyle.PRIMARY)])
    buttons.append([InlineKeyboardButton(text="🔙 برگشت به بازار", callback_data="bm:back", style=ButtonStyle.DANGER)])
    buttons.append(home_button())
    return "".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)


async def cb_bm_katana(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    text, kb = _render_katana_dealer(player)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


async def cmd_forge(msg: Message):
    """میانبرِ مستقیم: /forge — بدونِ رفتن به منوی اصلیِ بازار سیاه، صاف می‌ره سراغِ دلالِ بیداری."""
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    text, kb = _render_katana_dealer(player)
    await msg.answer(text, reply_markup=kb)


async def cb_bm_awk_buy(cb: CallbackQuery):
    uid = cb.from_user.id
    key = cb.data.split(":", 1)[1]
    player = await aget_player(uid)
    if not player or key not in AWAKEN_DEALER_PRICES:
        await cb.answer("❌", show_alert=True)
        return
    if key not in _current_stock():
        await cb.answer("❌ این آیتم الان تو موجودیِ دلال نیست — بعداً که چرخش کرد دوباره سر بزن.", show_alert=True)
        await cb_bm_katana(cb)
        return

    cfg = AWAKEN_DEALER_PRICES[key]
    daily = _ensure_daily(player)
    bought_today = daily["bought"].get(key, 0)
    if bought_today >= cfg["daily_cap"]:
        await cb.answer("❌ سهمیه‌ی امروزت برای این آیتم تموم شده.", show_alert=True)
        return

    price = _price_with_discount(player, cfg["price"])
    if player.get("zen", 0) < price:
        await cb.answer(f"❌ Zen کافی نداری! ({bz_to_display(price)} لازمه)", show_alert=True)
        return

    player["zen"] -= price
    daily["bought"][key] = bought_today + 1
    kind = cfg.get("kind", "awaken_material")
    result_note = ""

    if kind == "awaken_material":
        player.setdefault("inventory", []).append({
            "name": key, "emoji": cfg["emoji"], "type": "awaken_material",
            "sell": int(price * 0.3),
            # 🐛 فیکس: بدون این فلگ، موادِ بیداری تو کوله‌پشتیِ عمومی با بقیه‌ی
            # لوت‌ها قاطی می‌شدن و دکمه‌ی «فروش»/«فروش همه» می‌گرفتن — بازیکن‌ها
            # داشتن ناخواسته موادِ گرون‌قیمتی که خریده بودن رو با «فروش همه» از
            # دست می‌دادن (یا با فروشِ دستیِ اشتباهی، چون تو لیست شبیهِ لوتِ عادی بود).
            "shop_exclusive": True,
        })

    elif kind == "craft_material":
        import crafting_system as cfs
        cfs.add_material(player, key, 1, item_type="material")

    elif kind == "consumable_buff":
        from crafting_system import clean_expired_potion_buffs
        clean_expired_potion_buffs(player)
        buffs = player.setdefault("active_potion_buffs", {})
        stat = cfg["buff_stat"]
        was_active = stat in buffs
        buffs[stat] = {
            "value": cfg["buff_value"],
            "expires_at": time.time() + cfg["duration"],
            "name": cfg["name_fa"],
        }
        result_note = "تازه شد" if was_active else "فعال شد"

    elif kind == "consumable_heal":
        try:
            from skill_tree import effective_max_hp
            max_hp = effective_max_hp(player)
        except ImportError:
            max_hp = player.get("max_hp", 100)
        heal = int(max_hp * cfg.get("heal_pct", 0))
        player["hp"] = min(max_hp, player.get("hp", 0) + heal)
        result_note = f"{heal} HP درمان شدی"

    elif kind == "consumable_xp":
        amount = cfg.get("amount", 0)
        player["xp"] = player.get("xp", 0) + amount
        try:
            from bot import level_up_check
            player, leveled = level_up_check(player)
            if leveled:
                result_note = "لول‌آپ شدی! 🎉"
        except Exception:
            pass

    await asave_player(uid, player)

    log_sync(
        f"🔮 **KAELITH VAULT BUY**\n👤 {player.get('name','—')} (`{uid}`)\n"
        f"📦 {cfg['name_fa']} ({kind}) | 💰 {bz_to_display(price)}",
        "ECONOMY"
    )
    confirm = f"✅ {cfg['emoji']} {cfg['name_fa']} خریدی!"
    if result_note:
        confirm += f" ({result_note})"
    await cb.answer(confirm, show_alert=True)
    await cb_bm_katana(cb)


# ============================================================
#  🕵️ تجهیزاتِ جاسوسی — Spy Loadout
# ============================================================
async def cb_bm_spy(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    zen = player.get("zen", 0)
    lines = ["🕵️ **تجهیزات جاسوسی — Kaelith**\n",
              "_بخر، بعد از پایین برو پنلِ «🎒 لودآوت» و تجهیزش کن تا واقعاً اثر بذاره._\n\n"]
    buttons = []
    for i, item in enumerate(SPY_ITEMS):
        cat = spy.SPY_CATEGORY.get(item["name"], "utility")
        cat_label = spy.CATEGORY_LABEL[cat]
        lines.append(f"{item['emoji']} **{item['name']}** [{cat_label}]\n   {item['effect']} — {bz_to_display(item['cost'])}\n")
        buttons.append([InlineKeyboardButton(
            text=f"{item['emoji']} خرید {item['name']} ({bz_to_display(item['cost'])})",
            callback_data=f"bm_spy:{i}", style=ButtonStyle.SUCCESS)])
    lines.append(f"\n💰 موجودی: **{bz_to_display(zen)}**")
    buttons.append([InlineKeyboardButton(text="🎒 لودآوت / مصرفِ آیتم‌ها", callback_data="bm_spy_loadout", style=ButtonStyle.PRIMARY)])
    buttons.append([InlineKeyboardButton(text="🔙 برگشت به بازار", callback_data="bm:back", style=ButtonStyle.DANGER)])
    buttons.append(home_button())
    try:
        await cb.message.edit_text("".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    except Exception:
        await cb.message.answer("".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await cb.answer()


async def cb_bm_spy_buy(cb: CallbackQuery):
    uid = cb.from_user.id
    idx = int(cb.data.split(":")[1])
    player = await aget_player(uid)
    if not player or idx >= len(SPY_ITEMS):
        await cb.answer("❌", show_alert=True)
        return
    item = SPY_ITEMS[idx]
    if player.get("zen", 0) < item["cost"]:
        await cb.answer("❌ Zen کافی نداری!", show_alert=True)
        return
    player["zen"] -= item["cost"]
    player.setdefault("inventory", []).append({
        "name": item["name"], "emoji": item["emoji"], "type": "spy",
        "effect": item["effect"], "sell": int(item["cost"] * 0.5),
    })
    await asave_player(uid, player)
    log_sync(f"🕵️ **BM SPY BUY**\n👤 {player.get('name','—')} (`{uid}`)\n📦 {item['name']}", "ECONOMY")
    await cb.answer(f"✅ {item['name']} خریدی! برو لودآوت تجهیزش کن.", show_alert=True)
    await cb_bm_spy(cb)


def _loadout_kb(player: dict) -> InlineKeyboardMarkup:
    lo = spy.ensure_loadout(player)
    rows = []
    for slot in spy.SLOT_KEYS:
        cur = lo.get(slot)
        if cur:
            rows.append([InlineKeyboardButton(
                text=f"↩️ خروج {cur['name']} از {spy.CATEGORY_LABEL[slot]}",
                callback_data=f"bm_spy_unequip:{slot}", style=ButtonStyle.DANGER)])
        else:
            owned = {it["name"] for it in player.get("inventory", []) if spy.SPY_CATEGORY.get(it["name"]) == slot}
            for name in owned:
                rows.append([InlineKeyboardButton(
                    text=f"⚔️ تجهیز {name} ({spy.CATEGORY_LABEL[slot]})",
                    callback_data=f"bm_spy_equip:{name}", style=ButtonStyle.SUCCESS)])
    utility_owned = {it["name"] for it in player.get("inventory", []) if spy.SPY_CATEGORY.get(it["name"]) == "utility"}
    for name in utility_owned:
        rows.append([InlineKeyboardButton(text=f"🎫 مصرفِ {name}", callback_data=f"bm_spy_use:{name}", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="🔙 برگشت به جاسوسی", callback_data="bm:spy", style=ButtonStyle.PRIMARY)])
    rows.append(home_button())
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_bm_spy_loadout(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    text = spy.loadout_text(player)
    try:
        await cb.message.edit_text(text, reply_markup=_loadout_kb(player))
    except Exception:
        await cb.message.answer(text, reply_markup=_loadout_kb(player))
    await cb.answer()


async def cb_bm_spy_equip(cb: CallbackQuery):
    uid = cb.from_user.id
    item_name = cb.data.split(":", 1)[1]
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    ok, msg = spy.equip(player, item_name)
    if ok:
        await asave_player(uid, player)
    await cb.answer(msg, show_alert=True)
    await cb_bm_spy_loadout(cb)


async def cb_bm_spy_unequip(cb: CallbackQuery):
    uid = cb.from_user.id
    slot = cb.data.split(":", 1)[1]
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    ok, msg = spy.unequip(player, slot)
    if ok:
        await asave_player(uid, player)
    await cb.answer(msg, show_alert=True)
    await cb_bm_spy_loadout(cb)


async def cb_bm_spy_use(cb: CallbackQuery):
    uid = cb.from_user.id
    item_name = cb.data.split(":", 1)[1]
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    ok, msg = spy.use_utility(player, item_name)
    if ok:
        await asave_player(uid, player)
    await cb.answer(msg, show_alert=True)
    await cb_bm_spy_loadout(cb)


# ─── Register (باید قبلِ ثبتِ bm:katana/bm:spy قدیمی صدا زده بشه) ─
def register_bm_katana_spy_handlers(dp, bot):
    dp.message.register(cmd_forge,              Command("forge"))
    dp.callback_query.register(cb_bm_katana,       F.data == "bm:katana")
    dp.callback_query.register(cb_bm_awk_buy,       F.data.startswith("bm_awk_buy:"))

    dp.callback_query.register(cb_bm_spy,           F.data == "bm:spy")
    dp.callback_query.register(cb_bm_spy_buy,       F.data.startswith("bm_spy:"))
    dp.callback_query.register(cb_bm_spy_loadout,   F.data == "bm_spy_loadout")
    dp.callback_query.register(cb_bm_spy_equip,     F.data.startswith("bm_spy_equip:"))
    dp.callback_query.register(cb_bm_spy_unequip,   F.data.startswith("bm_spy_unequip:"))
    dp.callback_query.register(cb_bm_spy_use,       F.data.startswith("bm_spy_use:"))
