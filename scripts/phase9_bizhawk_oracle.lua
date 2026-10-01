local root = assert(os.getenv("JFG_PHASE9_ORACLE_ROOT"),
  "JFG_PHASE9_ORACLE_ROOT is required")
local replay_path = assert(os.getenv("JFG_PHASE9_REPLAY_PATH"),
  "JFG_PHASE9_REPLAY_PATH is required")
local target = tonumber(os.getenv("JFG_PHASE9_ORACLE_TARGET") or "35000")
local input_clock = os.getenv("JFG_PHASE9_ORACLE_INPUT_CLOCK") or "emulator-frame"
assert(input_clock == "emulator-frame" or input_clock == "consumed-vi" or
  input_clock == "controller-poll",
  "invalid oracle input clock")
assert(input_clock ~= "consumed-vi" or os.getenv("JFG_PHASE9_ORACLE_VI_TRACE") == "1",
  "consumed-vi input requires VI tracing")
local consumed_vi_count = 0
local checkpoint_text = os.getenv("JFG_PHASE9_ORACLE_CHECKPOINTS") or
  "8100,21990,27000,32000,34000,35000"

assert(target ~= nil and target >= 3 and target <= 1000000,
  "invalid oracle target")
os.execute('if not exist "' .. root .. '" mkdir "' .. root .. '"')

local checkpoints = {}
for value in checkpoint_text:gmatch("[^,]+") do
  local frame = tonumber(value)
  assert(frame ~= nil and frame >= 0 and frame <= target,
    "invalid oracle checkpoint")
  checkpoints[frame] = true
end
assert(checkpoints[target], "the target must be an oracle checkpoint")

local replay = assert(io.open(replay_path, "r"))
assert(replay:read("*l") == "jfg-phase8-input-v2",
  "invalid Phase 9 replay header")
local events = {}
local previous_end = 0
for line in replay:lines() do
  local first, last, connected, buttons, stick_x, stick_y = line:match(
    "^(%d+),(%d+),([01]),([0-9A-Fa-f]+),(-?%d+),(-?%d+)$")
  assert(first ~= nil, "invalid Phase 9 replay record")
  local event = {
    first = tonumber(first),
    last = tonumber(last),
    connected = connected == "1",
    buttons = tonumber(buttons, 16),
    stick_x = tonumber(stick_x),
    stick_y = tonumber(stick_y),
  }
  assert(event.first < event.last and event.first >= previous_end and
      event.last <= 1000000 and event.buttons <= 0xFFFF and
      event.stick_x >= -128 and event.stick_x <= 127 and
      event.stick_y >= -128 and event.stick_y <= 127,
    "invalid Phase 9 replay interval")
  table.insert(events, event)
  previous_end = event.last
end
replay:close()
assert(#events > 0, "empty Phase 9 replay")

local button_names = {
  { 0x0800, "DPad U" }, { 0x0400, "DPad D" },
  { 0x0200, "DPad L" }, { 0x0100, "DPad R" },
  { 0x1000, "Start" }, { 0x2000, "Z" },
  { 0x4000, "B" }, { 0x8000, "A" },
  { 0x0008, "C Up" }, { 0x0004, "C Down" },
  { 0x0002, "C Left" }, { 0x0001, "C Right" },
  { 0x0020, "L" }, { 0x0010, "R" },
}

local event_index = 1
local function sample_at(frame)
  -- The selected-input exporter uses one event per actual controller poll.
  -- Its final replay interval extends to the target emulator frame for the
  -- native probe; it must not hold that final button/stick after poll EOF.
  if input_clock == "controller-poll" and frame >= #events then
    return { connected = true, buttons = 0, stick_x = 0, stick_y = 0 }
  end
  while event_index <= #events and frame >= events[event_index].last do
    event_index = event_index + 1
  end
  if event_index <= #events then
    local event = events[event_index]
    if frame >= event.first and frame < event.last then
      return event
    end
  end
  return {
    connected = true,
    buttons = 0,
    stick_x = 0,
    stick_y = 0,
  }
end

local function apply_input(frame)
  local sample = sample_at(frame)
  assert(sample.connected,
    "the canonical emulator route does not support dynamic disconnection")
  local buttons = {}
  for _, binding in ipairs(button_names) do
    buttons[binding[2]] = (sample.buttons & binding[1]) ~= 0
  end
  if input_clock == "controller-poll" then
    -- Match the Phase 9.5 bridge's isolation from host analog-key autoholds.
    for _, name in ipairs({ "A Left", "A Right", "A Up", "A Down" }) do
      buttons[name] = false
    end
  end
  joypad.set(buttons, 1)
  joypad.setanalog({
    ["X Axis"] = sample.stick_x,
    ["Y Axis"] = sample.stick_y,
  }, 1)
  return sample
end

local trace = assert(io.open(root .. "/checkpoints.tsv", "w"))
trace:setvbuf("no")
trace:write("schema\t1\n")
trace:write("target\t", tostring(target), "\n")
trace:write("replay-events\t", tostring(#events), "\n")
trace:write("input-clock\t", input_clock, "\n")
trace:write("initial-flash-sha256\t",
  memory.hash_region(0, 0x20000, "FlashRAM"):lower(), "\n")
if os.getenv("JFG_PHASE9_ORACLE_DOMAIN_INVENTORY") == "1" then
  local names = {}
  for _, name in pairs(memory.getmemorydomainlist()) do
    assert(type(name) == "string" and name ~= "" and
      name:find("[\r\n\t]") == nil, "invalid memory domain name")
    names[#names + 1] = name
  end
  assert(#names > 0 and #names <= 64, "invalid memory domain count")
  table.sort(names)
  for _, name in ipairs(names) do
    local size = memory.getmemorydomainsize(name)
    assert(type(size) == "number" and size == math.floor(size) and size > 0,
      "invalid memory domain size")
    trace:write("memory-domain\t", name, "\t", tostring(size), "\n")
  end
end
local poll_index = 0
local completed_updates = 0
local poll_hash_writer = nil
local controller_read_start_calls = 0
local controller_get_data_calls = 0
local event_trace = nil
local controller_callers_trace = nil
local controller_callers_rows = 0
local event_ranges = {}
local event_rows = 0
local last_event_sample = { connected = true, buttons = 0,
  stick_x = 0, stick_y = 0 }
local event_spec = os.getenv("JFG_PHASE9_EVENT_TRACE_RANGE")
if event_spec ~= nil and event_spec ~= "" then
  assert(input_clock == "controller-poll" and
    os.getenv("JFG_PHASE9_POLL_HASHES") == "1" and
    os.getenv("JFG_PHASE9_UPDATE_HASHES") == "1" and
    os.getenv("JFG_PHASE9_ORACLE_VI_TRACE") == "1" and
    #event_spec <= 64 and event_spec:match("^[0-9:,]+$") and
    event_spec:sub(1, 1) ~= ",", "event trace requires poll/update/VI capture")
  local previous_last = -1
  for range in event_spec:gmatch("[^,]+") do
    local first, last = range:match("^(%d+):(%d+)$")
    first, last = tonumber(first), tonumber(last)
    assert(first ~= nil and last ~= nil and first > previous_last and
      last >= first and last - first <= 31 and last <= 1000000 and
      #event_ranges < 2, "invalid event trace range")
    event_ranges[#event_ranges + 1] = { first, last }
    previous_last = last
  end
  assert(#event_ranges > 0 and event_spec:sub(-1) ~= "," and
    not event_spec:find(",,"), "invalid event trace range list")
  event_trace = assert(io.open(root .. "/events.tsv", "w"))
  event_trace:setvbuf("no")
  event_trace:write("sequence\tevent\tpoll\tcompleted_updates\tframe" ..
    "\tvi\tstart_calls\tget_calls\tconnected\tbuttons" ..
    "\tstick_x\tstick_y\n")
  controller_callers_trace = assert(io.open(root .. "/controller-callers.tsv", "w"))
  controller_callers_trace:setvbuf("no")
  controller_callers_trace:write(
    "sequence\tpoll\tcompleted_updates\tframe\tvi\tcaller\tdestination\n")
end
local function register_value(names)
  local registers = emu.getregisters()
  for _, name in ipairs(names) do
    if registers[name] ~= nil then return registers[name] end
  end
  return nil
end
local function trace_event(kind, poll, sample)
  if event_trace == nil then return end
  if sample ~= nil then last_event_sample = sample end
  local selected = false
  for _, range in ipairs(event_ranges) do
    if poll >= range[1] and poll <= range[2] then selected = true end
  end
  if not selected then return end
  event_rows = event_rows + 1
  assert(event_rows <= 4096, "event trace overflow")
  event_trace:write(tostring(event_rows), "\t", kind, "\t", tostring(poll),
    "\t", tostring(completed_updates), "\t", tostring(emu.framecount()),
    "\t", tostring(consumed_vi_count), "\t",
    tostring(controller_read_start_calls), "\t",
    tostring(controller_get_data_calls), "\t",
    last_event_sample.connected and "1" or "0", "\t",
    tostring(last_event_sample.buttons), "\t",
    tostring(last_event_sample.stick_x), "\t",
    tostring(last_event_sample.stick_y), "\n")
end
if os.getenv("JFG_PHASE9_POLL_HASHES") == "1" then
  -- US libultra controller entry points. These counters test whether the
  -- emulator input callback and native HLE snapshot the same call phase.
  event.onmemoryexecute(function()
    controller_read_start_calls = controller_read_start_calls + 1
    trace_event("start-entry", poll_index)
  end, 0x80097D10, "phase9-controller-start-entry", "System Bus")
  event.onmemoryexecute(function()
    controller_get_data_calls = controller_get_data_calls + 1
    local poll = math.max(0, poll_index - 1)
    trace_event("get-entry", poll)
    if controller_callers_trace ~= nil then
      local selected = false
      for _, range in ipairs(event_ranges) do
        if poll >= range[1] and poll <= range[2] then selected = true end
      end
      if selected then
        local caller = assert(register_value(
          { "RA", "ra", "ra_lo", "R31", "r31", "GPR31" })) & 0xFFFFFFFF
        local destination = assert(register_value(
          { "A0", "a0", "a0_lo", "R4", "r4", "GPR4" })) & 0xFFFFFFFF
        assert(caller >= 0x80000000 and caller <= 0x803FFFFC and
          caller % 4 == 0 and destination >= 0x80000000 and
          destination <= 0x803FFFE8, "controller caller or destination invalid")
        controller_callers_rows = controller_callers_rows + 1
        assert(controller_callers_rows <= 256,
          "controller callers trace overflow")
        controller_callers_trace:write(tostring(controller_callers_rows),
          "\t", tostring(poll), "\t", tostring(completed_updates),
          "\t", tostring(emu.framecount()), "\t",
          tostring(consumed_vi_count), "\t",
          string.format("0x%08x", caller), "\t",
          string.format("0x%08x", destination), "\n")
      end
    end
  end, 0x80097DD4, "phase9-controller-get-entry", "System Bus")
end
if input_clock == "consumed-vi" then
  -- Mupen64Plus N64Input.GetControllerInput invokes InputCallbacks before
  -- reading the controller axes/buttons. Select the same consumed-VI clock
  -- used by native sample_host_controller at that input polling point.
  event.oninputpoll(function()
    local sample = apply_input(consumed_vi_count)
    trace:write("input-poll\t", tostring(emu.framecount()),
      "\tconsumed-vi\t", tostring(consumed_vi_count),
      "\tbuttons\t", string.format("%04X", sample.buttons),
      "\tstick\t", tostring(sample.stick_x), ",", tostring(sample.stick_y), "\n")
  end, "phase9-consumed-vi-input")
elseif input_clock == "controller-poll" then
  event.oninputpoll(function()
    local sample = apply_input(poll_index)
    trace_event("input-poll", poll_index, sample)
    if poll_hash_writer ~= nil then poll_hash_writer(sample) end
    trace:write("input-poll\t", tostring(emu.framecount()),
      "\tindex\t", tostring(poll_index),
      "\tbuttons\t", string.format("%04X", sample.buttons),
      "\tstick\t", tostring(sample.stick_x), ",", tostring(sample.stick_y),
      "\tmode\t", tostring(memory.read_u8(0xA51B0, "RDRAM")),
      "\tlevel\t", tostring(memory.read_u32_be(0xFB114, "RDRAM")),
      "\trng\t", tostring(memory.read_u32_be(0xA33E4, "RDRAM")), "\n")
    poll_index = poll_index + 1
  end, "phase9-controller-poll-input")
end

local retrace_hash = assert(io.open(root .. "/retrace-hashes.jsonl", "w"))
retrace_hash:setvbuf("no")
retrace_hash:write(
  '{"kind":"jfg-phase9-retrace-hash-header","schema":1}\n')

local function physical_address(address)
  if address == nil then
    return nil
  end
  return address & 0x1FFFFFFF
end

local controller_return_trace = nil
local controller_return_pending = nil
local controller_return_rows = 0
local return_pc_spec = os.getenv("JFG_PHASE9_CONTROLLER_RETURN_PC")
if return_pc_spec ~= nil and return_pc_spec ~= "" then
  assert(return_pc_spec:match("^0x[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]$") ~= nil and
    #event_ranges > 0, "controller return requires bounded event windows")
  local return_pc = tonumber(return_pc_spec:sub(3), 16)
  assert(return_pc ~= nil and return_pc >= 0x80000000 and
    return_pc <= 0x803FFFFC and return_pc % 4 == 0,
    "invalid controller return PC")
  controller_return_trace = assert(io.open(root .. "/controller-return.tsv", "w"))
  controller_return_trace:setvbuf("no")
  controller_return_trace:write(
    "sequence\tpoll\tcompleted_updates\tvi\tframe\taddress\tdata\n")
  local function selected_poll(poll)
    for _, range in ipairs(event_ranges) do
      if poll >= range[1] and poll <= range[2] then return true end
    end
    return false
  end
  event.onmemoryexecute(function()
    local poll = math.max(0, poll_index - 1)
    if not selected_poll(poll) then return end
    assert(controller_return_pending == nil,
      "nested controller data read in bounded window")
    local address = assert(register_value({ "A0", "a0", "a0_lo", "R4", "r4", "GPR4" })) &
      0xFFFFFFFF
    local caller = assert(register_value({ "RA", "ra", "ra_lo", "R31", "r31", "GPR31" })) &
      0xFFFFFFFF
    local physical = physical_address(address)
    assert(caller == return_pc and address >= 0x80000000 and
      address <= 0x803FFFE8 and physical + 24 <= 0x400000,
      "controller data return site or destination changed")
    controller_return_pending = { poll = poll, address = address }
  end, 0x80097DD4, "phase9-controller-return-entry", "System Bus")
  event.onmemoryexecute(function()
    local pending = controller_return_pending
    if pending == nil then return end
    assert(math.max(0, poll_index - 1) == pending.poll,
      "controller poll advanced inside data read")
    controller_return_rows = controller_return_rows + 1
    assert(controller_return_rows <= 256, "controller return trace overflow")
    local data = memory.read_bytes_as_binary_string(
      physical_address(pending.address), 24, "RDRAM")
    assert(#data == 24, "controller return data is incomplete")
    local bytes = {}
    for index = 1, 24 do
      bytes[#bytes + 1] = string.format("%02x", data:byte(index))
    end
    controller_return_trace:write(tostring(controller_return_rows), "\t",
      tostring(pending.poll), "\t", tostring(completed_updates), "\t",
      tostring(consumed_vi_count), "\t", tostring(emu.framecount()), "\t",
      string.format("0x%08x", pending.address), "\t",
      table.concat(bytes), "\n")
    controller_return_pending = nil
  end, return_pc, "phase9-controller-return-exit", "System Bus")
end

if os.getenv("JFG_PHASE9_ORACLE_ALLOC_TRACE") == "1" then
  -- US mmAlloc epilogue, before restoring sp: original size is at sp+0x30,
  -- result in v0 and caller at sp+0x14. No shared pending-call state is needed.
  event.onmemoryexecute(function()
    if consumed_vi_count > 100 then return end
    local sp = assert(register_value({ "SP", "sp", "sp_lo", "R29", "r29", "GPR29" }))
    local result = assert(register_value({ "V0", "v0", "v0_lo", "R2", "r2", "GPR2" }))
    local address = physical_address(sp)
    assert(address ~= nil and address + 0x34 <= 0x400000, "invalid allocation stack")
    trace:write("mm-alloc\t", tostring(emu.framecount()),
      "\tconsumed-vi\t", tostring(consumed_vi_count),
      "\tsize\t", tostring(memory.read_u32_be(address + 0x30, "RDRAM")),
      "\tresult\t", tostring(result & 0xFFFFFFFF),
      "\tcaller\t", string.format("0x%08X", memory.read_u32_be(address + 0x14, "RDRAM")), "\n")
  end, 0x8004A5FC, "phase9-mm-alloc-return", "System Bus")
end

-- Native hashes are sampled on successful game VI queue consumption, not at
-- emulator frame boundaries. This opt-in diagnostic locates the relevant
-- queue and callers before a matching consumption-point hook is selected.
-- A receive entry can block or fail: never label it a consumed retrace.
local diagnostic_vi_queue = nil
local diagnostic_vi_message = nil
if os.getenv("JFG_PHASE9_ORACLE_VI_TRACE") == "1" then
  local vi_queue = nil
  local function argument(index)
    return register_value({ "A" .. index, "a" .. index, "a" .. index .. "_lo",
      "R" .. (4 + index), "r" .. (4 + index), "GPR" .. (4 + index) })
  end
  event.onmemoryexecute(function()
    local queue = assert(argument(0), "VI trace cannot read A0") & 0xFFFFFFFF
    vi_queue = queue
    diagnostic_vi_queue = queue
    diagnostic_vi_message = assert(argument(1), "VI trace cannot read A1") & 0xFFFFFFFF
    trace:write("vi-configure-entry\t", tostring(emu.framecount()),
      "\tqueue\t", string.format("0x%08X", queue),
      "\tinterval\t", tostring(argument(2)), "\n")
  end, 0x80098E30, "phase9-vi-configure-entry", "System Bus")
  event.onmemoryexecute(function()
    local queue = argument(0)
    if queue ~= nil and (queue & 0xFFFFFFFF) == vi_queue then
      local caller = register_value({ "RA", "ra", "ra_lo", "R31", "r31", "GPR31" })
      assert(caller ~= nil, "VI trace cannot read RA")
      trace:write("vi-receive-entry\t", tostring(emu.framecount()),
        "\tcaller\t", string.format("0x%08X", caller & 0xFFFFFFFF),
        "\tblock\t", tostring(argument(2)), "\n")
    end
  end, 0x80096910, "phase9-vi-receive-entry", "System Bus")
end

local function read_actor_position(actor)
  local address = physical_address(actor)
  if address == nil or address == 0 or address + 0x18 > 0x400000 then
    return nil
  end
  return {
    yaw = memory.read_u16_be(address, "RDRAM"),
    x = memory.read_u32_be(address + 0x0C, "RDRAM"),
    y = memory.read_u32_be(address + 0x10, "RDRAM"),
    z = memory.read_u32_be(address + 0x14, "RDRAM"),
  }
end

local function find_named_actor(name_word_0, name_word_1)
  local list = memory.read_u32_be(0xF2CA4, "RDRAM")
  local count = memory.read_u32_be(0xF2CA8, "RDRAM")
  local list_offset = physical_address(list)
  if list_offset == nil or list_offset == 0 or count > 1024 or
      list_offset + count * 4 > 0x400000 then
    return nil
  end
  for index = 0, count - 1 do
    local actor = memory.read_u32_be(list_offset + index * 4, "RDRAM")
    local actor_offset = physical_address(actor)
    if actor_offset ~= nil and actor_offset ~= 0 and
        actor_offset + 0x44 <= 0x400000 then
      local header = memory.read_u32_be(actor_offset + 0x40, "RDRAM")
      local header_offset = physical_address(header)
      if header_offset ~= nil and header_offset ~= 0 and
          header_offset + 0x0C <= 0x400000 and
          memory.read_u32_be(header_offset + 4, "RDRAM") == name_word_0 and
          memory.read_u32_be(header_offset + 8, "RDRAM") == name_word_1 then
        return actor
      end
    end
  end
  return nil
end

local player_actor = nil
local hints_actor = nil
local player_control_calls = 0
local hints_control_calls = 0
local hints_talk_calls = 0

local function hash_region(address, length)
  local physical = physical_address(address)
  if physical == nil or physical + length > 0x400000 then
    return nil
  end
  return memory.hash_region(physical, length, "RDRAM"):lower()
end

local function json_hash(value)
  if value == nil then
    return "null"
  end
  return '"' .. value .. '"'
end

local last_dump_front_mode = nil
local function write_retrace_hash(frame, output, clock_kind, sample)
  local retrace_hash = output or retrace_hash
  local actor_list = memory.read_u32_be(0xF2CA4, "RDRAM")
  local actor_count = memory.read_u32_be(0xF2CA8, "RDRAM")
  local rng_seed = memory.read_u32_be(0xA33E4, "RDRAM")
  local front_mode = memory.read_u8(0xA51B0, "RDRAM")
  if output ~= nil and clock_kind ~= "update" and clock_kind ~= "poll"
      and os.getenv("JFG_PHASE9_ORACLE_TRANSITION_DUMPS") == "1"
      and front_mode ~= last_dump_front_mode then
    local snapshot = assert(io.open(root .. string.format(
      "/transition-vi-%06d-mode-%02d.rdram", frame, front_mode), "wb"))
    snapshot:write(memory.read_bytes_as_binary_string(0, 0x400000, "RDRAM"))
    snapshot:close()
    last_dump_front_mode = front_mode
  end
  local actor_table_hash = nil
  local actor_table_valid = actor_count <= 256
  if actor_table_valid then
    actor_table_hash = hash_region(actor_list, actor_count * 4)
    actor_table_valid = actor_table_hash ~= nil
  end
  local player_value = player_actor or 0
  local player_hash = nil
  if player_value ~= 0 then
    player_hash = hash_region(player_value, 0x200)
  end
  retrace_hash:write(
    clock_kind == "poll" and '{"kind":"jfg-phase9-poll-hash","schema":1,"poll":'
      or clock_kind == "update" and '{"kind":"jfg-phase9-update-hash","schema":1,"update":'
      or '{"kind":"jfg-phase9-retrace-hash","schema":1,"retrace":',
    tostring(frame), ',"front_mode":', tostring(front_mode),
    ',"rng_seed":"', string.format("0x%08x", rng_seed),
    '","player_actor":"', string.format("0x%08x", player_value),
    '","player_sha256":', json_hash(player_hash),
    ',"actor_list":"', string.format("0x%08x", actor_list),
    '","actor_count":', tostring(actor_count),
    ',"actor_table_sha256":', json_hash(actor_table_hash),
    ',"globals_sha256":', json_hash(hash_region(0x800A4FCC, 0x90)),
    ',"camera_sha256":', json_hash(hash_region(0x801045B0, 0x158)),
    ',"actors":[')
  local first = true
  if actor_table_valid then
    local list_offset = physical_address(actor_list)
    for index = 0, actor_count - 1 do
      local actor = memory.read_u32_be(list_offset + index * 4, "RDRAM")
      local digest = nil
      if actor ~= 0 then
        digest = hash_region(actor, 0x200)
      end
      if not first then
        retrace_hash:write(",")
      end
      first = false
      retrace_hash:write('{"index":', tostring(index),
        ',"address":"', string.format("0x%08x", actor),
        '","sha256":', json_hash(digest), "}")
    end
  end
  retrace_hash:write("]")
  if clock_kind == "update" then
    retrace_hash:write(',"controller_polls":', tostring(poll_index),
      ',"emulator_frame":', tostring(emu.framecount()))
    if os.getenv("JFG_PHASE9_ORACLE_VI_TRACE") == "1" then
      retrace_hash:write(',"oracle_consumed_vi":', tostring(consumed_vi_count))
    end
  elseif clock_kind == "poll" then
    assert(sample ~= nil, "poll semantic hash requires current sample")
    retrace_hash:write(',"level_word":',
      tostring(memory.read_u32_be(0xFB114, "RDRAM")),
      ',"connected":', sample.connected and "1" or "0",
      ',"buttons":', tostring(sample.buttons),
      ',"stick_x":', tostring(sample.stick_x),
      ',"stick_y":', tostring(sample.stick_y),
      ',"update_counter_valid":',
        os.getenv("JFG_PHASE9_UPDATE_HASHES") == "1" and "true" or "false",
      ',"completed_updates":',
        os.getenv("JFG_PHASE9_UPDATE_HASHES") == "1" and
          tostring(completed_updates) or "null",
      ',"controller_read_start_calls":', tostring(controller_read_start_calls),
      ',"controller_get_data_calls":', tostring(controller_get_data_calls),
      ',"emulator_frame":', tostring(emu.framecount()))
  end
  retrace_hash:write("}\n")
end

local consumed_vi_hash = nil
local update_hash = nil
local poll_hash = nil
if os.getenv("JFG_PHASE9_POLL_HASHES") == "1" then
  assert(input_clock == "controller-poll",
    "poll semantic hashes require controller-poll input")
  poll_hash = assert(io.open(root .. "/poll-hashes.jsonl", "w"))
  poll_hash:setvbuf("no")
  poll_hash:write('{"kind":"jfg-phase9-poll-hash-header","schema":1,',
    '"boundary":"pre-controller-input"}\n')
  poll_hash_writer = function(sample)
    write_retrace_hash(poll_index, poll_hash, "poll", sample)
  end
end
local focus_first, focus_last = nil, nil
local focus_spec = os.getenv("JFG_PHASE9_FOCUS_UPDATES")
if focus_spec ~= nil and focus_spec ~= "" then
  local first, last = focus_spec:match("^(%d+):(%d+)$")
  focus_first, focus_last = tonumber(first), tonumber(last)
  assert(focus_first ~= nil and focus_last ~= nil and focus_first >= 1 and
    focus_last >= focus_first and focus_last - focus_first <= 15 and
    os.getenv("JFG_PHASE9_UPDATE_HASHES") == "1",
    "invalid focused update capture range")
end
local si_trace = nil
local si_clock_trace = nil
local si_clock_receive_hits = 0
local si_rows = 0
local si_pending = nil
local si_return_hooks = {}
local si_hook_names = {}
if os.getenv("JFG_PHASE9_SI_TRACE") == "1" then
  assert(focus_first ~= nil and
    os.getenv("JFG_PHASE9_ORACLE_VI_TRACE") == "1" and
    os.getenv("JFG_PHASE9_UPDATE_HASHES") == "1" and
    os.getenv("JFG_PHASE9_ORACLE_DOMAIN_INVENTORY") == "1",
    "SI trace requires focused update, VI and save inventory")
  si_trace = assert(io.open(root .. "/si-transactions.tsv", "w"))
  si_trace:setvbuf("no")
  -- Diagnostic-only core Count observations. They are not hardware timing
  -- qualification: a core may update its exposed Count lazily.
  if os.getenv("JFG_PHASE9_SI_CLOCK_TRACE") == "1" then
    si_clock_trace = assert(io.open(root .. "/si-clock.tsv", "w"))
    si_clock_trace:setvbuf("no")
    si_clock_trace:write("event\tframe\tupdate\tpoll\tcount\n")
  end
  local function si_clock(kind)
    if si_clock_trace == nil then return false end
    if completed_updates + 1 < focus_first - 1 or
        completed_updates + 1 > focus_last + 1 then return end
    local count = assert(register_value({ "CP0 REG9" }), "Count unavailable") & 0xFFFFFFFF
    si_clock_trace:write(kind, "\t", tostring(emu.framecount()), "\t",
      tostring(completed_updates), "\t", tostring(poll_index), "\t",
      string.format("0x%08x", count), "\n")
    return true
  end
  if si_clock_trace ~= nil then
  event.onmemorywrite(function() si_clock("ack-write") end,
    0xA4800018, "phase9-si-clock-ack", "System Bus")
  event.onmemoryexecute(function()
    local result = assert(register_value({ "V0", "v0", "v0_lo", "R2", "r2", "GPR2" })) & 0xFFFFFFFF
    if si_clock("game-recv-return-" .. string.format("%08x", result)) then
      si_clock_receive_hits = si_clock_receive_hits + 1
    end
  end, 0x80043168, "phase9-si-clock-recv", "System Bus")
  end
  si_trace:write("sequence\tentry_frame\tentry_update\tentry_poll\tentry_vi" ..
    "\treturn_frame\treturn_update\treturn_poll\treturn_vi" ..
    "\tdirection\taddress\tcaller\tbefore\tafter\n")
  local function bytes_at(address)
    assert(address >= 0x80000000 and address <= 0x803FFFC0,
      "SI PIF buffer outside RDRAM")
    local raw = memory.read_bytes_as_binary_string(
      physical_address(address), 64, "RDRAM")
    assert(#raw == 64, "SI PIF buffer is incomplete")
    local result = {}
    for index = 1, 64 do
      result[index] = string.format("%02x", raw:byte(index))
    end
    return table.concat(result)
  end
  -- US libultra __osSiRawStartDma. Dynamic caller hooks avoid assuming that
  -- all controller and accessory transactions share one return site.
  event.onmemoryexecute(function()
    if completed_updates + 1 < focus_first - 1 or
        completed_updates + 1 > focus_last + 1 then return end
    assert(si_pending == nil, "nested SI DMA in focused window")
    si_clock("dma-entry")
    local direction = assert(register_value(
      { "A0", "a0", "a0_lo", "R4", "r4", "GPR4" })) & 0xFFFFFFFF
    local address = assert(register_value(
      { "A1", "a1", "a1_lo", "R5", "r5", "GPR5" })) & 0xFFFFFFFF
    local caller = assert(register_value(
      { "RA", "ra", "ra_lo", "R31", "r31", "GPR31" })) & 0xFFFFFFFF
    assert((direction == 0 or direction == 1) and
      caller >= 0x80000000 and caller <= 0x803FFFFC and caller % 4 == 0,
      "SI DMA direction or caller changed")
    if si_return_hooks[caller] == nil then
      assert(#si_hook_names < 32, "SI DMA return sites unbounded")
      local name = "phase9-si-return-" .. string.format("%08x", caller)
      si_return_hooks[caller] = true
      si_hook_names[#si_hook_names + 1] = name
      event.onmemoryexecute(function()
        local pending = si_pending
        if pending == nil then return end
        assert(pending.caller == caller, "SI DMA returned to another caller")
        si_clock("dma-return")
        si_rows = si_rows + 1
        assert(si_rows <= 256, "SI transaction trace overflow")
        si_trace:write(tostring(si_rows), "\t", tostring(pending.frame),
          "\t", tostring(pending.update), "\t", tostring(pending.poll),
          "\t", tostring(pending.vi), "\t", tostring(emu.framecount()),
          "\t", tostring(completed_updates), "\t", tostring(poll_index),
          "\t", tostring(consumed_vi_count), "\t",
          tostring(pending.direction), "\t",
          string.format("0x%08x", pending.address), "\t",
          string.format("0x%08x", pending.caller), "\t",
          pending.before, "\t", bytes_at(pending.address), "\n")
        si_pending = nil
      end, caller, name, "System Bus")
    end
    si_pending = { frame = emu.framecount(), update = completed_updates,
      poll = poll_index, vi = consumed_vi_count, direction = direction,
      address = address, caller = caller, before = bytes_at(address) }
  end, 0x8009A830, "phase9-si-entry", "System Bus")
end
local watch_word = nil
local update_word = nil
local update_word_trace = nil
local update_word_spec = os.getenv("JFG_PHASE9_UPDATE_WORD")
if update_word_spec ~= nil and update_word_spec ~= "" then
  assert(update_word_spec:match("^0x[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]$") ~= nil and
    os.getenv("JFG_PHASE9_UPDATE_HASHES") == "1",
    "update word requires completed-update capture")
  update_word = tonumber(update_word_spec:sub(3), 16)
  assert(update_word ~= nil and update_word >= 0x80000000 and
    update_word <= 0x803FFFFC and update_word % 4 == 0,
    "invalid update word address")
  update_word_trace = assert(io.open(root .. "/update-word.tsv", "w"))
  update_word_trace:setvbuf("no")
  update_word_trace:write("update\tcontroller_polls\tvi\tframe\taddress\tvalue\n")
end
local watch_spec = os.getenv("JFG_PHASE9_WATCH_WORD")
if watch_spec ~= nil and watch_spec ~= "" then
  assert(watch_spec:match("^0x[0-9A-Fa-f]+$") ~= nil and
    focus_first ~= nil and os.getenv("JFG_PHASE9_ORACLE_VI_TRACE") == "1",
    "actor-word watch requires focused update and VI tracing")
  watch_word = tonumber(watch_spec:sub(3), 16)
  assert(watch_word ~= nil and watch_word >= 0x80000000 and
    watch_word <= 0x803FFFFC and watch_word % 4 == 0,
    "invalid actor-word watch address")
end
local watch_trace = nil
local watch_hits = 0
if watch_word ~= nil then
  watch_trace = assert(io.open(root .. "/watch-word.tsv", "w"))
  watch_trace:setvbuf("no")
  watch_trace:write("address\tframe\tcompleted_updates\tcontroller_polls\t",
    "consumed_vi\tpc\tpreword\tcallback_value\tflags\n")
  for byte = 0, 3 do
    event.onmemorywrite(function(address, value, flags)
      if completed_updates + 1 < focus_first - 1 or
          completed_updates + 1 > focus_last + 1 then return end
      watch_hits = watch_hits + 1
      assert(watch_hits <= 1024, "actor-word watch overflow")
      local pc = register_value({ "PC", "pc", "Pc" })
      local preword = memory.read_u32_be(physical_address(watch_word), "RDRAM")
      watch_trace:write(string.format("0x%08x", address or watch_word + byte),
        "\t", tostring(emu.framecount()), "\t", tostring(completed_updates),
        "\t", tostring(poll_index), "\t", tostring(consumed_vi_count),
        "\t", pc and string.format("0x%08x", pc & 0xFFFFFFFF) or "unknown",
        "\t", string.format("0x%08x", preword),
        "\t", tostring(value), "\t", tostring(flags), "\n")
    end, watch_word + byte, "phase9-watch-word-" .. tostring(byte), "System Bus")
  end
end
local entry_pc = nil
local entry_spec = os.getenv("JFG_PHASE9_ENTRY_PC")
if entry_spec ~= nil and entry_spec ~= "" then
  assert(entry_spec:match("^0x[0-9A-Fa-f]+$") ~= nil and
    focus_first ~= nil and os.getenv("JFG_PHASE9_ORACLE_VI_TRACE") == "1",
    "entry probe requires focused update and VI tracing")
  entry_pc = tonumber(entry_spec:sub(3), 16)
  assert(entry_pc ~= nil and entry_pc >= 0x80000000 and
    entry_pc <= 0x803FFFFC and entry_pc % 4 == 0,
    "invalid entry probe PC")
end
local entry_trace = nil
local entry_hits = 0
local entry_catalog_written = false
local entry_fpu_trace = nil
local entry_memory_trace = nil
local entry_gpr_trace = nil
local entry_fcr_trace = nil
local trace_entry_fpu = os.getenv("JFG_PHASE9_ENTRY_FPU") == "1"
local trace_entry_memory = os.getenv("JFG_PHASE9_ENTRY_MEMORY") == "1"
local trace_entry_gpr = os.getenv("JFG_PHASE9_ENTRY_GPR") == "1"
local trace_entry_fcr = os.getenv("JFG_PHASE9_ENTRY_FCR") == "1"
assert(not trace_entry_fpu or entry_pc ~= nil,
  "entry FPU trace requires focused entry probe")
assert(not trace_entry_memory or entry_pc ~= nil,
  "entry memory trace requires focused entry probe")
assert(not trace_entry_gpr or entry_pc ~= nil,
  "entry GPR trace requires focused entry probe")
assert(not trace_entry_fcr or entry_pc ~= nil,
  "entry FCR trace requires focused entry probe")
local gpr_names = { "r0", "at", "v0", "v1", "a0", "a1", "a2", "a3",
  "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7", "s0", "s1", "s2",
  "s3", "s4", "s5", "s6", "s7", "t8", "t9", "k0", "k1", "gp", "sp",
  "s8", "ra" }
local function point_addresses(name)
  local specification = os.getenv(name) or ""
  local addresses, seen, consumed = {}, {}, {}
  if specification == "" then return addresses end
  for item in specification:gmatch("[^,]+") do
    assert(#item == 10 and item:match("^0x[0-9a-fA-F]+$"), "invalid point probe address")
    local address = tonumber(item:sub(3), 16)
    assert(address >= 0x80000000 and address <= 0x803ffffc and address % 4 == 0 and
      not seen[address] and #addresses < 16, "unbounded/duplicate point probe address")
    addresses[#addresses + 1], consumed[#consumed + 1], seen[address] = address, item, true
  end
  assert(table.concat(consumed, ",") == specification, "invalid point probe separators")
  return addresses
end
local point_pcs = point_addresses("JFG_PHASE9_POINT_PCS")
local point_words = point_addresses("JFG_PHASE9_POINT_WORDS")
local point_trace, point_hits = nil, 0
assert(#point_pcs > 0 or #point_words == 0, "point words require instruction PCs")
if #point_pcs > 0 then
  assert(focus_first ~= nil and os.getenv("JFG_PHASE9_ORACLE_VI_TRACE") == "1",
    "point probe requires focused updates and VI tracing")
  point_trace = assert(io.open(root .. "/point-probe.tsv", "w"))
  point_trace:setvbuf("no")
  point_trace:write("frame\tcompleted_updates\tcontroller_polls\tconsumed_vi\tpc\topcode")
  for index = 0, 31 do point_trace:write("\tr", index, "_lo\tr", index, "_hi") end
  for _, address in ipairs(point_words) do point_trace:write(string.format("\tm%08x", address)) end
  point_trace:write("\n")
  for _, pc in ipairs(point_pcs) do
    event.onmemoryexecute(function()
      if completed_updates + 1 < focus_first - 1 or completed_updates + 1 > focus_last + 1 then return end
      point_hits = point_hits + 1
      assert(point_hits <= 4096, "point probe hit budget exceeded")
      local registers = emu.getregisters()
      point_trace:write(tostring(emu.framecount()), "\t", tostring(completed_updates), "\t",
        tostring(poll_index), "\t", tostring(consumed_vi_count), "\t", string.format("0x%08x", pc),
        "\t", string.format("0x%08x", memory.read_u32_be(physical_address(pc), "RDRAM")))
      for index = 0, 31 do
        for _, part in ipairs({"lo", "hi"}) do
          local name = gpr_names[index + 1] .. "_" .. part
          local value = registers[name]
          assert(type(value) == "number" and value == math.floor(value), "point GPR missing: " .. name)
          point_trace:write("\t", string.format("0x%08x", value & 0xffffffff))
        end
      end
      for _, address in ipairs(point_words) do
        point_trace:write("\t", string.format("0x%08x", memory.read_u32_be(physical_address(address), "RDRAM")))
      end
      point_trace:write("\n")
    end, pc, "phase9-point-" .. string.format("%08x", pc), "System Bus")
  end
end
if entry_pc ~= nil then
  entry_trace = assert(io.open(root .. "/entry-args.tsv", "w"))
  entry_trace:setvbuf("no")
  entry_trace:write("frame\tcompleted_updates\tcontroller_polls\tconsumed_vi\t",
    "pc\ta0\ta1\ta2\ta3\n")
  if trace_entry_fpu then
    entry_fpu_trace = assert(io.open(root .. "/entry-fpu.tsv", "w"))
    entry_fpu_trace:setvbuf("no")
    entry_fpu_trace:write("frame\tcompleted_updates\tcontroller_polls\tconsumed_vi\tpc")
    for index = 0, 31 do
      entry_fpu_trace:write("\tf", index, "_lo\tf", index, "_hi")
    end
    entry_fpu_trace:write("\n")
  end
  if trace_entry_memory then
    entry_memory_trace = assert(io.open(root .. "/entry-memory.tsv", "w"))
    entry_memory_trace:setvbuf("no")
    entry_memory_trace:write("frame\tcompleted_updates\tcontroller_polls\t",
      "consumed_vi\tpc\ta1_256\ta2_256\ta3_256\n")
  end
  if trace_entry_gpr then
    entry_gpr_trace = assert(io.open(root .. "/entry-gpr.tsv", "w"))
    entry_gpr_trace:setvbuf("no")
    entry_gpr_trace:write("frame\tcompleted_updates\tcontroller_polls\tconsumed_vi\tpc")
    for index = 0, 31 do
      entry_gpr_trace:write("\tr", index, "_lo\tr", index, "_hi")
    end
    entry_gpr_trace:write("\n")
  end
  if trace_entry_fcr then
    entry_fcr_trace = assert(io.open(root .. "/entry-fcr.tsv", "w"))
    entry_fcr_trace:setvbuf("no")
    entry_fcr_trace:write("frame\tcompleted_updates\tcontroller_polls\t",
      "consumed_vi\tpc\tfcr31\n")
  end
  event.onmemoryexecute(function()
    if completed_updates + 1 < focus_first - 1 or
        completed_updates + 1 > focus_last + 1 then return end
    if not entry_catalog_written and
        os.getenv("JFG_PHASE9_ENTRY_REGISTER_CATALOG") == "1" then
      local registers = emu.getregisters()
      local names = {}
      for name in pairs(registers) do
        if type(name) == "string" then names[#names + 1] = name end
      end
      assert(#names >= 1 and #names <= 512, "register catalog is unbounded")
      table.sort(names)
      local catalog = assert(io.open(root .. "/entry-register-catalog.tsv", "w"))
      catalog:write("name\ttype\tvalue\n")
      for _, name in ipairs(names) do
        assert(name:find("[\r\n\t]") == nil, "invalid register name")
        local value = tostring(registers[name]):gsub("[\r\n\t]", " ")
        catalog:write(name, "\t", type(registers[name]), "\t", value, "\n")
      end
      catalog:close()
      entry_catalog_written = true
    end
    entry_hits = entry_hits + 1
    assert(entry_hits <= 1024, "entry probe overflow")
    local arguments = {}
    for index = 0, 3 do
      local value = assert(register_value({ "A" .. index, "a" .. index,
        "a" .. index .. "_lo", "R" .. (4 + index), "r" .. (4 + index),
        "GPR" .. (4 + index) }), "entry probe cannot read argument")
      arguments[#arguments + 1] = string.format("0x%08x", value & 0xFFFFFFFF)
    end
    entry_trace:write(tostring(emu.framecount()), "\t", tostring(completed_updates),
      "\t", tostring(poll_index), "\t", tostring(consumed_vi_count), "\t",
      string.format("0x%08x", entry_pc), "\t", table.concat(arguments, "\t"), "\n")
    if entry_fpu_trace ~= nil then
      local registers = emu.getregisters()
      entry_fpu_trace:write(tostring(emu.framecount()), "\t",
        tostring(completed_updates), "\t", tostring(poll_index), "\t",
        tostring(consumed_vi_count), "\t", string.format("0x%08x", entry_pc))
      for index = 0, 31 do
        for _, part in ipairs({ "lo", "hi" }) do
          local name = "CP1 FGR REG" .. index .. "_" .. part
          local value = registers[name]
          assert(type(value) == "number" and value == math.floor(value),
            "entry FPU register missing: " .. name)
          entry_fpu_trace:write("\t", string.format("0x%08x", value & 0xFFFFFFFF))
        end
      end
      entry_fpu_trace:write("\n")
    end
    if entry_memory_trace ~= nil then
      entry_memory_trace:write(tostring(emu.framecount()), "\t",
        tostring(completed_updates), "\t", tostring(poll_index), "\t",
        tostring(consumed_vi_count), "\t", string.format("0x%08x", entry_pc))
      for index = 2, 4 do
        local address = tonumber(arguments[index]:sub(3), 16)
        assert(address >= 0x80000000 and address <= 0x803FFF00,
          "entry memory argument is outside RDRAM")
        entry_memory_trace:write("\t")
        for offset = 0, 252, 4 do
          entry_memory_trace:write(string.format("%08x",
            memory.read_u32_be(physical_address(address + offset), "RDRAM")))
        end
      end
      entry_memory_trace:write("\n")
    end
    if entry_gpr_trace ~= nil then
      local registers = emu.getregisters()
      entry_gpr_trace:write(tostring(emu.framecount()), "\t",
        tostring(completed_updates), "\t", tostring(poll_index), "\t",
        tostring(consumed_vi_count), "\t", string.format("0x%08x", entry_pc))
      for index = 0, 31 do
        for _, part in ipairs({ "lo", "hi" }) do
          local name = gpr_names[index + 1] .. "_" .. part
          local value = registers[name]
          assert(type(value) == "number" and value == math.floor(value),
            "entry GPR register missing: " .. name)
          entry_gpr_trace:write("\t", string.format("0x%08x", value & 0xFFFFFFFF))
        end
      end
      entry_gpr_trace:write("\n")
    end
    if entry_fcr_trace ~= nil then
      local value = emu.getregisters()["FCR31"]
      assert(type(value) == "number" and value == math.floor(value),
        "entry FCR31 register missing")
      entry_fcr_trace:write(tostring(emu.framecount()), "\t",
        tostring(completed_updates), "\t", tostring(poll_index), "\t",
        tostring(consumed_vi_count), "\t",
        string.format("0x%08x", entry_pc), "\t",
        string.format("0x%08x", value & 0xFFFFFFFF), "\n")
    end
  end, entry_pc, "phase9-entry-probe", "System Bus")
end
local queue_trace = nil
local queue_hits = 0
local queue_clock_trace = nil
local rcp_clock_trace = nil
local queue_clock_hits = 0
local queue_clock_hooks = {}
local exception_resume_hooks = {}
local os_clock_trace = nil
local os_clock_calls = {}
local os_clock_hits = 0
local os_clock_exceptions = 0
local os_clock_switches = 0
local os_clock_started = 0
local queue_spec = os.getenv("JFG_PHASE9_QUEUE_TRACE")
if queue_spec ~= nil and queue_spec ~= "" then
  assert(focus_first ~= nil and os.getenv("JFG_PHASE9_ORACLE_VI_TRACE") == "1",
    "queue probe requires focused update and VI tracing")
  local selected_queues = {}
  local selected_count = 0
  for token in queue_spec:gmatch("[^,]+") do
    assert(token:match("^0x[0-9A-Fa-f]+$") ~= nil, "invalid queue probe address")
    local address = tonumber(token:sub(3), 16)
    assert(address ~= nil and address >= 0x80000000 and
      address <= 0x803FFFFC and address % 4 == 0 and
      not selected_queues[address], "invalid or duplicate queue probe address")
    selected_queues[address] = true
    selected_count = selected_count + 1
  end
  assert(selected_count >= 1 and selected_count <= 8,
    "queue probe requires 1..8 queues")
  -- Exposed Count can be lazily updated by the core. These observations
  -- qualify ordering/intervals in this reference, not hardware cycle costs.
  local function record_queue_clock(kind)
    if kind == "exception" then os_clock_exceptions = os_clock_exceptions + 1 end
    if queue_clock_trace == nil or completed_updates + 1 < focus_first - 1 or
        completed_updates + 1 > focus_last + 1 then return end
    local count = assert(register_value({ "CP0 REG9" }), "Count unavailable") & 0xFFFFFFFF
    local epc = assert(register_value({ "CP0 REG14" }), "EPC unavailable") & 0xFFFFFFFF
    local cause = assert(register_value({ "CP0 REG13" }), "Cause unavailable") & 0xFFFFFFFF
    queue_clock_hits = queue_clock_hits + 1
    assert(queue_clock_hits <= 8192, "queue clock probe overflow")
    queue_clock_trace:write(kind, "\t", tostring(emu.framecount()), "\t",
      tostring(completed_updates), "\t", tostring(poll_index), "\t",
      tostring(consumed_vi_count), "\t", string.format("0x%08x", count), "\t",
      string.format("0x%08x", epc), "\t", string.format("0x%08x", cause), "\n")
    -- Read-only device observations. Cause.IP2 alone cannot identify which
    -- RCP device asserted; record the pending and enabled bits separately.
    -- These are observations at CPU boundaries, not device latency samples.
    local status = assert(register_value({ "CP0 REG12" })) & 0xffffffff
    rcp_clock_trace:write(kind, "\t", completed_updates, "\t",
      string.format("0x%08x", count), "\t", string.format("0x%08x", status))
    for _, address in ipairs({0xa4300008, 0xa430000c, 0xa4040010,
                               0xa410000c, 0xa4400010}) do
      rcp_clock_trace:write("\t", string.format("0x%08x",
        memory.read_u32_be(address, "System Bus") & 0xffffffff))
    end
    rcp_clock_trace:write("\n")
  end
  local function running_thread()
    -- US guest ABI address observed in the original receive routine.
    local address = memory.read_u32_be(0xa9e90, "RDRAM") & 0xffffffff
    assert(address >= 0x80000000 and address <= 0x803ffffc and address % 4 == 0,
      "invalid running thread pointer")
    return address
  end
  -- Observe resumption of the interrupted thread, not merely an eret that
  -- may dispatch some other thread. These are wall intervals, including
  -- intervening scheduled work; they are never constant HLE costs.
  local interrupted_threads = {}
  local resume_addresses = {}
  local function begin_exception_clock()
    if completed_updates + 1 < focus_first - 1 or
        completed_updates + 1 > focus_last + 1 then return end
    local pc = assert(register_value({ "CP0 REG14" })) & 0xffffffff
    assert(pc >= 0x80000000 and pc <= 0x803ffffc and pc % 4 == 0,
      "invalid exception resume PC")
    local thread = running_thread()
    assert(interrupted_threads[thread] == nil, "nested unfinished exception observation")
    local sp = assert(register_value({ "SP", "sp", "sp_lo", "R29", "r29", "GPR29" })) & 0xffffffff
    interrupted_threads[thread] = {pc = pc, sp = sp}
    if not resume_addresses[pc] then
      assert(#exception_resume_hooks < 256, "exception resume hook overflow")
      local name = "phase9-exception-resume-" .. string.format("%08x", pc)
      resume_addresses[pc] = true
      exception_resume_hooks[#exception_resume_hooks + 1] = name
      event.onmemoryexecute(function()
        local status = assert(register_value({ "CP0 REG12" })) & 0xffffffff
        if (status & 2) ~= 0 then return end
        local active_thread = running_thread()
        local pending = interrupted_threads[active_thread]
        if pending == nil or pending.pc ~= pc then return end
        local active_sp = assert(register_value({ "SP", "sp", "sp_lo", "R29", "r29", "GPR29" })) & 0xffffffff
        if active_sp ~= pending.sp then return end
        interrupted_threads[active_thread] = nil
        record_queue_clock("exception-resume-" .. string.format("%08x", pc))
      end, pc, name, "System Bus")
    end
  end
  local function finish_os_call(pc)
    local thread = running_thread()
    local stack = os_clock_calls[thread]
    local call = stack and stack[#stack]
    if call == nil or call.caller ~= pc then return end
    local sp = assert(register_value({ "SP", "sp", "sp_lo", "R29", "r29", "GPR29" })) & 0xffffffff
    if sp ~= call.sp then return end
    table.remove(stack)
    local count = assert(register_value({ "CP0 REG9" })) & 0xffffffff
    local result = assert(register_value({ "V0", "v0", "v0_lo", "R2", "r2", "GPR2" })) & 0xffffffff
    os_clock_hits = os_clock_hits + 1
    os_clock_trace:write(call.id, "\t", call.update, "\t", string.format("0x%08x", thread),
      "\t", call.kind, "\t", string.format("0x%08x", call.queue), "\t", call.block,
      "\t", call.valid, "\t", call.capacity, "\t", call.output, "\t",
      string.format("0x%08x", call.caller), "\t", (count - call.count) & 0xffffffff,
      "\t", os_clock_exceptions - call.exceptions, "\t",
      os_clock_switches - call.switches, "\t", string.format("0x%08x", result), "\n")
  end
  local entry_clock_calls = {}
  local entry_return_hooks = {}
  local function begin_entry_clock()
    if completed_updates + 1 < focus_first - 1 or
        completed_updates + 1 > focus_last + 1 then return end
    local thread = running_thread()
    local caller = assert(register_value({ "RA", "ra", "ra_lo", "R31", "r31", "GPR31" })) & 0xffffffff
    local sp = assert(register_value({ "SP", "sp", "sp_lo", "R29", "r29", "GPR29" })) & 0xffffffff
    assert(caller >= 0x80000000 and caller <= 0x803ffffc and caller % 4 == 0,
      "invalid entry clock return address")
    local stack = entry_clock_calls[thread] or {}
    entry_clock_calls[thread] = stack
    assert(#stack < 32, "entry clock nesting overflow")
    stack[#stack + 1] = {caller = caller, sp = sp}
    if not entry_return_hooks[caller] then
      assert(#queue_clock_hooks < 64, "entry clock return hook overflow")
      local name = "phase9-entry-clock-return-" .. string.format("%08x", caller)
      entry_return_hooks[caller] = true
      queue_clock_hooks[#queue_clock_hooks + 1] = name
      event.onmemoryexecute(function()
        local active = entry_clock_calls[running_thread()]
        local call = active and active[#active]
        local return_sp = assert(register_value({ "SP", "sp", "sp_lo", "R29", "r29", "GPR29" })) & 0xffffffff
        if call ~= nil and call.caller == caller and call.sp == return_sp then
          table.remove(active)
          record_queue_clock("entry-return")
        end
      end, caller, name, "System Bus")
    end
  end
  local function clock_hook(pc, kind)
    local name = "phase9-queue-clock-" .. kind
    queue_clock_hooks[#queue_clock_hooks + 1] = name
    event.onmemoryexecute(function()
      record_queue_clock(kind)
      if kind == "exception" then begin_exception_clock() end
      if kind == "entry" then begin_entry_clock() end
      if kind:sub(1, 7) == "return-" then finish_os_call(pc) end
    end,
      pc, name, "System Bus")
  end
  if os.getenv("JFG_PHASE9_QUEUE_CLOCK_TRACE") == "1" then
    queue_clock_trace = assert(io.open(root .. "/queue-clock.tsv", "w"))
    queue_clock_trace:setvbuf("no")
    queue_clock_trace:write("event\tframe\tupdate\tpoll\tvi\tcount\tepc\tcause\n")
    rcp_clock_trace = assert(io.open(root .. "/rcp-clock.tsv", "w"))
    rcp_clock_trace:setvbuf("no")
    rcp_clock_trace:write("event\tupdate\tcount\tstatus\tmi_pending\tmi_mask\tsp_status\tdp_status\tvi_line\n")
    os_clock_trace = assert(io.open(root .. "/os-call-clock.tsv", "w"))
    os_clock_trace:setvbuf("no")
    os_clock_trace:write("id\tupdate\tthread\tkind\tqueue\tblock\tvalid\tcapacity\toutput\tcaller\tticks\texceptions\tswitches\tresult\n")
    queue_clock_hooks[#queue_clock_hooks + 1] = "phase9-os-running-thread-write"
    event.onmemorywrite(function() os_clock_switches = os_clock_switches + 1 end,
      0x800a9e90, "phase9-os-running-thread-write", "System Bus")
    clock_hook(0x80000180, "exception")
    if entry_pc ~= nil then clock_hook(entry_pc, "entry") end
  end
  local return_hooks = {}
  queue_trace = assert(io.open(root .. "/queue-calls.tsv", "w"))
  queue_trace:setvbuf("no")
  queue_trace:write("frame\tcompleted_updates\tcontroller_polls\tconsumed_vi\t",
    "kind\tqueue\ta1\ta2\tcaller\n")
  local function record_queue_call(kind)
    if completed_updates + 1 < focus_first - 1 or
        completed_updates + 1 > focus_last + 1 then return end
    local a0 = assert(register_value({ "A0", "a0", "a0_lo", "R4", "r4", "GPR4" })) &
      0xFFFFFFFF
    if not selected_queues[a0] then return end
    local a1 = assert(register_value({ "A1", "a1", "a1_lo", "R5", "r5", "GPR5" })) &
      0xFFFFFFFF
    local a2 = assert(register_value({ "A2", "a2", "a2_lo", "R6", "r6", "GPR6" })) &
      0xFFFFFFFF
    local caller = assert(register_value({ "RA", "ra", "ra_lo", "R31", "r31", "GPR31" })) &
      0xFFFFFFFF
    record_queue_clock(kind .. "-" .. string.format("%08x", a0))
    if os_clock_trace ~= nil then
      local thread = running_thread()
      local stack = os_clock_calls[thread] or {}
      os_clock_calls[thread] = stack
      assert(#stack < 16, "OS call nesting overflow")
      os_clock_started = os_clock_started + 1
      local physical = a0 & 0x1fffffff
      stack[#stack + 1] = {id = os_clock_started, update = completed_updates,
        kind = kind, queue = a0, caller = caller, block = a2,
        valid = memory.read_u32_be(physical + 8, "RDRAM"),
        capacity = memory.read_u32_be(physical + 16, "RDRAM"),
        output = (kind == "recv" and a1 ~= 0) and 1 or 0,
        count = assert(register_value({ "CP0 REG9" })) & 0xffffffff,
        exceptions = os_clock_exceptions, switches = os_clock_switches,
        sp = assert(register_value({ "SP", "sp", "sp_lo", "R29", "r29", "GPR29" })) & 0xffffffff}
    end
    if queue_clock_trace ~= nil and not return_hooks[caller] then
      assert(caller >= 0x80000000 and caller <= 0x803FFFFC and caller % 4 == 0,
        "invalid queue return PC")
      assert(#queue_clock_hooks < 64, "queue return hook overflow")
      return_hooks[caller] = true
      clock_hook(caller, "return-" .. string.format("%08x", caller))
    end
    queue_hits = queue_hits + 1
    assert(queue_hits <= 4096, "queue probe overflow")
    queue_trace:write(tostring(emu.framecount()), "\t", tostring(completed_updates),
      "\t", tostring(poll_index), "\t", tostring(consumed_vi_count), "\t",
      kind, "\t", string.format("0x%08x", a0), "\t",
      string.format("0x%08x", a1), "\t", string.format("0x%08x", a2),
      "\t", string.format("0x%08x", caller), "\n")
  end
  event.onmemoryexecute(function() record_queue_call("recv") end,
    0x80096910, "phase9-queue-recv-entry", "System Bus")
  event.onmemoryexecute(function() record_queue_call("send") end,
    0x80096F20, "phase9-queue-send-entry", "System Bus")
end
if os.getenv("JFG_PHASE9_UPDATE_HASHES") == "1" then
  update_hash = assert(io.open(root .. "/update-hashes.jsonl", "w"))
  update_hash:setvbuf("no")
  update_hash:write('{"kind":"jfg-phase9-update-hash-header","schema":1}\n')
  if event_trace ~= nil then
    event.onmemoryexecute(function()
      trace_event("update-begin", poll_index)
    end, 0x80044FAC, "phase9-game-update-entry", "System Bus")
  end
  -- US main_game_loop's final jr ra, after its stack/register restoration.
  -- This is the same completed call boundary used by the native dispatcher.
  event.onmemoryexecute(function()
    completed_updates = completed_updates + 1
    trace_event("update-end", poll_index)
    write_retrace_hash(completed_updates, update_hash, "update")
    if update_word_trace ~= nil then
      update_word_trace:write(tostring(completed_updates), "\t",
        tostring(poll_index), "\t", tostring(consumed_vi_count), "\t",
        tostring(emu.framecount()), "\t",
        string.format("0x%08x", update_word), "\t",
        string.format("0x%08x", memory.read_u32_be(
          physical_address(update_word), "RDRAM")), "\n")
    end
    if focus_first ~= nil and completed_updates >= focus_first and
        completed_updates <= focus_last then
      local snapshot = assert(io.open(root .. "/focus-update-" ..
        tostring(completed_updates) .. ".rdram", "wb"))
      snapshot:write(memory.read_bytes_as_binary_string(0, 0x400000, "RDRAM"))
      snapshot:close()
    end
    trace:write("game-update\t", tostring(emu.framecount()),
      "\tconsumed-vi\t", tostring(consumed_vi_count),
      "\tupdate\t", tostring(completed_updates), "\n")
  end, 0x80045814, "phase9-game-update-return", "System Bus")
end
if os.getenv("JFG_PHASE9_ORACLE_VI_TRACE") == "1" then
  consumed_vi_hash = assert(io.open(root .. "/consumed-vi-hashes.jsonl", "w"))
  consumed_vi_hash:setvbuf("no")
  consumed_vi_hash:write('{"kind":"jfg-phase9-retrace-hash-header","schema":1}\n')
  -- Supported US __scMain immediately after osRecvMesg returns. Disassembly
  -- establishes s4 = queue, s5 = message output and the return site below.
  event.onmemoryexecute(function()
    local queue = assert(register_value({ "S4", "s4", "s4_lo", "R20", "r20", "GPR20" })) & 0xFFFFFFFF
    local result = assert(register_value({ "V0", "v0", "v0_lo", "R2", "r2", "GPR2" })) & 0xFFFFFFFF
    if queue ~= diagnostic_vi_queue or result ~= 0 then return end
    local output = assert(register_value({ "S5", "s5", "s5_lo", "R21", "r21", "GPR21" }))
    local address = physical_address(output)
    assert(address ~= nil and address + 4 <= 0x400000, "invalid VI message output")
    local message = memory.read_u32_be(address, "RDRAM")
    if message ~= diagnostic_vi_message then return end
    consumed_vi_count = consumed_vi_count + 1
    trace_event("vi-consumed", poll_index)
    trace:write("vi-consumed\t", tostring(emu.framecount()),
      "\tsequence\t", tostring(consumed_vi_count), "\n")
    write_retrace_hash(consumed_vi_count, consumed_vi_hash)
  end, 0x8004F9E0, "phase9-vi-consumed", "System Bus")
end

event.onmemoryexecute(function()
  player_actor = register_value({ "A0", "a0", "a0_lo", "R4", "r4", "GPR4" })
  player_control_calls = player_control_calls + 1
end, 0x80032A48, "phase9-control-player", "System Bus")

local hints_base = nil
local hints_control_hook = nil
local hints_talk_hook = nil
local function refresh_hints_hooks()
  local table = memory.read_u32_be(0xFEAA0, "RDRAM")
  local table_offset = physical_address(table)
  if table_offset == nil or table_offset == 0 or
      table_offset + 32 * 32 + 4 > 0x400000 then
    return
  end
  local base = memory.read_u32_be(table_offset + 32 * 32, "RDRAM")
  if base == 0 or base == hints_base then
    return
  end
  if hints_control_hook ~= nil then
    event.unregisterbyid(hints_control_hook)
  end
  if hints_talk_hook ~= nil then
    event.unregisterbyid(hints_talk_hook)
  end
  hints_base = base
  hints_control_hook = event.onmemoryexecute(function()
    hints_actor = register_value({ "A0", "a0", "a0_lo", "R4", "r4", "GPR4" })
    hints_control_calls = hints_control_calls + 1
  end, base + 0x2E8, "phase9-mrhints-control", "System Bus")
  hints_talk_hook = event.onmemoryexecute(function()
    hints_talk_calls = hints_talk_calls + 1
  end, base + 0x2540, "phase9-mrhints-talk", "System Bus")
end

local function write_actor_trace(frame, kind, actor, calls)
  local position = read_actor_position(actor)
  if position == nil then
    trace:write(kind, "\t", tostring(frame), "\tactor\t0x00000000\tcalls\t",
      tostring(calls), "\n")
    return
  end
  trace:write(kind, "\t", tostring(frame), "\tactor\t",
    string.format("0x%08X", actor & 0xFFFFFFFF), "\tyaw\t",
    string.format("0x%04X", position.yaw), "\tposition-bits\t",
    string.format("%08X,%08X,%08X", position.x, position.y, position.z),
    "\tcalls\t", tostring(calls), "\n")
end

local function capture(frame)
  local stem = string.format("checkpoint-%06d", frame)
  client.screenshot(root .. "/" .. stem .. ".png")
  local snapshot = assert(io.open(root .. "/" .. stem .. ".rdram", "wb"))
  snapshot:write(memory.read_bytes_as_binary_string(0, 0x400000, "RDRAM"))
  snapshot:close()
  local front_mode = memory.read_u8(0xA51B0, "RDRAM")
  trace:write("checkpoint\t", tostring(frame), "\tfront-mode\t",
    tostring(front_mode), "\n")
  write_actor_trace(frame, "player", player_actor, player_control_calls)
  write_actor_trace(frame, "kingbear",
    find_named_actor(0x4B696E67, 0x42656172), 0)
  write_actor_trace(frame, "mrhints", hints_actor, hints_control_calls)
  trace:write("mrhints-talk\t", tostring(frame), "\tcalls\t",
    tostring(hints_talk_calls), "\n")
end

emu.limitframerate(false)
client.frameskip(8)
client.speedmode(400)

while emu.framecount() <= target do
  local frame = emu.framecount()
  refresh_hints_hooks()
  if input_clock == "emulator-frame" then apply_input(frame) end
  write_retrace_hash(frame)
  if checkpoints[frame] then
    capture(frame)
  end
  if frame == target then
    break
  end
  emu.frameadvance()
end

-- Remove our breakpoints while the core is alive. Leaving removal to the Lua
-- console's close handler can dereference a disposed Mupen64Plus core.
for _, name in ipairs({ "phase9-consumed-vi-input", "phase9-controller-poll-input",
    "phase9-controller-start-entry", "phase9-controller-get-entry",
    "phase9-mm-alloc-return",
    "phase9-game-update-entry",
    "phase9-game-update-return",
    "phase9-vi-configure-entry", "phase9-vi-receive-entry", "phase9-vi-consumed",
    "phase9-control-player", "phase9-mrhints-control", "phase9-mrhints-talk" }) do
  event.unregisterbyname(name)
end
if controller_return_trace ~= nil then
  event.unregisterbyname("phase9-controller-return-entry")
  event.unregisterbyname("phase9-controller-return-exit")
  assert(controller_return_pending == nil and controller_return_rows > 0,
    "controller return probe did not complete")
  controller_return_trace:close()
end
if watch_trace ~= nil then
  for byte = 0, 3 do
    event.unregisterbyname("phase9-watch-word-" .. tostring(byte))
  end
  watch_trace:write("result\ttrue\t", tostring(watch_hits), "\n")
  watch_trace:close()
end
if point_trace ~= nil then
  for _, pc in ipairs(point_pcs) do event.unregisterbyname("phase9-point-" .. string.format("%08x", pc)) end
  point_trace:write("result\ttrue\t", tostring(point_hits), "\n")
  point_trace:close()
end
if entry_trace ~= nil then
  event.unregisterbyname("phase9-entry-probe")
  entry_trace:write("result\ttrue\t", tostring(entry_hits), "\n")
  entry_trace:close()
end
if entry_fpu_trace ~= nil then
  entry_fpu_trace:write("result\ttrue\t", tostring(entry_hits), "\n")
  entry_fpu_trace:close()
end
if entry_memory_trace ~= nil then
  entry_memory_trace:write("result\ttrue\t", tostring(entry_hits), "\n")
  entry_memory_trace:close()
end
if entry_gpr_trace ~= nil then
  entry_gpr_trace:write("result\ttrue\t", tostring(entry_hits), "\n")
  entry_gpr_trace:close()
end
if entry_fcr_trace ~= nil then
  entry_fcr_trace:write("result\ttrue\t", tostring(entry_hits), "\n")
  entry_fcr_trace:close()
end
if queue_trace ~= nil then
  for _, name in ipairs(queue_clock_hooks) do event.unregisterbyname(name) end
  for _, name in ipairs(exception_resume_hooks) do event.unregisterbyname(name) end
  if queue_clock_trace ~= nil then
    queue_clock_trace:write("result\ttrue\t", tostring(queue_clock_hits), "\n")
    queue_clock_trace:close()
    rcp_clock_trace:write("result\ttrue\t", tostring(queue_clock_hits), "\n")
    rcp_clock_trace:close()
    local unfinished = 0
    for _, stack in pairs(os_clock_calls) do unfinished = unfinished + #stack end
    os_clock_trace:write("result\ttrue\t", os_clock_hits, "\t", unfinished, "\n")
    os_clock_trace:close()
  end
  event.unregisterbyname("phase9-queue-recv-entry")
  event.unregisterbyname("phase9-queue-send-entry")
  queue_trace:write("result\ttrue\t", tostring(queue_hits), "\n")
  queue_trace:close()
end
trace:write("result\ttrue\t", tostring(emu.framecount()), "\n")
trace:close()
retrace_hash:close()
if consumed_vi_hash ~= nil then consumed_vi_hash:close() end
if update_hash ~= nil then update_hash:close() end
if update_word_trace ~= nil then update_word_trace:close() end
if poll_hash ~= nil then poll_hash:close() end
if event_trace ~= nil then event_trace:close() end
if controller_callers_trace ~= nil then controller_callers_trace:close() end
if si_trace ~= nil then
  if si_clock_trace ~= nil then
  event.unregisterbyname("phase9-si-clock-ack")
  event.unregisterbyname("phase9-si-clock-recv")
  si_clock_trace:close()
  assert(si_clock_receive_hits > 0, "SI clock receive hook produced no observations")
  end
  event.unregisterbyname("phase9-si-entry")
  for _, name in ipairs(si_hook_names) do event.unregisterbyname(name) end
  assert(si_pending == nil and si_rows > 0,
    "SI transaction trace did not complete")
  si_trace:close()
end
client.exitCode(0)
