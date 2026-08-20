# ============================================================
#  ASTRAL ABYSS RPG — Database (MongoDB)
# ============================================================
import os
import random
import asyncio
from typing import Optional
from pymongo import MongoClient
from pymongo.collection import Collection

MONGODB_URL = os.getenv("MONGODB_URL", "")

_client = None
_db = None

def get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(
            MONGODB_URL,
            maxPoolSize=50,
            connectTimeoutMS=5000,
            serverSelectionTimeoutMS=5000,
            socketTimeoutMS=10000,
        )
        _db = _client["astral_abyss"]
    return _db

def players_col() -> Collection:
    return get_db()["players"]

def account_links_col() -> Collection:
    """
    نگاشتِ «الیاس → اصلی» برای سیستمِ اتصالِ حساب (account_link.py).
    هر سند: {_id: alias_uid, primary: primary_uid, linked_at: ts}
    یعنی: هر وقت کسی با alias_uid وارد شد، باید بره سراغِ primary_uid.
    (نگاه کن به resolve_uid پایین‌تر — همه‌جا همینو صدا می‌زنه.)
    """
    return get_db()["account_links"]

def link_codes_col() -> Collection:
    """کدهای موقتِ اتصالِ حساب (account_link.py) — هر سند: {_id: code, primary, expires_at, used}."""
    return get_db()["link_codes"]

def resolve_uid(user_id: int) -> int:
    """
    اگه این uid قبلاً (از طریقِ account_link.py) به یه uid دیگه وصل شده
    باشه (مثلاً یه پلیر که هم تلگرام هم گپ بازی می‌کنه و حساب‌هاشو به‌هم
    وصل کرده)، uidِ اصلی (primary) رو برمی‌گردونه؛ وگرنه خودِ user_id.

    این تابع تویِ get_player/save_player صدا زده می‌شه، پس ۱۴۴ فایلِ
    دیگه‌ی کدبیس که database.get_player(uid)/save_player(uid,...) رو
    صدا می‌زنن، بدونِ هیچ تغییری، خودکار روی حسابِ اصلی کار می‌کنن.
    """
    link = account_links_col().find_one({"_id": user_id})
    return link["primary"] if link else user_id


# ============================================================
#  رفعِ RACE CONDITION روی save_player
# ------------------------------------------------------------
#  مشکل قبلی: هر هندلر جداگونه get_player → mutate → save_player رو
#  انجام می‌داد، بدون هیچ قفلی. save_player هم فقط یه $set خامِ کلِ
#  سندِ درحافظه بود. یعنی اگه دو تا اکشنِ هم‌زمان (مثلاً حمله + خرید
#  از مغازه، یا دو تا انتقالِ بانکیِ همزمان روی یه گیرنده) رخ می‌داد:
#  هر دو از رویِ یه نسخه‌ی قدیمیِ مشترک می‌خوندن، و هرکدوم که آخر
#  save می‌کرد، تغییراتِ اون‌یکی رو کامل پاک می‌کرد (Lost Update) —
#  مثلاً Zen/آیتمی که همزمان اضافه شده بود، گم می‌شد.
#
#  راه‌حل، دو لایه:
#
#  ۱) player_lock(uid) — قفلِ asyncio.Lock سراسری به‌ازای هر uid.
#     هر بلاکِ «بخون → تغییر بده → ذخیره کن» که برای یه بازیکن اجرا
#     می‌شه باید کاملاً داخلِ این قفل باشه (نه فقط خودِ save_player)،
#     چون خودِ race تو فاصله‌ی خوندن تا نوشتن اتفاق می‌افته، نه لحظه‌ی
#     نوشتن. این قفل reentrant نیست — پس هیچ‌وقت داخلِ یه بلاکِ
#     player_lock(uid) دوباره برای همون uid قفل نگیر (دِدلاک می‌شه).
#     برای عملیاتِ دوطرفه (مثلِ انتقالِ بانکی بینِ دو بازیکن) همیشه
#     قفل‌ها رو به‌ترتیبِ ثابت (مثلاً sorted بر اساسِ uid) بگیر تا
#     دِدلاکِ کلاسیکِ «قفلِ متقاطع» رخ نده.
#
#  ۲) نسخه‌گذاریِ خوش‌بینانه (Optimistic Concurrency) داخلِ خودِ
#     save_player — به‌عنوانِ خط دفاعیِ دوم، برای اون صدها جای دیگه‌ی
#     کدبیس که هنوز داخلِ player_lock پوشیده نشدن. هر سندِ بازیکن یه
#     فیلدِ داخلیِ "_v" داره. save_player فقط وقتی می‌نویسه که "_v"ِ
#     سندِ فعلیِ دیتابیس با "_v"ِ نسخه‌ای که موقعِ get_player خونده
#     بودی یکی باشه (شرطِ atomic تو خودِ ایندکسِ Mongo، نه تو پایتون).
#     اگه یکی نبود یعنی یه نوشتنِ دیگه بینِ خوندن و نوشتنِ تو فاصله
#     افتاده — یه هشدارِ بلند تو لاگ می‌ره (که بفهمیم کدوم مسیر هنوز
#     زیرِ player_lock نرفته) و بازم می‌نویسه تا دیتای بازیکن گم نشه،
#     ولی این حالت دیگه نباید تو مسیرهایی که به player_lock مهاجرت
#     کردن پیش بیاد.
# ============================================================
_player_locks: dict[int, asyncio.Lock] = {}


def _get_player_lock(user_id: int) -> asyncio.Lock:
    lock = _player_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _player_locks[user_id] = lock
    return lock


class player_lock:
    """
    Async context manager: کلِ بلاکِ get_player→mutate→save_player رو
    براش بذار تا هیچ اکشنِ دیگه‌ای (تو همین پروسه) نتونه هم‌زمان روی
    همین بازیکن بنویسه.

        async with player_lock(uid):
            p = get_player(uid)
            p["zen"] += 100
            save_player(uid, p)

    برای عملیاتِ دوطرفه (دو uid)، از player_lock_pair استفاده کن که
    خودش ترتیبِ گرفتنِ قفل‌ها رو مدیریت می‌کنه.
    """
    def __init__(self, user_id: int):
        self.user_id = user_id
        self._lock = _get_player_lock(user_id)

    async def __aenter__(self):
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._lock.release()
        return False


class player_lock_pair:
    """
    قفلِ هم‌زمانِ دو بازیکن (مثلاً انتقالِ بانکی/تریدِ مستقیم بینِ دو
    نفر) — همیشه قفل‌ها رو به‌ترتیبِ عددیِ uid می‌گیره (نه به ترتیبِ
    sender/target) تا اگه دو تا انتقالِ هم‌زمانِ متقاطع اتفاق بیفته
    (A→B و هم‌زمان B→A) هیچ‌وقت دِدلاک نشه.

        async with player_lock_pair(uid1, uid2):
            a = get_player(uid1); b = get_player(uid2)
            ...
            save_player(uid1, a); save_player(uid2, b)
    """
    def __init__(self, uid_a: int, uid_b: int):
        lo, hi = sorted((uid_a, uid_b))
        self._lock_lo = _get_player_lock(lo)
        self._lock_hi = _get_player_lock(hi) if hi != lo else None

    async def __aenter__(self):
        await self._lock_lo.acquire()
        if self._lock_hi is not None:
            await self._lock_hi.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._lock_hi is not None:
            self._lock_hi.release()
        self._lock_lo.release()
        return False

def boss_col() -> Collection:
    return get_db()["boss"]

def guild_boss_col() -> Collection:
    """رئیس‌های اختصاصی هر گیلد (یه سند به‌ازای هر guild_id)."""
    return get_db()["guild_boss"]

def bounty_col() -> Collection:
    """جایزه‌های سرِ بازیکنا (یه سند به‌ازای هر target uid)."""
    return get_db()["bounty"]

def auction_col() -> Collection:
    """آگهی‌های فعال حراجی (یه سند به‌ازای هر listing)."""
    return get_db()["auction"]

def house_col() -> Collection:
    """ملک شخصی بازیکنا (یه سند به‌ازای هر uid)."""
    return get_db()["house"]


def bank_cards_col() -> Collection:
    """نگاشتِ شماره‌کارتِ ۱۶ رقمی یکتا → آی‌دیِ تلگرامِ صاحبش (یه سند به‌ازای هر کارت)."""
    return get_db()["bank_cards"]


def bank_tx_col() -> Collection:
    """تاریخچه‌ی کاملِ تراکنش‌های عابربانک (یه سند به‌ازای هر انتقال، برای گزارش/ادمین)."""
    return get_db()["bank_transactions"]


_ledger_indexed = False

def ledger_col() -> Collection:
    """تاریخچه‌ی خامِ همه‌ی تراکنش‌های اقتصادیِ حساس (بازار سیاه + حراجی) —
    یه سند به‌ازای هر تراکنش، برای رهگیریِ Exploit/Bug (economy_ledger.py)."""
    global _ledger_indexed
    col = get_db()["economy_transactions"]
    if not _ledger_indexed:
        try:
            col.create_index([("user_id", 1), ("ts", -1)])
            col.create_index([("kind", 1), ("ts", -1)])
        except Exception:
            pass
        _ledger_indexed = True
    return col


def guild_treasury_col() -> Collection:
    """صندوق مشترک هر گیلد (یه سند به‌ازای هر guild_id) — کمک بازیکن‌ها + خرج روحیه‌ی گروهی."""
    return get_db()["guild_treasury"]


def casino_col() -> Collection:
    """آمار/تاریخچه‌ی کازینو به‌ازای هر بازیکن (لیدربورد هفتگی، VIP tier و غیره)."""
    return get_db()["casino_stats"]


def pool_col() -> Collection:
    return get_db()["char_pool"]

# ─── Dynamic Economy Engine ────────────────────────────────────
def market_col() -> Collection:
    """وضعیت زنده‌ی قیمت هر آیتم توی هر بازار (ضریب عرضه/تقاضا + تاریخچه)."""
    return get_db()["market_state"]

def tax_col() -> Collection:
    """صندوق مالیات سراسری (میشه بعداً به جایزه‌ی باس جهانی/ایونت وصلش کرد)."""
    return get_db()["tax_ledger"]

def events_col() -> Collection:
    """رویدادهای اقتصادی موقت فعال (فرنزی/کرش/معافیت مالیاتی)."""
    return get_db()["market_events"]

def dealer_col() -> Collection:
    """دیلرهای گردشیِ بازارِ سیاه — یه سند به‌ازای هر نقشه‌ای که الان یه دیلرِ فعال داره."""
    return get_db()["black_market_dealers"]

def smuggling_col() -> Collection:
    """تابلوی قاچاقِ بازیکن‌محور — یه سند به‌ازای هر قراردادِ فعال/تمام‌شده."""
    return get_db()["smuggling_contracts"]

def system_col() -> Collection:
    """وضعیتِ سراسریِ ربات که به هیچ بازیکن خاصی وصل نیست (مثل زمانِ آخرین
    جایزه‌ی هفتگی). فقط یه سند با _id ثابت برای هر «کلید» سیستمی."""
    return get_db()["system_state"]


# ─── جکپاتِ تجمعیِ سراسریِ کازینو ───────────────────────────────
JACKPOT_SEED = 50_000  # مقدارِ اولیه بعد از هر بار برد شدنِ جکپات

def get_jackpot() -> int:
    doc = system_col().find_one({"_id": "casino_jackpot"})
    if not doc:
        system_col().update_one({"_id": "casino_jackpot"}, {"$set": {"amount": JACKPOT_SEED}}, upsert=True)
        return JACKPOT_SEED
    return int(doc.get("amount", JACKPOT_SEED))

def add_to_jackpot(amount: int) -> int:
    doc = system_col().find_one_and_update(
        {"_id": "casino_jackpot"},
        {"$inc": {"amount": amount}},
        upsert=True,
        return_document=True,
    )
    return int(doc.get("amount", JACKPOT_SEED))

def reset_jackpot() -> None:
    system_col().update_one({"_id": "casino_jackpot"}, {"$set": {"amount": JACKPOT_SEED}}, upsert=True)

# ─── Player defaults / migration (سازگاری با سیستم‌های جدید) ──
# نکته‌ی مهم: بازیکن‌های قدیمی که از قبل تو دیتابیس هستن این فیلدهای جدید رو ندارن.
# به‌جای نوشتن یه اسکریپت migration جدا که باید دستی اجرا بشه، همین‌جا هر بار
# get_player صدا زده می‌شه، فیلدهای گم‌شده به‌صورت idempotent اضافه می‌شن
# (فقط تو حافظه — تا وقتی save_player صدا زده نشه چیزی تو دیتابیس تغییر نمی‌کنه).
_NEW_FIELD_DEFAULTS = {
    # پیش‌فرضِ موقت تا وقتی واقعاً ازش پرسیده بشه (فقط برای اینکه کارتِ
    # پروفایل کرش نکنه). gender_chosen=False یعنی «هنوز صریحاً انتخاب
    # نکرده» — چه پلیرِ قدیمی باشه چه پلیرِ جدیدی که هنوز رو دکمه نزده.
    # bot.py با یه middleware، هر پلیری با gender_chosen=False رو (چه
    # قدیمی چه جدید) یه‌بار با کیبوردِ ♂️/♀️ گیت می‌کنه.
    "gender": lambda: "male",
    "gender_chosen": lambda: False,
    "equipped": lambda: {s: None for s in
        ["weapon", "helmet", "armor", "gloves", "boots", "ring", "amulet", "relic"]},
    "ascensions_passed": lambda: [],
    "ascension_cooldowns": lambda: {},
    "titles_unlocked": lambda: [],
    "characters_seen": lambda: [],
    "epilogues_seen": lambda: [],
    "achievements_done": lambda: [],
    "login_streak": lambda: 0,
    "last_login_day": lambda: -1,
    "weekly_champion_count": lambda: 0,
    "pvp_season_points": lambda: 0,
    "boss_mastery": lambda: {},
    "current_fight": lambda: None,
    "bm_reputation": lambda: 0,
    "skill_points": lambda: 0,
    "unlocked_skills": lambda: [],
    "loot_streak": lambda: 0,
    "loot_best_streak": lambda: 0,
    "pity_counter": lambda: 0,
    "fortune_ward_count": lambda: 0,
    "set_collection": lambda: {},
    "guilds": lambda: {},  # guild_id -> {contribution, quests_done, active_quest, joined_at}
    "active_food_buffs": lambda: {},  # stat -> {value, expires_at, name} (cooking_system.py)

    # ═══ حالت سخت (Hardcore Mode) ═══════════════════════════════
    # مرگ و مجازات
    "death_count": lambda: 0,
    "death_curse_until": lambda: 0,      # timestamp — تا کی نفرین مرگ فعاله
    "heal_lockout_until": lambda: 0,     # timestamp — تا کی درمان قفله
    # ─── ریجن غیرفعال HP (hp_regen.py) ───
    "last_damage_ts": lambda: 0,         # timestamp — آخرین باری که HP کم شد
    "hp_regen_last_ts": lambda: 0,       # timestamp — آخرین باری که ریجن اعمال شد
    "injuries": lambda: [],              # ["old_wound","fracture","curse_perm","annihilated"]
    # خستگی و استراحت
    "battles_since_rest": lambda: 0,
    "resting_until": lambda: 0,          # timestamp
    # دیوارهای سختی سطح (هر ۱۰ سطح)
    "walls_cleared": lambda: [],         # [10, 20, ...]
    # باس‌های منطقه‌ای که کشته شدن (برای بازشدن تیر بعدی نقشه‌ها)
    "area_bosses_killed": lambda: [],    # [map_name, ...]
    # محدودیت‌های روزانه (نبرد/درمان — محدودیت لوت/سفر تو loot_handlers.py جدا نگه‌داری می‌شه)
    "daily_battle_used": lambda: 0,
    "daily_battle_reset_at": lambda: 0,
    "daily_heal_used": lambda: 0,
    "daily_heal_reset_at": lambda: 0,
    "daily_bm_buy_used": lambda: 0,
    "daily_bm_buy_reset_at": lambda: 0,

    # ═══ خط داستانی اصلی (Story Mode) ═══════════════════════════
    "quest_node": lambda: None,          # آی‌دیِ گره‌ی فعلی تو گراف داستان
    "quest_flags": lambda: {},           # تصمیم‌های قبلی (برای شاخه‌بندی)
    "resonance": lambda: 0,              # -100 (Void) تا +100 (Light)
    "main_chapter": lambda: 0,           # آخرین فصلِ تکمیل‌شده
    "side_quests_done": lambda: [],
    "side_quests_active": lambda: {},    # {quest_id: node_id}
    "kill_log": lambda: {},              # {enemy_name: count} — برای ماموریت‌های «N تا بکش»
    "quest_riddle_tries": lambda: 0,     # تعدادِ تلاشِ غلطِ ریدلِ فعلی
    "quest_seq_progress": lambda: [],    # پیشرفتِ پازلِ sequence فعلی
    "rebirth_count": lambda: 0,          # تعداد Rebirth انجام‌شده — سقفِ سطح رو بالا می‌بره

    # ═══ PvP v2 ═══════════════════════════════════════════════
    "pvp_wins": lambda: 0,
    "pvp_losses": lambda: 0,
    "pvp_streak": lambda: 0,
    "pvp_best_streak": lambda: 0,
    "pvp_points": lambda: 0,
    "pvp_total_dmg_dealt": lambda: 0,
    "pvp_total_dmg_taken": lambda: 0,
    "pvp_biggest_hit": lambda: 0,
    "pvp_ability_usage": lambda: {},
    "pvp_history": lambda: [],
    # ─── سیزن‌پسِ PvP (weekly_rewards.py) ────────────────────────
    "pvp_season_history": lambda: [],    # [{season, league, points, rank, reward}] — حداکثر ۱۰ فصلِ آخر
    "pvp_last_season_league": lambda: None,   # لیگِ نهاییِ آخرین فصلِ تمام‌شده (بج تو پروفایل)
    "pvp_last_season_points": lambda: 0,
    "pvp_last_season_rank": lambda: None,     # رتبه‌ی نهایی (اگه تو تاپ ۱۰۰ بوده)

    # ─── تشخیصِ الگوی رفتاریِ مشکوک (anti_farm.py) ──────────────
    "af_action_times": lambda: [],       # timestamp چند اکشنِ آخر (attack/loot/bosshit) برای تحلیلِ الگو

    # ─── سیستمِ استادی (mentor_system.py) ────────────────────────
    "graduated_mentee_count": lambda: 0,      # چندتا شاگرد تا الان فارغ‌التحصیل کردی (برای عنوانِ استادی)
    "mentor_last_milestone_level": lambda: 0, # آخرین سطحی که لحظه‌ی باند توش فعال شد

    # ═══ عابربانک / کارت بین‌بازیکنی (bank_system.py) ═══════════
    "bank_card": lambda: None,          # شماره‌کارتِ ۱۶ رقمی یکتا (اولین بار موقع ورود به بانک ساخته می‌شه)
    "bank_pin": lambda: None,           # PIN اختیاری (۴ رقمی) — None یعنی هنوز فعال نشده
    "bank_pin_fails": lambda: 0,        # تلاش‌های ناموفقِ پشت‌سرهم — برای قفل موقتِ ضدحدس‌زنی
    "bank_pin_locked_until": lambda: 0,
    "bank_transfer_today": lambda: 0,   # مجموع Zen منتقل‌شده‌ی امروز (سقفِ روزانه)
    "bank_transfer_reset_at": lambda: 0,
    "bank_history": lambda: [],         # آخرین تراکنش‌ها (واریز/برداشت) — حداکثر ۱۵ تا نگه داشته می‌شه

    # ═══ لوکیشن‌های متروکه (abandoned_locations.py) ═════════════
    "sickness_until": lambda: 0,        # تا کی افکتِ «بیماری» از بیمارستان متروکه فعاله
    "bank_heist_cooldowns": lambda: {}, # {map_name: timestamp} — ضدفارمِ بانکِ متروکه‌ی هر نقشه

    # ═══ نمسیس (nemesis_system.py / nemesis_handlers.py) ════════
    "nemesis_history": lambda: [],      # لیست نمسیس‌های شکست‌خورده: [{name, tier, encounters, defeated_at}]
    "nemesis_titles":  lambda: [],      # عنوان‌های دائمیِ گرفته‌شده از شکستِ نمسیس

    # ═══ کازینو (casino_handlers.py) ═════════════════════════════
    "casino_total_wagered": lambda: 0,  # مجموعِ کلِ Zenِ شرط‌بندی‌شده (مبنای VIP tier)
    "casino_weekly_net":    lambda: 0,  # سود/زیانِ خالصِ این هفته (برای لیدربورد)
    "casino_week_id":       lambda: "", # کلیدِ هفته‌ای که casino_weekly_net براشه (برای ریست خودکار)

    # ═══ حراجی زنده (auction_system.py) ══════════════════════════
    "auction_bid_locks": lambda: {},    # {listing_id: locked_zen} — Zenِ درگیرِ پیشنهادهای فعالِ این بازیکن

    # ═══ آنبوردینگ/تیوتوریالِ پلیرِ جدید (onboarding.py) ═════════
    # سیستمِ تیوتوریال غیرفعال شده — همه‌ی پلیرها (قدیمی و جدید) مستقیم
    # پنلِ کامل رو می‌بینن. tutorial_done پیش‌فرض True شده تا هیچ‌کس
    # وارد مسیرِ تیوتوریال نشه.
    "tutorial_done": lambda: True,
    "tutorial_step": lambda: "done",

    # ═══ شکافِ Abyss — Rift Dive (rift_dive_system.py / rift_dive_handlers.py) ═
    "rift_run":             lambda: None,   # ران فعال (None یعنی الان تو شکاف نیست)
    "rift_shards":          lambda: 0,      # ارز مخصوصِ شکاف (Echo Shard) — برای فروشگاهِ بعدی
    "rift_best_depth":      lambda: 0,      # عمیق‌ترین رکورد کلی
    "rift_best_depth_week": lambda: 0,      # عمیق‌ترین رکورد این هفته (لیدربورد)
    "rift_week_id":         lambda: "",     # کلیدِ هفته‌ای که rift_best_depth_week براشه
    "rift_stats":           lambda: {"runs": 0, "deaths": 0, "total_rooms": 0},

    # ═══ مونت — mount_system.py / mount_handlers.py ════════════
    "owned_mounts":  lambda: [],
    "active_mount":  lambda: None,

    # ═══ رخدادِ هم‌گرایی — convergence_system.py / convergence_handlers.py ═
    "convergence_stats": lambda: {"total_units": 0, "events_participated": 0},

    # ═══ الهه‌ی آغازها — goddess_system.py / goddess_handlers.py ═══════
    "goddess_favor":      lambda: 0,
    "goddess_last_pray":  lambda: 0,
    "goddess_cheat_skill": lambda: None,

    # ═══ ایسکای — isekai_flavor.py / isekai_personas.py ════════════════
    "isekai_truck_hits": lambda: 0,
    "isekai_titles":     lambda: [],
}

def apply_player_defaults(doc: dict) -> dict:
    """پر کردن فیلدهای گم‌شده روی یه سند بازیکن (idempotent، بدون تاثیر رو فیلدهای موجود)."""
    is_new_field_pass = "tutorial_done" not in doc
    for key, default_fn in _NEW_FIELD_DEFAULTS.items():
        if key not in doc:
            doc[key] = default_fn()
    # ─── بازیکنِ قدیمی که این فیچر (تیوتوریال) موقعِ ساختِ کاراکترش
    # هنوز وجود نداشت رو نباید وسطِ بازی بندازیم تو تیوتوریال. اگه
    # از قبل کاراکتر داره یا هر نشونه‌ای از پیشرفت (کشتن/سطح/دراپ)
    # داشته باشه، همون لحظه‌ی اولین لود، تیوتوریال رو براش تموم‌شده
    # علامت می‌زنیم.
    if is_new_field_pass and (
        doc.get("character")
        or doc.get("kills", 0) > 0
        or doc.get("level", 1) > 1
        or doc.get("inventory")
    ):
        doc["tutorial_done"] = True
        doc["tutorial_step"] = "done"

    # ─── مهاجرتِ سیستمِ کلاسِ جدید (Stage 1) ─────────────────────
    # هر سندِ قدیمی که از سیستمِ قبلیِ «۳۵۰ کرکترِ رندوم» مونده (یعنی
    # character داره ولی class نداره) دیگه معتبر نیست — طبقِ تصمیمِ
    # پروژه، این پلیرها باید از /start دوباره کاراکترشون (اسم + کلاس)
    # رو بسازن. فقط فیلدهای مربوط به ساختِ کاراکتر پاک می‌شن؛ پیشرفتِ
    # حساب (سطح/zen/اینونتوری/کیل و...) دست‌نخورده می‌مونه.
    if not doc.get("class") and (doc.get("character") or doc.get("gender_chosen") or doc.get("_awaiting_gender")):
        doc["character"] = None
        doc["class"] = None
        doc["class_system_data"] = {}
        doc["skills"] = []
        doc["stats"] = None
        doc["gender"] = None
        doc["gender_chosen"] = False
        doc["_awaiting_gender"] = False
        doc["name"] = None

    # ─── باگ‌فیکس: create_player قبلاً katana_skills/katana_dimensions رو
    # به‌اشتباه [] (لیست) می‌ساخت، درحالی‌که katana_skills.py/katana_dimensions.py
    # هر دو انتظار دیکشنری (per-character) دارن — با store.get(character_name)
    # روی لیست، AttributeError می‌داد و پنل حمله («یه مشکلی پیش اومد») کرش
    # می‌کرد. این‌جا هر سندِ قدیمی که این دو فیلد رو به‌شکلِ لیست ذخیره کرده،
    # خودکار به دیکشنری خالی تبدیل می‌شه (پیشرفتِ واقعیِ کاتانا از دست نمی‌ره،
    # چون این فیلدها وقتی [] بودن اصلاً قابلِ استفاده نبودن).
    if isinstance(doc.get("katana_skills"), list):
        doc["katana_skills"] = {}
    if isinstance(doc.get("katana_dimensions"), list):
        doc["katana_dimensions"] = {}

    # ─── باگ‌فیکس: create_player قبلاً katana_awakening رو None می‌ساخت، ولی
    # همه‌جای دیگه‌ی کد (katana_core.py, katana_handlers.py, combat_v3.py, ...)
    # با player.get("katana_awakening", 0) خونده می‌شه — چون کلید از قبل با
    # مقدارِ None وجود داشت، اون پیش‌فرضِ 0 اعمال نمی‌شد و به dmg_multiplier_for_stage
    # مقدار None می‌رسید (TypeError تو مقایسه‌ی stage <= 0، پنل حمله کرش می‌کرد).
    if doc.get("katana_awakening") is None:
        doc["katana_awakening"] = 0

    # ─── باگ‌فیکس: hunt_claimed_at هم مثل katana_awakening، None ساخته
    # می‌شد ولی hunt_questline.py (کلایمِ پاداشِ کوئست‌لاینِ حمله) دیکشنری
    # می‌خواد — با مقدارِ None، هر کلایم روی «📜 کوئست حمله» کرش می‌کرد.
    if doc.get("hunt_claimed_at") is None:
        doc["hunt_claimed_at"] = {}

    # آیتم‌های قدیمی تو اینونتوری رو هم به schema جدید آپگرید کن (فاز Item System v2)
    if doc.get("inventory"):
        try:
            from item_system import migrate_inventory
            doc["inventory"] = migrate_inventory(doc["inventory"])
        except ImportError:
            pass
    return doc

# ─── Players ────────────────────────────────────────────────

def get_player(user_id: int) -> Optional[dict]:
    """
    نکته: اگه user_id به یه حسابِ دیگه لینک شده باشه (account_link.py؛
    مثلاً پلیرِ گپ که حسابشو به حسابِ تلگرامش وصل کرده)، این تابع خودکار
    سندِ حسابِ اصلی رو برمی‌گردونه — همون فیکسِ «دو پنل».
    """
    user_id = resolve_uid(user_id)
    return get_player_raw(user_id)


def get_player_raw(user_id: int) -> Optional[dict]:
    """نسخه‌ی خام — بدونِ resolve_uid. فقط برای منطقِ داخلیِ account_link.py استفاده کن."""
    doc = players_col().find_one({"_id": user_id})
    if doc:
        doc.pop("_id", None)
        doc = apply_player_defaults(doc)
        # ─── بهینه‌سازیِ کارایی: قبلاً هرکدوم از این ۴ تا چکِ خودترمیمی/
        # لول‌آپ اگه چیزی تغییر می‌داد، بلافاصله یه save_player جدا صدا
        # می‌زد — یعنی هر بار get_player تا ۴ رفت‌وبرگشتِ اضافه‌ی بلاکینگ
        # به دیتابیس می‌زد (روی هر لودِ پروفایل، نه فقط دفعه‌ی اول!). چون
        # save_player (pymongo) سینکرونه، این ۴ رفت‌وبرگشت کل event loopِ
        # ربات رو برای مدتِ کوئری قفل می‌کردن و زیرِ لود باعثِ دیلیِ کلیِ
        # ربات می‌شدن. حالا فقط یه فلگ نگه می‌داریم و در آخر، اگه هرکدوم
        # از چک‌ها چیزی عوض کرده باشه، فقط یه‌بار save_player صدا می‌زنیم.
        needs_save = False
        if _sync_pending_levelups(doc):
            needs_save = True
        try:
            from hp_regen import apply_passive_regen
            if apply_passive_regen(doc):
                needs_save = True
        except ImportError:
            pass
        # ─── باگ‌فیکس: خودترمیمیِ متریال‌هایی که قبلاً (باگیِ migrate_legacy_item)
        # اشتباهاً اسلاتِ Relic گرفته بودن و با ۰ افیکس اکیپ شده بودن.
        # فقط یه‌بار برای هر پلیر (اولین لودِ بعدِ این آپدیت) کاری می‌کنه.
        try:
            from item_system import repair_fake_equipment
            if repair_fake_equipment(doc):
                needs_save = True
        except ImportError:
            pass
        # ─── باگ‌فیکس: خودترمیمیِ لوتِ رئیسِ گیلد که قبلاً همیشه اسلاتِ
        # Relic می‌گرفت (مثلاً شمشیرِ پادشاهِ تباهی) — الان بر اساسِ
        # loot_slot واقعیِ هر باس (GUILD_BOSS_DATA) اصلاح می‌شه.
        try:
            from guild_system import repair_guild_boss_loot_slots
            if repair_guild_boss_loot_slots(doc):
                needs_save = True
        except ImportError:
            pass
        if needs_save:
            save_player(user_id, doc)
        # نگهبانِ HP: مقدارِ فعلی رو یادداشت می‌کنیم تا save_player بفهمه
        # اگه بینِ این لود و ذخیره‌ی بعدی HP کم شد، تایمرِ ریجن ریست بشه.
        # فیلدِ زیر transient‌ـه و هیچ‌وقت تو دیتابیس ذخیره نمی‌شه.
        doc["_hp_watch"] = doc.get("hp")
    return doc


def _sync_pending_levelups(player: dict) -> bool:
    from game_data import xp_for_level, is_level_wall, effective_max_level
    leveled = False
    old_level = player.get("level", 1)
    cap = effective_max_level(player)
    while player.get("xp", 0) >= xp_for_level(player.get("level", 1)) and player.get("level", 1) < cap:
        lvl = player["level"]
        # حالت سخت: دیوار سختی — همون قانونِ همه‌جای دیگه
        if is_level_wall(lvl) and lvl not in player.get("walls_cleared", []):
            break
        player["level"] = lvl + 1
        player["max_hp"] = player.get("max_hp", 100) + 5
        from skill_tree import effective_max_hp
        player["hp"] = effective_max_hp(player)  # باگ‌فیکس: باف max_hp_pct هم لحاظ بشه
        leveled = True
    if leveled:
        try:
            from skill_tree import grant_levelup_points
            grant_levelup_points(player, old_level, player["level"])
        except ImportError:
            pass
    return leveled


def save_player(user_id: int, data: dict):
    """اگه user_id لینک شده باشه، رویِ سندِ حسابِ اصلی ذخیره می‌کنه (نگاه کن به resolve_uid)."""
    save_player_raw(resolve_uid(user_id), data)


def save_player_raw(user_id: int, data: dict):
    """
    ذخیره‌ی سندِ بازیکن — به‌جای $set خام، یه compare-and-swap اتمیک روی
    فیلدِ نسخه‌ی داخلی "_v" انجام می‌ده (نگاه کن به توضیحِ بالای
    player_lock). این تضمین می‌کنه که اگه یه نوشتنِ دیگه بینِ
    get_player و همین save_player برای همین بازیکن اتفاق افتاده باشه،
    این نوشتن به‌جای پاک‌کردنِ خاموشِ اون تغییرات، تشخیص داده بشه.

    نکته: این جایگزینِ player_lock نیست، مکملشه — player_lock جلوی
    خودِ race رو از قبل می‌گیره، این فقط تضمین می‌کنه حتی بدونش هم
    دیتا خاموش خراب نشه.
    """
    # ─── تشخیصِ خودکارِ دمیج برای سیستمِ ریجنِ غیرفعال (hp_regen.py) ───
    # اگه از لحظه‌ی get_player تا همین ذخیره، HP کم شده باشه (یعنی جایی تو
    # مسیر کدِ صدازننده دمیج خورده)، تایمرِ last_damage_ts ریست می‌شه تا
    # ریجن دوباره از صفر (بعد از REGEN_DELAY_SECONDS) شروع بشه.
    hp_watch = data.get("_hp_watch")
    if hp_watch is not None and data.get("hp", 0) < hp_watch:
        try:
            from hp_regen import mark_damage_taken
            mark_damage_taken(data)
        except ImportError:
            import time as _time
            data["last_damage_ts"] = _time.time()

    expected_v = data.get("_v")
    data_to_save = {k: v for k, v in data.items() if k not in ("_id", "_v", "_hp_watch")}

    if expected_v is None:
        # مسیرِ قدیمی/اولین‌بار — هنوز نسخه‌ای نداریم، با upsert معمولی
        # می‌نویسیم و شمارنده‌ی نسخه رو از صفر شروع می‌کنیم.
        players_col().update_one(
            {"_id": user_id},
            {"$set": data_to_save, "$inc": {"_v": 1}},
            upsert=True,
        )
        data["_v"] = 1
        return

    version_filter = {"_id": user_id}
    if expected_v == 0:
        # سندهای قدیمی که هنوز فیلدِ "_v" رو ندارن باید مثلِ نسخه‌ی ۰ در نظر گرفته بشن
        version_filter["$or"] = [{"_v": 0}, {"_v": {"$exists": False}}]
    else:
        version_filter["_v"] = expected_v

    result = players_col().update_one(
        version_filter,
        {"$set": data_to_save, "$inc": {"_v": 1}},
    )

    if result.matched_count == 0:
        # تناقضِ نسخه: یه جای دیگه‌ی کد بینِ خوندن و نوشتنِ ما، بدونِ
        # player_lock، همین بازیکن رو ذخیره کرده. برای این‌که دیتای
        # همین درخواست گم نشه بازم می‌نویسیم (بهتر از حذفِ خاموشِ یه
        # طرفِ تغییرات)، ولی بلند لاگ می‌کنیم که بفهمیم کدوم مسیر رو
        # باید به player_lock مهاجرت بدیم.
        try:
            from logger import log_sync
            log_sync(f"⚠️ [RACE] save_player conflict uid={user_id} expected_v={expected_v} — این مسیر هنوز زیرِ player_lock نیست", "WARNING")
        except Exception:
            print(f"[RACE-WARNING] save_player conflict uid={user_id} expected_v={expected_v}")
        players_col().update_one(
            {"_id": user_id},
            {"$set": data_to_save, "$inc": {"_v": 1}},
            upsert=True,
        )
        current = players_col().find_one({"_id": user_id}, {"_v": 1})
        data["_v"] = current.get("_v", expected_v + 1) if current else expected_v + 1
    else:
        data["_v"] = expected_v + 1

# ============================================================
#  🆕 لایه‌ی Async (باگ‌فیکسِ کندیِ کلیِ ربات)
# ------------------------------------------------------------
#  pymongo سنکرونه؛ get_player/save_player هر بار که صدا زده می‌شن،
#  کلِ event loopِ asyncio (یعنی کلِ ربات، برای همه‌ی بازیکن‌های
#  هم‌زمان) رو تا تمومِ رفت‌وبرگشتِ Mongo فریز می‌کنن. این ۴ تا
#  wrapper، بدونِ هیچ تغییری تو منطقِ خودِ get_player/save_player،
#  فقط همون فراخوانیِ سنکرون رو تو یه ترد جدا (thread pool) اجرا
#  می‌کنن — یعنی در حین اجرا شدنشون، event loop آزاده و می‌تونه
#  هم‌زمان به بقیه‌ی بازیکن‌ها سرویس بده.
#
#  مهاجرت تدریجیه: فایل‌ها یکی‌یکی از get_player/save_player
#  (سنکرون) به await aget_player/asave_player تبدیل می‌شن، شروع از
#  پرترافیک‌ترین مسیرها (حمله، باس، ...). فایل‌هایی که هنوز مهاجرت
#  نکردن دقیقاً مثلِ قبل کار می‌کنن (get_player/save_player خودشون
#  دست‌نخورده باقی موندن).
# ============================================================
async def aget_player(user_id: int) -> Optional[dict]:
    return await asyncio.to_thread(get_player, user_id)

async def asave_player(user_id: int, data: dict):
    return await asyncio.to_thread(save_player, user_id, data)

async def aget_player_raw(user_id: int) -> Optional[dict]:
    return await asyncio.to_thread(get_player_raw, user_id)

async def asave_player_raw(user_id: int, data: dict):
    return await asyncio.to_thread(save_player_raw, user_id, data)


def _default_player_fields(user_id: int, username: str, name: str) -> dict:
    """قالبِ کاملِ یه پلیرِ تازه — هم create_player و هم full_reset_player
    (پایین‌تر) از همینجا استفاده می‌کنن تا یه پلیرِ جدید و یه پلیرِ
    «کاملاً ریست‌شده» همیشه دقیقاً یه ساختار داشته باشن (بدونِ کپی‌پیستِ
    دوباره‌ی این دیکشنری تو جای دیگه، که قبلاً باعث می‌شد نسخه‌ی ریست
    از قلم‌افتادگی داشته باشه)."""
    return {
        "id": user_id,
        "username": username,
        "name": name,          # ممکنه هنوز None باشه — تا وقتی بازیکن اسمِ دلخواهش رو
                                # از فلوی /start (نام → کلاس) بفرسته پر نمی‌شه
        "character": None,     # فقط برای ماجراجو پر می‌شه (هویتِ داخلیِ کاتانا)
        "class": None,         # wizard | adventurer | merchant | healer — بعدِ انتخاب پر می‌شه
        "class_system_data": {},
        "skills": [],
        "stats": None,
        "katana_level": 1,
        "level": 1,
        "xp": 0,
        "hp": 100,
        "max_hp": 100,
        "zen": 1125,  # ۱.۵ برابر مقدار قبلی (۷۵۰) — کمک بیشتر به پلیرهای جدید در استارت
        "inventory": [],
        "map": "Verdant Vale",
        "combo": 0,
        "last_attack": 0,
        "total_damage": 0,
        "kills": 0,
        "pvp_wins": 0,
        "loot_streak": 0,
        "loot_best_streak": 0,
        "pity_counter": 0,
        "fortune_ward_count": 0,
        "set_collection": {},
        "bm_reputation": 0,        # رپیوتیشن بازار سیاه — تخفیف مالیات (موتور اقتصاد)
        "skill_points": 0,         # امتیاز آزاد درخت مهارت (skill_tree.py)
        "unlocked_skills": [],     # لیست node_id های باز شده
        # ── فیلدهای جدید (Item System v2 / Combat Power / World Tier) ──
        "equipped": {s: None for s in
            ["weapon", "helmet", "armor", "gloves", "boots", "ring", "amulet", "relic"]},
        "ascensions_passed": [],
        "ascension_cooldowns": {},
        "titles_unlocked": [],
        "characters_seen": [],
        "epilogues_seen": [],
        "achievements_done": [],
        "login_streak": 0,
        "last_login_day": -1,
        "weekly_champion_count": 0,
        "pvp_season_points": 0,
        "boss_mastery": {},
        "current_fight": None,
        "guilds": {},          # guild_id -> {contribution, quests_done, active_quest, joined_at}
        # ── زیرسیستم‌های اقتصادی/اجتماعیِ اضافه‌شده بعداً — قبلاً فقط تو
        # create_player نبودن و /resetall و /playerreset لمسشون نمی‌کردن،
        # یعنی «ریستِ کامل» واقعاً کامل نبود (پول تو بانک/سهام/شرط‌بندیِ
        # کازینو و... دست‌نخورده می‌موند). حالا با full_reset_player زیر
        # همه‌ی این‌ها هم صفر می‌شن. ──
        "pvp_losses": 0, "pvp_streak": 0, "pvp_best_streak": 0, "pvp_points": 0,
        "pvp_total_dmg_dealt": 0, "pvp_total_dmg_taken": 0, "pvp_biggest_hit": 0,
        "pvp_ability_usage": {}, "pvp_history": [],
        "bank_card": None, "bank_debt": 0, "bank_debt_since": None, "bank_debt_last_growth": None,
        "bank_pin": None, "bank_pin_fails": 0, "bank_pin_locked_until": 0,
        "bank_transfer_today": 0, "bank_transfer_reset_at": 0,
        "loan_principal": 0, "loan_taken_at": None, "loan_due_at": None, "loan_penalized": False,
        "savings_zen": 0, "savings_since": None, "credit_score": 0,
        "casino_total_wagered": 0, "casino_week_id": None, "casino_weekly_net": 0,
        "bp_season": None, "bp_points": 0, "bp_premium": False,
        "bp_claimed_free": [], "bp_claimed_premium": [],
        "market_favor_tokens": 0, "nemesis": None,
        "mentor_of": [], "mentor_pair_points": 0,
        "stand_bond_xp": 0, "stand_fragments": 0, "stand_last_train": 0,
        "stand_train_streak": 0, "stand_train_best_streak": 0,
        "active_pet_id": None, "katana_bond": 0, "katana_bond_level": 0,
        "katana_awakening": 0, "katana_dimensions": {}, "katana_kills": 0,
        "katana_deaths": 0, "katana_skills": {}, "katana_quests": {},
        "rebirth_count": 0, "resonance": 0, "main_chapter": 0,
        "side_quests_done": [], "side_quests_active": {}, "kill_log": {},
        "quest_node": None, "quest_flags": {}, "quest_riddle_tries": 0, "quest_seq_progress": [],
        "walls_cleared": [], "area_bosses_killed": [], "boss_hits_total": 0,
        "hunt_claimed_at": {}, "daily_quest_progress": {},
        "death_count": 0, "death_curse_until": 0, "heal_lockout_until": 0,
        "heal_cooldown_until": 0, "injuries": [], "battles_since_rest": 0, "resting_until": 0,
        "daily_battle_used": 0, "daily_battle_reset_at": 0,
        "daily_heal_used": 0, "daily_heal_reset_at": 0,
        "daily_bm_buy_used": 0, "daily_bm_buy_reset_at": 0,
        "streak_shield_used_day": None,
        "active_title": None, "stance": None, "stance_changed_at": 0, "rage": 0,
        "sickness_until": 0,
    }


def create_player(user_id: int, username: str, name: str) -> dict:
    # اگه این uid از قبل (به یه حسابِ دیگه) لینک شده، نباید یه سندِ جدید
    # بسازیم رو خودِ alias — باید رویِ حسابِ اصلی بسازیم (این مسیر عملاً
    # نباید پیش بیاد چون get_player(alias) از قبل سندِ primary رو
    # برمی‌گردونه، ولی برای اطمینان همینجا هم گارد می‌ذاریم).
    user_id = resolve_uid(user_id)
    data = _default_player_fields(user_id, username, name)
    save_player(user_id, data)
    return data


# ─── فیلدهایی که یه «ریستِ کامل» نباید دست بزنه ────────────────────
# هویت (id/username/name)، خودِ کاراکتر (طبقِ درخواستِ صریح: «کاراکتر
# حذف نشه، همه‌چیزِ دیگه ریست بشه» — این شاملِ کاتانا هم می‌شه، پس
# katana_* دیگه معاف نیست)، وضعیتِ بن/یادداشتِ ادمین، مُهرِ الهی
# (پاداشِ دستیِ ادمین، نه پیشرفتِ خودِ بازیکن)، و مراحلِ آموزشِ اولیه
# (تا آموزش دوباره روی پلیرِ باتجربه اجرا نشه).
RESET_PRESERVE_KEYS = {
    "id", "username", "name", "character", "banned", "ban_reason",
    "admin_note", "divine_seal", "gender", "gender_chosen",
    "tutorial_done", "tutorial_step",
}
# 🆕 باگ‌فیکس: قبلاً katana_* (لول/بوند/کیل/awakening/dimensions/skills/quests)
# با پیشوند از ریستِ کامل معاف بود، یعنی بعدِ /resetall یا /playerreset
# سطح کاتانا (مثلاً ۳۳) دست‌نخورده می‌موند و به‌اشتباه «ریست نشده» به نظر
# می‌رسید. طبقِ خواسته‌ی جدید، فقط خودِ فیلدِ character (این‌که پلیر کدوم
# کاراکتره) حفظ می‌مونه؛ همه‌چیزِ دیگه از جمله کاتانا کامل صفر می‌شه.
RESET_PRESERVE_PREFIXES = ()


def full_reset_player(user_id: int, *, new_character: str | None = None) -> Optional[dict]:
    """ریستِ واقعی و کاملِ یه پلیر: سندِ فعلی رو با یه سندِ تازه (طبقِ
    همون قالبِ _default_player_fields) جایگزین می‌کنه — نه یه merge/$set
    جزئی. این فرق مهمه: نسخه‌ی قبلیِ /resetall و /playerreset فقط چند
    فیلدِ مشخص رو صفر می‌کردن و بقیه‌ی فیلدها (مثلاً موجودیِ بانک، وام،
    سهامِ بورس، امتیازِ کازینو، پیشرفتِ بتل‌پس، ...) دست‌نخورده می‌موندن،
    یعنی «ریستِ کامل» در عمل کامل نبود.

    فقط کاراکتر، هویت و وضعیتِ بن/یادداشت/مُهرِ الهی حفظ می‌مونن؛ هرچیزِ
    دیگه‌ای — شاملِ کاتانا (لول/بوند/کیل/awakening/dimensions/skills/...)،
    سطح/XP/Zen/کوله‌پشتی/گیلد/بانک/کازینو/PvP/دستاورد/... — به مقدارِ
    پیش‌فرضِ یه پلیرِ تازه برمی‌گرده.

    new_character: اگه پر بشه، به‌جای حفظِ کاراکترِ فعلی، همین کاراکتر
    رو ست می‌کنه (برای حالتِ «ریستِ کامل شامل کاراکتر»).
    """
    old = get_player_raw(user_id)
    if not old:
        return None

    preserved = {
        k: v for k, v in old.items()
        if k in RESET_PRESERVE_KEYS or any(k.startswith(p) for p in RESET_PRESERVE_PREFIXES)
    }
    fresh = _default_player_fields(user_id, old.get("username", ""), old.get("name", "—"))
    fresh.update(preserved)
    if new_character is not None:
        fresh["character"] = new_character

    # جایگزینیِ کاملِ سند (نه $set) — تا فیلدهایی که تو fresh نیستن هم
    # واقعاً از دیتابیس پاک بشن، نه اینکه از قبل باقی بمونن.
    players_col().replace_one({"_id": user_id}, {**fresh, "_id": user_id}, upsert=True)
    return get_player_raw(user_id)

def all_players() -> dict:
    result = {}
    for doc in players_col().find():
        uid = str(doc["_id"])
        doc.pop("_id", None)
        result[uid] = apply_player_defaults(doc)
    return result

# ─── Character Pool ──────────────────────────────────────────

def generated_chars_col() -> Collection:
    """کرکترایی که به‌صورت پروسیجرال (بعد از تمومِ ۳۵۰ تای دستی) ساخته شدن."""
    return get_db()["generated_characters"]


# اسمِ کرکترایی که تا الان پروسیجرال ساخته شدن (برای جلوگیری از تکرار
# و برای اینکه assign_random_char بدونه از کجا انتخاب کنه). با
# load_generated_characters() موقعِ استارتِ ربات پر می‌شه.
_generated_names_cache: list = []


def load_generated_characters():
    """موقعِ استارتِ ربات صدا زده می‌شه: کرکترای پروسیجرالِ ساخته‌شده‌ی
    قبلی رو از دیتابیس می‌خونه و می‌ریزه تو ALL_CHARACTERS، تا combat،
    profile، loot و بقیه‌ی سیستم‌ها بدونِ هیچ تغییرِ اضافه‌ای بشناسنشون."""
    from characters import ALL_CHARACTERS
    global _generated_names_cache
    _generated_names_cache = []
    for doc in generated_chars_col().find():
        name = doc["_id"]
        data = {k: v for k, v in doc.items() if k != "_id"}
        ALL_CHARACTERS[name] = data
        _generated_names_cache.append(name)


def _create_and_register_new_character() -> str:
    """وقتی pool ۳۵۰ تای دستی تموم شد، یه کرکترِ جدیدِ پروسیجرال می‌سازه،
    تو ALL_CHARACTERS (رم) و دیتابیس (برای بعد از ری‌استارت) ثبتش
    می‌کنه و اسمشو برمی‌گردونه."""
    from characters import ALL_CHARACTERS, RANDOM_CHAR_NAMES
    from character_generator import generate_character
    existing_names = set(RANDOM_CHAR_NAMES) | set(_generated_names_cache) | set(ALL_CHARACTERS.keys())
    existing_katanas = {v.get("katana") for v in ALL_CHARACTERS.values() if v.get("katana")}
    name, data = generate_character(existing_names, existing_katanas)
    ALL_CHARACTERS[name] = data
    generated_chars_col().insert_one({"_id": name, **data})
    _generated_names_cache.append(name)
    return name


def assign_random_char() -> Optional[str]:
    from characters import RANDOM_CHAR_NAMES
    doc = pool_col().find_one({"_id": "pool"}) or {"taken": []}
    taken = doc.get("taken", [])
    full_pool = RANDOM_CHAR_NAMES + _generated_names_cache
    available = [c for c in full_pool if c not in taken]
    if available:
        chosen = random.choice(available)
    else:
        # ۳۵۰ تای دستی + هرچی تا الان پروسیجرال ساخته شده هم تموم شده:
        # به‌جای تکرار (ریست pool)، یه کرکترِ کاملاً تازه می‌سازیم.
        chosen = _create_and_register_new_character()
    pool_col().update_one(
        {"_id": "pool"},
        {"$addToSet": {"taken": chosen}},
        upsert=True
    )
    return chosen

def ensure_katana_character(player: dict) -> bool:
    """🆕 باگ‌فیکس: قبلاً سیستمِ کاتانا فقط مخصوصِ کلاسِ ماجراجو بود و بقیه‌ی
    کلاس‌ها اصلاً player["character"] نمی‌گرفتن. طبقِ تصمیمِ جدیدِ پروژه این
    محدودیت برداشته شده — هر پلیری (فارغ از کلاس) با اولین ورود به یکی از
    فیچرهای کاتانا (اگه هنوز هویتِ کاتانا نداشته باشه)، همین‌جا به‌صورتِ
    lazy یه هویتِ کاتانای رندوم می‌گیره؛ هم پلیرهای جدید هم پلیرهای قدیمی
    که قبل از این تغییر کلاسشون رو انتخاب کرده بودن، پوشش داده می‌شن.
    خروجی True یعنی چیزی عوض شده و لازمه بعدش save_player صدا زده بشه."""
    if player.get("character"):
        return False
    char = assign_random_char()
    player["character"] = char
    try:
        from character_lore import mark_character_seen
        mark_character_seen(player, char)
    except Exception:
        pass
    return True


def assign_special_char(char_name: str) -> bool:
    from characters import ALL_CHARACTERS
    if char_name not in ALL_CHARACTERS:
        return False
    pool_col().update_one(
        {"_id": "pool"},
        {"$addToSet": {"taken": char_name}},
        upsert=True
    )
    return True

def release_char(char_name: str):
    pool_col().update_one(
        {"_id": "pool"},
        {"$pull": {"taken": char_name}}
    )


def seal_holders_col() -> Collection:
    """یه سند به‌ازای هر مُهرِ یکتا (divine_mandate): {_id: seal_id, holder: telegram_id}."""
    return get_db()["seal_holders"]


def get_seal_holder(seal_id: str) -> Optional[int]:
    """آیدیِ کسی که الان این مُهرِ یکتا رو داره، اگه کسی نداره None."""
    doc = seal_holders_col().find_one({"_id": seal_id})
    return doc.get("holder") if doc else None


def assign_seal_holder(seal_id: str, telegram_id: int) -> Optional[int]:
    """
    مُهرِ یکتا رو به یه بازیکن جدید می‌ده. اگه قبلاً یکی دیگه این مُهرو
    داشته، آیدیِ اون نفرِ قبلی رو برمی‌گردونه (تا ادمین/هندلر بتونه
    مُهر رو از پروفایلِ نفرِ قبلی هم پاک کنه)، وگرنه None.
    """
    prev = get_seal_holder(seal_id)
    seal_holders_col().update_one(
        {"_id": seal_id},
        {"$set": {"holder": telegram_id}},
        upsert=True
    )
    return prev if prev != telegram_id else None

# ─── World Boss ──────────────────────────────────────────────

def _default_boss() -> dict:
    return {
        "_id": "boss",
        "name": "مائو (Maō)",
        "hp": 5000,
        "max_hp": 5000,
        "alive": False,
        "contributors": {}
    }

def get_boss() -> dict:
    doc = boss_col().find_one({"_id": "boss"})
    if not doc:
        doc = _default_boss()
        boss_col().insert_one(doc)
    doc.pop("_id", None)
    return doc

def save_boss(boss: dict):
    data = {k: v for k, v in boss.items() if k != "_id"}
    boss_col().update_one(
        {"_id": "boss"},
        {"$set": data},
        upsert=True
    )

def reset_boss():
    save_boss(_default_boss())

def load_boss() -> dict:
    return get_boss()

def boss_damage(user_id: int, dmg: int) -> dict:
    boss = get_boss()
    boss["hp"] = max(0, boss["hp"] - dmg)
    uid = str(user_id)
    boss["contributors"][uid] = boss["contributors"].get(uid, 0) + dmg
    save_boss(boss)
    return boss
