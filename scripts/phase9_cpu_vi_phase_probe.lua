local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"))
local trace = assert(io.open(root .. "/cpu-vi_phase.tsv", "w"))
trace:write("v_sync\tsample\tcount\tcurrent\tedge_count\n")
local done = false
for _ = 1, 180 do
  emu.frameadvance()
  if memory.read_u32_be(0x1000, "RDRAM") == 0x4a464750 then
    for row = 0, 127 do
      for col = 0, 4 do
        if col ~= 0 then trace:write("\t") end
        trace:write(memory.read_u32_be(0x1100 + row * 20 + col * 4, "RDRAM"))
      end
      trace:write("\n")
    end
    trace:write("result\ttrue\t128\n")
    done = true
    break
  end
end
trace:close()
client.exitCode(done and 0 or 3)
