local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"))
local trace = assert(io.open(root .. "/cpu-vi_manager.tsv", "w"))
local events = assert(io.open(root .. "/vi-events.tsv", "w"))
events:write("event\tcount\tcurrent\tv_sync\tcause\tepc\n")
local function capture(label)
  local r = emu.getregisters()
  events:write(string.format("%s\t%08x\t%08x\t%08x\t%08x\t%08x\n", label,
    r["CP0 REG9"] & 0xffffffff, memory.read_u32_be(0xa4400010, "System Bus"),
    memory.read_u32_be(0xa4400018, "System Bus"), r["CP0 REG13"] & 0xffffffff,
    r["CP0 REG14"] & 0xffffffff))
  events:flush()
end
event.onmemoryexecute(function() capture("start") end, 0x80000400, "vi-test-start", "System Bus")
event.onmemoryexecute(function() capture("init") end, 0x8009ab80, "vi-test-init", "System Bus")
event.onmemoryexecute(function() capture("interrupt") end, 0x80075030, "vi-test-interrupt", "System Bus")
trace:write("case\tcount\tpayload\tvi_count\ttime_hi\ttime_lo\tstatus\n")
local done = false
for _ = 1, 180 do
  emu.frameadvance()
  if memory.read_u32_be(0x301780, "RDRAM") == 0x4a464756 then
    for row = 0, 23 do
      local base = 0x301400 + row * 28
      trace:write(memory.read_u32_be(base + 24, "RDRAM"))
      for column = 0, 5 do trace:write("\t", memory.read_u32_be(base + column * 4, "RDRAM")) end
      trace:write("\n")
    end
    trace:write("result\ttrue\t24\n")
    done = true
    break
  end
end
for _, name in ipairs({"vi-test-start", "vi-test-init", "vi-test-interrupt"}) do event.unregisterbyname(name) end
trace:close()
events:close()
client.exitCode(done and 0 or 3)
