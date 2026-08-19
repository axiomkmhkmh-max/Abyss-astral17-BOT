# ============================================================
#  ASTRAL ABYSS — REGION BOSS SYSTEM
# ------------------------------------------------------------
#  باسِ چندنفره‌ی مخصوصِ هر «مپ» (نه هر گروه/چت). دقیقاً از همون
#  موتور boss_engine.py (فازها، عناصر، مکانیک شیلد/ناحیه/خشم،
#  پاداشِ رتبه‌ای عادلانه) استفاده می‌کنه — فقط ذخیره‌سازی به‌جای
#  chat_id، به‌ازای map_name جداست.
#
#  چرا جدا از group_bosses؟ چون بازی عمدتاً تو چتِ خصوصیِ هر
#  بازیکن جریان داره (نه گروه) — پلیرها هرکدوم تو چتِ خودشون
#  می‌رن سراغِ یه مپ. یه باسِ منطقه‌ای باید بینِ همه‌ی بازیکن‌هایی
#  که (تو هر چتی) اون مپ رو دارن، مشترک باشه؛ برخلافِ باسِ گروهی
#  که فقط مالِ اعضای همون گروهه.
#
#  هر مپ در یک لحظه فقط یه باسِ زنده داره. بعدِ کشتنش، یه
#  کول‌داون کوتاه قبلِ اسپاونِ بعدی می‌گذره تا مپ خالی نمونه ولی
#  اسپم هم نشه.
# ============================================================
import random
import time
from pymongo.collection import Collection

from database import get_db

REGION_BOSS_RESPAWN_COOLDOWN = 900  # ۱۵ دقیقه بعدِ کشتنِ باسِ یه مپ، تا باسِ بعدی

# مقیاسِ HP باسِ منطقه‌ای نسبت به باسِ جهانی — چون معمولاً تعدادِ کمتری از
# بازیکن‌ها هم‌زمان رو یه مپِ خاص جمع می‌شن تا رویِ باسِ جهانی/گروهیِ بزرگ
REGION_BOSS_HP_SCALE = 0.55


def region_boss_col() -> Collection:
    return get_db()["region_bosses"]


def get_region_boss(map_name: str) -> dict | None:
    doc = region_boss_col().find_one({"_id": map_name})
    if not doc:
        return None
    doc.pop("_id", None)
    return doc


def save_region_boss(map_name: str, boss: dict):
    data = {k: v for k, v in boss.items() if k != "_id"}
    region_boss_col().update_one({"_id": map_name}, {"$set": data}, upsert=True)


def mark_region_boss_killed(map_name: str):
    region_boss_col().update_one(
        {"_id": map_name},
        {"$set": {"alive": False, "_last_killed_at": time.time()}},
        upsert=True,
    )


def region_boss_cooldown_remaining(map_name: str) -> int:
    doc = region_boss_col().find_one({"_id": map_name})
    if not doc:
        return 0
    last_killed = doc.get("_last_killed_at")
    if not last_killed:
        return 0
    remain = int(last_killed + REGION_BOSS_RESPAWN_COOLDOWN - time.time())
    return max(0, remain)


def spawn_region_boss(map_name: str, template_id: str | None = None) -> dict:
    """یه باسِ تازه‌ی مخصوصِ این مپ می‌سازه (HP مقیاس‌شده، بقیه دقیقاً طبقِ
    boss_engine). اگه بازیکن‌های زیادی هم‌زمان دستِ‌به‌دست باهاش بجنگن،
    سریع‌تر از باسِ جهانی/گروهی جواب می‌ده — چون معمولاً یه گروهِ کوچیکن."""
    import boss_engine as be
    if not template_id or template_id not in be.WORLD_BOSS_TEMPLATES:
        template_id = random.choice(list(be.WORLD_BOSS_TEMPLATES.keys()))
    boss = be.spawn_boss(template_id, chat_id=0)  # chat_id بی‌معنیه؛ همه از پی‌وی خودشون می‌زنن

    # 🩹 نکته: boss_engine._start_phase مقدارِ phase_hp رو از رویِ
    # WORLD_BOSS_TEMPLATES[...]["total_hp"] (ثابت) می‌سازه، نه از رویِ
    # boss["total_hp"] — پس صرفِ ست‌کردنِ boss["total_hp"] کافی نیست؛
    # باید همه‌ی فیلدهای HP-محورِ فازِ تازه‌ساخته‌شده رو دستی مقیاس کنیم.
    scale = REGION_BOSS_HP_SCALE
    boss["total_hp"] = max(1, int(boss["total_hp"] * scale))
    boss["phase_max_hp"] = max(1, int(boss["phase_max_hp"] * scale))
    boss["hp"] = boss["phase_max_hp"]
    if boss.get("mechanic") == "shield" and boss.get("shield_max"):
        boss["shield_max"] = max(1, int(boss["shield_max"] * scale))
        boss["shield_hp"] = boss["shield_max"]

    boss["map_name"] = map_name
    boss["invited_uids"] = []  # کسانی که با /binvite دعوت شدن (فقط برای نمایش؛ باسِ منطقه‌ای اصلاً برای همه بازه)
    save_region_boss(map_name, boss)
    return boss


def list_active_region_bosses() -> list[dict]:
    out = []
    for doc in region_boss_col().find({"alive": True}):
        map_name = doc.pop("_id")
        doc["map_name"] = map_name
        out.append(doc)
    return out


def top_contributors(boss: dict, n: int = 3) -> list[tuple[int, int]]:
    contributors = boss.get("contributors", {})
    ranked = sorted(contributors.items(), key=lambda kv: kv[1].get("dmg", 0), reverse=True)
    return [(int(uid), c.get("dmg", 0)) for uid, c in ranked[:n]]
