# GH-052: [Playtest] With Modern Controls the character turns transparent during combat

Status: resolved locally; owner approved the 180-unit non-transparent Modern Aim build after the preview launch repair. Regional/device coverage was not specified; unreleased.

Source: [[Playtest] With Modern Controls the character turns transparent during combat](https://github.com/TK22-26/JetForceGemini-Recomp/issues/52). Evidence snapshot retained privately in D:/JFG-private/remaining-gh-issues-20261027/github-issues.json.

## Reported symptoms and reproduction

### Problem type

Gameplay or progression

### Launcher and game build

1.4.0 Release build

### Windows version, GPU, and input device

Windows 10, GTX 1080, XBOX Controller

### What happened and how to reproduce it

With modern controls the character turns transparent in combat situations even though the camera is zoomed out.

I think an option to turn transparency during combat on or off would be good, in case someone wants to keep it as an enemy indicator.

Also i think an additional option for modern controls where the camera gets behind the character like with classic controls would be good.

### How often does it happen?

Every attempt

### Support ZIP and additional details

_No response_

## Scope and evidence

Local owner-authorized batch: separate native combat fade from proximity fade; add requested setting. Preserve existing approved fixes, user profiles and ROMs. No GitHub posting or issue changes. A reported symptom is not yet a confirmed cause. Attempts, results, final remedy and verification limits will be recorded here.

## October 27 candidate

Added Combat transparency under Modern Controls / Advanced settings. Default On preserves the existing native aim/fire opacity. Off bypasses only the player camera/aim fade API, retaining near-body camera fading and scene/death/other-actor opacity paths.

Implementation candidate; validation pending. No release or GitHub changes.

## October 27 local candidate and verification

Advanced Modern controls now offer Combat transparency, enabled by default. Disabling it replaces the native camera/aim opacity result only for the connected, owned Modern player in ordinary gameplay, while still computing the close-camera fade. Cinematics, Original controls and other actors are excluded. Existing profiles migrate with the previous behavior preserved.

A copied profile migrated through the real serializer to v8 and ran normal Play with the setting off. Of 1,701 calls to the actual native fade routine, 175 combat fades were removed and 1,344 close-camera fades were retained; the game exited cleanly. Configuration/UI checks also passed. Private evidence: remaining-gh-issues-20261027/opacity-028-analysis.json and opacity-026 capture. This is locally verified behavior, with owner batch review still pending.


## November 8 owner camera-distance follow-up

The owner confirms that disabling Combat transparency keeps the character solid,
but the camera eventually approaches enough to make the character transparent
again. The owner clarified that this happens while aiming or firing and approved
30 minutes of bounded investigation. The active manual session is the current
USA regional preview. This is partial confirmation of the opacity option, not
acceptance of the overall camera behavior.

Initial hypothesis: native combat/Aim framing still contracts camera distance,
so the preserved near-body fade becomes active even with combat fade disabled.
Camera collision, actual clearance and rendered eye position need to be
distinguished before changing behavior. Preserve the approved PAL Aim entry/
release sweep and original wall/floor handling. No cause or fix is yet claimed.
Private evidence: `issue52-camera-distance-20261108/`.

## November 8 bounded camera-distance candidate

Cause: Combat transparency Off changed the opacity decision but retained the
native ground-Aim camera's authored inward movement. Its eased close-up eventually
entered the deliberately preserved proximity-fade range. In a copied USA replay,
234 of 300 Aim updates faded (minimum alpha 145/255) with combat transparency Off.
This is an interaction between the option and native camera framing, not evidence
that the proximity fade itself is defective.

The candidate extends the native Aim point request to at least the existing
200-unit Modern shoulder distance, inside the qualified ground-Aim owner and
before its original scenery intersection and easing. The resulting native
collision point remains authoritative. Combat transparency On, Original controls,
scripted cameras and sniper optics retain their previous framing; the existing
actual-pose Aim-release transition and safety fade remain in place.

Source: `pc_combat_camera_request` in `include/jfg/runtime/pc_input.hpp`, the scoped
native Aim/ray integration in `src/boot/native/guest_execution.cpp`, and its transient
owner fields in `runtime_state.hpp`. The PC-input suite passes 2,354 checks,
including the new clear-view/opacity and unchanged optic/default contracts.

The first 110-second baseline stopped before its scripted Aim holds and therefore
did not qualify; the 180-second repeat covered both holds/releases. Two initial
standalone test compile commands lacked the generated catalog include and then
the stick-scaling implementation. Both failures are retained; the corrected
qualified compile and run passed. No generated game code or personal saves are
included in the repository.

Current result: candidate built for USA/PAL/JP; automated clear-route comparison passed on USA, PAL, JP; owner review pending.

- us: 300 opaque and 0 faded Aim updates; first release steps [0.9631605174051823, 0.9631605174051823].
- pal: 300 opaque and 0 faded Aim updates; first release steps [0.9692897715767267, 0.9692745928679595].
- jpn: 240 opaque and 0 faded Aim updates; first release steps [0.974071253298712, 0.974071253298712].
  Fixture limit: shortened JP clear-route scenario; standard 180-second third run was declined by the local deadline reserve.

Remaining: owner assessment of framing at level/up/down angles, sustained firing,
near-wall collision and sniper use. Automated clear-route results do not prove
every wall/floor, multiplayer or campaign situation. No new manual acceptance,
release, commit, push or GitHub issue change is claimed. Previous PAL/controller
Aim-release acceptance is preserved separately.

Lesson: an opacity preference must be checked alongside the camera ownership and
distance that can trigger a second opacity policy. Change requested camera
geometry before collision, not the already resolved position or safety fade.

Private evidence: `D:/JFG-private/issue52-camera-distance-20261108/` (baseline,
component output, regional identities, native qualification and failures).
Manual preview: `D:/JFG-previews/issue52-combat-camera-20261108/`.

## November 8 owner framing adjustment

The owner requests a slightly closer camera specifically in non-transparent
Modern aiming. This is framing feedback, not blanket manual acceptance of #52.
The next candidate sets the minimum ordinary Aim request to 180 units (10%
closer than the first 200-unit candidate), separately from the normal 200-unit
Modern shoulder distance. Collision handling, safety fading, native optics and
the existing Aim-release transition continue through their existing paths.
Build and targeted native verification are in progress. Private evidence:
`D:/JFG-private/issue52-camera-closer-20261108/`.

The 180-unit candidate passes all 2,354 PC-input checks. USA/PAL/JP runtimes are rebuilt and their packages verified. The owner elected manual camera checks; the started muted automated runs were cancelled before qualification, with partial logs preserved. No native-camera pass is claimed for this adjustment. Previous 200-unit evidence remains historical. This supersedes the planned
automated clear-route verification for the 180-unit adjustment.

The normal follow camera retains its independent 200-unit distance. This is a
small framing adjustment to the earlier candidate, not a change to collision,
opacity thresholds or release interpolation. The same Desktop test shortcut now
opens the closer build with a copied profile and retained selected region.
Owner visual acceptance remains pending; no commit, push or release is claimed.
Private evidence: `issue52-camera-closer-20261108/`.

## Preview launch correction

The closer preview initially rejected its USA save identity because staging converted the marker to CRLF. The marker is now restored byte-for-byte; the shipped launcher accepts USA/PAL/JP storage and every save/pak hash is unchanged. See [the staging issue](preview-save-identity-newlines.md). The subsequent owner approval is recorded below.

## November 8 owner acceptance

After delivery of the repaired closer-camera launcher, the owner replied
"approved". The assistant acknowledged this as approval of the closer camera
build, and the owner requested that this acceptance be entered in the Desktop
issue-review text file. The 180-unit non-transparent Modern Aim build is therefore
owner-approved locally. This supersedes the earlier pending camera-approval
statements above; they describe the status at those earlier handoffs.

The approval did not enumerate ROM regions, input devices or individual routes.
Do not infer that USA, PAL and JP were all manually tested. Native wall/optics
coverage beyond the recorded checks is not expanded by this acceptance. No
release, commit, push or GitHub issue closure is implied.
