# Modern Floyd vertical aiming reversed with inversion Off

- Status: owner reproduced in Modern Players and Floyd preview 1; correction passes native tests and owner confirms preview 2 works; accepted, unreleased.
- Severity: reversed aiming direction; co-op input otherwise responds.
- Related: [Floyd cannot fire, #37](github-floyd-cannot-fire.md).
- Affected: Modern Floyd adapter introduced in the local 2026-10-21 preview.

Owner joined Floyd and confirmed controls work, but moving the mouse vertically
aims in the opposite direction. P2 Advanced Invert vertical was Off. The captured
P2 profile also has `look.mouse_invert_y=0`; this is not accidental enablement.
Owner closed the preview before requesting the correction. Controller direction
was not owner-tested; its adapter shares the same coordinate conversion.

The new adapter passed Modern positive-up look directly into the native absolute
Floyd stick. Original `0x80031090` negates Y at `0x80031160` into the reticle's
`+0x4C` offset, then subtracts that offset from screen centre at `0x8003136C`.
That reverses the displayed direction. Candidate converts the Modern Y sign at
this boundary for mouse and controller, after the saved inversion preference.
It preserves native reticle acquisition and the horizontal direction.

Earlier tests checked internal values but did not follow raw device motion through
the original reticle consumer into screen direction. New qualification must test
that entire path with inversion Off and On. Source/controller/reticle tests passed at initial qualification; the subsequent
owner acceptance is recorded below. The correction remains unreleased.

Private evidence: D:/JFG-private/floyd-p2-modern-20261021/vertical-inversion.
This establishes the local Floyd adapter regression, not a retrospective cause
for the separate mouse capture/inversion report #32.

Candidate qualification: raw mouse and controller input, Off/On, up/down, three sensitivities, one/three native ticks and both generated execution paths pass the original Floyd reticle consumer. Old adapter reverses all 96 cases; candidate reverses none. Runtime build and PC-input suite pass, including existing character/boss vertical-direction regressions. This is native consumer proof, not a GPU image or owner acceptance.

The first native fixture did not compile because its minimal CPU context omitted odd floating-point registers. Its log is preserved; the second fixture uses the original 8-byte register layout and odd-register pointer. Generated game code was unchanged.

Added a persistent raw-input regression covering mouse/controller, Off/On, up/down and three sensitivities. The native consumer independently established the expected sign. Focused suite passes.

Preview 2 delivered and launcher reopened with the same profile/save, hash-verified unchanged. P2 mouse inversion remains Off. Runtime SHA-256: `c16099ba8960efa8da60d9831788dbc9dcd9e36444552dbd6cb96104b550b37e`. Package protocol, helper verification and inventory checks pass. Previous preview binary and failed fixture log retained privately. Owner retest, mission completion and multiplayer-camera validation remain pending. No commit or release.

Owner retested preview 2 and confirms it works on 2026-10-21. This accepts the vertical-direction correction. A separate [widescreen bounds comparison](floyd-widescreen-aim-bounds.md) is requested; mission completion and broader multiplayer camera coverage remain separate.
