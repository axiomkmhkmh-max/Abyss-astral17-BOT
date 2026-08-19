# ============================================================
#  ASTRAL ABYSS — Guild War Deepening (نقشه‌ی جنگِ گیلدها)
#  روی همون سیستمِ «جنگ هفتگی گیلدها»ی قبلی (guild_system.war_*)
#  یه لایه‌ی عمیق‌تر می‌سازه: ۶ قلمرو که گیلدها باهم روش می‌جنگن،
#  حمله/گاریزون، پرکِ کنترلِ قلمرو، سکه‌ی جنگ و فروشگاهِ جنگی.
# ============================================================
from __future__ import annotations
import time
import random

import guild_system as gs
from combat_power import calculate_combat_power

RAID_COOLDOWN     = 25 * 60      # هر ۲۵ دقیقه یه حمله
GARRISON_COOLDOWN = 40 * 60      # هر ۴۰ دقیقه یه گاریزون
GARRISON_DECAY_PER_HOUR = 0.12   # دفاعِ گاریزون‌شده هر ساعت ۱۲٪ افت می‌کنه
CAPTURE_DEFENSE_AFTER = 0.55     # وقتی قلمرو دست عوض می‌کنه، دفاعش این‌قدرِ قبلی می‌شه (قابلِ تلافی)

TERRITORIES = {
    "outpost":  {"name": "پاسگاهِ مرزی",        "emoji": "🏕",  "base_defense": 260,
                 "desc": "دروازه‌ی ورود به قلمروهای جنگی — ساده‌ترین هدف برای شروع.",
                 "perk": "raid_cd_pct", "perk_val": 0.15, "perk_desc": "کول‌داونِ حمله ۱۵٪ کمتر"},
    "forge":    {"name": "کوره‌ی جنگی",          "emoji": "🔥",  "base_defense": 420,
                 "desc": "کنترلش هزینه‌ی فورج و کرفتینگ رو ارزون‌تر می‌کنه.",
                 "perk": "craft_discount_pct", "perk_val": 0.12, "perk_desc": "۱۲٪ تخفیفِ کرفتینگ"},
    "market":   {"name": "بازارِ محاصره‌شده",     "emoji": "💰",  "base_defense": 420,
                 "desc": "کنترلش تخفیفِ مالیاتِ بازار می‌ده.",
                 "perk": "tax_discount_pct", "perk_val": 0.10, "perk_desc": "۱۰٪ تخفیفِ مالیاتِ اقتصاد"},
    "sanctum":  {"name": "معبدِ ممنوعه",          "emoji": "🔮",  "base_defense": 520,
                 "desc": "کنترلش تجربه‌ی اضافه به همه‌ی اعضا می‌ده.",
                 "perk": "xp_bonus_pct", "perk_val": 0.08, "perk_desc": "۸٪ XP اضافه"},
    "wilds":    {"name": "دشتِ شکارِ خونین",      "emoji": "🏹",  "base_defense": 480,
                 "desc": "کنترلش شانسِ لوتِ کمیاب رو بالا می‌بره.",
                 "perk": "loot_bonus_pct", "perk_val": 0.10, "perk_desc": "۱۰٪ شانسِ لوتِ نایاب"},
    "citadel":  {"name": "دژِ مرکزی",             "emoji": "🏰",  "base_defense": 700,
                 "desc": "قدرتمندترین قلمرو — کنترلش پاداشِ پایانِ هفته رو دوبرابر می‌کنه.",
                 "perk": "week_bonus_mult", "perk_val": 2.0, "perk_desc": "۲× پاداشِ پایانِ هفته"},
}
TERRITORY_IDS = list(TERRITORIES.keys())

WEEK_END_TERRITORY_POINTS = 400   # هر قلمرو کنترل‌شده، این‌قدر امتیازِ جنگِ هفتگی به گیلد می‌ده

WAR_SHOP = [
    {"id": "coin_chest_small", "name": "🎁 صندوقچه‌ی سکه‌ی جنگی کوچک", "cost": 40, "kind": "zen", "value": 4000},
    {"id": "coin_chest_big",   "name": "🎁 صندوقچه‌ی سکه‌ی جنگی بزرگ", "cost": 120, "kind": "zen", "value": 15000},
    {"id": "war_banner",       "name": "🚩 پرچمِ فاتحِ جنگ (عنوان)",   "cost": 200, "kind": "title", "value": "فاتحِ قلمروها"},
    {"id": "skill_orb",        "name": "🌟 گویِ مهارتِ جنگی",         "cost": 260, "kind": "skill_point", "value": 1},
    {"id": "repair_kit",       "name": "🔧 کیتِ تعمیرِ کاملِ تجهیزات", "cost": 90, "kind": "repair_all", "value": None},
]


# ────────────────────────────────────────────────────────────
#  ذخیره‌سازی
# ────────────────────────────────────────────────────────────
def _doc():
    from database import system_col
    doc = system_col().find_one({"_id": "guild_war_territories"})
    if not doc:
        doc = _fresh_doc()
        system_col().update_one({"_id": "guild_war_territories"}, {"$set": doc}, upsert=True)
    if "territories" not in doc or set(doc["territories"].keys()) != set(TERRITORY_IDS):
        doc = _fresh_doc()
        system_col().update_one({"_id": "guild_war_territories"}, {"$set": doc}, upsert=True)
    return doc


def _fresh_doc() -> dict:
    return {
        "_id": "guild_war_territories",
        "week_start": time.time(),
        "territories": {
            tid: {
                "controller": None,
                "defense": float(t["base_defense"]),
                "garrison": {},          # guild_id -> {"amount": float, "at": ts}
                "last_capture": None,
            } for tid, t in TERRITORIES.items()
        },
    }


def _save(doc: dict):
    from database import system_col
    data = {k: v for k, v in doc.items() if k != "_id"}
    system_col().update_one({"_id": "guild_war_territories"}, {"$set": data}, upsert=True)


def _decay_defense(terr: dict):
    """گاریزونِ نگهبانی‌شده با زمان افت می‌کنه — نگه‌داشتنِ یه قلمرو مداوم تلاش می‌خواد."""
    now = time.time()
    for gid, g in list(terr.get("garrison", {}).items()):
        hours = max(0.0, (now - g.get("at", now)) / 3600)
        g["amount"] = max(0.0, g["amount"] * ((1 - GARRISON_DECAY_PER_HOUR) ** hours))
        g["at"] = now
        if g["amount"] < 1:
            terr["garrison"].pop(gid, None)


def _effective_defense(tid: str, terr: dict) -> float:
    base = TERRITORIES[tid]["base_defense"] if terr.get("controller") is None else TERRITORIES[tid]["base_defense"] * CAPTURE_DEFENSE_AFTER
    garrison_bonus = sum(g["amount"] for g in terr.get("garrison", {}).values())
    return base + garrison_bonus


def _maybe_roll_week(doc: dict) -> list[str]:
    """اگه هفته‌ی جنگِ اصلی رول شده باشه، پاداشِ کنترلِ قلمرو رو بده و نقشه رو ریست کن."""
    main_war = gs.get_war_state()
    events = []
    if main_war["week_start"] > doc.get("week_start", 0) + 1:
        for tid, terr in doc["territories"].items():
            controller = terr.get("controller")
            if controller:
                mult = TERRITORIES[tid]["perk_val"] if TERRITORIES[tid]["perk"] == "week_bonus_mult" else 1.0
                pts = int(WEEK_END_TERRITORY_POINTS * mult)
                gs.add_war_points(controller, pts)
                events.append(f"{TERRITORIES[tid]['emoji']} {TERRITORIES[tid]['name']} پیشِ {gs.GUILDS[controller]['name']} بود → +{pts} امتیازِ جنگی")
        new_doc = _fresh_doc()
        doc.clear()
        doc.update(new_doc)
    return events


def get_state() -> dict:
    doc = _doc()
    _maybe_roll_week(doc)
    for terr in doc["territories"].values():
        _decay_defense(terr)
    _save(doc)
    return doc


# ────────────────────────────────────────────────────────────
#  UI متن
# ────────────────────────────────────────────────────────────
def war_map_text() -> str:
    doc = get_state()
    lines = ["🗺 **نقشه‌ی جنگِ گیلدها**\n"]
    for tid in TERRITORY_IDS:
        t = TERRITORIES[tid]
        terr = doc["territories"][tid]
        ctrl = terr.get("controller")
        ctrl_txt = f"{gs.GUILDS[ctrl]['emoji']} {gs.GUILDS[ctrl]['name']}" if ctrl else "🏳️ بی‌صاحب"
        eff_def = int(_effective_defense(tid, terr))
        lines.append(
            f"{t['emoji']} **{t['name']}** — {ctrl_txt}\n"
            f"   🛡 دفاع: {eff_def:,} | 🎁 پرک: {t['perk_desc']}\n"
        )
    lines.append("⚔️ با حمله می‌تونی قلمروی دشمن رو تصرف کنی؛ با گاریزون از قلمروی خودتون دفاع کن.")
    return "\n".join(lines)


def territory_detail_text(tid: str) -> str:
    doc = get_state()
    t = TERRITORIES[tid]
    terr = doc["territories"][tid]
    ctrl = terr.get("controller")
    ctrl_txt = f"{gs.GUILDS[ctrl]['emoji']} {gs.GUILDS[ctrl]['name']}" if ctrl else "🏳️ بی‌صاحب"
    eff_def = int(_effective_defense(tid, terr))
    garrison_lines = "\n".join(
        f"   • {gs.GUILDS[gid]['emoji']} {gs.GUILDS[gid]['name']}: {int(g['amount']):,}"
        for gid, g in terr.get("garrison", {}).items()
    ) or "   —"
    return (
        f"{t['emoji']} **{t['name']}**\n{t['desc']}\n\n"
        f"👑 کنترل‌کننده: {ctrl_txt}\n"
        f"🛡 دفاعِ فعلی: {eff_def:,}\n"
        f"🎁 پرک: {t['perk_desc']}\n\n"
        f"🏕 گاریزون‌های فعال:\n{garrison_lines}"
    )


# ────────────────────────────────────────────────────────────
#  حمله (Raid)
# ────────────────────────────────────────────────────────────
def raid_cooldown_remaining(player: dict) -> int:
    last = player.get("war_raid_cd", 0)
    cd = RAID_COOLDOWN
    perks = get_player_perks(player)
    cd = int(cd * (1 - perks.get("raid_cd_pct", 0)))
    remain = int(last + cd - time.time())
    return max(0, remain)


def raid_territory(player: dict, guild_id: str, tid: str) -> tuple[bool, str]:
    if not gs.is_member(player, guild_id):
        return False, "❌ اول باید عضوِ این گیلد باشی."
    remain = raid_cooldown_remaining(player)
    if remain > 0:
        m, s = divmod(remain, 60)
        return False, f"⏳ حمله‌ت هنوز کول‌داونه — {m} دقیقه و {s} ثانیه دیگه."

    doc = get_state()
    terr = doc["territories"][tid]
    if terr.get("controller") == guild_id:
        return False, "🏳️ این قلمرو همین الان دستِ خودتونه — به‌جاش گاریزون بذار."

    player["war_raid_cd"] = time.time()
    cp = calculate_combat_power(player)
    atk_power = cp * random.uniform(0.85, 1.2)
    eff_def = _effective_defense(tid, terr)
    def_roll = eff_def * random.uniform(0.85, 1.15)

    success = atk_power > def_roll
    margin = atk_power - def_roll
    t = TERRITORIES[tid]

    if success:
        prev_controller = terr.get("controller")
        terr["controller"] = guild_id
        terr["defense"] = t["base_defense"] * CAPTURE_DEFENSE_AFTER
        terr["garrison"] = {}
        terr["last_capture"] = time.time()
        _save(doc)
        gs.add_war_points(guild_id, 60)
        coins = random.randint(8, 16)
        player["war_coins"] = player.get("war_coins", 0) + coins
        prev_txt = f" (از {gs.GUILDS[prev_controller]['name']})" if prev_controller else ""
        return True, (
            f"🏴 **قلمروی {t['emoji']} {t['name']} تصرف شد!**{prev_txt}\n"
            f"⚔️ قدرتِ حمله: {int(atk_power):,} در برابرِ دفاعِ {int(def_roll):,}\n"
            f"🪙 +{coins} سکه‌ی جنگی | 🏅 +60 امتیازِ جنگیِ گیلد"
        )
    else:
        _save(doc)
        coins = random.randint(2, 5)
        player["war_coins"] = player.get("war_coins", 0) + coins
        gs.add_war_points(guild_id, 12)
        return False, (
            f"🛡 **حمله به {t['emoji']} {t['name']} دفع شد.**\n"
            f"⚔️ قدرتِ حمله: {int(atk_power):,} در برابرِ دفاعِ {int(def_roll):,} (کمبود {int(-margin):,})\n"
            f"🪙 +{coins} سکه‌ی جنگی به‌خاطرِ تلاش | 🏅 +12 امتیازِ جنگیِ گیلد"
        )


# ────────────────────────────────────────────────────────────
#  گاریزون (Garrison) — تقویتِ دفاعِ قلمروِ خودی
# ────────────────────────────────────────────────────────────
def garrison_cooldown_remaining(player: dict) -> int:
    last = player.get("war_garrison_cd", 0)
    remain = int(last + GARRISON_COOLDOWN - time.time())
    return max(0, remain)


def garrison_territory(player: dict, guild_id: str, tid: str) -> tuple[bool, str]:
    if not gs.is_member(player, guild_id):
        return False, "❌ اول باید عضوِ این گیلد باشی."
    doc = get_state()
    terr = doc["territories"][tid]
    if terr.get("controller") != guild_id:
        return False, "⚔️ فقط می‌تونی از قلمروهایی که خودِ گیلدت کنترلش می‌کنه دفاع کنی."
    remain = garrison_cooldown_remaining(player)
    if remain > 0:
        m, s = divmod(remain, 60)
        return False, f"⏳ گاریزونت هنوز کول‌داونه — {m} دقیقه و {s} ثانیه دیگه."

    player["war_garrison_cd"] = time.time()
    cp = calculate_combat_power(player)
    add = max(20, int(cp * 0.18))
    g = terr["garrison"].setdefault(guild_id, {"amount": 0.0, "at": time.time()})
    g["amount"] += add
    g["at"] = time.time()
    _save(doc)
    gs.add_war_points(guild_id, 18)
    t = TERRITORIES[tid]
    return True, (
        f"🏕 از {t['emoji']} {t['name']} محافظت کردی — دفاع +{add:,}\n"
        f"🏅 +18 امتیازِ جنگیِ گیلد"
    )


# ────────────────────────────────────────────────────────────
#  پرک‌ها — بر اساسِ قلمروهای تحتِ کنترلِ گیلدِ بازیکن
# ────────────────────────────────────────────────────────────
def get_player_perks(player: dict) -> dict:
    """جمعِ همه‌ی پرک‌های قلمروهایی که هر کدوم از گیلدهای بازیکن کنترل می‌کنه."""
    doc = get_state()
    perks: dict = {}
    player_guilds = set(player.get("guilds", {}).keys())
    if not player_guilds:
        return perks
    for tid, terr in doc["territories"].items():
        ctrl = terr.get("controller")
        if ctrl in player_guilds:
            t = TERRITORIES[tid]
            perks[t["perk"]] = max(perks.get(t["perk"], 0), t["perk_val"])
    return perks


# ────────────────────────────────────────────────────────────
#  فروشگاهِ جنگی (با سکه‌ی جنگ)
# ────────────────────────────────────────────────────────────
def war_shop_text(player: dict) -> str:
    coins = player.get("war_coins", 0)
    lines = [f"🪙 **فروشگاهِ جنگ** — موجودی: {coins:,} سکه\n"]
    for item in WAR_SHOP:
        lines.append(f"🔸 {item['name']} — {item['cost']} سکه")
    return "\n".join(lines)


def buy_war_item(player: dict, item_id: str) -> tuple[bool, str]:
    item = next((i for i in WAR_SHOP if i["id"] == item_id), None)
    if not item:
        return False, "❌ آیتم پیدا نشد."
    coins = player.get("war_coins", 0)
    if coins < item["cost"]:
        return False, f"❌ سکه‌ی جنگیت کافی نیست ({coins}/{item['cost']})."
    player["war_coins"] = coins - item["cost"]

    kind = item["kind"]
    if kind == "zen":
        player["zen"] = player.get("zen", 0) + item["value"]
        return True, f"✅ خریدی شد: **{item['name']}**\n💰 +{item['value']:,} Zen"
    if kind == "title":
        titles = player.setdefault("titles", [])
        if item["value"] not in titles:
            titles.append(item["value"])
        return True, f"✅ خریدی شد: **{item['name']}**\n🏷 عنوانِ «{item['value']}» باز شد!"
    if kind == "skill_point":
        player["skill_points"] = player.get("skill_points", 0) + item["value"]
        return True, f"✅ خریدی شد: **{item['name']}**\n🌟 +{item['value']} امتیازِ مهارت"
    if kind == "repair_all":
        eq = player.get("equipped", {})
        fixed = 0
        for slot, it in eq.items():
            if it and it.get("durability", 100) < it.get("max_durability", 100):
                it["durability"] = it.get("max_durability", 100)
                fixed += 1
        return True, f"✅ خریدی شد: **{item['name']}**\n🔧 {fixed} وسیله تعمیر شد."
    return False, "❌ خطای ناشناخته."
