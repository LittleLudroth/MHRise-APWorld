"""
Supplementary monster table for the MH Rise APworld

Splits large monsters by difficulty, either easy, medium, or hard. 
These catigorization were done manually, but generally follow the 
monster's first apperence in master rank. 1* and 2* quests went to easy,
3* and 4* quests went to medium, and 5*+ quests went to hard.

The file contains several sets of monster names, one for each difficulty tier

This file also contains a list of monsters who's AI breaks outside of master rank.
This list is used by quest rando to prevent these monsters from being swapped into
lower ranks.
"""
from __future__ import annotations
from typing import Any

EASY_MONSTERS: frozenset[str] = frozenset(
["Rathian",
"Khezu",
"Basarios",
"Barroth",
"Royal Ludroth",
"Great Baggi",
"Great Wroggi",
"Arzuros",
"Lagombi",
"Volvidon",
"Bishaten",
"Aknosom",
"Tetranadon",
"Somnacanth",
"Great Izuchi",
"Daimyo Hermitaur",
"Anjanath",
"Pukei-Pukei",
"Kulu-Ya-Ku",
"Jyuratodus",
"Tobi-Kadachi",
"Khezu",
"Blood Orange Bishaten"])

MEDIUM_MONSTERS: frozenset[str] = frozenset(
["Rathalos",
"Diablos",
"Tigrex",
"Nargacuga",
"Barioth",
"Zinogre",
"Mizutsune",
"Magnamalo",
"Rakna-Kadaki",
"Almudron",
"Goss Harag",
"Shogun Ceanataur",
"Lunagaron",
"Garangolm",
"Espinas",
"Seregios",
"Astalos",
"Gore Magala",
"Aurora Somnacanth",
"Pyre Rakna-Kadaki",
"Magma Almudron"]
)

HARD_MONSTERS: frozenset[str] = frozenset(
["Rajang",
"Kushala Daora",
"Chameleos",
"Teostra",
"Wind Serpent Ibushi",
"Thunder Serpent Narwa",
"Bazelgeuse",
"Velkhana",
"Malzeno",
"Gaismagorm",
"Shagaru Magala",
"Amatsu",
"Flaming Espinas",
"Gold Rathian",
"Silver Rathalos",
"Lucent Nargacuga",
"Violet Mizutsune",
"Furious Rajang",
"Chaotic Gore Magala",
"Crimson Glow Valstrax",
"Scorned Magnamalo",
"Narwa the Allmother",
"Seething Bazelgeuse",
"Primordial Malzeno",
"Risen Kushala Daora",
"Risen Chameleos",
"Risen Teostra",
"Risen Shagaru Magala",
"Risen Crimson Glow Valstrax"]
)

MASTER_RANK_ONLY_EMS: list[int] = [
    346, # Blood Orange Bishaten
    2075 # Risen Teostra
]