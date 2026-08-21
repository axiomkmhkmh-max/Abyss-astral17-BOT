# ============================================================
#  ASTRAL ABYSS RPG — Skill Tree Handlers (با لاگ‌گذاری کامل)
#  UI تلگرام برای درخت مهارت (skill_tree.py = موتور/دیتا)
# ============================================================
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from database import get_player, save_player, asave_player, aget_player
from logger import log_sync
import skill_tree as st


async def cmd_skills(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    await msg.answer(st.skill_summary_text(player), reply_markup=st.build_paths_menu_kb())


async def cb_skill_path(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
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
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return
    node_id = cb.data.split(":", 1)[1]
    ok, message = st.unlock_skill(player, node_id)
    await asave_player(uid, player)
    
    if ok:
        node = st.SKILL_TREE[node_id]
        log_sync(
            f"🌟 **SKILL UNLOCK**\n"
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
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return
    path = cb.data.split(":")[1]
    ok, message = st.respec_path(player, path)
    await asave_player(uid, player)
    
    if ok:
        log_sync(
            f"🔄 **SKILL RESPEC**\n"
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
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return
    ok, message = st.respec_path(player, None)
    await asave_player(uid, player)
    
    if ok:
        log_sync(
            f"🔄 **SKILL RESPEC ALL**\n"
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
    player = await aget_player(uid)
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


def register_skill_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_skills, F.text == "مهارت‌ها")
    dp.message.register(cmd_skills, Command("skills"))
    dp.callback_query.register(cb_skill_path, F.data.startswith("skill_path:"))
    dp.callback_query.register(cb_skill_unlock, F.data.startswith("skill_unlock:"))
    dp.callback_query.register(cb_skill_respec, F.data.startswith("skill_respec:"))
    dp.callback_query.register(cb_skill_respec_all, F.data == "skill_respec_all")
    dp.callback_query.register(cb_skill_back_menu, F.data == "skill_back_menu")
    dp.callback_query.register(cb_skill_close, F.data == "skill_close")
