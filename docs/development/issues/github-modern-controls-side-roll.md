# GH-033: Sideways roll unavailable with Modern Controls

## Owner acceptance (2026-10-20)

The owner approved all changes in the Modern Roll Direction Preview and requested
commit and push to `develop`: "approved on all - commit and push to develop".
This accepts the roll bindings and automatic-roll preference, prone-roll direction,
and live P1-P4 indicators. Earlier backward-crawl and controller reassignment fixes
remain owner-confirmed. The preview runtime is
`a26006f13c507dd4601461308ce43153d98d6eb90ca104685fce2ac130dee154`;
launcher is `4bff11b4c8145925f948f563dec573f46d382c1d622da36a0e0b0e488ba956f3`.
Acceptance supersedes earlier pending-preview statuses below. This is an accepted
development change, not a release or a claim of exhaustive hardware/collision
coverage. Automated evidence and its limits remain unchanged.

The owner separately approved one bounded ten-minute guard continuation solely
for acceptance records, commit and push. The production guard, investigation root,
cumulative seconds cap and existing counters are retained; no new gameplay
investigation is authorized.


## Tested preview candidate (2026-10-20)

Desktop shortcut: **JFG - Modern Roll Direction Preview**.
Package: `C:\JFG-previews\modern-roll-direction-20261020`. Runtime SHA-256 `a26006f13c507dd4601461308ce43153d98d6eb90ca104685fce2ac130dee154`;
launcher SHA-256 `4bff11b4c8145925f948f563dec573f46d382c1d622da36a0e0b0e488ba956f3`. Startup protocol and the actual
packaged launcher's extracted helper init/setup passed. No gameplay was launched.
The accepted previous preview, settings and saves remain intact; copied profile
hashes were verified. Ctrl, inversion and existing bindings remain unchanged.
New work awaits owner live verification and is unreleased. Earlier backward-crawl
and controller-assignment fixes remain owner-confirmed.

## Prone direction correction and explicit roll bindings (2026-10-20)

Cause: Modern lateral roll input continued feeding ordinary crawl magnitude after
native side-roll entry, adding unwanted longitudinal movement. Classic C-side
with neutral analog does not. `ModernProneRollMotionScope` in
`src/boot/native_boot.cpp` temporarily suppresses that magnitude and filtered
analog only in the qualified native direction/turn consumers. It preserves
native lateral velocity, inertia, speed/easing, repeat and the accepted crawl fix.
Qualification covers the captured player-1 Modern actor/control, humanoid prone
stance, active side roll, connected/unblocked gameplay and supported modes 0/3/5.

Verification: 834 exact scope checks; 5,184 independent trajectories and
2,765,021 checks, including 145,152 Classic reference frames. Extra longitudinal
samples fell from 144,384 to 0 with 0 lateral mismatches. 216 neutral/changed gesture
cases are byte-identical with scope enabled/disabled. Tests use actual native
crawl handlers and the shared physics prefix before collision, with controlled
math/timing/animation fixtures. They do not establish full collision/render or
physical gameplay acceptance. Legitimate prior momentum remains. Earlier entry
and repeat checks did not establish complete roll trajectories; future movement
changes must compare longitudinal and lateral paths as well as state transitions.

Both Modern action pickers now expose Roll Left/Right, unbound by default.
Advanced > Automatic movement rolling defaults On and is shared per player
across mouse/keyboard and controller. Off disables stick/A-D-triggered roll;
explicit bindings still work under the existing prone/crouch posture gates.
Manual intent takes precedence; opposing manual rolls cancel. Existing recording
intent bits are reused.168 Modern core, 416 roll and 101 independent sampling/
persistence checks passed. Existing profiles 1-5 migrate with defaults and retain
bindings; new saves use schema 6, which older executables reject. Keep the preview
profile isolated when returning to an older executable.

Final UI suites passed 839 Modern, 305 mapping and 55 menu-input checks. Initial
new-toggle pointer checks failed because a third card overflowed a nowrap grid;
vertical scrolling did not fix it. The existing two-column layout resolved it.
Eight unchanged Unicode lines affected by Windows locale editing were restored
byte-faithfully before the final passing tests. Failed fixtures/source-hash gates
and informative results remain in private evidence; no false live verification.

Evidence: `D:/JFG-private/modern-prone-roll-20261020/native`, `independent`,
`controller/roll-bindings-final-handoff.json`, `build-result.json`, `delivery.json`.
The independent Modern-identity fixture and scaler-link issues were corrected
without weakening production gates. Same enabled guard/root/counters and fixed
18:09:13UTC deadline apply; no extension is assumed.

- Status: Modern roll bindings, automatic-roll preference, prone direction and backward-crawl corrections owner-accepted; unreleased.
- Severity: missing gameplay movement mechanic; no progression block reported.
- Affected report: v1.2.0, Windows 10, Xbox Elite Core gamepad; GPU unspecified.
- Source: [GitHub #33](https://github.com/TK22-26/JetForceGemini-Recomp/issues/33), created 2026-10-20 08:22 UTC and updated 08:25 UTC.
- Owner evidence: Modern lateral movement while crouched immediately crawls; Original Controls can roll. Exact owner runtime/profile was not supplied.

## Bindable roll actions and automatic-roll option requested (2026-10-20)

The owner additionally requests bindable Roll Left and Roll Right actions for
Modern mouse/keyboard and controller, plus an Advanced setting to disable
movement-triggered rolling. New bindings will default to unbound and automatic
rolling will remain enabled, preserving existing layouts. Implementation and
verification are in progress in the same guarded attempt; no extra time was
approved. Manual actions must remain available when automatic rolling is disabled.

The owner asked about vertical controller inversion: source default is Off
(`look.aim_invert_y=0`); the accepted preview profile retains On (`1`). No inversion
change was requested, and saved choices/Ctrl/custom bindings remain unchanged.

## Owner acceptance and remaining prone-roll regression (2026-10-20)

Owner confirms the backward-crawl correction and controller-assignment follow-up
are fixed. That live acceptance supersedes their earlier pending status below.
A separate defect remains: rolling while fully prone travels diagonally with
both reported Modern setups, while Classic/Original controls work correctly.
Reproduction: enter fully prone stance and roll laterally; observe longitudinal
travel alongside the lateral roll. Exact character, view heading and whether
previous crawl input is held/released remain to be measured. Assumed affected
preview: Modern Input Fix Preview, runtime
`db44d966bee4f28edf3dee08d76f9e78a9a38abd29c0b0a5975de9c562279882`.
Severity: movement-direction defect; no progression or save-loss report.

Prior fixtures verified native entry/repeat/release and backward-crawl motion;
they did not establish the full lateral roll trajectory. Cause and remedy remain
unconfirmed. Compare actual Classic/Modern motion and preserve the accepted
backward-crawl and assignment fixes, native roll behavior, Ctrl and custom binds.
The owner explicitly re-admitted the same shelved investigation for one guarded
attempt within the existing 18:09:13 UTC deadline; no added time or counter reset.
Evidence: `D:/JFG-private/modern-prone-roll-20261020`.

## Backward-crawl correction and follow-up preview (2026-10-20)

Implemented and verified in isolated native fixtures/build; owner live
verification remains pending. Both Modern keyboard/mouse and controller are
covered. This is an unreleased candidate.

Cause: the fixed Modern heading conflicts with the native backward-crawl flag's
30-update lock-on turn timeout. The resulting turn state can negate remaining
backward velocity on neutral release, producing the reported forward motion.
Earlier roll fixtures stubbed this direction helper and missed this interaction.
`ModernCrawlDirectionScope` in `src/boot/native_boot.cpp` runs after the actual
native helper, derives direction from filtered guest input, retains the prior
direction at neutral, and resets only the delayed-turn timer. Bounding that timer
also prevents signed-short overflow during a long backward hold. Native speed,
easing, animation and collision remain in control. Qualification requires the
current player-1 actor/control, connected/unblocked Modern input, modes 3/5,
humanoid crawl stance and no active roll. Original, mode 0 without the Modern
shoulder view, other ports/states and active rolls remain unchanged.

Exact adapter: 452 checks. Independent proof: 960 trajectories with both actual
humanoid crawl handlers and both input mappings. Old post-release forward-motion
samples: 4,352; candidate: 0. Persistent backward-turn-state samples: 11,760 to 0.
Also verified: 37,440 Original-equality frames, a 40,000-update backward hold,
signed-short boundary seeds and 16 crawl-to-left/right-roll trigger/repeat/release
cases. The actual section16 physics prefix reaches world-velocity writes, then
stops at first unmodeled call 0x80009A04; both handler fixtures use that shared
layout. Power/trig/sqrt, animation phase and easing constants are controlled
fixtures, not native timing measurements. Full second-character physics,
collision/render and physical play remain unverified. Roll transition checks
supply native side intent; full existing roll-gate proof remains the prior
5,132-check evidence. Initial fixture address/sign/compiler assumptions and
failed request syntax are retained with their corrected results.

Desktop: **JFG - Modern Input Fix Preview**.
Package: `C:\JFG-previews\modern-input-followup-20261020`.
Runtime SHA-256: `db44d966bee4f28edf3dee08d76f9e78a9a38abd29c0b0a5975de9c562279882`.
Release build, runtime protocol and the actual deployed launcher's extracted
helper init/setup pass. Current Modern Roll Preview settings/controller files/save
were copied and hash-verified unchanged; the old preview/profile remain intact.
Ctrl remains crouch; the C request was cancelled. This package also includes the
[INPUT-012 assignment follow-up](controller-remove-auto-reassignment.md).

Evidence: `D:/JFG-private/modern-crawl-reversal-20261020`, especially
`independent/final-verification.json`, `native/scope-harness/result.json`,
`applied-candidates.json`, `build-source-final.json`, `build-result.json`,
`baseline-preservation.json` and `delivery.json`. The previous frozen source is
preserved in `baseline-source`; current build source is `D:/JFG-roll-src-20261020`.
Tested scope SHA-256:
`69db8a355ad646e503a1e1d42aed323323817c7471a91992a19369f038da6f4c`.

Lesson: retain the actual-native release/long-hold fixture for future movement
changes; sign-only tests miss the direction/turn/physics interaction. Owner should
check sustained backward crawl, release, reversal and subsequent rolls on both
Modern inputs, then Original Controls. The same enabled production guard/root
and charges remain under the 18:09:13 UTC deadline. No game/emulator, public
issue action, commit or release was launched by this follow-up.

## Owner regression report (2026-10-20, follow-up)

The owner reports that crawling straight backward in both Modern keyboard/mouse
and controller modes produces a forward snap at the end, described as a
rubber-band motion. This is an open owner-reported movement regression, not
live acceptance of the roll preview. Assumed affected build: Modern Roll Preview
`48d5a17e38fba59d14ed867ffcd7ce3886f7725d901e777a69e8a1284ebac51f`;
exact level/character and whether the motion is visual or world displacement
are not yet independently verified. Reproduction: enter crouch/crawl, hold
straight backward and reverse; observe the forward movement at the end.
Severity: gameplay movement defect; no save-loss report. At intake, cause and
remedy were unconfirmed; the correction above records subsequent evidence. Existing input/native fixture checks did not validate this live
movement sequence. The fresh investigation must test translation over a full
crawl cycle, release and reversal, with both Modern modes and Original control
comparison; preserve native roll behavior. Prior tests remain evidence only
for their stated coverage.

Owner approved a new one-hour parallel follow-up, deadline 2026-10-20
18:09:13 UTC, on the same enabled production investigation/root/counters.
The temporary request for C as crouch was withdrawn: keep Ctrl and all existing
custom bindings. No crouch-key change was made. Evidence will be retained at
`D:/JFG-private/modern-crawl-reversal-20261020`.

## Reproduction and scope

The reporter can crouch and go prone with Modern Controls but cannot roll
sideways, on every attempt. Character, location, aim state and exact bindings
were not supplied; no support attachment or comment was present in the API
snapshot. The owner's subsequent comparison independently supports the symptom.

The owner later reports that attempted sideways crawling currently produces
forward crawling instead. This directional symptom is owner-reported, not
independently reproduced by the mapping/native branch checks. Its exact build,
character, camera orientation and directional cause remain unspecified. Do not
claim that the missing roll-action finding also proves this separate direction
problem fixed.

The latest published release checked during triage was v1.3.0. The evidence
below concerns frozen current working sources, not new live tests of either
release. Do not infer a v1.3 regression or which preview the owner tested.

The owner authorized one hour of parallel review ending 2026-10-20 13:43:01 UTC,
with findings required before implementation. Investigation used the guarded job
`high-refresh-rendering-20261011-modern-roll-review-20261020` under the existing
production investigation/root and retained counters. No game/emulator, product
patch, installed preview/profile change, commit, release or public issue action
was performed. Concurrent cutscene work remains separate.

## Authorized implementation (2026-10-20)

After reviewing the findings and selecting the v1 policy, the owner approved
parallel implementation for two hours and clarified: **Only the roll fixes**.
GH-032 mouse capture/inversion is outside this change. The implementation window
is 13:27:04 through 15:27:04 UTC on 2026-10-20. The enabled production guard retains
the same investigation/root and all prior counters, adding only the explicit
7,200-second allowance and the necessary named-peer job/grading headroom.

Implementation covers native Juno/Vela rolling from crouch and crawl, actual
keyboard movement bindings (either forward/back action blocks a roll, including
W+S together), lateral controller intent after the ordinary deadzone, held
repeats, and native gameplay qualification. The initial controller direction
boundary is the lateral sector of an eight-way stick: within 22.5 degrees of
left/right; diagonals remain crawling. There is no extra strength threshold.
This angle is an implementation choice pending owner feel-testing.

Independent mapping/native integration checks and an isolated preview are planned.
Original Controls, old recordings, mouse/look behavior, other ports, native
movement/animation and concurrent cutscene work must be preserved. No autonomous
gameplay, public GitHub action, commit or release is authorized by this work.
Private implementation evidence: `D:/JFG-private/modern-roll-implementation-20261020`.

## Preview delivery (2026-10-20)

The isolated Release build succeeds, and all eight selected CTest suites pass:
Modern roll, existing Modern controls, PC input, replay parsing, recorded-time
playback, controller ports, cutscene skip and rain fade. Independent final
native integration passes 5132 checks; recorded-time
review passes 78 cases, including mode 0.
The follow-up exact-adapter proof passes 5064 checks with no failures.
The mode-0 follow-up and timeline suites are rebuilt and retested after the
initial full build. Private evidence retains all initial and final proof
counts, the original failures, corrected tests, exact source hashes and limits.

Final review removed an unnecessary mouse-capture dependency: explicit Modern
roll intent now works in action-only mode 0 as well as modes 3/5. This changes
only roll qualification and its recorded-time context; capture/inversion code
is unchanged. Legacy modes 1/2/4, absent Modern identity or intent, wrong actor,
disconnection and native input/stance locks remain excluded.

Native dispatch retains helper selection. Review removed a redundant numeric
character-to-helper pairing because the cited upstream enum was an unverified
GameFlags enum, not a proven control-character mapping. The exact two-helper
whitelist, actual current actor/control identity, humanoid crouch/crawl stance,
Modern intent and all input/context gates remain in place; final proof covers
both eligible helpers. The unsupported pairing inference is not acceptance
evidence and is corrected in the retained native review.
Recordings containing the new roll-intent bits require an updated reader; older
runtimes reject those reserved bits. Existing recordings remain compatible.

Desktop shortcut: **JFG - Modern Roll Preview**.
Package: `C:/JFG-previews/modern-roll-20261020`.
Runtime SHA-256: `48d5a17e38fba59d14ed867ffcd7ce3886f7725d901e777a69e8a1284ebac51f`.
Frozen build source: `D:/JFG-roll-src-20261020`; build output:
`D:/JFG-roll-build-20261020`. The preview has the exact required 14 runtime files.
The deployed launcher helper's init/setup checks both pass, as does the actual
runtime frontend protocol probe. This verifies startup packaging, not gameplay.

The preview copies the Native Cutscene Skip Preview's current settings and save.
The source profile, active preview and shared build remain untouched. No game was
autonomously launched. The owner must still check left/right rolls with keyboard
and controller from both crouch and crawl, simultaneous/held-before-crouch entry,
repeats, release/reversal, look, aim/jump exits, nearby walls, and Original
Controls. The 22.5-degree controller lateral cone remains a candidate feel choice.
Sideways crawl remains deliberately unavailable in the lateral sector for v1;
the owner's earlier forward-crawl symptom has no separate root-cause claim.
GH-032 remains unchanged. No public issue post/closure, commit or release occurred.

The first native build exposed an existing renderer compatibility mismatch:
its frozen helper used C++20 `std::span` in the pinned C++17 RT64 target. The
concurrent renderer work had already replaced that signature with pointer/count
and updated its callsites. Only those three reviewed peer files were copied into
the isolated source; the original failure log is retained. The subsequent
build and renderer interpolation regression test pass. No shared renderer
source or shared build was changed by the roll task.

Source-freeze bookkeeping also stopped one build attempt before compilation:
the new untracked issue note was absent from the initial manifest. The corrected
manifest includes it and verifies all frozen source hashes; both failed-step
receipts are retained. No failed runtime was delivered.

## Implemented candidate and verification in progress

The sampler records explicit left/right roll intent in Modern flags 0x08/0x10.
The current player update captures that intent under the existing qualified
Modern action-table scope. Only the native humanoid crouch/crawl lateral helper
receives the missing held C-left/right action, and the held word is restored
immediately on return. The adapter checks current actor/control ownership,
player port, character, stance, gameplay/input locks, connection and action
table. It does not force a posture, zero analog input, alter animation/physics,
or turn the side action into a pressed-edge-only gesture. Native aim/jump
ordering and held-repeat remain in control.

Older recordings have no roll intent and retain their behavior. New recordings
preserve the explicit intent; qualification playback at recorded times preserves
a short roll request once, like a native button pulse. Conflicting skipped
left/right requests, incompatible source/connection changes and a pending pulse
followed by explicitly conflicting intent are rejected as unrepresentable rather
than silently losing or choosing an action. Standalone conflicting flags cancel.
Focus/replay suspension and current native locks remain independent gates.

Focused checks so far: 194 new policy checks, 161 existing Modern checks,
expanded replay parsing tests, 54 timeline checks; 2,919 exact adapter/memory
checks; independent real-mapping/native checks (2,168 checks, plus all 65,536
quantized stick-direction pairs against an angle oracle); and 1,290 checks through
actual adapter classes and unchanged native stance/helper functions. Fixtures
cover animation requests and ownership/branch behavior, not rendered collision,
feel, latency or full in-game transitions. Owner gameplay is still required.

Informative failures are retained privately: compiler output-directory quoting
was corrected without changing production code; a short-roll resampling loss and
a subsequent conflicting-intent edge were caught and corrected before delivery.
The first isolated CMake configure rejected the normalizer digest: the public
normalizer content was identical after line-ending normalization, but its original
private provenance used CRLF. The frozen build preserves that exact existing
script byte form; generated-source validation stays enabled and no generated
input or shared build was modified. Corrected configure passes.

The preview build freezes current source including existing accepted rain,
fog/camera/controller changes and concurrent cutscene/render candidates. Only
the roll/input-recording changes are introduced by this task; an isolated source
checkout/build avoids changing the active peer build or preview. This is not an
assertion that every previously pending candidate has received live acceptance.

## Owner-selected v1 policy (2026-10-20)

The owner selects the movement-based option and explicitly drops the proposed
gentle-sideways-tilt crawl behavior for v1. This supersedes the earlier fidelity
recommendation and low-tilt proposal below.

- Controller lateral movement intent requests the native roll from crouch or
  crawl. Retain the ordinary movement deadzone, but do not add a separate
  gentle-tilt band or require a strong-stick threshold to preserve sideways
  crawling. The precise lateral/diagonal boundary still needs candidate tuning.
- Keyboard/mouse uses an unopposed lateral movement action alone (default A or
  D, honoring remaps). Forward/back and diagonal movement retain crawling;
  opposing A+D cancels. Mouse look remains separate.
- Cover both supported humanoid low postures and preserve native held-repeat.
  Lupus remains excluded. LB/RB and D-pad are alternatives discussed, not the
  selected default layout.
- Sideways-crawl preservation is deliberately deferred. The owner considers
  it low priority and prefers revisiting it only if player feedback warrants
  it. This is a product priority, not a measured usage-frequency claim.

This records the selected behavior and newly reported symptom. No product code,
runtime/profile, tests, preview or release changed with this policy update.
The existing production guard, investigation/root, charges and review deadline
remain in force; this documentation update grants no new execution allowance.

## Confirmed cause

Regular Modern movement provides analog X/Y but never emits native C-left/right
lateral-action bits `0x2`/`0x1`. Those entries still exist in the native action
table; no current Modern action or binding exposes them. Rebinding Crouch or
adjusting sensitivity cannot restore a signal absent from the action catalogue.
The boss-specific mapper has separate lateral-bit translation, but that path is
not ordinary player movement.

Sources: [Modern action catalogue and mapping](../../../include/jfg/runtime/modern_controls.hpp),
[Original controller mapping](../../../include/jfg/runtime/controller_mapping.hpp),
and [native input dispatch](../../../src/boot/native_boot.cpp). Frozen source
anchors and hashes are retained privately because concurrent work can move lines.

| Input path | Observed output | Interpretation |
| --- | --- | --- |
| Original Normal crouch + C-left/right | Native crouch and held side bits (`0x4002`/`0x4001`) | Required roll action is reachable, consistent with owner's successful live roll |
| Modern gamepad crouch + full lateral movement | Crouch `0x4`, analog X +/-80; no side bit | Analog alone can enter crawl |
| Modern keyboard Ctrl + A/D | Crouch `0x4`, analog X +/-80 (Shift +/-127); no side bit | Same missing action; remapping movement changes analog input only |

## Native behavior and entry order

The unchanged Juno lateral helper (`0x01004934`) consumes **held** action-table
slots 5/6, not analog direction or pressed edges. Crouch mode 1 requests native
roll animations and lateral state 1/2. Left wins if both actions are held. An
unfinished maneuver keeps its direction; completion can restart a held action.
One-roll-per-press, double-tap or repeat delays would be new behavior decisions.

The Juno crouch handler (`0x01002EB4`) enters crawl state 2 when incoming movement
magnitude exceeds 0.5 without an active roll. With a side action, the roll
animation guards that transition: the same analog magnitude stays present while
the character remains crouched and starts rolling. **Global analog
neutralization is not needed for an already-crouched roll.** This native movement
threshold is not a verified controller engagement threshold.

Crouch is press-to-enter and persists after release. A symmetric Crouch-button
toggle was not established; native Jump/clearance can exit it. Testing whether
B/Circle/Ctrl is held is therefore insufficient.

The standing handler (`0x01002708`) calls the lateral helper in standing mode
before processing the pressed Crouch action. With absolute current forward
velocity at most 2, incoming magnitude above 0.5 enters prone/crawl state 2
immediately; lower magnitude enters crouch state 1. Forward velocity above 2
selects sliding crouch instead. The dispatcher chooses its handler once per
update. The actual-function proof confirms that adding side bits alone does
not prevent the simultaneous standing + Crouch + lateral analog transition.
A mapper waiting to observe state 1 can miss that entry entirely.

The eventual remedy needs an explicit entry policy using the genuine Crouch
press and qualified actor state, or a narrow native transition adapter. Bounded
analog-to-digital translation on entry is a design option, not a validated
remedy. Do not force state or replace native motion without proving transition,
input-lock, animation and collision behavior.

Already-prone state 2 uses distinct lateral states 3/4 and animation requests.
The original manual subsequently confirms rolling is intended from crawling
as well as crouching (see the documented-intent section below); the visible
runtime result still needs live validation.
Vela's helper mirrors the held-input structure; full Vela state transitions,
animation appearance and Lupus behavior are not established by the Juno proof.

## Original documented design intent

The owner's follow-up requested online evidence of the intended use before
choosing a Modern layout. Two original publications were retrieved and their
actual scanned pages visually inspected on 2026-10-20:

- [US instruction booklet, printed p.10 (PDF p.12)](https://www.videogamemanual.com/n64/Jet%20Force%20Gemini%20%28USA%29.pdf#page=12):
  distinguishes analog-stick crawling from C-left/right rolling. It explicitly
  describes the latter as an evasive action available while either crouched or
  crawling. The same side buttons provide standing sidestep/strafe.
- [Official Nintendo Player's Guide, printed p.7 (PDF p.9)](https://datassette.s3.us-west-004.backblazeb2.com/revistas/jet_force_gemini_nintendo_players_guide.pdf?VersionId=4_zd2580b9b75789e418f390019_f11538760ea54ba37_d20221006_m211339_c004_v0402010_t0041_u01665090819693#page=9):
  its Drop and Roll technique tells the player to get low, use a lateral
  C-button and evade shots. It explicitly excludes Lupus from this maneuver.

This establishes the documented intended role: a deliberate lateral combat
evasion from a low posture, alongside ordinary crawling. It also resolves the
earlier uncertainty about the *intended identity* of the native prone lateral
path: rolling is documented in both crouched and crawling postures. Rendered
appearance and full runtime behavior still require the candidate's live check.
The documents do not establish an invulnerability duration or damage-immunity
rule, and this review did not investigate damage logic.

**Historical design inference, superseded by the owner's v1 policy:** preserving independent crawl and roll choices is the
closest match to these original controls. Independently remappable roll
directions, or a deliberate roll modifier plus lateral input, therefore deserve
priority over automatically replacing every pure lateral crawl input. Hard-stick
thresholds or automatic A/D rolling remain possible Modern conveniences, with
an explicit way to retain crawling. No particular binding is selected here.

Candidate eligibility should cover the supported humanoids' crouched **and**
crawling roll paths, with Lupus excluded. This revises the earlier state-1-first
proposal. A simultaneous crouch/move input may enter native crawl, then request
its documented roll on the next eligible update; forcing state 1 is not implied
by the original design. That ordering and responsiveness still need candidate
tests and owner play, rather than claiming the missing entry behavior fixed.

Evidence is retained privately as `modern-roll-intent-review-20261020`, including
source URLs, PDF hashes and inspected page images. The booklet's PDF had no
extractable text, so the scan was checked directly. Initial PDF-reader setup
failed because the module was absent and the local pip configuration combined
user/target installation; a process-scoped override installed the reader only
in the private evidence directory. The original one-hour deadline and production
investigation/root/charges remain unchanged. This continuation adds no execution
seconds and implements no gameplay change.

## Earlier device-specific proposals

The following are the initial convenience-layout options. The subsequent
manual/guide review above favored separate deliberate roll input for fidelity.
The owner has now selected movement-based rolling without gentle sideways
crawling for v1, as recorded above. None is implemented.

- **Controller:** keep the look stick independent. Recognize deliberate lateral
  movement-stick intent for the native side action, preserving low-tilt and
  forward/back crawling. Lateral dominance, engagement/release thresholds and
  entry handling require physical-controller review. Do not reuse the existing
  digital-axis threshold as a proven roll threshold: raw 8689 produces only
  X=3 under the current default movement mapping.
- **Keyboard/mouse:** map unopposed pure lateral movement actions (default A/D,
  honoring remaps) to native side actions in qualified crouch context, with
  explicit entry handling. W/S and diagonals can retain crawl; A+D cancels.
  This replaces the current pure-lateral crawl gesture while crouched. Mouse
  look remains separate.
- **Alternative:** expose remappable left/right lateral or roll actions,
  preserving every current crawl gesture. This needs catalogue, profile
  compatibility, UI and help changes, plus deliberate posture/entry handling.

Share native action plumbing, with device-specific gesture selection. The input
sampler has an observed player actor/control pointer, but it can describe the
preceding update. Qualify current gameplay/player/character state; a numeric
stance alone is insufficient. Preserve Original Controls, native repeat rules
and existing menu, boss, aim, scripted, focus and device-transition gates.

## Attempts and evidence

| Action | Result and limit |
| --- | --- |
| Initial triage | Recorded unverified v1.2 report; private API snapshot `issue-triage-20261020/123300` retained |
| Owner comparison | Modern crawls; Original rolls; owner runtime unidentified |
| Current gamepad mapper proof | 262,149 checks pass, including every signed-16 lateral value on both selectable movement sticks and Original comparisons |
| Current keyboard mapper proof | 395 checks pass; all 8,388,608 existing action combinations examined, none emit the missing side bits |
| Unchanged native-function proof | 1,768 checks pass, retaining the 1,256-check crouch/crawl/helper baseline and adding standing-entry cases; generated span and fallback paths exercised |
| Early analog-suppression hypothesis | Rejected for already-crouched rolling; entry remains separate |
| Informative setup failures | Controller compile output-path quoting, missing native-fixture main-section relocation base, and an already-created documentation evidence directory; corrected only commands/fixtures/directory handling, retaining failed evidence |

Private evidence: `D:/JFG-private/modern-roll-review-20261020`. Subdirectories
`controller`, `mouse` and `native` contain final reviews, frozen sources, hashes,
harness outputs and receipts. Native animation remapping/progression, curves,
ceiling and math dependencies are explicit fixtures. These tests establish
mapping and branch behavior, not complete animation appearance, collision,
camera feel or a delivered fix. Generated game code, ROMs and saves remain private.

## Required candidate validation and remaining work

Separately check crouch first then sideways, simultaneous Crouch/sideways,
sideways held before Crouch, moving/sliding entry and already-prone movement.
Cover both directions, held repeats, reversal/release, opposing inputs,
controller low/full tilt and diagonals, custom bindings, mouse turning,
focus/device/style changes and Original Controls. Validate supported characters,
native animation/collision, camera continuity and recording/replay. Exclude
menus, boss, aim, airborne/swimming/ledge, damage and scripted/input-locked states.
The owner accepts the v1 sideways-crawl tradeoff. Direction classification,
ordinary-deadzone behavior and the eventual candidate require owner live play.

Cause is localized in the reviewed source; **no final remedy, fixed build or
release exists from this review**. The prior
[held-aim/diagonal-speed correction](github-held-aim-and-diagonal-movement.md)
does not establish roll coverage. The separate
[mouse capture/inversion report](github-mouse-look-and-inversion.md) remains
unresolved. The pinned upstream reference review/catalog was consulted without
updating dependencies.

## Transferable lessons

Input parity includes discrete native actions as well as analog movement.
Compare action tables and full state-entry order, not just button labels or
steady-state poses. Distinguish press-to-enter stance from held action and
preserve native animation eligibility. Mapping/fixture proofs do not qualify
physical input feel or live gameplay.
