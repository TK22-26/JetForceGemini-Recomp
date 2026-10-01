local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"))
local trace = assert(io.open(root .. "/cpu-pi_timing.tsv", "w"))
local device = assert(io.open(root .. "/pi-registers.tsv", "w"))
local bytes = assert(io.open(root .. "/pi-bytes.tsv", "w"))
bytes:write("length\tphase\tcopied_mismatches\ttrailing_bytes\n")
local byte_profile = false
device:write("length\tphase\tcount\tpending\tword\tdram\tcart\tlength_reg\tstatus\n")
trace:write("length\tphase\tlaunch\tlast_pending\tfirst_complete\n")
local pending, cases = nil, 0
event.onmemoryexecute(function()
  assert(pending == nil)
  local r = emu.getregisters()
  pending = {length=assert(r.s4_lo), phase=assert(r.s3_lo), launch=r["CP0 REG9"] & 0xffffffff}
  if cases == 0 then byte_profile = pending.length == 1 end
end, 0x80000800, "pi-tight-launch", "System Bus")
event.onmemoryexecute(function()
  assert(pending)
  local count = emu.getregisters()["CP0 REG9"] & 0xffffffff
  if not pending.observed then
    if byte_profile then
      local offset = memory.read_u32_be(0xa4600000, "System Bus") - 0x300000
      local source = memory.read_u32_be(0xa4600004, "System Bus") - 0x10000000
      local mismatches = 0
      for i = 0, pending.length - 1 do
        if memory.read_u8(0x300000 + offset + i, "RDRAM") ~= memory.read_u8(0xb0000000 + source + i, "System Bus") then
          mismatches = mismatches + 1
        end
      end
      local trailing = {}
      for i = pending.length, pending.length + 15 do
        trailing[#trailing + 1] = string.format("%02x", memory.read_u8(0x300000 + offset + i, "RDRAM"))
      end
      bytes:write(pending.length, "\t", pending.phase, "\t", mismatches, "\t", table.concat(trailing), "\n")
    end
    device:write(pending.length, "\t", pending.phase, "\t", count, "\t",
      memory.read_u32_be(0xa4300008, "System Bus") & 16, "\t",
      memory.read_u32_be(0x300000 + (pending.phase % 2) * 4, "RDRAM"), "\t",
      memory.read_u32_be(0xa4600000, "System Bus"), "\t",
      memory.read_u32_be(0xa4600004, "System Bus"), "\t",
      memory.read_u32_be(0xa460000c, "System Bus"), "\t",
      memory.read_u32_be(0xa4600010, "System Bus"), "\n")
    pending.observed = true
  end
  if (memory.read_u32_be(0xa4300008, "System Bus") & 16) == 0 then
    pending.last = count
  else
    trace:write(pending.length, "\t", pending.phase, "\t", pending.launch, "\t",
      pending.last or pending.launch, "\t", count, "\n")
    pending = nil
    cases = cases + 1
  end
end, 0x80000840, "pi-tight-poll", "System Bus")
local done = false
for _ = 1, 180 do
  emu.frameadvance()
  if memory.read_u32_be(0x1000, "RDRAM") == 0x4a464751 then
    assert(cases == 152 and pending == nil)
    if not byte_profile then
      for row = 0, 151 do
        assert(memory.read_u32_be(0x1100 + row * 12 + 8, "RDRAM") == (row % 2 == 0 and 0x80371240 or 0x0000000f))
      end
    end
    trace:write("result\ttrue\t152\n")
    done = true
    break
  end
end
trace:close()
device:close()
bytes:close()
event.unregisterbyname("pi-tight-launch")
event.unregisterbyname("pi-tight-poll")
client.exitCode(done and 0 or 3)
