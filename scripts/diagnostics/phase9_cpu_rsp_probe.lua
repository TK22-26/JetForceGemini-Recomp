local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"))
local trace = assert(io.open(root .. "/cpu-rsp.tsv", "w"))
trace:write("type\tnops\tflags\tload_ticks\tstart_ticks\tcomplete_ticks\tsp_status\tmi_pending\n")
local deadlines = assert(io.open(root .. "/rsp-deadlines.tsv", "w"))
deadlines:write("case\tlaunch\tlast_running\tfirst_halted\thelper_entry\tbefore_start\n")
local launches = 0
local pending = nil
local helper_entry = nil
local devices = assert(io.open(root .. "/rsp-device-events.tsv", "w"))
devices:write("case\tsite\tcount\tmi_pending\tsp_status\n")
local function device_event(site, count)
  devices:write(launches, "\t", site, "\t", count, "\t",
    memory.read_u32_be(0xa4300008, "System Bus"), "\t",
    memory.read_u32_be(0xa4040010, "System Bus"), "\n")
end
local boundaries = assert(io.open(root .. "/rsp-boundaries.tsv", "w"))
boundaries:write("case\tpc\tcount\tmi_pending\tsp_status\n")
local function boundary(pc)
  if launches == 0 then return end
  boundaries:write(launches, "\t", pc, "\t", emu.getregisters()["CP0 REG9"] & 0xffffffff, "\t",
    memory.read_u32_be(0xa4300008, "System Bus"), "\t",
    memory.read_u32_be(0xa4040010, "System Bus"), "\n")
end
for _, pc in ipairs({0x80000808, 0x80000818, 0x8000082c, 0x800991ec}) do
  event.onmemoryexecute(function() boundary(pc) end, pc, "rsp-boundary-" .. pc, "System Bus")
end
local loads = assert(io.open(root .. "/rsp-loads.tsv", "w"))
loads:write("case\tsp_mem\tsp_dram\tread_length\tdma_full\tdma_busy\tsp_pc\tsp_status\ttask_dmem\tboot_imem\n")
local load_count = 0
local function words(address, count)
  local result = {}
  for word = 0, count - 1 do
    result[#result + 1] = string.format("%08x", memory.read_u32_be(address + word * 4, "System Bus"))
  end
  return table.concat(result)
end
event.onmemoryexecute(function()
  load_count = load_count + 1
  assert(load_count <= 16)
  loads:write(load_count)
  for _, address in ipairs({0xa4040000, 0xa4040004, 0xa4040008,
      0xa4040014, 0xa4040018, 0xa4080000, 0xa4040010}) do
    loads:write("\t", memory.read_u32_be(address, "System Bus"))
  end
  loads:write("\t", words(0xa4000fc0, 16), "\t", words(0xa4001000, 96), "\n")
end, 0x800991b4, "micro-sp-load-return", "System Bus")
event.onmemoryexecute(function()
  local registers = emu.getregisters()
  if registers["a0_lo"] == 0x125 then
    helper_entry = assert(registers["CP0 REG9"]) & 0xffffffff
  end
end, 0x80098030, "micro-sp-helper-entry", "System Bus")
event.onmemoryexecute(function()
  local registers = emu.getregisters()
  if registers["a0_lo"] ~= 0x125 then return end
  assert(pending == nil, "overlapping SP microtest launches")
  launches = launches + 1
  assert(launches <= 16)
  pending = {launch = assert(registers["CP0 REG9"]) & 0xffffffff,
    helper_entry = assert(helper_entry), before_start = assert(registers["s6_lo"]) & 0xffffffff}
  helper_entry = nil
end, 0x80098038, "micro-sp-launch", "System Bus")
event.onmemoryexecute(function()
  if pending then device_event("after-start", emu.getregisters()["CP0 REG9"] & 0xffffffff) end
end, 0x800991ec, "micro-sp-after-start", "System Bus")
event.onmemoryexecute(function()
  assert(pending ~= nil, "SP polling without a launch")
  local count = assert(emu.getregisters()["CP0 REG9"]) & 0xffffffff
  local status = memory.read_u32_be(0xa4040010, "System Bus")
  if not pending.first then device_event("first-poll", count); pending.first = true end
  if not pending.dp and (memory.read_u32_be(0xa4300008, "System Bus") & 32) ~= 0 then
    device_event("first-dp", count); pending.dp = true
  end
  if (status & 1) == 0 then
    pending.running = count
  else
    device_event("first-halted", count)
    assert(pending.running ~= nil, "SP task already completed before first poll")
    deadlines:write(launches, "\t", pending.launch, "\t", pending.running, "\t", count,
      "\t", pending.helper_entry, "\t", pending.before_start, "\n")
    pending = nil
  end
end, 0x80000808, "micro-sp-poll", "System Bus")
local done = false
for _ = 1, 180 do
  emu.frameadvance()
  if memory.read_u32_be(0x1000, "RDRAM") == 0x4a464752 then
    for row = 0, 15 do
      for column = 0, 7 do
        if column ~= 0 then trace:write("\t") end
        trace:write(memory.read_u32_be(0x1100 + row * 32 + column * 4, "RDRAM"))
      end
      trace:write("\n")
    end
    trace:write("result\ttrue\t16\n")
    assert(launches == 16 and pending == nil)
    deadlines:write("result\ttrue\t16\n")
    assert(load_count == 16)
    loads:write("result\ttrue\t16\n")
    done = true
    break
  end
end
trace:close()
deadlines:close()
loads:close()
devices:close()
boundaries:close()
for _, pc in ipairs({0x80000808, 0x80000818, 0x8000082c, 0x800991ec}) do
  event.unregisterbyname("rsp-boundary-" .. pc)
end
event.unregisterbyname("micro-sp-load-return")
event.unregisterbyname("micro-sp-launch")
event.unregisterbyname("micro-sp-poll")
event.unregisterbyname("micro-sp-helper-entry")
event.unregisterbyname("micro-sp-after-start")
client.exitCode(done and 0 or 3)
