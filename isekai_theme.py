# ============================================================
#  ASTRAL ABYSS — لایه‌ی حس‌وحالِ ایزکای (Isekai Flavor Layer)
# ------------------------------------------------------------
#  این ماژول هیچ منطقِ بازی رو عوض نمی‌کنه — فقط یه لایه‌ی *نمایشی*
#  رو کاراکترهای بازی (اسمِ نقشه‌ها) اضافه می‌کنه. کلیدهای داخلیِ
#  نقشه‌ها (همون رشته‌های انگلیسیِ "Verdant Vale" و...) دست‌نخورده
#  می‌مونن، چون ده‌ها فایلِ دیگه (لوت/ریید/کدکس/باس/گیلد/مزرعه) دقیقاً
#  با همین رشته‌ها به‌عنوانِ کلید کار می‌کنن — تغییرِ خودِ کلیدها یعنی
#  باید ده‌ها فایل رو هم‌زمان و بدونِ خطا آپدیت کنیم که ریسکِ کرش‌کردنِ
#  ربات رو بالا می‌بره. به‌جاش، هرجا اسمِ نقشه به بازیکن نشون داده
#  می‌شه (نه جایی که به‌عنوانِ کلیدِ دیکشنری استفاده می‌شه)، از
#  map_label() یا map_full_label() استفاده کن.
# ============================================================

# ─── اسمِ ژاپنی/آناخوانای هر قلمرو (کلیدِ داخلی → نمایش) ──────────
MAP_JP_NAME: dict[str, str] = {
    "Abyssal Black Market":  "闇市 (Yamiichi)",
    "Sands of Eternity":     "永遠の砂漠 (Eien no Sabaku)",
    "Holy Luminarchy":       "光の都 (Hikari no Miyako)",
    "Celestial Spire":       "天空の塔 (Tenkuu no Tou)",
    "Frostheim":             "雪の王国 (Yuki no Oukoku)",
    "Voidbreak Wastes":      "虚無の荒野 (Kyomu no Kouya)",
    "Azure Tides Empire":    "蒼の帝国 (Ao no Teikoku)",
    "Stormward Archipelago": "嵐の群島 (Arashi no Gunto)",
    "The Sunken City":       "水没の都 (Suibotsu no Miyako)",
    "Verdant Vale":          "精霊の森 (Seirei no Mori)",
    "Emberhollow":           "炎の谷 (Honoo no Tani)",
    "Dragonnest Peaks":      "竜の巣 (Ryuu no Su)",
    "Ruins of Orion-7":      "オリオン7遺跡 (Orion-7 Iseki)",
    "Dreadgate Citadel":     "忘却の砦 (Boukyaku no Toride)",
    "Clockwork Depths":      "絡繰工廷 (Karakuri Koutei)",
    "Throne of Oblivion":    "忘却の玉座 (Bourei no Gyokuza)",
}

# ─── زیرنویسِ ایزکاییِ هر قلمرو — جایگزینِ desc انگلیسیِ MAPS_DATA ──
MAP_JP_DESC: dict[str, str] = {
    "Abyssal Black Market":  "بازارِ سایه‌ها — جایی که هیچ سؤالی پرسیده نمی‌شه.",
    "Sands of Eternity":     "صحرایی که زمان توش انگار متوقف شده.",
    "Holy Luminarchy":       "پایتختِ نور — مقرِ کلیسای اعظم.",
    "Celestial Spire":       "برجی معلق میانِ ابرها، خونه‌ی ستاره‌شناسان.",
    "Frostheim":             "قلمروی یخ‌زده‌ای که هیچ‌وقت بهار نمی‌بینه.",
    "Voidbreak Wastes":      "سرزمینی که واقعیت توش می‌شکنه.",
    "Azure Tides Empire":    "امپراتوریِ موج‌های آبی‌رنگِ بی‌پایان.",
    "Stormward Archipelago": "جزایرِ طوفانی، پناهگاهِ دزدانِ دریایی.",
    "The Sunken City":       "شهرِ غرق‌شده‌ای زیرِ سایه‌ی امواج.",
    "Verdant Vale":          "جنگلی که روحِ طبیعت توش نفس می‌کشه.",
    "Emberhollow":           "دره‌ای که همیشه زیرِ خاکسترِ آتشفشانه.",
    "Dragonnest Peaks":      "قله‌هایی که خونه‌ی اژدهایانِ باستانیه.",
    "Ruins of Orion-7":      "خرابه‌های یه تمدنِ فراموش‌شده از ستاره‌ها.",
    "Dreadgate Citadel":     "دژی که حتی نورِ خورشید هم واردش نمی‌شه.",
    "Clockwork Depths":      "شهرِ زیرزمینیِ چرخ‌دنده‌ها و کارآکوریِ دورف‌ها.",
    "Throne of Oblivion":    "تختی که آخرین پادشاهِ دنیا هم ازش فرار کرد.",
}


def map_label(internal_name: str) -> str:
    """اسمِ ژاپنیِ نقشه (بدونِ اسمِ اصلی) — برای جاهایی که فضا کمه."""
    return MAP_JP_NAME.get(internal_name, internal_name)


def map_full_label(internal_name: str) -> str:
    """اسمِ اصلی + اسمِ ژاپنی، برای جاهایی که فضا اجازه می‌ده — مثلاً:
    'Verdant Vale — 精霊の森 (Seirei no Mori)'"""
    jp = MAP_JP_NAME.get(internal_name)
    return f"{internal_name} — {jp}" if jp else internal_name


# ============================================================
#  🏰 REALM_DATA — لایه‌ی «قلمرو» (امپراتوری/پادشاهی/شهر آزاد و...)
# ------------------------------------------------------------
#  دقیقاً همون فلسفه‌ی MAP_JP_NAME: هیچ منطقی عوض نمی‌شه، فقط یه
#  لایه‌ی نمایشیِ عمیق‌تر رو هرکدوم از ۱۵ نقشه سوار می‌کنیم — هر
#  نقشه دیگه صرفاً یه «منطقه» نیست، بلکه یه قلمروِ کاملِ ایزکاییه:
#  حکومت (امپراتوری/پادشاهی/فدراسیون/شهرِ آزاد و...)، حاکم، پایتخت،
#  و چندتا شهر/محله‌ی دیگه. از realm_line() / realm_block() هرجا
#  که سفر/ورود به مپ نمایش داده می‌شه استفاده کن.
# ============================================================
REALM_DATA: dict[str, dict] = {
    "Abyssal Black Market": {
        "polity": "شهرِ آزاد",
        "name": "یامی‌ایچیِ آزاد",
        "ruler_title": "سرکرده‌ی بازار",
        "ruler_name": "کیجین بی‌چهره",
        "capital": "میدانِ معامله‌ی سیاه",
        "cities": ["کوچه‌ی دلالان", "بندرِ پنهان"],
        "tagline": "جایی که هیچ پرچمی حکومت نمی‌کنه — فقط طلا حرف می‌زنه.",
    },
    "Sands of Eternity": {
        "polity": "پادشاهیِ",
        "name": "شنِ جاودان",
        "ruler_title": "سلطان",
        "ruler_name": "راشدینِ سوم",
        "capital": "الکاهریه",
        "cities": ["واحه‌ی سپید", "دروازه‌ی کاروان"],
        "tagline": "قدیمی‌ترین پادشاهیِ دنیا — جایی که حتی زمان هم خوابش برده.",
    },
    "Holy Luminarchy": {
        "polity": "قلمروِ مقدسِ",
        "name": "نور",
        "ruler_title": "اسقفِ اعظم",
        "ruler_name": "سراف",
        "capital": "هایلوریا",
        "cities": ["دهکده‌ی زائران", "برجِ ناقوس"],
        "tagline": "پایتختِ ایمان — جایی که هیچ سایه‌ای دووم نمیاره.",
    },
    "Celestial Spire": {
        "polity": "شورای",
        "name": "ستاره‌شناسانِ آسمانی",
        "ruler_title": "کهنه‌استادِ برج",
        "ruler_name": "الدریک",
        "capital": "تنکویا",
        "cities": ["رصدگاهِ غربی", "پلکانِ ابرها"],
        "tagline": "یه برجِ معلق که هیچ‌وقت زمین رو لمس نمی‌کنه.",
    },
    "Frostheim": {
        "polity": "پادشاهیِ",
        "name": "یخِ ابدی",
        "ruler_title": "ملکه",
        "ruler_name": "اسکادی",
        "capital": "یوکی‌کیو",
        "cities": ["دهکده‌ی گرگ‌سواران", "قلعه‌ی بلورین"],
        "tagline": "قلمروی که بهار توش فقط یه افسانه‌ست.",
    },
    "Voidbreak Wastes": {
        "polity": "سرزمینِ بی‌قانونِ",
        "name": "خلأ",
        "ruler_title": None,
        "ruler_name": None,
        "capital": "آخرین پناهگاه",
        "cities": ["حفره‌ی فراموشی", "کارخانه‌ی فاسد"],
        "tagline": "دیگه هیچ‌کس اینجا حکومت نمی‌کنه — فقط واقعیت داره می‌شکنه.",
    },
    "Azure Tides Empire": {
        "polity": "امپراتوریِ",
        "name": "موجِ آبی",
        "ruler_title": "امپراتور",
        "ruler_name": "کایتو",
        "capital": "آئوتو",
        "cities": ["بندرِ مروارید", "جزیره‌ی نهنگ"],
        "tagline": "امپراتوریِ بی‌پایانِ اقیانوس — هر موجش یه داستانه.",
    },
    "Stormward Archipelago": {
        "polity": "فدراسیونِ آزادِ",
        "name": "جزایرِ طوفان",
        "ruler_title": "ناخدای اعظم",
        "ruler_name": "بارباروسای سرخ",
        "capital": "بندرِ سیاه",
        "cities": ["اسکله‌ی دزدان", "جزیره‌ی فراموشی"],
        "tagline": "اینجا هیچ پادشاهی حکم نمی‌رونه — فقط بادبان و شمشیر.",
    },
    "The Sunken City": {
        "polity": "دولتِ باستانیِ",
        "name": "زیرِ آب",
        "ruler_title": "کاهنِ اعماق",
        "ruler_name": "نریوس",
        "capital": "آتلانتیرا",
        "cities": ["معبدِ غرق‌شده", "بازارِ مرجانی"],
        "tagline": "تمدنی که هزار سال پیش زیرِ موج‌ها خوابید و بیدار نشد.",
    },
    "Verdant Vale": {
        "polity": "قلمروِ الف‌هایِ",
        "name": "جنگل",
        "ruler_title": "بانو",
        "ruler_name": "سیلوانا",
        "capital": "الوندیل",
        "cities": ["روستای ریشه‌ها", "معبدِ سبز"],
        "tagline": "جنگلی که خودش هنوز نفس می‌کشه.",
    },
    "Emberhollow": {
        "polity": "قلمروِ",
        "name": "آتشِ ابدی",
        "ruler_title": "سردارِ شعله",
        "ruler_name": "ایگنیس",
        "capital": "امبرگارد",
        "cities": ["دره‌ی کوره‌ها", "معدنِ سرخ"],
        "tagline": "زمینی که هیچ‌وقت خاکسترش سرد نمی‌شه.",
    },
    "Dragonnest Peaks": {
        "polity": "قلمروِ",
        "name": "اژدهایانِ باستانی",
        "ruler_title": "اژدهای ارشد",
        "ruler_name": "وایرمث",
        "capital": "لانه‌ی بلند",
        "cities": ["دهکده‌ی کوهستان", "قبرستانِ اژدها"],
        "tagline": "تنها قلمروی که هیچ انسانی توش تاج نداره.",
    },
    "Ruins of Orion-7": {
        "polity": "تمدنِ گم‌شده‌ی",
        "name": "اوریون-۷",
        "ruler_title": "هوشِ مصنوعیِ باقی‌مانده",
        "ruler_name": "سیستم-۷",
        "capital": "مرکزِ فرماندهی",
        "cities": ["ناحیه‌ی صنعتی", "آزمایشگاهِ ۷"],
        "tagline": "تمدنی از میانِ ستاره‌ها که دیگه کسی زنده نمونده تا حکومتش کنه.",
    },
    "Dreadgate Citadel": {
        "polity": "دژِ نفرین‌شده‌ی",
        "name": "دروازه‌ی هراس",
        "ruler_title": "لردِ سایه",
        "ruler_name": "مورگات",
        "capital": "دژِ مرکزی",
        "cities": ["زندانِ زیرین", "قبرستانِ بی‌نام"],
        "tagline": "جایی که حتی نورِ خورشید هم اجازه‌ی ورود نداره.",
    },
    "Clockwork Depths": {
        "polity": "جمهوریِ دورف‌هایِ",
        "name": "کارآکوری",
        "ruler_title": "استادکارگاهِ اعظم",
        "ruler_name": "برندین",
        "capital": "کارآکوریوتی",
        "cities": ["کارگاهِ دنده‌ها", "معدنِ فولاد"],
        "tagline": "شهری که هیچ‌وقت چرخ‌دنده‌هاش از حرکت نمی‌ایستن.",
    },
    "Throne of Oblivion": {
        "polity": "قلمروِ مرده‌ی",
        "name": "فراموشی",
        "ruler_title": "پادشاهِ خاکسترها",
        "ruler_name": "اُبلیویون",
        "capital": "تالارِ تاجِ خاکستری",
        "cities": ["دخمه‌ی پادشاهانِ مرده", "زندانِ ابدیت"],
        "tagline": "سخت‌ترین قلمروِ دنیا — ولی گنجینه‌اش هم به همون اندازه بی‌نظیره.",
    },
}


def realm_name(internal_name: str) -> str:
    """اسمِ کاملِ قلمرو با نوعِ حکومتش، مثلاً: 'امپراتوریِ موجِ آبی'."""
    r = REALM_DATA.get(internal_name)
    if not r:
        return internal_name
    return f"{r['polity']} {r['name']}".strip()


def realm_line(internal_name: str) -> str:
    """یه خطِ کوتاه برای پیام‌های سفر/ورود، مثلاً:
    '🏰 امپراتوریِ موجِ آبی — پایتخت: آئوتو'"""
    r = REALM_DATA.get(internal_name)
    if not r:
        return ""
    return f"🏰 {realm_name(internal_name)} — پایتخت: **{r['capital']}**"


def realm_block(internal_name: str) -> str:
    """یه بلوکِ کاملِ اطلاعاتِ قلمرو، برای صفحه‌ی ورود به مپ یا دستورِ /realm."""
    r = REALM_DATA.get(internal_name)
    if not r:
        return ""
    lines = [f"🏰 **{realm_name(internal_name)}**"]
    if r.get("ruler_title"):
        who = f"{r['ruler_title']}" + (f" {r['ruler_name']}" if r.get("ruler_name") else "")
        lines.append(f"👑 حاکم: {who}")
    lines.append(f"🏙️ پایتخت: **{r['capital']}**")
    if r.get("cities"):
        lines.append(f"🏘️ شهرها/محله‌های شناخته‌شده: {'، '.join(r['cities'])}")
    lines.append(f"_{r['tagline']}_")
    return "\n".join(lines)


def random_city(internal_name: str) -> str:
    """یه اسمِ شهر/محلِ تصادفی از قلمرو — برای فلیورِ رویدادها و پیام‌های تصادفی."""
    import random as _r
    r = REALM_DATA.get(internal_name)
    if not r:
        return internal_name
    pool = [r["capital"], *r.get("cities", [])]
    return _r.choice(pool) if pool else internal_name


# ─── گیلدِ ماجراجویی: رتبه‌بندیِ F تا S (+ SS برای Rebirth) ────────
# ترتیب باید صعودی بمونه — rank_for_level روی همین لیست پیمایش می‌کنه.
GUILD_RANKS: list[tuple[int, str, str]] = [
    # (حداقلِ سطح، حرفِ رتبه، اسمِ فارسیِ رتبه)
    (1,   "F", "تازه‌کار"),
    (10,  "E", "ماجراجوی نوپا"),
    (25,  "D", "شکارچیِ رسمی"),
    (50,  "C", "قهرمانِ درجه‌سه"),
    (80,  "B", "قهرمانِ درجه‌دو"),
    (120, "A", "قهرمانِ درجه‌یک"),
    (160, "S", "افسانه‌ی زنده"),
]
RANK_SS_LABEL = ("SS", "فراتر از افسانه")  # فقط برای بازیکن‌های Rebirth-کرده


def rank_for_level(level: int, rebirth_count: int = 0) -> tuple[str, str]:
    """رتبه‌ی گیلدِ ماجراجویی بر اساسِ سطح (و Rebirth) رو برمی‌گردونه:
    (حرفِ رتبه, اسمِ فارسی). مثلاً ('C', 'قهرمانِ درجه‌سه')."""
    if rebirth_count > 0 and level >= 160:
        return RANK_SS_LABEL
    label = ("F", "تازه‌کار")
    for min_lv, letter, name_fa in GUILD_RANKS:
        if level >= min_lv:
            label = (letter, name_fa)
        else:
            break
    return label


def rank_line(player: dict) -> str:
    """یه خطِ آماده برای /status: '🎫 رتبه‌ی گیلد: C (قهرمانِ درجه‌سه)'"""
    letter, name_fa = rank_for_level(player.get("level", 1), player.get("rebirth_count", 0))
    return f"🎫 رتبه‌ی گیلدِ ماجراجویی: **{letter}** ({name_fa})"


def rank_up_announcement(old_level: int, new_level: int, rebirth_count: int = 0) -> str | None:
    """اگه بینِ old_level و new_level رتبه‌ی گیلد عوض شده باشه، یه پیامِ
    جشن‌گرفتنِ سبکِ ایزکای برمی‌گردونه (مثلِ ارتقای رتبه تو گیلدِ
    ماجراجویی) — وگرنه None. تو مسیرهای اصلیِ لول‌آپ (حمله/لوت) صدا زده
    می‌شه تا رتبه‌ی جدید حسِ یه رویداد واقعی رو داشته باشه، نه فقط یه عدد."""
    old_letter, _ = rank_for_level(old_level, rebirth_count)
    new_letter, new_name = rank_for_level(new_level, rebirth_count)
    if new_letter == old_letter:
        return None
    return (
        f"🏯 **گیلدِ ماجراجویی اطلاع داد:**\n"
        f"رتبه‌ت از **{old_letter}** به **{new_letter}** ارتقا پیدا کرد — از این به بعد "
        f"به‌عنوانِ «**{new_name}**» شناخته می‌شی!"
    )


# ============================================================
#  🏯 دستورِ /meikyu — دیدنِ شهرِ مرکزی/دخمه‌ای (میکیو) و رتبه‌ی فعلی
# ============================================================
NPC_FLAVOR = [
    "🧝 **مسئولِ پذیرشِ گیلد:** «رتبه‌ت هرچی بالاتر بره، مأموریت‌های بهتری بهت پیشنهاد می‌دیم.»",
    "⚒️ **آهنگرِ کارآکوری:** «یه تیغه از Karakuri Koutei بخر، تفاوتش رو تو نبردِ بعدی حس می‌کنی.»",
    "🍶 **صاحبِ میخانه:** «هرشب یه ماجراجوی جدید میاد اینجا و قسم می‌خوره فردا میره ته دخمه رو ببینه...»",
    "🕯️ **پیرمردِ کتابخونه:** «هرچی رزوننست بالاتر بره، صدای مائو رو واضح‌تر می‌شنوی. مراقب باش.»",
]


def meikyu_text(player: dict) -> str:
    letter, name_fa = rank_for_level(player.get("level", 1), player.get("rebirth_count", 0))
    npc = NPC_FLAVOR[player.get("level", 1) % len(NPC_FLAVOR)]
    return (
        "🏯 **میکیو (迷宮の街 / Meikyuu no Machi)**\n"
        "_شهری که مستقیم دورِ دهانه‌ی یه دخمه‌ی بی‌انتها ساخته شده._\n\n"
        f"🎫 رتبه‌ی فعلیت تو گیلدِ ماجراجویی: **{letter}** ({name_fa})\n\n"
        f"{npc}\n\n"
        "💡 هرچی سطحت بالاتر بره، رتبه‌ت خودکار تو گیلدِ ماجراجویی ارتقا پیدا می‌کنه — "
        "تا برسی به رتبه‌ی افسانه‌ای **S**، یا حتی فراتر از اون با Rebirth."
    )


def register_isekai_handlers(dp, bot):
    from aiogram.filters import Command
    from aiogram.types import Message

    @dp.message(Command("meikyu"))
    async def cmd_meikyu(msg: Message):
        from database import get_player
        player = get_player(msg.from_user.id)
        if not player:
            return await msg.answer("❗️ اول /start رو بزن.")
        await msg.answer(meikyu_text(player))

    @dp.message(Command("realm"))
    async def cmd_realm(msg: Message):
        from database import get_player
        player = get_player(msg.from_user.id)
        if not player:
            return await msg.answer("❗️ اول /start رو بزن.")
        map_name = player.get("map", "")
        block = realm_block(map_name)
        if not block:
            return await msg.answer("🌫️ هنوز تو هیچ قلمروِ شناخته‌شده‌ای نیستی.")
        await msg.answer(f"📍 تو الان تویِ این قلمرویی:\n\n{block}")

ISEKAI_LORE = """
🌌 جهانِ Astral Abyss

یه زمانی، جهان یکپارچه بود. تو و دوقلوت کیارَش داشتید سفر می‌کردید که
Abyss ظهور کرد — یه شکافِ عظیم که واقعیت رو پاره کرد و جهان رو به
۱۵ قلمروِ جدا از هم شکافت (Isekai واقعی: هرکسی که زنده موند، انگار به
یه دنیای کاملاً جدید «احضار» شده بود).

🏯 میکیو (迷宮の街 / Meikyuu no Machi) — «شهرِ دخمه»
مرکزِ نمادینِ این دنیای شکسته: یه شهر که مستقیم دورِ دهانه‌ی یه دخمه‌ی
بی‌انتها ساخته شده. اینجا مقرِ «گیلدِ ماجراجویی»یه — همون‌جایی که هر
بازیکنِ تازه‌وارد اولین رتبه‌ش (F) رو می‌گیره و قدم‌به‌قدم تا S بالا می‌ره.

👹 مائو (魔王 / Maō) — «لردِ شیطانی»
منبعِ فسادی که world_pulse (ضربانِ آبیس) رو تغذیه می‌کنه. هرچی گیجِ
فساد بالاتر بره، سایه‌ی مائو پررنگ‌تر می‌شه — ایونت‌های خطرناک‌تر،
باس‌های جهانیِ قوی‌تر. شکست‌دادنِ نهاییِ مائو هدفِ بزرگِ آرکِ فصلیه.

⚔️ حزبِ قهرمانان (パーティー / Party)
گیلدها و تیم‌ها همون «پارتی»ی کلاسیکِ ایزکایی‌ان — گروهی که با هم علیه
تهدیدِ مشترک می‌جنگن. رتبه‌ی گیلد (F→S، پایین‌تر رو ببین) دقیقاً همون
سیستمِ رتبه‌بندیِ گیلدهای ماجراجوییِ انیمه‌های ایزکاییه.

📊 پنجره‌ی وضعیت (ステータス / Status Window)
/status همون «پنجره‌ی وضعیتِ» کلاسیکِ ایزکاییه — HP/XP/سطح/آیتم، دقیقاً
همون‌جوری که تو یه دنیای گیم‌مانند انتظار داری ببینی.
"""
