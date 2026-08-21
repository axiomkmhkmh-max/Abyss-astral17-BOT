# ============================================================
#  ASTRAL ABYSS RPG — Handlers داشبوردِ آماریِ بازیکن (/stats) 📊
# ------------------------------------------------------------
#  آمارِ بازیکن الان پخشه: PvP تو /arena، حلقه تو /underground،
#  اکتشاف تو /pulse یا هیچ‌جا، تایتل‌ها تو /titles، فصل تو /season.
#  این هندلر یه صفحه‌ی جمع‌بندیِ همه‌شون رو یه‌جا نشون می‌ده.
# ============================================================
from aiogram.filters import Command
from aiogram.types import Message

from database import get_player, aget_player


def _safe(fn, *args, default=None, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:
        return default


async def build_stats_text(player: dict) -> str:
    name = player.get("name", "—")
    level = player.get("level", 1)
    zen = player.get("zen", 0)
    kills = player.get("kills", 0)
    rebirths = player.get("rebirth_count", 0)

    lines = [f"📊 **داشبوردِ {name}**\n"]
    lines.append(f"🏅 سطح: {level} | 💰 {zen:,} Zen | ⚔️ {kills:,} کشتار" + (f" | 🔁 {rebirths} تولدِ دوباره" if rebirths else ""))

    # ── Combat Power ──
    from combat_power import calculate_combat_power
    cp = _safe(calculate_combat_power, player, default=0)
    lines.append(f"\n💪 **Combat Power:** {cp:,}")

    # ── Item Score تجهیزات ──
    try:
        from item_system import calculate_item_score, EQUIP_SLOTS
        eq = player.get("equipped", {})
        item_score = sum(calculate_item_score(it) for it in eq.values() if it)
        filled = sum(1 for s in EQUIP_SLOTS if eq.get(s))
        lines.append(f"🎽 تجهیزات: {filled}/{len(EQUIP_SLOTS)} اسلات | ⭐ Item Score: {item_score:,}")
    except Exception:
        pass

    # ── PvP ──
    try:
        from pvp import league_for_points
        pts = player.get("pvp_points", 0)
        league = league_for_points(pts)
        w, l = player.get("pvp_wins", 0), player.get("pvp_losses", 0)
        lines.append(f"\n⚔️ **PvP:** {league} ({pts:,} امتیاز) | 🏆 {w} برد / {l} باخت")
    except Exception:
        pass

    # ── حلقه‌ی سایه (Underground) ──
    ug_w = player.get("underground_wins", 0)
    ug_l = player.get("underground_losses", 0)
    if ug_w or ug_l:
        streak = player.get("_ug_streak", 0)
        streak_txt = f" | استریک: {'🔥' if streak>0 else '🧊'}{abs(streak)}" if streak else ""
        lines.append(f"🩸 **حلقه‌ی سایه:** {ug_w} برد / {ug_l} باخت{streak_txt}")

    # ── اکتشاف (Fog of War) ──
    try:
        from economy import MAPS_DATA
        done = len(player.get("fog_completed_maps", []))
        total = len(MAPS_DATA)
        lines.append(f"🌫️ **اکتشاف:** {done}/{total} نقشه صد در صد کشف‌شده")
    except Exception:
        pass

    # ── عنوانِ فعال ──
    try:
        from titles_system import get_active_title, collect_titles
        active = get_active_title(player)
        n_titles = len(collect_titles(player))
        if active:
            lines.append(f"🏅 **عنوانِ فعال:** {active} (از {n_titles} عنوانِ باز‌شده)")
    except Exception:
        pass

    # ── مربی‌گری ──
    try:
        import mentor_system as ms
        if player.get("mentee_of"):
            mentor = await aget_player(player["mentee_of"])
            lines.append(f"🎓 **شاگردِ:** {mentor.get('name','—') if mentor else '—'}")
        elif player.get("mentor_of"):
            title = ms.mentor_title(player)
            grad = player.get("graduated_mentee_count", 0)
            lines.append(f"👨‍🏫 **استاد:** {len(player['mentor_of'])} شاگرد" + (f" | {title} ({grad} فارغ‌التحصیل)" if title else ""))
    except Exception:
        pass

    # ── همراه (Pet/Companion) ──
    try:
        import pet_system as ps
        pet = ps.active_pet(player)
        if pet:
            lines.append(f"🐾 **همراه:** {pet['emoji']} {pet['name']} (Lv.{pet.get('level',1)})")
    except Exception:
        pass

    # ── آرکِ فصلی ──
    try:
        import seasonal_arc as sa
        p = sa.progress()
        lines.append(f"\n📜 فصل {p['season']}: {p['kills']:,}/{p['goal']:,} کشتارِ سراسری" + (" ✅" if p["goal_reached"] else ""))
    except Exception:
        pass

    return "\n".join(lines)


async def cmd_stats(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    await msg.answer(await build_stats_text(player))


def register_stats_handlers(dp, bot):
    dp.message.register(cmd_stats, Command("stats"))
