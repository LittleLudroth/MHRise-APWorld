"""Per-slot options for the MH Rise apworld.

Two mutually-exclusive modes via the `mode` option:
- HuntAThon (default): per-monster license soft-gate.
- QuestRando: per-quest `Unlock:` items soft-gate clear checks; each
  pool quest's spawned monster is randomly swapped. 

Options that apply per mode:
- QuestRandoPool: QuestRando only — select whether QuestRando
  should randomize village quests, the base game hub, or the
  base game and master rank hub. Sunbreak must be enabled to play
  master rank QuestRando
- Questsanity: QuestRando only — select whether or not QuestRando
  includes optional quests.
- StartingMonsters: HuntAThon only — select the starting monster. Cannot be an elder dragon.
- GoalMonsters: HuntAThon only — select which elder dragon should be the goal.
- IncludeSunbreak: both modes.
- IncludeRisen: HuntAThon only (no Risen variant currently appears in
  any vanilla quest, so a no-op in QuestRando — wired anyway).
- IncludeWeapons / WeaponPool: both modes. In QuestRando the gate
  fires at clear time (same soft-gate shape as HuntAThon's hunt
  gate); weapon licenses fill spare itempool slots and one is
  precollected as the starter.
- StartingWeapon: both modes. Select a specific weapon license to
  start with. Does nothing if IncludeWeapons is disabled.
- MonsterCount: HuntAThon only — QuestRando's pool size is derived
  from the village quest catalog.
- ExcludedMonsters: both modes. Allows player to manually remove monsters
  from the pool.
- Deathlink: both modes. Enables or disables deathlink.
"""

from __future__ import annotations

from dataclasses import dataclass

from Options import Choice, DefaultOnToggle, OptionSet, PerGameCommonOptions, Range, Toggle

from .data.weapons import WEAPONS
from .data.monsters import MONSTERS

_WEAPON_NAMES = {w["name"] for w in WEAPONS}
_MONSTER_NAMES = {m["name"] for m in MONSTERS}


class Mode(Choice):
    """Game mode.

    - `hunt_a_thon` (default): hunting a large monster requires its
      license. Licenses are scattered across the multiworld. A random goal monster
      is selected, and hunting that goal monster wins the game.
      
      Monsters are split into three tiers based on difficulty. Accessing a tier of
      monsters is gated by having half of the previous tier unlocked or completed.
      Additionally, the goal monster is gated by having or completing half of the
      highest tier of monsters. 
      
      NOTE: Huntathon requires a save file at HR 100+ with the ability to clear
      Crimson Glow Valstrax for base game, a save file at MR 10+ with the ability
      to clear P. Malzeno and Amatsu if you enable Sunbreak, and a save file at
      MR 180+ with the ability to clear Risen Shagaru Magala for Sunbreak with Risen Elders enabled.

    - `quest_rando`: completing a quest requires its unlock item. Unlocks
      are scattered around the multiworld. Clear your way through quests 
      until reaching the goal. MonsterCount is ignored in this mode;
      the rest of the options apply. This option is intended for
      new save files.
      """

    display_name = "Mode"
    option_hunt_a_thon = 0
    option_quest_rando = 1
    default = 0

class QuestRandoPool(Choice):
    """
    QuestRando Only: Select which pool of quests should be randomized.
    - `quest_rando_village` (default): each village quest's boss monster
      is randomly swapped (within per-map compatibility). Clearing a quest
      sends AP checks when the matching `Unlock: <quest>` and — if weapons
      are enabled — the wielded weapon's license are held. Goal =
      clearing the final village urgent "Comeuppance". There are 18 quests
      in this pool.
    - `quest_rando_hub`: each low/high rank hub quest's boss monster is
      randomly swapped (within per-map compatibility). Clearing a quest sends
      AP checks when the matching `Unlock: <quest>` and — if weapons
      are enabled — the wielded weapon's license are held. Goal =
      clearing the 7* urgent "Serpent Goddess of Thunder". There are 59 quests
      in this pool.
    - `quest_rando_sunbreak`: each hub and master rank quest's boss monster
      is randomly swapped (within per-map compatibility). Clearing a quest
      sends AP checks when the matching `Unlock: <quest>` and — if weapons
      are enabled — the wielded weapon's license are held. Goal =
      clearing the MR6 urgent "Proof of Courage". This option requires 
      Sunbreak, and will default to `quest_rando_hub` if sunbreak is disabled.
      There are 118 quests in this pool.
    """
    display_name = "Quest Pool"
    option_quest_rando_village = 0
    option_quest_rando_hub = 1
    option_quest_rando_sunbreak = 2
    default = 0

class Questsanity(Toggle):
    """
    QuestRando Only: Include optional quests in the QuestRando pool.
    This option will add 3 quests to Village QuestRando,
    26 quests to Hub QuestRando, and 60 quests to Sunbreak QuestRando
    """
    display_name = "Questsanity"

class StartingMonsters(OptionSet):
    """
    Huntathon Only: Select which monsters can be the starting monster.
    Cannot include elder dragons or rajang to avoid overlap with the goal monster.
    See the game info document for a full list of expected monster names.
    Leave this option as "Random" to allow any starting monster.
    """
    display_name = "Starting Monsters"
    valid_keys = set([m["name"] for m in MONSTERS if "elder-dragon" not in m["tags"]]).union(set(["Random"]))
    default = set(["Random"])

class GoalMonsters(OptionSet):
    """
    Huntathon Only: Select which monsters can be the goal monster.
    The goal monster must be an elder dragon or Rajang.
    See the game info document for a full list of expected monster names.
    Leave this option as "Random" to allow any goal monster
    """
    display_name = "Goal Monsters"
    valid_keys = set([m["name"] for m in MONSTERS if "elder-dragon" in m["tags"]]).union(set(["Random"]))
    default = set(["Random"])

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

    Must contain at least one valid weapon name. Empty sets will default
    to all weapons. Names are case-sensitive and must match the entries in
    `data/weapons.py`. No effect when `include_weapons` is disabled.
    Applies to both modes."""

    display_name = "Weapon Pool"
    valid_keys = _WEAPON_NAMES
    default = _WEAPON_NAMES

class StartingWeapons(OptionSet):
    """
    Restrict which weapon types are eligible to be your starting weapon. One
    of the weapons types in this pool will be precollected. Leave the 
    option as "Random" to get any weapon from the weapon pool.

    Must contain at least one valid weapon name or Random. Empty sets will
    default to random selection. Any names not in the weapon pool will be ignored.
    No effect when `include_weapons` is disabled. Applies to both modes.
    """
    display_name = "Starting Weapons"
    valid_keys = _WEAPON_NAMES.union(set(("Random",)))
    default = set(("Random",))

class RandomizeQuestMonsters(DefaultOnToggle):
    """QuestRando only: when enabled (default), every pool quest's
    boss monster is randomly swapped (within per-map compatibility).
    When disabled, quests keep their vanilla boss — the rando reduces
    to gating clear checks on the per-quest `Unlock:` items without
    altering the in-game fight. No effect in HuntAThon."""

    display_name = "Randomize Quest Monsters"

class ExcludedMonsters(OptionSet):
    """
    Select any monsters which should be excluded from the pool. Note that
    excluding monsters will also reduce the maximum size of the huntathon pool.
    If you exclude all monsters in a biome, questrando will use default quest monsters in that biome.
    Leave empty to keep the entire monster pool.
    You can find a list of monster names as expected by this option in the game's info document.
    """

    display_name = "Excluded Monsters"
    valid_keys = _MONSTER_NAMES
    default = set()


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
    quest_rando_pool: QuestRandoPool
    questsanity: Questsanity
    include_sunbreak: IncludeSunbreak
    include_risen: IncludeRisen
    starting_monsters: StartingMonsters
    goal_monsters:GoalMonsters
    include_weapons: IncludeWeapons
    weapon_pool: WeaponPool
    starting_weapons: StartingWeapons
    randomize_quest_monsters: RandomizeQuestMonsters
    excluded_monsters: ExcludedMonsters
    monster_count: MonsterCount
    deathlink: Deathlink
