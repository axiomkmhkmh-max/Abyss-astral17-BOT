# ============================================================
#  ASTRAL ABYSS — Hunt Questline 🎯 (کوئست‌لاینِ حمله)
# ------------------------------------------------------------
#  دکمه‌ی «حمله» تا الان فقط یه راهِ فرعیِ کسب Zen/XP بود که همیشه
#  ضعیف‌تر از لوت به‌نظر می‌رسید (چون مسیرِ لوت setb/eqb/petb رو هم
#  حساب می‌کنه، ولی مسیرِ حمله نه). این ماژول دو کار می‌کنه:
#
#   ۱) یه زنجیره‌ی ۱۰ مرحله‌ای از «شکارِ هدف‌دار» می‌سازه — هر مرحله
#      یعنی کشتنِ N بار از یه دشمنِ مشخص (از همون kill_log که همه‌جای
#      بازی همین الان هم ثبت می‌شه). با کامل شدنِ هر مرحله، یه پاداشِ
#      Zen/XP کاملاً اختصاصی (که از هیچ مسیرِ دیگه‌ای گیر نمیاد) +
#      یه توانایی/باف دائمیِ کوچیک باز می‌شه.
#
#   ۲) این باف‌ها (get_hunt_bonuses) دقیقاً مثلِ ست‌ها/مُهرها/آیتم‌ها
#      باید قاطیِ setb بشن — این وایرینگ تو combat.py (دمیج) و
#      mob_combat.py + combat_handlers.py (zen/xp) انجام می‌شه.
# ============================================================
import time

# هر مرحله: enemy (باید دقیقاً کلیدِ ENEMIES تو combat.py باشه)، need (تعداد کشتار لازم)،
# zen/xp پاداشِ یک‌بارِ کلایم، ability_id/label برای نمایش، effect برای باف دائمی.
HUNT_LINE = [
    {
        "id": "hq1", "title": "شکارچیِ مبتدی",
        "enemy": "🐗 کاراگ", "need": 20,
        "zen": 3000, "xp": 400,
        "ability_label": "🗡️ ضربه‌ی اول (+2% آسیب)",
        "effect": {"dmg_pct": 0.02},
    },
    {
        "id": "hq2", "title": "شکارِ خرسِ پیر",
        "enemy": "🐻 دِرگون، پیرِ جنگل", "need": 10,
        "zen": 6000, "xp": 800,
        "ability_label": "🎯 چشمِ شکارچی (+3% کریتیکال)",
        "effect": {"crit_pct": 0.03},
    },
    {
        "id": "hq3", "title": "گرگ‌کُشِ یخبندان",
        "enemy": "🐺 فِنراک", "need": 15,
        "zen": 10000, "xp": 1300,
        "ability_label": "❄️ رگِ سرد (+2% خون‌آشامی)",
        "effect": {"lifesteal_pct": 0.02},
    },
    {
        "id": "hq4", "title": "قلبِ یخِ زمهریر",
        "enemy": "🧊 زمهریر، دلِ یخ", "need": 8,
        "zen": 18000, "xp": 2200,
        "ability_label": "🛡️ پوستِ سخت (+3% دفاع)",
        "effect": {"defense_pct": 0.03},
    },
    {
        "id": "hq5", "title": "چشمِ خلأ",
        "enemy": "👁️ زیراکس", "need": 12,
        "zen": 30000, "xp": 3500,
        "ability_label": "⚔️ خشمِ شکار (+3% آسیب)",
        "effect": {"dmg_pct": 0.03},
    },
    {
        "id": "hq6", "title": "شعله‌یِ کوره‌شیطان",
        "enemy": "👿 ایگناروث، کوره‌شیطان", "need": 10,
        "zen": 50000, "xp": 5000,
        "ability_label": "🔥 اقبالِ شکارچی (+4% Zen از کشتار)",
        "effect": {"zen_pct": 0.04},
    },
    {
        "id": "hq7", "title": "اژدهاکُشِ اوج",
        "enemy": "🐉 درایکو", "need": 8,
        "zen": 80000, "xp": 8000,
        "ability_label": "📚 خردِ نبرد (+4% XP از کشتار)",
        "effect": {"xp_pct": 0.04},
    },
    {
        "id": "hq8", "title": "شبحِ دروازه‌ی مرگ",
        "enemy": "👹 بلاک‌هورن", "need": 10,
        "zen": 130000, "xp": 12000,
        "ability_label": "🎯 دقتِ نهایی (+4% کریتیکال)",
        "effect": {"crit_pct": 0.04},
    },
    {
        "id": "hq9", "title": "لویاثانِ کهن",
        "enemy": "🐋 لویاثانِ کهن، مویرا", "need": 5,
        "zen": 220000, "xp": 18000,
        "ability_label": "🌊 خون‌آشامیِ عمیق (+3% خون‌آشامی)",
        "effect": {"lifesteal_pct": 0.03},
    },
    {
        "id": "hq10", "title": "شاهِ اژدهایان",
        "enemy": "👑 وایرمگدون، شاهِ اژدها", "need": 5,
        "zen": 400000, "xp": 30000,
        "ability_label": "👑 لقبِ شکارچیِ اعظم (+6% آسیب، +6% کریتیکال)",
        "effect": {"dmg_pct": 0.06, "crit_pct": 0.06},
    },
]

_HUNT_BY_ID = {q["id"]: q for q in HUNT_LINE}


def _kills_of(player: dict, enemy_name: str) -> int:
    return player.get("kill_log", {}).get(enemy_name, 0)


def hunt_progress(player: dict) -> list[dict]:
    """برای هر مرحله وضعیت الان رو برمی‌گردونه: کشتارِ فعلی/لازم، کلایم‌شده یا نه، قابلِ کلایم یا نه."""
    claimed = set(player.get("hunt_claimed", []))
    out = []
    for q in HUNT_LINE:
        have = _kills_of(player, q["enemy"])
        is_claimed = q["id"] in claimed
        out.append({
            **q,
            "have": have,
            "claimed": is_claimed,
            "claimable": (not is_claimed) and have >= q["need"],
        })
    return out


def claim_hunt_reward(player: dict, quest_id: str) -> dict | None:
    """اگه مرحله‌ی quest_id قابلِ کلایمه، پاداشش رو می‌ده و برمی‌گردونه. وگرنه None."""
    q = _HUNT_BY_ID.get(quest_id)
    if not q:
        return None
    claimed = player.setdefault("hunt_claimed", [])
    if quest_id in claimed:
        return None
    if _kills_of(player, q["enemy"]) < q["need"]:
        return None
    claimed.append(quest_id)
    player["zen"] = player.get("zen", 0) + q["zen"]
    player["xp"] = player.get("xp", 0) + q["xp"]
    unlocked = player.setdefault("hunt_abilities", [])
    if quest_id not in unlocked:
        unlocked.append(quest_id)
    # باگ‌فیکس: چون database.py این فیلد رو None می‌سازه (نه {})، .get(..., {})
    # وقتی کلید از قبل با مقدار None وجود داشت، پیش‌فرض رو اعمال نمی‌کرد و
    # خط بعدی با TypeError ('NoneType' object does not support item assignment) کرش می‌کرد.
    player["hunt_claimed_at"] = player.get("hunt_claimed_at") or {}
    player["hunt_claimed_at"][quest_id] = time.time()
    return q


def get_hunt_bonuses(player: dict) -> dict:
    """dict تخت از باف‌های تجمعیِ توانایی‌های بازشده — دقیقاً هم‌شکلِ setb/eqb."""
    bonuses = {}
    unlocked = set(player.get("hunt_abilities", []))
    for qid in unlocked:
        q = _HUNT_BY_ID.get(qid)
        if not q:
            continue
        for k, v in q.get("effect", {}).items():
            bonuses[k] = bonuses.get(k, 0) + v
    return bonuses


def next_hunt_hint(player: dict) -> str | None:
    """اولین مرحله‌ای که هنوز کلایم نشده رو برمی‌گردونه (برای نمایش تو پنلِ حمله)."""
    for q in hunt_progress(player):
        if not q["claimed"]:
            if q["claimable"]:
                return f"✅ **{q['title']}** آماده‌ی کلایمه! (📜 کوئست حمله رو بزن)"
            return f"🎯 **{q['title']}**: {q['have']}/{q['need']} × {q['enemy']}"
    return None
