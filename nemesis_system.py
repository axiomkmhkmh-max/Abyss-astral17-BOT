# ============================================================
#  ASTRAL ABYSS — Nemesis System (v2)
# ------------------------------------------------------------
#  وقتی از یه دشمنِ معمولی فرار می‌کنی یا شکستت می‌ده، یه شانسی هست
#  که اون دشمن رو "به یاد بسپاری" — دفعه‌ی بعد که تو هر مپی لوت
#  می‌کنی، ممکنه همون دشمن (قوی‌تر، با یه لقبِ تشدیدی) دوباره ظاهر
#  بشه. اگه شکستش بدی، نمسیس تموم می‌شه، یه پاداشِ اضافه می‌گیری و
#  یه عنوانِ دائمی به کارنامه‌ت اضافه می‌شه. اگه بازم ببره/فرار کنی،
#  لقبش تشدید می‌شه، قوی‌تر می‌شه و یه توانایی ویژه باز می‌کنه.
# ============================================================
import random
import time

NEMESIS_TITLES = ["زخم‌خورده", "کینه‌توز", "بی‌رحم", "افسانه‌ای"]
NEMESIS_CREATE_CHANCE = 0.35   # شانسِ اینکه یه دشمنِ فرارکرده/برنده نمسیس بشه
NEMESIS_SPAWN_CHANCE  = 0.30   # شانسِ ظاهرشدنِ نمسیس تو هر مواجهه (اگه فعال باشه)
NEMESIS_TIER_HP_MULT  = 0.25   # هر تشدید، +۲۵٪ HP/دمیج
NEMESIS_HISTORY_LIMIT = 12     # حداکثر تعداد نمسیسِ شکست‌خورده که تو تاریخچه نگه می‌داریم

# ─── توانایی‌های ویژه (فقط از تشدیدِ دوم به بعد باز می‌شن) ───────
# هر نمسیس، وقتی HPش زیرِ ۵۰٪ می‌ره، یک‌بار تو کل مبارزه از یکی از
# این توانایی‌ها استفاده می‌کنه — این جدا از ضربِ سادهٔ آمار (HP/دمیج)ه.
NEMESIS_ABILITIES = {
    "خشمِ بازگشته": {
        "min_tier": 1,
        "dmg_pct": 0.55,
        "desc": "یک ضربه‌ی خشمگینِ اضافه می‌زنه که از دمیجِ معمولش قوی‌تره",
    },
    "زخمِ کهنه": {
        "min_tier": 1,
        "dmg_pct": 0.35,
        "heal_pct": 0.15,
        "desc": "بهت آسیب می‌زنه و بخشی از HPِ خودش رو ترمیم می‌کنه",
    },
    "غرشِ انتقام": {
        "min_tier": 2,
        "dmg_pct": 0.70,
        "combo_break": True,
        "desc": "یه ضربه‌ی سنگین می‌زنه و کومبوی تو رو صفر می‌کنه",
    },
}


def _pick_ability(tier: int) -> tuple[str, dict] | None:
    available = [(n, a) for n, a in NEMESIS_ABILITIES.items() if tier >= a["min_tier"]]
    if not available:
        return None
    return random.choice(available)


def maybe_create_nemesis(player: dict, enemy: dict) -> str | None:
    """موقعِ فرار یا شکست خوردن از یه دشمنِ معمولی (نه باس) صدا زده می‌شه."""
    if enemy.get("is_boss") or enemy.get("is_nemesis"):
        return None

    existing = player.get("nemesis")
    if existing and existing.get("base_name") == enemy.get("name"):
        existing["tier"] = min(existing.get("tier", 0) + 1, len(NEMESIS_TITLES) - 1)
        existing["encounters"] = existing.get("encounters", 1) + 1
        player["nemesis"] = existing
        title = NEMESIS_TITLES[existing["tier"]]
        return f"⚔️ *{enemy['name']}»‌ی {title}* قوی‌تر از قبل داره میاد سراغت..."

    try:
        from world_pulse import get_chain_effect, CHAIN_NEMESIS_SPAWN_MULT
        create_mult = CHAIN_NEMESIS_SPAWN_MULT if get_chain_effect() == "nemesis_surge" else 1.0
    except Exception:
        create_mult = 1.0

    if random.random() < NEMESIS_CREATE_CHANCE * create_mult:
        player["nemesis"] = {
            "base_name": enemy.get("name", "دشمن"),
            "tier": 0,
            "encounters": 1,
            "hp": enemy.get("hp", 100),
            "dmg": enemy.get("dmg", 10),
            "xp": enemy.get("xp", 20),
            "zen": enemy.get("zen", 15),
            "weak": enemy.get("weak", "آتش"),
            "first_seen": time.time(),
        }
        return f"👁️ حس می‌کنی *{enemy.get('name','این دشمن')}* این ماجرا رو فراموش نمی‌کنه..."
    return None


def maybe_spawn_nemesis(player: dict) -> dict | None:
    """موقعِ ساختِ یه مواجهه‌ی جدید (تو mob_combat.py) صدا زده می‌شه."""
    nem = player.get("nemesis")
    if not nem:
        return None

    try:
        from world_pulse import nemesis_spawn_boost
        spawn_mult, tier_bonus = nemesis_spawn_boost()
    except Exception:
        spawn_mult, tier_bonus = 1.0, 0

    if random.random() >= NEMESIS_SPAWN_CHANCE * spawn_mult:
        return None

    tier = min(nem.get("tier", 0) + tier_bonus, len(NEMESIS_TITLES) - 1)
    title = NEMESIS_TITLES[tier]
    mult = 1 + NEMESIS_TIER_HP_MULT * (tier + 1)
    hp = int(nem.get("hp", 100) * mult)
    ability = _pick_ability(tier)
    return {
        "name": f"{nem['base_name']} {title}",
        "hp": hp,
        "max_hp": hp,
        "dmg": int(nem.get("dmg", 10) * mult),
        "xp": int(nem.get("xp", 20) * mult),
        "zen": int(nem.get("zen", 15) * mult),
        "weak": nem.get("weak", "آتش"),
        "drop_chance": 0.5,
        "tier": "nemesis",
        "nemesis_tier": tier,
        "is_boss": False,
        "is_nemesis": True,
        "ability_name": ability[0] if ability else None,
        "ability_used": False,
    }


def maybe_trigger_ability(enemy: dict) -> dict | None:
    """موقعِ هر راندِ مبارزه با نمسیس صدا زده می‌شه (تو mob_combat.py).
    اگه HP نمسیس زیرِ ۵۰٪ باشه و هنوز تواناییش رو استفاده نکرده، یک‌بار
    توی کل مبارزه فعالش می‌کنه. برمی‌گردونه: {dmg, heal, combo_break, msg} یا None."""
    if not enemy.get("is_nemesis") or not enemy.get("ability_name") or enemy.get("ability_used"):
        return None
    if enemy.get("hp", 0) > enemy.get("max_hp", 1) * 0.5:
        return None

    name = enemy["ability_name"]
    ability = NEMESIS_ABILITIES.get(name)
    if not ability:
        return None
    enemy["ability_used"] = True
    dmg = int(enemy.get("dmg", 10) * ability["dmg_pct"])
    heal = int(enemy.get("max_hp", enemy.get("hp", 100)) * ability.get("heal_pct", 0))
    msg = f"👁️‍🗨️ **{enemy['name']}** توانایی ویژه‌ش «{name}» رو فعال کرد! {ability['desc']}."
    return {"dmg": dmg, "heal": heal, "combo_break": ability.get("combo_break", False), "msg": msg}


def clear_nemesis_on_defeat(player: dict, enemy: dict) -> str | None:
    """موقعِ کشتنِ یه دشمن صدا زده می‌شه — اگه همون نمسیس بود، پاکش می‌کنه،
    یه عنوانِ دائمی می‌ده و تو تاریخچه ثبتش می‌کنه."""
    if not enemy.get("is_nemesis"):
        return None
    nem = player.get("nemesis")
    if "nemesis" in player:
        del player["nemesis"]

    base_name = (nem or {}).get("base_name") or enemy.get("name", "دشمن")
    tier = (nem or {}).get("tier", 0)
    encounters = (nem or {}).get("encounters", 1)
    title_name = f"شکارچیِ {base_name}"

    titles = player.setdefault("titles_unlocked", [])
    gained_title = title_name not in titles
    if gained_title:
        titles.append(title_name)
    nem_titles = player.setdefault("nemesis_titles", [])
    if title_name not in nem_titles:
        nem_titles.append(title_name)

    history = player.setdefault("nemesis_history", [])
    history.append({
        "name": base_name,
        "tier": tier,
        "encounters": encounters,
        "defeated_at": time.time(),
    })
    if len(history) > NEMESIS_HISTORY_LIMIT:
        del history[: len(history) - NEMESIS_HISTORY_LIMIT]

    msg = f"🩸 **بالاخره از {enemy['name']} انتقام گرفتی!** این دشمنی تموم شد."
    if gained_title:
        msg += f"\n🏅 عنوانِ دائمیِ جدید: **{title_name}**"
    return msg
