# Stage 3 — Class Active-Ability Systems

## Critical bug fix
- `combat.py`: `kcore` was only defined inside the `is_adventurer` branch but
  read unconditionally later (Legendary/Mythic katana tier check). Every
  attack by a Wizard, Merchant, or Healer crashed with `NameError`. Fixed by
  giving `kcore` a neutral default before the branch.

## New files
- `class_abilities.py` — pure game logic for all 4 active systems (no aiogram
  dependency): lazy resource regen (mana/stamina/faith), wizard spell synergy
  / mana shield / arcane nova, merchant hire/dismiss mercenary / haggle /
  bribe, healer holy light / divine shield / purify / self-revive, adventurer
  dungeon exploration / relics.
- `class_ability_handlers.py` — Telegram UI: `/class` command + `class_panel`
  callback, per-class panel renderer, and one callback handler per action.
  Registered via `register_class_ability_handlers(dp, bot)`.

## Modified files
- `combat.py`: kcore fix; mana-shield/divine-shield charges now absorb
  60%/70% of enemy retaliation damage and consume a charge; wizard spell
  charge forces an element-weakness match + bonus damage on the next hit;
  adventurer relics add flat bonus damage (same pattern as merchant mercs).
- `combat_handlers.py`: healer self-revive checked on death (after the
  existing katana phoenix-style revive check); attack panel gained a
  "⚜️ Class Powers" button linking to the new panel.
- `bot.py`: registered `class_ability_handlers`; added `/class` to the
  Telegram command menu and to `/status` output.

## Known limitations / not yet covered
- No live aiogram/MongoDB environment was available here, so the new modules
  were verified with `py_compile` (177/177 files clean) and a standalone
  logic-level smoke test of `class_abilities.py` (all 4 classes) — but not a
  real end-to-end Telegram run. Test locally before deploying.
- Resource regen (mana/stamina/faith) is lazy — it's only computed when the
  player opens `/class` or spends the resource, not on a background timer.
  Fine for normal use, but the displayed number on `/status` may lag until
  `/class` is opened once.
- Wizard's "known elements" still only unlocks up to all 3 via repeated
  spellcasting (every 4th cast) — no dedicated UI to show synergy progress
  beyond the counter.
- Merchant mercenaries have no upkeep cost and no combat "which mercenary"
  flavor beyond a flat damage bonus — kept intentionally simple per the
  existing Stage 2 pattern.
