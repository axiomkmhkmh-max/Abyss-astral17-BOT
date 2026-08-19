# ============================================================
#  ASTRAL ABYSS — Combat Stance System (مکانیک کاملاً جدید)
# ------------------------------------------------------------
#  بازیکن بین ۳ استنسِ جنگی سوییچ می‌کنه؛ استنس روی خودِ پروفایل
#  ذخیره می‌شه (player["stance"]) پس با ری‌استارت سرور از بین نمی‌ره.
#  سوییچ استنس یه کول‌داونِ کوچیک داره تا کسی هر ضربه استنس عوض نکنه.
# ============================================================
import time

STANCES = {
    "aggressive": {
        "name": "⚔️ تهاجمی",
        "desc": "دمیج +۲۵٪ / آسیب دریافتی +۲۰٪",
        "dmg_mult": 1.25, "incoming_mult": 1.20, "rage_mult": 1.0, "crit_bonus": 0.0,
    },
    "balanced": {
        "name": "⚖️ متعادل",
        "desc": "بدون تغییر دمیج / گیج Rage سریع‌تر پر می‌شه",
        "dmg_mult": 1.0, "incoming_mult": 1.0, "rage_mult": 1.3, "crit_bonus": 0.0,
    },
    "defensive": {
        "name": "🛡️ دفاعی",
        "desc": "دمیج -۱۵٪ / آسیب دریافتی -۳۰٪ / شانس کریت اضافه",
        "dmg_mult": 0.85, "incoming_mult": 0.70, "rage_mult": 0.8, "crit_bonus": 0.06,
    },
}
STANCE_ORDER = ["aggressive", "balanced", "defensive"]
STANCE_SWITCH_COOLDOWN = 15  # ثانیه


def get_stance(player: dict) -> str:
    s = player.get("stance", "balanced")
    return s if s in STANCES else "balanced"


def stance_switch_cooldown(player: dict) -> int:
    remaining = int(player.get("stance_changed_at", 0) + STANCE_SWITCH_COOLDOWN - time.time())
    return max(0, remaining)


def set_stance(player: dict, key: str) -> bool:
    """True اگه عوض شد. اگه کول‌داون در جریانه یا استنس نامعتبره، False."""
    if key not in STANCES:
        return False
    if get_stance(player) == key:
        return True
    if stance_switch_cooldown(player) > 0:
        return False
    player["stance"] = key
    player["stance_changed_at"] = time.time()
    return True


def apply_stance_outgoing(dmg: int, player: dict) -> int:
    if dmg <= 0:
        return dmg
    return max(1, int(dmg * STANCES[get_stance(player)]["dmg_mult"]))


def apply_stance_incoming(dmg: int, player: dict) -> int:
    if dmg <= 0:
        return dmg
    return max(0, int(dmg * STANCES[get_stance(player)]["incoming_mult"]))


def stance_rage_delta(player: dict, base_rage: float) -> float:
    """اختلافِ rage نسبت به حالتِ بدونِ استنس (برای اعمال به‌صورت post-hoc)."""
    mult = STANCES[get_stance(player)]["rage_mult"]
    return base_rage * (mult - 1.0)


def stance_crit_bonus(player: dict) -> float:
    return STANCES[get_stance(player)]["crit_bonus"]


def stance_row_text(player: dict) -> str:
    cur = get_stance(player)
    return f"{STANCES[cur]['name']} — {STANCES[cur]['desc']}"
