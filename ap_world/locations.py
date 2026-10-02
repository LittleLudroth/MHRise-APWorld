"""Location table for the MH Rise apworld.

Two modes, two location families (see options.py:Mode):

- HuntAThon: two locations per curated monster, `f"Hunt {name} (1/2)"`
  and `f"Hunt {name} (2/2)"`. Both fire on the same in-game hunt event
  — the two-slot structure exists purely to double the multiworld item
  slots per monster.

- QuestRando: two locations per village quest in the active pool,
  `f"Clear: {quest.name} (1/2)"` and `f"Clear: {quest.name} (2/2)"`.
  Both fire on the same quest-clear event (same two-slot design as
  HuntAThon).

IDs are static and known at module import time (same stability story as
items.py) so the datapackage stays frozen across seeds and option/mode
choices.

ID layout:
- 1..(2N): monster hunt locations. Order matches items.py
  (`MONSTERS + APEX_MONSTERS + SMALL_MONSTERS`); each monster reserves
  two consecutive IDs (`(1/2)` then `(2/2)`).
- 2000..2999: per-village-quest clear locations. Two consecutive IDs
  per entry in `QUESTRANDO_VILLAGE_QUESTS` (filtered identically to
  items.py via `_in_questrando_pool`), `(1/2)` then `(2/2)`. Items
  and locations live in separate AP namespaces, so the 2000+ id range
  is shared with the `Unlock:` item ids without collision.

Only locations the active mode uses get added to the multiworld; the
rest sit in the static map for datapackage stability.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Location, LocationProgressType

from .items import (
    ALL_CURATED_MONSTERS,
    QUESTSANITY_VILLAGE_QUESTS,
    QUESTSANITY_HUB_QUESTS,
    QUESTSANITY_MR_QUESTS,
    quest_display_name,
)
from .options import Mode, QuestRandoPool
from .data.quests import QuestLevel, EnemyLv
from .data.monster_categories import EASY_MONSTERS, MEDIUM_MONSTERS, HARD_MONSTERS
if TYPE_CHECKING:
    from .world import MHRiseWorld


LOCATION_ID_BASE = 0
LOCATIONS_PER_MONSTER = 2
LOCATIONS_PER_QUEST = 2
QUEST_CLEAR_ID_BASE = 2000
HUB_QUEST_CLEAR_ID_BASE = 3000
MR_QUEST_CLEAR_ID_BASE = 4000

LOCATION_NAME_TO_ID: dict[str, int] = {}

for _i, _monster in enumerate(ALL_CURATED_MONSTERS):
    for _slot in range(LOCATIONS_PER_MONSTER):
        _id = LOCATION_ID_BASE + _i * LOCATIONS_PER_MONSTER + _slot + 1
        _name = f"Hunt {_monster['name']} ({_slot + 1}/{LOCATIONS_PER_MONSTER})"
        assert _name not in LOCATION_NAME_TO_ID, f"duplicate location name {_name}"
        LOCATION_NAME_TO_ID[_name] = _id

for _i, _quest in enumerate(QUESTSANITY_VILLAGE_QUESTS):
    for _slot in range(LOCATIONS_PER_QUEST):
        _id = QUEST_CLEAR_ID_BASE + _i * LOCATIONS_PER_QUEST + _slot
        assert _id < 9000, "QuestRando village quest count overflowed reserved range"
        _name = f"Clear: {quest_display_name(_quest)} ({_slot + 1}/{LOCATIONS_PER_QUEST})"
        assert _name not in LOCATION_NAME_TO_ID, f"duplicate location name {_name}"
        LOCATION_NAME_TO_ID[_name] = _id

for _i, _quest in enumerate(QUESTSANITY_HUB_QUESTS):
    for _slot in range(LOCATIONS_PER_QUEST):
        _id = HUB_QUEST_CLEAR_ID_BASE + _i * LOCATIONS_PER_QUEST + _slot
        assert _id < 9000, "QuestRando hub quest count overflowed reserved range"
        _name = f"Clear: {quest_display_name(_quest)} ({_slot + 1}/{LOCATIONS_PER_QUEST})"
        assert _name not in LOCATION_NAME_TO_ID, f"duplicate location name {_name}"
        LOCATION_NAME_TO_ID[_name] = _id

for _i, _quest in enumerate(QUESTSANITY_MR_QUESTS):
    for _slot in range(LOCATIONS_PER_QUEST):
        _id = MR_QUEST_CLEAR_ID_BASE + _i * LOCATIONS_PER_QUEST + _slot
        assert _id < 9000, "QuestRando hub quest count overflowed reserved range"
        _name = f"Clear: {quest_display_name(_quest)} ({_slot + 1}/{LOCATIONS_PER_QUEST})"
        assert _name not in LOCATION_NAME_TO_ID, f"duplicate location name {_name}"
        LOCATION_NAME_TO_ID[_name] = _id


def hunt_location_names(monster: dict) -> list[str]:
    """Return the AP location names for hunting a given monster — one per
    slot. Both fire on the same in-game hunt event."""
    return [
        f"Hunt {monster['name']} ({slot + 1}/{LOCATIONS_PER_MONSTER})"
        for slot in range(LOCATIONS_PER_MONSTER)
    ]


def quest_clear_location_names(quest: dict) -> list[str]:
    """Return the AP location names for clearing a quest — both slots.
    Both fire on the same in-game quest-clear event."""
    return [
        f"Clear: {quest_display_name(quest)} ({slot + 1}/{LOCATIONS_PER_QUEST})"
        for slot in range(LOCATIONS_PER_QUEST)
    ]


class MHRiseLocation(Location):
    game = "Monster Hunter Rise"


def create_all_locations(world: MHRiseWorld) -> None:
    """Dispatch on mode."""
    if world.options.mode.value == Mode.option_quest_rando:
        _create_locations_questrando(world)
    else:
        _create_locations_huntathon(world)


def _create_locations_huntathon(world: MHRiseWorld) -> None:
    """Add hunt locations for every monster in the seed to the corresponding region

    The seed subset is computed in `world.generate_early` and stored on
    `world.seed_monsters`."""
    regions = [world.get_region(n) for n in world.region_names]

    # Add locations for each region based on what difficulty the monster is
    easy_location_map: dict[str, int] = {}
    medium_location_map: dict[str, int] = {}
    hard_location_map: dict[str, int] = {}
    for monster in world.seed_monsters:
        if monster["name"] in EASY_MONSTERS or monster == world.starting_monster:
            for name in hunt_location_names(monster):
                easy_location_map[name] = LOCATION_NAME_TO_ID[name]
        elif monster["name"] in MEDIUM_MONSTERS:
            for name in hunt_location_names(monster):
                medium_location_map[name] = LOCATION_NAME_TO_ID[name]
        else:
            for name in hunt_location_names(monster):
                hard_location_map[name] = LOCATION_NAME_TO_ID[name]

    regions[0].add_locations(easy_location_map, MHRiseLocation)
    regions[1].add_locations(medium_location_map, MHRiseLocation)
    regions[2].add_locations(hard_location_map, MHRiseLocation)

    # Both goal-monster hunt locations are EXCLUDED so AP fill never
    # places progression/useful items at them. (2/2) is then locked with
    # Victory in items.place_victory; place_locked_item bypasses the
    # progress_type flag, so the lock still works. Hunting the goal ends
    # the run — anything stranded at goal (1/2) would be unreachable.
    for name in hunt_location_names(world.goal_monster):
        world.get_location(name).progress_type = LocationProgressType.EXCLUDED


def _create_locations_questrando(world: MHRiseWorld) -> None:
    """Add two Clear-locations per village quest in the active pool."""

    if world.options.quest_rando_pool.value == QuestRandoPool.option_quest_rando_village:
        # Get the four village regions, map each quest level to its corresponding region
        regions = [world.get_region(n) for n in world.region_names]
        assert len(regions) == 4, "Invalid number of regions for Village Quests, should be impossible"
        level_map:dict[QuestLevel, dict[str, int]] = {QuestLevel.QL2: {},
                                                      QuestLevel.QL3: {},
                                                      QuestLevel.QL4: {},
                                                      QuestLevel.QL5: {}
                                                     }
        
        for quest in world.quest_pool:
            for name in quest_clear_location_names(quest):
                level_map[quest["quest_level"]][name] = LOCATION_NAME_TO_ID[name]

        # as of python 3.7, dictionaries must preserve insertion order, so level map and regions
        # are in corresponding order
        for i, key in enumerate(level_map.keys()):
            regions[i].add_locations(level_map[key], MHRiseLocation)

    elif world.options.quest_rando_pool.value == QuestRandoPool.option_quest_rando_hub:
        # Get the 7 hub regions, map each quest level to its corresponding region
        regions = [world.get_region(n) for n in world.region_names]
        assert len(regions) == 7, "Invalid number of regions for Hub Quests, should be impossible"
        level_map:dict[QuestLevel, dict[str, int]] = {QuestLevel.QL1: {},
                                                      QuestLevel.QL2: {},
                                                      QuestLevel.QL3: {},
                                                      QuestLevel.QL4: {},
                                                      QuestLevel.QL5: {},
                                                      QuestLevel.QL6: {},
                                                      QuestLevel.QL7: {}
                                                     }

        for quest in world.quest_pool:
            for name in quest_clear_location_names(quest):
                level_map[quest["quest_level"]][name] = LOCATION_NAME_TO_ID[name]

        # as of python 3.7, dictionaries must preserve insertion order, so level map and regions
        # are in corresponding order
        for i, key in enumerate(level_map.keys()):
            regions[i].add_locations(level_map[key], MHRiseLocation)

    else:
        regions = [world.get_region(n) for n in world.region_names]
        assert len(regions) == 13, "Invalid number of regions for MR Quests, should be impossible"
        mr_level_map:dict[tuple[QuestLevel, EnemyLv], dict[str, int]] = \
                                                     {(QuestLevel.QL1,EnemyLv.Low): {},
                                                      (QuestLevel.QL2,EnemyLv.Low): {},
                                                      (QuestLevel.QL3,EnemyLv.Low): {},
                                                      (QuestLevel.QL4,EnemyLv.High): {},
                                                      (QuestLevel.QL5,EnemyLv.High): {},
                                                      (QuestLevel.QL6,EnemyLv.High): {},
                                                      (QuestLevel.QL7,EnemyLv.High): {},
                                                      (QuestLevel.QL1,EnemyLv.Master): {},
                                                      (QuestLevel.QL2,EnemyLv.Master): {},
                                                      (QuestLevel.QL3,EnemyLv.Master): {},
                                                      (QuestLevel.QL4,EnemyLv.Master): {},
                                                      (QuestLevel.QL5,EnemyLv.Master): {},
                                                      (QuestLevel.QL6,EnemyLv.Master): {},
                                                     }

        for quest in world.quest_pool:
            for name in quest_clear_location_names(quest):
                mr_level_map[(quest["quest_level"],quest["enemy_level"])][name] = LOCATION_NAME_TO_ID[name]

        # as of python 3.7, dictionaries must preserve insertion order, so level map and regions
        # are in corresponding order
        for i, key in enumerate(mr_level_map.keys()):
            regions[i].add_locations(mr_level_map[key], MHRiseLocation)
    

    # Both goal quest clear locations are EXCLUDED so AP fill doesn't
    # strand progression items at the run-ending clear. (2/2) is locked
    # with Victory in items.place_victory; place_locked_item bypasses
    # progress_type, so the lock still works.
    for name in quest_clear_location_names(world.goal_quest):
        world.get_location(name).progress_type = LocationProgressType.EXCLUDED
