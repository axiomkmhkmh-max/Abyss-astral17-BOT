# ============================================================
#  ASTRAL ABYSS — Economy & Items Database
# ============================================================
import random, time

# ─── Currency ────────────────────────────────────────────────
BZ_PER_SZ = 100
BZ_PER_GZ = 10_000
BZ_PER_DZ = 1_000_000

def bz_to_display(bz: int) -> str:
    """عددِ خامِ Zen رو به فرمتِ رده‌بندی‌شده تبدیل می‌کنه (🥉BZ/🥈SZ/🥇GZ/💎DZ).
    باگ‌فیکس: قبلاً فقط ۲ تا رده‌ی بالایی نشون داده می‌شد و مابقی (رده‌های
    پایین‌تر) کامل قورت می‌رفت — یعنی مثلاً دادنِ ۵۰۰ Zen به بازیکنی که
    ۵,۰۰۰,۰۰۰ Zen داشت هیچ فرقی تو نمایش نمی‌ذاشت («💎5DZ» قبل و بعد
    عین هم بود)، چون Zenِ کوچیک تو رده‌ی BZ گم می‌شد و اصلاً نمایش
    داده نمی‌شد. حالا همه‌ی رده‌های غیرصفر رو نشون می‌ده."""
    if bz <= 0: return "🥉0 BZ"
    dz, rem = divmod(bz, BZ_PER_DZ)
    gz, rem = divmod(rem, BZ_PER_GZ)
    sz, bzr = divmod(rem, BZ_PER_SZ)
    parts = []
    if dz: parts.append(f"💎{dz}DZ")
    if gz: parts.append(f"🥇{gz}GZ")
    if sz: parts.append(f"🥈{sz}SZ")
    if bzr or not parts: parts.append(f"🥉{bzr}BZ")
    return " ".join(parts)

# ─── Maps ────────────────────────────────────────────────────
# 🌸 حس‌وحالِ ایزکای: خودِ کلیدها (اسمِ انگلیسی) دست‌نخورده موندن چون
# ده‌ها فایلِ دیگه دقیقاً با همین رشته‌ها به‌عنوانِ شناسه کار می‌کنن؛
# فقط "desc" (زیرنویسِ نمایشی) عوض شده. اسمِ ژاپنیِ هرکدوم رو تو
# isekai_theme.py (MAP_JP_NAME) ببین — همون‌جا هرجا لازم بود نمایش
# داده می‌شه، بدونِ ریسکِ شکستنِ جاهای دیگه‌ی کد.
MAPS_DATA = {
    "Abyssal Black Market": {"emoji":"🖤","zone":"safe",      "travel":0,  "tier":"rare",   "desc":"بازارِ سایه‌ها — Yamiichi (闇市)"},
    "Sands of Eternity":    {"emoji":"🏜️","zone":"contested", "travel":10, "tier":"common", "desc":"صحرای جاودان — Eien no Sabaku (永遠の砂漠)"},
    "Holy Luminarchy":      {"emoji":"✨","zone":"safe",      "travel":12, "tier":"rare",   "desc":"پایتختِ نور — Hikari no Miyako (光の都)"},
    "Celestial Spire":      {"emoji":"🏰","zone":"contested", "travel":14, "tier":"rare",   "desc":"برجِ آسمانی — Tenkuu no Tou (天空の塔)"},
    "Frostheim":            {"emoji":"❄️","zone":"contested", "travel":15, "tier":"rare",   "desc":"قلمروی یخ — Yuki no Oukoku (雪の王国)"},
    "Voidbreak Wastes":     {"emoji":"🌑","zone":"danger",    "travel":20, "tier":"epic",   "desc":"سرزمینِ پوچی — Kyomu no Kouya (虚無の荒野)"},
    "Azure Tides Empire":   {"emoji":"🌊","zone":"contested", "travel":12, "tier":"common", "desc":"امپراتوریِ آبی — Ao no Teikoku (蒼の帝国)"},
    "Stormward Archipelago":{"emoji":"⛈️","zone":"danger",    "travel":15, "tier":"rare",   "desc":"جزایرِ طوفانی — Arashi no Gunto (嵐の群島)"},
    "The Sunken City":      {"emoji":"🐚","zone":"contested", "travel":16, "tier":"rare",   "desc":"شهرِ غرق‌شده — Suibotsu no Miyako (水没の都)"},
    "Verdant Vale":         {"emoji":"🌿","zone":"safe",      "travel":10, "tier":"common", "desc":"جنگلِ ارواح — Seirei no Mori (精霊の森)"},
    "Emberhollow":          {"emoji":"🔥","zone":"danger",    "travel":15, "tier":"rare",   "desc":"دره‌ی آتش — Honoo no Tani (炎の谷)"},
    "Dragonnest Peaks":     {"emoji":"🐉","zone":"danger",    "travel":20, "tier":"epic",   "desc":"لانه‌ی اژدها — Ryuu no Su (竜の巣)"},
    "Ruins of Orion-7":     {"emoji":"🏚️","zone":"contested", "travel":13, "tier":"rare",   "desc":"خرابه‌های اوریون-۷ — Orion-7 Iseki (オリオン7遺跡)"},
    "Dreadgate Citadel":    {"emoji":"💀","zone":"danger",    "travel":18, "tier":"epic",   "desc":"دژِ فراموشی — Boukyaku no Toride (忘却の砦)"},
    "Clockwork Depths":     {"emoji":"⚙️","zone":"contested", "travel":14, "tier":"rare",   "desc":"شهرِ کارآکوری — Karakuri Koutei (絡繰工廷)"},
    # 🆕 مپِ جدید — Tier 6 (بالاترین)، به‌شدت سخت، در ازاش بهترین لوتِ کل بازی
    "Throne of Oblivion":   {"emoji":"👑","zone":"danger",    "travel":25, "tier":"legendary","desc":"تختِ فراموشی — Bourei no Gyokuza (忘却の玉座)"},
}

ZONE_E = {"safe":"🟢","contested":"🟡","danger":"🔴"}
RARITY_E = {"common":"⚪","uncommon":"🟢","rare":"🔵","epic":"🟣","mythic":"🟠","legendary":"🟡"}

# ─── Loot Pools per Map ──────────────────────────────────────
MAP_ENEMIES = {
    "Sands of Eternity":     ["🦂 کژدم طلایی","🐍 مار شن","🏺 نگهبان معبد","👻 روح بیابان","🌪️ گردباد زنده"],
    "Holy Luminarchy":       ["😇 فرشته타락한","⚔️ شوالیه مقدس","🕊️ کبوتر نور","🧙 کشیش دیوانه","👼 نگهبان بهشت"],
    "Celestial Spire":       ["🌟 موجود اتری","⚡ شکارچی آسمان","🌀 پیچش فضا","💫 ستاره زنده","🔮 جادوگر برج"],
    "Frostheim":             ["🐺 گرگ یخی","❄️ غول برف","🦊 روباه آرکتیک","🧊 گلم یخ","🌨️ طوفان زنده"],
    "Voidbreak Wastes":      ["👁️ چشم خلأ","🌑 سایه خورنده","💀 ارواح فاسد","🕳️ دهان خلأ","👾 موجود بعد دیگر"],
    "Azure Tides Empire":    ["🦈 کوسه زرهی","🐙 اختاپوس غول","🌊 موج زنده","🦑 ماهی مرکب","🐋 نهنگ باستانی"],
    "Stormward Archipelago": ["🏴‍☠️ دزد دریایی","⚡ طوفان‌زده","🦅 عقاب طوفان","🌩️ صاعقه زنده","🐊 تمساح دریا"],
    "The Sunken City":       ["🐠 ماهی باستانی","🦀 خرچنگ غول","🌿 جلبک زنده","🐡 موجود نورانی","🦭 نهنگ دریا"],
    "Verdant Vale":          ["🐗 گراز جنگلی","🌳 درخت تاریک","🍄 قارچ سمی","🦋 پروانه دیو","🌺 گل گوشتخوار"],
    "Emberhollow":           ["🦎 اژدهای کوچک","🔥 گلم آتش","🌋 سنگ مذاب","💀 اسکلت سوخته","🐍 مار آتشین"],
    "Dragonnest Peaks":      ["🐉 اژدهای جوان","🦅 عقاب غول","🌋 ترکش آتشفشان","💎 اژدهای کریستال","👑 اژدهای ارشد"],
    "Ruins of Orion-7":      ["🤖 ربات نگهبان","⚙️ گلم فلزی","💡 سنتینل","🔫 تیرانداز خودکار","🛡️ نگهبان مکانیک"],
    "Dreadgate Citadel":     ["💀 سرباز مرده","👹 شیطان نگهبان","⛓️ زنجیری","🧟 زامبی جنگجو","😈 دیوان دروازه"],
    "Clockwork Depths":      ["⚙️ کارگر مکانیک","🔧 ربات تعمیرکار","💣 بمب متحرک","🔩 گلم فولادی","⛏️ ماینر"],
    "Abyssal Black Market":  ["🕵️ دزد بازار","🗡️ قاتل مزدور","🎭 فریبکار","💼 دلال خطرناک","🌑 سایه‌بان"],
    "Throne of Oblivion":    ["🩻 استخوان‌آور","⚰️ نگهبانِ تابوتِ شاهی","👑 اربابِ تاجِ فراموش‌شده","💀 پادشاهِ خاکسترها","🖤 روحِ سرکش"],
}

# ─── Sub-Locations per Map (برای انتخاب لوکیشن قبل از لوت) ────
# هر مپ ۴ لوکیشن تماتیک خودش رو داره — اینا فقط برای فلیور/UI هستن،
# موب واقعی همچنان از combat.MAP_ENEMIES میاد (تم‌بندی از قبل درسته).
MAP_LOCATIONS = {
    "Sands of Eternity": [
        {"name":"معبد فراموش‌شده",        "emoji":"🏛️","desc":"زیر شن‌های نیمه‌مدفون"},
        {"name":"داروخانه کاروانی متروکه","emoji":"💊","desc":"باقی‌مانده‌ی یه کاروان قدیمی"},
        {"name":"خانه‌های متروکه واحه",   "emoji":"🏚️","desc":"روستایی که شن بلعیدش"},
        {"name":"اردوگاه رهاشده",         "emoji":"⛺","desc":"آثار یه اردوگاه ناپدیدشده"},
    ],
    "Holy Luminarchy": [
        {"name":"بیمارستان مقدس",     "emoji":"🏥","desc":"محل شفای زائران، حالا خالی از سکنه"},
        {"name":"کلیسای بزرگ",        "emoji":"⛪","desc":"سکوت سنگین زیر گنبد طلایی"},
        {"name":"کتابخانه کشیشان",    "emoji":"📚","desc":"طومارهای قدیمی خاک‌گرفته"},
        {"name":"کاخ اسقف اعظم",      "emoji":"🏛️","desc":"راهروهای متروک کاخ مقدس"},
    ],
    "Celestial Spire": [
        {"name":"برج ستاره‌شناسان",   "emoji":"🔭","desc":"ابزارهای رصد شکسته و پراکنده"},
        {"name":"رصدخانه کیهانی",     "emoji":"🌌","desc":"نور ستاره‌ها از سقف شکسته می‌تابد"},
        {"name":"راهروهای معلق",      "emoji":"🌉","desc":"پل‌های شناور بین برج‌ها"},
        {"name":"آزمایشگاه اختری",    "emoji":"🧪","desc":"شیشه‌های شکسته‌ی آزمایش‌های ناتمام"},
    ],
    "Frostheim": [
        {"name":"کلینیک یخ‌زده",      "emoji":"🏥","desc":"تخت‌های بیمارستانی زیر لایه‌ی یخ"},
        {"name":"پناهگاه متروکه",     "emoji":"🏚️","desc":"جایی که اهالی از سرما فرار کردند"},
        {"name":"انبار یخی",          "emoji":"🧊","desc":"جعبه‌های منجمدشده روی هم"},
        {"name":"معبد یخی باستانی",   "emoji":"⛩️","desc":"مجسمه‌های یخ‌زده‌ی خدایان فراموش‌شده"},
    ],
    "Voidbreak Wastes": [
        {"name":"بیمارستان روانی رهاشده","emoji":"🏥","desc":"دیوارهایی که هنوز زمزمه می‌کنند"},
        {"name":"خانه‌های ویران خلأ",     "emoji":"🏚️","desc":"واقعیت اینجا کمی خم شده"},
        {"name":"حفره‌های خزنده",         "emoji":"🕳️","desc":"تونل‌هایی که به‌جایی ختم نمی‌شن"},
        {"name":"کارخانه‌ی فاسد",         "emoji":"🏭","desc":"ماشین‌آلاتی که دیگه معنایی ندارن"},
    ],
    "Azure Tides Empire": [
        {"name":"درمانگاه بندری",      "emoji":"🏥","desc":"وسایل پزشکی زنگ‌زده کنار اسکله"},
        {"name":"اسکله متروکه",        "emoji":"⚓","desc":"طناب‌های پوسیده و قایق‌های شکسته"},
        {"name":"خانه‌های ماهیگیران",   "emoji":"🏚️","desc":"کلبه‌هایی که موج آنها را رها کرد"},
        {"name":"کشتی غرق‌شده",        "emoji":"🚢","desc":"بدنه‌ی نیمه‌مدفون در شن ساحل"},
    ],
    "Stormward Archipelago": [
        {"name":"درمانگاه جزیره",        "emoji":"🏥","desc":"چادر پزشکی که توفان ویرانش کرد"},
        {"name":"مخفیگاه دزدان دریایی",  "emoji":"🏴‍☠️","desc":"غاری پر از گنج‌های جاافتاده"},
        {"name":"کلبه‌های ویران",        "emoji":"🏚️","desc":"سقف‌های پاره از باد شدید"},
        {"name":"بندر متروکه",           "emoji":"⚓","desc":"اسکله‌ای که دیگه کشتی نمی‌بیند"},
    ],
    "The Sunken City": [
        {"name":"بیمارستان زیرآب",     "emoji":"🏥","desc":"تخت‌های پوشیده از جلبک دریایی"},
        {"name":"معبد غرق‌شده",        "emoji":"🏛️","desc":"ستون‌های آتلانتیسی زیر آب"},
        {"name":"غار مرجانی",          "emoji":"🐚","desc":"راهروهای طبیعی پر از مرجان"},
        {"name":"خرابه‌های آتلانتیس",  "emoji":"🏚️","desc":"باقی‌مانده‌ی شهری که فرو رفت"},
    ],
    "Verdant Vale": [
        {"name":"درمانگاه گیاهی",      "emoji":"🏥","desc":"عطاری‌ای که گیاهانش وحشی شدن"},
        {"name":"روستای متروکه",       "emoji":"🏚️","desc":"خانه‌های خالی زیر شاخ‌وبرگ"},
        {"name":"کلبه‌ی جنگلی",        "emoji":"🌳","desc":"چوب پوسیده و بوی خاک نمناک"},
        {"name":"معبد الف‌های باستانی","emoji":"⛩️","desc":"حکاکی‌های سبز رنگ‌ورورفته"},
    ],
    "Emberhollow": [
        {"name":"بیمارستان سوخته",     "emoji":"🏥","desc":"دیوارهای دوده‌گرفته و تخت‌های ذوب‌شده"},
        {"name":"کارخانه‌ی مذاب",      "emoji":"🏭","desc":"کوره‌هایی که هنوز داغ‌اند"},
        {"name":"خانه‌های خاکستری",    "emoji":"🏚️","desc":"خاکستر جای زندگی رو گرفته"},
        {"name":"معدن آتشفشانی",       "emoji":"⛏️","desc":"تونل‌هایی رو به قلب کوه"},
    ],
    "Dragonnest Peaks": [
        {"name":"لانه‌ی اژدها",       "emoji":"🏔️","desc":"استخوان‌های غول‌آسا روی صخره"},
        {"name":"روستای ویران کوهستان","emoji":"🏚️","desc":"خانه‌هایی که پنجه‌ها ویرانشون کرد"},
        {"name":"غار کوهستانی",       "emoji":"⛰️","desc":"صدای غرش از اعماق می‌آید"},
        {"name":"قبرستان اژدها",      "emoji":"🦴","desc":"استخوان‌های نسل‌های گذشته"},
    ],
    "Ruins of Orion-7": [
        {"name":"اتاق سرور",            "emoji":"🖥️","desc":"چراغ‌های چشمک‌زن بدون هیچ سیگنالی"},
        {"name":"کارخانه‌ی متروکه",     "emoji":"🏭","desc":"خط تولیدی که سال‌هاست متوقفه"},
        {"name":"آپارتمان‌های رهاشده",  "emoji":"🏚️","desc":"طبقه‌هایی که دیگه کسی توش زندگی نمی‌کنه"},
        {"name":"آزمایشگاه ربات‌سازی",  "emoji":"🔬","desc":"قطعات نیمه‌ساخته روی میزها"},
    ],
    "Dreadgate Citadel": [
        {"name":"زندان زیرزمینی",      "emoji":"⛓️","desc":"سلول‌هایی که هنوز بوی ترس می‌دهند"},
        {"name":"دژ تسخیرشده",         "emoji":"🏰","desc":"پرچم‌های سیاه روی برج‌های شکسته"},
        {"name":"خانه‌های نفرین‌شده",  "emoji":"🏚️","desc":"دری که خودش باز و بسته می‌شود"},
        {"name":"قبرستان دروازه",      "emoji":"💀","desc":"سنگ‌قبرهایی بدون اسم"},
    ],
    "Clockwork Depths": [
        {"name":"کارگاه ماشین‌ها",     "emoji":"⚙️","desc":"دنده‌هایی که هنوز به‌آرومی می‌چرخند"},
        {"name":"کارخانه‌ی دنده‌سازی", "emoji":"🏭","desc":"صدای مداوم فلز روی فلز"},
        {"name":"آپارتمان کارگران",    "emoji":"🏚️","desc":"خونه‌های خالی کارگران معدن"},
        {"name":"انبار قطعات",         "emoji":"🔧","desc":"جعبه‌های پر از قطعات زنگ‌زده"},
    ],
    "Abyssal Black Market": [
        {"name":"درمانگاه زیرزمینی",   "emoji":"🏥","desc":"جایی که دزدها زخم‌هاشون رو مخفیانه درمان می‌کنن"},
        {"name":"کوچه‌های تاریک بازار","emoji":"🏚️","desc":"سایه‌هایی که همیشه یه چیزی می‌فروشن"},
        {"name":"مخفیگاه دلالان",      "emoji":"🎭","desc":"اتاق پشتی پر از جنس مشکوک"},
        {"name":"انبار قاچاق",         "emoji":"🗝️","desc":"صندوق‌هایی که رسید ندارن"},
    ],
    "Throne of Oblivion": [
        {"name":"تالارِ تاجِ خاکستری", "emoji":"👑","desc":"تختی که هزار سال کسی روش ننشسته"},
        {"name":"دخمه‌ی پادشاهانِ مرده","emoji":"⚰️","desc":"ردیف تابوت‌هایی که هنوز نفس می‌کشن"},
        {"name":"زندانِ ابدیت",        "emoji":"⛓️","desc":"زنجیرهایی که خودشون رو دوباره می‌بندن"},
        {"name":"معبدِ خاکسترها",       "emoji":"🕯️","desc":"شعله‌هایی سیاه که گرما ندارن"},
    ],
}

DEFAULT_LOCATIONS = [
    {"name":"منطقه‌ی نامشخص", "emoji":"🌫️", "desc":"جایی که نقشه دقیق نداره"},
]

# ─── Location Type Tagging (برای موتورهای عمیقِ لوکیشن — abandoned_locations.py) ──
# هر لوکیشن (بر اساس اسمش) به یکی از ۴ تیپِ عمیق نگاشت می‌شه:
#   house     → خونه‌های متروکه (لوت سریع کم‌ریسک + شانس تله)
#   hospital  → بیمارستان/کلینیک/داروخانه‌ی متروکه (آیتم دارویی نادر + شانس بیماری)
#   bank      → بانک/گاوصندوق متروکه (بیشترین Zen خام، نیازمند کلید، شانس آلارم)
#   building  → همه‌ی بقیه (معبد/برج/کارخانه/غار و...) → ساختمونِ چندطبقه‌ی push-your-luck
_HOUSE_KEYWORDS    = ["خانه", "کلبه", "روستا", "آپارتمان", "پناهگاه"]
_HOSPITAL_KEYWORDS = ["بیمارستان", "کلینیک", "درمانگاه", "داروخانه"]
_BANK_KEYWORDS     = ["بانک", "گاوصندوق", "خزانه"]

def classify_location_type(loc_name: str) -> str:
    for kw in _BANK_KEYWORDS:
        if kw in loc_name:
            return "bank"
    for kw in _HOSPITAL_KEYWORDS:
        if kw in loc_name:
            return "hospital"
    for kw in _HOUSE_KEYWORDS:
        if kw in loc_name:
            return "house"
    return "building"

def _tag_and_ensure_bank(locs: list[dict]):
    for loc in locs:
        loc.setdefault("type", classify_location_type(loc["name"]))
    if not any(l["type"] == "bank" for l in locs):
        locs.append({
            "name": "بانک متروکه", "emoji": "🏦",
            "desc": "گاوصندوق‌های زنگ‌زده پشت دری قفل‌شده که هنوز کسی بازش نکرده",
            "type": "bank",
        })

for _map_name in MAP_LOCATIONS:
    _tag_and_ensure_bank(MAP_LOCATIONS[_map_name])
_tag_and_ensure_bank(DEFAULT_LOCATIONS)
del _map_name

# هر آیتمِ متریال یه "desc" داره — این آیتم‌ها فقط برای فروش/فلیورن
# (قابلِ‌اکیپ نیستن، item_system.py این رو جدا هندل می‌کنه)، ولی طبق
# درخواست، توضیح می‌گیرن تا معلوم باشه هرکدوم چیه و مالِ کجاست.
MAP_LOOT = {
    "Sands of Eternity": [
        {"name":"Sand Crystal","emoji":"💠","rarity":"common","sell":50,"buy":100,"desc":"بلوری از شن‌های متبلورشده‌ی زیرِ آفتابِ بی‌رحمِ صحرا."},
        {"name":"Desert Relic","emoji":"🏺","rarity":"rare","sell":300,"buy":600,"desc":"یادگاریِ یه تمدنِ گم‌شده که زیرِ شن‌ها مدفون بود."},
        {"name":"Scorpion Venom","emoji":"🦂","rarity":"uncommon","sell":120,"buy":240,"desc":"زهرِ غلیظِ کژدم‌های غول‌پیکرِ این منطقه — تو کیمیاگری کاربرد داره."},
        {"name":"Ancient Coin","emoji":"🪙","rarity":"rare","sell":400,"buy":800,"desc":"سکه‌ای از دورانی که این صحرا هنوز یه واحه‌ی سرسبز بود."},
        {"name":"Sun Stone","emoji":"☀️","rarity":"epic","sell":1500,"buy":3000,"desc":"سنگی که انگار خودِ نورِ خورشید توش زندانی شده."},
    ],
    "Holy Luminarchy": [
        {"name":"Holy Crystal","emoji":"✨","rarity":"rare","sell":500,"buy":1000,"desc":"بلوری که با انرژیِ مقدسِ کلیسای بزرگ شارژ شده."},
        {"name":"Angel Feather","emoji":"🪶","rarity":"epic","sell":2000,"buy":4000,"desc":"پَری که می‌گن از بالِ یه فرشته‌ی نگهبان افتاده."},
        {"name":"Sacred Scroll","emoji":"📜","rarity":"rare","sell":600,"buy":1200,"desc":"طوماری با خط‌های باستانیِ کشیشانِ اعظم."},
        {"name":"Divine Shard","emoji":"💎","rarity":"legendary","sell":10000,"buy":20000,"desc":"تکه‌ای از یه مصنوعه‌ی الهیِ افسانه‌ای — بسیار کمیاب."},
        {"name":"Light Essence","emoji":"🌟","rarity":"uncommon","sell":200,"buy":400,"desc":"جوهرِ نورِ خالص که از گنبدِ طلاییِ کلیسا تراوش می‌کنه."},
    ],
    "Celestial Spire": [
        {"name":"Aether Core","emoji":"🔮","rarity":"epic","sell":2500,"buy":5000,"desc":"هسته‌ی انرژیِ اتریک که برجِ ستاره‌شناسان رو روشن نگه می‌داره."},
        {"name":"Star Fragment","emoji":"⭐","rarity":"rare","sell":700,"buy":1400,"desc":"تکه‌ای از یه ستاره‌ی فروافتاده، هنوز کمی گرم."},
        {"name":"Cosmos Dust","emoji":"🌌","rarity":"uncommon","sell":150,"buy":300,"desc":"غبارِ کیهانی که از شکاف‌های رصدخانه جمع می‌شه."},
        {"name":"Sky Crystal","emoji":"💠","rarity":"rare","sell":800,"buy":1600,"desc":"بلوری شفاف که رنگِ آسمونِ همیشه‌درخشانِ اینجا رو گرفته."},
        {"name":"Nebula Stone","emoji":"🌠","rarity":"legendary","sell":15000,"buy":30000,"desc":"سنگی افسانه‌ای که می‌گن از قلبِ یه سحابی اومده."},
    ],
    "Frostheim": [
        {"name":"Frost Gem","emoji":"❄️","rarity":"rare","sell":600,"buy":1200,"desc":"جواهری یخ‌زده که هیچ‌وقت آب نمی‌شه."},
        {"name":"Ice Core","emoji":"🧊","rarity":"epic","sell":2000,"buy":4000,"desc":"هسته‌ی یخیِ متراکم از اعماقِ معبدِ باستانیِ یخی."},
        {"name":"Wolf Pelt","emoji":"🐺","rarity":"common","sell":80,"buy":160,"desc":"پوستِ گرمِ یه گرگِ یخیِ شکارشده."},
        {"name":"Frozen Rune","emoji":"🔵","rarity":"rare","sell":900,"buy":1800,"desc":"رونی حک‌شده رو یخ که هنوز یه انرژیِ ضعیف ازش می‌تراود."},
        {"name":"Glacial Heart","emoji":"💙","rarity":"legendary","sell":12000,"buy":24000,"desc":"قلبِ منجمدشده‌ی یه موجودِ افسانه‌ای یخی."},
    ],
    "Voidbreak Wastes": [
        {"name":"Void Shard","emoji":"🌑","rarity":"epic","sell":3000,"buy":6000,"desc":"تکه‌ای از خلأ که نگاه‌کردن بهش حس عجیبی می‌ده."},
        {"name":"Corrupted Core","emoji":"☠️","rarity":"rare","sell":1000,"buy":2000,"desc":"هسته‌ای که فسادِ خلأ ازش رد شده و دیگه هیچ‌وقت مثل قبل نیست."},
        {"name":"Dark Matter","emoji":"⚫","rarity":"legendary","sell":20000,"buy":40000,"desc":"ماده‌ای که از فیزیکِ شناخته‌شده پیروی نمی‌کنه — بسیار نادر."},
        {"name":"Void Heart","emoji":"💜","rarity":"epic","sell":4000,"buy":8000,"desc":"قلبِ تپنده‌ی یه موجودِ خلأ، حتی بعدِ مرگش هنوز می‌تپه."},
        {"name":"Rift Crystal","emoji":"🔮","rarity":"rare","sell":1200,"buy":2400,"desc":"بلوری که از یه شکافِ فضایی-زمانی بیرون کشیده شده."},
    ],
    "Azure Tides Empire": [
        {"name":"Pearl","emoji":"🪨","rarity":"common","sell":60,"buy":120,"desc":"مرواریدی معمولی از صدف‌های کفِ اقیانوس."},
        {"name":"Sea Crystal","emoji":"💠","rarity":"rare","sell":500,"buy":1000,"desc":"بلوری آبی‌رنگ که با نمکِ دریا شکل گرفته."},
        {"name":"Shark Tooth","emoji":"🦷","rarity":"uncommon","sell":180,"buy":360,"desc":"دندونِ یه کوسه‌ی زرهیِ این آب‌ها — هنوز تیزه."},
        {"name":"Ocean Heart","emoji":"💙","rarity":"epic","sell":2500,"buy":5000,"desc":"جواهری که می‌گن قلبِ خودِ اقیانوسه."},
        {"name":"Atlantean Relic","emoji":"🐚","rarity":"legendary","sell":18000,"buy":36000,"desc":"یادگاری از تمدنِ گم‌شده‌ی آتلانتیس."},
    ],
    "Stormward Archipelago": [
        {"name":"Storm Crystal","emoji":"⚡","rarity":"rare","sell":700,"buy":1400,"desc":"بلوری که هنوز انرژیِ صاعقه‌ای که توش گیر افتاده رو نگه داشته."},
        {"name":"Pirate Gold","emoji":"🪙","rarity":"common","sell":100,"buy":200,"desc":"طلای غنیمتیِ یه کشتیِ دزدانِ دریایی."},
        {"name":"Thunder Gem","emoji":"⛈️","rarity":"epic","sell":2200,"buy":4400,"desc":"جواهری که با هر صاعقه‌ای که این جزایر می‌بینن، درخشان‌تر می‌شه."},
        {"name":"Sea Map","emoji":"🗺️","rarity":"rare","sell":800,"buy":1600,"desc":"نقشه‌ی دست‌نویسِ یه ناخدای دزدِ دریایی."},
        {"name":"Storm Heart","emoji":"🌩️","rarity":"legendary","sell":14000,"buy":28000,"desc":"هسته‌ی یه طوفانِ افسانه‌ای که هیچ‌وقت آروم نمی‌گیره."},
    ],
    "The Sunken City": [
        {"name":"Atlantean Coin","emoji":"🪙","rarity":"uncommon","sell":200,"buy":400,"desc":"سکه‌ای از دورانی که این شهر هنوز روی آب بود."},
        {"name":"Deep Sea Pearl","emoji":"🫧","rarity":"rare","sell":600,"buy":1200,"desc":"مرواریدی نادر از عمیق‌ترین نقطه‌ی این خرابه‌ها."},
        {"name":"Ancient Artifact","emoji":"🏺","rarity":"epic","sell":3000,"buy":6000,"desc":"مصنوعه‌ای دست‌نخورده از میانِ ستون‌های غرق‌شده."},
        {"name":"Trident Shard","emoji":"🔱","rarity":"rare","sell":900,"buy":1800,"desc":"تکه‌ای شکسته از سه‌شاخه‌ی یه فرمانروای دریا."},
        {"name":"Lost Crown","emoji":"👑","rarity":"legendary","sell":25000,"buy":50000,"desc":"تاجِ گم‌شده‌ی آخرین پادشاهِ آتلانتیس."},
    ],
    "Verdant Vale": [
        {"name":"Forest Herb","emoji":"🌿","rarity":"common","sell":40,"buy":80,"desc":"گیاهِ دارویی که فقط تو این جنگل‌های الفی می‌روید."},
        {"name":"Elven Crystal","emoji":"💚","rarity":"rare","sell":500,"buy":1000,"desc":"بلوری سبزرنگ که با جادوی الف‌ها هم‌آهنگ شده."},
        {"name":"Ancient Root","emoji":"🌳","rarity":"uncommon","sell":150,"buy":300,"desc":"ریشه‌ای از یه درختِ چندصدساله."},
        {"name":"Life Essence","emoji":"✨","rarity":"epic","sell":2000,"buy":4000,"desc":"جوهرِ حیاتی که از قلبِ جنگل تراوش می‌کنه."},
        {"name":"World Tree Seed","emoji":"🌱","rarity":"legendary","sell":30000,"buy":60000,"desc":"دانه‌ای افسانه‌ای، می‌گن از خودِ درختِ جهان اومده."},
    ],
    "Emberhollow": [
        {"name":"Lava Stone","emoji":"🌋","rarity":"common","sell":70,"buy":140,"desc":"سنگی که هنوز از گدازه‌های آتشفشان داغه."},
        {"name":"Fire Crystal","emoji":"🔥","rarity":"rare","sell":600,"buy":1200,"desc":"بلوری که شعله‌ی درونش هیچ‌وقت خاموش نمی‌شه."},
        {"name":"Dragon Scale","emoji":"🐉","rarity":"epic","sell":2500,"buy":5000,"desc":"فلسِ یه اژدهای کوچکِ این سرزمینِ آتشفشانی."},
        {"name":"Ember Core","emoji":"💛","rarity":"rare","sell":800,"buy":1600,"desc":"هسته‌ی گداخته‌ای که از قلبِ کوره‌های زیرزمینی بیرون اومده."},
        {"name":"Phoenix Ash","emoji":"🦅","rarity":"legendary","sell":16000,"buy":32000,"desc":"خاکسترِ افسانه‌ای که می‌گن از ققنوسِ همیشه‌زنده‌ست."},
    ],
    "Dragonnest Peaks": [
        {"name":"Dragon Scale","emoji":"🐉","rarity":"rare","sell":1000,"buy":2000,"desc":"فلسِ سختِ یه اژدهای جوانِ این قله‌ها."},
        {"name":"Dragon Egg Shard","emoji":"🥚","rarity":"epic","sell":4000,"buy":8000,"desc":"تکه‌ای از پوسته‌ی یه تخمِ اژدهای شکسته."},
        {"name":"Ancient Bone","emoji":"🦴","rarity":"uncommon","sell":300,"buy":600,"desc":"استخوانِ یه موجودِ باستانیِ این کوهستان."},
        {"name":"Dragon Heart","emoji":"❤️","rarity":"legendary","sell":35000,"buy":70000,"desc":"قلبِ نادرِ یه اژدهای ارشد — بسیار کمیاب."},
        {"name":"Wing Fragment","emoji":"🦅","rarity":"rare","sell":1200,"buy":2400,"desc":"پاره‌ای از بالِ یه عقابِ غولِ این قله‌ها."},
    ],
    "Ruins of Orion-7": [
        {"name":"Tech Scrap","emoji":"⚙️","rarity":"common","sell":50,"buy":100,"desc":"قراضه‌ی فلزیِ باقی‌مانده از ماشین‌آلاتِ این مگاساختار."},
        {"name":"Energy Cell","emoji":"🔋","rarity":"rare","sell":700,"buy":1400,"desc":"باتریِ انرژی‌زایی که هنوز کمی شارژ داره."},
        {"name":"AI Core","emoji":"🤖","rarity":"epic","sell":3500,"buy":7000,"desc":"هسته‌ی پردازشیِ یه هوشِ مصنوعیِ رهاشده."},
        {"name":"Nano Chip","emoji":"💡","rarity":"uncommon","sell":200,"buy":400,"desc":"تراشه‌ی نانویی از تجهیزاتِ پیشرفته‌ی این ویرانه‌ها."},
        {"name":"Orion Crystal","emoji":"🔮","rarity":"legendary","sell":20000,"buy":40000,"desc":"بلوری اسرارآمیز که راز و رمزِ خودِ اوریون-۷ رو تو خودش داره."},
    ],
    "Dreadgate Citadel": [
        {"name":"Dark Essence","emoji":"💀","rarity":"rare","sell":800,"buy":1600,"desc":"جوهرِ تاریکی که از دیوارهای این دژ می‌تراود."},
        {"name":"Legion Seal","emoji":"⛓️","rarity":"epic","sell":3000,"buy":6000,"desc":"مُهرِ رسمیِ لژیونِ نگهبانِ این قلعه."},
        {"name":"Cursed Rune","emoji":"☠️","rarity":"rare","sell":1000,"buy":2000,"desc":"رونی نفرین‌شده که بهتره زیاد بهش خیره نشی."},
        {"name":"Dread Stone","emoji":"🖤","rarity":"uncommon","sell":250,"buy":500,"desc":"سنگی سیاه که یه حسِ ترسِ مبهم منتقل می‌کنه."},
        {"name":"Legion Heart","emoji":"💔","rarity":"legendary","sell":28000,"buy":56000,"desc":"قلبِ فرماندهِ لژیون — نمادِ قدرتِ این دژِ نفرین‌شده."},
    ],
    "Clockwork Depths": [
        {"name":"Gear Fragment","emoji":"⚙️","rarity":"common","sell":45,"buy":90,"desc":"تکه‌ای از یه چرخ‌دنده‌ی غول‌پیکرِ شهرِ ساعت‌ساز."},
        {"name":"Iron Ore","emoji":"⬛","rarity":"common","sell":60,"buy":120,"desc":"سنگِ معدنِ آهنِ خامِ استخراج‌شده از اعماق."},
        {"name":"Steel Core","emoji":"🔩","rarity":"rare","sell":600,"buy":1200,"desc":"هسته‌ی فولادیِ یکی از ماشین‌های اصلیِ این شهر."},
        {"name":"Dwarf Rune","emoji":"🔧","rarity":"epic","sell":2800,"buy":5600,"desc":"رونی حک‌شده به دستِ استادکارانِ دورفیِ فراموش‌شده."},
        {"name":"Masterwork Ingot","emoji":"🥇","rarity":"legendary","sell":22000,"buy":44000,"desc":"شمشِ فلزی که فقط یه بار در نسل‌ها ساخته می‌شه."},
    ],
    "Abyssal Black Market": [
        {"name":"Stolen Goods","emoji":"🎭","rarity":"common","sell":80,"buy":160,"desc":"کالای دزدی، منشأش رو کسی نمی‌پرسه."},
        {"name":"Black Crystal","emoji":"🖤","rarity":"rare","sell":900,"buy":1800,"desc":"بلوری تیره که فقط تو تاریکیِ این بازار پیدا می‌شه."},
        {"name":"Shadow Gem","emoji":"💜","rarity":"epic","sell":3200,"buy":6400,"desc":"جواهری که با سایه‌های این بازارِ زیرزمینی گره خورده."},
        {"name":"Void Pass","emoji":"🎫","rarity":"rare","sell":1100,"buy":2200,"desc":"بلیطِ ورود به معاملاتِ خاصِ سایه‌بان‌های بازار."},
        {"name":"Abyss Heart","emoji":"🌑","rarity":"legendary","sell":40000,"buy":80000,"desc":"قلبِ خودِ آبیس — کمیاب‌ترین کالای این بازارِ سیاه."},
    ],
    # 🆕 بهترین لوتِ کل بازی — طبقِ درخواست، چون این مپ به‌شدت سخته باید جبرانِ
    # واقعی داشته باشه. حتی آیتمِ common اینجا از epic خیلی از مپ‌های دیگه بهتره.
    "Throne of Oblivion": [
        {"name":"Ash-Crowned Bone","emoji":"🦴","rarity":"rare","sell":1500,"buy":3000,"desc":"استخوانی که هنوز خاطره‌ی تاج رو یادشه."},
        {"name":"Oblivion Ember","emoji":"🕯️","rarity":"epic","sell":6000,"buy":12000,"desc":"اخگرِ سیاهی که به‌جای گرما، سکوت پخش می‌کنه."},
        {"name":"Chain of Eternity","emoji":"⛓️","rarity":"epic","sell":9000,"buy":18000,"desc":"زنجیری که هیچ‌وقت واقعاً پاره نمی‌شه."},
        {"name":"Forgotten Crown Shard","emoji":"👑","rarity":"legendary","sell":55000,"buy":110000,"desc":"تکه‌ای از تاجِ آخرین پادشاهِ فراموش‌شده."},
        {"name":"Heart of Oblivion","emoji":"💀","rarity":"legendary","sell":75000,"buy":150000,"desc":"قلبِ خودِ اُبلیویون — نایاب‌ترین و ارزشمندترین کالای کل دنیا."},
    ],
}

# ============================================================
#  مصرفِ مستقیمِ موادِ نقشه‌ای (MAP_LOOT)
# ------------------------------------------------------------
#  تا اینجا هر ۷۵ آیتمِ بالا (متریال‌های نقشه‌ای) دو مصرف داشتن:
#  فروش، یا تبدیل تو material_exchange.py. حالا یه مصرفِ سومِ
#  «مستقیم» هم می‌گیرن — دکمه‌ی ✨ مصرف تو /inventory، دقیقاً از
#  همون فریم‌ورکِ item_system.use_consumable که برای پوشن/طومار
#  ساخته شده بود (چیزِ جدیدی لازم نیست، فقط item["consumable"] رو
#  پر می‌کنیم). اثر بر اساسِ ریرتی مقیاس می‌شه:
#    common/uncommon → یه مقدار Zen/XP آنیِ کوچیک
#    rare/epic       → بافِ موقتِ دمیج/طلا/تجربه
#    legendary       → بافِ قدرتمند و اختصاصیِ همون آیتم (۹۰ دقیقه)
#  علاوه‌بر این، همچنان قابلِ فروش/تبدیل/لیست‌کردن تو مغازه هم هستن —
#  هیچ رفتارِ قبلی خراب نمی‌شه.
# ============================================================
_MAT_BUFF_STATS = ["dmg_pct", "xp_pct", "gold_find_pct"]

def _name_bucket(name: str, n: int) -> int:
    """هشِ ساده و دترمینیستیک (بینِ اجراهای مختلف هم ثابت می‌مونه،
    برخلافِ hash() پایتون که رندومایز می‌شه) — فقط برای پخش‌کردنِ
    یکنواختِ استتِ بافِ rare/epic بینِ آیتم‌های مختلف."""
    h = 0
    for ch in name:
        h = (h * 131 + ord(ch)) % 1_000_003
    return h % n

# اثرِ اختصاصی برای هر ۱۴ آیتمِ legendaryِ نقشه‌ای — هرکدوم متناسب با
# فلیورِ خودش (مثلاً Divine Shard → دمیج، Glacial Heart → HP، و...)
_LEGENDARY_CONSUMABLE = {
    "Divine Shard":     {"buff_stat": "dmg_pct",       "buff_value": 0.25},
    "Nebula Stone":     {"buff_stat": "xp_pct",        "buff_value": 0.35},
    "Glacial Heart":    {"buff_stat": "max_hp_flat",   "buff_value": 150},
    "Dark Matter":      {"buff_stat": "elem_amp",      "buff_value": 0.30},
    "Atlantean Relic":  {"buff_stat": "gold_find_pct", "buff_value": 0.35},
    "Storm Heart":      {"buff_stat": "elem_amp",      "buff_value": 0.25},
    "Lost Crown":       {"buff_stat": "gold_find_pct", "buff_value": 0.30},
    "World Tree Seed":  {"buff_stat": "max_hp_flat",   "buff_value": 200},
    "Phoenix Ash":      {"buff_stat": "dmg_pct",       "buff_value": 0.22},
    "Dragon Heart":     {"buff_stat": "dmg_pct",       "buff_value": 0.28},
    "Orion Crystal":    {"buff_stat": "xp_pct",        "buff_value": 0.30},
    "Legion Heart":     {"buff_stat": "dmg_pct",       "buff_value": 0.24},
    "Masterwork Ingot": {"buff_stat": "max_hp_flat",   "buff_value": 180},
    "Abyss Heart":      {"buff_stat": "elem_amp",      "buff_value": 0.35},
}
_LEGENDARY_DURATION = 5400  # ۹۰ دقیقه

_RARITY_SCALE = {
    "common":   {"kind": "gold", "mult": 0.6},
    "uncommon": {"kind": "xp",   "mult": 0.7},
    "rare":     {"kind": "buff", "value": 0.06, "duration": 1200},   # ۲۰ دقیقه
    "epic":     {"kind": "buff", "value": 0.13, "duration": 2700},   # ۴۵ دقیقه
}

def _build_material_consumable(item: dict) -> dict:
    name = item.get("name", "")
    if name in _LEGENDARY_CONSUMABLE:
        cfg = _LEGENDARY_CONSUMABLE[name]
        return {"kind": "buff", "buff_stat": cfg["buff_stat"],
                "buff_value": cfg["buff_value"], "duration": _LEGENDARY_DURATION}

    scale = _RARITY_SCALE.get(item.get("rarity", "common"), _RARITY_SCALE["common"])
    if scale["kind"] == "gold":
        return {"kind": "gold", "amount": max(15, int(item.get("sell", 20) * scale["mult"]))}
    if scale["kind"] == "xp":
        return {"kind": "xp", "amount": max(15, int(item.get("sell", 20) * scale["mult"]))}
    stat = _MAT_BUFF_STATS[_name_bucket(name, len(_MAT_BUFF_STATS))]
    return {"kind": "buff", "buff_stat": stat, "buff_value": scale["value"], "duration": scale["duration"]}

for _map_items in MAP_LOOT.values():
    for _it in _map_items:
        _it["usable"] = True
        _it["consumable"] = _build_material_consumable(_it)
del _map_items, _it

# حالت سخت: هزینه‌ی سفر ۵ برابر شد. چون سیستم فعلی هزینه‌ی سفر رو با
# «ثانیه‌ی زمانِ انتظار» (نه طلا) مدل می‌کنه، این ضریب رو دقیقاً همونجا
# (روی travel_seconds تو MAPS_DATA) اعمال می‌کنیم. اگه بازیکن طلا نداشته
# باشه، طبق درخواست پیاده می‌ره و ۲ برابر زمان (یعنی ۱۰ برابر مقدار پایه) می‌بره.
HARDCORE_TRAVEL_TIME_MULT = 5
HARDCORE_TRAVEL_NO_GOLD_EXTRA_MULT = 2
TRAVEL_MIN_GOLD_REQUIRED = 200  # حداقل طلا برای سفر سواره (وگرنه پیاده می‌ری)

def get_travel_time(map_name: str, player_zen: int = 10_000) -> int:
    """زمان سفر واقعی بعد از اعمال ضریب حالت سخت + جریمه‌ی نداشتن طلا."""
    base = MAPS_DATA.get(map_name, {}).get("travel", 10)
    total = base * HARDCORE_TRAVEL_TIME_MULT
    if player_zen < TRAVEL_MIN_GOLD_REQUIRED:
        total *= HARDCORE_TRAVEL_NO_GOLD_EXTRA_MULT
    return int(total)

# حالت سخت: شانس و کیفیت لوت نصف شد (rarity بالاتر خیلی نادرتر)
HARDCORE_LOOT_CHANCE_MULT = 0.5

# شانسِ اینکه هر اسلاتِ لوت به‌جای متریال، یه آیتمِ قابل‌اکیپ (زره/سلاح/جواهر) باشه.
# نقشه‌های تیر بالاتر شانسِ گیر بهتری هم می‌دن (هم رریتیِ اجباری بالاتر).
GEAR_DROP_CHANCE_IN_LOOT = 0.22

# شانسِ اینکه (اگه گیر نبود) یه آیتمِ مصرفی به‌جای متریالِ خام دراپ بشه
CONSUMABLE_DROP_CHANCE_IN_LOOT = 0.14

def roll_loot(map_name: str, count: int = 5, player_level: int = 1) -> list[dict]:
    pool = MAP_LOOT.get(map_name, MAP_LOOT["Abyssal Black Market"])
    tier = MAPS_DATA.get(map_name, {}).get("tier", "common")
    # وزن آیتم‌های نادر/حماسی/لجندری بیشتر کم شده تا لوت خفن خیلی کمیاب‌تر بشه
    weights = {
        "common":  [60,27,10,2.5,0.5],
        "rare":    [35,35,22,7,1],
        "epic":    [18,25,32,20,5],
        # 🆕 مپِ نایتمر (Throne of Oblivion) — سخت‌ترین مپ، در ازاش بهترین توزیعِ لوت
        "legendary": [5,15,30,32,18],
    }.get(tier, [60,27,10,2.5,0.5])

    # نقشه‌های نادرتر گیرِ کمی بهترم می‌ندازن (نه اجباری، فقط بخت بیشتر)
    tier_forced_rarity = {"common": None, "rare": "uncommon", "epic": "rare", "legendary": "epic"}.get(tier)

    results = []
    for _ in range(count):
        # ۵۰٪ شانس که اصلاً چیزی از این تلاش لوت گیر نیاد (حالت سخت)
        if random.random() > HARDCORE_LOOT_CHANCE_MULT:
            continue

        if random.random() < GEAR_DROP_CHANCE_IN_LOOT:
            from item_system import generate_random_equipment
            item = generate_random_equipment(
                player_level, forced_rarity=tier_forced_rarity,
                drop_source=f"loot:{map_name}",
            )
            results.append(item)
            continue

        if random.random() < CONSUMABLE_DROP_CHANCE_IN_LOOT:
            from item_system import generate_consumable
            item = generate_consumable(player_level)
            results.append(item)
            continue

        item = random.choices(pool, weights=weights[:len(pool)], k=1)[0].copy()
        var = random.uniform(0.85, 1.25)
        item["sell"] = int(item["sell"] * var)
        item["buy"]  = int(item["buy"]  * var)
        results.append(item)
    return results

def get_enemy(map_name: str) -> str:
    enemies = MAP_ENEMIES.get(map_name, ["👾 موجود ناشناس"])
    return random.choice(enemies)

# ─── حالت سخت: ورشکستگی ────────────────────────────────────────
# اگه Zen به صفر برسه، بازیکن نمی‌تونه لوت/سفر/درمان کنه تا یه آیتم بفروشه.
def is_bankrupt(player: dict) -> bool:
    return player.get("zen", 0) <= 0

BANKRUPTCY_MSG = "💸 **ورشکسته‌ای!** Zen تو صفره. اول یه آیتم از کوله‌پشتیت بفروش (🖤بازار سیاه ›› 💰 فروش آیتم)."

# ─── Katana Forge ────────────────────────────────────────────
# سیستم قدیمی (۱۷ سطح خطی ساده) با موتور حرفه‌ای جدید جایگزین شد.
# جزئیات کامل (تیرها، مواد، شانس فورج، فرمول‌ها) تو katana_system.py هست.
# KATANA_LEVELS اینجا فقط برای سازگاری با importهای قدیمی نگه داشته شده؛
# محتواش کامل از katana_system میاد (۵۲ سطح به‌جای ۱۷ سطح قبلی).
from katana_system import (
    KATANA_LEVELS, KATANA_TIERS, FORGE_SHOP_ITEMS,
    MAX_NORMAL_LEVEL, TRANSCENDENT_LEVEL,
    get_katana_title, get_katana_suffix, get_katana_full_stats,
    attempt_forge, forge_cost, forge_materials, success_chance,
    dmg_bonus as katana_dmg_bonus,
    crit_bonus as katana_crit_bonus,
    lifesteal_bonus as katana_lifesteal_bonus,
    element_amplify_bonus as katana_element_amplify_bonus,
)


# ─── Black Market Items ──────────────────────────────────────
SPY_ITEMS = [
    {"name":"Purple Smoke",       "emoji":"🟣","cost":15000, "rarity":"rare",   "effect":"دود بنفش — فرار از دشمن"},
    {"name":"Ghost Radar",        "emoji":"📡","cost":6000, "rarity":"rare",   "effect":"نشون دادن موقعیت دشمن"},
    {"name":"Architect Key",      "emoji":"🗝️","cost":12000, "rarity":"rare",   "effect":"باز کردن مناطق مخفی"},
    {"name":"Silent Step Module", "emoji":"👣","cost":6000, "rarity":"rare",   "effect":"حذف صدای حرکت"},
    {"name":"Cloak Beacon",       "emoji":"📡","cost":15000, "rarity":"rare",   "effect":"مخفی شدن از اسکنر"},
    {"name":"Nano Wire Trap",     "emoji":"🕸️","cost":15000, "rarity":"mythic", "effect":"تله نانو — آسیب PvP"},
    {"name":"EMP Coin",           "emoji":"💫","cost":6000, "rarity":"epic",   "effect":"غیرفعال کردن تله‌ها"},
    {"name":"Shadow Lens",        "emoji":"🔭","cost":6000, "rarity":"rare",   "effect":"دیدن در تاریکی"},
    {"name":"Pulse Scanner",      "emoji":"📻","cost":6000, "rarity":"rare",   "effect":"اسکن منطقه"},
    {"name":"Memory Scrambler",   "emoji":"🧠","cost":9000, "rarity":"mythic", "effect":"گیج کردن حریف PvP"},
    {"name":"Data Worm",          "emoji":"🐛","cost":6000, "rarity":"epic",   "effect":"هک سیستم دشمن"},
    {"name":"Pulse Charge",       "emoji":"⚡","cost":6000, "rarity":"epic",   "effect":"غیرفعال کردن رادار"},
    {"name":"Void Pass",          "emoji":"🎫","cost":9000, "rarity":"mythic", "effect":"عبور از Void Zone"},
]

DEFENSE_ITEMS = [
    {"name":"Laser Walls",      "emoji":"🔴","cost_sz":3,  "rarity":"rare",   "effect":"دیوار لیزری دفاعی"},
    {"name":"Gravity Traps",    "emoji":"🌀","cost_sz":3,  "rarity":"rare",   "effect":"تله گرانشی"},
    {"name":"Sentry Turrets",   "emoji":"🤖","cost_sz":3,  "rarity":"rare",   "effect":"تیربار خودکار"},
    {"name":"Pulse Barricades", "emoji":"🛡️","cost_sz":3,  "rarity":"rare",   "effect":"موانع پالسی"},
    {"name":"Drone Watchers",   "emoji":"🚁","cost_sz":3,  "rarity":"rare",   "effect":"پهپاد نگهبان"},
    {"name":"Motion Seals",     "emoji":"🔒","cost_sz":3,  "rarity":"rare",   "effect":"قفل حرکتی"},
    {"name":"Arc Mines",        "emoji":"💣","cost_sz":3,  "rarity":"rare",   "effect":"مین قوسی"},
    {"name":"Phase Shields",    "emoji":"💠","cost_sz":6,  "rarity":"epic",   "effect":"سپر فازی"},
    {"name":"Echo Beacons",     "emoji":"📡","cost_sz":3,  "rarity":"rare",   "effect":"چراغ پژواک"},
    {"name":"Null Zones",       "emoji":"⬛","cost_sz":3,  "rarity":"rare",   "effect":"منطقه بی‌اثر"},
    {"name":"Spike Emitters",   "emoji":"🔱","cost_sz":3,  "rarity":"rare",   "effect":"تیرانداز تیغه"},
    {"name":"Rift Alarms",      "emoji":"🚨","cost_sz":3,  "rarity":"rare",   "effect":"هشدار شکاف"},
]

SHADOW_AUCTION = [
    {"name":"Soul Stone",          "emoji":"💎","cost":240000, "rarity":"legendary","effect":"زنده کردن هم‌تیمی / ارتقای کاتانا"},
    {"name":"Essence of Decider",  "emoji":"✨","cost":None,  "rarity":"legendary","effect":"تکامل قدرت‌های Aetheryx"},
    {"name":"Void Heart",          "emoji":"💜","cost":300000,"rarity":"legendary","effect":"منبع انرژی بی‌پایان"},
    {"name":"Chrono-Hourglass",    "emoji":"⌛","cost":None,  "rarity":"legendary","effect":"برگشت زمان ۵ ثانیه در مبارزه"},
]

_market_refresh = {"t":0,"items":[]}
# حالت سخت: تنوع کالای بازار سیاه از ۶ به ۴ کم شد و قیمت‌ها ۳ برابر شدن
HARDCORE_MARKET_ITEM_COUNT = 4
HARDCORE_MARKET_PRICE_MULT = 3.0

def get_market_items():
    now = time.time()
    if now - _market_refresh["t"] > 3600:
        from economy import MAP_LOOT
        pool = []
        for items in MAP_LOOT.values():
            pool.extend(items)
        chosen = random.sample(pool, min(HARDCORE_MARKET_ITEM_COUNT, len(pool)))
        selected = []
        for item in chosen:
            item = item.copy()
            item["market_price"] = int(item["buy"] * random.uniform(1.1,1.5) * HARDCORE_MARKET_PRICE_MULT)
            selected.append(item)
        _market_refresh["items"] = selected
        _market_refresh["t"] = now
    return _market_refresh["items"]
