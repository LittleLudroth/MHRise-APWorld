"""Per-slot options for the MH Rise apworld.

Two mutually-exclusive modes via the `mode` option:
- HuntAThon (default): per-monster license soft-gate.
- QuestRando: per-quest `Unlock:` items soft-gate clear checks; each
  pool quest's spawned monster is randomly swapped. Goal = clearing
  "Comeuppance".

Options that apply per mode:
- IncludeSunbreak: both modes.
- IncludeRisen: HuntAThon only (no Risen variant currently appears in
  any vanilla quest, so a no-op in QuestRando — wired anyway).
- IncludeWeapons / WeaponPool: both modes. In QuestRando the gate
  fires at clear time (same soft-gate shape as HuntAThon's hunt
  gate); weapon licenses fill spare itempool slots and one is
  precollected as the starter.
- MonsterCount: HuntAThon only — QuestRando's pool size is derived
  from the village quest catalog.
- Deathlink: both modes. Enables or disables deathlink.
"""

from __future__ import annotations

from dataclasses import dataclass

from Options import Choice, DefaultOnToggle, OptionSet, PerGameCommonOptions, Range, Toggle

from .data.weapons import WEAPONS

_WEAPON_NAMES = {w["name"] for w in WEAPONS}


class Mode(Choice):
    """Game mode.

    - `hunt_a_thon` (default): hunting a large monster requires its
      license. Licenses are scattered across the multiworld. Standard
      hunt-for-keys loop.
    - `quest_rando`: each village quest's boss monster is randomly
      swapped (within per-map compatibility). Clearing a quest sends
      AP checks when the matching `Unlock: <quest>` and — if weapons
      are enabled — the wielded weapon's license are held. Goal =
      clearing the final village urgent "Comeuppance" (its boss stays
      as the intended Magnamalo). MonsterCount is ignored in this
      mode; the rest of the options apply."""

    display_name = "Mode"
    option_hunt_a_thon = 0
    option_quest_rando = 1
    default = 0


class IncludeSunbreak(DefaultOnToggle):
    """Include Sunbreak monsters (and their subspecies / Risen variants) in
    the world. When disabled, only base-game Rise monsters are randomized."""

    display_name = "Include Sunbreak"


class IncludeRisen(Toggle):
    """Include Risen elder dragons (Anomaly Investigation endgame —
    Risen Kushala Daora, Chameleos, Teostra, Shagaru Magala, Crimson
    Glow Valstrax). Default off because they are post-credits / very
    high difficulty. Has no effect when Sunbreak is disabled."""

    display_name = "Include Risen"


class IncludeWeapons(DefaultOnToggle):
    """Add weapon-type licenses to the pool. When enabled, weapon
    licenses fill the spare itempool slots; the player needs the
    license for their currently-equipped weapon to complete a hunt
    (HuntAThon) or send a quest-clear check (QuestRando). One random
    weapon license is always precollected. Applies to both modes."""

    display_name = "Include Weapons"


class WeaponPool(OptionSet):
    """Restrict which weapon-type licenses are eligible for the pool
    (and for the precollected starter weapon). Defaults to all 14
    weapons. To play with a smaller set, list the weapon names you
    want — e.g.:

        weapon_pool:
          - Long Sword
          - Bow
          - Switch Axe

    Must contain at least one valid weapon name. Names are
    case-sensitive and must match the entries in `data/weapons.py`.
    No effect when `include_weapons` is disabled. Applies to both
    modes."""

    display_name = "Weapon Pool"
    valid_keys = _WEAPON_NAMES
    default = _WEAPON_NAMES


class RandomizeQuestMonsters(DefaultOnToggle):
    """QuestRando only: when enabled (default), every pool quest's
    boss monster is randomly swapped (within per-map compatibility).
    When disabled, quests keep their vanilla boss — the rando reduces
    to gating clear checks on the per-quest `Unlock:` items without
    altering the in-game fight. No effect in HuntAThon."""

    display_name = "Randomize Quest Monsters"


class MonsterCount(Range):
    """Number of monsters randomly drawn into the world. Determines how
    many hunts are randomized. Clamped to the available pool size at
    generation time (max 32 with Sunbreak off, 72 with Sunbreak on).
    Min 3 — at N=2 the spare-slot budget is too tight to fit weapon
    licenses without overrunning available locations."""

    display_name = "Monster Count"
    range_start = 3
    range_end = 72
    default = 15

class Deathlink(Toggle):
    """Enable or disable deathlink. When enabled,
    a faint will count as a death. This setting can be toggled in game."""
    display_name = "Deathlink"

@dataclass
class MHRiseOptions(PerGameCommonOptions):
    mode: Mode
    include_sunbreak: IncludeSunbreak
    include_risen: IncludeRisen
    include_weapons: IncludeWeapons
    weapon_pool: WeaponPool
    randomize_quest_monsters: RandomizeQuestMonsters
    monster_count: MonsterCount
    deathlink: Deathlink
