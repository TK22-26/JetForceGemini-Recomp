# CPU-visible framebuffer writeback experiment (2026-09-26)

Status: opt-in runtime repair, repeated route and focused branch proof.
**Not the update-1292 timing fix.** Matching actor/state prefix remains 1291.

## Cause and repair

Instruction observation exposed a different path through `mainUpdateZBCheck`
at `0x80045914`: native executed 553 instructions while the uninterrupted
reference took 278 Count ticks. The first depth-test record at `0x800fd750`
ended in `01` natively and `00` in the reference. Both used depth buffer
`0x8015af40`; the routine searches a 7-by-7 area for cleared depth pixels.

RT64 rendered into its private RAM, but the native bridge did not transfer
completed framebuffer results back to live guest RAM. Earlier rendered-window
controls checked actor hashes, not this CPU-visible buffer, and therefore
did not exclude this defect.

`JFG_PHASE9_RENDERER_WRITEBACK_PROBE=1` enables an independently authored
bridge using RT64's public framebuffer ownership/timestamp information:

- Complete synchronous rendering, then identify framebuffer ranges written
  by that task and commit those ranges before delivering SP/DP notifications.
- Validate every owned CPU byte against the submitted snapshot before any
  commit. A conflicting CPU write rejects the whole operation, including
  when the GPU wrote the same value as the submitted snapshot.
- Preserve memory outside owned ranges, handle logical byte addresses in
  word-swapped RAM, and support the 4 MiB guest with RT64's 8 MiB backing.
- Disable fast replay render skipping while enabled. Skipping rendering
  cannot preserve CPU-visible framebuffer results.

The flag remains off by default. This is conservative whole-framebuffer
ownership, not a complete asynchronous bus or cache-coherence model. Multiple
queued snapshots and overlapping CPU/GPU ownership need further coverage.
RT64's render-to-RAM path supplies pixels; host rendering duration is not
used as guest device time. SP/DP timing remains independently unresolved.

## Evidence

Private artifacts (no ROM contents distributed):

- `renderer-writeback-native-20260926a`: rejected invalid span size; the
  initial helper incorrectly required live guest RAM to be 8 MiB. Preserved
  as a failed run, not reclassified.
- `renderer-writeback-native-20260926b` and `...c`: both exit zero, 3000
  retraces, 1413 completed updates and 1423 controller polls. No ownership
  conflicts. Identical final state hash
  `f7d29223aa0a51779cf6b8387621f86aa41ca5362627b2e37da311bde5391be7`.
- Native executable SHA-256:
  `ff9245215f169ef694ec8f3f9b7e6367372bc577ae7ace1a47436c230fc01cf8`.
- The repaired depth check executes **139 instructions**, agreeing exactly
  with 278 reference Count ticks on all six captured calls. Reference:
  `execution-zbuffer-oracle-20260926a`.
- Actor/update hash stream is unchanged by this repair:
  `edd1bcca844f8fd2708650d922f829beab673ceffef9911a5275b0edbe0cca8e`.
  The repeat's `prefix-comparison.json` still first differs at update 1292.
- Renderer ownership tests plus clock, timer and scheduler CTests pass.

## Execution observation

`scripts/phase9_execution_probe_root.py` regenerates a private diagnostic
root using N64Recomp instruction hooks: 378,954 sites, covering generated
functions and overlays. `execution-root-20260926c/root` is the current
diagnostic build root. Comparison against the control root verifies all
2935 body/thunk sources differ only by observer calls and indentation.
The callback counts work; it does not modify guest Count or service devices.

Independent paired observations also show:

- Texture-scroll routine `0x80013970`: 16,484 instructions versus 32,968
  uninterrupted reference ticks. One VI-interrupted invocation takes 3206
  additional ticks; this is not a proposed interrupt-cost constant.
- CPU-effects routine `0x80045a44`: 264 instructions versus 528 ticks.
- After writeback, graphics-receive return to pacing entry contains 112,641
  native instructions. Reference wall intervals still include interrupts;
  subtracting their aggregate duration requires direct paired evidence.

The comparison utility explicitly labels interrupted observations and
refuses shifted update/poll pairing. The two-tick profile is a reference
hypothesis, not hardware qualification. Game clock integration still needs
OS execution accounting and independent device deadlines; these diagnostic
counts must not be substituted for those missing components.

### Interrupted-work reconciliation

The subsequent `execution-interrupt-oracle-20260926a` capture pairs each
interruption with resumption at its EPC in the same guest thread and with
the same SP, after EXL clears. An eret alone is insufficient: it may run a
different thread. All callbacks are bounded and removed at shutdown.
The run exits zero and preserves the existing oracle update trace digest.

`compare_phase9_execution_work.py --graphics-to-pacing` compares these
observations with `renderer-writeback-native-20260926c`. For all six
same-index intervals, reference wall time minus the union of measured
interrupt-to-resumption intervals equals **225282 ticks**, exactly twice
112641 native instructions. Four intervals contain a 666-tick interruption;
the frontier interval contains 666 and 3206 ticks; one contains none.
No residual remains in this bounded generated-work interval. These are
measured intervals, not constants to install in the runtime. The parser
rejects missing/ambiguous pairs and never double-counts nested intervals.
