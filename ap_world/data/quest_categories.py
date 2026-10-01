"""Supplementary quest table for the MH Rise AP world

Splits the quests from quests.py into catergories such as
key quests, urgent quests, and optional quests. These categorizations
had to be done by hand, and are necessary for the more complex unlock logic
of hub and master quest rando. 

There are several tables in this file, stored as either dictionaries or frozen sets
URGENT_QUEST_DATA is a dictionary mapping urgent quest_nos to a dictionary with the 
following data fields:
- key_count: the number of key quests needed to unlock this quest
- key_list: a list of key quest_nos that can contribute to unlocking the key quest
- previous_urgents: a list of quest numbers detailing which non-gate urgents preceed this urgent
- unlocked_quests: a list of quest_nos detailing which quests become available after
  completing the urgent quest
Note that for master rank quests, urgent quests have the 
key requirements for the previous urgents in the tier added
to their key requirements. This is to prevent logic from
thinking that two keys in a tier is enough for all urgents
while also allowing for keys unlocked by previous urgents
to be used for the next key requirement.

BANNED_QUESTS is a frozenset of quest numbers corresponding to otherwise valid quests
that we exclude from the randomizer. This includes support surveys, follower quests,
and other quests with excessive or annoying in-game unlock requirements

OPTIONAL_QUESTS is a frozenset of quest numbers corresponding to all optional quests
that aren't removed by banned_quests. This set allows us to exclude these quests unless
the questsanity option is enabled.

Note that the urgent rampages Serpent God of Wind and The Rampage Approaches are excluded
from these lists, as they are not locations. We only made The Blue Apex a location because
it directly unlocks a tier, and we would have liked to just skip it entirely.
"""
from __future__ import annotations
from enum import IntEnum, IntFlag
from typing import Any

URGENT_QUEST_DATA: dict[int, dict[str, Any]] = {
    # Feathered Frenzy (Aknosom)
    303:{"key_count":3,
         "key_list":[203,206,207],
         "previous_urgents":[],
         "unlocked_quests":[305,306,307,308,309,311]
         },
    # Monkey Wrench in Your Plans (Bishaten)
    402:{"key_count":4,
         "key_list":[305,306,307,308,309],
         "previous_urgents":[],
         "unlocked_quests":[403,404,405,406,407,408,409,411]
         },
    # Comeuppance (Magnamalo) — also the village goal
    501:{"key_count":5,
         "key_list":[404,405,406,407,408,409],
         "previous_urgents":[],
         "unlocked_quests":[]
         },
    # Dead Ringer (Tetranadon)
    10203:{"key_count":3,
           "key_list":[10104,10105,10106,10107,10108,10109],
           "previous_urgents":[],
           "unlocked_quests":[10204,10205,10206,10207,10208,10209,
                              10210,10211,10214]
           },
    # Hellfire (Magnamalo)
    10302:{"key_count":5,
           "key_list":[10204,10205,10206,10207,10208,10209,10210],
           "previous_urgents":[],
           "unlocked_quests":[10303,10304,10305,10306,10307,10308,
                              10309,10310,10311,10312,10313,10314,10315]
           },
    # The Blue Apex (Apex Arzuros)
    10403:{"key_count":6,
           "key_list":[10303,10304,10305,10306,10307,10308,10309,
                       10310,10311,10312,10313,10314],
           "previous_urgents":[],
           "unlocked_quests":[10404,10405,10406,10407,10408,10409,
                              10410,10411,10413,10414,10416,10417,10419,]
            },
    # The Restless Swamp (Jyuratodus)
    10503:{"key_count":5,
           "key_list":[10404,10405,10406,10407,10408,10409,10410,10411],
           "previous_urgents":[],
           "unlocked_quests":[10504,10505,10506,10507,10508,10509,10510,
                              10511,10512,10513,10515,10518,]
           },
    # A Bewitching Dance (Mizutsune)
    10602:{"key_count":5,
           "key_list":[10504,10505,10506,10507,10508,10509,10510],
           "previous_urgents":[],
           "unlocked_quests":[10604,10605,10606,10607,10608,10609,
                              10610,10612,10613,10614,10615,10616,]
           },
    # Can't Kill It with Fire (Rakna-kadaki)
    10701:{"key_count":5,
           "key_list":[10604,10605,10606,10607,10608,10609,10610],
           "previous_urgents":[],
           "unlocked_quests":[10708,10709,10710,10711,10712,10713,
                              10714,10715,10716,10717,10718,10719,10721]
           },
    # Serpent Goddess of Thunder (Narwa) - also the hub goal
    10702:{"key_count":5,
           "key_list":[10708,10709,10710,10711,10712,10713],
           "previous_urgents":[],
           "unlocked_quests":[]
           },
    # Uninvited Guest (Damiyo Hermitaur)
    315100:{"key_count":0,
            "key_list":[],
            "previous_urgents":[10702],
            "unlocked_quests":[315102,315103,315104,315108,315122,315160]
            },
    # Tetranadon Blockade (Tetranadon)
    315190:{"key_count":2,
            "key_list":[315102,315103,315104],
            "previous_urgents":[],
            "unlocked_quests":[315109,315110,315111,315112,315113]
            },
    # Scarlet Tengu in the Shrine Ruins (Blood Orange Bishaten)
    405200:{"key_count":4,
            "key_list":[315109,315110,315111,315112,315113,315102,
                        315103,315104],
            "previous_urgents":[315190],
            "unlocked_quests":[315201,315202,315203,315204,315224,
                               315200,315212,315214,315216,315219,
                               315260,315261]
            },
    # Provoking an Anjanath's Wrath (Anjanath)
    315290:{"key_count":2,
            "key_list":[315201,315202,315203,315204,315224],
            "previous_urgents":[],
            "unlocked_quests":[315205,315206,315207,315208]
            },
    # A Rocky Rampage (Garangolm)
    405300:{"key_count":4,
            "key_list":[315201,315202,315203,315204,315224,
                        315205,315206,315207,315208],
            "previous_urgents":[315290],
            "unlocked_quests":[315301,315302,315303,315304,315305,
                               315315,315313,315321,315323,315360,]
            },
    # Keep it Busy (Aurora Somnacanth)
    315390:{"key_count":2,
            "key_list":[315301,315302,315303,315304,315305],
            "previous_urgents":[],
            "unlocked_quests":[315306,315307,315308,315309,315310]
            },
    # Ice Wolf, Red Moon (Lunagaron)
    405400:{"key_count":4,
            "key_list":[315301,315302,315303,315304,315305,
                        315306,315307,315308,315309,315310],
            "previous_urgents":[315390],
            "unlocked_quests":[315401,315402,315403,315404,315400,
                               315414,315415,315416,315417,315425,
                               315426,315427,315460,315461]
            },
    # In Search of the Doctor (Astalos)
    315490:{"key_count":2,
            "key_list":[315401,315402,315403,315404],
            "previous_urgents":[],
            "unlocked_quests":[315406,315407,315408,315409]
            },
    # A Slumbering Jungle Espinas (Espinas)
    315491:{"key_count":4,
            "key_list":[315401,315402,315403,315404,315406,315407,
                        315408,315409],
            "previous_urgents":[315490],
            "unlocked_quests":[315418,315419,315420,315421]
            },
    # Witness by Moonlight (Malzeno)
    405500:{"key_count":6,
            "key_list":[315401,315402,315403,315404,315406,315407,
                        315408,315409,315418,315419,315420,315421],
            "previous_urgents":[315490, 315491],
            "unlocked_quests":[315501,315502,315503,315504,315500,
                               315512,315525,315524,315561,]
            },
    # Dark Citadel, White Wheel (Shagaru Magala)
    315590:{"key_count":2,
            "key_list":[315501,315502,315503,315504],
            "previous_urgents":[],
            "unlocked_quests":[315507,315509,315511]
            },
    # Gathering of the Qurio (Lunagaron)
    315591:{"key_count":4,
            "key_list":[315501,315502,315503,315504,315507,
                        315509,315511],
            "previous_urgents":[315590],
            "unlocked_quests":[]
            },
    # Proof of Courage (Gaismagorm) - also the MR goal
    405600:{"key_count":0,
            "key_list":[],
            "previous_urgents":[],
            "unlocked_quests":[]
            },
}

# All quest_nos with operation in the english name, which includes all support surveys
# and a few other quests that are dropped for being boss rushes anyway
_SUPPORT_SURVEY_QUEST_NOS = (455201,455202,455203,455204,455205,455206,455301,455302,
                             455303,455305,455306,455307,455308,455310,455312,455313,
                             455401,455402,455403,455406,455407,455408,455409,455410,
                             455411,455412,455414,455501,455503,455504,455505,455506,
                             455508,455510,455511,455512,455513,)

# All hunting quest Follower Quest Nos, found by comparing a list of hunting quests
# to a list of key/urgent quests and a list of non-follower optional quests and marking
# any values in neither as a Follower Quest
_FOLLOWER_QUEST_QUEST_NOS = (465201,465202,465203,465301,465302,465305,465306,465307,
                             465308,465309,455413,465401,465402,465403,465404,465405,
                             465406,465407,465408,465409,465410,465501,465502,465504,
                             465505,465506,465507,)

# Currently removes Do It for the Dango (since it's locked behind comeuppance)
# Also removes Beyond the Silence, Emperor of Flame, and Storm of The Kushala Daora 
# since they aren't unlocked by an urgent and I don't want to deal with it
_OTHER_BANNED_QUESTS = (10611,315506,315510,315508,)

# A frozenset of banned quests, including support surveys, follower quests, and other 
# quests with annoying unlock conditions
BANNED_QUESTS = frozenset(_SUPPORT_SURVEY_QUEST_NOS + _FOLLOWER_QUEST_QUEST_NOS + _OTHER_BANNED_QUESTS)

# A frozenset of all non-banned optional quests, used to indicate which quests should be added 
# as locations for questsanity 
OPTIONAL_QUESTS = frozenset((# Village Optionals
                             311,403,411,
                             # HR Optionals
                             10110,10211,10214,10315,10413,10414,10416,10417,10419, 
                             10511,10512,10513,10515,10518,10612,10613,10614,10615,
                             10616,10714,10715,10716,10717,10718,10719,10721,
                             # MR optionals
                             315108,315122,315160,315200,315212,315214,315216,315219,
                             315260,315261,315315,315313,315321,315323,315360,315400,
                             315414,315415,315416,315417,315425,315426,315427,315460,
                             315461,315500,315512,315525,315524,315561,315220,315318,
                             315429,315523,))

# A frozenset of all optional gathering/small monster quests. Used to indicate whether or not
# a quest should be included as part of questsanity_nonhunting
# Also used to ensure that these quests are not put in quest_swaps
OPTIONAL_NONHUNTING_QUESTS = frozenset(())