# ============================================================
#  ASTRAL ABYSS — Artifact Forge (کورهٔ مصنوعات)
# ------------------------------------------------------------
#  ۱۴ آیتمِ legendaryِ نقشه‌ای (Divine Shard، Dragon Heart، Abyss
#  Heart و امثالش) تا اینجا فقط قابل‌فروش بودن، یا به‌عنوانِ یکی از
#  ۵ تا ماده‌ی یه دستورِ عمومیِ map_recipes.py مصرف می‌شدن (همون‌قدر
#  که یه Sand Crystal ارزون‌قیمت وزن داشت). این ماژول بهشون یه
#  مسیرِ کرفتِ اختصاصی و بالاتر از سقفِ فعلی می‌ده:
#
#    🔨 آهنگریِ عادی (crafting_system.FORGE_RECIPES) سقفش تیرِ ۵ /
#       ریرتیِ legendary‌ه.
#    🏺 کورهٔ مصنوعات فقط با ۱ آیتمِ legendaryِ نقشه‌ای (+ Zen +
#       غبارِ‌اختری) یه تجهیزِ ancient می‌سازه — یه پله بالاترِ چیزی
#       که آهنگریِ معمولی می‌تونه بسازه، و هر مصنوعه اسم/فلیورِ
#       اختصاصیِ خودشو داره.
#
#  خودکفاست — فقط از item_system (ساختِ تجهیز) و crafting_system
#  (astral_dust) می‌خونه، هیچ فایلِ قدیمی رو خراب نمی‌کنه.
# ============================================================
from __future__ import annotations

import item_system as isy
import crafting_system as cfs

# (اسمِ آیتمِ legendaryِ نقشه‌ای) → دستورِ مصنوعه
# هر مصنوعه یه اسلات/اسم/فلیورِ اختصاصی داره که با خودِ متریال هم‌خونیه.
ARTIFACT_RECIPES = {
    "Divine Shard": {
        "slot": "amulet", "result_name": "گردنبندِ تکه‌ی الهی", "emoji": "💎",
        "result_desc": "گردنبندی که هنوز از تکه‌ی افتاده‌ی مصنوعه‌ی الهی می‌درخشه.",
        "zen_cost": 22000, "req_forge_level": 6, "map": "Holy Luminarchy",
    },
    "Nebula Stone": {
        "slot": "relic", "result_name": "کُرهٔ سحابی", "emoji": "🌠",
        "result_desc": "کره‌ای که قلبِ یه سحابیِ فروپاشیده توشه.",
        "zen_cost": 33000, "req_forge_level": 6, "map": "Celestial Spire",
    },
    "Glacial Heart": {
        "slot": "armor", "result_name": "زرهِ قلبِ‌یخی", "emoji": "🧊",
        "result_desc": "زرهی که سرمای قلبِ یه غولِ افسانه‌ای رو حبس کرده.",
        "zen_cost": 26000, "req_forge_level": 6, "map": "Frostheim",
    },
    "Dark Matter": {
        "slot": "weapon", "result_name": "تیغه‌ی مادهٔ‌تاریک", "emoji": "⚫",
        "result_desc": "تیغه‌ای که از قوانینِ فیزیک پیروی نمی‌کنه.",
        "zen_cost": 44000, "req_forge_level": 7, "map": "Voidbreak Wastes",
    },
    "Atlantean Relic": {
        "slot": "relic", "result_name": "مصنوعه‌ی آتلانتیس", "emoji": "🐚",
        "result_desc": "یادگاریِ زنده‌مانده از عمیق‌ترین نقطه‌ی اقیانوس.",
        "zen_cost": 40000, "req_forge_level": 7, "map": "Azure Tides Empire",
    },
    "Storm Heart": {
        "slot": "weapon", "result_name": "نیزه‌ی قلبِ‌طوفان", "emoji": "🌩️",
        "result_desc": "نیزه‌ای که هیچ‌وقت رعدوبرقش نمی‌خوابه.",
        "zen_cost": 30000, "req_forge_level": 6, "map": "Stormward Archipelago",
    },
    "Lost Crown": {
        "slot": "helmet", "result_name": "تاجِ گم‌شده", "emoji": "👑",
        "result_desc": "تاجِ آخرین پادشاهِ آتلانتیس، بازسازی‌شده.",
        "zen_cost": 55000, "req_forge_level": 8, "map": "The Sunken City",
    },
    "World Tree Seed": {
        "slot": "ring", "result_name": "حلقه‌ی دانهٔ‌درختِ‌جهان", "emoji": "🌱",
        "result_desc": "حلقه‌ای که هنوز درونش یه جوونه‌ی زنده‌ست.",
        "zen_cost": 66000, "req_forge_level": 8, "map": "Verdant Vale",
    },
    "Phoenix Ash": {
        "slot": "boots", "result_name": "چکمه‌ی خاکسترِ ققنوس", "emoji": "🦅",
        "result_desc": "چکمه‌ای که با هر قدم انگار دوباره متولد می‌شه.",
        "zen_cost": 35000, "req_forge_level": 7, "map": "Emberhollow",
    },
    "Dragon Heart": {
        "slot": "weapon", "result_name": "شمشیرِ قلبِ‌اژدها", "emoji": "❤️",
        "result_desc": "شمشیری که هنوز ضربانِ قلبِ اژدهای ارشد توشه.",
        "zen_cost": 77000, "req_forge_level": 9, "map": "Dragonnest Peaks",
    },
    "Orion Crystal": {
        "slot": "gloves", "result_name": "دستکشِ بلورِ اوریون", "emoji": "🔮",
        "result_desc": "دستکشی متصل به هوشِ مصنوعیِ رهاشده‌ی اوریون-۷.",
        "zen_cost": 44000, "req_forge_level": 7, "map": "Ruins of Orion-7",
    },
    "Legion Heart": {
        "slot": "armor", "result_name": "زرهِ قلبِ‌لژیون", "emoji": "💔",
        "result_desc": "زرهِ فرماندهِ لژیونِ نگهبانِ دژِ نفرین‌شده.",
        "zen_cost": 62000, "req_forge_level": 8, "map": "Dreadgate Citadel",
    },
    "Masterwork Ingot": {
        "slot": "weapon", "result_name": "تبرِ شمشِ‌استادکاری", "emoji": "🥇",
        "result_desc": "تبری که فقط یه‌بار در نسل‌ها ساخته می‌شه.",
        "zen_cost": 48000, "req_forge_level": 7, "map": "Clockwork Depths",
    },
    "Abyss Heart": {
        "slot": "relic", "result_name": "قلبِ آبیس", "emoji": "🌑",
        "result_desc": "قلبِ خودِ آبیس — نادرترین مصنوعه‌ی این دنیا.",
        "zen_cost": 88000, "req_forge_level": 9, "map": "Abyssal Black Market",
    },
}

ASTRAL_DUST_COST = 4
FORCED_RARITY = "ancient"  # یه پله بالاتر از سقفِ آهنگریِ عادی (legendary)


def has_legendary_material(player: dict, name: str) -> bool:
    return any(it.get("name") == name for it in player.get("inventory", []))


def _pop_named(player: dict, name: str) -> dict | None:
    inv = player.setdefault("inventory", [])
    for i, it in enumerate(inv):
        if it.get("name") == name:
            return inv.pop(i)
    return None


def can_craft_artifact(player: dict, legendary_name: str) -> tuple[bool, str]:
    recipe = ARTIFACT_RECIPES.get(legendary_name)
    if not recipe:
        return False, "❌ این آیتم دستورِ مصنوعه نداره."
    c = cfs.get_crafting(player)
    if c["forge_level"] < recipe["req_forge_level"]:
        return False, f"❌ به سطحِ آهنگریِ {recipe['req_forge_level']} نیاز داری (الان: {c['forge_level']})."
    if not has_legendary_material(player, legendary_name):
        return False, f"❌ {legendary_name} تو کوله‌پشتیت نیست."
    if cfs.material_qty(player, "astral_dust") < ASTRAL_DUST_COST:
        return False, f"❌ به {ASTRAL_DUST_COST}x 🌟 غبارِ‌اختری نیاز داری (Soul Stone یا لوتِ باس بگیرش)."
    if player.get("zen", 0) < recipe["zen_cost"]:
        return False, f"❌ به {recipe['zen_cost']:,} Zen نیاز داری."
    return True, ""


def craft_artifact(uid: int, player: dict, legendary_name: str) -> tuple[bool, str, dict | None]:
    ok, why = can_craft_artifact(player, legendary_name)
    if not ok:
        return False, why, None
    recipe = ARTIFACT_RECIPES[legendary_name]

    _pop_named(player, legendary_name)
    cfs._consume_materials(player, {"astral_dust": ASTRAL_DUST_COST})
    player["zen"] -= recipe["zen_cost"]

    template = {
        "name": recipe["result_name"], "emoji": recipe["emoji"],
        "desc": recipe["result_desc"], "slot": recipe["slot"],
    }
    item = isy.generate_item(template, player.get("level", 1), forced_rarity=FORCED_RARITY,
                              drop_source=f"artifact:{legendary_name}")
    item["artifact_source"] = legendary_name
    player.setdefault("inventory", []).append(item)
    logs = cfs._gain_xp(player, "forge", 200)

    msg = (f"🏺 با **{legendary_name}** ساختی:\n"
           f"{item['emoji']} **{item['name']}** ({isy.RARITY_DATA[item['rarity']]['label']}) "
           f"⭐ Item Score: {item['item_score']}")
    if logs:
        msg += "\n" + "\n".join(logs)
    return True, msg, item


def available_recipes_text(player: dict) -> str:
    """فهرستِ همه‌ی ۱۴ دستور + وضعیتِ فعلیِ بازیکن نسبت‌بهشون."""
    lines = []
    for name, recipe in ARTIFACT_RECIPES.items():
        have_mat = "✅" if has_legendary_material(player, name) else "❌"
        c = cfs.get_crafting(player)
        lvl_ok = "✅" if c["forge_level"] >= recipe["req_forge_level"] else "❌"
        lines.append(
            f"{recipe['emoji']} **{recipe['result_name']}** (از {name})\n"
            f"   {have_mat} داری | {lvl_ok} سطحِ آهنگریِ {recipe['req_forge_level']} | "
            f"💰 {recipe['zen_cost']:,} Zen + {ASTRAL_DUST_COST}x🌟"
        )
    return "\n".join(lines)
