# ============================================================
#  ASTRAL ABYSS — Raid Event Handlers (با لاگ‌گذاری کامل)
# ============================================================
import random

from gap_dispatcher import GapDispatcher
from gap_types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
from economy import bz_to_display, MAP_LOOT, RARITY_E
from raid_system import get_random_event, build_event_kb, get_outcome, MAP_EVENTS, DEFAULT_EVENTS
from game_data import xp_for_level, effective_max_level
from gap_mob_combat import dungeon_state  # چک می‌کنیم آیا بازیکن داخل زنجیره‌ی دانجن هست یا نه
from logger import log_sync

# Active raid sessions: uid → event dict
raid_sessions: dict[int, dict] = {}

def get_loot_from_tier(map_name: str, tier: str) -> dict | None:
    from economy import RARITY_E
    pool = MAP_LOOT.get(map_name, [])
    if not pool:
        return None

    tier_order = ["common", "uncommon", "rare", "epic", "mythic", "legendary"]
    tier_idx = tier_order.index(tier) if tier in tier_order else 0

    # Filter by rarity or take best available
    filtered = [i for i in pool if tier_order.index(i.get("rarity","common")) >= tier_idx]
    if not filtered:
        filtered = pool

    item = random.choice(filtered).copy()
    variation = random.uniform(0.85, 1.25)
    item["sell"] = int(item["sell"] * variation)
    item["buy"]  = int(item["buy"]  * variation)
    return item

def hp_bar(current: int, maximum: int, length: int = 8) -> str:
    if maximum <= 0: return "⬛" * length
    filled = max(0, int((current / maximum) * length))
    return "🟥" * filled + "⬛" * (length - filled)

async def start_raid_event(msg, uid: int, map_name: str):
    """شروع رویداد raid برای یه مپ — صدا زده میشه از _do_loot"""
    player = get_player(uid)
    if not player:
        return

    event = get_random_event(map_name)
    raid_sessions[uid] = {"event": event, "map": map_name}

    log_sync(
        f"⚡ **RAID EVENT START**\n"
        f"👤 {player.get('name','—')} (`{uid}`)\n"
        f"📍 مپ: {map_name}\n"
        f"📋 رویداد: {event['name']}\n"
        f"📝 توضیح: {event['desc'][:100]}...",
        "LOOT"
    )

    kb = build_event_kb(event, uid)
    await msg.edit_text(
        f"⚠️ **رویداد: {event['name']}**\n\n"
        f"{event['desc']}\n\n"
        f"❤️ HP: {player.get('hp',100)}/{player.get('max_hp',100)} "
        f"{hp_bar(player.get('hp',100), player.get('max_hp',100))}\n\n"
        f"انتخاب کن:",
        reply_markup=kb
    )

async def handle_raid_outcome(cb: CallbackQuery):
    """هندل کردن نتیجه انتخاب کاربر"""
    uid = cb.from_user.id

    # Parse callback: raid:event_id:choice:uid
    parts = cb.data.split(":")
    if len(parts) < 4:
        await cb.answer("❌ خطا!", show_alert=True)
        return

    choice_key = parts[2]
    cb_uid     = int(parts[3])

    if cb_uid != uid:
        await cb.answer("❌ این رویداد برای تو نیست!", show_alert=True)
        return

    session = raid_sessions.get(uid)
    if not session:
        await cb.answer("⏰ رویداد منقضی شد!", show_alert=True)
        return

    event    = session["event"]
    map_name = session["map"]
    outcome  = get_outcome(event, choice_key)

    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    # Apply HP cost
    hp_cost = outcome.get("hp_cost", 0)
    if hp_cost > 0:
        player["hp"] = max(1, player.get("hp", 100) - hp_cost)

    # Apply zen bonus/penalty
    zen_bonus = outcome.get("zen_bonus", 0)
    player["zen"] = max(0, player.get("zen", 0) + zen_bonus)

    # Get loot
    loot_tier = outcome.get("loot_tier", "common")
    item      = get_loot_from_tier(map_name, loot_tier)

    # 🐛 باگ‌فیکس: هماهنگ با نسخه‌ی تلگرامِ raid_handlers.py — دکمه‌ی
    # «فروش» قبلاً کلِ کوله‌پشتی رو می‌فروخت (حتی آیتم‌های قفل‌شده‌ی
    # قبلی)، نه فقط چیزی که همین الان دراپ شده.
    for _it in player.get("inventory", []):
        _it.pop("_just_looted", None)

    # Add 5 items total (1 guaranteed from event + 4 random)
    items_gotten = []
    if item:
        item["_just_looted"] = True
        items_gotten.append(item)
        player.setdefault("inventory", []).append(item)

    # 4 more random items based on tier
    tier_bonus_count = {"common":1,"uncommon":2,"rare":3,"epic":4,"mythic":5,"legendary":5}.get(loot_tier, 1)
    for _ in range(min(tier_bonus_count, 4)):
        extra = get_loot_from_tier(map_name, "common")
        if extra:
            extra["_just_looted"] = True
            items_gotten.append(extra)
            player["inventory"].append(extra)

    # XP reward
    xp_reward = {"common":10,"uncommon":20,"rare":35,"epic":60,"mythic":100,"legendary":150}.get(loot_tier, 10)
    player["xp"] = player.get("xp", 0) + xp_reward

    # Level up check
    # 🐛 باگ‌فیکس: هماهنگ با نسخه‌ی تلگرامِ raid_handlers.py — سقفِ سطح
    # اضافه شد و HP هر لول از ۱۰ به ۵ (هماهنگ با بقیه‌ی بازی).
    leveled = False
    old_level = player.get("level", 1)
    while player["xp"] >= xp_for_level(player["level"]) and player["level"] < effective_max_level(player):
        player["level"]  += 1
        player["max_hp"] += 5
        from skill_tree import effective_max_hp
        player["hp"]      = effective_max_hp(player)
        leveled = True
    if leveled:
        from skill_tree import grant_levelup_points
        grant_levelup_points(player, old_level, player["level"])
        log_sync(
            f"⭐ **LEVEL UP (RAID)**\n"
            f"👤 {player.get('name','—')} (`{uid}`)\n"
            f"📊 سطح: {old_level} → {player['level']}",
            "LEVELUP"
        )

    save_player(uid, player)
    del raid_sessions[uid]

    # Build result text
    rarity_emoji = {"common":"⚪","uncommon":"🟢","rare":"🔵","epic":"🟣","mythic":"🟠","legendary":"🟡"}
    
    # ─── لاگ کامل لوت رید ─────────────────────────────────────────
    loot_details = []
    for it in items_gotten:
        r = rarity_emoji.get(it.get("rarity","common"), "⚪")
        loot_details.append(f"{it['emoji']} {it['name']} {r} — {bz_to_display(it.get('sell',0))}")
    
    log_sync(
        f"⚡ **RAID EVENT COMPLETE**\n"
        f"👤 {player.get('name','—')} (`{uid}`)\n"
        f"📍 مپ: {map_name}\n"
        f"📋 رویداد: {event['name']}\n"
        f"🎯 انتخاب: {choice_key}\n"
        f"{'─'*20}\n"
        f"📦 **آیتم‌های دریافتی ({len(items_gotten)}):**\n" + ("\n".join(f"  • {it}" for it in loot_details) if loot_details else "  • هیچی\n") +
        f"{'─'*20}\n"
        f"💰 Zen: {zen_bonus:+,}\n"
        f"❤️ HP: {player.get('hp',100)}/{player.get('max_hp',100)}\n"
        f"✨ XP: +{xp_reward}\n"
        f"🎯 نتیجه: {outcome['msg'][:100]}...",
        "LOOT"
    )

    lines = [
        f"✅ **نتیجه:**\n\n",
        f"{outcome['msg']}\n\n",
        f"{'─'*20}\n",
        f"🎒 **لوت دریافتی:**\n",
    ]

    total_val = 0
    for it in items_gotten:
        r = rarity_emoji.get(it.get("rarity","common"), "⚪")
        lines.append(f"{it['emoji']} **{it['name']}** {r} — {bz_to_display(it['sell'])}\n")
        total_val += it.get("sell", 0)

    lines.append(f"\n{'─'*20}\n")
    if hp_cost > 0:
        lines.append(f"❤️ HP -{hp_cost} → {player['hp']}/{player['max_hp']}\n")
    if zen_bonus > 0:
        lines.append(f"💰 Zen +{zen_bonus:,}\n")
    elif zen_bonus < 0:
        lines.append(f"💸 Zen {zen_bonus:,}\n")
    lines.append(f"✨ XP +{xp_reward}\n")
    lines.append(f"💎 ارزش کل لوت: **{bz_to_display(total_val)}**")

    if leveled:
        lines.append(f"\n\n🎉 **LEVEL UP! → {player['level']}**")

    # ── اگه بازیکن داخل زنجیره‌ی دانجنه، این نتیجه یه مرحله از دانجنه ──
    d_state = dungeon_state.get(uid)
    in_dungeon = bool(d_state) and d_state.get("map") == map_name
    if in_dungeon:
        d_state["stage"] += 1
        if d_state["stage"] >= d_state["total"]:
            dungeon_state.pop(uid, None)
            lines.append("\n\n👑 **دانجن به پایان رسید! باس نهایی داره میاد...**")
            
            log_sync(
                f"👑 **DUNGEON COMPLETE**\n"
                f"👤 {player.get('name','—')} (`{uid}`)\n"
                f"📍 مپ: {map_name}\n"
                f"📊 مراحل: {d_state['total']}\n"
                f"🎁 کل آیتم‌ها: {len(items_gotten)}\n"
                f"💰 کل Zen: {zen_bonus:+,}\n"
                f"💎 ارزش کل لوت: {bz_to_display(total_val)}",
                "LOOT"
            )
            
            await cb.message.edit_text("".join(lines), reply_markup=None)
            await cb.answer("👑 باس دانجن!")
            from mob_combat import start_encounter
            await start_encounter(cb.message, uid, map_name, force_boss=True)
            return
        else:
            lines.append(f"\n\n🌀 **مرحله {d_state['stage']}/{d_state['total']} دانجن رد شد!**")
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="➡️ ادامه‌ی دانجن", callback_data=f"dg_next:{map_name}:{uid}"),
            ],[
                InlineKeyboardButton(text="🏠 پنل اصلی", callback_data="menu:home"),
            ]])
            await cb.message.edit_text("".join(lines), reply_markup=kb)
            await cb.answer("🌀 مرحله بعد!")
            return

    # ── حالت عادی (خارج از دانجن) ──
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"💰 فروشِ همین لوت ({bz_to_display(total_val)})", callback_data="raidloot:sell_new"),
        InlineKeyboardButton(text="🎒 نگه دار", callback_data="loot:keep"),
    ],[
        InlineKeyboardButton(text="🗺 لوت دوباره", callback_data="loot:again"),
    ],[
        InlineKeyboardButton(text="🏠 پنل اصلی", callback_data="menu:home"),
    ]])

    await cb.message.edit_text("".join(lines), reply_markup=kb)
    await cb.answer()

async def cb_raidloot_sell_new(cb: CallbackQuery):
    """🐛 باگ‌فیکس: این دکمه قبلاً (وقتی از callback_data='loot:sell_all'
    استفاده می‌کرد) کلِ کوله‌پشتی رو می‌فروخت — حتی آیتم‌های قفل‌شده و
    هرچی از قبل تو کوله‌پشتی بود. حالا فقط دقیقاً همون آیتم‌هایی که تو
    همین رویداد دراپ شدن (و قفل نیستن) فروخته می‌شن."""
    uid = cb.from_user.id
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    from economy import MAPS_DATA
    from economy_engine import get_dynamic_price, register_trade, compute_sell_tax, add_reputation, deposit_tax_pool
    from economy_ledger import record_transaction

    inv = player.get("inventory", [])
    to_sell = [it for it in inv if it.get("_just_looted") and not it.get("locked")]
    locked_skipped = sum(1 for it in inv if it.get("_just_looted") and it.get("locked"))

    if not to_sell:
        for it in inv:
            it.pop("_just_looted", None)
        save_player(uid, player)
        msg = "🔒 همه‌ی آیتم‌های این لوت قفل بودن — چیزی فروخته نشد." if locked_skipped else "❌ چیزی برای فروش نبود."
        await cb.answer(msg, show_alert=True)
        return

    zone = MAPS_DATA.get(player.get("map", ""), {}).get("zone", "contested")
    gross_total = 0
    sold_items = []
    for it in to_sell:
        _, sell_p, _, _ = get_dynamic_price("global_loot", it)
        gross_total += sell_p
        register_trade("global_loot", it, "sell")
        sold_items.append(f"{it.get('emoji','📦')} {it.get('name','—')} — {bz_to_display(sell_p)}")

    tax = compute_sell_tax(player, gross_total, zone, "global_loot")
    zen_before = player.get("zen", 0)

    to_sell_ids = {id(it) for it in to_sell}
    player["inventory"] = [it for it in inv if id(it) not in to_sell_ids]
    for it in player["inventory"]:
        it.pop("_just_looted", None)
    player["zen"] = player.get("zen", 0) + tax["net"]
    add_reputation(player, min(3, len(to_sell)))
    save_player(uid, player)
    deposit_tax_pool(tax["tax_amount"], uid)

    record_transaction(
        "raidloot_sell_new", uid, username=player.get("name"),
        item_name=f"{len(to_sell)} آیتم", quantity=len(to_sell),
        amount=gross_total, fee=tax["tax_amount"],
        balance_before=zen_before, balance_after=player["zen"],
        extra={"items": sold_items, "zone": zone},
    )

    log_sync(
        f"💰 **SELL RAID LOOT (فقط دراپِ همین دفعه)**\n"
        f"👤 {player.get('name','—')} (`{uid}`)\n"
        f"📦 {len(to_sell)} آیتم فروخته شد — خالص: {bz_to_display(tax['net'])}"
        + (f"\n🔒 {locked_skipped} آیتمِ قفل‌شده نگه داشته شد." if locked_skipped else ""),
        "LOOT"
    )

    text = f"💰 **{len(to_sell)} آیتمِ همین لوت فروخته شد!**\nخالص دریافتی: {bz_to_display(tax['net'])}"
    if locked_skipped:
        text += f"\n🔒 {locked_skipped} آیتمِ قفل‌شده نگه داشته شد."
    await cb.message.edit_text(text, reply_markup=None)
    await cb.answer("💰 فروخته شد!")

async def cb_dungeon_next(cb: CallbackQuery):
    """رفتن به مرحله‌ی بعدی دانجن (بعد از رد کردن یه مرحله)"""
    parts = cb.data.split(":")
    if len(parts) < 3:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    map_name, cb_uid = parts[1], int(parts[2])
    uid = cb.from_user.id
    if cb_uid != uid:
        await cb.answer("❌ این برای تو نیست!", show_alert=True)
        return
    if uid not in dungeon_state:
        await cb.answer("⏰ دانجن دیگه فعال نیست!", show_alert=True)
        return
    
    log_sync(
        f"🌀 **DUNGEON NEXT STAGE**\n"
        f"👤 کاربر: `{uid}`\n"
        f"📍 مپ: {map_name}\n"
        f"📊 مرحله: {dungeon_state[uid]['stage']+1}/{dungeon_state[uid]['total']}",
        "LOOT"
    )
    
    await start_raid_event(cb.message, uid, map_name)
    await cb.answer()

def register_gap_raid_handlers(dp: GapDispatcher):
    dp.register_callback(handle_raid_outcome, data_startswith="raid:")
    dp.register_callback(cb_dungeon_next,     data_startswith="dg_next:")
    dp.register_callback(cb_raidloot_sell_new, data="raidloot:sell_new")
