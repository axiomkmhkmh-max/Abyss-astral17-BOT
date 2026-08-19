# ============================================================
#  ASTRAL ABYSS — Ultra Combat System
# ============================================================
import random, time
from economy import MAPS_DATA, bz_to_display, RARITY_E
from logger import log_sync

# ─── Enemy Database ──────────────────────────────────────────

ENEMIES = {
    # Verdant Vale
    "🐗 کاراگ":        {"hp":112,  "dmg":8,  "xp":15, "zen":10, "weak":"آتش",    "drop_chance":0.3,  "tier":"common"},
    "🌳 روتگار":        {"hp":167, "dmg":12, "xp":22, "zen":18, "weak":"آتش",    "drop_chance":0.2,  "tier":"common"},
    "🍄 وبازاد":          {"hp":83,  "dmg":15, "xp":18, "zen":14, "weak":"یخ",     "drop_chance":0.35, "tier":"common"},
    "🦋 مورنا":        {"hp":126,  "dmg":10, "xp":20, "zen":16, "weak":"برق",    "drop_chance":0.25, "tier":"common"},
    "🌺 زهرگل، دهانِ سبز": {"hp":140, "dmg":16, "xp":26, "zen":20, "weak":"خلأ", "drop_chance":0.2, "tier":"rare"},
    "🐍 سیثرا":           {"hp":98,  "dmg":18, "xp":20, "zen":15, "weak":"یخ",     "drop_chance":0.3,  "tier":"common"},
    "🦎 دراگیل":       {"hp":182, "dmg":16, "xp":28, "zen":22, "weak":"آتش",    "drop_chance":0.2,  "tier":"common"},
    "🐝 زیمبا":         {"hp":70,  "dmg":20, "xp":16, "zen":12, "weak":"آتش",    "drop_chance":0.4,  "tier":"common"},
    "🦅 کورواک":        {"hp":153, "dmg":22, "xp":30, "zen":24, "weak":"برق",    "drop_chance":0.25, "tier":"common"},
    "🐻 دِرگون، پیرِ جنگل":       {"hp":840, "dmg":75, "xp":45, "zen":38, "weak":"آتش",    "drop_chance":0.15, "tier":"rare"},
    "🌿 ویندرا":         {"hp":119,  "dmg":12, "xp":18, "zen":14, "weak":"آتش",    "drop_chance":0.3,  "tier":"common"},
    "🍃 سیلوان، پژواکِ برگ":          {"hp":630, "dmg":60, "xp":35, "zen":28, "weak":"آتش",    "drop_chance":0.2,  "tier":"rare"},
    # Frostheim
    "🐺 فِنراک":           {"hp":461, "dmg":54, "xp":30, "zen":25, "weak":"آتش",    "drop_chance":0.3,  "tier":"rare"},
    "❄️ بورگاث":           {"hp":840, "dmg":75, "xp":50, "zen":40, "weak":"آتش",    "drop_chance":0.15, "tier":"rare"},
    "🦊 اسکا":     {"hp":105,  "dmg":20, "xp":28, "zen":22, "weak":"برق",    "drop_chance":0.3,  "tier":"common"},
    "🧊 زمهریر، دلِ یخ":            {"hp":1050, "dmg":66, "xp":45, "zen":35, "weak":"آتش",    "drop_chance":0.1,  "tier":"epic"},
    "🐻‍❄️ گروم‌زوزه":        {"hp":756, "dmg":84, "xp":40, "zen":32, "weak":"آتش",    "drop_chance":0.2,  "tier":"rare"},
    "🌨️ وایترا":           {"hp":546, "dmg":66, "xp":35, "zen":28, "weak":"آتش",    "drop_chance":0.25, "tier":"rare"},
    "🦌 کریستان":          {"hp":126,  "dmg":15, "xp":22, "zen":18, "weak":"آتش",    "drop_chance":0.3,  "tier":"common"},
    "⛄ یارموث":      {"hp":672, "dmg":72, "xp":38, "zen":30, "weak":"آتش",    "drop_chance":0.2,  "tier":"rare"},
    "🧟 کالگار":      {"hp":167, "dmg":19, "xp":32, "zen":26, "weak":"آتش",    "drop_chance":0.25, "tier":"common"},
    "❄️ پریزماک":      {"hp":714, "dmg":78, "xp":42, "zen":34, "weak":"آتش",    "drop_chance":0.18, "tier":"rare"},
    # Voidbreak Wastes
    "👁️ زیراکس":           {"hp":630, "dmg":90, "xp":60, "zen":50, "weak":"نور",    "drop_chance":0.2,  "tier":"epic"},
    "🌑 نول‌گاست":      {"hp":756, "dmg":105, "xp":70, "zen":60, "weak":"نور",    "drop_chance":0.15, "tier":"epic"},
    "💀 وخشوران":       {"hp":546, "dmg":84, "xp":55, "zen":45, "weak":"مقدس",   "drop_chance":0.2,  "tier":"rare"},
    "🕳️ آبادون، دهانِ هیچ":         {"hp":1260, "dmg":135, "xp":100,"zen":80, "weak":"نور",    "drop_chance":0.1,  "tier":"legendary"},
    "👾 کای‌مورگ":    {"hp":923, "dmg":114, "xp":80, "zen":65, "weak":"نور",    "drop_chance":0.15, "tier":"epic"},
    "🌀 ورتیگون":         {"hp":588, "dmg":96, "xp":58, "zen":48, "weak":"نور",    "drop_chance":0.2,  "tier":"rare"},
    "💜 پرگاست":          {"hp":672, "dmg":102, "xp":65, "zen":55, "weak":"مقدس",   "drop_chance":0.18, "tier":"epic"},
    "🖤 اومبراک":     {"hp":798, "dmg":108, "xp":72, "zen":60, "weak":"نور",    "drop_chance":0.15, "tier":"epic"},
    "🌌 دوالگاث، بلعنده‌ی ستارگان":          {"hp":1092, "dmg":126, "xp":90, "zen":75, "weak":"نور",    "drop_chance":0.12, "tier":"epic"},
    # Emberhollow
    "🦎 پیروک":     {"hp":672, "dmg":96, "xp":65, "zen":55, "weak":"یخ",     "drop_chance":0.2,  "tier":"rare"},
    "🔥 ماگموث":          {"hp":840, "dmg":84, "xp":58, "zen":48, "weak":"یخ",     "drop_chance":0.15, "tier":"rare"},
    "💀 چارکون":     {"hp":126,  "dmg":22, "xp":35, "zen":28, "weak":"آب",     "drop_chance":0.3,  "tier":"common"},
    "🌋 بازالتور":          {"hp":714, "dmg":90, "xp":60, "zen":50, "weak":"یخ",     "drop_chance":0.2,  "tier":"rare"},
    "🔴 اخگرک":         {"hp":112,  "dmg":24, "xp":30, "zen":24, "weak":"آب",     "drop_chance":0.3,  "tier":"common"},
    "🦂 سیندراک":          {"hp":461, "dmg":84, "xp":40, "zen":32, "weak":"یخ",     "drop_chance":0.25, "tier":"rare"},
    "👿 ایگناروث، کوره‌شیطان":            {"hp":1007, "dmg":114, "xp":80, "zen":65, "weak":"یخ",     "drop_chance":0.15, "tier":"epic"},
    "🌪️ پیروکین":        {"hp":546, "dmg":78, "xp":48, "zen":40, "weak":"آب",     "drop_chance":0.22, "tier":"rare"},
    "🐍 شراره‌مار":         {"hp":140, "dmg":26, "xp":38, "zen":30, "weak":"یخ",     "drop_chance":0.28, "tier":"common"},
    # Dragonnest Peaks
    "🐉 درایکو":     {"hp":1260, "dmg":150, "xp":120,"zen":100,"weak":"یخ",     "drop_chance":0.15, "tier":"epic"},
    "🦅 تالون‌گارد":         {"hp":756, "dmg":114, "xp":80, "zen":65, "weak":"برق",    "drop_chance":0.2,  "tier":"rare"},
    "💎 کریستالیون":  {"hp":1680, "dmg":195, "xp":200,"zen":180,"weak":"خلأ",    "drop_chance":0.08, "tier":"legendary"},
    "👑 وایرمگدون، شاهِ اژدها":     {"hp":2520, "dmg":240, "xp":300,"zen":250,"weak":"مقدس",   "drop_chance":0.05, "tier":"legendary"},
    "🔥 اینفرناکس":       {"hp":1470, "dmg":174, "xp":150,"zen":130,"weak":"یخ",     "drop_chance":0.1,  "tier":"epic"},
    "❄️ گلیشیوس":        {"hp":1344, "dmg":156, "xp":130,"zen":110,"weak":"آتش",    "drop_chance":0.12, "tier":"epic"},
    "⚡ تندرفنگ":     {"hp":1428, "dmg":180, "xp":160,"zen":140,"weak":"زمین",   "drop_chance":0.1,  "tier":"legendary"},
    "🐲 پریمورداکس":   {"hp":2100, "dmg":216, "xp":250,"zen":220,"weak":"خلأ",    "drop_chance":0.07, "tier":"legendary"},
    "🦴 بونوراث":      {"hp":923, "dmg":120, "xp":90, "zen":75, "weak":"مقدس",   "drop_chance":0.18, "tier":"epic"},
    # Ruins of Orion-7
    "🤖 سنتری-۷":     {"hp":588, "dmg":78, "xp":48, "zen":40, "weak":"برق",    "drop_chance":0.25, "tier":"rare"},
    "⚙️ آیرون‌کور":         {"hp":923, "dmg":105, "xp":75, "zen":60, "weak":"برق",    "drop_chance":0.15, "tier":"rare"},
    "🔫 گان‌درون": {"hp":420, "dmg":120, "xp":60, "zen":50, "weak":"خلأ",    "drop_chance":0.2,  "tier":"rare"},
    "🛸 هاوک‌یونیت":       {"hp":714, "dmg":96, "xp":65, "zen":55, "weak":"برق",    "drop_chance":0.2,  "tier":"rare"},
    "💡 لومینکس":     {"hp":546, "dmg":114, "xp":58, "zen":48, "weak":"خلأ",    "drop_chance":0.22, "tier":"rare"},
    "🖥️ زیرو-وان، هسته‌ی سرکش":{"hp":1176, "dmg":135, "xp":110,"zen":90, "weak":"برق",    "drop_chance":0.12, "tier":"epic"},
    "🔧 فیکس‌بات":    {"hp":126,  "dmg":18, "xp":28, "zen":22, "weak":"آب",     "drop_chance":0.3,  "tier":"common"},
    "💣 مکاماین":        {"hp":251,  "dmg":165, "xp":40, "zen":35, "weak":"یخ",     "drop_chance":0.25, "tier":"rare"},
    "🛡️ گاردکس":   {"hp":840, "dmg":90, "xp":70, "zen":58, "weak":"برق",    "drop_chance":0.18, "tier":"rare"},
    # Dreadgate Citadel
    "💀 کاراون":      {"hp":672, "dmg":90, "xp":55, "zen":45, "weak":"مقدس",   "drop_chance":0.25, "tier":"rare"},
    "👹 بلاک‌هورن":    {"hp":1176, "dmg":144, "xp":110,"zen":90, "weak":"مقدس",   "drop_chance":0.12, "tier":"epic"},
    "😈 مالفوراث، ارباب دروازه":    {"hp":2100, "dmg":210, "xp":250,"zen":200,"weak":"نور",    "drop_chance":0.06, "tier":"legendary"},
    "🧟 روتلینگ":      {"hp":167, "dmg":24, "xp":38, "zen":30, "weak":"مقدس",   "drop_chance":0.28, "tier":"common"},
    "⛓️ چین‌گارد":           {"hp":588, "dmg":84, "xp":45, "zen":38, "weak":"آتش",    "drop_chance":0.25, "tier":"rare"},
    "💀 زوال‌شوالیه":      {"hp":923, "dmg":120, "xp":80, "zen":65, "weak":"مقدس",   "drop_chance":0.18, "tier":"epic"},
    "🕸️ تارک":      {"hp":140, "dmg":22, "xp":32, "zen":26, "weak":"آتش",    "drop_chance":0.3,  "tier":"common"},
    "👻 کاسلوریث":          {"hp":630, "dmg":96, "xp":55, "zen":45, "weak":"مقدس",   "drop_chance":0.22, "tier":"rare"},
    "🦇 دوزخ‌بال":       {"hp":112,  "dmg":20, "xp":28, "zen":22, "weak":"نور",    "drop_chance":0.3,  "tier":"common"},
    # Stormward Archipelago
    "🏴‍☠️ بارک‌هوک":    {"hp":167, "dmg":22, "xp":38, "zen":30, "weak":"برق",    "drop_chance":0.3,  "tier":"common"},
    "⚡ زاکار، طوفان‌زده":        {"hp":630, "dmg":105, "xp":65, "zen":55, "weak":"زمین",   "drop_chance":0.2,  "tier":"rare"},
    "🌩️ ولتاراک":      {"hp":840, "dmg":135, "xp":90, "zen":75, "weak":"زمین",   "drop_chance":0.15, "tier":"epic"},
    "🦜 اسکورک":        {"hp":98,  "dmg":16, "xp":22, "zen":18, "weak":"برق",    "drop_chance":0.35, "tier":"common"},
    "🌊 موج‌روان":          {"hp":672, "dmg":90, "xp":60, "zen":50, "weak":"زمین",   "drop_chance":0.22, "tier":"rare"},
    "⚓ ناخدا زنگار":       {"hp":1007, "dmg":126, "xp":95, "zen":80, "weak":"مقدس",   "drop_chance":0.15, "tier":"epic"},
    "🦈 توفان‌باله":      {"hp":756, "dmg":108, "xp":72, "zen":60, "weak":"برق",    "drop_chance":0.2,  "tier":"rare"},
    "🐊 نمک‌آرواره":        {"hp":840, "dmg":102, "xp":70, "zen":58, "weak":"برق",    "drop_chance":0.18, "tier":"rare"},
    # Holy Luminarchy
    "😇 سرافیل، سرافِ تیره":  {"hp":756, "dmg":120, "xp":80, "zen":70, "weak":"تاریکی", "drop_chance":0.2,  "tier":"rare"},
    "⚔️ لومینارک":     {"hp":1050, "dmg":135, "xp":100,"zen":85, "weak":"خلأ",    "drop_chance":0.15, "tier":"epic"},
    "👼 گابریون، نگهبانِ درگاه":     {"hp":1680, "dmg":180, "xp":180,"zen":150,"weak":"تاریکی", "drop_chance":0.08, "tier":"legendary"},
    "🕊️ نوربال":        {"hp":112,  "dmg":18, "xp":28, "zen":22, "weak":"تاریکی", "drop_chance":0.3,  "tier":"common"},
    "🧙 کورویس، راهبِ گمراه":      {"hp":672, "dmg":105, "xp":65, "zen":55, "weak":"خلأ",    "drop_chance":0.22, "tier":"rare"},
    "✨ درخشا":          {"hp":546, "dmg":84, "xp":50, "zen":42, "weak":"تاریکی", "drop_chance":0.25, "tier":"rare"},
    "🛡️ سپرِ تابان":      {"hp":923, "dmg":114, "xp":85, "zen":70, "weak":"خلأ",    "drop_chance":0.18, "tier":"epic"},
    "⚡ تندرِ مقدس":        {"hp":714, "dmg":132, "xp":75, "zen":62, "weak":"تاریکی", "drop_chance":0.2,  "tier":"rare"},
    # Clockwork Depths
    "⚙️ کاگ‌ورک":   {"hp":153, "dmg":20, "xp":32, "zen":25, "weak":"آب",     "drop_chance":0.3,  "tier":"common"},
    "💣 تیک‌تاک‌ماین":     {"hp":251,  "dmg":165, "xp":40, "zen":35, "weak":"یخ",     "drop_chance":0.25, "tier":"rare"},
    "🔩 کلاسوسِ فولادی":      {"hp":1260, "dmg":126, "xp":90, "zen":75, "weak":"برق",    "drop_chance":0.12, "tier":"epic"},
    "🔨 همرگیر":         {"hp":630, "dmg":96, "xp":55, "zen":45, "weak":"آب",     "drop_chance":0.22, "tier":"rare"},
    "⛏️ دریل‌بات":     {"hp":126,  "dmg":22, "xp":30, "zen":24, "weak":"آب",     "drop_chance":0.3,  "tier":"common"},
    "🔬 آزمونگر":   {"hp":503, "dmg":84, "xp":42, "zen":35, "weak":"برق",    "drop_chance":0.25, "tier":"rare"},
    "💥 کاتاپولترون":  {"hp":336,  "dmg":135, "xp":38, "zen":32, "weak":"آب",     "drop_chance":0.28, "tier":"rare"},
    # Azure Tides Empire
    "🦈 زره‌باله": {"hp":160, "dmg":18, "xp":30, "zen":24, "weak":"برق", "drop_chance":0.22, "tier":"rare"},
    "🐙 کراکن‌لینگ": {"hp":170, "dmg":19, "xp":32, "zen":25, "weak":"برق", "drop_chance":0.2, "tier":"rare"},
    "🐋 لویاثانِ کهن، مویرا": {"hp":180, "dmg":20, "xp":35, "zen":28, "weak":"برق", "drop_chance":0.18, "tier":"legendary"},
    "🐚 صدف‌گرد":     {"hp":112,  "dmg":14, "xp":22, "zen":18, "weak":"برق",    "drop_chance":0.35, "tier":"common"},
    "🦭 فُک‌بان":          {"hp":182, "dmg":26, "xp":45, "zen":38, "weak":"برق",    "drop_chance":0.25, "tier":"common"},
    "🐡 بادکنک":     {"hp":98,  "dmg":35, "xp":30, "zen":25, "weak":"یخ",     "drop_chance":0.3,  "tier":"common"},
    "🦑 تایتانِ جوهر":    {"hp":923, "dmg":102, "xp":78, "zen":63, "weak":"برق",    "drop_chance":0.18, "tier":"rare"},
    "🐊 بریناو":     {"hp":672, "dmg":90, "xp":55, "zen":45, "weak":"برق",    "drop_chance":0.22, "tier":"rare"},
    # The Sunken City
    "🐠 آبتاب":    {"hp":126,  "dmg":18, "xp":28, "zen":22, "weak":"برق",    "drop_chance":0.3,  "tier":"common"},
    "🦀 کلوراک":       {"hp":923, "dmg":105, "xp":70, "zen":58, "weak":"آتش",    "drop_chance":0.18, "tier":"rare"},
    "🌿 جلبک‌پیچ":       {"hp":182, "dmg":22, "xp":40, "zen":32, "weak":"آتش",    "drop_chance":0.25, "tier":"common"},
    "👻 دراون‌سول":      {"hp":630, "dmg":84, "xp":52, "zen":42, "weak":"مقدس",   "drop_chance":0.22, "tier":"rare"},
    "🐡 فلس‌درخشان":      {"hp":112,  "dmg":16, "xp":24, "zen":19, "weak":"تاریکی", "drop_chance":0.32, "tier":"common"},
    "🦈 آرواره‌ی کهن":     {"hp":1007, "dmg":120, "xp":85, "zen":70, "weak":"برق",    "drop_chance":0.15, "tier":"epic"},
    "🌊 موج‌زاد":       {"hp":714, "dmg":90, "xp":60, "zen":50, "weak":"زمین",   "drop_chance":0.2,  "tier":"rare"},
    "🐙 آتلانتراک": {"hp":1260, "dmg":135, "xp":110,"zen":90, "weak":"برق",    "drop_chance":0.12, "tier":"epic"},
    # Sands of Eternity
    "🦂 نیشِ زرین": {"hp":150, "dmg":17, "xp":28, "zen":22, "weak":"یخ", "drop_chance":0.25, "tier":"rare"},
    "🏺 سرکوفاگون": {"hp":165, "dmg":18, "xp":30, "zen":24, "weak":"خلأ", "drop_chance":0.2, "tier":"epic"},
    "🌪️ شن‌روان": {"hp":155, "dmg":17, "xp":29, "zen":23, "weak":"زمین", "drop_chance":0.22, "tier":"rare"},
    "🐍 شن‌مار":           {"hp":140, "dmg":24, "xp":35, "zen":28, "weak":"یخ",     "drop_chance":0.28, "tier":"common"},
    "🦁 نیشِ کویر":         {"hp":840, "dmg":114, "xp":75, "zen":62, "weak":"آب",     "drop_chance":0.2,  "tier":"rare"},
    "👁️ رعشم":        {"hp":672, "dmg":96, "xp":60, "zen":50, "weak":"نور",    "drop_chance":0.22, "tier":"rare"},
    "🏜️ کرمِ دیوان":      {"hp":1176, "dmg":126, "xp":100,"zen":85, "weak":"آب",     "drop_chance":0.15, "tier":"epic"},
    "💀 سارکوباند":     {"hp":714, "dmg":90, "xp":62, "zen":52, "weak":"آتش",    "drop_chance":0.2,  "tier":"rare"},
    "🦅 بازِ کویر":        {"hp":167, "dmg":25, "xp":42, "zen":34, "weak":"برق",    "drop_chance":0.25, "tier":"common"},
    # Celestial Spire
    "🌟 اترون":      {"hp":840, "dmg":126, "xp":90, "zen":75, "weak":"تاریکی", "drop_chance":0.18, "tier":"epic"},
    "💫 استلاریس":      {"hp":672, "dmg":105, "xp":70, "zen":58, "weak":"خلأ",    "drop_chance":0.2,  "tier":"rare"},
    "🔮 آرکانوس":      {"hp":1470, "dmg":174, "xp":160,"zen":130,"weak":"برق",    "drop_chance":0.1,  "tier":"legendary"},
    "☁️ نیمبوراک":         {"hp":588, "dmg":84, "xp":50, "zen":42, "weak":"برق",    "drop_chance":0.25, "tier":"rare"},
    "🌈 پریزمال":          {"hp":503, "dmg":96, "xp":45, "zen":38, "weak":"تاریکی", "drop_chance":0.28, "tier":"rare"},
    "⭐ میتئوراک":        {"hp":756, "dmg":114, "xp":72, "zen":60, "weak":"زمین",   "drop_chance":0.2,  "tier":"epic"},
    "🌙 لوناروح":           {"hp":672, "dmg":90, "xp":60, "zen":50, "weak":"آتش",    "drop_chance":0.22, "tier":"rare"},
    "🌌 گلکسیون":      {"hp":1680, "dmg":180, "xp":180,"zen":150,"weak":"خلأ",    "drop_chance":0.08, "tier":"legendary"},
    # Abyssal Black Market
    "🕵️ پنجه‌ی چابک":       {"hp":140, "dmg":25, "xp":35, "zen":30, "weak":"برق",    "drop_chance":0.35, "tier":"common"},
    "🗡️ خنجرِ اجیر، مورگات":      {"hp":714, "dmg":120, "xp":70, "zen":60, "weak":"نور",    "drop_chance":0.2,  "tier":"rare"},
    "🌑 سایه‌ارباب، نایراث":         {"hp":1050, "dmg":150, "xp":110,"zen":90, "weak":"نور",    "drop_chance":0.12, "tier":"epic"},
    "🎭 نقاب‌دار، دوروک":          {"hp":167, "dmg":28, "xp":42, "zen":35, "weak":"برق",    "drop_chance":0.28, "tier":"common"},
    "💼 واسطه‌ی مار، سیلوک":      {"hp":588, "dmg":96, "xp":52, "zen":44, "weak":"مقدس",   "drop_chance":0.25, "tier":"rare"},
    "🔪 لاتِ کوچه":      {"hp":126,  "dmg":22, "xp":30, "zen":24, "weak":"نور",    "drop_chance":0.32, "tier":"common"},
    "🧪 زهرگر، وایپرا":      {"hp":153, "dmg":30, "xp":38, "zen":32, "weak":"یخ",     "drop_chance":0.28, "tier":"common"},

    # ══════════════ 👑 Throne of Oblivion (نقشه‌ی جدید — خیلی خیلی سخت) ══════════════
    # 🆕 مپِ نایتمر: HP/دمیج به‌مراتب بالاتر از سقفِ قبلیِ بازی (که ~۲۵۰۰ HP بود) —
    # طبقِ درخواستِ صریح، این مپ باید واقعاً و به‌شدت سخت باشه؛ در ازاش لوتش (پایین‌تر
    # تو MAP_LOOT اقتصادی) از هر مپِ دیگه‌ای بهتره.
    "🩻 استخوان‌آور": {"hp":650000, "dmg":220, "xp":140, "zen":120, "weak":"مقدس", "drop_chance":0.25, "tier":"epic"},
    "🕯️ شمعِ سیاه، خاموش‌گر": {"hp":900000, "dmg":260, "xp":170, "zen":150, "weak":"نور", "drop_chance":0.2, "tier":"epic"},
    "⚰️ نگهبانِ تابوتِ شاهی": {"hp":1400000, "dmg":310, "xp":220, "zen":190, "weak":"برق", "drop_chance":0.15, "tier":"legendary"},
    "👑 تاجِ فراموش‌شده، ارباب": {"hp":2200000, "dmg":380, "xp":300, "zen":260, "weak":"خلأ", "drop_chance":0.1, "tier":"legendary"},
    "🖤 روحِ سرکش، مالاگورث": {"hp":3500000, "dmg":440, "xp":380, "zen":330, "weak":"مقدس", "drop_chance":0.06, "tier":"legendary"},
    "💀 اُبلیویون، پادشاهِ خاکسترها": {"hp":5000000, "dmg":520, "xp":520, "zen":450, "weak":"نور", "drop_chance":0.03, "tier":"legendary"},
    "⛓️ زنجیرِ ابدیت": {"hp":750000, "dmg":240, "xp":150, "zen":130, "weak":"آتش", "drop_chance":0.22, "tier":"epic"},
    "🌫️ سایه‌ی بی‌نام": {"hp":550000, "dmg":210, "xp":130, "zen":110, "weak":"مقدس", "drop_chance":0.28, "tier":"epic"},
}

MAP_ENEMIES = {
    "Verdant Vale": ["🐗 کاراگ","🌳 روتگار","🍄 وبازاد","🦋 مورنا","🌺 زهرگل، دهانِ سبز","🐍 سیثرا","🦎 دراگیل","🐝 زیمبا","🦅 کورواک","🐻 دِرگون، پیرِ جنگل","🌿 ویندرا","🍃 سیلوان، پژواکِ برگ"],
    "Frostheim": ["🐺 فِنراک","❄️ بورگاث","🦊 اسکا","🧊 زمهریر، دلِ یخ","🐻‍❄️ گروم‌زوزه","🌨️ وایترا","🦌 کریستان","⛄ یارموث","🧟 کالگار","❄️ پریزماک"],
    "Voidbreak Wastes": ["👁️ زیراکس","🌑 نول‌گاست","💀 وخشوران","🕳️ آبادون، دهانِ هیچ","👾 کای‌مورگ","🌀 ورتیگون","💜 پرگاست","🖤 اومبراک","🌌 دوالگاث، بلعنده‌ی ستارگان"],
    "Emberhollow": ["🦎 پیروک","🔥 ماگموث","💀 چارکون","🌋 بازالتور","🔴 اخگرک","🦂 سیندراک","👿 ایگناروث، کوره‌شیطان","🌪️ پیروکین","🐍 شراره‌مار"],
    "Dragonnest Peaks": ["🐉 درایکو","🦅 تالون‌گارد","💎 کریستالیون","👑 وایرمگدون، شاهِ اژدها","🔥 اینفرناکس","❄️ گلیشیوس","⚡ تندرفنگ","🐲 پریمورداکس","🦴 بونوراث"],
    "Ruins of Orion-7": ["🤖 سنتری-۷","⚙️ آیرون‌کور","🔫 گان‌درون","🛸 هاوک‌یونیت","💡 لومینکس","🖥️ زیرو-وان، هسته‌ی سرکش","🔧 فیکس‌بات","💣 مکاماین","🛡️ گاردکس"],
    "Dreadgate Citadel": ["💀 کاراون","👹 بلاک‌هورن","😈 مالفوراث، ارباب دروازه","🧟 روتلینگ","⛓️ چین‌گارد","💀 زوال‌شوالیه","🕸️ تارک","👻 کاسلوریث","🦇 دوزخ‌بال"],
    "Stormward Archipelago": ["🏴‍☠️ بارک‌هوک","⚡ زاکار، طوفان‌زده","🌩️ ولتاراک","🦜 اسکورک","🌊 موج‌روان","⚓ ناخدا زنگار","🦈 توفان‌باله","🐊 نمک‌آرواره"],
    "Holy Luminarchy": ["😇 سرافیل، سرافِ تیره","⚔️ لومینارک","👼 گابریون، نگهبانِ درگاه","🕊️ نوربال","🧙 کورویس، راهبِ گمراه","✨ درخشا","🛡️ سپرِ تابان","⚡ تندرِ مقدس"],
    "Clockwork Depths": ["⚙️ کاگ‌ورک","💣 تیک‌تاک‌ماین","🔩 کلاسوسِ فولادی","🔨 همرگیر","⛏️ دریل‌بات","🔬 آزمونگر","💥 کاتاپولترون"],
    "Azure Tides Empire": ["🦈 زره‌باله","🐙 کراکن‌لینگ","🐋 لویاثانِ کهن، مویرا","🐚 صدف‌گرد","🦭 فُک‌بان","🐡 بادکنک","🦑 تایتانِ جوهر","🐊 بریناو"],
    "The Sunken City": ["🐠 آبتاب","🦀 کلوراک","🌿 جلبک‌پیچ","👻 دراون‌سول","🐡 فلس‌درخشان","🦈 آرواره‌ی کهن","🌊 موج‌زاد","🐙 آتلانتراک"],
    "Sands of Eternity": ["🦂 نیشِ زرین","🏺 سرکوفاگون","🌪️ شن‌روان","🐍 شن‌مار","🦁 نیشِ کویر","👁️ رعشم","🏜️ کرمِ دیوان","💀 سارکوباند","🦅 بازِ کویر"],
    "Celestial Spire": ["🌟 اترون","💫 استلاریس","🔮 آرکانوس","☁️ نیمبوراک","🌈 پریزمال","⭐ میتئوراک","🌙 لوناروح","🌌 گلکسیون"],
    "Abyssal Black Market": ["🕵️ پنجه‌ی چابک","🗡️ خنجرِ اجیر، مورگات","🌑 سایه‌ارباب، نایراث","🎭 نقاب‌دار، دوروک","💼 واسطه‌ی مار، سیلوک","🔪 لاتِ کوچه","🧪 زهرگر، وایپرا"],
    "Throne of Oblivion": ["🩻 استخوان‌آور","🕯️ شمعِ سیاه، خاموش‌گر","⚰️ نگهبانِ تابوتِ شاهی","👑 تاجِ فراموش‌شده، ارباب","🖤 روحِ سرکش، مالاگورث","💀 اُبلیویون، پادشاهِ خاکسترها","⛓️ زنجیرِ ابدیت","🌫️ سایه‌ی بی‌نام"],
}

# ─── Mob Abilities (mob_abilities.py) ──────────────────────────
# هر دشمنِ بالا الان یه ability واقعی می‌گیره (زهرآگین/خون‌آشام/خشم/
# پوست زره‌ای/خاردار/خودترمیم‌گر/ضربه‌ی دوگانه/نگاه نفرین‌شده/
# زره‌پوش آهنین/شکارچی کمین‌گر) — مکانیک‌هاش تو calc_combat پایین
# و تو mob_combat.py واقعاً اثر می‌ذارن، نه فقط تو متن.
import mob_abilities
mob_abilities.assign_abilities(ENEMIES)

# ─── Attack Types ────────────────────────────────────────────

# حالت سخت وحشتناک: شانس کریت پایه‌ی هر نوع حمله یک‌چهارم شد (سخت‌تر از قبل)
ATTACK_TYPES = {
    "quick":    {"name":"⚡ حمله سریع",   "cooldown":10, "dmg_mult":0.8,  "crit":round(0.10/4,4), "desc":"سریع ولی ضعیف‌تر"},
    "heavy":    {"name":"💥 حمله قوی",    "cooldown":30, "dmg_mult":1.5,  "crit":round(0.15/4,4), "desc":"قوی ولی کندتر — سپر دشمن رو می‌شکنه"},
    "element":  {"name":"🌀 حمله عنصری", "cooldown":20, "dmg_mult":1.2,  "crit":round(0.20/4,4), "desc":"اثر عنصری ویژه"},
    "combo":    {"name":"🔥 حمله کومبو",  "cooldown":15, "dmg_mult":2.0,  "crit":round(0.25/4,4), "desc":"فقط با combo بالا"},
    # نکته: این حمله فقط وقتی که rage/ultimate gauge (بازیکن) پره فعاله؛
    # قفل‌شدنش تو combat_handlers.py مثل قفل combo چک می‌شه.
    "ultimate": {"name":"☄️ ضربه نهایی",  "cooldown":45, "dmg_mult":3.2,  "crit":round(0.35/4,4), "desc":"فقط با rage پر — نادیده‌گیری بخشی از armor دشمن"},
    # 🆕 پری/کانتر تایمینگ‌محور (combat_parry.py): دمیجِ پایه‌ش عمداً کمه چون
    # ارزشِ واقعیش تو نتیجه‌ی تایمینگه، نه تو دمیجِ خودِ calc_combat.
    "parry":    {"name":"🛡️ پری/کانتر",   "cooldown":18, "dmg_mult":0.6,  "crit":round(0.10/4,4), "desc":"ریسک بالا-پاداش بالا — اگه سریع بزنی، ضدحمله‌ی دشمن رو کامل خنثی می‌کنی و کانترِ قوی می‌زنی"},
}

# ─── Status Effects ──────────────────────────────────────────

STATUSES = {
    "bleed":   {"emoji":"🩸","name":"خونریزی", "dmg":8,  "turns":3},
    "burn":    {"emoji":"🔥","name":"سوختگی",  "dmg":12, "turns":2},
    "poison":  {"emoji":"☠️","name":"زهر",     "dmg":6,  "turns":4},
    "stun":    {"emoji":"⚡","name":"بیهوشی",  "dmg":0,  "turns":1},
    "freeze":  {"emoji":"❄️","name":"انجماد",  "dmg":0,  "turns":1},
    "weaken":  {"emoji":"💔","name":"ضعف",     "dmg":4,  "turns":3},
}

ELEMENT_STATUS = {
    "سم": "poison", "خون": "bleed", "آتش": "burn",
    "ماگما": "burn", "آتشفشان": "burn", "برق": "stun",
    "صاعقه": "stun", "یخ": "freeze", "برف": "freeze",
    "وحشت": "weaken", "نفرین": "weaken",
}

# ─── Drop Items ──────────────────────────────────────────────

ENEMY_DROPS = {
    "common":    [
        {"name":"Bone Fragment","emoji":"🦴","sell":30},
        {"name":"Monster Scale","emoji":"🐉","sell":50},
        {"name":"Dark Shard","emoji":"⬛","sell":40},
        {"name":"Wild Herb","emoji":"🌿","sell":25},
        {"name":"Claw","emoji":"🦞","sell":35},
    ],
    "rare":      [
        {"name":"Rare Core","emoji":"💠","sell":200},
        {"name":"Enchanted Fang","emoji":"🗡️","sell":280},
        {"name":"Storm Essence","emoji":"⚡","sell":250},
        {"name":"Shadow Dust","emoji":"🌑","sell":220},
        {"name":"Crystal Heart","emoji":"💎","sell":350},
    ],
    "epic":      [
        {"name":"Epic Soul","emoji":"💜","sell":1000},
        {"name":"Void Fragment","emoji":"🌌","sell":1200},
        {"name":"Dragon Tear","emoji":"🐲","sell":1500},
        {"name":"Abyss Crystal","emoji":"🔮","sell":1100},
        {"name":"Ancient Rune","emoji":"📿","sell":1300},
    ],
    "legendary": [
        {"name":"Legendary Essence","emoji":"✨","sell":5000},
        {"name":"God Shard","emoji":"👑","sell":8000},
        {"name":"Soul Stone Fragment","emoji":"💎","sell":6000},
        {"name":"Void Heart Shard","emoji":"💜","sell":7000},
    ],
}

# ─── Combat Calculations ─────────────────────────────────────

def get_map_enemies(map_name: str, count: int = 3) -> list[dict]:
    pool = MAP_ENEMIES.get(map_name, list(ENEMIES.keys())[:5])
    selected = random.sample(pool, min(count, len(pool)))
    result = []
    for name in selected:
        data = ENEMIES.get(name, {}).copy()
        data["name"] = name
        # Scale HP/DMG slightly randomly
        data["hp"]  = int(data["hp"]  * random.uniform(0.9, 1.2))
        data["dmg"] = int(data["dmg"] * random.uniform(0.9, 1.15))
        result.append(data)
    return result

def calc_combat(player: dict, enemy: dict, attack_type: str) -> dict:
    from characters import ALL_CHARACTERS
    is_adventurer = bool(player.get("character"))
    char = ALL_CHARACTERS.get(player.get("character", ""), {}) if is_adventurer else {}

    # ─── Base damage: منبعش برای هر کلاس فرق می‌کنه ───────────────
    # ماجراجو: مثلِ قبل از base_dmg هویتِ کاتانا (۹ تا ۲۱، بسته به rarity).
    # سه کلاسِ دیگه: از atk کلاسِ خودشون (class_system.py) که موقعِ
    # ساختِ کاراکتر روی player["stats"] نشست.
    if is_adventurer:
        base_dmg = char.get("base_dmg", 12)
    else:
        base_dmg = (player.get("stats") or {}).get("atk", 10)

    level_bonus = player.get("level", 1) * 3
    katana_lv   = player.get("katana_level", 1)

    # ─── بونوس‌های کاتانا (فورج + Soul/Awakening/Bond) — این‌ها فقط
    # برای ماجراجو معنا دارن چون فقط اون کاتانا داره. برای بقیه‌ی
    # کلاس‌ها صفر می‌مونن؛ دیگه به‌جاش هرکلاس بونوسِ خودش رو داره
    # (پایین‌تر، بخشِ «بونوسِ کلاس‌محور»).
    katana_bonus = katana_crit_add = katana_lifesteal = katana_elem_amp = 0
    katana_soul_dmg_mult = 1.0
    relic_defense_pct = 0.0
    # ─── باگ‌فیکسِ حیاتی: kcore قبلاً فقط داخلِ if is_adventurer تعریف
    # می‌شد ولی پایین‌تر (تایرِ Legendary/Mythic کاتانا) بدونِ قید صدا
    # زده می‌شد → برای سه کلاسِ غیر-ماجراجو با NameError کرش می‌کرد و
    # عملاً هیچ حمله‌ای براشون کار نمی‌کرد. حالا همیشه یه مقدارِ
    # پیش‌فرضِ بی‌اثر داره و فقط برای ماجراجو واقعی پر می‌شه.
    kcore = {"crit": 0, "lifesteal": 0, "dmg_mult": 1.0, "dmg_mult_flat": 0.0,
              "special": None, "special_active": False, "skills": {}}
    if is_adventurer:
        # 🆕 باگ‌فیکس: هر کدوم از این بلوک‌ها (فورجِ کاتانا/Soul-Awakening-Bond/
        # رلیک‌های کلاس) قبلاً بدونِ try/except صدا زده می‌شدن — اگه دیتای
        # ذخیره‌شده‌ی یه بازیکنِ خاص (مثلاً یه کاراکترِ قدیمی یا رکوردِ
        # ناقص) با یکی از این توابع جور درنمی‌اومد، کلِ حمله با یه
        # اکسپشنِ کنترل‌نشده کرش می‌کرد و کاربر فقط پیامِ عمومیِ «یه
        # مشکلی پیش اومد» رو می‌دید. حالا هر بلوک جدا محافظت می‌شه؛
        # اگه یکی خطا بده، فقط همون بونوس صفر می‌مونه و بقیه‌ی حمله
        # عادی ادامه پیدا می‌کنه (به‌جای این‌که کلِ نبرد کرش کنه).
        try:
            from katana_system import crit_bonus as katana_crit_bonus, \
                lifesteal_bonus as katana_lifesteal_bonus, \
                element_amplify_bonus as katana_element_amplify_bonus
            from economy import KATANA_LEVELS
            katana_bonus     = KATANA_LEVELS.get(katana_lv, {}).get("dmg", 0)
            katana_crit_add  = katana_crit_bonus(katana_lv)
            katana_lifesteal = katana_lifesteal_bonus(katana_lv)
            katana_elem_amp  = katana_element_amplify_bonus(katana_lv)
        except Exception as e:
            log_sync(f"⚠️ calc_combat: خطا تو بونوسِ فورجِ کاتانا (uid={player.get('id')}): {type(e).__name__}: {e}", "ERROR")

        # ─── Katana Soul / Awakening / Bond (katana_core.py) ──────
        # لایه‌ی جدید و مستقل روی فورج قدیمی — اضافه می‌شه، جایگزینش نمی‌کنه.
        try:
            from katana_core import calc_katana_bonus
            kcore = calc_katana_bonus(player)
            katana_crit_add  += kcore["crit"]
            katana_lifesteal += kcore["lifesteal"]
            katana_soul_dmg_mult = kcore["dmg_mult"] + kcore["dmg_mult_flat"]
        except Exception as e:
            log_sync(f"⚠️ calc_combat: خطا تو Katana Soul/Awakening/Bond (uid={player.get('id')}): {type(e).__name__}: {e}", "ERROR")

        # 🗺️ رلیک‌های جمع‌شده (Stage 3 — class_abilities.py) هرکدوم اثرِ
        # خودشونو دارن (قبلاً همه فقط دمیجِ یکسان می‌دادن — الان دمیج/
        # کریت/لایف‌استیل روی حمله می‌شینه، دفاع پایین‌تر کنارِ محاسبه‌ی
        # ضدحمله اعمال می‌شه).
        try:
            from class_abilities import adventurer_relic_bonuses
            relic_b = adventurer_relic_bonuses(player)
            katana_bonus     += relic_b["dmg_flat"]
            katana_crit_add  += relic_b["crit_pct"]
            katana_lifesteal += relic_b["lifesteal_pct"]
            relic_defense_pct = relic_b["defense_pct"]
        except Exception as e:
            log_sync(f"⚠️ calc_combat: خطا تو رلیک‌های ماجراجو (uid={player.get('id')}): {type(e).__name__}: {e}", "ERROR")

    # ─── بونوسِ کلاس‌محور — جادوگر/تاجر/درمانگر ────────────────────
    # Stage 2: مکانیزمِ پسیوِ هر کلاس تو نبردِ خام. Stage 3: فلوی تعاملیِ
    # واقعی (class_abilities.py + class_ability_handlers.py) رو هم اینجا
    # وصل می‌کنیم — طلسمِ ترکیبیِ جادوگر (فلگِ مصرفی)، سپرهای مانا/الهی
    # (چک‌شون پایین‌تر، کنارِ محاسبه‌ی ضدحمله‌ست).
    class_crit_add = class_dmg_mult_add = class_lifesteal = 0.0
    player_class = player.get("class")
    wizard_spell_charge = False
    if player_class == "wizard":
        # High Burst Damage: کریت بیشتر و ضریبِ دمیجِ بیشتر (پرنوسان و پرقدرت)
        class_crit_add   = 0.08
        class_dmg_mult_add = 0.15
        # 🔮 طلسمِ ترکیبی (class_abilities.wizard_cast_synergy) — یه‌بار
        # مصرفه: اگه فعال بود، این ضربه دمیجِ اضافه می‌گیره و پایین‌تر
        # (تعیینِ element) تضمین می‌شه که به ضعفِ دشمن بخوره.
        wizard_spell_charge = player.pop("_wizard_spell_charge", False)
        if wizard_spell_charge:
            class_dmg_mult_add += 0.25
    elif player_class == "merchant":
        # Mercenary Call: هر مزدورِ اجیرشده یه دمیجِ فلتِ کوچیک اضافه می‌کنه
        mercs = len(player.get("class_system_data", {}).get("mercenaries_hired", []))
        katana_bonus += min(mercs, 5) * 3
    elif player_class == "healer":
        # Support sustain: بخشی از دمیجِ واردشده به‌صورتِ لایف‌استیل برمی‌گرده
        class_lifesteal = 0.10


    # باف‌های درخت مهارت (skill_tree.py) — همیشه dict کامل با صفر پیش‌فرض برمی‌گرده
    # 🆕 باگ‌فیکس: این بلوک اصلاً try/except نداشت — اگه get_skill_bonuses برای
    # دیتای این بازیکن اکسپشن می‌داد، کلِ نبرد کرش می‌کرد.
    try:
        from skill_tree import get_skill_bonuses
        skb = get_skill_bonuses(player)
    except Exception as e:
        log_sync(f"⚠️ calc_combat: خطا تو skill_tree (uid={player.get('id')}): {type(e).__name__}: {e}", "ERROR")
        skb = {"dmg_pct": 0, "crit_chance": 0, "elem_amp": 0}

    # ─── باگ‌فیکس: ست‌ها (loot_engine.py) محاسبه می‌شدن ولی هیچ‌وقت به
    # combat.py وصل نشده بودن — «افکت ست‌ها کار نمیکنه» دقیقاً همین بود.
    # 🆕 باگ‌فیکس ۲: قبلاً فقط ImportError گرفته می‌شد؛ هر اکسپشنِ دیگه‌ای
    # (مثلاً دیتای ناقصِ همون بازیکن) کرش می‌کرد. حالا هر خطایی گرفته می‌شه.
    try:
        from loot_engine import get_set_bonus_stats
        setb = get_set_bonus_stats(player)
    except Exception as e:
        if not isinstance(e, ImportError):
            log_sync(f"⚠️ calc_combat: خطا تو loot_engine ست‌ها (uid={player.get('id')}): {type(e).__name__}: {e}", "ERROR")
        setb = {}

    # ─── مُهرهای الهی (divine_seals.py) — همون کلیدهای setb رو استفاده
    # می‌کنن (crit_pct, dmg_pct, elem_amp, counter_pct, defense_pct,
    # lifesteal_pct)، پس فقط merge می‌شن، نیازی به مسیر جدید نیست.
    try:
        from divine_seals import get_seal_bonus_stats
        for k, v in get_seal_bonus_stats(player).items():
            setb[k] = setb.get(k, 0) + v
    except Exception as e:
        if not isinstance(e, ImportError):
            log_sync(f"⚠️ calc_combat: خطا تو divine_seals (uid={player.get('id')}): {type(e).__name__}: {e}", "ERROR")

    # ─── 🎯 کوئست‌لاینِ حمله (hunt_questline.py) — توانایی‌های دائمیِ باز شده
    # با شکارِ هدف‌دار، دقیقاً مثلِ ست‌ها/مُهرها قاطیِ setb می‌شن.
    try:
        from hunt_questline import get_hunt_bonuses
        for k, v in get_hunt_bonuses(player).items():
            setb[k] = setb.get(k, 0) + v
    except Exception as e:
        if not isinstance(e, ImportError):
            log_sync(f"⚠️ calc_combat: خطا تو hunt_questline (uid={player.get('id')}): {type(e).__name__}: {e}", "ERROR")

    # ─── 🧬 اکسیرِ ذاتِ آبیس (market_questline.py) — بونوسِ دائمیِ
    # حاصل از کوئست‌لاینِ بازار، دقیقاً مثلِ ست‌ها/مُهرها قاطیِ setb می‌شه.
    try:
        from market_questline import get_elixir_bonuses
        for k, v in get_elixir_bonuses(player).items():
            setb[k] = setb.get(k, 0) + v
    except Exception as e:
        if not isinstance(e, ImportError):
            log_sync(f"⚠️ calc_combat: خطا تو market_questline (uid={player.get('id')}): {type(e).__name__}: {e}", "ERROR")

    # ─── 🔗 اتصالِ Item System v2 — افیکسِ آیتم‌های اکیپ‌شده تا الان فقط
    # رو Combat Power (نمایشی) اثر داشت، نه رو دمیجِ واقعی. حالا دقیقاً
    # مثلِ ست‌ها/مُهرها قاطیِ setb می‌شه.
    eqb = {}
    try:
        from item_system import combat_bonus_stats
        eqb = combat_bonus_stats(player)
        for k in ("dmg_pct", "crit_pct", "lifesteal_pct", "defense_pct", "elem_amp"):
            if eqb.get(k):
                setb[k] = setb.get(k, 0) + eqb[k]
    except Exception as e:
        if not isinstance(e, ImportError):
            log_sync(f"⚠️ calc_combat: خطا تو item_system (uid={player.get('id')}): {type(e).__name__}: {e}", "ERROR")
        eqb = {}

    # 🐾 بونوسِ همراه (Pet/Companion) — همون کلیدهایی که بالا استفاده شدن.
    try:
        from pet_system import pet_combat_bonus
        petb = pet_combat_bonus(player)
        for k, v in petb.items():
            eqb[k] = eqb.get(k, 0) + v
            if k in ("dmg_pct", "crit_pct", "lifesteal_pct", "defense_pct"):
                setb[k] = setb.get(k, 0) + v
    except Exception as e:
        if not isinstance(e, ImportError):
            log_sync(f"⚠️ calc_combat: خطا تو pet_system (uid={player.get('id')}): {type(e).__name__}: {e}", "ERROR")

    try:
        from game_data import rebirth_bonuses
        rb = rebirth_bonuses(player)
    except Exception as e:
        log_sync(f"⚠️ calc_combat: خطا تو rebirth_bonuses (uid={player.get('id')}): {type(e).__name__}: {e}", "ERROR")
        rb = {"dmg_pct": 0}

    # پرک گیلد ماجراجویان: دمیج بیشتر تو نبرد PvE
    try:
        from guild_system import get_perk
        guild_dmg_pct = get_perk(player, "pve_dmg_pct")
    except Exception as e:
        log_sync(f"⚠️ calc_combat: خطا تو guild_system (uid={player.get('id')}): {type(e).__name__}: {e}", "ERROR")
        guild_dmg_pct = 0

    combo       = player.get("combo", 0)
    combo_mult  = 1 + (combo * 0.08)
    atk         = ATTACK_TYPES.get(attack_type, ATTACK_TYPES["quick"])
    try:
        from world_pulse import pulse_value as _pulse_val
        _pulse_crit = _pulse_val("crit_add")
    except Exception as e:
        log_sync(f"⚠️ calc_combat: خطا تو world_pulse (uid={player.get('id')}): {type(e).__name__}: {e}", "ERROR")
        _pulse_crit = 0
    dmg_mult    = atk["dmg_mult"] + skb["dmg_pct"] + setb.get("dmg_pct", 0) + rb["dmg_pct"] + guild_dmg_pct + class_dmg_mult_add
    crit_chance = atk["crit"] + katana_crit_add + class_crit_add + skb["crit_chance"] + setb.get("crit_pct", 0) + _pulse_crit
    crit_chance = max(0.0, crit_chance - mob_abilities.crit_penalty(enemy))

    # Element weakness bonus — کاتانای بالاتر و درخت مهارت (مسیر عنصر) ضریب ضعف رو تقویت می‌کنن.
    # جادوگر عنصر نداره (کاتانا/کرکتر نمی‌گیره) ولی از روی عناصرِ بازشده‌ی
    # طلسمش (fire/water/lightning) هم می‌تونه ضعفِ دشمن رو target کنه.
    weak = enemy.get("weak", "")
    if is_adventurer:
        element = char.get("element", "")
    elif player_class == "wizard":
        _WIZARD_ELEMENT_FA = {"fire": "آتش", "water": "یخ", "lightning": "برق"}
        if wizard_spell_charge:
            # طلسمِ ترکیبیِ فعال‌شده: این یه ضربه رو، صرفِ‌نظر از عناصرِ
            # بازشده، تضمین می‌کنیم به ضعفِ دشمن بخوره.
            element = weak
        else:
            known_fa = {_WIZARD_ELEMENT_FA.get(e) for e in player.get("class_system_data", {}).get("elements_known", [])}
            element = weak if weak in known_fa else ""
    else:
        element = ""
    elem_mult   = (1.5 + katana_elem_amp + skb["elem_amp"] + setb.get("elem_amp", 0)) if element == weak and element else 1.0

    # Combo attack
    if attack_type == "combo" and combo < 3:
        dmg_mult = 0.6  # penalty if not enough combo

    # Ultimate attack — اگه یه‌جوری بدون rage پر صدا زده بشه (مثلاً باگ UI)،
    # به‌جای دمیج ۳.۲x فقط یه حمله‌ی ضعیف معمولی حساب می‌شه.
    if attack_type == "ultimate" and player.get("rage", 0) < 100:
        dmg_mult = 0.5

    raw = (base_dmg + level_bonus + katana_bonus + random.randint(-5, 12))
    raw = int(raw * dmg_mult * combo_mult * elem_mult * katana_soul_dmg_mult)
    raw = int(raw * mob_abilities.dmg_reduction_mult(enemy))  # 🛡️ پوست زره‌ای

    logs   = []
    result = {
        "dmg": raw, "crit": False, "miss": False,
        "counter": False, "status": None,
        "enemy_dmg": 0, "logs": logs,
        "elem_bonus": elem_mult > 1.0,
        "lifesteal_heal": 0,  # هندلر باید این مقدار رو به HP پلیر اضافه کنه
        "reflect_dmg": 0,     # 🔗 Item System v2 — دمیجی که با افیکسِ خاردار به دشمن برمی‌گرده
        "pet_proc": None,     # 🐾 اگه همراه تو این نبرد کمکِ فعال کرد، توضیحش اینجاست
    }

    # ─── وضعیت‌های فعالِ دشمن (Status Effects) ────────────────────
    # 🆕 باگ‌فیکس: قبلاً وقتی دشمن دچار «بیهوشی»/«انجماد» می‌شد فقط یه خطِ
    # لاگ چاپ می‌شد ولی هیچ اثرِ واقعی‌ای نداشت — دشمن بازم عادی ضدحمله
    # می‌زد، و خونریزی/سوختگی/زهر هم هیچ دمیجِ جداگانه‌ای نمی‌زدن. حالا
    # وضعیت‌ها واقعاً رو enemy["_status"] ذخیره می‌شن (چند نوبت دووم
    # میارن) و اثرِ واقعی دارن:
    #   ⚡ بیهوشی / ❄️ انجماد → دشمن تا وقتی این وضعیت فعاله اصلاً
    #                            ضدحمله نمی‌زنه (نه فقط همون یه ضربه)
    #   🩸 خونریزی / 🔥 سوختگی / ☠️ زهر → هر ضربه‌ی بعدیِ تو، یه دمیجِ
    #                            اضافه‌ی جدا هم رو دشمن می‌زنه
    #   💔 ضعف → دمیجِ ضدحملهٔ دشمن ۳۰٪ کم می‌شه
    active_status = enemy.get("_status")
    status_blocks_counter = False
    weaken_mult = 1.0
    if active_status and active_status.get("turns_left", 0) > 0:
        sk = active_status.get("key")
        sdef = STATUSES.get(sk, {})
        if sk in ("stun", "freeze"):
            status_blocks_counter = True
            logs.append(f"{sdef.get('emoji','⚡')} دشمن هنوز **{sdef.get('name','بیهوش')}**ه و نمی‌تونه ضدحمله بزنه!")
        elif sk == "weaken":
            weaken_mult = 0.7
            logs.append(f"{sdef.get('emoji','💔')} دشمن هنوز **{sdef.get('name','ضعیف')}**ه — ضدحمله‌ش ضعیف‌تره.")
        elif sdef.get("dmg", 0) > 0:
            tick_dmg = sdef["dmg"]
            enemy["hp"] = max(0, enemy.get("hp", enemy.get("max_hp", 1)) - tick_dmg)
            logs.append(f"{sdef.get('emoji','')} **{sdef.get('name','')}** {tick_dmg} آسیبِ اضافه به دشمن زد!")
        active_status["turns_left"] -= 1
        if active_status["turns_left"] <= 0:
            enemy["_status"] = None

    # Status effect — status_chance مسیر عنصر شانس پروک رو بالا می‌بره.
    # 🆕 این بخش قبلاً بعد از محاسبه‌ی ضدحمله بود؛ یعنی حتی اگه همین
    # ضربه دشمن رو بیهوش می‌کرد، بازم تو همون نوبت ضدحمله می‌خورد.
    # الان قبل از محاسبه‌ی ضدحمله انجام می‌شه تا اگه بیهوشی/انجماد
    # بخوره، همون لحظه جلوی ضدحمله رو هم بگیره.
    status_key = ELEMENT_STATUS.get(element)
    if status_key and random.random() < (0.25 + skb["status_chance"]):
        s = STATUSES[status_key]
        result["status"] = status_key
        logs.append(f"{s['emoji']} دشمن دچار **{s['name']}** شد!")
        enemy["_status"] = {"key": status_key, "turns_left": s["turns"]}
        if status_key in ("stun", "freeze"):
            status_blocks_counter = True

    # Critical (مسیر تهاجم: crit_dmg_bonus روی ضریب ۲x پایه اضافه می‌شه)
    if random.random() < crit_chance:
        result["dmg"]  = int(raw * (2.0 + skb["crit_dmg_bonus"] + eqb.get("crit_dmg_bonus", 0)))
        result["crit"] = True
        logs.append("💥 **CRITICAL HIT!**")

    # Miss — dodge_chance مسیر پایداری هم به شانس جاخالی خودت اضافه می‌شه (برای میسِ خودت تاثیری نداره،
    # این فقط شانس اینه که دشمن ضدحمله رو جاخالی بدی که پایین‌تر اعمال می‌شه)
    # 🔗 افیکسِ accuracy (Item System v2) این شانسِ پایه رو کم می‌کنه.
    base_miss_chance = max(0.01, 0.08 - eqb.get("accuracy_pct", 0))
    if random.random() < base_miss_chance:
        result["dmg"]  = 0
        result["miss"] = True
        logs.append("💨 **Miss!** دشمن dodge کرد!")
        # توجه: قبلاً اینجا return می‌شد و دشمن هیچ‌وقت ضدحمله نمی‌زد اگه پلیر miss می‌کرد.
        # حالا میس فقط یعنی خودت آسیب نزدی، ولی دشمن هنوز می‌تونه بهت حمله کنه.

    # ⛓️ زره‌پوش آهنین (ironclad) — گاهی حمله رو کاملاً بلاک می‌کنه
    if result["dmg"] > 0 and random.random() < mob_abilities.block_chance(enemy):
        result["dmg"] = 0
        logs.append(f"⛓️ **بلاک کامل!** {enemy.get('name','دشمن')} حمله‌ت رو کاملاً دفع کرد!")

    # Enemy retaliation — این خطِ اصلی آسیب گرفتنِ پلیره.
    # قبلاً این فقط ۱۲٪ شانس داشت («Counter») و در نتیجه پلیر عملاً هیچ‌وقت دمیج نمی‌خورد.
    # الان دشمن، تا وقتی این ضربه نکشتش، با شانس بالا ضدحمله می‌زنه (مگه اینکه خودش جاخالی بده).
    enemy_hp_before = enemy.get("hp", enemy.get("max_hp", 1))
    enemy_survives  = (enemy_hp_before - result["dmg"]) > 0
    retaliate_chance = 0.85 - skb["counter_reduction"] - skb["dodge_chance"] - setb.get("counter_pct", 0)
    if enemy_survives and not status_blocks_counter and random.random() < max(0.05, retaliate_chance):
        result["counter"]   = True
        base_enemy_dmg = int(enemy.get("dmg", 10) * random.uniform(0.7, 1.1))
        base_enemy_dmg = int(base_enemy_dmg * mob_abilities.counter_bonus_mult(enemy))  # 😡 خشم زیرِ ۳۰٪ HP
        base_enemy_dmg = int(base_enemy_dmg * weaken_mult)  # 💔 ضعف — ضدحمله ضعیف‌تر
        if random.random() < 0.15:
            base_enemy_dmg = int(base_enemy_dmg * 1.5)
            logs.append(f"💥 **ضدحمله کریتیکال دشمن!** {base_enemy_dmg} آسیب خوردی!")
        else:
            logs.append(f"⚡ دشمن ضدحمله زد و {base_enemy_dmg} آسیب خوردی!")
        base_enemy_dmg = int(base_enemy_dmg * (1 - skb["counter_dmg_reduction"] - setb.get("defense_pct", 0) - relic_defense_pct))
        try:
            from world_pulse import pulse_value
            base_enemy_dmg = int(base_enemy_dmg * pulse_value("enemy_dmg_mult"))
        except ImportError:
            pass

        # ☠️ زهرآگین — دمیجِ زهرِ اضافه رو ضدحمله
        v_bonus = mob_abilities.venom_bonus(enemy, base_enemy_dmg)
        if v_bonus:
            base_enemy_dmg += v_bonus
            logs.append(f"☠️ زهرِ {enemy.get('name','دشمن')} تو رگ‌هات پخش شد و {v_bonus} آسیبِ اضافه زد!")

        # ⚔️ ضربه‌ی دوگانه — گاهی یه ضربه‌ی دومِ اضافه رو همون ضدحمله
        if mob_abilities.maybe_double_strike(enemy):
            extra_hit = int(base_enemy_dmg * 0.6)
            base_enemy_dmg += extra_hit
            logs.append(f"⚔️ {enemy.get('name','دشمن')} دوبار پشتِ‌سرِهم بهت زد! (+{extra_hit})")

        result["enemy_dmg"] = max(0, base_enemy_dmg)

        # 🛡 سپرِ مانا/الهی (class_abilities.py) — یه شارژ، بخشِ زیادی از
        # ضدحمله رو جذب می‌کنه و مصرف می‌شه.
        if result["enemy_dmg"] > 0:
            csd_shield = player.get("class_system_data", {})
            if player_class == "wizard" and csd_shield.get("mana_shield_charges", 0) > 0:
                absorbed = int(result["enemy_dmg"] * 0.6)
                result["enemy_dmg"] -= absorbed
                csd_shield["mana_shield_charges"] -= 1
                logs.append(f"🛡 **سپرِ مانا** {absorbed} آسیب رو جذب کرد! (باقی‌مونده: {csd_shield['mana_shield_charges']})")
            elif player_class == "healer" and csd_shield.get("divine_shield_charges", 0) > 0:
                absorbed = int(result["enemy_dmg"] * 0.7)
                result["enemy_dmg"] -= absorbed
                csd_shield["divine_shield_charges"] -= 1
                logs.append(f"🛡 **سپرِ الهی** {absorbed} آسیب رو جذب کرد! (باقی‌مونده: {csd_shield['divine_shield_charges']})")

        # 🩸 خون‌آشام — با ضدحمله، بخشی از HP خودش رو ترمیم می‌کنه
        vamp = mob_abilities.vamp_heal(enemy, result["enemy_dmg"])
        if vamp:
            enemy["hp"] = min(enemy.get("max_hp", enemy["hp"]), enemy.get("hp", 0) + vamp)
            logs.append(f"🩸 {enemy.get('name','دشمن')} {vamp} HP از خونت جذب کرد!")

        # 🔗 افیکسِ reflect_dmg («خاردار» تجهیزات) — بخشی از دمیجی که خوردی، برمی‌گرده رو دشمن.
        reflect_pct = eqb.get("reflect_pct", 0)
        if reflect_pct > 0 and result["enemy_dmg"] > 0:
            result["reflect_dmg"] = int(result["enemy_dmg"] * reflect_pct)

    # 🌵 خاردار (mob ability) — هر بار بهش ضربه بزنی، خارهاش بهت آسیب می‌زنن
    thorn_dmg = mob_abilities.thorns_reflect(enemy, result["dmg"])
    if thorn_dmg:
        result["enemy_dmg"] = result.get("enemy_dmg", 0) + thorn_dmg
        logs.append(f"🌵 خارهای {enemy.get('name','دشمن')} {thorn_dmg} آسیب بهت برگردوندن!")

    # Element bonus log — به‌جای پیامِ ژنریکِ «ضعف عنصری»، یه خطِ نمایشیِ
    # مخصوصِ همون عنصر نشون بده (حسِ نبرد رو زنده‌تر می‌کنه).
    ELEMENT_HIT_FLAVOR = {
        "آتش":    "🔥 آتشِ تو دشمن رو می‌سوزونه!",
        "یخ":     "❄️ یخ تو رگ‌های دشمن نفوذ کرد و کندش کرد!",
        "برق":    "⚡ برق از سراسرِ بدنِ دشمن عبور کرد!",
        "زمین":   "🪨 صخره‌های تو دفاعِ دشمن رو خرد کردن!",
        "آب":     "🌊 موجِ تو دشمن رو غرق کرد!",
        "نور":    "✨ نورِ تو تاریکیِ دشمن رو سوزوند!",
        "تاریکی": "🌑 سایه‌ی تو روحِ دشمن رو بلعید!",
        "مقدس":   "🕊️ قدرتِ مقدسِ تو فسادِ دشمن رو پاک کرد!",
        "خلأ":    "🕳️ خلأ تو دشمن رو به نیستی کشوند!",
    }
    if result["elem_bonus"]:
        flavor = ELEMENT_HIT_FLAVOR.get(element, "🎯 ضعف عنصری!")
        logs.append(f"{flavor} (×{round(elem_mult, 2)})")

    # Lifesteal از کاتانا + مسیرِ پایداریِ درخت‌مهارت + ساستینِ درمانگر — درصدی از دمیج واردشده به‌صورت هیل برمی‌گرده
    total_lifesteal = katana_lifesteal + class_lifesteal + skb["lifesteal"] + setb.get("lifesteal_pct", 0)
    if total_lifesteal > 0 and result["dmg"] > 0:
        heal = int(result["dmg"] * total_lifesteal)
        if heal > 0:
            result["lifesteal_heal"] = heal
            logs.append(f"🩸 **{'نورِ مقدس' if player_class == 'healer' else 'جذب حیات کاتانا'}:** +{heal} HP")

    # ─── اثر ویژه‌ی تایر کاتانا (Legendary/Mythic) ────────────
    result["katana_soul_dmg"] = 0
    if kcore["special"] == "double_strike" and kcore["special_active"] and result["dmg"] > 0:
        if random.random() < 0.15:
            extra = result["dmg"]
            result["dmg"] += extra
            result["katana_soul_dmg"] = extra
            logs.append(f"🌟 **ضربه‌ی دوبل کاتانا!** +{extra} آسیب اضافه")
    elif kcore["special"] == "soul_drain" and kcore["special_active"] and result["dmg"] > 0 and not enemy_survives:
        heal = int(enemy_hp_before * 0.10)
        if heal > 0:
            result["lifesteal_heal"] = result.get("lifesteal_heal", 0) + heal
            logs.append(f"👑 **جذب روح (Mythic)!** با کشتنِ دشمن +{heal} HP گرفتی")

    # ─── Combat Engine v2 hook ────────────────────────────────
    # armor/resistance/accuracy دشمن + rage/ultimate gauge + perfect counter +
    # guard break همه اینجا اضافه می‌شن. try/except یعنی اگه combat_engine.py
    # هنوز آپلود نشده باشه، نبرد دقیقاً مثل قبل (بدون این مکانیک‌ها) کار می‌کنه.
    try:
        from combat_engine import apply_combat_v2
        result = apply_combat_v2(player, enemy, attack_type, result)
    except Exception:
        pass

    # 🐾 توانایی فعالِ همراه — بعد از همه‌چی، یه شانسِ کوچیک برای کمکِ ویژه.
    try:
        from pet_system import pet_ability_proc
        proc = pet_ability_proc(player)
        if proc and not result["miss"]:
            stat, power = proc["stat"], proc["power"]
            tag = f"{proc['emoji']} {proc['name']}"
            if stat == "dmg_pct" and result["dmg"] > 0:
                bonus = max(1, int(result["dmg"] * 0.25 * power))
                result["dmg"] += bonus
                result["pet_proc"] = f"{tag} یه ضربه‌ی اضافه زد! (+{bonus})"
            elif stat == "crit_pct" and result["dmg"] > 0:
                bonus = max(1, int(result["dmg"] * 0.4 * power))
                result["dmg"] += bonus
                result["crit"] = True
                result["pet_proc"] = f"{tag} کمک کرد یه کریتِ اضافه بخوره!"
            elif stat == "lifesteal_pct" and result["dmg"] > 0:
                heal = max(1, int(result["dmg"] * 0.3 * power))
                result["lifesteal_heal"] = result.get("lifesteal_heal", 0) + heal
                result["pet_proc"] = f"{tag} بهت {heal} HP شفا داد!"
            elif stat in ("defense_pct", "accuracy_pct") and result.get("enemy_dmg", 0) > 0:
                reduction = int(result["enemy_dmg"] * 0.35 * power)
                if reduction > 0:
                    result["enemy_dmg"] = max(0, result["enemy_dmg"] - reduction)
                    result["pet_proc"] = f"{tag} جلوی بخشی از ضربه رو گرفت!"
            if result.get("pet_proc"):
                result["logs"].append(f"🐾 {result['pet_proc']}")
    except ImportError:
        pass

    return result

# ============================================================
# 📊 خلاصه‌ی آمارِ مبارزه — نسخه‌ی «بدونِ دشمن» از منطقِ calc_combat،
# برای نمایشِ پنلِ «آمار مبارزه» به بازیکن. عمداً calc_combat رو دست
# نمی‌زنه (چون اون تابع مسیرِ واقعیِ نبرده و ریسکِ باگ داره)، فقط
# همون منابعِ بونوس رو دوباره جمع می‌زنه تا یه خلاصه‌ی خوانا بده.
# ============================================================
def get_combat_stats_summary(player: dict) -> dict:
    from characters import ALL_CHARACTERS
    is_adventurer = bool(player.get("character"))
    char = ALL_CHARACTERS.get(player.get("character", ""), {}) if is_adventurer else {}
    katana_lv = player.get("katana_level", 1)

    katana_bonus = katana_crit_add = katana_lifesteal = katana_elem_amp = 0
    katana_soul_dmg_mult = 1.0
    relic_defense_pct = 0.0
    if is_adventurer:
        try:
            from katana_system import crit_bonus as katana_crit_bonus, \
                lifesteal_bonus as katana_lifesteal_bonus, \
                element_amplify_bonus as katana_element_amplify_bonus
            from economy import KATANA_LEVELS
            katana_bonus     = KATANA_LEVELS.get(katana_lv, {}).get("dmg", 0)
            katana_crit_add  = katana_crit_bonus(katana_lv)
            katana_lifesteal = katana_lifesteal_bonus(katana_lv)
            katana_elem_amp  = katana_element_amplify_bonus(katana_lv)
        except Exception:
            pass
        try:
            from katana_core import calc_katana_bonus
            kcore = calc_katana_bonus(player)
            katana_crit_add  += kcore["crit"]
            katana_lifesteal += kcore["lifesteal"]
            katana_soul_dmg_mult = kcore["dmg_mult"] + kcore["dmg_mult_flat"]
        except Exception:
            pass
        try:
            from class_abilities import adventurer_relic_bonuses
            relic_b = adventurer_relic_bonuses(player)
            katana_bonus     += relic_b["dmg_flat"]
            katana_crit_add  += relic_b["crit_pct"]
            katana_lifesteal += relic_b["lifesteal_pct"]
            relic_defense_pct = relic_b["defense_pct"]
        except Exception:
            pass

    class_crit_add = class_dmg_mult_add = class_lifesteal = 0.0
    player_class = player.get("class")
    if player_class == "wizard":
        class_crit_add = 0.08
        class_dmg_mult_add = 0.15
    elif player_class == "healer":
        class_lifesteal = 0.10

    try:
        from skill_tree import get_skill_bonuses
        skb = get_skill_bonuses(player)
    except Exception:
        skb = {"dmg_pct": 0, "crit_chance": 0, "elem_amp": 0, "lifesteal": 0, "counter_dmg_reduction": 0}

    try:
        from loot_engine import get_set_bonus_stats
        setb = get_set_bonus_stats(player)
    except Exception:
        setb = {}
    try:
        from divine_seals import get_seal_bonus_stats
        for k, v in get_seal_bonus_stats(player).items():
            setb[k] = setb.get(k, 0) + v
    except Exception:
        pass
    try:
        from hunt_questline import get_hunt_bonuses
        for k, v in get_hunt_bonuses(player).items():
            setb[k] = setb.get(k, 0) + v
    except Exception:
        pass
    try:
        from market_questline import get_elixir_bonuses
        for k, v in get_elixir_bonuses(player).items():
            setb[k] = setb.get(k, 0) + v
    except Exception:
        pass

    eqb = {}
    try:
        from item_system import combat_bonus_stats
        eqb = combat_bonus_stats(player)
        for k in ("dmg_pct", "crit_pct", "lifesteal_pct", "defense_pct", "elem_amp"):
            if eqb.get(k):
                setb[k] = setb.get(k, 0) + eqb[k]
    except Exception:
        eqb = {}
    try:
        from pet_system import pet_combat_bonus
        petb = pet_combat_bonus(player)
        for k, v in petb.items():
            eqb[k] = eqb.get(k, 0) + v
            if k in ("dmg_pct", "crit_pct", "lifesteal_pct", "defense_pct"):
                setb[k] = setb.get(k, 0) + v
    except Exception:
        petb = {}

    try:
        from game_data import rebirth_bonuses
        rb = rebirth_bonuses(player)
    except Exception:
        rb = {"dmg_pct": 0}

    try:
        from guild_system import get_perk
        guild_dmg_pct = get_perk(player, "pve_dmg_pct")
    except Exception:
        guild_dmg_pct = 0

    atk = ATTACK_TYPES.get("quick", {"dmg_mult": 1.0, "crit": 0.0})
    total_dmg_pct    = (atk["dmg_mult"] - 1.0) + skb.get("dmg_pct", 0) + setb.get("dmg_pct", 0) + rb.get("dmg_pct", 0) + guild_dmg_pct + class_dmg_mult_add
    total_crit_pct   = atk["crit"] + katana_crit_add + class_crit_add + skb.get("crit_chance", 0) + setb.get("crit_pct", 0)
    total_lifesteal  = katana_lifesteal + class_lifesteal + skb.get("lifesteal", 0) + setb.get("lifesteal_pct", 0)
    total_defense    = setb.get("defense_pct", 0) + relic_defense_pct
    total_elem_amp   = katana_elem_amp + skb.get("elem_amp", 0) + setb.get("elem_amp", 0)
    elem_mult_active = 1.5 + total_elem_amp

    return {
        "is_adventurer": is_adventurer,
        "player_class": player_class,
        "katana_level": katana_lv,
        "katana_bonus_dmg": katana_bonus,
        "katana_soul_dmg_mult": katana_soul_dmg_mult,
        "dmg_pct": total_dmg_pct,
        "crit_pct": total_crit_pct,
        "lifesteal_pct": total_lifesteal,
        "defense_pct": total_defense,
        "elem_amp": total_elem_amp,
        "elem_mult_active": elem_mult_active,
        "has_element_access": is_adventurer or player_class == "wizard",
        "gold_find_pct": setb.get("gold_find_pct", 0) + eqb.get("gold_find_pct", 0),
        "xp_pct": setb.get("xp_pct", 0) + eqb.get("xp_pct", 0),
    }


HARDCORE_DROP_CHANCE_MULT = 0.5

# شانسِ اینکه دراپ به‌جای متریالِ ساده، یه تجهیزاتِ واقعی و قابل‌اکیپ باشه
EQUIPMENT_DROP_CHANCE = 0.32
CONSUMABLE_DROP_CHANCE = 0.14  # شانسِ اینکه به‌جای متریالِ خام، یه آیتمِ مصرفی (پوشن/طومار/کیسه‌طلا) دراپ بشه

def get_drop(enemy: dict, player: dict | None = None) -> dict | None:
    from game_data import rebirth_bonuses
    loot_bonus = rebirth_bonuses(player)["loot_pct"] if player else 0
    if random.random() > enemy.get("drop_chance", 0.2) * HARDCORE_DROP_CHANCE_MULT * (1 + loot_bonus):
        return None
    tier = enemy.get("tier", "common")

    if random.random() < EQUIPMENT_DROP_CHANCE:
        from item_system import generate_random_equipment, RARITY_DATA
        player_level = player.get("level", 1) if player else 1
        forced_rarity = tier if tier in RARITY_DATA else None
        return generate_random_equipment(
            player_level, forced_rarity=forced_rarity,
            drop_source=f"mob:{enemy.get('name','?')}"
        )

    if random.random() < CONSUMABLE_DROP_CHANCE:
        from item_system import generate_consumable
        player_level = player.get("level", 1) if player else 1
        return generate_consumable(player_level)

    pool = ENEMY_DROPS.get(tier, ENEMY_DROPS["common"])
    item = random.choice(pool).copy()
    item["rarity"] = tier
    return item

# ─── حالت سخت وحشتناک: کمین دشمن + ضربه مرگبار (سخت‌تر از راند اول) ─
AMBUSH_CHANCE = 0.25               # قبلاً ۱۵٪ بود
DEADLY_BLOW_MIN_LEVEL = 40         # قبلاً ۵۰ بود — زودتر شروع می‌شه
DEADLY_BLOW_CHANCE = 0.15          # قبلاً ۱۰٪ بود
DEADLY_BLOW_HP_PCT = 0.5           # ۵۰٪ از HP فعلی رو یک‌جا می‌بره

def maybe_ambush(player: dict, enemy: dict) -> dict | None:
    """قبل از این‌که بازیکن اولین ضربه رو بزنه صدا زده می‌شه.
    اگه کمین موفق بشه، دشمن یه ضربه‌ی رایگان به بازیکن می‌زنه.
    خروجی: None (کمینی نبود) یا {"dmg": int, "msg": str}."""
    bonus_chance, dmg_mult = mob_abilities.ambush_bonus(enemy)  # 🌑 شکارچی کمین‌گر
    if random.random() > min(0.9, AMBUSH_CHANCE + bonus_chance):
        return None
    dmg = int(enemy.get("dmg", 10) * random.uniform(0.5, 0.9) * dmg_mult)
    return {"dmg": dmg, "msg": f"🌑 **کمین!** {enemy.get('name','دشمن')} قبل از اینکه آماده بشی بهت حمله کرد و {dmg} آسیب زد!"}

def maybe_deadly_blow(player: dict, enemy: dict) -> dict | None:
    """برای دشمنان سطح‌بالا (epic/legendary) وقتی بازیکن سطح بالای ۵۰ باشه،
    شانس یه ضربه‌ی مرگبار که نیمی از HP فعلی رو یک‌جا می‌بره."""
    if player.get("level", 1) < DEADLY_BLOW_MIN_LEVEL:
        return None
    if enemy.get("tier") not in ("epic", "legendary"):
        return None
    if random.random() > DEADLY_BLOW_CHANCE:
        return None
    dmg = max(1, int(player.get("hp", 100) * DEADLY_BLOW_HP_PCT))
    return {"dmg": dmg, "msg": f"☠️ **ضربه مرگبار!** {enemy.get('name','دشمن')} یه‌جا {dmg} HP ازت گرفت!"}

def hp_bar(current: int, maximum: int, length: int = 8) -> str:
    if maximum <= 0: return "⬛" * length
    filled = max(0, int((current / maximum) * length))
    return "🟥" * filled + "⬛" * (length - filled)

# ─── Daily Events ────────────────────────────────────────────

import datetime

DAILY_EVENTS = [
    {
        "name": "🌋 روز آتشفشان",
        "desc": "امروز همه آسیب‌های آتشی ۲ برابره!",
        "bonus": "fire_dmg_x2",
        "map":   "Emberhollow",
    },
    {
        "name": "❄️ توفان یخ",
        "desc": "دشمنان یخی HP کمتری دارن — راحت‌تر بزنشون!",
        "bonus": "ice_enemy_weak",
        "map":   "Frostheim",
    },
    {
        "name": "💰 روز طلایی",
        "desc": "امروز تمام Zen reward ها ۳ برابره!",
        "bonus": "zen_x3",
        "map":   None,
    },
    {
        "name": "⭐ روز XP",
        "desc": "امروز تمام XP ها ۲ برابره!",
        "bonus": "xp_x2",
        "map":   None,
    },
    {
        "name": "🐉 تهاجم اژدها",
        "desc": "اژدهاهای قوی‌تری ظاهر شدن! ولی جایزه بیشتره!",
        "bonus": "dragon_raid",
        "map":   "Dragonnest Peaks",
    },
    {
        "name": "🌑 شب خلأ",
        "desc": "موجودات خلأ همه جا هستن — خطرناکه ولی loot بمبه!",
        "bonus": "void_night",
        "map":   "Voidbreak Wastes",
    },
    {
        "name": "🛒 تخفیف بازار",
        "desc": "امروز همه اجناس بازار سیاه ۳۰٪ تخفیف دارن!",
        "bonus": "market_discount",
        "map":   "Abyssal Black Market",
    },
]

DAILY_QUESTS_POOL = [
    {"id":"q1", "name":"🗡 شکارچی",    "desc":"۵ دشمن بکش",          "target":5,  "type":"kill",   "reward_zen":500,  "reward_xp":100},
    {"id":"q2", "name":"⚔️ جنگجو",     "desc":"۳ حمله قوی بزن",       "target":3,  "type":"heavy",  "reward_zen":300,  "reward_xp":80},
    {"id":"q3", "name":"🗺 کاشف",      "desc":"۲ مپ رو لوت کن",       "target":2,  "type":"loot",   "reward_zen":400,  "reward_xp":90},
    {"id":"q4", "name":"💥 کریتیکال",  "desc":"۳ ضربه کریتیکال بزن",  "target":3,  "type":"crit",   "reward_zen":600,  "reward_xp":120},
    {"id":"q5", "name":"🔥 کومبو مستر", "desc":"کومبو ×۱۰ برسون",      "target":10, "type":"combo",  "reward_zen":800,  "reward_xp":150},
    {"id":"q6", "name":"💰 ثروتمند",   "desc":"۵۰۰ Zen جمع کن",      "target":500,"type":"earn",   "reward_zen":200,  "reward_xp":50},
    {"id":"q7", "name":"🐉 صیاد",      "desc":"یه دشمن legendary بکش","target":1,  "type":"legend", "reward_zen":2000, "reward_xp":300},
    {"id":"q8", "name":"🛡 محافظ",     "desc":"بدون مردن ۱۰ حمله بزن","target":10, "type":"survive","reward_zen":700,  "reward_xp":140},
]

def get_today_event() -> dict:
    day = datetime.date.today().toordinal()
    return DAILY_EVENTS[day % len(DAILY_EVENTS)]

def get_today_quests() -> list[dict]:
    day = datetime.date.today().toordinal()
    random.seed(day)
    quests = random.sample(DAILY_QUESTS_POOL, 3)
    random.seed()
    return quests

def get_event_multiplier(bonus: str, stat: str) -> float:
    multipliers = {
        "zen_x3":   {"zen": 3.0},
        "xp_x2":    {"xp": 2.0},
        "fire_dmg_x2": {"dmg": 2.0},
        "dragon_raid": {"zen": 2.0, "xp": 1.5},
        "void_night":  {"zen": 1.5, "xp": 1.5},
    }
    return multipliers.get(bonus, {}).get(stat, 1.0)
