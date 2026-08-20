# ============================================================
#  ASTRAL ABYSS — Isekai Personas 🌟 (عنوان‌های طنزآمیزِ ایسکای)
# ------------------------------------------------------------
#  یه لایه‌ی سبک روی titles_system.py: عنوان‌هایی که با رفرنس به
#  تروپ‌های کلاسیکِ ایسکای باز می‌شن (بازمانده‌ی کامیون، قهرمانِ
#  برگزیده، بازتولدیافته...). هیچ مکانیزمِ سنگینی نداره — فقط چک
#  می‌کنه شرایطِ ساده‌ای که از قبل تو player هست برقرارن یا نه.
# ============================================================

PERSONAS = {
    "truck_survivor":    {"title": "🚚 بازمانده‌ی کامیون",     "check": lambda p: p.get("isekai_truck_hits", 0) >= 1},
    "goddess_chosen":     {"title": "✨ برگزیده‌ی الهه",         "check": lambda p: p.get("goddess_favor", 0) >= 60},
    "cheat_wielder":      {"title": "⚡ دارنده‌ی چیت‌اسکیل",     "check": lambda p: bool(p.get("goddess_cheat_skill"))},
    "isekai_protagonist": {"title": "🌟 قهرمانِ ایسکای",         "check": lambda p: p.get("level", 1) >= 30},
    "reincarnated_hero":  {"title": "♻️ باز-تولدیافته",         "check": lambda p: p.get("rift_best_depth", 0) >= 20},
    "demon_lord_slayer":  {"title": "👹 قاتلِ لردِ شیاطین",       "check": lambda p: bool(p.get("boss_titles"))},
    "op_from_start":      {"title": "🎴 از اول قدرتمند",         "check": lambda p: p.get("level", 1) >= 60},
    "slime_reborn":       {"title": "🟢 بازتولدِ اسلایمی",       "check": lambda p: p.get("owned_mounts") and len(p["owned_mounts"]) >= 5},
}


def check_and_grant_personas(player: dict) -> list[str]:
    """همه‌ی شرط‌ها رو چک می‌کنه، عنوان‌های جدید رو به isekai_titles اضافه
    می‌کنه و لیستِ تازه‌بازشده‌ها رو برمی‌گردونه (برای اعلان به بازیکن)."""
    unlocked = player.setdefault("isekai_titles", [])
    newly = []
    for pid, data in PERSONAS.items():
        title = data["title"]
        if title in unlocked:
            continue
        try:
            if data["check"](player):
                unlocked.append(title)
                newly.append(title)
        except Exception:
            continue
    return newly
