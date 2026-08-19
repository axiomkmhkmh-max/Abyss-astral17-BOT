# ============================================================
#  ASTRAL ABYSS — Black Market Reputation Tiers (رتبه‌بندیِ دیلر)
# ------------------------------------------------------------
#  روی همون player["bm_reputation"] (۰-۱۰۰، از قبل تو economy_engine.py
#  وجود داره و فقط تخفیفِ مالیات می‌داد) یه سیستمِ رتبه‌بندیِ اسم‌دار
#  می‌سازه که چند تا سیستمِ جدید (دیلرهای گردشی + تابلوی قاچاق) رو
#  پشتِ رتبه‌های بالاتر قفل می‌کنه. هیچ فیلدِ جدیدی به پلیر اضافه
#  نمی‌کنه — فقط از رویِ همون عددِ موجود می‌خونه.
# ============================================================
from __future__ import annotations

TIERS = [
    {
        "key": "wanderer", "min_rep": 0, "name": "رهگذر", "emoji": "🧍",
        "desc": "تازه پاتو تو بازارِ سیاه گذاشتی. فعلاً فقط شاپِ عمومی و جاسوسی/دفاع در دسترسته.",
        "unlocks": set(),
        "heat_reduction": 0.0,
    },
    {
        "key": "acquainted", "min_rep": 20, "name": "آشنا", "emoji": "🙂",
        "desc": "دیلرها دیگه بهت مشکوک نیستن — دیلرهای گردشیِ نقشه‌ها رو می‌بینی.",
        "unlocks": {"dealers"},
        "heat_reduction": 0.05,
    },
    {
        "key": "trusted", "min_rep": 45, "name": "معتمد", "emoji": "🤝",
        "desc": "بازار بهت اعتماد کرده — می‌تونی رو تابلوی قاچاق قرارداد بذاری.",
        "unlocks": {"dealers", "smuggling"},
        "heat_reduction": 0.12,
    },
    {
        "key": "right_hand", "min_rep": 70, "name": "دستِ راستِ بازار", "emoji": "🖤",
        "desc": "نگهبان‌ها دیگه سراغت نمیان مگه به‌ندرت — و به کالای ویژه‌ی دیلرها دسترسی داری.",
        "unlocks": {"dealers", "smuggling", "dealer_exclusive"},
        "heat_reduction": 0.22,
    },
    {
        "key": "shadow_archon", "min_rep": 90, "name": "آرشونِ سایه", "emoji": "👁️",
        "desc": "تویی که بازارِ سیاه رو می‌چرخونی. حداکثر تخفیف، حداقل ریسک.",
        "unlocks": {"dealers", "smuggling", "dealer_exclusive", "big_contracts"},
        "heat_reduction": 0.35,
    },
]


def get_tier(player: dict) -> dict:
    rep = player.get("bm_reputation", 0)
    cur = TIERS[0]
    for t in TIERS:
        if rep >= t["min_rep"]:
            cur = t
    return cur


def next_tier(player: dict) -> dict | None:
    rep = player.get("bm_reputation", 0)
    for t in TIERS:
        if rep < t["min_rep"]:
            return t
    return None


def has_unlock(player: dict, feature: str) -> bool:
    return feature in get_tier(player)["unlocks"]


def heat_reduction(player: dict) -> float:
    return get_tier(player)["heat_reduction"]


def tier_progress_text(player: dict) -> str:
    rep = player.get("bm_reputation", 0)
    cur = get_tier(player)
    nxt = next_tier(player)
    lines = [
        f"{cur['emoji']} **رتبه‌ی فعلی: {cur['name']}**  ({rep}/100 رپیوتیشن)",
        f"_{cur['desc']}_",
    ]
    if nxt:
        need = nxt["min_rep"] - rep
        lines.append(f"\n⬆️ تا رتبه‌ی بعدی ({nxt['emoji']} {nxt['name']}): {need} رپیوتیشنِ دیگه")
    else:
        lines.append("\n✅ به بالاترین رتبه رسیدی!")
    lines.append("\n📈 رپیوتیشن با هر خرید/فروشِ بازارِ سیاه و تحویلِ قراردادها بالا می‌ره.")
    return "\n".join(lines)


def all_tiers_text() -> str:
    lines = ["🏷️ **نردبانِ رتبه‌های بازارِ سیاه**\n"]
    for t in TIERS:
        lines.append(f"{t['emoji']} **{t['name']}** — رپیوتیشنِ {t['min_rep']}+")
        lines.append(f"   _{t['desc']}_")
    return "\n".join(lines)
