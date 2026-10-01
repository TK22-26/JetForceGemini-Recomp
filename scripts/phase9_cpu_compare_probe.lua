local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"))
local trace = assert(io.open(root .. "/cpu-compare.tsv", "w"))
trace:write("case\tphase\tcompare\tlast_pending\tfirst_complete\n")
local pending, cases = nil, 0
event.onmemoryexecute(function()
  assert(pending == nil)
  local r = emu.getregisters()
  pending = {case=r.s1_lo, phase=r.s2_lo, compare=r.a0_lo & 0xffffffff,
    last=r["CP0 REG9"] & 0xffffffff}
end, 0x80000800, "compare-arm", "System Bus")
event.onmemoryexecute(function()
  assert(pending)
  local r = emu.getregisters()
  local count = r["CP0 REG9"] & 0xffffffff
  if (r["CP0 REG13"] & 0x8000) == 0 then
    pending.last = count
  else
    assert(pending.last)
    trace:write(pending.case, "\t", pending.phase, "\t", pending.compare, "\t", pending.last, "\t", count, "\n")
    pending = nil
    cases = cases + 1
  end
end, 0x80000840, "compare-poll", "System Bus")
local done = false
for _ = 1, 180 do
  emu.frameadvance()
  if memory.read_u32_be(0x1000, "RDRAM") == 0x4a46474d then
    assert(cases == 64 and pending == nil)
    for row = 0, 63 do
      assert(memory.read_u32_be(0x1100 + row * 16 + 8, "RDRAM") == 0x8000)
      assert((memory.read_u32_be(0x1100 + row * 16 + 12, "RDRAM") & 0x8000) == 0)
    end
    trace:write("result\ttrue\t64\n")
    done = true
    break
  end
end
trace:close()
event.unregisterbyname("compare-arm")
event.unregisterbyname("compare-poll")
client.exitCode(done and 0 or 3)
