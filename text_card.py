# ============================================================
#  ASTRAL ABYSS — Character Card (نسخه‌ی متنی)
# ------------------------------------------------------------
#  یه کارتِ هویتیِ متنی شبیهِ کارتِ قهرمانِ بازی‌های معروف، با خط‌کشیِ
#  یونیکد. برخلافِ profile_card.py (که عکسِ PNG می‌سازه)، این یکی فقط
#  متنه — نیازی به هیچ آرت/تصویری نداره، تو خودِ تلگرام (داخلِ یه
#  بلاکِ <pre> مونواسپیس) نمایش داده می‌شه و مستقیم قابلِ فوروارد به
#  گروه/چته. دقیقاً همون فرمتی که خودِ کاربر پیشنهاد داده بود.
# ============================================================

WIDTH = 26  # عرضِ داخلیِ کارت (بینِ دو تا ║)

RANK_DECOR = {
    "common":    {"badge": "⚪", "corner": "·"},
    "rare":      {"badge": "🔵", "corner": "◆"},
    "legendary": {"badge": "🟡", "corner": "★"},
    "special":   {"badge": "🟣", "corner": "✦"},
    "mythic":    {"badge": "🔴", "corner": "🔥"},
}

RANK_LABEL_EN = {
    "common": "Common", "rare": "Rare", "legendary": "Legendary",
    "special": "Special", "mythic": "Mythic",
}


def _center(text: str) -> str:
    """وسط‌چین کردنِ یه خط داخلِ عرضِ کارت (برای متنِ فارسی دقیق نیست،
    چون طولِ کاراکترها متغیره، ولی برای اسم/عددهای لاتین کاملاً درسته)."""
    text = str(text)
    if len(text) >= WIDTH:
        return text[:WIDTH]
    pad = WIDTH - len(text)
    left = pad // 2
    right = pad - left
    return f"{' ' * left}{text}{' ' * right}"


def _row(text: str = "") -> str:
    return f"║{_center(text)}║"


def generate_character_card_text(player: dict, char_data: dict) -> str:
    """کارتِ متنیِ کاملِ کاراکتر رو می‌سازه — شاملِ نام، رنک، کلاس، قدرت،
    سلاح، عنوانِ فعال، بردهای PvP و گیلد. آماده برای فرستادن داخلِ <pre>."""
    from combat_power import calculate_combat_power, get_cp_label
    from katana_core import get_katana_identity
    from isekai_theme import rank_for_level, map_label

    rarity = char_data.get("rarity", "common")
    decor  = RANK_DECOR.get(rarity, RANK_DECOR["common"])
    corner = decor["corner"]

    name      = player.get("name", "Traveler")
    char_name = player.get("character", "—")
    gender_ic = "♀" if player.get("gender") == "female" else "♂"

    ident       = get_katana_identity(char_name)
    katana_name = ident.get("name", char_data.get("katana", "—"))

    guild_letter, guild_fa = rank_for_level(player.get("level", 1), player.get("rebirth_count", 0))
    map_jp = map_label(player.get("map", ""))

    titles = player.get("titles_unlocked", [])
    try:
        from divine_seals import get_seal_title
        seal_title = get_seal_title(player)
    except Exception:
        seal_title = None
    active_title = seal_title or (titles[-1] if titles else "—")

    cp       = calculate_combat_power(player)
    cp_label = get_cp_label(cp)

    guild_txt = "—"
    try:
        from guild_system import GUILDS
        guilds = player.get("guilds", {})
        if guilds:
            gid = next(iter(guilds))
            guild_txt = GUILDS.get(gid, {}).get("name", gid)
    except Exception:
        pass

    lines = [
        f"╔{'═' * WIDTH}╗",
        _row(f"{corner} ASTRAL ABYSS {corner}"),
        _row(),
        _row(f"{name}  {gender_ic}"),
        _row(),
        _row(f"{decor['badge']} {char_name}"),
        _row(),
        _row(f"Level: {player.get('level', 1)}"),
        _row(f"Rank: {RANK_LABEL_EN.get(rarity, rarity)}"),
        _row(),
        _row(f"AdvRank: {guild_letter}"),
        _row(guild_fa),
        _row(),
        _row("Class:"),
        _row(char_data.get("element", "—")),
        _row(),
        _row("Power:"),
        _row(f"{cp:,}  ({cp_label})"),
        _row(),
        _row("Weapon:"),
        _row(katana_name),
        _row(),
        _row("Title:"),
        _row(active_title),
        _row(),
        _row(f"Wins: {player.get('pvp_wins', 0)}"),
        _row(),
        _row("Realm:"),
        _row(map_jp or "—"),
        _row(),
        _row("Guild:"),
        _row(guild_txt),
        _row(),
        f"╚{'═' * WIDTH}╝",
    ]
    return "\n".join(lines)
