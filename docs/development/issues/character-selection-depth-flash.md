# Character-selection rainbow/white flash after SS Anubis

Status: open; renderer-role candidate implemented, native checks and owner retest
required before acceptance. Juno departure and Vela rescue skipping are separately
owner-confirmed working in the preview.

## Report and reproduction

After SS Anubis departure, return to character selection. Owner repeatedly sees
a bright flash both after a natural departure (preview9) and after a successful
skip (preview10). Preview10 uses Custom60FPS, VSync on, Reduced blur,100%fog.
Owner video is1280x720 at120FPS. Frames795 and796 at roughly6.625seconds show a
rainbow/white version of the room; adjacent frames794 and797 have normal materials.
It lasts about one60Hz output interval. This is a visual corruption, not evidence
of a simulation slowdown. It is not specific to skipping.

## Evidence

Private diagnostic session:
D:/JFG-private/v131-rnd-20261019/cutscene-skip/owner-sessions/20261020-125514-ff39bdc0ad794f13a82ffe189ddd4aa5.
Owner video: C:/Users/tjkos/Videos/2026-10-20 08-56-41.mkv.
Extracted frames and pixel measurements remain in the private cutscene-skip folder.
No video, ROM or save is published.

Native fade logs request black RGB, not white. Final room commands use color
buffers0x10FF00/0x135700 and depth0x15AF40. Depth is cleared through SetColorImage
before drawing to the color buffer. Earlier rescue shots use0x15AF40 as color.
The rainbow bands and white background resemble depth interpreted asRGBA16.
The failing output's selected GPU buffer has not yet been logged, so this is a
strong source-supported hypothesis rather than a confirmed final cause.

## Candidate

RT64 early-presentation history previously checked address, dimensions and VI
compatibility without checking that the current allocation still contained color.
The workload candidate list also admitted recognized depth-only clears.
src/renderer/rt64_present_source.hpp and cmake/rt64_interpolation.cmake
now reject depth-only clears as interpolation candidates and require a current
color write before using historical VI compatibility to redirect presentation.
A directly requested VI/debugger depth display retains the existing conversion
path. No map IDs, timed masks or extra fade are used.

Regression cases in tests/rt64_interpolation_tests.cpp cover color-to-depth-to-color
reuse, mismatched address/size, known depth clears and genuine flat-color clears.
Selected source/type, rejected depth-history matches and actual depth conversions
are recorded through the existing optional interpolation log.

## Limitations and informative failures

Preview10's optional image-capture environment flag was removed by the launcher's
intentional JFG_* sanitization. No in-game transition images were saved. Owner video
provides the pixel evidence; subsequent standard capture needs no GPU readback.
The earlier empty-list/present-skip observations did not establish a cause.
Native checks do not prove the visual defect resolved; owner must repeat the return
to character selection, then the selected-source logs can be reviewed.

## Compatibility lesson

A framebuffer address is reusable storage, not a permanent color-image identity.
Historical compatibility must be checked against the current role before selecting
an early display source. Keep intended depth presentation separate from this rule.

Related: [Native cutscene skipping](optional-cutscene-skipping.md).

## Preview11 validation

Native build and both jfg.rt64_interpolation / jfg.cutscene_skip tests passed.
The generated renderer contains the tested role predicates and diagnostic sites.
Preview11 is packaged with unchanged save/settings and no GPU readback capture;
owner visual retest pending. Private receipt: cutscene-skip/preview-receipt-v11.json.

Preview11 owner result: white flash persists. This candidate is NOT a verified fix. New closed capture: owner-sessions/20261020-131703-9007e95299e5435d89e625a93066989b. Reviewing actual present-source/depth-conversion events before further changes; Vela/Juno skip remain accepted.

Preview11 selected-source logs show zero present-depth-conversion and zero present-depth-history-rejected events in the complete capture. The originally suspected early-presentation depth-redirection path did not occur, despite the owner seeing the flash. Do not claim that path as the root cause. Investigating writes/copies into the selected color target and in-flight target ownership instead.

## Depth pixel match and copy diagnostics

The closed preview11 RDRAM depth buffer at 0x15AF40, decoded as RGB555, shows the same white background and rainbow geometry pattern as the owner video. This supports depth-as-colour contamination but does not identify the write that causes it. Both native colour buffers decode normally at exit. Private images: cutscene-skip/preview11-native-buffers.

Adding diagnostic-only framebuffer pair/binding, type-conversion and actual per-output texture traces. These distinguish in-workload copies and interpolated outputs from the already-eliminated presentation-time depth conversion. No new visual remedy is claimed; all traces are gated by existing diagnostics.

## Preview12 diagnostic handoff

Build and renderer/cutscene component tests passed. This preview retains accepted Vela/Juno skips. It adds fbpair-record/fbpair-bind, framebuffer-type-copy and present-output-target events, active only with diagnostics. It is not a new visual fix. Owner reproduction of SS Anubis departure/character-selection flash requested. Save and settings preserved, audio muted, no GPU image readbacks. Private receipt: cutscene-skip/preview-receipt-v12.json.

## Owner preview12 follow-up

Owner reports flash only after playing Vela rescue and Juno departure; skipping Vela prevents it. Two closed preview12 sessions are available: 13:31:19 and 13:34:45 UTC. The latter skips Vela. This reproduction constraint is being correlated against framebuffer copy traces. Tawfret intro skip and focus-return camera reset are additional open reports.

## Captured contamination path and preview13 candidate

Preview12 session 13:34:45 shows tick3676: pair0 clears 0x15AF40 depth; pair1 draws real colour0x135700 with that depth; pair2 binds0x15AF40 as colour for readback; pair3 restores0x135700 without drawing. The extra output overrides the readback target. At steady time532024022325 the depth texture2371041461952 is converted into output texture2371036445632, which is subsequently presented at532024032123. The base output uses real colour texture2371036444624. Thus the selected VI remains valid while an interpolated output contains encoded depth.

The current-workload candidate check now rejects a colour/readback allocation also used for depth by that workload. It leaves ordinary colour presentation, explicit VI/depth paths and later genuine colour reuse intact; no fixed address blacklist or frame hiding. Regression fixture mirrors the four captured pairs and proves the previous single-pair predicate accepted the bad candidate. Candidate pending build and owner visual retest.

Preview13 initial integration build rejected std::span because pinned RT64 uses C++17. Changed the workload helper to a pointer/count view without changing the renderer language standard or selection rule; failed build log retained. A call-site adaptation check initially expected seven replacements rather than the six actual calls and stopped before rebuilding; corrected to the audited six. Rebuild pending.

### Preview13 validation

Native build and renderer/cutscene component suites passed. The generated workload queue uses the workload-aware depth-use predicate. Packaged with save/settings preserved and muted audio. Owner visual confirmation pending; no frame suppression or hard-coded address ban. The previous preview11 failed remedy remains documented above.

## Owner acceptance of preview13

Owner confirms the flash fix in preview13. This accepts the local workload-aware depth/readback exclusion. Build and renderer tests passed before the visual review; no release yet. The capture is 20261020-135821-12ef9f4c072f4183a963b0f418e49df2. Earlier failed remedies and the captured cause remain above.
