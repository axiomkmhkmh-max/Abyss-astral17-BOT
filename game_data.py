# ============================================================
#  ASTRAL ABYSS RPG — Game Constants
# ============================================================

# نکته: قبلاً اینجا یه ست جداگونه از MAPS/MAP_EMOJI/BLACK_MARKET_ITEMS/BASE_PRICES
# بود که هیچ‌جای دیگه‌ی کد استفاده نمی‌شد (نقشه‌های واقعی از economy.py → MAPS_DATA/MAP_LOOT
# میان که با SPAWN_MAPS تو bot.py هماهنگه). اون بلوک کد مرده و اسم نقشه‌هاش هم با نقشه‌های
# واقعی فرق داشت (مثلاً "Sunken City" اینجا vs "The Sunken City" تو economy.py) که گیج‌کننده
# بود؛ حذف شد. اگه بعداً لازم شد از economy.MAPS_DATA / economy.MAP_LOOT استفاده کنید.

WORLD_BOSS_MAX_HP = 5000
WORLD_BOSS_NAME = "مائو (Maō)"

LORE_RESPONSES = [
    "🌑 *در اعماق آبیس، صداها آرام می‌شوند...*\nانگار دنیا نفس می‌کشد، اما تو نمی‌توانی آن را بشنوی.",
    "👁️ *چشمانی در تاریکی تو را می‌نگرند...*\nاز کجا آمده‌ای، جنگجو؟ آیا آماده‌ای؟",
    "⚔️ *کاتانا در دستت می‌لرزد...*\nنیروهای باستانی از عمق Void Rift بیدار می‌شوند.",
    "🌌 *ستاره‌ها در Lost Nebula خاموش می‌شوند...*\nتاریکی جایشان را می‌گیرد. آیا تو روشنایی هستی؟",
    "🔥 *شعله‌های Ember Hollow زمزمه می‌کنند...*\nقدرت واقعی در درون تو پنهان است، نه در کاتانا.",
    "❄️ *یخ‌های Frostheim آب می‌شوند...*\nزمستان تمام شد. جنگ آغاز می‌شود.",
    "🏰 *از Dread Citadel صدای زنجیرها می‌آید...*\nکسی در آنجا زندانی است. یا شاید چیزی.",
    "🐉 *غرش اژدها از Dragonnest Peaks می‌آید...*\nآنها بیدار شده‌اند. آیا جرأت داری؟",
    "💎 *کریستال‌های Crystal Desert می‌درخشند...*\nاسرار باستانی در عمق شن‌ها پنهانند.",
    "🌑 *سایه‌های Shadow Rift حرکت می‌کنند...*\nهر قدمی که برمی‌داری، آنها دنبالت می‌آیند.",
    "🌿 *جنگل Verdant Vale نجوا می‌کند...*\nطبیعت هیچ‌چیز را فراموش نمی‌کند. حتی گناهان تو را.",
    "⚙️ *آهن‌های Iron Forest زنگ می‌زنند...*\nماشین جنگ هرگز نمی‌ایستد.",
    "🏚️ *از Ruins Orion باد می‌وزد...*\nتمدنی که بود، دیگر نیست. فقط خاطره.",
    "✨ *نور از Celestial Spire می‌تابد...*\nاما نور همیشه به معنای امنیت نیست.",
    "⛈️ *طوفان Storm Archipelago نزدیک می‌شود...*\nدریا عصبانی است. چرا؟ تنها خودش می‌داند.",
]

BOSS_SPAWN_MESSAGES = [
    "💀 *زمین می‌لرزد...* **{boss}** از اعماق Abyss بیرون می‌آید!\n🔴 HP: {hp:,}\nهمه جنگجویان! حمله کنید! `/attack`",
    "🌑 *تاریکی همه جا را می‌گیرد...* **{boss}** ظاهر شد!\n🔴 HP: {hp:,}\nاو قدرتمند است. با هم می‌توانیم! `/attack`",
    "⚡ *صاعقه‌ای آسمان را می‌شکافد...* **{boss}** آمد!\n🔴 HP: {hp:,}\nزمان مبارزه است! `/attack`",
]

ATTACK_POWER_NAMES = [
    "گام خلأ", "برش تاریکی", "هاله سکوت", "کشش گرانشی",
    "لغزش سایه", "ضربه بی‌صدا", "موج ترس", "برش شعله",
    "موج انرژی", "جهش نور", "سپر درخشان", "تابش خورشید",
    "ضربه شوک", "جرقه برق", "سرعت الکتریکی", "برش یخی",
    "مه سرد", "لغزش یخی", "برش سایه", "هاله ترس",
]

COMBO_TITLES = {
    1:  ("اولین ضربه",   ""),
    2:  ("ضربه دوم",      "🔥"),
    3:  ("سه‌گانه",       "🔥🔥"),
    5:  ("طوفان",         "⚡⚡"),
    8:  ("آشوب",          "💥💥💥"),
    12: ("اژدهای خشم",    "🐉💥"),
    20: ("خدای جنگ",      "👑⚡🔥"),
}

def get_combo_title(combo: int) -> tuple[str, str]:
    title, emoji = "اولین ضربه", ""
    for threshold, (t, e) in sorted(COMBO_TITLES.items()):
        if combo >= threshold:
            title, emoji = t, e
    return title, emoji

LEVEL_XP = [
    0,      # 1
    200,    # 2
    500,    # 3
    1000,   # 4
    1800,   # 5
    2800,   # 6
    4200,   # 7
    6000,   # 8
    8500,   # 9
    11500,  # 10
    15000,  # 11
    19500,  # 12
    25000,  # 13
    32000,  # 14
    40000,  # 15
    50000,  # 16
    62000,  # 17
    76000,  # 18
    92000,  # 19
    110000, # 20
]

MAX_LEVEL = 200

# ═══════════════════════════════════════════════════════════════
#  سیستم Rebirth (چرخه‌ی تولدِ دوباره) — طبق درخواست
# ═══════════════════════════════════════════════════════════════
# وقتی به سقفِ سطحِ فعلیت رسیدی، می‌تونی «Rebirth» کنی: سطح برمی‌گرده
# به ۱، ولی یه سری باف دائمی می‌گیری و سقفِ سطح ۵۰ تا بالاتر می‌ره.
# اینجوری بازی هیچ‌وقت واقعاً «تموم» نمی‌شه.
REBIRTH_LEVEL_STEP = 50   # هر ریبرث، سقف ۵۰ تا بالاتر می‌ره (۲۰۰→۲۵۰→۳۰۰...)

# باف‌های دائمیِ هر ریبرث (تجمعی، هرچی بیشتر ریبرث کنی بیشتر می‌شه)
REBIRTH_DMG_PCT_PER   = 0.10   # +۱۰٪ دمیج به‌ازای هر ریبرث
REBIRTH_LOOT_PCT_PER  = 0.08   # +۸٪ شانس لوت/دراپ به‌ازای هر ریبرث
REBIRTH_XP_PCT_PER    = 0.06   # +۶٪ XP دریافتی به‌ازای هر ریبرث
REBIRTH_MAXHP_PER     = 15     # +۱۵ Max HP پایه به‌ازای هر ریبرث (همیشه، حتی سطح ۱)

def effective_max_level(player: dict) -> int:
    """سقفِ سطحِ فعلیِ این بازیکن، با احتسابِ تعداد Rebirth."""
    rb = player.get("rebirth_count", 0)
    return MAX_LEVEL + rb * REBIRTH_LEVEL_STEP

def rebirth_ready(player: dict) -> bool:
    return player.get("level", 1) >= effective_max_level(player)

def rebirth_bonuses(player: dict) -> dict:
    """باف‌های دائمیِ فعلیِ بازیکن، بر اساسِ تعداد Rebirth."""
    rb = player.get("rebirth_count", 0)
    return {
        "dmg_pct":  rb * REBIRTH_DMG_PCT_PER,
        "loot_pct": rb * REBIRTH_LOOT_PCT_PER,
        "xp_pct":   rb * REBIRTH_XP_PCT_PER,
        "max_hp":   rb * REBIRTH_MAXHP_PER,
    }

def do_rebirth(player: dict) -> dict:
    """بازنشانیِ سطح/XP/HP + افزایشِ شمارنده‌ی Rebirth. چیزهایی که حفظ می‌شن:
    Zen، کوله‌پشتی، کاتانا، گیلدها، ست‌ها، پیشرفتِ داستان، دیوارهای شکسته‌شده."""
    player["rebirth_count"] = player.get("rebirth_count", 0) + 1
    player["level"] = 1
    player["xp"] = 0
    base_hp = 100 + rebirth_bonuses(player)["max_hp"]
    player["max_hp"] = int(base_hp)
    from skill_tree import effective_max_hp
    player["hp"] = effective_max_hp(player)  # باگ‌فیکس: باف max_hp_pct هم لحاظ بشه
    # حالتِ سختِ خستگی/نفرین/کول‌داون هم پاک می‌شه — شروعِ تازه واقعاً تازه‌ست
    player["battles_since_rest"] = 0
    player["resting_until"] = 0
    player["death_curse_until"] = 0
    player["heal_lockout_until"] = 0
    return player

# ─── حالت سخت: کاهش XP دریافتی از کشتن ─────────────────────────
# طبق درخواست: XP گرفتن سخت‌تر و کمتر بشه. این ضریب روی هر منبعِ XP
# (حمله‌ی combat_handlers.py و لوتِ mob_combat.py) اعمال می‌شه — یعنی
# با همون فرمولِ سطحِ سخت (xp_for_level) ترکیب می‌شه و مجموعاً گرایندِ
# لول‌آپ خیلی کندتر می‌شه.
XP_GAIN_MULTIPLIER = 0.275   # (نصفِ نصف‌شده — قبلاً 0.55 بود)

# همون منطق برای Zen: نصف شدنِ درآمدِ Zen از نبرد معمولی و mob.
ZEN_GAIN_MULTIPLIER = 0.5

# ─── حالت سخت (Hardcore Mode) ──────────────────────────────────
# قبلاً level*(level+1)*25 بود که باعث می‌شد لول ۱۷ فقط با ۲-۳ روز
# گرایندِ پیوسته قابل‌دسترسی باشه (طبق گزارش، خیلی راحت و سریع).
# ضریب به ۴۵ افزایش پیدا کرد (تقریباً ۱.۸ برابر بیشتر XP لازمه) تا
# با سقفِ روزانه‌ی جدیدِ XP (نگاه کن به anti_farm.py) ترکیب بشه و
# رسیدن به لول ۱۷ چند هفته طول بکشه، نه چند روز.
def xp_for_level(level: int) -> int:
    # 🐛 باگ‌فیکس: قبلاً از سطح ۲۰۰ (MAX_LEVEL) به بعد همیشه یه عددِ نجومی
    # (999,999,999) برمی‌گردوند — که عملاً غیرقابل‌دسترسه. مشکل اینجا بود
    # که REBIRTH_LEVEL_STEP سقفِ واقعیِ بازیکن (effective_max_level) رو
    # بعد از هر Rebirth ۵۰ تا بالاتر می‌بره (۲۰۰→۲۵۰→۳۰۰...)، ولی چون این
    # تابع مستقل از effective_max_level بود، هیچ بازیکنی — حتی بعد از
    # چندبار Rebirth — عملاً نمی‌تونست از لول ۲۰۰ بالاتر بره (چون رسیدن
    # به آستانه‌ی ۲۰۰→۲۰۱ عملاً ناممکن بود). فرمول رو نامحدود کردیم؛
    # سقفِ واقعی همیشه با effective_max_level(player) تو حلقه‌ی لول‌آپ
    # اعمال می‌شه، نه اینجا.
    return level * (level + 1) * 45

# ─── دیوارهای سختی (Hard Level Walls) — غیرفعال شد ─────────────
# قبلاً هر ۱۰ سطح (۱۰، ۲۰، ۳۰...) یه دیوار بود: بازیکن XP جمع می‌کرد ولی
# سطحش بالاتر از دیوار نمی‌رفت تا یه «باس دیوار» رو شکست بده. طبق درخواست
# حذف شد — الان لول‌آپ هیچ محدودیتی نداره (چه از حمله/لوت، چه از XP گیلد).
# تابع رو نگه داشتیم (نه پاک) که importهای موجود (database.py، bot.py،
# combat_handlers.py، mob_combat.py) نشکنن — فقط دیگه هیچ‌وقت True نمی‌ده.
LEVEL_WALL_STEP = 10

def is_level_wall(level: int) -> bool:
    return False

def next_level_wall(level: int) -> int | None:
    if level >= MAX_LEVEL:
        return None
    nxt = ((level // LEVEL_WALL_STEP) + 1) * LEVEL_WALL_STEP
    return nxt if nxt <= MAX_LEVEL else None

def wall_boss_stats(level: int) -> dict:
    """آمار باس دیوار سختی — هر چی دیوار بالاتر، باس قوی‌تر."""
    tier_n = level // LEVEL_WALL_STEP
    return {
        "name": f"👹 نگهبان دیوار سطح {level}",
        "hp":  int(400 * tier_n * (1 + tier_n * 0.15)),
        "dmg": int(30 * tier_n * (1 + tier_n * 0.08)),
        "xp":  int(200 * tier_n),
        "zen": int(180 * tier_n),
        "weak": "",
        "tier": "legendary",
        "is_wall_boss": True,
        "wall_level": level,
    }

RARITY_COLOR = {
    "common":    "⚔️ عادی",
    "uncommon":  "🟢 غیر عادی",
    "rare":      "💠 نادر",
    "epic":      "🟣 حماسی",
    "mythic":    "🟠 افسانه‌ای",
    "legendary": "🌟 لژندری",
    "special":   "👑 ویژه",
}
