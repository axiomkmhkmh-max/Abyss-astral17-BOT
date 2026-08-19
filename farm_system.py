# ============================================================
#  ASTRAL ABYSS RPG — Farm & Livestock 🌾  (v1)
#  زیرسیستمِ دومِ فیچرِ خونه/مزرعه/زمین/شهر (بعد از land_system.py).
#
#  مزرعه رو زمینِ خودت (land_system) می‌سازی — تعدادِ اسلات‌های
#  کاشت/دام‌داری به سایزِ زمینت بستگی داره. بدونِ زمین، مزرعه نداری.
#
#  «مینی‌گیمِ» این بخش یه مکانیزمِ تایمینگِ واقعیه، نه تپ‌زدنِ مصنوعی:
#    🌱 محصول: هرچی زودتر بعدِ رسیدن برداشت کنی، تازه‌تره → بازدهِ
#       بیشتر. دیر بجنبی، محصول می‌پوسه و از دست می‌ره.
#    🐄 دام: هرچی منظم‌تر تغذیه‌ش کنی (تو بازه‌ی درست، نه زود نه دیر)،
#       «شادی»‌ش بالاتر می‌ره و تولیدش بیشتر می‌شه؛ فراموش‌کردنش
#       شادی رو می‌ریزه پایین.
# ============================================================
import time
from database import get_db
import land_system as ls

CROPS = {
    "wheat":     {"name": "🌾 گندم",        "seed_cost": 50,   "grow_seconds": 1800,   "yield_min": 3, "yield_max": 5, "sell": 15,  "mat_emoji": "🌾"},
    "carrot":    {"name": "🥕 هویج",        "seed_cost": 90,   "grow_seconds": 2700,   "yield_min": 3, "yield_max": 6, "sell": 22,  "mat_emoji": "🥕"},
    "tomato":    {"name": "🍅 گوجه",        "seed_cost": 150,  "grow_seconds": 3600,   "yield_min": 4, "yield_max": 7, "sell": 30,  "mat_emoji": "🍅"},
    "pumpkin":   {"name": "🎃 کدوتنبل",     "seed_cost": 400,  "grow_seconds": 10800,  "yield_min": 2, "yield_max": 4, "sell": 90,  "mat_emoji": "🎃"},
    "moonflower":{"name": "🌙 گلِ ماه",     "seed_cost": 1200, "grow_seconds": 21600,  "yield_min": 1, "yield_max": 2, "sell": 350, "mat_emoji": "🌙"},
}

# کیفیتِ برداشت بر اساسِ فاصله‌ی زمانی از لحظه‌ی «رسیدن» (به‌نسبتِ grow_seconds)
QUALITY_TIERS = [
    (0.15, "🌟 تازه",   1.5),
    (1.00, "✅ معمولی", 1.0),
    (2.50, "🥀 دیرمونده", 0.7),
]  # بعدِ این حد، محصول کاملاً می‌پوسه (صفر بازده)

FARM_SLOTS_BY_LAND = {"small": 2, "medium": 4, "large": 6}
BARN_SLOTS_BY_LAND = {"small": 1, "medium": 2, "large": 3}

LIVESTOCK = {
    "chicken": {"name": "🐔 مرغ",   "cost": 800,  "cycle_seconds": 3 * 3600, "produce_min": 2, "produce_max": 3, "mat_id": "egg",  "mat_name": "🥚 تخم‌مرغ", "sell": 12, "feed_cost": 20},
    "sheep":   {"name": "🐑 گوسفند", "cost": 2000, "cycle_seconds": 8 * 3600, "produce_min": 1, "produce_max": 3, "mat_id": "wool", "mat_name": "🧶 پشم",     "sell": 35, "feed_cost": 40},
    "cow":     {"name": "🐄 گاو",    "cost": 3500, "cycle_seconds": 6 * 3600, "produce_min": 2, "produce_max": 4, "mat_id": "milk", "mat_name": "🥛 شیر",     "sell": 45, "feed_cost": 60},
}

FEED_WINDOW_EARLY = 0.5   # تغذیه قبل از ۵۰٪ چرخه = «زودِ زیاد»، شادی رو کم می‌ده
FEED_WINDOW_LATE = 1.5    # تغذیه بعد از ۱۵۰٪ چرخه = «دیرِ زیاد»، شادی رو کم می‌ده
HAPPINESS_MAX = 100
HAPPINESS_GOOD_FEED_GAIN = 15
HAPPINESS_BAD_FEED_GAIN = 3
HAPPINESS_DECAY_PER_MISSED_CYCLE = 20
HAPPINESS_MIN_MULT = 0.5   # شادیِ صفر یعنی نصفِ بازدهِ عادی
HAPPINESS_MAX_MULT = 1.5   # شادیِ کامل یعنی ۱.۵ برابر بازده


def farm_col():
    return get_db()["farms"]


def ensure_farm(uid: int) -> dict:
    doc = farm_col().find_one({"_id": uid})
    if not doc:
        doc = {"_id": uid, "crop_slots": [], "barn": []}
        farm_col().insert_one(doc)
    return doc


def _slot_limits(uid: int) -> tuple[int, int]:
    land = ls.get_my_land(uid)
    if not land:
        return 0, 0
    return FARM_SLOTS_BY_LAND[land["size"]], BARN_SLOTS_BY_LAND[land["size"]]


def _add_material(player: dict, mat_id: str, name: str, emoji: str, qty: int, sell: int):
    inv = player.setdefault("inventory", [])
    for it in inv:
        if it.get("type") == "material" and it.get("material_id") == mat_id:
            it["qty"] = it.get("qty", 1) + qty
            return
    inv.append({
        "id": f"mat_{mat_id}_{int(time.time()*1000)}",
        "material_id": mat_id, "name": name, "emoji": emoji,
        "type": "material", "qty": qty, "sell": sell,
    })


# ─── کاشت/برداشتِ محصول ──────────────────────────────────────────
def plant_crop(uid: int, player: dict, crop_key: str) -> tuple[bool, str]:
    crop = CROPS.get(crop_key)
    if not crop:
        return False, "❌ محصولِ نامعتبر."
    max_slots, _ = _slot_limits(uid)
    if max_slots == 0:
        return False, "❌ اول باید زمین بخری (🗺 زمین) — بدونِ زمین مزرعه نداری."
    doc = ensure_farm(uid)
    slots = doc["crop_slots"]
    if len(slots) >= max_slots:
        return False, f"❌ همه‌ی {max_slots} اسلاتِ کاشتِ زمینت پره! یا برداشت کن یا زمینت رو بزرگ کن."
    if player.get("zen", 0) < crop["seed_cost"]:
        return False, f"❌ برای بذرِ {crop['name']} به {crop['seed_cost']:,} Zen نیاز داری."
    player["zen"] -= crop["seed_cost"]
    now = time.time()
    slots.append({"crop": crop_key, "planted_at": now, "ready_at": now + crop["grow_seconds"]})
    farm_col().update_one({"_id": uid}, {"$set": {"crop_slots": slots}})
    return True, f"🌱 {crop['name']} کاشتی — تا {crop['grow_seconds']//60} دقیقه‌ی دیگه آماده‌ست."


def farm_status(uid: int) -> list[dict]:
    doc = ensure_farm(uid)
    now = time.time()
    out = []
    for i, s in enumerate(doc["crop_slots"]):
        crop = CROPS[s["crop"]]
        if now < s["ready_at"]:
            out.append({"idx": i, "crop": s["crop"], "state": "growing",
                        "remaining": int(s["ready_at"] - now)})
        else:
            elapsed_ratio = (now - s["ready_at"]) / crop["grow_seconds"]
            if elapsed_ratio > QUALITY_TIERS[-1][0]:
                out.append({"idx": i, "crop": s["crop"], "state": "spoiled"})
            else:
                for max_ratio, label, mult in QUALITY_TIERS:
                    if elapsed_ratio <= max_ratio:
                        out.append({"idx": i, "crop": s["crop"], "state": "ready",
                                    "quality_label": label, "quality_mult": mult})
                        break
    return out


def harvest_crop(uid: int, player: dict, slot_idx: int) -> tuple[bool, str]:
    doc = ensure_farm(uid)
    slots = doc["crop_slots"]
    if slot_idx < 0 or slot_idx >= len(slots):
        return False, "❌ اسلاتِ نامعتبر."
    s = slots[slot_idx]
    crop = CROPS[s["crop"]]
    now = time.time()
    if now < s["ready_at"]:
        return False, "⏳ هنوز آماده نیست."
    elapsed_ratio = (now - s["ready_at"]) / crop["grow_seconds"]
    if elapsed_ratio > QUALITY_TIERS[-1][0]:
        slots.pop(slot_idx)
        farm_col().update_one({"_id": uid}, {"$set": {"crop_slots": slots}})
        return False, f"🥀 {crop['name']} خیلی دیر برداشتش کردی و پوسید — هیچی گیرت نیومد."
    label, mult = None, 1.0
    for max_ratio, lbl, m in QUALITY_TIERS:
        if elapsed_ratio <= max_ratio:
            label, mult = lbl, m
            break
    import random
    base = random.randint(crop["yield_min"], crop["yield_max"])
    qty = max(1, int(base * mult))
    _add_material(player, s["crop"], crop["name"], crop["mat_emoji"], qty, crop["sell"])
    slots.pop(slot_idx)
    farm_col().update_one({"_id": uid}, {"$set": {"crop_slots": slots}})
    return True, f"{label} برداشت: **{qty}× {crop['name']}** به کوله‌پشتیت اضافه شد."


# ─── دام‌داری ─────────────────────────────────────────────────────
def buy_animal(uid: int, player: dict, animal_key: str) -> tuple[bool, str]:
    animal = LIVESTOCK.get(animal_key)
    if not animal:
        return False, "❌ دامِ نامعتبر."
    _, max_barn = _slot_limits(uid)
    if max_barn == 0:
        return False, "❌ اول باید زمین بخری (🗺 زمین) — بدونِ زمین طویله نداری."
    doc = ensure_farm(uid)
    barn = doc["barn"]
    if len(barn) >= max_barn:
        return False, f"❌ همه‌ی {max_barn} جای طویله‌ی زمینت پره!"
    if player.get("zen", 0) < animal["cost"]:
        return False, f"❌ برای خریدِ {animal['name']} به {animal['cost']:,} Zen نیاز داری."
    player["zen"] -= animal["cost"]
    now = time.time()
    barn.append({"animal": animal_key, "bought_at": now, "last_fed_at": now,
                "last_collect_at": now, "happiness": 70})
    farm_col().update_one({"_id": uid}, {"$set": {"barn": barn}})
    return True, f"{animal['name']} رو خریدی و آوردیش تو طویله!"


def barn_status(uid: int) -> list[dict]:
    doc = ensure_farm(uid)
    now = time.time()
    out = []
    for i, a in enumerate(doc["barn"]):
        animal = LIVESTOCK[a["animal"]]
        cycles_ready = int((now - a["last_collect_at"]) // animal["cycle_seconds"])
        out.append({
            "idx": i, "animal": a["animal"], "happiness": a["happiness"],
            "cycles_ready": max(0, min(cycles_ready, 4)),
            "time_since_fed": now - a["last_fed_at"],
        })
    return out


def feed_animal(uid: int, player: dict, slot_idx: int) -> tuple[bool, str]:
    doc = ensure_farm(uid)
    barn = doc["barn"]
    if slot_idx < 0 or slot_idx >= len(barn):
        return False, "❌ اسلاتِ نامعتبر."
    a = barn[slot_idx]
    animal = LIVESTOCK[a["animal"]]
    if player.get("zen", 0) < animal["feed_cost"]:
        return False, f"❌ برای غذای {animal['name']} به {animal['feed_cost']:,} Zen نیاز داری."
    now = time.time()
    ratio = (now - a["last_fed_at"]) / animal["cycle_seconds"]
    if FEED_WINDOW_EARLY <= ratio <= FEED_WINDOW_LATE:
        gain, note = HAPPINESS_GOOD_FEED_GAIN, "⏱️ زمان‌بندیِ خوب!"
    else:
        gain, note = HAPPINESS_BAD_FEED_GAIN, "⏱️ یکم زود/دیر تغذیه‌ش کردی — تاثیرِ کمتری داشت."
    player["zen"] -= animal["feed_cost"]
    a["happiness"] = min(HAPPINESS_MAX, a["happiness"] + gain)
    a["last_fed_at"] = now
    farm_col().update_one({"_id": uid}, {"$set": {"barn": barn}})
    return True, f"{animal['name']} رو تغذیه کردی. {note} (شادی: {a['happiness']}/100)"


def collect_produce(uid: int, player: dict, slot_idx: int) -> tuple[bool, str]:
    doc = ensure_farm(uid)
    barn = doc["barn"]
    if slot_idx < 0 or slot_idx >= len(barn):
        return False, "❌ اسلاتِ نامعتبر."
    a = barn[slot_idx]
    animal = LIVESTOCK[a["animal"]]
    now = time.time()
    cycles = int((now - a["last_collect_at"]) // animal["cycle_seconds"])
    if cycles <= 0:
        remain = int(animal["cycle_seconds"] - (now - a["last_collect_at"]))
        return False, f"⏳ هنوز چیزی تولید نکرده — {remain//60} دقیقه‌ی دیگه سر بزن."
    # اگه چند سیکل نادیده گرفته شده باشه، شادی افت می‌کنه (نگهداری از دام فراموش شده)
    missed_penalty = max(0, cycles - 1) * HAPPINESS_DECAY_PER_MISSED_CYCLE
    a["happiness"] = max(0, a["happiness"] - missed_penalty)
    cycles = min(cycles, 4)  # سقفِ انباشت — ضدِ غیبتِ طولانی
    happiness_mult = HAPPINESS_MIN_MULT + (a["happiness"] / HAPPINESS_MAX) * (HAPPINESS_MAX_MULT - HAPPINESS_MIN_MULT)
    import random
    total_qty = 0
    for _ in range(cycles):
        total_qty += max(1, int(random.randint(animal["produce_min"], animal["produce_max"]) * happiness_mult))
    _add_material(player, animal["mat_id"], animal["mat_name"], animal["mat_name"].split()[0], total_qty, animal["sell"])
    a["last_collect_at"] = now
    farm_col().update_one({"_id": uid}, {"$set": {"barn": barn}})
    happy_txt = "😊" if a["happiness"] >= 70 else ("😐" if a["happiness"] >= 35 else "😞")
    return True, f"{animal['name']} {happy_txt}: **{total_qty}× {animal['mat_name']}** به کوله‌پشتیت اضافه شد."


def sell_animal(uid: int, player: dict, slot_idx: int) -> tuple[bool, str]:
    doc = ensure_farm(uid)
    barn = doc["barn"]
    if slot_idx < 0 or slot_idx >= len(barn):
        return False, "❌ اسلاتِ نامعتبر."
    a = barn.pop(slot_idx)
    animal = LIVESTOCK[a["animal"]]
    refund = int(animal["cost"] * 0.4)
    player["zen"] = player.get("zen", 0) + refund
    farm_col().update_one({"_id": uid}, {"$set": {"barn": barn}})
    return True, f"{animal['name']} رو فروختی و {refund:,} Zen گرفتی."


def farm_summary_text(uid: int) -> str:
    max_slots, max_barn = _slot_limits(uid)
    if max_slots == 0:
        return "🌾 اول باید زمین بخری (🗺 زمین) تا بتونی مزرعه راه بندازی."
    crops = farm_status(uid)
    barn = barn_status(uid)
    lines = [f"🌱 اسلاتِ کاشت: {len(crops)}/{max_slots} | 🐄 طویله: {len(barn)}/{max_barn}", ""]
    if crops:
        for c in crops:
            crop = CROPS[c["crop"]]
            if c["state"] == "growing":
                m, s = divmod(c["remaining"], 60)
                lines.append(f"  🌱 {crop['name']}: در حالِ رشد ({m} دقیقه مونده)")
            elif c["state"] == "ready":
                lines.append(f"  {c['quality_label']} {crop['name']}: آماده‌ی برداشته!")
            else:
                lines.append(f"  🥀 {crop['name']}: پوسیده — برداشتش کن تا اسلات آزاد شه")
    else:
        lines.append("  — چیزی کاشته نشده —")
    lines.append("")
    if barn:
        for a in barn:
            animal = LIVESTOCK[a["animal"]]
            ready_txt = f"📦 {a['cycles_ready']}× آماده‌ی برداشت" if a["cycles_ready"] > 0 else "⏳ هنوز آماده نیست"
            lines.append(f"  {animal['name']}: شادی {a['happiness']}/100 — {ready_txt}")
    else:
        lines.append("  — دامی نداری —")
    return "\n".join(lines)
