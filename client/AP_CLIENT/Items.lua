-- Tracks which items the player has received from the AP server.
-- v1 only cares about license items (one per huntable monster) and the
-- Victory item, but this module is the central place to handle any future
-- item types (filler, key items, etc.).
--
-- Soft gate: holding a license enables checks for that monster's hunt
-- locations. Hunting an unlicensed monster does nothing (the death hook
-- silently drops the event).
local Items = {}

-- Set of license item names the player holds. Keys are item names like
-- "Rathian License"; values are always true.
Items.held = {}

Items.has_victory = false

Items.reached_medium = false
Items.reached_hard = false
Items.reached_goal = false

-- Cached singletons
local PlayerManager
local QuestManager
local CreatureManager

-- A list of spawned birds that need to be deleted at quest's end
local spawned_birds = {}

-- A list of where each bird type is found, originally created by Bimmr
local SPIRIT_BIRDS = {
    atk = 10,
    def = 11,
    hp = 12,
    stm = 13,
    all = 14,
    gold = 30
}

-- A display string for whatever the most recent buff/debuff/status applied was
local last_applied = ""

Items.last_index = 0
local Lookups = require("AP_CLIENT/Lookups")

-- Raw item IDs that arrived before APClientPP had the data package
-- ready to resolve them to names. The very first on_items_received
-- batch on a freshly-opened socket (which is where precollected items
-- like the starter unlock land) can fire before the package sync, in
-- which case get_item_name returns the literal "Unknown" string.
-- Without retry, the starter quest's `Unlock:` item never enters
-- Items.held and the tracker's Available section is empty. We stash
-- the raw ids here and re-resolve on on_data_package_changed and at
-- the start of every subsequent Items.Receive call.
Items.pending_ids = {}

function Items.Reset()
    Items.held = {}
    Items.has_victory = false
    Items.reached_medium = false
    Items.reached_hard = false
    Items.reached_goal = false
    Items.last_index = 0
    Items.pending_ids = {}
    PlayerManager = nil
    QuestManager = nil
    CreatureManager = nil
    last_applied = ""
end

function Items.Has(item_name)
    return Items.held[item_name] == true
end

local function send_chat(text)
    local chatman = sdk.get_managed_singleton("snow.gui.ChatManager")
    if not chatman then return end
    chatman:setChatNetworkInfomation(tostring(text), 0, 0, 3, false)
end

local function extract_item_id(item)
    local item_id = nil
    pcall(function() item_id = item.item or item:get_item() end)
    return item_id
end

local function extract_item_index(item)
    local item_index = nil
    pcall(function() item_index = item.index or item:get_index() end)
    return item_index
end

local function resolve_id_to_name(ap_client, item_id)
    if not (ap_client and item_id) then return nil end
    local name = nil
    pcall(function()
        name = ap_client:get_item_name(item_id, ap_client:get_game())
    end)
    -- "Unknown" is APClientPP's unresolved-id sentinel — the data
    -- package hasn't caught up to this id yet.
    if name == "Unknown" then return nil end
    return name
end

-- Apply a successfully-resolved name to the held set. Returns true if
-- this was new state (i.e. worth a chat notification).
local function apply_resolved(ap_client, name, index)
    if name == "Victory" then
        if Items.has_victory then return false end
        Items.has_victory = true
        return true
    end

    -- Resolve one-time filler or trap items if they are new
    if index <= Items.last_index or Items.held[name] then return false end
    if name == "Full Heal" then
        Items.TriggerHeal()
    elseif name == "Free Birds" then
        Items.TriggerBirds()
    elseif name == "Random Buff" then
        Items.TriggerBuff()
    elseif name == "Dull Trap" then
        Items.TriggerDullTrap()
    elseif name == "Status Trap" then
        Items.TriggerStatusTrap()
    elseif name == "Debuff Trap" then
        Items.TriggerDebuffTrap()
    else
        -- If item isn't a single use, it goes in held
        Items.held[name] = true
    end

    -- Set item index to latest value
    Items.last_index = index
    return true
end

-- A simplified version of apply_resolved that is used for items that arrived prior to
-- the name table being resolved. Since we don't have access to item index, it will not actually
-- do anything with filler or trap items to ensure they aren't repeated
local function apply_resolved_delayed(name)
    if name == "Victory" then
        if Items.has_victory then return false end
        Items.has_victory = true
        return true
    end

    -- check if the item is a filler or trap
    -- Back compat: will always pass if filler_names is empty
    if Lookups.filler_names[name] ~= nil then return false end

    if Items.held[name] then return false end
    Items.held[name] = true
    return true
end

-- Retry name resolution for any ids that came in before APClientPP's
-- data package was ready. Called from on_data_package_changed (when
-- the package syncs after slot_connect) and at the head of every
-- subsequent Items.Receive call (belt-and-suspenders — a later batch
-- arriving with the same package update would also re-prime the
-- cache). Returns the number of newly-resolved items.
function Items.ResolvePending(ap_client, silent)
    if not ap_client then return 0 end
    if next(Items.pending_ids) == nil then return 0 end
    local count = 0
    local still_pending = {}
    for _, item_id in ipairs(Items.pending_ids) do
        local name = resolve_id_to_name(ap_client, item_id)
        if name then
            if apply_resolved_delayed(name) then
                if not silent then send_chat("[AP] Received: " .. name) end
                count = count + 1
            end
        else
            still_pending[#still_pending + 1] = item_id
        end
    end
    Items.pending_ids = still_pending
    if count > 0 then
        log.info(string.format(
            "[Items] resolved %d previously-pending item(s); %d still pending",
            count, #still_pending))
    end
    return count
end

-- Called from the AP on_items_received callback. `items` is a list of
-- received item objects from APClientPP, each exposing :get_name().
-- AP occasionally re-sends items the player already holds (reconnect /
-- catch-up); the chat notification is suppressed in that case so the
-- player only sees a "Received" line for genuinely new items.
--
-- `silent`: when true, state still updates but no chat lines are
-- emitted. Used by the catch-up window right after slot_connect so the
-- chat doesn't get flooded with one "[AP] Received: X" per held item.
function Items.Receive(items, ap_client, silent)
    if type(items) ~= "table" then return 0 end
    -- Get needed singletons if not already defined.
    if not PlayerManager then PlayerManager = sdk.get_managed_singleton("snow.player.PlayerManager") end
    if not QuestManager then QuestManager = sdk.get_managed_singleton("snow.QuestManager") end
    if not CreatureManager then CreatureManager = sdk.get_managed_singleton("snow.envCreature.EnvironmentCreatureManager") end

    -- Check for a saved index value for this seed if we currently don't have one
    if Items.last_index == 0 then
        local filename = "APSAVE_" .. ap_client:get_seed() .. "_" .. ap_client:get_slot() .. ".json"
        local savedata = json.load_file(filename)
        if savedata ~= nil and savedata["last_index"] ~= nil then
            Items.last_index = tonumber(savedata["last_index"])
        end
    end
    
    -- Retry any leftover ids before processing the new batch — a fresh
    -- batch can mean the data package just synced.
    Items.ResolvePending(ap_client, silent)
    local count = 0
    local deferred = 0
    for _, item in ipairs(items) do
        local item_id = extract_item_id(item)
        local index = extract_item_index(item)
        local name = resolve_id_to_name(ap_client, item_id)
        if name and index then
            if apply_resolved(ap_client, name, index) then
                if not silent then send_chat("[AP] Received: " .. name) end
                if not silent and name == "Random Buff" and last_applied ~= "" then
                    send_chat("Applied buff: " .. last_applied) end
                if not silent and name == "Debuff Trap" and last_applied ~= "" then
                    send_chat("Applied debuff: " .. last_applied) end
                if not silent and name == "Status Trap" and last_applied ~= "" then
                    send_chat("Applied status: " .. last_applied) end
                last_applied = ""
                count = count + 1
            end
        elseif item_id then
            -- Data package not yet ready for this id. Stash it; we'll
            -- resolve in on_data_package_changed or on the next batch.
            Items.pending_ids[#Items.pending_ids + 1] = item_id
            deferred = deferred + 1
        end
    end
    if deferred > 0 then
        log.info(string.format(
            "[Items] %d item(s) deferred pending data package sync", deferred))
    end

    -- Update the current save file with the latest index seen
    local filename = "APSAVE_" .. ap_client:get_seed() .. "_" .. ap_client:get_slot() .. ".json"
    local save_data = {}
    save_data["last_index"] = Items.last_index
    json.dump_file(filename, save_data)

    -- Check huntathon tier logic if needed
    if Lookups.mode == "hunt_a_thon" then
        local next = next
        if next(Lookups.license_to_tier) == nil then
            -- back-compat: we can skip checking tier status if license_to_tier is empty
        else
            -- Count how many items are in each tier
            local easy = 0
            local medium = 0
            local hard = 0

            for license,_ in pairs(Items.held) do
                local tier = Lookups.license_to_tier[license]
                if tier == "easy" then
                    easy = easy + 1
                elseif tier == "medium" then
                    medium = medium + 1
                elseif tier == "hard" then
                    hard = hard + 1
                end
            end

            -- Check if player has reached each tier
            if not Items.reached_medium then
                Items.reached_medium = easy >= math.ceil(Lookups.easy_monster_count / 2)
            end

            if Items.reached_medium and not Items.reached_hard then
                Items.reached_hard = medium >= math.ceil(Lookups.medium_monster_count / 2)
            end

            if Items.reached_hard and not Items.reached_goal then
                Items.reached_goal = hard >= math.ceil(Lookups.hard_monster_count / 2)
            end
        end
    end
    return count
end

-- These functions implement the effects of the various filler items and traps in the mod
-- They are instant effects and should only trigger once per filler item
-- Any function other than Emote Trap will fizzle if activated outside of a hunt

-- This function gets the player's max hp and sets their current health to that value
-- It returns false if heal fails for any reason
function Items.TriggerHeal()
    -- Confirm needed singletons are already defined, break if they aren't
    if PlayerManager == nil then return false end
    if QuestManager == nil then return false end

    -- Start by checking if a quest is actually active before doing anything
    local quest_status = QuestManager:get_field("_QuestStatus")
    if quest_status ~= 2 then return false end -- Any state other than quest active should not trigger the effect

    local masterPlayer = PlayerManager:call("findMasterPlayer")
    if not masterPlayer then return false end

    local player_data = masterPlayer:call("get_PlayerData")
    if not player_data then return false end

    local health = player_data:get_field("_vitalMax") * 1.
    if health == nil then return false end

    player_data:call("setVital(System.Single)", health)
    player_data:set_field("_r_Vital", health)
    return true
end

-- This function actually spawns birds at the player's location
-- The approach for this function was inspired by Bimmr's SpiritBird mod on Nexus
function Items.TriggerBirds()
    if PlayerManager == nil then return false end
    if QuestManager == nil then return false end
    if CreatureManager == nil then return false end

    -- Start by checking if a quest is actually active before doing anything
    local quest_status = QuestManager:get_field("_QuestStatus")
    if quest_status ~= 2 then return false end -- Any state other than quest active should not trigger the effect

    -- Get player's location to spawn birds
    local masterPlayer = PlayerManager:call("findMasterPlayer")
    if not masterPlayer then return false end

    local player_object = masterPlayer:call("get_GameObject")
    if not player_object then return false end

    -- Get the list of critters, including the birds
    local ec_list = CreatureManager:get_field("_EcPrefabList")
    if not ec_list then return false end

    local ec_items = ec_list:get_field("mItems")
    if not ec_items then return false end

    -- Spawn two atk/def birds and 5 hp/stm birds at the player's location
    local bird_types = {"atk", "atk", "def", "def", "hp", "hp", "hp", "hp", "hp", "stm", "stm", "stm", "stm", "stm"}
    for _,bird_type in pairs(bird_types) do
        -- Get the bird data from prefabs
        local ec_bird = ec_items[SPIRIT_BIRDS[bird_type]]
        if not ec_bird then return false end

        -- Ensure bird is ready to be spawned
        if not ec_bird:call("get_Standby") then
            ec_bird:call("set_Standby", true)
        end

        -- Get player location and spawn the bird
        local player_location = player_object:call("get_Transform"):call("get_Position")
        local bird = ec_bird:call("instantiate(via.vec3)", player_location)
        if sdk.is_managed_object(bird) then  -- Confirm that the bird spawned before preparing to delete it
            table.insert(spawned_birds, bird)
        end
    end
end

-- A function that removes any birds spawned by the mod from the game at quest's end
-- Also used when the script is reset to ensure that the birds aren't there forever
function Items.ClearBirds()
    for _, bird in ipairs(spawned_birds) do
        bird:call("destroy", bird)
    end
    spawned_birds = {}
end

-- This function grants the player a random buff from this list
-- 25% attack increase, 25% defence increase, fish health regeneration
-- stamina use reduction, 25% crit rate increase, debuff prevention
-- Unfortunately, element, status, and resistance buffs aren't easily accessible.
-- I don't want to have to add timers/buff management to the client, so those buffs aren't available for now.
function Items.TriggerBuff()
    if PlayerManager == nil then return false end
    if QuestManager == nil then return false end

    -- Start by checking if a quest is actually active before doing anything
    local quest_status = QuestManager:get_field("_QuestStatus")
    if quest_status ~= 2 then return false end -- Any state other than quest active should not trigger the effect

    -- Get important singletons for player data
    local masterPlayer = PlayerManager:call("findMasterPlayer")
    if not masterPlayer then return false end

    local player_data = masterPlayer:call("get_PlayerData")
    if not player_data then return false end

    -- Setting a buff requires setting its value to something and setting its timer
    -- These can be found in player_data
    -- The buff to set is determined randomly from the available buff table
    local buff_table = {"atk", "def", "fish_regen", "stamina_buff", "crit", "no_debuff"}
    local buff = buff_table[math.random(#buff_table)]

    if buff == "atk" then
        local atk_timer = player_data:get_field("_AtkUpBuffSecondTimer")
        -- If the player has an existing buff, double the timer
        if atk_timer ~= 0 then
            player_data:set_field("_AtkUpBuffSecondTimer", atk_timer * 2)
        -- Otherwise, give a 20% atk increase for 2 minutes
        else
            local buff_strength = player_data:get_field("_Attack") * 0.25
            player_data:set_field("_AtkUpBuffSecond", buff_strength)
            player_data:set_field("_AtkUpBuffSecondTimer", 12000)
        end
        last_applied = "Attack Up"
        return true
    elseif buff == "def" then
        local def_timer = player_data:get_field("_DefUpBuffSecondTimer")
        -- If the player has an existing buff, double the timer
        if def_timer ~= 0 then
            player_data:set_field("_DefUpBuffSecondTimer", def_timer * 2)
        -- Otherwise, give a 25% def increase for 2 minutes
        else
            local buff_strength = player_data:get_field("_Defence") * 0.25
            player_data:set_field("_DefUpBuffSecond", buff_strength)
            player_data:set_field("_DefUpBuffSecondTimer", 12000)
        end
        last_applied = "Defense Up"
        return true
    elseif buff == "fish_regen" then
        local fish_timer = player_data:get_field("_FishRegeneEnableTimer")
        -- If the player has an existing buff, double the timer
        if fish_timer ~= 0 then
            player_data:set_field("_FishRegeneEnableTimer", fish_timer * 2)
        -- Otherwise, give fish regen increase for 2 minutes
        else
            player_data:set_field("_FishRegeneEnableTimer", 12000)
        end
        last_applied = "Fish Regeneration"
        return true
    elseif buff == "stamina_buff" then
        player_data:set_field("_StaminaUpBuffSecondTimer", 12000)
        return true
    elseif buff == "crit" then
        local crit_timer = player_data:get_field("_AtkUpEcSecondTimer")
        -- If the player has an existing buff, double the timer
        if crit_timer ~= 0 then
            player_data:set_field("_AtkUpEcSecondTimer", crit_timer * 2)
        -- Otherwise, give 25% crit up for 2 minutes
        else
            player_data:set_field("_AtkUpEcSecond", 25)
            player_data:set_field("_AtkUpEcSecondTimer", 12000)
        end
        last_applied = "stamina_buff"
        return true
    elseif buff == "no_debuff" then
        player_data:set_field("_DebuffPreventionTimer", 12000)
        last_applied = "Debuff Prevention"
        return true
    else
        return false
    end
end

-- This function sets the player's sharpness to 0 and the sharpness tier to red
function Items.TriggerDullTrap()
    if PlayerManager == nil then return false end
    if QuestManager == nil then return false end

    -- Start by checking if a quest is actually active before doing anything
    local quest_status = QuestManager:get_field("_QuestStatus")
    if quest_status ~= 2 then return false end -- Any state other than quest active should not trigger the effect

    -- Change sharpness level to 0 and sharpness gauge to 0
    -- It won't update the bar until player hits something
    local masterPlayer = PlayerManager:call("findMasterPlayer")
    if not masterPlayer then return false end
    masterPlayer:set_field("<SharpnessLv>k__BackingField", 0)
    masterPlayer:set_field("<SharpnessGauge>k__BackingField", 0)
    return true
end

-- This function grants the player a random status from the following list
-- any elemental blight, blast, hellfire, stink, bleed
function Items.TriggerStatusTrap()
    if PlayerManager == nil then return false end
    if QuestManager == nil then return false end

    -- Start by checking if a quest is actually active before doing anything
    local quest_status = QuestManager:get_field("_QuestStatus")
    if quest_status ~= 2 then return false end -- Any state other than quest active should not trigger the effect

    -- Get important singletons for player data
    local masterPlayer = PlayerManager:call("findMasterPlayer")
    if not masterPlayer then return false end

    -- Set up table of possible statuses
    local status_table = {"fireblight", "waterblight", "iceblight", "thunderblight", "dragonblight", "blast", "stink", "bleed"}
    local status = status_table[math.random(#status_table)]

    if status == "fireblight" then
        masterPlayer:set_field("_FireLDurationTimer", 800)
        last_applied = "Fireblight"
        return true
    elseif status == "waterblight" then
        masterPlayer:set_field("_WaterLDurationTimer", 1500)
        last_applied = "Waterblight"
        return true
    elseif status == "iceblight" then
        masterPlayer:set_field("_IceLDurationTimer", 1500)
        last_applied = "Iceblight"
        return true
    elseif status == "thunderblight" then
        masterPlayer:set_field("_ThunderLDurationTimer", 1500)
        last_applied = "Thunderblight"
        return true
    elseif status == "dragonblight" then
        masterPlayer:set_field("_DragonLDurationTimer", 1500)
        last_applied = "Dragonblight"
        return true
    elseif status == "blast" then
        -- note that this effect just makes the player explode instantly
        masterPlayer:set_field("_BombDurationTimer", 1)
        last_applied = "Blastblight"
        return true
    elseif status == "stink" then
        masterPlayer:set_field("_StinkDurationTimer", 3000)
        last_applied = "Stench"
        return true
    elseif status == "bleed" then
        masterPlayer:set_field("_BleedingDebuffTimer", 1000)
        last_applied = "Bleed"
        return true
    else
        return false
    end
end

-- This function grants the player a random debuff that scales with their current
-- stats. Possible effects are resistance down and def down. I wanted to do damage debuffs, but they don't exist in game
function Items.TriggerDebuffTrap()
    if PlayerManager == nil then return false end
    if QuestManager == nil then return false end

    -- Start by checking if a quest is actually active before doing anything
    local quest_status = QuestManager:get_field("_QuestStatus")
    if quest_status ~= 2 then return false end -- Any state other than quest active should not trigger the effect

    -- Get important singletons for player data
    local masterPlayer = PlayerManager:call("findMasterPlayer")
    if not masterPlayer then return false end

    -- Set up table of possible statuses
    local debuff_table = {"def_down", "res_down"}
    local debuff = debuff_table[math.random(#debuff_table)]

    if debuff == "def_down" then
        masterPlayer:set_field("_DefenceDownDurationTimer", 3000)
        last_applied = "Defense Down"
        return true
    elseif debuff == "res_down" then
        masterPlayer:set_field("_ResistanceDownDurationTimer", 3000)
        last_applied = "Resitance Down"
        return true
    else
        return false
    end
end

re.on_script_reset(Items.ClearBirds())

return Items
