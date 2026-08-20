# ============================================================
#  ASTRAL ABYSS — Appraisal (تشخیص) 🔍
# ------------------------------------------------------------
#  یه اسکیلِ پسیوِ کلاسیکِ ایسکای: «چشمانت می‌درخشه و...». وقتی
#  بازیکن به سطحِ لازم برسه، خودکار باز می‌شه (نیازی به خرجِ اسکیل‌
#  پوینت نداره — شبیهِ goddess_system که با خودِ حساب رشد می‌کنه).
#  دو تا قابلیت:
#   ۱) appraise_enemy — تو صحنه‌ی نبرد (mob_combat.py) یه دکمه‌ی
#      «🔍 آنالیز» اضافه می‌کنه که استتِ واقعیِ دشمن رو فاش می‌کنه.
#   ۲) appraise_item — دستورِ /appraise که همه‌ی آیتم‌های اکیپ‌شده
#      رو با جزئیاتِ فلیوردار نشون می‌ده.
#  این ماژول خالص/بدون aiogram‌ه؛ هندلرها تو appraisal_handlers.py.
# ============================================================
import random

UNLOCK_LEVEL = 5

FLAVOR_INTROS = [
    "👁️ چشمانت برای یه لحظه می‌درخشن و...",
    "🔍 ذهنت خودکار جزئیات رو تحلیل می‌کنه...",
    "✨ یه لایه‌ی نامرئی از اطلاعات جلوی چشمت ظاهر می‌شه...",
    "👁️‍🗨️ حسِ تشخیصت فعال می‌شه...",
]

TIER_LABELS = {
    "common": "⚪ معمولی", "rare": "🔵 نادر", "epic": "🟣 حماسی",
    "legendary": "🟠 افسانه‌ای", "mythic": "🔴 اسطوره‌ای",
}


def is_unlocked(player: dict) -> bool:
    return bool(player.get("appraisal_unlocked")) or player.get("level", 1) >= UNLOCK_LEVEL


def check_auto_unlock(player: dict) -> bool:
    """اگه به سطحِ لازم رسیده و هنوز فلگ نخورده، باز می‌کنه و True برمی‌گردونه
    (برای نمایشِ یه پیامِ یه‌بارِ «تشخیص باز شد!»)."""
    if not player.get("appraisal_unlocked") and player.get("level", 1) >= UNLOCK_LEVEL:
        player["appraisal_unlocked"] = True
        return True
    return False


def unlock_announcement() -> str:
    return (
        "🔍 **مهارتِ تشخیص باز شد!**\n"
        "_«یه چیزی تو دیدنت عوض شده... انگار می‌تونی از پشتِ ظاهرِ چیزها، ذاتشون رو ببینی.»_\n\n"
        "از این به بعد تو نبردها می‌تونی دشمنت رو آنالیز کنی، و با /appraise تجهیزاتت رو دقیق بررسی کنی."
    )


def appraise_enemy(enemy: dict) -> str:
    intro = random.choice(FLAVOR_INTROS)
    tier = enemy.get("tier", "common")
    tier_label = TIER_LABELS.get(tier, tier)
    lines = [
        intro,
        "",
        f"🔎 **{enemy.get('name','دشمن')}**",
        f"  🏷 رتبه: {tier_label}",
        f"  ❤️ HP: {enemy.get('hp', 0):,}/{enemy.get('max_hp', enemy.get('hp', 0)):,}",
        f"  ⚔️ قدرتِ حمله: {enemy.get('dmg', 0):,}",
    ]
    if enemy.get("weak"):
        lines.append(f"  🎯 نقطه‌ضعف: {enemy['weak']}")
    if enemy.get("is_boss"):
        boss_tier = enemy.get("boss_tier")
        if boss_tier:
            lines.append(f"  👑 نوعِ باس: {boss_tier}")
        if enemy.get("_awakened"):
            lines.append("  ⚠️ در فازِ بیداری — قدرتش بالاتر از حدِ عادیه!")
        else:
            awaken_pct = int(enemy.get("awaken_pct", 0.35) * 100)
            lines.append(f"  ⚠️ زیرِ {awaken_pct}٪ HP وارد فازِ بیداری می‌شه.")
    if enemy.get("is_apex"):
        lines.append("  🌟 این یه نمونه‌ی Apex نایاب‌ه — استتش بالاتر از حدِ معمولِ نوعشه.")
    if enemy.get("is_nemesis"):
        lines.append("  💢 این یه نمسیسه — یه‌بار قبلاً بهت باخته و برگشته.")
    return "\n".join(lines)


def appraise_item(item: dict) -> str:
    from item_system import calculate_item_score

    intro = random.choice(FLAVOR_INTROS)
    rarity = item.get("rarity", "common")
    lines = [
        intro,
        "",
        f"🔎 **{item.get('name','آیتم')}**",
        f"  🏷 ندرت: {TIER_LABELS.get(rarity, rarity)}",
        f"  ⭐ Item Score: {item.get('item_score', calculate_item_score(item)):,}",
        f"  📏 نیازِ سطح: {item.get('level_req', 1)} | 🔧 آپگرید: +{item.get('upgrade_level', 0)}",
    ]
    aff = item.get("affixes", {})
    all_aff = aff.get("prefix", []) + aff.get("suffix", [])
    if all_aff:
        lines.append("  ✨ افیکس‌های پنهان:")
        for a in all_aff:
            lines.append(f"     • {a.get('label','?')}: +{a.get('value',0)}")
    dur = item.get("max_durability", 0)
    if dur:
        lines.append(f"  🛠 دوام: {item.get('durability', dur)}/{dur}")
    return "\n".join(lines)


def appraise_all_equipped(player: dict) -> str:
    equipped = player.get("equipped", {})
    items = [(slot, it) for slot, it in equipped.items() if it]
    if not items:
        return "👁️‍🗨️ چیزی برای تحلیل نیست — هیچ تجهیزاتی اکیپ نکردی."
    blocks = [f"🔍 **تحلیلِ تجهیزات** ({len(items)} آیتم)\n"]
    for slot, item in items:
        blocks.append(appraise_item(item))
        blocks.append("")
    return "\n".join(blocks).strip()
