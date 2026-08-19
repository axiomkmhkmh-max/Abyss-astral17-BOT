# ============================================================
#  ASTRAL ABYSS — Achievements & Titles System
# ------------------------------------------------------------
#  این سیستم قبلاً هیچ‌جا واقعاً پیاده نشده بود — فقط یه کامنت تو
#  combat_power.py بود که می‌گفت «فاز بعدی، فعلاً fallback امن».
#  فیلد player["titles_unlocked"] از قبل تو database.py و
#  combat_power.py تعریف شده بود ولی هیچ‌کس واقعاً پرش نمی‌کرد —
#  همون فیلد رو اینجا واقعاً استفاده می‌کنیم (یعنی Combat Power هم
#  خودکار از این دستاوردها تأثیر می‌گیره، بدون نیاز به تغییر جای دیگه).
# ============================================================

# هر دستاورد: id یکتا -> {title (متنی که به titles_unlocked اضافه می‌شه),
# desc (توضیح برای /دستاوردها), check(player)->bool}
ACHIEVEMENTS = {
    "kills_10":      {"title": "🗡 شکارچی مبتدی",    "desc": "۱۰ دشمن رو شکست بده",
                       "check": lambda p: p.get("kills", 0) >= 10},
    "kills_100":     {"title": "⚔️ قصاب سایه‌ها",     "desc": "۱۰۰ دشمن رو شکست بده",
                       "check": lambda p: p.get("kills", 0) >= 100},
    "kills_500":     {"title": "💀 آقای مرگ",         "desc": "۵۰۰ دشمن رو شکست بده",
                       "check": lambda p: p.get("kills", 0) >= 500},
    "level_10":      {"title": "🌱 تازه‌کار",         "desc": "به سطح ۱۰ برس",
                       "check": lambda p: p.get("level", 1) >= 10},
    "level_50":      {"title": "🔥 جنگجوی باتجربه",  "desc": "به سطح ۵۰ برس",
                       "check": lambda p: p.get("level", 1) >= 50},
    "level_100":     {"title": "👑 اسطوره",           "desc": "به سطح ۱۰۰ برس",
                       "check": lambda p: p.get("level", 1) >= 100},
    "pvp_10":        {"title": "🆚 مبارز آزموده",     "desc": "۱۰ برد PvP کسب کن",
                       "check": lambda p: p.get("pvp_wins", 0) >= 10},
    "pvp_50":        {"title": "🏆 قهرمان آرنا",      "desc": "۵۰ برد PvP کسب کن",
                       "check": lambda p: p.get("pvp_wins", 0) >= 50},
    "pvp_streak_5":  {"title": "⚡ سریِ برنده",        "desc": "۵ برد پشت‌سرهم تو PvP",
                       "check": lambda p: p.get("pvp_best_streak", 0) >= 5},
    "boss_hunter":   {"title": "🐉 نابودگر باس‌ها",    "desc": "۵ باس منطقه رو شکست بده",
                       "check": lambda p: len(p.get("area_bosses_killed", [])) >= 5},
    "loot_streak_10":{"title": "💎 شکارچی گنج",        "desc": "استریک لوت رو به ۱۰ برسون",
                       "check": lambda p: p.get("loot_best_streak", 0) >= 10},
    "guild_member":  {"title": "🏛 عضو گیلد",          "desc": "به یه گیلد بپیوند",
                       "check": lambda p: bool(p.get("guilds"))},
    "rich_1m":       {"title": "💰 ثروتمند",           "desc": "۱ میلیون Zen جمع کن",
                       "check": lambda p: p.get("zen", 0) >= 1_000_000},
    "rebirth_1":     {"title": "🔄 تولد دوباره",       "desc": "یک بار Rebirth کن",
                       "check": lambda p: p.get("rebirth_count", 0) >= 1},
}


def check_achievements(player: dict) -> list[str]:
    """
    شرط تمام دستاوردهای هنوز-باز-نشده رو چک می‌کنه؛ هر کدوم که شرطش برآورده
    شده باشه رو به player["titles_unlocked"] اضافه می‌کنه و برمی‌گردونه
    (تا هندلرِ صداکننده بتونه پیام «🏅 دستاورد جدید!» رو نشون بده).
    ایمنه که هر بار صدا زده بشه — دستاوردِ تکراری اضافه نمی‌شه.
    """
    unlocked = player.setdefault("titles_unlocked", [])
    newly = []
    for ach_id, ach in ACHIEVEMENTS.items():
        if ach_id in player.get("achievements_done", []):
            continue
        try:
            done = ach["check"](player)
        except Exception:
            done = False
        if done:
            player.setdefault("achievements_done", []).append(ach_id)
            if ach["title"] not in unlocked:
                unlocked.append(ach["title"])
            newly.append(ach["title"])
    return newly


def achievements_list_text(player: dict) -> str:
    done_ids = set(player.get("achievements_done", []))
    lines = ["🏅 **دستاوردها**\n"]
    for ach_id, ach in ACHIEVEMENTS.items():
        mark = "✅" if ach_id in done_ids else "🔒"
        lines.append(f"{mark} {ach['title']} — {ach['desc']}")
    unlocked_count = len(done_ids)
    lines.append(f"\n📊 {unlocked_count}/{len(ACHIEVEMENTS)} باز شده")
    return "\n".join(lines)
