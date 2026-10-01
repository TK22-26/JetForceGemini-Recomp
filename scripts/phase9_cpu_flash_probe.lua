local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"))
local trace = assert(io.open(root .. "/cpu-flash.tsv", "w"))
trace:write("phase\tstage\tlaunch\tlast_pending\tfirst_complete\tpi_status\tpayload\n")
local commands = assert(io.open(root .. "/flash-commands.tsv", "w"))
commands:write("phase\tstage\tcommand\tstatus_before\tstatus_after\n")
local pending, command, count = nil, nil, 0
local epochs = assert(io.open(root .. "/flash-epochs.tsv", "w"))
epochs:write("phase\tstage\tbefore_store\tafter_store\tmfc0_value\n")
local clears = assert(io.open(root .. "/flash-clear.tsv", "w"))
clears:write("phase\tstage\tcommand\tstatus_before\tstatus_after\n")
event.onmemoryexecute(function()
  local r = emu.getregisters()
  command = {r.s5_lo, r.s4_lo, r.a0_lo, r.v1_lo}
end, 0x80000808, "flash-command", "System Bus")
event.onmemoryexecute(function()
  assert(command)
  commands:write(table.concat(command, "\t"), "\t", emu.getregisters().v0_lo, "\n")
  command = nil
end, 0x80000810, "flash-command-after", "System Bus")
event.onmemoryexecute(function()
  local r = emu.getregisters()
  clears:write(r.s5_lo, "\t", r.s4_lo, "\t", r.a0_lo, "\t", r.v0_lo, "\t", r.a2_lo, "\n")
end, 0x80000818, "flash-clear-after", "System Bus")
event.onmemoryexecute(function()
  assert(pending == nil)
  local r = emu.getregisters()
  pending = {phase=r.s5_lo, stage=r.s4_lo, launch=r["CP0 REG9"] & 0xffffffff}
end, 0x80000840, "flash-dma", "System Bus")
event.onmemoryexecute(function()
  local r = emu.getregisters()
  assert(pending)
  if pending.epoch then return end
  pending.epoch = true
  epochs:write(pending.phase, "\t", pending.stage, "\t", pending.launch, "\t",
    r["CP0 REG9"] & 0xffffffff, "\t", r.t5_lo, "\n")
end, 0x80000844, "flash-after-store", "System Bus")
event.onmemoryexecute(function()
  assert(pending)
  local ticks = emu.getregisters()["CP0 REG9"] & 0xffffffff
  if not pending.data then
    local bytes = {}
    for i = 0, 127 do bytes[#bytes+1] = string.format("%02x", memory.read_u8(0x301000 + i, "RDRAM")) end
    pending.data = table.concat(bytes)
    pending.status = memory.read_u32_be(0xa4600010, "System Bus")
  end
  if (memory.read_u32_be(0xa4300008, "System Bus") & 16) == 0 then pending.last = ticks
  else
    trace:write(pending.phase, "\t", pending.stage, "\t", pending.launch, "\t", pending.last or pending.launch,
      "\t", ticks, "\t", pending.status, "\t", pending.data, "\n")
    pending = nil
    count = count + 1
  end
end, 0x80000880, "flash-poll", "System Bus")
local done = false
for _ = 1, 180 do
  emu.frameadvance()
  if memory.read_u32_be(0x1000, "RDRAM") == 0x4a464746 then
    done = count == 40 and pending == nil
    break
  end
end
trace:write("result\t", tostring(done), "\t", count, "\n")
trace:close()
commands:close()
epochs:close()
clears:close()
for _, name in ipairs({"flash-command", "flash-command-after", "flash-dma", "flash-after-store", "flash-poll", "flash-clear-after"}) do event.unregisterbyname(name) end
client.exitCode(done and 0 or 3)
