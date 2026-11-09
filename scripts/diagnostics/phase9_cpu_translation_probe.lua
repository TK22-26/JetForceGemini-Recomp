local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"))
local trace = assert(io.open(root .. "/cpu-translation.tsv", "w"))
trace:write("kind\tindex\thi_or_ticks\tlo0_or_result\tlo1\tmask\n")
local done = false
for _ = 1, 180 do
  emu.frameadvance()
  if memory.read_u32_be(0x1218, "RDRAM") == 0x4a464754 then
    for index = 0, 31 do
      trace:write("tlb\t", index)
      for word = 0, 3 do
        trace:write("\t", string.format("0x%08x", memory.read_u32_be(
          0x1000 + index * 16 + word * 4, "RDRAM")))
      end
      trace:write("\n")
    end
    for index = 0, 2 do
      trace:write("call\t", index, "\t", memory.read_u32_be(0x1200 + index * 8, "RDRAM"),
        "\t", string.format("0x%08x", memory.read_u32_be(0x1204 + index * 8, "RDRAM")),
        "\t-\t-\n")
    end
    local probes = memory.read_u32_be(0x1238, "RDRAM")
    assert(probes == 0 or probes == 6, "invalid extra TLB probe count")
    for index = 0, probes - 1 do
      trace:write("probe\t", index, "\t-\t", string.format("0x%08x",
        memory.read_u32_be(0x1220 + index * 4, "RDRAM")), "\t-\t-\n")
    end
    trace:write("result\ttrue\t", string.format("0x%08x",
      memory.read_u32_be(0x121c, "RDRAM")), "\n")
    done = true
    break
  end
end
trace:close()
client.exitCode(done and 0 or 3)
