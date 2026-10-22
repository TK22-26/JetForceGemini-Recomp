# RENDER-016: GitHub #25 Ally X cutscenes, homing reticle and rain

## Delivery and issue status — 2026-10-22 UTC

Rain and reticle presentation and the brief room-entry rain delay are released in v1.4.0 after local owner approval. The approved reply closes #25 and invites a new report if any symptom persists. Ally X hardware retesting and the separate hut slowdown are not claimed as verified fixes.

[Release v1.4.0](https://github.com/TK22-26/JetForceGemini-Recomp/releases/tag/v1.4.0); [verified issue action](https://github.com/TK22-26/JetForceGemini-Recomp/issues/25#issuecomment-6332070678).
Earlier entries below preserve their original investigation and verification scope.

- Status: PARTIALLY RESOLVED LOCALLY: owner confirms the unreleased timestamp correction restores missing rain/reticles and approves the replacement spatial-fade preview as fixing the Tawfret rain delay. Release, original reporter/Ally X retest and hut performance remain open.
- Report: https://github.com/TK22-26/JetForceGemini-Recomp/issues/25
- Hardware: Windows 11, Xbox Ally X; no support ZIP or recording attached.
- Severity: substantial cutscene slowdown and missing gameplay/weather visuals.

The reporter identifies large slowdown during the first-level hut tribal
cutscene, missing reticles for weapons including homing missiles, and missing
rain in the zombie world. They also saw reticle/rain omissions in PJ64 with
GLideN64; this is not proof of original-hardware behavior or our root cause.

Existing v1.3 cutscene/blur work and the released shuriken CPU-framebuffer
retention fix are relevant leads, not verification of these cases. Treat the
three paths independently: exact cutscene and hardware performance, weapon
visibility/CPU drawing and final presentation, and weather production/import.
At initial triage there was no patch or live verification for this report. Owner prioritized #24 first; subsequent rain verification is recorded below.
No GitHub comment or closure has been sent. Target v1.3; retain open status
until each symptom has independent evidence and acceptance.

## Owner Tawfret confirmation and active rain investigation (2026-10-19)

The owner confirms rain is missing on Tawfret in the current v1.3 preview,
including after selecting Original FPS. Rain is the active priority; missing
homing-missile/other weapon reticles and Ally X hut performance remain separate
open targets. Similar GLideN64 behavior is a reporter observation, not evidence
that native hardware omits the effects.

The latest closed Settings Preview run is the owner's Tawfret capture:
20261019-033008-f8512a61d2ad4e24a151061b91c43362. Retained private inputs,
frame timings, map state, controls, save and configuration have SHA-256 manifests
under v13-tawfret-rain-20261019/owner-tawfret-original. Its configuration is
Original, VSync on, Reduced blur and 100% original fog. This rules out the new
zero-fog setting for this sample. Frame counters alone cannot prove weather
pixels were generated or displayed.

Historical fix f53dea1 preserved CPU framebuffer effects by completed color
readback, CPU import before VI hashing, and game-selected-buffer presentation.
The fix remains in the current source; high-refresh later adds a retained CPU
mask path. Current hypotheses: native effect gating, CPU draw/import visibility,
or subsequent presentation overwrite. No root cause or rain correction yet.
The latest capture has compact timing/control data, not a complete framebuffer
or original software-drawing trace; its observational limits will be retained.

The production guard remains enabled with the same investigation and counters.
The owner approved two hours for this rain continuation. No autonomous gameplay
or emulator runs; the owner verifies the candidate.


### Focused Tawfret diagnostic prepared (2026-10-19 UTC)

The latest owner capture is level 0x9e, Original presentation, VSync on and
fog 100%. It contains no weather or rain pixel-write events, so it cannot
establish whether weather generation or presentation fails. The earlier CPU
framebuffer preservation fix is still present. A missing module-5 publication
in this recording is a lead only, not a confirmed cause.

The owner approved a short new capture. The explicit --weather-diagnostics
launcher action enables read-only native weather setup/update/draw observations,
postprocess gating returns, actual rainFastDraw changed-pixel counts, deferred
software-line writes and the existing renderer import trace. Ordinary play and
ordinary diagnostics leave this extra probe disabled. No weather values are
forced and no game-state writes are introduced. This is diagnostic preparation,
not a rain fix; owner gameplay capture and analysis remain pending.

Private evidence: D:/JFG-private/v13-tawfret-rain-20261019, including a hashed
copy of the original owner capture/save/config before preparation. No ROM,
generated native source, or personal save is checked in.

Validation: native Release runtime and launcher compiled; 658 launcher checks
passed, including explicit weather-capture activation and duplicate-capture
rejection. Package hashes verified, copied save hash matches the untouched
source, and muted/Original/full-fog configuration checked. The desktop
JFG - Tawfret Rain Capture shortcut opens this diagnostic for the owner;
gameplay and visual verification remain pending. Logs are private under
D:/JFG-private/v13-tawfret-rain-20261019/owner-capture.

Capture preparation failure: launching the managed helper directly omitted
the required launcher identity and was rejected before game startup. The
desktop shortcut now uses the normal native launcher with an explicit weather
diagnostic argument; that launcher supplies the normal package identity and
keeps the map/settings menus available. No recording or save change occurred
in the rejected launch.


### First focused capture reviewed (2026-10-19 UTC)

Owner capture 20261019-034831-1010b4b44f124fabac6b32474af5f777
completed in level 158 / 0x9e. It recorded 1,640 CPU postprocess calls,
no weather setup/update/rain-drawer calls, and no rain pixel writes.
The native weather state stayed at type zero. The final logical RAM snapshot
has a zero weather count and zero weather parameters in the current level
header (header +0xa0 through +0xab). Native initialization and drawing both
gate weather on this count. This narrows the next check to why that room has
no weather setup; it does not yet establish whether the loaded header is
wrong, whether this room uses another rain effect, or whether native game
conditions intentionally disable rain. No weather-forcing workaround applied.

Private summary and header observations: owner-weather-summary.json and
owner-header.json under the investigation evidence directory. Reticle review
remains queued; the owner requested a Map / Settings / Mods all-weapons action
to make each weapon available for testing.


### Landing-room hypothesis resolved against original assets

The native room-158 header in captured RAM exactly matches the original ROM
weather fields: all zero, with native name Swamp Landing Play. The same
0x118-byte raw header layout shows Swamp Maze (138) also has weather count zero.
In contrast Swamp (115), Swamp bog (118), Swamp Creek (121), Swamp track (125)
and Swamp_Ruin (132) each specify 1,104 rain particles. Swamp Landing (135),
a distinct cutscene room, also has rain. Thus absence of weather setup in the
owner recording is expected for the recorded landing gameplay room and does
not prove a renderer regression or resolve the broader GitHub report.

Private header-rom-compare.json and native-weather-rooms.json record this
read-only comparison. No room assets or weather values have been patched.
The owner was asked for a short capture past the landing/maze in a rain-enabled
room, with an option to prepare a direct starting point. Rain remains the
owner-prioritized investigation; all-weapons packaging and live FPS follow-up
are secondary. The weapons test byte-diff check initially assumed swapped
memory even in the unswapped fixture; the fixture was corrected, rerun pending.


### Owner confirms rain past the landing zone

On 2026-10-19 the owner continued the focused capture and explicitly confirmed
rain is visible beyond the landing zone. Live room logs reached Swamp bog (118)
and Swamp (115), both rain-enabled in the original ROM. The closed capture's
initial-profile/video.ini records Custom 120 FPS, VSync on, Reduced blur and
100% fog. This corrects the earlier provisional attribution to Original FPS:
the earlier dry landing capture used Original, but the owner changed settings
before the later wet-room run. No rain correction was needed for this reported
reproduction: landing/maze dryness matches native room data.

The completed wet-room capture is
20261019-040009-de0a1a0d65fe4f768f401d83f14f6a34. It contains 1,363
rainFastDraw observations and all 1,363 changed framebuffer pixels (210 to
4,399 changed pixels per call). The owner visually confirmed the rain. Final
RAM identifies Swamp Grave Yard (242), so this was not limited to the landing.
Private wet-capture-summary.json links the draw counts and recorded session.
These diagnostic timings are not a performance qualification.

The owner separately questioned rain in the opening cutscene, replayed it,
and confirmed: "nevermind the rain is there". Record this as owner visual
verification, separate from the completed wet-room log and consistent with
the rain-enabled native Swamp Landing cutscene header (135). Do not confuse
the cutscene with the deliberately dry Swamp Landing Play room (158).

Rain is verified for these owner-tested v1.3 scenes/settings, not every device
or weather scene. No weather values, assets or renderer behavior were changed
to obtain this result. The GitHub reporter's v1.2.1 / Ally X environment has
not been independently verified, and the issue remains open for weapon
reticles and device-specific cutscene performance. If their rain report
persists, obtain the exact room, version and settings before changing weather.

Transferable lesson: distinguish playable-room and cutscene weather headers,
and use each capture's initial settings instead of assuming settings stayed
unchanged between runs. Pair actual pixel-write observations with visual
confirmation; an inactive weather module in a dry room is not proof of a
rendering regression.

Owner follow-up decision: ask the GitHub reporter to confirm rain on v1.3. No additional rain patch is planned from the verified owner reproduction. Reporter confirmation remains pending; no comment has been posted in this continuation.

## Owner reticle/hut review and reporter follow-up (2026-10-19)

The owner cannot reproduce the missing weapon reticle using mouse/Modern
Controls, and reports the hut scene plays fine. This is scoped owner feedback,
not proof that the Ally X reporter's input path or machine is fixed. No new
reticle correction is justified by the current reproduction.

Owner decision: request a v1.3 retest for weapon reticles, rain and the hut
scene. Ask which input device and control mode the reporter uses (mouse versus
controller/handheld; Modern Controls versus Original Mapping), plus exact
weapons and aim/fire bindings if the reticle still fails. Preserve the distinct
performance report and request location/settings or support logs if it persists.
This follow-up is queued for v1.3 availability; no message or closure was sent.

## Reporter v1.3 follow-up and R&D (2026-10-19)

[Reporter follow-up](https://github.com/TK22-26/JetForceGemini-Recomp/issues/25#issuecomment-6272632791)
confirms missing falling rain through Tawfret, despite visible ground splashes.
Rain briefly appears on room entry or lightning. Homing missiles, tri-rockets
and most throwables lack reticles; cluster bombs/flares are exceptions and
ordinary plus/X shapes work. Settings are Modern Controls defaults with Y aim
inverted, 1080p/60 FPS; 120 FPS drops in some areas. The hut cutscene was not
explicitly requalified in this follow-up.

The owner considers this enough information to start testing and is independently
trying the reporter's settings. Do not interrupt or alter that game/profile.
The earlier dry-room explanation does not resolve the wet-room report. No new
GitHub response is authorized.

### Hardware and driver research

The reported **Xbox Ally X** corresponds to ASUS RC73XA (2025), with Ryzen AI
Z2 Extreme, 24 GB LPDDR5X, a 1080p/120 Hz FreeSync panel and AMD graphics.
AMD lists that processor as 16 RDNA 3.5 graphics cores, 8 CPU cores/16 threads,
15-35 W configurable TDP. The older Ally X RC72LA uses Z1 Extreme/RDNA 3 and
must not be treated as the same hardware.

Sources: [ASUS RC73XA specifications](https://rog.asus.com/us/gaming-handhelds/rog-ally/rog-xbox-ally-x-2025/spec/),
[AMD Z-series specifications](https://www.amd.com/en/products/processors/handhelds/ryzen-z-series.html).
The [ASUS RC73XA driver page](https://www.asus.com/us/supportonly/rc73xa/helpdesk_download/)
lists graphics driver 32.0.32015.5008 dated 2026-10-16 at review time; the
reporter's installed driver is unknown. AMD's
[26.8.1 release notes](https://www.amd.com/en/resources/support-articles/release-notes/RN-RAD-WIN-26-8-1.html)
direct handheld users to device-specific OEM drivers. No driver installation,
rollback or upgrade was requested or performed. These sources do not establish
an AMD driver defect in JFG.

### Shared rendering lead

Historical [GLideN64 #976](https://github.com/gonetz/GLideN64/issues/976) reports
both JFG rain and crosshair loss as CPU framebuffer effects, with emulator
differences. [GLide64 documentation](https://github.com/mupen64plus/mupen64plus-video-glide64mk2/blob/master/src/Glide64/Help/Glide64%20Readme.html)
specifically identifies rain as CPU-written framebuffer pixels.
This supports investigating the common import path, not transplanting a plugin
setting or claiming the same root cause.

Our diagnostic weather and deferred-line scopes identify actual CPU pixel writes.
The prior wet-room capture records 1,363 rain pixel-output events at Custom 120,
VSync on, Reduced blur, full fog. It is not a reproduction of the reporter's
controller/60 FPS case or hardware.

The rt64_cpu_overlay.hpp path retains three changed-pixel masks with framebuffer-
address matching and at most two VI ticks of age. The rt64_video_settings.cmake
integration composites fresh VI changes or retained masks onto the selected
presentation target. Investigate generation, changed-pixel import, framebuffer/
tick ownership and final composition separately. GPU synchronization or driver-
dependent behavior remains a hypothesis until a failing capture or hardware
comparison shows it.

### Discriminating checks

Start with official v1.3.0, 1080p/Custom 60, Modern controller, default bindings
and inverted aim Y in a verified wet room. Check actual falling streaks as well
as ground splashes. Check homing/tri-rockets and one affected throwable while
holding Aim; keep a known-working cross reticle as control.

If reproduced, record writes/import/presentation at the failure before changing
FPS or control mode. If not, test settings one at a time; a desktop pass cannot
prove Ally X correctness. Fog, blur, driver postprocessing, power mode, API,
device/driver identity and exact framebuffer sizes are useful comparison data,
not grounds to dismiss the report. No new runtime fix is delivered by this R&D.

### Follow-up: upstream repair and local exclusions

[GLideN64 #2653](https://github.com/gonetz/GLideN64/issues/2653) describes JFG
reticles where the central cross renders but surrounding CPU-drawn parts do
not. [PR #2657](https://github.com/gonetz/GLideN64/pull/2657) repaired interaction
between auxiliary framebuffer copies and main-framebuffer CPU effects: removing
the current auxiliary buffer could leave the current framebuffer null, and
generic guards then skipped otherwise valid work. This is a useful ownership
invariant to check in RT64, not evidence that our implementation has that defect
or a patch to copy between different renderers.

Both earlier local CPU-effect fixes, f53dea1dcd64262c4b90e45864b0f33d87908863
and 95efb8f97b47717921aa4c29ab17245771c3ff22, were verified as ancestors of
v1.3.0 with git merge-base --is-ancestor. They are present in the released
source; a missing merge does not explain this report.

The retained-mask copy is enclosed in RenderWorkerExecution, whose destructor
ends, executes and waits for its worker before the frame is published as valid.
Thus the simple hypothesis that publication always precedes completion of that
copy is not supported by this source path. This does not establish correctness
of resource reuse, cross-worker ownership, imports, selection or driver behavior.

Read-only source review and historical evidence are complete for this R&D pass.
The owner is testing independently; no new game run, driver change, runtime
patch or reporter resolution is claimed. Private source-review logs and API
snapshots are retained under D:/JFG-private/v131-rnd-20261019 and the guarded
step directory. Continue with a failing generation/import/presentation capture
if the owner's reproduction succeeds; otherwise narrow hardware and settings
differences without discarding the Ally X report.

## Wet-capture coverage correction and incremental-mask hypothesis (2026-10-19)

The earlier known-good wet capture contains 2,012 reticle-line-output events,
but all report **zero changed pixels**. Those are calls to the deferred line
processing path, not 2,012 successful reticle drawings. This capture verifies
rain generation and owner-visible rain, not the missing homing/tri-rocket
reticles. Its 1,363 rain calls all changed pixels; renderer tracing records
1,170 submit-time retained masks and 192 VI-time retained masks, followed by
5,444 cached-mask compositions and 14 fresh-VI compositions. Counts alone
cannot prove pixel-level coverage on every output.

Source review found a distinct candidate limitation to investigate: RT64's
FbReadAnyChangesCS compares RAM against the previous native/import buffer,
so successive imports can produce incremental masks. Our retained-mask
selector chooses one latest mask for a framebuffer and scene-age window.
If two disjoint CPU edits to one scene enter through separate imports,
replacing the earlier mask with the later delta can lose earlier edits on
a freshly interpolated target. This is a conditional source-level hypothesis,
not a reproduction of #25. The known-good rain trace has no duplicate retained
imports with the same framebuffer address and tick; different-tick imports
still need explicit render-generation ownership to assess this case.

Do not extend mask age or accumulate masks across unrelated framebuffer
generations as a speculative remedy: that risks stale rain/reticle trails.
A failing capture should record the native-draw result, import change count,
mask selection/rejection reason, base framebuffer generation and final
composition before selecting a remedy. No AMD-specific cause is established.

Private evidence: wet-reticle-writes.json, wet-overlay-event-inventory.json and
wet-retained-delta-groups.json under D:/JFG-private/v131-rnd-20261019.
Owner is concurrently testing the official release at the reported settings.


## Reusable offline analysis

Added [analyze_runtime_effects.py](../../../scripts/analyze_runtime_effects.py)
to summarize actual changed-pixel calls and software audio queue age from an
existing closed gameplay.tsv. Example:

    python scripts/analyze_runtime_effects.py <closed-session>/gameplay.tsv

It excludes the first ten seconds by default; use --from-seconds 0 for startup.
It keeps paused/prebuffer audio separate from active playback, validates sample
rates and cumulative/current byte consistency, and reports missing probes
without treating them as a clean pass. It cannot prove visible output, speaker
latency or complete trace delivery.

Five focused unit tests pass, including zero-write reticle calls, a persistent
1.2-second backlog without any underrun event, changing cumulative byte totals,
startup/paused buffers, and malformed evidence. Applying it to the historical
full-run and wet-room captures reproduces the source-review measurements.
No game executable or active user profile was modified.


### Owner reproduces the reporter configuration (2026-10-19, 22:45 UTC)

The owner confirms reproduction in the official v1.3.0 desktop launcher and
answers "Everything he noted" when asked whether both missing falling rain and
missing homing/tri-rocket reticles occur. The owner identifies widescreen as
the strongest lead, with 60 FPS, 1080p, inverted Y and Modern controller controls
also changed relative to the earlier accepted local setup. This establishes
local reproduction outside the Xbox Ally X; an Ally-specific hardware or driver
fault is no longer required to explain the symptoms. It does not yet isolate
a setting or confirm a single cause for every symptom.

First requested controlled comparison: disable only the in-game widescreen
option in the same wet room, preserving 60 FPS, output resolution and controls.
Result is pending. Do not interpret the earlier dry landing-room result as
resolving this reproduced wet-room failure.

Source lead: native widescreen uses a 320x240 allocation with 320x180 display,
changes VI scaling and can request triple buffering. Retained CPU overlays use
exact framebuffer identity, dimensions and a two-tick age limit. Verify the
actual VI-derived dimensions and buffer lifecycle before altering acceptance,
mask lifetime or composition. No frame-rate or camera setting has been changed
by the investigation while the owner tests. No GitHub response has been posted.


Controlled comparison update: the owner disabled in-game widescreen while
preserving the other settings; neither falling rain nor the missing reticles
returned. This rejects an immediate aspect-toggle recovery, but does not rule
out state retained from startup. The next comparison keeps widescreen off and
changes only Custom FPS to 120 with a full game stop/start to clear renderer
state. That result is pending. No fix claim is made.


Second comparison: the owner restarted with widescreen off and Custom 120 FPS;
neither effect returned. Widescreen-off and raising the FPS target therefore do
not restore this failure in ordinary Play.

A concrete production/logging dependency was found in source: output samples
are written and read only when interpolation tracing is enabled
(interpolation_bridge.hpp, record_presentation_output / presentation_output_sample).
The CPU-overlay selector nevertheless uses that sample's tick in normal Play.
With logging off, the default tick is zero and nonzero-timestamp retained masks
fail the selector's frame->tick <= tick check. Fresh Present masks can still
appear, which is consistent with intermittent effects. This is a deterministic
code defect; a logging-disabled regression test and correction are being
prepared. Live verification of the remedy and coverage of each reported weapon
remain pending; no claim yet that this explains every #25 symptom.


### Production output timestamp correction

The retained CPU-mask selector uses the output sample's VI tick to reject
future or expired masks. Those samples were treated as diagnostic-only state:
both recording and lookup returned early when JFG_RT64_INTERPOLATION_TRACE was
unset. Consequently ordinary Play supplied tick zero and rejected every cached
mask whose tick was nonzero. Diagnostic captures populated the same metadata,
masking the defect. Direct fresh-Present masks remained a separate path, so
brief appearance did not establish stable retention.

The correction promotes output metadata to production state independent of
logging. File tracing is still optional. Framebuffer matching, immutable mask
ownership and the existing two-VI lifetime are unchanged; this does not force
native rain or reticle visibility, change controller input, or disable safety
checks. Source: [output metadata](../../../include/jfg/renderer/interpolation_bridge.hpp)
and [regression coverage](../../../tests/rt64_interpolation_tests.cpp).

The new logging-disabled regression failed against the released header and
passes after the correction. It checks actual retained-mask selection, rejects
wrong framebuffer identity, future masks and expired masks, and verifies mask
release. The focused RT64 shell, interpolation and semantic-presentation CTest
suites all pass with JFG diagnostic environment variables cleared. The native
Release runtime was rebuilt. These checks establish the metadata defect and
remedy, not final visual acceptance or a hut-performance fix.

Private build/test/preview receipts are retained under
D:/JFG-private/v131-rnd-20261019. Preparation first stopped on a stale runtime
identity sidecar; the official identity writer regenerated it from the actual
dirty candidate source and binary before packaging. A prior source-equivalence
check stopped on line-ending byte differences; normalized content and the
matching source commit were verified before the build. Neither interrupted
preparation was treated as a successful validation.

The owner approved four additional hours for this reproduced defect and will
perform visual verification. The preview copies the current profile, starts
muted and uses normal Play without detailed logging. Required visual acceptance:
falling rain in the same wet room and homing/tri-rocket/throwable reticles while
holding Aim, followed by 60 FPS and widescreen comparisons. Ordinary Play and
capture mode must agree before claiming resolution.

Transferable lesson: production rendering decisions must never consume state
that is only populated by diagnostics. Test fixes with instrumentation disabled
as well as enabled; diagnostic success alone can conceal a release defect.


## Owner candidate verification, 2026-10-19
The owner reports that falling rain and the previously missing aimed weapon reticles
both return in the candidate. They also report that rain appears about half a second
after entering a room. This confirms restoration of the two missing effects, not
resolution of the room-entry delay. No timing trace or original-game comparison yet
establishes whether the delay is native weather activation or overlay presentation.
The correction is production timestamp maintenance, not forced weather/reticle
visibility or relaxed stale-mask validation. The controller Remove regression
reported during the same session is tracked separately in
[INPUT-012](controller-remove-auto-reassignment.md).

Owner follow-up: brief room-entry rain delay remains a required fix, separate from accepted missing-rain/reticle correction. Not waived by release acceptance of other features.


## Guarded room-entry delay investigation (2026-10-20 UTC)

Owner authorized parallel investigation for up to two hours. The production guard
remains enabled under the original high-refresh investigation; its counters,
roots and prior evidence are preserved. This continuation isolates the reported
roughly half-second room-entry rain delay from the owner-accepted restoration
of missing rain/reticles. Native weather activation, first CPU pixel writes,
framebuffer import and final presentation remain separate hypotheses. No delay
fix or original-game parity is yet established. Existing closed owner captures
and source will be reviewed before selecting a remedy. Private evidence ID:
`tawfret-rain-delay-20261019`. Owner gameplay/profile and unrelated cutscene work
remain undisturbed.

### Completed finding: native fade gate delays the first rain writes

Five playable wet-room entries in two retained owner weather captures reproduce
a delay closely matching the owner's estimate. Times below are measured from
native weather setup, not from the first visibly playable frame.

| Capture suffix / entry | Level ID | Fade gate first clears | First changed rain pixels |
|---|---:|---:|---:|
| `040009` / 0 | 118 | 394.910 ms | 428.424 ms |
| `040009` / 1 | 115 | 400.350 ms | 433.981 ms |
| `040009` / 2 | 118 | 401.045 ms | 435.109 ms |
| `040009` / 3 | 242 | 395.906 ms | 426.885 ms |
| `040321` / 1 | 118 | 401.780 ms | 433.933 ms |

All five follow the same recorded native sequence:

1. The first eleven `mainCPUeffects` calls return `1` from `fxFadeOn`;
   rain drawing is skipped and the previous framebuffer height remains zero.
2. On call twelve, the fade checks return `0`. The previous height is still
   zero, so the rain branch initializes that height without drawing.
3. On call thirteen, the previous height is 240 and `rainFastDraw` changes
   framebuffer pixels.

The original US symbols identify `mainCPUeffects` at `0x80045A44` and
`fxFadeOn` at `0x8006B978`. The generated native branch at `0x80045AC0`
skips rain while the fade gate is nonzero. The height check at `0x80045AF0`
and store at `0x80045B2C` account for the additional eligible call.
Rain setup resets that height at `0x8005BD24`. The current build uses this
same generated source directory; searches of host source found these weather
targets in the read-only
[diagnostic scope](../../../src/boot/native_boot.cpp), without a host override
for the fade gate. Private extracts retain the exact source paths and operations.

This establishes the cause of the **archived generation delay**. It supports
native transition suppression as the explanation for the owner's current
symptom, but does not establish that the entire current visible delay is native.
The original code's behavior is preserved; no N64/emulator visual comparison
was performed in this continuation.

### Renderer review and remaining limits

Source review found no fixed half-second renderer warmup.
[CPU-effect import](../../../src/renderer/rt64_shell.cpp) occurs at task
submission or VI processing. The retained
[overlay selector](../../../src/renderer/rt64_cpu_overlay.hpp) requires the
same framebuffer and a mask no more than two VI ticks old. Selection once per
Present sequence and a fully owned three-mask pool remain possible sources
of additional latency; neither was demonstrated in these entries.

Generic presentation resumes 74.853-86.856 ms after setup. A same-address
generic present follows the first rain write by 15.575-36.713 ms. These are
dispatch observations, not proof that a particular rain mask reached the
screen. Joining the gameplay and interpolation clocks to establish exact mask
retention/composition timing was prepared but did not execute before the
guard stopped the session.

The captures predate the accepted output-timestamp correction and use weather
instrumentation. The first identifies runtime
`8c8ffaa007ed4633afe707222a05d51ded8cc2c0a9d33f611828246ce8b0c9cf`;
the captured configuration is Custom 120 FPS, VSync on, Reduced blur and
100% fog. Instrumentation affects wall time. A separate level-135 cutscene
entry is excluded from the five-entry playable range. There is no matching
room-entry video or new current-preview capture in this pass.

Evidence ID `tawfret-rain-delay-20261019` contains
`capture-review/fade-gate-timeline.json`, `capture-review/rain-entry-summary.json`,
the native source extracts and renderer review. Original gameplay trace hashes:

- `20261019-040009-de0a1a0d65fe4f768f401d83f14f6a34`:
  `c715790d7e66e6cf95cdf0cfc849043d7c5b118aedeffc440a258d38ffaee2a1`.
- `20261019-040321-e624db228bd14d0ea9b30ad4441f8b34`:
  `ecada9d7b726459865025bb575419621d6a142841188f955af98f1be8cd2c608`.

### Remedy status, stop and transferable lesson

No rain-timing remedy was implemented or validated. Removing the native fade
gate would change transition behavior; extending retained-mask lifetime would
not address the measured absence of native rain writes and risks stale effects.
The earlier timestamp correction remains separately owner-accepted and
unreleased. The owner's request to address the visible delay remains open.

The parallel session stopped early when the completed cutscene peer was graded:
the private admission had reserved exactly one additional attempt, and the
shared investigation reached its attempt ceiling while rain work was still
running. The supervisor terminated rain work on shelving. All counters and
evidence were retained; the production guard remains enabled. No bypass,
renewed admission or direct investigation execution followed. See
[AUTO-002](parallel-investigation-admission.md). Pending steps `206` and `307`
remain unexecuted; their proposed outputs are not validation evidence.
This final record preserves completed findings and the stop reason only.

Measure native generation separately from import and presentation. An output
timestamp defect can explain missing effects while an independent native fade
rule explains their late start. Diagnostic captures and generic present events
cannot by themselves establish ordinary-Play visual parity.

### Renewed solution candidate (2026-10-20 UTC)

The owner renewed solution work within the original two-hour parallel-work
window. The same production investigation and all historical charges remain
intact. Deferred capture/renderer reviews have now completed. Matching the five
first native rain writes to renderer activity gives 24-37 ms to composition and
32-38 ms to a display event, reinforcing native fade gating as the principal
archived delay. These are historical diagnostic captures, not new visual
verification of the current preview.

A candidate in `include/jfg/renderer/rain_fade.hpp` tracks the fade attached to
the actual submitted framebuffer. Main-frame construction appends the next
fade to `otherScreen`, while CPU weather modifies completed `currentScreen`;
reading the newest global alpha is therefore incorrect. The candidate records
by display-list build, seals at frame completion, and requires matching list
start/end and target on task submission. Only the rain-specific fade query
(return PC `0x80045AC0`) is eligible for an override, during a matched simple
fade-in. Native rain geometry, density, RNG, blend exponent, and the other
fade queries remain native. The source RGB argument is temporarily faded and
restored around each native line draw.

This is an approximate composition candidate, not exact native fade parity.
An isolated harness compiled the unchanged generated native line writer and
exercised the candidate color helper: 60,000 arithmetic/span-path comparisons,
311,040 composition cases, endpoint, clipping, and memory checks passed their
stated invariants. Single-stroke error is at most one RGB555 channel level;
repeated quantization reached eight levels for 16 coincident exponent-4
strokes. That adversarial overlap result is retained, not treated as visual
acceptance. Runtime integration, targeted lifecycle tests, and live owner
verification remain pending at this stage.

Private evidence: `D:/JFG-private/tawfret-rain-delay-20261019/overlay-review/`
(`rain-write-to-display-summary.json`, `fade-ownership-and-composition-review.json`)
and `pixel-review/native-line-harness/native-line-results.json`. Generated
source, ROM material, and personal captures remain private.

### Final candidate and validation (2026-10-20 UTC)

The initial candidate review found an important ownership failure: native
shadow/type-3, type-4 and type-5 graphics tasks can submit between the main
frame and CPU weather. Invalidating all metadata on those submissions would
suppress the correction on ordinary shadow frames and lose the last partially
faded frame at fade completion. The final candidate tracks the exact auxiliary
entry scopes, preserves disjoint command/image ranges, and invalidates matching
metadata on conflicting ranges or unknown submissions. Auxiliary nesting is
restored on return. Unsupported signatures, transitions, dimensions and DP
recovery fall back to native gating. Only relevant dispatched functions create
a rain scope; ordinary dispatches avoid its initialization work.

Validation completed against header SHA-256
`e7b174419932d4186d6085b2e2b8ce8cc265a18221a94560aa45a5c13ca82a3e`:

- 1,008 tracked checks pass under MSVC C++20, optimization, `/W4 /WX`.
  Coverage includes actual dispatch scopes, previous/pending framebuffer
  ownership, auxiliary submissions and overlap, gate call-site identity,
  transition changes, recovery, invalid memory, and argument restoration.
- An isolated harness executes unchanged generated `mainCPUeffects` and
  `fxFadeOn`. In its controlled visible-fade sequence, the first native rain
  dispatch advances from processing call 13 to call 2; initially fully black
  advances from 13 to 3. Native height initialization is retained. Dry rooms,
  missing weather, non-simple/fade-out transitions, recovery and mismatched
  ownership retain their original dispatch behavior. Other fade-gate returns
  and effect dispatch counts remain unchanged. These synthetic sequences do
  not measure live visible latency.
- The unchanged native line-writer harness verifies the actual source-color
  helper, native arithmetic, both generated execution paths, clipping,
  coverage and endpoint behavior. Accumulated overlap rounding remains the
  limitation recorded above; passing tests do not establish visual parity.
- The complete native runtime translation unit compiles with warnings treated
  as errors, and a separate executable links successfully. The shared build
  was read only; every enumerated project library/object/resource input kept
  the same hash before and after linking. A source comparison found only the
  rain header/hooks as substantive differences from that build's source.

Informative failures were retained: the first private compile invocation
failed in `vcvars` command quoting, then in response-file external-include
formatting, before compiling the source. After the auxiliary correction,
strict compilation caught a shadowed local variable; it was renamed and both
strict component and runtime builds passed. No failed result was rewritten.

Preview: **JFG - Tawfret Rain Fade Preview** on the owner's desktop, at
`C:/JFG-previews/tawfret-rain-fade-20261019`. Runtime SHA-256:
`92aff977d4d441c689fa80fe694f86d5436eca8c155ab5b9f8e2b7352bf2e78f`.
It uses copied rain-test save/settings, starts muted, and reads the already
imported ROM from its original location. Original profiles/previews remain
unchanged. The launcher/game was not started by this investigation.

Owner verification remains required: enter/reload wet Tawfret rooms, watch
rain through the fade, repeat transitions, and check normal rain/reticles.
Compare rain brightness/overlap during the fade and confirm there is no flash
or late pop-in. No new original-game or current-preview visual comparison has
been claimed. This is an intentional change to inherited fade gating, not a
released resolution of GitHub #25 or its separate performance report.

Private final evidence under `D:/JFG-private/tawfret-rain-delay-20261019`:
`pixel-review/tracker-tests-auxiliary/auxiliary-result.json`,
`pixel-review/native-postprocess-harness/native-postprocess-results.json`,
`overlay-review/candidate-independent-review-v2.json`,
`solution/native-compile-v2/result.json`, and `solution/preview-receipt.json`.
Source: [rain fade policy](../../../include/jfg/renderer/rain_fade.hpp),
[native hooks](../../../src/boot/native_boot.cpp),
[tests](../../../tests/rain_fade_tests.cpp). No commit or release was created.

Transferable lesson: CPU framebuffer effects must use the fade belonging to
the completed image, not newer simulation globals. Keep auxiliary graphics
ownership and native blend exponents explicit; affine composition reasoning
must be qualified by repeated low-precision rounding.

### Preview startup failure reported (2026-10-20 UTC)

The owner reports that the Tawfret Rain Fade Preview launcher does not start
the game. The package/hash and component checks above did not exercise the
launcher-to-game startup path; live rain verification is blocked. A guarded
continuation within the original approved window is inspecting actual startup
logs and correcting the delivery. Cause and remedy are not yet established.
Original saves/settings remain preserved; do not interpret the previous
package validation as successful startup.

### Preview startup correction (2026-10-20 UTC)

Confirmed cause: the private packaging step added `jfg-native-boot.exe.support`
and `RAIN PREVIEW.txt` to `jfg-package.json`. The deployed launcher's
`PortablePackage.Resolve` requires exactly its 14 runtime members; the 16-entry
manifest was rejected before runtime startup even though every individual hash
matched. The earlier custom package check missed this exact-set requirement.
This was a preview packaging error, not evidence about the rain candidate.

The two extra entries were removed from the manifest. Both files remain beside
the runtime. No executable, dependency, original profile or save was changed.
The initial suggestion of a missing ROM was incorrect: the launcher's first
initialization had already imported the ROM successfully into the independent
preview profile before rejecting the manifest. The original imported ROM was
preserved. The preview notes now describe that normal import behavior.

Validation uses the **deployed embedded helper** from this preview, with its
normal launcher identity. `--frontend-worker init` and `setup` both exit zero;
the final status is `ROM and game files verified. Click Play.` This exercises
the real manifest validator, verified ROM import, and the candidate executable's
`--frontend-version` handshake. Original and copied save hashes are unchanged.
No autonomous gameplay was performed; visible Tawfret verification remains
pending. The same desktop shortcut is ready to retry.

Preserved evidence:
`D:/JFG-private/tawfret-rain-delay-20261019/launch-repair/before-correction/`,
`initial-diagnostics.txt`, and `repair-result.json`. Earlier package receipts
remain historical and are superseded for startup acceptance by this result.

Transferable packaging rule: keep documentation and identity sidecars outside
the manifest's exact runtime-member array. Before handing off a preview, use
the deployed launcher's setup action; standalone file-hash checks cannot replace
its package/ROM/protocol validation. See
[package contract](../../../launcher/windows/PortablePackage.cs) and
[frontend setup](../../../launcher/windows/FrontendBridge.cs).


### Returned rain-delay preview recording (2026-10-20 UTC)

The owner reports "it seems acceptable but not perfect", then clarifies:
"Rain still seems late. better but still late." This is partial subjective
improvement, not acceptance of the remaining room-entry delay.

Closed session `20261020-031759-869071c839c7455499120eab763c17c1` ran
205.530 seconds with the intended `92aff977...` runtime at Custom 60 FPS,
VSync on, Reduced blur and 100% fog. Both launcher and native support logs
record normal closure with exit zero; the earlier package startup fault is
resolved for this owner run. Original recording and saves remain untouched.

The decisive candidate result is negative: all 5,930 `rain-fade-frame` events
carry an inactive fade snapshot (simple-in, alpha, RGB and epoch all zero),
and there are **zero** `rain-fade-gate` overrides despite eight wet-room
transitions (levels 118/242). Thus this session does not validate the proposed
fade-gate remedy. Its passing synthetic component/native-postprocess tests
did not establish real in-game fade tracking. Source integration is being
checked before any new fix claim.

CPU overlay import and composition remain active. Their events cannot identify
rain alone. Standard launcher recording did not enable the weather pixel-write
probe and contains no video/screenshots, so exact visible onset and a measured
before/after rain-delay improvement cannot be claimed from this capture. Route
request timestamps also include loading/fade-out and must not be compared
directly with the historical weather-setup-to-first-write metric.

Private evidence: `D:/JFG-private/tawfret-rain-delay-20261019/recording-review/`
contains immutable capture hashes, `recording-summary.json`, corrected
`interpolation-event-summary.json` and `runtime-effects.json`. An initial
generic interpolation summary parsed its timestamp column as an event name;
that output is retained as an informative analysis error and superseded by
the format-specific summary. The guarded review remains in the original
investigation and originally approved parallel window.


### Confirmed unsupported transition and spatial remedy work (2026-10-20 UTC)

Source and an unchanged-native-function harness establish the missed case.
The black entry descriptor at `0x800A32EC` is `83 00 00 00 0014 0000`:
type 3, inward direction, black, duration 20. It selects the mesh routine
`0x8006CC20`. The white descriptor at `0x800A32F4` selects type 0 and
`0x8006C124`, the only path supported by the first candidate. The source
selects between them using `0x800A32A0`; do not generalize either branch to
all travel modes from this evidence alone. The final archived and returned
RDRAM states both retain type 3, corroborating the source diagnosis without
claiming they contain every earlier transition's state.

The recorded fields are the same completed-frame Fade object consumed by
both the gate override and rain color adjustment. All-zero metadata therefore
means those mechanisms were inactive, rather than merely omitted from the log.
An actual type-0 setup/update/draw control passes 640 checks and activates the
candidate. The exact black type-3 setup/update/draw reproduces inactive metadata
in 2,092 checks across both generated native-span and fallback paths. This
explains the gap in the earlier component validation; it does not negate the
owner's subjective report that the result looked somewhat better.

Type 3 is a moving spatial gradient made from ten vertices and six triangles.
Its left/right shaded regions can overlap and require ordered source-over
composition. Treating it as one scalar alpha, simply clearing its fade gate,
or restoring only fully covered pixels would be incorrect. Actual emitted
matrix/viewport and clipping must belong to the same completed framebuffer.
The native NTSC fade projection scales Y by 1.2; a later global value or the
final-frame matrix can already have been restored to 1.0.

A private stroke helper has been validated for a proposed per-pixel remedy:
capture original stroke pixels read-only, run the unchanged native leaf,
then restore/replay those pixels with a spatially faded source color. This
preserves native register effects, endpoint rejection, raster walk, packed
blend exponents, coverage and coincident-stroke order. It passed 156,004
identity cases, 96,000 uniform-fade comparisons and 96,000 per-pixel comparisons
against the unchanged native point writer. These are helper results, not an
integrated game fix. Raster coverage, mesh alpha quantization and the effective
clipping rectangle still require validation; unknown clipping must fail closed.

Private evidence under `recording-review/`: `recording-independent-diagnosis.json`,
`native-fade-harness/`, `native-type3-black/type3-result.json`,
`native-line-callback/result.json`, and `spatial-fade/`. The initial callback
fixture compared raw word-swapped byte locations against logical pixel
addresses; the fixture was corrected without changing the helper and its
failed result was retained. The delivered preview has not been relabeled as
fixed. No commit or release has been created.

Transferable lesson: prove the exact transition selected by a real failing
route before designing a fade workaround. A correct synthetic test of a
different native transition does not establish coverage of the user's case.

### Integrated spatial-fade preview delivered (2026-10-20 UTC)

The replacement now supports the observed NTSC 320x240 single-player black
inward type-3 transition. It snapshots the actual native mesh, emitted matrix,
viewport and proven scissor while constructing a main display list, then carries
that snapshot through sealing/submission to the matching completed framebuffer.
The first CPU-effects fade gate opens only once that owned mesh reveals pixels
and its transition epoch still matches. Fully covered frames retain native
suppression. The original native rain-height warmup remains intact.

Each native rain line runs with its original register behavior. Its original
pixels are then restored and replayed with the captured spatial fade applied
to the source RGB, preserving the native exponent, coverage and stroke order.
The coordinate mapping uses the actual guest pixel address relative to the
completed framebuffer, including the native 30-row rain offset. This is the
remedy for the confirmed unsupported-transition cause; live visual qualification
is still pending and the issue is not resolved or released.

Clipping acceptance is deliberately bounded: the native empty-debug-text path
must emit its exact six commands, both referenced static state lists must match,
and only the known viewport/matrix pair may intervene before the fade mesh.
Different dimensions, PAL projection, multiplayer, other transition types, or
intervening text/window output retain native gating. If an individual line cannot
be captured after the batch gate opens, its temporary source becomes black with
the original blend exponent, and its stack argument is restored afterward. This
prevents an unattenuated bright line; the rare fallback may darken a visible line.

Validation against the delivered header SHA256
`20793ca67d3cb4b09b7acbba9725fd8ab93cabe0f8ab77dd462c7493ea2f2033`:

- 1,049 tracked regression checks pass under strict MSVC C++20 `/W4 /WX`.
  New checks cover scissor continuity, owned dimensions/frame/epoch, replay,
  native return preservation and conservative failure behavior.
- 30,912 actual-native integration checks pass across setup/update/draw,
  emitted scissor/matrix, submission, CPU-effects gate, warmup and point writer.
  Wrong framebuffer/epoch, missing scissor, full black, PAL and outward fade
  negatives retain native behavior. In the controlled normal case the gate
  opens at zero-based tick 2, native warmup occupies that tick, drawing starts
  at tick 3, and the first nonzero RGB among five sample strokes is tick 5.
  Rejected/native-gated scenarios first dispatch at tick 22. These synthetic
  ticks are not a measured live presented rain-onset improvement.
- 2,956,932 geometry/scissor checks and 19 independent integrated failure-policy
  checks pass. Pixel-center opacity matches the independent affine/barycentric
  reference, but actual RDP coverage/alpha quantization and RGB555 accumulated
  rounding still require visual comparison.
- Isolated native compilation/linking pass, with stable hashed link inputs.
  The deployed embedded launcher helper passes both init and setup, including
  the runtime protocol handshake. The exact 14-file manifest is retained.

Informative failures remain preserved. The first integration fixture copied only
64 of the required 128 bytes of the native static RDP list, causing correct
rejection; copying the complete unchanged list made integration pass. The first
new tracked fixture used shift 320 instead of its intended 160; correcting that
input preserved its independently calculated opacity/pixel expectations. An
independent review found unattenuated fallback and frame-dimension ownership gaps;
both were corrected before delivery. An early private renderer compile rejected
third-party anonymous-struct warnings; dependency include classification was
corrected while retaining strict project warnings.

Parallel build compatibility: the shared cutscene work changed renderer inputs
and the prompt ABI during this review. This candidate uses a private renderer
rebuilt against the frozen first-preview headers and original prompt behavior,
a frozen native boot with only rain diagnostics added, and unchanged hashed
remaining link inputs. The shared build and parallel source changes were not
reverted. Its sidecar is generated from a coherent private source snapshot with
explicit source/link provenance, not attributed to the concurrently edited tree.

The same `JFG - Tawfret Rain Fade Preview` desktop shortcut now opens runtime
`b2d6cc2949a3401d55ba8ff4136cb64eda330333b0808676fa0b7e65c950b09c`.
Existing preview saves/settings are hash-preserved; the old executable, sidecar,
manifest and notes are backed up privately. No autonomous gameplay, commit or
release was performed. Re-enter a wet Tawfret room and inspect repeated reveals,
normal rain and reticles to qualify the new candidate. Its standard recording
now includes spatial acceptance/scissor counters and processed line/pixel counts.

Source: [frame ownership and native hooks](../../../include/jfg/renderer/rain_fade.hpp),
[spatial mesh/scissor capture](../../../include/jfg/renderer/rain_spatial_fade.hpp),
[native line replay](../../../include/jfg/renderer/native_rain_line.hpp), and
[regression checks](../../../tests/rain_fade_tests.cpp).
Private evidence under `recording-review/`: `native-spatial-integration/`,
`tracker-tests-spatial/result.json`, `spatial-fade/`, `native-compile-v3/result.json`,
`native-compile-v3/identity-provenance.json`, `before-spatial-deployment/`, and
`spatial-preview-receipt.json`. Earlier candidate/failed fixture receipts are
historical evidence, not current acceptance claims.

Transferable lessons: test the transition actually selected by the failing route;
bind projection/clipping and effect metadata to a submitted framebuffer rather
than mutable globals; validate the full unchanged native path; and keep frozen
headers, renderer ABI and linked inputs coherent during parallel builds.

### Owner accepts the rain-delay fix (2026-10-20 UTC)

After delivery of the replacement spatial-fade preview, the owner reports
“approved fixed”. Record the Tawfret rain-delay remedy as **owner-confirmed
locally**, superseding the preceding pending owner-verification status.
The delivered runtime is
`b2d6cc2949a3401d55ba8ff4136cb64eda330333b0808676fa0b7e65c950b09c`
in `JFG - Tawfret Rain Fade Preview`.

This is the owner's acceptance of the observed symptom, not a newly measured
onset time or proof of pixel-exact parity. Existing native/regression/launcher
results remain the technical validation; unsupported paths and raster-rounding
limits documented above remain applicable. No additional experiment or build
was performed for this status update.

The rain-delay portion is accepted locally. The broader RENDER-016 report
remains open for original reporter/Ally X verification, hut performance and
release. No commit, public issue closure or release is implied by this approval.


## Related crosshair report (2026-10-21 UTC)

New [#36](github-weapon-crosshairs.md) reports missing rocket/homing crosshairs
on v1.3.0 with Windows 10 and an RTX 5060 Ti. It may overlap the accepted local
reticle correction, but reporter retest is needed before calling it the same
cause or resolved. #25 still needs updated-build/Ally X retesting, including the
separate hut/cutscene performance point. No additional reticle fix is inferred.
