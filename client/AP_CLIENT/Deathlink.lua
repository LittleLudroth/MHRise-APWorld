-- Deathlink handler
-- Hooks onto death camera to detect deaths
-- Kills player using setDie function when deathlink arrives
-- In this version, deathlinks that arrive while player is in lobby or tent are dropped
local Deathlink = {}
local PlayerManager
local ChangeSpaceManager

Deathlink.hook_installed = false
Deathlink.deathlink_called = false
Deathlink.last_death_time = 0

-- Called by the AP on_bounced callback upon recieving an external deathlink
function Deathlink.KillHunter()
    -- Get PlayerManager if not already saved
    if not PlayerManager then
        PlayerManager = sdk.get_managed_singleton("snow.player.PlayerManager")
    end
    if PlayerManager == nil then return false end

    -- Get ChangeSpaceManager if not already saved
    if not ChangeSpaceManager then
        ChangeSpaceManager = sdk.get_managed_singleton("snow.wwise.WwiseChangeSpaceWatcher")
    end
    if ChangeSpaceManager == nil then return false end

    -- Check if the player is currently in a tent to avoid causing a visual bug
    if ChangeSpaceManager:call("get_IsCamp()") then
        log.info("[Deathlink] Player in camp, kill function aborted")
        return false
    end

    -- Get the master player. The player type is different in lobby and in quest
    local masterPlayer = PlayerManager:call("findMasterPlayer")
    if masterPlayer == nil then return false end

    -- Set flag so hook function can check if death trigger was due to deathlink
    Deathlink.deathlink_called = true

    -- If player is in lobby, there is no setDie function and call will return nil
    if masterPlayer:call("setDie") == nil then 
        log.info("[Deathlink] Deathlink recieved but kill failed")
        Deathlink.deathlink_called = false -- no death sent, reset the flag here
        return false
    else -- death is detected, flag will be reset by on_player_death
        log.info("[Deathlink] Deathlink recieved and kill succeeded")
        return true
    end
end

-- Getter that returns time of last death
function Deathlink.GetLastDeathTime()
    return Deathlink.last_death_time
end

-- Handles sending a deathlink message when player dies
local function on_player_death()
    local AP_REF = _G.AP_REF
    if not AP_REF or not AP_REF.APClient then return end
    if AP_REF.APTags[1] ~= "DeathLink" then
        log.info("[Deathlink] deathlink isn't enabled, dropping player death")
        return end -- If deathlink isn't enabled, don't send anything

    local tags = {"DeathLink"}
    local source = AP_REF.APClient:get_player_alias(AP_REF.APClient:get_player_number())

    -- Use a random death descriptor for cause
    local descriptors = {"crushed", "eaten", "destroyed", "ripped in half", "stomped",
                         "hunted", "vaporized", "put to sleep", "sent back to camp", 
                         "trampled", "carted", "scorched", "drowned", "smashed"}
    local cause = source .. " was " .. descriptors[math.random(#descriptors)] .. " by a monster"
    local data = {time=Deathlink.last_death_time, cause=cause, source=source}

    local ok = AP_REF.APClient:Bounce(data, {}, {}, tags)
    if ok then
        log.info("[Deathlink] on_player_death sent deathlink message")
    else 
        log.info("[Deathlink] on_player_death bounce call for deathlink failed")
    end
end

-- Hooks onto wwise.WwiseChangeSpaceWatcher's onPlayerDeath method to detect player deaths
function Deathlink.InstallHook()
    if Deathlink.hook_installed then return end

    local space_watcher = sdk.find_type_definition("snow.wwise.WwiseChangeSpaceWatcher")
    if not space_watcher then
        log.info("[Deathlink] WwiseChangeSpaceWatcher type not found - hook not installed")
    end

    local method = space_watcher:get_method("onPlayerDie")
    if not method then
        log.info("[Deathlink] onPlayerDie not found — hook not installed")
        return
    end

    sdk.hook(method, function(args)
        -- update time of most recent death
        Deathlink.last_death_time = os.time()

        --Check if death was due to deathlink trigger
        if Deathlink.deathlink_called then
            Deathlink.deathlink_called = false
            log.info("[Deathlink] Ignored death triggered by deathlink message")
            return end
        on_player_death() --NOTE: It would be nice to get monster name to populate message
    end, function(retval) return retval end)

    Deathlink.hook_installed = true
    log.info("[Deathlink] OnPlayerDie hook installed")
end

return Deathlink