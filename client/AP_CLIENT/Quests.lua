-- Quest randomizer mode. Two hooks:
--
-- 1. snow.QuestManager.initQuestDataDictionary (post): walk
--    Lookups.quest_swaps and mutate each affected QuestData's
--    _BossEmType[0] / _TgtEmType[0] via array:call("Set", 0, em_type)
--    (RiseQuestLoader idiom validated by Probe 3).
-- 2. snow.QuestManager.setQuestClear (no args, pre): on a successful
--    clear, send BOTH `Clear: <name> (1/2)` + `(2/2)` locations to
--    AP if the quest is in Lookups.quest_locations (the seed's
--    village quest set) AND the player holds:
--    - the matching `Unlock: <name>` item (always required), and
--    - the license for their currently-equipped weapon (when
--      `include_weapons` is on).
--    Hub / event / rampage clears fire the same hook but are
--    silently dropped (not in Lookups.quest_locations). Re-clears
--    of the same quest re-fire the hook; AP server dedupes location
--    IDs at its layer, so re-clearing after picking up the unlock
--    later is the correct way to claim a missed check.
--
-- Vanilla engine progression drives village questboard visibility —
-- this client doesn't try to gate per-quest visibility on AP items.
-- See QUEST.md "Research: village quest visibility" for why the
-- hard-gate approach was abandoned.
local Quests = {}

local Lookups = require("AP_CLIENT/Lookups")
local Items = require("AP_CLIENT/Items")
local Session = require("AP_CLIENT/Session")
local Tracker = require("AP_CLIENT/Tracker")
local Weapons = require("AP_CLIENT/Weapons")

Quests.hooks_installed = false
Quests.swaps_applied = false
Quests.swap_attempts = 0
Quests.last_swap_log = {}

local function send_chat(text)
    local chatman = sdk.get_managed_singleton("snow.gui.ChatManager")
    if not chatman then return end
    chatman:setChatNetworkInfomation(tostring(text), 0, 0, 3, false)
end

-- ---------------------------------------------------------------
-- Quest catalog walkers
-- ---------------------------------------------------------------

local function visit_param_array(field_name, visitor)
    local qm = sdk.get_managed_singleton("snow.QuestManager")
    if not qm then return false end
    local container = nil
    pcall(function() container = qm:get_field(field_name) end)
    if not container then return false end
    local arr = nil
    pcall(function() arr = container:get_field("_Param") end)
    if not arr then return false end
    local count = nil
    pcall(function() count = arr:read_dword(0x1c) end)
    if not count or count <= 0 then return false end
    for i = 0, count - 1 do
        local elem = nil
        pcall(function() elem = arr:call("get_Item", i) end)
        if elem then
            local qn = nil
            pcall(function() qn = elem:get_field("_QuestNo") end)
            if qn and visitor(elem, qn) then return true end
        end
    end
    return false
end

-- Engine-sourced quest accessibility (gh #23). Two orthogonal gates,
-- both read from snow.progress.quest.ProgressQuestManager (read-only):
--
--   * Tier gate (per QuestLevel): is this quest's tier reached?
--       - URGENT quest (qn == its tier's urgent): isUnlockUrgent(Village,
--         QL) — flips true the moment the urgent becomes takeable.
--       - NON-URGENT quest: isClearUrgent(Village, QL) — flips true once
--         the tier's urgent is CLEARED (then the rest of the tier opens).
--   * Per-quest intra-tier gate: checkUnlockCondition(qn) — story/NPC
--     gating WITHIN an already-reached tier (e.g. talk-to-NPC quests).
--
-- A quest is accessible iff BOTH gates pass. Probe 4
-- (debug_tools/QuestRandoSpike.lua) characterized this across three
-- save states; checkUnlockCondition alone was wrong (true for gated
-- quests in an unreached tier — the #23 bug). QuestCategory.Village = 0.
--
-- All method handles cached on first use (resolve-once idiom). Bool
-- reads accept boolean or 0/1 number (some REFramework builds box bools).
local _pqm_methods = nil          -- { check_unlock, unlock_urgent, clear_urgent }
local _pqm_resolved = false
local VILLAGE_QUEST_CATEGORY = 0
local HUB_QUEST_CATEGORY = 2
local MR_QUEST_CATEGORY = 7

local function resolve_pqm_methods()
    if _pqm_resolved then return _pqm_methods end
    _pqm_resolved = true
    local td = sdk.find_type_definition("snow.progress.quest.ProgressQuestManager")
    if not td then return nil end
    local m = {}
    pcall(function()
        m.check_unlock = td:get_method("checkUnlockCondition(snow.quest.QuestNo)")
    end)
    pcall(function()
        m.unlock_urgent = td:get_method(
            "isUnlockUrgent(snow.quest.QuestCategory, snow.quest.QuestLevel)")
    end)
    pcall(function()
        m.clear_urgent = td:get_method(
            "isClearUrgent(snow.quest.QuestCategory, snow.quest.QuestLevel)")
    end)
    _pqm_methods = m
    return m
end

-- a1/a2 are the (optional) call args. checkUnlockCondition takes one
-- (quest_no); isUnlockUrgent/isClearUrgent take two (category, level).
-- Packed explicitly rather than via `...` — a `...` forward into the
-- pcall closure is illegal (varargs can't be an upvalue).
local function call_bool(method, pqm, a1, a2)
    if not method then return nil end
    local result = nil
    local ok = pcall(function()
        if a2 == nil then
            result = method:call(pqm, a1)
        else
            result = method:call(pqm, a1, a2)
        end
    end)
    if not ok then return nil end
    if type(result) == "boolean" then return result end
    if type(result) == "number" then return result ~= 0 end
    return nil
end

-- Returns:
--   true  -> engine says accessible (both gates pass)
--   false -> engine says NOT accessible
--   nil   -> couldn't read (singleton not loaded, not in a save, method
--            unresolved, or a call threw) — caller decides the fallback.
-- quest_no / quest_level are integers; is_urgent is a bool (quest is its
-- tier's urgent).
function Quests.EngineQuestAccessible(quest_no, quest_level, enemy_level, is_urgent)
    local m = resolve_pqm_methods()
    if not m then return nil end
    local pqm = sdk.get_managed_singleton("snow.progress.quest.ProgressQuestManager")
    if not pqm then return nil end

    local cu = call_bool(m.check_unlock, pqm, quest_no)

    -- Set quest category
    local qc
    if enemy_level == 0 then
        qc = VILLAGE_QUEST_CATEGORY
    elseif enemy_level == 3 then
        qc = MR_QUEST_CATEGORY
    else
        qc = HUB_QUEST_CATEGORY
    end

    -- PoC's 6* status will break these functions, so instead look at if t5 is unlocked
    if quest_no == 405600 then
        quest_level = 4
    end

    local tier
    -- The functions below don't work on 1* hub quests (always return false)
    -- Manually check if the target quest is 1* hub and return true for tier
    if qc == HUB_QUEST_CATEGORY and quest_level == 0 then
        tier = true
        if cu == nil or tier == nil then return nil end
        return (tier == true) and (cu == true)
    end

    -- Handle all other quests
    if is_urgent then
        tier = call_bool(m.unlock_urgent, pqm, qc, quest_level)
    else
        tier = call_bool(m.clear_urgent, pqm, qc, quest_level)
    end
    if cu == nil or tier == nil then return nil end
    return (tier == true) and (cu == true)
end

local function apply_swap_to_param(param, em_types, quest_no)
    local boss = nil
    local tgt = nil
    pcall(function() boss = param:get_field("_BossEmType") end)
    pcall(function() tgt = param:get_field("_TgtEmType") end)
    if not boss or not tgt then
        log.info(string.format(
            "[Quests] qn=%d: missing _BossEmType / _TgtEmType", quest_no))
        return false
    end
    -- Modification varies by quest type
    -- Handle single target quests
    if # em_types == 1 then
        local ok_boss = pcall(function() boss:call("Set", 0, em_types[1]) end)
        local ok_tgt = pcall(function() tgt:call("Set", 0, em_types[1]) end)
        if not ok_boss or not ok_tgt then
            pcall(function() boss:write_dword(0x20, em_types[1]) end)
            pcall(function() tgt:write_dword(0x20, em_types[1]) end)
        end
    -- handle same monster 2 target quests
    elseif em_types[1] == em_types[2] then
        local ok_boss_one = pcall(function() boss:call("Set", 0, em_types[1]) end)
        local ok_boss_two = pcall(function() boss:call("Set", 1, em_types[2]) end)
        local ok_tgt = pcall(function() tgt:call("Set", 0, em_types[1]) end)
        if not ok_boss_one or not ok_boss_two or not ok_tgt then
            pcall(function() boss:write_dword(0x20, em_types[1]) end)
            pcall(function() boss:write_dword(0x24, em_types[2]) end)
            pcall(function() tgt:write_dword(0x20, em_types[1]) end)
        end
    -- handle different monster 2 target quests
    else
        local ok_boss_one = pcall(function() boss:call("Set", 0, em_types[1]) end)
        local ok_boss_two = pcall(function() boss:call("Set", 1, em_types[2]) end)
        local ok_tgt_one = pcall(function() tgt:call("Set", 0, em_types[1]) end)
        local ok_tgt_two = pcall(function() tgt:call("Set", 1, em_types[2]) end)
        if not ok_boss_one or not ok_boss_two or not ok_tgt_one or not ok_tgt_two then
            pcall(function() boss:write_dword(0x20, em_types[1]) end)
            pcall(function() boss:write_dword(0x24, em_types[2]) end)
            pcall(function() tgt:write_dword(0x20, em_types[1]) end)
            pcall(function() tgt:write_dword(0x24, em_types[2]) end)
        end
    end
return true
end

function Quests.ApplySwaps()
    if Lookups.mode ~= "quest_rando" then return 0 end
    Quests.swap_attempts = Quests.swap_attempts + 1

    local pending = {}
    local total = 0
    for qn_str, em in pairs(Lookups.quest_swaps or {}) do
        local n = tonumber(qn_str)
        local em_n = em
        if n and em_n then
            pending[n] = em_n
            total = total + 1
        end
    end
    if total == 0 then return 0 end

    local applied = 0
    Quests.last_swap_log = {}
    for _, container_name in ipairs({"_normalQuestData", "_nomalQuestDataKohaku"}) do
        visit_param_array(container_name, function(elem, qn)
            local em = pending[qn]
            if em then
                if apply_swap_to_param(elem, em, qn) then
                    applied = applied + 1
                    Quests.last_swap_log[#Quests.last_swap_log + 1] =
                        (# em == 1) and string.format("  qn=%d em=%d", qn, em[1]) or string.format("  qn=%d em=%d, %d", qn, em[1], em[2])
                    pending[qn] = nil
                end
            end
            return false
        end)
    end

    Quests.swaps_applied = applied == total
    log.info(string.format(
        "[Quests] applied %d/%d swaps (attempt %d)",
        applied, total, Quests.swap_attempts))
    if applied < total then
        local missing = {}
        for qn, _ in pairs(pending) do missing[#missing + 1] = tostring(qn) end
        log.info("[Quests] missing quest_nos: " .. table.concat(missing, ", "))
    end
    return applied
end

function Quests.ApplySwapsIfReady()
    local qm = sdk.get_managed_singleton("snow.QuestManager")
    if not qm then return end
    Quests.ApplySwaps()
end

-- ---------------------------------------------------------------
-- Clear -> AP location send
-- ---------------------------------------------------------------

local function get_active_quest_no()
    local qm = sdk.get_managed_singleton("snow.QuestManager")
    if not qm then return nil end
    local qd = nil
    pcall(function() qd = qm:call("getActiveQuestData") end)
    if not qd then return nil end
    local qn = nil
    pcall(function() qn = qd:call("getQuestNo") end)
    if type(qn) == "number" then return qn end
    return nil
end

-- Build the two Clear: location names for a quest. Mirror of
-- locations.py:quest_clear_location_names.
local function clear_locations_for(quest_display_name)
    return {
        string.format("Clear: %s (1/2)", quest_display_name),
        string.format("Clear: %s (2/2)", quest_display_name),
    }
end

local function on_quest_cleared()
    if Lookups.mode ~= "quest_rando" then return end
    local solo, count = Session.IsSolo()
    if not solo then
        log.info(string.format(
            "[Quests] skipped clear-check (multiplayer quest, %d players)",
            count or -1))
        return
    end

    local qn = get_active_quest_no()
    if not qn then
        log.info("[Quests] setQuestClear fired but no active quest_no")
        return
    end

    -- Only quests in Lookups.quest_locations have a Clear: location
    -- on the AP server. Hub / rampage / event / quest_no=0 fire the
    -- same hook — silently drop.
    if not Lookups.quest_locations[tostring(qn)] then
        log.info(string.format(
            "[Quests] cleared qn=%d not in seed — skipping", qn))
        return
    end

    local quest_display_name = Lookups.quest_names[tostring(qn)] or tostring(qn)

    -- Soft gate: require the matching Unlock: <name> item. The
    -- starter (qn == Lookups.starting_quest) is precollected, so
    -- Items.Has() returns true for it after slot_connect. Other
    -- unlocks must arrive from the multiworld.
    local unlock_name = Lookups.quest_unlocks[tostring(qn)]
    if unlock_name and not Items.Has(unlock_name) then
        send_chat(string.format(
            "[AP] Cleared %s but unlock not yet held — re-clear once unlocked",
            quest_display_name))
        log.info(string.format(
            "[Quests] qn=%d cleared without unlock %q — dropping",
            qn, unlock_name))
        return
    end

    -- Weapon gate (when enabled): same soft-gate shape as Monsters.lua
    -- uses for hunts. The wielded weapon's license must be held; the
    -- precollected starter weapon is treated as always held by
    -- Weapons.HasLicenseForCurrent().
    if Lookups.weapons_enabled and not Weapons.HasLicenseForCurrent() then
        local wname = Weapons.GetCurrentName() or "?"
        send_chat(string.format(
            "[AP] Cleared %s but %s license not held — re-clear once licensed",
            quest_display_name, wname))
        log.info(string.format(
            "[Quests] qn=%d cleared without weapon license (%s) — dropping",
            qn, wname))
        return
    end

    local AP_REF = _G.AP_REF
    if not AP_REF or not AP_REF.APClient then return end
    local game = AP_REF.APClient:get_game()

    local ids = {}
    for _, loc_name in ipairs(clear_locations_for(quest_display_name)) do
        local id = AP_REF.APClient:get_location_id(loc_name, game)
        if id and id > 0 then
            ids[#ids + 1] = id
        else
            log.info(string.format(
                "[Quests] no location id for '%s'", loc_name))
        end
    end
    if #ids == 0 then return end

    local ok = AP_REF.APClient:LocationChecks(ids)
    if ok then
        Tracker.MarkQuestCleared(qn)
        send_chat(string.format("[AP] Sent check: Clear %s", quest_display_name))
        log.info(string.format(
            "[Quests] sent clear checks for qn=%d (%s) ids=%s",
            qn, quest_display_name, table.concat(
                (function() local s = {} for _, v in ipairs(ids) do s[#s+1] = tostring(v) end return s end)(), ","
            )))
    else
        log.info(string.format(
            "[Quests] LocationChecks failed for qn=%d", qn))
    end
end

-- ---------------------------------------------------------------
-- Hook install
-- ---------------------------------------------------------------

local function install_init_dict_hook()
    local td = sdk.find_type_definition("snow.QuestManager")
    if not td then return false, "QuestManager type not found" end
    local method = td:get_method("initQuestDataDictionary")
    if not method then return false, "initQuestDataDictionary not found" end
    local ok, err = pcall(function()
        sdk.hook(method,
            function(args) end,
            function(retval)
                local hok, herr = pcall(Quests.ApplySwaps)
                if not hok then
                    log.info("[Quests] initQuestDataDictionary post error: " .. tostring(herr))
                end
                return retval
            end)
    end)
    if not ok then return false, tostring(err) end
    return true
end

local function install_completion_hook()
    local td = sdk.find_type_definition("snow.QuestManager")
    if not td then return false, "QuestManager type not found" end
    local method = td:get_method("setQuestClear")
    if not method then return false, "setQuestClear not found" end
    local ok, err = pcall(function()
        sdk.hook(method,
            function(args)
                local hok, herr = pcall(on_quest_cleared)
                if not hok then
                    log.info("[Quests] setQuestClear pre error: " .. tostring(herr))
                end
            end,
            function(retval) return retval end)
    end)
    if not ok then return false, tostring(err) end
    return true
end

function Quests.InstallHooks()
    if Quests.hooks_installed then return end

    local ok1, err1 = install_init_dict_hook()
    log.info("[Quests] initQuestDataDictionary hook: " ..
        (ok1 and "ok" or ("fail — " .. tostring(err1))))

    local ok2, err2 = install_completion_hook()
    log.info("[Quests] setQuestClear hook: " ..
        (ok2 and "ok" or ("fail — " .. tostring(err2))))

    Quests.hooks_installed = ok1 and ok2

    -- If the player is already in-game when slot connects, the
    -- initQuestDataDictionary hook won't fire again at load. Apply
    -- swaps immediately so the player doesn't need a title-screen
    -- bounce.
    Quests.ApplySwapsIfReady()
end

return Quests
