-- Bounded, read-only capture of the verified Japanese BizHawk movie.
-- All RAM words below are *unverified JP probes*, not semantic game fields.
local root = assert(os.getenv("JFG_TAS_CAPTURE_ROOT"))
local first = assert(tonumber(os.getenv("JFG_TAS_CAPTURE_FIRST")))
local last = assert(tonumber(os.getenv("JFG_TAS_CAPTURE_LAST")))
local previous = tonumber(os.getenv("JFG_TAS_CAPTURE_PREVIOUS") or "-1")
local resume_state = os.getenv("JFG_TAS_CAPTURE_RESUME_STATE")
local interval = assert(tonumber(os.getenv("JFG_TAS_CAPTURE_INTERVAL")))
local expected_length = assert(tonumber(os.getenv("JFG_TAS_CAPTURE_MOVIE_LENGTH")))
local full_rdram = os.getenv("JFG_TAS_CAPTURE_FULL_RDRAM") == "1"
assert(first >= 0 and first <= last and last < expected_length)
assert(last - first <= 20000 and interval >= 1 and interval <= 20000)
assert(movie.isloaded() and movie.mode() == "PLAY", "movie not playing")
assert(movie.length() == expected_length, "movie length mismatch")
assert(movie.getreadonly(), "movie must be read-only")
local header = movie.getheader()
assert(string.lower(header.SHA1 or "") ==
  "15099233760b36e7afad7da36b9464da1512c4b1", "movie ROM mismatch")

emu.limitframerate(false)
client.frameskip(8)
client.speedmode(400)
local polls = 0
event.oninputpoll(function() polls = polls + 1 end, "phase95-tas-polls")

if resume_state then
  assert(first == previous + 1 and previous >= 0, "invalid resume interval")
  assert(savestate.load(resume_state, true), "could not load prior state")
  assert(emu.framecount() == previous, "resume state frame mismatch")
  assert(movie.mode() == "PLAY", "movie stopped after state load")
  emu.frameadvance()
else
  assert(first == 0 and emu.framecount() == 0,
    "fresh capture must start at movie frame zero")
end

local output = assert(io.open(root .. "/frames.tsv", "w"))
output:setvbuf("no")
output:write("schema\t1\nprobe_status\tunverified-jp\n")
output:write("frame\tmovie_mode\tinput_polls_since_worker_start\t",
  "raw_0xA51B0_u8\traw_0xFB114_u32be\t",
  "raw_0xA33E4_u32be\traw_0x1BD150_u32be\n")

local function capture_checkpoint(frame)
  local stem = root .. string.format("/checkpoint-%06d", frame)
  if full_rdram then
    local all = assert(io.open(stem .. ".rdram", "wb"))
    for address = 0, 0x3F0000, 0x10000 do
      all:write(memory.read_bytes_as_binary_string(address, 0x10000, "RDRAM"))
    end
    all:close()
  end
  client.screenshot(stem .. ".png")
end

while true do
  local frame = emu.framecount()
  assert(frame <= last, "capture passed requested end")
  local mode = movie.mode()
  assert(mode == "PLAY" or (frame == expected_length - 1 and
    mode == "FINISHED"), "movie left playback unexpectedly")
  output:write(frame, "\t", mode, "\t", polls, "\t",
    string.format("%02X", memory.read_u8(0xA51B0, "RDRAM")), "\t",
    string.format("%08X", memory.read_u32_be(0xFB114, "RDRAM")), "\t",
    string.format("%08X", memory.read_u32_be(0xA33E4, "RDRAM")), "\t",
    string.format("%08X", memory.read_u32_be(0x1BD150, "RDRAM")), "\n")
  if frame == first or frame == last or frame % interval == 0 then
    capture_checkpoint(frame)
  end
  if frame == last then break end
  emu.frameadvance()
end
output:close()
local state_path = root .. "/continuation.State"
savestate.save(state_path, true)
local saved = assert(io.open(state_path, "rb"), "continuation file missing")
assert(saved:seek("end") > 0, "continuation file empty")
saved:close()
local done = assert(io.open(root .. "/done.tsv", "w"))
done:write("schema\t1\nfirst\t", first, "\nlast\t", last,
  "\nmovie_length\t", expected_length, "\n")
done:close()
event.unregisterbyname("phase95-tas-polls")
client.exitCode(0)
client.exit()
