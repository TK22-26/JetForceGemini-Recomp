# Modern controller Floyd flight inversion

- Status: implemented in local preview7; automated checks pass and owner approved preview7 on 2026-10-21; unreleased.
- Report: 2026-10-21 owner likes inverted flight steering but requests an option.
- Affected: Modern controller, Floyd missions, local preview6. Push the movement stick up: Floyd pitches down regardless of normal look inversion.
- Severity: control preference limitation; flight remains playable.

The original mission handler uses movement Y for aircraft pitch. Normal look inversion belongs to the independent aim channel. Add per-player `pad_floyd_flight_invert_y`, default true, in Modern controller Advanced settings as **Invert Floyd flight steering**. Off reverses only mission movement Y before native aircraft steering. On retains existing behavior. Co-op reticle, normal look, mouse flight and Classic are unchanged. Profile schema7 migrates versions1–6 to On and preserves other bindings/preferences. Controller reset restores On; keyboard reset preserves this preference.

Validation and preview delivery completed; owner acceptance recorded below. Same enabled production guard, investigation and counters; approved deadline 2026-10-21 22:37:40 UTC. Private evidence: `D:/JFG-private/floyd-mission-mouse-flight-20261021/controller-flight`.


## Verification and delivery

Four focused component suites pass: PC input, Modern mapping/profiles, roll and navigation. Real RmlUi checks pass (920 checks), including a pointer click on the new toggle, saved reload, unchanged normal look/P2 settings, hiding on keyboard, keyboard reset preserving it and controller reset restoring On. Native flight tests cover 192 controller cases across both generated execution paths, all physical ports, joined/owner routing, both axis directions, both preference values and 1/2/3 update ticks. The original pitch and rotated forward-thrust signs match the setting; native Fire and thrust remain intact. Prior mouse steering/strafe coverage also passes: 3,963 cases / 438,752 checks total, native maximum speed8. The serial Release runtime and updated launcher build pass.

An initial scoped edit stopped because the older launcher-only snapshot did not contain the newer runtime mouse mapper. Only schema/UI edits were applied there; runtime edits remain in the root and isolated runtime source. An initial native fixture run lacked its private owner-memory input after copying the harness; restored the preserved input and reran successfully. These were preparation failures, not game regressions; failed logs are retained.

Preview7 replaces both launcher and runtime. Runtime protocol, helper setup and package inventory pass; existing profile/settings/save hashes are unchanged, so existing profiles gain default-On behavior through migration without rewriting them. Previous preview6 binaries are preserved privately. Schema7 requires the matching new launcher/runtime; older strict parsers do not understand the new field. Preserve a pre-migration profile when rolling back to old binaries. No ROMs, generated game code or saves are published.

Owner approved the delivered preview7 controls. No separate firing or mission-completion result was supplied; those broader checks remain pending. These automated checks are not full mission/EmuHawk replays. The broader Floyd report remains open until its outstanding live checks are complete. Transferable lesson: aircraft pitch is a movement preference and must not reuse an aim inversion preference; migrate defaults explicitly and test device/player/reset isolation.

Evidence: `D:/JFG-private/floyd-mission-mouse-flight-20261021/controller-flight/qualification.json`, `ui-results`, `native-integration/run-2.log`, build logs and `delivery.json`.
Runtime SHA-256: `85146670b22a83a7fb65a08db4a4abdc21065bd0aabdced0ce6159cc332e5479`.
Launcher SHA-256: `66b850f1cee6172091c5f3c84066944767f645a40ab47cb145551efe4ad06e89`.


## Owner acceptance — 2026-10-21

Owner replied “approved” after the preview7 launcher was opened for testing and the controller flight toggle/defaults and included mouse A/D strafing were described. Record the delivered controls preview as accepted, including the requested controller flight preference. No additional runtime change is required for this report. This approval supplies no separate per-case test transcript or completed mission result, so it does not close the broader Floyd firing/completion checks or establish an EmuHawk comparison for this preference. Local accepted change; no commit, push or release in this follow-up.
