# Live map Mods layout and disabled-state review

- ID: UI-009.
- Status: owner-approved on 2026-10-21 after local preview review; verified in native UI tests and visual captures. Unreleased.
- Scope: Windows native RmlUi Mods settings, owner-supplied Live map settings HTML reference, 2026-10-21. No game profile or save mutation is needed to reproduce.
- Severity: minor visual/accessibility issue in the initial unreleased redesign.

The reference separates saved toggles from one-time actions, adds a save warning, active-mod count, amber switches, and a fixed footer. Existing runtime capability and grant acknowledgement remain authoritative; the mockup's immediate success-on-click behavior is not used. Floyd retains request feedback because its existing bridge does not expose a confirmed unlock result.

During source review, the initial new ON-switch rule was more specific than the shared disabled-button rule. Inject a snapshot with a saved health toggle and the mods-error flag: the unavailable switch could remain amber. The candidate adds a scoped disabled background/knob rule, plus a visible tab keyboard-focus bar independent of border styling. Synthetic snapshots and native rendered geometry cover these states without running a game.

Private evidence: mods-design-20261021, immutable guarded queue steps ui900 onward. Original source backups and failed checks are retained. The native fixture also exercises stopped/stale capabilities, pending/confirmed/unconfirmed weapon status, empty/nonempty active count, 100/125/150% scaling and compact-window scrolling.

Compatibility lesson: native RmlUi selector specificity and actual rendered scroll geometry must be checked after importing a browser design. Visual success must follow runtime acknowledgement. This layout does not fix gameplay inventory logic; see [GH-039](github-give-all-weapons.md).

No commit or released version contains this candidate yet.

Initial native integration run passed 941 checks. A later editing step implicitly read UTF-8 through the Windows legacy code page, corrupting the middle dot in a controller-label fixture and map symbol text. The full run correctly failed at check 439; this was an editing regression, not an unrelated controls defect. Restoring the exact UTF-8 characters fixes the cause, and all subsequent reads/writes explicitly specify UTF-8. A targeted --mods-only mode also executes the same native Mods fixtures independently of the controls suite.

Visual review additionally found that RmlUi flex badges with direct text produced empty colored circles. Explicit child text elements restore intrinsic text geometry; the fixture checks both count and ON text dimensions. The action visibility checks now require viewport containment and an actual native hit target, not merely a position above the footer.

Owner review caught the initial robot placeholder for Floyd. It is replaced by the reference open-padlock/sparkle line path. The encoding repair also normalizes the three edited source files to LF, avoiding doubled carriage returns during Windows writes. The corrected UTF-8 full suite passed 973 checks before this final icon/line-ending refinement.

Final validation: the corrected padlock/UTF-8/LF build passes all 973 native integration checks, including 100/125/150% scale, compact viewport containment, actual action hit targeting, badge text geometry, keyboard focus, disabled/error state, and real-feedback-only success presentation. The earlier targeted mode passed 86 checks. Final screenshots were visually reviewed. The current launcher was staged into the existing Give Weapons Fix Preview and its package manifest revalidated through the production resolver. Runtime bytes and profile/save contents were not changed by this UI delivery.

Private final evidence: mods-design-20261021/ui-padlock, package-verification.log and closeout.json. No public commit or release was created. The guard stayed enabled; all edits/builds/renders ran serially inside the already admitted Mods worker with its existing deadline and counters.

Owner acceptance (2026-10-21): the owner replied "approved" after the final Mods layout, visible ON/count badges and reference Floyd padlock were delivered. This accepts the presentation locally. Existing gameplay-command limitations and separate GH-039 save/reload/release checks retain their recorded scope. No additional test, commit or release is implied by this approval.
