# ============================================================
#  ASTRAL ABYSS — Team System + Combat Heal (با لاگ‌گذاری کامل)
#  رفع باگ: دعوت تیم - گیر کردن در منوی انتخاب بازیکن
# ============================================================
import time
import random
from aiogram import Dispatcher, F, Bot
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from database import get_player, save_player, all_players
from economy import bz_to_display
from logger import log_sync

# ─── حالت سخت: نفرین مرگ / قفل درمان / محدودیت روزانه ────────
from combat_handlers import (
    heal_locked, curse_active, DEATH_CURSE_HEAL_PEN,
    heal_on_cooldown, start_heal_cooldown, heal_cooldown_remaining, HEAL_COOLDOWN_SECONDS,
)
from skill_tree import effective_max_hp

def _house_heal_bonus(player: dict) -> float:
    """پرکِ ملک شخصی: خونه‌های بالاتر یه بونوس درمانِ اضافه می‌دن."""
    try:
        from house_system import hp_regen_bonus
        return hp_regen_bonus(player)
    except ImportError:
        return 0.0

def hardcore_heal_cost(base_cost: int, player: dict) -> int:
    """هزینه‌ی درمان (که همه‌جا قبلاً ۳ برابر شده) + سورشارژ نفرین مرگ."""
    cost = base_cost
    if curse_active(player):
        cost = int(cost * (1 + DEATH_CURSE_HEAL_PEN))
    return cost

# ─── Team Storage ────────────────────────────────────────────
# uid → {"partner": uid, "since": time}
teams: dict[int, dict] = {}
# Pending invites: target_uid → {"from": uid, "expires": time}
team_invites: dict[int, dict] = {}

# ─── Heal Items ──────────────────────────────────────────────
HEAL_ITEMS = [
    {"name": "Minor Potion",  "emoji": "🧪", "hp": 25,  "cost": 300,  "desc": "بازیابی ۲۵ HP"},
    {"name": "Health Potion", "emoji": "💊", "hp": 50,  "cost": 750,  "desc": "بازیابی ۵۰ HP"},
    {"name": "Mega Potion",   "emoji": "💉", "hp": 100, "cost": 1500,  "desc": "بازیابی ۱۰۰ HP"},
    {"name": "Elixir",        "emoji": "✨", "hp": 200, "cost": 3000, "desc": "بازیابی ۲۰۰ HP"},
    {"name": "Full Restore",  "emoji": "💎", "hp": 999, "cost": 9000, "desc": "HP کامل بازیابی"},
]

def hp_bar(current: int, maximum: int, length: int = 8) -> str:
    if maximum <= 0: return "⬛" * length
    filled = max(0, int((current / maximum) * length))
    bar_color = "🟩" if filled > length//2 else "🟨" if filled > length//4 else "🟥"
    return bar_color * filled + "⬛" * (length - filled)

# ─── Team Commands ───────────────────────────────────────────

async def cmd_team(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    from level_gate import check_level
    ok, why = check_level(player, "team")
    if not ok:
        await msg.answer(why)
        return

    # Check current team
    if uid in teams:
        partner_uid = teams[uid]["partner"]
        partner = get_player(partner_uid)
        partner_name = partner["name"] if partner else "نامشخص"
        since = int(time.time() - teams[uid]["since"])
        mins = since // 60

        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💔 ترک تیم", callback_data=f"team:leave:{uid}", style=ButtonStyle.DANGER)
        ]])
        await msg.answer(
            f"👥 **تیم فعلی:**\n\n"
            f"🔴 **{player['name']}** (تو)\n"
            f"🔵 **{partner_name}**\n\n"
            f"⏱ مدت: **{mins} دقیقه**\n\n"
            f"مزایای تیم:\n"
            f"• ⚔️ حمله مشترک به باس\n"
            f"• 💊 هیل تیمی\n"
            f"• 💰 اشتراک Zen در PvP\n"
            f"• 🛡 دفاع مشترک",
            reply_markup=kb
        )
        return

    # No team - show options
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➕ دعوت بازیکن", callback_data="team:invite_menu", style=ButtonStyle.PRIMARY),
        InlineKeyboardButton(text="🔍 تیم‌های آنلاین", callback_data="team:browse", style=ButtonStyle.PRIMARY),
    ]])
    await msg.answer(
        f"👥 **سیستم تیم**\n\n"
        f"تو الان تیم نداری!\n\n"
        f"با یه تیم:\n"
        f"• ⚔️ حمله مشترک به باس +۵۰٪\n"
        f"• 💊 هیل تیمی در فایت\n"
        f"• 💰 Zen بیشتر در PvP\n"
        f"• 🛡 دفاع مشترک\n\n"
        f"_حداکثر ۲ نفر در تیم_",
        reply_markup=kb
    )

# ─── دعوت به تیم ─────────────────────────────────────────────

async def cb_team_invite_menu(cb: CallbackQuery):
    uid = cb.from_user.id
    players = all_players()
    candidates = [
        (int(pid), p) for pid, p in players.items()
        if int(pid) != uid
        and int(pid) not in teams
        and p.get("character")
    ]

    if not candidates:
        await cb.answer("😔 هیچ بازیکن آزادی پیدا نشد!", show_alert=True)
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 برگشت", callback_data="team:back", style=ButtonStyle.PRIMARY)
        ]])
        await cb.message.edit_text("👥 **هیچ بازیکنی برای دعوت پیدا نشد.**", reply_markup=kb)
        return

    buttons = []
    for tid, p in candidates[:10]:
        buttons.append([InlineKeyboardButton(
            text=f"📨 دعوت {p['name']} (Lv.{p.get('level',1)})",
            callback_data=f"team:send_invite:{tid}"
        , style=ButtonStyle.PRIMARY)])
    buttons.append([InlineKeyboardButton(text="🔙 برگشت", callback_data="team:back", style=ButtonStyle.PRIMARY)])

    await cb.message.edit_text(
        f"👥 **انتخاب بازیکن برای دعوت:**\n\n"
        f"{len(candidates)} بازیکن آنلاین و آزاد",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await cb.answer()

# ─── ارسال دعوت ──────────────────────────────────────────────

async def cb_team_send_invite(cb: CallbackQuery, bot: Bot):
    # 🔎 دیباگ موقت: تأیید می‌کنه که هندلر واقعاً صدا زده شده
    log_sync(f"🔎 DEBUG cb_team_send_invite ENTER | uid={cb.from_user.id} | data={cb.data}", "TEAM")
    try:
        await _cb_team_send_invite_body(cb, bot)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log_sync(f"🔴 **cb_team_send_invite CRASH**\n`{type(e).__name__}: {e}`\n```{tb[-1500:]}```", "ERROR")
        try:
            await cb.answer("⚠️ خطا تو ارسال دعوت! لاگ شد.", show_alert=True)
        except Exception:
            pass


async def _cb_team_send_invite_body(cb: CallbackQuery, bot: Bot):
    uid = cb.from_user.id
    parts = cb.data.split(":")
    if len(parts) < 3:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    target_uid = int(parts[2])

    if uid in teams:
        await cb.answer("❌ قبلاً توی تیم هستی!", show_alert=True)
        return

    if target_uid in teams:
        await cb.answer("❌ این بازیکن قبلاً توی تیمه!", show_alert=True)
        return

    player = get_player(uid)
    target = get_player(target_uid)
    if not player or not target:
        await cb.answer("❌ بازیکن پیدا نشد!", show_alert=True)
        return

    # Send invite
    team_invites[target_uid] = {
        "from": uid,
        "from_name": player["name"],
        "expires": time.time() + 60
    }

    log_sync(
        f"📨 **TEAM INVITE SENT**\n"
        f"👤 فرستنده: {player.get('name','—')} (`{uid}`)\n"
        f"👤 گیرنده: {target.get('name','—')} (`{target_uid}`)",
        "TEAM"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ قبول", callback_data=f"team:accept:{uid}", style=ButtonStyle.SUCCESS),
        InlineKeyboardButton(text="❌ رد",   callback_data=f"team:reject:{uid}", style=ButtonStyle.DANGER),
    ]])

    try:
        await bot.send_message(
            target_uid,
            f"👥 **دعوت تیم!**\n\n"
            f"**{player['name']}** (Lv.{player.get('level',1)}) بهت دعوت فرستاد!\n"
            f"کاراکتر: {player.get('character','—')}\n\n"
            f"⏳ ۶۰ ثانیه وقت داری!",
            reply_markup=kb
        )
        
        # 🔥 رفع باگ: صفحه رو با پیام موفقیت آپدیت کن
        back_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 برگشت به تیم", callback_data="team:back", style=ButtonStyle.PRIMARY)
        ]])
        await cb.message.edit_text(
            f"✅ **دعوت به {target['name']} فرستاده شد!**\n\n"
            f"⏳ منتظر جواب باش...",
            reply_markup=back_kb
        )
        await cb.answer(f"📨 دعوت به {target['name']} فرستاده شد!", show_alert=True)
        
    except Exception as e:
        await cb.answer("❌ نتونستم پیام بفرستم! (شاید ربات رو استارت نکرده)", show_alert=True)
        log_sync(
            f"❌ **TEAM INVITE FAILED**\n"
            f"👤 فرستنده: `{uid}`\n"
            f"👤 گیرنده: `{target_uid}`\n"
            f"❌ خطا: {str(e)}",
            "ERROR"
        )

# ─── قبول دعوت ──────────────────────────────────────────────

async def cb_team_accept(cb: CallbackQuery, bot: Bot):
    uid = cb.from_user.id
    parts = cb.data.split(":")
    if len(parts) < 3:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    from_uid = int(parts[2])

    invite = team_invites.get(uid)
    if not invite or invite["from"] != from_uid:
        await cb.answer("⏰ دعوت منقضی شد!", show_alert=True)
        try:
            await cb.message.edit_text("❌ این دعوت دیگه معتبر نیست.")
        except Exception:
            pass
        return

    if time.time() > invite["expires"]:
        await cb.answer("⏰ دعوت منقضی شد!", show_alert=True)
        del team_invites[uid]
        try:
            await cb.message.edit_text("❌ زمان دعوت تموم شد.")
        except Exception:
            pass
        return

    if uid in teams or from_uid in teams:
        await cb.answer("❌ یکی از شما قبلاً توی تیمه!", show_alert=True)
        return

    # Create team
    now = time.time()
    teams[uid]      = {"partner": from_uid, "since": now}
    teams[from_uid] = {"partner": uid,      "since": now}
    del team_invites[uid]

    p1 = get_player(uid)
    p2 = get_player(from_uid)

    log_sync(
        f"✅ **TEAM FORMED**\n"
        f"👤 عضو ۱: {p1.get('name','—') if p1 else '—'} (`{uid}`)\n"
        f"👤 عضو ۲: {p2.get('name','—') if p2 else '—'} (`{from_uid}`)",
        "TEAM"
    )

    await cb.answer("✅ تیم تشکیل شد!", show_alert=True)
    
    team_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💔 ترک تیم", callback_data=f"team:leave:{uid}", style=ButtonStyle.DANGER)
    ]])
    
    await cb.message.edit_text(
        f"👥 **تیم تشکیل شد!**\n\n"
        f"🔴 {p1['name'] if p1 else '—'}\n"
        f"🔵 {p2['name'] if p2 else '—'}\n\n"
        f"✅ مزایا فعال شدند!\n"
        f"• ⚔️ حمله مشترک به باس +۵۰٪\n"
        f"• 💊 هیل تیمی در فایت\n"
        f"• 💰 Zen بیشتر در PvP",
        reply_markup=team_kb
    )

    try:
        await bot.send_message(
            from_uid,
            f"👥 **{p1['name'] if p1 else '—'} دعوتت رو قبول کرد!**\n\n"
            f"تیم تشکیل شد! ✅"
        )
    except Exception:
        pass

# ─── رد دعوت ─────────────────────────────────────────────────

async def cb_team_reject(cb: CallbackQuery, bot: Bot):
    uid = cb.from_user.id
    parts = cb.data.split(":")
    if len(parts) < 3:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    from_uid = int(parts[2])
    team_invites.pop(uid, None)
    
    log_sync(
        f"❌ **TEAM REJECTED**\n"
        f"👤 ردکننده: `{uid}`\n"
        f"👤 فرستنده: `{from_uid}`",
        "TEAM"
    )
    
    await cb.answer("❌ رد کردی!", show_alert=True)
    await cb.message.edit_text("❌ دعوت رد شد.")
    try:
        p = get_player(uid)
        await bot.send_message(from_uid, f"❌ {p['name'] if p else '—'} دعوتت رو رد کرد.")
    except Exception:
        pass

# ─── ترک تیم ─────────────────────────────────────────────────

async def cb_team_leave(cb: CallbackQuery, bot: Bot):
    uid = cb.from_user.id
    parts = cb.data.split(":")
    if len(parts) < 3:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    
    if uid not in teams:
        await cb.answer("❌ توی تیم نیستی!", show_alert=True)
        return

    partner_uid = teams[uid]["partner"]
    p = get_player(uid)
    partner = get_player(partner_uid)
    
    log_sync(
        f"💔 **TEAM LEFT**\n"
        f"👤 خروج‌کننده: {p.get('name','—') if p else '—'} (`{uid}`)\n"
        f"👤 هم‌تیمی: {partner.get('name','—') if partner else '—'} (`{partner_uid}`)",
        "TEAM"
    )
    
    teams.pop(uid, None)
    teams.pop(partner_uid, None)

    await cb.answer("💔 از تیم خارج شدی!", show_alert=True)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➕ دعوت بازیکن", callback_data="team:invite_menu", style=ButtonStyle.PRIMARY),
        InlineKeyboardButton(text="🔍 تیم‌های آنلاین", callback_data="team:browse", style=ButtonStyle.PRIMARY),
    ]])
    await cb.message.edit_text(
        f"💔 **از تیم خارج شدی!**\n\n"
        f"برای تشکیل تیم جدید از دکمه‌های زیر استفاده کن.",
        reply_markup=kb
    )
    
    try:
        await bot.send_message(
            partner_uid,
            f"💔 **{p['name'] if p else '—'} از تیم خارج شد!**\nتیم منحل شد."
        )
    except Exception:
        pass

# ─── مرور تیم‌های فعال ──────────────────────────────────────

async def cb_team_browse(cb: CallbackQuery):
    await cb.answer("🔍 در حال جستجو...")
    lines = ["👥 **تیم‌های فعال:**\n\n"]
    seen = set()
    count = 0
    for uid, team in teams.items():
        partner = team["partner"]
        if (uid, partner) in seen or (partner, uid) in seen:
            continue
        seen.add((uid, partner))
        p1 = get_player(uid)
        p2 = get_player(partner)
        if p1 and p2:
            lines.append(f"⚔️ {p1['name']} + {p2['name']}\n")
            count += 1

    if count == 0:
        lines.append("_هیچ تیم فعالی نیست_")

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔙 برگشت", callback_data="team:back", style=ButtonStyle.PRIMARY)
    ]])
    await cb.message.edit_text("".join(lines), reply_markup=kb)

# ─── برگشت به منوی اصلی ─────────────────────────────────────

async def cb_team_back(cb: CallbackQuery):
    uid = cb.from_user.id
    
    # بررسی اینکه آیا کاربر هنوز تیم داره
    if uid in teams:
        partner_uid = teams[uid]["partner"]
        partner = get_player(partner_uid)
        partner_name = partner["name"] if partner else "نامشخص"
        since = int(time.time() - teams[uid]["since"])
        mins = since // 60

        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💔 ترک تیم", callback_data=f"team:leave:{uid}", style=ButtonStyle.DANGER)
        ]])
        await cb.message.edit_text(
            f"👥 **تیم فعلی:**\n\n"
            f"🔴 **{player.get('name','—') if player else '—'}** (تو)\n"
            f"🔵 **{partner_name}**\n\n"
            f"⏱ مدت: **{mins} دقیقه**\n\n"
            f"مزایای تیم:\n"
            f"• ⚔️ حمله مشترک به باس\n"
            f"• 💊 هیل تیمی\n"
            f"• 💰 اشتراک Zen در PvP\n"
            f"• 🛡 دفاع مشترک",
            reply_markup=kb
        )
        await cb.answer()
        return
    
    # اگر تیم نداره، منوی اصلی رو نشون بده
    player = get_player(uid)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➕ دعوت بازیکن", callback_data="team:invite_menu", style=ButtonStyle.PRIMARY),
        InlineKeyboardButton(text="🔍 تیم‌های آنلاین", callback_data="team:browse", style=ButtonStyle.PRIMARY),
    ]])
    await cb.message.edit_text(
        f"👥 **سیستم تیم**\n\n"
        f"تو الان تیم نداری!\n\n"
        f"با یه تیم:\n"
        f"• ⚔️ حمله مشترک به باس +۵۰٪\n"
        f"• 💊 هیل تیمی در فایت\n"
        f"• 💰 Zen بیشتر در PvP\n"
        f"• 🛡 دفاع مشترک\n\n"
        f"_حداکثر ۲ نفر در تیم_",
        reply_markup=kb
    )
    await cb.answer()

# ─── Heal System ─────────────────────────────────────────────

# ─── Heal System ─────────────────────────────────────────────

async def cmd_heal(msg: Message):
    await cmd_heal_for(msg.from_user.id, msg)


async def cmd_heal_for(uid: int, target: Message):
    """همون منوی درمانِ HP، ولی uid رو جدا می‌گیره — تا هم /heal مستقیم
    (target.from_user == خودِ کاربر) و هم دکمه‌ی داخلِ 🏥 بیمارستان
    (که target یه CallbackQuery.message‌ـه و from_user‌ش خودِ رباته)
    بتونن ازش استفاده کنن."""
    player = get_player(uid)
    if not player:
        await target.answer("❌ اول /start بزن!")
        return

    if heal_locked(player):
        rem = int(player["heal_lockout_until"] - time.time())
        await target.answer(f"⏳ به‌خاطر نفرین مرگ، تا {rem//60}:{rem%60:02d} دیگه نمی‌تونی درمان بشی.")
        save_player(uid, player)
        return

    if heal_on_cooldown(player):
        rem = heal_cooldown_remaining(player)
        await target.answer(f"⏳ درمان تازه استفاده شده — تا {rem//60}:{rem%60:02d} دیگه دوباره می‌تونی درمان بشی.")
        return

    hp     = player.get("hp", 100)
    max_hp = effective_max_hp(player)
    zen    = player.get("zen", 0)

    # Check team heal option
    team_heal_txt = ""
    if uid in teams:
        partner_uid = teams[uid]["partner"]
        partner = get_player(partner_uid)
        if partner:
            p_hp = partner.get("hp", 100)
            p_max = effective_max_hp(partner)
            team_heal_txt = (
                f"\n{'─'*20}\n"
                f"👥 **هم‌تیمی: {partner['name']}**\n"
                f"❤️ HP: {p_hp}/{p_max} {hp_bar(p_hp, p_max)}\n"
            )

    buttons = []
    for i, item in enumerate(HEAL_ITEMS):
        cost = hardcore_heal_cost(item["cost"], player)
        can_afford = zen >= cost
        hp_gain = min(item["hp"], max_hp - hp)
        if hp_gain <= 0 and item["hp"] < 999:
            continue
        buttons.append([InlineKeyboardButton(
            text=f"{item['emoji']} {item['name']} +{item['hp'] if item['hp']<999 else 'Full'} HP ({bz_to_display(cost)}) {'✅' if can_afford else '❌'}",
            callback_data=f"heal_item:{i}:self"
        , style=ButtonStyle.DANGER)])
        if uid in teams:
            buttons.append([InlineKeyboardButton(
                text=f"💊 هیل هم‌تیمی ({item['name']})",
                callback_data=f"heal_item:{i}:partner"
            , style=ButtonStyle.SUCCESS)])

    full_cost_per_hp = hardcore_heal_cost(15, player)
    buttons.append([InlineKeyboardButton(
        text=f"🏥 درمان کامل ({full_cost_per_hp} BZ per HP)",
        callback_data="heal:full"
    , style=ButtonStyle.SUCCESS)])

    curse_txt = f"\n👻 نفرین مرگ فعاله: +{int(DEATH_CURSE_HEAL_PEN*100)}٪ هزینه درمان" if curse_active(player) else ""
    await target.answer(
        f"💊 **درمانِ سریعِ HP**\n\n"
        f"❤️ HP: **{hp}/{max_hp}**\n"
        f"{hp_bar(hp, max_hp)}\n"
        f"💰 موجودی: **{bz_to_display(zen)}**\n"
        f"🩹 وضعیتِ کول‌داون: {'⏳ در انتظار' if heal_on_cooldown(player) else '✅ آماده'}"
        f"{curse_txt}"
        f"{team_heal_txt}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

async def cb_heal_item(cb: CallbackQuery, bot: Bot):
    uid = cb.from_user.id
    parts = cb.data.split(":")
    if len(parts) < 3:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    idx     = int(parts[1])
    target  = parts[2]  # "self" or "partner"

    if idx >= len(HEAL_ITEMS):
        await cb.answer("❌", show_alert=True)
        return

    item   = HEAL_ITEMS[idx]
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    if heal_locked(player):
        rem = int(player["heal_lockout_until"] - time.time())
        await cb.answer(f"⏳ به‌خاطر نفرین مرگ، تا {rem//60}:{rem%60:02d} دیگه نمی‌تونی درمان بشی.", show_alert=True)
        return
    if heal_on_cooldown(player):
        rem = heal_cooldown_remaining(player)
        await cb.answer(f"⏳ درمان تازه استفاده شده — {rem//60}:{rem%60:02d} دیگه صبر کن.", show_alert=True)
        return

    cost = hardcore_heal_cost(item["cost"], player)
    if player.get("zen", 0) < cost:
        await cb.answer(f"❌ Zen کافی نداری! {bz_to_display(player['zen'])} / {bz_to_display(cost)}", show_alert=True)
        return

    start_heal_cooldown(player)
    player["zen"] -= cost
    save_player(uid, player)

    if target == "self":
        heal_amount = item["hp"] if item["hp"] < 999 else effective_max_hp(player)
        from loot_engine import get_set_bonus_stats
        from guild_system import get_perk
        heal_amount = int(heal_amount * (1 + get_set_bonus_stats(player).get("heal_pct", 0) + get_perk(player, "heal_pct") + _house_heal_bonus(player)))
        old_hp = player["hp"]
        player["hp"] = min(effective_max_hp(player), player["hp"] + heal_amount)
        actual = player["hp"] - old_hp
        save_player(uid, player)
        
        log_sync(
            f"💊 **HEAL SELF**\n"
            f"👤 {player.get('name','—')} (`{uid}`)\n"
            f"❤️ +{actual} HP\n"
            f"💰 هزینه: {bz_to_display(cost)}\n"
            f"📦 آیتم: {item['name']}",
            "TEAM"
        )
        
        await cb.answer(f"{item['emoji']} +{actual} HP!", show_alert=True)
        await cb.message.edit_text(
            f"💊 **{item['name']}** استفاده شد!\n\n"
            f"❤️ HP: {player['hp']}/{effective_max_hp(player)}\n"
            f"{hp_bar(player['hp'], effective_max_hp(player))}\n"
            f"💰 موجودی: {bz_to_display(player['zen'])}"
        )
    else:
        # Heal partner
        if uid not in teams:
            await cb.answer("❌ توی تیم نیستی!", show_alert=True)
            return
        partner_uid = teams[uid]["partner"]
        partner = get_player(partner_uid)
        if not partner:
            await cb.answer("❌ هم‌تیمی پیدا نشد!", show_alert=True)
            return
        heal_amount = item["hp"] if item["hp"] < 999 else effective_max_hp(partner)
        from loot_engine import get_set_bonus_stats
        from guild_system import get_perk
        heal_amount = int(heal_amount * (1 + get_set_bonus_stats(partner).get("heal_pct", 0) + get_perk(player, "heal_pct") + _house_heal_bonus(player)))
        old_hp = partner["hp"]
        partner["hp"] = min(effective_max_hp(partner), partner["hp"] + heal_amount)
        actual = partner["hp"] - old_hp
        save_player(partner_uid, partner)
        
        log_sync(
            f"💊 **HEAL PARTNER**\n"
            f"👤 دهنده: {player.get('name','—')} (`{uid}`)\n"
            f"👤 گیرنده: {partner.get('name','—')} (`{partner_uid}`)\n"
            f"❤️ +{actual} HP\n"
            f"💰 هزینه: {bz_to_display(cost)}\n"
            f"📦 آیتم: {item['name']}",
            "TEAM"
        )
        
        await cb.answer(f"💊 هم‌تیمی +{actual} HP!", show_alert=True)
        try:
            await bot.send_message(
                partner_uid,
                f"💊 **{player['name']} بهت هیل داد!**\n"
                f"{item['emoji']} +{actual} HP\n"
                f"❤️ HP: {partner['hp']}/{effective_max_hp(partner)}"
            )
        except Exception:
            pass
        await cb.message.edit_text(
            f"💊 **{partner['name']} هیل شد!**\n"
            f"+{actual} HP\n"
            f"❤️ HP: {partner['hp']}/{effective_max_hp(partner)}\n"
            f"💰 موجودی: {bz_to_display(player['zen'])}"
        )

async def cb_heal_full(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    if heal_locked(player):
        rem = int(player["heal_lockout_until"] - time.time())
        await cb.answer(f"⏳ به‌خاطر نفرین مرگ، تا {rem//60}:{rem%60:02d} دیگه نمی‌تونی درمان بشی.", show_alert=True)
        return
    if heal_on_cooldown(player):
        rem = heal_cooldown_remaining(player)
        await cb.answer(f"⏳ درمان تازه استفاده شده — {rem//60}:{rem%60:02d} دیگه صبر کن.", show_alert=True)
        return

    hp     = player.get("hp", 100)
    max_hp = effective_max_hp(player)
    missing = max_hp - hp

    if missing <= 0:
        await cb.answer("❤️ HP کاملته!", show_alert=True)
        return

    cost = missing * hardcore_heal_cost(15, player)
    if player.get("zen", 0) < cost:
        await cb.answer(f"❌ Zen کافی نداری! نیاز: {bz_to_display(cost)}", show_alert=True)
        return

    start_heal_cooldown(player)
    player["zen"] -= cost
    player["hp"]   = max_hp
    save_player(uid, player)
    
    log_sync(
        f"🏥 **HEAL FULL**\n"
        f"👤 {player.get('name','—')} (`{uid}`)\n"
        f"❤️ +{missing} HP\n"
        f"💰 هزینه: {bz_to_display(cost)}",
        "TEAM"
    )
    
    await cb.answer(f"✅ +{missing} HP! کامل شدی!", show_alert=True)
    await cb.message.edit_text(
        f"💊 **درمان کامل!**\n\n"
        f"❤️ HP: {max_hp}/{max_hp} {'🟩'*8}\n"
        f"💰 هزینه: {bz_to_display(cost)}\n"
        f"موجودی: {bz_to_display(player['zen'])}"
    )

# ─── Combat Heal (Emergency) ─────────────────────────────────

def get_combat_heal_kb(uid: int) -> InlineKeyboardMarkup:
    buttons = []
    player = get_player(uid)
    if not player:
        return InlineKeyboardMarkup(inline_keyboard=[])

    zen = player.get("zen", 0)
    for i, item in enumerate(HEAL_ITEMS[:3]):
        cost = hardcore_heal_cost(item["cost"], player)
        can = zen >= cost
        buttons.append([InlineKeyboardButton(
            text=f"{item['emoji']} {item['name']} +{item['hp']} HP ({bz_to_display(cost)}) {'✅' if can else '❌'}",
            callback_data=f"combat_heal:{i}:{uid}"
        , style=ButtonStyle.DANGER)])
    buttons.append([InlineKeyboardButton(text="🔙 ادامه فایت", callback_data="combat_heal:cancel", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def cb_combat_heal(cb: CallbackQuery):
    await cb.answer("⛔ دیگه نمی‌تونی وسطِ نبرد درمان بشی! باید قبل یا بعدِ فایت به فکرِ HP-ات باشی.", show_alert=True)
    return

# ─── Team Status ─────────────────────────────────────────────

def get_team_bonus(uid: int) -> dict:
    if uid not in teams:
        return {"dmg_bonus": 0, "zen_bonus": 0, "xp_bonus": 0}
    bonus = {"dmg_bonus": 10, "zen_bonus": 0.2, "xp_bonus": 0.15}
    # ─── بونوسِ تنوعِ استند: اگه دسته‌ی استندِ تو و پارتنرت فرق کنه ────
    # (مثلاً تو تهاجمی، پارتنرت دفاعی) یعنی ترکیبِ متعادل‌تری دارید —
    # یه بونوسِ دمیجِ اضافه به‌عنوانِ پاداشِ همکاریِ استراتژیک.
    try:
        partner_uid = teams[uid]["partner"]
        me = get_player(uid)
        partner = get_player(partner_uid)
        if me and partner and me.get("character") and partner.get("character"):
            from stand_system import get_stand
            my_cat = get_stand(me["character"])["category"]
            partner_cat = get_stand(partner["character"])["category"]
            if my_cat != partner_cat:
                bonus["dmg_bonus"] += 6
    except Exception:
        pass
    return bonus

def is_in_team(uid: int) -> bool:
    return uid in teams

def get_partner(uid: int) -> int | None:
    if uid in teams:
        return teams[uid]["partner"]
    return None

# ─── Register ────────────────────────────────────────────────

def register_team_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_team,  Command("team"))
    dp.message.register(cmd_heal,  Command("heal"))

    async def _w_team_send_invite(c): await cb_team_send_invite(c, bot)
    async def _w_team_accept(c): await cb_team_accept(c, bot)
    async def _w_team_reject(c): await cb_team_reject(c, bot)
    async def _w_team_leave(c): await cb_team_leave(c, bot)
    async def _w_heal_item(c): await cb_heal_item(c, bot)

    dp.callback_query.register(cb_team_invite_menu,              F.data == "team:invite_menu")
    dp.callback_query.register(_w_team_send_invite, F.data.startswith("team:send_invite:"))
    dp.callback_query.register(_w_team_accept, F.data.startswith("team:accept:"))
    dp.callback_query.register(_w_team_reject, F.data.startswith("team:reject:"))
    dp.callback_query.register(_w_team_leave,  F.data.startswith("team:leave:"))
    dp.callback_query.register(cb_team_browse,                    F.data == "team:browse")
    dp.callback_query.register(cb_team_back,                      F.data == "team:back")

    dp.callback_query.register(_w_heal_item,   F.data.startswith("heal_item:"))
    dp.callback_query.register(cb_heal_full,                      F.data == "heal:full")
    dp.callback_query.register(cb_combat_heal,                    F.data.startswith("combat_heal:"))
