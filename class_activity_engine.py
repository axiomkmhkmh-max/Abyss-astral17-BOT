# ============================================================
#  ASTRAL ABYSS RPG — Class Daily-Activity Engine
#  (class_activity_engine.py)
# ------------------------------------------------------------
#  هدف: هرچی «لوت» (loot_handlers.py) برای ماجراجو هست، این ماژول
#  زیرساختِ مشترکش رو برای بقیه‌ی کلاس‌ها (تاجر/درمانگر/جادوگر) فراهم
#  می‌کنه — یه چرخه‌ی اکشنِ روزانه (batch + سقفِ روزانه، دقیقاً همون
#  الگوی loot_state) + یه تابعِ واحد برای گرنت‌کردنِ Zen/XP طبقِ رِنجِ
#  تیرِ خودِ همون اکتیویتی (بدونِ ضریبِ اقتصادِ خامِ نبرد — چون رِنج‌ها
#  از قبل تنظیم‌شدن) + همون سقفِ ضدـ‌فارمِ روزانه (anti_farm.py) — یعنی این
#  سه تا سیستمِ جدید نمی‌تونن اقتصاد رو نسبت به ماجراجو نامتوازن کنن.
#
#  هر کلاس (merchant/healer/wizard) با یه "activity_key" جدا از این
#  ماژول استفاده می‌کنه (state per uid per key)، پس اکشن‌های تاجر و
#  درمانگر و جادوگر مستقل از همن.
# ============================================================
from __future__ import annotations

import time
import random

import anti_farm as af


# ─── تنظیماتِ پیش‌فرضِ چرخه‌ی اکشن (قابلِ override به‌ازای هر کلاس) ───
DEFAULT_MAX_ACTIONS   = 5
DEFAULT_BATCH_RESET   = 600     # ۱۰ دقیقه برای هر بچ (هم‌سنگِ لوت)
DEFAULT_DAILY_MAX     = 40      # سقفِ روزانه‌ی اکشن (کمتر از ۶۸ی ماجراجو چون این‌ها سیستمِ دومی‌ان)
DEFAULT_DAILY_RESET   = 86400

# state[key][uid] = {"actions", "reset_at", "daily_used", "daily_reset_at", ...extra}
_state: dict[str, dict[int, dict]] = {}


def get_state(key: str, uid: int, *, max_actions: int = DEFAULT_MAX_ACTIONS,
              batch_reset: int = DEFAULT_BATCH_RESET, daily_reset: int = DEFAULT_DAILY_RESET,
              extra_defaults: dict | None = None) -> dict:
    bucket = _state.setdefault(key, {})
    now = time.time()
    s = bucket.get(uid)
    if not s:
        s = {
            "actions": max_actions,
            "reset_at": now + batch_reset,
            "daily_used": 0,
            "daily_reset_at": now + daily_reset,
        }
        if extra_defaults:
            s.update(extra_defaults)
        bucket[uid] = s
        return s

    if now >= s.get("daily_reset_at", 0):
        s["daily_used"] = 0
        s["daily_reset_at"] = now + daily_reset

    if now >= s.get("reset_at", 0):
        s["actions"] = max_actions
        s["reset_at"] = now + batch_reset

    return s


def use_action(key: str, uid: int, *, max_actions: int = DEFAULT_MAX_ACTIONS,
               batch_reset: int = DEFAULT_BATCH_RESET, daily_max: int = DEFAULT_DAILY_MAX,
               daily_reset: int = DEFAULT_DAILY_RESET) -> tuple[bool, dict]:
    """یه اکشن مصرف می‌کنه. اگه اکشن/سقفِ روزانه تموم باشه False برمی‌گردونه."""
    s = get_state(key, uid, max_actions=max_actions, batch_reset=batch_reset, daily_reset=daily_reset)
    if s["actions"] <= 0:
        return False, s
    if s.get("daily_used", 0) >= daily_max:
        return False, s
    s["actions"] -= 1
    s["daily_used"] += 1
    return True, s


def action_bar(n: int, max_actions: int = DEFAULT_MAX_ACTIONS) -> str:
    n = max(0, min(n, max_actions))
    return "🟩" * n + "⬛" * (max_actions - n)


def status_line(s: dict, *, max_actions: int = DEFAULT_MAX_ACTIONS, daily_max: int = DEFAULT_DAILY_MAX) -> str:
    now = time.time()
    reset_in = max(0, int(s.get("reset_at", now) - now))
    daily_used = s.get("daily_used", 0)
    return (
        f"⚡ اقدامات: {action_bar(s['actions'], max_actions)} ({s['actions']}/{max_actions})\n"
        f"⏳ ریست بچ: {reset_in//60}:{reset_in%60:02d}\n"
        f"📊 روزانه: {daily_used}/{daily_max} ({max(0, daily_max - daily_used)} مانده)"
    )


# ─── گرنتِ Zen/XP — رِنج‌های تیر (merchant_deals/wizard_atelier/healer_duty)
# خودشون از قبل تنظیم‌شدن و پاداشِ نهایی‌ان؛ برخلافِ لوتِ خامِ نبرد
# (mob_combat.py و...) که ضریبِ سراسریِ اقتصاد (XP_GAIN_MULTIPLIER/
# ZEN_GAIN_MULTIPLIER) روش اعمال می‌شه. این تابع فقط همین سه ماژول رو
# صدا می‌زنن (نبرد اصلاً ازش استفاده نمی‌کنه)، پس اون ضرایب اینجا نباید
# دوباره اعمال بشن — وگرنه رِنجی که تو پیش‌نمایش نشون داده می‌شه
# (مثلاً «30–55 XP») با چیزی که واقعاً می‌گیری فرق می‌کنه (باگ‌فیکس).
def grant_rewards(player: dict, uid: int, *, base_zen: int, base_xp: int, source: str,
                   zen_mult: float = 1.0, xp_mult: float = 1.0) -> dict:
    """پاداشِ Zen/XP رو دقیقاً طبقِ رِنجِ تیرِ همون اکتیویتی (بدونِ ضریبِ
    اقتصادِ سراسری) به‌علاوه‌ی سقفِ نرمِ ضدـ‌فارمِ روزانه اعمال می‌کنه، بعد لولِ
    کاراکتر رو چک می‌کنه (level_up_check از bot.py — لِیزی import که جلوگیریِ
    از ایمپورتِ حلقوی می‌کنه، دقیقاً همون الگوی guild_handlers.py/item_system.py)."""
    zen_gain = int(base_zen * zen_mult)
    xp_gain  = int(base_xp * xp_mult)

    zen_gain = int(zen_gain * af.daily_mult(player, "zen"))
    xp_gain  = int(xp_gain * af.daily_mult(player, "xp"))

    af.register_daily_gain(player, "zen", zen_gain)
    af.register_daily_gain(player, "xp", xp_gain)
    af.log_if_suspicious(uid, player.get("name", "—"), zen_gain, xp_gain, source)

    player["zen"] = player.get("zen", 0) + zen_gain
    player["xp"]  = player.get("xp", 0) + xp_gain

    try:
        from bot import level_up_check
        player, leveled = level_up_check(player)
    except Exception:
        leveled = False

    return {
        "zen": zen_gain, "xp": xp_gain,
        "leveled": leveled, "new_level": player.get("level", 1),
    }


# ─── کمکی: انتخابِ رندومِ یه بازیکنِ واقعیِ دیگه (برای فلیورِ ملموس‌تر
# و گاهی تعاملِ واقعیِ بین‌بازیکنی) — همیشه try/except، هیچ‌وقت نباید
# اکشنِ اصلی رو خراب کنه اگه دیتابیس کند/خالی بود ───────────────────
def pick_random_other_player(exclude_uid: int, *, class_filter: str | None = None,
                              require_field: str | None = None, sample: int = 25) -> dict | None:
    try:
        from database import all_players
        pool = all_players()
    except Exception:
        return None
    candidates = []
    for k, doc in pool.items():
        try:
            uid = int(k)
        except (TypeError, ValueError):
            continue
        if uid == exclude_uid:
            continue
        if not doc.get("name") or not doc.get("class"):
            continue
        if class_filter and doc.get("class") != class_filter:
            continue
        if require_field and not doc.get(require_field):
            continue
        candidates.append((uid, doc))
    if not candidates:
        return None
    random.shuffle(candidates)
    uid, doc = candidates[0]
    doc["_uid"] = uid
    return doc
