"""Fuzz config space for MH Rise apworld generation.

Each config is a dict matching the apworld's option keys. `to_yaml`
emits a valid Archipelago YAML wrapping the config under the
"Monster Hunter Rise" game key.

Constraint respected by `random_config`: when `include_weapons` is
true, `weapon_pool` is always a non-empty subset (else `generate_early`
raises in ap_world/world.py).
"""
from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "ap_world" / "data"))
from weapons import WEAPONS  # noqa: E402
from monsters import MONSTERS

WEAPON_NAMES = [w["name"] for w in WEAPONS]
GAME_NAME = "Monster Hunter Rise"

DEFAULT_CONFIG: dict[str, Any] = {
    "mode": "hunt_a_thon",
    "quest_rando_pool": "quest_rando_village",
    "questsanity": False,
    "include_sunbreak": True,
    "include_risen": False,
    "starting_monsters": ["Random"],
    "goal_monsters": ["Random"],
    "include_weapons": True,
    "weapon_pool": list(WEAPON_NAMES),
    "starting_weapons": ["Random"],
    "randomize_quest_monsters": True,
    "excluded_monsters": [],
    "monster_count": 15,
    "deathlink": False,
}

QUEST_RANDO_CONFIG: dict[str, Any] = {
    **DEFAULT_CONFIG,
    "mode": "quest_rando",
}


def random_config(rng: random.Random) -> dict[str, Any]:
    mode = rng.choice(["hunt_a_thon", "quest_rando"])
    quest_rando_pool = rng.choice(["quest_rando_village", "quest_rando_hub", "quest_rando_sunbreak"])
    include_weapons = rng.random() < 0.7
    if include_weapons:
        pool_size = rng.randint(1, len(WEAPON_NAMES))
        weapon_pool = rng.sample(WEAPON_NAMES, pool_size)
        starting_weapons_count = rng.randint(0, len(weapon_pool))
        starting_weapons = rng.sample(weapon_pool, starting_weapons_count)
        if not starting_weapons:
            starting_weapons = ["Random"]
    else:
        weapon_pool = list(WEAPON_NAMES)
        starting_weapons = ["Random"]

    starting_monster_candidates = [m["name"] for m in MONSTERS if "elder-dragon" not in m["tags"]]
    goal_monster_candidates = [m["name"] for m in MONSTERS if "elder-dragon" in m["tags"]]

    if rng.random() < 0.5 and len(starting_monster_candidates) > 1:
        starting_monster_count = rng.randint(1, len(starting_monster_candidates))
        starting_monsters = rng.sample(starting_monster_candidates, starting_monster_count)
    else:
        starting_monsters = ["Random"]

    if rng.random() < 0.5 and len(goal_monster_candidates) > 1:
        goal_monster_count = rng.randint(1, len(goal_monster_candidates))
        goal_monsters = rng.sample(goal_monster_candidates, goal_monster_count)
    else:
        goal_monsters = ["Random"]

    if rng.random() < 0.3:
        # There are possible configurations that break huntathon
        # This is fine, I don't want to add safeguards to ensure an elder dragon is always available
        # I am specifically capping the exclude pool at n-6 to reduce how often this happens
        excluded_monster_count = rng.randint(1, len(MONSTERS) - 6)
        excluded_monsters = rng.sample([m["name"] for m in MONSTERS], excluded_monster_count)
    else:
        excluded_monsters = []
    return {
        "mode": mode,
        "quest_rando_pool": quest_rando_pool,
        "questsanity": rng.random() < 0.3,
        "include_sunbreak": rng.random() < 0.7,
        "include_risen": rng.random() < 0.3,
        "starting_monsters": starting_monsters,
        "goal_monsters": goal_monsters,
        "include_weapons": include_weapons,
        "weapon_pool": weapon_pool,
        "starting_weapons": starting_weapons,
        "randomize_quest_monsters": rng.random() < 0.7,
        "excluded_monsters": excluded_monsters,
        "monster_count": rng.randint(3, 72),
        "deathlink": rng.random() < 0.5,
    }


EDGE_CONFIGS: list[dict[str, Any]] = [
    DEFAULT_CONFIG,
    {**DEFAULT_CONFIG, "include_sunbreak": False, "include_risen": False, "include_weapons": False, "monster_count": 3},
    {**DEFAULT_CONFIG, "include_sunbreak": True, "include_risen": True, "include_weapons": True, "monster_count": 72},
    {**DEFAULT_CONFIG, "monster_count": 3},
    {**DEFAULT_CONFIG, "monster_count": 72},
    # Sunbreak off + monster_count > base-game pool → exercises the
    # generate_early clamp (`n = min(requested, len(available))`).
    {**DEFAULT_CONFIG, "include_sunbreak": False, "monster_count": 60},
    {**DEFAULT_CONFIG, "weapon_pool": [WEAPON_NAMES[0]]},
    {**DEFAULT_CONFIG, "include_sunbreak": False, "include_risen": False, "monster_count": 32},
    # QuestRando: now honors include_weapons / weapon_pool too. Exercise
    # the toggles and weapon-pool truncation.
    QUEST_RANDO_CONFIG,
    {**QUEST_RANDO_CONFIG, "include_sunbreak": False},
    {**QUEST_RANDO_CONFIG, "include_risen": True},
    {**QUEST_RANDO_CONFIG, "include_weapons": False},
    {**QUEST_RANDO_CONFIG, "include_sunbreak": False, "include_weapons": False},
    {**QUEST_RANDO_CONFIG, "weapon_pool": [WEAPON_NAMES[0]]},
    {**QUEST_RANDO_CONFIG, "weapon_pool": WEAPON_NAMES[:3]},
    {**QUEST_RANDO_CONFIG, "randomize_quest_monsters": False},
]


def to_yaml(config: dict[str, Any], slot_name: str) -> str:
    doc = {
        "name": slot_name,
        "game": GAME_NAME,
        "description": f"fuzz slot {slot_name}",
        GAME_NAME: config,
        "requires": {"version": "0.6.7"},
    }
    return yaml.safe_dump(doc, sort_keys=False)
