local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"))
local trace = assert(io.open(root .. "/cpu-mask.tsv", "w"))
trace:write("old_mask\trequested_mask\tticks\tresult\tstatus\tmi_mask\n")
local done = false
for _ = 1, 180 do
  emu.frameadvance()
  if memory.read_u32_be(0x1000, "RDRAM") == 0x4a46474d then
    assert(memory.read_u32_be(0x1008, "RDRAM") == 128)
    for index = 0, 127 do
      local base = 0x1100 + index * 16
      trace:write(index < 64 and 0 or 63, "\t", index % 64, "\t",
        memory.read_u32_be(base, "RDRAM"))
      for field = 1, 3 do
        trace:write("\t", string.format("0x%08x", memory.read_u32_be(base + field * 4, "RDRAM")))
      end
      trace:write("\n")
    end
    trace:write("result\ttrue\t", string.format("0x%08x", memory.read_u32_be(0x1004, "RDRAM")), "\n")
    done = true
    break
  end
end
trace:close()
client.exitCode(done and 0 or 3)
