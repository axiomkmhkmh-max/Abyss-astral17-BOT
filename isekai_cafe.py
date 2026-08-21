# ============================================================
#  ASTRAL ABYSS — Slow Life / Isekai Cafe ☕ (شاخه‌ی غیرجنگی)
# ------------------------------------------------------------
#  برای کسایی که خسته‌ی گرایندنِ نبردن: یه مسیرِ کاملاً غیرجنگیِ
#  موازی. کافه رو تقویت می‌کنی، منو باز می‌کنی، درآمدِ منفعل جمع
#  می‌کنی، و گاهی از مهمون‌های عجیب پذیرایی می‌کنی.
#
#  دیتا: player["cafe"] = {
#      "level": int, "menu": [item_id,...], "reputation": int,
#      "treasury": int, "guests_served": int, "last_income_ts": float,
#  }
#  player["cafe_last_serve_ts"] — کول‌داونِ پذیرایی.
# ============================================================
import random
import time

INCOME_PER_HOUR_PER_LEVEL = 25
INCOME_CAP_HOURS = 16
UPGRADE_BASE_COST = 250
SERVE_COOLDOWN = 60 * 45  # هر ۴۵ دقیقه یه مهمون

MENU_ITEMS = {
    "tea":       {"name": "🍵 چایِ گیاهانِ Abyss", "cost": 150, "income_bonus": 8,  "rep_bonus": 3},
    "pastry":    {"name": "🥐 کروسانِ ستاره‌ای",    "cost": 350, "income_bonus": 15, "rep_bonus": 6},
    "stew":      {"name": "🍲 خورشتِ سیاه‌چال",     "cost": 700, "income_bonus": 28, "rep_bonus": 10},
    "moon_cake": {"name": "🌙 کیکِ مهتاب",          "cost": 1500, "income_bonus": 55, "rep_bonus": 20},
}

RARE_GUESTS = [
    {"name": "🗡 یه ماجراجوی خسته", "zen": (80, 150), "rep": (5, 10),
     "line": "«بهترین غذاییه که این چند هفته خوردم... ممنونم.»"},
    {"name": "👑 یه اشراف‌زاده‌ی ناشناس", "zen": (200, 400), "rep": (10, 18),
     "line": "«جالبه... یه‌جا تو Abyss که آدم می‌تونه نفس بکشه.»"},
    {"name": "🐉 یه موجودِ عجیب در لباسِ مبدل", "zen": (300, 600), "rep": (15, 25),
     "line": "«هه. حتی من هم گاهی فقط دلم یه فنجون چای می‌خواد.»"},
]

REGULAR_GUEST_ZEN = (20, 45)
REGULAR_GUEST_REP = (1, 3)
RARE_GUEST_CHANCE = 0.12


def _cafe(player: dict) -> dict:
    c = player.get("cafe")
    if not c:
        c = {"level": 1, "menu": [], "reputation": 0, "treasury": 0, "guests_served": 0, "last_income_ts": time.time()}
        player["cafe"] = c
    return c


def income_per_hour(player: dict) -> int:
    c = _cafe(player)
    base = c["level"] * INCOME_PER_HOUR_PER_LEVEL
    for mid in c["menu"]:
        item = MENU_ITEMS.get(mid)
        if item:
            base += item["income_bonus"]
    return base


def pending_income(player: dict) -> int:
    c = _cafe(player)
    elapsed_hrs = min((time.time() - c.get("last_income_ts", time.time())) / 3600, INCOME_CAP_HOURS)
    return int(elapsed_hrs * income_per_hour(player))


def collect_income(player: dict) -> int:
    c = _cafe(player)
    amount = pending_income(player)
    c["treasury"] = c.get("treasury", 0) + amount
    c["last_income_ts"] = time.time()
    return amount


def upgrade_cost(player: dict) -> int:
    c = _cafe(player)
    return UPGRADE_BASE_COST * c["level"]


def upgrade_cafe(player: dict) -> tuple[bool, str]:
    c = _cafe(player)
    cost = upgrade_cost(player)
    if player.get("zen", 0) < cost:
        return False, f"❌ Zen کافی نداری (نیاز: {cost:,})."
    player["zen"] -= cost
    c["level"] += 1
    return True, f"☕ کافه ارتقا پیدا کرد! سطح جدید: {c['level']}"


def unlock_menu_item(player: dict, item_id: str) -> tuple[bool, str]:
    c = _cafe(player)
    item = MENU_ITEMS.get(item_id)
    if not item:
        return False, "❌ آیتمِ نامعتبر."
    if item_id in c["menu"]:
        return False, "❌ این آیتم از قبل تو منوته."
    if player.get("zen", 0) < item["cost"]:
        return False, f"❌ Zen کافی نداری (نیاز: {item['cost']:,})."
    player["zen"] -= item["cost"]
    c["menu"].append(item_id)
    c["reputation"] = c.get("reputation", 0) + item["rep_bonus"]
    return True, f"✅ {item['name']} به منو اضافه شد! (+{item['income_bonus']} درآمد/ساعت, +{item['rep_bonus']} اعتبار)"


def can_serve(player: dict) -> tuple[bool, int]:
    last = player.get("cafe_last_serve_ts", 0)
    remaining = SERVE_COOLDOWN - (time.time() - last)
    return remaining <= 0, max(0, int(remaining))


def serve_guest(player: dict) -> tuple[bool, str]:
    c = _cafe(player)
    ok, remaining = can_serve(player)
    if not ok:
        mins = remaining // 60
        return False, f"⏳ کافه الان مهمون نداره — {mins} دقیقه‌ی دیگه دوباره سر بزن."

    player["cafe_last_serve_ts"] = time.time()
    c["guests_served"] = c.get("guests_served", 0) + 1

    is_rare = random.random() < RARE_GUEST_CHANCE
    if is_rare:
        guest = random.choice(RARE_GUESTS)
        zen = random.randint(*guest["zen"])
        rep = random.randint(*guest["rep"])
        text = f"✨ **{guest['name']}** وارد کافه شد!\n_{guest['line']}_\n💰 +{zen:,} Zen | ⭐ +{rep} اعتبار"
    else:
        zen = random.randint(*REGULAR_GUEST_ZEN)
        rep = random.randint(*REGULAR_GUEST_REP)
        text = f"🙂 یه مهمونِ عادی از کافه راضی رفت.\n💰 +{zen:,} Zen | ⭐ +{rep} اعتبار"

    player["zen"] = player.get("zen", 0) + zen
    c["reputation"] = c.get("reputation", 0) + rep
    return True, text


def cafe_power_bonus(player: dict) -> float:
    """سهمِ خیلی کوچیکِ کافه تو Combat Power — این مسیر عمداً برای آرامشه، نه قدرت."""
    c = player.get("cafe")
    if not c:
        return 0.0
    return min(80.0, c.get("reputation", 0) * 0.5)


def status_text(player: dict) -> str:
    c = _cafe(player)
    pending = pending_income(player)
    lines = [
        f"☕ **کافه‌ی تو** — سطح {c['level']}\n",
        f"💰 خزانه: {c.get('treasury',0):,} Zen (+{pending:,} در انتظار)",
        f"⭐ اعتبار: {c.get('reputation',0):,}",
        f"👥 مهمون‌های پذیرایی‌شده: {c.get('guests_served',0):,}",
        f"📈 درآمد: {income_per_hour(player):,} Zen/ساعت\n",
    ]
    if c["menu"]:
        lines.append("📋 منو: " + ", ".join(MENU_ITEMS[m]["name"] for m in c["menu"]))
    else:
        lines.append("📋 منو: هنوز چیزی اضافه نکردی.")
    return "\n".join(lines)
