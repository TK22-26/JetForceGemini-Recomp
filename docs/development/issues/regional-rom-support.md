# ROM-REGIONS: PAL and Japanese ROM support

- Status: shared three-region implementation and enhanced native/launcher handoff qualified within the documented scope; public-default resource-bounded compilation and owner feature/campaign acceptance remain open; unreleased.
- Severity: regional compatibility and acceptance limitation. Development build admission includes US/PAL/JP; the published v1.4.0 package remains US-only.
- Affected: ROM generation, regional host address/timing assumptions, launcher/runtime admission and gameplay qualification.

## Additional automated-check continuation

Owner approval: four hours, 2026-11-01 23:02:40 UTC through
2026-11-02 03:02:40 UTC. Private evidence root:
`regional-automation-20261101-owner4h`. The same production investigation,
ledger, roots, counters and deadline are preserved. This pass extends the
existing v28 native/v30 launcher handoff from implementation `5bac0c8`;
it does not certify every feature, campaign route or a public release.

| Check | US | PAL | JP | Evidence and limit |
|---|---|---|---|---|
| Normal enhanced Play: fresh slot and separate 180-second reload | Pass | Pass | Pass | Valid 131,072-byte saves; unchanged reload hashes; Goldwood frames inspected; `normal-save-lifecycle.qualified.json` |
| Five-minute scripted Modern actions | Pass | Pass | Pass | Aim/look/fire, jump, crouch, pause/Save/resume and intro skip; `modern-actions.qualified.json` |
| Separate reload of changed Modern saves | Pass | Pass | Pass | Saved ammunition 97/96/97 visible; save bytes unchanged; `modern-save-reload.qualified.json` |
| Sequential 15-minute enhanced Play | Pass | Pass | Pass | Repeated movement, pause and intro skip; normal exit, no unsupported accesses or audio underruns/overruns; `sustained-play.qualified.json` |
| Full-size checksum and padding menus | Pass | Pass | Pass | Four cases per region, every frame reviewed; `checksum-menus.qualified.json` |
| Denied atomic replacement, then exact-destination retry | Pass | Pass | Pass | Preserved failed bytes, release read lease, retry without copying/resetting; `same-path-save-recovery.qualified.json` |
| Malformed save lengths at actual native startup | Pass | Pass | Pass | Nine unchanged rejected fixtures: 1, 131,071 and 131,073 bytes; `invalid-save-startup.result.json` |
| Actual legacy-profile upgrade and import recovery | Pass | Pass | Pass | Installed assembly and frontend init/import/setup; isolated v1.4-signoff fixture; `product-recovery.result.json`, `legacy-frontend-upgrade.result.json` |
| Public build resume input validation/configuration | Pass | Pass | Pass | Damaged generation rejected before configure; valid generation configures; not complete compile/link |
| Public-default native compile/link under bounded test resources | Not qualified | Interrupted | Interrupted | US 8 GiB failures below; distinct from passed enhanced v28 builds |
| Unskipped story to character selection | Pass | Pass | Pass | All frames reviewed; no skip confirmations; `unskipped-story.qualified.json` |
| Saved-slot confirmation into gameplay without cutscene skipping | Pass | Pass | Pass | At least 60 seconds in gameplay, all Goldwood frames reviewed; `unskipped-entry.qualified.json` |

The WSL follow-up runs 172 tests with no failures and six explicit skips
(166 passes). It executes compiler, Linux invocation and symlink checks that
were absent from the Windows run. The remaining skips concern Windows-only
policies/fixed-toolchain harnesses or unavailable historical inputs. It does
not qualify Linux live gameplay or resolve every prior skipped test.

### Storage, controls and product scope

Checksum/padding cases observe the original file-select behavior: valid slots
and changed unused padding retain the existing slot; changed payload or stored
checksum presents a new slot. All files stay unchanged merely by viewing the
menu. Japanese file-select labels were inspected; this is not complete language
or font acceptance.

The exact-path write tests deny delete sharing through a read lease. Each
native process reports `flash-persist` and leaves the erased fixture unchanged.
After releasing the lease, a separate process writes a valid slot at that same
path without resetting or copying its contents. Failed-byte snapshots and
separate attempt logs remain preserved; no temporary files remain. All successful
retries close normally with zero unsupported accesses and audio underruns/overruns.
Earlier copied-fixture retries are retained separately in
`save-write-failure.qualified.json`; they are not relabeled as exact-path tests.
No personal saves, power loss or complete campaign durability were tested.

Modern reloads retain 24/22/24 changed bytes relative to the original fresh
US/PAL/JP fixtures and show the saved ammunition counts. These are logical
input replays in Juno's Goldwood opening area, not physical keyboard/controller,
rumble, Floyd/co-op, all-character or campaign-wide feature acceptance.

The sustained runs enter the pause root 12/10/12 times and finish in inspected
Goldwood shallow-water scenes. Final-five-minute combined private memory stays
within 987.9-988.1 MiB (US), 1009.2-1012.3 MiB (PAL), and 991.3-991.6 MiB (JP).
Requested 120 Hz is not a measured presentation-rate guarantee or an indefinite
leak test. The opening walkway is not qualification of the separately documented
Walkway departure music route.

Actual product checks preserve legacy campaign/controller data produced by the
retained v1.4 signoff helper (`2cb7236`), isolate regional/navigation namespaces,
reject wrong bundles and foreign/unmarked regional profiles, and recover after
locked-destination import failures. All three original ROM byte orders normalize;
modified imports preserve the prior valid ROM and a subsequent valid retry works.
This covers local session preparation and frontend upgrade, not historical
installer/prerequisite/reboot acceptance.

### Opening and entry scope

The fresh-slot story reaches native character selection (mode 5), where it
waits for input. The original driver incorrectly required gameplay mode 16
without supplying character confirmation. Its three failed assertions remain
preserved. Independent qualification checks the expected selection screen,
normal exit, actual native job membership, checksum-valid save and zero skip
confirmations. Actual durations are 651.0/557.3/242.6 seconds for US/PAL/JP;
PAL/JP close normally after selection is stable, rather than waiting out the
650-second maximum.

Separate saved-slot processes use title Start and ordinary A confirmations,
with no Start input after poll 242. They reach Goldwood gameplay without a
cutscene-skip confirmation and remain there for at least 60 seconds before a
normal owned-window close. Actual durations are 225.1/196.6/224.7 seconds;
480 seconds is a maximum, not an asserted completed duration. Every final
image was reviewed. The helper initially expected its own closer to supply
the window receipt; the independent monitor's actual WM_CLOSE receipts establish
normal closure instead. This also preserves the helper failures honestly.
A first monitor found the supervisor process but omitted its native window
child and closed nothing; the corrected monitor verifies the whole owned tree.

The owner began separate manual sessions during the later checks, then asked
for muted automation. Only guarded game audio sessions were muted; manual
sessions were excluded. Saved-slot entry runs receive a private muted profile
before launch. An idle waiter restart first rejected its harmless console
helper, then was corrected without interrupting a game. Input scheduling was
extended before execution to cover delayed character confirmation. No future
underrun diagnosis is implied by collecting the normal counters.

### Audio exceptions

The first US fresh-slot run records four underruns while WSL/import checks run.
The PAL five-minute Modern run records one with no heavy compiler running;
its empty/resume trace observations are about 29.4 ms apart, not a measured
audible-gap duration. A US copied-fixture write retry records one during
compilation, and JP's changed-save reload records one without a compiler run.
The extended PAL story records one more underrun. Their causes and audible effects remain unknown. No audio remedy is claimed.
The isolated repeat of the same US native identity, input and 180-second
duration records zero underruns/overruns after compiler and other gameplay
runs finish. The earlier four events are not reproduced; that does not prove
their cause or audible quality. Lightweight documentation/orchestration continued.
Evidence: `isolated-intro-audio.qualified.json`.

The owner explicitly deferred further underrun investigation until manual
listening identifies an audible issue. Retain these counters as observations;
they do not block the manual-testing handoff or establish an audible defect.

All other initial fresh/reload runs, the three sustained sessions, all twelve
checksum menus and all exact-path successful retries record zero underruns and
overruns. Those passes do not erase the exceptions or replace listening tests.

### Guard repair and source-build limits

Read-only process queries found native compiler descendants outside the
Windows job despite the packaged Python worker itself being assigned. The
unfinished builds and queued helpers were stopped. An unpackaged worker was
explicitly attached to the same production job before its gate opened; actual
native membership is recorded in later replay receipts. Earlier observations
remain evidence, but earlier native containment and resource accounting are
not retroactively established.

The [containment repair](windows-packaged-python-child-containment.md), committed
as `582cda8`, rejects packaged workers, assigns suspended processes before
execution, migrates guard consumers and rejects historical receipts during
expired-attempt recovery. Final affected suites pass 507 tests with no skips;
a real synthetic CMake/MSBuild/CL build verifies native membership and resource
accounting. The production guard stays enabled with no counter/root reset.

The resumed public-default US build fails with C1060 heap-exhaustion and D8040
child-process errors under an 8 GiB nested test limit. Reducing compilation to
one job also fails: MSBuild reports StackOverflowException, and the recorded
peak reaches about 8 GiB. The exact compiler/.NET allocation is unlocalized.
The serial retry conservatively subtracts all prior outer-job CPU from the
original 5,000-second build allowance; no resource limit is raised. Both failed
logs/status/source receipts remain retained. The serial helper exits and closes
its job; a later cleanup request rejects the already-stale PID before any kill.
No third retry or direct fallback was made. Public-default compile/link remains
unqualified in this resource envelope; these failures do not establish a source
defect on an unconstrained host or invalidate the enhanced v28 bundles.

The guard repair changed automation code and one CPU microcase runner included
in the conservative native-source closure; its checkpoint retained all compiled
game/runtime sources and 145 launcher inputs. The supplied handoff manifests
remain immutable at `5bac0c8`. A subsequent owner report opened a separate
[Modern Aim-release camera candidate](modern-aim-release-camera-snap.md);
that candidate changes game-source inputs and requires its own build/play
qualification. Earlier v28 results are not relabeled as tests of that change.
See `guard-change-handoff-correspondence.json`. Stale launcher, bootstrap,
FlashRAM and PAL-cadence summaries were corrected to match their actual evidence.

Original private orchestration failures are retained in both step manifests:
a status-print variable error after helper launch, a wrong replay directory
corrected before execution, quoting/encoding failures, a shadowed accounting
variable after launch, and a missing import before staging. Running helpers were
verified rather than duplicated; failed steps are not test passes. The closeout
auditor also initially assumed every receipt had a `complete` field, then
compared raw ROM hashes with normalized bundle identities. Those two audit
assertions were corrected to use the WSL receipt's actual result schema and
canonical ROM byte order; no ROM or runtime change was needed. No personal
save, ROM, generated game body or private capture is committed.

Remaining acceptance covers all-character campaign progression, broader Modern
features, Floyd/co-op, flight, bosses, transitions/cinematics, PAL languages,
Japanese text, physical controllers, listening, host/platform coverage and
release review. Optional PAL/JP flying-motion enhancement still needs a regional
reference; original regional movement remains active. No unrun manual check is
assumed passed.

## Five-hour continuation — current checkpoint

This checkpoint predates the additional automated checks above. Its evidence
and then-current remaining work are preserved; later results narrow only their
explicitly tested scope.

The owner approved this continuation from 2026-11-01 20:35:42 UTC through
2026-11-02 01:35:42 UTC. The production guard remains enabled on the same
investigation, with all roots, counters, charges and failed evidence preserved.
Private evidence root: `regional-architecture-20261101-owner5h`.

| Evidence | US | PAL | JP | Scope |
|---|---|---|---|---|
| v28 fresh original reconstruction and CPU/audio generation | Pass | Pass | Pass | Current producer verified; no relabeled earlier generation |
| v28 enhanced native compile/link and immutable bundle | Pass | Pass | Pass | Shared runtime, native timing/collision/optimizations enabled |
| v28 200-VI boot, 32-poll stop, wrong-ROM/storage rejection | Pass | Pass | Pass | Bounded execution and revision isolation |
| v28 150-second enhanced Play, requested 120 Hz | Pass | Pass | Pass | Same-revision v16 save reload; normal window close; zero unsupported accesses |
| v28 final-frame review | Pass | Pass | Pass | Goldwood walkway, Juno, tribal and HUD visible; PAL side borders corrected |
| Latest original instruction qualification | Pass | Pass | Pass | 379 instruction bindings per revision, including 169 additional member contracts |
| Latest host and pipeline contracts | Pass | Pass | Pass | Shared suites: 111 CTests and 138 Python tests; not three independent campaign runs |
| Local native-build admission and launcher tests | Pass | Pass | Pass | All three admitted; 39 focused policy/bundle tests plus launcher/setup/native-UI tests |
| v28 fresh new slot, 6,000 VI; separate reload, 8,000 VI | Pass | Pass | Pass | Final binaries in original-OS probe mode; populated private saves; Goldwood frames inspected |
| v30 launcher import/setup/direct Play and clean shutdown | Pass | Pass | Pass | Actual installed regional bundles; exact source identity; other-region saves unchanged |
| Development-profile upgrade v28 to v29 | Pass | Pass | Pass | Actual init/setup; save and settings hashes unchanged; not a historical-release upgrade |
| v30 native-session support ZIP export | Pass | Pass | Pass | Actual installed exporter; revision/build identity retained; bounded sanitized text only |
| Campaign, feature and hardware acceptance | Pending | Pending | Pending | Owner playtesting; no unrun manual check is a pass |

Implementation commit on `develop`:
`5bac0c896c3e4a47456b2973994bbe7151062e77`. All three final v28 enhanced
Play replays pass with normal window close, zero unsupported accesses and
zero audio underruns/overruns. All final frames were inspected in Goldwood.
The sequential JP run does not reproduce the two earlier concurrent-run
underruns; their cause and audible effect remain unmeasured. Fractional alpha
and moving-presentation observations are present for every region. Requested
120-Hz output remains distinct from measured presentation performance.
The v30 handoff launcher is rebuilt from this commit with its actual source
identity; product and save results remain separately recorded below.

Final native evidence: `regional-snapshot-v28.result.json`, with common native
source closure `0993b4454d750dc684643768dd982498317e24dfcfd13c4befe7ea605885679b`
and producer `179b39c194ce2520111ab0f75f337bf21fb1163b347d869673c29c4af7d046cf`.
All 593 native source inputs match the committed implementation. The v30
launcher records that commit and its 145 production inputs. The final
correspondence audit verifies those inputs against the checkout. Subsequent
documentation changes do not alter the native or launcher source closure.
These identities are private candidate evidence, not a release tag or a
console-parity claim.

The latest source qualifies actor/player, camera, NPC, door, sidekick, flight,
effect, cutscene, inventory, exit, model-instance and track-geometry members
against independently hashed original owners. Tests move record fields and
reject old layouts. Common packed arrays and sound queue ABI are admitted only
after original constructor/consumer arithmetic passes strict guards. Missing
members, changed operands, wrong owners or damaged array formulas reject generation.

Concrete corrections in this window:

- Presentation carries an exact VI interval and VI clock through history, blur
  pairing and RT64 scheduling. PAL intervals such as 3/50 and 4/50 no longer
  fail an integer-FPS gate. Long mixed-cadence component checks and v26/v27
  fractional interpolation traces pass. A requested output rate is not measured
  presentation performance.
- The shared VI-size helper applies PAL scanline-aspect units using actual VI
  sync timing. Viewport, edge clipping and mouse mapping agree. Full-frame
  288-line PAL and 240-line NTSC/MPAL fixtures have the same 4:3 ratio; native
  cinematic cropping is retained. v27 PAL removes the earlier vertical borders.
  Hardware crop/overscan acceptance remains separate. References:
  [libdragon PAL/NTSC documentation](https://github.com/DragonMinded/libdragon/wiki/PAL-NTSC-support)
  and [Nintendo VI manual](https://jrra.zone/n64/doc/pro-man/pro30/30-01.htm).
- The optional flying-motion correction uses its qualified US three-VI reference
  only. PAL/JP execute their original movement path until their encounters qualify
  an enhancement; identical body shape is not behavioral timing evidence.
- Empty asynchronous volume snapshots are rejected; see the
  [volume issue](async-volume-empty-snapshot.md). Its full host-suite reruns pass.
- Exit definitions now preserve the original `FF` high-byte sentinel; see
  [NAV-EXIT-SENTINEL](navigation-exit-destination-sentinel.md). This is a host
  navigation defect, not a native-hardware bug. Both memory layouts and relocated
  fields pass regression tests.
- The remaining US-only music correction writes only its bound tune byte. A
  checked raw byte-write API preserves adjacent bytes and rejects bad addresses.
  Walkway remains excluded: NTSC hardware omits departure music, while the
  separately checked PAL emulator session includes it. JP expectation is unknown.

The final complete Python regression passes: 1,933 tests discovered, 49
explicitly skipped, no failures or errors (`regional-all-python-v29`). Skips
retain their individual missing compiler, platform or private-fixture reasons
in the private result; they are not passes. Three directly relevant compiler
checks that skipped on Windows subsequently pass under WSL with no skips:
entry identity across reload, success-only initializer storage, and compiled
RAM/MMIO/poll timing equivalence (`regional-wsl-abi-v30`). That does not
qualify Linux live gameplay or the separately pinned replay core.
The first broad run loaded the release fixture before its destination-isolation correction and retained that
one failure. The subsequent 38-test release run and final full run both pass.

The final product audit found two additional downstream omissions. The
[release verifier](regional-package-verifier.md) still required the old flat
package format; it now validates the regional format, with all 38 release
tests passing. The [support sanitizer](regional-support-identity.md) dropped
the selected ROM revision; the rebuilt v29 launcher preserves its verified
revision and program hashes, with all-three ZIP export/privacy tests among
748 passing launcher checks. These product-only changes do not alter the
frozen v28 native runtime closure. Final installed-bundle Play and native-session
support exports also pass, separately from those synthetic tests.

### Final local handoff

The private `owner-review-v30` folder contains the launcher built from
`5bac0c8`, all three verified v28 runtime bundles, imported local ROM copies
and isolated test profiles. `Play-US.ps1`, `Play-PAL.ps1` and `Play-JPN.ps1`
start normal game flow through the actual launcher. Choose the supplied
save at file select; the scripts do not warp the game. The supplied saves
retain their earlier v16 provenance, with current enhanced reload evidence.
Original ROM hashes are unchanged; no personal save was copied or edited.
The folder contains private game inputs and is not a distributable release.

Final receipts under the private evidence root:

- `owner-review-v30.result.json` and `launcher-product-v30.result.json`: actual
  import, setup, verified runtime selection, Playing status, clean shutdown and
  save isolation for each region.
- `launcher-upgrade-v29.result.json`: earlier development profiles retain every
  save/settings hash while selecting the newer bundle.
- `actual-support-exports-v30.result.json`: actual installed support exporter
  retains exact identities in all three native-session ZIPs; no upload occurred.
- `regional-save-v28-qualified.result.json`: fresh populated 131,072-byte slots
  and separate-process reload on final binaries. New-slot ship frames and
  reload Goldwood frames were inspected. This is original-OS probe evidence,
  separate from the enhanced Play replay.

Remaining acceptance covers campaign progression with all characters; Modern
controls, Floyd/co-op, flight, bosses, transitions and cinematics; Japanese
text and PAL languages; physical controllers, listening and sustained
performance. Optional PAL/JP flying-motion correction still needs its own
reference before enablement; original regional movement is active. Broad
historical-install migration, other platforms/hardware and public-release
qualification remain open. No unrun check is assumed passed.

Retained failures and limits:

- v24 Play first rejected a harness-written CRLF profile marker. Canonical LF
  bytes passed v24b; the runtime rejection was correct.
- v25 RT64 compilation rejected a C++20 defaulted comparison in its C++17 build.
  Explicit operators and a C++17 test target fixed the build contract; v26 passed.
- Original binding qualification rejected a mistaken `turnRate` name and an
  invalid null overlay-slot key. Two same-offset door-indicator reads also used
  the wrong semantic field name; the corrected owner is now explicit.
- The full suite first exposed the empty-volume snapshot race (110/111). A later
  build caught the absent byte-write API; both failures are retained, and the
  corrected current source passes all 111 tests.
- Model face bounds had used an adjacent halfword without an original consumer
  witness. The reader now uses the native final-batch sentinel; poisoned-field
  and relocated mesh fixtures pass. Track face counts have a separate qualified
  loader witness and are not inferred from the model format.
- Windows legacy text encoding damaged one documentation write; explicit UTF-8
  repaired it. Rejected private edit scripts and intermediate receipts remain
  retained; no failed script or partial build is counted as qualification.
- v27b US/PAL report zero audio underruns/overruns. JP reports two underruns and
  zero overruns during three concurrent Play processes. Cause and audible impact
  are unmeasured. The final sequential v28 run reports zero underruns/overruns
  for all three; that is a bounded non-reproduction, not a proven audio remedy.
- Normal Play replays use Classic controls and existing same-revision test saves.
  They do not cover Modern controls, Floyd, bosses, transitions, all languages,
  or campaign completion. Current-build new-slot creation and reload pass the
  separately recorded original-OS probes; they are not enhanced feature
  acceptance. Earlier v16 evidence remains explicitly historical.

The following four-hour and eight-hour sections preserve their then-current
status and failures. They do not override this current checkpoint.

## Current four-hour continuation

The owner approved four additional hours on 2026-11-01. The same production
investigation retains all prior charges and failures; the guard remains enabled.
Private evidence root: `regional-architecture-20261101-continuation`.

The source candidate is committed locally on `develop` as
`6ef37e9ec1f5168da1f406bc5765a79e48ba6d1f` (2026-11-01 17:31:15 UTC).
This commit is not a released resolution or completion of the regional plan.

Current v23 live validation uses the independently inspected v16 same-revision
private saves as inputs to ordinary enhanced Play. Each result must carry the
current executable identity and the prior save's provenance. Current new-slot
creation and the separate 8,000-VI original-OS reload are not being rerun or
reported as v23 passes. v23 still requires its own native boot, exact-poll and
wrong-ROM/storage rejection checks, normal Play close and captured-frame review.
The original v23 waiter was replaced before execution to focus on that changed
profile; its phase bound remains inside the unchanged four-hour supervisor limit.

| Evidence | US | PAL | JP | Scope |
|---|---|---|---|---|
| Frozen v16 native compile/link and identity | Pass | Pass | Pass | Original-OS configuration; enhanced timing/collision/optimizations disabled |
| v16 200-VI boot, exact 32-poll stop, wrong-ROM and storage rejection | Pass | Pass | Pass | Zero unsupported accesses in bounded boot |
| v16 neutral 200-VI repeatability | Pass | Pass | Pass | Two runs per revision |
| v16 new slot, 6,000 VI | Pass | Pass | Pass | New private 131,072-byte FlashRAM, opening Juno ship scene captured |
| v16 same-region reload, 8,000 VI | Pass | Pass | Pass | Juno in Goldwood opening walkway, green tribal and HUD visually reviewed |
| Current original code/data/instruction qualification | Pass | Pass | Pass | 435 code, 225 data and 210 instruction references per revision |
| Original ROM NPC asset parser | Pass | Pass | Pass | 45 groups and 19 choices; no imported US tables |
| v21 enhanced native compile preflight | Pass | Pass | Pass | Superseded after audit found nominal PAL clock assumptions; no full-build acceptance |
| v22 enhanced candidate build | Link failed | Link failed | Link failed | Generated game compilation completed; stale host caller objects requested the old audio ABI |
| v23 forced host rebuild | Incomplete | Incomplete | Incomplete | Original generation and native identity verification pass; rebuild stopped inside approved window |
| v23 enhanced Play and launcher handoff | Not run | Not run | Not run | Insufficient remaining time; PAL/JP product admission stays closed |
| Campaign/manual feature acceptance | Pending | Pending | Pending | Owner will playtest; no unrun check is a pass |

The v16 results verify the PAL exception-entry and JP matrix-body corrections,
but do not qualify subsequent source or the enhanced Play profile. v18 passed
all three native compile preflights; its full build was stopped after discovering
additional US math-table assumptions. It is superseded, not a qualified Play
candidate. The first tree-stop command returned a nonzero code; a subsequent
process check verified that its helper had exited. The production supervisor
and queue continued without a new admission or changed counters.

v19 freezes the shared renderer, overlay/member, native operation, math, sound
and ROM asset migration. Its math differential compile exposed a wrong RAM-size
member name; v20 corrects it and adds captured-projection spatial fade support.
All three original v19 generation receipts validate against the unchanged
generator before reuse by v20. This is verified corpus reuse, not a new compiler
execution. The v19 source, generation, failure and partial build remain retained. Eight focused C++ suites pass (`regional-math-assets-msvc-v5`):
navigation, sound queue recovery, PC input, semantic presentation, rain fade,
flying motion, checked game memory and ROM asset bounds. Twenty-six Python
binding/operation/identity/bundle tests pass (`regional-contract-components-v4.log`).
These are scoped contract checks, not campaign or enhanced Play acceptance.
The expanded shared-pipeline selection passes 130 Python tests. The complete
Windows host build caught an unsigned fill value narrowing to a FlashRAM byte
in the new test fixture; the value now has the explicit byte type. All 110 host
tests pass after that correction. The final projection changes pass the eight
affected suites (`regional-math-assets-msvc-v7`). Repository hygiene passes
after exact-body review of opcode lists and handwritten synthetic source fixtures;
credential, ROM, generated-payload and other checks remain enabled.

The v20 full native preflight found two composition errors that the isolated
host suites did not compile: three renderer operations belong to overlays but
used the resident-code accessor, and a weather diagnostic local variable hid
its method. v21 uses the typed overlay-token accessor and a distinct local name.
These are compile failures, not observed gameplay regressions. The v20 logs
and original source remain retained in `source-archive-v20`, with every frozen
file hash verified before its old physical directory became a build workspace.
`source-snapshot-v21` remains the immutable source identity. Incremental builds
reuse unchanged dependency outputs, reconfigure, recapture native identity,
and compare the workspace with the frozen source before publishing a bundle.
This avoids recompiling unchanged dependencies without relabeling old output.

PAL/JP ordinary product admission is still closed. A matching local development
candidate can be built through the existing `--candidate` path. Pending work
includes current enhanced native qualification, product handoff, the remaining
feature/layout matrix and manual gameplay. Previous checkpoints below are
historical; they intentionally retain their failures and then-current status.

## End of the four-hour continuation

The guarded run stopped within the approved window. The current v23 original
CPU/audio generation receipt and native source identity checks pass for all three.
Its forced native host rebuild was interrupted before complete native acceptance;
no current enhanced Play result or launcher handoff is claimed. Completed generated
C objects, partial host objects, source snapshots, failed linker logs and receipts
remain private for a properly admitted continuation. The final private checkpoint
is `continuation-final-status.json`. The guard remains enabled and all charges
and counters remain intact.

Still required: finish the current enhanced build/boot/Play qualification; complete
remaining actor/control/model/scene field ownership; implement exact fractional
PAL presentation duration; finish product setup/upgrade/direct-launch checks and
owner campaign/feature playtesting. These are not all manual-verification items.
PAL/JP ordinary product admission remains closed. No release was published.

## Shared host migration and discovered regional differences

All three revisions now compose `RendererGameLayout`, member layouts, sound
recovery and native math explicitly from original-qualified bindings. There is
no implicit US layout in these shared interfaces. Original overlay module IDs
resolve through the descriptor instead of indexing regional section arrays.
`OverlayMemory` checks the live module owner, domain and extent. Instruction
operand witnesses qualify actor/player fields; original relocation witnesses
qualify module-internal data. Ambiguous short functions require a separately
qualified caller edge, not a guessed address delta.

`native-operations.json` pins the selected revision, descriptor, bindings,
original body, generated source digest, symbol and exact entry. Native cache,
collision, shadow, SP/MI and math consumers select this map. The generated
manifest requires it; missing or modified evidence rejects the corpus.

Concrete causes and remedies found during this continuation:

- Renderer hooks, presentation identity, fade/blur setup, day/night data,
  diagnostics and original return sites still held US coordinates. They now
  use mandatory session bindings. A relocated-layout rain regression verifies
  that new coordinates work, stale US coordinates fail and damaged guards fail.
- Credits' ending flag is at module offset `0xC06` in US, `0xCC6` in PAL and
  `0xBF6` in JP. The write now resolves its qualified halfword and live owner.
- The native math helpers read US sine/arctangent tables and recorded US PCs.
  The mandatory math layout now supplies both tables and all entry/return sites.
  Original table bytes are hash-qualified; generated-C differential
  validation now passes 400,000 cases per revision, including actual native
  admissions, guarded fallback, CPU state, timing, floating-point state and RAM.
- The audio recovery callback/player addresses and PAL VI recovery counter
  differ. Sound recovery and frame recovery now use named original bindings.
- NPC parsing used US ROM offsets. `RomAssetDirectory` is a distinct ROM-coordinate
  contract derived from original PI initialization operands. Its checked view
  verifies revision, table/data boundaries, monotonic offsets and each section.
  All three original directories contain 71 sections plus their terminal offset.
  The first parser incorrectly treated 71 as the largest valid section index,
  read alignment padding as an end offset and rejected all three originals.
  Correct count semantics pass original-ROM parsing and malformed-input tests.
- The first renderer diagnostic span crossed DATA/BSS. Qualification rejected it;
  separate domain references preserve the complete observation without weakening
  the bounds check. JP's random-number function also has a real leading prefix,
  so its operand witness is mapped independently instead of copying US offsets.

These remedies are candidate source changes, not released resolutions. The
superseded builds and informative qualification/test failures remain private.
No original ROM, generated game body, dialogue text or save is published.

### Presentation and nominal audio clock correction

The residual timing audit found two additional shared 60 Hz assumptions:
`PresentationHistory` calculated source cadence and early output release from
60 VI ticks per second, and the host audio queue estimate consumed PCM bytes
using the same fixed divisor. Graphics task timestamps are actual session
retraces, so that interpretation is wrong for PAL's nominal 50 Hz timebase.
The candidate now carries the session VI rate into history snapshots and the
output-boundary comparison; nominal host audio DMA consumes with the selected
rate while retaining fractional bytes. Original OS device scheduling retains
its register-driven owner. The four affected host suites pass (`regional-clock-contracts-v22`), including
50/60 Hz scene release and exact PCM accounting over 1,000 seconds at four
sample rates. The new full native build remains pending.

Camera/flying-motion values are separate game-level units. Their conversion
must be qualified against original owners before changing them; the retrace
correction is not evidence that every game timer should be divided by 50.
The existing conservative interpolation policy still uses endpoints when the
observed VI interval does not produce an integer source rate.

### Full-build linker failure and timestamp remedy

All three v22 generated-game compilations completed, but native linking failed:
`live_frontend.obj` and `guest_execution.obj` requested the old
`HostAudioDevice::service(bool, bool)` while the current implementation declares
an unsigned VI-rate argument. The private workspace synchronization used `copy2`,
retaining source edit timestamps older than objects created by the preceding
preflight. Source hashes alone did not make those stale objects rebuild.

The v23 attempt preserves the failed logs and native identity inputs, copies
changed content with current timestamps, and invalidates the affected C++ ABI
headers and all native host source timestamps. Ordinary dependency rebuilding
must now rebuild their consumers. Completed generated C objects remain reusable:
their source, headers and compiler flags did not change. No old-signature shim or
runtime behavior workaround is added. v23 link and live results remain separate
acceptance requirements. The transferable lesson is to reconcile content identity
with build-system invalidation when populating a reused workspace; a frozen source
manifest cannot by itself prove that every linked object used those bytes.

### Remaining PAL interpolation duration contract

The 50 Hz audit also identifies a concrete enhancement limitation. History
currently represents source cadence as an integer FPS and admits only intervals
that divide the session VI rate. PAL intervals of three, four or six VIs therefore
hold endpoints; the existing synthetic three-VI check reproduces this. The actual
frequency of those intervals in current PAL Play has not been measured. This is
unfinished implementation, not a campaign check that the owner can sign off by
assuming it passed.

The proper remaining change is to carry the exact duration (VI interval / VI rate)
through history, world/blur pairing and the RT64 output scheduler. RT64's integer
refresh hint must not become the time authority. Rounding 50/3 to 16 or 17 FPS
would introduce drift and is not an acceptable remedy. Verify fractional cadence,
variable intervals, early next-scene arrival, blur ownership and capped/uncapped
output on both clocks, then capture live PAL output. The current 50/60 Hz clock
correction remains useful but does not close this requirement. No runtime change
or new successful verification is claimed here.

### Door presentation consumer follow-up

The final common-member review found that door-indicator presentation still
bypassed the renderer layout. Its type, control pointer and animation-frame
checks now consume the already qualified common actor members. A relocated
fixture leaves the old coordinates invalid and verifies the scope restores
all guest bytes. The initial candidate mislabeled the `0x28` animation-frame
field as scale (`0x08`); the original fixture rejected that change. The corrected
semantic member is `layout.actor.animationFrame`, not a new guessed offset.
The retained failed test is `regional-door-layout-v23`; the corrected semantic
presentation suite passes in `regional-door-layout-v23-corrected`. Frozen v23
waits for v22 full native checks before reusing unchanged build objects and
recapturing identity; v22 is never edited while its build is running. Indicator-specific alpha/visibility/control-byte
ownership remains in the residual schema audit.

### Remaining implementation ownership audit

The residual numeric-expression inventory is an audit lead, not a defect count.
The following work is distinct from manual playtesting and remains open:

| Owner | Remaining contract work | Why it matters |
|---|---|---|
| `controller_input.cpp`, `gameplay_scopes.hpp`, `guest_execution.cpp` | Qualify remaining player velocity, animation, boss/landing and Floyd control members; confirm game-level camera tick units | These read/write live game state; retrace rate alone does not prove their units or layouts |
| `flying_motion.inl` | Qualify squad control speed/health/spin, velocity vectors, descriptors and the legacy movement timebase | Existing original code bindings and movement math tests do not establish every regional field or reference cadence |
| `navigation_mod.hpp` | Qualify door, NPC, squad and collectible control schemas, remaining model/collision records | Navigation inspects multiple actor-specific layouts, beyond the common actor header |
| Renderer presentation helpers | Complete model/header, sprite/effect control and door-indicator schema ownership | Relocated renderer globals do not qualify every structure dereference |
| Scene/cutscene helpers | Complete the shared level-header field proof; retain explicitly US-only optional music policy | Original regional behavior must remain separate from an optional correction |
| Presentation cadence | Carry exact VI duration through history, blur pairing and RT64 output scheduling | PAL three/four/six-VI intervals currently fail the integer-FPS eligibility rule |
| Product handoff | Current native bundle admission, installation/upgrade and direct-launch checks | A verified source corpus or compile is not an installed, testable product |

Already-qualified residual actor and transition consumers now use their existing
named bindings in flight, frontend, live-task, report and navigation code. The
navigation suite passes after this migration. The first invocation used a wrong
CMake target spelling and never compiled; its log remains retained. Four
historical US heap matrix addresses were removed from the diagnostic seeds;
actual runtime matrix destinations and qualified resident owners supply them.

The private `remaining-host-schema-audit-v23` reconciles the prior 146 textual
leads: 17 changed or disappeared, while 129 remain for semantic review. These
are neither an exhaustive current scan nor a defect count. A separate original
body comparison (`original-control-schema-comparison-v23`) verifies the hashes
of 52 selected control owners per revision: 28 have identical selected memory
operand streams across all three; 24 need individual comparison. Neither stream
equality nor a difference establishes a semantic field contract. Original owner,
base pointer, width and use still require explicit qualification.

The fixed NTSC corrected-reference AI profile remains explicitly NTSC and rejects
other timing inputs. Extending that external-reference diagnostic model requires
separate original evidence; it does not replace the regional hardware device
clock. The renderer startup register seed is replaced by the original VI mode
before display submission. Neither numeric occurrence is proof of a PAL gameplay
failure.

## Regional feature acceptance matrix

This is the intended three-region scope, with current evidence rather than a
percentage. A shared implementation does not make regional behavior verified.

| Feature or contract | Shared implementation | Regional validation still needed |
|---|---|---|
| Original boot, new slot and reload | Original-OS v16 passes all three | Repeat on current enhanced candidate; longer routes |
| ROM/bundle/save identity | Catalog, strict bundle resolver and revision namespaces | Current product install/upgrade/direct-launch handoff |
| Original controls and modern input | Semantic hooks plus qualified player/actor members; scoped tests pass | Live movement, aiming, camera, rumble and controller swaps per revision |
| Navigation and NPC rewards | Checked globals/modules; all three original NPC catalogs parse | Live map/collectible/dialogue behavior, languages and progression |
| Audio and cutscene hooks | Original task transport and regional code/data bindings | Live mixer, transitions, cutscenes and each advertised option |
| Presentation and camera | Explicit renderer layout, original hook guards | Regional camera, shadow, interpolation, blur and UI comparisons |
| Spatial rain wipe | Frame-derived affine matrix/viewport/scissor; NTSC, PAL and scaled synthetic geometry tests pass | Live regional wipe/pixel comparison remains pending |
| Blur optimization | Complete 320x240 command recognition uses regional assets | Other frame sizes remain on the existing general renderer path |
| Native timing/collision/math | Regional operation map; original-reference math, collision, shadow and cache comparisons pass on all three | Current enhanced Play routes and interacting features |
| Remaining binary schemas | Qualified member subset; remaining fixed fields inventoried | Complete ownership/qualification of residual model/control/scene assumptions |
| Campaign and release | No three-region release yet | All characters, transitions, saves, features, timing/performance and host coverage |

### Current native-operation and product checks

`native-math-v21-{us,pal,jpn}` compares 400,000 cases per revision against the
selected original generated routines. `native-collision-v20-*` passes 50,000
cases per revision, full CPU/stack/floating-state comparison, periodic full RAM
comparison, the complete regional collision overlay and unsupported-state
fallback/cancellation checks. The JP split helper retains its own additional
arithmetic; no US replacement body is used. `native-shadow_filter-v20-*` passes
2,048 cases and `native-cache_all-v20-*` passes 512 cases per revision.

The collision/cache/shadow verification tools previously still named US
reference files. They now use the same qualified semantic operation map as
production. The collision fixture composes section identity, entries and global
extent from the descriptor; it maps and compares the entire selected overlay.
These verification-tool changes do not change the frozen v20 runtime source.

The frame-derived spatial fade retains exact mesh/command ownership and rejects
skewed, degenerate or insufficient-coverage projections. It derives affine
screen coordinates from the captured fixed-point matrix and viewport, accepts
PAL's scale without an NTSC TV-byte gate, and validates dimension-derived scissor
commands. Live RDP coverage/rounding comparison remains pending; the existing
original path handles unrecognized geometry.

The current launcher compiles and passes its C# suite, setup checks, native
graphics/viewport/storage checks (`launcher-v20`). Ordinary PAL/JP admission
remains closed pending the current native result and a deliberate local test
handoff; a launcher build alone never changes support policy.

## Previous eight-hour checkpoint

End-of-window checkpoint: **2026-11-01T12:15:00.253266+00:00**. The full architecture goal remains
incomplete. Current source is preserved as v17; the independently frozen v16
native candidate predates its cache-binding and source-identity corrections.

| Layer | US | PAL | JP |
|---|---|---|---|
| Exact original reconstruction and shared CPU/audio generation (v16) | Passed | Passed | Passed |
| Earlier v7 native compile and bundle identity | Passed | Passed | Passed |
| Earlier v7 bounded original-OS boot | Passed, 200 VI | Failed: omitted constant-register exception entry | Failed: split matrix-body metadata loses stack restoration |
| v16 native compile/link | Incomplete; 2907/2929 compile entries logged | Incomplete; 2917/2917 compile entries logged | Incomplete; 2860/2922 compile entries logged |
| v16 bounded native integration | Not completed at checkpoint | Not completed at checkpoint | Not completed at checkpoint |
| v16 original-OS repeatability | Not completed | Not completed | Not completed |
| v16 menu/new-slot exploration | Not completed | Not completed | Not completed |
| v16 same-region save reload | Skipped: insufficient approved time | Skipped: insufficient approved time | Skipped: insufficient approved time |
| Current v17 cache binding and source identity | Component checks passed; fresh native build required | Component checks passed; fresh native build required | Component checks passed; fresh native build required |
| Regional product admission | Existing US policy | Closed | Closed |

Compile-entry counts are progress observations, not completed object or link
verification. Missing native receipts remain incomplete. No build, bounded boot,
menu capture or component test is treated as regional gameplay/release acceptance.
The private `final-checkpoint.json` preserves this checkpoint and its available
receipts; interrupted build directories and earlier failed evidence are retained.

The shared corrections cover constant-register entries, hash-qualified complete
function bodies and alternate-entry branch closure. Current v17 additionally
composes regional cache-address bindings and captures previously omitted native
source inputs in artifact identity. Detailed causes, attempted remedies and
scoped tests remain below. No release or new maintainer commit was created.

## Architecture plan

The owner requested a shared architecture for all three original revisions on 2026-11-01.
The [implementation plan](../../planning/regional-runtime-architecture.md) defines one revision
catalog and generation pipeline, typed game bindings, shared runtime ownership, regional
launcher/save integration and staged acceptance. US migrates onto the same interfaces as PAL
and Japan. Implementation is in progress under the owner-approved guarded job. The plan itself is not runtime or gameplay verification.

## Architecture implementation in progress

The owner activated the full three-revision goal and approved eight hours on 2026-11-01.
Guarded evidence ID: `regional-architecture-20261101`; the same production investigation and
all prior counters are preserved. The initial migration scan records 854 address/identity sites
in 76 source/tool files; this is an inventory to classify, not a coverage or completion claim.
The canonical ROM catalog and separate native-build admission policy are implemented.
All three shared generated corpora pass model, relocation, call inventory and original-OS hook checks. PAL/JP runtime admission remains closed while host integration and gameplay are qualified.
The architecture milestones and gameplay acceptance are still open.

## Original-game evidence

The owner reconfirmed **no music leaving Walkway on NTSC N64 hardware**, then heard music in the
original PAL ROM in EmuHawk after loading Juno in Walkway. PAL hardware and Japanese music behavior
remain untested. This regional difference is not evidence of a native NTSC bug. The copied PAL save
worked in that one review session; it does not prove general cross-region save compatibility.
[Music evidence and rollback](flight-transition-missing-music.md) preserve the original correction.

## Earlier metadata prerequisite stage

[ROM profiles](../../../scripts/build/rom_profiles.py) identify the exact original revisions below,
normalize the three standard N64 storage byte orders for metadata preparation, and reject unknown,
truncated or modified images. The input file is never rewritten. Recognition is distinct from native
runtime admission: both native build entry points continue to reject PAL/JP before generation.

| Profile | Normalized SHA-1 | Matching reconstruction | Executable overlays after bounded expansion |
|---|---|---|---|
| US | `493ced9008dbe932d6e91179b68e8630cf23a023` | Existing US pipeline | Existing qualified US generated inventory |
| PAL | `50651c4e0c46332f7f0b45870263f0a8b9a49602` | Byte-for-byte verified | 155 |
| Japan / Star Twins | `15099233760b36e7afad7da36b9464da1512c4b1` | Byte-for-byte verified | 155 |

[prepare_regional_metadata.py](../../../scripts/build/prepare_regional_metadata.py) clones the pinned
decomp into a new private workspace, extracts original instructions, builds ELF/map metadata and
requires the rebuilt ROM to match every input byte. It writes an explicit `native_playable: false`
manifest with remaining work. No ROM, generated game code, ELF, personal save or capture is committed.
The upstream checkout and dependency pin remain unchanged. The
[overlay metadata helper](../../../scripts/build/regional_overlays.py) reads all 157 linker slots,
requires the expected 155 populated overlays, checks ordered bounds, entry points and relocation
record sizes, and describes original text/data/BSS separately. Relocation lengths are **bytes**;
using them as record counts would overrun adjacent content. No extracted game body is copied into
public source.

Run this prerequisite in WSL/Linux with the normal MIPS build tools installed:

```sh
python3 scripts/build/prepare_regional_metadata.py \
  --rom /private/input/region.n64 --workspace /private/new-regional-workspace
```

The workspace must be new, private and contain no spaces in its path. The command accepts only the
PAL and Japanese hashes above. It is a metadata developer tool, not a Play command or launcher option.

## Actual failures, causes and remedies

The pinned decomp is `b49aa4791e8fb1e7acd3bba10346876358d0a9a7`. Initial stock regional builds failed:
regional object enumeration omitted top-level assembly, common SDK source compilation was unrelated
to the regional linker input, and Japanese C files depended on incomplete regional headers. The
metadata tool enumerates regional assembly and reconstructs C-marked segments directly from the
original instructions. It does not substitute US game bodies or invent missing overlay definitions.

PAL additionally referenced five shared linker aliases whose named asset/overlay segments do not
exist in its basic map. Removing those unused aliases in the private clone permits an exact rebuild;
the asset lookup-table extent remains unqualified. Japanese reconstruction initially differed by
10,605 bytes. Its opaque executable prefix at ROM offset `0x9E4D0` was classified as DATA and moved
after the following audio microcode. Classifying that original prefix as TEXTBIN preserves section
order and produces an exact hash match. The tool checks the pinned input shape before applying this
adjustment; an unexpected future metadata layout fails closed.

Private probes also exposed a helper named `queue.py` shadowing Python's standard module and a
transient WSL `/tmp` workspace disappearing between invocations. Isolated Python execution and
persistent private workspaces resolved those orchestration failures. No production guard setting,
investigation identity or accounting counter was changed to retry them.

## Earlier prerequisite validation and its limits

Before the architecture implementation, the committed metadata tool was run from fresh workspaces against both original regional images.
Both builds pass the upstream SHA-1 check and an independent byte-for-byte comparison. Regional
byte-order, rejection and metadata-boundary tests pass. Private evidence ID:
`reorganization-followups-20261101`, including failed stock builds, mismatch classification and
`regional-full-tool-pal.json` / `regional-full-tool-jpn.json` from the final tool.
The first matching stage exposed only zero PAL overlays and one Japanese overlay; exact byte
reconstruction alone therefore did not establish usable code coverage. The completed expansion
now reconstructs all 155 code overlays in each image, with the same byte-for-byte check.

A further private run with the pinned, patched N64Recomp successfully dumps both ELF contexts.
Each has **157 executable sections** (entry, main and 155 overlays), compared with the current
US transform's 156-section contract. Main relocation tables have 520 entries each; total parsed
relocations are 28,432 PAL and 27,914 Japanese. The generated contexts describe 2,920 PAL and 2,928
Japanese executable function symbols. These are regional inventories, not substitutes for the US
signed denominators or proof that every function boundary is correct.

The pinned maps name 0 of the boot bridge's 69 SDK entry points for PAL and 41 for Japan. A missing
name is missing identification, not proof that a routine is absent from the ROM. No US address is
used as a guessed replacement. The private `regional-context-results.json` records the contexts,
linker boundaries and exact missing-name lists.

This does **not** complete native regional support. Function-boundary qualification, missing SDK
identification, CPU/RSP generation, the regional static-section layout and per-region host hooks
are still required. The US transformer deliberately retains its closed identity and inventory
checks; changing its expected counts would not establish regional correctness. US-specific addresses, bootstrap/timing,
audio and presentation assumptions must be ported and validated, followed by real native boot,
controller/save and normal/skipped-transition qualification. Neither regional ROM was run by the
native recomp during that earlier prerequisite stage. The current checkpoint above records later native attempts. No regional gameplay acceptance, release or support claim is made.

## Audio program identity

A bounded comparison found one exact occurrence in each regional ROM of the complete 6,208-byte
US audio microcode program and its 704-byte companion data. The existing DMA/command-table parser
accepts that shared program layout. Private regional-audio-identity.json records hashes and unique
locations. This narrows future RSP work; it does not qualify regional task submission, timing,
sequence assets or the cause of the Walkway music difference.

## Transferable lesson

Keep ROM identity, exact reconstruction, generated-code coverage, host integration and gameplay
qualification separate. A matching ROM rebuilt from opaque binary segments can have very incomplete
executable metadata. A known hash or successful emulator session cannot authorize using US host
addresses with a different regional image.

## Shared architecture implementation evidence (2026-11-01)

Implementation is active under the owner's eight-hour admission in the same production
investigation; its guard remains enabled. No PAL/JP native Play admission has been enabled.
The revision catalog now generates Python, C++ and C# views, with native build admission kept
separate. Catalog views compile and agree on all three exact identities. Focused catalog/model
tests, the native unit suite and the full managed launcher test entry point pass. The launcher
still uses its US path pending session/bundle and storage migration.

The shared program model reconciles every executable ELF symbol by section, address and extent:
US has 156 sections and 2,911 bodies; PAL has 157 and 2,920; Japan has 157 and 2,928. The US
inventory additionally accounts for 824 covered aliases and 12 recovered zero-size functions.
Six compiler-renamed scheduler labels initially failed a name-based correspondence; preserving
the original labels as aliases and validating their coordinates/extent resolves that mismatch.
This is metadata validation, not evidence that every instruction path or host binding works.

A separate original-ROM relocation decoder validates all 28,035 US, 28,432 PAL and 27,914 Japanese
records, including table bounds, unique patch sites, source domains and atomic HI16/LO16 pairing.
All three have 157 overlay slots, of which two are empty. No overlay DATA-source record occurs
in these exact inputs. Synthetic coverage nevertheless verifies DATA offset zero after text,
including overlays, and rejects writes into BSS/retained metadata (upstream observation JFG-UP-012).
The existing production transformer has not yet been migrated to this decoder.

Correction to the SDK denominator: 69 is the bridge's candidate-name list, not 69 SDK entries
already named in US. The pinned US map names 58; Japan names 41, including one absent from the US
name list. Missing names remain identification questions. Instruction-shape and independent
caller/data cross-references identify regional candidates, including the remaining PAL interrupt
mask and controller-read entries; they are not yet qualified runtime bindings.

A fresh optimized US baseline build is in progress after discovering that the old build cache
points at a missing generated directory. A fresh matching reconstruction and complete US
generation succeeded; no old generated directory was silently substituted or relabeled.
The generation pipeline, typed runtime migration, regional native boot/gameplay, save isolation,
feature qualification and campaign acceptance remain open. Private evidence is retained under
`regional-architecture-20261101`; earlier failed probes and the previous baseline are preserved.


The new shared translator's first private run rejected cross-section JAL records because it
mistook synthetic linker coordinates for simultaneously loaded CPU addresses. All three images
exposed this. Offline rewriting now preserves the explicit relocation target section/offset;
architectural jump-region inference cannot replace that identity. Validation against the complete
US baseline and original record inventories is required before this translator replaces the
production path. The failed receipt remains in the private evidence directory.


The shared compiler input stage emits all three corpora. US and PAL subsequently pass the
independent compiler decision reconciliation. Japan exposed an omitted direct-tail candidate:
a branch-likely instruction crossing a function boundary was present in the compiler sidecar
but absent from the original-instruction scanner. The scanner inherited the US-only assumption
that only ordinary conditional opcodes occurred at these boundaries. It now covers ordinary,
likely, REGIMM and floating-point conditional branches, with synthetic boundary tests. The
per-site validator was retained; Japanese normalization must be repeated against the corrected
inventory. This fixes inventory completeness, not an observed native-gameplay symptom.

### Shared generation and US baseline checkpoint (2026-11-01)

The shared compiler and normalizer now account for US (2,911 bodies), PAL (2,920)
and Japan (2,928), including the JP branch-likely inventory correction recorded
below. Original relocation inventories contain 28,035 / 28,432 / 27,914 records;
the shared US translation is byte-for-byte equal to the established transform.
These are generation checks, not native PAL/JP boot or gameplay qualification.

A fresh optimized US baseline build completed with no source changes during the
build. A preserved copy reached 200 retraces, 79 graphics tasks and 97 decoded
audio tasks with zero unsupported accesses, using fresh private save paths.
The probe explicitly reports acceptance=false and is not campaign verification.
Private receipts: `us-native-build.result.json`,
`us-baseline-runtime/cold-boot.result.json` and `cold-boot.log` in the guarded
`regional-architecture-20261101` workspace. Runtime migration is still open.

The stronger input-contract replay initially stopped during JSON emission because
the new immutable count maps were passed directly to the JSON encoder. The
runtime manifest producer now takes an explicit dictionary snapshot at its
serialization boundary; the contract stays immutable. The failed run is retained
in guarded step 048. This was a build-tool regression, not a game runtime result.

Descriptor integration exposed two different entry concepts: the original US ELF
has no generated function label at the IPL handoff, whereas PAL/JP do. The shared
runtime interprets that bootstrap before entering generated functions. `EntryRef`
now represents a checked resident bootstrap instruction separately from `CodeRef`;
it does not synthesize a callable wrapper or weaken generated-entry validation.

Cross-region reference checks also found a PAL extraction boundary mismatch:
the ELF text/data split excludes embedded RSP bytes that the game's relocation
domain includes. Early PAL generation counts did not detect this semantic error.
Correcting and reproducing that original boundary is required before PAL boot;
the earlier PAL translation is superseded candidate evidence, not qualification.

The corrected original-domain extraction has now reproduced all three inputs,
and all three normalized corpora and C++ descriptors validate. PAL's former
49 conflicting data correspondences dropped to three after the boundary repair;
remaining ambiguities are not admitted as bindings. US translation is unchanged.
The native core now consumes revision-bound SDK/linker bindings, IPL entry/TV mode
and exact ROM identity for v7 corpora. This integration still needs native replay.

During overlay migration, the cold-load observer's range check was found to
reject the final valid slot (157) even though the table resolver/index include it.
The check now rejects slots greater than the declared count. This was a source
boundary defect, not a reported live crash; final-slot regression coverage and
native verification remain required.

The execution-site pass found that PAL merges the scheduler park routine into
another authoritative body. Seven independent original JAL callers identify the
interior entry. The old inventory left those calls unresolved despite preserving
the surrounding body. The shared generator now declares interior entries from
all original direct JAL sites, retains section-qualified relocation identity and
rejects ambiguous unrelocated targets. It preserves whole bodies and emits only
explicit support thunks. The park binding is separate from the 58 SDK names;
neither an invented SDK label nor a body-boundary guess is used. Synthetic merged
body and overlapping-section tests accompany the repair; regeneration and native
validation remain pending for this inventory change.

### Launcher identity and save namespace implementation (2026-11-01)

The existing launcher imports only US and uses one campaign profile. New candidate
contracts normalize the three standard byte orders, identify against the shared
catalog, and reserve isolated PAL/Japanese campaign and navigation namespaces.
Historical US saves retain their exact path and bytes. Regional directories with
unidentified existing saves are rejected; there is no implicit cross-region copy.
These contracts are not yet connected to every launch route, so this is not
launcher or regional gameplay acceptance.

The managed launcher and setup checks passed (708 and 28 checks respectively).
The post-link bundle contract passed four synthetic Python tests, including
a PAL sidecar paired with a US embedded identity, changed dependencies, missing
files, duplicate members and a mismatched selected revision. Managed session
composition now retains read locks on the ROM and runtime files, checks the
binary's own identity, and only then prepares writable regional storage. Both
native-frontend Play/direct-Play and the legacy preview launch call that same
composition. PAL/JP product admission remains closed pending runtime evidence.
The historical pre-regional runtime package needs a new build manifest before
this development launcher can use it; it is not guessed to be US from its filename.

The first integrated managed test run failed in the pre-existing map explorer
close test, before the new bundle tests ran. It also failed fixture cleanup
because a command writer remained active. See the separate
[shutdown record](launcher-explorer-shutdown.md); this failure is not counted
as regional launch verification.

The integrated launcher rerun passed 719 managed checks and 28 setup checks,
including bundle/ROM mismatch, dependency tampering and held file leases.
The first private original-ROM import harness did not compile because the old
.NET Framework compiler interpreted a forward-slash source argument incorrectly.
No original-ROM test ran in that failed attempt. Correcting the private harness
to use a Windows path allowed all three actual ROM imports to pass: canonical
digest/reimport checks, simultaneous private copies, unchanged original SHA-256
digests, isolated profile markers, and PAL/JP admission rejection before writable
profile creation. No personal save or ROM was modified. This is import/storage
evidence; native gameplay remains a separate pending gate.

### Device-clock migration findings

Read-only runtime review found additional explicit US assumptions: the guest VI
path admits only V_SYNC 525/H_SYNC 3093 and a fixed 783520 Count-tick period;
`OriginalTimingAiDma` requires that same period and uses the NTSC video oscillator,
as does the host PCM queue. Merely changing IPL TV mode would therefore reject PAL
or use the wrong audio clock. These are open regional integration requirements.
The pinned libultra `rcp.h` distinguishes NTSC/PAL oscillator constants. The
already-pinned Ares debugger reference is being read for clock ownership and
register semantics; no dependency update, timing-parity claim or shelved
investigation restart is implied. Native boot has not yet qualified a PAL mode.

### Windows identity-query compile correction (2026-11-01)

The first shared US native build failed in `native_boot.cpp`: MSVC rejected
passing a non-constexpr local descriptor reference to the catalog consteval
lookup. This was a host compile error, before any regional runtime probe.
The local reference is now explicitly constexpr; descriptor validation remains
in place. Incremental build and runtime qualification are pending in the
private `us-regional-native-build-v2` receipt. The failed v1 log is preserved.

### Required OS binding migration (2026-11-01)

The shared OS bridge now names the exception preamble, scheduler park, VI
worker, current-thread pointer and FlashRAM handle through original-image
bindings for each revision. Private `kernel-core-binding-proofs-v2.json`
records independent original instruction witnesses. The PAL scheduler entry
is accepted only as the independently inventoried interior callable; arbitrary
interior instructions remain noncallable. Binding ABI 2 separately carries
typed VI instruction sites. Eleven nonmapped initialization helpers remain
original generated calls; the four mapped helpers retain their execution
disposition. Regeneration, compilation and live regional checks remain pending.

The MSVC correction passed in private build v2: executable
`c4fecc2ff5fd2c932bd192961fc2427594a409f09da9c034468fd6c59cd7305b`,
200 retraces, 84 controller samples, 79 graphics tasks, 97 audio tasks and
zero unsupported accesses. Actual binary identity and bundle agreed; a PAL
ROM was rejected before any save file was opened. The cold-boot run had zero
completed gameplay updates and does not establish gameplay acceptance.

Kernel binding ABI 2 then qualified and compiled against all three original
corpora (66 code operations, four data objects and two instruction sites each);
the synthetic C++ contract tests also passed. This is static qualification,
with native execution of the changed kernel bindings still pending.

### Embedded build compatibility key (2026-11-01)

The CMake regional target now prepares an identity before native compilation
from dirty source contents, generated CPU manifest, descriptor and bindings,
RSP outputs, dependency pins and the actual compiler/configuration/options.
The source check runs on incremental builds and preserves the header timestamp
when unchanged. Identity query schema 2 exposes these hashes; the launcher
and post-link bundle validator reject inconsistent composite keys. The final
executable hash remains in the package manifest, outside its own inputs.
Native compilation of this integration and packaged launcher verification are
pending; the earlier v2 cold-boot evidence retains identity schema 1.

### Shared VI and AI clock owner (2026-11-01)

The candidate replaces NTSC-only VI constants with a register-driven scan
clock shared by every revision. It tracks field parity, the five-field HSYNC
leap pattern, fractional Count ticks, current line and interrupt coincidence;
inactive VI has no invented periodic interrupt. PAL inputs use the pinned
SDK video clock, rather than multiplying a US frame duration. AI DMA now
receives the same explicit clock input and retains fractional sample time;
host playback receives that video clock separately and does not drive guest
completion. The old truncated NTSC AI timing and fixed VI reference receipts
remain historical and do not qualify this model. This does not resolve or
reopen the shelved original-mode simulation-parity investigation.

Synthetic VI checks passed for NTSC accumulation, the PAL five-field leap
cycle, current-line/interrupt agreement, interlaced parity, mode changes,
inactive scan and unreachable coincidence. Native integration and PAL/JP
execution remain pending; no physical-console timing parity is claimed.

Identity schema 2 passed the managed launcher suite, including an independent
canonical Python-to-C# compatibility-key vector. Existing import, profile
isolation, bundle mismatch and window-close regressions remained in the suite.
This verifies the managed components; it is not live PAL/JP Play acceptance.

The first private fuzzy hook-discovery pass stopped before comparison because
it requested the retired `relocations.json` member. The current input contract
names this `translated-relocations.json`; the corrected private discovery tool
uses that member. This helper failure made no runtime or binding changes.
Fuzzy candidates remain discovery evidence, not permission to install hooks.

The required storage review confirmed the earlier sector/page mismatch and
additional differences between the historical reference bus and the SDK
command contract. The [FlashRAM issue](flashram-device-contract.md) now owns
that evidence and the required persistence tests. These are shared-service
limitations, not a reason to copy a separate Flash bus per game revision.

### Original debug-print callback inventory gap (2026-11-01)

The resident-code audit found the US ELF/context omits the 20-byte callback
passed by original `osSyncPrintf` to `_Printf`. PAL and JP inventory the leaf.
US currently substitutes a host implementation. The original caller's checked
LUI/ADDIU argument identifies the callback independently of its body hash; a
save-packaging leaf has identical bytes and makes hash-only discovery ambiguous.
Private `resident-gap-proofs-v2/proofs.json` records caller/body hashes and
ROM/ELF byte agreement. The required correction is metadata recovery preserving
every loaded byte, followed by shared generation and removal of the substituted
US callback only after execution is verified. No runtime correction is yet
claimed. Other nonzero resident gaps and non-CPU text payloads still require
explicit inventory dispositions before code coverage can be accepted.

The expanded private recovery qualified 20 missing US resident routines:
17 diagnostic decode routines, motor-data construction, controller-pak page
traversal and the print callback. Independent PAL and JP boundaries agree;
original US control transfers and the bounded switch table were checked. The
US cartridge entry symbol also now owns its existing ELF section. Five
US/JP symbols that represented non-CPU payloads were reclassified privately.
Every loaded ELF section byte and original input remains unchanged. All three
corrected inventories passed shared generation and normalization; this does
not establish that all indirect calls or gameplay routes have executed.
The public extraction pipeline and optimizer filename assumptions still need
integration before this private metadata candidate replaces production inputs.

The first private exception-qualification harness failed before evaluating
inputs because its temporary Windows path was shallower than a repository
module path. Running the same prototype from an appropriate private directory
then reproduced all three existing exception targets from original resolver
and relocation-processor operands. No target or validation rule was relaxed.

The v3 native build reached its 30-minute subprocess limit after generated
CPU and RT64 compilation, while compiling the native host modules. Its failed
receipt and log remain intact. The known project child is stopped before an
incremental v4 resume in the same build directory with unchanged captured
source and generated inputs. This is a build-time limit, not evidence of a
runtime failure or permission to relax the production investigation guard.

The shared metadata qualifier is now project source with reviewed per-revision
recipes. It recovers all 26 US omitted bodies in one stage, owns the existing
entry symbol and classifies the five US/JP non-CPU symbols. Real-input checks
preserved every loaded ELF byte and reproduced the independently prepared
boundaries; synthetic tests reject stale/missing symbols, overflow, malformed
tables and loaded-byte changes. Shared exception qualification now derives
the unresolved pointer from independent original resolver and relocation-
processor witnesses and pins the complete exceptional record set. Public
pipeline integration and regenerated native gameplay are still pending.

The unchanged v4 incremental resume completed in 360.922 seconds. The preserved
runtime is `us-regional-runtime-v4`, executable SHA-256
`19072681b1120ca225c6d629f1545eaea432f8cae2f957bc0d248db5d36d55b5`.
Identity schema 2/binding ABI 2 matched the bundle; a PAL input was rejected
before save creation. The original-OS cold-boot probe reached 200 retraces in
9.016 seconds: 84 controller samples, 79 graphics tasks, 96 audio tasks and
zero unsupported accesses. It recorded zero completed gameplay updates and
`acceptance: false`. This qualifies this bounded US boot path for the new
kernel bindings and VI/AI integration, not gameplay, PAL/JP execution, physical
timing parity or the later metadata-recovery candidate.

A subsequent source audit found the pre-link CPU identity currently hashes
the generated manifest rather than the complete generated source bytes.
Dependency identity likewise records pins rather than actual compiled
dependency content. Final executable hashes still protect a completed bundle,
but those narrower compatibility-key inputs do not satisfy the full M1 cache
contract. Both closures must be corrected before declaring that gate complete.

The native audio source cache now takes revision-bound coordinates. Original
callback, factory, initializer and reclamation bodies independently qualify
the callback, cache heads, 76 nodes of 20 bytes, 640-byte sample buffers, frame
and pending-DMA counters for all three exact images. The shared helper passed
its cache, rejection-without-writes and both-memory-layout tests at two
independently relocated synthetic layouts. This is binding and helper
qualification; live audio/gameplay remain pending. The first qualification
harness loaded the old Python module before editing it and rejected the new
mandatory data set; the fresh-process rerun preserves that failed log and uses
the updated validator without loosening coverage.

New native builds now require the shared v7 descriptor/binding corpus. The
embedded US-address/SDK-sidecar fallback has been removed; historical private
roots receive a regeneration error, while already preserved binaries remain
intact. The sync-print callback host replacement is retired because all three
qualified inventories now contain the original callable leaf. Those calls
execute generated guest instructions. This requires the new metadata corpus;
old v7 corpora cannot pass the current producer/binding checks.

The pre-link identity now hashes every file in the normalized CPU tree,
the compiled RT64 library, native RSP/SDL headers, selected import/runtime
libraries and generated native variants. CMake orders the dependency build
before this snapshot. Bundle publication recomputes the full recorded input
closure and compares it with the executable's embedded key. Synthetic tests
verify changed CPU bytes, changed compiled libraries and changed headers
invalidate identities while their manifest/pin stays unchanged. Native
integration of this stronger key still awaits the next build.

The two interrupt-mask instruction sites are now explicit bound InstructionRefs
for each original SDK body. Their original load/store encodings were verified
in all three ROMs and the source rewrite retains the instruction hooks. A test
fixture initially relocated only lowercase hook PCs, leaving uppercase comment
PCs unchanged; the required consistency check rejected it. Correcting both
representations passed without changing the production check.

The first-run installer now loads the managed launcher ROM validator before
creating build output or installing prerequisites. It shares canonical byte-order
identification and the catalog admission gate; no second US hash is embedded in
the PowerShell installer. Step 130 passed 723 managed launcher checks, 28 setup
checks and three builder admission/save-namespace tests. The builder also uses
exact marker bytes and rejects Windows reparse points without resolving them
away. PAL/JP native Play admission remains closed.

## Fresh common CLI generation and a concrete regional ABI difference

Private step 126 completed the full public generation CLI for all three exact
revisions, with fresh matching reconstruction, patched/built pinned CPU/RSP
tools, CPU normalization and schema-3 generation receipt verification. Results:
US 5,918 normalized files, PAL 5,886 and JP 5,898. The captured producer inputs
remained unchanged. These are generation results, not native gameplay passes.
The next US integration build is testing the shared FlashRAM and complete
pre-link dependency identity; no PAL/JP Play gate has been changed.

Private steps 131–136 investigated the remaining resident host hooks. Unique
instruction shapes are only discovery candidates. Original call-site witnesses
and global accessors disambiguate short functions; body hashes alone do not
prove that two different routines have the same semantic role.

The original rumble routines provide a concrete reason to retain explicit
regional layouts. US `rumbleStart` indexes 10-byte records with packed state,
while PAL indexes 12-byte records with a byte state. Its intensity and duration
fields move accordingly, and PAL multiplies seconds by 50 rather than US 60.
The three-argument call interface remains controller index, intensity and float
duration. PAL's original binary also calls a permission/pause gate, although
the pinned C reconstruction's conditional source alone would suggest that gate
is US-only. The original ROM-derived disassembly is the authority here. JP
counterparts were located and retained for the same review; no physical
hardware behavior is inferred from this static evidence.

The existing host rumble adapter and duration clock still require migration
and tests against the qualified bindings. Do not copy a US record stride,
field guard or nominal retrace rate into PAL/JP. This finding is a compatibility
limitation in the migration, not a newly verified native-N64 bug.

A profile-marker regression check found that .NET text decoding accepted a BOM
that the Python builder rejected. The managed profile reader now compares the
ASCII bytes without encoding detection. BOM and CRLF variants are rejected by
tests, and the exact marker remains shared by both launch paths. Step 146 ran
the managed/setup suites; this changes marker validation, not existing save
contents or their region.

## US native integration and resident semantic migration

The preserved private v5 US runtime built with the shared FlashRAM device and
complete CPU/dependency identity. Its 200-retrace original-OS cold boot recorded
84 controller samples, 79 graphics tasks, 96 decoded audio tasks and zero
unsupported accesses. Its optional completed-update hash counter was not
enabled; this is a bounded boot probe, not gameplay acceptance. Bundle recomputation passed, and the PAL ROM
was rejected by this US executable before save/pak creation. Private receipts:
`us-regional-native-build-v5.result.json` and
`us-regional-runtime-qualification-v5.result.json` under the regional workspace.

The native resident dispatch now resolves 133 game entry points by semantic
name from exact original body recipes for each revision. Identical short bodies
require an original direct-call anchor; ambiguous, absent, non-call and cyclic
anchors fail qualification. All three staged descriptors compiled and validated;
four negative anchor cases were rejected before installation. This does not
qualify host assumptions about data layout or optional behavior.

The unreachable SDK-name branches naming generated `fn_044` functions were
removed: none of the immutable regional SDK catalogs contains those CIC names.
Original guest CIC code remains in generated execution. No successful stub was
introduced. First-run validation was also exercised through the actual managed
assembly/PowerShell boundary with all three original ROMs: US reached a test
prerequisite stub; PAL/JP were rejected before output creation. No installation
or personal save change occurred in that boundary test.

The producer freshness identity now follows transitive local Python imports,
explicit subprocess entry points, catalog recipes, locked compiler patches and
RSP/timing templates. The former hand list omitted imported helpers such as
`native_program_identity`; this could admit a stale generation root after a
helper edit. The first closure scan rejected an intentional CLI compatibility
shim as ambiguous; the corrected resolver follows the real `scripts.__path__`
search order. Existing roots remain evidence and require fresh normalization
before a new build with the expanded closure.

Resident scalar/pointer consumers now use named data references derived from
original operand pairs inside qualified owner bodies for each ROM. Thirty-nine
new references were selected, including rumble permission, pause and controller
port ownership; array/structure views with unproved extents were excluded.
Original model qualification passed all three revisions before the recipes
were installed. Shared helper headers and remaining structure/instruction-site
consumers still require migration; this is not full game-state qualification.

The host rumble envelope now requires an explicit timebase and uses the
shared Count frequency in native execution. Its second-based request duration,
four-second continuous limit and one-second cooldown no longer assume 60
retrace ticks. Synthetic tests cover 50 Hz, 60 Hz and 46.875 MHz clocks,
including expiry/cooldown boundaries. Native hooks use qualified function and
scalar bindings while original guest code retains its regional record layout.
Physical controller response in PAL/JP remains unverified.

The portable package producer now accepts one to three verified revision
bundles and places each under `runtimes/<revision-id>`. The schema-2 package
index pins each bundle manifest; CRT and game-library hashes are rechecked
after copying. Duplicate/relabelled inputs and closed native admission are
rejected before output creation. Synthetic three-region packaging uses an
isolated admission fixture; the operational PAL/JP gates remain closed.

[Overlay ownership migration](regional-overlay-ownership.md) now resolves named
original module IDs through each descriptor. This removes generated ordinal
assumptions from the migrated native consumers. Module-internal layouts and
return sites remain open and must not be inferred from this owner change.

The optional native CTest verifier now uses a regional evidence adapter instead
of an undefined legacy SDK-identification path. It checks ROM, embedded program,
generated tree, descriptor/bindings and source identity before running, and
requires explicit matching ROM/revision fields in the emulator checkpoint.
Historical Phase 6 receipts and their verifier remain preserved. Synthetic
identity tests passed all three target shapes; new matching emulator checkpoint
captures are still required before claiming regional oracle parity.

The migrated named scalar reads now use `ResidentMemory` with typed `DataRef`
values. Each access checks revision, resident section owner, domain extent,
alignment and the current RAM span. Three independently relocated synthetic
layouts passed, along with cross-revision, overlay, truncated and out-of-extent
rejections. This view does not translate raw US addresses. Remaining raw
structure/header consumers are still tracked as open migration work.

The cutscene sound-omission boundary now consumes typed regional state,
function, instruction-site and handle-array references. Original interpreter
and cleanup bodies prove the three call ABIs, sixteen word handles and actor
handle offset in US/PAL/JP; JP call offsets differ by one instruction. An
initial generic instruction-block alignment did not identify the PAL calls;
the follow-up classified the exact semantic call targets and their argument
setup instead, retaining that failed discovery log. Full original-body
qualification replaces the former partial US entry-opcode guard; the live
caller still must contain the exact JAL to its bound target. Relocated helper
tests pass, with live regional skip/audio behavior still pending.

Twenty-five additional scene/controller scalar bindings were qualified,
including current level, level header, pending transition, script state and
controller disable. Their native scalar readers now use the typed view.

Shared navigation/gameplay memory now requires an explicitly composed regional
descriptor and binding context; raw hardware memory has its own view. Native
composition injects the linked revision, while historical tests explicitly
construct synthetic fixture contexts. Fifty-seven qualified shared scalar
reads and player-port lookup use semantic names with typed extent checks.
The first compile exposed three remaining constructions in the flying adapter;
those now receive the same explicit native/test composition. Relocated actor
list and gameplay-state tests cover all three catalog identities, with missing
bindings, wrong revision and truncated memory rejected. Remaining instruction
guards, arrays and structure layouts still require regional qualification.

Shared navigation guards now use qualified instruction references and original
words from the selected revision, rather than comparing US addresses and US
address operands. Forty-five sites were matched inside uniquely qualified
original owners, including camera, player transitions, collision accessor,
hang/grab and boss dispatch. Binding ABI 3 carries the original instruction
word; the package and launcher reject the old ABI for new builds. A first
qualification attempt rejected differing regional symbol names; semantic owner
names are now shared while each owner retains its own exact original hash.
Existing navigation and relocated memory tests pass; live feature acceptance
and the remaining unbound sites are still open.

The shared navigation header no longer reads game globals or resident guards
through US addresses. Original initializer/accessor bodies qualify four camera
records, four multiplayer records and their inventory subrange, sixteen weapon
object IDs, and twenty-five four-byte exit conditions. The historical scanner
continues using its first fifteen weapon IDs. Player-list ambiguity was resolved
through independently bound list/count operands; sidekick ownership through an
original mapped caller. Scalar transition/sidekick pointers and camera collision
track access also use the regional context. Structure fields and live regional
feature behavior still need the remaining acceptance work.

The native control-table migration now qualifies both original nine-word tables
through the regional player dispatcher and exact original content hashes before
scoped writes/restoration. A changed content fingerprint is rejected. The sine
entry exposed a real inventory difference: US has an alternate entry inside its
84-byte cosine body, while PAL/JP split the entry into its own body. Each now
uses its actual original owner, anchored by the same semantic math call.

The scene transition handler has no direct resident caller or plain initialized
pointer in the searched main image. Its qualification therefore checks nine
independently bound semantic callees and the independently bound transition
prompt, in addition to its exact original body. Native return/instruction sites
are migrating to that evidence. Three sidekick return sites remain open after
one PAL alignment contained too few instructions for the generic matcher.

The immutable v6 native builds compiled their generated game corpora but failed
at two bridge observers: the migration had requested `osAiSetNextBuffer` from
the SDK interception map even though it is an original-code observation point,
not an intercepted SDK service. All three builds expose the same omission.
The bridge now uses a separate `audio.ai_submit` code binding, qualified by its
exact original body and AI-register writes; it does not add an HLE interception.
A generation-time native-consumer check now rejects missing named code, data,
instruction and OS-observer dependencies before the expensive compilation.
The v6 failures remain preserved; the corrected native build is still pending.

The three remaining sidekick return sites now bind through the qualified
original sidekick owner, with original calls to the independently bound
controller/math operations and exact argument delay slots checked in all three
ROMs. PAL moves the flight return by 28 bytes; no common delta is assumed.
The first qualification rejected a mis-transcribed floating-point store register;
using the actual original instruction passed all three models.

A stock-input US v5 exploration exposed a diagnostic limitation: the original-OS
path accepted `--probe-polls` but had no termination gate at that boundary, so
execution exceeded the requested count and ended by watchdog (exit 4). The
candidate now stops after the original `osContStartReadData` body returns and
reports a poll target separately from a VI target. Native integration of this
correction is pending; the exploratory replay is not gameplay acceptance.
Private evidence: `stock-new-save-us-v5-v1` under the regional workspace.

The current Windows contract suite passed fifteen selected C++ targets, and
178 Python build tests passed with four skips (`regional-contracts-v12`). The
FlashRAM fixture narrowing warning and private orchestration encoding failure
are preserved separately from runtime behavior. Full launcher v10 validation
passed 732 managed checks, 28 setup checks and native frontend/storage checks.

The source hygiene scan identified its sole new payload match as thirteen
standard MIPS primary-opcode numbers in the address-reference validator. The
existing exact-body review catalog now records that false positive. The source
scan passes; a changed-body negative check remains rejected. No path-wide or
credential exception was added. All 292 local links in changed documents were
valid.

Exploratory stock-controller replay on the preserved US v5 candidate created
a fresh private slot and reached the opening cinematic, confirmed by a frame
capture. Earlier captures stayed in name entry; the corrected route uses the
original keyboard index wrap to select END. These are route-development
observations, not current-build gameplay/save-reload acceptance. Private evidence:
`stock-new-save-us-v5-v1` through `stock-new-save-us-v5-v4`; the v1 poll-target
run ended by watchdog, while subsequent VI-bounded probes exited normally.

Reviewing cinematic replay found a remaining 60 Hz assumption in the optional
cutscene-skip confirmation gesture. Original-OS replay now derives elapsed
milliseconds from the same explicit Count clock as SI/VI device scheduling;
physical live input retains the monotonic host gesture clock. The historical
cooperative replay uses its selected nominal frequency explicitly. Overflow,
fractional boundaries, long captures and 50/60 Hz conversion passed Windows
clock contract tests. Native/regional skip integration remains pending.

Static review found a direct-launch data-isolation gap: Python/C# profile
selection validates `rom-revision.txt`, but native `--rom/--save/--controller-pak`
startup and the legacy native profile reader did not consult that marker. A
direct invocation could therefore open a profile already marked for another
revision, despite the correct ROM/executable check. No personal save corruption
was observed. The native boundary is being corrected to inspect both storage
paths before either is opened; malformed or mismatching markers must reject.
Unmarked diagnostic files remain separate from regional normal-Play admission.
The v9 source snapshot is preserved as superseded before its final full build.

The native startup candidate now inspects both save-device profile markers
after ROM validation and before backing allocation or any save/pak access.
Existing mismatching, malformed, oversized and non-file markers reject even in
diagnostics. PAL/JP normal Play requires a marked persistent profile; explicit
unmarked diagnostic files and legacy US files remain supported without assigning
a guessed identity. The launcher/build tool still owns marker creation/migration.
Windows synthetic tests passed all three owners, cross-region rejection,
missing/invalid markers and read-only behavior. Native executable checks remain
pending. This does not identify the region of an arbitrary unmarked raw save.

The preserved US v5 route subsequently created a slot, completed the supported
intro-skip sequence and reached Goldwood's arrival cinematic. A new process
loaded a copy of that freshly created FlashRAM file and reached Goldwood gameplay
with Juno and the HUD visible. The initial/final copied save digest matched,
and both VI-bounded runs exited with zero unsupported accesses. These are scoped
observations of the retained v5 candidate, not acceptance of v7/v10 or PAL/JP.
Private evidence: `stock-gameplay-us-v5-v1` and `stock-save-reload-us-v5-v1`.
The `completed_updates` probe field counts only when update-hash capture is
enabled; its zero value in these runs must not be interpreted as no game updates.

The v7 native bridge preflight passed all three revisions and full compilation
is ongoing. The v8 preflight also passed all three after the poll-boundary and
overlay-code migration; it was superseded before a full corpus build. The v9
source was preserved but superseded before its full build when the native save
namespace gap was found. The v10 source is frozen with both the shared replay
clock and native storage admission corrections. Compilation and exact native
integration results remain pending; no regional product gate was opened.

The v10 Windows native preflight found C4996/C2220 in the new pre-storage
namespace validator: it used `std::getenv` in a Windows-compiled branch, unlike
the existing startup code. The candidate now uses Windows `_dupenv_s` with
scoped ownership and keeps the portable `std::getenv` branch elsewhere. The
warning policy remains enabled. Namespace fixture tests had passed but did not
compile this live bridge module; this is why the full native preflight remains
a required gate. The failed v10 source/logs are retained, and a corrected v11
snapshot will repeat native compilation and storage-admission integration.

### Remaining host integration audit

A focused scan after the typed-binding migration found 139 absolute literal
occurrences (94 distinct values) and 297 relative-layout lines in native host,
mod and runtime headers. These are occurrence counts, not bugs or completion
percentages. Context review classified the absolute matches; instruction words,
display-list fields and hardware/tag bounds are excluded from game bindings.
The private receipt `remaining-regional-host-assumptions-v3-classified.json`
pins each reviewed source line and file digest. This narrower scan does not
replace the full M0 inventory, which also covers scene IDs, generated profiles,
small numeric section indices and indirect layout assumptions.

| Remaining responsibility | Current consumers | Required replacement and acceptance |
|---|---|---|
| Modern character movement/animation/camera | `controller_input.cpp`, `gameplay_scopes.hpp`, `guest_execution.cpp` | Qualified character callback bindings and field layouts; each character's ground, air, swim and crawl paths per revision |
| Pointer menus and feedback | `controller_input.cpp`, `guest_execution.cpp` | Revision-owned title/save/pause/options fields and live overlay leases; pointer selection and native sound on each regional menu |
| Navigation and cutscene completion | `guest_execution.cpp`, navigation headers | Bound enemy/run handlers and transition flag/layout; ordinary and skipped transitions, map actions and native behavior comparisons |
| Optional host-clock and optimized paths | `flying_motion.inl`, `guest_execution.cpp`, generation profiles | Replace remaining code/data tokens and source-section ordinals; qualify audio demand, flying motion and shadow filtering independently |
| Diagnostic evidence | `runtime_reports.cpp`, `runtime_diagnostics.cpp`, trace scopes | Bind RNG, camera/global hash spans and trace fields before accepting regional semantic-hash comparisons |
| Historical cooperative backend | controller observations and thread-mask check | Bind the remaining OS policy/controller fields and qualify that backend separately from original-OS native execution |

The flying-motion resolver still contains a literal generated-section index;
PAL/JP's extra entry section makes that an outstanding ownership assumption.
Existing named `OriginalModule` migrations therefore do not establish complete
coverage of every consumer. Most other relative-layout candidates belong to
navigation and menu/character structures; equal field offsets need original
regional evidence, not merely successful compilation. Public native builds
keep `JFG_NATIVE_PLAY_OPTIMIZATIONS` off by default; the optional optimized
profile has additional US-specific contracts that remain unqualified.

All M0-M6 exit gates remain open. Product admission stays closed for PAL/JP;
none of this audit changes a regional support claim or marks campaign/feature
qualification complete.

The focused absolute-literal review classified 56 feature-binding occurrences,
65 diagnostic observations, ten cooperative-backend observations, one
cooperative-backend contract and seven non-binding constants. These figures
cover only that scan; the 297 relative-layout lines and the broader M0 inventory
are not thereby qualified. The v10 preflight subsequently failed all three
regions on the same Windows environment API warning; the corrected v11 source
is frozen and building. Its private configuration explicitly disables native
Play timing, collision and generated optimizations, so its results must not be
presented as qualification of the released enhanced Play profile.

### Original-OS probe protocol correction

A verification review found that the new poll-stop producer added fields and a
stop reason while the parent-process parser still required the older retrace
record. It would reject a successful updated child. Separately, a three-VI
request selected the historical cooperative checkpoint even under original OS;
a retained US v5 run reproduced parent exit 3 with a zero child exit, four VI
interrupts and zero HLE-created threads. Step 225's initial expectation of a
later Python M2-schema error was wrong: the parent rejected the record first.
The evidence is retained; no regional oracle acceptance was issued.

The candidate now uses one typed original-OS observation contract for producer
and parent validation, checks the exact requested poll/retrace boundary, rejects
unsupported accesses and inflated acceptance/snapshot claims, and selects the
original-OS record even at three VIs. Historical cooperative checkpoint parsing
remains separate. Native integration is pending the corrected source build;
this protocol is bounded smoke evidence, not gameplay or emulator parity.
The regional Python verifier still needs an explicit original-OS smoke mode;
its old Phase 6 delegate cannot qualify this backend.

Windows tests pass the shared original-OS probe contract, including three VI,
exact poll stop, CRLF normalization, mismatched targets, counter overflow,
noncanonical numbers, extra records and false acceptance claims. Parent routing
now selects the requested backend explicitly; it cannot accept a cooperative
record as an original-OS result. The v11 build was superseded before native
qualification after this defect was found. A v12 snapshot includes both this
protocol correction and the Windows namespace fix; native integration is pending.

The regional verification CLI now defaults explicitly to bounded original-OS
smoke: verified bundle/corpus/source identity, fresh private storage, neutral
input, exact retrace boundary, repeated complete observation comparison and
retained failure logs. Its receipt explicitly denies oracle parity, full
snapshot and gameplay qualification. `--backend cooperative-phase6` retains
the separate historical oracle path with an explicit backend environment.
Synthetic backend, boundary, counter/type, duplicate-record and inflated-claim
checks pass; current native execution is pending v12. This verification-only
change leaves the frozen native source closure unchanged.

### First complete three-region native build results

All v7 executables compiled, linked and passed bundle/source identity checks.
Each rejected a wrong-region ROM before storage. The US 200-VI original-OS
probe passed with zero unsupported accesses. PAL instead trapped on an unresolved
resident generated target inside a known body; JP trapped on a native memory
access while executing a resident function. Neither region reached the bounded
boot target, and their queued menu explorations were skipped. Build success did
not establish boot support. The exact targets, executable hashes and original
function coordinates are retained privately in the v7 qualification receipts.
Root causes and remedies are under investigation; PAL/JP admission stays closed.

### PAL exception entry inventory omission

The PAL v7 unresolved call is an original exception preamble that constructs a
constant address with LUI/ADDIU and jumps through that register into its own
body. Direct-call, branch and alias discovery did not inventory this interior
entry. The shared inventory now recognizes contiguous LUI plus ADDIU/ORI plus
JR/JALR witnesses, requires unique original body ownership and emits an alternate
entry while preserving the full original body. No region address override or
generated-source patch is used. Synthetic checks and fresh compiler generation
are required; native PAL boot validation remains pending.

### JP matrix body split causes the first native crash

Focused original-OS register traces localized an eight-byte stack imbalance to
mathMtxCatF. JP ELF metadata described its first 180 bytes and the following
84-byte internal entry as separate sized functions. The first generated body
therefore ended before its original stack restoration. Its full 264 original
bytes are identical in US, PAL and JP. The metadata qualifier now supports
explicit, hash-proven shared bodies: it extends the owner and retains the second
symbol as a zero-size interior alias, with all loaded bytes unchanged. The JP
semantic binding now requires that full body. This is a candidate remedy;
fresh generation and native boot verification remain required. No null-pointer
guard or forced register restoration is used. Initial diagnostic input omitted
the required hexadecimal prefix and was rejected before execution; corrected
private traces established the call chain and stack change.

The conservative original-body control-flow audit also found three cosine
prefixes in each of PAL and JP represented as four-byte bodies before their
sine entry labels. These are the same class of lost fallthrough: each original
prefix adjusts the angle then continues through the sine routine. The same
shared-body metadata mechanism now retains each complete body and its sine
entry alias. Cosf/Sinf bindings retain their distinct entry offsets and original
caller witnesses. The audit additionally flagged explicit BREAK bodies, a
nonreturning US thread-cleanup call and a JP NOP label in padding; these are
separate classifications and are not claimed as additional fixed runtime bugs.

The v7 US menu replay also reached the opening ship cinematic, with a visible
skip prompt and a newly written private save matching the retained fresh-slot
route. Its 6,000-VI run reported zero unsupported accesses. This is US candidate
menu/save evidence only; it does not qualify PAL/JP or the latest source.
The corrected shared-body candidate is frozen for all three regions; bounded
cold boot, exact poll stop, namespace checks, repeatability and menu exploration
are queued under the existing production supervisor.

Generated review of the JP shared-body alias exposed a second inventory gap:
a backward branch local to the full body becomes an external tail transfer from
its suffix entry. Generation now closes branch destinations across all generated
entry suffixes until no new entry is required, retaining original body extents.
The synthetic backward-branch case previously had an unresolved destination;
it now has a section-qualified callable target. Native verification is pending.
Attempted reuse of Linux temporary reconstruction/compiler files failed after
their lifetime ended. Fresh regeneration uses persistent private scratch storage;
failed reuse receipts remain preserved.

The final corrected input audit preserves the union of original executable body
bytes and every original function entry in all three images. PAL's constant
exception entry and JP's matrix backward-loop entry are explicit callables;
all inventoried direct targets resolve to an authoritative body or alternate
entry. The 75-test regional suite, two added edge regressions, source hygiene
and frozen native-source correspondence pass. This establishes input closure
for these corrections; actual execution remains a separate pending gate.

A private compiled regression now reproduces the JP matrix failure using the
actual retained generated functions. The old 180-byte-body output executes 45
observed instructions, leaves SP eight bytes low, leaves the saved FPR unrestored
and produces an incomplete matrix. The corrected full body executes 245
observed instructions for the identity-matrix fixture, restores SP/FPR and
produces all 16 expected values. Restoring a captured interior-entry state and
calling the corrected alias also completes the backward loop and restores the
stack. Receipt: `jp-matrix-generated-regression-v16-cxx3/result.json`.
This is a private generated-function semantics regression with an observation
host; it does not model scheduling/devices or qualify native boot/gameplay.
Earlier harness attempts hit the generated C hook macro, then C/C++ linkage,
then the observation-host state symbol; those failed logs remain preserved.
No generated function source or original instruction was edited for the test.

### Instruction-cache overlay address binding correction

The original-OS cache model still read the US runlink table pointer in both
its generated fast path and host slow path. Comparing the exact qualified
bindings gives US `0x800FEAA0`, PAL `0x800FE500` and JP `0x800FE9C0`.
This affects the physical address used for modeled overlay cache costs;
boot success alone cannot establish correct regional timing. The fixed slot
holes were another implicit dependency, even though those holes currently
agree across the three inputs. This consumer was outside the narrower host
literal scan above and remains part of the full M0 coverage requirement.

The correction composes the table-pointer offset, original slot membership,
record stride and RDRAM extent from the existing linked descriptor/bindings.
Both paths call the same bounded address translator. No revision switch,
default US pointer, source-section ordinal or original-code patch is used.
Uninitialized/unmapped guest allocations retain an explicit unknown-address
observation. Invalid pointers, holes, overflowing record offsets and translated
RDRAM overruns cannot produce an out-of-bounds host read.

Windows/MSVC and Linux/GCC component checks pass: distinct explicit table
locations with a conflicting legacy table, absent slots, missing composition,
address boundaries, 250,000 differential cache transitions, 65,536 native-path
boundary cases and 65,536 bounded span/prefix comparisons. Private evidence:
`regional-cache-binding-v17/`. These tests qualify the shared translator and
clock invariants, not original hardware timing or native regional gameplay.

The running v16 source snapshot is immutable and predates this additional
correction. Its pending boot/menu results apply only to that frozen source.
Current source now requires fresh CPU generation, native rebuild and all
regional replay checks; no v16 artifact is relabeled as the current source.
The regional generator already uses hash-qualified scheduler/idle sites in
`regional/execution.py`; the legacy timing helper's US site constants are not
the shared generation path. PAL/JP product admission remains closed.

### Native source identity coverage correction

The source identity capture used a suffix allowlist that omitted the included
`flying_motion.inl` implementation and local HLSL shader sources. A source-only
change in one of those files could therefore leave that part of the compatibility
key unchanged. Compiled dependency hashes do not replace complete source
provenance. The correction captures all files under the declared native source
roots, excluding Python bytecode/cache residue instead of guessing future input
extensions. Existing path containment and missing/duplicate input checks remain.

Regression tests change inline, shader and previously unknown source extensions
and require identity invalidation; bytecode/cache residue does not invalidate
source identity. Source and producer identity tests pass. Private evidence:
`native-source-closure-v17/result.json`. Historical v16 manifests remain immutable
and use the older coverage; their retained full source snapshots still preserve
the omitted files. They are not proofs of the corrected identity contract.
Fresh native generation/build and bundle verification remain required.

The exact native timing-composition function was additionally compiled and run
against all three retained linked descriptors with synthetic RDRAM. Each selects
its own qualified pointer, preserves the original 155 populated module slots,
and gives identical fast/slow address results. The first standalone harness
lacked the generated ROM-catalog include path; the corrected harness includes
that existing build output. Both attempts are retained under
`regional-cache-composition-v17*`; no production source change was needed for
that harness failure. Final current-source checks pass 77 regional Python tests,
nine identity/legacy timing tests, repository hygiene and whitespace validation.
Current source is retained as v17; four native/generator files differ from v16.
These component results still do not constitute a v17 native build.

### Remaining work at the approved-window cutoff

All M0-M6 exit gates remain open. Continue with fresh generation/build of the
preserved current source and exact regional boot/storage/probe validation, then
same-region new-slot/reload and actual gameplay/transition evidence. Finish the
remaining character, pointer-menu, navigation, diagnostics and optional-profile
binding/layout migration before feature acceptance. Controller, audio, campaign,
performance, installation/upgrade and release review require their own evidence.
The current component checks pass; they do not close those gates. The guarded
execution allowance is separate from goal completion and must not be reset or
bypassed to continue this investigation.

The four-hour continuation moved 28 remaining feature code identities to
regional body-qualified bindings (character controls/animation, menus, flying
movement, shadow filtering and instruments). Correspondence uses original
module ownership, unique whole instruction shapes or aligned bodies with
independently named semantic callees through the original relocation records;
the shadow difference is three trailing padding words. The shared flying hook
now resolves the original collision module rather than a US source index.
Consumer coverage now includes boot inline files. Original-model qualification
and recipe tests passed; current native build and feature behavior are pending.

Regional menu, animation-family and flying-state fields now resolve through
original relocation operands in exact hashed owner bodies. Generation rederives
those relocations from the original ROM, rejects wrong modules/domains and
checks field extents and immutable table content. PAL/JP title, settings,
character tables and collision state differ from US. JP additionally moves the
second pause counter into resident state and widens it from 16 to 32 bits; all
three original initializer/counter references identify that same owner change.
The consumer reads the declared owner/width rather than a region-name branch.
Overlay views require the active runtime owner and checked descriptor extent.
The audio frame queue is identified at its original SDK initializer, with its
valid-count field checked against the SDK ABI. Feature live tests remain open.

### Four-hour continuation checkpoint — 2026-11-01

The retained v16 candidates now pass original-OS cold boot, wrong-ROM and
namespace rejection, exact poll-stop, fresh private save creation, and
same-region save reload on all three revisions. Screenshots were inspected:
all three reloads reach Juno in the Goldwood opening walkway with a HUD.
Two repeated 200-VI neutral runs pass for each revision. The initial PAL/JP
smoke attempt rejected byte-swapped .n64 inputs in the smoke verifier; rerunning
with the independently normalized originals passed. This was a verifier input
format failure, not a runtime failure. No owner manual playtest is recorded.

Current source goes beyond v16: original-relocation-derived overlay data,
JP's resident word-sized pause statistic, instruction-derived object members,
and explicit dialogue/Floyd layouts replace additional US coordinates.
Eight MSVC component suites pass after those changes. The first flying adapter
fixture compile failed because new binding helpers were absent; the corrected
fixture deliberately uses unrelated module/field coordinates.

A further implementation gap remains in enhanced Play generation: collision,
shadow, cache and device-access variants still selected old US generated
filenames and hashes. They require revision-bound semantic source selection,
then fresh complete native builds. v16 has those enhanced paths disabled and
does not qualify current source or full Play support. Evidence remains private
under regional-architecture-20261101-continuation; no released resolution.

The wider enhanced-profile audit found additional US coordinates in shared
renderer helpers (presentation identity, camera precision/LOD, shadow staging,
blur and rain/fade), outside the first native-host scan. They remain required
implementation work, not manual verification. In addition, device-variant
dispatch assumed resident source section zero; PAL's main section is one.
That ordinal gate is removed in favor of resident ownership plus the exact
revision-bound operation dispatch. Renderer data-owner migration is underway.
The v18 frozen candidate predates these further renderer changes.

## Manual testing regressions, 2026-11-02

The owner reports Modern Aim-release camera snapping, PAL backward body tilt,
PAL name-entry keyboard cadence and PAL Vela rescue blur. Earlier boot,
action-delivery and save passes do not establish those visual behaviors.
The [Aim-return candidate](modern-aim-release-camera-snap.md) passes components
but its full native rebuild fails within the guarded resource envelope.
The [backward-pose correction](pal-modern-backward-body-tilt.md) restores a
distinct body-bank binding accidentally replaced with camera delta; original
US/PAL/JP binding qualification and focused regressions pass, full native/live
verification remains pending. Baseline PAL and US both retain the unwanted bank.
[Keyboard capture](name-entry-key-animation-cadence.md) confirms partial scene
interpolation while presenting near120FPS; exact key ownership remains open.
[PAL Vela rescue blur](vela-rescue-cutscene-stutter-resolution.md#pal-owner-regression-2026-11-02)
requires its own captured draw-path diagnosis and regression test.

These source candidates are newer than the immutable v28 runtime/v30 launcher
handoff. Current source and producer fingerprints differ; do not label the
old compiled candidates as containing these fixes. No all-regions visual
acceptance, native replacement, push or release is claimed.

## Presentation regression handoff, 2026-11-02

Local `owner-review-v31` supersedes the v30 test handoff for these corrections.
It combines the unchanged v30 launcher with newly qualified US/PAL/JP native
runtimes and separately copied owner settings/saves. Full builds and normal
name-entry replays pass; each scene fully interpolates all 41 key draws.
The shorter PAL/JP native blur operation now passes the shared recognizer and
original-emitter consumer regressions. The earlier Modern Aim-return and body
bank corrections are also linked. Their live behavior and PAL/JP rescue
appearance still need owner review. No release or whole-campaign acceptance
is implied. See [keyboard evidence](name-entry-key-animation-cadence.md),
[rescue blur](vela-rescue-cutscene-stutter-resolution.md) and the resolved
[enhanced-build compiler pressure](build-blur-audit-compiler-memory.md).

Two private handoff-assembler errors were rejected before delivery: assuming
US used a regional subfolder (its canonical save root remains the profile),
and supplying source-build manifests without the portable CRT closure. The
helper now derives the save root from the existing profile contract and uses
the established portable runtime manifest/verified dependencies. Actual managed
init/setup succeeds for all regions; original profiles and earlier failure logs
are preserved. These were assembly errors, not new game-runtime regressions.

The final packaged launcher also starts the correct new native executable and
closes normally for each revision in isolated, explicitly muted profiles.
The handoff saves remain unchanged. Receipt: `launcher-smoke-v31.result.json`.

## Owner PAL retest and Aim-return replacement, 2026-11-03/04

The owner confirms the name-entry keyboard, rescue blur and backward body tilt
fixed on PAL with a controller. Modern Aim release remained instant in v31.
The [Aim-release record](modern-aim-release-camera-snap.md) documents the failed
candidate, actual missed camera-ownership path and replacement.

The shared replacement builds in US/PAL/JP and passes two actual emitted-view
controller returns in every region, plus a separate PAL mouse/quick-reaim replay.
Local v32 combines those runtimes with the existing launcher and copies of current
v31 profiles. Owner visual retesting of Aim remains pending; the three accepted
PAL fixes do not imply full regional campaign or independent US/JP visual acceptance.

The completed v32 package also passes actual launcher init/setup/direct Play
and normal close for every matching runtime in isolated muted profiles.
The handoff saves remain unchanged. Evidence: launcher-smoke-v32.result.json.
Owner visual confirmation of the new Aim return remains pending.

## Final scope-out boundary handoff, 2026-11-04 UTC

v32 was rejected for an initial jump followed by smoothing on PAL/controller.
The [Aim record](modern-aim-release-camera-snap.md) preserves the owner capture,
rejected intermediate candidate and final onset/collision-ownership correction.
The owner approves smooth scope-out and natural scope-in on PAL/controller.
All three regional native regressions pass; USA/JP manual testing remains pending.
The local v33 build is unreleased.
The v33 package preserves the previously accepted keyboard, rescue-blur and
backward-pose changes. Full campaign and independent US/JP visual acceptance
remain separate from these targeted native checks.
