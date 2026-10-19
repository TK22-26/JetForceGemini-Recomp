# RENDER-012: Glass shakes in high-refresh mode

Status: Open. Owner rejects both identity-only and reflection-UV candidates; focused pane matching evidence awaits capture closure.
The report is not yet confirmed resolved. Target: v1.3.
Severity: visible rendering defect; no reported simulation/progression impact.

The owner reports on 2026-10-18 that glass is shaky in high-FPS mode while
reviewing the private Vela blur preview. The owner clarified: the breakable
glass in the room immediately before Vela shakes severely when walking near
it. The prisoner/capsule glass was separately confirmed stable by the owner;
do not treat these as the same rendering path or expand this symptom to all
glass. Affected baseline: 1.3.0-beta.2 owner blur review, runtime
a9654ea8d161b6906387eb2026ce5ecdb2c2a0b590745bc384a38d9ffa6133e6.
The copied profile initially selects custom 120 FPS with VSync; the owner's
actual setting at the report has not yet been independently confirmed.

Hypotheses to distinguish: unmatched transparent geometry; different camera
phases for glass and opaque scenery; native-rate animated texture or vertices;
incorrect transparent-pass ordering or feedback history. The owner's suggestion
of incomplete interpolation is plausible, not a confirmed diagnosis.

The current workflow leaves visual/gameplay verification to the owner.
No automatic replay or screenshot run was launched for this report. Keep the
owner's pre-rescue checkpoint and settings across candidates. The separate
source-workload blur-binding candidate is not yet a demonstrated glass remedy.

Related: [Vela rescue](vela-rescue-cutscene-stutter-resolution.md),
[late-object interpolation](tutorial-late-object-jitter.md).
Transferable lesson: a high output rate and high-resolution render target do
not establish that transparent and opaque surfaces share a presentation phase.

Owner verification: prisoner glass is visually stable in this baseline; the
breakable glass report remains open. No agent gameplay verification performed.

## Source finding and candidate, 2026-10-18

The pinned US transparent-object dispatcher calls glassDraw (overlay 101,
0x06500DCC) for behavior 78. Intact glass uses four vertices from control+0x0C
and double-buffered triangle/UV data at control+4/+8; it calls the already
observed camPushModelMtx. These vertices are a shared overlay quad, outside
the actor's model allocations. Existing rigid ownership only recognizes model
vertex ranges, so this custom quad lacks an actor key. Multiple intact panes
have identical local geometry and therefore cannot uniquely anchor the
fallback shape history. This is a concrete interpolation coverage gap, not yet
a live-confirmed cause of the reported shaking.

Candidate: recognize the validated intact quad and bind its existing captured
matrix to actor lifetime, control allocation, header and camera. Preserve exact
geometry/topology, matrix-byte and live-actor checks. Only positive intact
state +0x88 and a valid two-buffer selector qualify; shattered glass keeps its
existing path. No guest physics, damage, collision, glass opacity or timing is
changed. The prisoner's stable glass is not used as the scope of this patch.

Known limit: glassControl also generates camera-dependent texture coordinates
at native update cadence. This candidate does not yet interpolate those UVs.
If the pane edges become stable but reflections still step, investigate that
separately; do not call the entire issue fixed after a successful build.

Source: include/jfg/renderer/presentation_identity.hpp and pinned US overlay
101/transparent-object dispatch. Private generated code remains private.
Validation: source review only; compilation and owner visual result pending.

The intact-glass identity candidate compiles successfully. Runtime SHA-256:
881f1fd582c88ee560c4240e3723f8b3e47fa1f6d8a127441c1729ea8f42ac81. No gameplay or visual tests were run; owner review is pending.
The running blur-only comparison was not changed.

2026-10-18 follow-up: focused semantic-presentation tests pass for intact glass, shared quad ownership, alternating triangle buffers, duplicate/invalid owners and shattered state exclusion. Candidate is present in the current tree; live owner confirmation remains pending. Camera-dependent reflection UVs remain native cadence.

## Owner rejection of first candidate, 2026-10-18

Glass still shaky in runtime 669acb5f0cf377a40bd4f57cf7fd907a32890ee9141c01e1f2b7727426c845b2. Component checks did not establish live resolution. No autonomous visual verification authorized. Source/evidence investigation continues under the owner-approved bounded continuation, preserving all counters.

## Reflection UV candidate

Intact glass now supplies texture-coordinate velocity to the existing RT64 presentation shader. The history follows actor lifetime, camera and original quad vertex; double-buffer addresses and RT64 vertex copies do not change ownership. Texture-width/height wrapping follows the native reflection angle wrap. Missing scenes, lifetime changes, conflicting duplicate samples and invalid texture metadata reject history. UV motion is used only with a matched pane transform; authored glass opacity, collision, shattering and native endpoint coordinates are unchanged. Component checks pass; owner visual verification remains pending.

Combined private Motion Clarity Review prepared on 2026-10-18. Runtime SHA-256: 8c81e21948e0af3a269b875dc3147d7f80c46d2a9f1f9e6b98bc955ed3ab80b8. Build and focused navigation, semantic-presentation and 371 PC-input checks pass. Latest owner save/settings copied to an isolated profile, originals unchanged. Muted 120 FPS/VSync with buffered FPS, controls, blur-copy and glass-match evidence. This is not live verification or a release; the owner performs gameplay/visual review.


## Owner rejection of UV candidate, 2026-10-18
Owner reports "glass is still shakey" in Motion Clarity Review runtime
8c81e21948e0af3a269b875dc3147d7f80c46d2a9f1f9e6b98bc955ed3ab80b8.
The source-only blur bypass removed the separate boss-motion smear but did not
resolve this glass issue. Component checks establish the math and fixture
ownership behavior, not successful matching in this live room.

The running capture records event 7 in blur-source-audit: pane identities,
owned vertices, matched vertices and moving UV vertices. Review after clean game
exit before proposing another change. If identity count is nonzero but ownership
or matching is absent, investigate the live custom-quad/matrix association;
if matching succeeds, distinguish pane geometry/camera phase from reflection UV.
No changes made to the owner's running build or save. Prisoner glass remains
separately owner-confirmed stable.


### Source-supported missing identity cause
The native intact quad is an overlay constant, initialized from linked address
0x06501134. The renderer materializes overlay data into its expanded snapshot
and rewrites display-list references to that shadow address, but the actor's
control+0x0C pointer remains the linked overlay address. PresentationGuestView
rejects that segment. Our identity capture was validating the unconverted
pointer, so it never published glass identities. This explains the zero
pane records in both closed owner captures. The fix must resolve the pointer
through the same bounded overlay mapping used to materialize graphics data,
not relax general memory validation or guess a physical mask.


The overlay-address candidate resolves the complete 40-byte shared quad through
the same graphics address translator used for display-list materialization.
Both range endpoints must translate contiguously, and the resulting snapshot
range must be valid. Tests exercise the linked 0x86501134 alias in an 8 MiB
renderer snapshot and reject missing/cross-boundary ranges. The former fixture
only used ordinary RAM and therefore missed the real rejection. The test now
links the production translator rather than duplicating its implementation.
Visual acceptance is still pending; the absence of identity was confirmed by
the prior captures, while successful matching after this correction needs review.


The overlay-address candidate compiled and passed the semantic presentation and navigation component tests. Private owner preview runtime a452fcaf8dd0b3255eff3383bb85b41d14d4d83c3d8706f5dffda04d6f4347fe replaces the previously rejected build; saves/settings are preserved. Live glass verification remains pending. Blur remains Off for this isolated comparison; the owner-selected Reduced default belongs to the forthcoming three-mode setting.


### Owner verification of overlay-address remedy
Owner reports: "glass is fixed. capture closed". This accepts the rebuilt overlay-address candidate in the previously failing pre-Vela breakable-glass room. The actual cause was rejected shared overlay vertex addresses, preventing glass identity and UV interpolation from activating. The remedy resolves and bounds-checks those addresses through the renderer production translator. Component regression checks pass, and owner live verification is now positive. Not yet released. Other glass types/levels are not implied verified by this room-specific result.

Closed owner audit blur-source-audit-17923699591324738.csv saved 8664 rows and reports zero overflow. It now contains 724 glass-identity events, whereas both rejected builds had none. See the private glass-overlay-audit-summary.json for matching counts; owner acceptance remains the visual evidence.
