# ============================================================
#  ASTRAL ABYSS — Story Mode Handlers (Telegram layer) — v3
#  حالا با پازلِ واقعی: riddle (متنی)، sequence (کاوش/ترتیب)،
#  memory_check (به‌یادآوردن، با جریمه‌ی جوابِ غلط)
# ============================================================
import random, time
from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player
from quest_engine import (
    MAIN_CHAPTERS, get_node, chapter_by_num, next_chapter_for,
    SIDE_QUESTS, get_side_quest_node, clamp_resonance, resonance_label,
)
from game_data import wall_boss_stats

RIDDLE_DEFAULT_MAX_TRIES = 3


async def safe_edit_text(message, text, reply_markup=None):
    """مثلِ message.edit_text ولی اگه محتوا/دکمه‌ها دقیقاً همونیه که الان
    رو صفحه‌ست (مثلاً بازیکن دوباره تو همون نبرد باخت)، تلگرام ارور
    'message is not modified' می‌ده که قبلاً هندل نمی‌شد و کالبک رو کلاً
    می‌ترکوند (پس دکمه انگار کار نمی‌کرد چون cb.answer() هیچ‌وقت اجرا
    نمی‌شد). این تابع اون ارورِ خاص رو نادیده می‌گیره؛ بقیه‌ی ارورها
    عادی raise می‌شن."""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


# ────────────────────────────────────────────────────────────
# /story — ورودِ اصلی به خط داستانی
# ────────────────────────────────────────────────────────────
async def cmd_story(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return

    node_id = player.get("quest_node")
    if node_id:
        await _render_node(msg, player, node_id, edit=False, owner_uid=uid)
        return

    ch = next_chapter_for(player)
    if not ch:
        done = player.get("main_chapter", 0)
        if done >= 20:
            await msg.answer(
                "🎉 کل خط داستانیِ نوشته‌شده تا سطح ۲۰۰ رو تموم کردی!\n\n"
                "🌌 یه رازِ بزرگ هنوز بازه... ادامه‌ش، تو بخشِ بعدیِ Astral Abyss میاد."
            )
            return
        nxt = chapter_by_num(done + 1)
        if nxt:
            await msg.answer(
                f"🔒 فصل بعدی: **{nxt['title']}** ({nxt['map']})\n"
                f"باید به سطح {nxt['level_wall']} برسی تا باز بشه. (الان: سطح {player.get('level',1)})"
            )
        else:
            await msg.answer("📖 فعلاً همه‌ی داستانِ نوشته‌شده رو دیدی — بقیه‌ش داره نوشته می‌شه!")
        return

    if not ch.get("written"):
        await msg.answer(
            f"🔒 فصل {ch['num']} (اکتِ {ch['act']}): **{ch['title']}** ({ch['map']}) به سطح رسیدی، ولی "
            f"محتوای کاملش هنوز نوشته نشده. به‌زودی اضافه می‌شه!\n\n"
            f"📝 خلاصه: {ch.get('synopsis','—')}"
        )
        return

    player["quest_node"] = ch["entry_node"]
    save_player(uid, player)
    await _render_node(msg, player, ch["entry_node"], edit=False, owner_uid=uid)


async def cmd_chapters(msg: Message):
    """نقشه‌ی کلیِ ۲۰ فصل + پیشرفتِ فعلی."""
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    done = player.get("main_chapter", 0)
    lines = ["📖 **نقشه‌ی خط داستانی (سطح ۱ تا ۲۰۰)**\n"]
    act_names = {1: "🌱 اکتِ ۱ — کشف", 2: "🌀 اکتِ ۲ — شکاف", 3: "🌑 اکتِ ۳ — لبه‌ی بی‌نهایت"}
    cur_act = 0
    for ch in MAIN_CHAPTERS:
        if ch["act"] != cur_act:
            cur_act = ch["act"]
            lines.append(f"\n{act_names[cur_act]}")
        mark = "✅" if ch["num"] <= done else ("▶️" if ch["num"] == done + 1 else "🔒")
        lines.append(f"{mark} فصل {ch['num']} (Lv{ch['level_wall']}): {ch['title']}")
    await msg.answer("\n".join(lines))


# ────────────────────────────────────────────────────────────
# رندر یه گره
# ────────────────────────────────────────────────────────────
async def _render_node(target, player: dict, node_id: str, edit: bool, owner_uid: int):
    node = get_node(node_id)
    if not node:
        text = "❌ این بخش از داستان هنوز نوشته نشده. (به زودی...)"
        kb = None
    else:
        text, kb = _build_node_view(node, player, owner_uid)

    if edit:
        await safe_edit_text(target.message, text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


def _build_node_view(node: dict, player: dict, owner_uid: int) -> tuple[str, InlineKeyboardMarkup | None]:
    ntype = node["type"]

    if ntype in ("narration", "dialogue"):
        prefix = f"**{node['speaker']}:**\n\n" if ntype == "dialogue" else ""
        text = prefix + node["text"]
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="▶️ ادامه", callback_data=f"qst_next:{owner_uid}:{node['next']}", style=ButtonStyle.PRIMARY)
        ]])
        return text, kb

    if ntype == "choice":
        text = node["text"]
        buttons = []
        for i, opt in enumerate(node["options"]):
            if opt.get("requires_flag") and not player.get("quest_flags", {}).get(opt["requires_flag"]):
                continue
            buttons.append([InlineKeyboardButton(text=opt["text"], callback_data=f"qst_choice:{owner_uid}:{i}", style=ButtonStyle.PRIMARY)])
        return text, InlineKeyboardMarkup(inline_keyboard=buttons)

    if ntype == "memory_check":
        text = "🧠 **آزمونِ حافظه**\n\n" + node["text"]
        buttons = [
            [InlineKeyboardButton(text=opt["text"], callback_data=f"qst_mem:{owner_uid}:{i}", style=ButtonStyle.PRIMARY)]
            for i, opt in enumerate(node["options"])
        ]
        return text, InlineKeyboardMarkup(inline_keyboard=buttons)

    if ntype == "riddle":
        tries = player.get("quest_riddle_tries", 0)
        max_tries = node.get("max_tries", RIDDLE_DEFAULT_MAX_TRIES)
        speaker = node.get("speaker", "🧩 معما")
        text = f"**{speaker}:**\n\n{node['text']}\n\n💬 {node.get('text_extra','')}".strip()
        if tries > 0:
            text += f"\n\n❌ {tries}/{max_tries} تلاشِ اشتباه."
        if tries >= 1 and node.get("hint"):
            text += f"\n{node['hint']}"
        text += "\n\n✍️ جوابت رو مستقیم تو چت تایپ کن و بفرست."
        return text, None  # پاسخ با پیامِ متنی میاد، نه دکمه

    if ntype == "sequence":
        text = node["text"] + "\n\n"
        progress = player.get("quest_seq_progress", [])
        buttons = []
        for clue in node["clues"]:
            done_mark = "✅ " if clue["id"] in progress else ""
            buttons.append([InlineKeyboardButton(
                text=f"{done_mark}{clue['label']}", callback_data=f"qst_clue:{owner_uid}:{clue['id']}"
            , style=ButtonStyle.PRIMARY)])
        if progress:
            text += "📋 پیشرفت: " + " → ".join(progress) + "\n"
        return text, InlineKeyboardMarkup(inline_keyboard=buttons)

    if ntype == "combat":
        text = node["text"] + "\n\n⚔️ آماده‌ای؟"
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⚔️ شروعِ نبرد", callback_data=f"qst_fight:{owner_uid}", style=ButtonStyle.DANGER)
        ]])
        return text, kb

    if ntype == "chapter_end":
        resonance = player.get("resonance", 0)
        text = node["text"].format(resonance=resonance, resonance_label=resonance_label(resonance))
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ باشه", callback_data=f"qst_end_chapter:{owner_uid}", style=ButtonStyle.SUCCESS)
        ]])
        return text, kb

    return "❌ نوعِ گره‌ی ناشناخته.", None


def _goto(player: dict, node_id: str | None):
    player["quest_node"] = node_id
    player["quest_riddle_tries"] = 0
    player["quest_seq_progress"] = []
    if node_id:
        player.setdefault("quest_fight_losses", {}).pop(node_id, None)


# ────────────────────────────────────────────────────────────
# دکمه‌ی «ادامه»
# ────────────────────────────────────────────────────────────
async def cb_quest_next(cb: CallbackQuery):
    _, owner_s, next_id = cb.data.split(":", 2)
    uid = cb.from_user.id
    if int(owner_s) != uid:
        await cb.answer("❌ این پیام برای تو نیست — برای شروع/ادامه‌ی داستانِ خودت /story بزن.", show_alert=True)
        return
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    _goto(player, next_id)
    save_player(uid, player)
    await _render_node(cb, player, next_id, edit=True, owner_uid=uid)
    await cb.answer()


# ────────────────────────────────────────────────────────────
# choice — شاخه‌بندیِ آزاد (بدونِ جوابِ غلط)
# ────────────────────────────────────────────────────────────
async def cb_quest_choice(cb: CallbackQuery):
    _, owner_s, idx_s = cb.data.split(":", 2)
    uid = cb.from_user.id
    if int(owner_s) != uid:
        await cb.answer("❌ این پیام برای تو نیست — برای شروع/ادامه‌ی داستانِ خودت /story بزن.", show_alert=True)
        return
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    node = get_node(player.get("quest_node", ""))
    if not node or node["type"] != "choice":
        await cb.answer("❌ این انتخاب دیگه معتبر نیست.", show_alert=True)
        return

    try:
        idx = int(idx_s)
        opt = node["options"][idx]
    except Exception:
        await cb.answer("❌ خطا!", show_alert=True)
        return

    if opt.get("set_flag"):
        player.setdefault("quest_flags", {})[opt["set_flag"]] = True
    katana_line = ""
    if opt.get("resonance"):
        old_res = player.get("resonance", 0)
        new_res = clamp_resonance(old_res + opt["resonance"])
        player["resonance"] = new_res
        from katana_resonance import katana_resonance_reaction
        katana_line = katana_resonance_reaction(player, old_res, new_res)

    _goto(player, opt["next"])
    save_player(uid, player)
    await _render_node(cb, player, opt["next"], edit=True, owner_uid=uid)
    await cb.answer(f"💬 {katana_line}" if katana_line else "")


# ────────────────────────────────────────────────────────────
# memory_check — گزینه‌ی درست/غلط با جریمه
# ────────────────────────────────────────────────────────────
async def cb_quest_memcheck(cb: CallbackQuery):
    _, owner_s, idx_s = cb.data.split(":", 2)
    uid = cb.from_user.id
    if int(owner_s) != uid:
        await cb.answer("❌ این پیام برای تو نیست — برای شروع/ادامه‌ی داستانِ خودت /story بزن.", show_alert=True)
        return
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    node = get_node(player.get("quest_node", ""))
    if not node or node["type"] != "memory_check":
        await cb.answer("❌ این آزمون دیگه معتبر نیست.", show_alert=True)
        return

    try:
        idx = int(idx_s)
        opt = node["options"][idx]
    except Exception:
        await cb.answer("❌ خطا!", show_alert=True)
        return

    if opt.get("correct"):
        _goto(player, opt["next"])
        save_player(uid, player)
        await _render_node(cb, player, opt["next"], edit=True, owner_uid=uid)
        await cb.answer("✅ درست بود!")
        return

    # جوابِ غلط → جریمه + رفتن به on_fail
    penalty = node.get("fail_penalty", {})
    penalty_lines = []
    katana_line = ""
    if "resonance" in penalty:
        old_res = player.get("resonance", 0)
        new_res = clamp_resonance(old_res + penalty["resonance"])
        player["resonance"] = new_res
        penalty_lines.append(f"Resonance {penalty['resonance']:+d}")
        from katana_resonance import katana_resonance_reaction
        katana_line = katana_resonance_reaction(player, old_res, new_res)
    if "hp" in penalty:
        player["hp"] = max(1, player.get("hp", 100) + penalty["hp"])
        penalty_lines.append(f"HP {penalty['hp']:+d}")
    if "zen" in penalty:
        player["zen"] = max(0, player.get("zen", 0) + penalty["zen"])
        penalty_lines.append(f"Zen {penalty['zen']:+d}")

    fail_node = node.get("on_fail")
    penalty_txt = (" | " + ", ".join(penalty_lines)) if penalty_lines else ""
    katana_txt = f"\n💬 {katana_line}" if katana_line else ""
    await cb.answer(f"❌ اشتباه بود!{penalty_txt}{katana_txt}", show_alert=True)
    if fail_node:
        # باگ‌فیکس: قبلاً حتی وقتی on_fail خالی بود، _goto(player, None) صدا
        # زده می‌شد که quest_node رو کامل خالی می‌کرد — یعنی بازیکن بی‌صدا از
        # وسطِ داستان بیرون می‌افتاد و /story بعدی می‌رفت سراغِ فصلِ بعدی،
        # انگار این بخش هیچ‌وقت وجود نداشته. حالا فقط وقتی fail_node واقعی
        # داریم quest_node رو عوض می‌کنیم؛ وگرنه همون‌جا می‌مونیم.
        _goto(player, fail_node)
        save_player(uid, player)
        await _render_node(cb, player, fail_node, edit=True, owner_uid=uid)
    else:
        save_player(uid, player)


# ────────────────────────────────────────────────────────────
# riddle — پاسخِ متنی (message handler، نه callback)
# ────────────────────────────────────────────────────────────
def _normalize(s: str) -> str:
    return "".join(s.strip().lower().split())

async def msg_quest_riddle_answer(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player or not player.get("quest_node"):
        return  # نه تو داستانه، نه ربطی به این هندلر داره

    node = get_node(player["quest_node"])
    if not node or node["type"] != "riddle":
        return  # اینجا فعلاً منتظرِ ریدل نیستیم؛ بذار پیام به هندلرِ بعدی برسه

    answer = _normalize(msg.text or "")
    accepted = [_normalize(a) for a in node.get("accepted_answers", [])]
    max_tries = node.get("max_tries", RIDDLE_DEFAULT_MAX_TRIES)

    if answer in accepted:
        correct_node = node["on_correct"]
        _goto(player, correct_node)
        save_player(uid, player)
        await msg.answer("✅ **درسته!**")
        await _render_node(msg, player, correct_node, edit=False, owner_uid=uid)
        return

    tries = player.get("quest_riddle_tries", 0) + 1
    player["quest_riddle_tries"] = tries

    if tries >= max_tries:
        fail_node = node.get("on_fail")
        _goto(player, fail_node)
        save_player(uid, player)
        await msg.answer(f"❌ جوابت درست نبود و تلاش‌هات تموم شد ({max_tries}/{max_tries}).")
        if fail_node:
            await _render_node(msg, player, fail_node, edit=False, owner_uid=uid)
        return

    save_player(uid, player)
    text, _ = _build_node_view(node, player, uid)
    await msg.answer(f"❌ جوابِ درستی نبود. دوباره امتحان کن!\n\n{text}")


# ────────────────────────────────────────────────────────────
# sequence — کاوش/ترتیب
# ────────────────────────────────────────────────────────────
async def cb_quest_clue(cb: CallbackQuery):
    _, owner_s, clue_id = cb.data.split(":", 2)
    uid = cb.from_user.id
    if int(owner_s) != uid:
        await cb.answer("❌ این پیام برای تو نیست — برای شروع/ادامه‌ی داستانِ خودت /story بزن.", show_alert=True)
        return
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    node = get_node(player.get("quest_node", ""))
    if not node or node["type"] != "sequence":
        await cb.answer("❌ این بخش دیگه معتبر نیست.", show_alert=True)
        return

    clue = next((c for c in node["clues"] if c["id"] == clue_id), None)
    if not clue:
        await cb.answer("❌ خطا!", show_alert=True)
        return

    progress = player.get("quest_seq_progress", [])
    if clue_id in progress:
        await cb.answer(f"ℹ️ {clue['text']}", show_alert=True)
        return

    required = node.get("required_order")
    if required:
        expected = required[len(progress)]
        if clue_id != expected:
            player["quest_seq_progress"] = []
            save_player(uid, player)
            await cb.answer(node.get("wrong_order_msg", "🤔 ترتیب اشتباهه — از اول شروع کن."), show_alert=True)
            await _render_node(cb, player, player["quest_node"], edit=True, owner_uid=uid)
            return

    progress.append(clue_id)
    player["quest_seq_progress"] = progress
    save_player(uid, player)
    await cb.answer(f"🔎 {clue['text']}", show_alert=True)

    if len(progress) >= len(node["clues"]):
        complete_node = node["on_complete"]
        _goto(player, complete_node)
        save_player(uid, player)
        await _render_node(cb, player, complete_node, edit=True, owner_uid=uid)
    else:
        await _render_node(cb, player, player["quest_node"], edit=True, owner_uid=uid)


# ────────────────────────────────────────────────────────────
# نبردِ داستانی
# ────────────────────────────────────────────────────────────
async def cb_quest_fight(cb: CallbackQuery):
    owner_s = cb.data.split(":", 1)[1]
    uid = cb.from_user.id
    if int(owner_s) != uid:
        await cb.answer("❌ این پیام برای تو نیست — برای شروع/ادامه‌ی داستانِ خودت /story بزن.", show_alert=True)
        return
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    node = get_node(player.get("quest_node", ""))
    if not node or node["type"] != "combat":
        await cb.answer("❌ این نبرد دیگه معتبر نیست.", show_alert=True)
        return

    enemy_cfg = node["enemy"]
    if enemy_cfg.get("use_wall_boss"):
        wb = wall_boss_stats(enemy_cfg["wall_level"])
        enemy_hp, enemy_dmg, enemy_name = wb["hp"], wb["dmg"], wb["name"]
    else:
        enemy_hp, enemy_dmg, enemy_name = enemy_cfg["hp"], enemy_cfg["dmg"], enemy_cfg["name"]

    from characters import ALL_CHARACTERS
    char_data = ALL_CHARACTERS.get(player.get("character"), {})
    p_dmg = max(5, int(char_data.get("base_dmg", 10) + player.get("level", 1) * 1.5))
    p_hp  = player.get("hp", player.get("max_hp", 100))

    # ── باگ‌فیکس: مکانیزمِ «دلجویی» ────────────────────────────
    # قبلاً اگه بازیکن می‌باخت، quest_node عوض نمی‌شد و enemy هم هر بار
    # دقیقاً به همون قدرتِ اول برمی‌گشت — یعنی اگه نبرد از اول نامتعادل
    # بود (مثلِ ch1_grove_combat که تقریباً هم‌قدرتِ باسِ همون فصل بود)
    # بازیکن تا ابد تو یه لوپِ باخت گیر می‌کرد. حالا هر باختِ متوالی رو
    # می‌شماریم و کمی به بازیکن کمک می‌کنیم، و بعد از چند بار، تضمین
    # می‌کنیم که پیش بره — دقیقاً مثلِ الگویی که riddle/memory_check
    # با max_tries و on_fail از قبل استفاده می‌کنن.
    loss_streak_map = player.setdefault("quest_fight_losses", {})
    loss_streak = loss_streak_map.get(player["quest_node"], 0)
    comeback_mult = min(1.0 + 0.2 * loss_streak, 2.0)   # تا ۲ برابر دمیج بعدِ باخت‌های پیاپی
    p_dmg = int(p_dmg * comeback_mult)
    guaranteed_win = loss_streak >= 4                    # بعد از ۴ باختِ پیاپی، دیگه شکست ممکن نیست

    rounds = 0
    while enemy_hp > 0 and p_hp > 0 and rounds < 300:
        enemy_hp -= p_dmg * random.uniform(0.8, 1.2)
        if enemy_hp <= 0:
            break
        p_hp -= enemy_dmg * random.uniform(0.6, 1.0)
        rounds += 1

    if p_hp > 0 or guaranteed_win:
        player["hp"] = max(1, int(p_hp))
        loss_streak_map.pop(player["quest_node"], None)
        if p_hp <= 0 and guaranteed_win:
            lines = [
                node.get("win_text", "پیروز شدی!")
                + "\n\n🗡️ روحِ کاتانا: «...به‌سختی بود، ولی بردی. گاهی همینم کافیه.»"
            ]
        else:
            lines = [node.get("win_text", "پیروز شدی!")]
        if node.get("reward_item"):
            STORY_ITEM_NAMES = {
                "root_of_memory": ("🌿 ریشه‌ی خاطره", "🌿"),
                "mirror_shard": ("🪞 تکه‌ی آینه‌ی کسارین", "🪞"),
                "admiral_compass": ("⚓ قطب‌نمای دریاسالار رنا", "⚓"),
            }
            item_id = node["reward_item"]
            item_name, item_emoji = STORY_ITEM_NAMES.get(item_id, ("🎁 یادگارِ داستانی", "🎁"))
            player.setdefault("inventory", []).append(
                {"name": item_name, "emoji": item_emoji, "id": item_id}
            )
            lines.append(f"🎁 آیتمِ داستانی گرفتی: {item_name}")
        if node.get("reward_zen_bonus"):
            bonus = 500
            player["zen"] = player.get("zen", 0) + bonus
            lines.append(f"💰 +{bonus} Zen غنیمت")

        if node.get("is_chapter_boss") and enemy_cfg.get("use_wall_boss"):
            wl = enemy_cfg["wall_level"]
            if wl not in player.get("walls_cleared", []):
                player.setdefault("walls_cleared", []).append(wl)
                lines.append(f"🚧 دیوار سختیِ سطح {wl} هم شکسته شد!")

        _goto(player, node["on_win"])
        save_player(uid, player)
        await safe_edit_text(
            cb.message,
            "\n\n".join(lines),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="▶️ ادامه", callback_data=f"qst_next:{uid}:{node['on_win']}", style=ButtonStyle.PRIMARY)
            ]])
        )
    else:
        new_streak = loss_streak + 1
        loss_streak_map[player["quest_node"]] = new_streak
        # نبردهای معمولی (غیرِ باس) دیگه بازیکن رو تا ¼ HP خالی نمی‌کنن —
        # چون این حالت باعث می‌شد تلاشِ بعدی حتی سخت‌تر از قبل بشه (اسپیرالِ
        # شکست). باس‌فایت‌ها همچنان جریمه‌ی واقعی دارن.
        if node.get("is_chapter_boss"):
            player["hp"] = max(1, player.get("max_hp", 100) // 4)
        else:
            player["hp"] = max(1, int(player.get("hp", player.get("max_hp", 100)) * 0.5))
        save_player(uid, player)
        remaining = max(0, 4 - new_streak)
        hint = (
            f"\n\n💪 تیغه‌ات داره یاد می‌گیره — تلاشِ بعدی قوی‌تری می‌کنی."
            if remaining else
            "\n\n🗡️ روحِ کاتانا: «بسه... این‌بار با هم می‌بریمش.»"
        )
        await safe_edit_text(
            cb.message,
            node.get("lose_text", "شکست خوردی...") + hint,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⚔️ دوباره امتحان کن", callback_data=f"qst_fight:{uid}", style=ButtonStyle.DANGER)
            ]])
        )
    await cb.answer()


# ────────────────────────────────────────────────────────────
# پایانِ فصل
# ────────────────────────────────────────────────────────────
async def cb_quest_end_chapter(cb: CallbackQuery):
    owner_s = cb.data.split(":", 1)[1]
    uid = cb.from_user.id
    if int(owner_s) != uid:
        await cb.answer("❌ این پیام برای تو نیست — برای شروع/ادامه‌ی داستانِ خودت /story بزن.", show_alert=True)
        return
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    node = get_node(player.get("quest_node", ""))
    if not node or node["type"] != "chapter_end":
        await cb.answer("❌", show_alert=True)
        return

    ch_num = node.get("next_chapter", (player.get("main_chapter", 0) + 1))
    player["main_chapter"] = max(player.get("main_chapter", 0), ch_num - 1)
    _goto(player, None)
    save_player(uid, player)

    await safe_edit_text(cb.message, "📖 فصل تموم شد! هروقت آماده بودی، `/story` رو بزن تا ادامه بدی.")
    await cb.answer()


# ────────────────────────────────────────────────────────────
# ماموریت‌های فرعی (بدون تغییر نسبت به قبل)
# ────────────────────────────────────────────────────────────
async def cmd_sidequests(msg: Message):
    uid = msg.from_user.id
    player = get_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return

    current_map = player.get("map", "Verdant Vale")
    available = [
        (qid, sq) for qid, sq in SIDE_QUESTS.items()
        if sq["map"] == current_map
        and qid not in player.get("side_quests_done", [])
        and player.get("level", 1) >= sq["level_req"]
    ]
    if not available:
        await msg.answer("📭 تو این منطقه ماموریتِ فرعیِ جدیدی نیست.")
        return

    buttons = []
    for qid, sq in available:
        active = player.get("side_quests_active", {}).get(qid)
        label = f"{'▶️' if active else '🆕'} {sq['title']} ({sq['giver']})"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"sq_open:{uid}:{qid}", style=ButtonStyle.PRIMARY)])
    await msg.answer(f"📜 **ماموریت‌های فرعیِ {current_map}**", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


async def cb_sq_open(cb: CallbackQuery):
    owner_s, qid = cb.data.split(":", 2)[1:]
    uid = cb.from_user.id
    if int(owner_s) != uid:
        await cb.answer("❌ این پیام برای تو نیست — با /sidequests ماموریت‌های خودت رو ببین.", show_alert=True)
        return
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    sq = SIDE_QUESTS.get(qid)
    if not sq:
        await cb.answer("❌ خطا!", show_alert=True)
        return
    node_id = player.get("side_quests_active", {}).get(qid, sq["entry_node"])
    player.setdefault("side_quests_active", {})[qid] = node_id
    save_player(uid, player)
    await _render_sq_node(cb, player, qid, node_id, owner_uid=uid)
    await cb.answer()


def _build_sq_view(node: dict, player: dict, qid: str, owner_uid: int) -> tuple[str, InlineKeyboardMarkup | None]:
    ntype = node["type"]
    if ntype == "dialogue":
        text = f"**{node['speaker']}:**\n\n{node['text']}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="▶️ ادامه", callback_data=f"sq_next:{owner_uid}:{qid}:{node['next']}", style=ButtonStyle.PRIMARY)
        ]])
        return text, kb
    if ntype == "choice":
        buttons = [
            [InlineKeyboardButton(text=opt["text"], callback_data=f"sq_choice:{owner_uid}:{qid}:{i}", style=ButtonStyle.PRIMARY)]
            for i, opt in enumerate(node["options"])
        ]
        return node["text"], InlineKeyboardMarkup(inline_keyboard=buttons)
    if ntype == "reward":
        if node.get("requires_kill"):
            req = node["requires_kill"]
            done = player.get("kill_log", {}).get(req["enemy"], 0)
            if done < req["count"]:
                text = f"⏳ هنوز کافی نیست: {done}/{req['count']} {req['enemy']} کشتی."
                return text, InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🔄 چک کردنِ پیشرفت", callback_data=f"sq_check:{owner_uid}:{qid}", style=ButtonStyle.PRIMARY)
                ]])
        return node["text"], None
    return "❌", None


async def _render_sq_node(cb: CallbackQuery, player: dict, qid: str, node_id: str, owner_uid: int):
    node = get_side_quest_node(qid, node_id)
    if not node:
        await safe_edit_text(cb.message, "❌ این بخش از ماموریت هنوز نوشته نشده.")
        return
    text, kb = _build_sq_view(node, player, qid, owner_uid)

    if node["type"] == "reward" and qid not in player.get("side_quests_done", []):
        req = node.get("requires_kill")
        if req:
            done = player.get("kill_log", {}).get(req["enemy"], 0)
            if done < req["count"]:
                await safe_edit_text(cb.message, text, reply_markup=kb)
                return
        rewards = node.get("rewards", {})
        player["zen"] = player.get("zen", 0) + rewards.get("zen", 0)
        player["xp"]  = player.get("xp", 0) + rewards.get("xp", 0)
        player.setdefault("side_quests_done", []).append(qid)
        player.get("side_quests_active", {}).pop(qid, None)
        save_player(cb.from_user.id, player)

    await safe_edit_text(cb.message, text, reply_markup=kb)


async def cb_sq_next(cb: CallbackQuery):
    _, owner_s, qid, node_id = cb.data.split(":", 3)
    uid = cb.from_user.id
    if int(owner_s) != uid:
        await cb.answer("❌ این پیام برای تو نیست — با /sidequests ماموریت‌های خودت رو ببین.", show_alert=True)
        return
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    player.setdefault("side_quests_active", {})[qid] = node_id
    save_player(uid, player)
    await _render_sq_node(cb, player, qid, node_id, owner_uid=uid)
    await cb.answer()


async def cb_sq_check(cb: CallbackQuery):
    _, owner_s, qid = cb.data.split(":", 2)
    uid = cb.from_user.id
    if int(owner_s) != uid:
        await cb.answer("❌ این پیام برای تو نیست — با /sidequests ماموریت‌های خودت رو ببین.", show_alert=True)
        return
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    node_id = player.get("side_quests_active", {}).get(qid)
    await _render_sq_node(cb, player, qid, node_id, owner_uid=uid)
    await cb.answer()


async def cb_sq_choice(cb: CallbackQuery):
    _, owner_s, qid, idx_s = cb.data.split(":", 3)
    uid = cb.from_user.id
    if int(owner_s) != uid:
        await cb.answer("❌ این پیام برای تو نیست — با /sidequests ماموریت‌های خودت رو ببین.", show_alert=True)
        return
    player = get_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    node_id = player.get("side_quests_active", {}).get(qid)
    node = get_side_quest_node(qid, node_id)
    if not node or node["type"] != "choice":
        await cb.answer("❌", show_alert=True)
        return
    opt = node["options"][int(idx_s)]
    if opt.get("resonance"):
        player["resonance"] = clamp_resonance(player.get("resonance", 0) + opt["resonance"])
    if opt.get("set_flag"):
        player.setdefault("quest_flags", {})[opt["set_flag"]] = True
    player["side_quests_active"][qid] = opt["next"]
    save_player(uid, player)
    await _render_sq_node(cb, player, qid, opt["next"], owner_uid=uid)
    await cb.answer()


# ────────────────────────────────────────────────────────────
# Register
# ────────────────────────────────────────────────────────────
def register_quest_handlers(dp):
    dp.message.register(cmd_story, Command("story"))
    dp.message.register(cmd_chapters, Command("chapters"))
    dp.message.register(cmd_sidequests, Command("sidequests"))

    dp.callback_query.register(cb_quest_next, F.data.startswith("qst_next:"))
    dp.callback_query.register(cb_quest_choice, F.data.startswith("qst_choice:"))
    dp.callback_query.register(cb_quest_memcheck, F.data.startswith("qst_mem:"))
    dp.callback_query.register(cb_quest_clue, F.data.startswith("qst_clue:"))
    dp.callback_query.register(cb_quest_fight, F.data.startswith("qst_fight:"))
    dp.callback_query.register(cb_quest_end_chapter, F.data.startswith("qst_end_chapter:"))

    dp.callback_query.register(cb_sq_open, F.data.startswith("sq_open:"))
    dp.callback_query.register(cb_sq_next, F.data.startswith("sq_next:"))
    dp.callback_query.register(cb_sq_check, F.data.startswith("sq_check:"))
    dp.callback_query.register(cb_sq_choice, F.data.startswith("sq_choice:"))

    # ─── باگ‌فیکسِ حیاتی ────────────────────────────────────────
    # این هندلر قبلاً بدونِ هیچ فیلتری ثبت شده بود، یعنی هر پیامی
    # (از جمله هر دستور ادمین/کاتانا/رید/مهارت/گیلدی که بعد از این
    # تو bot.py رجیستر می‌شد) اول می‌رسید اینجا؛ حتی وقتی ریدل نبود
    # و تابع فقط `return` می‌زد، aiogram پیام رو «مصرف‌شده» حساب
    # می‌کرد و اجازه نمی‌داد به هیچ هندلرِ بعدی برسه — یعنی عملاً
    # هرچی که رجیستریش بعد از این خط بود (پنل ادمین، کاتانا،
    # progression، رید، مهارت‌ها، گیلد) هیچ‌وقت پیام دریافت نمی‌کرد.
    # فیکس: یه فیلترِ async که فقط وقتی پلیر واقعاً وسطِ یه ریدله
    # True برمی‌گردونه، تا در غیرِاین‌صورت پیام آزادانه به هندلرهای
    # بعدی برسه.
    async def _is_awaiting_riddle(msg: Message) -> bool:
        player = get_player(msg.from_user.id)
        if not player or not player.get("quest_node"):
            return False
        node = get_node(player["quest_node"])
        return bool(node and node.get("type") == "riddle")

    dp.message.register(msg_quest_riddle_answer, _is_awaiting_riddle)
