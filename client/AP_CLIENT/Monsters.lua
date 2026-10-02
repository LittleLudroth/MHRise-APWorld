-- Hooks snow.enemy.EnemyCharacterBase.dieNotifyToQuest. On every enemy
-- death/capture, resolves em_type -> license item name (via Lookups), then
-- -> AP location ids (Hunt {name} (1/2) + (2/2)) via the AP client's data
-- package, and sends a LocationChecks call.
--
-- Soft gate: if the player doesn't hold the corresponding license, the
-- check is silently dropped. Future versions may flip
-- this to a hard gate by blocking damage / hiding quests.
local Monsters = {}

local Lookups = require("AP_CLIENT/Lookups")
local Items = require("AP_CLIENT/Items")
local Session = require("AP_CLIENT/Session")
local Weapons = require("AP_CLIENT/Weapons")
local Tracker = require("AP_CLIENT/Tracker")

Monsters.hook_installed = false

-- Cached reflection handles. Resolved lazily on first hook fire because
-- the type definition isn't always available at script-load time (it is
-- now, but defensive caching is cheap).
local enemy_type_field = nil

local function resolve_enemy_type_field()
    if enemy_type_field then return enemy_type_field end
    local td = sdk.find_type_definition("snow.enemy.EnemyCharacterBase")
    if not td then return nil end
    enemy_type_field = td:get_field("<EnemyType>k__BackingField")
    return enemy_type_field
end

-- Returns the localized monster name for a given em_type, or nil. Uses the
-- same MessageManager:getEnemyNameMessage path as the dump tool, for chat
-- output only — not load-bearing.
local message_manager = nil
local get_enemy_name_message_method = nil
local function get_enemy_name(em_type)
    if not message_manager then
        message_manager = sdk.get_managed_singleton("snow.gui.MessageManager")
    end
    if not get_enemy_name_message_method then
        local td = sdk.find_type_definition("snow.gui.MessageManager")
        if td then
            get_enemy_name_message_method = td:get_method("getEnemyNameMessage")
        end
    end
    if not message_manager or not get_enemy_name_message_method then return nil end
    local ok, name = pcall(function()
        return get_enemy_name_message_method:call(message_manager, em_type)
    end)
    if ok and type(name) == "string" and #name > 0 then return name end
    return nil
end

local function send_chat(text)
    local chatman = sdk.get_managed_singleton("snow.gui.ChatManager")
    if not chatman then return end
    chatman:setChatNetworkInfomation(tostring(text), 0, 0, 3, false)
end

-- Build the two location names for a license item name. Mirror of
-- locations.py:hunt_location_names. License "Rathian License" ->
-- ["Hunt Rathian (1/2)", "Hunt Rathian (2/2)"].
local function hunt_locations_for_license(item_name)
    local monster_name = item_name:match("^(.*) License$")
    if not monster_name then return nil end
    return {
        string.format("Hunt %s (1/2)", monster_name),
        string.format("Hunt %s (2/2)", monster_name),
    }
end

local function on_enemy_died(em_type)
    if not Lookups.connected then return end

    -- Single-player gate: skip checks when in a MP quest. Sidesteps
    -- host/guest license desync. dieNotifyToQuest only fires during a
    -- quest, so the player count is meaningful here.
    local solo, count = Session.IsSolo()
    if not solo then
        log.info(string.format("[Monsters] skipped check (multiplayer quest, %d players)", count or -1))
        return
    end

    local item_name = Lookups.GetItemNameByEmType(em_type)
    if not item_name then
        -- Unknown em_type (small monster not in seed, etc.) — silently drop.
        return
    end

    -- Soft gate: only send checks for monsters within regions that we can reach 
    -- and whose license we hold OR for the starting monster
    -- (precollected — never arrives via on_items_received in some AP setups,
    -- so we treat it as always held).
    local monster_name = item_name:match("^(.*) License$")
    local is_starter = (monster_name ~= nil) and (monster_name == Lookups.starting_monster)
    if not is_starter and not Items.Has(item_name) then
        log.info(string.format("[Monsters] skipped check for %s (no license held)", item_name))
        return
    end

    -- Additionally check if we can actually reach the tier the monster is in
    -- If we cannot, don't send the check
    local tier = Lookups.license_to_tier[item_name]
    local can_reach_tier
    if tier == "medium" then
        can_reach_tier = Items.reached_medium
    elseif tier == "hard" then
        can_reach_tier = Items.reached_hard
    elseif tier == "goal" then
        can_reach_tier = Items.reached_goal
    else
        -- back-compat: licenses not in license_to_tier default to true
        -- For old seeds, this means all licenses will default to true
        can_reach_tier = true
    end

    if not can_reach_tier then
        log.info(string.format("[Monsters] skipped check for %s (can't reach tier)", item_name))
        return
    end

    -- Weapon gate (when enabled). Same soft-gate model as the monster
    -- gate above: the player can fight, but the check only sends if they
    -- hold the license for their currently-equipped weapon.
    if Lookups.weapons_enabled and not Weapons.HasLicenseForCurrent() then
        local wname = Weapons.GetCurrentName() or "?"
        log.info(string.format("[Monsters] skipped check (no license for %s)", wname))
        return
    end

    local loc_names = hunt_locations_for_license(item_name)
    if not loc_names then return end

    local AP_REF = _G.AP_REF
    if not AP_REF or not AP_REF.APClient then return end
    local game = AP_REF.APClient:get_game()

    local ids = {}
    for _, loc_name in ipairs(loc_names) do
        local id = AP_REF.APClient:get_location_id(loc_name, game)
        if id and id > 0 then
            ids[#ids + 1] = id
        else
            log.info(string.format("[Monsters] no location id for %s", loc_name))
        end
    end
    if #ids == 0 then return end

    local ok = AP_REF.APClient:LocationChecks(ids)
    local pretty = get_enemy_name(em_type) or monster_name or ("em_type=" .. tostring(em_type))
    if ok then
        -- AP doesn't echo self-checks via on_location_checked, so mark
        -- the tracker locally on a successful send. monster_name is
        -- the seed-canonical name (license-stripped); Tracker section
        -- builders compare against this same form.
        if monster_name then Tracker.MarkHunted(monster_name) end
        send_chat(string.format("[AP] Sent check: Hunt %s", pretty))
        log.info(string.format("[Monsters] sent checks for %s ids=%s", pretty, table.concat(
            (function() local s = {} for _, v in ipairs(ids) do s[#s+1] = tostring(v) end return s end)(), ","
        )))
    else
        log.info(string.format("[Monsters] LocationChecks call failed for %s", pretty))
    end
end

function Monsters.InstallHook()
    if Monsters.hook_installed then return end

    local td = sdk.find_type_definition("snow.enemy.EnemyCharacterBase")
    if not td then
        log.info("[Monsters] EnemyCharacterBase type not found — hook not installed")
        return
    end
    local method = td:get_method("dieNotifyToQuest")
    if not method then
        log.info("[Monsters] dieNotifyToQuest not found — hook not installed")
        return
    end

    sdk.hook(method, function(args)
        local ok, err = pcall(function()
            local enemy = sdk.to_managed_object(args[2])
            if not enemy then return end
            local field = resolve_enemy_type_field()
            if not field then return end
            local em_type = field:get_data(enemy)
            if type(em_type) ~= "number" then return end
            on_enemy_died(em_type)
        end)
        if not ok then
            log.info("[Monsters] hook callback error: " .. tostring(err))
        end
    end, function(retval) return retval end)

    Monsters.hook_installed = true
    log.info("[Monsters] dieNotifyToQuest hook installed")
end

return Monsters
