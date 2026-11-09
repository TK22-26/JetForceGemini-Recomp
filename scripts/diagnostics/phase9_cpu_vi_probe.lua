local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"))
local trace = assert(io.open(root .. "/cpu-vi.tsv", "w"))
trace:write("v_sync\th_sync\tsample\tticks\n")
local done = false
for _ = 1, 600 do
  emu.frameadvance()
  if memory.read_u32_be(0x1000, "RDRAM") == 0x4a464756 then
    for row = 0, 11 do
      local address = 0x1100 + row * 136
      for sample = 0, 31 do
        trace:write(memory.read_u32_be(address, "RDRAM"), "\t",
          memory.read_u32_be(address + 4, "RDRAM"), "\t", sample, "\t",
          memory.read_u32_be(address + 8 + sample * 4, "RDRAM"), "\n")
      end
    end
    trace:write("result\ttrue\t384\n")
    done = true
    break
  end
end
trace:close()
client.exitCode(done and 0 or 3)
