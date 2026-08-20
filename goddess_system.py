# ============================================================
#  ASTRAL ABYSS — الهه‌ی آغازها 🕊 (Goddess of Beginnings)
# ------------------------------------------------------------
#  یه شخصیتِ ثابت و همیشگی، رفرنسِ کلاسیکِ «الهه‌ی تنظیم‌کننده‌ی
#  ایسکای». دعا می‌کنی، لطفِ الهه بالا می‌ره، دیالوگ‌ها عوض می‌شن.
#  یه‌بار تو کل حساب می‌تونی «چیت‌اسکیل» بخوای — یه بونوسِ دائمیِ
#  کوچیک ولی همیشگی رو Combat Power که با لولِ خودِ کاراکتر رشد
#  می‌کنه (شبیهِ mount_system و stand_system، هوکِ combat_power.py).
# ============================================================
import random
import time

PRAY_COOLDOWN = 6 * 3600  # هر ۶ ساعت یه‌بار می‌تونی دعا کنی

FAVOR_TIERS = [
    (0,   "🤍 غریبه", "هنوز منو نمی‌شناسی، مسافر."),
    (20,  "💙 آشنا", "اسمت رو یادم مونده... جالبه."),
    (60,  "💜 معتمَد", "شاید... شاید تو واقعاً فرق داری."),
    (150, "💛 برگزیده", "سرنوشتت رو با علاقه دنبال می‌کنم."),
    (400, "🌟 پیوندخورده", "بینِ من و تو یه پیوندیه که خودم هم درکش نمی‌کنم."),
]

DIALOGUE_POOL = {
    "🤍 غریبه": [
        "یه کامیون تو رو به اینجا پرت کرد. عذر می‌خوام، این بخشِ کار همیشه یکم... خشنه.",
        "هر مسافرِ تازه‌ای همینو می‌پرسه: «چرا من؟» صادقانه؟ نمی‌دونم.",
    ],
    "💙 آشنا": [
        "شنیدم تو Abyss داری کارای جالبی می‌کنی. ادامه بده.",
        "بعضی‌وقتا از اینجا نگاهت می‌کنم. فقط... نگاه می‌کنم.",
    ],
    "💜 معتمَد": [
        "بین خودمون بمونه: بعضی از مسافرا رو پشیمون می‌شم که فرستادم. تو نه.",
        "قدرتِ چیت‌اسکیلی که بهت دادم رو داری خوب استفاده می‌کنی.",
    ],
    "💛 برگزیده": [
        "شاید تو همونی باشی که این‌بار می‌تونه تعادل رو برگردونه.",
        "هر بار که اسمت رو تو گزارش‌ها می‌بینم، یه لبخندِ کوچیک می‌زنم.",
    ],
    "🌟 پیوندخورده": [
        "دیگه فقط یه مسافر نیستی. بخشی از این داستان شدی — و بخشی از من.",
        "هرجا بری، یه تکه از لطفِ من همراهته. همیشه.",
    ],
}

CHEAT_SKILLS = {
    "unyielding_will":  {"name": "⚡ اراده‌ی خم‌ناپذیر", "desc": "هیچ‌وقت واقعاً تسلیم نمی‌شی.", "cp_per_level": 3.0},
    "silver_tongue":    {"name": "🗣 زبانِ نقره‌ای",     "desc": "کلمات همیشه به نفعت کار می‌کنن.", "cp_per_level": 2.6},
    "fortunes_favor":   {"name": "🍀 لطفِ اقبال",        "desc": "شانس همیشه یه‌ذره طرفِ توئه.",   "cp_per_level": 2.8},
    "berserkers_echo":  {"name": "🔥 پژواکِ خشم",        "desc": "هرچی زخمی‌تر، خطرناک‌تر.",       "cp_per_level": 3.2},
    "void_whisper":     {"name": "🌑 نجواهای خلاء",      "desc": "چیزی از تاریکی بهت گوش می‌ده.",  "cp_per_level": 3.4},
}


def _favor(player: dict) -> int:
    return player.get("goddess_favor", 0)


def favor_tier(player: dict) -> tuple[str, str]:
    favor = _favor(player)
    tier_name, flavor = FAVOR_TIERS[0][1], FAVOR_TIERS[0][2]
    for threshold, name, txt in FAVOR_TIERS:
        if favor >= threshold:
            tier_name, flavor = name, txt
    return tier_name, flavor


def next_tier_gap(player: dict) -> tuple[str | None, int]:
    favor = _favor(player)
    for threshold, name, _ in FAVOR_TIERS:
        if favor < threshold:
            return name, threshold - favor
    return None, 0


def get_dialogue(player: dict) -> str:
    tier_name, _ = favor_tier(player)
    pool = DIALOGUE_POOL.get(tier_name, DIALOGUE_POOL["🤍 غریبه"])
    return random.choice(pool)


def can_pray(player: dict) -> tuple[bool, int]:
    last = player.get("goddess_last_pray", 0)
    remaining = PRAY_COOLDOWN - (time.time() - last)
    return remaining <= 0, max(0, int(remaining))


def pray(player: dict) -> dict:
    ok, remaining = can_pray(player)
    if not ok:
        hrs = remaining // 3600
        mins = (remaining % 3600) // 60
        return {"ok": False, "message": f"⏳ الهه هنوز خسته‌ست — {hrs} ساعت و {mins} دقیقه‌ی دیگه دوباره بیا."}

    player["goddess_last_pray"] = time.time()
    player["goddess_favor"] = player.get("goddess_favor", 0) + random.randint(3, 8)

    roll = random.random()
    if roll < 0.55:
        zen = random.randint(150, 500)
        player["zen"] = player.get("zen", 0) + zen
        msg = f"🕊 الهه لبخند زد و {zen:,} Zen به کیفت افتاد."
    elif roll < 0.85:
        xp = random.randint(80, 250)
        player["xp"] = player.get("xp", 0) + xp
        msg = f"🕊 یه پرتوِ کوچیک از دانشِ الهه بهت رسید — +{xp:,} XP."
    else:
        if player.get("rift_shards", 0) >= 0:
            player["rift_shards"] = player.get("rift_shards", 0) + 1
        msg = "🕊 الهه یه 🔹Echo Shard از دنیای دیگه برات فرستاد."

    return {"ok": True, "message": msg, "favor": player["goddess_favor"]}


def can_claim_cheat_skill(player: dict) -> bool:
    return not player.get("goddess_cheat_skill")


def claim_cheat_skill(player: dict, skill_id: str) -> tuple[bool, str]:
    if not can_claim_cheat_skill(player):
        return False, "❌ قبلاً چیت‌اسکیلت رو گرفتی — فقط یه‌بار می‌شه."
    if skill_id not in CHEAT_SKILLS:
        return False, "❌ چیت‌اسکیلِ نامعتبر."
    player["goddess_cheat_skill"] = skill_id
    s = CHEAT_SKILLS[skill_id]
    return True, f"⚡ **{s['name']}** بهت داده شد!\n{s['desc']}"


def goddess_power_bonus(player: dict) -> float:
    """سهمِ چیت‌اسکیل تو Combat Power — با لولِ خودِ کاراکتر رشد می‌کنه."""
    skill_id = player.get("goddess_cheat_skill")
    if not skill_id or skill_id not in CHEAT_SKILLS:
        return 0.0
    per_level = CHEAT_SKILLS[skill_id]["cp_per_level"]
    return per_level * max(1, player.get("level", 1))
