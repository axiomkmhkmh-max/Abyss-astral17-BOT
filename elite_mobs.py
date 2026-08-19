# ============================================================
#  ASTRAL ABYSS — Elite Mobs 👑 (عمیق‌سازیِ دشمن‌ها + اتصال به لوت)
# ------------------------------------------------------------
#  به‌جای نوشتنِ صدها دشمنِ دستیِ جدید، هر دشمنِ وحشیِ معمولی شانس
#  داره یه «نخبه» (Elite) بشه: یک یا دو Affix تصادفی روش سوار می‌شه
#  که هم استت‌هاش (HP/دمیج/XP/Zen) و هم پروفایلِ دفاعیِ واقعیِ نبرد
#  رو عوض می‌کنه — دقیقاً همون فیلدهایی که combat_engine.get_enemy_defense
#  صراحتاً از روی enemy می‌خونه (armor/evasion/accuracy/guard_chance/
#  elem_resist/crit_resist). یعنی بدونِ دست‌زدن به combat.py یا
#  combat_engine.py، نبرد واقعاً فرق می‌کنه، نه فقط تو متن.
#
#  اتصالِ لوت ↔ نبرد: شانسِ ظاهرشدنِ نخبه به دو چیزِ واقعی وصله —
#    ۱) خطرِ منطقه (zone: safe/contested/danger از economy.MAPS_DATA)
#    ۲) استریکِ لوتِ خودِ بازیکن (player["loot_streak"]) — هرچی
#       استریکت بهتر باشه، شانسِ برخورد به نخبه هم بالاتر می‌ره.
#  و برعکس: کشتنِ نخبه یه بونوسِ اضافه به همون استریک می‌ده — یعنی
#  این دو سیستم (map_activity هم همین‌طور) یه حلقه‌ی به‌هم‌وصل می‌سازن،
#  نه سه تا مکانیکِ جدا.
# ============================================================
import random

ELITE_BASE_CHANCE = {"safe": 0.05, "contested": 0.09, "danger": 0.14}
ELITE_STREAK_BONUS_PER_STACK = 0.01     # هر واحدِ loot_streak
ELITE_STREAK_BONUS_CAP = 0.10
ELITE_CHANCE_CAP = 0.30
DOUBLE_AFFIX_CHANCE = 0.20              # وقتی نخبه شد، ۲۰٪ شانسِ یه Affix دومِ اضافه

ELITE_HP_MULT  = 1.35
ELITE_XP_MULT  = 1.7
ELITE_ZEN_MULT = 1.7
ELITE_STREAK_BONUS = 1                  # کشتنِ نخبه، این‌قدر اضافه به loot_streak می‌ده

AFFIXES = {
    "blazing": {
        "name": "آتشین", "emoji": "🔥",
        "dmg_mult": 1.25, "elem_resist_add": 0.08,
        "desc": "دمیجِ بیشتر و کمی مقاومتِ عنصری.",
    },
    "armored": {
        "name": "زره‌پوش", "emoji": "🛡️",
        "hp_mult": 1.25, "dmg_mult": 0.9, "armor_add": 20,
        "desc": "خیلی سرسخت‌تره، ولی دستش کندتره.",
    },
    "swift": {
        "name": "سریع", "emoji": "⚡",
        "evasion_add": 0.14, "accuracy_add": 0.05,
        "desc": "به‌سختی بهش می‌خوره؛ سریع‌تر از حدِ معموله.",
    },
    "warded": {
        "name": "محافظت‌شده", "emoji": "🔮",
        "hp_mult": 1.15, "elem_resist_add": 0.16,
        "desc": "یه سپرِ عنصریِ قوی دورشه.",
    },
    "feral": {
        "name": "وحشی", "emoji": "💀",
        "dmg_mult": 1.3, "hp_mult": 0.9,
        "desc": "شیشه‌ایه، ولی دمیجش وحشتناکه — سریع تمومش کن.",
    },
    "haunting": {
        "name": "روح‌سرگردان", "emoji": "🌀",
        "guard_chance_add": 0.16, "crit_resist_add": 0.10, "hp_mult": 1.1,
        "desc": "مدام سپر می‌گیره؛ حمله‌ی سنگین لازمه بشکنیش.",
    },
}

_TIER_ORDER = ["common", "rare", "epic", "legendary"]


def elite_chance(zone: str, loot_streak: int) -> float:
    base = ELITE_BASE_CHANCE.get(zone, ELITE_BASE_CHANCE["contested"])
    streak_bonus = min(ELITE_STREAK_BONUS_CAP, loot_streak * ELITE_STREAK_BONUS_PER_STACK)
    return min(ELITE_CHANCE_CAP, base + streak_bonus)


def _zone_of(map_name: str) -> str:
    try:
        from economy import MAPS_DATA
        return MAPS_DATA.get(map_name, {}).get("zone", "contested")
    except Exception:
        return "contested"


def maybe_elevate(enemy: dict, player: dict, map_name: str) -> dict:
    """
    اگه شانس بیاد، دشمنِ وحشیِ معمولی رو به یه Elite تبدیل می‌کنه و یه
    dict جدید برمی‌گردونه؛ اگه نه، دقیقاً همون enemy ورودی رو (بدونِ
    تغییر) پس می‌ده. باس و نمسیس هیچ‌وقت elevate نمی‌شن — این‌ها از
    قبل خودشون خاصن.
    """
    if enemy.get("is_boss") or enemy.get("is_nemesis") or enemy.get("is_apex"):
        return enemy

    zone = _zone_of(map_name)
    streak = player.get("loot_streak", 0)
    if random.random() > elite_chance(zone, streak):
        return enemy

    e = dict(enemy)
    picks = random.sample(list(AFFIXES.keys()), 2 if random.random() < DOUBLE_AFFIX_CHANCE else 1)

    e["hp"] = int(e.get("hp", 100) * ELITE_HP_MULT)
    e["max_hp"] = e["hp"]
    e["xp"] = int(e.get("xp", 20) * ELITE_XP_MULT)
    e["zen"] = int(e.get("zen", 15) * ELITE_ZEN_MULT)
    e["drop_chance"] = 1.0  # نخبه همیشه لوت می‌ده

    cur = e.get("tier", "common")
    if cur not in _TIER_ORDER or _TIER_ORDER.index(cur) < 1:
        e["tier"] = "rare"  # حداقل پروفایلِ دفاعیِ rare می‌گیره

    prefix_bits = []
    for key in picks:
        aff = AFFIXES[key]
        prefix_bits.append(f"{aff['emoji']}{aff['name']}")
        e["dmg"] = int(e.get("dmg", 10) * aff.get("dmg_mult", 1.0))
        e["hp"] = int(e["hp"] * aff.get("hp_mult", 1.0))
        e["max_hp"] = e["hp"]
        if "armor_add" in aff:
            e["armor"] = e.get("armor", 0) + aff["armor_add"]
        if "evasion_add" in aff:
            e["evasion"] = e.get("evasion", 0) + aff["evasion_add"]
        if "accuracy_add" in aff:
            e["accuracy"] = e.get("accuracy", 0) + aff["accuracy_add"]
        if "elem_resist_add" in aff:
            e["elem_resist"] = e.get("elem_resist", 0) + aff["elem_resist_add"]
        if "guard_chance_add" in aff:
            e["guard_chance"] = e.get("guard_chance", 0) + aff["guard_chance_add"]
        if "crit_resist_add" in aff:
            e["crit_resist"] = e.get("crit_resist", 0) + aff["crit_resist_add"]

    e["name"] = f"👑{''.join(prefix_bits)} {e.get('name', 'دشمن')}"
    e["is_elite"] = True
    e["_elite_affixes"] = picks
    return e


def elite_intro_line(enemy: dict) -> str:
    """یه خطِ معرفی برای بالای صفحه‌ی نبرد، فقط وقتی enemy نخبه‌ست."""
    if not enemy.get("is_elite"):
        return ""
    descs = " | ".join(AFFIXES[k]["desc"] for k in enemy.get("_elite_affixes", []) if k in AFFIXES)
    return f"👑 **یه نسخه‌ی نخبه ظاهر شد!**\n_{descs}_\n\n"


def apply_elite_kill_bonus(player: dict, enemy: dict):
    """
    بعدِ کشتنِ موفقِ یه نخبه صدا زده می‌شه — یه بونوسِ کوچیکِ اضافه به
    loot_streak می‌ده (جدا از افزایشِ عادیِ streak که loot_engine خودش
    انجام می‌ده). حلقه‌ی لوت↔نبرد رو می‌بنده: کیلِ نخبه یعنی استریکِ
    بهتر یعنی شانسِ نخبه‌ی بعدی هم بالاتر.
    """
    if not enemy.get("is_elite"):
        return
    player["loot_streak"] = player.get("loot_streak", 0) + ELITE_STREAK_BONUS
