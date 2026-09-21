"""Region graph for the MH Rise apworld.

huntathon currently has a single region, the origin region
Questathon has regions split by quest level, with each region
having an exit to the next quest level
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from .options import Mode, QuestRandoPool


from BaseClasses import Region, Entrance

if TYPE_CHECKING:
    from .world import MHRiseWorld


ORIGIN_REGION_NAME = "Origin"

VILLAGE_ENTRANCES = tuple(["Unlock V3", "Unlock V4", "Unlock V5"])
HUB_ENTRANCES = tuple(["Unlock H2", "Unlock H3", "Unlock H4", "Unlock H5", "Unlock H6", "Unlock H7"])
MASTER_ENTRANCES = tuple(["Unlock M1", "Unlock M2", "Unlock M3", "Unlock M4", "Unlock M5", "Unlock M6"])


def create_and_connect_regions(world: MHRiseWorld) -> None:
    all_regions = []
    origin = Region(ORIGIN_REGION_NAME, world.player, world.multiworld)
    all_regions.append(origin)

    # Quest rando regions are split by quest tier and level
    if world.options.mode.value == Mode.option_quest_rando:
        if world.options.quest_rando_pool.value == QuestRandoPool.option_quest_rando_village:
            # Create a region for each village quest tier from 3* to 4*
            # We'll use Origin for the starting tier V2*
            village_3 = Region("Village 3*", world.player, world.multiworld)
            origin.connect(village_3, VILLAGE_ENTRANCES[0])
            all_regions.append(village_3)

            village_4 = Region("Village 4*", world.player, world.multiworld)
            village_3.connect(village_4, VILLAGE_ENTRANCES[1])
            all_regions.append(village_4)

            village_5 = Region("Village 5*", world.player, world.multiworld)
            village_4.connect(village_5, VILLAGE_ENTRANCES[2])
            all_regions.append(village_5)

        else:
            # Both hub and sunbreak will have regions running up to 7*
            # Origin is H1* in both
            hub_2 = Region("Hub 2*", world.player, world.multiworld)
            origin.connect(hub_2, HUB_ENTRANCES[0])
            all_regions.append(hub_2)

            hub_3 = Region("Hub 3*", world.player, world.multiworld)
            hub_2.connect(hub_3, HUB_ENTRANCES[1])
            all_regions.append(hub_3)

            hub_4 = Region("Hub 4*", world.player, world.multiworld)
            hub_3.connect(hub_4, HUB_ENTRANCES[2])
            all_regions.append(hub_4)

            hub_5 = Region("Hub 5*", world.player, world.multiworld)
            hub_4.connect(hub_5, HUB_ENTRANCES[3])
            all_regions.append(hub_5)

            hub_6 = Region("Hub 6*", world.player, world.multiworld)
            hub_5.connect(hub_6, HUB_ENTRANCES[4])
            all_regions.append(hub_6)

            hub_7 = Region("Hub 7*", world.player, world.multiworld)
            hub_6.connect(hub_7, HUB_ENTRANCES[5])
            all_regions.append(hub_7)

            if world.options.quest_rando_pool.value == QuestRandoPool.option_quest_rando_sunbreak:
                # Add sunbreak exclusive master rank regions
                master_1 = Region("Master 1*", world.player, world.multiworld)
                hub_7.connect(master_1, MASTER_ENTRANCES[0])
                all_regions.append(master_1)

                master_2 = Region("Master 2*", world.player, world.multiworld)
                master_1.connect(master_2, MASTER_ENTRANCES[1])
                all_regions.append(master_2)

                master_3 = Region("Master 3*", world.player, world.multiworld)
                master_2.connect(master_3, MASTER_ENTRANCES[2])
                all_regions.append(master_3)

                master_4 = Region("Master 4*", world.player, world.multiworld)
                master_3.connect(master_4, MASTER_ENTRANCES[3])
                all_regions.append(master_4)

                master_5 = Region("Master 5*", world.player, world.multiworld)
                master_4.connect(master_5, MASTER_ENTRANCES[4])
                all_regions.append(master_5)

                master_6 = Region("Master 6*", world.player, world.multiworld)
                master_5.connect(master_6, MASTER_ENTRANCES[5])
                all_regions.append(master_6)

        world.multiworld.regions += all_regions
        world.region_names = [r.name for r in all_regions]


    # Currently, Huntathon has no additional regions, so just create the origin
    world.multiworld.regions += all_regions
    world.region_names = [r.name for r in all_regions]