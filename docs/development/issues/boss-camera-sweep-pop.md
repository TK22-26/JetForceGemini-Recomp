# Boss briefly pops during camera sweeps

- Status: camera-aware correction component-tested and owner-verified in the local v1.3 Boss Camera Review; unreleased. Five isolated shared-camera fallback updates remain in the completed capture; this is not full zero-stall qualification.
- Severity: visible rendering glitch; repeated boss-only interpolation holds during camera motion corrected in the owner-reviewed candidate.
- Build/profile: v1.3 Blur Options Review, runtime 905aae5bf275e54c1ca543ed61d0dc3309767e2f20d6e6ae6fb9d639043ec88e; owner Vela boss testing.
- Reproduction: turn camera fully left then fully right. Boss appears to jump or disappear/reappear for one frame while remaining on screen.
- Evidence: owner live report 2026-10-18 evening; current owner capture on D:/JFG-private/v13-blur-options-20261018/owner-preview.
- Hypotheses: discontinuous camera/actor interpolation, unexpected visibility rejection, or native camera-dependent draw. None confirmed. Owner accepts blur appearance separately.
- Attempts: initial source/capture investigation only. No autonomous game or visual run; owner verifies candidates.
- Remaining validation: broader v1.3 regression/performance qualification; retained isolated shared-camera fallback updates are documented below. Original hardware comparison is not claimed.
- Compatibility: retain native simulation and boss behavior; do not mask a real visibility issue by interpolating across camera cuts.


### Targeted evidence prepared
The current history matcher rejects an entire actor if any of its vertices
fails continuity, including a projected movement threshold during a camera
sweep. This is a plausible lead, not a confirmed cause in the owner capture.
Prior captures lacked per-actor history outcomes. New opt-in numeric rows record
registered/submitted actor geometry, actual interpolation matches, rejection
reasons and camera identity/view operands. Native model draw calls identify actor,
behavior, selected model and opacity. Rows stay buffered; no screenshots or
per-frame file writes. Normal releases do not enable this audit. Owner replay of
the camera sweep is still needed to connect any rejection or missing draw to
the visible pop; no boss behavior or interpolation policy has changed yet.


### Source finding while owner records ? 2026-10-18

The semantic history gate is actor-wide: a missing vertex endpoint or a projected
motion rejection for any vertex clears every matched vertex of that lifetime
(semantic_presentation.hpp, record_into). The final renderer then sets each
owned transform's matched flag to false and holds its complete current
world/camera endpoint (rt64_f3ddkr.cpp, semantic conversion). Other scenery may
continue blending its camera over the same displayed frames. This is a concrete
mechanism for a brief relative jump, but is not yet tied to the reported boss
event. A large boss can have an off-screen vertex even while its body remains
visible; owner confirmation that the boss stays on screen does not exclude this
gate.

Do not simply relax all motion/cut limits. If the completed capture confirms
this path, evaluate camera continuity separately from actor deformation, while
retaining actor-wide animation decisions, real camera-cut checks, lifetime and
topology protections. No interpolation policy has been changed for this lead.
The current capture parser associates native behavior rows with each individual
run rather than combining actor addresses across processes; addresses can be
reused and are not sufficient identity on their own.


### Owner capture reviewed ? 2026-10-18 21:38 Eastern

Owner supplied 22 VLC snapshots (Pictures/vlcsnap-2026-10-18-21h36m56s449.png
through 21h37m24s203.png) and clarified that the boss glides then jumps in
position rather than simply disappearing. Stills alone cannot establish
successive video-frame timing; VLC snapshot filenames are extraction times.

Completed private evidence: door-owner-preview/controls-11628-401718000.tsv and
blur-source-audit-17923730415929679.csv under the existing v13-blur-options
evidence folder. The audit reached its fixed buffer limit: 555408 events total,
262144 saved, 293264 dropped. Later events cannot be claimed analyzed. Preserve
this limitation; future focused capture should avoid logging the entire route.

In the retained portion, the prominent 2532-vertex actor at 0x801bc0a0,
model 0x80318020, lifetime 577, has geometry in all 2893 sampled scenes, but
222 scenes hold its current endpoint. It transitions from matching to holding
53 times. Beyond the initial scene, the rejection reason is projected motion,
with no invalid or conflicting vertices. At tick 11671 a single failing vertex
is enough to suppress interpolation for the entire actor. This strongly
supports the actor-wide continuity fallback lead, but exact correspondence
to the owner's video frames still needs timestamps and positive boss-model
identification. Analysis receipts: boss-audit-summary.json and
boss-owner-finding.json. No boss fix is shipped.


All 22 owner-supplied stills were inspected. The series shows successive
groups with the boss near the same screen position while the room and reticle
advance, followed by a larger boss position change; it also contains visible
afterimages. This is consistent with the hold/jump lead, not proof that blur is
the initiating cause. The original video path was requested to verify adjacent
frame timing. Do not assume the snapshot extraction times are playback times.

The retained actor's holds include 31 spans of four scenes, seven spans of five
scenes, and three spans of six scenes. Its recorded native draw opacity is 255
throughout (18500 draw observations); this actor is not fading in/out via native
opacity. Retained history ends near 292.4 seconds into the run, whereas the
native controls trace continues. Do not extrapolate the detailed history to the
unrecorded remainder.

No new runtime was installed after this owner run. The additional door material
packet is source-only, not compiled or deployed. Next continuation must build
and validate it if retained. The current owner preview still has runtime hash
b668ab7dafdd338ae10206d8dc1618e10482fdce114cdfb935420d92a6c340ca.
The same production investigation retains all prior guard counters and roots;
finishing this approved session does not authorize another attempt.


### Two-hour owner continuation ? video correlation and candidate

Owner provided private owner video 2026-10-18 21-28-31.mkv (7.94 s,
1280x720, 120 FPS H.264). All 22 screenshots were matched against decoded video
frames; they map to frames 385?409 (3.208?3.408 s), mostly adjacent frames.
This verifies the screenshot groups are not seconds apart in gameplay.
The clip's start time places them approximately 272.6?272.8 seconds after the
controls trace began. The retained trace has motion rejection holds at
272.688?272.787 s; exact cross-clock alignment is still approximate.

Video inspection shows groups of four output frames with nearly fixed boss
screen position while scenery advances, then a larger position change.
The log still submits 2532 actor vertices, native opacity 255. This supports a
presentation history failure rather than native disappearance or fading.
Private numeric correlation: snapshot-video-matches.json, clip-log-window.json
and within-hold-video-differences.json in D:/JFG-private/v13-boss-camera-20261018.

Candidate: semantic skinning now carries the actual emitted camera's immutable,
validated view/projection operands and room generation. With trustworthy
operands, camera continuity and per-vertex world movement are checked
independently. Ordinary camera motion cannot reject an entire actor merely
because one near/off-screen vertex moves far in projected coordinates.
World displacement remains bounded to 128 guest units per source interval,
matching the established bridge bound; camera angular/eye motion, lens changes,
room generation, missing endpoints, topology and invalid samples still reject.
Unknown/ambiguous camera operands retain the conservative existing policy.

The actor's joints still interpolate together. No simulation, AI, input or
collision changes. The scoped door workaround and accepted glass/blur settings
remain. Component regression checks cover a visible body plus an extremity
crossing the camera plane, 120/360 output phase continuity, world relocations,
invalid vertices, duplicate conflicts, model changes, cadence, camera/zoom cuts
and stale operands. Build and live verification are separate; candidate is not
yet owner verified or released.

Runtime compiled and semantic component regressions passed, including existing glass/door checks. Boss Camera Review packaged with runtime c955a489f9be1e63dded2ba16f2cb4d1205e7519054e91cddd8c8fcd75d56506. Latest owner save copied without modification; 120 FPS, Reduced blur, VSync on, starts muted. Owner visual verification remains pending.


### Owner acceptance and completed capture - 2026-10-18 21:58 Eastern

The owner reports **"the boss now feels and looks good"** and explicitly closed
the game. This is owner live visual verification of Boss Camera Review,
runtime c955a489f9be1e63dded2ba16f2cb4d1205e7519054e91cddd8c8fcd75d56506,
120 FPS target, VSync enabled, Reduced blur. No autonomous gameplay or visual
test was performed. The candidate remains local and unreleased.

Completed evidence under D:/JFG-private/v13-boss-camera-20261018/owner-preview:

- blur-source-audit-17923747965087005.csv: all 235,211 events saved, zero dropped.
- controls-25156-403472921.tsv: full owner trace to 288.58 seconds.
- frames-20261019-015316-38940-0.csv: 33,629 output observations; queue dropped
  zero and writer_failed zero.

The actor/model matching the previous prominent boss evidence
(0x801bc0a0 / 0x80318020, new lifetime 564) submits all 2,532 vertices in
every one of 611 captured source scenes. It interpolates in 605 scenes. The
new event 11 proves **140 scene updates** would have hit the old projected
motion rejection but instead keep every submitted boss vertex matched with a
validated continuous camera. This connects the implemented remedy to the
actual owner run rather than only to synthetic tests.

There is one initial history/cadence hold and five isolated later holds, at
ticks 16610, 16686, 16830, 16888 and 16946. Each later hold also affects all
other submitted semantic actors at that tick, including the player. They
coincide with shared camera changes; the earlier boss-only multi-scene
projected-motion hold pattern is absent from this boss segment. The audit
stores only four view coefficients, so it does not independently prove which
full camera continuity sub-check rejected each update. Preserve these as
conservative shared-camera fallbacks, not a claim that every source update
interpolates. The owner did not report a visible problem in this pass.

Performance is a separate qualification: during the recorded boss interval,
2,432 present-return observations have median 8.338 ms, 99th percentile
8.919 ms and maximum 33.487 ms; three exceed 16.7 ms. Across the entire run
the maximum is 526.802 ms; the full-run outlier has not been attributed here.
These are CPU present-return intervals, not monitor scanout measurements or
proof of native simulation slowdown. Do not describe this capture as a
zero-hitch full-run performance pass.

Final cause/remedy for the reported repeating glide/jump: the previous
screen-space vertex-motion guard could misclassify normal camera motion as an
actor discontinuity and hold every joint while surrounding camera motion kept
interpolating. The candidate checks validated camera continuity separately
from bounded world-space deformation. It retains lifetime, topology, invalid
sample, actual camera-cut and unknown-operand protections. Simulation and
boss behavior are unchanged.

Private summaries: boss-audit-summary.json, owner-candidate-rescues.json,
owner-candidate-holds-and-timing.json, residual-hold-classification.json.
Existing component/build validation passed before this owner run; no runtime
changes were made after acceptance. The scoped door opaque workaround remains
a separate open transparent-material investigation.

## v1.3.0 source availability

The documented change is included in tag v1.3.0 (launcher/source
02be6fa9a4c50f4056f778c5148ca8ac70b0e92b; clean runtime
665596482a7395593e85dbe73f1bd4b016d183d9). See the
[combined release qualification](../releases-1.3.0-qualification.md) for owner
acceptance, source CI, package and publication evidence. Earlier failed attempts
and the scene/device/seed limits above remain part of this record; inclusion
does not turn an unverified broader report into a confirmed resolution.
