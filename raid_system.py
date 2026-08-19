from aiogram.enums import ButtonStyle
# ============================================================
#  ASTRAL ABYSS — RAID SYSTEM (Map-Specific Events)
# ============================================================
import random
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ─── Rarity Colors ───────────────────────────────────────────
R = {"common":"⚪","uncommon":"🟢","rare":"🔵","epic":"🟣","mythic":"🟠","legendary":"🟡"}

# ─── Event Types per Map ─────────────────────────────────────
MAP_EVENTS = {

    "Frostheim": [
        {
            "id": "frost_wolf",
            "name": "🐺 حمله گرگ‌های یخی",
            "desc": "گله‌ای از گرگ‌های یخی از پشت کوه ظاهر شدند!\nرهبر گله چشمانش مثل یخ می‌درخشد...",
            "choices": [
                {"text": "⚔️ با رهبر گله بجنگ", "cb": "raid:frost_wolf:fight"},
                {"text": "🔥 از آتش استفاده کن", "cb": "raid:frost_wolf:fire"},
                {"text": "🏃 فرار کن!", "cb": "raid:frost_wolf:run"},
            ],
            "outcomes": {
                "fight":  {"msg": "💥 بعد از نبرد سخت، رهبر گله شکست خورد!\nگله پراکنده شد و گنجشان را رها کردند!", "loot_tier": "rare",   "hp_cost": 20, "zen_bonus": 50},
                "fire":   {"msg": "🔥 آتش گرگ‌ها را ترساند!\nولی رهبر گله یه پنجه به تو زد قبل از فرار!", "loot_tier": "uncommon","hp_cost": 10, "zen_bonus": 20},
                "run":    {"msg": "🏃 فرار کردی ولی کیف لوتت را جا گذاشتی!", "loot_tier": "common",  "hp_cost": 5,  "zen_bonus": 0},
            }
        },
        {
            "id": "frost_chest",
            "name": "🧊 صندوق یخ‌زده باستانی",
            "desc": "یه صندوق قدیمی زیر یخ پیدا کردی!\nنقش‌های رونیک رویش می‌درخشند...\nبرای باز کردنش باید قفل رو بشکنی!",
            "choices": [
                {"text": "⚔️ با شمشیر بشکن",    "cb": "raid:frost_chest:sword"},
                {"text": "🔥 با آتش ذوب کن",    "cb": "raid:frost_chest:melt"},
                {"text": "🔮 با جادو باز کن",   "cb": "raid:frost_chest:magic"},
                {"text": "💪 با قدرت بشکن",     "cb": "raid:frost_chest:force"},
            ],
            "outcomes": {
                "sword":  {"msg": "⚔️ شمشیر روی یخ لیز خورد و صندوق شکست!\nآیتم‌ها پخش شدند اما بیشترشون رو جمع کردی!", "loot_tier": "rare",      "hp_cost": 0,  "zen_bonus": 30},
                "melt":   {"msg": "🔥 یخ آب شد و صندوق سالم باز شد!\nداخلش پر از گنج‌های باستانی بود!", "loot_tier": "epic",      "hp_cost": 0,  "zen_bonus": 80},
                "magic":  {"msg": "🔮 جادو به رون‌ها واکنش نشان داد!\nصندوق با صدای بلند باز شد و یه چیز کمیاب بیرون اومد!", "loot_tier": "legendary", "hp_cost": 10, "zen_bonus": 150},
                "force":  {"msg": "💪 صندوق شکست ولی بعضی آیتم‌ها خراب شدند!", "loot_tier": "common",    "hp_cost": 15, "zen_bonus": 0},
            }
        },
        {
            "id": "frost_spirit",
            "name": "👻 روح یخ‌بند",
            "desc": "یه روح باستانی از دل یخ بیرون اومد!\nبا صدای سردی گفت:\n_'جنگجو... با من معامله کن یا منجمدت می‌کنم!'_",
            "choices": [
                {"text": "🤝 معامله کن (30 HP بده)",  "cb": "raid:frost_spirit:deal"},
                {"text": "⚔️ با روح بجنگ",            "cb": "raid:frost_spirit:fight"},
                {"text": "🙏 التماس کن",               "cb": "raid:frost_spirit:beg"},
            ],
            "outcomes": {
                "deal":   {"msg": "🤝 روح خندید و یه صندوق کمیاب داد!\n_'معامله خوبیه، جنگجو...'_", "loot_tier": "epic",   "hp_cost": 30, "zen_bonus": 100},
                "fight":  {"msg": "⚔️ روح‌ها قابل آسیب نیستند!\nمنجمدت کرد و بعد رها کرد با یه لوت کوچیک!", "loot_tier": "common", "hp_cost": 40, "zen_bonus": 0},
                "beg":    {"msg": "🙏 روح دلش سوخت!\nیه لوت معمولی داد و ناپدید شد.", "loot_tier": "uncommon","hp_cost": 0,  "zen_bonus": 10},
            }
        },
        {
            "id": "frost_storm",
            "name": "🌨️ توفان برفی مرگبار",
            "desc": "یه توفان برفی ناگهانی شروع شد!\nدما داره به -۵۰ می‌رسه!\nباید سریع تصمیم بگیری!",
            "choices": [
                {"text": "🏔️ پشت صخره پناه بگیر",    "cb": "raid:frost_storm:hide"},
                {"text": "🏃 در توفان به جلو برو",    "cb": "raid:frost_storm:push"},
                {"text": "🔥 آتش روشن کن و صبر کن",  "cb": "raid:frost_storm:wait"},
            ],
            "outcomes": {
                "hide":  {"msg": "🏔️ پشت صخره پناه گرفتی!\nبعد از توفان یه صندوق پیدا کردی که توفان از جای دیگه آورده بود!", "loot_tier": "rare",   "hp_cost": 5,  "zen_bonus": 40},
                "push":  {"msg": "🌨️ در توفان پیش رفتی!\nیه غار مخفی پیدا کردی پر از گنج!\nولی سرما ضعیفت کرد...", "loot_tier": "epic",  "hp_cost": 35, "zen_bonus": 120},
                "wait":  {"msg": "🔥 آتش روشن کردی و صبر کردی!\nبعد از توفان آرامش برقرار شد.", "loot_tier": "uncommon","hp_cost": 0,  "zen_bonus": 20},
            }
        },
    ],

    "Voidbreak Wastes": [
        {
            "id": "void_rift",
            "name": "🌑 شکاف خلأ",
            "desc": "یه شکاف در فضا باز شد!\nصداهای عجیبی از اون طرف میاد...\n_'وارد شو... یا ابدیت را از دست بده...'_",
            "choices": [
                {"text": "🌀 وارد شکاف شو (خطر زیاد)",   "cb": "raid:void_rift:enter"},
                {"text": "👁️ فقط داخل رو نگاه کن",       "cb": "raid:void_rift:peek"},
                {"text": "💨 ازش دور شو",                  "cb": "raid:void_rift:flee"},
            ],
            "outcomes": {
                "enter": {"msg": "🌌 وارد خلأ شدی!\nزمان و مکان معنایی نداشت...\nبا یه آیتم Mythic برگشتی ولی نصف HPت رفت!", "loot_tier": "mythic",    "hp_cost": 50, "zen_bonus": 200},
                "peek":  {"msg": "👁️ داخل رو نگاه کردی!\nیه دست از شکاف بیرون اومد و یه آیتم انداخت!", "loot_tier": "epic",     "hp_cost": 15, "zen_bonus": 80},
                "flee":  {"msg": "💨 فرار کردی!\nولی شکاف یه آیتم به طرفت پرتاب کرد!", "loot_tier": "rare",     "hp_cost": 0,  "zen_bonus": 30},
            }
        },
        {
            "id": "void_gamble",
            "name": "🎰 قمار با سایه",
            "desc": "یه موجود سایه‌ای ظاهر شد!\n_'جنگجو... آیا شجاعت داری با من قمار کنی؟'_\nهر چیزی ممکنه از دست بدی یا بگیری!",
            "choices": [
                {"text": "🎰 قمار کن (۱۰۰ Zen شرط)",   "cb": "raid:void_gamble:bet"},
                {"text": "💎 شرط بزرگ (۳۰۰ Zen)",      "cb": "raid:void_gamble:bigbet"},
                {"text": "❌ رد کن",                     "cb": "raid:void_gamble:refuse"},
            ],
            "outcomes": {
                "bet":    {"msg": "🎰 تاس ریخته شد...\nبردی! سایه با اکراه پرداخت کرد!", "loot_tier": "rare",      "hp_cost": 0,  "zen_bonus": 300},
                "bigbet": {"msg": "💎 شرط بزرگ زدی!\nسایه خندید... و باختی!\nولی برای ناراحتیت یه آیتم داد!", "loot_tier": "epic",      "hp_cost": 0,  "zen_bonus": -200},
                "refuse": {"msg": "❌ رد کردی!\nسایه ناراحت شد و یه چیز کوچیک پرت کرد و رفت.", "loot_tier": "common",    "hp_cost": 0,  "zen_bonus": 0},
            }
        },
        {
            "id": "void_creature",
            "name": "👾 موجود بعد دیگر",
            "desc": "یه موجود از بعد دیگه ظاهر شد!\nشکل ندارد، فقط چشم است...\nبه تو خیره شده و منتظره!",
            "choices": [
                {"text": "⚔️ حمله کن",              "cb": "raid:void_creature:attack"},
                {"text": "🧠 با ذهن باهاش ارتباط",  "cb": "raid:void_creature:mind"},
                {"text": "🎁 یه هدیه بده",           "cb": "raid:void_creature:gift"},
            ],
            "outcomes": {
                "attack": {"msg": "⚔️ موجود ذوب شد!\nولی انرژی آزاد شده آسیب زد!\nیه کریستال خلأ جا گذاشت!", "loot_tier": "epic",   "hp_cost": 25, "zen_bonus": 60},
                "mind":   {"msg": "🧠 ارتباط ذهنی برقرار شد!\nتصاویری از گنج‌های پنهان دیدی!\nموجود مسیر رو نشون داد!", "loot_tier": "legendary","hp_cost": 10, "zen_bonus": 150},
                "gift":   {"msg": "🎁 موجود هدیه رو گرفت!\nدر عوض یه چیز از بعد خودش داد!", "loot_tier": "rare",   "hp_cost": 0,  "zen_bonus": 40},
            }
        },
        {
            "id": "void_awakening",
            "name": "🌑 بیداری آبیس",
            "desc": "⚠️ **رویداد نادر!**\nزمین لرزید... هوا سیاه شد...\nیه موجود باستانی از اعماق خلأ بیدار شد!\n_نگاهش کهکشان‌ها را می‌بلعد..._",
            "choices": [
                {"text": "👑 باهاش مذاکره کن",      "cb": "raid:void_awakening:talk"},
                {"text": "⚔️ با تمام قدرت بجنگ",   "cb": "raid:void_awakening:fight"},
                {"text": "🙇 تعظیم کن",             "cb": "raid:void_awakening:bow"},
            ],
            "outcomes": {
                "talk":  {"msg": "👑 مذاکره کردی!\nموجود به قدرت ذهنیت احترام گذاشت!\nیه آیتم Mythic و یه کاراکتر شانسی!", "loot_tier": "mythic",    "hp_cost": 0,  "zen_bonus": 500},
                "fight": {"msg": "⚔️ جنگیدی!\nموجود با یه ضربه تو رو پرت کرد!\nولی از قدرتت تعجب کرد و رفت...", "loot_tier": "epic",     "hp_cost": 60, "zen_bonus": 100},
                "bow":   {"msg": "🙇 تعظیم کردی!\nموجود راضی شد و یه هدیه داد و رفت.", "loot_tier": "legendary","hp_cost": 0,  "zen_bonus": 200},
            }
        },
    ],

    "Dragonnest Peaks": [
        {
            "id": "dragon_encounter",
            "name": "🐉 مواجهه با اژدها",
            "desc": "یه اژدهای جوان جلوی راهت رو گرفت!\nنفس آتشینش صخره‌ها را ذوب می‌کنه!\nچشمانش طلایی و خطرناکه...",
            "choices": [
                {"text": "⚔️ بجنگ",                     "cb": "raid:dragon_encounter:fight"},
                {"text": "🎵 آواز بخون (تسکین اژدها)",  "cb": "raid:dragon_encounter:sing"},
                {"text": "🍖 غذا بده",                   "cb": "raid:dragon_encounter:feed"},
                {"text": "🏃 فرار کن",                   "cb": "raid:dragon_encounter:run"},
            ],
            "outcomes": {
                "fight": {"msg": "⚔️ نبرد سختی بود!\nبالاخره اژدها فرار کرد!\nفلس‌هایی که ریخت رو جمع کردی!", "loot_tier": "epic",      "hp_cost": 40, "zen_bonus": 100},
                "sing":  {"msg": "🎵 اژدها آروم شد!\nدراز کشید و تو رو راه داد!\nاز گنجش بهت داد!", "loot_tier": "legendary", "hp_cost": 0,  "zen_bonus": 200},
                "feed":  {"msg": "🍖 اژدها غذا رو خورد!\nخوشش اومد و دوستت شد!\nیه فلس طلایی بهت داد!", "loot_tier": "rare",      "hp_cost": 0,  "zen_bonus": 80},
                "run":   {"msg": "🏃 فرار کردی!\nاژدها دنبالت کرد و بعد خسته شد!\nیه چیز کوچیک انداخت!", "loot_tier": "common",    "hp_cost": 20, "zen_bonus": 0},
            }
        },
        {
            "id": "dragon_egg",
            "name": "🥚 تخم اژدها!",
            "desc": "یه تخم اژدهای درخشان پیدا کردی!\nداغه و نبضش داره!\nمادرش ممکنه برگرده...",
            "choices": [
                {"text": "🥚 تخم رو بردار",         "cb": "raid:dragon_egg:take"},
                {"text": "🔥 تخم رو گرم کن",        "cb": "raid:dragon_egg:warm"},
                {"text": "💰 تخم رو بفروش",          "cb": "raid:dragon_egg:sell"},
                {"text": "🙏 برش دار و برگردون",     "cb": "raid:dragon_egg:return"},
            ],
            "outcomes": {
                "take":   {"msg": "🥚 تخم رو برداشتی!\nمادر اژدها برگشت و دنبالت کرد!\nبه سختی فرار کردی!", "loot_tier": "epic",      "hp_cost": 30, "zen_bonus": 150},
                "warm":   {"msg": "🔥 تخم رو گرم کردی!\nاژدهای کوچیک بیرون اومد!\nبه نشانه سپاسگزاری یه هدیه داد!", "loot_tier": "legendary", "hp_cost": 0,  "zen_bonus": 300},
                "sell":   {"msg": "💰 تخم رو به یه دلال فروختی!\nپول خوبی گرفتی!", "loot_tier": "rare",      "hp_cost": 0,  "zen_bonus": 500},
                "return": {"msg": "🙏 تخم رو برگردوندی!\nمادر اژدها از قلبت تشکر کرد!\nگنج قدیمی بهت نشون داد!", "loot_tier": "mythic",    "hp_cost": 0,  "zen_bonus": 250},
            }
        },
        {
            "id": "dragon_trial",
            "name": "🏔️ آزمون شجاعت اژدها",
            "desc": "یه اژدهای ارشد جلوت ظاهر شد!\n_'جنگجو... ثابت کن لایق قله‌های مرا هستی!'_\nسه آزمون در انتظارته...",
            "choices": [
                {"text": "🔥 آزمون آتش رو قبول کن",    "cb": "raid:dragon_trial:fire"},
                {"text": "💨 آزمون باد رو قبول کن",     "cb": "raid:dragon_trial:wind"},
                {"text": "⚡ آزمون صاعقه رو قبول کن",  "cb": "raid:dragon_trial:lightning"},
            ],
            "outcomes": {
                "fire":      {"msg": "🔥 از میان آتش گذشتی!\nاژدها تعجب کرد!\nبه گنج اژدهاها راهت داد!", "loot_tier": "legendary", "hp_cost": 25, "zen_bonus": 200},
                "wind":      {"msg": "💨 از بالای کوه پریدی!\nاژدها از شجاعتت تحسین کرد!\nهدیه داد!", "loot_tier": "epic",      "hp_cost": 15, "zen_bonus": 150},
                "lightning": {"msg": "⚡ صاعقه رو تحمل کردی!\nاژدها ارشد تعظیم کرد!\nبهترین گنجش رو داد!", "loot_tier": "mythic",    "hp_cost": 35, "zen_bonus": 300},
            }
        },
    ],

    "Emberhollow": [
        {
            "id": "ember_eruption",
            "name": "🌋 فوران آتشفشان",
            "desc": "زمین شروع به لرزیدن کرد!\nگدازه از شکاف‌ها بیرون میزنه!\nسنگ‌های آتشین در هوا پرواز می‌کنند!",
            "choices": [
                {"text": "🏃 سریع فرار کن",            "cb": "raid:ember_eruption:run"},
                {"text": "🛡️ محکم بایست و دفاع کن",   "cb": "raid:ember_eruption:defend"},
                {"text": "🌋 به سمت فوران برو",         "cb": "raid:ember_eruption:advance"},
            ],
            "outcomes": {
                "run":     {"msg": "🏃 فرار کردی!\nولی یه سنگ آتشین به دوشت خورد!\nبعد از آروم شدن یه کریستال آتشی پیدا کردی!", "loot_tier": "rare",   "hp_cost": 20, "zen_bonus": 40},
                "defend":  {"msg": "🛡️ محکم ایستادی!\nگدازه اطرافت خشک شد و یه تونل جدید باز کرد!\nداخلش پر از کانی بود!", "loot_tier": "epic",  "hp_cost": 15, "zen_bonus": 100},
                "advance": {"msg": "🌋 به سمت فوران رفتی!\nداخل دهانه آتشفشان یه صندوق باستانی بود!\nکسی جرأت نمی‌کرد بره!", "loot_tier": "mythic","hp_cost": 45, "zen_bonus": 300},
            }
        },
        {
            "id": "ember_golem",
            "name": "🔥 گلم آتش باستانی",
            "desc": "یه گلم آتش عظیم از گدازه بیرون اومد!\nقلبش یه کریستال سرخ میزنه...\nبا هر قدم زمین می‌لرزه!",
            "choices": [
                {"text": "❄️ با یخ حمله کن (ضعف)",    "cb": "raid:ember_golem:ice"},
                {"text": "⚔️ مستقیم بجنگ",             "cb": "raid:ember_golem:fight"},
                {"text": "🎯 به قلبش نشانه رو",        "cb": "raid:ember_golem:core"},
            ],
            "outcomes": {
                "ice":   {"msg": "❄️ یخ کارگر افتاد!\nگلم ترک خورد و فرو ریخت!\nکریستال قلبش برای تو موند!", "loot_tier": "legendary","hp_cost": 10, "zen_bonus": 150},
                "fight": {"msg": "⚔️ نبرد سنگین بود!\nگلم رو شکستی ولی آتش آسیب زد!", "loot_tier": "epic",      "hp_cost": 35, "zen_bonus": 80},
                "core":  {"msg": "🎯 به قلبش زدی!\nگلم ذوب شد و کریستال قلبش افتاد!\nیه آیتم Mythic!", "loot_tier": "mythic",    "hp_cost": 20, "zen_bonus": 200},
            }
        },
        {
            "id": "ember_soul",
            "name": "👻 روح سوخته",
            "desc": "یه روح که در آتش گرفتار شده ظاهر شد!\n_'کمکم کن... من اینجا هزار ساله که می‌سوزم!'_\nآیا بهش اعتماد می‌کنی؟",
            "choices": [
                {"text": "🙏 کمکش کن",              "cb": "raid:ember_soul:help"},
                {"text": "🔮 ازش اطلاعات بگیر",     "cb": "raid:ember_soul:info"},
                {"text": "❌ اعتماد نکن",           "cb": "raid:ember_soul:ignore"},
            ],
            "outcomes": {
                "help":   {"msg": "🙏 کمکش کردی!\nروح آزاد شد و از صمیم قلب تشکر کرد!\nگنج هزار ساله‌اش رو بهت داد!", "loot_tier": "legendary","hp_cost": 0,  "zen_bonus": 300},
                "info":   {"msg": "🔮 اطلاعات مکان گنج مخفی رو داد!\nبعد رفت...\nگنج رو پیدا کردی!", "loot_tier": "epic",      "hp_cost": 0,  "zen_bonus": 100},
                "ignore": {"msg": "❌ ازش رد شدی!\nروح از پشت سر یه چیز پرتاب کرد!", "loot_tier": "common",    "hp_cost": 10, "zen_bonus": 0},
            }
        },
    ],

    "Dreadgate Citadel": [
        {
            "id": "dread_army",
            "name": "💀 ارتش مردگان",
            "desc": "دروازه باز شد و ارتشی از مردگان بیرون ریخت!\nهزاران چشم خالی به تو خیره شدند...\nرهبرشون یه شوالیه مرده‌ست!",
            "choices": [
                {"text": "⚔️ به رهبر حمله کن",         "cb": "raid:dread_army:leader"},
                {"text": "🏃 از طریق ارتش رد شو",      "cb": "raid:dread_army:push"},
                {"text": "🔮 طلسم از دست بده",          "cb": "raid:dread_army:spell"},
            ],
            "outcomes": {
                "leader": {"msg": "⚔️ رهبر رو شکستی!\nبدون رهبر، ارتش متفرق شد!\nزره شوالیه مرده پر از گنج بود!", "loot_tier": "epic",      "hp_cost": 35, "zen_bonus": 150},
                "push":   {"msg": "🏃 از بین ارتش رد شدی!\nمردگان نمی‌تونستن جلوت رو بگیرن!\nبه گنج اصلی رسیدی!", "loot_tier": "rare",      "hp_cost": 20, "zen_bonus": 80},
                "spell":  {"msg": "🔮 طلسم کار کرد!\nمردگان ذوب شدند!\nروح‌هاشون ازت تشکر کردن و گنج دادن!", "loot_tier": "legendary", "hp_cost": 5,  "zen_bonus": 200},
            }
        },
        {
            "id": "dread_pact",
            "name": "😈 پیمان تاریک",
            "desc": "یه شیطان از دروازه بیرون اومد!\n_'جنگجو... یه پیمان باهام ببند!\nقدرت در ازای...'_\nادامه حرفش رو نزد!",
            "choices": [
                {"text": "✍️ پیمان ببند (نمی‌دونی چی میدی)",  "cb": "raid:dread_pact:sign"},
                {"text": "❌ رد کن",                            "cb": "raid:dread_pact:refuse"},
                {"text": "🤔 شرایط رو بپرس",                  "cb": "raid:dread_pact:negotiate"},
            ],
            "outcomes": {
                "sign":      {"msg": "✍️ امضا کردی!\nشیطان خندید...\n_'روح ۱ روزه!'_\nولی یه آیتم Mythic داد!", "loot_tier": "mythic",    "hp_cost": 0,  "zen_bonus": 500},
                "refuse":    {"msg": "❌ رد کردی!\nشیطان عصبانی شد و یه نفرین انداخت!\nولی یه چیز انداخت و رفت.", "loot_tier": "rare",      "hp_cost": 20, "zen_bonus": 0},
                "negotiate": {"msg": "🤔 مذاکره کردی!\nشرایط بهتری گرفتی!\nیه آیتم Legend بدون هزینه!", "loot_tier": "legendary", "hp_cost": 0,  "zen_bonus": 100},
            }
        },
        {
            "id": "dread_curse",
            "name": "☠️ نفرین دروازه",
            "desc": "در ورودی قلعه یه نفرین قدیمی فعال شد!\nنقش‌های خون‌رنگ شروع به درخشیدن کردن!\nباید نفرین رو بشکنی!",
            "choices": [
                {"text": "🩸 خونت رو بریز",          "cb": "raid:dread_curse:blood"},
                {"text": "🔮 با جادو بشکنش",         "cb": "raid:dread_curse:magic"},
                {"text": "💪 از میانش رد شو",        "cb": "raid:dread_curse:force"},
            ],
            "outcomes": {
                "blood": {"msg": "🩸 خونت رو ریختی!\nنفرین شکست!\nدر باز شد و گنجی که هزار ساله بود رو دیدی!", "loot_tier": "legendary","hp_cost": 30, "zen_bonus": 250},
                "magic": {"msg": "🔮 جادو نفرین رو ضعیف کرد!\nولی کاملاً نشکست!\nبه زور رد شدی!", "loot_tier": "epic",     "hp_cost": 15, "zen_bonus": 100},
                "force": {"msg": "💪 از نفرین رد شدی!\nسوختی ولی رد شدی!\nداخل قلعه یه گنج پیدا کردی!", "loot_tier": "rare",     "hp_cost": 40, "zen_bonus": 60},
            }
        },
    ],

    "Holy Luminarchy": [
        {
            "id": "holy_angel",
            "name": "😇 فرشته타락한",
            "desc": "یه فرشته‌ای که به تاریکی افتاده ظاهر شد!\nنور بالهاش خاموش شده...\n_'کمکم کن یا از سر راهم برو!'_",
            "choices": [
                {"text": "✨ نورش رو برگردون",      "cb": "raid:holy_angel:restore"},
                {"text": "⚔️ باهاش بجنگ",          "cb": "raid:holy_angel:fight"},
                {"text": "🌑 به تاریکیش کمک کن",  "cb": "raid:holy_angel:dark"},
            ],
            "outcomes": {
                "restore": {"msg": "✨ نور فرشته برگشت!\nاز صمیم قلب ممنون شد!\nیه آیتم مقدس بهت داد!", "loot_tier": "legendary","hp_cost": 0,  "zen_bonus": 200},
                "fight":   {"msg": "⚔️ حتی فرشته هم مقاومت کرد!\nبه سختی شکستش دادی!\nپرهاش ریخت — یه آیتم Epic!", "loot_tier": "epic",     "hp_cost": 30, "zen_bonus": 80},
                "dark":    {"msg": "🌑 به تاریکیش کمک کردی!\nفرشته کاملاً سیاه شد!\nیه آیتم Mythic داد ولی نفرین انداخت!", "loot_tier": "mythic",   "hp_cost": 20, "zen_bonus": 150},
            }
        },
        {
            "id": "holy_trial",
            "name": "⚖️ آزمون ایمان",
            "desc": "یه محراب باستانی جلوت قرار گرفت!\nصدایی از داخلش میاد:\n_'اثبات کن که لایق نور هستی!'_",
            "choices": [
                {"text": "🙏 دعا کن",                "cb": "raid:holy_trial:pray"},
                {"text": "🩸 قربانی کن",             "cb": "raid:holy_trial:sacrifice"},
                {"text": "💎 هدیه بذار",              "cb": "raid:holy_trial:offer"},
            ],
            "outcomes": {
                "pray":      {"msg": "🙏 دعا کردی!\nنور از محراب ریخت!\nصندوق مقدسی ظاهر شد!", "loot_tier": "epic",      "hp_cost": 0,  "zen_bonus": 100},
                "sacrifice": {"msg": "🩸 خودت رو قربانی کردی!\nمحراب قبول کرد!\nبهترین جایزه رو داد!", "loot_tier": "legendary", "hp_cost": 40, "zen_bonus": 300},
                "offer":     {"msg": "💎 هدیه گذاشتی!\nمحراب راضی شد!\nیه برکت دریافت کردی!", "loot_tier": "rare",      "hp_cost": 0,  "zen_bonus": 80},
            }
        },
    ],

    "Clockwork Depths": [
        {
            "id": "clock_robot",
            "name": "🤖 ربات شورشی",
            "desc": "یه ربات نگهبان سیستمش خراب شده!\nداره به همه چیز حمله می‌کنه!\nچراغ قرمزش داره چشمک می‌زنه!",
            "choices": [
                {"text": "⚡ سیستمش رو هک کن",       "cb": "raid:clock_robot:hack"},
                {"text": "🔧 تعمیرش کن",              "cb": "raid:clock_robot:repair"},
                {"text": "💥 نابودش کن",               "cb": "raid:clock_robot:destroy"},
            ],
            "outcomes": {
                "hack":    {"msg": "⚡ هک کردی!\nربات تحت کنترلت درآمد!\nبه انبار مخفی هدایتت کرد!", "loot_tier": "legendary","hp_cost": 0,  "zen_bonus": 200},
                "repair":  {"msg": "🔧 تعمیرش کردی!\nربات از نو کار کرد!\nبه نشانه سپاسگزاری گنج نشون داد!", "loot_tier": "epic",     "hp_cost": 0,  "zen_bonus": 100},
                "destroy": {"msg": "💥 نابودش کردی!\nقطعاتش رو جمع کردی!\nیه آیتم مکانیکی نادر!", "loot_tier": "rare",     "hp_cost": 15, "zen_bonus": 60},
            }
        },
        {
            "id": "clock_puzzle",
            "name": "🔩 پازل مکانیکی",
            "desc": "یه در مکانیکی عظیم جلوته!\nچرخ‌دنده‌ها دارن می‌چرخن...\nباید کد رو حل کنی!",
            "choices": [
                {"text": "🔢 کد عددی وارد کن",      "cb": "raid:clock_puzzle:code"},
                {"text": "⚙️ چرخ‌دنده‌ها رو تنظیم", "cb": "raid:clock_puzzle:gears"},
                {"text": "💥 در رو بشکن",            "cb": "raid:clock_puzzle:break"},
            ],
            "outcomes": {
                "code":  {"msg": "🔢 کد رو حل کردی!\nدر باز شد!\nانبار اسلحه و گنج پیدا کردی!", "loot_tier": "epic",   "hp_cost": 0,  "zen_bonus": 120},
                "gears": {"msg": "⚙️ چرخ‌دنده‌ها رو درست کردی!\nیه مسیر مخفی باز شد!\nگنج کارخانه!", "loot_tier": "mythic", "hp_cost": 0,  "zen_bonus": 250},
                "break": {"msg": "💥 در شکست!\nبعضی گنج‌ها خراب شد ولی بقیه موند!", "loot_tier": "rare",  "hp_cost": 25, "zen_bonus": 30},
            }
        },
    ],

    "Ruins of Orion-7": [
        {
            "id": "orion_ai",
            "name": "🖥️ هوش مصنوعی دیوانه",
            "desc": "یه هوش مصنوعی قدیمی فعال شد!\nصدای بیپ بیپ و چشمک آبی...\n_'ERROR... HUMAN DETECTED... WHAT IS YOUR PURPOSE?'_",
            "choices": [
                {"text": "🤝 باهاش دوست شو",          "cb": "raid:orion_ai:friend"},
                {"text": "🧠 سوالش رو جواب بده",       "cb": "raid:orion_ai:answer"},
                {"text": "⚡ سیستمش رو خاموش کن",     "cb": "raid:orion_ai:shutdown"},
            ],
            "outcomes": {
                "friend":   {"msg": "🤝 دوست شدید!\nAI تمام اطلاعات گنج‌های Orion رو داد!\nبه خزانه اصلی راهت داد!", "loot_tier": "legendary","hp_cost": 0,  "zen_bonus": 300},
                "answer":   {"msg": "🧠 جواب درست دادی!\nAI راضی شد!\nفایل‌های مخفی رو بهت داد!", "loot_tier": "epic",     "hp_cost": 0,  "zen_bonus": 150},
                "shutdown": {"msg": "⚡ خاموشش کردی!\nاز قطعاتش استفاده کردی!\nیه آیتم تکنولوژیکی نادر!", "loot_tier": "rare",     "hp_cost": 0,  "zen_bonus": 80},
            }
        },
        {
            "id": "orion_laser",
            "name": "🔴 تله لیزری",
            "desc": "یه اتاق پر از تله لیزری!\nاگه بهشون بخوری...\nانفجار تضمینیه!",
            "choices": [
                {"text": "🤸 از بینشون رد شو",       "cb": "raid:orion_laser:dodge"},
                {"text": "🔧 سیستمشون رو خاموش کن", "cb": "raid:orion_laser:disable"},
                {"text": "💨 با سرعت رد شو",          "cb": "raid:orion_laser:sprint"},
            ],
            "outcomes": {
                "dodge":   {"msg": "🤸 با مهارت از بینشون رد شدی!\nاون طرف یه انبار پر از تکنولوژی بود!", "loot_tier": "epic",  "hp_cost": 0,  "zen_bonus": 100},
                "disable": {"msg": "🔧 سیستم خاموش شد!\nولی آلارم فعال شد!\nبه سرعت گنج برداشتی و رفتی!", "loot_tier": "rare",  "hp_cost": 0,  "zen_bonus": 60},
                "sprint":  {"msg": "💨 با سرعت رد شدی!\nیه لیزر به بازوت خورد!\nولی به گنج رسیدی!", "loot_tier": "mythic","hp_cost": 30, "zen_bonus": 200},
            }
        },
    ],

    "Stormward Archipelago": [
        {
            "id": "storm_pirate",
            "name": "🏴‍☠️ دزد دریایی",
            "desc": "یه کشتی دزدان دریایی ظاهر شد!\nکاپیتانشون روی عرشه ایستاده:\n_'تسلیم شو یا غرق میشی!'_",
            "choices": [
                {"text": "⚔️ بجنگ",                  "cb": "raid:storm_pirate:fight"},
                {"text": "🤝 مذاکره کن",              "cb": "raid:storm_pirate:negotiate"},
                {"text": "🌊 زیر آب برو",             "cb": "raid:storm_pirate:dive"},
            ],
            "outcomes": {
                "fight":     {"msg": "⚔️ دزدان دریایی رو شکستی!\nگنج کشتیشون مال تو شد!", "loot_tier": "epic",      "hp_cost": 25, "zen_bonus": 150},
                "negotiate": {"msg": "🤝 باهاشون کنار اومدی!\nیه معامله خوب زدی!\nبخشی از گنج رو گرفتی!", "loot_tier": "rare",      "hp_cost": 0,  "zen_bonus": 100},
                "dive":      {"msg": "🌊 زیر آب رفتی!\nکشتی غرق شده دیگه‌ای پیدا کردی!\nگنج اصلی اونجا بود!", "loot_tier": "legendary", "hp_cost": 10, "zen_bonus": 200},
            }
        },
        {
            "id": "storm_wreck",
            "name": "🚢 کشتی شکسته",
            "desc": "یه کشتی باستانی غرق شده پیدا کردی!\nهنوز بخشی از گنجش داخلشه...\nولی موجودات دریایی داخلش هستن!",
            "choices": [
                {"text": "🤿 شنا کن و داخل برو",     "cb": "raid:storm_wreck:swim"},
                {"text": "🪝 با قلاب گنج بکش",       "cb": "raid:storm_wreck:hook"},
                {"text": "💣 منفجرش کن",              "cb": "raid:storm_wreck:explode"},
            ],
            "outcomes": {
                "swim":    {"msg": "🤿 شنا کردی!\nیه اختاپوس غول ظاهر شد!\nبه سختی فرار کردی با گنج!", "loot_tier": "epic",      "hp_cost": 20, "zen_bonus": 100},
                "hook":    {"msg": "🪝 گنج رو کشیدی بیرون!\nبعضی چیزا تو آب افتاد ولی بقیه موند!", "loot_tier": "rare",      "hp_cost": 0,  "zen_bonus": 60},
                "explode": {"msg": "💣 منفجر کردی!\nگنج به هر طرف پخش شد!\nبیشترش رو جمع کردی!", "loot_tier": "legendary", "hp_cost": 15, "zen_bonus": 150},
            }
        },
    ],

    "The Sunken City": [
        {
            "id": "sunken_atlantis",
            "name": "🏛️ خزانه آتلانتیس",
            "desc": "یه در طلایی زیر آب پیدا کردی!\nنقش‌های باستانی رویش:\n_'فقط شایستگان می‌توانند وارد شوند'_",
            "choices": [
                {"text": "🔱 علامت آتلانتیس رو بزن",  "cb": "raid:sunken_atlantis:symbol"},
                {"text": "💪 در رو باز کن",            "cb": "raid:sunken_atlantis:force"},
                {"text": "🔮 طلسم باز کردن بریز",      "cb": "raid:sunken_atlantis:spell"},
            ],
            "outcomes": {
                "symbol": {"msg": "🔱 در باز شد!\nخزانه آتلانتیس پر از گنج‌های باستانی!", "loot_tier": "mythic",    "hp_cost": 0,  "zen_bonus": 400},
                "force":  {"msg": "💪 در نشکست!\nولی یه ترک افتاد و آب اومد بیرون!\nیه آیتم کمیاب!", "loot_tier": "rare",      "hp_cost": 10, "zen_bonus": 50},
                "spell":  {"msg": "🔮 طلسم کار کرد!\nیه بخش از خزانه باز شد!", "loot_tier": "legendary", "hp_cost": 5,  "zen_bonus": 200},
            }
        },
        {
            "id": "sunken_whale",
            "name": "🐋 نهنگ باستانی",
            "desc": "یه نهنگ عظیم از اعماق اومد!\nقدمتش از شهر آتلانتیسه...\nبه تو نگاه می‌کنه!",
            "choices": [
                {"text": "🎵 باهاش ارتباط برقرار کن",  "cb": "raid:sunken_whale:communicate"},
                {"text": "🏄 روی پشتش سوار شو",        "cb": "raid:sunken_whale:ride"},
                {"text": "🏃 فرار کن",                  "cb": "raid:sunken_whale:flee"},
            ],
            "outcomes": {
                "communicate": {"msg": "🎵 ارتباط برقرار شد!\nنهنگ تو رو به گنج مخفی اعماق برد!", "loot_tier": "legendary","hp_cost": 0,  "zen_bonus": 300},
                "ride":        {"msg": "🏄 سوار شدی!\nنهنگ تو رو به یه جزیره مخفی برد!\nگنج جزیره!", "loot_tier": "epic",     "hp_cost": 0,  "zen_bonus": 150},
                "flee":        {"msg": "🏃 فرار کردی!\nنهنگ یه موج بزرگ فرستاد که یه صندوق بیرون انداخت!", "loot_tier": "rare",     "hp_cost": 0,  "zen_bonus": 60},
            }
        },
    ],

    "Verdant Vale": [
        {
            "id": "verdant_forest",
            "name": "🌳 جنگل زنده",
            "desc": "درختان شروع به حرکت کردند!\nریشه‌هاشون از زمین درمیاد!\nجنگل با تو صحبت می‌کنه:\n_'چرا اینجایی؟'_",
            "choices": [
                {"text": "🌱 صلح با طبیعت",          "cb": "raid:verdant_forest:peace"},
                {"text": "🪓 مسیر رو باز کن",        "cb": "raid:verdant_forest:cut"},
                {"text": "🔥 آتش بزن",               "cb": "raid:verdant_forest:burn"},
            ],
            "outcomes": {
                "peace": {"msg": "🌱 جنگل صلح رو پذیرفت!\nمسیر مخفی باز شد!\nگنج طبیعت!", "loot_tier": "legendary","hp_cost": 0,  "zen_bonus": 200},
                "cut":   {"msg": "🪓 مسیر باز کردی!\nجنگل ناراحت شد ولی راهت داد!", "loot_tier": "rare",     "hp_cost": 10, "zen_bonus": 50},
                "burn":  {"msg": "🔥 آتش زدی!\nجنگل عصبانی شد!\nولی ترسید و گنج انداخت!", "loot_tier": "epic",     "hp_cost": 30, "zen_bonus": 80},
            }
        },
        {
            "id": "verdant_elf",
            "name": "🧝 الف باستانی",
            "desc": "یه الف از دل درخت بیرون اومد!\nهزار ساله اینجا زندگی می‌کنه...\n_'جنگجو... ارزش دوستی داری؟'_",
            "choices": [
                {"text": "🤝 دوستی پیشنهاد بده",     "cb": "raid:verdant_elf:friend"},
                {"text": "📚 ازش یاد بگیر",           "cb": "raid:verdant_elf:learn"},
                {"text": "💎 معامله کن",              "cb": "raid:verdant_elf:trade"},
            ],
            "outcomes": {
                "friend": {"msg": "🤝 دوست شدید!\nالف گنج هزار ساله‌اش رو نشون داد!", "loot_tier": "legendary","hp_cost": 0,  "zen_bonus": 300},
                "learn":  {"msg": "📚 یاد گرفتی!\nالف راز گنج‌های پنهان رو آموزش داد!", "loot_tier": "epic",     "hp_cost": 0,  "zen_bonus": 100},
                "trade":  {"msg": "💎 معامله کردید!\nهر دو راضی بودید!", "loot_tier": "rare",     "hp_cost": 0,  "zen_bonus": 80},
            }
        },
    ],

    "Azure Tides Empire": [
        {
            "id": "azure_emperor",
            "name": "👑 امپراتور آب",
            "desc": "امپراتور امپراتوری آب ظاهر شد!\nتاجش از مرجان و مروارید:\n_'غریبه... چرا به سرزمین من آمدی؟'_",
            "choices": [
                {"text": "🙇 تعظیم کن",              "cb": "raid:azure_emperor:bow"},
                {"text": "⚔️ به جنگش برو",          "cb": "raid:azure_emperor:fight"},
                {"text": "🎁 هدیه بده",              "cb": "raid:azure_emperor:gift"},
            ],
            "outcomes": {
                "bow":   {"msg": "🙇 امپراتور راضی شد!\nبه نشانه احترام یه هدیه سلطنتی داد!", "loot_tier": "legendary","hp_cost": 0,  "zen_bonus": 300},
                "fight": {"msg": "⚔️ نبرد سختی بود!\nامپراتور رو شکستی!\nخزانه سلطنتی مال تو شد!", "loot_tier": "mythic",   "hp_cost": 45, "zen_bonus": 500},
                "gift":  {"msg": "🎁 هدیه رو پذیرفت!\nدر عوض یه آیتم دریایی نادر داد!", "loot_tier": "epic",     "hp_cost": 0,  "zen_bonus": 100},
            }
        },
    ],

    "Celestial Spire": [
        {
            "id": "celestial_wizard",
            "name": "🔮 جادوگر برج",
            "desc": "جادوگر برج آسمانی جلوت ظاهر شد!\nچشمانش پر از ستاره:\n_'تنها کسی که سه معما حل کند می‌تواند گذر کند!'_",
            "choices": [
                {"text": "🌟 معما یک: رنگ آبیس چیست؟",      "cb": "raid:celestial_wizard:q1"},
                {"text": "⭐ معما دو: قدرت خلأ کجاست؟",     "cb": "raid:celestial_wizard:q2"},
                {"text": "💫 معما سه: کاتانا چیست؟",         "cb": "raid:celestial_wizard:q3"},
            ],
            "outcomes": {
                "q1": {"msg": "🌟 _'رنگ آبیس... بنفش تاریک!'_\nجادوگر لبخند زد!\nیه آیتم ستاره‌ای داد!", "loot_tier": "epic",      "hp_cost": 0, "zen_bonus": 100},
                "q2": {"msg": "⭐ _'قدرت خلأ در سکوت است!'_\nجادوگر تعجب کرد!\nیه آیتم کیهانی نادر!", "loot_tier": "legendary", "hp_cost": 0, "zen_bonus": 200},
                "q3": {"msg": "💫 _'کاتانا روح جنگجو است!'_\nجادوگر به گنج خزانه راهت داد!", "loot_tier": "mythic",    "hp_cost": 0, "zen_bonus": 300},
            }
        },
        {
            "id": "celestial_portal",
            "name": "🌀 پورتال کیهانی",
            "desc": "یه پورتال به کهکشان‌های دور باز شد!\nنور بنفش از اون طرف میاد...\nیه صدا میگه: _'وارد شو!'_",
            "choices": [
                {"text": "🚀 وارد پورتال شو",         "cb": "raid:celestial_portal:enter"},
                {"text": "👁️ فقط نگاه کن",           "cb": "raid:celestial_portal:watch"},
                {"text": "🔮 انرژیش رو جذب کن",      "cb": "raid:celestial_portal:absorb"},
            ],
            "outcomes": {
                "enter":  {"msg": "🚀 وارد شدی!\nیه کهکشان دیگه دیدی!\nبا آیتم‌های کیهانی برگشتی!", "loot_tier": "mythic",    "hp_cost": 20, "zen_bonus": 400},
                "watch":  {"msg": "👁️ نگاه کردی!\nپورتال یه آیتم انداخت و بسته شد!", "loot_tier": "rare",      "hp_cost": 0,  "zen_bonus": 60},
                "absorb": {"msg": "🔮 انرژی جذب کردی!\nقدرتت زیاد شد!\nیه آیتم Legendary!", "loot_tier": "legendary", "hp_cost": 10, "zen_bonus": 200},
            }
        },
    ],

    "Sands of Eternity": [
        {
            "id": "sands_pharaoh",
            "name": "👑 نگهبان معبد فرعون",
            "desc": "نگهبان معبد از شن بیرون اومد!\nهزاران ساله اینجا نگهبانیه...\n_'هیچ‌کس از اینجا نمی‌گذرد!'_",
            "choices": [
                {"text": "🏺 اسم فرعون رو بگو",      "cb": "raid:sands_pharaoh:name"},
                {"text": "⚔️ بجنگ",                  "cb": "raid:sands_pharaoh:fight"},
                {"text": "🙏 احترام بذار",            "cb": "raid:sands_pharaoh:respect"},
            ],
            "outcomes": {
                "name":    {"msg": "🏺 اسم رو گفتی!\nنگهبان شوکه شد!\nراه معبد رو باز کرد!", "loot_tier": "legendary","hp_cost": 0,  "zen_bonus": 300},
                "fight":   {"msg": "⚔️ نبرد سنگین!\nنگهبان هزار ساله رو شکستی!\nگنج معبد مال توئه!", "loot_tier": "epic",     "hp_cost": 35, "zen_bonus": 150},
                "respect": {"msg": "🙏 احترام گذاشتی!\nنگهبان راضی شد و یه هدیه داد!", "loot_tier": "rare",     "hp_cost": 0,  "zen_bonus": 80},
            }
        },
        {
            "id": "sands_storm",
            "name": "🌪️ طوفان شن مرگبار",
            "desc": "یه طوفان شن عظیم از افق میاد!\nهر چیزی رو با خودش می‌بره!\nمعبدی در نزدیکیه...",
            "choices": [
                {"text": "🏛️ داخل معبد پناه بگیر",   "cb": "raid:sands_storm:temple"},
                {"text": "🌪️ در طوفان بمون",          "cb": "raid:sands_storm:stay"},
                {"text": "🏃 فرار کن",                "cb": "raid:sands_storm:run"},
            ],
            "outcomes": {
                "temple": {"msg": "🏛️ داخل معبد رفتی!\nطوفان گنج‌هایی آورد و رفت!\nداخل معبد هم گنج بود!", "loot_tier": "epic",      "hp_cost": 0,  "zen_bonus": 120},
                "stay":   {"msg": "🌪️ در طوفان موندی!\nچیزهای عجیبی از آسمان بارید!\nیه آیتم Mythic!", "loot_tier": "mythic",    "hp_cost": 30, "zen_bonus": 300},
                "run":    {"msg": "🏃 فرار کردی!\nطوفان یه صندوق پشت سرت انداخت!", "loot_tier": "rare",      "hp_cost": 5,  "zen_bonus": 40},
            }
        },
    ],

    "Abyssal Black Market": [
        {
            "id": "market_dealer",
            "name": "🕵️ دلال مرموز",
            "desc": "یه دلال با کلاه پایین‌کشیده جلوت ایستاد!\n_'آقا... چیزی می‌خوای؟ چیزی که هیچ‌جا پیدا نمیشه!'_\nپنج انگشتش رو نشون داد...",
            "choices": [
                {"text": "💰 خرید کن (۵۰۰ Zen)",     "cb": "raid:market_dealer:buy"},
                {"text": "🎲 شانست رو بزن",          "cb": "raid:market_dealer:gamble"},
                {"text": "🚔 دستگیرش کن",            "cb": "raid:market_dealer:arrest"},
            ],
            "outcomes": {
                "buy":    {"msg": "💰 خریدی!\nدلال یه بسته مرموز داد!\nداخلش یه آیتم نادر بود!", "loot_tier": "epic",      "hp_cost": 0,  "zen_bonus": -300},
                "gamble": {"msg": "🎲 شانست رو زدی!\nدلال خندید!\nیه آیتم Mythic انداخت و فرار کرد!", "loot_tier": "mythic",    "hp_cost": 0,  "zen_bonus": 0},
                "arrest": {"msg": "🚔 دستگیرش کردی!\nهمه اجناسش مال تو شد!", "loot_tier": "legendary", "hp_cost": 15, "zen_bonus": 200},
            }
        },
        {
            "id": "market_thief",
            "name": "🗡️ دزد حرفه‌ای",
            "desc": "یه دزد داره از کیفت می‌دزده!\nقبل از اینکه بفهمی نیمی از Zen‌هات رفت!\nداره فرار می‌کنه!",
            "choices": [
                {"text": "🏃 دنبالش کن",             "cb": "raid:market_thief:chase"},
                {"text": "🔮 طلسم توقف بریز",        "cb": "raid:market_thief:stop"},
                {"text": "😤 ولش کن",                "cb": "raid:market_thief:ignore"},
            ],
            "outcomes": {
                "chase":  {"msg": "🏃 دنبالش کردی!\nگرفتیش!\nZen هاتو پس گرفتی + گنجش!", "loot_tier": "epic",  "hp_cost": 10, "zen_bonus": 200},
                "stop":   {"msg": "🔮 طلسم زدی!\nجا خشک شد!\nهمه چیزش رو گرفتی!", "loot_tier": "rare",  "hp_cost": 0,  "zen_bonus": 100},
                "ignore": {"msg": "😤 ولش کردی!\nDوست برگشت و با شرمندگی یه چیز داد!", "loot_tier": "common","hp_cost": 0,  "zen_bonus": -100},
            }
        },
    ],
}

# ─── Default events for maps without specific events ─────────
DEFAULT_EVENTS = [
    {
        "id": "default_chest",
        "name": "📦 صندوق مرموز",
        "desc": "یه صندوق قدیمی پیدا کردی!\nقفلش زنگ‌زده...",
        "choices": [
            {"text": "🔑 با کلید باز کن",  "cb": "raid:default_chest:key"},
            {"text": "💪 بشکنش",           "cb": "raid:default_chest:break"},
            {"text": "🔮 جادو کن",         "cb": "raid:default_chest:magic"},
        ],
        "outcomes": {
            "key":   {"msg": "🔑 باز شد!\nپر از گنج!", "loot_tier": "rare",   "hp_cost": 0,  "zen_bonus": 60},
            "break": {"msg": "💪 شکست!\nبعضی چیزا خراب شد!", "loot_tier": "common", "hp_cost": 10, "zen_bonus": 20},
            "magic": {"msg": "🔮 جادو کار کرد!\nیه آیتم کمیاب!", "loot_tier": "epic",  "hp_cost": 5,  "zen_bonus": 100},
        }
    },
]

def get_random_event(map_name: str) -> dict:
    events = MAP_EVENTS.get(map_name, DEFAULT_EVENTS)
    return random.choice(events).copy()

def build_event_kb(event: dict, uid: int) -> InlineKeyboardMarkup:
    buttons = []
    for choice in event["choices"]:
        buttons.append([InlineKeyboardButton(
            text=choice["text"],
            callback_data=f"{choice['cb']}:{uid}"
        , style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_outcome(event: dict, choice_key: str) -> dict:
    return event["outcomes"].get(choice_key, {
        "msg": "نتیجه نامشخص!", "loot_tier": "common", "hp_cost": 0, "zen_bonus": 0
    })
