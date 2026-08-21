# ============================================================
#  ASTRAL ABYSS — Weekly Rewards (Leaderboard + PvP Season)
# ------------------------------------------------------------
#  هر هفته (هر ۷ روز) دو تا چیز اتفاق می‌افته:
#   ۱) نفر اولِ رده‌بندیِ کلی (همون چیزی که «🏆 رده‌بندی» نشون می‌ده:
#      بیشترین سطح، بعد بیشترین XP) یه جایزه‌ی Zen می‌گیره.
#   ۲) فصل PvP هفتگی تموم می‌شه: نفراتِ برترِ pvp_season_points جایزه
#      می‌گیرن و امتیازِ فصلی همه صفر می‌شه تا فصلِ بعد از صفر شروع بشه
#      (رنکِ همیشگی/pvp_points دست‌نخورده می‌مونه — این یکی permanent-ه).
#
#  چون ربات با polling (نه webhook) کار می‌کنه، این با یه حلقه‌ی
#  asyncio بی‌نهایت پیاده شده که هر ساعت چک می‌کنه آیا یه هفته گذشته یا نه.
# ============================================================
import asyncio
import time
from database import asave_player

WEEK_SECONDS = 7 * 86400
CHECK_INTERVAL = 3600  # هر ساعت یه بار چک کن

TOP_LEADERBOARD_REWARD = 30_000   # Zen برای نفر اولِ رده‌بندیِ کلی
PVP_SEASON_REWARDS = [50_000, 25_000, 10_000]  # نفر ۱ / ۲ / ۳ فصل PvP


async def _run_once(bot):
    from database import all_players, save_player, system_col

    players = all_players()
    if not players:
        return

    # ─── ۱) نفر اولِ رده‌بندیِ کلی ───────────────────────────
    top_overall = sorted(
        players.items(),
        key=lambda kv: (kv[1].get("level", 1), kv[1].get("xp", 0)),
        reverse=True
    )
    if top_overall:
        uid_str, p = top_overall[0]
        uid = int(uid_str)
        p["zen"] = p.get("zen", 0) + TOP_LEADERBOARD_REWARD
        p["weekly_champion_count"] = p.get("weekly_champion_count", 0) + 1
        await asave_player(uid, p)
        try:
            await bot.send_message(
                uid,
                f"👑 **قهرمانِ هفته شدی!**\n\n"
                f"نفر اولِ رده‌بندیِ کلی این هفته بودی (Lv.{p.get('level',1)}).\n"
                f"🎁 جایزه: +{TOP_LEADERBOARD_REWARD:,} Zen\n"
                f"🏆 تعداد دفعاتِ قهرمانی: {p['weekly_champion_count']}"
            )
        except Exception:
            pass

    # ─── ۲) فصل PvP هفتگی — سیزن‌پسِ کامل ───────────────────
    # قبلاً فقط ۳ نفرِ اولِ کل سرور جایزه می‌گرفتن و بقیه فقط ریست
    # می‌شدن؛ الان: شماره‌ی فصل نگه داشته می‌شه، هر شرکت‌کننده‌ای
    # بر اساسِ لیگِ نهایی‌ش (نه فقط تاپ ۳) جایزه می‌گیره، تاریخچه‌ی
    # فصل‌های قبلی رو خودِ پروفایل رو نگه می‌داره، و یه بجِ
    # «آخرین فصل» می‌مونه که تو پروفایل/رنک نشون داده می‌شه.
    from pvp import league_for_points, season_reward_for_league
    from database import system_col

    season_doc = system_col().find_one({"_id": "pvp_season_meta"}) or {"_id": "pvp_season_meta", "season_num": 0}
    season_num = season_doc.get("season_num", 0) + 1
    system_col().update_one({"_id": "pvp_season_meta"}, {"$set": {"season_num": season_num}}, upsert=True)

    top_pvp = sorted(
        players.items(),
        key=lambda kv: kv[1].get("pvp_season_points", 0),
        reverse=True
    )
    top_pvp = [(uid, p) for uid, p in top_pvp if p.get("pvp_season_points", 0) > 0]

    for i, (uid_str, p) in enumerate(top_pvp):
        uid = int(uid_str)
        season_pts = p.get("pvp_season_points", 0)
        league = league_for_points(season_pts)
        rank = i + 1
        reward = season_reward_for_league(league)
        if rank <= 3:
            reward += PVP_SEASON_REWARDS[rank - 1]   # بونوسِ اضافه‌ی تاپ ۳ رو کل سرور

        p["zen"] = p.get("zen", 0) + reward
        p["pvp_last_season_league"] = league
        p["pvp_last_season_points"] = season_pts
        p["pvp_last_season_rank"] = rank if rank <= 100 else None

        hist = p.setdefault("pvp_season_history", [])
        hist.append({"season": season_num, "league": league, "points": season_pts,
                     "rank": rank, "reward": reward})
        p["pvp_season_history"] = hist[-10:]   # فقط ۱۰ فصلِ آخر نگه داشته می‌شه

        await asave_player(uid, p)

        # فقط تاپ ۱۰ پیام مستقیم می‌گیرن — بقیه بی‌سروصدا جایزه‌شون رو تو /pvpseason می‌بینن
        if rank <= 10:
            try:
                await bot.send_message(
                    uid,
                    f"🏁 **پایانِ فصل #{season_num} PvP!**\n\n"
                    f"رتبه‌ی #{rank} فصل رو کسب کردی — {league} ({season_pts:,} امتیازِ فصلی).\n"
                    f"🎁 جایزه: +{reward:,} Zen\n"
                    f"از /pvpseason می‌تونی تاریخچه‌ی فصل‌هات رو ببینی."
                )
            except Exception:
                pass

    # ریست امتیازِ فصلیِ همه (فصل جدید از صفر شروع می‌شه)
    for uid_str, p in players.items():
        if p.get("pvp_season_points", 0) != 0:
            p["pvp_season_points"] = 0
            await asave_player(int(uid_str), p)

    system_col().update_one(
        {"_id": "weekly_reward"},
        {"$set": {"last_run": time.time()}},
        upsert=True
    )


async def weekly_rewards_loop(bot):
    from database import system_col
    while True:
        try:
            doc = system_col().find_one({"_id": "weekly_reward"})
            last_run = doc.get("last_run", 0) if doc else 0
            if last_run == 0:
                # اولین بار — فقط زمان رو ثبت کن، جایزه نده (تا هفته‌ی اول کامل بگذره)
                system_col().update_one(
                    {"_id": "weekly_reward"},
                    {"$set": {"last_run": time.time()}},
                    upsert=True
                )
            elif time.time() - last_run >= WEEK_SECONDS:
                await _run_once(bot)
                _advance_weekly_boss()
        except Exception:
            pass
        await asyncio.sleep(CHECK_INTERVAL)


# ─── چرخشِ باسِ هفته ────────────────────────────────────────────
def _advance_weekly_boss():
    """هر هفته یه باسِ جدید از لیستِ باس‌های جهانی به‌عنوانِ «باسِ هفته»
    انتخاب می‌شه (چرخشیه، نه رندوم، تا هیچ باسی خیلی دیر نیاد)."""
    from database import system_col
    from boss_engine import WORLD_BOSS_TEMPLATES
    ids = list(WORLD_BOSS_TEMPLATES.keys())
    if not ids:
        return
    doc = system_col().find_one({"_id": "weekly_boss"})
    idx = (doc.get("index", -1) + 1) % len(ids) if doc else 0
    system_col().update_one(
        {"_id": "weekly_boss"},
        {"$set": {"index": idx, "template_id": ids[idx]}},
        upsert=True
    )


def get_weekly_featured_boss_id() -> str:
    """template_id باسِ هفته‌ی جاری رو برمی‌گردونه. اگه هنوز هیچ چرخشی
    انجام نشده (اولین هفته‌ی کاری ربات)، اولین باسِ لیست رو پیش‌فرض می‌ذاره."""
    from database import system_col
    from boss_engine import WORLD_BOSS_TEMPLATES
    doc = system_col().find_one({"_id": "weekly_boss"})
    ids = list(WORLD_BOSS_TEMPLATES.keys())
    if not ids:
        return ""
    if not doc or doc.get("template_id") not in WORLD_BOSS_TEMPLATES:
        first = ids[0]
        system_col().update_one(
            {"_id": "weekly_boss"},
            {"$set": {"index": 0, "template_id": first}},
            upsert=True
        )
        return first
    return doc["template_id"]
