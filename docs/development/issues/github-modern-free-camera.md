# GH-055: [proposal] Question for camera control

Status: Owner confirms already tested and approved as an optional Advanced control setting; regional/device coverage unspecified; unreleased.

Source: [[proposal] Question for camera control](https://github.com/TK22-26/JetForceGemini-Recomp/issues/55). Evidence snapshot retained privately in D:/JFG-private/remaining-gh-issues-20261027/github-issues.json.

## Reported symptoms and reproduction

### Problem or goal

Hi, this may not be a proposal per se but i dont know where else to ask. IÃ¢â‚¬â„¢m enjoying Modern Controls mostly for the updated aiming that lets me invert the YÃ¢â‚¬â€˜axis properly.

One thing IÃ¢â‚¬â„¢m struggling with is the camera behavior. When I rotate the camera, my character always turns with it, so I canÃ¢â‚¬â„¢t freely look around the character. IÃ¢â‚¬â„¢m hoping for a more modern thirdÃ¢â‚¬â€˜person camera where the camera can rotate independently, or alternatively, keeping the Modern aiming but using the original gameÃ¢â‚¬â„¢s camera behavior during normal movement.

Is this currently possible in Recomp and I just havenÃ¢â‚¬â„¢t found the option yet?

### Proposed change

ThirdÃ¢â‚¬â€˜person camera where the camera can rotate independently, or alternatively, keeping the Modern aiming but using the original gameÃ¢â‚¬â„¢s camera behavior during normal movement.

### How could we verify it?

_No response_

## Scope and evidence

Local owner-authorized batch: add default free camera / original movement option. Preserve existing approved fixes, user profiles and ROMs. No GitHub posting or issue changes. A reported symptom is not yet a confirmed cause. Attempts, results, final remedy and verification limits will be recorded here.

## October 27 candidate

Added Free movement by default under Modern Controls / Advanced settings, shared by controller and keyboard/mouse. Original turning/locomotion runs while the Modern independent camera remains acquired. Existing profiles default to current strafing behavior.

Implementation candidate; validation pending. No release or GitHub changes.

## October 27 local candidate

Modern controls now offer Free movement by default and a bindable Movement toggle action (unbound initially). Free movement retains the native body's movement/turning while the Modern camera remains independently adjustable. Holding Aim uses the existing Modern aiming path. Race and Floyd contexts are excluded. Focus loss preserves the chosen mode; the replay format records it explicitly. Profiles migrate through schema v8 with prior defaults and bindings preserved.

Component/configuration tests, the 1,015-check native UI suite, and normal Play comparisons passed. With the same input timeline, each mode produced 530 ordinary movement updates and 180 Aim updates. Strafe body/view remained aligned; free movement differed in 485 ordinary updates and returned to alignment for all 180 Aim updates. Both runs exited cleanly. This verifies native behavior and transitions, not broad campaign compatibility or the owner's final visual approval.

Private evidence: remaining-gh-issues-20261027/movement-aim-024-analysis.json and the underlying gameplay/replay traces. The first UI test exposed an identifier collision with existing directional-key controls; the new setting now has its own nonoverlapping identifier.

## November 8 owner acceptance

The owner confirms that #53 and #55 were already tested and approved as optional
Advanced control options. Record this existing acceptance; do not ask for repeat
manual sign-off. The confirmation does not enumerate ROM regions or input devices.
Earlier pending-review statements are historical. No release or GitHub closure
is implied.
