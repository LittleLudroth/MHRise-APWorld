-- In-game tracker UI. Mode-aware: HuntAThon renders four monster /
-- weapon sections; QuestRando renders four quest sections.
--
-- HuntAThon: Available Monsters / Available Weapons (when enabled) /
--            Hunted Monsters / Locked Monsters.
-- QuestRando: Available Quests (unlock held + engine-accessible) /
--             Inaccessible Quests (unlock held, engine-gated) /
--             Cleared Quests / Locked Quests (unlock NOT held).
--
-- Visibility is owned by Tracker.visible. Auto-flipped to true on
-- successful slot_connect (see MHRiseAP.lua), reset to false on
-- disconnect. The user can also toggle via a REFramework overlay
-- checkbox.
local Tracker = {}

local Items = require("AP_CLIENT/Items")
local Lookups = require("AP_CLIENT/Lookups")
local Weapons = require("AP_CLIENT/Weapons")

Tracker.visible = false
-- Per-slot check ledger: monster_name -> { ["1"] = true, ["2"] = true }.
-- A monster only counts as hunted when BOTH slots are present. Each
-- monster has two AP locations — Hunt X (1/2) and Hunt X (2/2) — that
-- need to be checked individually. A single check (e.g. another world
-- releasing one of our locations to us) does NOT make the monster
-- hunted; only when both locations have been registered, by any
-- combination of self-hunt + release, does it move into Hunted.
--
-- Two paths populate this ledger:
--   1. Self-hunts: Tracker.MarkHunted(monster_name) marks BOTH slots
--      at once, called from Monsters.lua after a successful
--      LocationChecks send. AP doesn't reliably echo our own checks
--      back via on_location_checked, so the local mark is the
--      authoritative path for self-hunts.
--   2. Other-world releases: Tracker.NoteLocationChecked(loc_id)
--      marks one slot at a time, called from on_location_checked.
--      This handles the case where another player's release sends
--      one of our hunt locations back to us.
--
-- (String-keyed inner sets per the int-keyed-table gotcha in
-- CLAUDE.md.)
Tracker.checked = {}

-- QuestRando ledger: string(quest_no) -> { ["1"] = true, ["2"] = true }.
-- Mirrors Tracker.checked: a quest has TWO Clear: locations — Clear X
-- (1/2) and (2/2) — and only counts as cleared when BOTH slots are
-- present. A single slot arriving (e.g. another world releasing one of
-- our two Clear: locations) must NOT mark the quest cleared (gh #18).
--
-- Two populate paths, same shape as the monster ledger:
--   1. Self-clears: Tracker.MarkQuestCleared(quest_no) marks BOTH slots
--      at once (a self-clear sends both ids in one LocationChecks call).
--   2. Other-world releases: Tracker.NoteLocationChecked(loc_id) marks
--      one slot at a time via the (n/2) suffix.
Tracker.quest_cleared = {}

local function license_to_name(item_name)
    return item_name:match("^(.*) License$") or item_name
end

local function note_check(monster, slot)
    if type(monster) ~= "string" or monster == "" then return end
    if type(slot) ~= "string" or slot == "" then return end
    local entry = Tracker.checked[monster]
    if not entry then
        entry = {}
        Tracker.checked[monster] = entry
    end
    entry[slot] = true
end

local function is_fully_hunted(monster)
    local entry = Tracker.checked[monster]
    return entry ~= nil and entry["1"] == true and entry["2"] == true
end

local function note_quest_slot(qn_str, slot)
    if type(qn_str) ~= "string" or qn_str == "" then return end
    if type(slot) ~= "string" or slot == "" then return end
    local entry = Tracker.quest_cleared[qn_str]
    if not entry then
        entry = {}
        Tracker.quest_cleared[qn_str] = entry
    end
    entry[slot] = true
end

local function is_fully_cleared(qn_str)
    local entry = Tracker.quest_cleared[qn_str]
    return entry ~= nil and entry["1"] == true and entry["2"] == true
end

function Tracker.NoteLocationChecked(loc_id)
    local AP_REF = _G.AP_REF
    if not AP_REF or not AP_REF.APClient then return end
    local game = AP_REF.APClient:get_game()
    local ok, loc_name = pcall(function()
        return AP_REF.APClient:get_location_name(loc_id, game)
    end)
    if not ok or type(loc_name) ~= "string" then return end
    local monster, slot = loc_name:match("^Hunt (.*) %((%d+)/%d+%)$")
    if monster and slot then
        note_check(monster, slot)
        return
    end
    -- QuestRando: `Clear: <name> (n/2)` location. Cross-reference
    -- against Lookups.quest_names to find the matching quest_no, then
    -- mark only THAT slot — the quest is cleared only once both slots
    -- arrive (gh #18). AP doesn't reliably echo our own self-clear
    -- sends, so this path normally fires only for external releases.
    local q_name, q_slot = loc_name:match("^Clear: (.*) %((%d+)/%d+%)$")
    if q_name and q_slot then
        for qn_str, name in pairs(Lookups.quest_names) do
            if name == q_name then
                note_quest_slot(qn_str, q_slot)
                return
            end
        end
    end
end

function Tracker.MarkHunted(monster_name)
    if type(monster_name) ~= "string" or monster_name == "" then return end
    -- A self-hunt sends both (1/2) and (2/2) in the same LocationChecks
    -- call, so mark both slots in one shot.
    note_check(monster_name, "1")
    note_check(monster_name, "2")
end

-- QuestRando: called from Quests.lua after a successful clear-check
-- LocationChecks send. A self-clear sends both (1/2) and (2/2) in the
-- same LocationChecks call, so mark both slots at once. Idempotent.
function Tracker.MarkQuestCleared(quest_no)
    if type(quest_no) ~= "number" then return end
    local qn_str = tostring(quest_no)
    note_quest_slot(qn_str, "1")
    note_quest_slot(qn_str, "2")
end

function Tracker.Reset()
    Tracker.checked = {}
    Tracker.quest_cleared = {}
    Tracker.visible = false
end

-- Build the four section lists. Cheap (≤72 monsters + 14 weapons) so
-- it's fine to recompute every frame; no caching needed in v1.
local function build_sections()
    local available_monsters = {}
    local available_weapons = {}
    local hunted = {}
    local locked = {}

    -- Iterate the string-keyed forward map (item_name -> em_type)
    -- rather than the int-keyed reverse map. REFramework's Lua VM
    -- has been observed to throw "invalid key to 'next'" when
    -- iterating int-keyed tables here; string keys traverse cleanly.
    for license_name, _ in pairs(Lookups.item_name_to_em_type) do
        local name = license_to_name(license_name)
        if is_fully_hunted(name) then
            hunted[#hunted + 1] = name
        elseif Items.Has(license_name) or name == Lookups.starting_monster then
            available_monsters[#available_monsters + 1] = name
        else
            locked[#locked + 1] = name
        end
    end

    if Weapons.enabled then
        -- Identify weapon licenses by POSITIVE membership in the
        -- weapon-license name set (from slot_data) — not by exclusion.
        -- Exclusion ("anything not a monster license") wrongly swept up
        -- non-license items like the Poogie filler (gh #16). Then add
        -- the precollected starter weapon (which doesn't arrive via
        -- items_received).
        local weapon_license_names = {}
        for _, name in pairs(Weapons.weapon_type_to_item_name) do
            weapon_license_names[name] = true
        end
        local saw_starter = false
        for license_name, _ in pairs(Items.held) do
            if weapon_license_names[license_name] then
                local name = license_to_name(license_name)
                if name == Weapons.starting_weapon then saw_starter = true end
                available_weapons[#available_weapons + 1] = name
            end
        end
        if Weapons.starting_weapon and not saw_starter then
            available_weapons[#available_weapons + 1] = Weapons.starting_weapon
        end
    end

    table.sort(available_monsters)
    table.sort(available_weapons)
    table.sort(hunted)
    table.sort(locked)
    return available_monsters, available_weapons, hunted, locked
end

-- QuestRando sections.
-- Cleared = BOTH Clear: locations registered (self-clear or external
--   release).
--   For a swapped quest the fought monster's name is appended as
--   " - <monster>" (gh #22); unswapped quests / older seeds show no
--   suffix.
-- Available = unlock held + engine reports accessible + not yet cleared.
-- Inaccessible = unlock held + engine reports NOT accessible. Accessibility
--   is read live from the engine via Quests.EngineQuestAccessible, which
--   ANDs two gates: the per-tier urgent oracle (isUnlockUrgent for a tier's
--   own urgent quest, isClearUrgent for the tier's non-urgents) and the
--   per-quest intra-tier oracle (checkUnlockCondition, for story/NPC gates).
--   This reflects the actual game, not the over-approximated fill rule
--   (gh #23). If the engine read is unavailable (nil — not in a save yet),
--   or the seed predates quest_levels, the quest is treated as Available
--   (no false "Inaccessible" claim).
-- Locked = unlock NOT held + not yet cleared.
local function build_quest_sections()
    local Quests = require("AP_CLIENT/Quests")
    local available = {}
    local inaccessible = {}
    local locked = {}
    local cleared = {}
    -- Engine-accurate accessibility: pair the quest's tier (quest_levels)
    -- and urgent-status (tier_urgents) with the engine's per-tier + per-
    -- quest oracles. Missing tier data (old seed) or an unreadable engine
    -- (nil — not in a save, singleton not loaded) -> treat as accessible so
    -- we never show a false "Inaccessible" claim.
    local function engine_accessible(qn_str)
        local ql = Lookups.quest_levels[qn_str]
        local el = Lookups.enemy_levels[qn_str]
        if ql == nil then return true end   -- back-compat: old seed
        if el == nil then el = 0 end -- back-compat: default to village quests if el not defined
        local is_urgent = Lookups.tier_urgents[tostring(ql)..","..tostring(el)] == tonumber(qn_str)
        local v = Quests.EngineQuestAccessible(tonumber(qn_str), ql, el, is_urgent)
        if v == nil then return true end
        return v
    end
    for qn_str, _ in pairs(Lookups.quest_locations) do
        local display = Lookups.quest_names[qn_str] or qn_str
        if is_fully_cleared(qn_str) then
            local fought = Lookups.quest_swap_names[qn_str]
            if fought then
                display = display .. " - " .. fought
            end
            cleared[#cleared + 1] = display
        else
            local unlock_name = Lookups.quest_unlocks[qn_str]
            local held = unlock_name == nil or Items.Has(unlock_name)
            if not held then
                locked[#locked + 1] = display
            elseif engine_accessible(qn_str) then
                available[#available + 1] = display
            else
                inaccessible[#inaccessible + 1] = display
            end
        end
    end
    table.sort(available)
    table.sort(inaccessible)
    table.sort(locked)
    table.sort(cleared)
    return available, inaccessible, locked, cleared
end

-- QuestRando weapons section: list of held weapon-license names plus
-- the precollected starter weapon (which doesn't arrive via
-- items_received). Identifies weapon licenses by POSITIVE membership in
-- the weapon-license name set (from slot_data), not by exclusion — the
-- old "not a quest unlock" test wrongly swept up the Poogie filler item
-- (gh #16). Mirrors the HuntAThon `build_sections` weapon path.
local function build_quest_weapon_section()
    local weapons = {}
    if not Weapons.enabled then return weapons end
    -- Reverse-set of weapon-license item names for the membership test.
    local weapon_license_names = {}
    for _, name in pairs(Weapons.weapon_type_to_item_name) do
        weapon_license_names[name] = true
    end
    local saw_starter = false
    for license_name, _ in pairs(Items.held) do
        if weapon_license_names[license_name] then
            local name = license_to_name(license_name)
            if name == Weapons.starting_weapon then saw_starter = true end
            weapons[#weapons + 1] = name
        end
    end
    if Weapons.starting_weapon and not saw_starter then
        weapons[#weapons + 1] = Weapons.starting_weapon
    end
    table.sort(weapons)
    return weapons
end

local function draw_section(label, items)
    imgui.text(label)
    imgui.separator()
    if #items == 0 then
        imgui.text("  (none)")
    else
        for _, item in ipairs(items) do
            imgui.text("  " .. item)
        end
    end
    imgui.text("")  -- blank line between sections
end

local logged_draw_error = false
function Tracker.Draw()
    if not Tracker.visible then return end
    if not Lookups.connected then return end
    -- Only render while the REFramework overlay is open. Mirrors the
    -- gate AP_REF/core.lua uses for its own window via UpdateBehavior.
    if not reframework:is_drawing_ui() then return end

    -- Build sections OUTSIDE the imgui begin/end pair so a bad table
    -- iteration can't leave imgui in a half-open state.
    local available_monsters, available_weapons, hunted_monsters, locked_monsters
    local available_quests, inaccessible_quests, locked_quests, cleared_quests, quest_weapons
    local build_ok, build_err = pcall(function()
        if Lookups.mode == "quest_rando" then
            available_quests, inaccessible_quests, locked_quests, cleared_quests = build_quest_sections()
            quest_weapons = build_quest_weapon_section()
        else
            available_monsters, available_weapons, hunted_monsters, locked_monsters = build_sections()
        end
    end)
    if not build_ok then
        if not logged_draw_error then
            log.info("[Tracker] build_sections error: " .. tostring(build_err))
            logged_draw_error = true
        end
        return
    end

    local ok, err = pcall(function()
        imgui.set_next_window_size(Vector2f.new(320, 500), 4)
        Tracker.visible = imgui.begin_window("MH Rise AP Tracker", Tracker.visible, nil)
        if Tracker.visible then
            if Lookups.mode == "quest_rando" then
                draw_section("Available Quests", available_quests)
                if Weapons.enabled then
                    draw_section("Available Weapons", quest_weapons)
                end
                draw_section("Inaccessible Quests", inaccessible_quests)
                draw_section("Cleared Quests", cleared_quests)
                draw_section("Locked Quests", locked_quests)
            else
                draw_section("Available Monsters", available_monsters)
                if Weapons.enabled then
                    draw_section("Available Weapons", available_weapons)
                end
                draw_section("Hunted Monsters", hunted_monsters)
                draw_section("Locked Monsters", locked_monsters)
            end
        end
        imgui.end_window()
    end)
    if not ok and not logged_draw_error then
        log.info("[Tracker] draw error: " .. tostring(err))
        logged_draw_error = true
    end
end

return Tracker
