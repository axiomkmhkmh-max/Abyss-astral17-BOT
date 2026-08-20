# ============================================================
#  ASTRAL ABYSS RPG — صفحه‌ی یکپارچه‌ی عنوان‌ها 🏅
#  عنوان از منابع مختلفی میاد: دستاوردها (achievements.py)،
#  خرید از گیلد (guild_system.py) که همه تو titles_unlocked
#  می‌ریزن، نمسیس (nemesis_titles) و مُهرهای الهی (divine_seals).
#  این ماژول همه رو یه‌جا جمع می‌کنه و به بازیکن اجازه می‌ده
#  یکیشو برای نمایشِ روی کارتِ پروفایل انتخاب کنه.
# ============================================================
from typing import Optional


def collect_titles(player: dict) -> list[dict]:
    """همه‌ی عنوان‌های در دسترسِ این پلیر رو از منابعِ مختلف جمع می‌کنه،
    با حفظِ ترتیب و بدون تکرار."""
    seen = set()
    titles: list[dict] = []

    def _add(title: Optional[str], source: str):
        if not title or title in seen:
            return
        seen.add(title)
        titles.append({"title": title, "source": source})

    for t in player.get("titles_unlocked", []):
        _add(t, "دستاورد / گیلد")

    for t in player.get("nemesis_titles", []):
        _add(t, "نمسیس")

    for t in player.get("fog_titles", []):
        _add(t, "اکتشاف")

    for t in player.get("underground_titles", []):
        _add(t, "حلقه‌ی سایه")

    for t in player.get("pet_titles", []):
        _add(t, "همراه")

    for t in player.get("boss_titles", []):
        _add(t, "شکارِ باس")

    for t in player.get("isekai_titles", []):
        _add(t, "ایسکای")

    try:
        from divine_seals import get_seal_title
        _add(get_seal_title(player), "مُهرِ الهی")
    except ImportError:
        pass

    return titles


def get_active_title(player: dict) -> Optional[str]:
    """عنوانی که الان باید رو پروفایل نشون داده بشه: انتخابِ صریحِ بازیکن،
    وگرنه رفتارِ قدیمی (مُهرِ الهی در اولویت، بعد آخرین عنوانِ باز‌شده)."""
    available = [t["title"] for t in collect_titles(player)]
    chosen = player.get("active_title")
    if chosen and chosen in available:
        return chosen

    try:
        from divine_seals import get_seal_title
        seal_title = get_seal_title(player)
        if seal_title:
            return seal_title
    except ImportError:
        pass

    unlocked = player.get("titles_unlocked", [])
    return unlocked[-1] if unlocked else None


def set_active_title(player: dict, title: str) -> bool:
    available = [t["title"] for t in collect_titles(player)]
    if title not in available:
        return False
    player["active_title"] = title
    return True


def clear_active_title(player: dict):
    """برگشت به رفتارِ خودکار (آخرین عنوانِ باز‌شده / مُهرِ الهی)."""
    player.pop("active_title", None)
