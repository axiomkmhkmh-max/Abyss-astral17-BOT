# ============================================================
#  ASTRAL ABYSS — Goddess Blessing Selection 🕊 (موهبتِ الهه)
# ------------------------------------------------------------
#  قدمِ آخرِ ساختِ کاراکتر: یه‌بار در کلِ حساب، بازیکن یکی از چند
#  «موهبتِ الهه» رو انتخاب می‌کنه که مسیرِ کلاسشو خفیف تغییر می‌ده.
#  مکانیزمِ واقعی (ذخیره/محاسبه‌ی CP) همون goddess_system.CHEAT_SKILLS
#  / claim_cheat_skill هست — این ماژول فقط UIِ لحظه‌ی ساختِ کاراکتر
#  رو می‌سازه (و claim رو یه‌بار برای همیشه قفل می‌کنه، پس دیگه از
#  /goddess هم بعداً قابلِ گرفتن نیست).
# ============================================================
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ButtonStyle

from goddess_system import CHEAT_SKILLS, claim_cheat_skill, can_claim_cheat_skill

INTRO_TEXT = (
    "🕊 **الهه‌ی آغازها ظاهر می‌شه...**\n\n"
    "_«قبل از اینکه راهت رو تو Abyss شروع کنی، یه هدیه‌ی کوچیک بهت می‌دم — "
    "یه موهبت که همیشه همراهته و هرچی قوی‌تر بشی، قوی‌تر می‌شه. "
    "فقط یه‌بار می‌تونی انتخاب کنی، پس خوب فکر کن.»_\n\n"
    "یکی از موهبت‌های زیر رو انتخاب کن:\n"
)


def blessing_kb() -> InlineKeyboardMarkup:
    rows = []
    for skill_id, s in CHEAT_SKILLS.items():
        rows.append([InlineKeyboardButton(
            text=f"{s['name']}", callback_data=f"charcreate_blessing:{skill_id}", style=ButtonStyle.PRIMARY,
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def blessing_list_text() -> str:
    lines = [INTRO_TEXT]
    for s in CHEAT_SKILLS.values():
        lines.append(f"{s['name']} — {s['desc']}")
    return "\n".join(lines)


def grant_starting_blessing(player: dict, skill_id: str) -> tuple[bool, str]:
    if not can_claim_cheat_skill(player):
        return False, "❌ قبلاً موهبتت رو گرفتی."
    ok, msg = claim_cheat_skill(player, skill_id)
    if ok:
        msg = f"🕊 **موهبتِ الهه رو پذیرفتی!**\n\n{msg}\n\n_این موهبت همراهته — هرچی سطحت بالاتر بره، قوی‌تر می‌شه._"
    return ok, msg
