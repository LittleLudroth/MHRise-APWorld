"""Item table for the MH Rise apworld.

Spans two modes (see options.py:Mode):
- HuntAThon: one license item per curated monster. Hunting the monster
  sends checks; license soft-gates.
- QuestRando: one `Unlock: <quest>` item per village quest in the
  active pool, plus weapon licenses when enabled. Clearing a quest
  sends checks only when the player holds both the matching unlock
  AND (if weapons enabled) the wielded weapon's license. Soft gate at
  clear time — engine drives in-game quest visibility.

IDs are static and known at module import time so the AP datapackage is
stable across seeds AND across option/mode choices.

ID layout:
- 1..N: monster license items. Order is `MONSTERS + APEX_MONSTERS +
       SMALL_MONSTERS`, so existing IDs are preserved if a future option
       merges Apex or Small into the active pool. event_id=0 -> id=1 to
       keep us off the AP-reserved id 0 sentinel.
- 2000..2999: QuestRando `Unlock: <quest>` items, one per entry in the
       filtered village pool (`QUESTRANDO_VILLAGE_QUESTS`), indexed by
       position. Items and locations live in separate AP namespaces, so
       the 2000+ id space is shared between this and the Clear locations
       in locations.py — no collision.
- 3000..3999: QuestRando `Unlock: <quest>` items for hub quests, one per
        entry in the filtered hub pool (`QUESTRANDO_HUB_QUESTS`), indexed
        by position. 
- 4000..4999: QuestRando `Unlock: <quest>` items for master rank quests, one per
        entry in the filtered mr hub pool (`QUESTRANDO_MR_QUESTS`), indexed
        by position. 
- 9001: Victory (delivered when the goal monster is hunted in HuntAThon
       or when Comeuppance clears in QuestRando).
- 9100..9113: weapon license items (14 contiguous, indexed by WEAPONS
       order). Parked alongside the existing fixed-id items so they
       don't collide with the monster range or the future Apex/Small
       reservations.
- 9999: Poogie (filler).

The Lua client receives the EmType / quest-id maps via slot_data on
connect, so it never needs to read the master tables from disk.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification

from .data.monsters import MONSTERS, APEX_MONSTERS, SMALL_MONSTERS
from .data.quests import QUESTS, EnemyLv, QuestLevel, QuestType
from .data.weapons import WEAPONS
from .data.quest_categories import OPTIONAL_QUESTS, BANNED_QUESTS
from .options import Mode, QuestRandoPool

if TYPE_CHECKING:
    from .world import MHRiseWorld


# Full universe of curated monsters. Stable ordering matters here — IDs are
# assigned by position, so prepending or reordering buckets would break the
# datapackage for existing seeds.
ALL_CURATED_MONSTERS: tuple[dict, ...] = MONSTERS + APEX_MONSTERS + SMALL_MONSTERS

# quest_no for the village goal quest ("Comeuppance"). Confirmed against the
# vanilla catalog; intentionally hardcoded by quest_no rather than
# looked up by name because the `name` field is locale-dependent.
COMEUPPANCE_QUEST_NO = 501

# quest_no for the hub goal quest ("Serpent Goddess of Thunder").
# Confirmed against the vanilla catalog; intentionally hardcoded
# by quest_no rather than looked up by name because the `name`
# field is locale-dependent.
SGOT_QUEST_NUMBER = 10702

# quest_no for the MR goal quest ("Proof of Courage"). Confirmed against the
# vanilla catalog; intentionally hardcoded by quest_no rather than
# looked up by name because the `name` field is locale-dependent.
POC_QUEST_NUMBER = 405600

# quest_no for the only required rampage quest in progression (The Blue Apex)
# Confirmed against the vanilla catalog; intentionally hardcoded by quest_no
# rather than looked up by name because the `name` field is locale-dependent.
TBA_QUEST_NUMBER = 10403

# quest_no for the starter village quest, precollected so the player can
# do at least one hunt from t=0. QL1 is all training (excluded), so the
# starter is the first real QL2 hunt: Great Izuchi, Great Pain.
STARTER_QUEST_NO = 202

# quest_no for the starter hub quest, precollected so the player can
# do at least one hunt from t=0. the starter is the first real QL1 hunt: Shady Monster.
HUB_STARTER_QUEST_NO = 10104

# Per-tier urgent quest_nos for MR. The in game unlock requirements 
# for these urgent quests are used as entrance requirements 
# for the region corresponding to that quest level
#
# QL2 has no prior urgent (its "urgent" is the precollected starter at
# quest_no=202). QL6 is excluded from the pool entirely (only the goal
# at QL5 / quest_no=501 lives above QL4).
TIER_URGENT_QUEST_NOS: dict[QuestLevel, int] = {
    QuestLevel.QL3: 303,  # Feathered Frenzy (Aknosom)
    QuestLevel.QL4: 402,  # Monkey Wrench in Your Plans (Bishaten)
    QuestLevel.QL5: 501,  # Comeuppance (Magnamalo) — also the goal
}

# Per-tier urgent quest_nos for MR. The in game unlock requirements 
# for these urgent quests are used as entrance requirements 
# for the region corresponding to that quest level
#
# QL1 has no prior urgent
# QL7EX is excluded from the pool, as the goal quest is also the unlock
HUB_TIER_URGENT_QUEST_NOS: dict[QuestLevel, int] = {
    QuestLevel.QL2: 10203,  # Dead Ringer (Tetranadon)
    QuestLevel.QL3: 10302,  # Hellfire (Magnamalo)
    QuestLevel.QL4: 10403,  # The Blue Apex (Apex Arzuros)
    QuestLevel.QL5: 10503,  # The Restless Swamp (Jyuratodus)
    QuestLevel.QL6: 10602,  # A Bewitching Dance (Mizutsune)
    QuestLevel.QL7: 10701,  # Can't Kill It with Fire
    QuestLevel.QL7EX: 10702,  # Serpent Goddess of Thunder (Narwa) - also the hub goal
}

# Per-tier urgent quest_nos for MR. The in game unlock requirements 
# for these urgent quests are used as entrance requirements 
# for the region corresponding to that quest level
MR_TIER_URGENT_QUEST_NOS: dict[QuestLevel, int] = {
    QuestLevel.QL1: 315100,  # Uninvited Guest (Damiyo Hermitaur)
    QuestLevel.QL2: 405200,  # Scarlet Tengu in the Shrine Ruins (Blood Orange Bishaten)
    QuestLevel.QL3: 405300,  # A Rocky Rampage (Garangolm)
    QuestLevel.QL4: 405400,  # Ice Wolf, Red Moon (Lunagaron)
    QuestLevel.QL5: 405500,  # Witness by Moonlight (Malzeno)
    QuestLevel.QL6: 405600,  # Proof of Courage (Gaismagorm) - also the MR goal
}

FULL_TIER_URGENT_QUEST_NOS: dict[tuple[QuestLevel, EnemyLv], int] = {
    (QuestLevel.QL3, EnemyLv.Village): 303,  # Feathered Frenzy (Aknosom)
    (QuestLevel.QL4, EnemyLv.Village): 402,  # Monkey Wrench in Your Plans (Bishaten)
    (QuestLevel.QL5, EnemyLv.Village): 501,  # Comeuppance (Magnamalo) — also the goal
    (QuestLevel.QL2, EnemyLv.Low): 10203,  # Dead Ringer (Tetranadon)
    (QuestLevel.QL3, EnemyLv.Low): 10302,  # Hellfire (Magnamalo)
    (QuestLevel.QL4, EnemyLv.High): 10403,  # The Blue Apex (Apex Arzuros)
    (QuestLevel.QL5, EnemyLv.High): 10503,  # The Restless Swamp (Jyuratodus)
    (QuestLevel.QL6, EnemyLv.High): 10602,  # A Bewitching Dance (Mizutsune)
    (QuestLevel.QL7, EnemyLv.High): 10701,  # Can't Kill It with Fire
    (QuestLevel.QL7EX, EnemyLv.High): 10702,  # Serpent Goddess of Thunder (Narwa) - also the hub goal
    (QuestLevel.QL1, EnemyLv.Master): 315100,  # Uninvited Guest (Damiyo Hermitaur)
    (QuestLevel.QL2, EnemyLv.Master): 405200,  # Scarlet Tengu in the Shrine Ruins (Blood Orange Bishaten)
    (QuestLevel.QL3, EnemyLv.Master): 405300,  # A Rocky Rampage (Garangolm)
    (QuestLevel.QL4, EnemyLv.Master): 405400,  # Ice Wolf, Red Moon (Lunagaron)
    (QuestLevel.QL5, EnemyLv.Master): 405500,  # Witness by Moonlight (Malzeno)
    (QuestLevel.QL6, EnemyLv.Master): 405600,  # Proof of Courage (Gaismagorm) - also the MR goal
}

# Mid-Urgent quests that don't unlock a new tier of quests (in logic).
# This set is used in rules.py to determine which key quests
# have unlock requirements beyond access to the region
MID_URGENT_QUEST_NOS: frozenset[int] = frozenset([
    10702,  # Serpent Goddess of Thunder (Narwa)
    315190, # Tetranadon Blockade (Tetranadon)
    315290, # Provoking an Anjanath's Wrath (Anjanath)
    315390, # Keep it Busy (Aurora Somnacanth)
    315490, # In Search of the Doctor (Astalos)
    315491, # A Slumbering Jungle Espinas (Espinas)
    315590, # Dark Citadel, White Wheel (Shagaru Magala)
])

_HUNTING_QUEST_TYPES = QuestType.HUNTING | QuestType.KILL | QuestType.CAPTURE

# em_types of the large, randomizable monsters. A quest only belongs in
# the QuestRando pool if BOTH its boss AND its clear-target are large —
# some "hunt a large boss" village quests actually clear on a SMALL
# monster (e.g. Ladies of the Lake clears on Ludroth, THE BEST Quest on
# Rachnoid). Swapping the boss on those breaks completion (gh #19), so
# they're filtered out. monster_bucket alone misses them because it's
# derived from boss_em_type, not target_em_type.
_LARGE_MONSTER_EM_TYPES: frozenset[int] = frozenset(m["em_type"] for m in MONSTERS)


def _in_questsanity_pool(quest: dict) -> bool:
    """Filter used identically by items, locations, and generate_early
    so static IDs stay aligned with the dynamic seed's quest_pool.

    Pool: every Village quest with a real boss-monster bucket, whose
    quest_type is one of HUNTING / KILL / CAPTURE (so gather quests
    like 'Plump and Juicy' and arena chains like 'Third Wheel' are
    excluded — clearing those doesn't reduce to 'kill the swapped
    boss'), and no QL5/QL6 entries except the goal itself
    (quest_no=501). Quests whose boss OR clear-target is a small
    monster are excluded (gh #19) — swapping their boss makes them
    uncompletable."""
    if quest["quest_no"] in BANNED_QUESTS:
        return False
    if quest["enemy_level"] != EnemyLv.Village:
        return False
    if quest["monster_bucket"] != "monster":
        return False
    # Both the spawned boss AND the clear-target must be large monsters.
    # Some village "hunt" quests clear on a small monster (gh #19) — the
    # boss swap would make them uncompletable, so exclude them.
    if quest["boss_em_type"] not in _LARGE_MONSTER_EM_TYPES:
        return False
    if quest["target_em_type"] not in _LARGE_MONSTER_EM_TYPES:
        return False
    if not (quest["quest_type"] & _HUNTING_QUEST_TYPES):
        return False
    if quest["quest_level"] in (QuestLevel.QL5, QuestLevel.QL6):
        return quest["quest_no"] == COMEUPPANCE_QUEST_NO
    return True

def _in_questrando_pool(quest: dict) -> bool:
    """
    Filter used identically by items, locations, and generate_early
    so static IDs stay aligned with the dynamic seed's quest_pool.

    Same as _in_questsanity_pool but also excludes optional quests
    """
    if quest["quest_no"] in OPTIONAL_QUESTS:
        return False
    else:
        return _in_questsanity_pool(quest)

def _in_questsanity_hub_pool(quest: dict) -> bool:
    """
    Filter used identically by items, locations, and generate_early
    so static IDs stay aligned with the dynamic seed's quest_pool.

    Pool: every low/high rank hub quest with a real boss-monster bucket, whose
    quest_type is one of HUNTING / KILL / CAPTURE (so gather quests
    like 'Plump and Juicy' and arena chains like 'Third Wheel' are
    excluded — clearing those doesn't reduce to 'kill the swapped
    boss'), with the goal being Serpent Goddess of Thunder (quest_no=10702).
    Rampage quests are also excluded, with necessary progression rampages being 
    added manually. Quests in QL7EX are excluded, since they are gated by hunter
    rank grinding. A Quests whose boss OR clear-target is a small monster are
    excluded (gh #19), as swapping their boss makes them uncompletable.
    """
    if quest["quest_no"] in BANNED_QUESTS:
        return False
    if quest["quest_no"] in OPTIONAL_QUESTS:
        return False
    if quest["quest_no"] == TBA_QUEST_NUMBER:
        return True # This sucks, but TBA specifically needs to be except
    if quest["enemy_level"] != EnemyLv.Low and quest["enemy_level"] != EnemyLv.High:
        return False
    if quest["monster_bucket"] != "monster":
        return False
    # Both the spawned boss AND the clear-target must be large monsters.
    # Some hub "hunt" quests clear on a small monster (gh #19) — the
    # boss swap would make them uncompletable, so exclude them.
    if quest["boss_em_type"] not in _LARGE_MONSTER_EM_TYPES:
        return False
    if quest["target_em_type"] not in _LARGE_MONSTER_EM_TYPES:
        return False
    if not (quest["quest_type"] & _HUNTING_QUEST_TYPES):
        return False
    if quest["quest_level"] == QuestLevel.QL7EX:
        return False
    return True

def _in_questrando_hub_pool(quest: dict) -> bool:
    """
    Filter used identically by items, locations, and generate_early
    so static IDs stay aligned with the dynamic seed's quest_pool.

    Same as _in_questsanity_hub_pool but also excludes optional quests
    """
    if quest["quest_no"] in OPTIONAL_QUESTS:
        return False
    else:
        return _in_questsanity_hub_pool(quest)

def _in_questsanity_mr_pool(quest: dict) -> bool:
    """
    Filter used identically by items, locations, and generate_early
    so static IDs stay aligned with the dynamic seed's quest_pool.

    Pool: every master rank hub quest with a real boss-monster bucket,
    whose quest_type is one of HUNTING / KILL / CAPTURE (so gather quests
    like 'Plump and Juicy' and arena chains like 'Third Wheel' are
    excluded — clearing those doesn't reduce to 'kill the swapped
    boss'), with the goal being Proof of Courage (quest_no=405600). 
    Quests in QL7EX are excluded, since they are gated by hunter rank grinding.
    Quests in MR6 other than Proof of Courage are excluded, since they are blocked
    behind the goal quest. A Quests whose boss OR clear-target is a small monster
    are excluded (gh #19), as swapping their boss makes them uncompletable.
    """
    if quest["quest_no"] in BANNED_QUESTS:
        return False
    if quest["quest_no"] in OPTIONAL_QUESTS:
        return False
    if quest["enemy_level"] != EnemyLv.Master:
        return False
    if quest["monster_bucket"] != "monster":
        return False
    # Both the spawned boss AND the clear-target must be large monsters.
    # Some hub "hunt" quests clear on a small monster (gh #19) — the
    # boss swap would make them uncompletable, so exclude them.
    if quest["boss_em_type"] not in _LARGE_MONSTER_EM_TYPES:
        return False
    if quest["target_em_type"] not in _LARGE_MONSTER_EM_TYPES:
        return False
    if not (quest["quest_type"] & _HUNTING_QUEST_TYPES):
        return False
    if quest["quest_level"] == QuestLevel.QL7EX:
        return False
    if quest["quest_level"] == QuestLevel.QL6 and quest["enemy_level"] == EnemyLv.Master:
        return quest["quest_no"] == POC_QUEST_NUMBER
    return True

def _in_questrando_mr_pool(quest: dict) -> bool:
    """
    Filter used identically by items, locations, and generate_early
    so static IDs stay aligned with the dynamic seed's quest_pool.

    Same as _in_questsanity_mr_pool but also excludes optional quests
    """
    if quest["quest_no"] in OPTIONAL_QUESTS:
        return False
    else:
        return _in_questsanity_mr_pool(quest)

# Quests included in the Village Questsanity pool
QUESTSANITY_VILLAGE_QUESTS: tuple[dict, ...] = tuple(
    q for q in QUESTS if _in_questsanity_pool(q)
)

# Quests included in the Hub Questsanity pool
QUESTSANITY_HUB_QUESTS: tuple[dict, ...] = tuple(
    q for q in QUESTS if _in_questsanity_hub_pool(q)
)

# Quests included in the Sunbreak Questsanity pool
QUESTSANITY_MR_QUESTS: tuple[dict, ...] = tuple(
    q for q in QUESTS if _in_questsanity_mr_pool(q)
)

# Legacy alias retained for any external consumer; safe to remove once
# nothing imports it directly. Currently used by locations.py.
VILLAGE_QUESTS: tuple[dict, ...] = QUESTSANITY_VILLAGE_QUESTS

FILLER_ITEM_NAME = "Poogie"

WEAPON_LICENSE_ID_BASE = 9100
QUEST_UNLOCK_ID_BASE = 2000
HUB_QUEST_UNLOCK_ID_BASE = 3000
MR_QUEST_UNLOCK_ID_BASE = 4000


def quest_display_name(quest: dict) -> str:
    """Display name for a quest. Prefers the localized `name`; falls
    back to `dbg_name` when the dumper couldn't resolve it (some 33
    no-monster entries lack a resolved name)."""
    return quest["name"] if quest["name"] is not None else quest["dbg_name"]


def unlock_item_name(quest: dict) -> str:
    """AP item name for a quest unlock."""
    return f"Unlock: {quest_display_name(quest)}"


ITEM_NAME_TO_ID: dict[str, int] = {}

for _i, _monster in enumerate(ALL_CURATED_MONSTERS):
    _id = _i + 1
    assert _id != 0, "AP reserves item id 0 as invalid"
    _name = f"{_monster['name']} License"
    assert _name not in ITEM_NAME_TO_ID, f"duplicate license name {_name}"
    ITEM_NAME_TO_ID[_name] = _id

for _i, _quest in enumerate(QUESTSANITY_VILLAGE_QUESTS):
    _id = QUEST_UNLOCK_ID_BASE + _i
    assert _id < 9000, "QuestRando village quest count overflowed reserved range"
    _name = unlock_item_name(_quest)
    assert _name not in ITEM_NAME_TO_ID, f"duplicate unlock item name {_name}"
    ITEM_NAME_TO_ID[_name] = _id

for _i, _quest in enumerate(QUESTSANITY_HUB_QUESTS):
    _id = HUB_QUEST_UNLOCK_ID_BASE + _i
    assert _id < 9000, "QuestRando hub quest count overflowed reserved range"
    _name = unlock_item_name(_quest)
    assert _name not in ITEM_NAME_TO_ID, f"duplicate unlock item name {_name}"
    ITEM_NAME_TO_ID[_name] = _id

for _i, _quest in enumerate(QUESTSANITY_MR_QUESTS):
    _id = MR_QUEST_UNLOCK_ID_BASE + _i
    assert _id < 9000, "QuestRando MR quest count overflowed reserved range"
    _name = unlock_item_name(_quest)
    assert _name not in ITEM_NAME_TO_ID, f"duplicate unlock item name {_name}"
    ITEM_NAME_TO_ID[_name] = _id



ITEM_NAME_TO_ID["Victory"] = 9001
ITEM_NAME_TO_ID[FILLER_ITEM_NAME] = 9999

for _i, _weapon in enumerate(WEAPONS):
    _name = f"{_weapon['name']} License"
    assert _name not in ITEM_NAME_TO_ID, f"duplicate license name {_name}"
    ITEM_NAME_TO_ID[_name] = WEAPON_LICENSE_ID_BASE + _i


# Precomputed lookup: quest unlock item name -> quest dict. Used by
# classification to tag the goal-quest unlock with skip-balancing.
_UNLOCK_NAME_TO_QUEST: dict[str, dict] = {
    unlock_item_name(q): q for q in QUESTSANITY_VILLAGE_QUESTS + QUESTSANITY_HUB_QUESTS + QUESTSANITY_MR_QUESTS
}


def license_item_name(monster: dict) -> str:
    """Return the AP item name for the license of a given monster."""
    return f"{monster['name']} License"


def weapon_license_item_name(weapon: dict) -> str:
    """Return the AP item name for the license of a given weapon type."""
    return f"{weapon['name']} License"


class MHRiseItem(Item):
    game = "Monster Hunter Rise"


_WEAPON_LICENSE_NAMES = frozenset(weapon_license_item_name(w) for w in WEAPONS)


def create_item_with_correct_classification(world: MHRiseWorld, name: str) -> MHRiseItem:
    if name == FILLER_ITEM_NAME:
        classification = ItemClassification.filler
    elif name == "Victory":
        # Skip-balancing on the goal item — receiving it ends the run,
        # so AP's progression balancer pulling it forward to relieve
        # another player's BK collapses pacing.
        classification = ItemClassification.progression_skip_balancing
    elif (
        world.options.mode.value == Mode.option_hunt_a_thon
        and getattr(world, "goal_monster", None) is not None
        and name == license_item_name(world.goal_monster)
    ):
        # HuntAThon: the goal monster's license gates Victory. Same
        # skip-balancing logic as Victory itself.
        classification = ItemClassification.progression_skip_balancing
    elif (
        world.options.mode.value == Mode.option_quest_rando
        and getattr(world, "goal_quest", None) is not None
        and name == unlock_item_name(world.goal_quest)
    ):
        # QuestRando: the goal quest's unlock gates Victory. Same
        # skip-balancing logic as HuntAThon's goal-monster license.
        classification = ItemClassification.progression_skip_balancing
    elif name in _UNLOCK_NAME_TO_QUEST:
        # Quest unlocks gate per-quest Clear locations (see rules.py).
        classification = ItemClassification.progression
    elif name in _WEAPON_LICENSE_NAMES:
        # Weapon licenses are soft-gated client-side only (no apworld
        # rules reference them). Marking them progression makes fill
        # treat them as gating items competing for reachable locations,
        # which over-constrains placement at low monster_count and
        # produces FillError. `useful` keeps them prioritized for
        # placement without entering the progression-balancing math.
        classification = ItemClassification.useful
    else:
        # Monster licenses are progression — each one gates the player's
        # access to its monster's hunt locations.
        classification = ItemClassification.progression
    return MHRiseItem(name, classification, ITEM_NAME_TO_ID[name], world.player)


def get_filler_item_name() -> str:
    """Wrapped by `MHRiseWorld.get_filler_item_name(self)`. Called by AP
    whenever it needs an extra filler item — e.g. when the item pool is
    short relative to location count, or for plando."""
    return FILLER_ITEM_NAME


def place_victory(world: MHRiseWorld) -> None:
    """Lock the Victory item at the mode-appropriate goal location.

    Runs before `create_all_items` counts unfilled locations so the goal
    slot is excluded from the filler math (locked items don't go into the
    multiworld itempool).

    - HuntAThon: goal monster's (2/2) hunt location.
    - QuestRando: Comeuppance's clear location.
    """
    if world.options.mode.value == Mode.option_quest_rando:
        from .locations import quest_clear_location_names

        goal_loc_name = quest_clear_location_names(world.goal_quest)[1]  # (2/2)
    else:
        from .locations import hunt_location_names

        goal_loc_name = hunt_location_names(world.goal_monster)[1]  # (2/2)
    location = world.get_location(goal_loc_name)
    location.place_locked_item(create_item_with_correct_classification(world, "Victory"))


def create_all_items(world: MHRiseWorld) -> None:
    """Dispatch on mode."""
    if world.options.mode.value == Mode.option_quest_rando:
        if world.options.quest_rando_pool.value == QuestRandoPool.option_quest_rando_village:
            _create_items_questrando(world)
        else:
            _create_items_questrando_hub(world) # hub and mr questrando share the same starting quests
    else:
        _create_items_huntathon(world)


def _create_items_huntathon(world: MHRiseWorld) -> None:
    """Build the item pool.

    For N = len(world.seed_monsters), the multiworld will create 2N
    locations. `place_victory` consumes one of them (locked, no itempool
    slot), so 2N-1 itempool slots need filling. Of those:

    - N-1 monster licenses (the starter's license is precollected).
    - "Spare" slots = N. Filled, in priority order, by:
      1. The starter weapon license (precollected if weapons enabled).
      2. Up to (spare - 1) random non-starter weapon licenses (if
         weapons enabled), capped at 13. The (spare - 1) cap reserves
         at least one slot for Poogie filler so AP's excluded-location
         fill has something to draw from — the goal monster's two
         hunt locations are EXCLUDED (see locations.py), and AP's
         excluded fill only consumes filler items (not `useful` like
         weapon licenses, not `progression` like monster licenses).
      3. Poogie filler for any leftover slots.

    Spare ≥ 3 is guaranteed by the option floor of monster_count=3.
    """
    place_victory(world)

    starting_name = world.starting_monster["name"]

    itempool: list[Item] = []
    precollected: list[MHRiseItem] = []

    for monster in world.seed_monsters:
        item_name = license_item_name(monster)
        item = create_item_with_correct_classification(world, item_name)
        if monster["name"] == starting_name:
            precollected.append(item)
        else:
            itempool.append(item)

    # Spare slot count = unfilled locations (Victory already locked) minus
    # the monster licenses we just placed in the pool.
    unfilled = len(world.multiworld.get_unfilled_locations(world.player))
    spare = unfilled - len(itempool)
    assert spare >= 1, "spare-slot invariant broken (need ≥1 slot beyond licenses)"

    # Weapon licenses (when enabled). Starter is always precollected,
    # never truncated. The non-starter pool is drawn from
    # `world.weapon_pool` (the weapon_pool option's resolved subset),
    # shuffled and as many as fit go into the pool — when
    # monster_count is small or weapon_pool is small, we drop the rest.
    #
    # Reserve 1 spare slot for filler so that the goal monster's (1/2)
    # location (marked EXCLUDED in locations.py) can be filled. AP's
    # excluded-location fill pulls from the filler pool only —
    # `useful`-classified weapon licenses don't qualify, so without a
    # reserved filler the gen fails with "Not enough filler items for
    # excluded locations".
    if bool(world.options.include_weapons.value):
        # confirm starting_weapon is defined, should always pass
        assert world.starting_weapon is not None

        starting_weapon_name = world.starting_weapon["name"]
        precollected.append(create_item_with_correct_classification(
            world, weapon_license_item_name(world.starting_weapon)))
        non_starter_weapons = [
            w for w in world.weapon_pool if w["name"] != starting_weapon_name
        ]
        world.random.shuffle(non_starter_weapons)
        weapon_budget = max(spare - 1, 0)
        weapons_to_add = non_starter_weapons[:weapon_budget]
        for weapon in weapons_to_add:
            itempool.append(create_item_with_correct_classification(
                world, weapon_license_item_name(weapon)))
        spare -= len(weapons_to_add)

    # Poogie filler mops up any leftover slots.
    for _ in range(spare):
        itempool.append(create_item_with_correct_classification(world, FILLER_ITEM_NAME))

    world.multiworld.itempool += itempool
    for item in precollected:
        world.push_precollected(item)


def _create_items_questrando(world: MHRiseWorld) -> None:
    """Build the QuestRando item pool.

    Topology for V = len(world.quest_pool) village quests:
    - 2V `Clear: <name> (n/2)` locations (mirrors HuntAThon's two-slot
      pattern; both fire on the same in-game clear event).
    - place_victory locks Victory at goal Clear (2/2) → 2V-1 unfilled
      locations to fill.
    - V `Unlock: <name>` items, one per quest. Starter (quest_no=202)
      is precollected; goal unlock is also placed but treated as
      skip-balancing.
    - Spare slots = (2V-1) - (V-1) = V slots beyond the quest unlocks.
      Filled in priority order:
        1. Starter weapon license (precollected) if weapons enabled.
        2. Up to (spare-1) random non-starter weapon licenses, capped
           at 13. The (spare-1) cap reserves at least one Poogie slot
           for AP's excluded-location fill (goal Clear (1/2) is
           EXCLUDED — weapon licenses are `useful`, not filler, so
           excluded fill rejects them).
        3. Poogie filler for leftover slots.
    """
    place_victory(world)

    starter_quest_name = quest_display_name(world.starting_quest)

    # Precollect the starter (qn=202) PLUS 3 random other QL2 unlocks.
    # The QuestRando rule chain (QL3 urgent + HasAll QL2 unlocks)
    # makes only QL2 quests sphere-0 reachable, but with just 1
    # precollected unlock only 2 locations are reachable — too few to
    # host the remaining 6 QL2 unlocks. Precollecting 4 (starter + 3)
    # opens 8 sphere-0 reachable Clear locations, giving fill room
    # for the remaining QL2 unlocks plus an early QL3 unlock or two.
    from .data.quests import QuestLevel
    non_starter_ql2: list[dict] = [
        q for q in world.quest_pool
        if q["quest_level"] == QuestLevel.QL2
        and quest_display_name(q) != starter_quest_name
    ]
    extra_ql2_count = min(3, len(non_starter_ql2))
    extra_ql2_starters = world.random.sample(non_starter_ql2, extra_ql2_count)
    extra_ql2_names = {quest_display_name(q) for q in extra_ql2_starters}

    itempool: list[Item] = []
    precollected: list[MHRiseItem] = []

    for quest in world.quest_pool:
        item_name = unlock_item_name(quest)
        item = create_item_with_correct_classification(world, item_name)
        name = quest_display_name(quest)
        if name == starter_quest_name or name in extra_ql2_names:
            precollected.append(item)
        else:
            itempool.append(item)

    # Mark the remaining (non-precollected) QL2 unlocks as
    # local_early so AP's distribute_early_items pass tries to
    # place them in this world's earliest reachable Clear
    # locations before the main fill loop. Without this hint, fill
    # may put QL3+ unlocks at the precollected sphere-0 locations
    # and leave no room for the rest of QL2.
    for quest in world.quest_pool:
        if (
            quest["quest_level"] == QuestLevel.QL2
            and quest_display_name(quest) != starter_quest_name
            and quest_display_name(quest) not in extra_ql2_names
        ):
            item_name = unlock_item_name(quest)
            world.multiworld.local_early_items[world.player][item_name] = (
                world.multiworld.local_early_items[world.player].get(item_name, 0) + 1
            )

    # Spare slots = unfilled (excludes the Victory-locked goal slot)
    # minus the unlock items we just placed. Reserve ≥1 for Poogie so
    # the EXCLUDED goal Clear (1/2) can be filled — weapon licenses are
    # `useful` and don't satisfy excluded-fill.
    unfilled = len(world.multiworld.get_unfilled_locations(world.player))
    spare = unfilled - len(itempool)
    assert spare >= 1, "spare-slot invariant broken (need ≥1 slot beyond unlocks)"

    if bool(world.options.include_weapons.value):
        # confirm starting_weapon is defined, should always pass
        assert world.starting_weapon is not None

        starting_weapon_name = world.starting_weapon["name"]
        precollected.append(create_item_with_correct_classification(
            world, weapon_license_item_name(world.starting_weapon)))
        non_starter_weapons = [
            w for w in world.weapon_pool if w["name"] != starting_weapon_name
        ]
        world.random.shuffle(non_starter_weapons)
        weapon_budget = max(spare - 1, 0)
        weapons_to_add = non_starter_weapons[:weapon_budget]
        for weapon in weapons_to_add:
            itempool.append(create_item_with_correct_classification(
                world, weapon_license_item_name(weapon)))
        spare -= len(weapons_to_add)

    for _ in range(spare):
        itempool.append(create_item_with_correct_classification(world, FILLER_ITEM_NAME))

    world.multiworld.itempool += itempool
    for item in precollected:
        world.push_precollected(item)

def _create_items_questrando_hub(world: MHRiseWorld) -> None:
    """Build the QuestRando hub item pool.

    Topology for V = len(world.quest_pool) hub quests:
    - 2V `Clear: <name> (n/2)` locations (mirrors HuntAThon's two-slot
      pattern; both fire on the same in-game clear event).
    - place_victory locks Victory at goal Clear (2/2) → 2V-1 unfilled
      locations to fill.
    - V `Unlock: <name>` items, one per quest. Starter (Shady Monster no 10104)
      is precollected; goal unlock is also placed but treated as
      skip-balancing.
    - Spare slots = (2V-1) - (V-1) = V slots beyond the quest unlocks.
      Filled in priority order:
        1. Starter weapon license (precollected) if weapons enabled.
        2. Up to (spare-1) random non-starter weapon licenses, capped
           at 13. The (spare-1) cap reserves at least one Poogie slot
           for AP's excluded-location fill (goal Clear (1/2) is
           EXCLUDED — weapon licenses are `useful`, not filler, so
           excluded fill rejects them).
        3. Poogie filler for leftover slots.
    """
    place_victory(world)

    starter_quest_name = quest_display_name(world.starting_quest)

    # Precollect the starter (Shady Monster no 10104) PLUS 3 random other QL1 unlocks.
    # The QuestRando rule chain
    # makes only QL1 quests sphere-0 reachable, but with just 1
    # precollected unlock only 2 locations are reachable — too few to
    # host the remaining 5 QL1 unlocks. Precollecting 4 (starter + 3)
    # opens 8 sphere-0 reachable Clear locations, giving fill room
    # for the remaining QL1 unlocks plus an early QL2 unlock or two.
    from .data.quests import QuestLevel, EnemyLv
    non_starter_ql1: list[dict] = [
        q for q in world.quest_pool
        if q["quest_level"] == QuestLevel.QL1
        and quest_display_name(q) != starter_quest_name
        and q["enemy_level"] == EnemyLv.Low
    ]
    extra_ql1_count = min(3, len(non_starter_ql1))
    extra_ql1_starters = world.random.sample(non_starter_ql1, extra_ql1_count)
    extra_ql1_names = {quest_display_name(q) for q in extra_ql1_starters}

    itempool: list[Item] = []
    precollected: list[MHRiseItem] = []

    for quest in world.quest_pool:
        item_name = unlock_item_name(quest)
        item = create_item_with_correct_classification(world, item_name)
        name = quest_display_name(quest)
        if name == starter_quest_name or name in extra_ql1_names:
            precollected.append(item)
        else:
            itempool.append(item)

    # Mark the remaining (non-precollected) QL1 unlocks as
    # local_early so AP's distribute_early_items pass tries to
    # place them in this world's earliest reachable Clear
    # locations before the main fill loop. Without this hint, fill
    # may put QL2+ unlocks at the precollected sphere-0 locations
    # and leave no room for the rest of QL1.
    for quest in world.quest_pool:
        if (
            quest["quest_level"] == QuestLevel.QL1
            and quest_display_name(quest) != starter_quest_name
            and quest_display_name(quest) not in extra_ql1_names
            and quest["enemy_level"] == EnemyLv.Low
        ):
            item_name = unlock_item_name(quest)
            world.multiworld.local_early_items[world.player][item_name] = (
                world.multiworld.local_early_items[world.player].get(item_name, 0) + 1
            )

    # Spare slots = unfilled (excludes the Victory-locked goal slot)
    # minus the unlock items we just placed. Reserve ≥1 for Poogie so
    # the EXCLUDED goal Clear (1/2) can be filled — weapon licenses are
    # `useful` and don't satisfy excluded-fill.
    unfilled = len(world.multiworld.get_unfilled_locations(world.player))
    spare = unfilled - len(itempool)
    assert spare >= 1, "spare-slot invariant broken (need ≥1 slot beyond unlocks)"

    if bool(world.options.include_weapons.value):
        # confirm starting_weapon is defined, should always pass
        assert world.starting_weapon is not None
        
        starting_weapon_name = world.starting_weapon["name"]
        precollected.append(create_item_with_correct_classification(
            world, weapon_license_item_name(world.starting_weapon)))
        non_starter_weapons = [
            w for w in world.weapon_pool if w["name"] != starting_weapon_name
        ]
        world.random.shuffle(non_starter_weapons)
        weapon_budget = max(spare - 1, 0)
        weapons_to_add = non_starter_weapons[:weapon_budget]
        for weapon in weapons_to_add:
            itempool.append(create_item_with_correct_classification(
                world, weapon_license_item_name(weapon)))
        spare -= len(weapons_to_add)

    for _ in range(spare):
        itempool.append(create_item_with_correct_classification(world, FILLER_ITEM_NAME))

    world.multiworld.itempool += itempool
    for item in precollected:
        world.push_precollected(item)
