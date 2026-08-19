# ============================================================
#  ASTRAL ABYSS — Combat Engine v2
# ------------------------------------------------------------
#  این فایل جداست و هیچ تابع قدیمی combat.py رو جایگزین نمی‌کنه.
#  calc_combat() تو combat.py در همون آخر کارش (بعد از محاسبه‌ی
#  dmg/crit/miss/counter/lifesteal قدیمی) این ماژول رو با try/except
#  صدا می‌زنه تا نتیجه رو با مکانیک‌های جدید تکمیل کنه:
#
#     • ۹ عنصر + یه چرخه‌ی برتری/ضعف ثانویه (علاوه بر weak اصلی)
#     • Armor / Elemental Resistance / Accuracy / Evasion دشمن —
#       به‌صورت خودکار از روی tier محاسبه می‌شه، پس نیازی به ادیت
#       دستی ۲۰۰+ دشمن تو combat.py نیست. اگه یه دشمن خاص بعداً
#       خودش armor/accuracy/... رو صراحتاً داشته باشه، همون اولویت داره.
#     • Rage/Ultimate Gauge روی خود پروفایل بازیکن (player["rage"])
#       ذخیره می‌شه — با ری‌استارت سرور از بین نمی‌ره.
#     • Guard Break — بعضی دشمن‌ها (بر اساس tier) شانس "guard" دارن؛
#       heavy/ultimate این سپر رو می‌شکنه و بونوس دمیج می‌ده.
#     • Perfect Counter — وقتی دشمن ضدحمله می‌زنه، شانسی هست که
#       بازیکن کامل خنثاش کنه و بخشی از دمیج رو برگردونه.
#
#  اگه این فایل هنوز آپلود نشده باشه یا هر ارور دیگه‌ای بده، نبرد
#  دقیقاً مثل قبل (بدون این مکانیک‌ها) کار می‌کنه — چون combat.py
#  این importِ داخلش رو تو try/except گذاشته.
# ============================================================
import random

# ─── ۹ عنصر (دقیقاً همون‌هایی که تو weak دشمن‌ها / element کاراکترها هست) ───
ELEMENT_CYCLE = ["آتش", "یخ", "برق", "زمین", "آب", "نور", "تاریکی", "مقدس", "خلأ"]


def _cycle_index(e: str) -> int:
    return ELEMENT_CYCLE.index(e) if e in ELEMENT_CYCLE else -1


def element_cycle_modifier(attacker_element: str, enemy_weak: str) -> float:
    """
    اثر ثانویه‌ی عنصری — علاوه بر ضعف اصلی (weak) که تو خود combat.py
    هندل می‌شه. هر عنصر تو چرخه نسبت به همسایه‌ی بعدی‌ش کمی برتری داره
    (+۱۲٪) و نسبت به همسایه‌ی قبلی‌ش کمی ضعف (-۱۰٪). این فقط یه مدولاسیون
    کوچیکه، سیستم weak اصلی رو override نمی‌کنه.
    """
    ai, wi = _cycle_index(attacker_element), _cycle_index(enemy_weak)
    if ai == -1 or wi == -1:
        return 1.0
    n = len(ELEMENT_CYCLE)
    if wi == (ai + 1) % n:
        return 1.12
    if wi == (ai - 1) % n:
        return 0.90
    return 1.0


# ─── Enemy Defense Profile (بر اساس tier) ─────────────────────
TIER_DEFENSE = {
    "common":    {"armor": 0,  "accuracy": 0.85, "evasion": 0.05, "crit_resist": 0.00, "guard_chance": 0.00, "elem_resist": 0.00},
    "rare":      {"armor": 6,  "accuracy": 0.88, "evasion": 0.08, "crit_resist": 0.05, "guard_chance": 0.06, "elem_resist": 0.08},
    "epic":      {"armor": 14, "accuracy": 0.90, "evasion": 0.11, "crit_resist": 0.10, "guard_chance": 0.13, "elem_resist": 0.14},
    "legendary": {"armor": 24, "accuracy": 0.93, "evasion": 0.14, "crit_resist": 0.16, "guard_chance": 0.22, "elem_resist": 0.20},
}
BOSS_BONUS = {"armor": 16, "accuracy": 0.05, "evasion": 0.05, "crit_resist": 0.08, "guard_chance": 0.15, "elem_resist": 0.10}


def get_enemy_defense(enemy: dict) -> dict:
    """
    اگه دشمن خودش این فیلدها رو صراحتاً داشته باشه (برای دشمن‌های دستیِ
    فازهای بعدی که دفاع خاص می‌خوایم) همونا اولویت دارن؛ وگرنه بر اساس
    tier + is_boss مقدار پیش‌فرض محاسبه می‌شه.
    """
    tier = enemy.get("tier", "common")
    base = dict(TIER_DEFENSE.get(tier, TIER_DEFENSE["common"]))
    if enemy.get("is_boss"):
        for k, v in BOSS_BONUS.items():
            base[k] += v
    for k in list(base.keys()):
        if k in enemy:
            base[k] = enemy[k]
    return base


def apply_armor(dmg: int, armor: float) -> int:
    """فرمول کلاسیک diminishing-returns: هرچی armor بیشتر بشه، اثر هر واحدش کمتره."""
    if dmg <= 0 or armor <= 0:
        return dmg
    mitig = armor / (armor + 100)
    return max(1, int(dmg * (1 - mitig)))


def apply_elem_resist(dmg: int, elem_bonus: bool, elem_resist: float) -> int:
    """اگه دمیج از ضعف عنصری (weak) بونوس گرفته باشه، مقاومت عمومی روش اثر نمی‌ذاره."""
    if dmg <= 0 or elem_bonus or elem_resist <= 0:
        return dmg
    return max(1, int(dmg * (1 - elem_resist)))


# ─── Rage / Ultimate Gauge ─────────────────────────────────────
RAGE_MAX = 100
RAGE_PER_HIT = 9
RAGE_PER_DMG_TAKEN = 0.15


def add_rage(player: dict, amount: float):
    player["rage"] = min(RAGE_MAX, int(player.get("rage", 0) + amount))


def spend_rage(player: dict):
    player["rage"] = 0


# ─── Perfect Counter ────────────────────────────────────────────
def roll_perfect_counter(skb: dict) -> bool:
    chance = 0.08 + skb.get("dodge_chance", 0) * 0.5
    return random.random() < chance


# ─── Main hook — از combat.calc_combat در آخر صدا زده می‌شه ─────
def apply_combat_v2(player: dict, enemy: dict, attack_type: str, result: dict) -> dict:
    logs = result.setdefault("logs", [])
    defense = get_enemy_defense(enemy)

    # ─── 🎭 کاراکتر: تیکِ افکت‌های وضعیتیِ نوبتِ قبل (سوختن/شوک/کندی/کوری) ──
    # همیشه صدا زده می‌شه، حتی رو میس — دقیقاً مثلِ rage روی خودِ enemy
    # ذخیره می‌مونه، پس با ری‌استارتِ سرور هم از بین نمی‌ره.
    try:
        from character_combat import tick_status
        tick_status(enemy, result)
    except Exception:
        pass

    # ─── مُهرِ الهی: ضریبِ سرعتِ پرشدنِ گیجِ rage (پیش‌فرض ۱.۰) ──────
    try:
        from divine_seals import get_seal_rage_mult
        rage_mult = get_seal_rage_mult(player)
    except ImportError:
        rage_mult = 1.0

    # ─── استند: تبدیلِ قدرتِ استند به اثرِ واقعیِ نبرد ────────────
    try:
        from stand_combat import stand_combat_modifiers
        stand_mods = stand_combat_modifiers(player)
    except Exception:
        stand_mods = {}

    if result["dmg"] > 0 and not result.get("miss"):
        # ── Guard / Guard Break ─────────────────────────────
        if random.random() < defense["guard_chance"]:
            if attack_type in ("heavy", "ultimate"):
                result["dmg"] = int(result["dmg"] * 1.2)
                result["guard_break"] = True
                logs.append("🛡️💥 **Guard Break!** سپر دشمن شکست و دمیج اضافه خورد!")
            else:
                result["dmg"] = int(result["dmg"] * 0.5)
                result["guarded"] = True
                logs.append("🛡️ دشمن سپرش رو بالا آورد و نصف دمیج رو خنثی کرد!")

        # ── اثرِ استند (تهاجمی/روان): ضریب و بونوسِ ثابت ─────────
        if stand_mods.get("dmg_mult", 1.0) != 1.0:
            result["dmg"] = int(result["dmg"] * stand_mods["dmg_mult"])
        if stand_mods.get("flat_bonus"):
            result["dmg"] += stand_mods["flat_bonus"]
            logs.append(f"🧠 استندت {stand_mods['flat_bonus']} دمیجِ روانیِ اضافه زد!")

        # ── 🎭 کاراکتر: عنصر (چرخه + ضعفِ جبرانی + افکتِ وضعیتیِ تازه) و
        # ندرت (دمیج/کریت/لایف‌استیل/توانایی خودکار) — قبل از armor تا
        # زره‌شکنی/خلأ رو همین ضربه هم ببینه.
        try:
            from character_combat import apply_character_combat
            result = apply_character_combat(player, enemy, attack_type, result, defense)
        except Exception:
            pass

        # ── Armor mitigation ─────────────────────────────────
        result["dmg"] = apply_armor(result["dmg"], defense["armor"])
        # ── Elemental resistance عمومی (اگه از weak بونوس نگرفته) ──
        result["dmg"] = apply_elem_resist(result["dmg"], result.get("elem_bonus", False), defense["elem_resist"])

        # ── اثرِ استند (زمان): پژواک — یه ضربه‌ی دومِ نصفه ─────────
        if stand_mods.get("echo_chance") and random.random() < stand_mods["echo_chance"]:
            echo_dmg = max(1, int(result["dmg"] * 0.5))
            result["dmg"] += echo_dmg
            logs.append(f"⏳ استندت زمان رو پژواک داد — {echo_dmg} دمیجِ اضافه!")

        # ── اثرِ استند (پشتیبان): بازگردوندنِ بخشی از دمیج به HP ────
        if stand_mods.get("lifesteal_pct"):
            heal = int(result["dmg"] * stand_mods["lifesteal_pct"])
            if heal > 0:
                max_hp = player.get("max_hp", player.get("hp", 100))
                player["hp"] = min(max_hp, player.get("hp", 0) + heal)
                logs.append(f"💫 استندت {heal} HP بهت برگردوند!")

        # ── Rage gauge از حمله‌ی موفق ──────────────────────────
        add_rage(player, RAGE_PER_HIT * rage_mult)

    if attack_type == "ultimate":
        spend_rage(player)

    # ── اثرِ استند (فضایی/دفاعی): کاهش یا خنثی‌سازیِ ضدحمله‌ی دشمن ──
    if result.get("enemy_dmg", 0) > 0:
        if stand_mods.get("dodge_counter_chance") and random.random() < stand_mods["dodge_counter_chance"]:
            logs.append("🌀 استندت با یه جاخالیِ بُعدی کاملِ ضدحمله رو خنثی کرد!")
            result["enemy_dmg"] = 0
        elif stand_mods.get("counter_reduce_pct"):
            reduced = int(result["enemy_dmg"] * stand_mods["counter_reduce_pct"])
            if reduced > 0:
                result["enemy_dmg"] -= reduced
                logs.append(f"🛡️ بارریرِ استندت {reduced} از ضدحمله‌ی دشمن رو خنثی کرد!")

    # ── Perfect Counter روی ضدحمله‌ی دشمن ─────────────────────
    if result.get("counter") and result.get("enemy_dmg", 0) > 0:
        try:
            from skill_tree import get_skill_bonuses
            skb = get_skill_bonuses(player)
        except Exception:
            skb = {}
        if roll_perfect_counter(skb):
            reflect = int(result["enemy_dmg"] * 0.6)
            result["enemy_dmg"] = 0
            result["perfect_counter"] = True
            result["dmg"] += reflect
            logs.append(f"✨🛡️ **PERFECT COUNTER!** ضدحمله رو خنثی کردی و {reflect} دمیج اضافه برگردوندی!")
        else:
            add_rage(player, result["enemy_dmg"] * RAGE_PER_DMG_TAKEN * rage_mult)

    return result
