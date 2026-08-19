from aiogram.enums import ButtonStyle
# ============================================================
#  ASTRAL ABYSS RPG — Skill Tree Engine
# ============================================================
#
# جایگزین/مکمل level_up ساده‌ی قبلی (که فقط +10 max_hp می‌داد).
# حالا هر لول‌آپ یک «Skill Point» می‌ده و بازیکن اونو تو یکی از
# ۴ مسیر تخصصی خرج می‌کنه. هر مسیر ۵ تیر داره؛ برای باز کردن تیر
# بعدی باید حداقل مقدار مشخصی امتیاز همون مسیر رو خرج کرده باشی
# (شبیه Path of Exile / Diablo — نه فقط زنجیره‌ی خطی prereq تنها).
#
# این فایل «موتور» خالصه: دیتای درخت + منطق آنلاک/امتیاز + متن و
# کیبورد تلگرام. هندلرهای async تو skill_handlers.py هستن
# (دقیقاً هم‌الگو با boss_engine.py / boss_handlers.py).
#
# نکته‌ی مهمِ یکپارچه‌سازی: get_skill_bonuses(player) یک dict
# تخت از باف‌های جمع‌شده برمی‌گردونه که combat.py / pvp.py /
# boss_engine.py / economy_engine.py / loot_engine.py مستقیم
# روش .get(key, 0) می‌زنن — یعنی نبود این فایل یا صفر بودن همه‌ی
# باف‌ها هیچ‌جا کرش نمی‌کنه (backward-safe).
# ============================================================

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ─── مسیرها ────────────────────────────────────────────────────

PATHS = {
    "offense":   {"name_fa": "تهاجم",   "emoji": "⚔️", "desc_fa": "دمیج خام، کریتیکال و بی‌رحمی در نبرد"},
    "defense":   {"name_fa": "پایداری", "emoji": "🛡️", "desc_fa": "HP، جاخالی، لایف‌استیل و بقا"},
    "elemental": {"name_fa": "عنصر",    "emoji": "🌪️", "desc_fa": "تقویت ضعف عنصری و افکت‌های وضعیت"},
    "fortune":   {"name_fa": "اقبال",   "emoji": "💰", "desc_fa": "طلا، شانس لوت و تخفیف بازار"},
}
PATH_ORDER = ["offense", "defense", "elemental", "fortune"]

# نیازِ «امتیاز خرج‌شده در همین مسیر» برای باز شدن هر تیر
# 🌟 گسترش: تیر ۶ و ۷ اضافه شد (عمق بیشتر برای بازیکن‌های لول بالا
# با انبوهِ امتیازِ خرج‌نشده). الگوی افزایشِ نیاز (دیفرنس +۱ در هر
# تیر: 2,3,4,5 → ادامه‌ش شد 6,7) دست‌نخورده موند.
TIER_UNLOCK_REQ = {1: 0, 2: 2, 3: 5, 4: 9, 5: 14, 6: 20, 7: 27}
TIER_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII"}

# ─── درخت مهارت ─────────────────────────────────────────────────
# هر نود: path, tier, cost, name_fa, desc_fa, emoji, prereq(list), effect(dict)

SKILL_TREE = {
    # ══════════════ ⚔️ OFFENSE ══════════════
    "off_t1_a": {"path": "offense", "tier": 1, "cost": 1, "emoji": "🗡️",
                 "name_fa": "ضربه سنگین", "desc_fa": "دمیج پایه +۳٪",
                 "prereq": [], "effect": {"dmg_pct": 0.03}},
    "off_t1_b": {"path": "offense", "tier": 1, "cost": 1, "emoji": "🎯",
                 "name_fa": "چشم شکارچی", "desc_fa": "شانس کریتیکال +۲٪",
                 "prereq": [], "effect": {"crit_chance": 0.02}},
    "off_t2_a": {"path": "offense", "tier": 2, "cost": 2, "emoji": "🔪",
                 "name_fa": "غریزه کشتار", "desc_fa": "دمیج پایه +۴٪",
                 "prereq": ["off_t1_a"], "effect": {"dmg_pct": 0.04}},
    "off_t2_b": {"path": "offense", "tier": 2, "cost": 2, "emoji": "☠️",
                 "name_fa": "ضربه مرگبار", "desc_fa": "آسیب کریتیکال +۳۰٪ (روی ×۲ پایه)",
                 "prereq": ["off_t1_b"], "effect": {"crit_dmg_bonus": 0.30}},
    "off_t3_a": {"path": "offense", "tier": 3, "cost": 2, "emoji": "🌀",
                 "name_fa": "طوفان تیغه", "desc_fa": "دمیج پایه +۵٪",
                 "prereq": ["off_t2_a"], "effect": {"dmg_pct": 0.05}},
    "off_t3_b": {"path": "offense", "tier": 3, "cost": 2, "emoji": "😤",
                 "name_fa": "خشم جنگجو", "desc_fa": "شانس کریتیکال +۳٪",
                 "prereq": ["off_t2_b"], "effect": {"crit_chance": 0.03}},
    "off_t4_a": {"path": "offense", "tier": 4, "cost": 3, "emoji": "🩸",
                 "name_fa": "شکافنده زره", "desc_fa": "۱۵٪ کمتر احتمال ضدحمله‌ی دشمن رو می‌خوری",
                 "prereq": ["off_t3_a"], "effect": {"counter_reduction": 0.15}},
    "off_t4_b": {"path": "offense", "tier": 4, "cost": 3, "emoji": "💢",
                 "name_fa": "ضربه بی‌رحم", "desc_fa": "دمیج پایه +۶٪",
                 "prereq": ["off_t3_b"], "effect": {"dmg_pct": 0.06}},
    "off_t5": {"path": "offense", "tier": 5, "cost": 5, "emoji": "👹",
               "name_fa": "آواتار جنگ", "desc_fa": "دمیج +۱۰٪ و کریتیکال +۵٪ هم‌زمان — قدرت نهایی مسیر تهاجم",
               "prereq": ["off_t4_a", "off_t4_b"], "effect": {"dmg_pct": 0.10, "crit_chance": 0.05}},
    "off_t6_a": {"path": "offense", "tier": 6, "cost": 4, "emoji": "🌑",
                 "name_fa": "برش سایه", "desc_fa": "دمیج پایه +۷٪",
                 "prereq": ["off_t5"], "effect": {"dmg_pct": 0.07}},
    "off_t6_b": {"path": "offense", "tier": 6, "cost": 4, "emoji": "🔪",
                 "name_fa": "چشم قصاب", "desc_fa": "شانس کریتیکال +۴٪",
                 "prereq": ["off_t5"], "effect": {"crit_chance": 0.04}},
    "off_t7": {"path": "offense", "tier": 7, "cost": 7, "emoji": "🔱",
               "name_fa": "خدای جنگ", "desc_fa": "دمیج +۱۵٪ و آسیب کریتیکال +۵۰٪ هم‌زمان — اوجِ نهاییِ مسیر تهاجم",
               "prereq": ["off_t6_a", "off_t6_b"], "effect": {"dmg_pct": 0.15, "crit_dmg_bonus": 0.50}},

    # ══════════════ 🛡️ DEFENSE ══════════════
    "def_t1_a": {"path": "defense", "tier": 1, "cost": 1, "emoji": "❤️",
                 "name_fa": "بدن سرسخت", "desc_fa": "حداکثر HP +۴٪",
                 "prereq": [], "effect": {"max_hp_pct": 0.04}},
    "def_t1_b": {"path": "defense", "tier": 1, "cost": 1, "emoji": "💨",
                 "name_fa": "گام سبک", "desc_fa": "شانس جاخالی از حمله دشمن +۳٪",
                 "prereq": [], "effect": {"dodge_chance": 0.03}},
    "def_t2_a": {"path": "defense", "tier": 2, "cost": 2, "emoji": "🩹",
                 "name_fa": "بازسازی سریع", "desc_fa": "حداکثر HP +۵٪",
                 "prereq": ["def_t1_a"], "effect": {"max_hp_pct": 0.05}},
    "def_t2_b": {"path": "defense", "tier": 2, "cost": 2, "emoji": "🧿",
                 "name_fa": "غریزه بقا", "desc_fa": "شانس جاخالی +۴٪",
                 "prereq": ["def_t1_b"], "effect": {"dodge_chance": 0.04}},
    "def_t3_a": {"path": "defense", "tier": 3, "cost": 2, "emoji": "🩸",
                 "name_fa": "رگ حیات", "desc_fa": "لایف‌استیل +۴٪ (روی هر دمیجی که می‌زنی)",
                 "prereq": ["def_t2_a"], "effect": {"lifesteal": 0.04}},
    "def_t3_b": {"path": "defense", "tier": 3, "cost": 2, "emoji": "🌙",
                 "name_fa": "سایه‌گریز", "desc_fa": "شانس جاخالی +۵٪",
                 "prereq": ["def_t2_b"], "effect": {"dodge_chance": 0.05}},
    "def_t4_a": {"path": "defense", "tier": 4, "cost": 3, "emoji": "⚕️",
                 "name_fa": "دست شفابخش", "desc_fa": "هزینه‌ی هیل ۱۵٪ ارزون‌تر می‌شه",
                 "prereq": ["def_t3_a"], "effect": {"heal_cost_discount": 0.15}},
    "def_t4_b": {"path": "defense", "tier": 4, "cost": 3, "emoji": "🛡️",
                 "name_fa": "اراده آهنین", "desc_fa": "دمیج ضدحمله‌ی دشمن که می‌خوری ۲۰٪ کمتره",
                 "prereq": ["def_t3_b"], "effect": {"counter_dmg_reduction": 0.20}},
    "def_t5": {"path": "defense", "tier": 5, "cost": 5, "emoji": "🔥",
               "name_fa": "قلب ققنوس", "desc_fa": "حداکثر HP +۱۵٪ و لایف‌استیل +۵٪ — نمادِ نمردنی مسیر پایداری",
               "prereq": ["def_t4_a", "def_t4_b"], "effect": {"max_hp_pct": 0.15, "lifesteal": 0.05}},
    "def_t6_a": {"path": "defense", "tier": 6, "cost": 4, "emoji": "⛓️",
                 "name_fa": "زره روح", "desc_fa": "حداکثر HP +۷٪",
                 "prereq": ["def_t5"], "effect": {"max_hp_pct": 0.07}},
    "def_t6_b": {"path": "defense", "tier": 6, "cost": 4, "emoji": "🕊️",
                 "name_fa": "رقص گریز", "desc_fa": "شانس جاخالی +۶٪",
                 "prereq": ["def_t5"], "effect": {"dodge_chance": 0.06}},
    "def_t7": {"path": "defense", "tier": 7, "cost": 7, "emoji": "♾️",
               "name_fa": "ققنوس جاودان", "desc_fa": "حداکثر HP +۲۰٪ و لایف‌استیل +۸٪ هم‌زمان — اوجِ نهاییِ مسیر پایداری",
               "prereq": ["def_t6_a", "def_t6_b"], "effect": {"max_hp_pct": 0.20, "lifesteal": 0.08}},

    # ══════════════ 🌪️ ELEMENTAL ══════════════
    "ele_t1_a": {"path": "elemental", "tier": 1, "cost": 1, "emoji": "🔆",
                 "name_fa": "هماهنگی عنصری", "desc_fa": "ضریب ضعف عنصری +۰.۰۵ اضافه‌تر",
                 "prereq": [], "effect": {"elem_amp": 0.05}},
    "ele_t1_b": {"path": "elemental", "tier": 1, "cost": 1, "emoji": "☣️",
                 "name_fa": "زهرآگین", "desc_fa": "شانس ایجاد افکت وضعیت (سوختگی/سرما/شوک...) +۵٪",
                 "prereq": [], "effect": {"status_chance": 0.05}},
    "ele_t2_a": {"path": "elemental", "tier": 2, "cost": 2, "emoji": "🌊",
                 "name_fa": "طنین عنصری", "desc_fa": "ضریب ضعف عنصری +۰.۰۷ اضافه‌تر",
                 "prereq": ["ele_t1_a"], "effect": {"elem_amp": 0.07}},
    "ele_t2_b": {"path": "elemental", "tier": 2, "cost": 2, "emoji": "🕸️",
                 "name_fa": "چنگال بلا", "desc_fa": "شانس افکت وضعیت +۷٪",
                 "prereq": ["ele_t1_b"], "effect": {"status_chance": 0.07}},
    "ele_t3_a": {"path": "elemental", "tier": 3, "cost": 2, "emoji": "🌈",
                 "name_fa": "چشمه عنصری", "desc_fa": "ضریب ضعف عنصری +۰.۰۸ اضافه‌تر",
                 "prereq": ["ele_t2_a"], "effect": {"elem_amp": 0.08}},
    "ele_t3_b": {"path": "elemental", "tier": 3, "cost": 2, "emoji": "🧪",
                 "name_fa": "طاعون خاموش", "desc_fa": "شانس افکت وضعیت +۸٪",
                 "prereq": ["ele_t2_b"], "effect": {"status_chance": 0.08}},
    "ele_t4_a": {"path": "elemental", "tier": 4, "cost": 3, "emoji": "🛡️",
                 "name_fa": "پوست عنصری", "desc_fa": "مقاومت در برابر افکت‌های وضعیت دشمن +۱۵٪ (کمتر گیر می‌کنی)",
                 "prereq": ["ele_t3_a"], "effect": {"status_resist": 0.15}},
    "ele_t4_b": {"path": "elemental", "tier": 4, "cost": 3, "emoji": "💫",
                 "name_fa": "قلب عنصر", "desc_fa": "ضریب ضعف عنصری +۰.۱۰ اضافه‌تر",
                 "prereq": ["ele_t3_b"], "effect": {"elem_amp": 0.10}},
    "ele_t5": {"path": "elemental", "tier": 5, "cost": 5, "emoji": "🐉",
               "name_fa": "آواتار عنصر", "desc_fa": "ضریب ضعف عنصری +۰.۱۵ و شانس افکت وضعیت +۱۰٪ هم‌زمان",
               "prereq": ["ele_t4_a", "ele_t4_b"], "effect": {"elem_amp": 0.15, "status_chance": 0.10}},
    "ele_t6_a": {"path": "elemental", "tier": 6, "cost": 4, "emoji": "🌌",
                 "name_fa": "طنین کیهانی", "desc_fa": "ضریب ضعف عنصری +۰.۱۲ اضافه‌تر",
                 "prereq": ["ele_t5"], "effect": {"elem_amp": 0.12}},
    "ele_t6_b": {"path": "elemental", "tier": 6, "cost": 4, "emoji": "🦠",
                 "name_fa": "وبای ابدی", "desc_fa": "شانس افکت وضعیت +۱۲٪",
                 "prereq": ["ele_t5"], "effect": {"status_chance": 0.12}},
    "ele_t7": {"path": "elemental", "tier": 7, "cost": 7, "emoji": "🌠",
               "name_fa": "خدای عناصر", "desc_fa": "ضریب ضعف عنصری +۰.۲۰ و شانس افکت وضعیت +۱۵٪ هم‌زمان — اوجِ نهاییِ مسیر عنصر",
               "prereq": ["ele_t6_a", "ele_t6_b"], "effect": {"elem_amp": 0.20, "status_chance": 0.15}},

    # ══════════════ 💰 FORTUNE ══════════════
    "for_t1_a": {"path": "fortune", "tier": 1, "cost": 1, "emoji": "🪙",
                 "name_fa": "دست پرچانه", "desc_fa": "تمام درآمد Zen شما +۳٪",
                 "prereq": [], "effect": {"gold_find_pct": 0.03}},
    "for_t1_b": {"path": "fortune", "tier": 1, "cost": 1, "emoji": "🍀",
                 "name_fa": "شانس خام", "desc_fa": "شانس ارتقای ندرت لوت +۲٪",
                 "prereq": [], "effect": {"loot_rarity_chance": 0.02}},
    "for_t2_a": {"path": "fortune", "tier": 2, "cost": 2, "emoji": "💵",
                 "name_fa": "چانه‌زن ماهر", "desc_fa": "تمام درآمد Zen شما +۴٪",
                 "prereq": ["for_t1_a"], "effect": {"gold_find_pct": 0.04}},
    "for_t2_b": {"path": "fortune", "tier": 2, "cost": 2, "emoji": "🎲",
                 "name_fa": "شانس تربیت‌شده", "desc_fa": "شانس ارتقای ندرت لوت +۳٪",
                 "prereq": ["for_t1_b"], "effect": {"loot_rarity_chance": 0.03}},
    "for_t3_a": {"path": "fortune", "tier": 3, "cost": 2, "emoji": "🏦",
                 "name_fa": "کیسه بی‌ته", "desc_fa": "تخفیف مالیات بازار (خرید و فروش) +۵٪",
                 "prereq": ["for_t2_a"], "effect": {"tax_discount": 0.05}},
    "for_t3_b": {"path": "fortune", "tier": 3, "cost": 2, "emoji": "🔑",
                 "name_fa": "قفل‌شکن", "desc_fa": "شانس ارتقای ندرت لوت +۴٪",
                 "prereq": ["for_t2_b"], "effect": {"loot_rarity_chance": 0.04}},
    "for_t4_a": {"path": "fortune", "tier": 4, "cost": 3, "emoji": "🛡️",
                 "name_fa": "طلسم استریک", "desc_fa": "یک بار در روز مرگ، streak لوتت صفر نمی‌شه",
                 "prereq": ["for_t3_a"], "effect": {"streak_shield_charge": 1}},
    "for_t4_b": {"path": "fortune", "tier": 4, "cost": 3, "emoji": "💎",
                 "name_fa": "خوش‌شانسی نادر", "desc_fa": "تمام درآمد Zen شما +۶٪",
                 "prereq": ["for_t3_b"], "effect": {"gold_find_pct": 0.06}},
    "for_t5": {"path": "fortune", "tier": 5, "cost": 5, "emoji": "👑",
               "name_fa": "دست میداس", "desc_fa": "درآمد Zen +۱۵٪ و تخفیف مالیات +۵٪ هم‌زمان — اوج مسیر اقبال",
               "prereq": ["for_t4_a", "for_t4_b"], "effect": {"gold_find_pct": 0.15, "tax_discount": 0.05}},
    "for_t6_a": {"path": "fortune", "tier": 6, "cost": 4, "emoji": "🏺",
                 "name_fa": "گنجینه بی‌کران", "desc_fa": "تمام درآمد Zen شما +۸٪",
                 "prereq": ["for_t5"], "effect": {"gold_find_pct": 0.08}},
    "for_t6_b": {"path": "fortune", "tier": 6, "cost": 4, "emoji": "🎴",
                 "name_fa": "دست سرنوشت", "desc_fa": "شانس ارتقای ندرت لوت +۶٪",
                 "prereq": ["for_t5"], "effect": {"loot_rarity_chance": 0.06}},
    "for_t7": {"path": "fortune", "tier": 7, "cost": 7, "emoji": "🌟",
               "name_fa": "میدان طلایی ابدی", "desc_fa": "درآمد Zen +۲۰٪ و تخفیف مالیات +۱۰٪ هم‌زمان — اوجِ نهاییِ مسیر اقبال",
               "prereq": ["for_t6_a", "for_t6_b"], "effect": {"gold_find_pct": 0.20, "tax_discount": 0.10}},
}

# ─── امتیاز لول‌آپ ───────────────────────────────────────────────

def points_for_single_level(new_level: int) -> int:
    """چند امتیاز برای رسیدن به این لول می‌گیری. هر لول ۱ تا، + بونوس در مایل‌استون‌ها."""
    pts = 1
    if new_level % 25 == 0:
        pts += 4          # جمعاً ۵ تا در مایل‌استون‌های ۲۵/۵۰/۷۵...
    elif new_level % 10 == 0:
        pts += 1          # جمعاً ۲ تا هر ۱۰ لول
    return pts


def grant_levelup_points(player: dict, old_level: int, new_level: int) -> int:
    """بین old_level و new_level (هر دو شامل رسیدن به new_level) امتیاز اهدا می‌کنه."""
    total = 0
    for lvl in range(old_level + 1, new_level + 1):
        total += points_for_single_level(lvl)
    player["skill_points"] = player.get("skill_points", 0) + total
    return total


# ─── منطق درخت ───────────────────────────────────────────────────

def _unlocked(player: dict) -> set:
    return set(player.get("unlocked_skills", []))


def points_spent_in_path(player: dict, path: str) -> int:
    unlocked = _unlocked(player)
    return sum(node["cost"] for nid, node in SKILL_TREE.items()
               if nid in unlocked and node["path"] == path)


def node_status(player: dict, node_id: str) -> str:
    """unlocked | available | locked_prereq | locked_tier | locked_points"""
    node = SKILL_TREE[node_id]
    unlocked = _unlocked(player)
    if node_id in unlocked:
        return "unlocked"
    if any(p not in unlocked for p in node["prereq"]):
        return "locked_prereq"
    spent = points_spent_in_path(player, node["path"])
    if spent < TIER_UNLOCK_REQ[node["tier"]]:
        return "locked_tier"
    if player.get("skill_points", 0) < node["cost"]:
        return "locked_points"
    return "available"


def can_unlock(player: dict, node_id: str) -> tuple[bool, str]:
    if node_id not in SKILL_TREE:
        return False, "این مهارت وجود نداره."
    status = node_status(player, node_id)
    if status == "unlocked":
        return False, "قبلاً باز کردی."
    if status == "locked_prereq":
        return False, "اول باید مهارت‌های قبلی همین مسیر رو باز کنی."
    if status == "locked_tier":
        node = SKILL_TREE[node_id]
        need = TIER_UNLOCK_REQ[node["tier"]]
        have = points_spent_in_path(player, node["path"])
        return False, f"برای این تیر باید {need} امتیاز تو همین مسیر خرج کرده باشی (الان: {have})."
    if status == "locked_points":
        node = SKILL_TREE[node_id]
        return False, f"امتیاز کافی نداری (نیاز: {node['cost']}، موجودی: {player.get('skill_points', 0)})."
    return True, ""


def unlock_skill(player: dict, node_id: str) -> tuple[bool, str]:
    ok, reason = can_unlock(player, node_id)
    if not ok:
        return False, f"❌ {reason}"
    node = SKILL_TREE[node_id]
    player["skill_points"] -= node["cost"]
    player.setdefault("unlocked_skills", []).append(node_id)
    return True, f"✅ **{node['name_fa']}** باز شد! {node['emoji']}\n{node['desc_fa']}"


RESPEC_COST_PER_POINT = 400  # زن به‌ازای هر امتیازی که برگردونده می‌شه


def respec_cost(player: dict, path: str | None = None) -> int:
    unlocked = _unlocked(player)
    if path:
        spent = sum(SKILL_TREE[n]["cost"] for n in unlocked if SKILL_TREE[n]["path"] == path)
    else:
        spent = sum(SKILL_TREE[n]["cost"] for n in unlocked)
    return spent * RESPEC_COST_PER_POINT


def respec_path(player: dict, path: str | None = None) -> tuple[bool, str]:
    cost = respec_cost(player, path)
    if cost == 0:
        return False, "چیزی برای ریست کردن نداری."
    if player.get("zen", 0) < cost:
        return False, f"برای ریست به {cost:,} Zen نیاز داری (موجودی: {player.get('zen', 0):,})."
    unlocked = _unlocked(player)
    if path:
        refund = sum(SKILL_TREE[n]["cost"] for n in unlocked if SKILL_TREE[n]["path"] == path)
        remaining = [n for n in unlocked if SKILL_TREE[n]["path"] != path]
    else:
        refund = sum(SKILL_TREE[n]["cost"] for n in unlocked)
        remaining = []
    player["zen"] -= cost
    player["skill_points"] = player.get("skill_points", 0) + refund
    player["unlocked_skills"] = remaining
    return True, f"🔄 ریست شد! {refund} امتیاز برگشت (هزینه: {cost:,} Zen)."


# ─── جمع‌بندی باف‌ها (نقطه‌ی اتصال به combat/pvp/economy/loot) ─────

_DEFAULT_BONUSES = {
    "dmg_pct": 0.0, "crit_chance": 0.0, "crit_dmg_bonus": 0.0,
    "counter_reduction": 0.0, "counter_dmg_reduction": 0.0,
    "max_hp_pct": 0.0, "dodge_chance": 0.0, "lifesteal": 0.0,
    "heal_cost_discount": 0.0, "elem_amp": 0.0, "status_chance": 0.0,
    "status_resist": 0.0, "gold_find_pct": 0.0, "loot_rarity_chance": 0.0,
    "tax_discount": 0.0, "streak_shield_charge": 0,
}


def get_skill_bonuses(player: dict) -> dict:
    """dict تخت از باف‌های جمع‌شده. همیشه همه‌ی کلیدها موجودن (صفر اگه چیزی باز نشده)."""
    bonuses = dict(_DEFAULT_BONUSES)
    unlocked = _unlocked(player)
    for nid in unlocked:
        node = SKILL_TREE.get(nid)
        if not node:
            continue
        for key, val in node["effect"].items():
            bonuses[key] = bonuses.get(key, 0) + val
    return bonuses


# ─── باگ‌فیکس: max_hp_pct (مسیر پایداری) هیچ‌جا مصرف نمی‌شد ────────
# player["max_hp"] همیشه یه مقدار پایه (خام) بود که این تابع ازش استفاده
# می‌کنه تا سقفِ HP واقعی (با احتساب باف٪ درخت مهارت) رو حساب کنه.
def effective_max_hp(player: dict) -> int:
    base = player.get("max_hp", 100)
    pct = get_skill_bonuses(player).get("max_hp_pct", 0)
    try:
        from loot_engine import get_set_bonus_stats
        pct += get_set_bonus_stats(player).get("hp_pct", 0)  # باگ‌فیکس: ست حاکم غرق‌شده (3pc) هم مرده بود
    except ImportError:
        pass
    flat = 0
    try:
        # 🔗 Item System v2 — افیکسِ max_hp («خرسی») تا الان جایی مصرف نمی‌شد.
        from item_system import equipment_stats
        flat = equipment_stats(player).get("max_hp", 0)
    except ImportError:
        pass
    return int(base * (1 + pct)) + int(flat)


# ─── UI: متن و کیبورد ────────────────────────────────────────────

def _status_icon(status: str) -> str:
    return {"unlocked": "✅", "available": "🔓", "locked_prereq": "🔒",
            "locked_tier": "🔒", "locked_points": "🔒"}.get(status, "🔒")


def skill_summary_text(player: dict) -> str:
    b = get_skill_bonuses(player)
    lines = [f"🌟 **درخت مهارت** — امتیاز آزاد: `{player.get('skill_points', 0)}`\n"]
    for path in PATH_ORDER:
        info = PATHS[path]
        spent = points_spent_in_path(player, path)
        lines.append(f"{info['emoji']} **{info['name_fa']}** — {spent} امتیاز خرج‌شده")
    lines.append("\n**باف‌های فعال:**")
    active = [(k, v) for k, v in b.items() if v]
    if not active:
        lines.append("— هنوز هیچی باز نکردی —")
    else:
        LABELS = {
            "dmg_pct": "🗡️ دمیج", "crit_chance": "🎯 شانس کریت", "crit_dmg_bonus": "☠️ آسیب کریت",
            "counter_reduction": "🩸 کاهش شانس ضدحمله دشمن", "counter_dmg_reduction": "🛡️ کاهش دمیج ضدحمله",
            "max_hp_pct": "❤️ حداکثر HP", "dodge_chance": "💨 جاخالی", "lifesteal": "🩸 لایف‌استیل",
            "heal_cost_discount": "⚕️ تخفیف هیل", "elem_amp": "🌪️ ضریب ضعف عنصری",
            "status_chance": "☣️ شانس افکت وضعیت", "status_resist": "🧿 مقاومت افکت وضعیت",
            "gold_find_pct": "💰 درآمد طلا", "loot_rarity_chance": "🍀 شانس ندرت لوت",
            "tax_discount": "🏦 تخفیف مالیات", "streak_shield_charge": "🛡️ محافظ استریک",
        }
        for k, v in active:
            label = LABELS.get(k, k)
            if k == "streak_shield_charge":
                lines.append(f"{label}: {int(v)}x")
            else:
                lines.append(f"{label}: +{v*100:.1f}٪")
    return "\n".join(lines)


def path_tree_text(player: dict, path: str) -> str:
    info = PATHS[path]
    lines = [f"{info['emoji']} **مسیر {info['name_fa']}** — {info['desc_fa']}",
             f"امتیاز آزاد: `{player.get('skill_points', 0)}`  |  خرج‌شده در این مسیر: `{points_spent_in_path(player, path)}`\n"]
    nodes_by_tier: dict[int, list[str]] = {}
    for nid, node in SKILL_TREE.items():
        if node["path"] == path:
            nodes_by_tier.setdefault(node["tier"], []).append(nid)
    for tier in sorted(nodes_by_tier):
        req = TIER_UNLOCK_REQ[tier]
        lines.append(f"── تیر {TIER_ROMAN[tier]} (نیاز: {req} امتیاز خرج‌شده) ──")
        for nid in nodes_by_tier[tier]:
            node = SKILL_TREE[nid]
            status = node_status(player, nid)
            icon = _status_icon(status)
            lines.append(f"{icon} {node['emoji']} **{node['name_fa']}** (هزینه {node['cost']}) — {node['desc_fa']}")
    return "\n".join(lines)


def build_paths_menu_kb() -> InlineKeyboardMarkup:
    rows = []
    for path in PATH_ORDER:
        info = PATHS[path]
        rows.append([InlineKeyboardButton(text=f"{info['emoji']} {info['name_fa']}", callback_data=f"skill_path:{path}", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="🔄 ریست کامل درخت", callback_data="skill_respec_all", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="🏠 بازگشت", callback_data="skill_close", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_path_kb(player: dict, path: str) -> InlineKeyboardMarkup:
    rows = []
    nodes_by_tier: dict[int, list[str]] = {}
    for nid, node in SKILL_TREE.items():
        if node["path"] == path:
            nodes_by_tier.setdefault(node["tier"], []).append(nid)
    for tier in sorted(nodes_by_tier):
        row = []
        for nid in nodes_by_tier[tier]:
            node = SKILL_TREE[nid]
            status = node_status(player, nid)
            icon = _status_icon(status)
            label = f"{icon} {node['emoji']} {node['name_fa']}"
            row.append(InlineKeyboardButton(text=label, callback_data=f"skill_unlock:{nid}", style=ButtonStyle.PRIMARY))
        rows.append(row)
    rows.append([InlineKeyboardButton(text=f"🔄 ریست همین مسیر ({respec_cost(player, path):,} Zen)",
                                       callback_data=f"skill_respec:{path}", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="⬅️ مسیرها", callback_data="skill_back_menu", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
