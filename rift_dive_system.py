# ============================================================
#  ASTRAL ABYSS — Rift Dive 🌀 (روگ‌لایکِ شکاف‌های Abyss)
# ------------------------------------------------------------
#  یه شکافِ Abyss باز می‌شه؛ بازیکن اتاق‌به‌اتاق پیش می‌ره (نبرد/گنج/
#  معبد/استراحت). هر اتاق ریسک/ریوارد داره. هر چند اتاق یه‌بار
#  «دروازه‌ی خروج» ظاهر می‌شه: یا برداشت پاداشِ جمع‌شده (Cash Out)
#  یا ریسک کردن و رفتن عمیق‌تر برای پاداشِ بزرگ‌تر. اگه بین دو
#  دروازه بمیره، فقط چیزی که تا آخرین دروازه برداشت کرده رو نگه
#  می‌داره — بقیه (pending) از دست می‌ره. این تنشِ «ادامه یا کش‌اوت»
#  هستـه‌ی اصلیِ حالته (الگوی extraction-roguelike).
#
#  فایلِ منطق خالص — بدون import مستقیمِ aiogram. HP این حالت با HP
#  واقعیِ کاراکتر فرق داره (rift_hp)؛ مردن تو شکاف هیچ آسیبی به
#  کاراکترِ اصلی نمی‌زنه، فقط رانِ فعلی رو تموم می‌کنه.
# ============================================================
import random
import time
from datetime import datetime, timezone

from combat_power import calculate_combat_power

ENTRY_LEVEL = 15
EXTRACTION_INTERVAL = 3          # هر ۳ اتاق، یه دروازه‌ی خروج
BASE_ENEMY_POWER = 180           # قدرتِ دشمن تو عمقِ ۱
DEPTH_POWER_GROWTH = 1.14        # رشدِ نمایی قدرتِ دشمن به‌ازای هر عمق
CHIP_DAMAGE_MIN, CHIP_DAMAGE_MAX = 6, 16     # آسیبِ همیشگی حتی موقعِ بردن (٪ از rift_hp_max)
LOSS_DAMAGE_MIN, LOSS_DAMAGE_MAX = 30, 48    # آسیبِ باختنِ یه نبرد

# ─── انواع اتاق و وزن‌شون بر اساسِ عمق ──────────────────────────
def _room_weights(depth: int) -> dict:
    # هرچی عمیق‌تر، شانسِ elite/shrine بیشتر می‌شه، rest کمتر می‌شه.
    danger = min(depth, 20)
    return {
        "combat":  55 - danger * 0.6,
        "elite":   8 + danger * 0.9,
        "treasure": 15,
        "shrine":  12 + danger * 0.3,
        "rest":    10 - danger * 0.3,
    }

def _roll_room_type(depth: int) -> str:
    weights = _room_weights(depth)
    weights = {k: max(1.0, v) for k, v in weights.items()}
    total = sum(weights.values())
    r = random.uniform(0, total)
    acc = 0
    for k, w in weights.items():
        acc += w
        if r <= acc:
            return k
    return "combat"

# ─── برکت‌ها/نفرین‌های معبد (هر گزینه یه ترید-آفه) ──────────────
SHRINE_OPTIONS = {
    "berserker": {"name": "🔥 خشمِ نبرد", "desc": "قدرت +18٪ | سقفِ HPِ رانِ فعلی -12٪",
                  "power_mult": 0.18, "hp_max_mult": -0.12},
    "warded":    {"name": "🛡 حفاظتِ باستانی", "desc": "سقفِ HPِ رانِ فعلی +22٪",
                  "hp_max_mult": 0.22},
    "fortune":   {"name": "🍀 اقبال", "desc": "درآمدِ Zen و Shard +30٪ | قدرت -8٪",
                  "zen_mult": 0.30, "shard_mult": 0.30, "power_mult": -0.08},
    "vampiric":  {"name": "🩸 پیوندِ خونی", "desc": "بعدِ هر برد، ۶٪ HP رانِ فعلی شفا می‌گیری",
                  "lifesteal": 0.06},
    "reckless":  {"name": "⚔️ بی‌پروایی", "desc": "قدرت +30٪ | آسیبِ ورودی +20٪",
                  "power_mult": 0.30, "incoming_mult": 0.20},
    "guarded":   {"name": "🧱 مراقبت", "desc": "آسیبِ ورودی -20٪ | درآمدِ Zen -10٪",
                  "incoming_mult": -0.20, "zen_mult": -0.10},
}

def _shrine_pair() -> list[str]:
    return random.sample(list(SHRINE_OPTIONS.keys()), 2)

# ─── کمکی‌های محاسبه‌ی رانِ فعلی ────────────────────────────────
def _run(player: dict) -> dict | None:
    return player.get("rift_run")

def is_in_run(player: dict) -> bool:
    r = player.get("rift_run")
    return bool(r and r.get("active"))

def can_start(player: dict) -> tuple[bool, str]:
    if is_in_run(player):
        return False, "❌ یه رانِ فعال داری — اول تمومش کن."
    if player.get("level", 1) < ENTRY_LEVEL:
        return False, f"❌ برای ورود به شکاف باید حداقل سطح {ENTRY_LEVEL} باشی."
    return True, ""

def _new_run() -> dict:
    return {
        "active": True,
        "depth": 0,
        "rift_hp": 100.0,
        "rift_hp_max": 100.0,
        "power_mult": 1.0,
        "incoming_mult": 1.0,
        "zen_mult": 1.0,
        "shard_mult": 1.0,
        "lifesteal": 0.0,
        "blessings": [],
        "banked_zen": 0,
        "banked_shards": 0,
        "banked_items": [],
        "pending_zen": 0,
        "pending_shards": 0,
        "pending_items": [],
        "room": None,          # اتاقِ فعلیِ حل‌نشده (منتظرِ اکشنِ بازیکن)
        "log": [],             # آخرین خط‌های رخداد، برای نمایش تو پنل
        "started_at": time.time(),
    }

def start_run(player: dict) -> dict:
    player["rift_run"] = _new_run()
    return player["rift_run"]

def _enemy_power(depth: int) -> float:
    return BASE_ENEMY_POWER * (DEPTH_POWER_GROWTH ** max(0, depth - 1))

def _effective_power(player: dict, run: dict) -> float:
    cp = calculate_combat_power(player)
    return cp * max(0.2, 1.0 + run["power_mult"])

def _apply_damage(run: dict, pct: float):
    run["rift_hp"] = max(0.0, run["rift_hp"] - (run["rift_hp_max"] * pct / 100.0) * max(0.1, 1.0 + run["incoming_mult"]))

def _heal(run: dict, pct: float):
    run["rift_hp"] = min(run["rift_hp_max"], run["rift_hp"] + run["rift_hp_max"] * pct / 100.0)

def _reward_scale(depth: int, player_level: int) -> float:
    return depth * (1.0 + player_level * 0.015)

# ─── ورود به اتاقِ بعدی ─────────────────────────────────────────
def enter_next_room(player: dict) -> dict:
    """اتاقِ جدید می‌سازه و تو run['room'] می‌ذاره. اگه اتاق نیازِ تصمیم داره
    (shrine) منتظرِ choose_shrine می‌مونه؛ وگرنه خودش با resolve_current_room حل می‌شه."""
    run = _run(player)
    run["depth"] += 1
    rtype = _roll_room_type(run["depth"])
    room = {"type": rtype, "resolved": False}
    if rtype == "shrine":
        room["options"] = _shrine_pair()
    run["room"] = room
    run["log"] = []
    return room

def is_extraction_gate(player: dict) -> bool:
    run = _run(player)
    return bool(run) and run["depth"] > 0 and run["depth"] % EXTRACTION_INTERVAL == 0 and (run["room"] is None or run["room"].get("resolved"))

def resolve_current_room(player: dict) -> dict:
    """اتاقِ فعلی رو حل می‌کنه (combat/elite/treasure/rest). shrine جدا با
    choose_shrine حل می‌شه. خروجی: {ok, log:[str], dead:bool}"""
    run = _run(player)
    room = run["room"]
    rtype = room["type"]
    log = []
    dead = False

    if rtype in ("combat", "elite"):
        is_elite = rtype == "elite"
        enemy_p = _enemy_power(run["depth"]) * (1.6 if is_elite else 1.0)
        my_p = _effective_power(player, run)
        ratio = my_p / max(1.0, enemy_p)
        win_chance = max(0.05, min(0.95, 0.35 + 0.5 * (ratio - 1.0)))
        won = random.random() < win_chance

        if won:
            _apply_damage(run, random.uniform(CHIP_DAMAGE_MIN, CHIP_DAMAGE_MAX) * (0.6 if ratio > 1.3 else 1.0))
            if run["lifesteal"]:
                _heal(run, run["lifesteal"] * 100)
            scale = _reward_scale(run["depth"], player.get("level", 1)) * (2.2 if is_elite else 1.0)
            zen_gain = int(35 * scale * max(0.3, 1.0 + run["zen_mult"]))
            shard_gain = int((2 + run["depth"] // 2) * (2.0 if is_elite else 1.0) * max(0.3, 1.0 + run["shard_mult"]))
            run["pending_zen"] += zen_gain
            run["pending_shards"] += shard_gain
            tag = "👹 نخبه" if is_elite else "⚔️ نبرد"
            log.append(f"{tag} — بردی! +{zen_gain:,} Zen | +{shard_gain} 🔹Shard")
            if is_elite and random.random() < 0.55:
                run["pending_items"].append({"depth": run["depth"], "elite": True})
                log.append("💠 یه تجهیزات از نخبه افتاد (تو صندوقِ راه مونده تا برداشت کنی).")
        else:
            dmg_pct = random.uniform(LOSS_DAMAGE_MIN, LOSS_DAMAGE_MAX)
            _apply_damage(run, dmg_pct)
            log.append(f"💥 باختی! آسیبِ سنگین خوردی ({dmg_pct:.0f}٪ از HPِ ران).")
            if run["rift_hp"] <= 0:
                dead = True
                log.append("☠️ HPِ رانت صفر شد — شکاف بستـه می‌شه.")

    elif rtype == "treasure":
        scale = _reward_scale(run["depth"], player.get("level", 1))
        zen_gain = int(25 * scale * max(0.3, 1.0 + run["zen_mult"]))
        shard_gain = int((3 + run["depth"] // 2) * max(0.3, 1.0 + run["shard_mult"]))
        run["pending_zen"] += zen_gain
        run["pending_shards"] += shard_gain
        drop_chance = min(0.75, 0.15 + run["depth"] * 0.03)
        if random.random() < drop_chance:
            run["pending_items"].append({"depth": run["depth"], "elite": False})
            log.append(f"📦 صندوقِ گنج — +{zen_gain:,} Zen | +{shard_gain} 🔹Shard | یه تجهیزات هم پیدا شد!")
        else:
            log.append(f"📦 صندوقِ گنج — +{zen_gain:,} Zen | +{shard_gain} 🔹Shard")

    elif rtype == "rest":
        heal_pct = random.uniform(18, 30)
        _heal(run, heal_pct)
        log.append(f"🕯 استراحت — {heal_pct:.0f}٪ HPِ ران رو برگردوندی. ({run['rift_hp']:.0f}/{run['rift_hp_max']:.0f})")

    room["resolved"] = True
    run["log"] = log
    if dead:
        run["active"] = False
    return {"ok": True, "log": log, "dead": dead, "room_type": rtype}

def choose_shrine(player: dict, option_id: str) -> list[str]:
    run = _run(player)
    room = run["room"]
    if room["type"] != "shrine" or room.get("resolved"):
        return ["❌ این معبد قبلاً استفاده شده."]
    opt = SHRINE_OPTIONS.get(option_id)
    if not opt or option_id not in room.get("options", []):
        return ["❌ گزینه‌ی نامعتبر."]

    run["power_mult"] += opt.get("power_mult", 0.0)
    run["incoming_mult"] += opt.get("incoming_mult", 0.0)
    run["zen_mult"] += opt.get("zen_mult", 0.0)
    run["shard_mult"] += opt.get("shard_mult", 0.0)
    run["lifesteal"] += opt.get("lifesteal", 0.0)
    if opt.get("hp_max_mult"):
        old_max = run["rift_hp_max"]
        run["rift_hp_max"] = max(30.0, old_max * (1.0 + opt["hp_max_mult"]))
        run["rift_hp"] = min(run["rift_hp"], run["rift_hp_max"])
    run["blessings"].append(option_id)
    room["resolved"] = True
    log = [f"✨ {opt['name']} گرفته شد — {opt['desc']}"]
    run["log"] = log
    return log

def extract_at_gate(player: dict) -> dict:
    """دروازه‌ی خروج: pending رو بانک می‌کنه (ریسکِ ازدست‌دادنش تموم می‌شه)
    ولی ران ادامه پیدا می‌کنه — بازیکن می‌تونه بعدش هم عمیق‌تر بره."""
    run = _run(player)
    run["banked_zen"] += run["pending_zen"]
    run["banked_shards"] += run["pending_shards"]
    run["banked_items"].extend(run["pending_items"])
    banked = {"zen": run["pending_zen"], "shards": run["pending_shards"], "items": len(run["pending_items"])}
    run["pending_zen"] = 0
    run["pending_shards"] = 0
    run["pending_items"] = []
    return banked

def _week_id() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.isocalendar().year}-W{now.isocalendar().week}"

def finalize_run(player: dict, died: bool) -> dict:
    """ران رو می‌بنده: banked رو واقعاً به پلیر می‌ده (pending اگه died=True
    از دست می‌ره، وگرنه اون هم بانک می‌شه چون بازیکن با پای خودش کش‌اوتِ نهایی زده)."""
    run = _run(player)
    if not died:
        run["banked_zen"] += run["pending_zen"]
        run["banked_shards"] += run["pending_shards"]
        run["banked_items"].extend(run["pending_items"])

    from item_system import merge_into_inventory
    zen_gain = run["banked_zen"]
    shard_gain = run["banked_shards"]
    items = _generate_reward_items(player, run)

    player["zen"] = player.get("zen", 0) + zen_gain
    player["rift_shards"] = player.get("rift_shards", 0) + shard_gain
    for it in items:
        merge_into_inventory(player.setdefault("inventory", []), it)

    depth_reached = run["depth"]
    player["rift_best_depth"] = max(player.get("rift_best_depth", 0), depth_reached)

    wid = _week_id()
    if player.get("rift_week_id") != wid:
        player["rift_week_id"] = wid
        player["rift_best_depth_week"] = 0
    player["rift_best_depth_week"] = max(player.get("rift_best_depth_week", 0), depth_reached)

    stats = player.setdefault("rift_stats", {"runs": 0, "deaths": 0, "total_rooms": 0})
    stats["runs"] = stats.get("runs", 0) + 1
    stats["deaths"] = stats.get("deaths", 0) + (1 if died else 0)
    stats["total_rooms"] = stats.get("total_rooms", 0) + depth_reached

    summary = {
        "died": died,
        "depth_reached": depth_reached,
        "zen_gain": zen_gain,
        "shard_gain": shard_gain,
        "items_gained": len(items),
        "lost_pending_zen": run["pending_zen"] if died else 0,
        "lost_pending_shards": run["pending_shards"] if died else 0,
    }
    player["rift_run"] = None
    return summary

def _generate_reward_items(player: dict, run: dict) -> list[dict]:
    from item_system import generate_random_equipment
    items = []
    for entry in run["banked_items"]:
        depth = entry.get("depth", 1)
        forced_rarity = "legendary" if (entry.get("elite") and depth >= 12) else None
        items.append(generate_random_equipment(player.get("level", 1), forced_rarity=forced_rarity))
    return items

def get_leaderboard(n: int = 10) -> list[dict]:
    from database import all_players
    wid = _week_id()
    players = all_players()
    ranked = []
    for p in players.values():
        if p.get("rift_week_id") == wid and p.get("rift_best_depth_week", 0) > 0:
            ranked.append(p)
    ranked.sort(key=lambda p: p.get("rift_best_depth_week", 0), reverse=True)
    return ranked[:n]
