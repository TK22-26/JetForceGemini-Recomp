# GH-034: Modern aiming range during the Twin Mantis fight

- Status: owner-approved boss aiming correction after live Twin Mantis review; all five boss fixtures match EmuHawk in both Modern input paths; unreleased. Remaining validation limits are documented below.
- Severity: high gameplay impact; reported reduced ability to target boss arms.
- Source: [GitHub #34](https://github.com/TK22-26/JetForceGemini-Recomp/issues/34), created 2026-10-20.
- Affected report: v1.3.0, Windows 10, RTX 3090 Ti driver 617.42, PS4 controller,
  Modern Controls. Reporter says every attempt; no support ZIP attached.

## Symptoms and reproduction

During the Twin Mantis boss fight, stand near the middle of the arena. When a
boss jumps to the left or right, the reporter cannot move the reticle far enough
to hit its outer arm with Modern controls. Moving far across the arena makes
the arm reachable. The reporter links a [reference video at about 30 seconds](https://www.youtube.com/watch?v=WDIhFvTal98).
The reported loss of horizontal range is reproduced below; actual outer-arm
shot collisions still need validation.

## Investigation scope and evidence

The owner requested investigation and validation against the original game in
EmuHawk before implementation. Compare the same arena/player/boss positions and
aim state, separating reticle displacement, actual shot direction and camera
framing. Review native boss-specific aim limits and Modern direct-look overrides.
At intake, range/clamp and camera-space differences were hypotheses. The
comparison below identifies the missing native weapon offset.
Preserve normal saves and existing previews; original-game tests use private
copied configurations and evidence. Initial authorization covered investigation only;
the later one-hour implementation approval and its results are recorded below.

Private evidence ID: `github34-review-20261020` (issue/comments snapshot).
Runs use the existing enabled production guard, root, counters and deadline.

## Prior validation scope

The earlier [Ichor boss controls fix](github-ichor-boss-controls.md) established
movement/input availability, not maximum aiming reach. This review isolates a
separate range defect; that historical acceptance remains preserved.

## Original-game comparison and confirmed cause (2026-10-20)

The original USA ROM was run in isolated BizHawk/EmuHawk 2.11.1 using the
Mupen64Plus cached interpreter and 4 MiB configuration. A private copied Lupus
boss checkpoint selected the character/room and marked the introduction seen;
normal controller startup reached active Twin Mantis combat, level 210. No
original-game gameplay-memory patches were used. Each input trial restored the
same checkpoint. The first setup attempt reached its bounded request limit in
saved-game confirmation; adding ordinary A confirmation to that test driver
resolved the fixture failure.

All compared endpoints have player position [-68, -44, -2005], character 2
(Lupus), combat state 32 and a valid boss actor. Horizontal angles below are
measured relative to the neutral forward direction, using the native weapon-aim
field; screenshots also show the missing off-center reticle travel.

| Input path | Measured left reach | Measured right reach |
|---|---:|---:|
| Original ROM in EmuHawk | 76.23 degrees | 76.23 degrees |
| Recomp Original controls | 76.23 degrees | Not tested |
| Recomp Modern controller | 56.25 degrees | 56.25 degrees |
| Recomp Modern mouse | 56.25 degrees | Not tested |

Original tests held analog X at +/-80, with and without R, and additionally
tested +/-127. All reached the same endpoints. Modern loses about **19.98
degrees on each measured side**, approximately 26% of the original horizontal
reach. The player's body still turns to the native +/-56.25-degree limit; the
missing part is the additional roughly 20-degree weapon/reticle offset.

The Modern direct-aim hook in src/boot/native_boot.cpp, at the shared guest
aim function 0x8003AABC, substitutes zero stick values while calling the native
helper, then updates the main yaw/pitch directly. That helper also writes
caller-provided horizontal and vertical weapon-offset outputs. Zero stick input
sets those outputs to zero, and the direct-aim replacement does not restore
their contribution. In boss combat, the caller clamps body yaw to +/-0x2800
but normally adds a separate weapon offset limited by 0xE38. The original
settled horizontal offset measures 3,638 angle units; Modern measures zero.
Thus the ordinary body rotation cannot supply the original total aim range.

The three native character boss handlers all use this same output contract and
body-angle clamp. That is a concrete reason to check Juno and Vela boss fights
when fixing it, not a claim that every boss was reproduced. The initial direct
comparison in this section is Lupus/Twin Mantis only; expanded coverage follows. The tested direct-aim hook is identical
in v1.3.0, the accepted preview source and the current checkout.

### Initial proposed remedy and validation

Preserve the original combined body-plus-weapon aiming envelope in Modern boss
aiming. The correction should account for the native weapon/reticle offsets
while respecting the native body clamp, rather than increasing a general camera
limit. Keep mouse and controller behavior consistent and preserve Original
controls, scope behavior, pitch convention and non-boss camera ownership.

At the initial review, no runtime fix had been implemented. Candidate acceptance
was defined to verify both
directions and vertical range, native reticle/shot correspondence, actual outer-arm
hits from arena center, release/reversal and scope behavior, plus the other
character boss handlers. Existing movement/input-availability checks did not
test reach to the edge of the aiming envelope; future acceptance must include
that boundary.

### Evidence and practical limits

Private artifact ID: github34-review-20261020. The comparison.json receipt records
all measurements, exact source-block hashes, raw-memory hashes and native
call-site contracts; checkpoint/RAM/saves/ROMs remain private. Tested recomp
runtime SHA-256: a26006f13c507dd4601461308ce43153d98d6eb90ca104685fce2ac130dee154.

Native runs used the same prepared save, effective replay inputs, one normal
exit warp and infinite health for bounded test setup. Player position matches,
but boss animation timing is not frame-matched between native and emulated runs.
Physical PS4 hardware, actual shot collisions and full-fight completion were
not tested. These limits do not explain away the observed 3,638-unit missing
weapon offset in both Modern paths. The initial review created no package, commit, push, release or public
issue reply for #34. A later private candidate package is recorded below. Work stayed within the existing enabled guard,
root, queue, deadline and counters.

## Shared boss correction and verified candidate (2026-10-20)

The owner approved one hour of parallel implementation and explicitly included
all related boss handlers and Mizar. The candidate restores the original
combined body/weapon horizontal and vertical envelope. It retains native
smoothing, the body clamp, native pitch limits and scope-dependent weapon
offset limits. Cached commanded offsets hold through neutral input and reverse
without accumulating motion beyond the clamp. Original controls bypass the
correction. Actor, boss, control ownership, focus and mode changes reset the
cached context.

Implementation: `PcBossAimMotion` and `pc_boss_aim_limit` in
`include/jfg/runtime/pc_input.hpp`, the shared `0x8003AABC` hook in
`src/boot/native_boot.cpp`, and behavioral coverage in `tests/pc_input_tests.cpp`.
The hook qualifies the exact native boss argument/stack/output-slot contract
and boss combat state. It applies to all three character boss handlers, including
upgraded variants and both Mizar encounters. It does not enlarge a general
camera limit or change normal movement.

### Original and candidate comparison

EmuHawk original tests restore the same private checkpoint for each direction,
then use ordinary controller inputs without gameplay-memory patches. Final
native tests use the same prepared saves, effective Modern input replay, and
infinite health for bounded setup. The native continue path needs an existing
arena exit for some checkpoints. These are arena-position and angle comparisons;
boss animation timing is not frame matched.

| Boss fixture | Character | Original horizontal reach | Candidate Modern reach |
|---|---|---:|---:|
| Juno boss, room 195 | Juno 1 | about 76.23 degrees per side | Matches |
| Vela boss, room 181 | Vela 0 | about 76.23 degrees per side | Matches |
| Twin Mantis, room 210 | Lupus 2 | about 76.23 degrees per side | Matches |
| First Mizar, room 386 | Juno 1 | about 76.23 degrees per side | Matches |
| Final Mizar, room 233 | Upgraded Juno 5 | about 76.23 degrees per side | Matches |

Across all five fixtures, Modern controller and mouse exercise opposite signed
horizontal and vertical endpoints, plus held aim after release; mouse also
reverses direction before release. Combined vertical reach matches the original
at about 79.98 degrees per side. The maximum difference is one angle unit,
about 0.0055 degrees. Positions and body limits match exactly. Script labels are not physical pitch
conventions: validation compares the actual signed angle fields. Full upgraded
Juno identity is verified in both EmuHawk and native execution. Persistent game
flag 95 selects the upgraded variant; only the disposable test save is changed.

Original controls on the corrected runtime still reach 13,878 yaw units from
the same Twin Mantis position, with zero Modern aim/boss-hook events. Supported
Modern mouse and controller modes 3/5 are exercised live by replay. Legacy
mode 4 shares the same boss correction but has source-level coverage only.

Core checks pass: 1,618 PC-input, 169 Modern-controls and 416 rolling checks.
An independent MSVC C++20 `/W4 /WX` test build also passes. Source review confirms
that boss-owned code in the checkout matches the isolated tested build; unrelated
concurrent cutscene work is preserved. Diagnostic-only tracing differences do
not alter the aiming state.

### Informative failures retained

- The first private runtime copy lacked its companion DLLs and failed Windows
  loading before gameplay. Copying the verified companion set fixed the fixture.
- An initial hook gate treated the linked overlay return address as a physical
  RDRAM instruction address, so the correction stayed inactive. The original
  contract was enumerated across all callers, and the final gate uses the exact
  observed boss ABI and state. The failed runtime trace remains preserved.
- An initial release replay used recorded VI values despite playback being
  indexed by input poll. The corrected driver schedules release by poll ordinal
  and final verification associates each boss call with the actual consumed
  input row. The first Mizar entrance runs had a shorter neutral tail than the
  VI-only count implied; dedicated reruns release earlier and verify more than
  30 distinct consumed neutral polls with stable aim. Endpoint-only evidence
  is retained separately. The final Mizar mouse run also exposed the old
  VI-filter assertion including two still-moving inputs; independent step 985
  supersedes that assertion with consumed-row and zero-look trace checks.
- The first optional scoped driver failed parsing its extracted fixture code
  before gameplay. A newline-anchored extraction was prepared, but the corrected driver
  was not executed because its reserved time exceeded the remaining approved
  window. No scoped runtime result is claimed.
- An original Vela fixture mistakenly retained the Lupus seed. Character/room
  assertions caught this before qualification; the corrected reference passed.
- Initial native Mizar runs restored anterooms 395 and 396, so no boss aim hook
  ran. Corrected fixtures use existing eligible arena exits, with the final
  fight's high-byte sentinel decoded from original code and data. These failed
  setups are preserved separately from successful boss tests.
- The first final-Mizar entrance replay reached the normal Area Cleared
  confirmation screen. Retained frame and transition RAM identified the pending
  destination as 233. Ordinary A-button confirmations in the corrected replay
  dismiss that screen; no gameplay or level-transition patch was needed.
- A broad source comparison initially reported surrounding diagnostic trace
  additions. Exact owned-fragment comparison plus review of the trace helper
  confirms the boss math, hook and lifecycle operations match the tested source.

### Preview, remaining verification and compatibility

Private preview: `C:/JFG-previews/boss-aim-range-20261020`, desktop shortcut
`JFG - Boss Aim Preview`. Launcher init/setup and runtime protocol checks pass;
runtime support identity is regenerated for the exact executable and matching
private symbols. Settings and saves are copied from the accepted mouse-inversion
preview and source hashes remain unchanged. The accepted Modern mouse default
and reset Off correction is retained; explicit saved choices are preserved.

Runtime SHA-256:
`97deb741658560d6859dc8ac2f3ec10dfdcc9a984456bec4ec52d50f7093470a`.
Private evidence ID: `github34-fix-20261020`; see `final-validation.json`,
`reference/original-reference-matrix-final.json`, `native-review.md`,
`boss-source-identity-final.json`, each native `summary.json`, and `delivery.json`.
The initial `github34-review-20261020` evidence remains intact. ROMs, generated
game code, personal saves, raw memory and symbols remain private.

The owner has approved this correction after live Twin Mantis review, as recorded
below. Actual outer-arm shot collisions from the arena center, physical PS4 hardware,
complete boss fights and native scoped gameplay were not separately confirmed by
that feedback. These are validation limits, not a pending owner-approval gate.
Keep #34 open until delivery and reporter retest. No commit, push, release or
public reply was made.
The same enabled production guard, investigation root and counters were retained
inside the approved one-hour deadline.

Transferable lessons: movement availability is not maximum aiming reach; test
both the body's clamp and the separately published weapon direction. Preserve
all native helper output slots, scope scaling and context resets. Linked overlay
return addresses need relocation before instruction-memory inspection. Replay
poll indices and VI timestamps are different clocks. Cover each shared handler,
the relevant upgraded variant and both encounters before generalizing a fix.

### Scope validation limit

The native scope-dependent offset formula and input scaling have source/unit
coverage. A disposable EmuHawk sniper fixture confirms the 5x envelope; matching
Modern runtime scope execution remains pending and is not claimed here.

The final documentation pass initially stopped when the Windows default decoder
read a UTF-8 changelog. An explicit UTF-8 continuation completed the changelog
and desktop tracker while preserving existing text. This was documentation
handling only; executable and test results did not change.

## Owner approval (2026-10-20)

The owner played the fixed Twin Mantis preview as Lupus after requesting a warp
to that fight. The handoff reached active room 210 through the existing arena
exit, using a separate checkpoint profile and the tested runtime above. The
regular profile save was preserved and hash-verified unchanged.

Owner feedback: "looks good, not sure what it was like before but it matches
the youtube video now". The owner then explicitly instructed: "just approve it".
**The boss aiming correction is owner-approved.** No further owner acceptance
is required. This does not claim an owner before/after comparison or live
coverage of every boss, device, shot collision or scoped state. Existing automated
coverage and its limits remain as recorded above.

Next release follow-up: include the approved fix and ask the #34 reporter to
retest. Approval is recorded locally; no new commit, push, release, issue closure
or public reply is performed. Private handoff evidence:
`github34-fix-20261020/owner-twin-mantis-handoff/arrival.json`.
