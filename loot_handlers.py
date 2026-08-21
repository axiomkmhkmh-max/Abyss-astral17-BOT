# ============================================================
#  ASTRAL ABYSS — Loot & Black Market Handlers (با لاگ‌گذاری کامل)
#  نمایش تمام آیتم‌های لوت‌شده با قیمت هرکدوم
# ============================================================
import asyncio, time, random, os
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

from database import get_player, save_player, asave_player, aget_player
from economy import (
    MAPS_DATA, ZONE_E, RARITY_E, roll_loot, get_enemy, bz_to_display,
    KATANA_LEVELS, SPY_ITEMS, DEFENSE_ITEMS, SHADOW_AUCTION,
    get_market_items, BZ_PER_SZ, BZ_PER_GZ,
    MAP_LOCATIONS, DEFAULT_LOCATIONS,
    is_bankrupt, BANKRUPTCY_MSG,
)
from characters import ALL_CHARACTERS
from logger import log_sync
from economy_ledger import record_transaction
from isekai_theme import map_label, realm_line, realm_name
import road_merchants as road_flavor

# ─── Dynamic Economy Engine (نوسان قیمت واقعی + مالیات چندلایه) ─
from economy_engine import (
    get_dynamic_price, register_trade, compute_sell_tax, compute_buy_total,
    add_reputation, deposit_tax_pool, get_market_overview,
    get_active_events_display, maybe_spawn_random_event, get_tax_pool,
    get_reputation_discount,
)

# ─── Loot State ──────────────────────────────────────────────
loot_state: dict[int, dict] = {}
MAX_ACTIONS   = 5
ACTION_RESET  = 600    # 10 minutes per batch
DAILY_MAX     = 68     # طبق درخواست: از ۵۰ به ۶۸ افزایش پیدا کرد
DAILY_RESET   = 86400  # 24 hours
DAILY_TRAVEL_MAX = 50  # با DAILY_MAX یکی شد — قبلاً ۱۰ بود و باعث می‌شد پلیر با اینکه اقدام داشت، غافلگیر بشه

def get_ls(uid):
    now = time.time()
    s = loot_state.get(uid, {})
    if not s:
        s = {
            "actions": MAX_ACTIONS,
            "reset_at": now + ACTION_RESET,
            "daily_used": 0,
            "daily_reset_at": now + DAILY_RESET,
            "traveling": None,
            "arrive": 0,
            "daily_travel_used": 0,
        }
        loot_state[uid] = s
        return s

    # اگه زمان سفر گذشته (یا سفر فوری بوده و جایی پاک نشده)، رفع گیر کن
    if s.get("traveling") and s.get("arrive", 0) <= now:
        s["traveling"] = None
        s["arrive"] = 0

    # Daily reset
    if now >= s.get("daily_reset_at", 0):
        s["daily_used"]     = 0
        s["daily_travel_used"] = 0
        s["daily_reset_at"] = now + DAILY_RESET

    # Batch reset
    if now >= s.get("reset_at", 0):
        s["actions"]  = MAX_ACTIONS
        s["reset_at"] = now + ACTION_RESET

    loot_state[uid] = s
    return s

async def use_action(uid: int) -> bool:
    s = get_ls(uid)
    if s["actions"] <= 0:
        return False
    if s.get("daily_used", 0) >= DAILY_MAX:
        return False
    player = await aget_player(uid)
    if player and is_bankrupt(player):
        return False
    s["actions"]    -= 1
    s["daily_used"]  = s.get("daily_used", 0) + 1
    return True

def action_bar(n):
    return "🟩"*n + "⬛"*(MAX_ACTIONS-n)

# ─── Keyboards ───────────────────────────────────────────────
def back_kb(cb_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔙 برگشت", callback_data=cb_data, style=ButtonStyle.PRIMARY)
    ]])

MAP_LIST = list(MAPS_DATA.keys())  # ایندکس ثابت برای callback

# عکس نقشه‌ی جهان — فایل عکستو با همین اسم کنار پروژه بذار
# (یا این مقدار رو به لینک آنلاین عکس تغییر بده)
WORLD_MAP_IMAGE = "world_map.jpg"


async def send_photo_or_text(target, image_path: str, caption: str, reply_markup=None):
    """
    اگه فایل عکس روی سرور وجود داشته باشه، عکس رو با کپشن می‌فرسته.
    اگه فایل نبود (یا خرابی توی فرستادنش پیش اومد)، به‌جاش یه پیام متنی
    ساده می‌فرسته تا ربات هیچ‌وقت کرش نکنه — کافیه بعداً فایل عکس رو
    توی پروژه بذاری تا خودکار فعال بشه.
    """
    if image_path and os.path.isfile(image_path):
        try:
            await target.answer_photo(
                photo=FSInputFile(image_path),
                caption=caption,
                reply_markup=reply_markup
            )
            return
        except Exception:
            pass
    await target.answer(caption, reply_markup=reply_markup)

# رنگ هر دکمه‌ی «پنل اصلی» — همیشه آبی (primary)، چون ناوبریه نه یه اکشن
def home_button() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="🏠 پنل اصلی", callback_data="menu:home", style=ButtonStyle.PRIMARY)]

# رنگ هر مپ رو بر اساس خطرِ همون منطقه تعیین می‌کنه: امن=سبز، مورد مناقشه=آبی، خطرناک=قرمز
_ZONE_STYLE = {"safe": ButtonStyle.SUCCESS, "contested": ButtonStyle.PRIMARY, "danger": ButtonStyle.DANGER}

def map_select_kb(current_map: str | None = None) -> InlineKeyboardMarkup:
    from economy import get_travel_time
    buttons = []
    for i, (name, data) in enumerate(MAPS_DATA.items()):
        zone = ZONE_E.get(data["zone"], "🟡")
        # ─── باگ‌فیکس: اگه بازیکن همین الان تو همین مپه، دیگه لازم نیست
        # دوباره سفر کنه — نباید دوباره زمانِ سفر رو نشونش بدیم/ازش بگیریم.
        if current_map is not None and name == current_map:
            t_txt = "همینجایی ✅"
        else:
            t = get_travel_time(name)
            t_txt = "فوری" if t == 0 else f"{t}s"
        buttons.append([
            InlineKeyboardButton(
                text=f"{data['emoji']} {map_label(name)} ({t_txt}) {zone}",
                callback_data=f"lg:{i}",
                style=_ZONE_STYLE.get(data.get("zone"), ButtonStyle.PRIMARY),
            ),
        ])
    buttons.append(home_button())
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def location_kb(map_idx: int, map_name: str, player: dict | None = None) -> InlineKeyboardMarkup:
    from fog_of_war import is_explored
    from map_activity import hot_locations
    locs = MAP_LOCATIONS.get(map_name, DEFAULT_LOCATIONS)
    hot = hot_locations(map_name)
    buttons = []
    for li, loc in enumerate(locs):
        if player is not None and not is_explored(player, map_name, li):
            label = "🌫️ ??? (کشف‌نشده)"
        else:
            label = f"{loc['emoji']} {loc['name']}"
            if loc['name'] in hot:
                label += " 🔥"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"loc:{map_idx}:{li}", style=ButtonStyle.SUCCESS)])
    buttons.append([InlineKeyboardButton(text="👑 چالش باس منطقه", callback_data=f"bossch:{map_idx}", style=ButtonStyle.DANGER)])
    buttons.append([InlineKeyboardButton(text="🔙 برگشت به نقشه", callback_data="loot:again", style=ButtonStyle.PRIMARY)])
    buttons.append(home_button())
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def cb_boss_challenge(cb: CallbackQuery):
    """👑 چالش باس منطقه — الان به‌جای یه فایتِ تک‌نفره، به باسِ چندنفره‌ی
    مشترکِ همین مپ ملحق می‌کنه (یا اگه زنده نبود، یکی تازه اسپان می‌کنه).
    هر بازیکنی که تو هر چتی سراغِ این مپ بیاد می‌تونه ملحق بشه؛ لوت هم
    دقیقاً بر اساسِ سهمِ دمیجِ هرکس (فرمولِ رتبه‌ایِ boss_engine) بینِ همه‌ی
    شرکت‌کننده‌ها عادلانه تقسیم می‌شه."""
    uid = cb.from_user.id
    try:
        idx = int(cb.data.split(":")[1])
        map_name = MAP_LIST[idx]
    except Exception:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    from mob_combat import MIN_HP_PCT_FOR_BOSS_CHALLENGE
    hp_pct = player.get("hp", 100) / max(1, player.get("max_hp", 100))
    if hp_pct < MIN_HP_PCT_FOR_BOSS_CHALLENGE:
        await cb.answer(
            f"❤️ برای چالش باس منطقه حداقل {int(MIN_HP_PCT_FOR_BOSS_CHALLENGE*100)}٪ HP لازمه! اول درمان شو.",
            show_alert=True)
        return
    await cb.answer("👑 وارد میدان باس شدی!")
    from region_boss_handlers import enter_region_boss
    await enter_region_boss(cb.message, uid, map_name)

async def _show_locations(msg, uid: int, map_name: str):
    s = get_ls(uid)
    s["traveling"] = None
    s["arrive"] = 0

    player = await aget_player(uid)
    # ─── باگ‌فیکس: مپِ فعلیِ پلیر باید همین‌جا (لحظه‌ی رسیدن) ثبت بشه،
    # نه فقط تو مسیرِ دخمه‌ی «_do_loot». قبلاً اگه بازیکن به building/
    # house/hospital/bank می‌رفت، player["map"] هیچ‌وقت آپدیت نمی‌شد و
    # پنلِ حمله همچنان مپِ قبلی رو نشون می‌داد.
    if player is not None and player.get("map") != map_name:
        player["map"] = map_name
        await asave_player(uid, player)
    data = MAPS_DATA[map_name]
    locs = MAP_LOCATIONS.get(map_name, DEFAULT_LOCATIONS)
    map_idx = MAP_LIST.index(map_name)

    from fog_of_war import is_explored, map_progress_text
    from map_activity import recent_feed_text
    lines = [
        f"{data['emoji']} **رسیدی به {map_name}!**\n_{data['desc']}_\n\n",
        f"{realm_line(map_name)}\n\n",
        f"{map_progress_text(player, map_name, len(locs))}\n\n",
        f"📡 **این‌جا چه خبره:**\n{recent_feed_text(map_name)}\n\n",
        "📍 **کجا رو بگردی؟**\n\n",
    ]
    for li, l in enumerate(locs):
        if is_explored(player, map_name, li):
            lines.append(f"{l['emoji']} {l['name']} — _{l['desc']}_\n")
        else:
            lines.append("🌫️ ??? — _هنوز کشفش نکردی_\n")
    text = "".join(lines)
    kb = location_kb(map_idx, map_name, player)
    try:
        await msg.edit_text(text, reply_markup=kb)
    except Exception:
        await msg.answer(text, reply_markup=kb)

def bm_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 فروشگاه",         callback_data="bm:shop", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="🤝 اعتماد بازار",     callback_data="bm:favor", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="🕵️ تجهیزات جاسوسی", callback_data="bm:spy", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="🔮 دلالِ بیداری",     callback_data="bm:katana", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="🏰 دفاع پایگاه",     callback_data="bm:defense", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="💎 حراجی سایه",      callback_data="bm:auction", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🗝️ صندوق‌ها و کلیدها", callback_data="bm:vault", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="🧩 مجموعه‌های ست",    callback_data="bm:sets", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="💰 فروش آیتم",       callback_data="bm:sell", style=ButtonStyle.DANGER)],
        [InlineKeyboardButton(text="📊 وضعیت بازار",     callback_data="bm:market", style=ButtonStyle.PRIMARY)],
        # ─── عمیق‌سازیِ بازارِ سیاه: رتبه‌بندی + دیلرهای گردشی + قاچاق ───
        [InlineKeyboardButton(text="🏷️ رتبه‌ی دیلر",     callback_data="bm:rank", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🕴️ دیلرهای گردشی",   callback_data="bm:dealers", style=ButtonStyle.DANGER)],
        [InlineKeyboardButton(text="📦 تابلوی قاچاق",     callback_data="bm:smuggle", style=ButtonStyle.DANGER)],
        home_button(),
    ])

# ─── /loot ───────────────────────────────────────────────────
async def cmd_loot(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    s = get_ls(uid)
    now = time.time()

    if s.get("traveling") and now < s.get("arrive", 0):
        rem = int(s["arrive"] - now)
        await msg.answer(f"🚶 در حال سفر به **{s['traveling']}**...\n⏳ {rem} ثانیه مانده")
        return

    daily_used = s.get("daily_used", 0)
    daily_left = DAILY_MAX - daily_used

    if daily_left <= 0:
        daily_rem = int(s.get("daily_reset_at", now) - now)
        h = daily_rem // 3600
        m = (daily_rem % 3600) // 60
        await msg.answer(
            f"📵 **سقف روزانه تموم شد!**\n\n"
            f"امروز {DAILY_MAX} اقدام انجام دادی.\n"
            f"⏳ ریست در: **{h}h {m}m**"
        )
        return

    if s["actions"] <= 0:
        rem = int(s["reset_at"] - now)
        await msg.answer(
            f"⚡ **اقدامات تموم شد!**\n"
            f"{action_bar(0)}\n"
            f"⏳ {rem//60}:{rem%60:02d} تا ریست بعدی\n\n"
            f"📊 روزانه: {daily_used}/{DAILY_MAX} اقدام"
        )
        return

    travel_used = s.get("daily_travel_used", 0)
    travel_left = DAILY_TRAVEL_MAX - travel_used
    if travel_left <= 0:
        daily_rem = int(s.get("daily_reset_at", now) - now)
        h = daily_rem // 3600
        m = (daily_rem % 3600) // 60
        await msg.answer(
            f"🚫 **سقفِ سفرِ روزانه تموم شد!**\n\n"
            f"امروز {DAILY_TRAVEL_MAX} بار سفر کردی (جدا از سقفِ اقدام‌ها).\n"
            f"⏳ ریست در: **{h}h {m}m**"
        )
        return

    from loot_engine import get_streak_title
    streak = player.get("loot_streak", 0)
    streak_title = get_streak_title(streak)
    streak_line = f"🔥 استریک لوت: {streak}x" + (f" {streak_title}" if streak_title else "") + "\n\n"

    reset_in = int(s["reset_at"] - now)
    await send_photo_or_text(
        msg, WORLD_MAP_IMAGE,
        f"🗺 **انتخاب مپ برای لوت:**\n\n"
        f"⚡ اقدامات: {action_bar(s['actions'])} ({s['actions']}/{MAX_ACTIONS})\n"
        f"⏳ ریست در: {reset_in//60}:{reset_in%60:02d}\n"
        f"📊 روزانه: {daily_used}/{DAILY_MAX} ({daily_left} مانده)\n"
        f"🚶 سفر روزانه: {travel_used}/{DAILY_TRAVEL_MAX} ({travel_left} مانده)\n\n"
        f"{streak_line}"
        f"🟢 Safe | 🟡 Contested | 🔴 Danger\n_(زمان داخل پرانتز = سفر)_",
        reply_markup=map_select_kb(player.get("map"))
    )

# ─── Travel ──────────────────────────────────────────────────
async def _send_road_arrival(msg, map_name: str, zone: str):
    """پیامِ نریشنِ ورودِ ایزکایی + دکمه‌ی دیدنِ تاجرِ دوره‌گرد — کاملاً افزودنی،
    به هیچ منطقِ دیگه‌ای دست نمی‌زنه."""
    try:
        await msg.answer(
            f"🌀 _{road_flavor.arrival_line(zone)}_",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🧳 تاجرِ دوره‌گرد رو ببین", callback_data=f"road:open:{map_name}")
            ]])
        )
    except Exception:
        pass


async def cb_loot_go(cb: CallbackQuery, bot: Bot):
    uid = cb.from_user.id
    try:
        idx = int(cb.data[3:])
    except:
        await cb.answer("❌ خطا!", show_alert=True)
        return

    if idx >= len(MAP_LIST):
        await cb.answer("❌ مپ پیدا نشد!", show_alert=True)
        return

    map_name = MAP_LIST[idx]
    s = get_ls(uid)

    if s["actions"] <= 0:
        now = time.time()
        rem = int(s["reset_at"] - now)
        await cb.answer(f"⚡ اقداماتت تموم شده! {rem//60}:{rem%60:02d} مانده", show_alert=True)
        return

    if s.get("traveling"):
        await cb.answer(f"🚶 هنوز داری به {s['traveling']} میری!", show_alert=True)
        return

    player = await aget_player(uid)
    if player and is_bankrupt(player):
        await cb.answer(BANKRUPTCY_MSG, show_alert=True)
        return

    if s.get("daily_travel_used", 0) >= DAILY_TRAVEL_MAX and player and player.get("map") != map_name:
        await cb.answer(f"🚫 امروز {DAILY_TRAVEL_MAX} بار سفر کردی! فردا دوباره تلاش کن.", show_alert=True)
        return

    data   = MAPS_DATA[map_name]

    # ─── همه‌ی محدودیت‌های ورود به مپ (لول + کیلِ باسِ تیرِ قبلی) حذف شد ───
    # قبلاً اینجا دو گیت بود: world_tiers.can_access_map (لول/Ascension)
    # و یه چکِ area_bosses_killed (باید باسِ تیر پایین‌تر رو کشته باشی).
    # طبق درخواست، هر دو کامل برداشته شدن — بازیکن با هر لول/پیشرفتی
    # می‌تونه مستقیم به هر مپی سفر کنه.

    zone_warn = "\n⚠️ **Danger Zone!**" if data["zone"] == "danger" else ""

    from economy import get_travel_time
    player_zen = player.get("zen", 0) if player else 0
    # ─── باگ‌فیکس: اگه بازیکن همین الان تو همین مپه، دیگه نباید دوباره
    # همون زمانِ سفر رو ازش بگیریم — قبلاً حتی سفر به همون مپیِ فعلی هم
    # کامل طول می‌کشید، انگار هیچ‌وقت اونجا نبوده.
    already_here = bool(player) and player.get("map") == map_name
    if already_here:
        travel = 0
    else:
        travel = get_travel_time(map_name, player_zen)
    walked = (not already_here) and player_zen < 200
    if walked:
        zone_warn += "\n🚶‍♂️ _طلای کافی برای سفر سواره نداشتی — پیاده می‌ری (زمان بیشتر)._"

    s["traveling"] = map_name
    s["arrive"]    = time.time() + travel
    if not already_here:
        s["daily_travel_used"] = s.get("daily_travel_used", 0) + 1
    token = s.get("travel_token", 0) + 1
    s["travel_token"] = token

    log_sync(
        f"🚶 **TRAVEL START**\n"
        f"👤 {player.get('name','—') if player else 'نامشخص'} (`{uid}`)\n"
        f"📍 مقصد: {map_name}\n"
        f"⏱️ زمان: {travel} ثانیه",
        "LOOT"
    )

    await cb.answer(f"🚶 عازمِ {realm_name(map_name)}!", show_alert=False)

    if travel == 0:
        s["traveling"] = None
        s["arrive"] = 0
        sent = await cb.message.answer(
            f"{data['emoji']} **رسیدی به {map_name}!**\n_{data['desc']}_\n\nدر حال ورود... ⏳"
        )
        await asyncio.sleep(1)
        await _send_road_arrival(cb.message, map_name, data["zone"])
        await _show_locations(sent, uid, map_name)
        return

    sent = await cb.message.answer(
        f"🌀 _{road_flavor.departure_line()}_\n\n"
        f"🚶 **در حالِ سفر به {realm_name(map_name)}** ({map_name})\n"
        f"_{data['desc']}_\n\n"
        f"⏳ **{travel} ثانیه** تا رسیدن{zone_warn}\n\n"
        f"_صبر کن..._",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ لغو سفر", callback_data="loot:cancel", style=ButtonStyle.DANGER)
        ]])
    )

    asyncio.create_task(_travel_task(sent, uid, map_name, travel, zone_warn, bot, token))

async def _travel_task(msg, uid: int, map_name: str, travel: int, zone_warn: str, bot: Bot, token: int):
    data = MAPS_DATA[map_name]
    elapsed = 0
    interval = 5

    while elapsed < travel:
        step = min(interval, travel - elapsed)
        await asyncio.sleep(step)
        elapsed += step

        cur = loot_state.get(uid, {})
        if cur.get("travel_token") != token:
            return

        remaining = travel - elapsed
        if remaining <= 0:
            break

        try:
            await msg.edit_text(
                f"🚶 **در حال سفر به {map_name}**\n"
                f"_{data['desc']}_\n\n"
                f"⏳ **{remaining} ثانیه** تا رسیدن{zone_warn}\n\n"
                f"_{road_flavor.road_ambient_line()}_",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="❌ لغو سفر", callback_data="loot:cancel", style=ButtonStyle.DANGER)
                ]])
            )
        except Exception:
            pass

    cur = loot_state.get(uid, {})
    if cur.get("travel_token") == token:
        cur["traveling"] = None
        cur["arrive"]    = 0
        
        log_sync(
            f"📍 **TRAVEL ARRIVE**\n"
            f"👤 کاربر: `{uid}`\n"
            f"📍 مقصد: {map_name}",
            "LOOT"
        )
        
        await _send_road_arrival(msg, map_name, data["zone"])
        await _show_locations(msg, uid, map_name)

async def cb_loot_cancel(cb: CallbackQuery):
    uid = cb.from_user.id
    s = get_ls(uid)
    
    log_sync(
        f"❌ **TRAVEL CANCEL**\n"
        f"👤 کاربر: `{uid}`\n"
        f"📍 مقصد لغو شده: {s.get('traveling', 'نامشخص')}",
        "LOOT"
    )
    
    s["traveling"] = None
    s["arrive"] = 0
    s["travel_token"] = s.get("travel_token", 0) + 1
    await cb.answer("❌ سفر لغو شد!")
    await cb.message.delete()

# ─── Do Loot ─────────────────────────────────────────────────
async def _do_loot(msg: Message, uid: int, map_name: str, bot: Bot):
    player = await aget_player(uid)
    if not player: return

    player["map"] = map_name
    await asave_player(uid, player)

    if not await use_action(uid):
        s = get_ls(uid)
        daily_used = s.get("daily_used", 0)
        if daily_used >= DAILY_MAX:
            await msg.edit_text("📵 **سقف روزانه تموم شد!**\nفردا دوباره بیا!")
        else:
            await msg.edit_text("⚡ اقداماتت تموم شده!")
        return

    from combat_handlers import update_quest
    update_quest(uid, "loot", 1)

    from mob_combat import start_encounter
    await start_encounter(msg, uid, map_name)

async def cb_loot_location(cb: CallbackQuery, bot: Bot):
    uid = cb.from_user.id
    try:
        _, map_idx_s, loc_idx_s = cb.data.split(":")
        map_idx, loc_idx = int(map_idx_s), int(loc_idx_s)
    except Exception:
        await cb.answer("❌ خطا!", show_alert=True)
        return

    if map_idx >= len(MAP_LIST):
        await cb.answer("❌ مپ پیدا نشد!", show_alert=True)
        return
    map_name = MAP_LIST[map_idx]

    s = get_ls(uid)
    if s["actions"] <= 0:
        now = time.time()
        rem = int(s["reset_at"] - now)
        await cb.answer(f"⚡ اقداماتت تموم شده! {rem//60}:{rem%60:02d} مانده", show_alert=True)
        return

    locs = MAP_LOCATIONS.get(map_name, DEFAULT_LOCATIONS)
    if loc_idx >= len(locs):
        await cb.answer("❌ لوکیشن پیدا نشد!", show_alert=True)
        return
    loc = locs[loc_idx]

    from fog_of_war import mark_explored, grant_discovery_reward
    from map_activity import log_event
    player = await aget_player(uid)
    discovered_note = ""
    if mark_explored(player, map_name, loc_idx):
        reward = grant_discovery_reward(player)
        await asave_player(uid, player)
        discovered_note = f"\n\n🗺️ **منطقه‌ی جدید کشف شد!** +{reward['zen']:,} Zen | +{reward['xp']} XP"
        log_sync(
            f"🗺️ **NEW DISCOVERY**\n👤 {cb.from_user.first_name} (`{uid}`)\n"
            f"📍 {map_name} → {loc['name']}\n💰 +{reward['zen']:,} Zen | ✨ +{reward['xp']} XP",
            "EXPLORE"
        )
        log_event(map_name, cb.from_user.first_name, "explore", loc["name"], actor_id=uid)
    else:
        log_event(map_name, cb.from_user.first_name, "loot", loc["name"], actor_id=uid)

    log_sync(
        f"🔍 **LOOT LOCATION**\n"
        f"👤 {cb.from_user.first_name} (`{uid}`)\n"
        f"📍 مپ: {map_name}\n"
        f"📍 لوکیشن: {loc['name']}",
        "LOOT"
    )

    await cb.answer(f"📍 وارد {loc['name']} شدی..." + (" 🗺️ کشف جدید!" if discovered_note else ""))

    # ─── آنبوردینگ: قدمِ سوم (لوت) تموم شد ────────────────────────
    import onboarding
    grad_hint = onboarding.on_loot_visited(player)
    if grad_hint:
        await asave_player(uid, player)
        from bot import main_kb, _is_group_chat
        is_group = _is_group_chat(cb.message.chat.type)
        await cb.message.answer(
            onboarding.strip_graduation_mark(grad_hint),
            reply_markup=main_kb(is_group=is_group)
        )

    loc_type = loc.get("type", "building")

    # ─── 🆕 موتورهای عمیقِ لوکیشن‌های متروکه ─────────────────────
    if loc_type == "building":
        if not await use_action(uid):
            s2 = get_ls(uid)
            await cb.message.edit_text(
                "📵 **سقف روزانه تموم شد!**" if s2.get("daily_used", 0) >= DAILY_MAX else "⚡ اقداماتت تموم شده!"
            )
            return
        from abandoned_locations import start_building_run, _building_kb
        res = start_building_run(uid, player, map_name)
        await asave_player(uid, player)
        text = f"{loc['emoji']} **{loc['name']}**\n_{loc['desc']}_{discovered_note}\n\n{res['text']}"
        kb = _building_kb(res.get("can_continue", False))
        try:
            await cb.message.edit_text(text, reply_markup=kb)
        except Exception:
            await cb.message.answer(text, reply_markup=kb)
        return

    if loc_type in ("house", "hospital", "bank"):
        if not await use_action(uid):
            s2 = get_ls(uid)
            await cb.message.edit_text(
                "📵 **سقف روزانه تموم شد!**" if s2.get("daily_used", 0) >= DAILY_MAX else "⚡ اقداماتت تموم شده!"
            )
            return
        from abandoned_locations import visit_location
        res = visit_location(player, loc, map_name)
        await asave_player(uid, player)
        prefix = f"{loc['emoji']} **{loc['name']}**\n_{loc['desc']}_{discovered_note}\n\n{res['text']}\n\n"
        if res.get("spawn_alarm"):
            try:
                await cb.message.edit_text(prefix + "🚨 نگهبانِ امنیتی سررسید...")
            except Exception:
                pass
            from mob_combat import start_encounter
            await start_encounter(cb.message, uid, map_name, force_boss=True)
            return
        try:
            await cb.message.edit_text(prefix + "در حال ادامه‌ی جستجو... ⏳")
        except Exception:
            pass
        from combat_handlers import update_quest
        update_quest(uid, "loot", 1)
        from mob_combat import start_encounter
        await start_encounter(cb.message, uid, map_name)
        return

    try:
        await cb.message.edit_text(
            f"{loc['emoji']} **{loc['name']}**\n_{loc['desc']}_{discovered_note}\n\nدر حال جستجو... ⏳"
        )
    except Exception:
        pass
    await _do_loot(cb.message, uid, map_name, bot)

async def cb_loot_sell_all(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    inv = player.get("inventory", [])
    if not inv:
        await cb.answer("🎒 کوله‌پشتیت خالیه!", show_alert=True)
        return

    zone = MAPS_DATA.get(player.get("map", ""), {}).get("zone", "contested")
    gross_total = 0
    
    # ─── لاگ کامل آیتم‌های فروخته‌شده ────────────────────────────
    sold_items = []
    for item in inv:
        _, sell_p, _, _ = get_dynamic_price("global_loot", item)
        gross_total += sell_p
        register_trade("global_loot", item, "sell")
        sold_items.append(f"{item.get('emoji','📦')} {item.get('name','—')} ({item.get('rarity','common')}) — {bz_to_display(sell_p)}")

    tax = compute_sell_tax(player, gross_total, zone, "global_loot")
    zen_before = player.get("zen", 0)
    player["inventory"] = []
    player["zen"] = player.get("zen", 0) + tax["net"]
    add_reputation(player, min(3, len(inv)))
    await asave_player(uid, player)
    deposit_tax_pool(tax["tax_amount"], uid)

    record_transaction(
        "loot_sell_all", uid, username=player.get("name"),
        item_name=f"{len(inv)} آیتم", quantity=len(inv),
        amount=gross_total, fee=tax["tax_amount"],
        balance_before=zen_before, balance_after=player["zen"],
        extra={"items": sold_items, "zone": zone},
    )

    log_sync(
        f"💰 **SELL ALL ITEMS (DETAILED)**\n"
        f"👤 {player.get('name','—')} (`{uid}`)\n"
        f"📦 تعداد آیتم‌ها: {len(inv)}\n"
        f"{'─'*20}\n"
        f"📋 **لیست آیتم‌های فروخته‌شده:**\n" + ("\n".join(f"  • {it}" for it in sold_items) if sold_items else "  • هیچی\n") +
        f"{'─'*20}\n"
        f"💰 مبلغ خام: {bz_to_display(gross_total)}\n"
        f"📉 مالیات ({tax['tax_rate']*100:.1f}٪): {bz_to_display(tax['tax_amount'])}\n"
        f"💵 دریافتی خالص: {bz_to_display(tax['net'])}\n"
        f"🏦 موجودی جدید: {bz_to_display(player['zen'])}",
        "ECONOMY"
    )

    tax_note = ("🎉 معاف از مالیات (ایونت فعال)!" if tax["tax_free_event"]
                else f"📉 مالیات ناحیه‌ی {ZONE_E.get(zone,'🟡')} ({tax['tax_rate']*100:.1f}٪): -{bz_to_display(tax['tax_amount'])}")
    await cb.answer(f"💰 {bz_to_display(tax['net'])} گرفتی!", show_alert=True)
    await cb.message.edit_text(
        f"💰 **همه فروخته شد!**\n\n"
        f"فروش خام: **{bz_to_display(gross_total)}**\n"
        f"{tax_note}\n"
        f"دریافتی خالص: **{bz_to_display(tax['net'])}**\n"
        f"موجودی: **{bz_to_display(player['zen'])}**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🗺 لوت دوباره", callback_data="loot:again", style=ButtonStyle.PRIMARY)
        ]])
    )

async def cb_loot_keep(cb: CallbackQuery):
    await cb.answer("🎒 آیتم‌ها نگه داشته شدن!")

# ─── باگ‌فیکس: دکمه‌ی «دابل یا هیچ» تو mob_combat.py ساخته می‌شد
# (callback_data="loot:gamble:{idx}") ولی هیچ‌جا هندلری براش ثبت
# نشده بود، پس با زدنش ربات هیچ جوابی نمی‌داد و کلاینت ارور می‌داد.
GAMBLE_WIN_CHANCE = 0.5

# ─── ایموجی‌های پرمیوم (custom emoji) ───────────────────────────
# نکته: دیگه لازم نیست اینجا دستی چیزی بسازیم — الان کل ربات یک
# middleware سراسری داره (نگاه کن به bot.py) که خودش parse_mode رو
# HTML می‌کنه و هر ایموجی معمولی تو متن رو به پرمیوم تبدیل می‌کنه.
# فقط کافیه از ایموجی معمولی و Markdown سبک (*bold*) استفاده کنیم.

async def cb_loot_gamble(cb: CallbackQuery):
    uid = cb.from_user.id
    try:
        idx = int(cb.data.split(":")[2])
    except Exception:
        await cb.answer("❌ خطا!", show_alert=True)
        return

    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    inv = player.get("inventory", [])
    if idx >= len(inv) or inv[idx].get("gambled"):
        await cb.answer("❌ این آیتم دیگه قابل قمار نیست!", show_alert=True)
        return

    item = inv[idx]
    won = random.random() < GAMBLE_WIN_CHANCE

    # ─── دکمه رو از پیام قبلی حذف کن تا نشه دوباره روش زد ──────────
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if won:
        old_sell = item.get("sell", 0)
        item["sell"] = old_sell * 2
        item["gambled"] = True
        await asave_player(uid, player)
        log_sync(
            f"🎲 **LOOT GAMBLE — WIN**\n"
            f"👤 {player.get('name','—')} (`{uid}`)\n"
            f"📦 آیتم: {item.get('name','—')}\n"
            f"💰 ارزش: {bz_to_display(old_sell)} → {bz_to_display(item['sell'])}",
            "LOOT"
        )
        await cb.answer("🎉 بردی!", show_alert=False)
        try:
            await cb.message.answer(
                f"🎮 *دابل یا هیچ — بردی! 🎉*\n\n"
                f"{item.get('emoji','📦')} *{item.get('name','—')}* حالا "
                f"{bz_to_display(item['sell'])} می‌ارزه (قبلاً {bz_to_display(old_sell)})."
            )
        except Exception:
            pass
    else:
        lost_item = inv.pop(idx)
        await asave_player(uid, player)
        log_sync(
            f"🎲 **LOOT GAMBLE — LOSS**\n"
            f"👤 {player.get('name','—')} (`{uid}`)\n"
            f"📦 آیتم از دست رفته: {lost_item.get('name','—')}",
            "LOOT"
        )
        await cb.answer("💔 باختی!", show_alert=False)
        try:
            await cb.message.answer(
                f"📰 *دابل یا هیچ — باختی! 💔*\n\n"
                f"{lost_item.get('emoji','📦')} *{lost_item.get('name','—')}* رو از دست دادی..."
            )
        except Exception:
            pass

async def cb_loot_again(cb: CallbackQuery):
    uid = cb.from_user.id
    s = get_ls(uid)
    now = time.time()
    if s["actions"] <= 0:
        rem = int(s["reset_at"] - now)
        await cb.answer(f"⚡ اقداماتت تموم شده! {rem//60}:{rem%60:02d} مانده", show_alert=True)
        return
    player = await aget_player(uid)
    await send_photo_or_text(
        cb.message, WORLD_MAP_IMAGE,
        f"🗺 **انتخاب مپ:**\n⚡ {action_bar(s['actions'])} ({s['actions']}/{MAX_ACTIONS})",
        reply_markup=map_select_kb(player.get("map") if player else None)
    )
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.answer()

# ─── Black Market ─────────────────────────────────────────────
BLACK_MARKET_IMAGE = "black_market.jpg"

async def bm_render(message, caption: str, reply_markup=None):
    try:
        await message.edit_caption(caption=caption, reply_markup=reply_markup)
    except Exception:
        try:
            await message.edit_text(caption, reply_markup=reply_markup)
        except Exception:
            pass

async def cmd_blackmarket(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    zen = player.get("zen", 0)
    
    log_sync(
        f"🖤 **BLACK MARKET OPEN**\n"
        f"👤 {player.get('name','—')} (`{uid}`)",
        "ECONOMY"
    )
    
    await send_photo_or_text(
        msg, BLACK_MARKET_IMAGE,
        f"🖤 **Abyssal Black Market**\n_Eternal Bazaar_\n\n"
        f"💰 موجودی: **{bz_to_display(zen)}**\n\n"
        f"⚠️ _دعوا ممنوع — نگهبان‌ها به Void تبعید می‌کنند!_\n\nچی می‌خوای؟",
        reply_markup=bm_main_kb()
    )

async def cb_bm_back(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    zen = player.get("zen", 0) if player else 0
    
    log_sync(
        f"🔙 **BLACK MARKET BACK**\n"
        f"👤 {player.get('name','—') if player else 'نامشخص'} (`{uid}`)",
        "ECONOMY"
    )
    
    await bm_render(
        cb.message,
        f"🖤 **Abyssal Black Market**\n_Eternal Bazaar_\n\n"
        f"💰 موجودی: **{bz_to_display(zen)}**\n\nچی می‌خوای؟",
        reply_markup=bm_main_kb()
    )
    await cb.answer()

# ─── BM Shop ─────────────────────────────────────────────────
def _market_discount_mult() -> float:
    """تکمیلِ ایونتِ روزانه‌ی «🛒 تخفیف بازار» — قبلاً فقط تو توضیحاتِ
    متنی بود و قیمتِ واقعی هیچ‌وقت تغییر نمی‌کرد. بازارِ سیاه همیشه در
    دسترسه (نیازی به سفر نداره)، پس این تخفیف با فعال‌بودنِ ایونت
    امروز اعمال می‌شه، نه با چکِ نقشه‌ی فعلیِ بازیکن.
    """
    from combat import get_today_event
    return 0.7 if get_today_event().get("bonus") == "market_discount" else 1.0


async def cb_bm_shop(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    zen = player.get("zen", 0) if player else 0
    items = get_market_items()
    spawned = maybe_spawn_random_event("blackmarket_shop")
    discount_mult = _market_discount_mult()

    lines = ["🛒 **فروشگاه اصلی**\n📊 _قیمت‌ها زنده‌ان — بر اساس عرضه/تقاضا نوسان می‌کنن_\n\n"]
    if spawned:
        lines.append(f"⚡ {spawned}\n")
    if discount_mult < 1.0:
        lines.append("🛒 **تخفیفِ ویژه‌ی امروز فعاله — ۳۰٪ روی همه‌چیز!**\n")
    for ev in get_active_events_display():
        lines.append(f"🔔 {ev}\n")
    lines.append("\n")

    buttons = []
    for i, item in enumerate(items):
        r = RARITY_E.get(item.get("rarity","common"), "⚪")
        buy_p, _, arrow, _ = get_dynamic_price("blackmarket_shop", item)
        buy_p = int(buy_p * discount_mult)
        lines.append(f"{item['emoji']} **{item['name']}** {r} {arrow} — {bz_to_display(buy_p)}\n")
        buttons.append([InlineKeyboardButton(
            text=f"{item['emoji']} خرید {item['name']} ({bz_to_display(buy_p)})",
            callback_data=f"bm_buy:{i}", style=ButtonStyle.SUCCESS)])
    lines.append(f"\n💰 موجودی: **{bz_to_display(zen)}**")
    buttons.append([InlineKeyboardButton(text="🔙 برگشت", callback_data="bm:back", style=ButtonStyle.PRIMARY)])
    buttons.append(home_button())
    await bm_render(cb.message, "".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await cb.answer()

async def cb_bm_buy(cb: CallbackQuery):
    uid = cb.from_user.id
    idx = int(cb.data.split(":")[1])
    items = get_market_items()
    player = await aget_player(uid)
    if not player or idx >= len(items):
        await cb.answer("❌ خطا!", show_alert=True)
        return
    if is_bankrupt(player):
        await cb.answer(BANKRUPTCY_MSG, show_alert=True)
        return
    item = items[idx]
    buy_p, _, _, _ = get_dynamic_price("blackmarket_shop", item)
    buy_p = int(buy_p * _market_discount_mult())
    bill = compute_buy_total(player, buy_p, "safe", "blackmarket_shop")
    if player.get("zen", 0) < bill["total"]:
        await cb.answer(f"❌ Zen کافی نداری!\n{bz_to_display(player['zen'])} / {bz_to_display(bill['total'])}", show_alert=True)
        return
    zen_before = player.get("zen", 0)
    player["zen"] -= bill["total"]
    player.setdefault("inventory", []).append(item.copy())
    add_reputation(player, 1)
    await asave_player(uid, player)
    register_trade("blackmarket_shop", item, "buy")
    deposit_tax_pool(bill["vat_amount"], uid)

    record_transaction(
        "bm_buy", uid, username=player.get("name"),
        item_name=item.get("name"), item_id=item.get("id"), rarity=item.get("rarity"),
        amount=bill["total"], fee=bill["vat_amount"],
        balance_before=zen_before, balance_after=player["zen"],
        note=f"idx={idx} discount_mult={_market_discount_mult()}",
    )

    log_sync(
        f"🛒 **BM BUY**\n"
        f"👤 {player.get('name','—')} (`{uid}`)\n"
        f"📦 آیتم: {item['name']}\n"
        f"💰 قیمت: {bz_to_display(bill['total'])}\n"
        f"📉 مالیات: {bz_to_display(bill['vat_amount'])}\n"
        f"💵 موجودی جدید: {bz_to_display(player['zen'])}",
        "ECONOMY"
    )

    vat_note = "" if bill["tax_free_event"] else f" (شامل {bz_to_display(bill['vat_amount'])} مالیات)"
    await cb.answer(
        f"✅ {item['name']} خریدی! -{bz_to_display(bill['total'])}{vat_note}\nموجودی: {bz_to_display(player['zen'])}",
        show_alert=True
    )

# ─── BM Spy ──────────────────────────────────────────────────
async def cb_bm_spy(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    zen = player.get("zen",0) if player else 0
    lines = ["🕵️ **تجهیزات جاسوسی — Kaelith**\n\n"]
    buttons = []
    for i, item in enumerate(SPY_ITEMS):
        r = RARITY_E.get(item["rarity"],"⚪")
        lines.append(f"{item['emoji']} **{item['name']}** {r}\n   {item['effect']} — {bz_to_display(item['cost'])}\n")
        buttons.append([InlineKeyboardButton(
            text=f"{item['emoji']} خرید {item['name']} ({bz_to_display(item['cost'])})",
            callback_data=f"bm_spy:{i}", style=ButtonStyle.SUCCESS)])
    lines.append(f"\n💰 موجودی: **{bz_to_display(zen)}**")
    buttons.append([InlineKeyboardButton(text="🔙 برگشت", callback_data="bm:back", style=ButtonStyle.PRIMARY)])
    buttons.append(home_button())
    await bm_render(cb.message, "".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await cb.answer()

async def cb_bm_spy_buy(cb: CallbackQuery):
    uid = cb.from_user.id
    idx = int(cb.data.split(":")[1])
    player = await aget_player(uid)
    if not player or idx >= len(SPY_ITEMS):
        await cb.answer("❌", show_alert=True)
        return
    item = SPY_ITEMS[idx]
    if player.get("zen",0) < item["cost"]:
        await cb.answer(f"❌ Zen کافی نداری!", show_alert=True)
        return
    zen_before = player.get("zen", 0)
    player["zen"] -= item["cost"]
    player.setdefault("inventory",[]).append({"name":item["name"],"emoji":item["emoji"],"type":"spy","effect":item["effect"],"sell":int(item["cost"]*0.5)})
    await asave_player(uid, player)

    record_transaction(
        "bm_spy_buy", uid, username=player.get("name"),
        item_name=item.get("name"), rarity=item.get("rarity"),
        amount=item["cost"], balance_before=zen_before, balance_after=player["zen"],
        note=f"idx={idx}",
    )
    
    log_sync(
        f"🕵️ **BM SPY BUY**\n"
        f"👤 {player.get('name','—')} (`{uid}`)\n"
        f"📦 آیتم: {item['name']}\n"
        f"💰 هزینه: {bz_to_display(item['cost'])}",
        "ECONOMY"
    )
    
    await cb.answer(f"✅ {item['name']} خریدی!", show_alert=True)

# ─── BM Market Favor (کوئست‌لاینِ بازار) ────────────────────────
async def _render_favor_panel(cb: CallbackQuery, player: dict):
    from market_questline import market_quest_progress, is_market_quest_ready, MARKET_SPECIAL_ITEMS

    progress = market_quest_progress(player)
    tokens = player.get("market_favor_tokens", 0)
    lines = [
        "🤝 **اعتمادِ بازار**\n"
        "_کوئست‌لاینِ تکرارشونده — هر بار کاملش کنی، یه نشانِ اعتماد می‌گیری_\n\n"
    ]
    for step in progress:
        mark = "✅" if step["done"] else "⬜"
        lines.append(f"{mark} {step['label']}: {step['have']}/{step['need']}\n")
    lines.append(f"\n🎫 نشانِ اعتماد: **{tokens}**\n")

    buttons = []
    if is_market_quest_ready(player):
        buttons.append([InlineKeyboardButton(text="🎁 دریافتِ نشانِ اعتماد", callback_data="bm_favor:claim", style=ButtonStyle.SUCCESS)])

    lines.append("\n🛍️ **آیتم‌های ویژه (فقط با نشانِ اعتماد):**\n")
    for iid, item in MARKET_SPECIAL_ITEMS.items():
        lines.append(f"{item['emoji']} **{item['name']}** — {item['cost_zen']:,} Zen + ۱ نشان\n   _{item['desc']}_\n")
        buttons.append([InlineKeyboardButton(
            text=f"{item['emoji']} خرید {item['name']}",
            callback_data=f"bm_favor:buy:{iid}", style=ButtonStyle.SUCCESS)])

    buttons.append([InlineKeyboardButton(text="🔙 برگشت", callback_data="bm:back", style=ButtonStyle.PRIMARY)])
    buttons.append(home_button())
    await bm_render(cb.message, "".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


async def cb_bm_favor(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    await _render_favor_panel(cb, player)
    await cb.answer()


async def cb_bm_favor_action(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    parts = cb.data.split(":")
    action = parts[1]

    from market_questline import claim_market_favor, buy_special_item

    if action == "claim":
        ok, msg_txt = claim_market_favor(player)
    elif action == "buy" and len(parts) > 2:
        ok, msg_txt = buy_special_item(player, parts[2])
        if ok:
            log_sync(
                f"🤝 **MARKET FAVOR BUY**\n👤 {player.get('name','—')} (`{uid}`)\n📦 {parts[2]}",
                "ECONOMY"
            )
    else:
        await cb.answer("❌", show_alert=True)
        return

    await asave_player(uid, player)
    await cb.answer(msg_txt, show_alert=True)
    await _render_favor_panel(cb, player)

# ─── BM Katana ───────────────────────────────────────────────
async def cb_bm_katana(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    char = ALL_CHARACTERS.get(player.get("character",""), {})
    katana = char.get("katana","کاتانا")
    lv = player.get("katana_level", 1)
    zen = player.get("zen",0)
    cur = KATANA_LEVELS.get(lv, KATANA_LEVELS[1])
    nxt = KATANA_LEVELS.get(lv+1)

    lines = [
        f"⚔️ **Katana Forge — Vax'ar**\n\n",
        f"🗡 **{katana}{cur['suffix']}**\n",
        f"📊 سطح: **{lv}** | رتبه: {cur['label']}\n",
        f"⚡ بونوس آسیب: **+{cur['dmg']}**\n",
        f"💰 موجودی: **{bz_to_display(zen)}**\n",
    ]
    buttons = []
    if nxt:
        lines.append(f"\n**ارتقای بعدی (Lv.{lv+1}):**\n")
        lines.append(f"🏷 {nxt['label']} | ⚡ +{nxt['dmg']} آسیب\n")
        lines.append(f"💰 هزینه: **{bz_to_display(nxt['cost'])}**")
        can = zen >= nxt["cost"]
        buttons.append([InlineKeyboardButton(
            text=f"{'⬆️' if can else '❌'} ارتقا به Lv.{lv+1} ({bz_to_display(nxt['cost'])})",
            callback_data=f"bm_katana_up:{lv}" if can else "bm:noop", style=ButtonStyle.SUCCESS)])
    else:
        lines.append("\n✅ **حداکثر سطح رسیدی!**")
    buttons.append([InlineKeyboardButton(text="🔙 برگشت", callback_data="bm:back", style=ButtonStyle.PRIMARY)])
    buttons.append(home_button())
    await bm_render(cb.message, "".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await cb.answer()

async def cb_bm_katana_up(cb: CallbackQuery):
    uid = cb.from_user.id
    lv = int(cb.data.split(":")[1])
    player = await aget_player(uid)
    if not player: return
    nxt = KATANA_LEVELS.get(lv+1)
    if not nxt or player.get("zen",0) < nxt["cost"]:
        await cb.answer("❌ Zen کافی نداری!", show_alert=True)
        return
    zen_before = player.get("zen", 0)
    player["zen"] -= nxt["cost"]
    player["katana_level"] = lv+1
    await asave_player(uid, player)

    record_transaction(
        "bm_katana_up", uid, username=player.get("name"),
        item_name=f"katana_lv{lv+1}",
        amount=nxt["cost"], balance_before=zen_before, balance_after=player["zen"],
        note=f"level {lv} -> {lv+1}",
    )
    
    log_sync(
        f"🔨 **KATANA UPGRADE (BM)**\n"
        f"👤 {player.get('name','—')} (`{uid}`)\n"
        f"📊 سطح: {lv} → {lv+1}\n"
        f"💰 هزینه: {bz_to_display(nxt['cost'])}",
        "CRAFT"
    )
    
    await cb.answer(f"⬆️ کاتانا به Lv.{lv+1} ارتقا یافت! +{nxt['dmg']} آسیب", show_alert=True)
    await cb_bm_katana(cb)

# ─── BM Defense ──────────────────────────────────────────────
async def cb_bm_defense(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    zen = player.get("zen",0) if player else 0
    lines = ["🏰 **دفاع پایگاه — The Warden**\n\n"]
    buttons = []
    if zen < 50000:
        lines.append(f"⚠️ _The Warden فقط با کسانی حرف می‌زنه که بیش از {bz_to_display(50000)} دارن!_\n")
        lines.append(f"💰 موجودی تو: **{bz_to_display(zen)}**")
    else:
        lines.append("_بعد از خرید، برای فعال‌سازیِ واقعی برو 🏠 /house ›› 🪤 مدیریتِ تله‌ها و نصبشون کن._\n")
        for i, item in enumerate(DEFENSE_ITEMS):
            cost_bz = item["cost_sz"] * BZ_PER_SZ
            r = RARITY_E.get(item["rarity"],"⚪")
            lines.append(f"{item['emoji']} **{item['name']}** {r}\n   {item['effect']} — {bz_to_display(cost_bz)}\n")
            buttons.append([InlineKeyboardButton(
                text=f"{item['emoji']} خرید {item['name']}",
                callback_data=f"bm_def:{i}", style=ButtonStyle.SUCCESS)])
        lines.append(f"\n💰 موجودی: **{bz_to_display(zen)}**")
    buttons.append([InlineKeyboardButton(text="🔙 برگشت", callback_data="bm:back", style=ButtonStyle.PRIMARY)])
    buttons.append(home_button())
    await bm_render(cb.message, "".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await cb.answer()

async def cb_bm_def_buy(cb: CallbackQuery):
    uid = cb.from_user.id
    idx = int(cb.data.split(":")[1])
    player = await aget_player(uid)
    if not player or idx >= len(DEFENSE_ITEMS):
        await cb.answer("❌", show_alert=True)
        return
    item = DEFENSE_ITEMS[idx]
    cost = item["cost_sz"] * BZ_PER_SZ
    if player.get("zen",0) < cost:
        await cb.answer("❌ Zen کافی نداری!", show_alert=True)
        return
    zen_before = player.get("zen", 0)
    player["zen"] -= cost
    player.setdefault("inventory",[]).append({"name":item["name"],"emoji":item["emoji"],"type":"defense","effect":item["effect"],"sell":int(cost*0.4)})
    await asave_player(uid, player)

    record_transaction(
        "bm_def_buy", uid, username=player.get("name"),
        item_name=item.get("name"), rarity=item.get("rarity"),
        amount=cost, balance_before=zen_before, balance_after=player["zen"],
        note=f"idx={idx}",
    )
    
    log_sync(
        f"🏰 **BM DEFENSE BUY**\n"
        f"👤 {player.get('name','—')} (`{uid}`)\n"
        f"📦 آیتم: {item['name']}\n"
        f"💰 هزینه: {bz_to_display(cost)}",
        "ECONOMY"
    )
    
    await cb.answer(f"✅ {item['name']} خریدی!", show_alert=True)

# ─── BM Auction ──────────────────────────────────────────────
async def cb_bm_auction(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    zen = player.get("zen",0) if player else 0
    lines = ["💎 **حراجی سایه — Shadow Brokers**\n\n"]
    buttons = []
    for i, item in enumerate(SHADOW_AUCTION):
        price_txt = bz_to_display(item["cost"]) if item["cost"] else "قیمت متغیر"
        lines.append(f"{item['emoji']} **{item['name']}** 🟡\n   {item['effect']}\n   💰 {price_txt}\n\n")
        if item["cost"]:
            buttons.append([InlineKeyboardButton(
                text=f"{item['emoji']} خرید {item['name']} ({price_txt})",
                callback_data=f"bm_auction_buy:{i}", style=ButtonStyle.SUCCESS)])
    lines.append(f"💰 موجودی: **{bz_to_display(zen)}**")
    buttons.append([InlineKeyboardButton(text="🔙 برگشت", callback_data="bm:back", style=ButtonStyle.PRIMARY)])
    buttons.append(home_button())
    await bm_render(cb.message, "".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await cb.answer()

async def cb_bm_auction_buy(cb: CallbackQuery):
    uid = cb.from_user.id
    idx = int(cb.data.split(":")[1])
    player = await aget_player(uid)
    if not player or idx >= len(SHADOW_AUCTION):
        await cb.answer("❌", show_alert=True)
        return
    item = SHADOW_AUCTION[idx]
    cost = item.get("cost", 0)
    if not cost:
        await cb.answer("❌ این آیتم فقط از طریق رویداد خاص در دسترسه!", show_alert=True)
        return
    if player.get("zen",0) < cost:
        await cb.answer(f"❌ Zen کافی نداری! {bz_to_display(player['zen'])} / {bz_to_display(cost)}", show_alert=True)
        return
    zen_before = player.get("zen", 0)
    player["zen"] -= cost
    player.setdefault("inventory",[]).append({"name":item["name"],"emoji":item["emoji"],"type":"legendary","effect":item["effect"],"sell":int(cost*0.7)})
    await asave_player(uid, player)

    record_transaction(
        "bm_shadow_auction_buy", uid, username=player.get("name"),
        item_name=item.get("name"),
        amount=cost, balance_before=zen_before, balance_after=player["zen"],
        note=f"idx={idx}",
    )
    
    log_sync(
        f"💎 **BM AUCTION BUY**\n"
        f"👤 {player.get('name','—')} (`{uid}`)\n"
        f"📦 آیتم: {item['name']}\n"
        f"💰 هزینه: {bz_to_display(cost)}",
        "ECONOMY"
    )
    
    await cb.answer(f"✅ {item['name']} خریدی!", show_alert=True)

async def cb_bm_market_overview(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    items = get_market_items()
    overview = get_market_overview("blackmarket_shop", items)
    rep = player.get("bm_reputation", 0)
    disc = int(get_reputation_discount(player) * 100)

    lines = ["📊 **وضعیت بازار — Abyssal Black Market**\n\n"]

    events = get_active_events_display()
    if events:
        lines.append("🔔 **رویدادهای فعال:**\n")
        for ev in events:
            lines.append(f"  • {ev}\n")
        lines.append("\n")
    else:
        lines.append("🔕 هیچ رویداد اقتصادی فعالی نیست.\n\n")

    if overview["gainers"]:
        lines.append("📈 **بیشترین رشد قیمت:**\n")
        for r in overview["gainers"]:
            lines.append(f"  {r['emoji']} {r['name']} — ×{r['mult']} ({bz_to_display(r['buy'])})\n")
        lines.append("\n")

    if overview["losers"]:
        lines.append("📉 **بیشترین کاهش قیمت:**\n")
        for r in overview["losers"]:
            lines.append(f"  {r['emoji']} {r['name']} — ×{r['mult']} ({bz_to_display(r['buy'])})\n")
        lines.append("\n")

    lines.append(f"🏦 صندوق مالیات سراسری: **{bz_to_display(get_tax_pool())}**\n")
    lines.append(f"🎫 رپیوتیشن بازار سیاه‌ات: **{rep}/100** (تخفیف مالیات: {disc}٪)\n")
    lines.append("\n_رپیوتیشن با هر خرید و فروش کم‌کم بالا می‌ره._")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 برگشت", callback_data="bm:back", style=ButtonStyle.PRIMARY)],
        home_button(),
    ])
    await bm_render(cb.message, "".join(lines), reply_markup=kb)
    await cb.answer()

# ─── BM Sell ─────────────────────────────────────────────────
async def cb_bm_sell(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    inv = player.get("inventory",[])
    if not inv:
        await cb.answer("🎒 کوله‌پشتیت خالیه!", show_alert=True)
        return

    gross_total = 0
    lines = ["💰 **فروش آیتم‌ها — Vax'ar**\n📊 _قیمت‌ها زنده‌ان_\n\n"]
    item_list = []
    sellable = [it for it in inv if not it.get("shop_exclusive")]
    if len(inv) != len(sellable):
        lines.append("🔒 _آیتم‌های ویژه‌ی بازار (نشان‌دار) اینجا قابلِ فروش نیستن — فقط تو مغازه‌ی خودت._\n\n")
    for item in sellable[:12]:
        _, sell_p, arrow, _ = get_dynamic_price("global_loot", item)
        gross_total += sell_p
        item_list.append(f"{item.get('emoji','📦')} {item['name']} {arrow} → {bz_to_display(sell_p)}")
        lines.append(f"{item_list[-1]}\n")
    if len(sellable) > 12:
        for item in sellable[12:]:
            _, sell_p, _, _ = get_dynamic_price("global_loot", item)
            gross_total += sell_p
        lines.append(f"... و {len(sellable)-12} آیتم دیگه\n")

    tax = compute_sell_tax(player, gross_total, "safe", "blackmarket_shop")
    disc = int(get_reputation_discount(player) * 100)
    lines.append(f"\n💰 فروش خام: **{bz_to_display(gross_total)}**")
    if tax["tax_free_event"]:
        lines.append("\n🎉 معاف از مالیات (ایونت فعال)")
    else:
        lines.append(f"\n📉 مالیات تخمینی ({tax['tax_rate']*100:.1f}٪ — رپیوتیشن {disc}٪ تخفیف): -{bz_to_display(tax['tax_amount'])}")
    lines.append(f"\n💵 دریافتی خالص تخمینی: **{bz_to_display(tax['net'])}**")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 فروش همه (~{bz_to_display(tax['net'])})", callback_data="bm_sell_all", style=ButtonStyle.DANGER)],
        [InlineKeyboardButton(text="🔙 برگشت", callback_data="bm:back", style=ButtonStyle.PRIMARY)],
        home_button(),
    ])
    await bm_render(cb.message, "".join(lines), reply_markup=kb)
    await cb.answer()

async def cb_bm_sell_all(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    inv = player.get("inventory",[])
    if not inv:
        await cb.answer("🎒 کوله‌پشتیت خالیه!", show_alert=True)
        return

    sellable = [it for it in inv if not it.get("shop_exclusive")]
    if not sellable:
        await cb.answer("🔒 همه‌ی آیتم‌هات ویژه‌ن — فقط تو مغازه‌ی خودت قابلِ فروشن!", show_alert=True)
        return

    gross_total = 0
    sold_items = []
    for item in sellable:
        _, sell_p, _, _ = get_dynamic_price("global_loot", item)
        gross_total += sell_p
        register_trade("global_loot", item, "sell")
        sold_items.append(f"{item.get('emoji','📦')} {item.get('name','—')} ({item.get('rarity','common')}) — {bz_to_display(sell_p)}")

    tax = compute_sell_tax(player, gross_total, "safe", "blackmarket_shop")
    zen_before = player.get("zen", 0)
    kept = [it for it in inv if it.get("shop_exclusive")]
    player["inventory"] = kept
    player["zen"] = player.get("zen", 0) + tax["net"]
    add_reputation(player, min(3, len(sellable)))
    await asave_player(uid, player)
    deposit_tax_pool(tax["tax_amount"], uid)

    record_transaction(
        "bm_sell_all", uid, username=player.get("name"),
        item_name=f"{len(sellable)} آیتم", quantity=len(sellable),
        amount=gross_total, fee=tax["tax_amount"],
        balance_before=zen_before, balance_after=player["zen"],
        extra={"items": sold_items},
    )

    log_sync(
        f"💰 **BM SELL ALL (DETAILED)**\n"
        f"👤 {player.get('name','—')} (`{uid}`)\n"
        f"📦 تعداد آیتم‌ها: {len(sellable)}\n"
        f"{'─'*20}\n"
        f"📋 **لیست آیتم‌های فروخته‌شده:**\n" + ("\n".join(f"  • {it}" for it in sold_items) if sold_items else "  • هیچی\n") +
        f"{'─'*20}\n"
        f"💰 مبلغ خام: {bz_to_display(gross_total)}\n"
        f"📉 مالیات ({tax['tax_rate']*100:.1f}٪): {bz_to_display(tax['tax_amount'])}\n"
        f"💵 دریافتی خالص: {bz_to_display(tax['net'])}\n"
        f"🏦 موجودی جدید: {bz_to_display(player['zen'])}",
        "ECONOMY"
    )

    tax_note = ("🎉 معاف از مالیات!" if tax["tax_free_event"]
                else f"📉 مالیات ({tax['tax_rate']*100:.1f}٪): -{bz_to_display(tax['tax_amount'])}")
    await cb.answer(f"💰 {bz_to_display(tax['net'])} گرفتی!", show_alert=True)
    await bm_render(
        cb.message,
        f"💰 **همه فروخته شد!**\n\n"
        f"فروش خام: **{bz_to_display(gross_total)}**\n"
        f"{tax_note}\n"
        f"دریافتی خالص: **{bz_to_display(tax['net'])}**\n"
        f"موجودی: **{bz_to_display(player['zen'])}**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 برگشت", callback_data="bm:back", style=ButtonStyle.PRIMARY)], home_button()])
    )

# ─── BM Vault (Lockboxes + Keys + Fortune Ward) ───────────────
async def cb_bm_vault(cb: CallbackQuery):
    from loot_engine import LOCKBOXES, KEYS, FORTUNE_WARD_PRICE
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    inv = player.get("inventory", [])
    boxes = [(i, it) for i, it in enumerate(inv) if it.get("type") == "lockbox"]
    keys  = [(i, it) for i, it in enumerate(inv) if it.get("type") == "key"]
    key_counts: dict[str, int] = {}
    for _, it in keys:
        key_counts[it["key_id"]] = key_counts.get(it["key_id"], 0) + 1

    lines = ["🗝️ **صندوق‌ها و کلیدها — Vax'ar Vault**\n\n"]
    buttons = []

    if not boxes:
        lines.append("📦 صندوقی نداری. حین لوت کردن یا کشتن باس‌ها دنبالشون بگرد!\n\n")
    else:
        lines.append(f"📦 **صندوق‌های تو ({len(boxes)}):**\n")
        for i, it in boxes[:8]:
            box_id = it.get("box_id")
            need_key = LOCKBOXES.get(box_id, {}).get("key")
            have = key_counts.get(need_key, 0)
            status = "✅ کلید داری" if have > 0 else "❌ کلید نداری"
            lines.append(f"{it['emoji']} **{it['name']}** — {status}\n")
            if have > 0:
                buttons.append([InlineKeyboardButton(text=f"🔓 باز کردن {it['name']}", callback_data=f"lbx_open:{i}", style=ButtonStyle.SUCCESS)])
        lines.append("\n")

    lines.append("🔑 **خرید کلید:**\n")
    for kid, k in KEYS.items():
        lines.append(f"{k['emoji']} {k['name']} — {bz_to_display(k['buy_price'])}\n")
        buttons.append([InlineKeyboardButton(text=f"خرید {k['emoji']} {k['name']}", callback_data=f"buy_key:{kid}", style=ButtonStyle.SUCCESS)])

    ward_count = player.get("fortune_ward_count", 0)
    lines.append(
        f"\n🍀 **طلسم شانس** — یه بار جلوی از دست رفتن استریک لوتت (مرگ/فرار) رو می‌گیره.\n"
        f"موجودی: {ward_count} عدد\n"
    )
    buttons.append([InlineKeyboardButton(text=f"🍀 خرید طلسم شانس ({bz_to_display(FORTUNE_WARD_PRICE)})", callback_data="buy_ward", style=ButtonStyle.SUCCESS)])

    lines.append(f"\n💰 موجودی: **{bz_to_display(player.get('zen', 0))}**")
    buttons.append([InlineKeyboardButton(text="🔙 برگشت", callback_data="bm:back", style=ButtonStyle.PRIMARY)])
    buttons.append(home_button())
    await bm_render(cb.message, "".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await cb.answer()

async def cb_lbx_open(cb: CallbackQuery):
    from loot_engine import LOCKBOXES, open_lockbox
    uid = cb.from_user.id
    try:
        idx = int(cb.data.split(":")[1])
    except Exception:
        await cb.answer("❌", show_alert=True)
        return
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    inv = player.get("inventory", [])
    if idx >= len(inv) or inv[idx].get("type") != "lockbox":
        await cb.answer("❌ این صندوق دیگه وجود نداره!", show_alert=True)
        return

    box_item = inv[idx]
    box_id = box_item["box_id"]
    need_key = LOCKBOXES[box_id]["key"]
    key_idx = next((i for i, it in enumerate(inv) if it.get("type") == "key" and it.get("key_id") == need_key), None)
    if key_idx is None:
        await cb.answer("❌ کلید مناسب این صندوق رو نداری!", show_alert=True)
        return

    results = open_lockbox(player, player.get("map"), box_id)
    for i in sorted([idx, key_idx], reverse=True):
        inv.pop(i)
    
    loot_items = []
    for r in results:
        if "set_id" not in r:
            inv.append(r)
            loot_items.append(f"{r.get('emoji','📦')} {r.get('name','—')} ({r.get('rarity','common')}) — {bz_to_display(r.get('sell',0))}")
    
    await asave_player(uid, player)

    log_sync(
        f"🔓 **LOCKBOX OPEN (DETAILED)**\n"
        f"👤 {player.get('name','—')} (`{uid}`)\n"
        f"📦 صندوق: {box_item['name']}\n"
        f"🎁 تعداد آیتم‌ها: {len(results)}\n"
        f"{'─'*20}\n"
        f"📋 **آیتم‌های داخل صندوق:**\n" + ("\n".join(f"  • {it}" for it in loot_items) if loot_items else "  • خالی بود!\n") +
        f"{'─'*20}\n"
        f"💰 کل ارزش: {bz_to_display(sum(r.get('sell',0) for r in results))}",
        "LOOT"
    )

    lines = [f"🔓 **{box_item['name']} باز شد!**\n\n"]
    if not results:
        lines.append("... عجیبه، خالی بود!\n")
    for r in results:
        if "set_id" in r:
            lines.append(f"🧩 قطعه‌ی ست: {r['emoji']} **{r['name']}** ({r['set_display']})\n")
        else:
            lines.append(f"{r['emoji']} **{r['name']}** ({r.get('rarity','rare')}) — {bz_to_display(r.get('sell',0))}\n")

    await cb.answer("🔓 صندوق باز شد!", show_alert=False)
    await bm_render(cb.message, "".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 برگشت به صندوق‌ها", callback_data="bm:vault", style=ButtonStyle.PRIMARY)],
        home_button(),
    ]))

async def cb_buy_key(cb: CallbackQuery):
    from loot_engine import KEYS
    uid = cb.from_user.id
    kid = cb.data.split(":", 1)[1]
    player = await aget_player(uid)
    if not player or kid not in KEYS:
        await cb.answer("❌", show_alert=True)
        return
    k = KEYS[kid]
    if player.get("zen", 0) < k["buy_price"]:
        await cb.answer("❌ Zen کافی نداری!", show_alert=True)
        return
    zen_before = player.get("zen", 0)
    player["zen"] -= k["buy_price"]
    player.setdefault("inventory", []).append(
        {"name": k["name"], "emoji": k["emoji"], "type": "key", "key_id": kid, "sell": int(k["buy_price"] * 0.3)}
    )
    await asave_player(uid, player)

    record_transaction(
        "bm_key_buy", uid, username=player.get("name"),
        item_name=k.get("name"), item_id=kid,
        amount=k["buy_price"], balance_before=zen_before, balance_after=player["zen"],
    )
    
    log_sync(
        f"🔑 **KEY BUY**\n"
        f"👤 {player.get('name','—')} (`{uid}`)\n"
        f"📦 کلید: {k['name']}\n"
        f"💰 هزینه: {bz_to_display(k['buy_price'])}",
        "ECONOMY"
    )
    
    await cb.answer(f"✅ {k['name']} خریدی!", show_alert=True)

async def cb_buy_ward(cb: CallbackQuery):
    from loot_engine import FORTUNE_WARD_PRICE
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    if player.get("zen", 0) < FORTUNE_WARD_PRICE:
        await cb.answer("❌ Zen کافی نداری!", show_alert=True)
        return
    zen_before = player.get("zen", 0)
    player["zen"] -= FORTUNE_WARD_PRICE
    player["fortune_ward_count"] = player.get("fortune_ward_count", 0) + 1
    await asave_player(uid, player)

    record_transaction(
        "bm_ward_buy", uid, username=player.get("name"),
        item_name="fortune_ward",
        amount=FORTUNE_WARD_PRICE, balance_before=zen_before, balance_after=player["zen"],
    )
    
    log_sync(
        f"🍀 **FORTUNE WARD BUY**\n"
        f"👤 {player.get('name','—')} (`{uid}`)\n"
        f"📦 تعداد: {player['fortune_ward_count']}\n"
        f"💰 هزینه: {bz_to_display(FORTUNE_WARD_PRICE)}",
        "ECONOMY"
    )
    
    await cb.answer("🍀 طلسم شانس خریدی! دفعه‌ی بعد که بمیری یا فرار کنی، استریکت حفظ می‌مونه.", show_alert=True)

# ─── BM Set Collection ─────────────────────────────────────────
async def cb_bm_sets(cb: CallbackQuery):
    from loot_engine import get_owned_set_summary
    uid = cb.from_user.id
    player = await aget_player(uid)
    lines = ["🧩 **مجموعه‌های ست تو**\n\n"]
    summary = get_owned_set_summary(player) if player else []
    if not summary:
        lines.append("هنوز هیچ قطعه‌ی ستی پیدا نکردی.\nتو نقشه‌های خطرناک (Voidbreak, Frostheim, Dragonnest, ...) دنبالشون بگرد!")
    else:
        lines += [s + "\n" for s in summary]
    await bm_render(cb.message, "".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 برگشت", callback_data="bm:back", style=ButtonStyle.PRIMARY)],
        home_button(),
    ]))
    await cb.answer()

async def cb_noop(cb: CallbackQuery):
    await cb.answer()

async def cb_menu_home(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    name = player.get("name", "جنگجو") if player else "جنگجو"

    log_sync(
        f"🏠 **MENU HOME**\n"
        f"👤 {name} (`{uid}`)",
        "INFO"
    )

    # به‌جای ادیت کردن پیام به یه متنِ «برگشتی»، پنل رو کامل حذف می‌کنیم —
    # هم گپ تمیزتر می‌مونه، هم دیگه پیامِ نیمه‌بازِ قدیمی رو نمی‌بینی.
    try:
        await cb.message.delete()
    except Exception:
        # اگه پیام قدیمی‌تر از ۴۸ ساعت باشه یا از قبل حذف شده، تلگرام
        # اجازه‌ی حذف نمی‌ده — تو اون حالت فقط دکمه‌ها رو برمی‌داریم.
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    await cb.answer("🌑 برگشتی به پنل اصلی — از دکمه‌های پایین صفحه استفاده کن.")
    await cb.answer()

# ─── Register ────────────────────────────────────────────────
def register_loot_handlers(dp: Dispatcher, bot: Bot):
    from raid_handlers import register_raid_handlers
    register_raid_handlers(dp)

    from black_market_expansion_handlers import register_black_market_expansion_handlers
    register_black_market_expansion_handlers(dp, bot)

    # عمداً قبل از ثبتِ bm:katana/bm:spy قدیمیِ پایین صدا زده می‌شه تا override بشن
    from black_market_katana_spy_handlers import register_bm_katana_spy_handlers
    register_bm_katana_spy_handlers(dp, bot)

    # عمداً قبل از ثبتِ bm:auction قدیمیِ پایین صدا زده می‌شه تا override بشه
    from black_market_shadow_handlers import register_black_market_shadow_handlers
    register_black_market_shadow_handlers(dp, bot)

    from mob_combat import register_mob_combat_handlers
    register_mob_combat_handlers(dp)

    dp.message.register(cmd_loot,        Command("loot"))
    dp.message.register(cmd_blackmarket, Command("blackmarket"))

    async def _cb_loot_go(c: CallbackQuery):
        await cb_loot_go(c, bot)
    dp.callback_query.register(_cb_loot_go, F.data.startswith("lg:"))

    async def _cb_loot_location(c: CallbackQuery):
        await cb_loot_location(c, bot)
    dp.callback_query.register(_cb_loot_location, F.data.startswith("loc:"))
    dp.callback_query.register(cb_boss_challenge, F.data.startswith("bossch:"))

    dp.callback_query.register(cb_loot_cancel,   F.data == "loot:cancel")
    dp.callback_query.register(cb_loot_sell_all, F.data == "loot:sell_all")
    dp.callback_query.register(cb_loot_keep,     F.data == "loot:keep")
    dp.callback_query.register(cb_loot_again,    F.data == "loot:again")
    dp.callback_query.register(cb_loot_gamble,   F.data.startswith("loot:gamble:"))

    dp.callback_query.register(cb_bm_back,        F.data == "bm:back")
    dp.callback_query.register(cb_bm_shop,        F.data == "bm:shop")
    dp.callback_query.register(cb_bm_spy,         F.data == "bm:spy")
    dp.callback_query.register(cb_bm_favor,       F.data == "bm:favor")
    dp.callback_query.register(cb_bm_katana,      F.data == "bm:katana")
    dp.callback_query.register(cb_bm_defense,     F.data == "bm:defense")
    dp.callback_query.register(cb_bm_auction,     F.data == "bm:auction")
    dp.callback_query.register(cb_bm_sell,        F.data == "bm:sell")
    dp.callback_query.register(cb_bm_market_overview, F.data == "bm:market")
    dp.callback_query.register(cb_bm_vault,       F.data == "bm:vault")
    dp.callback_query.register(cb_bm_sets,        F.data == "bm:sets")
    dp.callback_query.register(cb_noop,           F.data == "bm:noop")
    dp.callback_query.register(cb_menu_home,      F.data == "menu:home")

    dp.callback_query.register(cb_bm_buy,         F.data.startswith("bm_buy:"))
    dp.callback_query.register(cb_bm_spy_buy,     F.data.startswith("bm_spy:"))
    dp.callback_query.register(cb_bm_favor_action, F.data.startswith("bm_favor:"))
    dp.callback_query.register(cb_bm_katana_up,   F.data.startswith("bm_katana_up:"))
    dp.callback_query.register(cb_bm_def_buy,     F.data.startswith("bm_def:"))
    dp.callback_query.register(cb_bm_auction_buy, F.data.startswith("bm_auction_buy:"))
    dp.callback_query.register(cb_bm_sell_all,    F.data == "bm_sell_all")
    dp.callback_query.register(cb_lbx_open,       F.data.startswith("lbx_open:"))
    dp.callback_query.register(cb_buy_key,        F.data.startswith("buy_key:"))
    dp.callback_query.register(cb_buy_ward,       F.data == "buy_ward")
