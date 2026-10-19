# RENDER-015: Boss motion blur causes visual discomfort

Status: Owner confirms blur bypass removes the boss-motion smear/discomfort. Reduced-strength/native/off design remains open; other preview fixes still under owner review.
Reported: 2026-10-18. Severity: high usability/accessibility impact.

The owner reports Vela's boss arena stays at 120 output / 30 scene FPS but
movement smears the entire image and causes nausea/disorientation. The owner
requests disabling the effect if native blur is responsible. Previous acceptance
of softer authored Vela rescue shots does not establish that gameplay blur is
acceptable.

Affected: v1.3 private Glass and Controls Review, normal composite mode 4,
runtime SHA-256 669acb5f0cf377a40bd4f57cf7fd907a32890ee9141c01e1f2b7727426c845b2.
Private capture: D:/JFG-private/v13-owner-controls-20261018/owner-preview/
controls-42308-396164781.tsv and frames-20261018-235128-10164-0.csv.
After the first 10 seconds, present-return median is 8.342 ms and p99 is
8.845 ms. This is not a claim of zero stalls: transitions/pause are included
and maximum interval is 3.839371 seconds. The trace did not enable native-blur
events or images, so it cannot prove that the blur composite was running.

Hypothesis: native previous-frame compositing smears moving geometry even when
presentation is smooth. Next candidate presents the paired live world source,
using the existing source-only diagnostic whose visual effect the owner
previously reviewed. This intentionally removes the recognized composite,
including its native softness; unrelated scene logic is unchanged. Preservation
of all fades/effects still needs owner review. Do not describe this as a released
or fully validated fix.

Transferable lesson: stable FPS does not establish temporal image clarity.
Log effect activation separately from timing and keep accessibility preferences
distinct from fidelity comparisons.

The next private preview selects existing mode 5 at Play startup. It copies only a validated paired world source with matching dimensions/format; unsupported targets retain native rendering. Buffered blur-source audit records pass activation, source matching and whether each copy succeeded. This is an explicit effect-removal candidate, not a claim that native compositing was defective.

Combined private Motion Clarity Review prepared on 2026-10-18. Runtime SHA-256: 8c81e21948e0af3a269b875dc3147d7f80c46d2a9f1f9e6b98bc955ed3ab80b8. Build and focused navigation, semantic-presentation and 371 PC-input checks pass. Latest owner save/settings copied to an isolated profile, originals unchanged. Muted 120 FPS/VSync with buffered FPS, controls, blur-copy and glass-match evidence. This is not live verification or a release; the owner performs gameplay/visual review.


### Further evidence in the original owner capture
The submit records retain display-list lengths. Exactly 1,925 tasks have
623 commands, matching the native sixty-strip full-screen blur builder.
They begin at 218.636523 seconds, immediately after the boss-area transition,
and continue to 282.948680 seconds. Counts by native level: {181: 1925}.
Their output addresses alternate between the native feedback buffers. This is
strong evidence of active native blur in the reported fight, although the full
command fingerprint was not captured. The new audit records that fingerprint's
recognition and successful source copies directly.


### Owner A/B result, 2026-10-18
Owner: "yep, that removed it." The owner is still playing to check the other
candidates. This confirms the source-only presentation removes the reported
boss-motion problem; it does not establish that mode 4 exactly matches original
N64 feedback strength. No log has yet been finalized for this new run.

The owner wants some native character retained without intolerable smearing
and asks for design advice. Proposed next step: check history accumulation
against native scene cadence, then offer Off, Reduced and Original with optional
strength adjustment. Reduced should shorten temporal persistence and preserve
authored timing, rather than feed each interpolated output back into history.
A pure spatial softening treatment may preserve some softness without trails,
but would be a deliberate style approximation, not exact original rendering.
No new runtime settings or changes have been applied to the running review.


### Owner-approved direction
Owner favors Off / Reduced / Original and requests a high-FPS warning for
Original. Required default: Reduced, explicitly confirmed by the owner. Its strength still needs owner visual review.
Proposed inline copy when Original is selected with high refresh:
"Original blur creates strong motion trails and may cause motion sickness.
Try Reduced or Off if it feels uncomfortable."
Use an inline note rather than an interrupting popup. This setting/warning is
a recorded requirement, not yet implemented or shipped.


Finalized first Motion Clarity capture confirms 639 fully recognized native blur
passes and 2,543 successful source copies. One audited pass fell back as unpaired/
wrong-target; it was not silently counted as a successful copy. All 31,425 audit
rows were saved with zero overflow. The second glass/ledge review had no native
blur passes and no glass identity events, independently separating glass shaking
from native full-screen blur. Owner confirms the bypass removes the boss smear.
Reduced is explicitly owner-required as the eventual default; option implementation
and strength calibration remain pending. Existing preview still uses Off.


### Implementation handoff for the approved control
The three modes must be wired through VideoSettings parsing/serialization, the
native video-dialog request protocol, the RmlUi view and runtime configuration.
Old video.ini files must remain readable and select Reduced when no blur key
exists. Explicit saved Off/Original choices must survive subsequent launches.
The renderer currently uses process-cached diagnostic modes; a production
preference must not silently inherit the private mode-5 override. If applied
only on game startup, report that honestly in the existing restart UI.

The existing interpolated-history code seeds each output from a native
destination and keys history updates by workload identity. Reduced should
shorten native temporal persistence with a tested weighting rule; do not add
fresh feedback accumulation once per high-FPS presentation. Preserve unrelated
fades and reset history on scene/resource changes. Verify Off/Reduced/Original
mapping and existing-file migration in component checks; owner performs visual
comfort/fidelity comparisons at native rate and 120+ FPS. No numerical Reduced
strength or production runtime behavior has been implemented yet.


### Implemented candidate: persisted Off / Reduced / Original
The three-mode setting is now implemented end to end. Existing version-1
settings without the optional blur key and new profiles default to Reduced;
explicit choices persist. Version-2 video IPC carries the preference. The
existing running-game notice correctly reports that rendering changes apply
after restarting the game. Original at high FPS displays the requested inline
comfort warning. No popup or change to gameplay timing is introduced.

Reduced retains one quarter of the authored destination feedback, rounded to
native 8-bit alpha, in the two color commands of a completely recognized blur
pass. Original preserves those command values. Off applies full source alpha,
and at high FPS also retains the validated source-copy path. Native RAM is not
modified; unrelated display lists keep their original commands. Each high-FPS
phase reuses the native workload seed, rather than accumulating new history
once per output frame. Final visual strength/comfort still needs owner review.

Private diagnostic overrides remain separate, and the new preview does not
force mode 4 or 5 over the saved setting. An opt-in buffered audit records the
actual input/output alpha at the command handler for the owner's comparison.
Normal user launches do not enable that audit.

Configuration/migration/policy checks pass; semantic glass regression still
passes; 151 inactive-desktop RmlUi interaction checks pass with image capture
disabled. Runtime and launcher builds and frontend probe pass. The first
standalone launcher build exposed a sibling-header include-path error; the
include was corrected and rebuilt. No autonomous gameplay was performed.
Runtime 905aae5bf275e54c1ca543ed61d0dc3309767e2f20d6e6ae6fb9d639043ec88e; launcher 1fc0b12feb38390ea77a6807c069e9e5b0a6cee8ad66e0836a404329781e0e00.
Separate owner preview prepared with copied save/settings, original preserved.
This is an unreleased candidate, not owner acceptance of Reduced's strength.

### Owner review, 2026-10-18 evening

Owner reports that blur visually looks good in Blur Options Review. Reduced is accepted visually in the tested scene; Off / Reduced / Original persistence and UI have component coverage. A separate one-frame boss pop during left/right camera sweeps remains open, including while the boss remains on screen; see boss-camera-sweep-pop.md. Do not treat that pop as resolved by the blur preference.

## v1.3.0 source availability

The documented change is included in tag v1.3.0 (launcher/source
02be6fa9a4c50f4056f778c5148ca8ac70b0e92b; clean runtime
665596482a7395593e85dbe73f1bd4b016d183d9). See the
[combined release qualification](../releases-1.3.0-qualification.md) for owner
acceptance, source CI, package and publication evidence. Earlier failed attempts
and the scene/device/seed limits above remain part of this record; inclusion
does not turn an unverified broader report into a confirmed resolution.
