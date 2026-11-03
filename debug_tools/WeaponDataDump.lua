-- WeaponDataDump - a tool that access and dumps the weapon data catalog for MHRise
--
-- Iterates each of the weapon data modules in snow.Data.ContentsIdDataManager, including kinsects
-- Each module has an array of weapon data objects
--
-- Gathers weapon_name, weapon_type, rarity, element_type and weapon_id for all valid weapons
--
-- Result dumped to reframework/data/mhrise_weapon_data.json
-- Output feeds ap_world/data/weapon_data.py
--
-- Dev-only. Drop into <install>/reframework/autorun/. No AP server
-- connection needed. Never bundled into the player client zip (see
-- .github/workflows/release.yml AUTORUN_FILES allow-list).
--
-- Trigger: REFramework overlay button "MHRise Weapon Data Dump".
-- Don't auto-run on load — the ContentsIdDataManager singleton isn't
-- populated until well after script init.

if reframework:get_game_name() ~= "mhrise" then return end

log.info("[weapon-data] Loading...")

local OUTPUT_NAME = "mhrise_weapon_data.json"
local LOG_TAG = "[Weapon Dump] "

local state = {
    last_result_preview = nil,
    is_window_open = false,
    is_running = false,
}

local weapon_modules = {
    "_GreatSwordIdData",
    "_HammerIdData",
    "_LanceIdData",
    "_ShortSwordIdData",
    "_LightBowgunIdData",
    "_HeavyBowgunIdData",
    "_DualBladesIdData",
    "_LongSwordIdData",
    "_HornIdData",
    "_GunLanceIdData",
    "_BowIdData",
    "_SlashAxeIdData",
    "_ChargeAxeIdData",
    "_InsectGlaiveIdData",
    "_InsectIdModule",
}

local function safe_str(v)
    local ok, s = pcall(tostring, v)
    if ok then return s end
    return "<tostring error>"
end
local function log_info(msg) log.info(LOG_TAG .. msg) end

-- Gets data about an weapon from its data object and outputs it as a table
local function extract_data(weapon_data)
    local out = {}

    pcall(function() out.weapon_id = weapon_data:call("get_Id") end)
    if type(out.weapon_id) ~= "number" then return nil end

    pcall(function() out.weapon_type = weapon_data:call("get_DtWeaponType") end)
    pcall(function() out.weapon_name = weapon_data:call("get_Name") end)
    pcall(function() out.rarity = weapon_data:call("get_Rarity") end)
    pcall(function() out.element_type = weapon_data:call("get_MainElementType") end)

    return out
end

-- Walk a given weapon module's data array
-- and transfer data to output table. returns
-- (count_extracted, count_skipped, error_str|nil).
local function walk_weapon_array(weapon_manager, module_name, out)
    local data_array = nil
    pcall(function() data_array = weapon_manager:get_field("<BaseDataList>k__BackingField") end)
    if not data_array then
        return 0, 0, "<BaseDataList>k__BackingField missing in " .. module_name
    end

    local n = nil
    pcall(function() n = data_array:call("get_Length") end)
        if type(n) ~= "number" or n < 0 then
        return 0, 0, module_name .. " array length unreadable"
    end

    local extracted, skipped = 0, 0
    for i = 0, n - 1 do
        local weapon_data = nil
        pcall(function() weapon_data = data_array:call("GetValue", i) end)
        if weapon_data then
            local data_table = extract_data(weapon_data)
            if data_table then
                out[#out + 1] = data_table
                extracted = extracted + 1
            else
                skipped = skipped + 1
            end
        end
    end

    return extracted, skipped, nil
end

local function run_dump()
    if state.is_running then return end
    state.is_running = true

    local lines = {}
    local function push(msg)
        lines[#lines + 1] = msg
        log_info(msg)
    end

    local data_manager = sdk.get_managed_singleton("snow.data.ContentsIdDataManager")
    if not data_manager then
        push("ERROR: snow.data.ContentsIdDataManager singleton not available — is a save loaded?")
        state.last_result_preview = table.concat(lines, "\n")
        state.is_running = false
        return
    end

    local output = {}

    for _,module_name in pairs(weapon_modules) do
        local weapon_module = data_manager:get_field(module_name)
        if not weapon_module then
            push("ERROR: " .. module_name .. " singleton not available")
            state.last_result_preview = table.concat(lines, "\n")
            state.is_running = false
            return
        end
        local extracted, skipped, err =
            walk_weapon_array(weapon_module, module_name, output)
        if err then
            push(module_name .. ": " .. err)
        else
            push(string.format(module_name .. ": %d weapons, %d skipped",
                extracted, skipped))
        end
    end

    local payload = {
        source = "WeaponDataDump.lua",
        weapon_count = #output,
        weapons = output
    }

    local ok_dump = json.dump_file(OUTPUT_NAME, payload, 4)
    if ok_dump then
        push(string.format("dumped %d weapons -> %s", #output, OUTPUT_NAME))
    else
        push(string.format("json.dump_file failed for %s", OUTPUT_NAME))
    end

    push("")
    push("JSON written to <install>/reframework/data/.")
    state.last_result_preview = table.concat(lines, "\n")
    state.is_running = false
end

local function draw_window()
    if not state.is_window_open then return end
    if not reframework:is_drawing_ui() then return end

    local ok, err = pcall(function()
        imgui.set_next_window_size(Vector2f.new(560, 420), 4)
        state.is_window_open = imgui.begin_window(
            "MHRise Weapon Data Dump", state.is_window_open, nil)
        if state.is_window_open then
            imgui.text("Dumps weapon data from ContentsIdDataManager")
            imgui.text("Output: <install>/reframework/data/" .. OUTPUT_NAME)
            imgui.text("")
            if imgui.button("Dump catalog") then
                run_dump()
            end
            imgui.begin_child_window("weapon_data_preview",
                Vector2f.new(0, 280), true)
            if state.last_result_preview then
                imgui.text(state.last_result_preview)
            else
                imgui.text("(no dump yet)")
            end
            imgui.end_child_window()
        end
        imgui.end_window()
    end)
    if not ok then
        log_info("draw error: " .. safe_str(err))
    end
end

re.on_frame(function() draw_window() end)

re.on_draw_ui(function()
    if imgui.button("MHRise Weapon Data Dump") then
        state.is_window_open = not state.is_window_open
    end
end)

log.info("[weapon-data] Loaded")