# ============================================================
#  ASTRAL ABYSS RPG — Combat v3 (Katana Personality/Dimensions/Skills layer)
#  (combat_v3.py)  —  فاز ۲ / بخش ب
# ============================================================
#
# این فایل combat.py (calc_combat) رو دست‌نخورده نگه می‌داره و فقط
# «روش‌ لایه‌گذاری»یی که خودِ combat.py قبلاً برای combat_engine.apply_combat_v2
# استفاده می‌کرد رو برای سیستم جدید کاتانا هم تکرار می‌کنه: نتیجه‌ی calc_combat
# قدیمی رو می‌گیره و روش، بونوس‌های شخصیت/ابعاد/مهارت‌ها رو post-hoc اعمال می‌کنه.
#
# استفاده: به‌جای `from combat import calc_combat`، تو هندلر جدید از
# `from combat_v3 import calc_combat_v3` استفاده کن. اگه بازیکن کاراکتر/کاتانا
# نداشته باشه، دقیقاً همون رفتار قدیمی combat.py رو برمی‌گردونه (no-op).
# ============================================================

import random
from combat import calc_combat  # فایل قدیمی، دست‌نخورده

import katana_personality as kp
import katana_dimensions as kd
import katana_skills as ks


def calc_combat_v3(player: dict, enemy: dict, attack_type: str) -> dict:
    result = calc_combat(player, enemy, attack_type)

    character_name = player.get("character", "")
    if not character_name:
        return result

    logs = result.setdefault("logs", [])
    took_dmg_last_turn = bool(result.get("counter"))
    target_is_boss = bool(enemy.get("is_boss") or enemy.get("tier") == "boss")

    pers = kp.calc_personality_total_bonus(player, character_name, took_dmg_last_turn, target_is_boss)
    dims = kd.calc_dimensions_bonus(player, character_name)
    skb = ks.calc_skills_passive_bonus(player, character_name)

    # ── ۱) نافرمانی (وفاداری پایین) — قبل از هر بونوس دیگه چک می‌شه ──
    disobeyed = False
    if result["dmg"] > 0 and random.random() < pers.get("disobey_chance", 0.0):
        result["dmg"] = int(result["dmg"] * 0.5)
        result["crit"] = False
        disobeyed = True
        logs.append("😤 **کاتانا امروز حرف‌شنوی نداره...** ضربه‌ت ناقص خورد!")

    if result["dmg"] > 0 and not disobeyed:
        # ── ۲) ضرایب ثابت دمیج (تیپ شخصیتی + مهارت غیرفعال + خلق‌وخوی «غمگین») ──
        dmg_mult_flat = 1.0 + pers.get("dmg_mult_flat", 0.0) + skb.get("dmg_mult_flat", 0.0)
        all_mult = 1.0 + pers.get("all_mult", 0.0)
        result["dmg"] = int(result["dmg"] * dmg_mult_flat * all_mult)

        # ── ۳) کریتِ اضافه (اگه از قبل کریت نخورده) ──
        extra_crit = pers.get("crit", 0.0) + dims.get("crit", 0.0) + skb.get("crit", 0.0)
        if not result["crit"] and extra_crit > 0 and random.random() < extra_crit:
            result["dmg"] = int(result["dmg"] * 2.0)
            result["crit"] = True
            logs.append("💥 **کریتِ اضافه‌ی روحِ کاتانا!**")

        # ── ۴) ضربه‌ی غافلگیرکننده (خلق‌وخوی «مرموز») ──
        if pers.get("surprise_chance", 0.0) > 0 and random.random() < pers["surprise_chance"]:
            mult = pers.get("surprise_mult", 1.0)
            result["dmg"] = int(result["dmg"] * mult)
            logs.append(f"🌫️ **ضربه‌ی غافلگیرکننده!** (×{mult})")

        # ── ۵) نوسان دمیج (تیپ «دیوانه») ──
        var = pers.get("dmg_variance", 0.0)
        if var > 0:
            factor = 1 + random.uniform(-var, var)
            result["dmg"] = max(0, int(result["dmg"] * factor))

        # ── ۶) فعال‌سازی خودکار مهارت فعال ──
        proc_chance = dims.get("skill_chance_add", 0.0) + pers.get("special_chance_add", 0.0) * 0.3
        proc = ks.maybe_trigger_active_skill(player, character_name, extra_chance=proc_chance,
                                              speed_cd_reduction=dims.get("cooldown_reduction_seconds", 0.0))
        if proc:
            logs.append(f"{proc['emoji']} **{proc['name']} فعال شد!**")
            eff = proc["effect"]
            kind = eff.get("kind")
            if kind == "aoe":
                bonus_dmg = int(result["dmg"] * eff.get("value", 1.0))
                result["dmg"] += bonus_dmg
                result["katana_aoe_dmg"] = bonus_dmg
            elif kind == "defense_ignore":
                result["dmg"] = int(result["dmg"] * (1 + eff.get("value", 0.5)))
            elif kind == "double_hit":
                result["dmg"] = int(result["dmg"] * 2)
            elif kind == "lifesteal_boost":
                extra_heal = int(result["dmg"] * eff.get("value", 0.3))
                result["lifesteal_heal"] = result.get("lifesteal_heal", 0) + extra_heal
            elif kind == "elem_boost" and result.get("elem_bonus"):
                result["dmg"] = int(result["dmg"] * (1 + eff.get("value", 0.5)))
            elif kind == "dodge_next":
                result["shadow_step_active"] = True  # هندلر باید حمله‌ی بعدیِ دشمن رو کامل miss کنه

    # ── ۷) جاخالی از ضدحمله‌ی دشمن (تیپ «مرموز» + مهارت «شنل سایه») ──
    total_dodge = pers.get("dodge", 0.0) + skb.get("dodge", 0.0)
    if result.get("counter") and total_dodge > 0 and random.random() < total_dodge:
        result["counter"] = False
        result["enemy_dmg"] = 0
        logs.append("🌀 کاتانا جاخالی داد؛ ضدحمله‌ی دشمن بی‌اثر شد!")

    # ── ۸) لایف‌استیل اضافه (تیپ + بعد روح + مهارت غیرفعال) ──
    extra_lifesteal = pers.get("lifesteal", 0.0) + dims.get("lifesteal", 0.0) + skb.get("lifesteal", 0.0)
    if extra_lifesteal > 0 and result["dmg"] > 0:
        heal = int(result["dmg"] * extra_lifesteal)
        if heal > 0:
            result["lifesteal_heal"] = result.get("lifesteal_heal", 0) + heal
            logs.append(f"🩸 **بونوس روحیِ کاتانا:** +{heal} HP")

    return result


def on_kill(player: dict, enemy: dict) -> list[str]:
    """بعد از کشتنِ دشمن صدا زده بشه. وفاداری/خاطرات/HP خون‌خواهی رو آپدیت می‌کنه
    و پیام‌های نمایشی رو برمی‌گردونه (هندلر باید اضافه‌شون کنه به لاگِ نبرد)."""
    character_name = player.get("character", "")
    if not character_name:
        return []
    msgs = []

    enemy_tier = "boss" if (enemy.get("is_boss") or enemy.get("tier") == "boss") else \
                 ("elite" if enemy.get("tier") == "elite" else "normal")

    pentry = kp.get_personality(player, character_name)
    gain = kp.register_kill(pentry, enemy_tier)
    mem = kp.register_kill_for_memory(pentry)
    if mem:
        msgs.append(f"🧠 **خاطره‌ی جدید باز شد!** ({mem['count']}/{kp.MEMORY_MAX}) — {mem['bonus']['label']}")

    if enemy_tier == "boss":
        if kp.unlock_special_memory(pentry, "boss_kill"):
            msgs.append("🐲 **خاطره‌ی ویژه:** نبرد با یک باس بزرگ — پاداش دائمی گرفتی!")

    skb = ks.calc_skills_passive_bonus(player, character_name)
    if skb.get("hp_on_kill_pct", 0.0) > 0:
        max_hp = player.get("max_hp", 100)
        heal = int(max_hp * skb["hp_on_kill_pct"])
        if heal > 0:
            player["hp"] = min(max_hp, player.get("hp", max_hp) + heal)
            msgs.append(f"💉 **خون‌خواهی:** +{heal} HP")

    return msgs


def on_death(player: dict) -> dict:
    """موقع رسیدن HP به ۰ صدا زده بشه، قبل از قطعی‌کردن مرگ.
    اول چک می‌کنه ققنوس فعاله؛ اگه بود جلوی مرگ رو می‌گیره."""
    character_name = player.get("character", "")
    if not character_name:
        return {"revived": False, "messages": []}

    revive = ks.try_phoenix_rebirth(player, character_name)
    if revive:
        player["hp"] = revive["revive_hp"]
        return {"revived": True,
                "messages": [f"🐦‍🔥 **{revive['name']}!** کاتانا نذاشت بمیری — {revive['revive_hp']} HP برگشت!"]}

    pentry = kp.get_personality(player, character_name)
    stage = player.get("katana_awakening", 0)
    loss = kp.register_death(pentry, stage)
    return {"revived": False, "messages": [f"⚰️ کاتانا با مرگت ناراحت شد. وفاداری {loss} کاهش یافت."]}


def start_new_battle(player: dict):
    """در ابتدای هر نبردِ جدید (وقتی current_fight ست می‌شه) صدا زده بشه."""
    character_name = player.get("character", "")
    if character_name:
        ks.reset_battle_flags(player, character_name)
