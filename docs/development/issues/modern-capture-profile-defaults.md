# INPUT-008: Retained capture profile differs from modern defaults

Status: cause identified; owner's inversion choice corrected live; menu-binding UI verified in tests; local delivery/live confirmation pending. Severity: usability. Affected: draw-key preview, runtime source 27ddef0a5ed4afd1f1f9c26a5590b590cda5fe8e and retained route-capture profile.

During the longer owner measurement the owner reports unexpected mouse direction and E not acting as the expected A/Confirm. The attached Scooby-Doo image was accidental; the owner confirms JFG. Turning vertical inversion Off fixes the direction according to the owner.

The initial capture profile uses schema 2, E for Interact, Enter for Confirm, and mouse vertical inversion 1. After the owner's settings edit at approximately 13:38:51 UTC, schema 5 saves inversion 0, preserves Enter Confirm and migrates Backspace Back to Q. Keep this mid-session configuration change with the capture evidence.

Current source defaults use E for both Interact and Confirm in separate contexts. Saved Confirm bindings, including Enter, are deliberately preserved. The separate controls preview was previously aligned to E, but this older capture profile was not. Do not globally migrate explicit Enter choices based on this report. A profile-specific alignment can follow the recording without resetting other choices or saves.

Modern mouse default/reset is explicitly inversion On; existing unit/UI tests enforce it. PC-controls documentation describes On, while the Modern Controls settings table incorrectly said both mouse axes default Off. Correcting that table is documentation only. Changing the new/reset mouse default to Off is a follow-up choice; no new default or runtime fix is claimed here.

Remote develop at review is 63e49a7a71c3a914d2adc1d91fdcf00bef30d38e, already included by merge f70b513c896df107163f2d72abed344a87dc2517. The installed launcher's pinned modern_controls.hpp and modern editor/presentation source hashes match the merged source. Its older pc_input.hpp differs only by the later replay-focus helper. No evidence supports a missing merge of these controls.

Validation: read-only branch/provenance/configuration review and owner's live inversion report. No builds, tests or agent control mutations run alongside the measurement. E menu behavior follows the saved Enter binding; exact coverage of every guest dialog is not claimed. Raw inputs and the initial profile remain preserved.

Private evidence: final-measurement-20261016, session 20261016-133552-e6cd10c21fef4225a62f3f7b22eaadfa.
Compatibility lesson: merging source does not realign all retained preview profiles. Distinguish actual new defaults, saved preferences, and user-requested alignment of a known old profile. See [PC controls](../../features/pc-controls.md#modern-keyboard-confirm-default-2026-10-11).


## Confirmed hidden binding list bug

The owner subsequently added F as Confirm. The backend saved key.menu_confirm=70, but the Keys card did not display F. The owner also reports that Enter was never visible and expected E to advance Magnus dialogue. Source review confirms modernGroups filters keys to gameplay/scoped contexts, omitting menu-only actions. The earlier settings-only explanation was incomplete: retained bindings explain which key works, but the editor fails to show that binding. Preserve the owner-selected F and inversion Off. Current defaults already assign E to both Interact and Confirm in separate contexts; do not overwrite custom profiles. Candidate remedy: show explicit, editable Menus & dialogue rows in both list and diagram views, including unbound actions. Verification pending. Screenshots retained privately with this measurement. UI regression tests must cover Add F -> Confirm -> visible -> reload, clearing shared E without removing Interact, and old Enter profiles.


## Candidate UI remedy

Added a Menus & dialogue card to list and diagram views for keyboard and controller. Every menu action remains visible even when unbound; selecting its row captures a replacement and clearing affects only that action, preserving shared gameplay bindings. Help now explains that Confirm advances speech. No runtime mapping, defaults, owner F binding, inversion or save data changed. Native UI regression coverage added for old Enter, Add F to Confirm, persistence, shared E, unbound/rebind, diagram IDs and controller visibility. Candidate is not yet built or verified.


## Verification

The native offscreen RmlUi suite passes 717 checks, including the owner reproduction (old Enter profile; add F as Confirm; visible after reload), E shared with Interact, clearing and rebinding only Confirm, diagram visibility and unique IDs, controller menu editors and existing DPI/clear-button checks. The captured F layout was visually reviewed. This validates the editor; it does not prove every in-game dialogue branch. No desktop input was injected. Local launcher delivery follows; live owner confirmation is pending. Runtime controls and owner profile remain unchanged. Compatibility lesson: separate input contexts may share keys, but every stored action needs a visible editor and per-action clear semantics.
