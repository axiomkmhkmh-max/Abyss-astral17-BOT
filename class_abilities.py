# ============================================================
#  ASTRAL ABYSS RPG — Class Active-Ability Systems (Stage 3)
#  (class_abilities.py)
# ============================================================
#
# این ماژول لایه‌ی «فعال»ِ چهار سیستمِ کلاسیه — چیزی که تو Stage 2
# فقط پسیو بود (تو محاسبه‌ی خامِ combat.py). این‌جا بازیکن دکمه می‌زنه،
# منبعِ کلاسش (مانا/طلا/فیض/استامینا) خرج می‌شه، و یه اثرِ واقعی رخ می‌ده:
#
#   🧙‍♂️ جادوگر  → طلسمِ ترکیبی (Spell Synergy) / سپرِ مانا / طوفانِ ناحیه‌ای
#   💰 تاجر    → اجیر/اخراجِ مزدور / چانه‌زنی / رشوه به دشمن
#   ✨ درمانگر → نورِ مقدس / سپرِ الهی / پاکسازی / خودـ‌احیایی
#   🗺️ ماجراجو → کاوشِ دخمه (رلیک/تله/طلا)
#
# منطقِ خالص این‌جاست (بدون هیچ وابستگی‌ای به aiogram)؛ UI/دکمه‌ها تو
# class_ability_handlers.py هستن. combat.py هم دو تا فلگ/فیلد از این‌جا
# رو موقعِ محاسبه‌ی نبرد مصرف می‌کنه: player["_wizard_spell_charge"] و
# class_system_data["mana_shield_charges"] / ["divine_shield_charges"] /
# ["relics_collected"].
# ============================================================

import random
import time

# ─── ریجنِ خودکارِ منابع (مانا/استامینا/فیض) ─────────────────────
# هر منبعی هر REGEN_INTERVAL_SEC ثانیه، به‌اندازه‌ی regen_key خودش
# (که تو class_system.py تعریف شده) پر می‌شه — محاسبه‌ش lazy‌ه، یعنی
# نیازی به تسک/کرون نیست: فقط موقعِ استفاده یا نمایشِ پنل، فاصله‌ی
# زمانیِ سپری‌شده از آخرین آپدیت حساب می‌شه.
REGEN_INTERVAL_SEC = 90

RESOURCE_KEYS = {
    "wizard":     ("mana",    "max_mana",    "mana_regen"),
    "adventurer": ("stamina", "max_stamina", "stamina_regen"),
    "healer":     ("faith",   "max_faith",   "faith_regen"),
}

REVIVE_REGEN_SEC = 24 * 3600  # درمانگر هر ۲۴ ساعت یه Self-Revive جدید می‌گیره (سقف ۱)


def tick_regen(player: dict) -> None:
    """قبل از هرجایی که منبعِ کلاس نمایش داده می‌شه یا مصرف می‌شه، صدا زده
    می‌شه تا ریجنِ گذشته اعمال بشه. برای تاجر کاری نمی‌کنه (منبعش ریجن‌شونده نیست)."""
    cls = player.get("class")
    csd = player.setdefault("class_system_data", {})
    now = time.time()

    if cls in RESOURCE_KEYS:
        res_key, max_key, regen_key = RESOURCE_KEYS[cls]
        last = csd.get("_last_regen_ts", now)
        elapsed = max(0.0, now - last)
        ticks = int(elapsed // REGEN_INTERVAL_SEC)
        if ticks > 0:
            cur = csd.get(res_key, 0)
            mx = csd.get(max_key, cur)
            regen = csd.get(regen_key, 0)
            csd[res_key] = min(mx, cur + regen * ticks)
            csd["_last_regen_ts"] = last + ticks * REGEN_INTERVAL_SEC
        else:
            csd.setdefault("_last_regen_ts", now)

    if cls == "healer":
        last_rv = csd.get("_last_revive_regen_ts", now)
        if csd.get("revives_available", 0) < 1 and (now - last_rv) >= REVIVE_REGEN_SEC:
            csd["revives_available"] = csd.get("revives_available", 0) + 1
            csd["_last_revive_regen_ts"] = now
        else:
            csd.setdefault("_last_revive_regen_ts", now)


def resource_line(player: dict) -> str:
    """یه خطِ نمایشیِ آماده برای منبعِ کلاسِ فعلی (بعد از tick_regen)."""
    from class_system import CLASSES
    cls = player.get("class")
    c = CLASSES.get(cls, {})
    csd = player.get("class_system_data", {})
    if cls in RESOURCE_KEYS:
        res_key, max_key, _ = RESOURCE_KEYS[cls]
        return f"🔹 {c.get('resource_label_fa','منبع')}: {csd.get(res_key,0)}/{csd.get(max_key,0)}"
    if cls == "merchant":
        return f"🔹 {c.get('resource_label_fa','منبع')}: ×{csd.get('gold_multiplier',1.0):.2f}"
    return "🔹 منبع: —"


# ─── تشخیصِ دشمنِ «مرده‌ی متحرک» — برای Undead Purge درمانگر ─────
# دیتاست دشمن‌ها (combat.py) تگِ صریحِ "undead" نداره؛ به‌جاش از روی
# ایموجی/ضعفِ دشمن (که معمولاً «مقدس»ه برای مرده‌های متحرک) تشخیص می‌دیم.
_UNDEAD_MARKERS = ("🧟", "💀", "👻", "🦴")


def is_undead(enemy: dict) -> bool:
    if not enemy:
        return False
    name = enemy.get("name", "")
    if any(m in name for m in _UNDEAD_MARKERS):
        return True
    return enemy.get("weak") == "مقدس"


# ════════════════════════════════════════════════════════════
#  🧙‍♂️ WIZARD — Mana & Spell Synergy
# ════════════════════════════════════════════════════════════
WIZARD_SPELL_COST = 20
WIZARD_SHIELD_COST = 15
WIZARD_NOVA_COST = 30
_WIZARD_ALL_ELEMENTS = ["fire", "water", "lightning"]
_WIZARD_ELEMENT_FA = {"fire": "🔥 آتش", "water": "❄️ آب/یخ", "lightning": "⚡ رعد"}


def wizard_cast_synergy(player: dict) -> dict:
    """طلسمِ ترکیبی: مانا خرج می‌کنه و رو ضربه‌ی بعدیِ نبرد یه فلگِ مصرفی
    می‌ذاره (player["_wizard_spell_charge"]) که combat.py موقعِ حمله‌ی بعدی
    مصرفش می‌کنه — دمیجِ اضافه + تضمینِ برخورد به ضعفِ عنصریِ دشمن."""
    if player.get("class") != "wizard":
        return {"ok": False, "msg": "❌ این قابلیت مخصوصِ جادوگره."}
    tick_regen(player)
    csd = player.setdefault("class_system_data", {})
    if csd.get("mana", 0) < WIZARD_SPELL_COST:
        return {"ok": False, "msg": f"❌ مانا کافی نیست! ({csd.get('mana',0)}/{WIZARD_SPELL_COST})"}

    csd["mana"] -= WIZARD_SPELL_COST
    csd["synergy_combos_used"] = csd.get("synergy_combos_used", 0) + 1
    player["_wizard_spell_charge"] = True

    unlocked = None
    known = csd.get("elements_known", [])
    if len(known) < len(_WIZARD_ALL_ELEMENTS) and csd["synergy_combos_used"] % 4 == 0:
        remaining = [e for e in _WIZARD_ALL_ELEMENTS if e not in known]
        if remaining:
            new_el = random.choice(remaining)
            known.append(new_el)
            csd["elements_known"] = known
            unlocked = new_el

    return {"ok": True, "unlocked": unlocked, "mana_left": csd["mana"]}


def wizard_mana_shield(player: dict) -> dict:
    if player.get("class") != "wizard":
        return {"ok": False, "msg": "❌ این قابلیت مخصوصِ جادوگره."}
    tick_regen(player)
    csd = player.setdefault("class_system_data", {})
    if csd.get("mana", 0) < WIZARD_SHIELD_COST:
        return {"ok": False, "msg": f"❌ مانا کافی نیست! ({csd.get('mana',0)}/{WIZARD_SHIELD_COST})"}
    csd["mana"] -= WIZARD_SHIELD_COST
    csd["mana_shield_charges"] = csd.get("mana_shield_charges", 0) + 1
    return {"ok": True, "charges": csd["mana_shield_charges"], "mana_left": csd["mana"]}


def wizard_arcane_nova(player: dict, enemy: dict | None) -> dict:
    """طوفانِ ناحیه‌ای: بدونِ اینکه دشمن ضدحمله بزنه، مستقیم بهش دمیج می‌زنه."""
    if player.get("class") != "wizard":
        return {"ok": False, "msg": "❌ این قابلیت مخصوصِ جادوگره."}
    if not enemy:
        return {"ok": False, "msg": "❌ اول باید وارد نبرد بشی (یه دشمن پیدا کن)."}
    tick_regen(player)
    csd = player.setdefault("class_system_data", {})
    if csd.get("mana", 0) < WIZARD_NOVA_COST:
        return {"ok": False, "msg": f"❌ مانا کافی نیست! ({csd.get('mana',0)}/{WIZARD_NOVA_COST})"}

    csd["mana"] -= WIZARD_NOVA_COST
    atk = (player.get("stats") or {}).get("atk", 10)
    dmg = int((atk * 2.2 + player.get("level", 1) * 4) * random.uniform(0.9, 1.3))
    enemy["hp"] = max(0, enemy.get("hp", enemy.get("max_hp", 1)) - dmg)
    return {"ok": True, "dmg": dmg, "killed": enemy["hp"] <= 0, "mana_left": csd["mana"]}


# ════════════════════════════════════════════════════════════
#  💰 MERCHANT — Economy & Trading Empire
# ════════════════════════════════════════════════════════════
MERC_BASE_COST = 150
MERC_COST_STEP = 120
MAX_MERCS = 5
MERC_NAMES = [
    "🗡 حسام، شمشیرزنِ کاروان", "🏹 سایه، کماندارِ بیابان", "🛡 بهروز، سپردارِ سابق",
    "🪓 گرزان، تبرزنِ کوهستان", "🔪 نیلا، خنجرچیِ سایه‌ها", "⚔️ رستم‌بیگ، مزدورِ کهنه‌کار",
]

HAGGLE_COOLDOWN_SEC = 3600
BRIBE_TIER_COST = {"common": 40, "rare": 90, "epic": 180, "legendary": 350}


def merchant_hire_cost(player: dict) -> int:
    n = len(player.get("class_system_data", {}).get("mercenaries_hired", []))
    return MERC_BASE_COST + n * MERC_COST_STEP


def merchant_hire_mercenary(player: dict) -> dict:
    if player.get("class") != "merchant":
        return {"ok": False, "msg": "❌ این قابلیت مخصوصِ تاجره."}
    csd = player.setdefault("class_system_data", {})
    mercs = csd.setdefault("mercenaries_hired", [])
    if len(mercs) >= MAX_MERCS:
        return {"ok": False, "msg": f"❌ ظرفیتِ مزدور پره! ({MAX_MERCS}/{MAX_MERCS})"}
    cost = merchant_hire_cost(player)
    if player.get("zen", 0) < cost:
        return {"ok": False, "msg": f"❌ طلای کافی نداری! ({player.get('zen',0):,}/{cost:,})"}
    player["zen"] -= cost
    name = random.choice(MERC_NAMES)
    mercs.append(name)
    return {"ok": True, "name": name, "cost": cost, "count": len(mercs)}


def merchant_dismiss_mercenary(player: dict, index: int) -> dict:
    if player.get("class") != "merchant":
        return {"ok": False, "msg": "❌ این قابلیت مخصوصِ تاجره."}
    csd = player.setdefault("class_system_data", {})
    mercs = csd.get("mercenaries_hired", [])
    if not (0 <= index < len(mercs)):
        return {"ok": False, "msg": "❌ همچین مزدوری نداری."}
    removed = mercs.pop(index)
    return {"ok": True, "removed": removed}


def merchant_haggle(player: dict) -> dict:
    """چانه‌زنی: کولداونی، شانسی ضریبِ درآمدِ طلا (gold_multiplier) رو کمی بالا می‌بره."""
    if player.get("class") != "merchant":
        return {"ok": False, "msg": "❌ این قابلیت مخصوصِ تاجره."}
    csd = player.setdefault("class_system_data", {})
    now = time.time()
    last = csd.get("_last_haggle_ts", 0)
    remaining = int(HAGGLE_COOLDOWN_SEC - (now - last))
    if remaining > 0:
        return {"ok": False, "cooldown": remaining}
    csd["_last_haggle_ts"] = now
    success = random.random() < 0.7
    if success:
        gain = round(random.uniform(0.02, 0.05), 3)
        csd["gold_multiplier"] = round(min(2.0, csd.get("gold_multiplier", 1.0) + gain), 3)
        csd["market_influence"] = csd.get("market_influence", 0) + 1
        return {"ok": True, "success": True, "gain": gain, "mult": csd["gold_multiplier"]}
    return {"ok": True, "success": False}


def merchant_bribe(player: dict, enemy: dict | None) -> dict:
    """رشوه به دشمن: دشمنِ فعلی رو بدونِ جایزه/باخت فراری می‌ده — برای فرارِ امن از یه دشمنِ سخت."""
    if player.get("class") != "merchant":
        return {"ok": False, "msg": "❌ این قابلیت مخصوصِ تاجره."}
    if not enemy:
        return {"ok": False, "msg": "❌ الان تو نبرد نیستی."}
    cost = BRIBE_TIER_COST.get(enemy.get("tier", "common"), 40)
    if player.get("zen", 0) < cost:
        return {"ok": False, "msg": f"❌ طلای کافی نداری! ({player.get('zen',0):,}/{cost:,})"}
    player["zen"] -= cost
    return {"ok": True, "cost": cost}


# ════════════════════════════════════════════════════════════
#  ✨ HEALER — Holy Grace & Support
# ════════════════════════════════════════════════════════════
HOLY_LIGHT_COST = 15
DIVINE_SHIELD_COST = 12
PURIFY_COST = 20


def _max_hp(player: dict) -> int:
    try:
        from skill_tree import effective_max_hp
        return effective_max_hp(player)
    except Exception:
        return player.get("max_hp", 100)


def healer_holy_light(player: dict, enemy: dict | None) -> dict:
    """نورِ مقدس: همیشه خودت رو هیل می‌کنه؛ اگه دشمنِ فعلی مرده‌ی متحرکه، بهش دمیجِ اضافه هم می‌زنه."""
    if player.get("class") != "healer":
        return {"ok": False, "msg": "❌ این قابلیت مخصوصِ درمانگره."}
    tick_regen(player)
    csd = player.setdefault("class_system_data", {})
    if csd.get("faith", 0) < HOLY_LIGHT_COST:
        return {"ok": False, "msg": f"❌ فیضِ کافی نداری! ({csd.get('faith',0)}/{HOLY_LIGHT_COST})"}

    csd["faith"] -= HOLY_LIGHT_COST
    mx = _max_hp(player)
    heal = int(mx * 0.18)
    player["hp"] = min(mx, player.get("hp", 0) + heal)

    dmg = 0
    undead_hit = False
    killed = False
    if enemy and is_undead(enemy):
        undead_hit = True
        atk = (player.get("stats") or {}).get("atk", 10)
        dmg = int(atk * 1.8 + player.get("level", 1) * 3)
        enemy["hp"] = max(0, enemy.get("hp", enemy.get("max_hp", 1)) - dmg)
        killed = enemy["hp"] <= 0
        csd["undead_purged"] = csd.get("undead_purged", 0) + (1 if killed else 0)

    return {"ok": True, "heal": heal, "dmg": dmg, "undead_hit": undead_hit, "killed": killed, "faith_left": csd["faith"]}


def healer_divine_shield(player: dict) -> dict:
    if player.get("class") != "healer":
        return {"ok": False, "msg": "❌ این قابلیت مخصوصِ درمانگره."}
    tick_regen(player)
    csd = player.setdefault("class_system_data", {})
    if csd.get("faith", 0) < DIVINE_SHIELD_COST:
        return {"ok": False, "msg": f"❌ فیضِ کافی نداری! ({csd.get('faith',0)}/{DIVINE_SHIELD_COST})"}
    csd["faith"] -= DIVINE_SHIELD_COST
    csd["divine_shield_charges"] = csd.get("divine_shield_charges", 0) + 1
    return {"ok": True, "charges": csd["divine_shield_charges"], "faith_left": csd["faith"]}


def healer_purify(player: dict) -> dict:
    """پاکسازی: یه هیلِ مستقیمِ متوسط — راهِ سریعِ برگشت به میدون بدونِ نیاز به نبرد."""
    if player.get("class") != "healer":
        return {"ok": False, "msg": "❌ این قابلیت مخصوصِ درمانگره."}
    tick_regen(player)
    csd = player.setdefault("class_system_data", {})
    if csd.get("faith", 0) < PURIFY_COST:
        return {"ok": False, "msg": f"❌ فیضِ کافی نداری! ({csd.get('faith',0)}/{PURIFY_COST})"}
    csd["faith"] -= PURIFY_COST
    mx = _max_hp(player)
    heal = int(mx * 0.12)
    player["hp"] = min(mx, player.get("hp", 0) + heal)
    return {"ok": True, "heal": heal, "faith_left": csd["faith"]}


def healer_try_revive(player: dict) -> dict:
    """موقعِ مرگ صدا زده می‌شه (combat_handlers.py) — اگه Self-Revive داشته باشه، به‌جای اسپاون تو نقشه‌ی رندوم، همون‌جا با بخشی از HP زنده می‌مونه."""
    if player.get("class") != "healer":
        return {"revived": False}
    csd = player.setdefault("class_system_data", {})
    if csd.get("revives_available", 0) <= 0:
        return {"revived": False}
    csd["revives_available"] -= 1
    mx = _max_hp(player)
    player["hp"] = max(1, int(mx * 0.35))
    return {"revived": True, "messages": ["✨ **نورِ مقدس دورت رو گرفت و خودت رو Self-Revive کردی!**"]}


# ════════════════════════════════════════════════════════════
#  🗺️ ADVENTURER — Exploration & Relic System
# ════════════════════════════════════════════════════════════
DUNGEON_STAMINA_COST = 25
RELIC_CAP_FOR_BONUS = 10  # بعدِ ۱۰ تا از یه نوعِ رلیک، بونوسِ اون نوع دیگه رشد نمی‌کنه (جلوگیری از snowball)

RELIC_POOL = [
    "🗽 پیکرکِ فراموش‌شده", "📿 تسبیحِ روحِ باستانی", "🏺 کوزه‌ی رازآلودِ اعماق",
    "💍 حلقه‌ی گمشده‌ی پادشاهِ کهن", "🔱 سه‌شاخه‌ی اعماقِ تاریک", "🕯️ چراغِ ابدیِ گورستان",
    "📜 طومارِ زبانِ فراموش‌شده", "⚱️ خاکسترِ محافظِ دخمه",
]

# ─── باگ‌فیکس/گسترش: قبلاً هر ۸ آیتم دقیقاً یه اثرِ یکسان (فقط دمیجِ فلت)
# داشتن — فقط اسم و ایموجی فرق داشت. الان هرکدوم اثرِ مخصوصِ خودشو داره:
# چهارتا رو بونوسِ نبرد می‌دن (دمیج/کریت/لایف‌استیل/دفاع)، چهارتا رو
# خودِ چرخه‌ی کاوش رو بهتر می‌کنن (شانسِ اکتشاف/جاخالی‌دادنِ تله/طلای
# دخمه/شانسِ پیداکردنِ رلیکِ بعدی). هر نوع جدا تا RELIC_CAP_FOR_BONUS
# واحد حساب می‌شه — دقیقاً همون منطقِ سقفِ قبلی، حالا per-type.
RELIC_EFFECTS = {
    "🗽 پیکرکِ فراموش‌شده":        {"stat": "dmg_flat",         "per_unit": 2,     "desc": "دمیجِ فلت"},
    "🔱 سه‌شاخه‌ی اعماقِ تاریک":    {"stat": "crit_pct",         "per_unit": 0.005, "desc": "شانسِ کریت"},
    "📿 تسبیحِ روحِ باستانی":       {"stat": "lifesteal_pct",    "per_unit": 0.004, "desc": "لایف‌استیل"},
    "⚱️ خاکسترِ محافظِ دخمه":       {"stat": "defense_pct",      "per_unit": 0.005, "desc": "کاهشِ دمیجِ ضدحمله"},
    "🕯️ چراغِ ابدیِ گورستان":       {"stat": "exploration_luck", "per_unit": 1,     "desc": "شانسِ اکتشاف"},
    "📜 طومارِ زبانِ فراموش‌شده":    {"stat": "trap_evade_pct",   "per_unit": 0.03,  "desc": "جاخالی‌دادنِ تله"},
    "🏺 کوزه‌ی رازآلودِ اعماق":      {"stat": "dungeon_zen_pct",  "per_unit": 0.05,  "desc": "طلای دخمه‌های خالی"},
    "💍 حلقه‌ی گمشده‌ی پادشاهِ کهن": {"stat": "relic_find_pct",   "per_unit": 0.02,  "desc": "شانسِ پیداکردنِ رلیک"},
}


# ─── نگاشتِ نام‌های قدیمی → کانونیک — اگه اسم/ایموجیِ یه رلیک بعداً عوض
# بشه (مثلِ 🗿→🗽 برای پیکرک)، رلیک‌هایی که بازیکن‌ها از قبل تو
# relics_collected دارن با اسمِ قدیمی ذخیره‌ست؛ این alias باعث می‌شه
# بدونِ نیاز به migration دستیِ دیتابیس، همچنان اثرشون درست حساب بشه.
RELIC_NAME_ALIASES = {
    "🗿 پیکرکِ فراموش‌شده": "🗽 پیکرکِ فراموش‌شده",
}


def _canonical_relic_name(name: str) -> str:
    return RELIC_NAME_ALIASES.get(name, name)


def _relic_counts(player: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in player.get("class_system_data", {}).get("relics_collected", []):
        r = _canonical_relic_name(r)
        counts[r] = counts.get(r, 0) + 1
    return counts


def adventurer_relic_bonuses(player: dict) -> dict:
    """مجموعِ اثرِ همه‌ی رلیک‌های جمع‌شده، دسته‌بندی‌شده بر اساسِ نوع.
    combat.py و adventurer_explore این‌رو صدا می‌زنن تا اثرِ واقعیِ هر
    رلیک رو اعمال کنن (به‌جای دمیجِ یکسانِ قبلی)."""
    counts = _relic_counts(player)
    totals = {stat: 0 for stat in (
        "dmg_flat", "crit_pct", "lifesteal_pct", "defense_pct",
        "exploration_luck", "trap_evade_pct", "dungeon_zen_pct", "relic_find_pct",
    )}
    for name, n in counts.items():
        eff = RELIC_EFFECTS.get(name)
        if not eff:
            continue
        units = min(n, RELIC_CAP_FOR_BONUS)
        totals[eff["stat"]] += units * eff["per_unit"]
    return totals


def adventurer_explore(player: dict) -> dict:
    """کاوشِ دخمه: استامینا خرج می‌کنه، بر اساسِ exploration_luck (+ بونوسِ
    رلیکِ چراغِ گورستان) یکی از سه نتیجه پیش میاد: پیداکردنِ رلیک (شانسش
    از رلیکِ حلقه هم بونوس می‌گیره)، خوردنِ تله (evade‌ش از luck + رلیکِ
    طومار میاد)، یا یه دخمه‌ی خالی با طلا (که از رلیکِ کوزه بیشتر می‌شه)."""
    if player.get("class") != "adventurer":
        return {"ok": False, "msg": "❌ این قابلیت مخصوصِ ماجراجوئه."}
    tick_regen(player)
    csd = player.setdefault("class_system_data", {})
    if csd.get("stamina", 0) < DUNGEON_STAMINA_COST:
        return {"ok": False, "msg": f"❌ استامینای کافی نداری! ({csd.get('stamina',0)}/{DUNGEON_STAMINA_COST})"}

    csd["stamina"] -= DUNGEON_STAMINA_COST
    relic_b = adventurer_relic_bonuses(player)
    luck = csd.get("exploration_luck", 5) + relic_b["exploration_luck"]
    relic_chance = min(0.45, 0.15 + luck * 0.01) + relic_b["relic_find_pct"]
    relic_chance = min(0.65, relic_chance)  # سقفِ کلی، تا بونوسِ حلقه بی‌نهایت رشد نکنه
    trap_chance = max(0.10, 0.30 - luck * 0.01)

    roll = random.random()
    if roll < relic_chance:
        relic = random.choice(RELIC_POOL)
        csd.setdefault("relics_collected", []).append(relic)
        csd["dungeons_cleared"] = csd.get("dungeons_cleared", 0) + 1
        return {"ok": True, "outcome": "relic", "relic": relic, "stamina_left": csd["stamina"]}

    if roll < relic_chance + trap_chance:
        evaded = random.random() < min(0.75, luck * 0.03 + relic_b["trap_evade_pct"])
        if evaded:
            return {"ok": True, "outcome": "trap_evaded", "stamina_left": csd["stamina"]}
        dmg = random.randint(5, 15)
        player["hp"] = max(1, player.get("hp", 1) - dmg)
        return {"ok": True, "outcome": "trap_hit", "dmg": dmg, "stamina_left": csd["stamina"]}

    csd["dungeons_cleared"] = csd.get("dungeons_cleared", 0) + 1
    zen = int(random.randint(20, 60) * (1 + relic_b["dungeon_zen_pct"]))
    player["zen"] = player.get("zen", 0) + zen
    return {"ok": True, "outcome": "empty", "zen": zen, "stamina_left": csd["stamina"]}
