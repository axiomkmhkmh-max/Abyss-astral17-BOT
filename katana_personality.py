# ============================================================
#  ASTRAL ABYSS RPG — Katana Personality System
#  (katana_personality.py)  —  فاز ۱ / بخش الف
# ============================================================
#
# این فایل کاملاً جدید و مستقله؛ به هیچ فایل موجودی (katana_core.py,
# katana_system.py, katana_handlers.py, combat.py, ...) دست نمی‌زنه.
# فقط از KATANA_SOULS توی katana_core.py (اختیاری) می‌خونه تا تیپ
# شخصیتی رو با لور فعلیِ هر کاتانا هماهنگ کنه.
#
# چیزی که این فایل اضافه می‌کنه:
#   • تیپ شخصیتی (۱۲ نوع) — ثابت برای هر کاتانا، دیالوگ و بونوس مخفی داره
#   • وفاداری (Loyalty) ۰-۱۰۰ — با کشتن بالا میره، با مرگ پایین میاد
#   • خلق‌وخوی روزانه (Mood) — ۸ حالت، هر روز عوض می‌شه (تحت تاثیر وفاداری/کشته‌های دیروز)
#   • خاطرات (Memories) — هر ۱۰۰ کشته یه خاطره‌ی دائمی + خاطرات ویژه (باس/PvP/...)
#
# ── ساختار ذخیره‌سازی (per-character، چون یه بازیکن می‌تونه در طول زمان
#    کاراکتر/کاتانای متفاوتی داشته باشه) ──
#
#   player["katana_personality"] = {
#       "<character_name>": {
#           "type": "شجاع",                # ثابت، یک‌بار تعیین می‌شه
#           "loyalty": 42,                  # 0..100
#           "mood": "شاد",
#           "mood_date": "2026-07-07",      # تاریخ آخرین رول خلق‌وخو (UTC date)
#           "kills_today": 3,               # برای تاثیر رو رول فردا
#           "kills_yesterday": 5,
#           "memories": 3,                  # 0..50  (هر 100 کشته یکی)
#           "kill_count_for_memory": 320,   # شمارنده‌ی جدا برای خاطرات (کل کشته‌ها با این کاتانا)
#           "special_memories": ["boss_kill"],
#       },
#       ...
#   }
#
# نکته‌ی مهم: هیچ تابعی این‌جا مستقیماً save_player صدا نمی‌زنه.
# هندلر (فاز بعدی / katana_handlers.py توسعه‌یافته) مسئول ذخیره‌ی نهاییه.
# همه‌ی توابع idempotent‌ان: اگه دیکشنری وجود نداشته باشه می‌سازنش، وگرنه دست‌نخورده برش می‌گردونن.
# ============================================================

import random
import hashlib
from datetime import datetime, timezone

# ────────────────────────────────────────────────────────────
# ۱) ۱۲ تیپ شخصیتی
# ────────────────────────────────────────────────────────────

PERSONALITY_TYPES = {
    "شجاع":      {"emoji": "🦁", "desc": "بی‌باک و رودررو",        "bonus_desc": "+۳٪ دمیج وقتی HP بالای ۷۰٪"},
    "حیله‌گر":   {"emoji": "🦊", "desc": "زیرک و فرصت‌طلب",         "bonus_desc": "+۵٪ شانس کریت روی باس‌ها"},
    "خردمند":    {"emoji": "🦉", "desc": "آرام و دوراندیش",         "bonus_desc": "+۳٪ تجربه‌ی دریافتی"},
    "خشن":       {"emoji": "💢", "desc": "بی‌رحم و پرخاشگر",         "bonus_desc": "+۵٪ دمیج، −۳٪ دقت"},
    "مهربان":    {"emoji": "💗", "desc": "محافظ و دلسوز",           "bonus_desc": "+۳٪ لایف‌استیل"},
    "انتقام‌جو": {"emoji": "🩸", "desc": "تشنه‌ی جبران",             "bonus_desc": "+۱۰٪ دمیج بعد از خوردن ضربه"},
    "مرموز":     {"emoji": "🌫️", "desc": "غیرقابل پیش‌بینی",        "bonus_desc": "+۵٪ شانس فرار از حمله‌ی دشمن"},
    "شاد":       {"emoji": "😄", "desc": "سرزنده و خوش‌بین",         "bonus_desc": "+۵٪ شانس کریت"},
    "غمگین":     {"emoji": "😔", "desc": "سنگین و درون‌گرا",         "bonus_desc": "+۴٪ لایف‌استیل زیر ۳۰٪ HP"},
    "پرشور":     {"emoji": "🔥", "desc": "آتشین و بی‌قرار",          "bonus_desc": "+۵٪ شانس اثر ویژه‌ی تایر"},
    "سرد":       {"emoji": "🧊", "desc": "بی‌احساس و دقیق",          "bonus_desc": "+۳٪ دمیج ثابت (بدون نوسان)"},
    "دیوانه":    {"emoji": "🤪", "desc": "آشوب‌گر و غیرمنتظره",      "bonus_desc": "نوسان دمیج ±۱۵٪ (پرریسک)"},
}

PERSONALITY_LIST = list(PERSONALITY_TYPES.keys())

# کلیدواژه برای استخراج تیپ از متن روحِ کاتانا (katana_core.KATANA_SOULS[x]["personality"])
# اگه کاتانا روحِ نوشته‌شده نداشته باشه یا هیچ کلیدواژه‌ای مچ نشه، به fallback هش‌محور می‌ره.
_KEYWORD_MAP = [
    (("شجاع", "بی‌باک", "نترس"), "شجاع"),
    (("حیله", "زیرک", "فرصت"), "حیله‌گر"),
    (("خرد", "دوراندیش", "دانا", "عاقل"), "خردمند"),
    (("خشن", "وحشی", "بی‌رحم", "خشمگین"), "خشن"),
    (("مهربان", "دلسوز", "محافظ"), "مهربان"),
    (("انتقام",), "انتقام‌جو"),
    (("مرموز", "معما", "پرمعما", "پنهان", "راز"), "مرموز"),
    (("شاد", "سرزنده", "خوش"), "شاد"),
    (("غمگین", "غم", "دردناک", "سوگ"), "غمگین"),
    (("پرشور", "شعله‌ور", "آتشین", "پرحرارت"), "پرشور"),
    (("سرد", "بی‌احساس", "خونسرد", "بی‌عجله", "آروم"), "سرد"),
    (("دیوانه", "آشوب", "بی‌قانون"), "دیوانه"),
]


def _derive_personality_type(katana_name: str) -> str:
    """تیپ رو از متن روحِ کاتانای موجود در katana_core در میاره؛ اگه پیدا نشد،
    deterministic (هش اسم) یکی از ۱۲ تیپ رو انتخاب می‌کنه — همیشه یکسان برای یه اسمِ ثابت."""
    try:
        from katana_core import KATANA_SOULS
        soul = KATANA_SOULS.get(katana_name)
        if soul:
            text = soul.get("personality", "")
            for keys, ptype in _KEYWORD_MAP:
                if any(k in text for k in keys):
                    return ptype
    except ImportError:
        pass
    h = int(hashlib.md5(katana_name.encode("utf-8")).hexdigest(), 16)
    return PERSONALITY_LIST[h % len(PERSONALITY_LIST)]


# ────────────────────────────────────────────────────────────
# ۲) وفاداری (Loyalty) ۰..۱۰۰
# ────────────────────────────────────────────────────────────

LOYALTY_MAX = 100
LOYALTY_HIGH = 70   # بالاتر از این: بونوس پنهان
LOYALTY_LOW = 30    # پایین‌تر از این: شانس "لجبازی"

KILL_LOYALTY_GAIN = {"normal": (1, 2), "elite": (2, 4), "boss": (3, 5)}
DEATH_LOYALTY_BASE_LOSS = 5     # حداقل افت مرگ
DEATH_LOYALTY_PER_STAGE = 2     # هر مرحله‌ی بیداری، این‌قدر بیشتر افت می‌کنه
DEATH_LOYALTY_MAX_LOSS = 15

DISOBEY_CHANCE = 0.05           # زیر LOYALTY_LOW: شانس حمله‌ی ناقص


def _clamp_loyalty(v: int) -> int:
    return max(0, min(LOYALTY_MAX, v))


def register_kill(entry: dict, enemy_tier: str = "normal") -> int:
    """enemy_tier: 'normal' | 'elite' | 'boss'. برمی‌گردونه مقدار افزایش."""
    lo, hi = KILL_LOYALTY_GAIN.get(enemy_tier, KILL_LOYALTY_GAIN["normal"])
    gain = random.randint(lo, hi)
    entry["loyalty"] = _clamp_loyalty(entry.get("loyalty", 50) + gain)
    entry["kills_today"] = entry.get("kills_today", 0) + 1
    return gain


def register_death(entry: dict, awakening_stage: int = 0) -> int:
    """برمی‌گردونه مقدار افت وفاداری (منفی)."""
    loss = min(DEATH_LOYALTY_MAX_LOSS, DEATH_LOYALTY_BASE_LOSS + awakening_stage * DEATH_LOYALTY_PER_STAGE)
    entry["loyalty"] = _clamp_loyalty(entry.get("loyalty", 50) - loss)
    return -loss


def loyalty_state(entry: dict) -> str:
    lv = entry.get("loyalty", 50)
    if lv >= LOYALTY_HIGH:
        return "high"
    if lv < LOYALTY_LOW:
        return "low"
    return "normal"


# ────────────────────────────────────────────────────────────
# ۳) خلق‌وخوی روزانه (Mood) — ۸ حالت
# ────────────────────────────────────────────────────────────

MOOD_EFFECTS = {
    "شاد":     {"crit": 0.10, "desc": "😄 +۱۰٪ شانس کریت"},
    "عصبانی":  {"dmg_mult_flat": 0.15, "hit": -0.10, "desc": "😡 +۱۵٪ دمیج ولی −۱۰٪ دقت"},
    "غمگین":   {"all_mult": -0.05, "desc": "😢 −۵٪ همه‌چیز"},
    "آرام":    {"lifesteal": 0.05, "desc": "😌 +۵٪ لایف‌استیل"},
    "بی‌حال":  {"atk_speed": -0.10, "desc": "😴 −۱۰٪ سرعت حمله"},
    "پرشور":   {"special_chance_add": 0.20, "desc": "🔥 +۲۰٪ شانس اثر ویژه"},
    "مرموز":   {"surprise_chance": 0.05, "surprise_mult": 3.0, "desc": "🌫️ ۵٪ شانس ضربه‌ی غافلگیرکننده (×۳)"},
    "خونسرد":  {"desc": "🧊 همه‌چیز نرمال"},
}
MOOD_LIST = list(MOOD_EFFECTS.keys())


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def roll_daily_mood(entry: dict) -> str:
    """اگه تاریخ عوض شده باشه، خلق‌وخوی جدید رول می‌کنه (تحت تاثیر وفاداری و کشته‌های دیروز).
    اگه هنوز همون روزه، خلق‌وخوی فعلی رو دست‌نخورده برمی‌گردونه."""
    today = _today_str()
    if entry.get("mood_date") == today and entry.get("mood"):
        return entry["mood"]

    weights = {m: 1.0 for m in MOOD_LIST}
    lstate = loyalty_state(entry)
    if lstate == "high":
        for m in ("شاد", "پرشور", "آرام"):
            weights[m] += 1.5
        for m in ("غمگین", "بی‌حال"):
            weights[m] = max(0.2, weights[m] - 0.5)
    elif lstate == "low":
        for m in ("عصبانی", "غمگین", "بی‌حال"):
            weights[m] += 1.5
        for m in ("شاد", "پرشور"):
            weights[m] = max(0.2, weights[m] - 0.5)

    kills_yday = entry.get("kills_today", 0)  # قبل از رول جدید، این همون کشته‌های "دیروز"ه
    if kills_yday >= 15:
        for m in ("پرشور", "شاد"):
            weights[m] += 1.0
    elif kills_yday == 0:
        for m in ("بی‌حال", "غمگین"):
            weights[m] += 1.0

    moods, wts = zip(*weights.items())
    new_mood = random.choices(moods, weights=wts, k=1)[0]

    entry["kills_yesterday"] = kills_yday
    entry["kills_today"] = 0
    entry["mood"] = new_mood
    entry["mood_date"] = today
    return new_mood


# ────────────────────────────────────────────────────────────
# ۴) خاطرات (Memories)
# ────────────────────────────────────────────────────────────

MEMORY_KILLS_PER = 100
MEMORY_MAX = 50

# بونوس‌های چرخشی هر خاطره (کوچیک ولی دائمی و انباشتی)
_MEMORY_CYCLE = [
    {"dmg_mult_flat": 0.01, "label": "+۱٪ دمیج"},
    {"crit": 0.01, "label": "+۱٪ کریت"},
    {"lifesteal": 0.01, "label": "+۱٪ لایف‌استیل"},
]

SPECIAL_MEMORIES = {
    "boss_kill":         {"name": "🐲 نبرد با یک باس بزرگ",       "bonus": {"dmg_mult_flat": 0.02}},
    "pvp_win":           {"name": "⚔️ اولین برد PvP",              "bonus": {"crit": 0.02}},
    "near_death_survive": {"name": "💀 جان‌به‌دربردن از نابودی",    "bonus": {"lifesteal": 0.02}},
    "awakening_success":  {"name": "✨ بیداری موفق در آخرین لحظه",  "bonus": {"special_chance_add": 0.02}},
}


def register_kill_for_memory(entry: dict) -> dict | None:
    """کشته‌ی جدید رو برای پیشرفت خاطرات می‌شمره. اگه خاطره‌ی جدیدی باز شد، اطلاعاتش رو برمی‌گردونه، وگرنه None."""
    entry["kill_count_for_memory"] = entry.get("kill_count_for_memory", 0) + 1
    if entry.get("memories", 0) >= MEMORY_MAX:
        return None
    if entry["kill_count_for_memory"] % MEMORY_KILLS_PER == 0:
        entry["memories"] = entry.get("memories", 0) + 1
        idx = (entry["memories"] - 1) % len(_MEMORY_CYCLE)
        return {"count": entry["memories"], "bonus": _MEMORY_CYCLE[idx]}
    return None


def unlock_special_memory(entry: dict, key: str) -> bool:
    """برای فراخوانی از سیستم‌های دیگه (باس/PvP/...) — idempotent."""
    if key not in SPECIAL_MEMORIES:
        return False
    lst = entry.setdefault("special_memories", [])
    if key in lst:
        return False
    lst.append(key)
    return True


def _memory_total_bonus(entry: dict) -> dict:
    out = {"dmg_mult_flat": 0.0, "crit": 0.0, "lifesteal": 0.0, "special_chance_add": 0.0}
    n = entry.get("memories", 0)
    for i in range(n):
        b = _MEMORY_CYCLE[i % len(_MEMORY_CYCLE)]
        for k, v in b.items():
            if k in out:
                out[k] += v
    for key in entry.get("special_memories", []):
        b = SPECIAL_MEMORIES.get(key, {}).get("bonus", {})
        for k, v in b.items():
            if k in out:
                out[k] += v
    return out


# ────────────────────────────────────────────────────────────
# ۵) بونوس تیپ شخصیتی (وابسته به وضعیت زنده‌ی بازیکن)
# ────────────────────────────────────────────────────────────

def personality_type_bonus(ptype: str, player: dict, took_damage_last_turn: bool = False,
                            target_is_boss: bool = False) -> dict:
    """بونوس مخفیِ هر تیپ. خروجی با فرمت calc_katana_bonus سازگاره تا فاز۲ راحت جمعش کنه."""
    hp = player.get("hp", 100)
    max_hp = player.get("max_hp", 100) or 1
    hp_pct = hp / max_hp

    out = {"dmg_mult_flat": 0.0, "crit": 0.0, "hit": 0.0, "lifesteal": 0.0,
           "special_chance_add": 0.0, "dodge": 0.0, "dmg_variance": 0.0}

    if ptype == "شجاع" and hp_pct > 0.7:
        out["dmg_mult_flat"] += 0.03
    elif ptype == "حیله‌گر" and target_is_boss:
        out["crit"] += 0.05
    elif ptype == "خشن":
        out["dmg_mult_flat"] += 0.05
        out["hit"] -= 0.03
    elif ptype == "مهربان":
        out["lifesteal"] += 0.03
    elif ptype == "انتقام‌جو" and took_damage_last_turn:
        out["dmg_mult_flat"] += 0.10
    elif ptype == "مرموز":
        out["dodge"] += 0.05
    elif ptype == "شاد":
        out["crit"] += 0.05
    elif ptype == "غمگین" and hp_pct < 0.3:
        out["lifesteal"] += 0.04
    elif ptype == "پرشور":
        out["special_chance_add"] += 0.05
    elif ptype == "سرد":
        out["dmg_mult_flat"] += 0.03
    elif ptype == "دیوانه":
        out["dmg_variance"] = 0.15
    return out


# ────────────────────────────────────────────────────────────
# ۶) API اصلی — استفاده‌ی هندلرها/کامبت از این‌ها
# ────────────────────────────────────────────────────────────

def get_personality(player: dict, character_name: str) -> dict:
    """entry رو idempotent می‌سازه/برمی‌گردونه. توی حافظه mutate می‌کنه؛ save_player جداست."""
    store = player.setdefault("katana_personality", {})
    entry = store.get(character_name)
    if entry is None:
        entry = {
            "type": _derive_personality_type(character_name),
            "loyalty": 50,
            "mood": None,
            "mood_date": None,
            "kills_today": 0,
            "kills_yesterday": 0,
            "memories": 0,
            "kill_count_for_memory": 0,
            "special_memories": [],
        }
        store[character_name] = entry
    roll_daily_mood(entry)
    return entry


def calc_personality_total_bonus(player: dict, character_name: str,
                                  took_damage_last_turn: bool = False,
                                  target_is_boss: bool = False) -> dict:
    """جمع نهاییِ بونوس تیپ + خلق‌وخوی امروز + خاطرات + اثر وفاداری بالا/پایین.
    این دیکشنری تو فاز۲ با خروجی calc_katana_bonus (katana_core) ترکیب می‌شه."""
    entry = get_personality(player, character_name)
    ptype = entry["type"]
    mood = entry.get("mood") or "خونسرد"
    mood_fx = MOOD_EFFECTS.get(mood, {})

    out = {"dmg_mult_flat": 0.0, "crit": 0.0, "hit": 0.0, "lifesteal": 0.0,
           "special_chance_add": 0.0, "dodge": 0.0, "dmg_variance": 0.0,
           "atk_speed_mult": 0.0, "surprise_chance": 0.0, "surprise_mult": 0.0,
           "all_mult": 0.0, "disobey_chance": 0.0}

    for k, v in personality_type_bonus(ptype, player, took_damage_last_turn, target_is_boss).items():
        out[k] = out.get(k, 0.0) + v

    for k, v in mood_fx.items():
        if k == "desc":
            continue
        if k == "atk_speed":
            out["atk_speed_mult"] += v
        else:
            out[k] = out.get(k, 0.0) + v

    for k, v in _memory_total_bonus(entry).items():
        out[k] = out.get(k, 0.0) + v

    lstate = loyalty_state(entry)
    if lstate == "high":
        out["dmg_mult_flat"] += 0.05
        out["special_chance_add"] += 0.10
    elif lstate == "low":
        out["disobey_chance"] += DISOBEY_CHANCE

    return out


def display_personality(player: dict, character_name: str) -> str:
    entry = get_personality(player, character_name)
    ptype = entry["type"]
    tinfo = PERSONALITY_TYPES[ptype]
    mood = entry.get("mood") or "خونسرد"
    minfo = MOOD_EFFECTS.get(mood, {})
    lv = entry.get("loyalty", 50)

    bar_len = 10
    filled = int(lv / 100 * bar_len)
    bar = "🟩" * filled + "⬜" * (bar_len - filled)

    lines = []
    lines.append(f"{tinfo['emoji']} تیپ شخصیتی: **{ptype}** — {tinfo['desc']}")
    lines.append(f"   🎁 بونوس مخفی: {tinfo['bonus_desc']}")
    lines.append("")
    lines.append(f"🔗 وفاداری: {bar} {lv}/100")
    if lv >= LOYALTY_HIGH:
        lines.append("   ✅ وفاداری بالا: +۵٪ دمیج، +۱۰٪ شانس اثر ویژه")
    elif lv < LOYALTY_LOW:
        lines.append(f"   ⚠️ وفاداری پایین: {int(DISOBEY_CHANCE*100)}٪ شانس نافرمانی (حمله‌ی ناقص)")
    lines.append("")
    lines.append(f"{ '😶' if mood=='خونسرد' else ''} خلق‌وخوی امروز: **{mood}** — {minfo.get('desc','')}")
    lines.append("")
    n = entry.get("memories", 0)
    lines.append(f"🧠 خاطرات: {n}/{MEMORY_MAX}  ({entry.get('kill_count_for_memory',0)} کشته)")
    if entry.get("special_memories"):
        lines.append("   خاطرات ویژه:")
        for key in entry["special_memories"]:
            info = SPECIAL_MEMORIES.get(key)
            if info:
                lines.append(f"   • {info['name']}")

    return "\n".join(lines)
