-- Bounded, read-only observation / ordinary-controller-action bridge.
local root = assert(os.getenv("JFG_PHASE95_ROOT"))
local session = assert(os.getenv("JFG_PHASE95_SESSION"))
assert(session:match("^[a-f0-9]+$"))
local sequence, polls, player = 0, 0, 0
local buttons, sx, sy = 0, 0, 0
local bindings = {
  {0x8000,"A"},{0x4000,"B"},{0x2000,"Z"},{0x1000,"Start"},
  {0x0800,"DPad U"},{0x0400,"DPad D"},{0x0200,"DPad L"},{0x0100,"DPad R"},
  {0x0020,"L"},{0x0010,"R"},{0x0008,"C Up"},{0x0004,"C Down"},
  {0x0002,"C Left"},{0x0001,"C Right"},
}
local log = assert(io.open(root .. "/input-polls.tsv", "w"))
log:setvbuf("no")
log:write("schema\t1\tsession\t", session, "\n")
local function apply()
  local values = {}
  for _, binding in ipairs(bindings) do
    values[binding[2]] = (buttons & binding[1]) ~= 0
  end
  -- Mupen GetStickValues prioritizes these digital analog-direction bindings
  -- over X/Y Axis. Suppress host keyboard/autohold directions explicitly.
  for _, name in ipairs({"A Left", "A Right", "A Up", "A Down"}) do
    values[name] = false
  end
  joypad.set(values, 1)
  joypad.setanalog({["X Axis"]=sx, ["Y Axis"]=sy}, 1)
end
local function neutral()
  buttons, sx, sy = 0, 0, 0
  apply()
end
event.oninputpoll(function()
  apply()
  polls = polls + 1
  log:write(polls, "\t", emu.framecount(), "\t", sequence, "\t",
    buttons, "\t", sx, "\t", sy, "\n")
end, "phase95-input")
event.onmemoryexecute(function()
  local regs = emu.getregisters()
  local value = regs.A0 or regs.a0 or regs.a0_lo or regs.R4 or regs.r4 or regs.GPR4
  assert(value ~= nil, "controlPlayer register unavailable")
  player = value & 0xFFFFFFFF
end, 0x80032A48, "phase95-player", "System Bus")

local function publish()
  -- Ready file is renamed last: the host cannot observe a partial memory dump.
  local data = assert(io.open(root .. "/observation.rdram", "wb"))
  data:write(memory.read_bytes_as_binary_string(0, 0x400000, "RDRAM"))
  data:close()
  local ready = assert(io.open(root .. "/ready.tmp", "w"))
  ready:write("phase95-v1 ", session, " ", sequence, " ", emu.framecount(),
    " ", polls, " ", player, "\n")
  ready:close()
  assert(os.rename(root .. "/ready.tmp", root .. "/ready.txt"))
end

local function run()
  emu.limitframerate(false)
  client.frameskip(8)
  while true do
    neutral()
    publish()
    local deadline = os.time() + 30
    local command
    -- Pausing prevents unrecorded game progress while waiting for the planner.
    client.pause()
    repeat
      local file = io.open(root .. "/command.txt", "r")
      if file then command = file:read("*a"); file:close() end
      if not command then client.sleep(5); emu.yield() end
      assert(os.time() <= deadline, "planner command timeout")
    until command
    assert(os.remove(root .. "/command.txt"))
    local state_token, state_seq, operation, slot = command:match(
      "^phase95%-state ([a-f0-9]+) (%d+) (%a+) ([a-f0-9]+)\n$")
    if state_token then
      assert(state_token == session and tonumber(state_seq) == sequence,
        "stale state command")
      assert(#slot <= 32, "invalid checkpoint slot")
      local path = root .. "/checkpoint-" .. slot
      if operation == "save" then
        local existing = io.open(path .. ".State", "rb")
        if existing then existing:close(); error("checkpoint already exists") end
        assert(savestate.save(path .. ".State"), "savestate save failed")
        local side = assert(io.open(path .. ".side", "w"))
        side:write(session, " ", polls, " ", player, "\n")
        side:close()
      elseif operation == "load" then
        local side = assert(io.open(path .. ".side", "r"))
        local saved_session, saved_polls, saved_player = side:read("*a"):match(
          "^([a-f0-9]+) (%d+) (%d+)\n$")
        side:close()
        assert(saved_session == session, "checkpoint session mismatch")
        assert(savestate.load(path .. ".State"), "savestate load failed")
        polls, player = tonumber(saved_polls), tonumber(saved_player)
        neutral()
      else error("unsupported checkpoint operation") end
      log:write("checkpoint\t", sequence, "\t", operation, "\t", slot, "\n")
    else
    local token, seq, frames, mask, x, y = command:match(
      "^phase95%-v1 ([a-f0-9]+) (%d+) (%d+) (%d+) (-?%d+) (-?%d+)\n$")
    seq, frames, mask, x, y = tonumber(seq), tonumber(frames), tonumber(mask), tonumber(x), tonumber(y)
    assert(token == session and seq == sequence, "stale command or wrong session")
    assert(frames and frames <= 120 and mask <= 65535 and
      x >= -128 and x <= 127 and y >= -128 and y <= 127, "invalid action")
    if frames == 0 then break end
    buttons, sx, sy = mask, x, y
    apply()
    client.unpause()
    for _ = 1, frames do
      apply() -- analog autoholds must be installed before frontend frame sampling
      emu.frameadvance()
    end
    end
    sequence = sequence + 1
  end
end

local ok, problem = pcall(run)
neutral()
event.unregisterbyname("phase95-input")
event.unregisterbyname("phase95-player")
log:close()
local result = assert(io.open(root .. "/bridge-result.txt", "w"))
result:write(ok and "stopped\n" or ("error\n" .. tostring(problem) .. "\n"))
result:close()
client.exitCode(ok and 0 or 1)
