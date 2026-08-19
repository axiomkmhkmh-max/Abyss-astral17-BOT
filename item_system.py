# ============================================================
#  ASTRAL ABYSS — Item System v2
# ------------------------------------------------------------
#  این فایل جدیدِ جداست و هیچ importِ قبلی (economy.py / combat.py) رو
#  خراب نمی‌کنه. آیتم‌های قدیمی (فقط name/emoji/rarity/sell/buy) هنوز
#  همون‌جوری کار می‌کنن — این ماژول یه لایه‌ی «آپگرید» رو دیش می‌ذاره:
#
#     item = migrate_legacy_item(old_item)      # آیتم قدیمی رو کامل می‌کنه
#     item = generate_item(template, level)     # آیتم کاملاً جدید می‌سازه
#
#  همه‌جای دیگه‌ی کد (bot.py inventory, economy.py roll_loot, combat.py
#  get_drop) بازم می‌تونن به item["name"]/item["sell"]/item["emoji"]
#  دسترسی داشته باشن — این کلیدها همیشه حفظ می‌شن.
# ============================================================
import random
import time
import uuid

# ─── Rarity Tiers (کامل — ۱۱ سطح طبق مشخصات) ──────────────────
RARITY_ORDER = [
    "common", "uncommon", "rare", "epic", "mythic",
    "legendary", "ancient", "astral", "void", "celestial", "transcendent",
]

RARITY_DATA = {
    "common":      {"emoji": "⚪", "label": "عادی",       "score_mult": 1.0,  "max_affixes": 0, "sell_mult": 1.0,  "weight": 1000},
    "uncommon":    {"emoji": "🟢", "label": "غیرعادی",     "score_mult": 1.6,  "max_affixes": 1, "sell_mult": 1.6,  "weight": 500},
    "rare":        {"emoji": "🔵", "label": "نادر",       "score_mult": 2.6,  "max_affixes": 2, "sell_mult": 2.6,  "weight": 220},
    "epic":        {"emoji": "🟣", "label": "حماسی",      "score_mult": 4.2,  "max_affixes": 3, "sell_mult": 4.2,  "weight": 90},
    "mythic":      {"emoji": "🟠", "label": "میتیک",      "score_mult": 6.5,  "max_affixes": 4, "sell_mult": 6.5,  "weight": 34},
    "legendary":   {"emoji": "🟡", "label": "لژندری",     "score_mult": 10.0, "max_affixes": 5, "sell_mult": 10.0, "weight": 12},
    "ancient":     {"emoji": "🟤", "label": "باستانی",    "score_mult": 15.0, "max_affixes": 6, "sell_mult": 15.0, "weight": 5},
    "astral":      {"emoji": "🌌", "label": "اختری",      "score_mult": 22.0, "max_affixes": 6, "sell_mult": 22.0, "weight": 2},
    "void":        {"emoji": "🌑", "label": "خلأ",        "score_mult": 32.0, "max_affixes": 7, "sell_mult": 32.0, "weight": 0.8},
    "celestial":   {"emoji": "✨", "label": "آسمانی",     "score_mult": 46.0, "max_affixes": 7, "sell_mult": 46.0, "weight": 0.25},
    "transcendent":{"emoji": "👑", "label": "متعالی",     "score_mult": 70.0, "max_affixes": 8, "sell_mult": 70.0, "weight": 0.05},
}

def rarity_index(rarity: str) -> int:
    return RARITY_ORDER.index(rarity) if rarity in RARITY_ORDER else 0

def roll_rarity(luck_bonus: float = 0.0) -> str:
    """luck_bonus: 0.0-1.0 — هرچی بیشتر باشه شانس ندرت‌های بالاتر بیشتر می‌شه
    (loot streak / pity / اقبال درخت مهارت باید اینو بدن)."""
    weights = []
    for r in RARITY_ORDER:
        w = RARITY_DATA[r]["weight"]
        if r not in ("common", "uncommon"):
            w *= (1 + luck_bonus * 4)
        weights.append(w)
    return random.choices(RARITY_ORDER, weights=weights, k=1)[0]

# ─── Variants (نسخه‌های ویژه‌ی همون آیتم) ─────────────────────
VARIANTS = {
    "normal":    {"label": "",              "score_mult": 1.0,  "sell_mult": 1.0,  "chance": 0.93},
    "shiny":     {"label": "✨ درخشان",       "score_mult": 1.15, "sell_mult": 1.5,  "chance": 0.04},
    "ancient":   {"label": "🏛 باستانی",      "score_mult": 1.3,  "sell_mult": 2.0,  "chance": 0.02},
    "corrupted": {"label": "☠️ فاسدشده",     "score_mult": 1.4,  "sell_mult": 2.5,  "chance": 0.008},
    "perfect":   {"label": "💯 کامل (Perfect Roll)", "score_mult": 1.6, "sell_mult": 3.0, "chance": 0.002},
}

def roll_variant() -> str:
    names = list(VARIANTS.keys())
    weights = [VARIANTS[n]["chance"] for n in names]
    return random.choices(names, weights=weights, k=1)[0]

# ─── Affix Pools ───────────────────────────────────────────────
# هر افیکس: (id, نمایش، stat، (min,max) به‌ازای هر واحد rarity_index)
PREFIXES = [
    ("of_power",     "قدرتمند",    "dmg_pct",        (0.02, 0.05)),
    ("of_fury",      "خشمگین",     "crit_chance",    (0.01, 0.03)),
    ("of_ruin",      "ویرانگر",    "crit_dmg",       (0.05, 0.12)),
    ("of_the_leech", "خون‌آشام",   "lifesteal",       (0.01, 0.025)),
    ("of_haste",     "شتاب‌زده",   "cooldown_reduction", (0.01, 0.03)),
    ("of_the_bear",  "خرسی",       "max_hp",          (10, 40)),
    ("of_thorns",    "خاردار",     "reflect_dmg",     (0.02, 0.06)),
    ("of_warding",   "محافظ",      "armor",           (2, 8)),
]

SUFFIXES = [
    ("of_the_ember",   "شعله",       "element_dmg_fire",  (0.03, 0.08)),
    ("of_the_glacier", "یخبندان",    "element_dmg_ice",   (0.03, 0.08)),
    ("of_the_storm",   "طوفان",      "element_dmg_lightning", (0.03, 0.08)),
    ("of_the_void",    "خلأ",        "element_dmg_void",  (0.03, 0.08)),
    ("of_the_saint",   "قداست",      "element_dmg_holy",  (0.03, 0.08)),
    ("of_fortune",     "اقبال",      "gold_find_pct",     (0.02, 0.06)),
    ("of_wisdom",      "خرد",        "xp_pct",            (0.02, 0.06)),
    ("of_precision",   "دقت",        "accuracy",          (0.02, 0.05)),
]

def _roll_affix(pool: list, rarity_idx: int) -> dict:
    aid, label, stat, (lo, hi) = random.choice(pool)
    scale = 1 + rarity_idx * 0.35
    value = round(random.uniform(lo, hi) * scale, 4)
    return {"id": aid, "label": label, "stat": stat, "value": value}

def generate_affixes(rarity: str) -> dict:
    """برمی‌گردونه {"prefix": [...], "suffix": [...]} — تعداد بر اساس rarity."""
    ridx = rarity_index(rarity)
    max_affixes = RARITY_DATA[rarity]["max_affixes"]
    if max_affixes == 0:
        return {"prefix": [], "suffix": []}
    n_prefix = min(len(PREFIXES), (max_affixes + 1) // 2)
    n_suffix = min(len(SUFFIXES), max_affixes // 2)
    prefixes = [_roll_affix(PREFIXES, ridx) for _ in range(random.randint(0, n_prefix))]
    suffixes = [_roll_affix(SUFFIXES, ridx) for _ in range(random.randint(0, n_suffix))]
    return {"prefix": prefixes, "suffix": suffixes}

def is_perfect_roll(item: dict) -> bool:
    """اگه همه‌ی افیکس‌های آیتم نزدیک سقف مقدار ممکن‌شون رول شده باشن."""
    all_affixes = item.get("affixes", {}).get("prefix", []) + item.get("affixes", {}).get("suffix", [])
    if not all_affixes:
        return False
    return item.get("variant") == "perfect"

# ─── Equip Slots ────────────────────────────────────────────────
EQUIP_SLOTS = ["weapon", "helmet", "armor", "gloves", "boots", "ring", "amulet", "relic"]

# ─── Equipment Templates (اسم/ایموجی پایه به‌ازای هر اسلات) ─────
# اینا فقط پوسته‌ی ظاهریِ آیتم‌ان — رریتی/افیکس/دوام همه با generate_item
# رول می‌شن. برای تنوع بیشتر هر اسلات چندتا اسم داره.
EQUIPMENT_TEMPLATES = {
    "weapon":  [
        {"name": "شمشیر شکافنده", "emoji": "⚔️", "desc": "شمشیری سنگین که با هر ضربه شکاف عمیقی رو زره حریف می‌ندازه."},
        {"name": "تیغه‌ی سایه",   "emoji": "🗡️", "desc": "خنجری تیز و سبک، ساخته‌شده برای ضربه‌های سریع و بی‌صدا."},
        {"name": "گرزِ آبیس",     "emoji": "🔨", "desc": "گرزی سنگین آغشته به انرژیِ آبیس — ضربه‌هاش کوبنده‌ست."},
    ],
    "helmet":  [
        {"name": "کلاهخودِ جنگی", "emoji": "⛑️", "desc": "کلاهخودِ استاندارد جنگجویان — محافظتی قابل‌اعتماد در برابر ضربات."},
        {"name": "تاجِ تاریکی",   "emoji": "👑", "desc": "تاجی نفرین‌شده که ذهنِ صاحبش رو با قدرتِ تاریکی تقویت می‌کنه."},
    ],
    "armor":   [
        {"name": "زرهِ پلیت",       "emoji": "🛡️", "desc": "زرهِ فلزیِ سنگین — دفاعِ بالا در ازای کمی سنگینی."},
        {"name": "ردایِ اسرارآمیز", "emoji": "🥋", "desc": "ردایی سبک بافته‌شده با نخ‌های جادویی، دفاع رو با چابکی ترکیب می‌کنه."},
    ],
    "gloves":  [{"name": "دستکشِ چنگالی", "emoji": "🧤", "desc": "دستکشی با چنگال‌های فلزی که دقتِ ضربه رو بالا می‌بره."}],
    "boots":   [{"name": "چکمه‌ی سایه‌رو", "emoji": "🥾", "desc": "چکمه‌ای سبک که قدم‌ها رو تقریباً بی‌صدا می‌کنه."}],
    "ring":    [{"name": "حلقه‌ی نفرین", "emoji": "💍", "desc": "حلقه‌ای با انرژیِ تاریک که قدرتِ حمله رو تقویت می‌کنه."}],
    "amulet":  [{"name": "گردنبندِ ارواح", "emoji": "📿", "desc": "گردنبندی که زمزمه‌ی ارواحِ گذشته رو تو خودش حبس کرده."}],
    "relic":   [{"name": "مصنوعه‌ی گمشده", "emoji": "🔮", "desc": "مصنوعه‌ای باستانی با قدرتی ناشناخته و کمیاب."}],
}

def roll_equipment_template(slot: str = None) -> dict:
    """یه اسم/ایموجی/اسلات تصادفی برمی‌گردونه (بدون رریتی/افیکس)."""
    slot = slot if slot in EQUIP_SLOTS else random.choice(EQUIP_SLOTS)
    tpl = random.choice(EQUIPMENT_TEMPLATES[slot])
    return {"name": tpl["name"], "emoji": tpl["emoji"], "slot": slot}

def generate_random_equipment(player_level: int, slot: str = None, forced_rarity: str = None,
                               drop_source: str = "loot", luck_bonus: float = 0.0) -> dict:
    """یه آیتم قابل‌اکیپ کاملاً رندوم (اسلات تصادفی یا مشخص) می‌سازه.
    این تابعیه که مسیرِ دراپِ واقعی بازی (loot_engine/mob_combat/boss_engine)
    باید صداش بزنه تا آیتم‌ها واقعاً قابل‌اکیپ باشن، نه فقط متریال قابل‌فروش."""
    template = roll_equipment_template(slot)
    return generate_item(template, player_level, forced_rarity=forced_rarity,
                          drop_source=drop_source, luck_bonus=luck_bonus)

# ─── Core Generation ────────────────────────────────────────────
def new_item_id() -> str:
    return uuid.uuid4().hex[:12]

def calculate_item_score(item: dict) -> int:
    """Item Score — نمایانگر واقعی «قدرت» آیتم، برای ترکیب توی Combat Power."""
    rarity = item.get("rarity", "common")
    rdata = RARITY_DATA.get(rarity, RARITY_DATA["common"])
    base = 10 * rdata["score_mult"]

    lvl_req = item.get("level_req", 1)
    base += lvl_req * 0.8

    upgrade = item.get("upgrade_level", 0)
    base *= (1 + upgrade * 0.08)

    n_affix = len(item.get("affixes", {}).get("prefix", [])) + len(item.get("affixes", {}).get("suffix", []))
    base *= (1 + n_affix * 0.12)

    sockets = item.get("sockets", [])
    filled_sockets = sum(1 for s in sockets if s.get("gem"))
    base *= (1 + filled_sockets * 0.06)

    variant = item.get("variant", "normal")
    base *= VARIANTS.get(variant, VARIANTS["normal"])["score_mult"]

    durability_ratio = 1.0
    if item.get("max_durability", 0) > 0:
        durability_ratio = max(0.4, item.get("durability", item["max_durability"]) / item["max_durability"])
    base *= durability_ratio

    return int(base)

def get_repair_cost(item: dict) -> int:
    """هزینه‌ی تعمیر بر اساس ندرت + میزان خرابی."""
    if item.get("max_durability", 0) <= 0:
        return 0
    missing = item["max_durability"] - item.get("durability", item["max_durability"])
    if missing <= 0:
        return 0
    rarity = item.get("rarity", "common")
    per_point = 8 * RARITY_DATA.get(rarity, RARITY_DATA["common"])["score_mult"]
    return int(missing * per_point)

def degrade_durability(item: dict, amount: int = 1) -> dict:
    if item.get("max_durability", 0) <= 0:
        return item
    item["durability"] = max(0, item.get("durability", item["max_durability"]) - amount)
    return item

def make_sockets(rarity: str) -> list:
    """آیتم‌های نادرتر سوکت بیشتری دارن (خالی، بعداً با جم پر می‌شن)."""
    ridx = rarity_index(rarity)
    n = min(4, ridx // 2)
    return [{"gem": None} for _ in range(n)]

def generate_item(template: dict, player_level: int, forced_rarity: str = None,
                   drop_source: str = "unknown", luck_bonus: float = 0.0) -> dict:
    """
    template: دیکشنری پایه (حداقل name/emoji — می‌تونه از MAP_LOOT یا ENEMY_DROPS بیاد).
    خروجی: آیتم کامل با همه‌ی فیلدهای جدید + کلیدهای قدیمی (name/emoji/sell/buy/rarity)
    که هیچ‌جای کد فعلی رو خراب نمی‌کنه.
    """
    rarity = forced_rarity or template.get("rarity") or roll_rarity(luck_bonus)
    if rarity not in RARITY_DATA:
        rarity = "common"

    variant = roll_variant()
    affixes = generate_affixes(rarity)
    sockets = make_sockets(rarity)

    base_sell = template.get("sell", 30)
    base_buy = template.get("buy", base_sell * 2)
    rdata = RARITY_DATA[rarity]
    vdata = VARIANTS[variant]

    max_durability = 100 + rarity_index(rarity) * 20
    upgrade_level = 0

    item = {
        # ── فیلدهای قدیمی (سازگاری) ──
        "name": template.get("name", "Unknown Item"),
        "emoji": template.get("emoji", "📦"),
        "desc": template.get("desc", ""),
        "rarity": rarity,
        "sell": int(base_sell * rdata["sell_mult"] * vdata["sell_mult"]),
        "buy": int(base_buy * rdata["sell_mult"] * vdata["sell_mult"]),

        # ── فیلدهای جدید ──
        "item_id": (iid := new_item_id()),
        # "id" هم برای سازگاری با هندلرهای قدیمی (shop/auction/guild/house)
        # که هنوز با کلیدِ "id" کار می‌کنن نگه داشته می‌شه — هر دو یکی‌ان.
        "id": iid,
        "level_req": max(1, player_level - random.randint(0, 5)),
        "tier": rarity,
        "durability": max_durability,
        "max_durability": max_durability,
        "upgrade_level": upgrade_level,
        "sockets": sockets,
        "affixes": affixes,
        "variant": variant,
        "variant_label": vdata["label"],
        "element": template.get("element"),
        "set_id": template.get("set_id"),
        "slot": template.get("slot", "relic"),
        "market_value": int(base_sell * rdata["sell_mult"]),
        "craft_value": int(base_sell * rdata["sell_mult"] * 0.6),
        "weight": round(1 + rarity_index(rarity) * 0.5, 1),
        "drop_source": drop_source,
        "created_at": time.time(),
    }
    item["item_score"] = calculate_item_score(item)
    return item

def migrate_legacy_item(item: dict) -> dict:
    """آیتم‌های قدیمی (تو اینونتوری بازیکن‌های فعلی) رو با پیش‌فرض‌های امن کامل می‌کنه.
    idempotent است — روی آیتم جدید هم صدا بزنی مشکلی پیش نمیاد."""
    if "item_id" in item:
        item.setdefault("id", item["item_id"])  # سازگاری با هندلرهای قدیمی
        return item  # از قبل schema جدید داره

    rarity = item.get("rarity", "common")
    if rarity not in RARITY_DATA:
        rarity = "common"
    max_durability = 100 + rarity_index(rarity) * 20

    item.setdefault("item_id", new_item_id())
    item.setdefault("id", item["item_id"])
    item.setdefault("level_req", 1)
    item.setdefault("tier", rarity)
    item.setdefault("durability", max_durability)
    item.setdefault("max_durability", max_durability)
    item.setdefault("upgrade_level", 0)
    item.setdefault("sockets", [])
    item.setdefault("affixes", {"prefix": [], "suffix": []})
    item.setdefault("variant", "normal")
    item.setdefault("variant_label", "")
    item.setdefault("element", None)
    item.setdefault("set_id", None)
    # ─── باگ‌فیکس مهم ───────────────────────────────────────────
    # قبلاً اینجا item.setdefault("slot", "relic") بود — یعنی هر
    # آیتمِ قدیمیِ فاقدِ item_id (که اکثراً فقط متریال/جنسِ قابل‌فروشِ
    # ساده از MAP_LOOT بودن، نه زره/سلاح واقعی) به‌اشتباه یه اسلاتِ
    # Relic می‌گرفت. نتیجه: بازیکن می‌تونست مثلاً «Sand Crystal» رو
    # تو اسلاتِ Relic اکیپ کنه، ولی چون این آیتم‌ها هیچ‌وقت از
    # generate_item واقعی نیومدن، affixesشون همیشه خالی بود —
    # یعنی اکیپ‌کردنِ تقریباً هر چیزی هیچ باستی نمی‌داد.
    # الان: اگه آیتم از قبل slot نداشته باشه، اصلاً قابل‌اکیپ نیست
    # (None) — فقط آیتم‌هایی که واقعاً از generate_item/
    # generate_random_equipment اومدن (و slot واقعی دارن) قابل‌اکیپ می‌مونن.
    item.setdefault("slot", None)
    item.setdefault("market_value", item.get("sell", 0))
    item.setdefault("craft_value", int(item.get("sell", 0) * 0.6))
    item.setdefault("weight", 1.0)
    item.setdefault("drop_source", "legacy")
    item.setdefault("created_at", time.time())
    item["item_score"] = calculate_item_score(item)
    return item

def migrate_inventory(inventory: list) -> list:
    return [migrate_legacy_item(it) for it in inventory]


# ============================================================
#  Inventory Stacking — گروه‌بندیِ آیتم‌های تکراری/استک‌شونده
# ------------------------------------------------------------
#  تجهیزاتِ واقعی (که item_id و افیکس دارن) همیشه یکتا می‌مونن.
#  متریال/جم/پوشنِ کرفت‌شده از قبل تو همون یه ردیف با فیلدِ qty
#  جمع می‌شن (crafting_system.add_material). این تابع‌ها فقط برای
#  نمایش/فروش/انتقالِ دسته‌ای، آیتم‌های *تکراری* (مثلاً چندتا حقّه‌ی
#  درمانِ کوچک که هرکدوم از یه کشتارِ جدا اومدن) رو تو یه گروه
#  جمع می‌کنن — بدونِ این‌که لازم باشه همه‌ی نقاطِ دراپِ بازی رو
#  تغییر بدیم.
# ============================================================
def stack_key(item: dict):
    """کلیدِ گروه‌بندی؛ None یعنی این آیتم همیشه یکتاست (هیچ‌وقت گروه نمی‌شه)."""
    if item.get("item_id"):
        return None  # تجهیزِ واقعی با رریتی/افیکسِ خودش — یکتا
    if item.get("material_id"):
        return ("mat", item.get("type"), item["material_id"])
    return ("plain", item.get("name"), item.get("emoji"))


def group_inventory(inv: list) -> list:
    """inv رو به گروه‌های {"item","indices","qty","total_sell"} تبدیل می‌کنه
    (با حفظِ ترتیبِ اولین‌باری که هر کلید دیده شده). آیتم‌های یکتا هرکدوم
    گروهِ جدا (qty=1) می‌شن."""
    groups: dict = {}
    order = []
    for idx, it in enumerate(inv):
        key = stack_key(it)
        if key is None:
            key = ("uniq", idx)
        if key not in groups:
            groups[key] = {"item": it, "indices": [], "qty": 0, "total_sell": 0}
            order.append(key)
        g = groups[key]
        unit_qty = it.get("qty", 1)
        g["indices"].append(idx)
        g["qty"] += unit_qty
        g["total_sell"] += it.get("sell", 0) * unit_qty
    return [groups[k] for k in order]


def take_from_group(inv: list, indices: list[int], qty: int) -> int:
    """qty واحد رو از entryهایِ یه گروه (indices، بزرگ‌به‌کوچیک مرتب‌شون کن قبل صدازدن)
    برمی‌داره — اول از entryهایی که فیلدِ qty دارن (متریال/جم/پوشن) کم می‌کنه،
    وگرنه کلِ اون entry رو (که یعنی ۱ واحدِ ساده‌ست) پاک می‌کنه.
    برمی‌گردونه: چندتا واحدِ واقعی برداشته شده (ممکنه کمتر از qty باشه اگه کم بیاره)."""
    taken = 0
    for idx in sorted(indices, reverse=True):
        if taken >= qty:
            break
        if idx >= len(inv):
            continue
        it = inv[idx]
        remaining_need = qty - taken
        if "qty" in it:
            avail = it.get("qty", 0)
            take = min(avail, remaining_need)
            it["qty"] = avail - take
            taken += take
            if it["qty"] <= 0:
                inv.pop(idx)
        else:
            inv.pop(idx)
            taken += 1
    return taken


def merge_into_inventory(inv: list, item: dict) -> None:
    """آیتمی که کلید استک داره رو با entryِ مشابه (اگه باشه) تو inv ادغام می‌کنه؛
    وگرنه به‌عنوانِ entry جدید اضافه‌ش می‌کنه. تجهیزاتِ یکتا (item_id) همیشه
    entry جدا می‌مونن — استفاده‌ی اصلی: طرفِ گیرنده‌ی انتقال/معامله."""
    key = stack_key(item)
    if key is not None:
        for it in inv:
            if stack_key(it) == key:
                it["qty"] = it.get("qty", 1) + item.get("qty", 1)
                return
    inv.append(item)


def group_qty_available(inv: list, item_name: str) -> int:
    """چندتا واحدِ آیتمی با این اسم تو inv موجوده (جمعِ همه‌ی entryهای منطبق)."""
    total = 0
    for it in inv:
        if it.get("name") == item_name:
            total += it.get("qty", 1)
    return total


def take_qty_by_name(player: dict, item_name: str, qty: int) -> dict | None:
    """qty واحد از آیتمی به اسمِ item_name رو از اینونتوریِ player جدا می‌کنه و
    به‌صورتِ یه آیتمِ مستقل (با qty درست) برمی‌گردونه — برای انتقال/معامله‌ی
    دسته‌ای. اگه کمتر از qty موجود باشه، None برمی‌گردونه (بدونِ تغییر دادنِ
    چیزی — تراکنش باید لغو بشه)."""
    if qty <= 0:
        return None
    inv = player.setdefault("inventory", [])
    groups = group_inventory(inv)
    matching = next((g for g in groups if g["item"].get("name") == item_name), None)
    if not matching or matching["qty"] < qty:
        return None
    template = dict(matching["item"])
    taken = take_from_group(inv, matching["indices"], qty)
    if taken < qty:
        return None  # نباید برسه اینجا چون از قبل چک شد، ولی برای اطمینان
    key = stack_key(template)
    result = dict(template)
    result.pop("qty", None)
    if key is not None:
        result["qty"] = qty
        result["id"] = f"{result.get('id','item')}_xfer_{int(time.time()*1000)}_{uuid.uuid4().hex[:4]}"
    return result


def repair_fake_equipment(doc: dict) -> bool:
    """خودترمیمیِ داده‌های قبلاً خراب‌شده: پلیرهایی که از قبلِ باگ‌فیکسِ
    بالا آیتمِ متریالِ ساده (مثلِ Sand Crystal) رو تو اسلاتِ Relic
    اکیپ کرده بودن. این آیتم‌ها چون هیچ‌وقت از generate_item واقعی
    نیومدن، drop_source شون همیشه "legacy"ه (item_system هیچ‌وقت این
    مقدار رو ست نمی‌کنه) — همین یه نشونه‌ی قطعیه که این آیتم قرار
    نبوده قابل‌اکیپ باشه. هر آیتمِ این‌جوری رو غیرقابل‌اکیپ می‌کنیم
    و اگه از قبل اکیپ شده، به کوله‌پشتی برش می‌گردونیم.
    idempotent است — روی دیتای سالم صدا زدنش هیچ اثری نداره.
    برمی‌گردونه True اگه چیزی عوض شده باشه (یعنی صدازننده باید
    save_player رو صدا بزنه)."""
    changed = False

    inv = doc.get("inventory")
    if inv:
        for it in inv:
            if it.get("drop_source") == "legacy" and it.get("slot") is not None:
                it["slot"] = None
                changed = True

    eq = doc.get("equipped")
    if eq:
        inv = doc.setdefault("inventory", inv or [])
        for slot, item in list(eq.items()):
            if item and item.get("drop_source") == "legacy":
                item["slot"] = None
                inv.append(item)
                eq[slot] = None
                changed = True
        if changed:
            doc["inventory"] = inv
            doc["equipped"] = eq

    return changed

# ─── Display Helpers ────────────────────────────────────────────
def format_item_card(item: dict) -> str:
    rdata = RARITY_DATA.get(item.get("rarity", "common"), RARITY_DATA["common"])
    lines = [
        f"{item.get('emoji','📦')} **{item['name']}** {item.get('variant_label','')}",
        f"{rdata['emoji']} {rdata['label']} | ⭐ Item Score: **{item.get('item_score', calculate_item_score(item))}**",
        f"📏 Lv.Req: {item.get('level_req',1)} | 🔧 Upgrade: +{item.get('upgrade_level',0)}",
    ]
    if item.get("desc"):
        lines.append(f"_{item['desc']}_")
    dur = item.get("max_durability", 0)
    if dur:
        lines.append(f"🛠 دوام: {item.get('durability',dur)}/{dur}")
    aff = item.get("affixes", {})
    for a in aff.get("prefix", []) + aff.get("suffix", []):
        lines.append(f"  • {a['label']}: +{a['value']}")
    sockets = item.get("sockets", [])
    if sockets:
        filled = sum(1 for s in sockets if s.get("gem"))
        lines.append(f"💠 سوکت: {filled}/{len(sockets)}")
    return "\n".join(lines)


# ============================================================
#  🔗 اتصالِ Item System v2 به کامبتِ واقعی
# ------------------------------------------------------------
#  تا الان آیتم‌های اکیپ‌شده فقط رو Combat Power (نمایشی/متچ‌میکینگ)
#  اثر داشتن. این دو تابع، مجموعِ افیکسِ همه‌ی اسلات‌های اکیپ‌شده رو
#  به کلیدهایی که combat.py/skill_tree.py/economy_engine.py از قبل
#  می‌شناسن (dmg_pct, crit_pct, lifesteal_pct, defense_pct, ...)
#  ترجمه می‌کنن — دقیقاً همون الگویی که ست‌ها (loot_engine) و
#  مُهرهای الهی (divine_seals) ازش استفاده می‌کنن.
# ============================================================
def equipment_stats(player: dict) -> dict:
    """جمعِ خامِ همه‌ی افیکس‌های آیتم‌های اکیپ‌شده — کلید=نامِ استتِ افیکس.
    از crafting_system.py: جم‌های سوکت‌شده هم همینجا روش جمع می‌شن، چون
    سوکت قبلاً یه فیلدِ خالیِ بی‌مصرف بود — حالا insert_gem واقعاً پرش می‌کنه."""
    totals: dict = {}
    eq = player.get("equipped", {})
    for item in eq.values():
        if not item:
            continue
        aff = item.get("affixes", {})
        for a in aff.get("prefix", []) + aff.get("suffix", []):
            stat = a.get("stat")
            if not stat:
                continue
            totals[stat] = totals.get(stat, 0) + a.get("value", 0)
        for socket in item.get("sockets", []):
            gem = socket.get("gem")
            if not gem or not gem.get("stat"):
                continue
            totals[gem["stat"]] = totals.get(gem["stat"], 0) + gem.get("value", 0)
    return totals


def combat_bonus_stats(player: dict) -> dict:
    """افیکسِ خام رو به کلیدهای مصرفیِ combat.py/skill_tree.py/economy_engine.py
    ترجمه می‌کنه. armor به defense_pct (سقف ۳۵٪) تبدیل می‌شه، افیکس‌های
    عنصری (element_dmg_*) به‌صورتِ یه بونوسِ دمیجِ عمومی جمع می‌شن.
    بافِ موقتِ غذا (cooking_system.py) هم همینجا روش جمع می‌شه، چون
    همه‌ی مصرف‌کننده‌های این تابع (combat.py و بقیه) خودکار بافِ غذا رو
    هم می‌گیرن — بدونِ نیاز به تغییرِ جای دیگه."""
    raw = equipment_stats(player)
    elem_total = sum(v for k, v in raw.items() if k.startswith("element_dmg_"))
    total_armor = raw.get("armor", 0)
    try:
        from cooking_system import get_food_bonus_stats
        food = get_food_bonus_stats(player)
    except ImportError:
        food = {}
    try:
        from crafting_system import get_potion_bonus_stats
        potion = get_potion_bonus_stats(player)
    except ImportError:
        potion = {}
    return {
        "dmg_pct":            raw.get("dmg_pct", 0) + elem_total + food.get("dmg_pct", 0) + potion.get("dmg_pct", 0),
        "crit_pct":           raw.get("crit_chance", 0) + food.get("crit_pct", 0),
        "crit_dmg_bonus":     raw.get("crit_dmg", 0),
        "lifesteal_pct":      raw.get("lifesteal", 0),
        "defense_pct":        min(0.35, total_armor / 300 + food.get("defense_pct", 0)),
        "reflect_pct":        raw.get("reflect_dmg", 0),
        "max_hp_flat":        raw.get("max_hp", 0) + food.get("max_hp_flat", 0) + potion.get("max_hp_flat", 0),
        "gold_find_pct":      raw.get("gold_find_pct", 0) + food.get("gold_find_pct", 0) + potion.get("gold_find_pct", 0),
        "xp_pct":             raw.get("xp_pct", 0) + food.get("xp_pct", 0) + potion.get("xp_pct", 0),
        "accuracy_pct":       raw.get("accuracy", 0),
        "cooldown_reduction": raw.get("cooldown_reduction", 0),
        # 🆕 الکسیرِ تشدیدِ عنصری (crafting_system) از همینجا به combat.py می‌رسه
        "elem_amp":           food.get("elem_amp", 0) + potion.get("elem_amp", 0),
    }

# ============================================================
#  Usable Loot Consumables — آیتم‌های مصرفی که از دراپ/لوت میان
# ------------------------------------------------------------
#  برخلافِ تجهیزات (که اکیپ می‌شن)، این آیتم‌ها مستقیم تو کوله‌پشتی
#  دراپ می‌شن و از همون دکمه‌ی «✨ مصرف» تو /inventory قابلِ استفاده‌ن.
#  باف‌ها از همون سیستمِ player["active_potion_buffs"] که
#  crafting_system.drink_potion استفاده می‌کنه رد می‌شن — یعنی هم تو
#  محاسبه‌ی combat (item_system.combat_bonus_stats) هم تو /craft
#  خودکار دیده می‌شن، بدونِ نیاز به تغییرِ جای دیگه.
# ============================================================
CONSUMABLE_TEMPLATES = [
    {
        "key": "vial_minor_heal", "name": "حُقّه‌ی درمانِ کوچک", "emoji": "🧪",
        "desc": "شیشه‌ای کوچک از معجونِ درمانی — فوراً بخشی از HP رو برمی‌گردونه.",
        "rarity": "common", "kind": "heal", "heal_pct": 0.25,
    },
    {
        "key": "vial_major_heal", "name": "حُقّه‌ی درمانِ بزرگ", "emoji": "🍶",
        "desc": "معجونِ غلیظِ درمانی — بخشِ بزرگی از HP رو برمی‌گردونه.",
        "rarity": "rare", "kind": "heal", "heal_pct": 0.6,
    },
    {
        "key": "elixir_power_drop", "name": "الکسیرِ خشمِ نبرد", "emoji": "🥃",
        "desc": "دمیجِ بیشتر برای مدتی.",
        "rarity": "uncommon", "kind": "buff", "buff_stat": "dmg_pct", "buff_value": 0.08, "duration": 1200,
    },
    {
        "key": "elixir_fortune_drop", "name": "الکسیرِ اقبال", "emoji": "🍀",
        "desc": "شانسِ بیشترِ طلا برای مدتی.",
        "rarity": "uncommon", "kind": "buff", "buff_stat": "gold_find_pct", "buff_value": 0.12, "duration": 1200,
    },
    {
        "key": "scroll_wisdom_drop", "name": "طومارِ خرد", "emoji": "📜",
        "desc": "تجربه‌ی بیشتر برای مدتی.",
        "rarity": "uncommon", "kind": "buff", "buff_stat": "xp_pct", "buff_value": 0.12, "duration": 1200,
    },
    {
        "key": "pouch_gold", "name": "کیسه‌ی سکه", "emoji": "💰",
        "desc": "کیسه‌ای پر از سکه — بازش کن تا Zen بگیری.",
        "rarity": "common", "kind": "gold", "amount_base": 40,
    },
    {
        "key": "tome_xp", "name": "طومارِ تجربه", "emoji": "📖",
        "desc": "خوندنش بلافاصله تجربه بهت می‌ده.",
        "rarity": "uncommon", "kind": "xp", "amount_base": 30,
    },
]

_CONSUMABLE_BASE_SELL = {"common": 25, "uncommon": 60, "rare": 150, "epic": 400}

def generate_consumable(player_level: int = 1, forced_key: str = None) -> dict:
    """یه آیتمِ مصرفیِ کامل برمی‌گردونه — مستقیم قابلِ append به player['inventory']."""
    tpl = None
    if forced_key:
        tpl = next((t for t in CONSUMABLE_TEMPLATES if t["key"] == forced_key), None)
    tpl = tpl or random.choice(CONSUMABLE_TEMPLATES)

    rarity = tpl["rarity"]
    rdata = RARITY_DATA.get(rarity, RARITY_DATA["common"])
    base_sell = _CONSUMABLE_BASE_SELL.get(rarity, 25)

    consumable = {"kind": tpl["kind"]}
    if tpl["kind"] == "heal":
        consumable["heal_pct"] = tpl["heal_pct"]
    elif tpl["kind"] == "buff":
        consumable["buff_stat"] = tpl["buff_stat"]
        consumable["buff_value"] = tpl["buff_value"]
        consumable["duration"] = tpl["duration"]
    elif tpl["kind"] == "gold":
        consumable["amount"] = int(tpl["amount_base"] * (1 + max(1, player_level) * 0.6))
    elif tpl["kind"] == "xp":
        consumable["amount"] = int(tpl["amount_base"] * (1 + max(1, player_level) * 0.8))

    iid = new_item_id()
    return {
        "item_id": iid, "id": iid,
        "name": tpl["name"], "emoji": tpl["emoji"], "desc": tpl["desc"],
        "rarity": rarity,
        "sell": int(base_sell * rdata["sell_mult"]),
        "buy": int(base_sell * 2 * rdata["sell_mult"]),
        "usable": True,
        "consumable": consumable,
        "drop_source": "loot_consumable",
        "created_at": time.time(),
    }

def use_consumable(uid: int, player: dict, item: dict) -> tuple[bool, str]:
    """اثرِ آیتمِ مصرفی رو روی player اعمال می‌کنه. حذفِ آیتم از اینونتوری
    به عهده‌ی صداکننده‌ست (bot.py) — دقیقاً مثلِ الگوی inv_sell."""
    data = item.get("consumable")
    if not data:
        return False, "❌ این آیتم قابلِ مصرف نیست."

    kind = data.get("kind")

    if kind == "heal":
        try:
            from skill_tree import effective_max_hp
            max_hp = effective_max_hp(player)
        except ImportError:
            max_hp = player.get("max_hp", 100)
        heal = int(max_hp * data.get("heal_pct", 0)) + data.get("heal_flat", 0)
        player["hp"] = min(max_hp, player.get("hp", 0) + heal)
        return True, f"💚 {item['name']} رو مصرف کردی — {heal} HP درمان شدی. (HP: {player['hp']}/{max_hp})"

    if kind == "buff":
        from crafting_system import clean_expired_potion_buffs
        clean_expired_potion_buffs(player)
        buffs = player.setdefault("active_potion_buffs", {})
        stat = data["buff_stat"]
        was_active = stat in buffs
        buffs[stat] = {
            "value": data["buff_value"],
            "expires_at": time.time() + data["duration"],
            "name": item["name"],
        }
        verb = "تازه شد" if was_active else "فعال شد"
        return True, f"✨ {item['name']} رو مصرف کردی — باف {verb}: {item.get('desc','')}"

    if kind == "gold":
        amount = data.get("amount", 0)
        player["zen"] = player.get("zen", 0) + amount
        return True, f"💰 {item['name']} رو باز کردی — +{amount:,} Zen گرفتی!"

    if kind == "xp":
        amount = data.get("amount", 0)
        player["xp"] = player.get("xp", 0) + amount
        leveled = False
        try:
            from bot import level_up_check
            player, leveled = level_up_check(player)
        except Exception:
            pass
        extra = "\n🎉 **لول‌آپ شدی!**" if leveled else ""
        return True, f"📖 {item['name']} رو خوندی — +{amount:,} XP گرفتی!{extra}"

    return False, "❌ این آیتم قابلِ مصرف نیست."
