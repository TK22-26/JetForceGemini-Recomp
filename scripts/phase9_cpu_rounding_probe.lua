-- Isolated, diagnostic-only CPU semantics probe for the private test ROM.
local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"), "missing microtest output")
local trace = assert(io.open(root .. "/cpu-rounding.tsv", "w"))
trace:setvbuf("no")
trace:write("status\tframe\toperand_bits\tconverted_word\tfcr31\tmarker\n")
local done = false
for _ = 1, 180 do
  emu.frameadvance()
  local marker = memory.read_u32_be(0x100c, "RDRAM") & 0xffffffff
  if marker == 0x4a464743 then
    trace:write("complete\t", tostring(emu.framecount()), "\t",
      string.format("0x%08x", memory.read_u32_be(0x1000, "RDRAM") & 0xffffffff),
      "\t", string.format("0x%08x", memory.read_u32_be(0x1004, "RDRAM") & 0xffffffff),
      "\t", string.format("0x%08x", memory.read_u32_be(0x1008, "RDRAM") & 0xffffffff),
      "\t", string.format("0x%08x", marker), "\n")
    done = true
    break
  end
end
if not done then trace:write("not_reached\t", tostring(emu.framecount()), "\n") end
trace:close()
client.exitCode(done and 0 or 3)
