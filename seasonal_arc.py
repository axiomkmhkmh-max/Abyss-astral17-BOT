# ============================================================
#  ASTRAL ABYSS RPG — آرکِ فصلی 📜
# ------------------------------------------------------------
#  همون فصل‌بندیِ battle_pass رو (هر ۳۰ روز) قرض می‌گیره و یه
#  «داستانِ فصل» روش سوار می‌کنه: World Pulse (ضربان‌های آبیس) +
#  لورِ کاتانا/کاراکترها همه بخشی از یه روایتِ بزرگ‌ترن.
#
#  هر فصل یه هدفِ سراسری داره (مثلاً مجموع کشته‌های نمسیسِ کل
#  سرور). با رسیدن به هدف، یه بافِ همگانی برای بقیه‌ی همون فصل
#  برای همه‌ی بازیکن‌ها فعال می‌شه — یه دستاوردِ جمعی، نه فردی.
# ============================================================
import time

SEASON_GOAL_NEMESIS_KILLS = 500     # هدفِ سراسریِ فصل: مجموع کشته‌های نمسیسِ کل سرور
SEASON_BUFF_XP_MULT  = 1.20         # بافِ همگانی که با رسیدنِ به هدف باز می‌شه
SEASON_BUFF_ZEN_MULT = 1.10

# ─── فصل‌های داستانی — هر فصل یه فصلِ روایتِ آبیس رو باز می‌کنه ───
# 🌸 آرکِ ایزکای: این فصل‌ها حالا مستقیم به مائو (魔王 / لردِ شیطانی —
# منبعِ فسادِ world_pulse) وصلن. هرچی نمسیس بیشتری کشته بشه، یعنی
# سایه‌ی مائو کمرنگ‌تر می‌شه — فصل‌ها رو یه سفرِ داستانیِ واحد به‌سمتِ
# رودررویی با خودِ مائو می‌کنه، دقیقاً مثلِ آرکِ کلاسیکِ ایزکای.
SEASON_CHAPTERS = [
    {
        "title": "📜 فصل: طنینِ اول",
        "story": (
            "بعد از سکوتی طولانی، آبیس دوباره نفس کشید. اولین ضربان‌ها ضعیف بودن، "
            "ولی هرکسی که تو حلقه‌ی سایه یا زیرِ مه‌ی نقشه‌ها گوش می‌داد، صداشو شنید: "
            "چیزی داره بیدار می‌شه. کاتاناها تو دستِ صاحب‌هاشون گرم‌تر شدن. تو میکیو "
            "(迷宮の街)، گیلدِ ماجراجویی یه هشدارِ رسمی صادر کرد — یه نامی که سال‌ها "
            "کسی جرأتِ به‌زبان‌آوردنش رو نداشت، دوباره شنیده می‌شه: **مائو**."
        ),
    },
    {
        "title": "📜 فصل: زخم‌هایی که برنمی‌گردن",
        "story": (
            "نمسیس‌ها این فصل رو با کینه‌ای عمیق‌تر شروع می‌کنن — انگار مائو خودش "
            "داره بهشون یادآوری می‌کنه کی باعثِ شکستشون شده. هرکس یکی از این دشمن‌های "
            "قدیمی رو نهایی کنه، یه رشته از فسادی که مائو به این دنیا تزریق کرده رو "
            "پاره می‌کنه."
        ),
    },
    {
        "title": "📜 فصل: بازارِ سایه‌ها",
        "story": (
            "شایعه‌ست که خودِ داورِ حلقه‌ی سایه یه چیزی از مائو قرض گرفته — یه قدرتی "
            "که باعث می‌شه امشب‌هاش سخاوتمندتر از همیشه باشه. کسی نمی‌دونه قیمتش چیه، "
            "ولی همه دارن ریسک می‌کنن."
        ),
    },
    {
        "title": "📜 فصل: خطوطِ به‌هم‌ریخته",
        "story": (
            "خطِ داستانیِ همه‌ی جنگجوها این فصل یه‌جور بهم گره خورده — انگار مائو داره "
            "همه‌ی این دنیای شکسته رو مثلِ یه صفحه‌شطرنج می‌بینه. شکارِ نمسیس‌ها، مبارزات "
            "تو حلقه، حتی ساختنِ خونه — همه بخشی از یه معادله‌ی بزرگ‌ترن که مائو داره "
            "روش کار می‌کنه."
        ),
    },
    {
        "title": "📜 فصل: ندای عمیق",
        "story": (
            "یه صدای پایین، تقریباً نامحسوس، از اعماقِ آبیس میاد — صدای مائو، بیدارتر "
            "از همیشه. کسایی که حساسیتِ بیشتری دارن (رزوننسِ بالا یا پایین) می‌گن انگار "
            "داره یه چیزی رو می‌شمره. شاید کشته‌ها رو. شاید روزهای مونده تا خودش وارد "
            "میدون بشه."
        ),
    },
    {
        "title": "📜 فصل: پیش از توفان",
        "story": (
            "هر فصل، بمب‌های آبیس کمی خطرناک‌ترن. این فصل، حسِ عمومی اینه که مائو داره "
            "برای یه چیزِ بزرگ‌تر آماده می‌شه — نه فقط یه انفجارِ لحظه‌ای، بلکه یه "
            "تغییرِ دائمی تو نحوه‌ی نفس‌کشیدنِ خودِ دنیا. گیلدِ ماجراجویی از میکیو یه "
            "پیام برای همه‌ی رتبه‌های A و S فرستاده: **آماده باشید.**"
        ),
    },
    {
        "title": "📜 فصل: سایه‌ی مائو",
        "story": (
            "هرکی سطحِ رزوننسش بالاست می‌گه یه سایه رو بالای هرچهارده قلمرو دیده — فقط "
            "یه لحظه، فقط یه چشم‌به‌هم‌زدن. مائو دیگه پنهون نمی‌شه. هرچی این فصل نمسیسِ "
            "بیشتری بیفته، فرصتِ کمتری برای جمع‌کردنِ قدرت داره. این شاید آخرین فصل "
            "قبل از رودرروییِ نهایی باشه."
        ),
    },
]


def current_season() -> int:
    from battle_pass import current_season as _bp_season
    return _bp_season()


def _fresh_doc(season: int) -> dict:
    return {
        "_id": "seasonal_arc", "season": season,
        "nemesis_kills": 0, "goal_reached": False, "goal_reached_at": 0,
    }


def _doc() -> dict:
    from database import system_col
    season = current_season()
    doc = system_col().find_one({"_id": "seasonal_arc"})
    if not doc or doc.get("season") != season:
        doc = _fresh_doc(season)
        system_col().update_one({"_id": "seasonal_arc"}, {"$set": doc}, upsert=True)
    doc.setdefault("nemesis_kills", 0)
    doc.setdefault("goal_reached", False)
    doc.setdefault("goal_reached_at", 0)
    return doc


def _save(doc: dict):
    from database import system_col
    data = {k: v for k, v in doc.items() if k != "_id"}
    system_col().update_one({"_id": "seasonal_arc"}, {"$set": data}, upsert=True)


def chapter_for_season(season: int) -> dict:
    return SEASON_CHAPTERS[(season - 1) % len(SEASON_CHAPTERS)]


def register_nemesis_kill() -> bool:
    """هر بار یه نمسیس (تو هر جای دنیا، توسطِ هر بازیکنی) شکست می‌خوره صدا زده
    می‌شه. اگه همین کشته باعثِ رسیدن به هدفِ فصل بشه True برمی‌گردونه (برای
    اعلانِ یک‌بارِ سراسری)، وگرنه False."""
    doc = _doc()
    doc["nemesis_kills"] = doc.get("nemesis_kills", 0) + 1
    just_reached = False
    if not doc.get("goal_reached") and doc["nemesis_kills"] >= SEASON_GOAL_NEMESIS_KILLS:
        doc["goal_reached"] = True
        doc["goal_reached_at"] = time.time()
        just_reached = True
    _save(doc)
    return just_reached


def progress() -> dict:
    doc = _doc()
    return {
        "season": doc["season"],
        "kills": doc.get("nemesis_kills", 0),
        "goal": SEASON_GOAL_NEMESIS_KILLS,
        "goal_reached": doc.get("goal_reached", False),
        "chapter": chapter_for_season(doc["season"]),
    }


def buff_active() -> bool:
    return _doc().get("goal_reached", False)


def xp_mult() -> float:
    return SEASON_BUFF_XP_MULT if buff_active() else 1.0


def zen_mult() -> float:
    return SEASON_BUFF_ZEN_MULT if buff_active() else 1.0


def progress_bar(length: int = 10) -> str:
    p = progress()
    ratio = min(1.0, p["kills"] / p["goal"]) if p["goal"] else 0
    filled = int(length * ratio)
    return "🟥" * filled + "⬜" * (length - filled)


def status_text() -> str:
    p = progress()
    chapter = p["chapter"]
    lines = [
        f"{chapter['title']} (فصل {p['season']})\n",
        f"_{chapter['story']}_\n",
        f"🎯 **هدفِ سراسری:** شکارِ {p['goal']:,} نمسیس تو کل سرور",
        f"{progress_bar()} {p['kills']:,}/{p['goal']:,}",
    ]
    if p["goal_reached"]:
        lines.append(
            f"\n✅ **هدف رسید!** تا آخرِ فصل، بافِ همگانی فعاله: "
            f"+{int((SEASON_BUFF_XP_MULT-1)*100)}٪ XP | +{int((SEASON_BUFF_ZEN_MULT-1)*100)}٪ Zen"
        )
    else:
        lines.append(f"\nبا رسیدنِ به هدف: +{int((SEASON_BUFF_XP_MULT-1)*100)}٪ XP و +{int((SEASON_BUFF_ZEN_MULT-1)*100)}٪ Zen برای همه، تا آخرِ فصل.")
    return "\n".join(lines)
