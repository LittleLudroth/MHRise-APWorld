-- Weapon-type detection and license-name resolution.
-- Reads the current player's weapon type directly from the
-- snow.player.PlayerBase._playerWeaponType field — no need to call
-- PlayerManager.getPlayerWeaponType (which requires a hard-to-obtain
-- PlayerRequestEquipsData arg).
--
-- Stateless reader/translator: the held set lives in Items.held alongside
-- monster licenses. This module exposes GetCurrent / GetCurrentName for
-- inspection, and HasLicenseForCurrent for the hunt-time soft gate.
local Weapons = {}

local Items = require("AP_CLIENT/Items")
local Lookups = require("AP_CLIENT/Lookups")
-- Display names indexed by snow.player.PlayerWeaponType enum value
-- (stored as STRING keys — REFramework's Lua VM has been observed to
-- behave inconsistently with int-keyed tables; string keys sidestep
-- both pairs() and t[int] lookup bugs).
-- Source: mhrise_weapon_types.json dump (entries 0-13 are real weapons;
-- 14+ are sentinels like Max/AIStart, ignored). MUST match the names in
-- ap_world/data/weapons.py so license names resolve correctly.
Weapons.NAMES = {
    ["0"]  = "Great Sword",
    ["1"]  = "Switch Axe",
    ["2"]  = "Long Sword",
    ["3"]  = "Light Bowgun",
    ["4"]  = "Heavy Bowgun",
    ["5"]  = "Hammer",
    ["6"]  = "Gunlance",
    ["7"]  = "Lance",
    ["8"]  = "Sword & Shield",
    ["9"]  = "Dual Blades",
    ["10"] = "Hunting Horn",
    ["11"] = "Charge Blade",
    ["12"] = "Insect Glaive",
    ["13"] = "Bow",
}

-- Returns the integer weapon-type enum for the current master player, or
-- nil if not in a state where the player exists (title screen, loading).
function Weapons.GetCurrent()
    local pm = sdk.get_managed_singleton("snow.player.PlayerManager")
    if not pm then return nil end
    local ok, player = pcall(function() return pm:call("findMasterPlayer") end)
    if not ok or not player then return nil end
    local field_ok, value = pcall(function() return player:get_field("_playerWeaponType") end)
    if not field_ok or type(value) ~= "number" then return nil end
    return value
end

function Weapons.GetCurrentName()
    local id = Weapons.GetCurrent()
    if not id then return nil end
    return Weapons.NAMES[tostring(id)] or string.format("Weapon#%d", id)
end

-- Returns true if the player holds the license for their currently-equipped
-- weapon. Defaults true (allow) if weapon type can't be read — fail-open
-- so we don't accidentally block hunts during loading screens.
function Weapons.HasLicenseForCurrent()
    local id = Weapons.GetCurrent()
    if not id then return true end
    local key = tostring(id)
    local license_name = Lookups.weapon_type_to_item_name[key]
    if not license_name then
        -- No mapping for this weapon type (shouldn't happen if slot_data
        -- shipped correctly). Fail-open.
        return true
    end
    -- Starter weapon is precollected — treat as always held, mirroring
    -- how the monster gate treats the starter monster.
    if Lookups.starting_weapon and Weapons.NAMES[key] == Lookups.starting_weapon then
        return true
    end
    return Items.Has(license_name)
end

return Weapons
