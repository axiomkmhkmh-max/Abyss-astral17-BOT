# -*- coding: utf-8 -*-
"""
divine_seals.py

سیستم «مُهرهای نخستین» (Divine Seals).

برخلاف کاراکترها (که رندوم یا با گاچا به دست میان)، مُهرها فقط با
دستِ ادمین به بازیکن داده می‌شن — چون داستانی این‌جوریه که یه
«نخستین» (Firsts؛ همون‌هایی که کاراکترهای Mythic پژواک‌شونن) خودش
یه بازیکن رو انتخاب کرده، نه اینکه شانسی افتاده باشه دستش.

سه Tier:
- common          : افکتِ تکی و کوچیک، هر تعداد بازیکن می‌تونن هم‌زمان داشته باشن
- rare             : افکتِ دوتایی/بزرگ‌تر، هر تعداد بازیکن می‌تونن داشته باشن
- divine_mandate   : قوی‌ترین‌ها + یه تایتلِ نمایشی روی پروفایل — فقط ۱ نفر تو
                     کل سرور هم‌زمان می‌تونه هرکدومشون رو داشته باشه (یکتا)

فرمتِ effect دقیقاً با کلیدهایی که combat.py از get_set_bonus_stats()
می‌خونه هم‌خونیه (dmg_pct, crit_pct, elem_amp, counter_pct, defense_pct,
lifesteal_pct) تا بدون نوشتن مسیر جدید، مستقیم به ست‌بونوس‌های موجود
اضافه (merge) بشه. یه کلید اضافه‌ی مخصوص خودِ مُهرها هم هست:
rage_mult (ضریب سرعتِ پرشدنِ گیج rage/ultimate) که جدا تو
combat_engine.py مصرف می‌شه چون add_rage() تو ست‌بونوس‌های قدیمی
اصلاً وجود نداشت.
"""

from typing import Optional, Dict

# ---------------------------------------------------------------------------
DIVINE_SEALS: Dict[str, dict] = {

    # ═══════════════════════ COMMON (نامحدود) ═══════════════════════
    "ember_wrath": {
        "name": "مُهرِ آتش‌گدازِ نخستین", "tier": "common",
        "lore": "یه تیکه از خشمِ فراموش‌شده‌ی نخستین‌ها، که هنوز تو رگ‌های کسی که لمسش کرده می‌سوزه.",
        "effect": {"crit_pct": 0.08},
    },
    "silent_shade": {
        "name": "مُهرِ سایه‌ی خاموش", "tier": "common",
        "lore": "نخستین‌ها قبل از Abyss یاد گرفته بودن چطور از چشمِ سرنوشت پنهان بشن؛ این مهارت گاهی به یکی دیگه هم می‌رسه.",
        "effect": {"counter_pct": 0.10},
    },
    "life_current": {
        "name": "مُهرِ جریانِ حیات", "tier": "common",
        "lore": "پژواکی از قدرتی که یه نخستین برای زنده‌نگه‌داشتنِ کسی که دوستش داشت مصرف کرد.",
        "effect": {"lifesteal_pct": 0.06},
    },
    "iron_will": {
        "name": "مُهرِ اراده‌ی آهنین", "tier": "common",
        "lore": "درد رو حس می‌کنی، ولی زانو نمی‌زنی — این چیزیه که این مُهر بهت یاد می‌ده.",
        "effect": {"defense_pct": 0.08},
    },
    "frost_edge": {
        "name": "مُهرِ لبه‌ی یخی", "tier": "common",
        "lore": "سرمایی که هیچ‌وقت آب نمی‌شه، درست زیرِ پوستت جا خوش کرده.",
        "effect": {"elem_amp": 0.10},
    },
    "storm_pulse": {
        "name": "مُهرِ نبضِ طوفان", "tier": "common",
        "lore": "قلبت گاهی یه ضربان تندتر می‌زنه — انگار یه رعدِ کوچیک تو سینه‌ته.",
        "effect": {"dmg_pct": 0.05},
    },
    "ashen_step": {
        "name": "مُهرِ گامِ خاکستری", "tier": "common",
        "lore": "جای پات رو خاکستر می‌پوشونه، نه چون می‌سوزونی، بلکه چون از یه‌جایی که دیگه وجود نداره اومدی.",
        "effect": {"counter_pct": 0.07, "crit_pct": 0.03},
    },
    "verdant_pulse": {
        "name": "مُهرِ نبضِ سبز", "tier": "common",
        "lore": "چیزی درونت هنوز رشد می‌کنه، حتی وسطِ نبرد.",
        "effect": {"lifesteal_pct": 0.04, "defense_pct": 0.04},
    },
    "molten_core": {
        "name": "مُهرِ هسته‌ی مذاب", "tier": "common",
        "lore": "یه شعله‌ی کوچیک همیشه روشنه، حتی وقتی همه‌چی سرده.",
        "effect": {"dmg_pct": 0.04, "crit_pct": 0.04},
    },
    "hollow_grace": {
        "name": "مُهرِ فیضِ توخالی", "tier": "common",
        "lore": "یه لطفِ ناقص، از یه جایی که خودش هم دیگه کامل نیست.",
        "effect": {"elem_amp": 0.06, "defense_pct": 0.04},
    },
    "wandering_light": {
        "name": "مُهرِ نورِ سرگردان", "tier": "common",
        "lore": "یه پرتوِ گم‌شده که راهشو به سمتِ تو پیدا کرد.",
        "effect": {"crit_pct": 0.06, "lifesteal_pct": 0.02},
    },
    "quiet_storm": {
        "name": "مُهرِ طوفانِ آرام", "tier": "common",
        "lore": "بیرون آرومی، ولی چیزی زیرِ پوستت داره جمع می‌شه.",
        "effect": {"dmg_pct": 0.06},
    },
    "broken_chain": {
        "name": "مُهرِ زنجیرِ شکسته", "tier": "common",
        "lore": "یه‌بار یه‌چیزی تو رو نگه داشته بود. دیگه نه.",
        "effect": {"counter_pct": 0.09},
    },
    "still_water": {
        "name": "مُهرِ آبِ ساکن", "tier": "common",
        "lore": "زیرِ سطحِ آرومت، یه جریانِ قدیمی هنوز جاریه.",
        "effect": {"defense_pct": 0.07, "counter_pct": 0.03},
    },
    "grey_ash": {
        "name": "مُهرِ خاکسترِ خاکستری", "tier": "common",
        "lore": "چیزی که یه‌بار سوخت، دیگه هیچ‌وقت کاملاً خاموش نمی‌شه.",
        "effect": {"elem_amp": 0.08},
    },
    "faint_echo": {
        "name": "مُهرِ پژواکِ کم‌رنگ", "tier": "common",
        "lore": "یه صدای دور، از یکی که اسمشو دیگه هیچ‌کس یادش نیست.",
        "effect": {"crit_pct": 0.05, "counter_pct": 0.04},
    },
    "dull_flame": {
        "name": "مُهرِ شعله‌ی کدر", "tier": "common",
        "lore": "همیشه نمی‌سوزونه، ولی هیچ‌وقت هم کاملاً خاموش نمی‌شه.",
        "effect": {"dmg_pct": 0.03, "lifesteal_pct": 0.03},
    },
    "pale_root": {
        "name": "مُهرِ ریشه‌ی رنگ‌پریده", "tier": "common",
        "lore": "یه‌چیزی زیرِ خاکِ Abyss هنوز جونه می‌زنه — این ریشه‌ی همونه.",
        "effect": {"defense_pct": 0.06, "lifesteal_pct": 0.03},
    },
    "cracked_mirror": {
        "name": "مُهرِ آینه‌ی ترک‌خورده", "tier": "common",
        "lore": "تصویری که تو این مُهر می‌بینی، همیشه دقیقاً خودت نیست.",
        "effect": {"crit_pct": 0.07},
    },
    "borrowed_time": {
        "name": "مُهرِ زمانِ قرضی", "tier": "common",
        "lore": "یکی یه‌کم از وقتِ خودشو بهت داد. مصرفش کن.",
        "effect": {"dmg_pct": 0.04, "defense_pct": 0.03},
    },

    # ═══════════════════════ RARE (نامحدود، افکت قوی‌تر) ═══════════════════════
    "vaelthorian_wrath": {
        "name": "مُهرِ سرنوشتِ Yoraris", "tier": "rare",
        "lore": "کسی که این مُهر رو داره، یه‌بار مسیرِ آینده‌ش رو دیده و دیگه از هیچی نمی‌ترسه.",
        "effect": {"dmg_pct": 0.10, "rage_mult": 1.20},
    },
    "nyxalune_eclipse": {
        "name": "مُهرِ فراموشیِ Gravidor", "tier": "rare",
        "lore": "زیر نورِ این مُهر، ضربه‌ها یه لحظه دیرتر به هدف می‌رسن — دقیقاً همون یه لحظه‌ای که لازمه.",
        "effect": {"elem_amp": 0.15, "counter_pct": 0.05},
    },
    "seravyn_dawn": {
        "name": "مُهرِ غروبِ Cindrien", "tier": "rare",
        "lore": "یه نورِ اولیه که هیچ‌وقت کاملاً خاموش نشد — حتی بعد از Abyss.",
        "effect": {"lifesteal_pct": 0.10, "defense_pct": 0.05},
    },
    "azerion_hunger": {
        "name": "مُهرِ شکافِ Kaelvain", "tier": "rare",
        "lore": "یه خلأِ کوچیک، همیشه گرسنه‌ی یه ضربه‌ی دیگه.",
        "effect": {"crit_pct": 0.12, "dmg_pct": 0.04},
    },
    "origin_whisper": {
        "name": "مُهرِ زمزمه‌ی آغازین", "tier": "rare",
        "lore": "یه پژواک از قبل از این‌که هیچ‌چیزی اسمی داشته باشه.",
        "effect": {"counter_pct": 0.12, "crit_pct": 0.05},
    },
    "abyssal_calm": {
        "name": "مُهرِ آرامشِ اعماق", "tier": "rare",
        "lore": "عمیق‌ترین نقطه‌ی هر اقیانوسی، ساکت‌ترین جاشه.",
        "effect": {"defense_pct": 0.14, "lifesteal_pct": 0.04},
    },
    "shattered_fate": {
        "name": "مُهرِ سرنوشتِ خرد‌شده", "tier": "rare",
        "lore": "خطِ زندگیت یه‌بار پاره شد و دوباره، جوریِ دیگه، وصل شد.",
        "effect": {"dmg_pct": 0.08, "elem_amp": 0.08},
    },
    "starfall_grace": {
        "name": "مُهرِ فیضِ سقوطِ ستاره", "tier": "rare",
        "lore": "هرچیزی که از آسمون می‌افته، یه اثری از خودش رو زمین جا می‌ذاره.",
        "effect": {"crit_pct": 0.08, "lifesteal_pct": 0.06},
    },
    "void_anchor": {
        "name": "مُهرِ لنگرِ خلأ", "tier": "rare",
        "lore": "چیزی تو رو از سقوطِ کامل به نیستی نگه داشته. هنوز نمی‌دونی چرا.",
        "effect": {"defense_pct": 0.10, "counter_pct": 0.06},
    },
    "moonless_vow": {
        "name": "مُهرِ عهدِ بی‌ماه", "tier": "rare",
        "lore": "یه قول که تو تاریکیِ کاملی داده شد — بدونِ هیچ شاهدی.",
        "effect": {"elem_amp": 0.10, "crit_pct": 0.06},
    },
    "endless_ember": {
        "name": "مُهرِ اخگرِ بی‌پایان", "tier": "rare",
        "lore": "یه شعله‌ای که نه از هیزم زنده‌ست، نه از باد می‌میره.",
        "effect": {"dmg_pct": 0.10, "rage_mult": 1.15},
    },
    "echoed_resolve": {
        "name": "مُهرِ عزمِ پژواک‌شده", "tier": "rare",
        "lore": "یه اراده که یه‌بار شکست، ولی صداش هنوز تو Abyss می‌پیچه.",
        "effect": {"defense_pct": 0.08, "dmg_pct": 0.06, "rage_mult": 1.10},
    },

    # ═══════════════════════ DIVINE MANDATE (یکتا، فقط ۱ نفر هم‌زمان) ═══════════════════════
    "first_echo_mandate": {
        "name": "مُهرِ First Echo", "tier": "divine_mandate",
        "title": "🗣️ صدای نخستین",
        "lore": "این یکی نه هدیه‌ست، نه شانس — انتخابیه. کسی که این‌و داره، جهان بازی رسماً بهش به چشمِ یکی از Bearerهای اصلیِ داستان نگاه می‌کنه.",
        "effect": {"dmg_pct": 0.12, "elem_amp": 0.12, "rage_mult": 1.15},
    },
    "voidheart_mandate": {
        "name": "مُهرِ شکافِ نخستین", "tier": "divine_mandate",
        "title": "🕳️ بلعنده‌ی قلمرو",
        "lore": "Kaelvain یه تیکه از خودش رو، برای یه دلیلی که هیچ‌کس نمی‌دونه، تو یه بازیکن جا گذاشته.",
        "effect": {"crit_pct": 0.16, "counter_pct": 0.08},
    },
    "genesis_mandate": {
        "name": "مُهرِ غروبِ آخر", "tier": "divine_mandate",
        "title": "🌅 نورِ تولد",
        "lore": "Cindrien معتقده هرچیزی، حتی Abyss، یه‌بار می‌تونه دوباره متولد بشه — و این بازیکن رو آزمایشِ اول کرده.",
        "effect": {"lifesteal_pct": 0.14, "defense_pct": 0.08},
    },
    "destiny_mandate": {
        "name": "مُهرِ برشِ سرنوشت", "tier": "divine_mandate",
        "title": "⚔️ انتخاب‌کننده‌ی پایان",
        "lore": "Yoraris دیدنِ آینده رو متوقف کرد، چون این‌بار ترجیح داد که خودِ بازیکن تصمیم بگیره.",
        "effect": {"dmg_pct": 0.16, "crit_pct": 0.08},
    },
    "lunar_mandate": {
        "name": "مُهرِ فراموشیِ ابدی", "tier": "divine_mandate",
        "title": "🌑 قدم در سایه‌ی ماه",
        "lore": "Gravidor هیچ‌وقت با کسی صحبت نمی‌کنه — ولی این‌بار، سکوتش رو به یکی بخشید.",
        "effect": {"counter_pct": 0.14, "elem_amp": 0.10},
    },
    "abyss_silence_mandate": {
        "name": "مُهرِ سکوتِ Abyss", "tier": "divine_mandate",
        "title": "🕳️ شنونده‌ی سکوت",
        "lore": "این مُهر افکتِ ثابتی نداره — فقط برای رویدادهای خاصِ سرور، دستی توسط ادمین معنا و قدرتش تعریف می‌شه.",
        "effect": {},
    },
}

SEAL_EMOJI = {"common": "🔹", "rare": "🔸", "divine_mandate": "👑"}


def find_seal_id(query: str) -> Optional[str]:
    """جستجوی یه seal_id یا اسمِ فارسیِ مُهر، هم دقیق هم fuzzy."""
    if query in DIVINE_SEALS:
        return query
    q = query.strip().lower()
    for sid, data in DIVINE_SEALS.items():
        if sid.lower() == q or data["name"].lower() == q:
            return sid
    for sid, data in DIVINE_SEALS.items():
        if q in sid.lower() or q in data["name"].lower():
            return sid
    return None


def get_seal_bonus_stats(player: dict) -> Dict[str, float]:
    """معادلِ get_set_bonus_stats() ولی برای مُهرها — برای merge مستقیم تو combat.py."""
    seal_id = player.get("divine_seal")
    if not seal_id or seal_id not in DIVINE_SEALS:
        return {}
    effect = DIVINE_SEALS[seal_id]["effect"]
    return {k: v for k, v in effect.items() if k != "rage_mult"}


def get_seal_rage_mult(player: dict) -> float:
    """ضریبِ سرعتِ پرشدنِ گیجِ rage/ultimate — جدا از بقیه‌ی استت‌ها مصرف می‌شه."""
    seal_id = player.get("divine_seal")
    if seal_id and seal_id in DIVINE_SEALS:
        return DIVINE_SEALS[seal_id]["effect"].get("rage_mult", 1.0)
    return 1.0


def get_seal_title(player: dict) -> Optional[str]:
    """تایتلِ نمایشیِ روی پروفایل — فقط مُهرهای Divine Mandate تایتل دارن."""
    seal_id = player.get("divine_seal")
    if seal_id and seal_id in DIVINE_SEALS:
        return DIVINE_SEALS[seal_id].get("title")
    return None
