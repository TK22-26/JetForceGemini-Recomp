local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"))
local trace = assert(io.open(root .. "/cpu-clock.tsv", "w"))
trace:write("case\tticks\n")
local names = {"alu100", "alu1000", "cached100", "cached1000", "uncached100", "uncached1000"}
local done = false
for _ = 1, 180 do
  emu.frameadvance()
  if memory.read_u32_be(0x1018, "RDRAM") == 0x4a46474b then
    for index, name in ipairs(names) do
      trace:write(name, "\t", tostring(memory.read_u32_be(0x1000 + (index - 1) * 4, "RDRAM")), "\n")
    end
    trace:write("result\ttrue\n")
    done = true
    break
  end
end
trace:close()
client.exitCode(done and 0 or 3)
