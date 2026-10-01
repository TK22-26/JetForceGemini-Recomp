local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"))
local trace = assert(io.open(root .. "/cpu-queue.tsv", "w"))
trace:write("case\tticks\tresult\tvalid\n")
local names = {"leaf", "empty_recv", "send", "recv_output", "refill", "full_send", "recv_discard"}
local done = false
for _ = 1, 180 do
  emu.frameadvance()
  if memory.read_u32_be(0x1054, "RDRAM") == 0x4a464751 then
    for index, name in ipairs(names) do
      local base = 0x1000 + (index - 1) * 12
      trace:write(name, "\t", memory.read_u32_be(base, "RDRAM"), "\t",
        string.format("0x%08x", memory.read_u32_be(base + 4, "RDRAM")), "\t",
        memory.read_u32_be(base + 8, "RDRAM"), "\n")
    end
    trace:write("result\ttrue\t", memory.read_u32_be(0x1058, "RDRAM"), "\n")
    done = true
    break
  end
end
trace:close()
client.exitCode(done and 0 or 3)
