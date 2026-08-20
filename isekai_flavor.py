# ============================================================
#  ASTRAL ABYSS — Isekai Flavor 🚚🗣 (حسِ زنده‌بودنِ دنیا)
# ------------------------------------------------------------
#  دو رخدادِ سبک و پرتکرار که هیچ ربطی به تعادلِ بازی ندارن، فقط
#  حسِ «این دنیا داره بدونِ من هم اتفاق می‌افته» رو می‌سازن:
#
#  ۱) Rumor Mill — هر چند وقت یه‌بار یه شایعه درباره‌ی یکی از
#     بازیکن‌های واقعیِ سرور (بر اساسِ رنکینگِ واقعیش) برای یه
#     گروهِ تصادفی از بازیکن‌ها فرستاده می‌شه.
#  ۲) Truck-kun — رفرنسِ کلاسیکِ ایسکای: به‌ندرت یه بازیکنِ رندوم
#     «توسطِ کامیون ایزکای می‌شه» و یه پکیجِ کوچیکِ رندوم می‌گیره.
#     هربار که این اتفاق بیفته، عنوانِ «🚚 بازمانده‌ی کامیون» هم
#     باز می‌شه (از isekai_personas.py).
# ============================================================
import asyncio
import random
import time

CHECK_INTERVAL = 1200          # هر ۲۰ دقیقه چک می‌شه
RUMOR_CHANCE = 0.5             # هر چک، ۵۰٪ شانسِ یه شایعه
TRUCK_KUN_CHANCE = 0.10        # هر چک، ۱۰٪ شانسِ یه ایزکای‌شدنِ تصادفی
RUMOR_AUDIENCE_SIZE = 20       # به چند نفرِ رندوم شایعه فرستاده می‌شه

RUMOR_TEMPLATES = [
    "🗣 شنیدم **{name}** (Lv.{level}) تنها یه باسِ جهانی رو زمین زده... باورت می‌شه؟",
    "🗣 تو بازار پچ‌پچ می‌کنن که **{name}** یه گنجینه‌ی نایاب پیدا کرده و کسی نمی‌دونه کجا قایمش کرده.",
    "🗣 یکی می‌گفت **{name}** تو فصلِ آرنا داره می‌ترکونه — لیگش {league}ه!",
    "🗣 پیرمردِ کارگزار امروز گفت اسمِ **{name}** رو تو گزارش‌های عجیب دیده. مراقب باش کی رو عصبانی می‌کنی.",
    "🗣 شایعه شده **{name}** وارد یه شکافِ Abyss شده و دیگه کسی خبری ازش نداره... تا الان.",
    "🗣 تو میخونه‌ی محلی، همه دارن درباره‌ی ثروتِ **{name}** حرف می‌زنن — {zen:,} Zen؟! واقعیه؟",
]

TRUCK_KUN_LINES = [
    "🚚💥 یهو یه کامیونِ عجیب از ناکجاآباد ظاهر شد... و بعدش دیگه چیزی یادت نمیاد.\nوقتی چشماتو باز کردی، یه چیزی همراهت بود که قبلاً نداشتی.",
    "🚚💥 «متاسفم، این یه اتفاقِ ایزکای‌کلاسیکه» — صدایی از جایی نامعلوم گفت. بعدش یه نورِ آبی و... خب، بیا ببین چی گیرت اومده.",
    "🚚💥 دنیا یه لحظه چرخید، یه کامیون، یه فلاش‌ِ نور، و حالا یه هدیه‌ی عجیب تو دستته.",
]


def _rumor_col():
    from database import system_col
    return system_col()


def _pick_rumor_subject() -> dict | None:
    from database import all_players
    players = list(all_players().items())
    if not players:
        return None
    # با شانسِ برابر بینِ «رنکِ سطح» و «رنکِ فصلِ PvP» یه موضوع انتخاب می‌کنیم
    if random.random() < 0.5:
        players.sort(key=lambda kv: kv[1].get("level", 1), reverse=True)
    else:
        players.sort(key=lambda kv: kv[1].get("pvp_season_points", 0), reverse=True)
    top_slice = players[:15] or players
    uid_str, p = random.choice(top_slice)
    return {"uid": int(uid_str), "player": p}


def _format_rumor(subject: dict) -> str:
    from pvp import league_for_points
    p = subject["player"]
    template = random.choice(RUMOR_TEMPLATES)
    return template.format(
        name=p.get("name", "یه مسافرِ ناشناس"),
        level=p.get("level", 1),
        zen=p.get("zen", 0),
        league=league_for_points(p.get("pvp_season_points", 0)),
    )


async def _run_rumor(bot):
    from database import all_players
    subject = _pick_rumor_subject()
    if not subject:
        return
    text = _format_rumor(subject)
    players = list(all_players().keys())
    if not players:
        return
    audience = random.sample(players, min(RUMOR_AUDIENCE_SIZE, len(players)))
    for uid_str in audience:
        try:
            await bot.send_message(int(uid_str), text)
        except Exception:
            pass
        await asyncio.sleep(0.05)


def truck_kun_reward(player: dict) -> str:
    """پکیجِ رندومِ کوچیکِ ایزکای‌شدن رو به پلیر می‌ده و متنِ خلاصه رو برمی‌گردونه.
    خودِ save_player رو کالر باید صدا بزنه."""
    player["isekai_truck_hits"] = player.get("isekai_truck_hits", 0) + 1

    roll = random.random()
    if roll < 0.4:
        zen = random.randint(400, 1200)
        player["zen"] = player.get("zen", 0) + zen
        gift = f"💰 +{zen:,} Zen"
    elif roll < 0.7:
        xp = random.randint(150, 400)
        player["xp"] = player.get("xp", 0) + xp
        gift = f"⭐ +{xp:,} XP"
    elif roll < 0.9:
        player["rift_shards"] = player.get("rift_shards", 0) + random.randint(2, 5)
        gift = "🔹 چند Echo Shard"
    else:
        player["goddess_favor"] = player.get("goddess_favor", 0) + random.randint(10, 20)
        gift = "🕊 لطفِ الهه‌ی آغازها بالا رفت"

    return f"{random.choice(TRUCK_KUN_LINES)}\n\n🎁 گرفتی: {gift}"


async def _run_truck_kun(bot):
    from database import all_players, get_player, save_player
    from bot import level_up_check
    from isekai_personas import check_and_grant_personas

    players = list(all_players().keys())
    if not players:
        return
    uid = int(random.choice(players))
    player = get_player(uid)
    if not player:
        return

    text = truck_kun_reward(player)
    player, leveled = level_up_check(player)
    if leveled:
        text += f"\n\n🎉 این هدیه باعث شد به سطح {player.get('level',1)} برسی!"

    newly = check_and_grant_personas(player)
    save_player(uid, player)

    if newly:
        text += "\n\n🏅 عنوانِ جدید: " + " | ".join(newly)

    try:
        await bot.send_message(uid, text)
    except Exception:
        pass


async def isekai_flavor_loop(bot):
    while True:
        try:
            if random.random() < RUMOR_CHANCE:
                await _run_rumor(bot)
            if random.random() < TRUCK_KUN_CHANCE:
                await _run_truck_kun(bot)
        except Exception:
            pass
        await asyncio.sleep(CHECK_INTERVAL)
