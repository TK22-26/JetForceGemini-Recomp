local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"))
local out = assert(io.open(root .. "/cpu-si_overlap.tsv", "w"))
out:write("case\tfirst\tsecond\tlast_pending\tfirst_complete\tlate_mi\tlate_si\n")
local done = false
for _ = 1, 180 do
  emu.frameadvance()
  if memory.read_u32_be(0x1000, "RDRAM") == 0x4a46474f then
    for row = 0, 31 do
      for col = 0, 6 do
        if col ~= 0 then out:write("\t") end
        out:write(memory.read_u32_be(0x1100 + row * 28 + col * 4, "RDRAM"))
      end
      out:write("\n")
    end
    out:write("result\ttrue\t32\n")
    done = true
    break
  end
end
out:close()
client.exitCode(done and 0 or 3)
