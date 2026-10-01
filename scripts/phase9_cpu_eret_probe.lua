local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"))
local trace = assert(io.open(root .. "/cpu-eret.tsv", "w"))
trace:write("kind\titerations\teffects\tticks\tstatus\n")
local done = false
for _ = 1, 180 do
  emu.frameadvance()
  if memory.read_u32_be(0x1000, "RDRAM") == 0x4a464745 then
    for row = 0, 3 do
      for column = 0, 4 do
        if column ~= 0 then trace:write("\t") end
        trace:write(memory.read_u32_be(0x1100 + row * 20 + column * 4, "RDRAM"))
      end
      trace:write("\n")
    end
    trace:write("result\ttrue\t4\n")
    done = true
    break
  end
end
trace:close()
client.exitCode(done and 0 or 3)
