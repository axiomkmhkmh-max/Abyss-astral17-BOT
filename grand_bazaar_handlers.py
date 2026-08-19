# ============================================================
#  ASTRAL ABYSS RPG — 🏮 بازارِ بزرگ (Grand Bazaar Handlers)
# ------------------------------------------------------------
#  رابطِ تلگرامیِ grand_bazaar.py — یه هابِ زنده که بازیکن می‌تونه
#  باهاش قدم بزنه، با NPCها حرف بزنه، شایعه بشنوه و چانه بزنه.
#  دستور: /bazaar (تو PV یا گروه، مثلِ بقیه‌ی هندلرهای مشابه).
# ============================================================
from __future__ import annotations

import random
import time

from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
from logger import log_sync
import grand_bazaar as gb

# ─── کیبوردها ──────────────────────────────────────────────────

def _hub_keyboard() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for npc in gb.all_npcs():
        row.append(InlineKeyboardButton(text=f"{npc['title'].split()[0]} {npc['name']}", callback_data=f"bazaar_npc:{npc['id']}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        InlineKeyboardButton(text="🚶 قدم زدن تو بازار", callback_data="bazaar_wander"),
        InlineKeyboardButton(text="🚪 خروج", callback_data="bazaar_leave"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _npc_keyboard(npc_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛍️ درباره‌ی کالاها بپرس", callback_data=f"bazaar_goods:{npc_id}"),
            InlineKeyboardButton(text="👂 شایعه بشنو", callback_data=f"bazaar_rumor:{npc_id}"),
        ],
        [InlineKeyboardButton(text="💰 چانه بزن", callback_data=f"bazaar_haggle:{npc_id}")],
        [InlineKeyboardButton(text="👋 خداحافظی", callback_data=f"bazaar_bye:{npc_id}")],
        [InlineKeyboardButton(text="🔙 برگشت به بازار", callback_data="bazaar_hub")],
    ])


def _hub_text() -> str:
    ambient = gb.roll_ambient()
    lines = [
        "🏮 **بازارِ بزرگ**",
        "",
        "صدای چونه‌زدن، بوی ادویه و آهنگِ سازها از هر گوشه‌ای می‌رسه — این‌جا قلبِ تپنده‌ی هر قلمروئه.",
        f"_{ambient}_",
        "",
        "با کی می‌خوای حرف بزنی؟ یا فقط دوست داری قدم بزنی؟",
    ]
    return "\n".join(lines)


# ─── /bazaar ──────────────────────────────────────────────────

async def cmd_bazaar(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return
    await msg.answer(_hub_text(), reply_markup=_hub_keyboard())


async def cb_bazaar_hub(cb: CallbackQuery):
    await cb.answer()
    await cb.message.edit_text(_hub_text(), reply_markup=_hub_keyboard())


async def cb_bazaar_leave(cb: CallbackQuery):
    await cb.answer()
    await cb.message.edit_text("🚪 از بازارِ بزرگ خارج شدی. هر وقت خواستی، دوباره با /bazaar برگرد.")


# ─── تعاملِ NPC ────────────────────────────────────────────────

async def cb_bazaar_npc(cb: CallbackQuery):
    npc_id = cb.data.split(":", 1)[1]
    npc = gb.get_npc(npc_id)
    if not npc:
        await cb.answer("❌ این فروشنده پیدا نشد.", show_alert=True)
        return
    await cb.answer()

    uid = cb.from_user.id
    player = get_player(uid) or {}
    state = gb.player_bazaar_state(player)
    last = state.get(f"last_greet_{npc_id}")
    line = gb.npc_line(npc, "greeting", last)
    state[f"last_greet_{npc_id}"] = line
    player["grand_bazaar"] = state
    save_player(uid, player)

    text = (
        f"{npc['title']}\n"
        f"**{npc['name']}**\n"
        f"_{npc['desc']}_\n\n"
        f"💬 {line}"
    )
    await cb.message.edit_text(text, reply_markup=_npc_keyboard(npc_id))


async def cb_bazaar_goods(cb: CallbackQuery):
    npc_id = cb.data.split(":", 1)[1]
    npc = gb.get_npc(npc_id)
    if not npc:
        await cb.answer("❌ این فروشنده پیدا نشد.", show_alert=True)
        return
    await cb.answer()

    uid = cb.from_user.id
    player = get_player(uid) or {}
    state = gb.player_bazaar_state(player)
    last = state.get(f"last_goods_{npc_id}")
    line = gb.npc_goods_line(npc, last)
    state[f"last_goods_{npc_id}"] = line
    player["grand_bazaar"] = state
    save_player(uid, player)

    text = f"{npc['title']} **{npc['name']}**\n\n🛍️ {line}"
    await cb.message.edit_text(text, reply_markup=_npc_keyboard(npc_id))


async def cb_bazaar_rumor(cb: CallbackQuery):
    npc_id = cb.data.split(":", 1)[1]
    npc = gb.get_npc(npc_id)
    if not npc:
        await cb.answer("❌ این فروشنده پیدا نشد.", show_alert=True)
        return
    await cb.answer()

    uid = cb.from_user.id
    player = get_player(uid) or {}
    state = gb.player_bazaar_state(player)
    last = state.get(f"last_rumor_{npc_id}")
    line = gb.npc_line(npc, "rumor", last)
    state[f"last_rumor_{npc_id}"] = line
    player["grand_bazaar"] = state
    save_player(uid, player)

    text = f"{npc['title']} **{npc['name']}** _(با صدای آروم‌تر)_\n\n👂 {line}"
    await cb.message.edit_text(text, reply_markup=_npc_keyboard(npc_id))


async def cb_bazaar_haggle(cb: CallbackQuery):
    npc_id = cb.data.split(":", 1)[1]
    npc = gb.get_npc(npc_id)
    if not npc:
        await cb.answer("❌ این فروشنده پیدا نشد.", show_alert=True)
        return

    uid = cb.from_user.id
    player = get_player(uid) or {}
    state = gb.player_bazaar_state(player)
    ok, remain = gb.can_haggle(state)
    if not ok:
        mins = max(1, remain // 60)
        await cb.answer(f"⏳ {npc['name']} فعلاً حوصله‌ی چانه‌زنیِ بیشتر نداره. حدودِ {mins} دقیقه‌ی دیگه دوباره امتحان کن.", show_alert=True)
        return

    reward = gb.roll_haggle_reward()
    player["zen"] = player.get("zen", 0) + reward
    state["last_haggle_ts"] = time.time()
    player["grand_bazaar"] = state
    save_player(uid, player)
    await cb.answer(f"💰 +{reward} Zen")

    flavor = gb.npc_line(npc, "haggle_flavor")
    text = (
        f"{npc['title']} **{npc['name']}**\n\n"
        f"💰 {flavor}\n\n"
        f"دستت رو می‌فشره و **{reward} Zen** میذاره کف دستت."
    )
    await cb.message.edit_text(text, reply_markup=_npc_keyboard(npc_id))
    log_sync(f"🏮 **BAZAAR HAGGLE** — {player.get('name','—')} (`{uid}`) با {npc['name']} چانه زد، +{reward} Zen", "BAZAAR")


async def cb_bazaar_bye(cb: CallbackQuery):
    npc_id = cb.data.split(":", 1)[1]
    npc = gb.get_npc(npc_id)
    if not npc:
        await cb.answer()
        await cb.message.edit_text(_hub_text(), reply_markup=_hub_keyboard())
        return
    await cb.answer()

    line = gb.npc_line(npc, "farewell")
    text = f"{npc['title']} **{npc['name']}**\n\n👋 {line}"
    await cb.message.edit_text(text, reply_markup=_hub_keyboard())


# ─── قدم‌زدن تو بازار ────────────────────────────────────────────

async def cb_bazaar_wander(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid) or {}
    state = gb.player_bazaar_state(player)
    ok, remain = gb.can_wander(state)
    if not ok:
        await cb.answer(f"⏳ یه‌کم صبر کن ({remain} ثانیه) تا دوباره قدم بزنی.", show_alert=True)
        return

    state["last_wander_ts"] = time.time()
    last_amb = state.get("last_wander_ambient")

    lines = [gb.roll_ambient(last_amb)]
    state["last_wander_ambient"] = lines[0]

    encounter = None
    if random.random() < 0.35:
        encounter = gb.roll_encounter()
        lines.append("")
        lines.append(f"✨ {encounter['text']}")
        z = encounter.get("zen", 0)
        if z:
            player["zen"] = max(0, player.get("zen", 0) + z)
            sign = "+" if z > 0 else ""
            lines.append(f"({sign}{z} Zen)")

    player["grand_bazaar"] = state
    save_player(uid, player)

    await cb.answer("🚶")
    text = "🏮 **بازارِ بزرگ** — قدم می‌زنی...\n\n" + "\n".join(lines)
    await cb.message.edit_text(text, reply_markup=_hub_keyboard())


# ─── ثبت هندلرها ────────────────────────────────────────────────

def register_grand_bazaar_handlers(dp, bot):
    dp.message.register(cmd_bazaar, Command("bazaar"))
    dp.callback_query.register(cb_bazaar_hub, F.data == "bazaar_hub")
    dp.callback_query.register(cb_bazaar_leave, F.data == "bazaar_leave")
    dp.callback_query.register(cb_bazaar_wander, F.data == "bazaar_wander")
    dp.callback_query.register(cb_bazaar_npc, F.data.startswith("bazaar_npc:"))
    dp.callback_query.register(cb_bazaar_goods, F.data.startswith("bazaar_goods:"))
    dp.callback_query.register(cb_bazaar_rumor, F.data.startswith("bazaar_rumor:"))
    dp.callback_query.register(cb_bazaar_haggle, F.data.startswith("bazaar_haggle:"))
    dp.callback_query.register(cb_bazaar_bye, F.data.startswith("bazaar_bye:"))
