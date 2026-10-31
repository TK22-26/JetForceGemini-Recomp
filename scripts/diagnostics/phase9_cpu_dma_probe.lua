local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"))
local trace = assert(io.open(root .. "/cpu-dma.tsv", "w"))
trace:write("kind\tlength\tphase\tlaunch\tlast_pending\tfirst_complete\n")
local pending, cases = nil, 0
local payload = assert(io.open(root .. "/si-payloads.tsv", "w"))
payload:write("kind\tlength\tphase\tstatus\tpayload\n")
local completed = assert(io.open(root .. "/si-completed.tsv", "w"))
completed:write("kind\tlength\tphase\tstatus\tpif\n")
event.onmemoryexecute(function()
  assert(pending == nil)
  local r = emu.getregisters()
  pending = {kind=assert(r.s1_lo), length=assert(r.s4_lo), phase=assert(r.s3_lo),
    launch=assert(r["CP0 REG9"]) & 0xffffffff}
end, 0x80000800, "dma-launch", "System Bus")
event.onmemoryexecute(function()
  assert(pending)
  local count = assert(emu.getregisters()["CP0 REG9"]) & 0xffffffff
  local mask = pending.kind == 0 and 16 or 2
  if not pending.observed and pending.kind > 0 then
    payload:write(pending.kind, "\t", pending.length, "\t", pending.phase, "\t",
      memory.read_u32_be(0xa4800018, "System Bus"), "\t")
    for offset = 0, 63 do payload:write(string.format("%02x", memory.read_u8(0x300000 + offset, "RDRAM"))) end
    payload:write("\n")
    pending.observed = true
  end
  if (memory.read_u32_be(0xa4300008, "System Bus") & mask) == 0 then
    pending.last = count
  else
    if pending.kind > 0 then
      completed:write(pending.kind, "\t", pending.length, "\t", pending.phase, "\t",
        memory.read_u32_be(0xa4800018, "System Bus"), "\t")
      for offset = 0, 63 do completed:write(string.format("%02x", memory.read_u8(0xbfc007c0 + offset, "System Bus"))) end
      completed:write("\n")
    end
    trace:write(pending.kind, "\t", pending.length, "\t", pending.phase, "\t",
      pending.launch, "\t", pending.last or pending.launch, "\t", count, "\n")
    pending = nil
    cases = cases + 1
  end
end, 0x80000858, "dma-poll", "System Bus")
local done = false
for _ = 1, 180 do
  emu.frameadvance()
  if memory.read_u32_be(0x1000, "RDRAM") == 0x4a464744 then
    assert(cases == 320 and pending == nil)
    for row = 0, 31 do
      assert(memory.read_u32_be(0x1100 + row * 20 + 16, "RDRAM") == 0x80371240)
    end
    trace:write("result\ttrue\t320\n")
    done = true
    break
  end
end
trace:close()
payload:close()
completed:close()
event.unregisterbyname("dma-launch")
event.unregisterbyname("dma-poll")
client.exitCode(done and 0 or 3)
