# Phase 4 save-device runtime boundary

- Status: native model and isolated oracle execution implemented; the required
  G2 records were subsequently bound into the signed Phase 4/G2 aggregate.
- Data boundary: tests use synthetic bytes. Emulator-backed save bodies and
  unrestricted logs remain local and ignored.
- Distribution boundary: this work implements project-owned behavior and does
  not copy a proprietary Controller Pak filesystem or game save body.

Later references to pending aggregate publication are historical notes; the
dashboard and signed evidence carry current gate status.

## Implemented surface

`ControllerAccessoryBus` models four isolated controller ports. A Controller
Pak session is opaque and bound to both the bus identity and the current port
generation. Disconnects and accessory changes invalidate earlier sessions.
Controller Pak contents remain non-volatile across a temporary switch to a
Rumble Pak or no accessory. The logical note store supports bounded creation,
deletion, deterministic enumeration, reads, writes, capacity accounting, and
atomic process-style persistence.

The Controller Pak snapshot is deliberately a project-owned logical container,
not a raw `.mpk` image. A later libultra ABI bridge may translate game-facing
file operations into this model without publishing or depending on a
proprietary filesystem body.

`FlashRamStore` models the high-level 128 KiB FlashRAM surface used by the
pinned host references:

- exact 128-byte staged page writes;
- full-page replacement on program completion;
- page and whole-device erase;
- stable reads while an operation is pending;
- reusable staged data across completion or interruption;
- explicit busy, bounds, and empty-buffer failures;
- raw fixed-size 128 KiB persistence compatible with conventional emulator
  save images; and
- transactional reload rejection for missing, non-regular, truncated, or
  oversized images.

Device completion and host durability are separate. Once a FlashRAM command is
completed, its in-memory result remains committed even if the atomic host-file
write fails. The caller receives the I/O failure and can retry with
`persist_atomic`; the device is not left in an ambiguous busy state.

## Executable coverage

The ROM-free native suite covers:

| Area | Required behavior |
| --- | --- |
| Accessory detection | no device, wrong accessory, invalid port, invalid kind |
| Session integrity | cross-bus rejection, disconnect/reconnect invalidation |
| Port isolation | independent contents for all modeled ports |
| Rumble | accessory-only activation and reset on transition |
| Controller Pak | logical lifecycle and process-style durable round trip |
| FlashRAM commands | stage, program, erase page/all, interrupt, busy and bounds |
| FlashRAM persistence | raw-image round trip, failed-write retry, malformed rejection |
| Toolchains | GCC, MSVC, clang-cl, plus Address/UndefinedBehavior sanitizers |

An isolated local emulator oracle has also confirmed durable reload and cleanup
for both FlashRAM and Controller Pak domains. Its runner, configuration, raw
save bodies, hashes, and logs remain ignored. The public G2 record will expose
only validated aggregate counts and digests after every other G2 requirement is
closed.

## Remaining integration boundary

This is a device model, not yet the generated game's libultra ABI bridge. G2
closure still requires the final private evidence bundle to bind the native and
oracle executions. A later runtime integration must route the relevant
`osFlash*`, `osPfs*`, accessory probe, and rumble calls into these models and
verify the game's real call sequences without checking save bodies into Git.
