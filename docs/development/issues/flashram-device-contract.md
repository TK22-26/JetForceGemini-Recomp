# FlashRAM sector and command semantics

- ID: FLASH-CONTRACT-20261101.
- Status: shared-device candidate passes synthetic regressions, final all-three original-OS new-slot/reload probes and enhanced reload checks; broader owner persistence acceptance pending.
- Severity: moderate persistence correctness; gameplay impact has not been measured.
- Affected: current cooperative HLE FlashRAM boundary and original-OS reference Flash bus; all prospective regional native targets share these services.
- Release: no fix published or owner save retest recorded.

## Observed mismatch

The existing `osFlashSectorErase` HLE handler calls `FlashRamStore::begin_erase_page`,
which erases 128 bytes. The game and SDK describe a containing sector of 128 pages
(16 KiB). This is the previously cataloged [JFG-UP-020](../../upstream/reference-catalog.json)
limitation, now tracked with the regional architecture work. The page primitive's
own tests verify its documented extent; they never establish sector semantics.

The original-OS `ReferenceFlashBus` is explicitly a corrected-Mupen reference
profile. It likewise erases one page. It also retains the program source address
until status command `0xd2` and commits an erase at that command. The pinned SDK
uses `0x4b` to select a sector, `0x78` to execute erasure, `0xb4` to load the page
buffer, `0xa5` to program it, and `0xd2` to select status. The reference bus has no
chip-erase setup command and replaces programmed bytes rather than modeling the
one-to-zero bit constraint. These are differences in the model's contract, not
newly observed hardware defects or proof of a particular lost save.

## Evidence and required validation

The pinned local SDK `libultra/src/flash/flashsectorerase.c` and
`include/PR/os_internal_flash.h` establish the caller's operation order. The
[reviewed game save definitions](https://github.com/Ryan-Myers/Jet-Force-Gemini/blob/948e1f5acaa02d2df359ce647ca1f439036975d1/src/saves.h#L28)
describe sector grouping. The already pinned
[Ares cartridge model](https://github.com/HailToDodongo/ares-64/blob/b4ead632f6a983d2e86546a6bba2b7a5c2ccb6c0/ares/n64/cartridge/flash.cpp)
separately implements containing-sector erasure, a latched page buffer,
bitwise programming, command-time operation start and chip-specific busy time.
This is reference-source evidence, not a native-console measurement.

Private `regional-architecture-20261101/pinned-flash-contract-reference/provenance.json`
records the exact retrieved source hashes. Existing command/DMA comparison
receipts remain valid only for their historical reference profile and cannot
qualify a different physical-device implementation.

Required regressions fill three distinct adjacent sectors, erase a page inside
the middle sector and compare every byte plus both neighbors. Also cover the
first/last sector, pending interruption, failed persistence, command order,
program-buffer ownership, repeated programming without erasure, chip erasure,
busy deadlines and status acknowledgement. Live acceptance still needs valid
game slots/checksums and save/reload for each exact ROM revision on private data.

## Implementation direction and lesson

Keep a page primitive distinct from a containing-sector operation. The shared
store must retain transactional persistence; one production command owner must
serve all revisions with an explicit cartridge model and clock input. Historical
reference behavior can remain an evidence profile, but it must not silently
define the product's cartridge behavior. No personal save is modified by this
source review. A successful device persistence test is not a game-save or
physical-device acceptance test.

## Candidate implementation and tests

The shared store now exposes a containing-sector operation separately from its
128-byte page primitive. Normal programming clears bits; the old replacement
operation is explicitly restricted to the historical reference profile. The
cooperative SDK adapter calls the sector operation and reports the same
MX29L1100 identity and ready status as the production command device.

[FlashDevice](../../../include/jfg/boot/flash_device.hpp) owns the selected
MX29L1100 protocol for every revision. It latches the 128-byte source at DMA,
starts programming at `0xa5` and erasure at `0x78`, supports containing-sector
and whole-chip erase, and completes through an explicit Count deadline.
`0xd2` only selects status; it cannot commit a second write. Native idle and
fast-execution deadlines include pending FlashRAM completion. The existing
transactional store and host persistence retry remain the byte/durability owner.

The pinned reference's 3.5 ms program and 85 ms erase durations are converted
from the supplied Count frequency. This is a named reference-derived chip
model, not a measured cartridge identity or native-N64 timing claim. Reset
discards an uncompleted transaction deterministically; physical power-loss
outcomes are not inferred. The supported interface is the SDK's word command
aperture and page DMA, not arbitrary halfword/open-bus probing.

Private step `128-qualify-flash-command-contract` passed the store suite, the
new command-device suite and the unchanged historical command/DMA suite.
Checks include first/middle/last sector boundaries with all neighboring bytes,
pending interruption, failed durable writes, source changes after DMA,
reprogramming without erasure, chip erasure, status selection, exact before/at
deadline behavior and malformed transfers without RAM writes. Personal save
files were not used. Native compilation and valid in-game slots/checksums,
save/reload and restart remain required separately for US, PAL and JP.

The private US v5 native build and 200-retrace original-OS cold-boot probe
passed with this device integrated. No in-game save/reload was exercised by
that probe; valid slots, checksums and persistence acceptance remain open
for each revision.

The expanded Windows contract run found an MSVC warnings-as-errors failure in
the new synthetic sector-erase fixture: `std::fill_n` deduced an unsigned-int
fill value for byte storage. The fixture now supplies an explicit `uint8_t`;
the runtime erase implementation and expectations are unchanged. The failed
build is preserved as `regional-contracts-v11-native-build.log`; the corrected
Windows suite is rerun separately before the next native source snapshot.

## Four-hour regional continuation checkpoint

The full 110-test Windows host run passes with the typed byte fixture. Frozen
v16 native candidates for US, PAL and JP boot with the shared device, create a
new populated 131,072-byte private save, and reload it into the Goldwood opening
walkway in a separate process. The final frames were inspected for all three;
see [the regional evidence table](regional-rom-support.md#current-four-hour-continuation).
These checks establish valid in-game slot creation and same-region reload on
those exact builds. They do not exercise every campaign save transition, power
loss or physical cartridge timing. The subsequent enhanced source requires its
own native checks and the owner will perform broader persistence playtests.

## Enhanced regional continuation

All three v27 enhanced native candidates reload those same-revision private
v16 saves into Goldwood during bounded Play. This adds enhanced-runtime reload
evidence without relabeling the earlier new-slot tests as current. The final
source/product checkpoint is in the regional issue. Broader campaign saves,
interrupted persistence and owner acceptance remain open.

## Final five-hour continuation checkpoint

Final v28 binaries now independently create fresh populated 131,072-byte
private saves during 6,000-VI original-OS probes for US, PAL and JP. Separate
8,000-VI processes load each same-region save into Goldwood with unchanged
save hashes and zero unsupported accesses. New-slot ship frames and reload
walkway frames were inspected for all three. Current enhanced Play also
reloads the earlier v16 test saves; those input provenances remain separate.

Implementation commit: `5bac0c896c3e4a47456b2973994bbe7151062e77`. Private
receipt: `regional-architecture-20261101-owner5h/regional-save-v28-qualified.result.json`.
Actual launcher Play confirms other-region saves remain unchanged. This is
bounded game-save evidence on final binaries, not all-character campaign,
enhanced new-slot feature, power-loss or physical-device acceptance.

## Additional normal-Play qualification

The `regional-automation-20261101-owner4h` continuation independently creates
fresh private slots through normal enhanced Play on all three final v28
binaries, then reloads each in a separate 180-second process. All three game
checksums validate, the reloads retain the original save hashes, and inspected
frames show Juno in Goldwood. All six processes close normally with zero
unsupported accesses.

Twelve subsequent file-select cases verify full-size checksum behavior:
payload/checksum corruption shows a new slot, while untouched slots and changed
unused padding retain the existing slot. Every fixture stays byte-for-byte
unchanged and all final menu frames were inspected, including JP labels.
Evidence: `checksum-menus.qualified.json` in the same private root.

Controlled host-write failure now also passes on all three: a read lease
prevents atomic replacement, the original erased fixture stays unchanged, and
an explicit `flash-persist` trap stops execution. After releasing the lease,
a separate process writes a checksum-valid slot at that exact same destination,
without copying or resetting its contents. Failed-byte snapshots are preserved,
no temporary files remain, and all successful retries close normally with zero
unsupported accesses or audio underruns/overruns. Evidence:
`same-path-save-recovery.qualified.json`. Earlier copied-fixture retry results
remain separately scoped. Changed Modern pause/Save outputs also reload with
unchanged save hashes and visible ammunition 97/96/97; one JP reload audio
underrun is retained in the regional record. Campaign durability, actual
power loss and hardware timing are not inferred from these passes.
