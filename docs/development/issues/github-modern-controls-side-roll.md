# GH-033: Sideways roll unavailable with Modern Controls

- Status: Modern controller and keyboard/mouse roll candidate implemented; focused input/native checks pass, isolated build in progress, owner live verification pending.
- Severity: missing gameplay movement mechanic; no progression block reported.
- Affected report: v1.2.0, Windows 10, Xbox Elite Core gamepad; GPU unspecified.
- Source: [GitHub #33](https://github.com/TK22-26/JetForceGemini-Recomp/issues/33), created 2026-10-20 08:22 UTC and updated 08:25 UTC.
- Owner evidence: Modern lateral movement while crouched immediately crawls; Original Controls can roll. Exact owner runtime/profile was not supplied.

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
