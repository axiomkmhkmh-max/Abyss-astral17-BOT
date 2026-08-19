# ============================================================
#  ASTRAL ABYSS — BOSS INVITE SYSTEM
# ------------------------------------------------------------
#  یه لایه‌ی مشترک برای دعوت کردنِ یه بازیکنِ خاص به هر سه نوع
#  باس‌فایتِ چندنفره‌ی بازی: باسِ جهانی، باسِ گروه/چت، باسِ منطقه‌ای
#  (هر مپ). این فایل فقط state نگه می‌داره + یه لایه‌ی نازک برای
#  گرفتن/ذخیره‌کردنِ باسِ درست بر اساسِ نوعش — منطقِ خودِ نبرد هنوز
#  تو boss_engine.py + سه‌تا هندلرِ مربوطه‌ست.
# ============================================================
import time

INVITE_TTL_SEC = 300  # ۵ دقیقه فرصت برای قبول کردنِ دعوت

# target_uid → {"from_uid", "boss_type", "ref", "boss_name", "expires"}
pending_invites: dict[int, dict] = {}


def boss_type_label(boss_type: str) -> str:
    return {
        "world": "باسِ جهانی",
        "group": "باسِ این گروه",
        "region": "باسِ منطقه‌ای",
    }.get(boss_type, "باس")


def get_boss_by_ref(boss_type: str, ref) -> dict | None:
    if boss_type == "world":
        from database import get_boss
        return get_boss()
    if boss_type == "group":
        from group_system import get_group_boss
        return get_group_boss(int(ref))
    if boss_type == "region":
        from region_boss_system import get_region_boss
        return get_region_boss(str(ref))
    return None


def create_invite(from_uid: int, target_uid: int, boss_type: str, ref, boss_name: str) -> dict:
    invite = {
        "from_uid": from_uid,
        "boss_type": boss_type,
        "ref": ref,
        "boss_name": boss_name,
        "expires": time.time() + INVITE_TTL_SEC,
    }
    pending_invites[target_uid] = invite
    return invite


def pop_invite(target_uid: int) -> dict | None:
    invite = pending_invites.pop(target_uid, None)
    if not invite:
        return None
    if time.time() > invite["expires"]:
        return None
    return invite


def peek_invite(target_uid: int) -> dict | None:
    invite = pending_invites.get(target_uid)
    if not invite:
        return None
    if time.time() > invite["expires"]:
        pending_invites.pop(target_uid, None)
        return None
    return invite
