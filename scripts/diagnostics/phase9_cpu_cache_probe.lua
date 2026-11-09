local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"))
local trace = assert(io.open(root .. "/cpu-cache.tsv", "w"))
trace:write("kind\tfunction\talignment\tlength\tvalue\n")
local lengths = {-4, -1, 0, 1, 2, 15, 16, 17, 31, 32, 33, 8191, 8192, 8193, 16383, 16384}
local done = false
for _ = 1, 180 do
  emu.frameadvance()
  if memory.read_u32_be(0x1000, "RDRAM") == 0x4a46474b then
    assert(memory.read_u32_be(0x1004, "RDRAM") == 193)
    local index = 0
    for routine = 0, 2 do
      for _, alignment in ipairs({0, 1, 15, 31}) do
        for _, length in ipairs(lengths) do
          trace:write("call\t", routine, "\t", alignment, "\t", length, "\t",
            memory.read_u32_be(0x1100 + index * 4, "RDRAM"), "\n")
          index = index + 1
        end
      end
    end
    trace:write("call\t3\t0\t0\t", memory.read_u32_be(0x1400, "RDRAM"), "\n")
    for routine = 0, 3 do
      for phase = 0, 2 do
        trace:write("alias\t", routine, "\t", phase, "\t-\t", string.format("0x%08x",
          memory.read_u32_be(0x1010 + routine * 12 + phase * 4, "RDRAM")), "\n")
      end
    end
    trace:write("result\ttrue\t", string.format("0x%08x", memory.read_u32_be(0x1008, "RDRAM")), "\n")
    done = true
    break
  end
end
trace:close()
client.exitCode(done and 0 or 3)
