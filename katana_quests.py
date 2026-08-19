# ============================================================
#  ASTRAL ABYSS RPG — Katana Quest System
#  (katana_quests.py)  —  فاز ۳ / بخش ب
# ============================================================
#
# هر کاتانا ۵ مأموریتِ اصلی (مرتبط با فصل‌های لور) + ۱۰ مأموریتِ فرعی
# (مرتبط با تیپ شخصیتی) داره. مأموریت‌ها با update_quest_progress() از
# هندلرهای مختلف (combat_v3, دیتانشن‌ها، مهارت‌ها، ...) آپدیت می‌شن؛
# وقتی به هدف برسن، خودکار «کامل» می‌شن و جایزه‌شون آماده‌ی برداشته‌شدنه.
#
# دو نوع پیشرفت داریم:
#   • mode="increment": هر بار event فایر بشه، +amount به progress اضافه می‌شه (مثل کشتن).
#   • mode="set":        progress = max(progress, amount) — برای چیزهایی که «سطح فعلی»ان
#                        نه «تعداد رویداد» (مثل سطح پیوند، تعداد آیتم تو انبار).
#
# ذخیره‌سازی (per-character):
#   player["katana_quests"] = {
#       "<character_name>": {
#           "main": {1: {"progress": 12, "done": False, "claimed": False}, ...},
#           "side": {1: {...}, ...},
#       }
#   }
# ============================================================

from katana_core import get_katana_identity

# ────────────────────────────────────────────────────────────
# ۱) مأموریت‌های اصلی (۵ تا، مرتبط با فصل‌های لور)
# ────────────────────────────────────────────────────────────

MAIN_QUESTS = {
    1: {"title": "اثبات وجود", "event": "kill", "mode": "increment", "target": 30,
        "desc_tmpl": "با {katana} ۳۰ دشمن بکش.",
        "reward": {"gold": 3000, "loyalty": 5}},
    2: {"title": "جوهرِ بیداری", "event": "awaken_material_collected", "mode": "set", "target": 5,
        "desc_tmpl": "۵ واحد از موادِ بیداریِ مرحله‌ی اول {katana} رو جمع کن.",
        "reward": {"gold": 2000, "loyalty": 5}},
    3: {"title": "شکارچیِ باس", "event": "kill_boss", "mode": "increment", "target": 1,
        "desc_tmpl": "یک باس رو با {katana} شکست بده.",
        "reward": {"gold": 8000, "loyalty": 10, "item": ("soul_shard", 3)}},
    4: {"title": "لبه‌ی مرگ", "event": "survive_low_hp", "mode": "increment", "target": 1,
        "desc_tmpl": "یک‌بار با HP زیر ۱۰٪ از نبرد زنده بیرون بیا.",
        "reward": {"gold": 5000, "loyalty": 8}},
    5: {"title": "پیوندِ کامل", "event": "bond_level", "mode": "set", "target": 8,
        "desc_tmpl": "پیوند روحی‌ات با {katana} رو به سطح ۸ برسون.",
        "reward": {"gold": 10000, "loyalty": 15, "title_unlock": "همراهِ روح"}},
}

# ────────────────────────────────────────────────────────────
# ۲) مأموریت‌های فرعی (۱۰ تا، عمومی ولی با توضیح مطابق تیپ شخصیتی)
# ────────────────────────────────────────────────────────────

SIDE_QUESTS = {
    1: {"title": "شکار عنصری",     "event": "kill_weak_hit",      "mode": "increment", "target": 20,
        "reward": {"gold": 800, "loyalty": 2}},
    2: {"title": "افتخارِ میدان",  "event": "pvp_win",             "mode": "increment", "target": 3,
        "reward": {"gold": 1500, "loyalty": 3}},
    3: {"title": "کاوشگر",         "event": "visit_new_map",       "mode": "increment", "target": 1,
        "reward": {"gold": 500, "loyalty": 2}},
    4: {"title": "استادِ مهارت",   "event": "skill_proc",          "mode": "increment", "target": 10,
        "reward": {"gold": 1200, "loyalty": 3}},
    5: {"title": "تحملِ درد",      "event": "counter_survived",    "mode": "increment", "target": 50,
        "reward": {"gold": 2000, "loyalty": 4}},
    6: {"title": "ضربه‌ی مرگبار",  "event": "crit_hit",            "mode": "increment", "target": 25,
        "reward": {"gold": 1000, "loyalty": 2}},
    7: {"title": "گفتگوی روزانه",  "event": "daily_talk",          "mode": "increment", "target": 7,
        "reward": {"gold": 700, "loyalty": 5}},
    8: {"title": "یادِ ماندگار",   "event": "memory_unlocked",     "mode": "increment", "target": 1,
        "reward": {"gold": 1000, "loyalty": 3}},
    9: {"title": "تکاملِ آرام",    "event": "dimension_upgrade",   "mode": "increment", "target": 3,
        "reward": {"gold": 1500, "loyalty": 2}},
    10: {"title": "شکستنِ مهر",    "event": "seal_break",          "mode": "increment", "target": 1,
         "reward": {"gold": 2500, "loyalty": 4}},
}

_PERSONALITY_QUEST_FLAVOR = {
    "شجاع": "چون کاتانات شجاعه، رودررو وارد می‌شی و",
    "حیله‌گر": "چون کاتانات حیله‌گره، از فرصت‌ها استفاده می‌کنی و",
    "خردمند": "چون کاتانات خردمنده، با صبر",
    "خشن": "چون کاتانات خشنه، بی‌رحمانه",
    "مهربان": "چون کاتانات مهربونه، محتاطانه",
    "انتقام‌جو": "چون کاتانات انتقام‌جوعه، با اصرار",
    "مرموز": "چون کاتانات مرموزه، در سکوت",
    "شاد": "چون کاتانات شاده، با شور",
    "غمگین": "چون کاتانات غمگینه، آروم ولی پیوسته",
    "پرشور": "چون کاتانات پرشوره، بی‌وقفه",
    "سرد": "چون کاتانات سرده، دقیق و بی‌نوسان",
    "دیوانه": "چون کاتانات دیوانه‌ست، غیرقابل‌پیش‌بینی",
}


def _side_quest_desc(quest_id: int, ptype: str) -> str:
    flavor = _PERSONALITY_QUEST_FLAVOR.get(ptype, "")
    base = {
        1: "۲۰ ضربه‌ی ضعفِ عنصری بزن.",
        2: "۳ برد PvP کسب کن.",
        3: "یک نقشه‌ی جدید کشف کن.",
        4: "۱۰ بار یه مهارت فعال رو در نبرد فعال کن.",
        5: "۵۰ بار ضدحمله‌ی دشمن رو تحمل کن و زنده بمون.",
        6: "۲۵ ضربه‌ی کریتیکال بزن.",
        7: "۷ روز پشت‌سرهم با کاتانات گفتگو کن.",
        8: "یه خاطره‌ی جدید باز کن.",
        9: "۳ بار یکی از ابعادِ کاتانا (سرعت/دقت/روح) رو ارتقا بده.",
        10: "یه مهارت رو با شکستنِ مهر ارتقا بده.",
    }[quest_id]
    return f"{flavor} {base}".strip()


# ────────────────────────────────────────────────────────────
# ۳) ساخت/دسترسیِ ساختار مأموریت‌ها
# ────────────────────────────────────────────────────────────

def get_quests(player: dict, character_name: str) -> dict:
    store = player.setdefault("katana_quests", {})
    entry = store.get(character_name)
    if entry is None:
        entry = {
            "main": {qid: {"progress": 0, "done": False, "claimed": False} for qid in MAIN_QUESTS},
            "side": {qid: {"progress": 0, "done": False, "claimed": False} for qid in SIDE_QUESTS},
        }
        store[character_name] = entry
    return entry


def update_quest_progress(player: dict, character_name: str, event_type: str, amount: int = 1) -> list[dict]:
    """صدا زده می‌شه از combat_v3 / katana_dimensions / katana_skills / pvp_handlers و غیره.
    برمی‌گردونه لیستِ مأموریت‌هایی که تازه کامل شدن (main+side)."""
    entry = get_quests(player, character_name)
    completed = []

    for kind, defs in (("main", MAIN_QUESTS), ("side", SIDE_QUESTS)):
        for qid, qdef in defs.items():
            if qdef["event"] != event_type:
                continue
            q = entry[kind][qid]
            if q["done"]:
                continue
            if qdef["mode"] == "increment":
                q["progress"] += amount
            else:  # "set"
                q["progress"] = max(q["progress"], amount)
            if q["progress"] >= qdef["target"]:
                q["progress"] = qdef["target"]
                q["done"] = True
                completed.append({"kind": kind, "id": qid, "title": qdef["title"], "reward": qdef["reward"]})
    return completed


def claim_reward(player: dict, character_name: str, kind: str, qid: int) -> dict:
    """جایزه رو یک‌بار برمی‌داره (idempotent). خودِ اعمال طلا/آیتم به عهده‌ی هندلره."""
    entry = get_quests(player, character_name)
    defs = MAIN_QUESTS if kind == "main" else SIDE_QUESTS
    q = entry[kind].get(qid)
    if not q or not q["done"]:
        return {"success": False, "message": "این مأموریت هنوز کامل نشده."}
    if q["claimed"]:
        return {"success": False, "message": "جایزه‌ی این مأموریت قبلاً برداشته شده."}
    q["claimed"] = True
    return {"success": True, "reward": defs[qid]["reward"]}


# ────────────────────────────────────────────────────────────
# ۴) نمایش
# ────────────────────────────────────────────────────────────

def display_quests(player: dict, character_name: str) -> str:
    from katana_personality import _derive_personality_type
    entry = get_quests(player, character_name)
    ident = get_katana_identity(character_name)
    ptype = _derive_personality_type(ident["katana_name"])

    lines = [f"📜 **مأموریت‌های {ident['katana_name']}** 📜", "", "🎯 **اصلی**"]
    for qid, qdef in MAIN_QUESTS.items():
        q = entry["main"][qid]
        state = "✅ کامل" + (" (جایزه گرفته‌شده)" if q["claimed"] else " — /katana_quest claim برای جایزه") if q["done"] else f"{q['progress']}/{qdef['target']}"
        desc = qdef["desc_tmpl"].format(katana=ident["katana_name"])
        lines.append(f"   {qid}. **{qdef['title']}** — {desc}\n      وضعیت: {state}")

    lines.append("")
    lines.append("🔹 **فرعی**")
    for qid, qdef in SIDE_QUESTS.items():
        q = entry["side"][qid]
        state = "✅ کامل" + (" (جایزه گرفته‌شده)" if q["claimed"] else " — جایزه در انتظاره") if q["done"] else f"{q['progress']}/{qdef['target']}"
        desc = _side_quest_desc(qid, ptype)
        lines.append(f"   {qid}. **{qdef['title']}** — {desc}\n      وضعیت: {state}")

    return "\n".join(lines)
