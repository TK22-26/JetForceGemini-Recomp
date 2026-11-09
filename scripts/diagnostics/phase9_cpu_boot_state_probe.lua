-- Read-only IPL-to-game hardware state. No game save, input, or RAM injection.
local root = assert(os.getenv("JFG_CPU_MICRO_ROOT"))
local trace = assert(io.open(root .. "/cpu-boot_state.tsv", "w"))
trace:write("event\tcount\tstatus\tcause\tcompare\tfcr31\tmi_pending\tmi_mask\tv_sync\th_sync\n")
local hits = {}
local epc = assert(io.open(root .. "/boot-epc.tsv", "w"))
epc:write("event\tcount\tepc\n")
local function capture(label)
  hits[label] = (hits[label] or 0) + 1
  if hits[label] > (label == "interrupt" and 64 or 1) then return end
  local r = emu.getregisters()
  epc:write(string.format("%s\t%08x\t%08x\n", label, r["CP0 REG9"] & 0xffffffff,
    r["CP0 REG14"] & 0xffffffff))
  trace:write(label)
  for _, key in ipairs({"CP0 REG9", "CP0 REG12", "CP0 REG13", "CP0 REG11", "FCR31"}) do
    trace:write(string.format("\t%08x", assert(r[key], key) & 0xffffffff))
  end
  for _, address in ipairs({0xa4300008, 0xa430000c, 0xa4400018, 0xa440001c}) do
    trace:write(string.format("\t%08x", memory.read_u32_be(address, "System Bus")))
  end
  trace:write("\n")
  trace:flush()
end
local sites = {
  {"entry", 0x80000400}, {"handoff", 0x8003f500},
  {"os-init", 0x80097520}, {"vi-init", 0x8009ab80},
  {"vi-init-return", 0x80098b74}, {"interrupt", 0x80075030},
}
for _, site in ipairs(sites) do
  event.onmemoryexecute(function() capture(site[1]) end, site[2], "boot-state-" .. site[1], "System Bus")
end
for _ = 1, 120 do emu.frameadvance() end
for _, site in ipairs(sites) do event.unregisterbyname("boot-state-" .. site[1]) end
local done = hits.entry == 1 and hits.handoff == 1 and hits["os-init"] == 1 and hits["vi-init-return"] == 1
trace:write("result\t", tostring(done), "\t120\n")
trace:close()
epc:close()
client.exitCode(done and 0 or 3)
