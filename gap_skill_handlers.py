# ============================================================
#  ASTRAL ABYSS — Gap Skill Tree Handlers
#  (پورت از skill_handlers.py)
# ------------------------------------------------------------
#  باگ‌فیکس: سیستمِ درختِ مهارت (skill_tree.py) هیچ‌وقت برای گپ
#  پورت نشده بود — bot_dual.py هیچ register_gap_skill_handlers
#  ای نداشت، پس دستور /skills و کل UI خرجِ امتیاز مهارت روی گپ
#  اصلاً وجود نداشت (بازیکن‌های گپ امتیازِ مهارت جمع می‌کردن ولی
#  هیچ راهی برای خرجش نداشتن).
#  منطقِ خالص (skill_tree.py) عیناً import می‌شه — صفر تغییر.
# ============================================================
from __future__ import annotations

from gap_dispatcher import GapDispatcher
from gap_types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
from logger import log_sync
import skill_tree as st


async def cmd_skills(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    await msg.answer(st.skill_summary_text(player), reply_markup=st.build_paths_menu_kb())


async def cb_skill_path(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    if not player:
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return
    path = cb.data.split(":")[1]
    try:
        await cb.message.edit_text(st.path_tree_text(player, path), reply_markup=st.build_path_kb(player, path))
    except Exception:
        pass
    await cb.answer()


async def cb_skill_unlock(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    if not player:
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return
    node_id = cb.data.split(":", 1)[1]
    ok, message = st.unlock_skill(player, node_id)
    save_player(uid, player)

    if ok:
        node = st.SKILL_TREE[node_id]
        log_sync(
            f"🌟 **SKILL UNLOCK (Gap)**\n"
            f"👤 {player.get('name','—')} (`{uid}`)\n"
            f"🎯 مهارت: {node['name_fa']}\n"
            f"📊 مسیر: {st.PATHS[node['path']]['name_fa']}\n"
            f"💡 هزینه: {node['cost']} امتیاز",
            "SKILL"
        )

    await cb.answer(message, show_alert=not ok)
    if ok:
        path = st.SKILL_TREE[node_id]["path"]
        try:
            await cb.message.edit_text(st.path_tree_text(player, path), reply_markup=st.build_path_kb(player, path))
        except Exception:
            pass


async def cb_skill_respec(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    if not player:
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return
    path = cb.data.split(":")[1]
    ok, message = st.respec_path(player, path)
    save_player(uid, player)

    if ok:
        log_sync(
            f"🔄 **SKILL RESPEC (Gap)**\n"
            f"👤 {player.get('name','—')} (`{uid}`)\n"
            f"📊 مسیر: {st.PATHS[path]['name_fa'] if path else 'همه'}\n"
            f"💰 هزینه: {st.respec_cost(player, path):,} Zen",
            "SKILL"
        )

    await cb.answer(message, show_alert=True)
    if ok:
        try:
            await cb.message.edit_text(st.path_tree_text(player, path), reply_markup=st.build_path_kb(player, path))
        except Exception:
            pass


async def cb_skill_respec_all(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    if not player:
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return
    ok, message = st.respec_path(player, None)
    save_player(uid, player)

    if ok:
        log_sync(
            f"🔄 **SKILL RESPEC ALL (Gap)**\n"
            f"👤 {player.get('name','—')} (`{uid}`)\n"
            f"💰 هزینه: {st.respec_cost(player, None):,} Zen",
            "SKILL"
        )

    await cb.answer(message, show_alert=True)
    if ok:
        try:
            await cb.message.edit_text(st.skill_summary_text(player), reply_markup=st.build_paths_menu_kb())
        except Exception:
            pass


async def cb_skill_back_menu(cb: CallbackQuery):
    uid = cb.from_user.id
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    try:
        await cb.message.edit_text(st.skill_summary_text(player), reply_markup=st.build_paths_menu_kb())
    except Exception:
        pass
    await cb.answer()


async def cb_skill_close(cb: CallbackQuery):
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.answer()


def register_gap_skill_handlers(dp: GapDispatcher):
    dp.register_message(cmd_skills, commands=["skills"], text="مهارت‌ها")
    dp.register_callback(cb_skill_path, data_startswith="skill_path:")
    dp.register_callback(cb_skill_unlock, data_startswith="skill_unlock:")
    dp.register_callback(cb_skill_respec, data_startswith="skill_respec:")
    dp.register_callback(cb_skill_respec_all, data="skill_respec_all")
    dp.register_callback(cb_skill_back_menu, data="skill_back_menu")
    dp.register_callback(cb_skill_close, data="skill_close")
