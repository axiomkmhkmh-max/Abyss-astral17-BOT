# ============================================================
#  ASTRAL ABYSS RPG — Katana Multi-Dimensional Upgrade System
#  (katana_dimensions.py)  —  فاز ۱ / بخش ب
# ============================================================
#
# این فایل هم کاملاً جدید و مستقله. به katana_system.py دست نمی‌زنه —
# بعد «قدرت» (Power) دقیقاً همون katana_level فعلیه (۱ تا ۱۰۲)، فقط این‌جا
# به‌عنوان یکی از ۴ محور نمایش داده می‌شه. ۳ بعد جدید (سرعت/دقت/روح) کاملاً
# مستقل از فورج قدیمی، سطح و هزینه‌ی خودشون رو دارن.
#
# برخلاف بیداری (که شانس شکست داره)، ارتقاء ابعاد شکست نمی‌خوره —
# این‌جا هزینه (طلا+ماده) خودش سختی/بالانسه، نه ریسک. این باعث می‌شه
# ابعاد یه "grind قطعی و طولانی" باشن، نه یه قمار مثل بیداری.
#
# ── ساختار ذخیره‌سازی (per-character) ──
#   player["katana_dimensions"] = {
#       "<character_name>": {
#           "speed": 12,
#           "precision": 8,
#           "soul": 3,
#       },
#       ...
#   }
#   (بعد "power" ذخیره‌ی جدا نداره؛ همیشه از player["katana_level"] خونده می‌شه)
#
# هیچ تابعی مستقیم save_player صدا نمی‌زنه؛ هندلر (فاز بعد) مسئول کسر طلا/مواد و ذخیره‌ست.
# ============================================================

DIMENSION_KEYS = ["speed", "precision", "soul"]  # "power" جدا مدیریت می‌شه (katana_level)

DIMENSION_INFO = {
    "power": {
        "name_fa": "قدرت", "emoji": "⚔️", "max": 102,
        "desc": "همون سطح فورج اصلی (۱ تا ۱۰۲) — از /forge ارتقا پیدا می‌کنه.",
    },
    "speed": {
        "name_fa": "سرعت", "emoji": "💨", "max": 50, "material": "wind_essence",
        "desc": "هر ۱۰ سطح، ۱ ثانیه از کول‌داون حملات کم می‌کنه.",
    },
    "precision": {
        "name_fa": "دقت", "emoji": "🎯", "max": 50, "material": "crystal_shard",
        "desc": "شانس کریت و شانس هیت رو افزایش می‌ده.",
    },
    "soul": {
        "name_fa": "روح", "emoji": "👻", "max": 30, "material": "soul_fragment",
        "desc": "لایف‌استیل، شانس اثر ویژه و شانس مهارت‌ها رو افزایش می‌ده.",
    },
}

DIMENSION_MATERIALS_INFO = {
    "wind_essence":  {"emoji": "🌬️", "name_fa": "جوهر باد",       "rarity": "rare"},
    "crystal_shard": {"emoji": "💎", "name_fa": "تراشه‌ی کریستال", "rarity": "rare"},
    "soul_fragment": {"emoji": "🔮", "name_fa": "قطعه‌ی روح",       "rarity": "epic"},
}

_BASE_COST = {"speed": 800, "precision": 900, "soul": 2500}
_COST_EXP = {"speed": 1.30, "precision": 1.30, "soul": 1.45}
_MAT_QTY_BASE = {"speed": 2, "precision": 2, "soul": 1}


# ────────────────────────────────────────────────────────────
# ۱) دسترسی به سطح فعلی
# ────────────────────────────────────────────────────────────

def get_dimensions(player: dict, character_name: str) -> dict:
    """entry رو idempotent می‌سازه/برمی‌گردونه (فقط سرعت/دقت/روح، همه از سطح ۱ شروع می‌شن)."""
    store = player.setdefault("katana_dimensions", {})
    entry = store.get(character_name)
    if entry is None:
        entry = {k: 1 for k in DIMENSION_KEYS}
        store[character_name] = entry
    return entry


def get_dimension_level(player: dict, character_name: str, dim: str) -> int:
    if dim == "power":
        return player.get("katana_level", 1)
    return get_dimensions(player, character_name).get(dim, 1)


# ────────────────────────────────────────────────────────────
# ۲) هزینه‌ی ارتقا
# ────────────────────────────────────────────────────────────

def dimension_upgrade_cost(dim: str, target_level: int) -> int:
    return int(_BASE_COST[dim] * (target_level ** _COST_EXP[dim]))


def dimension_material_need(dim: str, target_level: int) -> tuple[str, int]:
    mat = DIMENSION_INFO[dim]["material"]
    qty = _MAT_QTY_BASE[dim] + target_level // 5
    return mat, qty


def attempt_dimension_upgrade(player: dict, character_name: str, dim: str,
                               gold: int, inventory: dict) -> dict:
    """مثل attempt_awaken تو katana_core.py — فقط محاسبه/اعتبارسنجی، بدون کسر واقعی.
    ارتقاء ابعاد شکست نمی‌خوره (فقط چک هزینه/موجودی)."""
    if dim not in DIMENSION_KEYS:
        return {"success": False, "message": "بعد نامعتبر."}

    cur = get_dimension_level(player, character_name, dim)
    cap = DIMENSION_INFO[dim]["max"]
    if cur >= cap:
        return {"success": False, "new_level": cur, "gold_spent": 0, "material_spent": 0,
                "message": f"{DIMENSION_INFO[dim]['emoji']} بعد «{DIMENSION_INFO[dim]['name_fa']}» به سقف خودش رسیده! ({cur}/{cap})"}

    target = cur + 1
    cost = dimension_upgrade_cost(dim, target)
    mat, qty = dimension_material_need(dim, target)

    if gold < cost:
        return {"success": False, "new_level": cur, "gold_spent": 0, "material_spent": 0,
                "material": mat, "message": f"💰 طلای کافی نداری! به {cost:,} Zen نیاز داری."}

    if inventory.get(mat, 0) < qty:
        info = DIMENSION_MATERIALS_INFO[mat]
        return {"success": False, "new_level": cur, "gold_spent": 0, "material_spent": 0,
                "material": mat,
                "message": f"📦 {info['emoji']} {info['name_fa']} کافی نداری! ({inventory.get(mat,0)}/{qty})"}

    entry = get_dimensions(player, character_name)
    entry[dim] = target
    return {"success": True, "new_level": target, "gold_spent": cost, "material": mat,
            "material_spent": qty,
            "message": f"{DIMENSION_INFO[dim]['emoji']} بعد «{DIMENSION_INFO[dim]['name_fa']}» به سطح {target}/{cap} رسید!"}


# ────────────────────────────────────────────────────────────
# ۳) اثرات هر بعد
# ────────────────────────────────────────────────────────────

def speed_cooldown_reduction(level: int) -> float:
    """هر ۱۰ سطح = ۱ ثانیه کمتر (max level=50 → 5 ثانیه)."""
    return level // 10


def precision_bonus(level: int) -> dict:
    return {"crit": round(level * 0.003, 4), "hit": round(level * 0.002, 4)}


def soul_bonus(level: int) -> dict:
    return {
        "lifesteal": round(level * 0.002, 4),
        "special_chance_add": round(level * 0.0015, 4),
        "skill_chance_add": round(level * 0.001, 4),
    }


def calc_dimensions_bonus(player: dict, character_name: str) -> dict:
    """جمع نهاییِ بونوس ۳ بعد (سرعت/دقت/روح). فاز۲ این رو با calc_katana_bonus ترکیب می‌کنه."""
    entry = get_dimensions(player, character_name)
    prec = precision_bonus(entry.get("precision", 1))
    soul = soul_bonus(entry.get("soul", 1))
    return {
        "cooldown_reduction_seconds": speed_cooldown_reduction(entry.get("speed", 1)),
        "crit": prec["crit"],
        "hit": prec["hit"],
        "lifesteal": soul["lifesteal"],
        "special_chance_add": soul["special_chance_add"],
        "skill_chance_add": soul["skill_chance_add"],
    }


# ────────────────────────────────────────────────────────────
# ۴) نمایش
# ────────────────────────────────────────────────────────────

def display_dimensions(player: dict, character_name: str) -> str:
    from economy import bz_to_display
    entry = get_dimensions(player, character_name)
    power_lv = player.get("katana_level", 1)

    lines = ["🔹 **ابعاد چندگانه‌ی کاتانا** 🔹", ""]

    lines.append(f"⚔️ قدرت (Power): سطح {power_lv}/{DIMENSION_INFO['power']['max']}")
    lines.append(f"   _{DIMENSION_INFO['power']['desc']}_")
    lines.append("")

    for dim in ("speed", "precision", "soul"):
        info = DIMENSION_INFO[dim]
        cur = entry.get(dim, 1)
        cap = info["max"]
        lines.append(f"{info['emoji']} {info['name_fa']} ({dim.title()}): سطح {cur}/{cap}")
        lines.append(f"   _{info['desc']}_")
        if cur < cap:
            target = cur + 1
            cost = dimension_upgrade_cost(dim, target)
            mat, qty = dimension_material_need(dim, target)
            minfo = DIMENSION_MATERIALS_INFO[mat]
            lines.append(f"   ➡️ ارتقا به {target}: {bz_to_display(cost)} + {qty}x {minfo['emoji']} {minfo['name_fa']}")
        else:
            lines.append("   🏆 به سقف رسیده")
        lines.append("")

    return "\n".join(lines).strip()
