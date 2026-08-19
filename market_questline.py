# ============================================================
#  ASTRAL ABYSS — Market Questline (کوئست‌لاینِ بازار) 🤝
# ------------------------------------------------------------
#  یه زنجیره‌ی «اعتمادِ بازار»ه که برخلافِ hunt_questline یک‌بارمصرف
#  نیست — هر بار که کاملش کنی، ۱ «نشانِ اعتماد» (token) می‌گیری که
#  می‌تونی خرجِ خریدِ یکی از آیتم‌های ویژه‌ی بازارِ سیاه بکنی (چیزایی
#  که هیچ‌جای دیگه‌ی بازی پیدا نمی‌شن). بعدِ مصرفِ نشان، باید دوباره
#  زنجیره رو کامل کنی تا دوباره بتونی بخری — دقیقاً همون چیزی که
#  خواسته شده بود.
#
#  مراحلش از رویِ استت‌هایی که از قبل تو پروفایلِ بازیکن ثبت می‌شن
#  محاسبه می‌شه (نه هوکِ جدید تو فایل‌های دیگه) — یه snapshot از
#  مقدارِ فعلی موقعِ claim قبلی نگه می‌داریم و رشدِ نسبت به همون
#  snapshot رو می‌سنجیم.
# ============================================================
import time

MARKET_QUEST_STEPS = [
    {"stat": "shop_sales",  "need": 3, "label": "🏪 ۳ فروشِ موفق تو مغازه‌ی خودت"},
    {"stat": "pvp_wins",    "need": 2, "label": "⚔️ ۲ بردِ PvP"},
    {"stat": "boss_hits",   "need": 5, "label": "👹 ۵ ضربه به یه باسِ جهانی"},
]

# آیتم‌های ویژه‌ای که فقط با «نشانِ اعتماد» قابلِ خریدن‌ان — جای دیگه
# نه لوت می‌شن، نه تو فروشگاهِ عادیِ بازارِ سیاه هستن.
MARKET_SPECIAL_ITEMS = {
    "boss_seal": {
        "id": "boss_seal",
        "name": "🔮 مُهرِ احضارِ باس",
        "emoji": "🔮",
        "cost_zen": 20_000,
        "desc": "با مصرف‌کردنش (از کوله‌پشتی)، اگه هیچ باسِ جهانیِ زنده‌ای نباشه، "
                "یه باسِ جدید همین الان تو همون چتی که آخرین‌بار احضار شده اسپان می‌شه.",
        "shop_exclusive": True,   # قابلِ فروش به بازارِ سیاه نیست، فقط تو مغازه‌ی شخصی
        "usable": True,
        "use_effect": "force_spawn_boss",
    },
    "abyss_elixir": {
        "id": "abyss_elixir",
        "name": "🧬 اکسیرِ ذاتِ آبیس",
        "emoji": "🧬",
        "cost_zen": 35_000,
        "desc": "با مصرف‌کردنش، +1% دائمی به یه استتِ دلخواهت اضافه می‌شه "
                "(دمیج/کریتیکال/دفاع/خون‌آشامی) — سقفِ تجمعی ۱۰٪ رو هر استت.",
        "shop_exclusive": True,
        "usable": True,
        "use_effect": "elixir_stat_boost",
    },
}

ELIXIR_STAT_CAP = 0.10
ELIXIR_STAT_STEP = 0.01
ELIXIR_STAT_OPTIONS = {
    "dmg":       ("dmg_pct", "⚔️ دمیج"),
    "crit":      ("crit_pct", "🎯 کریتیکال"),
    "defense":   ("defense_pct", "🛡️ دفاع"),
    "lifesteal": ("lifesteal_pct", "🩸 خون‌آشامی"),
}


# ─── ردیابیِ پیشرفت (بدون نیاز به هوکِ جدید تو فایل‌های دیگه) ────
def _current_stat(player: dict, stat: str) -> int:
    if stat == "shop_sales":
        return player.get("shop", {}).get("total_sales", 0)
    if stat == "pvp_wins":
        return player.get("pvp_wins", 0)
    if stat == "boss_hits":
        return player.get("boss_hits_total", 0)
    return 0


def _snapshot(player: dict) -> dict:
    return player.setdefault("market_quest_snapshot", {s["stat"]: 0 for s in MARKET_QUEST_STEPS})


def market_quest_progress(player: dict) -> list:
    snap = _snapshot(player)
    out = []
    for step in MARKET_QUEST_STEPS:
        base = snap.get(step["stat"], 0)
        have = max(0, _current_stat(player, step["stat"]) - base)
        out.append({**step, "have": min(have, step["need"]), "done": have >= step["need"]})
    return out


def is_market_quest_ready(player: dict) -> bool:
    return all(s["done"] for s in market_quest_progress(player))


def claim_market_favor(player: dict) -> tuple:
    """اگه همه‌ی مراحل کامل شده باشن، ۱ نشانِ اعتماد می‌ده و snapshot رو
    برای دورِ بعدی ریست می‌کنه."""
    if not is_market_quest_ready(player):
        return False, "❌ هنوز همه‌ی مراحل رو کامل نکردی."
    snap = _snapshot(player)
    for step in MARKET_QUEST_STEPS:
        snap[step["stat"]] = _current_stat(player, step["stat"])
    player["market_favor_tokens"] = player.get("market_favor_tokens", 0) + 1
    return True, "🤝 **اعتمادِ بازار جلب شد!** یه نشانِ اعتماد گرفتی — حالا می‌تونی یکی از آیتم‌های ویژه رو بخری."


# ─── خریدِ آیتمِ ویژه با نشانِ اعتماد ─────────────────────────────
def buy_special_item(player: dict, item_id: str) -> tuple:
    item = MARKET_SPECIAL_ITEMS.get(item_id)
    if not item:
        return False, "❌ آیتم نامعتبره."
    if player.get("market_favor_tokens", 0) <= 0:
        return False, "❌ نشانِ اعتماد نداری! اول کوئست‌لاینِ بازار رو کامل کن."
    if player.get("zen", 0) < item["cost_zen"]:
        return False, f"❌ Zen کافی نداری ({item['cost_zen']:,} لازمه)."
    player["market_favor_tokens"] -= 1
    player["zen"] -= item["cost_zen"]
    player.setdefault("inventory", []).append({
        "id": f"{item_id}_{int(time.time()*1000)}",
        "name": item["name"], "emoji": item["emoji"], "rarity": "rare",
        "type": "special", "special_id": item_id,
        "shop_exclusive": True, "usable": True,
    })
    return True, f"✅ **{item['name']}** رو خریدی! از کوله‌پشتیت می‌تونی مصرفش کنی."


# ─── مصرفِ آیتم‌های ویژه ───────────────────────────────────────
def use_boss_seal(player: dict, inv_item_id: str) -> tuple:
    inv = player.get("inventory", [])
    idx = next((i for i, x in enumerate(inv) if x.get("id") == inv_item_id and x.get("special_id") == "boss_seal"), None)
    if idx is None:
        return False, "❌ این مُهر رو دیگه نداری."
    from database import get_boss, system_col
    boss = get_boss()
    if boss.get("alive"):
        return False, "⚠️ یه باسِ جهانی همین الان زنده‌ست — نمی‌شه هم‌زمان دوتا احضار کرد."
    chat_doc = system_col().find_one({"_id": "boss_spawn_chat"})
    chat_id = chat_doc.get("chat_id") if chat_doc else None
    if not chat_id:
        return False, "❌ هنوز هیچ‌جا برای احضارِ باس ثبت نشده (باید یه ادمین اول دستی احضار کنه)."
    inv.pop(idx)
    return True, "PENDING_SPAWN"  # صداکننده (handler) باید خودش spawn رو صدا بزنه و پیام بفرسته


def use_abyss_elixir(player: dict, inv_item_id: str, stat_choice: str) -> tuple:
    if stat_choice not in ELIXIR_STAT_OPTIONS:
        return False, "❌ استتِ نامعتبر."
    inv = player.get("inventory", [])
    idx = next((i for i, x in enumerate(inv) if x.get("id") == inv_item_id and x.get("special_id") == "abyss_elixir"), None)
    if idx is None:
        return False, "❌ این اکسیر رو دیگه نداری."
    stat_key, label = ELIXIR_STAT_OPTIONS[stat_choice]
    bonuses = player.setdefault("elixir_bonuses", {})
    cur = bonuses.get(stat_key, 0)
    if cur >= ELIXIR_STAT_CAP:
        return False, f"❌ {label} از قبل به سقفِ +{int(ELIXIR_STAT_CAP*100)}٪ رسیده."
    inv.pop(idx)
    bonuses[stat_key] = round(min(ELIXIR_STAT_CAP, cur + ELIXIR_STAT_STEP), 4)
    return True, f"✅ **{label}** دائمی +{int(ELIXIR_STAT_STEP*100)}٪ شد! (جمع الان: {int(bonuses[stat_key]*100)}٪)"


def get_elixir_bonuses(player: dict) -> dict:
    """dict تخت، دقیقاً هم‌شکلِ setb — قاطیِ همون مسیرِ combat.py می‌شه."""
    return dict(player.get("elixir_bonuses", {}))
