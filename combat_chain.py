# ============================================================
#  ASTRAL ABYSS — Attack Chain / Finisher System (مکانیک کاملاً جدید)
# ------------------------------------------------------------
#  ترتیبِ آخرین ۳ نوع حمله‌ای که تو یه نبرد زده شده رو دنبال می‌کنه.
#  اگه بازیکن یه الگوی خاص رو کامل کنه، یه «فینیشر» فعال می‌شه: بونوس
#  دمیج + گاهی افکتِ ویژه (وضعیت اجباری/rage اضافه). زنجیره روی خودِ
#  پروفایل ذخیره می‌شه (player["atk_chain"]) و با شروعِ نبردِ جدید،
#  فرار یا مرگ ریست می‌شه (توسط combat_handlers.py صدا زده می‌شه).
# ============================================================

CHAIN_MAX_LEN = 3

FINISHERS = [
    {
        "seq": ["quick", "quick", "heavy"],
        "name": "برش سه‌گانه", "emoji": "🌪️", "dmg_mult": 1.4,
        "msg": "🌪️ **فینیشر: برش سه‌گانه!** آخرین ضربه ۴۰٪ قوی‌تر شد!",
    },
    {
        "seq": ["element", "element", "heavy"],
        "name": "شکاف عنصری", "emoji": "💠", "dmg_mult": 1.3, "force_status": True,
        "msg": "💠 **فینیشر: شکاف عنصری!** دشمن مجبور شد افکتِ عنصری بگیره!",
    },
    {
        "seq": ["heavy", "quick", "combo"],
        "name": "آتشبار پایانی", "emoji": "🔥", "dmg_mult": 1.5,
        "msg": "🔥 **فینیشر: آتشبار پایانی!** ۵۰٪ دمیج اضافه گرفتی!",
    },
    {
        "seq": ["quick", "element", "quick"],
        "name": "رقص تیغه", "emoji": "⚡", "dmg_mult": 1.25, "bonus_rage": 15,
        "msg": "⚡ **فینیشر: رقص تیغه!** ۲۵٪ دمیج اضافه + ۱۵ Rage اضافه!",
    },
]


def get_chain(player: dict) -> list:
    return player.get("atk_chain", [])


def reset_chain(player: dict):
    player["atk_chain"] = []


def chain_display(player: dict) -> str:
    """نمایشِ کوتاهِ زنجیره‌ی فعلی برای پنل حمله."""
    icons = {"quick": "⚡", "heavy": "💥", "element": "🌀", "combo": "🔥", "ultimate": "☄️"}
    chain = get_chain(player)
    if not chain:
        return "—"
    return " ".join(icons.get(a, "❔") for a in chain)


def track_chain(player: dict, atk_type: str) -> dict | None:
    """نوعِ حمله‌ی جدید رو اضافه می‌کنه؛ اگه الگوی فینیشری کامل شده باشه
    اون فینیشر رو برمی‌گردونه و زنجیره رو ریست می‌کنه، وگرنه None."""
    chain = player.setdefault("atk_chain", [])
    chain.append(atk_type)
    if len(chain) > CHAIN_MAX_LEN:
        chain.pop(0)

    for f in FINISHERS:
        n = len(f["seq"])
        if len(chain) >= n and chain[-n:] == f["seq"]:
            player["atk_chain"] = []
            return f
    return None
