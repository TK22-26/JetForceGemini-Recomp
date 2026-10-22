# GH-036: Missing weapon crosshairs

- Status: owner believes the existing accepted reticle correction already covers #36; treat as likely fixed locally, pending delivery and reporter confirmation. No separate repair investigation selected.
- Severity: aiming usability, reported on every attempt.
- Report: [GitHub #36](https://github.com/TK22-26/JetForceGemini-Recomp/issues/36), 2026-10-20; audited 2026-10-21 UTC.
- Setup: Windows 10, RTX 5060 Ti; input preset, bindings and output settings unspecified.

Owner disposition (2026-10-21): "36 I think is fixed already." Prioritize the
existing correction's delivery/retest rather than starting another reticle fix.
This is an owner assessment, not a new #36 reporter pass or released resolution.
The subsequent two-hour parallel repair allowance is for #38.

The reporter says several weapons, including rocket and homing launchers, lack
their UI crosshairs. No support ZIP is attached. The 2026-10-21 20:47 UTC audit
adds three comments that were absent from the previous review:

- @EnforcerRidley reports that the crosshairs which do appear resemble the
  pistol or sniper crosshair; they are unsure which. Treat wrong reticle identity
  as a separate, unverified observation.
- [@GenesisEB's frame-rate comparison](https://github.com/TK22-26/JetForceGemini-Recomp/issues/36#issuecomment-6317760225)
  reports missing explosives crosshairs after increasing frame rate above native,
  occasional flicker or a single-frame red lock indicator, and restored crosshairs
  after returning to native frame rate. Their suggestion about VSync-off visibility
  is a hypothesis, not a measured comparison.
- The original reporter reiterates the importance of higher-frame-rate play;
  they do not report testing the private correction.

Reproduce with the same weapon/aim state at native and elevated frame rates,
recording frame cap, VSync, resolution, controls, and unlocked versus red-lock
reticles separately. Native frame rate is a reporter-observed temporary workaround,
not a locally qualified fix or evidence that every affected setup behaves alike.

The symptoms overlap [#25's missing specialized reticles](github-ally-x-rendering.md).
Its output-timestamp correction is owner-approved locally and unreleased. This is
a candidate explanation for #36, not proof of the same cause or a resolved duplicate.
Ask the reporter to test the delivered reticle correction. If it persists, obtain
the affected-session support ZIP and record weapon, controls, Aim/Fire bindings,
resolution and frame cap separately. Preserve distinct reporter/hardware evidence.
The new comparison strengthens the rendering-timing lead but does not establish
that #25's correction resolves #36. Private issue/comment snapshot:
`github-follow-up-review-20261021T204709Z/github-issues.json`.

No additional code changes, native experiments or independent crosshair acceptance
were performed for #36 during this audit. Keep it open pending delivery and retest.
Lesson: matching visible symptoms on an older release should guide retesting, not
replace verification on the corrected build.
