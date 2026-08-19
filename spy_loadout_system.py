# ============================================================
#  ASTRAL ABYSS — Spy Loadout System (تجهیزاتِ جاسوسی، عمیق‌سازی)
# ------------------------------------------------------------
#  قبلاً: خرید از economy.SPY_ITEMS فقط یه آیتمِ بی‌اثر تو انبار
#  می‌ذاشت (فقط شمارشِ خام‌شون ۲٪ ریسکِ دیلر رو کم می‌کرد).
#
#  الان: هر آیتمِ جاسوسی یه «دسته» داره و بازیکن باید تجهیزش کنه
#  تا اثر بذاره — نه فقط داشته باشدش تو کوله‌پشتی:
#
#    🔭 شناسایی (recon)     → کاهشِ ریسکِ گیرافتادن پیشِ دیلرهای گردشی
#    🥷 مخفی‌کاری (stealth)  → امتیازِ امنیتِ اضافه برای دفاعِ خونه (robbery)
#    💣 خرابکاری (sabotage)  → بونوسِ سهمِ دزدی وقتی خودت مهاجمی
#    🎫 یکبارمصرف (utility)  → مصرفِ فوری برای فرارِ تضمینی/عبورِ امن
#
#  هر آیتمِ تجهیزشده «دوام» (charge) داره — با هر بار مصرفِ اثرش
#  کم می‌شه، و وقتی صفر شد می‌شکنه و اسلات خالی می‌شه (باید دوباره
#  از بازارِ سیاه بخری و تجهیز کنی). این یعنی بازارِ سیاه یه حلقه‌ی
#  اقتصادیِ واقعی می‌گیره، نه فقط یه خریدِ یک‌باره‌ی بی‌اثر.
#
#  فقط از رویِ economy.SPY_ITEMS و player["inventory"] کار می‌کنه؛
#  هیچ فایلِ قدیمی رو نمی‌شکنه (فقط black_market_dealers.catch_risk
#  و house_system.robbery_chance یه هوکِ اختیاریِ جدید می‌گیرن).
# ============================================================
from __future__ import annotations

DEFAULT_CHARGES = 6

SPY_CATEGORY: dict[str, str] = {
    "Ghost Radar":        "recon",
    "Pulse Scanner":      "recon",
    "Shadow Lens":        "recon",
    "Data Worm":          "recon",

    "Cloak Beacon":       "stealth",
    "Silent Step Module": "stealth",
    "EMP Coin":           "stealth",
    "Pulse Charge":       "stealth",

    "Nano Wire Trap":     "sabotage",
    "Memory Scrambler":   "sabotage",

    "Purple Smoke":       "utility",
    "Architect Key":      "utility",
    "Void Pass":          "utility",
}

CATEGORY_LABEL = {
    "recon":    "🔭 شناسایی",
    "stealth":  "🥷 مخفی‌کاری",
    "sabotage": "💣 خرابکاری",
    "utility":  "🎫 یکبارمصرف",
}

SLOT_KEYS = ["recon", "stealth", "sabotage"]  # utility اسلات نداره — مستقیم مصرف می‌شه

# هر واحدِ ریسک/امنیتی که یه آیتمِ تجهیزشده در طولِ عمرش می‌ده
RECON_RISK_REDUCTION_PER_ITEM   = 0.05
STEALTH_SECURITY_PER_ITEM       = 4
SABOTAGE_ATTACKER_BONUS_PER_ITEM = 0.06


def ensure_loadout(player: dict) -> dict:
    lo = player.setdefault("spy_loadout", {})
    for slot in SLOT_KEYS:
        lo.setdefault(slot, None)  # None یا {"name":..., "charges": N}
    return lo


def _inv_owned_count(player: dict, item_name: str) -> int:
    return sum(1 for it in player.get("inventory", []) if it.get("name") == item_name)


def _remove_one_from_inventory(player: dict, item_name: str) -> bool:
    inv = player.get("inventory", [])
    for i, it in enumerate(inv):
        if it.get("name") == item_name:
            del inv[i]
            return True
    return False


def equip(player: dict, item_name: str) -> tuple[bool, str]:
    """یه آیتمِ جاسوسیِ خریداری‌شده رو از انبار برمی‌داره و تو اسلاتِ دسته‌ش می‌ذاره."""
    cat = SPY_CATEGORY.get(item_name)
    if not cat:
        return False, "❌ این آیتم شناخته‌شده نیست."
    if cat == "utility":
        return False, "🎫 آیتم‌های یکبارمصرف تجهیز نمی‌شن — مستقیم از دکمه‌ی «مصرف» استفاده‌شون کن."

    if _inv_owned_count(player, item_name) < 1:
        return False, "❌ این آیتم رو تو انبارت نداری (اول از بازارِ سیاه بخر)."

    lo = ensure_loadout(player)
    if not _remove_one_from_inventory(player, item_name):
        return False, "❌ خطا در برداشتن از انبار."

    old = lo.get(cat)
    lo[cat] = {"name": item_name, "charges": DEFAULT_CHARGES}
    msg = f"✅ {item_name} تو اسلاتِ {CATEGORY_LABEL[cat]} تجهیز شد. (دوام: {DEFAULT_CHARGES})"
    if old:
        msg += f"\n🗑 {old['name']} قبلی از اسلات خارج شد و پس داده نمی‌شه."
    return True, msg


def unequip(player: dict, slot: str) -> tuple[bool, str]:
    lo = ensure_loadout(player)
    cur = lo.get(slot)
    if not cur:
        return False, "❌ این اسلات خالیه."
    lo[slot] = None
    return True, f"↩️ {cur['name']} از اسلاتِ {CATEGORY_LABEL[slot]} خارج شد (آیتم مصرف‌شده بود، برنمی‌گرده)."


def _consume_charge(player: dict, slot: str) -> str | None:
    """یه واحدِ دوام از آیتمِ تجهیزشده تو این اسلات کم می‌کنه؛ اگه شکست، اسم آیتمِ شکسته رو برمی‌گردونه."""
    lo = ensure_loadout(player)
    cur = lo.get(slot)
    if not cur:
        return None
    cur["charges"] -= 1
    if cur["charges"] <= 0:
        lo[slot] = None
        return cur["name"]
    return None


def recon_risk_reduction(player: dict) -> tuple[float, str | None]:
    """کاهشِ ریسکِ گیرافتادن پیشِ دیلر؛ با هر خریدِ ریسکی یه چارجِ recon مصرف می‌شه."""
    lo = ensure_loadout(player)
    cur = lo.get("recon")
    if not cur:
        return 0.0, None
    broken = _consume_charge(player, "recon")
    return RECON_RISK_REDUCTION_PER_ITEM, broken


def stealth_security_bonus(player: dict) -> int:
    """امتیازِ امنیتِ اضافه برای دفاعِ خونه — فقط از بودنِ آیتم تو اسلات (مصرف نمی‌شه مگه واقعاً دزدی بشه)."""
    lo = ensure_loadout(player)
    cur = lo.get("stealth")
    return STEALTH_SECURITY_PER_ITEM if cur else 0


def stealth_consume_on_robbery_defense(player: dict) -> str | None:
    lo = ensure_loadout(player)
    if not lo.get("stealth"):
        return None
    return _consume_charge(player, "stealth")


def sabotage_attacker_bonus(player: dict) -> tuple[float, str | None]:
    """وقتی خودت داری دزدی می‌کنی، بونوسِ سهمِ دزدی؛ یه چارجِ sabotage مصرف می‌شه."""
    lo = ensure_loadout(player)
    cur = lo.get("sabotage")
    if not cur:
        return 0.0, None
    broken = _consume_charge(player, "sabotage")
    return SABOTAGE_ATTACKER_BONUS_PER_ITEM, broken


# ─── آیتم‌های یکبارمصرفِ utility ────────────────────────────────
def use_utility(player: dict, item_name: str) -> tuple[bool, str]:
    cat = SPY_CATEGORY.get(item_name)
    if cat != "utility":
        return False, "❌ این آیتم یکبارمصرف نیست."
    if not _remove_one_from_inventory(player, item_name):
        return False, "❌ این آیتم رو تو انبارت نداری."

    flags = player.setdefault("spy_utility_flags", {})
    if item_name == "Purple Smoke":
        flags["guaranteed_escape"] = flags.get("guaranteed_escape", 0) + 1
        return True, "💨 دودِ بنفش آماده‌ست — دفعه‌ی بعد که پیشِ دیلر گیر بیفتی، تضمینی فرار می‌کنی."
    if item_name == "Void Pass":
        flags["void_pass"] = flags.get("void_pass", 0) + 1
        return True, "🎫 Void Pass فعال شد — خریدِ بعدیت از دیلرِ گردشی صفر ریسک داره."
    if item_name == "Architect Key":
        flags["dealer_exclusive_peek"] = flags.get("dealer_exclusive_peek", 0) + 1
        return True, "🗝️ Architect Key فعال شد — دفعه‌ی بعد که دیلرها رو باز کنی، کالای ویژه‌ی رتبه‌ی بالاتر هم می‌بینی."
    return True, "✅ مصرف شد."


def pop_utility_flag(player: dict, flag: str) -> bool:
    flags = player.setdefault("spy_utility_flags", {})
    if flags.get(flag, 0) > 0:
        flags[flag] -= 1
        return True
    return False


def loadout_text(player: dict) -> str:
    lo = ensure_loadout(player)
    lines = ["🎒 **لودآوتِ جاسوسی**\n"]
    for slot in SLOT_KEYS:
        cur = lo.get(slot)
        if cur:
            lines.append(f"{CATEGORY_LABEL[slot]}: **{cur['name']}** (دوام: {cur['charges']})")
        else:
            lines.append(f"{CATEGORY_LABEL[slot]}: _خالی_")
    flags = player.get("spy_utility_flags", {})
    active = [f for f, n in flags.items() if n > 0]
    if active:
        names = {"guaranteed_escape": "💨 فرارِ تضمینی", "void_pass": "🎫 Void Pass", "dealer_exclusive_peek": "🗝️ کلیدِ معمار"}
        lines.append("\n⚡ **آماده‌به‌مصرف:** " + "، ".join(f"{names.get(f,f)}×{flags[f]}" for f in active))
    return "\n".join(lines)
