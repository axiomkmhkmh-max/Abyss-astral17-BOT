# ============================================================
#  ASTRAL ABYSS — Codex (کدکسِ کاراکترها/استندها)
# ------------------------------------------------------------
#  چون هر بازیکن فقط یه کاراکتر داره (نه یه کالکشن)، «کدکس» به‌جای
#  کالکشن‌گرفتن، رو **کشف** کار می‌کنه: هر کاراکتری که تو PvP باهاش
#  رو‌به‌رو بشی، به کدکست اضافه می‌شه — با ~۳۸۰ کاراکتر تو بازی، این
#  یه هدفِ درازمدتِ طبیعی برای بازیکنایی می‌سازه که زیاد PvP می‌کنن.
#
#  هر مایل‌استون (۲۵/۵۰/۱۰۰/۲۰۰/کامل) یه پاداشِ یک‌بارمصرف داره.
# ============================================================
from __future__ import annotations

from characters import ALL_CHARACTERS

TOTAL_CHARACTERS = len(ALL_CHARACTERS)

MILESTONES = [
    (25,  {"zen": 5_000,  "stand_fragments": 5}),
    (50,  {"zen": 12_000, "stand_fragments": 10}),
    (100, {"zen": 30_000, "stand_fragments": 20}),
    (200, {"zen": 75_000, "stand_fragments": 40}),
]


def get_seen(player: dict) -> set:
    return set(player.get("codex_seen", []))


def mark_seen(player: dict, char_name: str) -> None:
    if not char_name or char_name not in ALL_CHARACTERS:
        return
    seen = player.setdefault("codex_seen", [])
    if char_name not in seen:
        seen.append(char_name)


def codex_progress(player: dict) -> tuple[int, int]:
    return len(get_seen(player)), TOTAL_CHARACTERS


def check_and_claim_milestones(player: dict) -> list[str]:
    """بعدِ هر mark_seen صدا زده می‌شه — اگه به یه مایل‌استونِ جدید
    رسیده باشه، پاداشش رو می‌ده و پیام‌ها رو برمی‌گردونه."""
    seen_count, _ = codex_progress(player)
    claimed = player.setdefault("codex_milestones_claimed", [])
    messages = []
    for threshold, reward in MILESTONES:
        if seen_count >= threshold and threshold not in claimed:
            claimed.append(threshold)
            player["zen"] = player.get("zen", 0) + reward.get("zen", 0)
            if reward.get("stand_fragments"):
                player["stand_fragments"] = player.get("stand_fragments", 0) + reward["stand_fragments"]
            messages.append(
                f"📖 کدکس: {threshold} کاراکتر کشف شد! (+{reward.get('zen',0):,} Zen، "
                f"+{reward.get('stand_fragments',0)} 🧩 فرگمنت)"
            )
    return messages


def category_breakdown(player: dict) -> dict[str, int]:
    """چندتا از کاراکترهای دیده‌شده تو هر دسته‌ی استند بودن — یه دیدِ
    اضافه که با کدکسِ خام قاطیه."""
    from stand_system import get_stand
    counts: dict[str, int] = {}
    for name in get_seen(player):
        cat = get_stand(name)["category"]
        counts[cat] = counts.get(cat, 0) + 1
    return counts


def format_codex_card(player: dict) -> str:
    seen_count, total = codex_progress(player)
    pct = int(seen_count / total * 100) if total else 0
    bar_len = 12
    filled = int(bar_len * seen_count / total) if total else 0
    bar = "🟩" * filled + "⬜" * (bar_len - filled)

    lines = [
        f"📖 **کدکسِ کاراکترها**",
        f"{bar} {seen_count}/{total} ({pct}٪)\n",
        "_هر کاراکتری که تو PvP باهاش رو‌به‌رو بشی، به کدکست اضافه می‌شه._\n",
    ]

    breakdown = category_breakdown(player)
    if breakdown:
        lines.append("🏷 **بر اساسِ دسته‌ی استند:**")
        for cat, count in sorted(breakdown.items(), key=lambda x: -x[1]):
            lines.append(f"  • {cat}: {count}")
        lines.append("")

    next_milestone = next((t for t, _ in MILESTONES if t > seen_count), None)
    if next_milestone:
        lines.append(f"🎯 مایل‌استونِ بعدی: {next_milestone} کاراکتر ({seen_count}/{next_milestone})")
    else:
        lines.append("🌟 همه‌ی مایل‌استون‌ها گرفته شدن!")

    return "\n".join(lines)
