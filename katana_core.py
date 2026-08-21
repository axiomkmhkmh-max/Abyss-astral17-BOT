# ============================================================
#  ASTRAL ABYSS RPG — Katana Soul, Awakening & Bond System
#  (katana_core.py)
# ============================================================
#
# این فایل یه لایه‌ی جدید و مستقل روی سیستم فورج قدیمی (katana_system.py,
# سطح ۱ تا ۵۲) اضافه می‌کنه. چیزی از فورج قدیمی رو پاک یا جایگزین نمی‌کنه؛
# katana_level و KATANA_LEVELS دقیقاً مثل قبل کار می‌کنن.
#
# چیزی که این‌جا اضافه میشه:
#   • KATANA_SOULS      → شخصیت/دیالوگ هر کاتانا (روح کاتانا)
#   • TIER_CONFIG        → ۴ رتبه (common/rare/legendary/mythic) بر اساس
#                          rarity کاراکتر، هرکدوم با سقف بیداری و اثر ویژه
#   • Awakening (۰ تا ۵) → مراحل بیداری با مهارت‌های فعال در نبرد
#   • Bond (۱ تا ۱۰)     → پیوند روحی بازیکن با کاتانا، بر اساس تعداد کشته
#
# نتیجه‌ی نهایی با calc_katana_bonus() به combat.py داده میشه و
# روی بونوس فورج قدیمی «اضافه» میشه، نه جایگزینش.
# ============================================================

import random
from characters import ALL_CHARACTERS

# ────────────────────────────────────────────────────────────
# ۱) رتبه‌بندی کاتانا بر اساس rarity کاراکتر
# ────────────────────────────────────────────────────────────

RARITY_TO_TIER = {
    "special":   "mythic",
    "mythic":    "mythic",  # 🆕 باگ‌فیکس: کاراکترهای MYTHIC_CHARACTERS (characters.py)
                            # rarity="mythic" دارن نه "special"، ولی این مپ کلیدِ
                            # "mythic" رو نداشت — یعنی get(rarity,"common") برای
                            # همه‌شون به‌اشتباه به "common" (کمترین رتبه‌ی کاتانا،
                            # کمترین دمیج/بیداری) می‌فرستادشون.
    "legendary": "legendary",
    "rare":      "rare",
    "common":    "common",
}

TIER_CONFIG = {
    "common": {
        "emoji": "⚔️", "name_fa": "معمولی", "max_awaken": 2,
        "dmg_min": 1.00, "dmg_max": 1.35,
        "success_base": 0.75, "cost_base": 600, "mat_qty_base": 2,
        "special": None,
    },
    "rare": {
        "emoji": "💠", "name_fa": "کمیاب", "max_awaken": 3,
        "dmg_min": 1.00, "dmg_max": 1.70,
        "success_base": 0.60, "cost_base": 2200, "mat_qty_base": 3,
        "special": None,
    },
    "legendary": {
        "emoji": "🌟", "name_fa": "افسانه‌ای", "max_awaken": 4,
        "dmg_min": 1.00, "dmg_max": 2.20,
        "success_base": 0.42, "cost_base": 7500, "mat_qty_base": 3,
        "special": "double_strike",   # ۱۵٪ شانس ضربه‌ی ۲ برابر
    },
    "mythic": {
        "emoji": "👑", "name_fa": "جاودانه", "max_awaken": 5,
        "dmg_min": 1.00, "dmg_max": 3.20,
        "success_base": 0.28, "cost_base": 22000, "mat_qty_base": 4,
        "special": "soul_drain",      # هر کشته ۱۰٪ HP دشمن رو به خودت برمی‌گردونه
    },
}

# ────────────────────────────────────────────────────────────
# ۲) بیداری (Awakening) — مراحل ۰ تا ۵
# ────────────────────────────────────────────────────────────

AWAKENING_STAGE_NAMES = {
    0: "خفته 💤",
    1: "بیدار 🌙",
    2: "درخشان ✨",
    3: "اسطوره‌ای 🌠",
    4: "فراطبیعی 🌌",
    5: "جاودانه ♾️",
}

AWAKENING_SKILLS = {
    1: {"key": "wave_slash",      "name": "موج برش",       "desc": "شانس ۱۲٪ ضربه‌ی اضافه که به‌طور مستقیم به دشمن آسیب می‌زنه"},
    2: {"key": "shadow_step",     "name": "گام سایه",      "desc": "شانس ۱۰٪ برای فرار کامل از ضدحمله‌ی بعدی دشمن"},
    3: {"key": "soul_reap",       "name": "درو روح",        "desc": "با هر کشتن، ۴٪ از HP ماکزیممت رو فوراً بازیابی می‌کنی"},
    4: {"key": "elemental_burst", "name": "انفجار عنصری",   "desc": "آسیب ضعف عنصری ۲۵٪ قوی‌تر می‌شه"},
    5: {"key": "void_touch",      "name": "لمس خلأ",        "desc": "شانس ۸٪ برای نادیده گرفتن کامل دفاع دشمن (فقط MYTHIC)"},
}

AWAKEN_MATERIALS = {1: "soul_shard", 2: "void_core", 3: "dragon_scale", 4: "phoenix_feather", 5: "soul_essence"}

MATERIALS_INFO = {
    "soul_shard":      {"emoji": "🔹", "name_fa": "تکه‌ی روح",       "rarity": "rare"},
    "void_core":       {"emoji": "🌑", "name_fa": "هسته‌ی خلأ",       "rarity": "epic"},
    "dragon_scale":    {"emoji": "🐉", "name_fa": "فلس اژدها",       "rarity": "epic"},
    "phoenix_feather": {"emoji": "🔥", "name_fa": "پر ققنوس",        "rarity": "legendary"},
    "soul_essence":    {"emoji": "💜", "name_fa": "جوهر روح",        "rarity": "legendary"},
}

FORGE_BREAK_ON_FAIL_AWAKEN = True  # شکست بدون طومار = یک مرحله پس‌رفت


def get_katana_identity(character_name: str) -> dict:
    """اسم کاتانا، عنصر، رارتیتی و تایر رو از روی کاراکتر بازیکن می‌گیره."""
    char = ALL_CHARACTERS.get(character_name, {})
    rarity = char.get("rarity", "common")
    return {
        "katana_name": char.get("katana", "بی‌نام"),
        "element":     char.get("element", ""),
        "rarity":      rarity,
        "tier":        RARITY_TO_TIER.get(rarity, "common"),
    }


def _default_emoji_for_element(element: str) -> str:
    e = element or ""
    table = [
        (("آتش", "شعله", "گدازه", "ماگما", "دوزخ", "جهنم"), "🔥"),
        (("یخ", "برفک", "سرد", "انجماد"), "❄️"),
        (("برق", "صاعقه", "الکتریک", "رعد"), "⚡"),
        (("سم", "زهر"), "☠️"),
        (("تاریک", "سایه", "شب", "مغاک", "خلأ"), "🌑"),
        (("نور", "مقدس", "قدس", "روشن"), "✨"),
        (("آب", "دریا", "موج", "شور"), "🌊"),
        (("زمین", "خاک", "سنگ", "گرانیت"), "🪨"),
        (("باد", "طوفان", "تندباد"), "🌪️"),
        (("جادو", "آرکین", "رون"), "🔮"),
        (("کهکشان", "فضا", "ستاره", "کیهان"), "🌌"),
    ]
    for keys, emo in table:
        if any(k in e for k in keys):
            return emo
    return "⚔️"


def dmg_multiplier_for_stage(tier: str, stage: int) -> float:
    cfg = TIER_CONFIG[tier]
    if stage <= 0:
        return 1.0
    frac = stage / cfg["max_awaken"]
    return round(cfg["dmg_min"] + (cfg["dmg_max"] - cfg["dmg_min"]) * frac, 3)


def unlocked_skills(tier: str, stage: int) -> list[dict]:
    cap = min(stage, TIER_CONFIG[tier]["max_awaken"])
    return [AWAKENING_SKILLS[s] for s in range(1, cap + 1)]


def awaken_cost(tier: str, target_stage: int) -> int:
    cfg = TIER_CONFIG[tier]
    return int(cfg["cost_base"] * (target_stage ** 1.7))


def awaken_material_need(tier: str, target_stage: int) -> tuple[str, int]:
    cfg = TIER_CONFIG[tier]
    mat = AWAKEN_MATERIALS[target_stage]
    qty = (cfg["mat_qty_base"] + target_stage) * 3  # حالت سخت: مواد ۳ برابر شد
    return mat, qty


def awaken_success_chance(tier: str, target_stage: int) -> float:
    cfg = TIER_CONFIG[tier]
    chance = cfg["success_base"] - (target_stage - 1) * 0.11
    chance = max(0.12, chance) * 0.5  # حالت سخت: شانس موفقیت نصف شد
    return round(min(0.40, chance), 3)  # سقف ۴۰٪ برای بالاترین سطح


def attempt_awaken(character_name: str, current_stage: int, inventory: dict,
                    gold: int, use_protection: bool = False) -> dict:
    """
    مثل attempt_forge تو katana_system.py — فقط محاسبه و نتیجه رو برمی‌گردونه.
    کم کردن واقعی طلا/مواد از پروفایل، کار هندلر (katana_handlers.py)‌ه.
    """
    ident = get_katana_identity(character_name)
    tier  = ident["tier"]
    cfg   = TIER_CONFIG[tier]

    if current_stage >= cfg["max_awaken"]:
        return {"success": False, "new_stage": current_stage, "gold_spent": 0,
                "material": None, "material_spent": 0, "chance": 0.0,
                "protection_used": False,
                "message": f"🗡️ کاتانای {ident['katana_name']} به اوج بیداری خودش رسیده! ({cfg['max_awaken']}/{cfg['max_awaken']})"}

    target = current_stage + 1
    cost   = awaken_cost(tier, target)
    mat, qty = awaken_material_need(tier, target)
    chance = awaken_success_chance(tier, target)

    if gold < cost:
        return {"success": False, "new_stage": current_stage, "gold_spent": 0,
                "material": mat, "material_spent": 0, "chance": chance, "protection_used": False,
                "message": f"💰 طلای کافی نداری! به {cost:,} Zen نیاز داری."}

    if inventory.get(mat, 0) < qty:
        info = MATERIALS_INFO[mat]
        return {"success": False, "new_stage": current_stage, "gold_spent": 0,
                "material": mat, "material_spent": 0, "chance": chance, "protection_used": False,
                "message": f"📦 مواد کافی نداری! به {qty}x {info['emoji']} {info['name_fa']} نیاز داری."}

    if use_protection and inventory.get("protection_scroll", 0) < 1:
        return {"success": False, "new_stage": current_stage, "gold_spent": 0,
                "material": mat, "material_spent": 0, "chance": chance, "protection_used": False,
                "message": "🛡️ طومار محافظت نداری!"}

    success = random.random() < chance
    new_stage = current_stage
    protection_used = False

    if success:
        new_stage = target
        skill = AWAKENING_SKILLS[target]
        message = (f"✨ **بیداری موفق!** کاتانای {ident['katana_name']} وارد مرحله‌ی "
                   f"«{AWAKENING_STAGE_NAMES[target]}» شد.\n"
                   f"🆕 مهارت جدید: **{skill['name']}** — {skill['desc']}")
    else:
        if use_protection:
            protection_used = True
            message = "🛡️ بیداری شکست خورد، ولی طومار محافظت مانع پس‌رفت کاتانا شد."
        elif FORGE_BREAK_ON_FAIL_AWAKEN and current_stage > 0:
            new_stage = current_stage - 1
            message = (f"💥 بیداری شکست خورد! روح کاتانا آشفته شد و یک مرحله پس‌رفت کرد "
                       f"→ «{AWAKENING_STAGE_NAMES[new_stage]}».")
        else:
            message = "💥 بیداری شکست خورد. طلا و مواد از دست رفت ولی مرحله حفظ شد."

    return {
        "success": success, "new_stage": new_stage, "gold_spent": cost,
        "material": mat, "material_spent": qty, "chance": chance,
        "protection_used": protection_used, "message": message,
    }


# ────────────────────────────────────────────────────────────
# ۳) پیوند روحی (Bond) — سطح ۱ تا ۱۰
# ────────────────────────────────────────────────────────────

BOND_KILLS_PER_LEVEL = 50
BOND_MAX_LEVEL = 10

BOND_PERKS = {
    3:  {"lifesteal": 0.05},
    5:  {"awaken_echo": True},   # اثر ویژه‌ی تایر با شانس کمتر حتی قبل از بیداری کامل فعال میشه
    7:  {"crit": 0.10},
    9:  {"hidden_skill": True, "dmg_mult": 0.08},
    10: {"soulbound": True},    # کاتانا جاودانه: بعد از مرگ Bond XP از دست نمی‌ره
}

BOND_LEVEL_DESC = {
    1: "شروع پیوند — روح کاتانا تازه بیدار شده",
    3: "+۵٪ لایف‌استیل — کاتانا شروع به اعتماد کردن بهت می‌کنه",
    5: "اثر ویژه‌ی تایر با شانس کم فعال میشه (پیش از بیداری کامل)",
    7: "+۱۰٪ شانس کریتیکال — هماهنگی کامل با کاتانا",
    9: "مهارت مخفی باز شد: +۸٪ آسیب کلی",
    10: "🔗 پیوند ابدی — کاتانا جاودانه شد و از این به بعد هیچ‌وقت با مرگت آسیب روحی نمی‌بینه",
}


def bond_level_from_xp(xp: int) -> int:
    return min(BOND_MAX_LEVEL, 1 + max(0, xp) // BOND_KILLS_PER_LEVEL)


def bond_xp_for_level(level: int) -> int:
    return (level - 1) * BOND_KILLS_PER_LEVEL


def get_bond_bonus(bond_level: int) -> dict:
    """جمع تجمعی همه‌ی پرک‌هایی که تا این سطح باز شدن."""
    out = {"lifesteal": 0.0, "crit": 0.0, "dmg_mult": 0.0,
           "awaken_echo": False, "hidden_skill": False, "soulbound": False}
    for lvl, perk in BOND_PERKS.items():
        if bond_level >= lvl:
            for k, v in perk.items():
                if isinstance(v, bool):
                    out[k] = out[k] or v
                else:
                    out[k] = out.get(k, 0) + v
    return out


def add_bond_xp(player: dict, amount: int = 1) -> dict:
    """بعد از هر کشتن صدا زده میشه. خروجی: {'leveled': bool, 'new_level': int}"""
    old_xp    = player.get("katana_bond", 0)
    old_level = bond_level_from_xp(old_xp)
    new_xp    = old_xp + amount
    new_level = bond_level_from_xp(new_xp)
    player["katana_bond"]       = new_xp
    player["katana_bond_level"] = new_level
    sync_soul_capacity(player)  # 🆕 ظرفیت روح با هر رشدی تو Bond XP هم آپدیت می‌شه (نه فقط بیداری)
    return {"leveled": new_level > old_level, "new_level": new_level, "old_level": old_level}


def apply_death_penalty(player: dict) -> dict:
    """بعد از مرگ بازیکن صدا زده میشه. حالت سخت: ۱۵٪ Bond XP از دست میره (قبلاً ۱۰٪) مگر سطح ۱۰ (soulbound)."""
    bond_level = player.get("katana_bond_level", 1)
    player["katana_deaths"] = player.get("katana_deaths", 0) + 1
    if bond_level >= BOND_MAX_LEVEL:
        return {"xp_lost": 0, "soulbound": True,
                "message": "🔗 کاتانا جاودانه‌ست — با مرگت آسیب روحی نمی‌بینه."}
    xp = player.get("katana_bond", 0)
    lost = int(xp * 0.15)
    player["katana_bond"] = max(0, xp - lost)
    player["katana_bond_level"] = bond_level_from_xp(player["katana_bond"])
    return {"xp_lost": lost, "soulbound": False,
            "message": f"💔 مرگت به روح کاتانا آسیب زد. -{lost} Bond XP" if lost > 0 else "روح کاتانا سالم موند."}


# ────────────────────────────────────────────────────────────
# ۳.۵) ظرفیت روح (Soul Capacity)
# ────────────────────────────────────────────────────────────
# 🆕 قبلاً «روح» کاتانا فقط یه لایه‌ی روایی/فلیور بود (KATANA_SOULS) و هیچ
# استتِ عددی‌ای به اسم «ظرفیت روح» وجود نداشت — یعنی ارتقای کاتانا (بیداری
# یا پیوند) هیچ‌وقت باعث نمی‌شد چیزی به اسم «ظرفیت» عوض بشه.
#
# این‌جا یه استتِ واقعی اضافه می‌شه: هرچی کاتانا بیدارتر بشه (Awakening) و
# بازیکن باهاش پیوندِ عمیق‌تری بگیره (Bond)، «ظرفیتِ روح»ش بیشتر می‌شه —
# این ظرفیت مستقیماً یه بونوسِ آسیبِ اضافه (فراتر از dmg_mult موجود) تولید
# می‌کنه و تو پروفایلِ کاتانا نمایش داده می‌شه.

SOUL_CAPACITY_BASE = {"common": 100, "rare": 180, "legendary": 300, "mythic": 500}
SOUL_CAPACITY_TIER_CAP = {"common": 300, "rare": 560, "legendary": 940, "mythic": 1600}
SOUL_CAPACITY_MAX_DMG_BONUS = 0.30  # سقفِ بونوسِ آسیبِ اضافه از ظرفیتِ کاملِ روح: +۳۰٪


def max_soul_capacity(tier: str, stage: int, bond_level: int) -> int:
    """ظرفیتِ روحِ کاتانا — با هر مرحله‌ی بیداری +۲۰٪ ظرفیتِ پایه و با هر
    سطح پیوند (از سطح ۲ به بعد) +۶٪ ظرفیتِ پایه اضافه می‌شه."""
    base = SOUL_CAPACITY_BASE.get(tier, SOUL_CAPACITY_BASE["common"])
    stage_bonus = stage * (base * 0.20)
    bond_bonus = max(0, bond_level - 1) * (base * 0.06)
    return int(base + stage_bonus + bond_bonus)


def soul_capacity_dmg_bonus(capacity: int, tier: str) -> float:
    """چه‌مقدار از ظرفیتِ روح به بونوسِ آسیبِ اضافه تبدیل می‌شه (سقف‌دار)."""
    tier_cap = SOUL_CAPACITY_TIER_CAP.get(tier, SOUL_CAPACITY_TIER_CAP["common"])
    frac = min(1.0, capacity / tier_cap) if tier_cap else 0.0
    return round(frac * SOUL_CAPACITY_MAX_DMG_BONUS, 3)


def sync_soul_capacity(player: dict) -> int:
    """بعدِ هر بیداریِ موفق یا هر بار که Bond لول‌آپ می‌کنه صدا زده می‌شه تا
    player['katana_soul_capacity'] آپدیت بشه. خروجی: ظرفیتِ جدید."""
    ident = get_katana_identity(player.get("character", ""))
    stage = player.get("katana_awakening", 0)
    bond_level = player.get("katana_bond_level", bond_level_from_xp(player.get("katana_bond", 0)))
    cap = max_soul_capacity(ident["tier"], stage, bond_level)
    player["katana_soul_capacity"] = cap
    return cap


# ────────────────────────────────────────────────────────────
# ۴) بونوس نهایی کاتانا برای نبرد
# ────────────────────────────────────────────────────────────

def calc_katana_bonus(player: dict) -> dict:
    """
    این تابع رو combat.py صدا می‌زنه. خروجی روی بونوسِ فورجِ قدیمی «اضافه» میشه.
    """
    char_name = player.get("character", "")
    ident = get_katana_identity(char_name)
    tier  = ident["tier"]
    stage = player.get("katana_awakening", 0)

    dmg_mult = dmg_multiplier_for_stage(tier, stage)
    bond_level = player.get("katana_bond_level", bond_level_from_xp(player.get("katana_bond", 0)))
    bond_bonus = get_bond_bonus(bond_level)

    special = TIER_CONFIG[tier]["special"]
    stage_maxed = stage >= TIER_CONFIG[tier]["max_awaken"]
    # اثر ویژه‌ی تایر: کامل فعاله وقتی بیداری کامله، یا با شانس کمتر از سطح Bond ۵ به بعد
    special_active = stage_maxed or (bond_bonus["awaken_echo"] and stage >= 1)
    special_chance = 1.0 if stage_maxed else (0.15 if bond_bonus["awaken_echo"] else 0.0)

    # 🆕 ظرفیتِ روح: اگه قبلاً سینک نشده (کاراکترهای قدیمی)، همین‌جا محاسبه می‌شه
    soul_capacity = player.get("katana_soul_capacity")
    if soul_capacity is None:
        soul_capacity = max_soul_capacity(tier, stage, bond_level)
    soul_bonus = soul_capacity_dmg_bonus(soul_capacity, tier)

    return {
        "tier": tier,
        "tier_emoji": TIER_CONFIG[tier]["emoji"],
        "dmg_mult": dmg_mult,
        "crit": bond_bonus["crit"],
        "lifesteal": bond_bonus["lifesteal"],
        "dmg_mult_flat": bond_bonus["dmg_mult"] + soul_bonus,
        "soul_capacity": soul_capacity,
        "soul_capacity_bonus": soul_bonus,
        "special": special,
        "special_active": special_active,
        "special_chance": special_chance,
        "skills": {s["key"]: True for s in unlocked_skills(tier, stage)},
    }


# ────────────────────────────────────────────────────────────
# ۵) روح کاتانا (شخصیت، دیالوگ) — Katana Soul
# ────────────────────────────────────────────────────────────
# کلید = اسم کاتانا (از characters.py، فیلد "katana")

KATANA_SOULS = {
    # ─── ۱۶ کاتانای Special Characters ───
    "Paradox Edge": {
        "personality": "مرموز، فرزانه، بازی‌گر با زمان",
        "greeting": ["زمان یه خط راست نیست... من همه‌ی مسیرهاش رو دیدم."],
        "attack_lines": ["یه لحظه که هزار بار تکرار شده!", "من قبلاً این ضربه رو زدم... و بازم می‌زنم.", "واقعیت، فقط یه پیشنهاده."],
        "kill_lines": ["سرنوشتت از قبل نوشته شده بود.", "این پایانِ همیشگیِ توئه، تو هر زمان‌خط."],
        "death_lines": ["نگران نباش... این فقط یه نسخه‌ست.", "بازمی‌گردیم. همیشه برمی‌گردیم."],
    },
    "Voidreaver": {
        "personality": "سرد، بی‌رحم، جاذب سکوت",
        "greeting": ["خلأ صدام می‌زنه... و من گوش می‌دم."],
        "attack_lines": ["هیچی نمی‌مونه.", "سکوت قبل از نابودیه.", "بیا تو خلأ."],
        "kill_lines": ["جذب شدی.", "دیگه چیزی از تو نمونده."],
        "death_lines": ["خلأ صبوره... منتظر می‌مونه.", "این پوچی موقتیه."],
    },
    "Nightfall": {
        "personality": "بی‌صدا، مرگبار، شبانه",
        "greeting": ["شب از آنِ منه."],
        "attack_lines": ["از سایه برات میام.", "صدایی نمی‌شنوی.", "شب تموم نمی‌شه."],
        "kill_lines": ["فرو رفتی تو تاریکی.", "خوش‌اومدی به شب ابدی."],
        "death_lines": ["سایه‌ها دوباره جمعمون می‌کنن.", "شب همیشه برمی‌گرده."],
    },
    "Stormwhisper": {
        "personality": "پرانرژی، آزاد، بی‌قرار",
        "greeting": ["باد و آتش، هردو گوش‌به‌فرمانِ منن!"],
        "attack_lines": ["طوفان می‌وزه!", "با سرعت باد!", "شعله‌ور و آزاد!"],
        "kill_lines": ["باد بردت.", "خاکسترت رو طوفان می‌بره."],
        "death_lines": ["طوفان فروکش می‌کنه، ولی دوباره می‌وزه.", "بادها صبر دارن."],
    },
    "Infernal Fang": {
        "personality": "خشمگین، سوزان، بی‌تاب",
        "greeting": ["آتیش تو رگ‌های منه!"],
        "attack_lines": ["بسوز!", "خاکسترت می‌کنم!", "شعله‌ی خشم!"],
        "kill_lines": ["فقط خاکستر موندی.", "آتیش پیروز شد."],
        "death_lines": ["شعله خاموش نمی‌شه، فقط کوچیک می‌شه.", "دوباره شعله‌ور می‌شیم."],
    },
    "Celestial Edge": {
        "personality": "آرام، درخشان، فرمانروا",
        "greeting": ["انرژی خالص، در خدمت توئه."],
        "attack_lines": ["نور می‌بره!", "درخشش پایان‌بخشه.", "انرژی خالص، ضربه‌ی خالص."],
        "kill_lines": ["به نور بازگشتی.", "درخشش تو رو بلعید."],
        "death_lines": ["نور هیچ‌وقت خاموش نمی‌شه.", "دوباره می‌درخشیم."],
    },
    "Sunflare": {
        "personality": "گرم، پرشور، سلطنتی",
        "greeting": ["خورشید هیچ‌وقت غروب نمی‌کنه، وقتی من دستتم."],
        "attack_lines": ["نور خورشید می‌سوزونه!", "شراره‌ی خورشیدی!", "تابش بی‌امان!"],
        "kill_lines": ["زیر آفتاب من ذوب شدی.", "خورشید بی‌رحمه."],
        "death_lines": ["خورشید فردا دوباره طلوع می‌کنه.", "این فقط غروبه، نه پایان."],
    },
    "Thunderveil": {
        "personality": "سریع، برقی، بی‌صبر",
        "greeting": ["سرعت من از فکرِ توئم بیشتره."],
        "attack_lines": ["جرقه می‌زنم!", "سریع‌تر از فکر!", "شوک الکتریکی!"],
        "kill_lines": ["برق تو رو گرفت.", "دیگه جریانی تو رگ‌هات نیست."],
        "death_lines": ["برق دوباره جمع میشه.", "این فقط یه قطعیِ کوتاهه."],
    },
    "Frostbite": {
        "personality": "سرد، صبور، بی‌رحم آرام",
        "greeting": ["سرما صبر می‌کنه... تا موقعِ درست."],
        "attack_lines": ["یخ می‌زنی.", "سرمای بی‌رحم!", "برشی سرد به روحت."],
        "kill_lines": ["یخ زدی، برای همیشه.", "سکوتِ یخی حاکم شد."],
        "death_lines": ["یخ ذوب نمی‌شه، فقط منتظر می‌مونه.", "زمستان دوباره میاد."],
    },
    "Abyssblade": {
        "personality": "تاریک، سنگین، هراس‌انگیز",
        "greeting": ["تاریکی، خونه‌ی واقعیه."],
        "attack_lines": ["از اعماق میام.", "سایه‌ت رو می‌بلعم.", "تاریکی بی‌انتها!"],
        "kill_lines": ["به اعماق برگشتی.", "تاریکی دوباره بلعید."],
        "death_lines": ["تاریکی همیشه منتظره.", "اعماق صبورن."],
    },
    "Venomfang": {
        "personality": "زیرک، خزنده، خطرناکِ آروم",
        "greeting": ["زهر آروم کار می‌کنه... ولی مطمئنه."],
        "attack_lines": ["نیشِ سمی!", "زهر تو رگ‌هاته.", "آروم ولی کشنده."],
        "kill_lines": ["زهر جواب داد.", "سمّ بی‌درمان بود."],
        "death_lines": ["زهر تو خاک می‌مونه.", "این فقط تأخیره."],
    },
    "Mindpiercer": {
        "personality": "هوشمند، نافذ، محاسبه‌گر",
        "greeting": ["ذهنت رو می‌بینم، قبل از حرکتِ بعدیت."],
        "attack_lines": ["فکرت رو خوندم!", "نفوذ به ذهن!", "گیج شدی، نه؟"],
        "kill_lines": ["ذهنت شکست.", "دیگه فکری نمونده."],
        "death_lines": ["ذهن‌ها هیچ‌وقت واقعاً نمی‌میرن.", "دوباره فکر می‌کنیم."],
    },
    "Seraph Blade": {
        "personality": "مقدس، سنگین‌وزن، عادل",
        "greeting": ["نور مقدس از دَمِ من می‌گذره."],
        "attack_lines": ["نور پاک‌کننده!", "قضاوت الهی!", "نور، تاریکی رو می‌سوزونه."],
        "kill_lines": ["پاک شدی.", "نور، عدالتش رو اجرا کرد."],
        "death_lines": ["نور مقدس هیچ‌وقت خاموش نمی‌شه.", "دوباره برمی‌خیزیم."],
    },
    "Verdant Edge": {
        "personality": "زنده، رشدیابنده، صبور",
        "greeting": ["طبیعت صبر داره... و رشد می‌کنه."],
        "attack_lines": ["ریشه‌ها می‌گیرنت!", "رشدِ ناگهانی!", "طبیعت وحشی می‌شه!"],
        "kill_lines": ["به خاک بازگشتی.", "طبیعت دوباره تو رو بلعید."],
        "death_lines": ["بذرها دوباره جوانه می‌زنن.", "طبیعت هیچ‌وقت واقعاً نمی‌میره."],
    },
    "Cosmos Blade": {
        "personality": "دوردست، بی‌کران، آرام",
        "greeting": ["ستاره‌ها منتظرن ببینن چیکار می‌کنی."],
        "attack_lines": ["ضربه‌ی کیهانی!", "فشارِ فضا!", "از میان ستاره‌ها می‌برم!"],
        "kill_lines": ["به کیهان پیوستی.", "ستاره‌ها تو رو بلعیدن."],
        "death_lines": ["کیهان بی‌کرانه... منتظرم می‌مونیم.", "دوباره تولد می‌گیریم، از غبار ستاره‌ها."],
    },
    "Tidal Fang": {
        "personality": "عمیق، آروم، طوفانی وقتی خشمگین",
        "greeting": ["اقیانوس همیشه راهی برای برگشتن پیدا می‌کنه."],
        "attack_lines": ["موجِ خشمگین!", "فشارِ اعماق!", "طوفانِ دریایی!"],
        "kill_lines": ["زیرِ موج‌ها گم شدی.", "دریا تو رو گرفت."],
        "death_lines": ["اقیانوس همیشه برمی‌گرده.", "موج بعدی در راهه."],
    },

    # ─── ۸ کاتانای Legendary ───
    "Wyrmcleaver": {
        "personality": "وحشی، غرورآمیز، اژدهاوار",
        "greeting": ["خون اژدها تو منه."],
        "attack_lines": ["غرشِ اژدها!", "پنجه‌ی آتشین!"],
        "kill_lines": ["شکارِ اژدها بودی."],
        "death_lines": ["اژدها هیچ‌وقت واقعاً نمی‌میره."],
    },
    "Spellscar": {
        "personality": "پرمعما، جادویی، بی‌قاعده",
        "greeting": ["جادو تو تیغه‌ی منه، نه تو دستِ تو."],
        "attack_lines": ["افسونِ برنده!", "زخمِ جادویی!"],
        "kill_lines": ["افسون شدی، برای همیشه."],
        "death_lines": ["جادو محو نمی‌شه، فقط پنهان می‌شه."],
    },
    "Nebula Tear": {
        "personality": "دوردست، غمگین، زیبا",
        "greeting": ["از دلِ یه سحابیِ درحال‌مرگ زاده شدم."],
        "attack_lines": ["پارگیِ سحابی!", "غبارِ ستاره‌ای می‌بارونم!"],
        "kill_lines": ["به غبار تبدیل شدی."],
        "death_lines": ["از خاکستر ستاره‌ها، دوباره متولد می‌شیم."],
    },
    "Heaven's Split": {
        "personality": "باشکوه، عادل، سنگین",
        "greeting": ["بهشت از دَمِ من می‌گذره."],
        "attack_lines": ["فروغِ عرشی!", "ضربه‌ی رستگاری!"],
        "kill_lines": ["به قضاوت رسیدی."],
        "death_lines": ["رستگاری، همیشه یه فرصتِ دیگه‌ست."],
    },
    "Sanctum Ray": {
        "personality": "درخشان، پاک، مصمم",
        "greeting": ["پرتوی من، تاریکی رو نمی‌شناسه."],
        "attack_lines": ["پرتوِ نیایش!", "زنجیرِ نورانی!"],
        "kill_lines": ["نور، تو رو پاک کرد."],
        "death_lines": ["نور هیچ‌وقت واقعاً خاموش نمی‌شه."],
    },
    "Soulflare": {
        "personality": "شعله‌ور، پرشور، سرگردان",
        "greeting": ["روحم می‌سوزه، حتی وقتی جسمم خاکستره."],
        "attack_lines": ["احتراقِ روح!", "شعله‌ی آبیِ سرگردان!"],
        "kill_lines": ["روحت با شعله‌ی من یکی شد."],
        "death_lines": ["از خاکستر، دوباره شعله‌ور می‌شم."],
    },
    "Chrono Fang": {
        "personality": "دقیق، بی‌عجله، بی‌رحم در انتظار",
        "greeting": ["زمان، دوستِ صبورِ منه."],
        "attack_lines": ["کندیِ لحظه!", "برشِ زمان‌پریش!"],
        "kill_lines": ["زمانت تموم شد."],
        "death_lines": ["ساعت دوباره کوک می‌شه."],
    },
    "Riftbreaker": {
        "personality": "شکافنده، بی‌قانون، خطرناک",
        "greeting": ["فضا برای من، فقط یه پرده‌ست که می‌شکافمش."],
        "attack_lines": ["بریدگیِ بُعدی!", "پرتابه‌ی شکاف!"],
        "kill_lines": ["به شکافِ دیگه‌ای پرتاب شدی."],
        "death_lines": ["شکاف‌ها همیشه دوباره باز می‌شن."],
    },
}

DEFAULT_SOUL_TEMPLATES = {
    "greeting": ["{katana} تو دستته... حسش می‌کنی؟"],
    "attack_lines": ["برشِ {element}!", "{katana} تشنه‌ست!", "ضربه‌ای از جنسِ {element}!"],
    "kill_lines": ["{katana} یه قربانیِ دیگه گرفت.", "خون‌آشامِ {element} سیر نمی‌شه."],
    "death_lines": ["{katana} کنارت می‌مونه... همیشه.", "کاتانا صبر می‌کنه تا دوباره بلندش کنی."],
}


def get_katana_soul(character_name: str) -> dict:
    ident = get_katana_identity(character_name)
    katana_name = ident["katana_name"]
    soul = KATANA_SOULS.get(katana_name)
    if soul:
        result = dict(soul)
    else:
        result = {k: [s.format(katana=katana_name, element=ident["element"]) for s in v]
                  for k, v in DEFAULT_SOUL_TEMPLATES.items()}
        result["personality"] = f"روحِ {ident['element']}، هنوز کاملاً شناخته‌نشده"
    result["katana_name"] = katana_name
    result["element"] = ident["element"]
    result["rarity"] = ident["rarity"]
    result["tier"] = ident["tier"]
    result["emoji"] = TIER_CONFIG[ident["tier"]]["emoji"] if katana_name in KATANA_SOULS or True else _default_emoji_for_element(ident["element"])
    return result


def katana_talk(player: dict, event: str) -> str:
    """event: 'greeting' | 'attack' | 'kill' | 'death'"""
    soul = get_katana_soul(player.get("character", ""))
    key_map = {"greeting": "greeting", "attack": "attack_lines", "kill": "kill_lines", "death": "death_lines"}
    lines = soul.get(key_map.get(event, "attack_lines"), [])
    if not lines:
        return ""
    return random.choice(lines)


# ─── دیالوگ صحنه‌ی «بیداری» کاتانا (Katana Awakening) ──────────
# اگه خودِ کاتانا تو KATANA_SOULS یه لیستِ "awaken_lines" مخصوص خودش
# داشته باشه از همون استفاده می‌شه؛ وگرنه یه خطِ عمومیِ نمایشی نشون
# داده می‌شه که هنوز حسِ «یه اتفاق مهم افتاد» رو منتقل می‌کنه.
AWAKEN_FLAVOR_GENERIC = [
    "قدرتی تازه تو رگ‌های فلزیم جاریه...",
    "بیدار شدم... و این‌بار قوی‌تر از همیشه.",
    "حسش می‌کنی؟ پیوندمون عمیق‌تر شد.",
    "یه لایه‌ی دیگه از قدرتم آزاد شد.",
    "روحم یه قدم به تعالی نزدیک‌تر شد.",
]

def katana_awaken_flavor(character_name: str, new_stage: int) -> str:
    soul = get_katana_soul(character_name)
    lines = soul.get("awaken_lines")
    line = random.choice(lines) if lines else random.choice(AWAKEN_FLAVOR_GENERIC)
    return f'💬 *"{line}"*'



# ────────────────────────────────────────────────────────────
# ۶) نمایش کامل کاتانا برای /katana
# ────────────────────────────────────────────────────────────

def display_katana_full(player: dict) -> str:
    from economy import bz_to_display
    char_name = player.get("character", "")
    ident = get_katana_identity(char_name)
    soul = get_katana_soul(char_name)
    tier = ident["tier"]
    cfg = TIER_CONFIG[tier]

    stage = player.get("katana_awakening", 0)
    bond_xp = player.get("katana_bond", 0)
    bond_level = player.get("katana_bond_level", bond_level_from_xp(bond_xp))
    kills = player.get("katana_kills", 0)
    deaths = player.get("katana_deaths", 0)

    kb = calc_katana_bonus(player)

    lines = []
    lines.append(f"{cfg['emoji']} **{soul['katana_name']}** {kb['tier_emoji']}")
    lines.append(f"_{soul.get('personality','')}_")
    lines.append(f"🎭 «{katana_talk(player, 'greeting')}»")
    lines.append("")
    lines.append(f"🏷️ رتبه: **{cfg['name_fa'].upper()}** ({tier})")
    lines.append(f"🌀 عنصر: {ident['element']}")
    lines.append(f"💤 بیداری: **{AWAKENING_STAGE_NAMES.get(stage,'؟')}** ({stage}/{cfg['max_awaken']})")
    lines.append(f"🔮 ظرفیت روح: **{kb['soul_capacity']}** (+{int(kb['soul_capacity_bonus']*100)}٪ آسیب اضافه)")
    lines.append(f"⚔️ بونوس آسیب فعلی: ×{kb['dmg_mult']}")
    if stage > 0:
        skills = unlocked_skills(tier, stage)
        if skills:
            lines.append("🧬 مهارت‌های باز شده:")
            for s in skills:
                lines.append(f"   • **{s['name']}** — {s['desc']}")
    if cfg["special"]:
        state = "🟢 فعال" if kb["special_active"] else (f"🟡 شانس {int(kb['special_chance']*100)}٪" if kb["special_chance"] else "🔴 هنوز باز نشده")
        eff_name = "ضربه‌ی دوبل (Legendary)" if cfg["special"] == "double_strike" else "جذب روح (Mythic)"
        lines.append(f"✨ اثر ویژه‌ی تایر: {eff_name} — {state}")

    lines.append("")
    lines.append(f"🔗 پیوند روحی: سطح **{bond_level}/{BOND_MAX_LEVEL}** ({bond_xp} XP)")
    if bond_level < BOND_MAX_LEVEL:
        next_need = bond_xp_for_level(bond_level + 1) - bond_xp
        lines.append(f"   تا سطح بعد: {max(0,next_need)} کشته‌ی دیگه")
    lines.append(f"   {BOND_LEVEL_DESC.get(bond_level, '')}")
    if kb["crit"] or kb["lifesteal"] or kb["dmg_mult_flat"]:
        extras = []
        if kb["crit"]: extras.append(f"+{int(kb['crit']*100)}٪ کریت")
        if kb["lifesteal"]: extras.append(f"+{int(kb['lifesteal']*100)}٪ لایف‌استیل")
        if kb["dmg_mult_flat"]: extras.append(f"+{int(kb['dmg_mult_flat']*100)}٪ آسیب کلی")
        lines.append(f"   بونوس پیوند: {', '.join(extras)}")

    lines.append("")
    lines.append(f"💀 کشته‌ها با این کاتانا: {kills}")
    lines.append(f"⚰️ مرگ‌های همراه این کاتانا: {deaths}")

    if stage < cfg["max_awaken"]:
        target = stage + 1
        cost = awaken_cost(tier, target)
        mat, qty = awaken_material_need(tier, target)
        chance = awaken_success_chance(tier, target)
        info = MATERIALS_INFO[mat]
        lines.append("")
        lines.append(f"➡️ **بیداری بعدی → {AWAKENING_STAGE_NAMES[target]}**")
        lines.append(f"   💰 هزینه: {bz_to_display(cost)}")
        lines.append(f"   📦 نیاز: {qty}x {info['emoji']} {info['name_fa']}")
        lines.append(f"   🎲 شانس موفقیت: {int(chance*100)}٪")
        next_cap = max_soul_capacity(tier, target, bond_level)
        lines.append(f"   🔮 ظرفیت روح بعدِ بیداری: {kb['soul_capacity']} → **{next_cap}**")
        lines.append("   از دستور /awaken برای تلاش استفاده کن.")
    else:
        lines.append("")
        lines.append("🏆 این کاتانا به اوج بیداریِ رتبه‌ش رسیده!")

    return "\n".join(lines)
