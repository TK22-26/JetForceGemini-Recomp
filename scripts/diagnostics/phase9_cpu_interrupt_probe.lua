local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"))
local trace = assert(io.open(root .. "/cpu-interrupt.tsv", "w"))
local exceptions = assert(io.open(root .. "/exceptions.tsv", "w"))
local vector = assert(io.open(root .. "/vector.tsv", "w"))
local initialization = assert(io.open(root .. "/initialization.tsv", "w"))
local function record_initialization(label)
  local r = emu.getregisters()
  initialization:write(label)
  for _, key in ipairs({"CP0 REG9", "CP0 REG12", "CP0 REG13", "FCR31"}) do
    initialization:write("\t", key, "=", string.format("%08x", assert(r[key], key) & 0xffffffff))
  end
  for _, address in ipairs({0xa4600014,0xa4600018,0xa460001c,0xa4600020,
      0xa4600024,0xa4600028,0xa460002c,0xa4600030,0xa4800018,0xbfc007fc,
      0xa4500008,0xa4500010,0xa4500014,0xa430000c}) do
    initialization:write(string.format("\t%08x=%08x", address, memory.read_u32_be(address, "System Bus")))
  end
  initialization:write("\n")
  initialization:flush()
end
event.onmemoryexecute(function() record_initialization("entry") end, 0x80097520, "init-entry", "System Bus")
event.onmemoryexecute(function() record_initialization("return") end, 0x80000410, "init-return", "System Bus")
exceptions:write("cause\tepc\tcount\n")
event.onmemoryexecute(function()
  local r = emu.getregisters()
  exceptions:write(string.format("%08x\t%08x\t%08x\n",
    assert(r["CP0 REG13"]) & 0xffffffff, assert(r["CP0 REG14"]) & 0xffffffff,
    assert(r["CP0 REG9"]) & 0xffffffff))
end, 0x80075030, "interrupt-micro-entry", "System Bus")
trace:write("case\tticks\thi\tlo\tf0\tfcr31\tworker\tpayload\n")
local done = false
for _ = 1, 180 do
  emu.frameadvance()
  if memory.read_u32_be(0x301780, "RDRAM") == 0x4a464749 then
    vector:write("general-exception-vector")
    for i = 0, 3 do vector:write(string.format("\t%08x", memory.read_u32_be(0x180 + 4 * i, "RDRAM"))) end
    vector:write("\n")
    for row = 0, 7 do
      for column = 0, 7 do
        if column ~= 0 then trace:write("\t") end
        trace:write(memory.read_u32_be(0x301400 + row * 32 + column * 4, "RDRAM"))
      end
      trace:write("\n")
    end
    trace:write("result\ttrue\t8\n")
    done = true
    break
  end
end
event.unregisterbyname("interrupt-micro-entry")
trace:close()
exceptions:close()
vector:close()
initialization:close()
event.unregisterbyname("init-entry")
event.unregisterbyname("init-return")
client.exitCode(done and 0 or 3)
