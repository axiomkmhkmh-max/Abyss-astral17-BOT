# ============================================================
#  ASTRAL ABYSS — Hidden Stat Awakening 💫 (بیداریِ استتِ مخفی)
# ------------------------------------------------------------
#  یه‌بار در کلِ بازی، وقتی بازیکن تو نبرد خیلی نزدیکِ مرگ می‌شه
#  (زیرِ یه درصدِ مشخص از max_hp)، یه شانسِ کوچیک هست یه «استتِ
#  مخفی» توش بیدار بشه — یه بونوسِ دائمیِ رندوم که مستقیم رو
#  player["stats"] اعمال می‌شه (دقیقاً مثلِ بونوسِ تکامل، از همون
#  مسیرِ سازگاریِ hp/max_hp که class_system.py استفاده می‌کنه).
#  بعد از اولین بیداری، دیگه هیچ‌وقت رول نمی‌شه (فلگِ
#  player["hidden_awakening"] دائمیه).
#
#  خالص/بدون aiogram — قلاب به مبارزه از mob_combat.py صدا زده می‌شه.
# ============================================================
import random

NEAR_DEATH_HP_PCT = 0.15   # زیرِ ۱۵٪ از max_hp
TRIGGER_CHANCE = 0.08      # هر بار که شرط بالا برقرار باشه، ۸٪ شانس

HIDDEN_STATS = {
    "iron_heart": {
        "name": "🫀 دلِ آهنین", "flavor": "قلبت یه لحظه از تپش وایساد — و بعد قوی‌تر از قبل برگشت.",
        "bonus": {"max_hp": 80}, "power": 220,
    },
    "berserker_vein": {
        "name": "🩸 رگِ خشم", "flavor": "خون تو رگ‌هات جوشید — دیگه هیچ ضربه‌ای انقدر دردناک نیست.",
        "bonus": {"atk": 22}, "power": 220,
    },
    "diamond_skin": {
        "name": "💎 پوستِ الماسی", "flavor": "لحظه‌ی آخر، بدنت خودش رو سخت‌تر از سنگ کرد.",
        "bonus": {"def": 22}, "power": 220,
    },
    "phoenix_pulse": {
        "name": "🔥 ضربانِ ققنوس", "flavor": "یه گرمای عجیب زیرِ پوستت — انگار چیزی نمی‌ذاره واقعاً بمیری.",
        "bonus": {"max_hp": 40, "atk": 10, "def": 10}, "power": 220,
    },
}


def has_awakened(player: dict) -> bool:
    return bool(player.get("hidden_awakening"))


def _is_near_death(player: dict) -> bool:
    max_hp = player.get("max_hp", 100)
    if max_hp <= 0:
        return False
    return (player.get("hp", 100) / max_hp) <= NEAR_DEATH_HP_PCT


def maybe_awaken(player: dict) -> dict | None:
    """صدا زده می‌شه بعدِ هر ضربه‌ی دریافتی تو نبرد. اگه شرایط جور بشه و
    رندوم برنده بشه، یه‌بار برای همیشه یه استتِ مخفی رو باز می‌کنه و
    دیکشنریِ {"msg": ...} برمی‌گردونه؛ در غیرِ این‌صورت None."""
    if has_awakened(player):
        return None
    if not _is_near_death(player):
        return None
    if random.random() > TRIGGER_CHANCE:
        return None

    stat_id = random.choice(list(HIDDEN_STATS.keys()))
    stat = HIDDEN_STATS[stat_id]
    bonus = stat["bonus"]

    stats = player.setdefault("stats", {"hp": player.get("max_hp", 100), "max_hp": player.get("max_hp", 100),
                                         "atk": 10, "def": 5})
    stats["atk"] = stats.get("atk", 10) + bonus.get("atk", 0)
    stats["def"] = stats.get("def", 5) + bonus.get("def", 0)
    hp_gain = bonus.get("max_hp", 0)
    if hp_gain:
        stats["max_hp"] = stats.get("max_hp", 100) + hp_gain
        stats["hp"] = stats.get("hp", stats["max_hp"]) + hp_gain
        player["max_hp"] = player.get("max_hp", 100) + hp_gain
        player["hp"] = player.get("hp", player["max_hp"]) + hp_gain

    player["hidden_awakening"] = {"id": stat_id, "name": stat["name"]}

    bonus_bits = []
    if bonus.get("atk"): bonus_bits.append(f"⚔️ +{bonus['atk']} حمله")
    if bonus.get("def"): bonus_bits.append(f"🛡 +{bonus['def']} دفاع")
    if bonus.get("max_hp"): bonus_bits.append(f"❤️ +{bonus['max_hp']} HP")

    msg = (
        f"\n\n💫💫💫 **یه چیزی درونت بیدار شد!** 💫💫💫\n"
        f"_{stat['flavor']}_\n\n"
        f"✨ استتِ مخفی: **{stat['name']}**\n"
        f"{' | '.join(bonus_bits)}\n"
        f"_(این یه‌بار در کلِ بازیت اتفاق افتاد — دائمیه.)_"
    )
    return {"msg": msg, "stat_id": stat_id}


def awakening_power_bonus(player: dict) -> float:
    """سهمِ بیداری برای Combat Power (combat_power.py)."""
    if not has_awakened(player):
        return 0.0
    stat_id = player.get("hidden_awakening", {}).get("id")
    stat = HIDDEN_STATS.get(stat_id)
    return float(stat["power"]) if stat else 0.0


def status_text(player: dict) -> str:
    if not has_awakened(player):
        return (
            "💫 **بیداریِ استتِ مخفی**\n\n"
            "هنوز چیزی درونت بیدار نشده. بعضی‌وقتا، تو لحظه‌ای که نزدیکِ مرگی، "
            "یه چیزِ نهفته ممکنه خودش رو نشون بده... اما نمی‌تونی مجبورش کنی."
        )
    info = player["hidden_awakening"]
    stat = HIDDEN_STATS.get(info["id"], {})
    return (
        f"💫 **بیداریِ استتِ مخفی**\n\n"
        f"✨ {stat.get('name', info.get('name','?'))}\n"
        f"_{stat.get('flavor','')}_"
    )
