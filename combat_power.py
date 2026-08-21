# ============================================================
#  ASTRAL ABYSS — Combat Power (CP) Engine
# ------------------------------------------------------------
#  قدرت واقعی بازیکن نباید فقط از Level بیاد. این ماژول همه‌ی منابع
#  قدرت (لول، کاتانا، کاراکتر، مهارت‌ها، تجهیزات، رپیوتیشن، عناوین)
#  رو ترکیب می‌کنه تا CP نهایی به دست بیاد.
#
#  همه‌ی importهای وابسته با try/except انجام می‌شن تا اگه یه ماژول
#  هنوز داخل پروژه کامل نشده (مثلاً equipment slots یا titles که تو
#  فازهای بعدی میان) این فایل crash نکنه — مقدار پیش‌فرض صفر می‌گیره.
# ============================================================
from item_system import calculate_item_score

# ─── وزن‌دهی هر منبع قدرت در فرمول نهایی ───────────────────────
WEIGHTS = {
    "level":      12,
    "character":  1.4,
    "katana":     1.0,
    "equipment":  1.0,
    "skills":     8,
    "reputation": 1.5,
    "titles":     1.0,
    "mastery":    1.0,
    "stand":      1.0,
    "mount":      1.0,
    "goddess":    1.0,
    "evolution":  1.0,
    "awakening":  1.0,
    "academy":    1.0,
    "villainess": 1.0,
    "cafe":       1.0,
}

CP_TIER_LABELS = [
    (0,       "🥉 مبتدی"),
    (500,     "🥈 جنگجو"),
    (1500,    "🥇 نخبه"),
    (4000,    "💎 استاد"),
    (10000,   "👑 افسانه"),
    (25000,   "🌌 اسطوره"),
    (60000,   "☄️ متعالی"),
]

def _safe_call(fn, *args, default=None, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:
        return default

def _level_score(player: dict) -> float:
    level = player.get("level", 1)
    return level * WEIGHTS["level"]

def _character_score(player: dict) -> float:
    try:
        from characters import ALL_CHARACTERS
    except ImportError:
        return 0.0
    char = ALL_CHARACTERS.get(player.get("character", ""), {})
    base_dmg = char.get("base_dmg", 0)
    rarity_mult = {"common": 1.0, "rare": 1.4, "legendary": 2.0, "mythic": 2.3, "special": 2.6}.get(char.get("rarity", "common"), 1.0)
    return base_dmg * rarity_mult * WEIGHTS["character"]

def _katana_score(player: dict) -> float:
    katana_lv = player.get("katana_level", 1)
    try:
        from katana_system import get_katana_full_stats
        stats = get_katana_full_stats(katana_lv) or {}
        raw = stats.get("dmg", katana_lv * 4) + stats.get("crit", 0) * 100 + stats.get("lifesteal", 0) * 100
    except Exception:
        raw = katana_lv * 5
    return raw * WEIGHTS["katana"]

def _equipment_score(player: dict) -> float:
    """جمع Item Score همه‌ی آیتم‌های equip‌شده (equipment slots — فاز بعدی).
    فعلاً اگه player['equipped'] وجود نداشته باشه صفر برمی‌گرده (بدون کرش)."""
    equipped = player.get("equipped", {})
    total = 0
    for slot, item in equipped.items():
        if item:
            total += item.get("item_score", calculate_item_score(item))
    return total * WEIGHTS["equipment"]

def _skills_score(player: dict) -> float:
    unlocked = player.get("unlocked_skills", [])
    return len(unlocked) * WEIGHTS["skills"]

def _reputation_score(player: dict) -> float:
    rep = player.get("bm_reputation", 0)
    return rep * WEIGHTS["reputation"]

def _titles_score(player: dict) -> float:
    """عناوین/دستاوردها (فاز بعدی — achievements.py). فعلاً fallback امن."""
    titles = player.get("titles_unlocked", [])
    return len(titles) * 20 * WEIGHTS["titles"]

def _mastery_score(player: dict) -> float:
    """Boss Knowledge / Mastery (فاز بعدی). فعلاً fallback امن."""
    mastery = player.get("boss_mastery", {})
    return sum(mastery.values()) * 0.5 * WEIGHTS["mastery"] if mastery else 0.0

def _stand_score(player: dict) -> float:
    """سهمِ استند (همراهِ روحانیِ جداگانه از خودِ کاراکتر) — فاز جدید."""
    try:
        from stand_system import stand_power_bonus
        return stand_power_bonus(player) * WEIGHTS["stand"]
    except Exception:
        return 0.0

def _mount_score(player: dict) -> float:
    """سهمِ مونتِ سوارشده (mount_system.py)."""
    try:
        from mount_system import mount_power_bonus
        return mount_power_bonus(player) * WEIGHTS["mount"]
    except Exception:
        return 0.0

def _goddess_score(player: dict) -> float:
    """سهمِ چیت‌اسکیلِ الهه‌ی آغازها (goddess_system.py)."""
    try:
        from goddess_system import goddess_power_bonus
        return goddess_power_bonus(player) * WEIGHTS["goddess"]
    except Exception:
        return 0.0

def _evolution_score(player: dict) -> float:
    """سهمِ مسیرِ تکاملِ گرفته‌شده (evolution_system.py)."""
    try:
        from evolution_system import evolution_power_bonus
        return evolution_power_bonus(player) * WEIGHTS["evolution"]
    except Exception:
        return 0.0

def _awakening_score(player: dict) -> float:
    """سهمِ استتِ مخفیِ بیدارشده (hidden_awakening.py)."""
    try:
        from hidden_awakening import awakening_power_bonus
        return awakening_power_bonus(player) * WEIGHTS["awakening"]
    except Exception:
        return 0.0

def _academy_score(player: dict) -> float:
    """سهمِ سال‌های گذروندهٔ آکادمی (academy_system.py)."""
    try:
        from academy_system import academy_power_bonus
        return academy_power_bonus(player) * WEIGHTS["academy"]
    except Exception:
        return 0.0

def _villainess_score(player: dict) -> float:
    """سهمِ مسیرِ زنانه‌ی جایگزین (villainess_arc.py)."""
    try:
        from villainess_arc import villainess_power_bonus
        return villainess_power_bonus(player) * WEIGHTS["villainess"]
    except Exception:
        return 0.0

def _cafe_score(player: dict) -> float:
    """سهمِ کافه — عمداً کوچیک، این مسیر برای آرامشه نه قدرت (isekai_cafe.py)."""
    try:
        from isekai_cafe import cafe_power_bonus
        return cafe_power_bonus(player) * WEIGHTS["cafe"]
    except Exception:
        return 0.0

def calculate_combat_power(player: dict) -> int:
    total = (
        _level_score(player)
        + _character_score(player)
        + _katana_score(player)
        + _equipment_score(player)
        + _skills_score(player)
        + _reputation_score(player)
        + _titles_score(player)
        + _mastery_score(player)
        + _stand_score(player)
        + _mount_score(player)
        + _goddess_score(player)
        + _evolution_score(player)
        + _awakening_score(player)
        + _academy_score(player)
        + _villainess_score(player)
        + _cafe_score(player)
    )
    return int(total)

def get_cp_breakdown(player: dict) -> dict:
    """برای پنل نمایش (📊 Combat Power) — نشون میده هر بخش چقدر سهم داره."""
    return {
        "level":      int(_level_score(player)),
        "character":  int(_character_score(player)),
        "katana":     int(_katana_score(player)),
        "equipment":  int(_equipment_score(player)),
        "skills":     int(_skills_score(player)),
        "reputation": int(_reputation_score(player)),
        "titles":     int(_titles_score(player)),
        "mastery":    int(_mastery_score(player)),
        "stand":      int(_stand_score(player)),
        "mount":      int(_mount_score(player)),
        "goddess":    int(_goddess_score(player)),
        "evolution":  int(_evolution_score(player)),
        "awakening":  int(_awakening_score(player)),
        "academy":    int(_academy_score(player)),
        "villainess": int(_villainess_score(player)),
        "cafe":       int(_cafe_score(player)),
    }

def get_cp_label(cp: int) -> str:
    label = CP_TIER_LABELS[0][1]
    for threshold, lbl in CP_TIER_LABELS:
        if cp >= threshold:
            label = lbl
    return label

def recommended_cp_for_tier(tier_num: int) -> int:
    """حداقل CP پیشنهادی (نه اجباری — گیت واقعی world_tiers.py با لول/آسنشنه)
    برای هشدار دادن به بازیکن که وارد محتوای خیلی بالاتر از قدرتش نشه."""
    return {1: 0, 2: 800, 3: 2500, 4: 6000, 5: 15000, 6: 35000}.get(tier_num, 0)

def is_underpowered(player: dict, tier_num: int) -> bool:
    cp = calculate_combat_power(player)
    return cp < recommended_cp_for_tier(tier_num) * 0.5

def format_cp_card(player: dict) -> str:
    cp = calculate_combat_power(player)
    label = get_cp_label(cp)
    breakdown = get_cp_breakdown(player)
    lines = [
        f"⚔️ **Combat Power: {cp:,}**",
        f"🏷 رتبه: {label}\n",
        "📊 **منابع قدرت:**",
        f"  ⭐ لول: {breakdown['level']:,}",
        f"  🎴 کاراکتر: {breakdown['character']:,}",
        f"  🗡 کاتانا: {breakdown['katana']:,}",
        f"  🛡 تجهیزات: {breakdown['equipment']:,}",
        f"  🌟 مهارت‌ها: {breakdown['skills']:,}",
        f"  🖤 رپیوتیشن: {breakdown['reputation']:,}",
        f"  🏆 عناوین: {breakdown['titles']:,}",
        f"  📖 مسترى: {breakdown['mastery']:,}",
        f"  👻 استند: {breakdown['stand']:,}",
        f"  🐎 مونت: {breakdown['mount']:,}",
        f"  🕊 الهه: {breakdown['goddess']:,}",
        f"  🧬 تکامل: {breakdown['evolution']:,}",
        f"  💫 بیداری: {breakdown['awakening']:,}",
        f"  🎓 آکادمی: {breakdown['academy']:,}",
        f"  🌹 مسیرِ زنانه: {breakdown['villainess']:,}",
        f"  ☕ کافه: {breakdown['cafe']:,}",
    ]
    return "\n".join(lines)
