# Mouse-look enabled before launch: reported startup crash

- ID: NATIVE-002; severity: high, release qualification blocker.
- Source: [GitHub #14](https://github.com/TK22-26/JetForceGemini-Recomp/issues/14), filed 2026-10-16.
- Affected report: v1.1.0, Windows 11, GTX 1650, keyboard/mouse. Mouse look enabled before launch reportedly fails every attempt; enabling after launch reportedly works.
- Status: access violation confirmed in supplied logs; current-build reproduction, cause and remedy unverified. Open.

The supplied support ZIP has SHA-256 `b86703183465c8906d41ef56e6149acde31b87f5c3f553ea6806004a1d961a93`. Its native log reaches `rom-ready`, then reports `0xc0000005`. The runtime build source is `d3b9d62e66cc4fdc2c27be5ad2e457a8ea7da394`; runtime SHA-256 `fa6e0ec8068a18ae23eaa24eb1a5cb66bbbe4d3a0b6197adda45ff6109a1cd80`. Crash, hang, breadcrumb and system logs are empty. The support data does not contain the modern mouse configuration or a stack. The reporter's OS description remains authoritative; the legacy launcher version string is not reliable OS identification.

Current source uses selected modern-control configuration and gates camera ownership during loading. Existing loading/entry tests cover a different defect ([CAMERA-003](modern-controller-state-transitions.md)); they do not identify this access violation. Neither later source changes nor successful owner play prove the reported launch sequence is fixed. The unrelated extended-play crash record [NATIVE-001](native-play-access-violation.md) cannot close this startup report.

No runtime remedy was attempted in this launcher-only review. Next qualification must reproduce enabled-before-launch versus enable-after-launch with the reported runtime and current candidate, copied profiles and matching crash symbols. Preserve the failing settings and startup stack before assigning a cause. Until then the Windows full-update gate remains open. Private evidence: `launcher-update-button-20261016/issue-14-support` and `issue-14.json`. No personal save or ROM is published.

Lesson: a bare access-violation exit code is not a diagnosis; generic camera fixes must not be used to close a startup crash without corresponding evidence.
