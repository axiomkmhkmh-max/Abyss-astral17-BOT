# ============================================================
#  ASTRAL ABYSS — Evolution Path 🧬 (تکامل)
# ------------------------------------------------------------
#  به‌جای لولِ ساده، تو ۳ نقطه‌ی مشخص (Lv.10 / Lv.25 / Lv.45) بازیکن
#  یه «تکامل» می‌گیره: بینِ دو مسیرِ منشعب یکی رو انتخاب می‌کنه (مثلِ
#  مونستر ایسکاها — اسلایم → اسلایمِ جنگی یا اسلایمِ جادویی). انتخاب
#  دائمیه و یه بونوسِ استتِ دائمی + یه عنوانِ فلیوردار می‌ده.
#
#  دیتای این ماژول: player["evolution_stage"] (int, پیش‌فرض ۰) و
#  player["evolution_path"] (لیستِ branch_idهای انتخاب‌شده به ترتیب).
#  خالص/بدون aiogram — هندلرها تو evolution_handlers.py.
# ============================================================

EVOLUTION_TREE = {
    "wizard": {
        1: {
            "level_req": 10, "title": "🌱 شکوفاییِ عنصر",
            "flavor": "مانایی که تو رگ‌هات جریان داره داره شکل می‌گیره. یه مسیر رو انتخاب کن.",
            "branches": {
                "wiz1_fire": {"name": "🔥 آرکینِ سوزان", "flavor": "شعله‌ای که تو دستاته دیگه فقط گرم نیست — می‌سوزونه.",
                              "stat_bonus": {"atk": 9, "max_hp": 15}, "power": 140},
                "wiz1_frost": {"name": "❄️ آرکینِ منجمد", "flavor": "سرمایی که ازت ساطع می‌شه، دشمن رو کند می‌کنه.",
                               "stat_bonus": {"def": 9, "max_hp": 25}, "power": 140},
            },
        },
        2: {
            "level_req": 25, "title": "⚡ بیداریِ آرکین",
            "flavor": "قدرتِ درونت داره از کنترلِ ساده فراتر می‌ره.",
            "branches": {
                "wiz2_storm": {"name": "🌩 جادوگرِ توفان", "flavor": "رعد و برق دیگه بهت گوش می‌ده.",
                               "stat_bonus": {"atk": 20, "max_hp": 40}, "power": 330},
                "wiz2_abyss": {"name": "🌀 جادوگرِ ژرفا", "flavor": "خلأِ بینِ دنیاها رو لمس کردی.",
                               "stat_bonus": {"def": 20, "max_hp": 60}, "power": 330},
            },
        },
        3: {
            "level_req": 45, "title": "☄️ تعالیِ کیمیا",
            "flavor": "دیگه جادو نمی‌کنی — خودت جادو شدی.",
            "branches": {
                "wiz3_undying": {"name": "👑 آرک‌میجِ فناناپذیر", "flavor": "مرگ برات دیگه یه پایانِ قطعی نیست.",
                                 "stat_bonus": {"def": 35, "atk": 15, "max_hp": 120}, "power": 700},
                "wiz3_ruin": {"name": "💥 آرک‌میجِ ویرانگر", "flavor": "هر جایی که قدم می‌ذاری، اثری از خودش به‌جا می‌مونه.",
                              "stat_bonus": {"atk": 40, "def": 10, "max_hp": 90}, "power": 700},
            },
        },
    },
    "adventurer": {
        1: {
            "level_req": 10, "title": "🌱 طلوعِ ماجراجو",
            "flavor": "جاده‌ها دیگه برات ناشناخته نیستن.",
            "branches": {
                "adv1_shadow": {"name": "🗡 شکارچیِ سایه", "flavor": "کاتانات رو سریع‌تر و بی‌صداتر می‌کشی.",
                                "stat_bonus": {"atk": 10, "max_hp": 15}, "power": 140},
                "adv1_relic": {"name": "🗝 کاوشگرِ رلیک", "flavor": "چشمت برای گنج و تله، هر دو، تیزتر شده.",
                               "stat_bonus": {"def": 10, "max_hp": 20}, "power": 140},
            },
        },
        2: {
            "level_req": 25, "title": "⚔️ افسانه‌ی جاده",
            "flavor": "اسمت دیگه بینِ مسافرها زمزمه می‌شه.",
            "branches": {
                "adv2_blade": {"name": "🌑 تیغِ سایه", "flavor": "تو تاریکی، خودِ خطر می‌شی.",
                               "stat_bonus": {"atk": 22, "max_hp": 40}, "power": 330},
                "adv2_guard": {"name": "🛡 پاسبانِ مرزها", "flavor": "هرچی سرِ راهت باشه، اول باید از رویِ تو رد بشه.",
                               "stat_bonus": {"def": 22, "max_hp": 55}, "power": 330},
            },
        },
        3: {
            "level_req": 45, "title": "🌌 اسطوره‌ی سرگردان",
            "flavor": "قصه‌ی تو دیگه فقط قصه‌ی یه ماجراجو نیست.",
            "branches": {
                "adv3_eternal": {"name": "⚔️ شمشیرزنِ ابدی", "flavor": "هیچ کاتانایی جز مالِ تو، دیگه بهت نمی‌خوره.",
                                 "stat_bonus": {"atk": 42, "def": 12, "max_hp": 90}, "power": 700},
                "adv3_hoarder": {"name": "💎 گنجینه‌یابِ بی‌مثال", "flavor": "دنیا دیگه رازی از تو نداره.",
                                 "stat_bonus": {"def": 32, "atk": 18, "max_hp": 110}, "power": 700},
            },
        },
    },
    "merchant": {
        1: {
            "level_req": 10, "title": "🌱 گشایشِ بازار",
            "flavor": "اولین قدم‌های امپراتوریِ تجاریت.",
            "branches": {
                "mer1_gold": {"name": "💰 بارونِ طلا", "flavor": "هر معامله‌ای که می‌کنی، یه‌جوری به نفعت تموم می‌شه.",
                              "stat_bonus": {"atk": 8, "max_hp": 15}, "power": 140},
                "mer1_deal": {"name": "🤝 استادِ مذاکره", "flavor": "هیچ‌کس نمی‌تونه سرت کلاه بذاره — تو همیشه یه قدم جلوتری.",
                              "stat_bonus": {"def": 8, "max_hp": 25}, "power": 140},
            },
        },
        2: {
            "level_req": 25, "title": "🏛 امپراتوریِ نوپا",
            "flavor": "اسمت دیگه رو تابلوهای بازارِ بزرگ دیده می‌شه.",
            "branches": {
                "mer2_auction": {"name": "🔨 شاهِ حراج", "flavor": "هر چیزی که می‌خوای، دیر یا زود مالِ تو می‌شه.",
                                 "stat_bonus": {"atk": 18, "max_hp": 40}, "power": 330},
                "mer2_shadow": {"name": "🖤 سایه‌ی بازارِ سیاه", "flavor": "بعضی معامله‌ها رو باید تو تاریکی انجام داد.",
                                "stat_bonus": {"def": 18, "max_hp": 60}, "power": 330},
            },
        },
        3: {
            "level_req": 45, "title": "👑 افسانه‌ی تجارت",
            "flavor": "دیگه تو بازی نمی‌کنی — بازار مالِ توئه.",
            "branches": {
                "mer3_emperor": {"name": "👑 امپراتورِ زرین", "flavor": "اقتصادِ نیم‌قاره زیرِ سایه‌ی توئه.",
                                 "stat_bonus": {"atk": 38, "def": 12, "max_hp": 90}, "power": 700},
                "mer3_banker": {"name": "🏦 بانکدارِ ابدی", "flavor": "هرکسی یه روز به تو بدهکار می‌شه.",
                                "stat_bonus": {"def": 38, "atk": 12, "max_hp": 100}, "power": 700},
            },
        },
    },
    "healer": {
        1: {
            "level_req": 10, "title": "🌱 روشناییِ نخست",
            "flavor": "فیضی که ازت می‌تابه، اولین‌بار محسوس شده.",
            "branches": {
                "heal1_guard": {"name": "🕊 نگهبانِ نور", "flavor": "بدنت خودش داره یاد می‌گیره چطور زخم رو ببنده.",
                                "stat_bonus": {"def": 9, "max_hp": 30}, "power": 140},
                "heal1_purify": {"name": "⚡ پاک‌کننده‌ی تاریکی", "flavor": "نورت دیگه فقط ترمیم نمی‌کنه — می‌سوزونه.",
                                 "stat_bonus": {"atk": 9, "max_hp": 15}, "power": 140},
            },
        },
        2: {
            "level_req": 25, "title": "✨ فیضِ کامل",
            "flavor": "الهه‌ای که بهش دعا می‌کنی، انگار جوابت رو داده.",
            "branches": {
                "heal2_angel": {"name": "👼 فرشته‌ی میدان", "flavor": "جایی که تو باشی، مرگ معطل می‌مونه.",
                                "stat_bonus": {"def": 20, "max_hp": 70}, "power": 330},
                "heal2_judge": {"name": "⚖️ قاضیِ الهی", "flavor": "نورت دیگه فقط برای خودی‌هاست.",
                                "stat_bonus": {"atk": 20, "max_hp": 45}, "power": 330},
            },
        },
        3: {
            "level_req": 45, "title": "🕊 تجسمِ الهه",
            "flavor": "دیگه دعا نمی‌کنی — خودت جوابِ دعای یکی دیگه‌ای.",
            "branches": {
                "heal3_seraph": {"name": "🌟 سرافیمِ جاودان", "flavor": "هیچ‌کس تو حضورِ تو واقعاً نمی‌میره.",
                                 "stat_bonus": {"def": 40, "max_hp": 160}, "power": 700},
                "heal3_herald": {"name": "🔥 قاصدِ داوری", "flavor": "فیضِ تو یه‌جور تیغه شده.",
                                 "stat_bonus": {"atk": 40, "def": 10, "max_hp": 90}, "power": 700},
            },
        },
    },
}


def _tree_for(player: dict) -> dict:
    return EVOLUTION_TREE.get(player.get("class"), {})


def current_stage(player: dict) -> int:
    return player.get("evolution_stage", 0)


def pending_stage(player: dict) -> dict | None:
    """اگه یه تکاملِ جدید باز شده باشه (سطح کافی + هنوز انتخاب نکرده)،
    اطلاعاتِ اون مرحله رو برمی‌گردونه؛ وگرنه None."""
    tree = _tree_for(player)
    if not tree:
        return None
    next_stage_num = current_stage(player) + 1
    stage = tree.get(next_stage_num)
    if not stage:
        return None
    if player.get("level", 1) < stage["level_req"]:
        return None
    return {"stage_num": next_stage_num, **stage}


def apply_evolution(player: dict, branch_id: str) -> tuple[bool, str]:
    stage = pending_stage(player)
    if not stage:
        return False, "❌ الان تکاملِ جدیدی برای انتخاب نداری."
    branch = stage["branches"].get(branch_id)
    if not branch:
        return False, "❌ این مسیر برای مرحله‌ی فعلی معتبر نیست."

    bonus = branch["stat_bonus"]
    stats = player.setdefault("stats", {"hp": player.get("max_hp", 100), "max_hp": player.get("max_hp", 100),
                                         "atk": 10, "def": 5})
    stats["atk"] = stats.get("atk", 10) + bonus.get("atk", 0)
    stats["def"] = stats.get("def", 5) + bonus.get("def", 0)
    hp_gain = bonus.get("max_hp", 0)
    stats["max_hp"] = stats.get("max_hp", 100) + hp_gain
    stats["hp"] = stats.get("hp", stats["max_hp"]) + hp_gain
    # سینکِ فیلدهای تاپ-لولِ سازگاری (همون الگویی که class_system.py استفاده می‌کنه)
    player["max_hp"] = player.get("max_hp", 100) + hp_gain
    player["hp"] = player.get("hp", player["max_hp"]) + hp_gain

    player["evolution_stage"] = stage["stage_num"]
    player.setdefault("evolution_path", []).append(branch_id)

    return True, (
        f"🧬 **تکامل انجام شد!**\n\n"
        f"{stage['title']}\n"
        f"➡️ **{branch['name']}**\n"
        f"_{branch['flavor']}_\n\n"
        f"⚔️ +{bonus.get('atk',0)} حمله | 🛡 +{bonus.get('def',0)} دفاع | ❤️ +{hp_gain} HP"
    )


def evolution_power_bonus(player: dict) -> float:
    """سهمِ تکامل‌های گرفته‌شده برای Combat Power (combat_power.py)."""
    tree = _tree_for(player)
    total = 0.0
    for i, branch_id in enumerate(player.get("evolution_path", []), start=1):
        stage = tree.get(i)
        if not stage:
            continue
        branch = stage["branches"].get(branch_id)
        if branch:
            total += branch.get("power", 0)
    return total


def status_text(player: dict) -> str:
    tree = _tree_for(player)
    if not tree:
        return "🧬 کلاسِ تو مسیرِ تکامل نداره."
    path = player.get("evolution_path", [])
    lines = [f"🧬 **مسیرِ تکاملِ تو** (مرحله {current_stage(player)}/{len(tree)})\n"]
    if not path:
        lines.append("هنوز هیچ تکاملی نگرفتی.")
    else:
        for i, branch_id in enumerate(path, start=1):
            stage = tree.get(i, {})
            branch = stage.get("branches", {}).get(branch_id, {})
            lines.append(f"{i}. {stage.get('title','')} → **{branch.get('name','?')}**")
    pending = pending_stage(player)
    if pending:
        lines.append(f"\n✨ یه تکاملِ جدید در دسترسه: **{pending['title']}**! از /evolve استفاده کن.")
    else:
        tree_keys = sorted(tree.keys())
        next_undone = [n for n in tree_keys if n > current_stage(player)]
        if next_undone:
            need_lvl = tree[next_undone[0]]["level_req"]
            lines.append(f"\n🔒 تکاملِ بعدی تو سطح {need_lvl} باز می‌شه.")
        else:
            lines.append("\n🏆 به آخرین مرحله‌ی تکاملت رسیدی!")
    return "\n".join(lines)
