# ============================================================
#  ASTRAL ABYSS RPG — Level Gate 🔒
#  همون سطح‌بندیِ دکمه‌های bot.py (LEVEL_REQUIREMENTS)، ولی این‌بار
#  واقعی — رو خودِ هندلرها هم چک می‌شه، نه فقط UI. یعنی حتی اگه
#  یکی مستقیم از دستورِ اسلش (/shop, /casino, ...) استفاده کنه هم
#  نمی‌تونه قفل رو دور بزنه.
# ============================================================
LEVEL_REQUIREMENTS = {
    "boss": 5, "bounty": 5, "underground": 12,
    "guilds": 10, "team": 5, "pvp": 5, "trade": 10, "track": 5,
    "auction": 12, "casino": 10, "shop": 12, "contracts": 12,
    "house": 12, "mentor": 12, "exchange": 12,
}


def check_level(player: dict, feature_key: str) -> tuple[bool, str]:
    req = LEVEL_REQUIREMENTS.get(feature_key, 1)
    lvl = player.get("level", 1)
    if lvl < req:
        return False, f"🔒 این قابلیت از سطح {req} باز می‌شه (سطح فعلیِ تو: {lvl})."
    return True, ""
