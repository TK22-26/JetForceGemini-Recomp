local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"))
local trace = assert(io.open(root .. "/cpu-ai.tsv", "w"))
local done = false
for _ = 1, 300 do
  emu.frameadvance()
  if memory.read_u32_be(0x1000, "RDRAM") == 0x4a464741 then
    local columns = memory.read_u32_be(0x1004, "RDRAM")
    if columns == 0 then columns = 10 end
    assert(columns == 10 or columns == 12 or columns == 16)
    trace:write("rate\tlength\tphase\tlaunch\tinitial_length\tinitial_status\tlast_pending\tfirst_complete\tfinal_length\tfinal_status")
    if columns >= 12 then trace:write("\thalf_count\thalf_length") end
    if columns == 16 then trace:write("\tsecond_pending\tsecond_complete\tsecond_length\tsecond_status") end
    trace:write("\n")
    for row = 0, 71 do
      for column = 0, columns - 1 do
        if column ~= 0 then trace:write("\t") end
        trace:write(memory.read_u32_be(0x1100 + row * columns * 4 + column * 4, "RDRAM"))
      end
      trace:write("\n")
    end
    done = true
    break
  end
end
trace:write("result\t", tostring(done), "\t72\n")
trace:close()
client.exitCode(done and 0 or 3)
