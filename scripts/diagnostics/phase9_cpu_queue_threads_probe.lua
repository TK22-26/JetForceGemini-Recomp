local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"))
local trace = assert(io.open(root .. "/cpu-queue_threads.tsv", "w"))
local exceptions = 0
event.onmemoryexecute(function()
  if memory.read_u32_be(0x301580, "RDRAM") ~= 0 then
    exceptions = exceptions + 1
  end
end, 0x80000180, "queue-threads-exceptions", "System Bus")
local names = {"send_lower", "send_higher", "recv_wake_sender", "recv_final",
  "worker_recv_first", "worker_recv_second", "worker_fill", "worker_block_send"}
trace:write("case\tticks\tresult\tvalid\tstatus\n")
local done = false
for _ = 1, 180 do
  emu.frameadvance()
  if memory.read_u32_be(0x301588, "RDRAM") == 0x4a464754 then
    for index, name in ipairs(names) do
      local base = 0x301400 + (index - 1) * 16
      trace:write(name, "\t", memory.read_u32_be(base, "RDRAM"), "\t",
        string.format("0x%08x", memory.read_u32_be(base + 4, "RDRAM")), "\t",
        memory.read_u32_be(base + 8, "RDRAM"), "\t",
        string.format("0x%08x", memory.read_u32_be(base + 12, "RDRAM")), "\n")
    end
    trace:write("payloads")
    for index = 0, 3 do
      trace:write("\t", memory.read_u32_be(0x301500 + index * 4, "RDRAM"))
    end
    trace:write("\nentry-status\t", string.format("0x%08x", memory.read_u32_be(0x301590, "RDRAM")),
      "\t", string.format("0x%08x", memory.read_u32_be(0x301594, "RDRAM")), "\n")
    trace:write("mi-masks")
    for index = 0, 4 do
      trace:write("\t", string.format("0x%08x", memory.read_u32_be(0x301598 + index * 4, "RDRAM")))
    end
    trace:write("\n")
    trace:write("result\ttrue\t", exceptions, "\t",
      memory.read_u32_be(0x301584, "RDRAM"), "\t",
      string.format("0x%08x", memory.read_u32_be(0x301580, "RDRAM")), "\t",
      string.format("0x%08x", memory.read_u32_be(0x30158c, "RDRAM")), "\n")
    done = true
    break
  end
end
trace:close()
event.unregisterbyname("queue-threads-exceptions")
client.exitCode(done and 0 or 3)
