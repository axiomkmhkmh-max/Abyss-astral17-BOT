# ============================================================
#  ASTRAL ABYSS — Stand Combat Integration (PvE)
# ------------------------------------------------------------
#  تا اینجا استند فقط رو Combat Power عدد اضافه می‌کرد. این فایل
#  همون قدرت رو به یه اثرِ واقعیِ توی نبرد تبدیل می‌کنه — بر اساسِ
#  دسته‌ی استندِ کاراکتر (که خودش deterministic و ثابته):
#
#     تهاجمی  → % افزایشِ مستقیمِ دمیج
#     روان    → دمیجِ ثابتِ اضافه («ضربه‌ی روانی») روی هر حمله
#     زمان    → شانسِ «پژواک» — یه ضربه‌ی دوم با نصفِ دمیج
#     دفاعی   → کاهشِ درصدیِ دمیجِ ضدحمله‌ی دشمن
#     فضایی   → شانسِ خنثی‌کردنِ کاملِ ضدحمله‌ی دشمن (جاخالیِ بُعدی)
#     پشتیبان → بازگردوندنِ درصدی از دمیجِ واردشده به‌عنوانِ HP
#
#  قدرتِ همه‌ی این‌ها از همون فرمولی میاد که Combat Power رو
#  می‌سازه (total_stand_score × رتبه × بونوسِ پیوند) — پس آپگرید یا
#  تمرینِ استند بلافاصله رو نبردِ واقعی هم اثر می‌ذاره.
#
#  از combat_engine.apply_combat_v2 با try/except صدا زده می‌شه؛
#  اگه هر ارورِ import ای بده، نبرد دقیقاً مثلِ قبل کار می‌کنه.
# ============================================================
from __future__ import annotations


def stand_combat_modifiers(player: dict) -> dict:
    """{dmg_mult, flat_bonus, echo_chance, counter_reduce_pct,
    dodge_counter_chance, lifesteal_pct, category}"""
    mods = {
        "dmg_mult": 1.0, "flat_bonus": 0, "echo_chance": 0.0,
        "counter_reduce_pct": 0.0, "dodge_counter_chance": 0.0,
        "lifesteal_pct": 0.0, "category": "",
    }
    char_name = player.get("character", "")
    if not char_name:
        return mods

    try:
        from stand_system import get_stand, total_stand_score, get_stand_rank
        stand = get_stand(char_name)
        total = total_stand_score(player, stand)
        _, rank_mult = get_stand_rank(total)
        try:
            from stand_bond import bond_power_multiplier
            bond_mult = bond_power_multiplier(player)
        except Exception:
            bond_mult = 1.0
        potency = total * rank_mult * bond_mult
    except Exception:
        return mods

    cat = stand["category"]
    mods["category"] = cat

    if cat == "تهاجمی":
        mods["dmg_mult"] = 1.0 + min(potency * 0.0025, 0.35)
    elif cat == "روان":
        mods["flat_bonus"] = int(min(potency * 0.6, 120))
    elif cat == "زمان":
        mods["echo_chance"] = min(potency * 0.0035, 0.30)
    elif cat == "دفاعی":
        mods["counter_reduce_pct"] = min(potency * 0.003, 0.40)
    elif cat == "فضایی":
        mods["dodge_counter_chance"] = min(potency * 0.002, 0.20)
    elif cat == "پشتیبان":
        mods["lifesteal_pct"] = min(potency * 0.0015, 0.15)

    return mods
