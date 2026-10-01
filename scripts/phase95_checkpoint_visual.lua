-- Read-only rendering probe for a sealed US BizHawk checkpoint.
-- This diagnostic never supplies controller input and is not a route proof.
local root = assert(os.getenv("JFG_PHASE95_VISUAL_ROOT"))
local state = assert(os.getenv("JFG_PHASE95_VISUAL_STATE"))

local ok, problem = pcall(function()
  emu.limitframerate(false)
  assert(savestate.load(state), "checkpoint load failed")
  local memory_file = assert(io.open(root .. "/visual.rdram", "wb"))
  memory_file:write(memory.read_bytes_as_binary_string(0, 0x400000, "RDRAM"))
  memory_file:close()
  client.screenshot(root .. "/visual.png")
  local picture = assert(io.open(root .. "/visual.png", "rb"), "screenshot missing")
  assert(picture:seek("end") > 100, "screenshot empty")
  picture:close()
end)

local result = assert(io.open(root .. "/visual-status.txt", "w"))
result:write(ok and "captured\n" or ("error\n" .. tostring(problem) .. "\n"))
result:close()
client.exitCode(ok and 0 or 1)
client.exit()
