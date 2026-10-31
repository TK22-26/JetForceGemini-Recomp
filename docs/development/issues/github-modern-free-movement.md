# GH-053: [Proposal] With Modern Controls a toggle for free movement (like with Classic) with a button press

Status: local candidate; configuration/UI/native movement and Aim checks passed; owner batch review pending.

Source: [[Proposal] With Modern Controls a toggle for free movement (like with Classic) with a button press](https://github.com/TK22-26/JetForceGemini-Recomp/issues/53). Evidence snapshot retained privately in D:/JFG-private/remaining-gh-issues-20261027/github-issues.json.

## Reported symptoms and reproduction

### Problem or goal

With modern controls there are only strafe movement controls, i thought a good idea would be to have a toggle with a button press that switches on the left stick between strafe movement and free 360 movement like with the classic control scheme while still retaining the rest of the modern controls, like you automatically have strafe controls when aiming while in the toggled free 360 movement mode.

### Proposed change

This toggle option could help with platforming sections and make those easier with modern controls.

### How could we verify it?

_No response_

## Scope and evidence

Local owner-authorized batch: add bindable strafe/free movement toggle. Preserve existing approved fixes, user profiles and ROMs. No GitHub posting or issue changes. A reported symptom is not yet a confirmed cause. Attempts, results, final remedy and verification limits will be recorded here.

## October 27 candidate

Added bindable Toggle movement action (unbound by default). It switches between the existing strafe scheme and native turning locomotion with independent Modern look; Aim temporarily strafes. Preference survives focus/menu suspension and is explicitly recorded in input replay bit 0x20.

Implementation candidate; validation pending. No release or GitHub changes.

## October 27 local candidate

Modern controls now offer Free movement by default and a bindable Movement toggle action (unbound initially). Free movement retains the native body's movement/turning while the Modern camera remains independently adjustable. Holding Aim uses the existing Modern aiming path. Race and Floyd contexts are excluded. Focus loss preserves the chosen mode; the replay format records it explicitly. Profiles migrate through schema v8 with prior defaults and bindings preserved.

Component/configuration tests, the 1,015-check native UI suite, and normal Play comparisons passed. With the same input timeline, each mode produced 530 ordinary movement updates and 180 Aim updates. Strafe body/view remained aligned; free movement differed in 485 ordinary updates and returned to alignment for all 180 Aim updates. Both runs exited cleanly. This verifies native behavior and transitions, not broad campaign compatibility or the owner's final visual approval.

Private evidence: remaining-gh-issues-20261027/movement-aim-024-analysis.json and the underlying gameplay/replay traces. The first UI test exposed an identifier collision with existing directional-key controls; the new setting now has its own nonoverlapping identifier.
