# ============================================================
#  ASTRAL ABYSS — Map Activity Feed 🔴 «زنده» (v2 — عمیق‌تر)
# ------------------------------------------------------------
#  مشکلی که حل می‌کنه: وقتی سرور بازیکنِ کمی داره، نقشه‌ها و
#  لوکیشن‌ها خالی/مرده به‌نظر می‌رسن و همین حسِ «هیچکی بازی
#  نمی‌کنه» ریزش می‌سازه.
#
#  v2 چه فرقی داره؟
#  • رویدادها الان در سطحِ لوکیشن هم قابلِ شمارشن، نه فقط مپ —
#    یعنی می‌شه فهمید کدوم لوکیشنِ خاص «داغ»ه.
#  • رویدادهای کمیاب (کیلِ لجندری، شکستِ باسِ منطقه) برجسته‌تر
#    نمایش داده می‌شن (فرمتِ متفاوت، نه فقط یه خطِ ساده).
#  • یه شاخصِ صادقانه‌ی «حضورِ همین‌الان» اضافه شد: اگه یه رویدادِ
#    واقعی تو ۵ دقیقه‌ی اخیر ثبت شده باشه، به‌جای خطِ فید، یه
#    نشانِ 🟢 مجزا نشون داده می‌شه (چون این واقعاً چیزیه که همین
#    الان اتفاق افتاده، نه فلش‌بک).
#  • یه شمارشگرِ صادقانه‌ی «بازدیدکنندگانِ متمایزِ ۲۴ ساعتِ اخیر»
#    هم اضافه شد — به‌جای وانمود به هم‌زمانی، واقعیتِ تجمعیِ
#    ترافیکِ مپ رو نشون می‌ده (که برای سرورِ کم‌جمعیت هم صادقانه
#    قانع‌کننده‌ست: «۱۱ نفر امروز اینجا بودن» بهتر از سکوته).
#  • خط‌های اتمسفریک الان بر اساسِ zone (safe/contested/danger)
#    فرق می‌کنن — منطقه‌ی امن با منطقه‌ی خطر یه حسِ متفاوت داره.
#  • پاک‌سازیِ خودکارِ رویدادهای قدیمی‌تر از ۲۴ ساعت، تا سندِ
#    دیتابیس بی‌نهایت بزرگ نشه.
# ============================================================
import time
import random

MAX_EVENTS_PER_MAP = 40           # سقفِ نگه‌داری خام (قبل از فیلترِ فرش/پروون)
PRUNE_MAX_AGE = 24 * 3600         # هر چیزِ قدیمی‌تر از این، در نوشتنِ بعدی پاک می‌شه
FRESH_WINDOW = 3 * 3600           # پنجره‌ی «فید» — رویدادهای این‌قدر تازه تو فید میان
LIVE_WINDOW = 5 * 60              # پنجره‌ی «همین الان اینجا کسی هست» (صادقانه، نه فلش‌بک)
HOT_LOCATION_WINDOW = 3600        # پنجره‌ی تشخیصِ «لوکیشنِ داغ»
HOT_LOCATION_THRESHOLD = 3        # از این تعداد رویداد به بالا تو یک ساعت = داغ

RARE_KINDS = {"boss_kill", "legendary_kill", "elite_kill"}

KIND_VERB = {
    "kill":            "یه دشمن رو تو {loc} شکار کرد",
    "explore":         "منطقه‌ی جدیدی رو تو {loc} کشف کرد",
    "loot":            "وارد {loc} شد و داشت می‌گشت",
    "boss":            "با باسِ منطقه‌ی {loc} درگیر شد",
    "boss_kill":       "باسِ منطقه‌ی {loc} رو شکست داد",
    "legendary_kill":  "یه دشمنِ لجندری رو تو {loc} از پا درآورد",
    "elite_kill":      "یه دشمنِ نخبه (👑) رو تو {loc} شکار کرد",
}

# خط‌های اتمسفریک — بر اساسِ zone (economy.MAPS_DATA[...]['zone']) فرق می‌کنن
AMBIENT_LINES_BY_ZONE = {
    "safe": [
        "🕯️ یه آتیشِ تازه‌خاموش‌شده — انگار کسی همین‌جا کمپ زده بود.",
        "👣 ردِ پایی تازه رو خاک — یکی همین امروز از اینجا رد شده.",
        "🍃 نسیمِ آرومی می‌وزه؛ این‌جا نسبتاً امن به‌نظر می‌رسه، ولی خبرا زیاده.",
        "🔔 صدای دورِ زنگوله‌های یه کاروان به گوش می‌رسه.",
    ],
    "contested": [
        "🌫️ صدای زوزه‌ای از دوردست میاد — انگار یه چیزی همین الان بیدار شد.",
        "⚔️ آثارِ یه درگیریِ اخیر رو زمین دیده می‌شه — کسی این‌جا جنگیده.",
        "🍃 بادِ سردی از شکاف‌های آبیس می‌وزه؛ حس می‌کنی یکی داره نگاهت می‌کنه.",
        "✨ یه ذره‌ی نورانی تو هوا معلقه، یه لحظه بعد ناپدید می‌شه.",
    ],
    "danger": [
        "🌑 سکوتِ عجیبی این‌جا حکم‌فرماست... انگار طوفان قبل از آرامشه.",
        "🩸 لکه‌های تازه‌ای رو زمین هست — یکی این‌جا به‌سختی جون سالم به در برده.",
        "👁️ حس می‌کنی چیزی از دور زیرِ نظرت داره — این‌جا هیچ‌وقت واقعاً خالی نیست.",
        "💀 بویِ سوختگی تو هوا پیچیده — یه نبردِ بزرگ این‌جا اتفاق افتاده.",
    ],
}
_DEFAULT_AMBIENT = AMBIENT_LINES_BY_ZONE["contested"]


def _zone_of(map_name: str) -> str:
    try:
        from economy import MAPS_DATA
        return MAPS_DATA.get(map_name, {}).get("zone", "contested")
    except Exception:
        return "contested"


def _doc() -> dict:
    from database import system_col
    doc = system_col().find_one({"_id": "map_activity"})
    if not doc:
        doc = {"_id": "map_activity", "feed": {}}
        system_col().update_one({"_id": "map_activity"}, {"$set": doc}, upsert=True)
    doc.setdefault("feed", {})
    return doc


def _save(doc: dict):
    from database import system_col
    system_col().update_one(
        {"_id": "map_activity"}, {"$set": {"feed": doc.get("feed", {})}}, upsert=True
    )


def _prune(events: list) -> list:
    now = time.time()
    events = [e for e in events if now - e.get("ts", 0) <= PRUNE_MAX_AGE]
    return events[-MAX_EVENTS_PER_MAP:]


def log_event(map_name: str, actor_name: str, kind: str, loc: str = "", actor_id: int | None = None):
    """
    بعدِ یه اکشنِ واقعیِ بازیکن (کیل/کشف/ورود به لوکیشن/چالشِ باس/کیلِ
    باس/کیلِ لجندری) صدا زده می‌شه. هیچ‌وقت نباید Exception پرت کنه —
    این فقط تزئینه، نباید جریانِ اصلیِ بازی رو خراب کنه.
    """
    try:
        doc = _doc()
        events = doc["feed"].setdefault(map_name, [])
        events.append({
            "ts": time.time(),
            "actor": (actor_name or "یه سالک").strip()[:32],
            "actor_id": actor_id,
            "kind": kind,
            "loc": loc,
        })
        doc["feed"][map_name] = _prune(events)
        _save(doc)
    except Exception:
        pass


def _fmt_line(e: dict, now: float) -> str:
    mins = int((now - e["ts"]) / 60)
    when = "همین الان" if mins < 1 else f"{mins} دقیقه پیش"
    kind = e.get("kind")
    verb = KIND_VERB.get(kind, "این‌جا بود")
    loc_txt = e.get("loc") or ""
    line = f"{e['actor']} {when} " + verb.format(loc=loc_txt)
    if kind in RARE_KINDS:
        return f"💥 **{line}**"
    return f"🔸 {line}"


def live_presence_badge(map_name: str) -> str | None:
    """
    اگه یه رویدادِ واقعی تو ۵ دقیقه‌ی اخیر تو این مپ ثبت شده، یه نشانِ
    صادقانه‌ی «همین الان کسی این دوروبره» برمی‌گردونه. این ادعا هیچ‌وقت
    دروغ نیست چون فقط رویدادهای واقعی حساب می‌شن.
    """
    try:
        doc = _doc()
        events = doc["feed"].get(map_name, [])
    except Exception:
        return None
    now = time.time()
    live = [e for e in events if now - e.get("ts", 0) <= LIVE_WINDOW]
    if not live:
        return None
    n = len({e.get("actor_id") or e.get("actor") for e in live})
    if n == 1:
        return "🟢 همین الان یکی همین دوروبَره..."
    return f"🟢 همین الان {n} نفر این دوروبَرن..."


def daily_visitor_count(map_name: str) -> int:
    """تعدادِ صادقانه‌ی بازدیدکنندگانِ متمایزِ ۲۴ ساعتِ اخیر (تجمعی، نه هم‌زمان)."""
    try:
        doc = _doc()
        events = doc["feed"].get(map_name, [])
    except Exception:
        return 0
    now = time.time()
    recent = [e for e in events if now - e.get("ts", 0) <= 24 * 3600]
    return len({e.get("actor_id") or e.get("actor") for e in recent})


def hot_locations(map_name: str) -> set:
    """اسمِ لوکیشن‌هایی که تو یک ساعتِ اخیر رویدادِ زیاد داشتن (برای بج 🔥)."""
    try:
        doc = _doc()
        events = doc["feed"].get(map_name, [])
    except Exception:
        return set()
    now = time.time()
    counts: dict[str, int] = {}
    for e in events:
        if now - e.get("ts", 0) > HOT_LOCATION_WINDOW:
            continue
        loc = e.get("loc")
        if not loc:
            continue
        counts[loc] = counts.get(loc, 0) + 1
    return {loc for loc, c in counts.items() if c >= HOT_LOCATION_THRESHOLD}


def recent_feed_text(map_name: str, limit: int = 2) -> str:
    """
    ۱ تا `limit` خط برای نشون‌دادنِ بالای نقشه/لوکیشن — ترکیبِ رویدادِ
    واقعیِ تازه (اگه باشه، رویدادهای کمیاب برجسته‌تر) + پرکردنِ
    اتمسفریکِ متناسب با zone (اگه رویدادِ تازه کم بود). به‌علاوه‌ی
    شاخصِ حضورِ زنده و شمارشگرِ بازدیدِ روزانه در انتها.
    هیچ‌وقت Exception پرت نمی‌کنه.
    """
    try:
        doc = _doc()
        events = list(doc["feed"].get(map_name, []))
    except Exception:
        events = []

    now = time.time()
    fresh = [e for e in events if now - e.get("ts", 0) <= FRESH_WINDOW]
    # رویدادهای کمیاب رو اول نشون بده، بعد جدیدترین‌ها
    fresh.sort(key=lambda e: (e.get("kind") in RARE_KINDS, e["ts"]), reverse=True)

    lines = [_fmt_line(e, now) for e in fresh[:limit]]

    if len(lines) < limit:
        need = limit - len(lines)
        pool = AMBIENT_LINES_BY_ZONE.get(_zone_of(map_name), _DEFAULT_AMBIENT)
        picks = random.sample(pool, min(need, len(pool)))
        lines.extend(picks)

    badge = live_presence_badge(map_name)
    if badge:
        lines.insert(0, badge)

    visitors = daily_visitor_count(map_name)
    if visitors >= 2:
        lines.append(f"👥 {visitors} نفر امروز این‌جا بودن.")

    return "\n".join(lines)
