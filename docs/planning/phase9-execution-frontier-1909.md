# Phase 9: strict prefix advances to update 1908

## Result (2026-09-26)

The opt-in original-OS path passes the requested 1291 boundary. Extending the
reference now proves **1908 consecutive matching completed-update states**.
The first selected-state mismatch is update **1909**: camera and 18 actor
records differ. Two independent native/oracle capture pairs reproduce it.
No native runtime code was changed to obtain this extension; the executable
is the one that passed the [1300 prefix](phase9-execution-frontier-1300.md).

This is a selected-state prefix, not equality of all RDRAM or complete runtime
state. In particular, the observed consumed-VI counters first differ at 1908,
one update before the selected actor/camera hashes differ. Corrected-Mupen
compatibility remains the reference profile, not physical-N64 timing truth.

## Reproduced boundary

| Completed update | Native consumed VI | Oracle consumed VI | Polls (both) | Native/oracle elapsed-VI word |
| --- | ---: | ---: | ---: | --- |
| 1907 | 4589 | 4589 | 1917 | 3 / 3 |
| 1908 | 4592 | 4593 | 1918 | 3 / 4 |
| 1909 | 4595 | 4596 | 1919 | 3 / 3 |
| 1910 | 4598 | 4599 | 1920 | 3 / 3 |

The elapsed-VI word is `0x800a3374`; the pacing-mode byte at `0x800fecac`
remains 3 on both sides throughout this window. Canonical focused RDRAM
confirms no differences in the compared actor ranges at 1908, followed by
18 differing actor ranges at 1909. The selected input between those two
updates is the same neutral poll. All **2290** shared delivered input polls
in the longer capture agree with the selected route and each other.

The timing difference precedes the actor/camera difference. That is a
concrete upstream lead, not yet proof of which CPU/device operation causes
it or a complete explanation of every differing byte. Do not insert a VI,
force the elapsed word, alter the recorded input or shift the comparison.

## Private evidence

All directories below are under `tools/private/`:

- `execution-prefix-native-20260926a`: normal target completion at 6000
  consumed VI; 2287 completed updates, 2299 controller polls, about 91 seconds.
  `comparison-1908.json` passes; `comparison-2278.json` first differs at 1909.
- `execution-prefix-oracle-20260926a`: normal completion at emulator frame
  6000, 5970 consumed VI, 2278 completed updates.
- `execution-prefix-focus-native-20260926a`: normal completion at 4800 VI,
  1973 updates, about 71 seconds; captures updates 1907-1910. Its complete
  update-record sequence equals the first 1973 records of the longer run.
- `execution-prefix-focus-oracle-20260926a`: normal completion at emulator
  frame 4800, 1962 updates; the complete update-record sequence equals the
  first 1962 records of the longer reference run.
- Focus-native `comparison-1908.json`, `comparison-1909.json` and
  `focus-comparison.json` preserve the repeated pass/failure boundary.

Pins:

- Native executable: `6edd2c402141dce44a2a0d4f81f4bdf66e9eedefcf0f10d36133c5b726106397`.
- Native EXE/DLL runtime: `d45c88d2d798f20c9b7d071895e148805ae9d6d3bdcce48960e03de345a1ffd9`.
- Longer native update trace: `5c0b4169c38b727e1bf2178701ed2c06f62c1832b05904205522323aa16b936c`.
- Longer oracle update trace: `08471f7456fba39103ac0036e8599b1f23b502e7549a20ff3ed7a47329dd0e47`.
- Focused native update trace: `45ee833c282ef24bd4e07f8377e0528a73aed58148b5f6d1059ea7edcac88f86`.
- Focused oracle update trace: `daf32c850bb38e9b9306298c4a057c4457854a3ae1e95fc75ba77c7eaf90ecb8`.
- Focus comparison: `88e77ddb0e4b3dcfd97a20571c52806981727e8e6ef9cefdcea27f55cb71d4ce`.

The generated root, input export, initial saves, US ROM and corrected oracle
remain those pinned by the 1300 evidence. The longer run consumed 2299 of
10881 route polls; it is not route completion.

## Automation change and verification

`scripts.phase95_native_replay` now accepts explicit
`--execution-profile original-os-probe` or `--execution-profile cooperative`.
Named profiles discard inherited `JFG_PHASE*` variables, then construct only
their declared execution flags and requested capture settings in the child
environment. They do not mutate the supervisor's process environment.
The objective/result records the profile and an EXE/DLL runtime digest.
Omitting the option preserves the older interface and is labeled
`legacy-environment`; it is not a pinned unattended execution setting.

The original-OS path rejects unqualified poll-stop mode and VI targets below
4 before launching. The focused native run intentionally inherited conflicting
`GUEST_OS_PROBE=0` and `SI_COUNT_PROBE=1` flags; its explicit profile correctly
selected original OS execution, disabled the legacy SI probe and reproduced
the longer native trace. Both default and opt-in executable paths are otherwise
unchanged. This does not promote the opt-in runtime to product acceptance.

49 Python tests pass across replay profiles, native/oracle replay contracts,
failure trace preservation, poll comparison, focused RDRAM comparison and
the existing update-job scheduler. `git diff --check` passes.

## Next work

The subsequent [pacing receive observation](phase9-pacing-receive-observation.md)
now measures the producer's actual call/return path. At invocation 1908 its
queue already holds 2 native / 3 reference messages before draining begins;
equal policy settings produce the corresponding 3 / 4 return values. Full
update traces and focused RDRAM remain unchanged under observation. The
remaining lead is the earlier message availability split, not a demonstrated
fault in the producer's counting logic. Selected-state frontier remains 1908.

Trace execution/device completion and guest queues around update 1908 to
distinguish CPU-work accounting from device-event timing/output visibility.
The local elapsed-word mismatch is not itself permission to patch gameplay.

The [durable profile handoff](autonomy-execution-profile-handoff.md) now carries
the execution and runtime/config pins through update, determinism and
candidate-retest packets. Live update -> focus -> boundary-analysis and repeat
jobs passed; candidate propagation has synthetic coverage, not a live game-fix
acceptance. Independent repair-loop closure, full-route qualification and
complete native snapshots remain open. The 1291 request is achieved; the entire
automation-loop goal is not complete.

The subsequent [device-event observation](phase9-device-event-observation.md)
adds bounded raw engine events and verifies unchanged full update traces and
focused RDRAM on both sides. The fresh pair again passes through update 1908;
it does not yet explain or fix the 1909 divergence.
