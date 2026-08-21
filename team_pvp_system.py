# ============================================================
#  ASTRAL ABYSS — Team PvP Engine (Squad Battles)
#  ۲به۲ / ۳به۳ / ۴به۴ / ۵به۵ — نبردِ گروهیِ هم‌زمان با:
#  🎯 آتش متمرکز (Focus Fire) · 🛡 محافظت از هم‌تیمی (Guard)
#  🌀 گیج‌بار تیمی (Team Synergy) → ⚡ اولتیمیتِ تیمی
#  🔗کومبو · 🔥مومنتوم · 👻دوج · 🔪فینیشینگ‌بلو · ☠️ DOT
# ============================================================
from __future__ import annotations
import time
import random
import uuid
from dataclasses import dataclass, field

from pvp import generate_abilities, ABILITY_SLOTS
from database import aget_player, asave_player

# ────────────────────────────────────────────────────────────
SQUAD_SIZES = [2, 3, 4, 5]
ROUND_TIMEOUT      = 35     # ثانیه‌ی مهلتِ هر راند برای کل تیم
FIGHT_MAX_ROUNDS   = 25     # سقفِ راند — جلوگیری از گیرکردنِ ابدی
LOBBY_TIMEOUT      = 300    # ۵ دقیقه مهلتِ پرشدنِ لابی
QUEUE_TIMEOUT      = 240    # ۴ دقیقه مهلتِ صفِ سریع

DODGE_BASE_CHANCE      = 0.07
DESPERATION_HP_PCT     = 0.20
DESPERATION_DMG_BONUS  = 0.18
EXECUTE_HP_PCT         = 0.20
EXECUTE_DMG_BONUS      = 0.28
COMBO_DMG_PER_STACK    = 0.04
COMBO_MAX_STACK        = 5
MOMENTUM_MAX           = 100
MOMENTUM_HIT_FLAT      = 10
MOMENTUM_CRIT_FLAT     = 16
MOMENTUM_TAKEN_FLAT    = 6
FOCUS_FIRE_BONUS_PCT   = 0.14     # هر حمله‌کننده‌ی اضافه رو یه هدف
GUARD_REDIRECT_PCT     = 0.55     # درصدی از دمیجِ هم‌تیمی که گارد جذب می‌کنه
SYNERGY_MAX            = 100
SYNERGY_PER_DMG        = 0.045    # هر واحد دمیج چقدر گیج‌بار تیمی پر می‌کنه
TEAM_ULT_DMG_MULT      = 2.4      # ضریبِ اولتیمیتِ تیمی رو میانگینِ دمیجِ تیم

WIN_ZEN_BASE   = 900
LOSE_ZEN_BASE  = 200
WIN_POINTS     = 28
LOSE_POINTS    = -14


def _elig_size_label(n: int) -> str:
    return f"{n} به {n}"


# ────────────────────────────────────────────────────────────
#  جنگجو (عضوِ یه اسکواد داخلِ نبرد)
# ────────────────────────────────────────────────────────────
@dataclass
class Warrior:
    uid: int
    name: str
    character: str
    level: int
    element: str
    team: str                      # "A" | "B"
    max_hp: int
    hp: int
    base_dmg: int
    abilities: list = field(default_factory=list)
    passive: dict = field(default_factory=dict)
    skill_bonuses: dict = field(default_factory=dict)
    energy: int = 50
    alive: bool = True
    shield: int = 0
    guarding_uid: int | None = None     # اگه این‌راند داره از یه هم‌تیمی محافظت می‌کنه
    combo: int = 0
    momentum: int = 0
    dots: list = field(default_factory=list)
    stunned: bool = False
    total_dmg: int = 0
    total_taken: int = 0
    kills: int = 0
    biggest_hit: int = 0
    finisher_count: int = 0
    dodge_count: int = 0
    mvp_score: float = 0.0


@dataclass
class SquadFight:
    fight_id: str
    size: int
    team_a: list = field(default_factory=list)
    team_b: list = field(default_factory=list)
    round_no: int = 1
    phase: str = "action_select"        # action_select | resolving | ended
    pending: dict = field(default_factory=dict)     # uid -> action dict
    synergy: dict = field(default_factory=lambda: {"A": 0, "B": 0})
    ult_charged: dict = field(default_factory=lambda: {"A": False, "B": False})
    winner: str | None = None
    created_at: float = field(default_factory=time.time)
    round_deadline: float = field(default_factory=lambda: time.time() + ROUND_TIMEOUT)
    prompt_msgs: dict = field(default_factory=dict)     # uid -> message_id
    round_log: list = field(default_factory=list)

    def all_warriors(self):
        return self.team_a + self.team_b

    def find(self, uid: int) -> Warrior | None:
        for w in self.all_warriors():
            if w.uid == uid:
                return w
        return None

    def team_of(self, uid: int) -> str | None:
        w = self.find(uid)
        return w.team if w else None

    def enemy_team(self, team: str):
        return self.team_b if team == "A" else self.team_a

    def own_team(self, team: str):
        return self.team_a if team == "A" else self.team_b

    def alive_in(self, team_list):
        return [w for w in team_list if w.alive]


# ─── حافظه‌ی سراسری (in-memory) ────────────────────────────────
active_fights: dict[str, SquadFight] = {}
player_in_fight: dict[int, str] = {}

lobbies: dict[str, dict] = {}          # lobby_id -> lobby dict
player_in_lobby: dict[int, str] = {}   # uid -> lobby_id

queue: dict[int, list] = {n: [] for n in SQUAD_SIZES}   # size -> [uid, ...]
player_in_queue: dict[int, int] = {}   # uid -> size


def get_fight_by_uid(uid: int) -> SquadFight | None:
    fid = player_in_fight.get(uid)
    return active_fights.get(fid) if fid else None


# ────────────────────────────────────────────────────────────
#  ساختِ جنگجو از رویِ پروفایل بازیکن
# ────────────────────────────────────────────────────────────
def build_warrior(uid: int, player: dict, char_data: dict, team: str) -> Warrior:
    from skill_tree import get_skill_bonuses, effective_max_hp
    try:
        from loot_engine import get_set_bonus_stats
        setb = get_set_bonus_stats(player)
    except Exception:
        setb = {}
    abilities, passive = generate_abilities(char_data)
    skb = get_skill_bonuses(player)
    max_hp = int(effective_max_hp(player) * (1 + setb.get("hp_pct", 0)))
    max_hp = max(60, max_hp)
    return Warrior(
        uid=uid, name=player.get("name", "Bearer"), character=player.get("character", "?"),
        level=player.get("level", 1), element=char_data.get("element", "—"), team=team,
        max_hp=max_hp, hp=max_hp, base_dmg=char_data.get("base_dmg", 10),
        abilities=abilities, passive=passive, skill_bonuses=skb, energy=50,
    )


def hp_bar(hp: int, max_hp: int, length: int = 8) -> str:
    hp = max(0, hp)
    pct = hp / max_hp if max_hp else 0
    block = "🟥" if pct <= 0.20 else "🟨" if pct <= 0.50 else "🟩"
    filled = int(pct * length)
    return block * filled + "⬜" * (length - filled)


def synergy_bar(value: int, length: int = 6) -> str:
    filled = int((value / SYNERGY_MAX) * length)
    filled = max(0, min(length, filled))
    return "🌀" * filled + "▫️" * (length - filled)


# ────────────────────────────────────────────────────────────
#  لابی — بازی با دوستان
# ────────────────────────────────────────────────────────────
def create_lobby(host_uid: int, host_name: str, size: int, chat_id: int) -> dict:
    lobby_id = uuid.uuid4().hex[:8]
    lobby = {
        "id": lobby_id, "host": host_uid, "size": size, "chat_id": chat_id,
        "team_a": [{"uid": host_uid, "name": host_name}],
        "team_b": [],
        "created_at": time.time(),
    }
    lobbies[lobby_id] = lobby
    player_in_lobby[host_uid] = lobby_id
    return lobby


def lobby_join(lobby_id: str, uid: int, name: str, team: str) -> tuple[bool, str]:
    lobby = lobbies.get(lobby_id)
    if not lobby:
        return False, "❌ این لابی دیگه وجود نداره."
    if uid in player_in_lobby:
        return False, "⚠️ تو همین الان تو یه لابی دیگه‌ای."
    key = "team_a" if team == "A" else "team_b"
    other = "team_b" if team == "A" else "team_a"
    if any(m["uid"] == uid for m in lobby[key] + lobby[other]):
        return False, "⚠️ تو همین الان تو این لابی هستی."
    if len(lobby[key]) >= lobby["size"]:
        return False, "❌ این تیم پُره."
    lobby[key].append({"uid": uid, "name": name})
    player_in_lobby[uid] = lobby_id
    return True, f"✅ به تیم {'A' if team=='A' else 'B'} پیوستی!"


def lobby_leave(uid: int):
    lobby_id = player_in_lobby.pop(uid, None)
    if not lobby_id:
        return
    lobby = lobbies.get(lobby_id)
    if not lobby:
        return
    lobby["team_a"] = [m for m in lobby["team_a"] if m["uid"] != uid]
    lobby["team_b"] = [m for m in lobby["team_b"] if m["uid"] != uid]
    if not lobby["team_a"] and not lobby["team_b"]:
        lobbies.pop(lobby_id, None)


def lobby_is_full(lobby: dict) -> bool:
    return len(lobby["team_a"]) == lobby["size"] and len(lobby["team_b"]) == lobby["size"]


def lobby_text(lobby: dict) -> str:
    lines = [
        f"⚔️ **لابی پی‌وی‌پی تیمی — {_elig_size_label(lobby['size'])}**",
        f"⏳ تا شروع باید هر دو تیم پُر بشن.\n",
        f"🔴 **تیم A** ({len(lobby['team_a'])}/{lobby['size']})",
    ]
    lines += [f"   • {m['name']}" for m in lobby["team_a"]] or ["   —"]
    lines.append(f"\n🔵 **تیم B** ({len(lobby['team_b'])}/{lobby['size']})")
    lines += [f"   • {m['name']}" for m in lobby["team_b"]] or ["   —"]
    return "\n".join(lines)


# ────────────────────────────────────────────────────────────
#  صفِ سریع — متچ‌میکینگِ خودکار بر اساسِ CP
# ────────────────────────────────────────────────────────────
def queue_join(uid: int, size: int) -> tuple[bool, str]:
    if uid in player_in_queue or uid in player_in_lobby or get_fight_by_uid(uid):
        return False, "⚠️ همین الان تو یه صف/لابی/نبرد دیگه‌ای."
    queue[size].append(uid)
    player_in_queue[uid] = size
    return True, f"⏳ وارد صفِ {_elig_size_label(size)} شدی — به محضِ پیداشدنِ حریف خبرت می‌کنیم."


def queue_leave(uid: int):
    size = player_in_queue.pop(uid, None)
    if size is not None and uid in queue.get(size, []):
        queue[size].remove(uid)


def queue_try_match(size: int) -> list | None:
    """اگه به تعدادِ کافی صف پُر شده باشه (2*size)، دو تیمِ متعادل برمی‌گردونه و صف رو خالی می‌کنه."""
    need = size * 2
    if len(queue[size]) < need:
        return None
    pool = queue[size][:need]
    queue[size] = queue[size][need:]
    for uid in pool:
        player_in_queue.pop(uid, None)
    return pool


def balance_teams_by_cp(uids: list, cps: dict) -> tuple[list, list]:
    """درفت متناوب (snake draft) بر اساسِ CP برای تعادلِ تیم‌ها."""
    ordered = sorted(uids, key=lambda u: -cps.get(u, 0))
    team_a, team_b = [], []
    for i, uid in enumerate(ordered):
        # 0,3,4,7,8.. -> A ; 1,2,5,6.. -> B  (snake)
        block = i // 2
        if (block % 2 == 0) == (i % 2 == 0):
            team_a.append(uid)
        else:
            team_b.append(uid)
    # ایمنی: اگه به هر دلیلی نامساوی شد، از انتهای تیمِ بزرگ‌تر جابه‌جا کن
    while len(team_a) > len(team_b):
        team_b.append(team_a.pop())
    while len(team_b) > len(team_a):
        team_a.append(team_b.pop())
    return team_a, team_b


# ────────────────────────────────────────────────────────────
#  شروعِ نبرد
# ────────────────────────────────────────────────────────────
def start_fight(size: int, team_a_data: list, team_b_data: list) -> SquadFight:
    """team_a_data/team_b_data: [(uid, player_dict, char_data), ...]"""
    fight_id = uuid.uuid4().hex[:10]
    ta = [build_warrior(uid, p, c, "A") for uid, p, c in team_a_data]
    tb = [build_warrior(uid, p, c, "B") for uid, p, c in team_b_data]
    fight = SquadFight(fight_id=fight_id, size=size, team_a=ta, team_b=tb)
    active_fights[fight_id] = fight
    for w in fight.all_warriors():
        player_in_fight[w.uid] = fight_id
    return fight


# ────────────────────────────────────────────────────────────
#  مکانیک‌های کمکی
# ────────────────────────────────────────────────────────────
def _roll_dodge(target: Warrior) -> bool:
    chance = DODGE_BASE_CHANCE + target.skill_bonuses.get("dodge_chance", 0)
    return random.random() < min(0.35, chance)


def _gain_momentum(actor: Warrior, was_crit: bool):
    actor.momentum = min(MOMENTUM_MAX, actor.momentum + (MOMENTUM_CRIT_FLAT if was_crit else MOMENTUM_HIT_FLAT))


def _combo_mult(actor: Warrior) -> float:
    return 1 + min(actor.combo, COMBO_MAX_STACK) * COMBO_DMG_PER_STACK


def _add_synergy(fight: SquadFight, team: str, dmg: int):
    if fight.ult_charged[team]:
        return
    fight.synergy[team] = min(SYNERGY_MAX, fight.synergy[team] + dmg * SYNERGY_PER_DMG)
    if fight.synergy[team] >= SYNERGY_MAX:
        fight.ult_charged[team] = True


def _compute_dmg(fight: SquadFight, actor: Warrior, target: Warrior, base_mult: float) -> tuple[int, bool, bool]:
    crit_chance = 0.14 + actor.skill_bonuses.get("crit_chance", 0)
    crit_dmg_bonus = 0.55 + actor.skill_bonuses.get("crit_dmg_bonus", 0)
    is_crit = random.random() < min(0.65, crit_chance)
    dmg = actor.base_dmg * (1.5 + actor.level * 0.12) * base_mult
    dmg *= _combo_mult(actor)
    dmg *= (1 + actor.skill_bonuses.get("dmg_pct", 0))
    is_desperation = actor.hp / actor.max_hp <= DESPERATION_HP_PCT if actor.max_hp else False
    if is_desperation:
        dmg *= (1 + DESPERATION_DMG_BONUS)
    is_execute = target.hp / target.max_hp <= EXECUTE_HP_PCT if target.max_hp else False
    if is_execute:
        dmg *= (1 + EXECUTE_DMG_BONUS)
    if is_crit:
        dmg *= (1 + crit_dmg_bonus)
    dmg *= random.uniform(0.9, 1.12)
    return max(1, int(dmg)), is_crit, is_execute


def _apply_damage(fight: SquadFight, actor: Warrior, target: Warrior, dmg: int, logs: list) -> int:
    """گارد را لحاظ می‌کنه (اگه یه هم‌تیمیِ دیگه داره ازش محافظت می‌کنه)."""
    guardian = None
    for w in fight.own_team(target.team):
        if w.alive and w.guarding_uid == target.uid and w is not target:
            guardian = w
            break
    dealt_to_target = dmg
    if guardian is not None:
        redirect = int(dmg * GUARD_REDIRECT_PCT)
        dealt_to_target = dmg - redirect
        _absorb(guardian, redirect, logs, protecting=target.name)
    _absorb(target, dealt_to_target, logs, protecting=None)
    actor.total_dmg += dmg
    if dmg > actor.biggest_hit:
        actor.biggest_hit = dmg
    _add_synergy(fight, actor.team, dmg)
    return dmg


def _absorb(warrior: Warrior, dmg: int, logs: list, protecting: str | None):
    remain = dmg
    if warrior.shield > 0:
        absorbed = min(warrior.shield, remain)
        warrior.shield -= absorbed
        remain -= absorbed
    warrior.hp = max(0, warrior.hp - remain)
    warrior.total_taken += dmg
    if protecting:
        logs.append(f"🛡 {warrior.name} با گارد، {remain} آسیب رو به‌جای {protecting} گرفت!")
    if warrior.hp <= 0 and warrior.alive:
        warrior.alive = False
        logs.append(f"☠️ **{warrior.name} از پا افتاد!**")


def _tick_dots(warrior: Warrior, logs: list):
    if not warrior.alive:
        return
    for dot in list(warrior.dots):
        dmg = max(1, int(warrior.max_hp * dot["dmg_pct"]))
        warrior.hp = max(0, warrior.hp - dmg)
        warrior.total_taken += dmg
        icon = {"bleed": "🩸", "poison": "☣️", "burn": "🔥"}.get(dot["kind"], "💢")
        logs.append(f"{icon} {warrior.name} از {dot['kind']} {dmg} آسیب دید")
        dot["turns"] -= 1
        if dot["turns"] <= 0:
            warrior.dots.remove(dot)
        if warrior.hp <= 0 and warrior.alive:
            warrior.alive = False
            logs.append(f"☠️ **{warrior.name} از پا افتاد!**")


# ────────────────────────────────────────────────────────────
#  حلِ راند — همه‌ی اکشن‌های جمع‌شده رو با هم اجرا می‌کنه
# ────────────────────────────────────────────────────────────
def resolve_round(fight: SquadFight) -> list[str]:
    logs: list[str] = []
    alive = [w for w in fight.all_warriors() if w.alive]

    # ۱) انرژی و کول‌داون‌ها
    for w in alive:
        w.energy = min(100, w.energy + 22)
        w.guarding_uid = None

    # ۲) پردازشِ اول: دفاع/گارد (شیلد و ریدایرکت رو ست می‌کنن)
    for w in alive:
        action = fight.pending.get(w.uid) or {"type": "attack", "target": None}
        if action["type"] == "defend":
            shield_amt = int(w.max_hp * 0.22)
            w.shield += shield_amt
            logs.append(f"🛡 {w.name} سپر گرفت (+{shield_amt})")
        elif action["type"] == "guard":
            ally_uid = action.get("target")
            ally = fight.find(ally_uid)
            if ally and ally.alive and ally.team == w.team:
                w.guarding_uid = ally_uid
                logs.append(f"🤝 {w.name} داره از {ally.name} محافظت می‌کنه!")

    # ۳) هدف‌گیریِ آتشِ متمرکز — بشمار چندتا حمله‌کننده رو یه هدف رفتن
    target_counts: dict[int, int] = {}
    for w in alive:
        action = fight.pending.get(w.uid)
        if not action:
            continue
        if action["type"] in ("attack", "ability"):
            t = action.get("target")
            if t:
                target_counts[t] = target_counts.get(t, 0) + 1

    # ۴) پردازشِ حمله/ابیلیتی — به ترتیبِ تصادفی برای هیجان
    attackers = [w for w in alive if (fight.pending.get(w.uid) or {}).get("type") in ("attack", "ability")]
    random.shuffle(attackers)

    for actor in attackers:
        if not actor.alive:
            continue
        action = fight.pending[actor.uid]
        target = fight.find(action.get("target"))
        if not target or not target.alive:
            # هدف از پیش مرده — به نزدیک‌ترین دشمنِ زنده منتقل کن
            enemies = fight.alive_in(fight.enemy_team(actor.team))
            if not enemies:
                continue
            target = random.choice(enemies)

        if actor.stunned:
            logs.append(f"😵 {actor.name} گیج بود و نتونست حرکت کنه.")
            actor.stunned = False
            continue

        if _roll_dodge(target):
            actor.combo = 0
            target.dodge_count += 1
            logs.append(f"👻 {target.name} از حمله‌ی {actor.name} جاخالی داد!")
            continue

        is_ability = action["type"] == "ability"
        ab = None
        base_mult = 1.0
        if is_ability:
            idx = action.get("ability_idx", 0)
            if 0 <= idx < len(actor.abilities):
                ab = actor.abilities[idx]
            if ab and actor.energy >= ab["cost"]:
                actor.energy -= ab["cost"]
                base_mult = ab.get("dmg_mult", 1.0)
                if ab["kind"] == "cc" and random.random() < 0.55:
                    target.stunned = True
                    logs.append(f"🌀 {actor.name} با {ab['name']} {target.name} رو گیج کرد!")
                if ab["kind"] == "ultimate":
                    logs.append(f"💥 **{actor.name} اولتیمیتِ {ab['name']} رو زد!**")
            else:
                is_ability = False
                base_mult = 1.0

        dmg, is_crit, is_execute = _compute_dmg(fight, actor, target, base_mult)
        # ─── بونوسِ آتشِ متمرکز ───
        extra_attackers = target_counts.get(target.uid, 1) - 1
        if extra_attackers > 0:
            dmg = int(dmg * (1 + extra_attackers * FOCUS_FIRE_BONUS_PCT))

        _apply_damage(fight, actor, target, dmg, logs)
        actor.combo = min(COMBO_MAX_STACK, actor.combo + 1)
        _gain_momentum(actor, is_crit)
        _gain_momentum(target, False)
        target.momentum = min(MOMENTUM_MAX, target.momentum + MOMENTUM_TAKEN_FLAT)

        tag = "🔗کومبو" if actor.combo > 1 else ""
        crit_tag = " 💥کریتیکال!" if is_crit else ""
        exec_tag = " 🔪فینیشینگ‌بلو!" if is_execute else ""
        focus_tag = " 🎯آتشِ متمرکز!" if extra_attackers > 0 else ""
        verb = f"با {ab['name']}" if is_ability and ab else "با حمله‌ی معمولی"
        logs.append(f"⚔️ {actor.name} {verb} به {target.name} **{dmg}** آسیب زد{crit_tag}{exec_tag}{focus_tag} {tag}".rstrip())
        if is_execute:
            actor.finisher_count += 1
        if not target.alive:
            actor.kills += 1

    # ۵) اولتیمیتِ تیمی — اگه گیج‌بار پُر شده باشه
    for team in ("A", "B"):
        if fight.ult_charged[team]:
            own = fight.alive_in(fight.own_team(team))
            enemies = fight.alive_in(fight.enemy_team(team))
            if own and enemies:
                avg_dmg = sum(w.base_dmg for w in own) / len(own)
                nuke = int(avg_dmg * TEAM_ULT_DMG_MULT * (1.4 + 0.15 * len(own)))
                logs.append(f"🌀⚡ **گیج‌بارِ تیمِ {team} پر شد — طوفانِ تیمی رها شد!**")
                for e in enemies:
                    portion = int(nuke / len(enemies))
                    _absorb(e, portion, logs, protecting=None)
                    logs.append(f"   💢 {e.name} از طوفانِ تیمی {portion} آسیب دید")
            fight.ult_charged[team] = False
            fight.synergy[team] = 0

    # ۶) DOT تیک
    for w in alive:
        _tick_dots(w, logs)

    # ۷) پایانِ راند
    fight.pending = {}
    fight.round_no += 1
    fight.round_deadline = time.time() + ROUND_TIMEOUT

    a_alive = fight.alive_in(fight.team_a)
    b_alive = fight.alive_in(fight.team_b)
    if not a_alive and not b_alive:
        fight.winner = "draw"
        fight.phase = "ended"
    elif not a_alive:
        fight.winner = "B"
        fight.phase = "ended"
    elif not b_alive:
        fight.winner = "A"
        fight.phase = "ended"
    elif fight.round_no > FIGHT_MAX_ROUNDS:
        # سقفِ راند — تیمی که مجموع HP٪ بیشتری داره برنده‌ست
        a_pct = sum(w.hp for w in a_alive) / max(1, sum(w.max_hp for w in a_alive))
        b_pct = sum(w.hp for w in b_alive) / max(1, sum(w.max_hp for w in b_alive))
        fight.winner = "A" if a_pct >= b_pct else "B"
        fight.phase = "ended"
        logs.append("⏱ راندها تموم شد — نبرد بر اساسِ HPِ باقی‌مونده تعیین‌تکلیف شد.")

    return logs


def team_status_text(fight: SquadFight) -> str:
    def block(team_list, tag):
        lines = [f"{tag} تیم:"]
        for w in team_list:
            status = "" if w.alive else " 💀"
            shield = f" 🛡{w.shield}" if w.shield else ""
            lines.append(f"   {hp_bar(w.hp, w.max_hp, 6)} {w.hp}/{w.max_hp} — {w.name}{shield}{status}")
        return "\n".join(lines)

    return (
        f"🔴 {block(fight.team_a, '🔴')}\n"
        f"   {synergy_bar(fight.synergy['A'])} گیج‌بارِ تیمی\n\n"
        f"🔵 {block(fight.team_b, '🔵')}\n"
        f"   {synergy_bar(fight.synergy['B'])} گیج‌بارِ تیمی"
    )


def mvp_of(fight: SquadFight) -> Warrior | None:
    all_w = fight.all_warriors()
    if not all_w:
        return None
    for w in all_w:
        w.mvp_score = w.total_dmg + w.kills * 300 + w.finisher_count * 120 - w.total_taken * 0.15
    return max(all_w, key=lambda w: w.mvp_score)


def cleanup_fight(fight: SquadFight):
    for w in fight.all_warriors():
        player_in_fight.pop(w.uid, None)
    active_fights.pop(fight.fight_id, None)


async def apply_rewards(fight: SquadFight, get_player, save_player):
    """پاداش‌ها رو به بازیکن‌ها می‌ده و امتیازِ لیگِ تیمی رو آپدیت می‌کنه. یه dict گزارش برمی‌گردونه."""
    report = {}
    winner_team = fight.winner
    for w in fight.all_warriors():
        player = await aget_player(w.uid)
        if not player:
            continue
        sp = player.setdefault("squad_pvp", {})
        for k in ("wins", "losses", "points", "mvp_count"):
            sp.setdefault(k, 0)
        won = (winner_team == w.team)
        draw = winner_team == "draw"
        if draw:
            zen = (WIN_ZEN_BASE + LOSE_ZEN_BASE) // 2
            pts = 4
        elif won:
            zen = WIN_ZEN_BASE + int(w.total_dmg * 0.6)
            pts = WIN_POINTS
            sp["wins"] += 1
        else:
            zen = LOSE_ZEN_BASE + int(w.total_dmg * 0.25)
            pts = LOSE_POINTS
            sp["losses"] += 1
        sp["points"] = max(0, sp.get("points", 0) + pts)
        player["zen"] = player.get("zen", 0) + zen
        report[w.uid] = {"won": won, "draw": draw, "zen": zen, "points": pts, "dmg": w.total_dmg}
        await asave_player(w.uid, player)
    mvp = mvp_of(fight)
    if mvp:
        player = await aget_player(mvp.uid)
        if player:
            sp = player.setdefault("squad_pvp", {})
            for k in ("wins", "losses", "points", "mvp_count"):
                sp.setdefault(k, 0)
            sp["mvp_count"] = sp.get("mvp_count", 0) + 1
            player["zen"] = player.get("zen", 0) + 250
            await asave_player(mvp.uid, player)
            if mvp.uid in report:
                report[mvp.uid]["mvp"] = True
                report[mvp.uid]["zen"] += 250
    return report, mvp
