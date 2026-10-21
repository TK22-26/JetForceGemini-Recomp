# GH-036: Missing weapon crosshairs

- Status: reported on v1.3.0; possible overlap with #25, not independently verified.
- Severity: aiming usability, reported on every attempt.
- Report: [GitHub #36](https://github.com/TK22-26/JetForceGemini-Recomp/issues/36), 2026-10-20; audited 2026-10-21 UTC.
- Setup: Windows 10, RTX 5060 Ti; input preset, bindings and output settings unspecified.

The reporter says several weapons, including rocket and homing launchers, lack
their UI crosshairs. No support ZIP or additional comments were attached at audit.
Reproduce with those weapons while aiming; exact controls and graphics settings
are still needed.

The symptoms overlap [#25's missing specialized reticles](github-ally-x-rendering.md).
Its output-timestamp correction is owner-approved locally and unreleased. This is
a candidate explanation for #36, not proof of the same cause or a resolved duplicate.
Ask the reporter to test the delivered reticle correction. If it persists, obtain
the affected-session support ZIP and record weapon, controls, Aim/Fire bindings,
resolution and frame cap separately. Preserve distinct reporter/hardware evidence.

No additional code changes, native experiments or independent crosshair acceptance
were performed for #36 during this audit. Keep it open pending delivery and retest.
Lesson: matching visible symptoms on an older release should guide retesting, not
replace verification on the corrected build.
