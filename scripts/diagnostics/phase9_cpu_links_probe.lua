local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"))
local trace = assert(io.open(root .. "/cpu-links.tsv", "w"))
trace:write("case\tpc\tslot_hi\tslot_lo\tlink_hi\tlink_lo\ttaken\n")
local done = false
for _ = 1, 180 do
  emu.frameadvance()
  if memory.read_u32_be(0x1000, "RDRAM") == 0x4a46474c then
    for row = 0, 11 do
      for column = 0, 6 do
        if column ~= 0 then trace:write("\t") end
        trace:write(string.format("%08x", memory.read_u32_be(0x1100 + row * 32 + column * 4, "RDRAM")))
      end
      assert(memory.read_u32_be(0x111c + row * 32, "RDRAM") == 0)
      trace:write("\n")
    end
    trace:write("result\ttrue\t12\n")
    done = true
    break
  end
end
trace:close()
client.exitCode(done and 0 or 3)
