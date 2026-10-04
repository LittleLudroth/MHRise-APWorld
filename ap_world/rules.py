"""Access rules for the MH Rise apworld.

- HuntAThon: each hunt location requires the corresponding monster's
  license. Additionally, medium monsters require half of all unlocks 
  for easy monsters and hard monsters require half of all unlocks for
  medium monsters. Both (1/2) and (2/2) share the same rule since both fire on
  the same in-game hunt event.
- QuestRando:
  - Each Clear location requires the matching `Unlock: X` item.
  - non-urgent quests additionally require their tier's urgent
    unlock (engine won't show the rest of the tier until the urgent
    has been cleared).
  - The tier urgent quests themselves additionally require enough key
    unlocks from the prior group of keys to unlock them in game.
  - Both (1/2) and (2/2) share the same rule since both fire on
    the same in-game quest clear event.

Precollected items satisfy their own rule trivially — `state.has`
returns True for precollected items just like items received from the
multiworld.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any
from math import ceil

from rule_builder.rules import Has, HasAll, HasFromList, True_, And

from .data.quests import QuestLevel
from .data.quest_categories import URGENT_QUEST_DATA, OPTIONAL_QUESTS
from .items import (
    TIER_URGENT_QUEST_NOS,
    HUB_TIER_URGENT_QUEST_NOS,
    MR_TIER_URGENT_QUEST_NOS,
    MID_URGENT_QUEST_NOS,
    TBA_QUEST_NUMBER,
    license_item_name,
    unlock_item_name,
)
from .locations import hunt_location_names, quest_clear_location_names
from .options import Mode, QuestRandoPool

if TYPE_CHECKING:
    from .world import MHRiseWorld


# A dictionary mapping all of the key quests to the urgent quest that unlocks them
# quests that map to None are key quests that are available from the start
key_quest_to_urgent:dict[int, Any] = {}
for quest in URGENT_QUEST_DATA:
    for key in URGENT_QUEST_DATA[quest]["unlocked_quests"]:
        if key in OPTIONAL_QUESTS:
            continue
        key_quest_to_urgent[key] = quest
    for key in URGENT_QUEST_DATA[quest]["key_list"]:
        if key not in key_quest_to_urgent:
            key_quest_to_urgent[key] = None

def set_all_rules(world: MHRiseWorld) -> None:
    if world.options.mode.value == Mode.option_hunt_a_thon:
        _set_rules_huntathon(world)
    else:
        _set_rules_questrando(world)
    set_completion_condition(world)


def _set_rules_huntathon(world: MHRiseWorld) -> None:
    """
    Handle rules by monster difficulty
    Each difficulty of monster requires half of the unlocks from the previous tier
    Additionally, the goal monster requires half of the hard monster unlocks
    """
    from .regions import HUNTATHON_ENTRANCES

    # Get the entrances for medium and hard monsters
    medium_entrance = world.get_entrance(HUNTATHON_ENTRANCES[0])
    hard_entrance = world.get_entrance(HUNTATHON_ENTRANCES[1])

    # Require half of the unlocks for monsters in previous tier
    medium_rule = HasFromList(count=ceil(len(world.easy_seed_monsters) / 2),
                    *[license_item_name(m) for m in world.easy_seed_monsters])\
                     if len(world.easy_seed_monsters) != 0 else True_()
    world.set_rule(medium_entrance, medium_rule)

    hard_rule = HasFromList(count=ceil(len(world.medium_seed_monsters) / 2),
                             *[license_item_name(m) for m in world.medium_seed_monsters])\
                              if len(world.medium_seed_monsters) != 0 else True_()
    world.set_rule(hard_entrance, hard_rule)

    goal_rule = HasFromList(count=ceil(len(world.hard_seed_monsters) / 2),
                             *[license_item_name(m) for m in world.hard_seed_monsters])\
                              if len(world.hard_seed_monsters) != 0 else True_()

    # Apply license requirement to every monster, and apply goal rule to final monster
    for monster in world.seed_monsters:
        license_rule = Has(license_item_name(monster))
        if monster == world.goal_monster:
            for loc_name in hunt_location_names(monster):
                world.set_rule(world.get_location(loc_name), And(license_rule, goal_rule))
        else:
            for loc_name in hunt_location_names(monster):
                world.set_rule(world.get_location(loc_name), license_rule)


def _set_rules_questrando(world: MHRiseWorld) -> None:
    """
    Handle quests by quest type using info in quest_catergories

    Rule shapes:
    -Urgent Quests require a number of key quest unlocks equal to the 
     number of key quests needed to unlock the quest in the base game. These
     key quests are pulled from the list of valid keys for that quest. In addition,
     Urgent quests require heir own unlock item.
     Some urgent quests (mid urgents) may have additional urgents preceeding them.
     These urgents will have the rule for preceeding urgents added to their own rule.
    -Key quests require their own unlock item. If the key quest is unlocked by a mid
     urgent, the key quest also requires that mid urgent's rule 
    -Optional require their own item

    All quests are regions split by quest level, so the rule for the urgent that unlocks
    each tier is applied to the entrance for that region. As such, the locations for that urgent
    don't need any additional rules.
    """
    from .regions import VILLAGE_ENTRANCES, HUB_ENTRANCES, MASTER_ENTRANCES
    quest_id_to_quest:dict[int, dict] = {quest["quest_no"]:quest for quest in world.quest_pool}
    urgent_rules_by_id = set_urgent_rules(world, quest_id_to_quest)

    if world.options.quest_rando_pool.value == QuestRandoPool.option_quest_rando_village:
        # The origin region is always unlocked, so don't need a rule for that
        # The other two regions are gated by their respective urgent quests
        # Set the entrance rule to the urgent quest requirements
        unlock_v3 = world.get_entrance(VILLAGE_ENTRANCES[0])
        unlock_v4 = world.get_entrance(VILLAGE_ENTRANCES[1])
        unlock_v5 = world.get_entrance(VILLAGE_ENTRANCES[2])

        # set the rule to reach 3, 4, and 5 star quests equal to the requirements
        # for the urgent quests that unlock that tier
        world.set_rule(unlock_v3, urgent_rules_by_id[TIER_URGENT_QUEST_NOS[QuestLevel.QL3]])
        world.set_rule(unlock_v4, urgent_rules_by_id[TIER_URGENT_QUEST_NOS[QuestLevel.QL4]])
        world.set_rule(unlock_v5, urgent_rules_by_id[TIER_URGENT_QUEST_NOS[QuestLevel.QL5]])

        # for quests not in urgent_rules, set their rule to require their own item
        for quest in world.quest_pool:
            if quest["quest_no"] in urgent_rules_by_id:
                continue
            for loc_name in quest_clear_location_names(quest):
                world.set_rule(world.get_location(loc_name),Has(unlock_item_name(quest)))

    else:
        # The rules for hub quests are the same in hub and sunbreak modes
        # get the various hub entrances from world
        unlock_h2 = world.get_entrance(HUB_ENTRANCES[0])
        unlock_h3 = world.get_entrance(HUB_ENTRANCES[1])
        unlock_h4 = world.get_entrance(HUB_ENTRANCES[2])
        unlock_h5 = world.get_entrance(HUB_ENTRANCES[3])
        unlock_h6 = world.get_entrance(HUB_ENTRANCES[4])
        unlock_h7 = world.get_entrance(HUB_ENTRANCES[5])

        # Set the entrance rules equal to the urgent quest requirements for each tier
        world.set_rule(unlock_h2, urgent_rules_by_id[HUB_TIER_URGENT_QUEST_NOS[QuestLevel.QL2]])
        world.set_rule(unlock_h3, urgent_rules_by_id[HUB_TIER_URGENT_QUEST_NOS[QuestLevel.QL3]])
        world.set_rule(unlock_h4, urgent_rules_by_id[HUB_TIER_URGENT_QUEST_NOS[QuestLevel.QL4]])
        world.set_rule(unlock_h5, urgent_rules_by_id[HUB_TIER_URGENT_QUEST_NOS[QuestLevel.QL5]])
        world.set_rule(unlock_h6, urgent_rules_by_id[HUB_TIER_URGENT_QUEST_NOS[QuestLevel.QL6]])
        world.set_rule(unlock_h7, urgent_rules_by_id[HUB_TIER_URGENT_QUEST_NOS[QuestLevel.QL7]])

        # If sunbreak is enabled, handle its regions too
        if world.options.quest_rando_pool.value == QuestRandoPool.option_quest_rando_sunbreak:
            unlock_m1 = world.get_entrance(MASTER_ENTRANCES[0])
            unlock_m2 = world.get_entrance(MASTER_ENTRANCES[1])
            unlock_m3 = world.get_entrance(MASTER_ENTRANCES[2])
            unlock_m4 = world.get_entrance(MASTER_ENTRANCES[3])
            unlock_m5 = world.get_entrance(MASTER_ENTRANCES[4])
            unlock_m6 = world.get_entrance(MASTER_ENTRANCES[5])

            world.set_rule(unlock_m1, urgent_rules_by_id[MR_TIER_URGENT_QUEST_NOS[QuestLevel.QL1]])
            world.set_rule(unlock_m2, urgent_rules_by_id[MR_TIER_URGENT_QUEST_NOS[QuestLevel.QL2]])
            world.set_rule(unlock_m3, urgent_rules_by_id[MR_TIER_URGENT_QUEST_NOS[QuestLevel.QL3]])
            world.set_rule(unlock_m4, urgent_rules_by_id[MR_TIER_URGENT_QUEST_NOS[QuestLevel.QL4]])
            world.set_rule(unlock_m5, urgent_rules_by_id[MR_TIER_URGENT_QUEST_NOS[QuestLevel.QL5]])
            world.set_rule(unlock_m6, urgent_rules_by_id[MR_TIER_URGENT_QUEST_NOS[QuestLevel.QL6]])

        # For mid urgents, grab the unlock condition from urgent_rules
        # For other quests, add own item rule and check if they are unlocked
        # by a mid urgent. if they are, add that mid_urgent as an unlock condition.
        for quest in world.quest_pool:
            # Handle urgent quests by skipping tier urgents and adding rules to mid urgents
            if quest["quest_no"] in urgent_rules_by_id:
                if quest["quest_no"] in MID_URGENT_QUEST_NOS:
                    for loc_name in quest_clear_location_names(quest):
                        world.set_rule(world.get_location(loc_name),urgent_rules_by_id[quest["quest_no"]])
                else:
                    continue

            # Handle other quests
            else:
                # Check if the quest is one of the key quests unlocked by a mid urgent
                # if it is, add the unlock rule for that mid urgent to the key quest's rule
                if quest["quest_no"] in key_quest_to_urgent and \
                 key_quest_to_urgent[quest["quest_no"]] in MID_URGENT_QUEST_NOS:
                    for loc_name in quest_clear_location_names(quest):
                        mid_urgent_rule = urgent_rules_by_id[key_quest_to_urgent[quest["quest_no"]]]
                        own_rule = Has(unlock_item_name(quest))
                        world.set_rule(world.get_location(loc_name), mid_urgent_rule & own_rule)
                # otherwise, just add the own item requirement
                else:
                    for loc_name in quest_clear_location_names(quest):
                        own_rule = Has(unlock_item_name(quest))
                        world.set_rule(world.get_location(loc_name), own_rule)

def set_completion_condition(world: MHRiseWorld) -> None:
    """The player has received the Victory item. Same condition both modes
    — what locks Victory differs (goal monster hunt vs Comeuppance clear)
    but Victory itself is the completion signal."""
    world.multiworld.completion_condition[world.player] = (
        lambda state: state.has("Victory", world.player)
    )


def set_urgent_rules(world: MHRiseWorld, quest_id_to_quest: dict[int,dict]) -> dict:
    """
    Create a rule set for each urgent quest
    Every urgent quest has the following rules
    Key rule: requires key_count unlock items for quests in key_list
    urgent_rule_one/two: if there are mid-urgents blocking this quest,
    add the rule for those mid-urgents to this quest's rule
    own_rule: every quest requires its own unlock
    """

    urgent_to_rule = {}
    for qn in URGENT_QUEST_DATA:
        # We can skip quests not in the quest_pool, but need to iterate 
        # over URGENT_QUEST_DATA instead of quest_pool to ensure
        # that quests in previous_urgents are always computed 
        # before they need to be referenced
        # We specifically need to allow The Blue Apex, as it is not in the quest pool
        # despite being a tier urgent.
        # TODO: This is stupid, fix it when you aren't drunk
        if qn == TBA_QUEST_NUMBER and world.options.quest_rando_pool.value != 0:
            pass
        elif qn not in quest_id_to_quest:
            continue

        # If the urgent requires key quests, set a rule requiring that number of key quests
        num_keys = URGENT_QUEST_DATA[qn]["key_count"]
        keys = [unlock_item_name(quest_id_to_quest[key_no]) for key_no in URGENT_QUEST_DATA[qn]["key_list"]]
        key_rule = HasFromList(count=num_keys, *keys) if num_keys and keys else True_()

        # If the urgent requires urgents other than the level gate,
        # set a rule requiring that those rules also be upheld
        # due to the order of URGENT_QUEST_DATA, the previous urgents
        # will always be defined in urgent_to_rule
        previous_urgents = URGENT_QUEST_DATA[qn]["previous_urgents"] # a list with 0 - 2 quest_nos
        urgent_rule_one = urgent_to_rule[previous_urgents[0]] if previous_urgents else True_()
        urgent_rule_two = urgent_to_rule[previous_urgents[1]] if len(previous_urgents) > 1 else True_()

        # All quests other than The Blue Apex require their own unlock item
        own_rule = Has(unlock_item_name(quest_id_to_quest[qn])) if qn != TBA_QUEST_NUMBER else True_()

        # Store the urgent quest rule for later
        urgent_to_rule[qn] = And(key_rule, urgent_rule_one, urgent_rule_two, own_rule)

    return urgent_to_rule # Always includes The Blue Apex, to ensure that hub/sunbreak quest rando will work
