-- ArmorDataDump - a tool that access and dumps the complete armor data catalog for MHRise
--
-- Iterates the <ArmorDataList>k__BackingField in snow.Data.ContentsIdDataManager's _PlArmorIdDataModule
-- This array has 5 entries, an array of armor data for each armor slot
--
-- Gathers armor_name, armor_slot, rarity, gender requirements, and armor_id for all valid armor
--
-- Result dumped to reframework/data/mhrise_armor_data.json
-- Output feeds ap_world/data/armor_data.py
--
-- Dev-only. Drop into <install>/reframework/autorun/. No AP server
-- connection needed. Never bundled into the player client zip (see
-- .github/workflows/release.yml AUTORUN_FILES allow-list).
--
-- Trigger: REFramework overlay button "MHRise Armor Data Dump".
-- Don't auto-run on load — the ContentsIdDataManager singleton isn't
-- populated until well after script init.

if reframework:get_game_name() ~= "mhrise" then return end

log.info("[armor-data] Loading...")

local OUTPUT_NAME = "mhrise_armor_data.json"
local LOG_TAG = "[Armor Dump] "

local state = {
    last_result_preview = nil,
    is_window_open = false,
    is_running = false,
}

local armor_slot_to_index = {
    head = 0,
    chest = 1,
    arms = 2,
    waist = 3,
    legs = 4
}

local function safe_str(v)
    local ok, s = pcall(tostring, v)
    if ok then return s end
    return "<tostring error>"
end
local function log_info(msg) log.info(LOG_TAG .. msg) end

-- Gets data about an armor piece from its data object and outputs it as a table
local function extract_data(armor_data, armor_slot)
    local out = {armor_slot = armor_slot_to_index[armor_slot]}

    if not armor_data:call("isValid") then return nil end -- not a valid armor piece

    pcall(function() out.armor_name = armor_data:call("getName") end)
    pcall(function() out.rarity = armor_data:call("getRare") end)
    pcall(function() out.sex_type = armor_data:call("getSexualEquipableFlag") end)
    pcall(function() out.armor_id = armor_data:call("get_Id") end)
    return out
end

-- Walk one of the 5 armor_slot arrays in <ArmorDataList>k__BackingField
-- and transfer data to output table. returns
-- (count_extracted, count_skipped, error_str|nil).
local function walk_armor_array(armor_manager, armor_slot, out)
    local container = nil
    pcall(function() container = armor_manager:get_field("<ArmorDataList>k__BackingField") end)
    if not container then
        return 0, 0, "<ArmorDataList>k__BackingField missing on DataManager"
    end

    local data_array = nil
    pcall(function() data_array = container:call("GetValue", armor_slot_to_index[armor_slot]) end)
    if not data_array then
        return 0, 0, "<ArmorDataList>k__BackingField " .. armor_slot .. " data missing"
    end

    local n = nil
    pcall(function() n = data_array:call("get_Length") end)
        if type(n) ~= "number" or n < 0 then
        return 0, 0, armor_slot .. " array length unreadable"
    end

    local extracted, skipped = 0, 0
    for i = 0, n - 1 do
        local armor_data = nil
        pcall(function() armor_data = data_array:call("GetValue", i) end)
        if armor_data then
            local data_table = extract_data(armor_data, armor_slot)
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

    local armor_manager = data_manager:get_field("_PlArmorIdDataModule")
    local output = {}

    for slot,_ in pairs(armor_slot_to_index) do
        local extracted, skipped, err =
            walk_armor_array(armor_manager, slot, output)
        if err then
            push(slot .. ": " .. err)
        else
            push(string.format(slot .. ": %d armor, %d skipped",
                extracted, skipped))
        end
    end

    local payload = {
        source = "ArmorDataDump.lua",
        armor_count = #output,
        armors = output
    }

    local ok_dump = json.dump_file(OUTPUT_NAME, payload, 4)
    if ok_dump then
        push(string.format("dumped %d armors -> %s", #output, OUTPUT_NAME))
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
            "MHRise Armor Data Dump", state.is_window_open, nil)
        if state.is_window_open then
            imgui.text("Dumps armor data from ContentsIdDataManager")
            imgui.text("._PlArmorIdDataModule.<ArmorDataList>k__BackingField")
            imgui.text("Output: <install>/reframework/data/" .. OUTPUT_NAME)
            imgui.text("")
            if imgui.button("Dump catalog") then
                run_dump()
            end
            imgui.begin_child_window("armor_data_preview",
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
    if imgui.button("MHRise Armor Data Dump") then
        state.is_window_open = not state.is_window_open
    end
end)

log.info("[armor-data] Loaded")