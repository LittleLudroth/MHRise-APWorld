"""WebWorld config — how the apworld appears on the AP website."""

from __future__ import annotations

from BaseClasses import Tutorial
from worlds.AutoWorld import WebWorld
from Options import OptionGroup
from . import options as mhrise_options

class MHRiseWebWorld(WebWorld):
    game = "Monster Hunter Rise"

    theme = "grass"

    setup_en = Tutorial(
        "Multiworld Setup Guide",
        "A guide to setting up Monster Hunter Rise for MultiWorld.",
        "English",
        "setup_en.md",
        "setup/en",
        ["SolomonW"],
    )

    tutorials = [setup_en]

    # Create option groups for the yaml
    # Core Options: general settings that apply to everything
    # Huntathon settings: specific options for huntathon
    # QuestRando settings: specific options for questrando
    # Weapon settings: settings related to randomzied weapons
    option_groups = [
        OptionGroup("Core Settings", [
            mhrise_options.Mode,
            mhrise_options.IncludeSunbreak,
            mhrise_options.IncludeRisen,
            mhrise_options.ExcludedMonsters,
            mhrise_options.Deathlink,
        ]),
        OptionGroup("Huntathon Settings", [
            mhrise_options.StartingMonsters,
            mhrise_options.GoalMonsters,
            mhrise_options.MonsterCount,
        ]),
        OptionGroup("QuestRando Settings", [
            mhrise_options.QuestRandoPool,
            mhrise_options.Questsanity,
            mhrise_options.RandomizeQuestMonsters
        ]),
        OptionGroup("Weapon Settings", [
            mhrise_options.IncludeWeapons,
            mhrise_options.WeaponPool,
            mhrise_options.StartingWeapons,
        ])
    ]
