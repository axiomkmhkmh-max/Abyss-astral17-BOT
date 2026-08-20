# ============================================================
#  ASTRAL ABYSS — Secret / Broken Class 🌌 (کلاسِ مخفیِ نایاب)
# ------------------------------------------------------------
#  کلاسیکِ ایسکایی: یه کلاسِ فوق‌العاده نایاب که فقط ~۱٪ از بازیکن‌ها
#  موقعِ ساختِ کاراکتر می‌گیرنش — صرفِ‌نظر از اینکه رویِ کدوم دکمه‌ی
#  کلاس زده باشن. خودِ کلاس (abyss_avatar) تو class_system.CLASSES
#  تعریف شده ولی عمداً تو CLASS_ORDER نیست، پس هیچ‌وقت تو کیبوردِ
#  انتخابِ عادی دیده نمی‌شه.
# ============================================================
import random

SECRET_CLASS_ID = "abyss_avatar"
SECRET_CLASS_CHANCE = 0.01  # ۱٪


def maybe_grant_secret_class(player: dict) -> bool:
    """صدا زده می‌شه بلافاصله بعدِ apply_class_to_player تو cb_set_class.
    اگه رول برنده بشه، کلاسِ بازیکن رو (هرچی انتخاب کرده بود) بازنویسی
    می‌کنه رو کلاسِ مخفی و True برمی‌گردونه."""
    if player.get("class") == SECRET_CLASS_ID:
        return False  # قبلاً گرفته (نباید دوباره رول بشه)
    if random.random() > SECRET_CLASS_CHANCE:
        return False

    from class_system import apply_class_to_player
    apply_class_to_player(player, SECRET_CLASS_ID)
    player["secret_class_hit"] = True
    return True


def reveal_text(player_name: str) -> str:
    return (
        "🌌💥 **یه چیزی اشتباه پیش رفت...**\n\n"
        f"وقتی روحِ {player_name} داشت وارد Abyss می‌شد، برای یه لحظه‌ی کوتاه "
        "خودِ شکافِ بینِ دنیاها بهش نگاه کرد — و به‌جای اینکه ردش کنه، توش نگهش داشت.\n\n"
        "این تصادفی نبود که تو رو تو ۱٪ از هزاران مسافر انتخاب کرد.\n\n"
        "🌌 **کلاسِ تو دیگه اونی نیست که انتخاب کرده بودی.**\n"
        "تبریک می‌گم — تو یکی از معدود **آواتارهای آبیس** هستی. کلاسی که رسماً وجود نداره."
    )
