"""Convert mhrise_quest_catalog.json (from QuestCatalogDump.lua) into
ap_world/data/quests.py.

One-time script — runs offline, reads a checked-in JSON snapshot, writes
a Python module. Re-run when Capcom drops a DLC patch that adds quests
(re-dump in-game with QuestCatalogDump.lua first).

Output module exports:
- QuestType (IntFlag), QuestLevel (IntEnum), EnemyLv (IntEnum),
  MapNoType (IntEnum) — mirror the in-game enums from
  snow.quest.* (sourced from RiseQuestLoader/Quest.h).
- QUESTS: tuple of dicts. quest_type / quest_level / enemy_level /
  map_no values are the enum members, NOT raw ints. Unknown raw values
  fall back to the int with a comment.

Filtering rules:
- Keep ALL quest_types — randomization scope may expand beyond hunting.
- Drop entries with boss_em_type != 0 whose em_type doesn't resolve in
  MONSTERS / APEX_MONSTERS / SMALL_MONSTERS. Log these — they hint at
  gaps in monsters.py.
- Keep entries with boss_em_type == 0 (gather, tour, training, etc.).
  These are real quests with no large-monster target; monster_name is
  None.
- Drop dbg_* fields from the output.

Usage:
    python debug_tools/convert_quest_catalog.py [INPUT_JSON]

INPUT_JSON defaults to a path under the env-var AP_GAME_INSTALL
(reframework/data/mhrise_quest_catalog.json) when present, otherwise
to ./mhrise_quest_catalog.json.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_monsters_module() -> ModuleType:
    """Load ap_world/data/monsters.py directly without triggering
    ap_world/__init__.py — that init imports `worlds.AutoWorld` which
    isn't available outside an Archipelago install.
    """
    path = REPO_ROOT / "ap_world" / "data" / "monsters.py"
    spec = importlib.util.spec_from_file_location("_ap_monsters", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_monsters_mod = _load_monsters_module()
MONSTERS = _monsters_mod.MONSTERS
APEX_MONSTERS = _monsters_mod.APEX_MONSTERS
SMALL_MONSTERS = _monsters_mod.SMALL_MONSTERS

OUTPUT_PATH = REPO_ROOT / "ap_world" / "data" / "quests.py"
DEFAULT_JSON_NAME = "mhrise_quest_catalog.json"

# In-game enum definitions, sourced from RiseQuestLoader/Quest.h (which
# in turn matches snow.quest.* in the game). value → member name. The
# script emits these as Python IntEnum / IntFlag in the generated
# quests.py so consumers don't deal with raw ints.

# snow.quest.QuestType — flag enum. Each bit is a single quest class;
# the C++ header overloads & / | on it. Observed in our catalog: only
# single-bit values appear (no combos), but typing it as IntFlag is
# the future-proof shape.
QUEST_TYPE_MEMBERS: dict[str, int] = {
    "INVALID": 0,
    "HUNTING": 1 << 0,
    "KILL": 1 << 1,
    "CAPTURE": 1 << 2,
    "BOSSRUSH": 1 << 3,
    "COLLECTS": 1 << 4,
    "TOUR": 1 << 5,
    "ARENA": 1 << 6,
    "SPECIAL": 1 << 7,
    "HYAKURYU": 1 << 8,
    "TRAINING": 1 << 9,
    "KYOUSEI": 1 << 10,
}

# snow.quest.QuestLevel.
QUEST_LEVEL_MEMBERS: dict[str, int] = {
    "INVALID": -1,
    "QL1": 0,
    "QL2": 1,
    "QL3": 2,
    "QL4": 3,
    "QL5": 4,
    "QL6": 5,
    "QL7": 6,
    "QL7EX": 7,
}

# snow.quest.EnemyLv.
ENEMY_LV_MEMBERS: dict[str, int] = {
    "Village": 0,
    "Low": 1,
    "High": 2,
    "Master": 3,
}

# snow.quest.MapNoType. A handful of Capcom-internal nameless slots
# (Stage_Name_NN) are placeholders the player never sees; preserved
# for round-trip fidelity.
MAP_NO_MEMBERS: dict[str, int] = {
    "Stage_Name_00": 0,
    "ShrineRuins": 1,
    "SandyPlains": 2,
    "FloodedForest": 3,
    "FrostCaverns": 4,
    "LavaCaverns": 5,
    "Stage_Name_06": 6,
    "RedStronghold": 7,
    "Stage_Name_08": 8,
    "InfernalSprings": 9,
    "Arena": 10,
    "CoralPalace": 11,
    "Jungle": 12,
    "Citadel": 13,
    "Stage_Name_14": 14,
    "YawningAbyss": 15,
    "Stage_Name_42": 16,
}


def resolve_default_input() -> Path:
    """Look in <game install>/reframework/data, then cwd."""
    game = os.environ.get("AP_GAME_INSTALL")
    if game:
        p = Path(game) / "reframework" / "data" / DEFAULT_JSON_NAME
        if p.exists():
            return p
    return Path(DEFAULT_JSON_NAME)


def format_enum_value(
    raw: int | None,
    enum_name: str,
    members: dict[str, int],
    is_flag: bool,
    unknowns: dict[str, set[int]],
) -> str:
    """Return a source-code-ready expression for an enum value.

    Known integer → `EnumName.MEMBER`. Unknown integer → raw int with
    a comment, also recorded in `unknowns[enum_name]` for the run
    summary.
    """
    if raw is None:
        return "None"
    # Reverse lookup: value → name. For flag enums with combinations
    # we fall back to int (no observed combos in catalog, but defensive).
    name_by_value = {v: k for k, v in members.items()}
    if raw in name_by_value:
        return f"{enum_name}.{name_by_value[raw]}"
    if is_flag and raw != 0:
        # Try decomposing into a | of known single-bit names.
        bits: list[str] = []
        remaining = raw
        for member_name, member_value in members.items():
            if member_value and (member_value & remaining) == member_value:
                bits.append(f"{enum_name}.{member_name}")
                remaining &= ~member_value
        if remaining == 0 and bits:
            return " | ".join(bits)
    unknowns.setdefault(enum_name, set()).add(raw)
    return f"{raw}  # unknown {enum_name}"


def build_em_type_lookup() -> dict[int, dict[str, str]]:
    """em_type → {name, bucket}, unioning all three monster tables.

    Buckets: 'monster' (randomizable large), 'apex', 'small'.
    """
    out: dict[int, dict[str, str]] = {}
    for entry in MONSTERS:
        out[entry["em_type"]] = {"name": entry["name"], "bucket": "monster"}
    for entry in APEX_MONSTERS:
        out[entry["em_type"]] = {"name": entry["name"], "bucket": "apex"}
    for entry in SMALL_MONSTERS:
        out[entry["em_type"]] = {"name": entry["name"], "bucket": "small"}
    return out


def convert(catalog_path: Path) -> None:
    print(f"reading {catalog_path}", file=sys.stderr)
    with catalog_path.open(encoding="utf-8") as f:
        catalog = json.load(f)

    quests_in = catalog["quests"] or []
    print(f"  {len(quests_in)} raw entries", file=sys.stderr)

    em_lookup = build_em_type_lookup()
    print(f"  {len(em_lookup)} known em_types across MONSTERS/APEX/SMALL",
          file=sys.stderr)

    kept: list[dict] = []
    dropped_unresolved: list[tuple[int, int, str]] = []  # (quest_no, em_type, source)

    for q in quests_in:
        boss_one = q.get("boss_em_type_one") or 0
        tgt_one = q.get("target_em_type_one") or 0
        monster_name = None
        monster_bucket = None

        if boss_one != 0:
            hit = em_lookup.get(boss_one)
            if hit is None:
                dropped_unresolved.append(
                    (q.get("quest_no", -1), boss_one, q.get("source", "?"))
                )
                continue
            monster_name = hit["name"]
            monster_bucket = hit["bucket"]

        kept.append({
            "quest_no": q["quest_no"],
            "source": q["source"],
            "name": q.get("name"),
            "dbg_name": q.get("dbg_name"),
            "quest_type": q.get("quest_type"),
            "quest_level": q.get("quest_level"),
            "enemy_level": q.get("enemy_level"),
            "map_no": q.get("map_no"),
            "base_time": q.get("base_time"),
            "time_limit": q.get("time_limit"),
            "quest_life": q.get("quest_life"),
            "boss_em_type_one": boss_one,
            "boss_em_type_two": q.get("boss_em_type_two"),
            "target_em_type_one": tgt_one,
            "target_em_type_two": q.get("target_em_type_two"),
            "two_target_quest": q.get("two_target_quest"),
            "monster_name": monster_name,
            "monster_bucket": monster_bucket,
        })

    kept.sort(key=lambda r: (r["source"], r["quest_no"]))

    print(f"  kept: {len(kept)}", file=sys.stderr)
    print(f"  dropped (unresolved em_type): {len(dropped_unresolved)}",
          file=sys.stderr)
    if dropped_unresolved:
        print("    quest_no | em_type | source", file=sys.stderr)
        for qn, em, src in dropped_unresolved:
            print(f"    {qn:>8} | {em:>7} | {src}", file=sys.stderr)

    unknowns: dict[str, set[int]] = {}
    write_module(kept, catalog_path, len(dropped_unresolved), unknowns)
    print(f"wrote {OUTPUT_PATH}", file=sys.stderr)
    if unknowns:
        print("  unknown enum values encountered (kept as raw int):",
              file=sys.stderr)
        for ename, vals in sorted(unknowns.items()):
            print(f"    {ename}: {sorted(vals)}", file=sys.stderr)


def emit_enum_class(
    name: str,
    members: dict[str, int],
    base: str,
) -> str:
    lines = [f"class {name}({base}):"]
    for member_name, value in members.items():
        lines.append(f"    {member_name} = {value}")
    return "\n".join(lines) + "\n"


def write_module(
    quests: list[dict],
    source_path: Path,
    n_dropped: int,
    unknowns: dict[str, set[int]],
) -> None:
    header = f'''"""Master quest table for the MH Rise Archipelago world.

Single source of truth for which quests exist in the game and what
monster each one spawns. Generated by `debug_tools/convert_quest_catalog.py`
from a snapshot of the in-game quest catalog (dumped via
`debug_tools/QuestCatalogDump.lua`). Do NOT hand-edit — regenerate.

Source snapshot: {source_path.name}
Total quests in source: see snapshot
Kept in QUESTS: {len(quests)}
Dropped (boss_em_type not resolvable in MONSTERS/APEX/SMALL): {n_dropped}

Fields per entry:
- quest_no: in-game quest identifier (the key)
- source: "normal" (base game / HR hub) or "kohaku" (Sunbreak / MR)
- name: localized quest title (game's current language at dump time;
  English when dumped from an English client). None if the dumper
  couldn't resolve it for this entry.
- dbg_name: Japanese dev-time name from the in-game _DbgName field.
  Stable fallback when `name` is None.
- quest_type: QuestType flag
- quest_level: QuestLevel enum
- enemy_level: EnemyLv enum
- map_no: MapNoType enum
- base_time / time_limit / quest_life: timing & cart fields
- boss_em_type: primary spawned monster em_type, or 0 for no-monster quests
- second_boss_em_type: secondary spawned monster em_type, or 0 for quests with one or fewer monsters
- target_em_type: primary clear-condition target em_type
- second_target_em_type: secondary clear-condition target em_type, or 0 if quest doesn't have different targets
- two_target_quest: 0 if not an MR two target quest, 1 if an MR two target quest
- monster_name: resolved display name from monsters.py master tables,
  or None when boss_em_type == 0
- monster_bucket: "monster" (large/randomizable), "apex", or "small";
  None when boss_em_type == 0
"""
from __future__ import annotations
from enum import IntEnum, IntFlag
from typing import Any


'''

    enums_block = (
        emit_enum_class("QuestType", QUEST_TYPE_MEMBERS, "IntFlag")
        + "\n"
        + emit_enum_class("QuestLevel", QUEST_LEVEL_MEMBERS, "IntEnum")
        + "\n"
        + emit_enum_class("EnemyLv", ENEMY_LV_MEMBERS, "IntEnum")
        + "\n"
        + emit_enum_class("MapNoType", MAP_NO_MEMBERS, "IntEnum")
        + "\n"
    )

    body_lines: list[str] = ["QUESTS: tuple[dict[str, Any], ...] = ("]
    for q in quests:
        qt = format_enum_value(
            q["quest_type"], "QuestType", QUEST_TYPE_MEMBERS, True, unknowns)
        ql = format_enum_value(
            q["quest_level"], "QuestLevel", QUEST_LEVEL_MEMBERS, False, unknowns)
        el = format_enum_value(
            q["enemy_level"], "EnemyLv", ENEMY_LV_MEMBERS, False, unknowns)
        mn = format_enum_value(
            q["map_no"], "MapNoType", MAP_NO_MEMBERS, False, unknowns)
        body_lines.append("    {")
        body_lines.append(f'        "quest_no": {q["quest_no"]!r},')
        body_lines.append(f'        "source": {q["source"]!r},')
        body_lines.append(f'        "name": {q["name"]!r},')
        body_lines.append(f'        "dbg_name": {q["dbg_name"]!r},')
        body_lines.append(f'        "quest_type": {qt},')
        body_lines.append(f'        "quest_level": {ql},')
        body_lines.append(f'        "enemy_level": {el},')
        body_lines.append(f'        "map_no": {mn},')
        body_lines.append(f'        "base_time": {q["base_time"]!r},')
        body_lines.append(f'        "time_limit": {q["time_limit"]!r},')
        body_lines.append(f'        "quest_life": {q["quest_life"]!r},')
        body_lines.append(f'        "boss_em_type": {q["boss_em_type_one"]!r},')
        body_lines.append(f'        "second_boss_em_type": {q["boss_em_type_two"]!r},')
        body_lines.append(f'        "target_em_type": {q["target_em_type_one"]!r},')
        body_lines.append(f'        "second_target_em_type": {q["target_em_type_two"]!r},')
        body_lines.append(f'        "two_target_quest": {q["two_target_quest"]!r},')
        body_lines.append(f'        "monster_name": {q["monster_name"]!r},')
        body_lines.append(f'        "monster_bucket": {q["monster_bucket"]!r},')
        body_lines.append("    },")
    body_lines.append(")")

    OUTPUT_PATH.write_text(
        header + enums_block + "\n" + "\n".join(body_lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    if len(sys.argv) >= 2:
        path = Path(sys.argv[1])
    else:
        path = resolve_default_input()
    if not path.exists():
        print(f"ERROR: catalog JSON not found at {path}", file=sys.stderr)
        print("Pass the path as the first argument, or set AP_GAME_INSTALL.",
              file=sys.stderr)
        sys.exit(1)
    convert(path)


if __name__ == "__main__":
    main()
