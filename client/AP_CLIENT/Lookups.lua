-- Caches per-session lookup tables built from slot_data on slot connect.
-- The apworld ships `monster_em_type_map` (item_name -> em_type); we
-- precompute the reverse (em_type -> item_name) so the death hook can
-- resolve a hunted monster's em_type back to a license item name in O(1).
local Lookups = {}

local Utils = require("AP_CLIENT/Utilities")

Lookups.connected = false
Lookups.mode = "hunt_a_thon"  -- "hunt_a_thon" | "quest_rando"
Lookups.starting_monster = nil
Lookups.goal_monster = nil

-- item_name -> em_type (e.g. "Rathian License" -> 1)
Lookups.item_name_to_em_type = {}

-- em_type -> item_name (e.g. "1" -> "Rathian License").
-- KEYS ARE STRINGS, not integers. REFramework's Lua VM has been
-- observed to throw "invalid key to 'next'" when iterating int-keyed
-- tables, and `t[int]` lookups have likewise been observed to miss
-- entries that were stored via int-key assignment. String-keying both
-- writes and reads sidesteps both bugs.
Lookups.em_type_to_item_name = {}

-- item_name to monster tier (easy, medium, hard, start, goal)
Lookups.license_to_tier = {}

-- number of monsters in each tier (easy, medium, hard)
Lookups.easy_monster_count = 0
Lookups.medium_monster_count = 0
Lookups.hard_monster_count = 0

-- QuestRando fields (populated only when mode == "quest_rando").
-- All quest_no keys are STRINGS for the same int-keyed-table reason
-- (see Lookups.em_type_to_item_name above). JSON delivery naturally
-- arrives string-keyed so this is just pass-through.
Lookups.quest_pool_type = "village" -- "village" | "hub" | "sunbreak"
Lookups.quest_swaps = {}     -- "quest_no" -> em_types (array)
Lookups.quest_swap_names = {} -- "quest_no" -> swapped-in monster display names (gh #22)
Lookups.quest_names = {}     -- "quest_no" -> display name
Lookups.quest_locations = {} -- "quest_no" -> 1 (set membership)
Lookups.quest_unlocks = {}   -- "quest_no" -> "Unlock: <name>" item name
Lookups.quest_levels = {}    -- "quest_no" -> QuestLevel int (QL1=0, QL2=1, ... QL7=6)
Lookups.enemy_levels = {}    -- "quest_no" -> EnemyLv int (village=0, low=1, high=2, master=3)
Lookups.tier_urgents = {}    -- "QL int str" -> that tier's urgent quest_no (int)
Lookups.key_to_urgent = {}   -- "key quest_no" -> unlocking Urgent quest_no 
Lookups.goal_quest = nil     -- int (quest_no)
Lookups.starting_quest = nil -- int (quest_no)

-- Weapon Fields
Lookups.enabled = false                 -- Indicates if weapon checks are enabled
Lookups.weapon_type_to_item_name = {}   -- weapon_type (int) -> license item name
Lookups.starting_weapon = nil           -- Starter weapon name, for display on connect

-- Deathlink flag
-- Used to determine whether or not the client should initially send or react to deathlinks
Lookups.death_link = false -- bool

function Lookups.Reset()
    Lookups.connected = false
    Lookups.mode = "hunt_a_thon"
    Lookups.starting_monster = nil
    Lookups.goal_monster = nil
    Lookups.item_name_to_em_type = {}
    Lookups.em_type_to_item_name = {}
    Lookups.license_to_tier = {}
    Lookups.easy_monster_count = 0
    Lookups.medium_monster_count = 0
    Lookups.hard_monster_count = 0
    Lookups.quest_pool_type = "village"
    Lookups.quest_swaps = {}
    Lookups.quest_swap_names = {}
    Lookups.quest_names = {}
    Lookups.quest_locations = {}
    Lookups.quest_unlocks = {}
    Lookups.quest_levels = {}
    Lookups.enemy_levels = {}
    Lookups.tier_urgents = {}
    Lookups.key_to_urgent = {}
    Lookups.goal_quest = nil
    Lookups.starting_quest = nil
    Lookups.death_link = false
    -- Reset Weapons too. Weapon status is kept here to allow Lookups to be 
    -- the root inport for the client. Previous structure had circular dep.
    Lookups.weapons_enabled = false
    Lookups.weapon_type_to_item_name = {}
    Lookups.starting_weapon = nil
end

-- Called from the on_slot_connected callback. slot_data shape depends
-- on mode (see ap_world/world.py:fill_slot_data).
--
-- Common:
--   mode:                       "hunt_a_thon" | "quest_rando"
--   world_version:              string
--   death_link:                  bool
--
-- HuntAThon:
--   monster_em_type_map:        {[item_name]: em_type}
--   starting_monster:           string
--   goal_monster:               string
--   include_sunbreak:           bool
--   include_weapons:            bool
--   weapon_type_to_item_name:   {[weapon_type]: item_name}  (when enabled)
--   starting_weapon:            string                        (when enabled)
--
-- QuestRando:
--   quest_swaps:                {[quest_no_str]: em_types}
--   quest_swap_names:           {[quest_no_str]: monster display name}
--                               (swapped-in monster; absent on older seeds)
--   quest_names:                {[quest_no_str]: display name}
--   quest_locations:            {[quest_no_str]: 1}  (set membership —
--                               quests that send AP Clear checks)
--   quest_unlocks:              {[quest_no_str]: "Unlock: <name>"}
--   quest_levels:               {[quest_no_str]: QuestLevel int}  (QL2=1
--                               QL3=2 QL4=3 QL5=4; absent on older seeds)
--   enemy_levels                {[quest_no_str]}: EnemyLv int
--   tier_urgents:               {[QL_int_str]: urgent quest_no}  (QL3/4/5;
--                               absent on older seeds)
--   goal_quest:                 int (quest_no)
--   starting_quest:             int (quest_no, precollected)
--   include_weapons:            bool
--   weapon_type_to_item_name:   {[weapon_type]: item_name}  (when enabled)
--   starting_weapon:            string                        (when enabled)
function Lookups.Load(slot_data)
    Lookups.Reset()
    if type(slot_data) ~= "table" then
        return false, "slot_data is not a table"
    end

    local mode = slot_data.mode

    -- set deathlink flag, default to false if not defined
    if slot_data.death_link ~= nil then
        Lookups.death_link = slot_data.death_link
    end

    if mode == "quest_rando" then
        Lookups.mode = "quest_rando"

        -- backwards compat, assumes village quest pool for old questrando
        if slot_data.quest_pool_type ~= nil then
            Lookups.quest_pool_type = slot_data.quest_pool_type
        end

        local swaps = slot_data.quest_swaps
        local locations = slot_data.quest_locations
        local names = slot_data.quest_names
        local unlocks = slot_data.quest_unlocks
        if type(swaps) ~= "table" or type(locations) ~= "table" then
            return false, "quest_swaps / quest_locations missing"
        end
        for k, v in pairs(swaps) do
            -- backwards compat, values sent as numbers are put in array
            -- values sent as string are split by comma into an array
            local em = type(v) == "number" and {v} or Utils.Split_Numbers(v)
            if em ~= nil then
                Lookups.quest_swaps[tostring(k)] = em
            end
        end
        for k, _ in pairs(locations) do
            Lookups.quest_locations[tostring(k)] = 1
        end
        if type(names) == "table" then
            for k, v in pairs(names) do
                Lookups.quest_names[tostring(k)] = v
            end
        end
        if type(unlocks) == "table" then
            for k, v in pairs(unlocks) do
                Lookups.quest_unlocks[tostring(k)] = v
            end
        end
        local swap_names = slot_data.quest_swap_names
        if type(swap_names) == "table" then
            for k, v in pairs(swap_names) do
                if type(v) == "string" then
                    Lookups.quest_swap_names[tostring(k)] = v
                end
            end
        end
        local levels = slot_data.quest_levels
        if type(levels) == "table" then
            for k, v in pairs(levels) do
                local ql = type(v) == "number" and v or tonumber(v)
                if ql ~= nil then
                    Lookups.quest_levels[tostring(k)] = ql
                end
            end
        end
        local enemy_levels = slot_data.enemy_levels
        if type(enemy_levels) == "table" then
            for k, v in pairs(enemy_levels) do
                local el = type(v) == "number" and v or tonumber(v)
                if el ~= nil then
                    Lookups.enemy_levels[tostring(k)] = el
                end
            end
        end
        local urgents = slot_data.tier_urgents
        if type(urgents) == "table" then
            for k, v in pairs(urgents) do
                local qn = type(v) == "number" and v or tonumber(v)
                if qn ~= nil then
                    -- backwords compat, ensure older key format is set to new key format
                    -- Detects old versions by checking if slot_data.quest_pool_type is defined
                    if slot_data.quest_pool_type == nil then
                        Lookups.tier_urgents[tostring(k)..",0"] = qn
                    else
                        Lookups.tier_urgents[tostring(k)] = qn
                    end
                end
            end
        end
        local key_to_urgent = slot_data.key_to_urgent
        if type(key_to_urgent) == "table" then
            for k, v in pairs(key_to_urgent) do
                local qn = type(v) == "number" and v or tonumber(v)
                if qn ~= nil then
                        Lookups.key_to_urgent[tostring(k)] = qn
                end
            end
        end
        Lookups.goal_quest = tonumber(slot_data.goal_quest)
        Lookups.starting_quest = tonumber(slot_data.starting_quest)

        -- Weapons cache (same shape as HuntAThon branch below). The
        -- weapon gate at quest-clear time reads these.
        if slot_data.include_weapons then
            Lookups.weapons_enabled = true
            local wmap = slot_data.weapon_type_to_item_name
            if type(wmap) == "table" then
                for k, v in pairs(wmap) do
                    Lookups.weapon_type_to_item_name[tostring(k)] = v
                end
            end
            Lookups.starting_weapon = slot_data.starting_weapon
        end

        Lookups.connected = true
        return true
    end

    -- HuntAThon (default if mode missing for back-compat).
    Lookups.mode = "hunt_a_thon"
    local em_map = slot_data.monster_em_type_map
    if type(em_map) ~= "table" then
        return false, "slot_data.monster_em_type_map missing"
    end

    -- Forward map (string-keyed by license name) keeps em_type as a
    -- number for its consumers. Reverse map keys by tostring(em_type)
    -- to keep all REFramework-Lua tables string-keyed (see comment on
    -- Lookups.em_type_to_item_name above).
    for item_name, em_type in pairs(em_map) do
        local n = type(em_type) == "number" and em_type or tonumber(em_type)
        if n ~= nil then
            Lookups.item_name_to_em_type[item_name] = n
            Lookups.em_type_to_item_name[tostring(n)] = item_name
        end
    end

    -- Populate a lookup table which maps licenses to the corresponding monster tier
    if type(slot_data.license_to_tier) == "table" then
        Lookups.license_to_tier = slot_data.license_to_tier
        for _, level in pairs(Lookups.license_to_tier) do
            if level == "easy" then
                Lookups.easy_monster_count = Lookups.easy_monster_count + 1
            elseif level == "medium" then
                Lookups.medium_monster_count = Lookups.medium_monster_count + 1
            elseif level == "hard" then
                Lookups.hard_monster_count = Lookups.hard_monster_count + 1
            end
        end
    end

    Lookups.starting_monster = slot_data.starting_monster
    Lookups.goal_monster = slot_data.goal_monster

    if slot_data.include_weapons then
        Lookups.weapons_enabled = true
        local wmap = slot_data.weapon_type_to_item_name
        if type(wmap) == "table" then
            -- Store with string keys (see comment on
            -- Lookups.em_type_to_item_name above for why). JSON keys
            -- arrive as strings already; just pass them through.
            for k, v in pairs(wmap) do
                Lookups.weapon_type_to_item_name[tostring(k)] = v
            end
        end
        Lookups.starting_weapon = slot_data.starting_weapon
    end

    Lookups.connected = true
    return true
end

function Lookups.GetItemNameByEmType(em_type)
    -- String-keyed reverse map; coerce to string for lookup.
    return Lookups.em_type_to_item_name[tostring(em_type)]
end

function Lookups.GetEmTypeByItemName(item_name)
    return Lookups.item_name_to_em_type[item_name]
end

return Lookups
