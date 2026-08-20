# ============================================================
#  ASTRAL ABYSS — Dungeon Core 🏰 (لردِ سیاه‌چال)
# ------------------------------------------------------------
#  هر بازیکن می‌تونه سیاه‌چالِ شخصیِ خودش رو بسازه: هسته رو تقویت
#  کنه، تله بچینه، یه نگهبان (موب) استخدام کنه، و خزانه‌ش پر بشه.
#  بقیه‌ی بازیکن‌ها می‌تونن با /raiddungeon بهش حمله کنن — یه
#  حل‌وفصلِ سریع (نه نبردِ نوبتی) بر اساسِ Combat Power در برابرِ
#  مجموعِ قدرتِ دفاعیِ سیاه‌چال. هیبریدِ PvE/PvP: دفاع «موب»ه ولی
#  حمله‌کننده یه بازیکنِ واقعیه.
#
#  دیتا: player["dungeon_core"] = {
#      "level": int, "traps": [trap_id,...], "monster": monster_id|None,
#      "treasury": int, "defense_wins": int, "defense_losses": int,
#      "raid_wins": int, "raid_losses": int, "last_income_ts": float,
#  }
#  player["dungeon_raid_cooldown"] — تایم‌استمپِ قابلِ‌حمله‌شدنِ بعدی.
# ============================================================
import random
import time

MAX_TRAP_SLOTS = 3
CORE_BASE_DEFENSE_PER_LEVEL = 25
RAID_COOLDOWN = 3 * 3600           # هر ۳ ساعت یه‌بار می‌تونی راید کنی
INCOME_PER_HOUR_PER_LEVEL = 40     # درآمدِ منفعلِ خزانه (هر ساعت)
INCOME_CAP_HOURS = 12              # بیشتر از ۱۲ ساعت جمع نمی‌شه (ضدِ فارمِ افلاین)
RAID_STEAL_PCT = 0.35              # سهمی از خزانه که برنده می‌بره
RAID_LOSS_PENALTY = 60             # اگه حمله‌کننده ببازه، این‌قدر Zen از دست می‌ده

TRAPS = {
    "spike_pit":   {"name": "🕳 چاله‌ی میخ", "cost": 200,  "defense": 30},
    "fire_rune":   {"name": "🔥 طلسمِ آتش",  "cost": 500,  "defense": 70},
    "frost_ward":  {"name": "❄️ حصارِ یخ",   "cost": 500,  "defense": 70},
    "void_snare":  {"name": "🌑 تله‌ی خلأ",  "cost": 1200, "defense": 150},
}

MONSTERS = {
    "goblin_guard":   {"name": "👺 نگهبانِ گابلین",  "cost": 300,  "defense": 60},
    "stone_golem":    {"name": "🗿 گولمِ سنگی",       "cost": 800,  "defense": 140},
    "shade_wraith":   {"name": "👻 روحِ سایه",        "cost": 1500, "defense": 240},
    "abyss_hound":    {"name": "🐺 سگِ آبیس",         "cost": 3000, "defense": 420},
}

REINFORCE_BASE_COST = 400  # هزینه‌ی لولِ بعدیِ هسته = base * سطحِ فعلی


def get_or_init_core(player: dict) -> dict:
    core = player.get("dungeon_core")
    if not core:
        core = {
            "level": 1, "traps": [], "monster": None, "treasury": 0,
            "defense_wins": 0, "defense_losses": 0, "raid_wins": 0, "raid_losses": 0,
            "last_income_ts": time.time(),
        }
        player["dungeon_core"] = core
    return core


def total_defense_power(player: dict) -> int:
    core = get_or_init_core(player)
    power = core["level"] * CORE_BASE_DEFENSE_PER_LEVEL
    for tid in core["traps"]:
        t = TRAPS.get(tid)
        if t:
            power += t["defense"]
    if core.get("monster"):
        m = MONSTERS.get(core["monster"])
        if m:
            power += m["defense"]
    return power


def reinforce_cost(player: dict) -> int:
    core = get_or_init_core(player)
    return REINFORCE_BASE_COST * core["level"]


def reinforce_core(player: dict) -> tuple[bool, str]:
    core = get_or_init_core(player)
    cost = reinforce_cost(player)
    if player.get("zen", 0) < cost:
        return False, f"❌ Zen کافی نداری (نیاز: {cost:,})."
    player["zen"] -= cost
    core["level"] += 1
    return True, f"⚒️ هسته تقویت شد! سطح جدید: {core['level']} (+{CORE_BASE_DEFENSE_PER_LEVEL} دفاعِ پایه)"


def build_trap(player: dict, trap_id: str) -> tuple[bool, str]:
    core = get_or_init_core(player)
    trap = TRAPS.get(trap_id)
    if not trap:
        return False, "❌ تله‌ی نامعتبر."
    if trap_id in core["traps"]:
        return False, "❌ این تله رو از قبل چیدی."
    if len(core["traps"]) >= MAX_TRAP_SLOTS:
        return False, f"❌ همه‌ی {MAX_TRAP_SLOTS} اسلاتِ تله پره — یکی رو جایگزین کن."
    if player.get("zen", 0) < trap["cost"]:
        return False, f"❌ Zen کافی نداری (نیاز: {trap['cost']:,})."
    player["zen"] -= trap["cost"]
    core["traps"].append(trap_id)
    return True, f"✅ {trap['name']} چیده شد! (+{trap['defense']} دفاع)"


def remove_trap(player: dict, trap_id: str) -> tuple[bool, str]:
    core = get_or_init_core(player)
    if trap_id not in core["traps"]:
        return False, "❌ این تله رو نداری."
    core["traps"].remove(trap_id)
    return True, "🗑 تله برداشته شد."


def hire_monster(player: dict, monster_id: str) -> tuple[bool, str]:
    core = get_or_init_core(player)
    m = MONSTERS.get(monster_id)
    if not m:
        return False, "❌ موجودِ نامعتبر."
    if player.get("zen", 0) < m["cost"]:
        return False, f"❌ Zen کافی نداری (نیاز: {m['cost']:,})."
    player["zen"] -= m["cost"]
    core["monster"] = monster_id
    return True, f"✅ {m['name']} به‌عنوانِ نگهبان استخدام شد! (+{m['defense']} دفاع)"


def pending_income(player: dict) -> int:
    core = get_or_init_core(player)
    elapsed_hrs = min((time.time() - core.get("last_income_ts", time.time())) / 3600, INCOME_CAP_HOURS)
    return int(elapsed_hrs * INCOME_PER_HOUR_PER_LEVEL * core["level"])


def collect_income(player: dict) -> int:
    core = get_or_init_core(player)
    amount = pending_income(player)
    core["treasury"] = core.get("treasury", 0) + amount
    core["last_income_ts"] = time.time()
    return amount


def withdraw_treasury(player: dict) -> tuple[bool, str]:
    collect_income(player)
    core = get_or_init_core(player)
    amount = core.get("treasury", 0)
    if amount <= 0:
        return False, "❌ خزانه‌ت خالیه."
    player["zen"] = player.get("zen", 0) + amount
    core["treasury"] = 0
    return True, f"💰 {amount:,} Zen از خزانه برداشت شد."


def can_raid(player: dict) -> tuple[bool, int]:
    until = player.get("dungeon_raid_cooldown", 0)
    remaining = until - time.time()
    return remaining <= 0, max(0, int(remaining))


def pick_raid_target(all_players: dict, attacker_uid: int) -> tuple[str, dict] | None:
    """یه هدفِ رندوم که سیاه‌چالِ خودش رو داره و خودِ حمله‌کننده نیست."""
    candidates = [
        (uid, p) for uid, p in all_players.items()
        if int(uid) != attacker_uid and p.get("dungeon_core")
    ]
    if not candidates:
        return None
    return random.choice(candidates)


def resolve_raid(attacker: dict, defender: dict) -> dict:
    """حل‌وفصلِ سریعِ راید — برمی‌گردونه: {win, attacker_cp, defense_power, stolen, msg}"""
    from combat_power import calculate_combat_power
    collect_income(defender)
    def_core = get_or_init_core(defender)

    atk_cp = calculate_combat_power(attacker)
    def_power = total_defense_power(defender)

    # شانسِ برد بر اساسِ نسبتِ قدرت، با یه کفِ/سقفِ منطقی
    ratio = atk_cp / max(1, def_power)
    win_chance = max(0.1, min(0.9, ratio / (ratio + 1)))
    win = random.random() < win_chance

    result = {"win": win, "attacker_cp": atk_cp, "defense_power": def_power, "stolen": 0}

    if win:
        stolen = int(def_core.get("treasury", 0) * RAID_STEAL_PCT)
        def_core["treasury"] -= stolen
        attacker["zen"] = attacker.get("zen", 0) + stolen
        def_core["defense_losses"] = def_core.get("defense_losses", 0) + 1
        get_or_init_core(attacker)["raid_wins"] = get_or_init_core(attacker).get("raid_wins", 0) + 1
        result["stolen"] = stolen
        result["msg"] = (
            f"⚔️ **راید موفق بود!**\n"
            f"سیاه‌چالِ {defender.get('name','یه بازیکن')} رو شکستی و {stolen:,} Zen از خزانه‌ش دزدیدی."
        )
    else:
        attacker["zen"] = max(0, attacker.get("zen", 0) - RAID_LOSS_PENALTY)
        def_core["defense_wins"] = def_core.get("defense_wins", 0) + 1
        get_or_init_core(attacker)["raid_losses"] = get_or_init_core(attacker).get("raid_losses", 0) + 1
        result["msg"] = (
            f"🛡 **راید شکست خورد!**\n"
            f"سیاه‌چالِ {defender.get('name','یه بازیکن')} دفاعش رو نگه داشت — {RAID_LOSS_PENALTY:,} Zen از دست دادی."
        )

    attacker["dungeon_raid_cooldown"] = time.time() + RAID_COOLDOWN
    return result


def status_text(player: dict) -> str:
    core = get_or_init_core(player)
    pending = pending_income(player)
    lines = [
        f"🏰 **سیاه‌چالِ شخصیِ تو** — سطح {core['level']}\n",
        f"🛡 قدرتِ دفاعیِ کل: {total_defense_power(player):,}",
        f"💰 خزانه: {core.get('treasury',0):,} Zen (+{pending:,} در انتظارِ جمع‌آوری)",
        f"⚔️ دفاع: {core.get('defense_wins',0)} برد / {core.get('defense_losses',0)} باخت",
        f"🗡 راید: {core.get('raid_wins',0)} برد / {core.get('raid_losses',0)} باخت\n",
    ]
    if core["traps"]:
        lines.append("🕳 تله‌ها: " + ", ".join(TRAPS[t]["name"] for t in core["traps"]))
    else:
        lines.append("🕳 تله‌ها: هیچی چیده نشده.")
    if core.get("monster"):
        lines.append(f"👹 نگهبان: {MONSTERS[core['monster']]['name']}")
    else:
        lines.append("👹 نگهبان: کسی استخدام نشده.")
    return "\n".join(lines)
