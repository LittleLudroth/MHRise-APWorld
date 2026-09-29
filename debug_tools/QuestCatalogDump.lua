-- QuestCatalogDump — one-shot dumper for the in-memory quest catalog.
--
-- Iterates snow.QuestManager's two NormalQuestData.Param[] arrays:
--   _normalQuestData._Param      — base + Sunbreak HR (222 entries
--                                  in the observed save: village
--                                  + low + high-rank hub)
--   _nomalQuestDataKohaku._Param — Sunbreak Master Rank (350
--                                  entries; engine has a "nomal"
--                                  typo, "kohaku" = MR codename)
--
-- Observed total: 572 quests. ~464 of those are hunt-class
-- (quest_type in {1,2,4}) with a real boss_em_type — that's the
-- randomizable surface.
--
-- _Param elements ARE the NormalQuestData.Param payload directly
-- (NOT QuestData wrappers — first-run gotcha that surfaced as
-- "every quest skipped"). Per-element fields like _QuestNo,
-- _BossEmType, _TgtEmType, _MapNo etc. live on the element
-- directly, no get_RawNormal indirection.
--
-- Localized titles: the translated title lives on the outer
-- QuestData. First attempt called
-- `getQuestText(QuestText.TITLE, nil)` and got nil for all 572
-- entries — the nil for the QuestIdentifier struct arg likely
-- failed overload resolution. Current attempt re-fetches via
-- QuestManager.getQuestData(quest_no) and calls
-- `getQuestText(0, QuestManager._QuestIdentifier, false)` using
-- the live identifier struct off the manager itself. Falls back
-- to `getQuestTextCore` (the underlying 4-arg form RiseQuestLoader
-- hooks directly) if the public form fails. If both still return
-- nil after this, the localization tables probably need the
-- quest-counter UI opened once before dumping — try that, then
-- re-run. `_DbgName` (Japanese dev text) is the unconditional
-- fallback so dumps remain useful even when localization fails.
-- Result dumped to
-- <install>/reframework/data/mhrise_quest_catalog.json.
--
-- Output feeds ap_world/data/quests.py — see gh issue #11 and
-- QUEST.md "AP integration plan".
--
-- Dev-only. Drop into <install>/reframework/autorun/. No AP server
-- connection needed. Never bundled into the player client zip (see
-- .github/workflows/release.yml AUTORUN_FILES allow-list).
--
-- Trigger: REFramework overlay button "MHRise Quest Catalog Dump".
-- Don't auto-run on load — the QuestManager singleton isn't
-- populated until well after script init.

if reframework:get_game_name() ~= "mhrise" then return end

log.info("[quest-catalog] Loading...")

local LOG_TAG = "[quest-catalog] "
local OUTPUT_NAME = "mhrise_quest_catalog.json"

-- EmTypes[] managed-array element 0 lives at +0x20 from the array
-- object's base on RE Engine x64 — confirmed in QUEST.md "RE Engine
-- System.Array layout". Element count at +0x1c. Both reads are
-- read-only here; the write-path open question (Set vs SetValue vs
-- direct memory write) is irrelevant for a dump.
local ARRAY_LEN_OFFSET = 0x1c
local ARRAY_ELEM0_OFFSET = 0x20
local ARRAY_ELEM1_OFFSET = 0x24

local state = {
    last_result_preview = nil,
    is_window_open = false,
    is_running = false,
}

local function log_info(msg) log.info(LOG_TAG .. msg) end

-- Cache for the localized-title resolver. Populated lazily on first
-- use because the QuestManager singleton + QuestData type def aren't
-- available at script-load time.
local name_resolver = {
    initialized = false,
    quest_manager = nil,
    get_quest_data_int = nil,        -- QuestManager.getQuestData(System.Int32)
    get_quest_text = nil,             -- QuestData.getQuestText(QuestText, QuestIdentifier, bool)
    get_quest_text_core = nil,        -- QuestData.getQuestTextCore(QuestText, QuestIdentifier, bool, bool)
    quest_identifier = nil,           -- live QuestManager._QuestIdentifier struct
    diag = { tried = 0, ok_main = 0, ok_core = 0, both_nil = 0 },
}

local function init_name_resolver(quest_manager)
    if name_resolver.initialized then return end
    name_resolver.initialized = true

    name_resolver.quest_manager = quest_manager
    pcall(function()
        name_resolver.quest_identifier = quest_manager:get_field("_QuestIdentifier")
    end)

    local qm_td = sdk.find_type_definition("snow.QuestManager")
    if qm_td then
        pcall(function()
            name_resolver.get_quest_data_int = qm_td:get_method("getQuestData(System.Int32)")
        end)
    end

    local qd_td = sdk.find_type_definition("snow.quest.QuestData")
    if qd_td then
        pcall(function()
            name_resolver.get_quest_text = qd_td:get_method(
                "getQuestText(snow.quest.QuestText, snow.LobbyManager.QuestIdentifier, System.Boolean)")
        end)
        pcall(function()
            name_resolver.get_quest_text_core = qd_td:get_method(
                "getQuestTextCore(snow.quest.QuestText, snow.LobbyManager.QuestIdentifier, System.Boolean, System.Boolean)")
        end)
    end

    log_info(string.format("name resolver init: qd_int=%s gqt=%s gqtc=%s qid=%s",
        tostring(name_resolver.get_quest_data_int ~= nil),
        tostring(name_resolver.get_quest_text ~= nil),
        tostring(name_resolver.get_quest_text_core ~= nil),
        tostring(name_resolver.quest_identifier ~= nil)))
end

-- QuestText.TITLE = 0 (per snow.quest.QuestText enum dump in QUEST.md).
local QUEST_TEXT_TITLE = 0

local function coerce_string(v)
    if v == nil then return nil end
    if type(v) == "string" then return (#v > 0) and v or nil end
    -- managed System.String case: try ToString-ish accessors
    local s = nil
    pcall(function() if v.get_Chars then s = tostring(v) end end)
    if type(s) == "string" and #s > 0 then return s end
    pcall(function() s = v:call("ToString") end)
    if type(s) == "string" and #s > 0 then return s end
    return nil
end

local function resolve_quest_name(quest_no)
    if not name_resolver.initialized then return nil end
    if not name_resolver.get_quest_data_int then return nil end

    name_resolver.diag.tried = name_resolver.diag.tried + 1

    local quest_data = nil
    pcall(function()
        quest_data = name_resolver.get_quest_data_int:call(
            name_resolver.quest_manager, quest_no)
    end)
    if not quest_data then return nil end

    local qid = name_resolver.quest_identifier
    local name = nil

    if name_resolver.get_quest_text then
        pcall(function()
            name = name_resolver.get_quest_text:call(
                quest_data, QUEST_TEXT_TITLE, qid, false)
        end)
        name = coerce_string(name)
        if name then
            name_resolver.diag.ok_main = name_resolver.diag.ok_main + 1
            return name
        end
    end

    if name_resolver.get_quest_text_core then
        pcall(function()
            name = name_resolver.get_quest_text_core:call(
                quest_data, QUEST_TEXT_TITLE, qid, false, false)
        end)
        name = coerce_string(name)
        if name then
            name_resolver.diag.ok_core = name_resolver.diag.ok_core + 1
            return name
        end
    end

    name_resolver.diag.both_nil = name_resolver.diag.both_nil + 1
    return nil
end

local function safe_str(v)
    local ok, s = pcall(tostring, v)
    if ok then return s end
    return "<tostring error>"
end

-- Read element 0 of an EmTypes[]-style i32 array via the documented
-- memory layout. Returns nil if the array is absent or empty.
local function read_em_slot0(array_obj)
    if not array_obj then return nil end
    local len = nil
    pcall(function() len = array_obj:read_dword(ARRAY_LEN_OFFSET) end)
    if type(len) ~= "number" or len < 1 then return nil end
    local v = nil
    pcall(function() v = array_obj:read_dword(ARRAY_ELEM0_OFFSET) end)
    return v
end

-- read element 1 of an EMTypes[]-style i32 array via the documented
-- memory layout. Returns nil if the array is absent or has less than 2 elements.
local function read_em_slot1(array_obj)
    if not array_obj then return nil end
    local len = nil
    pcall(function() len = array_obj:read_dword(ARRAY_LEN_OFFSET) end)
    if type(len) ~= "number" or len < 2 then return nil end
    local v = nil
    pcall(function() v = array_obj:read_dword(ARRAY_ELEM1_OFFSET) end)
    return v
end

-- Walk one NormalQuestData.Param element into a flat table.
--
-- IMPORTANT: _Param array elements ARE the NormalQuestData.Param
-- payload directly — they're NOT QuestData wrappers (a misreading of
-- RiseQuestLoader's code that we initially fell for, surfaced as
-- "every quest skipped" in the first run). The `_QuestNo`,
-- `_BossEmType` etc. fields live on this element directly. See
-- RiseQuestLoader/QuestLoader.cpp:823 — it reads `_QuestNo` straight
-- off each element with no `get_RawNormal` indirection.
local function extract_quest(param_obj, source_tag)
    local row = { source = source_tag }

    pcall(function() row.quest_no = param_obj:get_field("_QuestNo") end)
    if type(row.quest_no) ~= "number" then
        return nil  -- not a usable entry
    end

    pcall(function() row.quest_type = param_obj:get_field("_QuestType") end)
    pcall(function() row.quest_level = param_obj:get_field("_QuestLv") end)
    pcall(function() row.enemy_level = param_obj:get_field("_EnemyLv") end)
    pcall(function() row.map_no = param_obj:get_field("_MapNo") end)
    pcall(function() row.base_time = param_obj:get_field("_BaseTime") end)
    pcall(function() row.time_limit = param_obj:get_field("_TimeLimit") end)
    pcall(function() row.quest_life = param_obj:get_field("_QuestLife") end)

    local tgt_arr, boss_arr = nil, nil
    pcall(function() tgt_arr = param_obj:get_field("_TgtEmType") end)
    pcall(function() boss_arr = param_obj:get_field("_BossEmType") end)
    row.target_em_type_one = read_em_slot0(tgt_arr)
    row.boss_em_type_one = read_em_slot0(boss_arr)

    -- two target quests are hunting quests
    -- Get the second em value from the array if it exists
    row.target_em_type_two = read_em_slot1(tgt_arr)
    row.boss_em_type_two = read_em_slot1(boss_arr)

    -- handle cases where array is smaller than size 2
    if row.target_em_type_two == nil then
        row.target_em_type_two = -1
        row.boss_em_type_two = -1
        row.two_target_quest = 0
    -- Both two target quests with 2 of the same target and
    -- single target quests return 0 for the second em type
    -- Detecting single target quests can be done by checking
    -- quest type and if both of the boss monsters are the same
    elseif row.boss_em_type_one ~= row.boss_em_type_two and
        row.target_em_type_two == 0 then
        row.two_target_quest = 0

    -- Otherwise, there was a second monster, so set
    -- two_target_quest flag to 1
    else
        row.two_target_quest = 1
    end

    -- _DbgName is Japanese dev-time text but reachable without
    -- quest-counter UI context. Always populated as a fallback.
    pcall(function()
        local s = param_obj:get_field("_DbgName")
        if type(s) == "string" then row.dbg_name = s
        elseif s and s.read_wstring then row.dbg_name = s:read_wstring(0) end
    end)

    -- Localized title (English when game is in English). Best-effort
    -- — nil if QuestManager.getQuestData lookup fails or the engine
    -- hasn't loaded the relevant message tables yet. See header
    -- comment for the workaround (open quest counter, re-run).
    row.name = resolve_quest_name(row.quest_no)

    return row
end

-- Walk one QuestManager.<container>._Param array of
-- NormalQuestData.Param into the accumulator. Returns
-- (count_extracted, count_skipped, error_str|nil).
local function walk_param_array(quest_manager, container_field, source_tag, out)
    local container = nil
    pcall(function() container = quest_manager:get_field(container_field) end)
    if not container then
        return 0, 0, container_field .. " field missing on QuestManager"
    end

    local param_arr = nil
    pcall(function() param_arr = container:get_field("_Param") end)
    if not param_arr then
        return 0, 0, container_field .. "._Param missing"
    end

    local n = nil
    pcall(function() n = param_arr:call("get_Length") end)
    if type(n) ~= "number" or n < 0 then
        -- Try via memory layout fallback (managed array len at +0x1c)
        pcall(function() n = param_arr:read_dword(ARRAY_LEN_OFFSET) end)
    end
    if type(n) ~= "number" or n < 0 then
        return 0, 0, container_field .. "._Param length unreadable"
    end

    local extracted, skipped = 0, 0
    for i = 0, n - 1 do
        local quest_obj = nil
        pcall(function() quest_obj = param_arr:call("GetValue", i) end)
        if not quest_obj then
            -- get_element fallback in case GetValue rejects this type
            pcall(function() quest_obj = param_arr:get_element(i) end)
        end
        if quest_obj then
            local row = extract_quest(quest_obj, source_tag)
            if row then
                out[#out + 1] = row
                extracted = extracted + 1
            else
                skipped = skipped + 1
            end
        else
            skipped = skipped + 1
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

    local quest_manager = sdk.get_managed_singleton("snow.QuestManager")
    if not quest_manager then
        push("ERROR: snow.QuestManager singleton not available — is a save loaded?")
        state.last_result_preview = table.concat(lines, "\n")
        state.is_running = false
        return
    end

    init_name_resolver(quest_manager)

    local catalog = {}
    local normal_extracted, normal_skipped, normal_err =
        walk_param_array(quest_manager, "_normalQuestData", "normal", catalog)
    if normal_err then
        push("normal: " .. normal_err)
    else
        push(string.format("normal: %d quests, %d skipped",
            normal_extracted, normal_skipped))
    end

    local kohaku_extracted, kohaku_skipped, kohaku_err =
        walk_param_array(quest_manager, "_nomalQuestDataKohaku", "kohaku", catalog)
    if kohaku_err then
        push("kohaku: " .. kohaku_err)
    else
        push(string.format("kohaku: %d quests, %d skipped",
            kohaku_extracted, kohaku_skipped))
    end

    push(string.format(
        "names: tried=%d ok_main=%d ok_core=%d both_nil=%d",
        name_resolver.diag.tried,
        name_resolver.diag.ok_main,
        name_resolver.diag.ok_core,
        name_resolver.diag.both_nil))

    local payload = {
        source = "QuestCatalogDump.lua",
        quest_count = #catalog,
        quests = catalog,
    }

    local ok_dump = json.dump_file(OUTPUT_NAME, payload, 4)
    if ok_dump then
        push(string.format("dumped %d quests -> %s", #catalog, OUTPUT_NAME))
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
            "MHRise Quest Catalog Dump", state.is_window_open, nil)
        if state.is_window_open then
            imgui.text("Dumps QuestManager._normalQuestData._Param +")
            imgui.text("QuestManager._nomalQuestDataKohaku._Param.")
            imgui.text("Output: <install>/reframework/data/" .. OUTPUT_NAME)
            imgui.text("")
            if imgui.button("Dump catalog") then
                run_dump()
            end
            imgui.begin_child_window("quest_catalog_preview",
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
    if imgui.button("MHRise Quest Catalog Dump") then
        state.is_window_open = not state.is_window_open
    end
end)

log.info("[quest-catalog] Loaded.")
