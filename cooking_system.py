# ============================================================
#  ASTRAL ABYSS RPG — Home Cooking 🍲  (v1)
#  زیرسیستمِ سومِ فیچرِ خونه/مزرعه/زمین/شهر (بعد از land_system.py و
#  farm_system.py). مستقیم از موادِ خامِ مزرعه (محصولات + تولیداتِ
#  دام) استفاده می‌کنه.
#
#  مدل: با موادِ اینونتوریت یه غذا می‌پزی (cook) → غذا به‌صورتِ آیتمِ
#  استک‌شونده (type: food) میره تو کوله‌پشتی → هروقت خواستی می‌خوریش
#  (eat) → یه بافِ موقتِ ترکیبی (مثلِ equipment ولی جدا و کوتاه‌مدت)
#  فعال می‌شه. بافِ هر استت جداگونه نگه‌داری می‌شه، پس خوردنِ غذاهای
#  مختلف با استت‌های مختلف روی هم استک می‌شن؛ خوردنِ دوباره‌ی همون
#  غذا فقط تایمرش رو تازه می‌کنه (نه جمع‌زدنِ مقدار — ضدِ اسپم).
# ============================================================
import time
from database import get_player, save_player

RECIPES = {
    "bread": {
        "name": "🍞 نانِ گندمی",
        "ingredients": {"wheat": 4},
        "zen_cost": 20,
        "buff_stat": "dmg_pct", "buff_value": 0.05, "duration": 3600,
        "desc": "🗡 ۵٪ دمیجِ بیشتر — ۱ ساعت",
    },
    "soup": {
        "name": "🥕 سوپِ هویج",
        "ingredients": {"carrot": 3, "egg": 1},
        "zen_cost": 40,
        "buff_stat": "crit_pct", "buff_value": 0.04, "duration": 3600,
        "desc": "🎯 ۴٪ شانسِ کریتِ بیشتر — ۱ ساعت",
    },
    "pasta": {
        "name": "🍅 پاستایِ گوجه",
        "ingredients": {"tomato": 3, "milk": 1},
        "zen_cost": 60,
        "buff_stat": "defense_pct", "buff_value": 0.05, "duration": 3600,
        "desc": "🛡 ۵٪ دفاعِ بیشتر — ۱ ساعت",
    },
    "pie": {
        "name": "🎃 پایِ کدو",
        "ingredients": {"pumpkin": 2, "egg": 2, "milk": 1},
        "zen_cost": 100,
        "buff_stat": "max_hp_flat", "buff_value": 40, "duration": 5400,
        "desc": "❤️ ۴۰ HPِ بیشتر — ۹۰ دقیقه",
    },
    "omelet": {
        "name": "🥚 املتِ ویژه",
        "ingredients": {"egg": 4},
        "zen_cost": 30,
        "buff_stat": "gold_find_pct", "buff_value": 0.08, "duration": 3600,
        "desc": "💰 ۸٪ شانسِ بیشترِ طلا — ۱ ساعت",
    },
    "tea": {
        "name": "🌙 دمنوشِ گلِ ماه",
        "ingredients": {"moonflower": 1, "milk": 1},
        "zen_cost": 80,
        "buff_stat": "xp_pct", "buff_value": 0.10, "duration": 7200,
        "desc": "📈 ۱۰٪ تجربه‌ی بیشتر — ۲ ساعت (کمیاب)",
    },
}

FOOD_STAT_LABEL = {
    "dmg_pct": "🗡 دمیج", "crit_pct": "🎯 کریت", "defense_pct": "🛡 دفاع",
    "max_hp_flat": "❤️ HP", "gold_find_pct": "💰 طلا", "xp_pct": "📈 تجربه",
}


# ─── کمکی‌های اینونتوری ────────────────────────────────────────────
def _material_qty(player: dict, mat_id: str) -> int:
    for it in player.get("inventory", []):
        if it.get("type") == "material" and it.get("material_id") == mat_id:
            return it.get("qty", 0)
    return 0


def _consume_materials(player: dict, ingredients: dict) -> None:
    inv = player.setdefault("inventory", [])
    for mat_id, need in ingredients.items():
        for it in inv:
            if it.get("type") == "material" and it.get("material_id") == mat_id:
                it["qty"] = it.get("qty", 0) - need
                break
        inv[:] = [it for it in inv if not (it.get("type") == "material" and it.get("qty", 0) <= 0)]


def _add_food(player: dict, recipe_key: str, qty: int = 1) -> None:
    recipe = RECIPES[recipe_key]
    inv = player.setdefault("inventory", [])
    for it in inv:
        if it.get("type") == "food" and it.get("food_id") == recipe_key:
            it["qty"] = it.get("qty", 1) + qty
            return
    inv.append({
        "id": f"food_{recipe_key}_{int(time.time()*1000)}",
        "food_id": recipe_key, "name": recipe["name"], "emoji": recipe["name"].split()[0],
        "type": "food", "qty": qty,
    })


def missing_ingredients_text(player: dict, recipe_key: str) -> str:
    recipe = RECIPES[recipe_key]
    parts = []
    for mat_id, need in recipe["ingredients"].items():
        have = _material_qty(player, mat_id)
        mark = "✅" if have >= need else "❌"
        parts.append(f"{mark} {mat_id}: {have}/{need}")
    return " | ".join(parts)


def can_cook(player: dict, recipe_key: str) -> bool:
    recipe = RECIPES.get(recipe_key)
    if not recipe:
        return False
    if player.get("zen", 0) < recipe["zen_cost"]:
        return False
    return all(_material_qty(player, mat_id) >= need for mat_id, need in recipe["ingredients"].items())


# ─── پختن ──────────────────────────────────────────────────────────
def cook_recipe(uid: int, player: dict, recipe_key: str) -> tuple[bool, str]:
    recipe = RECIPES.get(recipe_key)
    if not recipe:
        return False, "❌ دستورِ پختِ نامعتبر."
    for mat_id, need in recipe["ingredients"].items():
        if _material_qty(player, mat_id) < need:
            return False, f"❌ موادِ کافی نداری:\n{missing_ingredients_text(player, recipe_key)}"
    if player.get("zen", 0) < recipe["zen_cost"]:
        return False, f"❌ برای پختِ {recipe['name']} به {recipe['zen_cost']:,} Zen (هزینه‌ی ادویه/سوخت) نیاز داری."
    _consume_materials(player, recipe["ingredients"])
    player["zen"] -= recipe["zen_cost"]
    _add_food(player, recipe_key, 1)
    return True, f"🍳 {recipe['name']} پختی! تو کوله‌پشتیته — هروقت خواستی بخورش تا باف بگیری."


# ─── خوردن / بافِ موقت ─────────────────────────────────────────────
def clean_expired_buffs(player: dict) -> bool:
    """بافِ منقضی‌شده رو پاک می‌کنه. True برمی‌گردونه اگه چیزی تغییر کرده."""
    buffs = player.get("active_food_buffs", {})
    now = time.time()
    changed = False
    for stat in list(buffs.keys()):
        if buffs[stat].get("expires_at", 0) <= now:
            del buffs[stat]
            changed = True
    return changed


def eat_food(uid: int, player: dict, food_key: str) -> tuple[bool, str]:
    recipe = RECIPES.get(food_key)
    if not recipe:
        return False, "❌ غذایِ نامعتبر."
    inv = player.setdefault("inventory", [])
    item = next((it for it in inv if it.get("type") == "food" and it.get("food_id") == food_key), None)
    if not item or item.get("qty", 0) <= 0:
        return False, f"❌ {recipe['name']} تو کوله‌پشتیت نداری — اول بپزش."
    item["qty"] -= 1
    if item["qty"] <= 0:
        inv.remove(item)
    clean_expired_buffs(player)
    buffs = player.setdefault("active_food_buffs", {})
    stat = recipe["buff_stat"]
    was_active = stat in buffs
    buffs[stat] = {"value": recipe["buff_value"], "expires_at": time.time() + recipe["duration"], "name": recipe["name"]}
    label = FOOD_STAT_LABEL.get(stat, stat)
    verb = "تازه شد" if was_active else "فعال شد"
    return True, f"😋 {recipe['name']} رو خوردی — بافِ {label} {verb} ({recipe['desc'].split('—')[-1].strip()})."


def get_food_bonus_stats(player: dict) -> dict:
    """بافِ فعالِ غذا رو (بعدِ پاک‌کردنِ منقضی‌شده‌ها) به کلیدهایِ همون
    combat_bonus_stats برمی‌گردونه، تا item_system بتونه روش جمع بزنه."""
    clean_expired_buffs(player)
    out: dict = {}
    for stat, b in player.get("active_food_buffs", {}).items():
        out[stat] = out.get(stat, 0) + b.get("value", 0)
    return out


def active_buffs_text(player: dict) -> str:
    clean_expired_buffs(player)
    buffs = player.get("active_food_buffs", {})
    if not buffs:
        return "— هیچ بافِ فعالی نداری —"
    now = time.time()
    lines = []
    for stat, b in buffs.items():
        remain = int(b["expires_at"] - now)
        m, s = divmod(max(0, remain), 60)
        label = FOOD_STAT_LABEL.get(stat, stat)
        val = b["value"]
        val_txt = f"{val:+.0%}" if isinstance(val, float) else f"{val:+d}"
        lines.append(f"  {label} {val_txt} — {b['name']} ({m}m مونده)")
    return "\n".join(lines)


def kitchen_summary_text(uid: int, player: dict) -> str:
    lines = ["🔥 **بافِ فعال:**", active_buffs_text(player), "", "🥘 **موادِ خام:**"]
    any_mat = False
    seen = set()
    for recipe in RECIPES.values():
        for mat_id in recipe["ingredients"]:
            if mat_id in seen:
                continue
            seen.add(mat_id)
    for mat_id in seen:
        have = _material_qty(player, mat_id)
        if have > 0:
            any_mat = True
        lines.append(f"  {mat_id}: {have}")
    if not any_mat:
        lines.append("  — موادی نداری؛ برو 🌾 مزرعه —")
    lines.append("")
    lines.append("🍞 **غذاهای آماده:**")
    foods = [it for it in player.get("inventory", []) if it.get("type") == "food"]
    if foods:
        for f in foods:
            lines.append(f"  {f['name']}: {f['qty']}×")
    else:
        lines.append("  — غذایی نپختی —")
    return "\n".join(lines)
