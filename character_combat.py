# ============================================================
#  ASTRAL ABYSS — Character Combat (Element + Rarity Engine)
# ------------------------------------------------------------
#  این فایل جداست و به هیچ فایل قدیمی دست نمی‌زنه. فقط از
#  combat_engine.apply_combat_v2 با try/except صدا زده می‌شه — پس اگه
#  این فایل هنوز آپلود نشده باشه یا ارور بده، نبرد دقیقاً مثل قبل کار
#  می‌کنه (بدون این مکانیک‌ها).
#
#  مشکلی که حل می‌کنه: تا الان «عنصر»ِ کاراکتر (char["element"]) یه
#  متن آزاد و منحصربه‌فرد بود (۲۱۴ مقدارِ مختلف رو ۳۸۰ کاراکتر — مثلاً
#  "خون کهن"، "بلور زمان"، "توفان شنی سرخ")، در حالی که ضعفِ دشمن‌ها
#  (enemy["weak"]) همیشه یکی از ۹ عنصرِ اصلیه (آتش/یخ/برق/زمین/آب/نور/
#  تاریکی/مقدس/خلأ). نتیجه: بونوسِ «ضعفِ عنصری» تقریباً فقط برای چند
#  کاراکترِ خاص (که element‌شون دقیقاً یکی از این ۹ تا بود) واقعاً فعال
#  می‌شد؛ برای بقیه (اکثریتِ ۳۸۰ تا) هیچ‌وقت تریگر نمی‌شد.
#
#  این ماژول برای هر ۳۸۰ کاراکتر (بدون ادیتِ دستی) یه عنصرِ اصلی
#  (core element, یکی از همون ۹ تا) محاسبه می‌کنه — اول با کلیدواژه از
#  روی متنِ عنصر خودشون، و اگه چیزی match نشد با یه hash قطعی روی اسمِ
#  کاراکتر (پس همیشه یکسان و تکرارپذیره، نه رندوم هر بار).
#
#  با این عنصرِ اصلی:
#    • ضعفِ عنصریِ جبرانی (اگه سیستمِ قدیمی تشخیص نداده بود)
#    • چرخه‌ی برتری/ضعفِ ثانویه‌ی combat_engine (که تعریف شده بود ولی
#      هیچ‌جا صدا زده نمی‌شد)
#    • یه افکتِ وضعیتیِ ماندگار مخصوصِ همون عنصر (سوختن/کندی/شوک/
#      زره‌شکنی/ضعف/کوری/تحلیلِ روح/پاکسازی/شکافِ زره) که واقعاً چند
#      نوبت روی enemy["current_fight"] می‌مونه — نه فقط یه خطِ لاگ.
#
#  و بر اساس rarity (common/rare/legendary/mythic/special):
#    • ضریبِ دمیجِ پایه، شانسِ کریتِ اضافه، لایف‌استیلِ اضافه
#    • یه توانایی خودکارِ «ضربه‌ی دوم» که هرچی ندرت بالاتر باشه هم
#      شانسش بیشتره هم قدرتش
# ============================================================
import random

# ─── ۹ عنصرِ اصلی — دقیقاً همونی که enemy["weak"] و combat_engine.ELEMENT_CYCLE استفاده می‌کنن ───
CORE_ELEMENTS = ["آتش", "یخ", "برق", "زمین", "آب", "نور", "تاریکی", "مقدس", "خلأ"]

# کلیدواژه‌هایی که تو متنِ آزادِ element هر کاراکتر می‌گردیم تا عنصرِ اصلیش رو حدس بزنیم
_ELEMENT_KEYWORDS = {
    "آتش":    ["آتش", "شعله", "گدازه", "ماگما", "خاکستر", "سوز", "اخگر", "کوره", "دوزخ"],
    "یخ":     ["یخ", "برف", "سرما", "انجماد", "سرد", "منجمد", "یخچال"],
    "برق":    ["برق", "رعد", "الکتریک", "آذرخش", "صاعقه", "شوک", "جرقه"],
    "زمین":   ["زمین", "خاک", "سنگ", "کریستال", "بلور", "نمک", "خار", "شن", "کوه", "مرجان"],
    "آب":     ["آب", "دریا", "اقیانوس", "موج", "جزر", "باران", "طوفان شن"],
    "نور":    ["نور", "تابش", "خورشید", "درخشا", "روشن", "طلوع", "سپید"],
    "تاریکی": ["تاریک", "سایه", "شب", "ظلمت", "مغاک", "شفق", "پرتگاه"],
    "مقدس":   ["مقدس", "الهی", "روحان", "فرشته"],
    "خلأ":    ["خلأ", "نیستی", "فضا", "کیهان", "کهکشان", "ستاره", "فراموشی", "فروپاشی", "رویا", "خون کهن"],
}

# ایندکسِ عنصرِ اصلیِ هر کاراکتر — یه بار موقعِ import ساخته می‌شه
CHARACTER_CORE_ELEMENT: dict = {}


def _classify(name: str, element_text: str) -> str:
    text = element_text or ""
    for core, keywords in _ELEMENT_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return core
    # هیچ کلیدواژه‌ای match نشد → hash قطعی روی اسمِ خودِ کاراکتر
    # (همیشه یه خروجیِ ثابت می‌ده، نه رندوم؛ برای همه‌ی ۳۸۰ تا خودکاره)
    seed = name or text or "?"
    h = sum(ord(c) for c in seed)
    return CORE_ELEMENTS[h % len(CORE_ELEMENTS)]


def _build_index():
    try:
        from characters import ALL_CHARACTERS
    except ImportError:
        return
    for cname, cdata in ALL_CHARACTERS.items():
        CHARACTER_CORE_ELEMENT[cname] = _classify(cname, cdata.get("element", ""))


_build_index()


def get_core_element(character_name: str) -> str:
    """عنصرِ اصلیِ (یکی از ۹ تا) هر کاراکتر — cache شده، ولی اگه کاراکترِ
    تازه‌ای اضافه شده باشه که هنوز ایندکس نشده، آنی محاسبه می‌شه."""
    core = CHARACTER_CORE_ELEMENT.get(character_name)
    if core:
        return core
    try:
        from characters import ALL_CHARACTERS
        cdata = ALL_CHARACTERS.get(character_name, {})
        core = _classify(character_name, cdata.get("element", ""))
        CHARACTER_CORE_ELEMENT[character_name] = core
        return core
    except ImportError:
        return CORE_ELEMENTS[0]


# ─── ندرت → مقیاسِ قدرت ─────────────────────────────────────────
RARITY_LABEL = {
    "common": "معمولی", "rare": "کمیاب", "legendary": "افسانه‌ای",
    "mythic": "میتیک", "special": "ویژه",
}

RARITY_BONUS = {
    "common":    {"dmg_mult": 1.00, "crit_bonus": 0.00, "lifesteal_bonus": 0.00, "special_chance": 0.00, "special_pct": 0.00},
    "rare":      {"dmg_mult": 1.06, "crit_bonus": 0.03, "lifesteal_bonus": 0.02, "special_chance": 0.05, "special_pct": 0.35},
    "legendary": {"dmg_mult": 1.14, "crit_bonus": 0.06, "lifesteal_bonus": 0.04, "special_chance": 0.10, "special_pct": 0.45},
    "mythic":    {"dmg_mult": 1.20, "crit_bonus": 0.08, "lifesteal_bonus": 0.05, "special_chance": 0.14, "special_pct": 0.55},
    "special":   {"dmg_mult": 1.28, "crit_bonus": 0.10, "lifesteal_bonus": 0.06, "special_chance": 0.18, "special_pct": 0.65},
}


def get_rarity_bonus(rarity: str) -> dict:
    return RARITY_BONUS.get(rarity, RARITY_BONUS["common"])


# ─── افکتِ وضعیتیِ ماندگارِ هر عنصر ──────────────────────────────
# روی enemy["current_fight"] ذخیره می‌شه (با پیشوندِ _cc_) پس با
# ری‌استارتِ سرور هم از بین نمی‌ره — دقیقاً مثلِ HP/rage.
ELEMENTAL_STATUS = {
    "آتش":    {"name": "سوختن",        "emoji": "🔥",  "kind": "dot",            "chance": 0.28, "turns": 3, "value": 0.14},
    "یخ":     {"name": "کند شدن",      "emoji": "❄️", "kind": "enemy_dmg_down", "chance": 0.24, "turns": 2, "value": 0.25},
    "برق":    {"name": "شوک",          "emoji": "⚡",  "kind": "stun",           "chance": 0.16, "turns": 1, "value": 1.00},
    "زمین":   {"name": "خردشدنِ زره",   "emoji": "🪨",  "kind": "armor_shred",    "chance": 0.24, "turns": 3, "value": 0.35},
    "آب":     {"name": "ضعف",          "emoji": "🌊",  "kind": "enemy_dmg_down", "chance": 0.24, "turns": 2, "value": 0.20},
    "نور":    {"name": "کوری",         "emoji": "✨",  "kind": "blind",          "chance": 0.22, "turns": 2, "value": 0.50},
    "تاریکی": {"name": "تحلیلِ روح",    "emoji": "🖤",  "kind": "lifesteal",      "chance": 0.22, "turns": 1, "value": 0.12},
    "مقدس":   {"name": "پاکسازی",      "emoji": "🕊️", "kind": "self_heal",      "chance": 0.20, "turns": 1, "value": 0.10},
    "خلأ":    {"name": "شکافِ زره",     "emoji": "🕳️", "kind": "armor_pierce",   "chance": 0.24, "turns": 1, "value": 0.35},
}


def tick_status(enemy: dict, result: dict):
    """افکت‌های وضعیتیِ نوبتِ قبل رو روی همین نوبت اعمال می‌کنه. باید هر
    نوبت صدا زده بشه — حتی اگه ضربه‌ی این نوبت میس شده باشه (سوختن
    مستقل از این‌که خودت هیت کردی یا نه ادامه داره)."""
    logs = result.setdefault("logs", [])

    # 🔥 سوختن
    dot_turns = enemy.get("_cc_dot_turns", 0)
    if dot_turns > 0:
        dot_dmg = enemy.get("_cc_dot_dmg", 0)
        if dot_dmg > 0 and enemy.get("hp", 0) > 0:
            enemy["hp"] = max(0, enemy["hp"] - dot_dmg)
            logs.append(f"🔥 سوختنِ باقی‌مونده {dot_dmg} آسیبِ اضافه به دشمن زد!")
        enemy["_cc_dot_turns"] = dot_turns - 1
        if enemy["_cc_dot_turns"] <= 0:
            enemy.pop("_cc_dot_dmg", None)

    # ⚡ شوک — ضدحمله‌ی این نوبت کاملاً خنثی می‌شه
    stun_turns = enemy.get("_cc_stun_turns", 0)
    if stun_turns > 0:
        if result.get("counter") and result.get("enemy_dmg", 0) > 0:
            result["counter"] = False
            result["enemy_dmg"] = 0
            logs.append("⚡ دشمن هنوز تو شوکِ ضربه‌ی قبلیه — نتونست ضدحمله بزنه!")
        enemy["_cc_stun_turns"] = stun_turns - 1

    # ❄️🌊 کندی/ضعف — ضدحمله‌ی دشمن ضعیف‌تر می‌شه
    ddown_turns = enemy.get("_cc_ddown_turns", 0)
    if ddown_turns > 0:
        pct = enemy.get("_cc_ddown_pct", 0)
        if pct and result.get("enemy_dmg", 0) > 0:
            reduced = int(result["enemy_dmg"] * pct)
            if reduced > 0:
                result["enemy_dmg"] -= reduced
                logs.append(f"❄️ دشمن هنوز کنده — ضدحمله‌اش {reduced} ضعیف‌تر خورد!")
        enemy["_cc_ddown_turns"] = ddown_turns - 1
        if enemy["_cc_ddown_turns"] <= 0:
            enemy.pop("_cc_ddown_pct", None)

    # ✨ کوری — شانسِ اینکه ضدحمله‌ی دشمن کلاً رد بشه
    blind_turns = enemy.get("_cc_blind_turns", 0)
    if blind_turns > 0:
        pct = enemy.get("_cc_blind_pct", 0)
        if pct and result.get("counter") and result.get("enemy_dmg", 0) > 0 and random.random() < pct:
            result["counter"] = False
            result["enemy_dmg"] = 0
            logs.append("✨ دشمنِ کورشده کاملاً هوا زد و ضدحمله‌اش رد شد!")
        enemy["_cc_blind_turns"] = blind_turns - 1
        if enemy["_cc_blind_turns"] <= 0:
            enemy.pop("_cc_blind_pct", None)

    # 🪨 زره‌شکنی — فقط انقضاش رو چک می‌کنیم؛ خودِ افتِ armor موقعِ اعمال ثبت می‌شه
    shred_turns = enemy.get("_cc_shred_turns", 0)
    if shred_turns > 0:
        shred_turns -= 1
        enemy["_cc_shred_turns"] = shred_turns
        if shred_turns <= 0:
            prev = enemy.pop("_cc_armor_before_shred", None)
            if prev is not None:
                enemy["armor"] = prev
            else:
                enemy.pop("armor", None)


def apply_character_combat(player: dict, enemy: dict, attack_type: str, result: dict, defense: dict) -> dict:
    """قلبِ سیستم: بر اساس عنصر + ندرتِ کاراکترِ خودِ بازیکن دمیج/کریت/
    لایف‌استیل رو تعدیل می‌کنه و افکتِ وضعیتیِ تازه رو رول می‌کنه.
    باید قبل از mitigation آرمور صدا زده بشه (تا زره‌شکنی/خلأ رو همین
    ضربه هم ببینه)."""
    logs = result.setdefault("logs", [])
    char_name = player.get("character", "")
    if not char_name:
        return result

    try:
        from characters import ALL_CHARACTERS
    except ImportError:
        return result
    char = ALL_CHARACTERS.get(char_name)
    if not char:
        return result

    rarity = char.get("rarity", "common")
    rb = get_rarity_bonus(rarity)
    core_elem = get_core_element(char_name)
    weak = enemy.get("weak", "")

    # ── چرخه‌ی برتری/ضعفِ ثانویه‌ی combat_engine (تعریف شده بود، صدا زده نمی‌شد) ──
    try:
        from combat_engine import element_cycle_modifier
        cyc = element_cycle_modifier(core_elem, weak)
    except Exception:
        cyc = 1.0
    if cyc != 1.0 and result["dmg"] > 0:
        result["dmg"] = int(result["dmg"] * cyc)

    # ── ضعفِ عنصریِ جبرانی: اگه combat.py (با تطبیقِ دقیقِ متنِ element)
    # این ترکیب رو رد کرده بود ولی عنصرِ اصلیِ ما match می‌کنه ──
    if not result.get("elem_bonus") and core_elem == weak and result["dmg"] > 0:
        result["dmg"] = int(result["dmg"] * 1.4)
        result["elem_bonus"] = True
        logs.append("🎯 ضعفِ عنصریِ کاراکترت رو پیدا کردی! (×1.4)")

    if result["dmg"] > 0:
        # ── ضریبِ دمیجِ ذاتیِ ندرت ──
        if rb["dmg_mult"] != 1.0:
            result["dmg"] = int(result["dmg"] * rb["dmg_mult"])

        # ── کریتِ اضافه (اگه از قبل کریت نخورده) ──
        if not result.get("crit") and rb["crit_bonus"] > 0 and random.random() < rb["crit_bonus"]:
            result["dmg"] = int(result["dmg"] * 2.0)
            result["crit"] = True
            logs.append(f"💥 **کریتِ ذاتیِ کاراکترِ {RARITY_LABEL.get(rarity, rarity)}!**")

        # ── لایف‌استیلِ ذاتیِ ندرت ──
        if rb["lifesteal_bonus"] > 0:
            heal = int(result["dmg"] * rb["lifesteal_bonus"])
            if heal > 0:
                result["lifesteal_heal"] = result.get("lifesteal_heal", 0) + heal

        # ── توانایی خودکارِ مخصوصِ ندرت‌های بالا: یه ضربه‌ی دومِ خودکار ──
        if rb["special_chance"] > 0 and random.random() < rb["special_chance"]:
            bonus = int(result["dmg"] * rb["special_pct"])
            if bonus > 0:
                result["dmg"] += bonus
                logs.append(f"🌟 **تواناییِ ذاتیِ {char_name} فعال شد!** +{bonus} آسیبِ اضافه!")

        # ── افکتِ عنصریِ تازه ──
        status = ELEMENTAL_STATUS.get(core_elem)
        if status and random.random() < status["chance"]:
            kind = status["kind"]
            if kind == "dot":
                enemy["_cc_dot_turns"] = status["turns"]
                enemy["_cc_dot_dmg"] = max(1, int(result["dmg"] * status["value"]))
            elif kind == "enemy_dmg_down":
                enemy["_cc_ddown_turns"] = status["turns"]
                enemy["_cc_ddown_pct"] = status["value"]
            elif kind == "stun":
                enemy["_cc_stun_turns"] = status["turns"]
            elif kind == "armor_shred":
                if "_cc_armor_before_shred" not in enemy:
                    enemy["_cc_armor_before_shred"] = defense.get("armor", 0)
                new_armor = max(0, int(defense.get("armor", 0) * (1 - status["value"])))
                enemy["armor"] = new_armor
                defense["armor"] = new_armor
                enemy["_cc_shred_turns"] = status["turns"]
            elif kind == "blind":
                enemy["_cc_blind_turns"] = status["turns"]
                enemy["_cc_blind_pct"] = status["value"]
            elif kind == "lifesteal":
                heal = int(result["dmg"] * status["value"])
                if heal > 0:
                    result["lifesteal_heal"] = result.get("lifesteal_heal", 0) + heal
            elif kind == "self_heal":
                max_hp = player.get("max_hp", player.get("hp", 100))
                heal = int(result["dmg"] * status["value"])
                if heal > 0:
                    player["hp"] = min(max_hp, player.get("hp", 0) + heal)
            elif kind == "armor_pierce":
                defense["armor"] = int(defense.get("armor", 0) * (1 - status["value"]))
            logs.append(f"{status['emoji']} دشمن دچار **{status['name']}** شد!")

    return result
