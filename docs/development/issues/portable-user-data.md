# LAUNCHER-004: GitHub #24 portable user data

- Status: local implementation qualified, desktop preview prepared; owner visual review and v1.3 release pending.
- Report: https://github.com/TK22-26/JetForceGemini-Recomp/issues/24
- Reported: 2026-10-18; current public launcher, release unspecified.
- Severity: portability/data-location limitation; no reported save corruption.

## Reproduction and cause

Place portable.txt beside JFG-Launcher.exe and launch from an extracted release.
The native frontend unconditionally selects LocalAppData/JFGRecomp/profiles/default.
No marker handler exists. The C# setup/support root and inventory asset cache
also independently select AppData. Redirecting only the profile would leave
reports and caches behind.

## Candidate and compatibility

Recognize portable.txt beside the actual launcher, and an explicit --portable
launch option. Use userdata beside the launcher for the application's data
root, including profiles, imported ROM, helper extraction, caches and support
reports. Pass that root to embedded helpers, whose extraction location must
not become the portable base. An explicit --profile remains authoritative for
its profile; normal launches retain the existing AppData location. Do not move,
overwrite or silently merge existing saves. Document copying an existing
profile while the launcher/game are closed. Moving the portable directory
must resolve its imported ROM and bundled runtime at their new locations.

## Validation and remaining work

Path/relocation tests, the launcher build and native storage/restart checks pass.
No runtime gameplay or owner visual verification is claimed for this new window. Keep #24 open until the combined
candidate is verified and released. No GitHub response has been sent.

## Implemented settings window

Owner requested Game > Settings... as a separate native window matching the
existing RmlUi settings dialogs, with only the portability option initially.
The new Storage section shows Portable mode, its data location, and what
switching does. Apply and restart is explicit. A running game or explicit
--profile blocks migration; the UI explains why. Cancel leaves storage alone.

The host authenticates the dialog process/owner, persists current settings,
copies each non-linked profile into a new destination via staging, then changes
portable.txt. Existing destination files are preserved; only missing persistent files are
added. The original saves remain in place. Only persistent settings/save
files and the imported ROM are copied; transient diagnostics/cache links are
not traversed. Caches/reports are recreated under the selected shared root.
The native frontend restarts after releasing its singleton lock; the new
process resolves the marker afresh and forwards JFG_DATA_ROOT to helpers.

Files: launcher/native/storage_settings.hpp; src/app/frontend_win32.cpp;
launcher/ui/storage_settings_ui.hpp and assets/settings.rml/settings.rcss;
launcher/windows/FirstRun.cs, Launcher.cs and InventoryImages.cs.
The legacy setup helper also honors the forwarded root.

## Checks and informative failures

650 launcher checks and 28 setup fixtures passed, including helper/cache/report
root forwarding and moved-package resolution. Focused storage fixtures verify
save/ROM copying, unchanged source data, existing destination preservation,
marker toggling, moving the game folder and rejection of invalid destinations.
RmlUi checks cover the Game menu, one-option dialog, displayed copy/restart
semantics, enabled/disabled states, both directions and layout.

The first native restart fixture used invalid dummy DLLs and was correctly
rejected by package validation. It was corrected to synthetic PE headers for
all required members; no real game executable or ROM is run. A later fixture
raced the startup worker by trusting a status file from the previous launch.
The host correctly rejected that busy-state request. The fixture now waits
for the same idle condition required by the real Game menu. These fixture
failures are not claimed as production bugs or successful qualification.

A destination that already contains first-run settings is handled by copying
only missing persistent files. This avoids an empty initialized portable profile
blocking migration of an existing save. Conflicting files (including saves) are
never replaced. Successful staging copies are cleaned only after validating
their absolute parent/name; failures preserve their staging evidence.
Map preferences and separate navigation profiles are included; transient
diagnostic/cache directories are excluded.

## Initial toggle candidate qualification and delivery

The final candidate passes 650 launcher checks, 28 mocked setup checks,
19 filesystem/storage checks, 20 RmlUi checks and three actual frontend
restarts on an isolated desktop. The production frontend source is compiled
with a test-only AppData root for that last check; the public binary has no
test-root override. The route switches normal -> portable -> normal ->
existing portable, verifies copied bytes and retains distinct save progress
at both destinations. All runs are ROM-free; no game is launched.

The native restart test and accepted window/layout checks are in
tests/storage_frontend_smoke.py and launcher/ui/tests/storage_settings_ui_tests.cpp.
File checks also verify missing preferences are added to existing profiles
without replacing their saved progress. Existing map preferences are copied.
[Source-pinned qualification](../../../evidence/portable-storage.json).

Desktop: JFG - Settings Preview. The private package starts portable with an
independently copied profile/ROM and muted audio. Its accepted gameplay runtime
is unchanged; only the launcher is replaced. Switching Portable mode off
explicitly selects normal AppData profiles; it keeps existing destination files.
The source profile hashes were checked unchanged after preparation.

Private evidence: v13-door-material-20261018/settings-delivery.json and
settings-validation/. The two informative fixture failures and successful
native checks are retained on D:. No GitHub response, closure, commit or public
release was performed. #24 remains open pending owner review and release.

## Owner-requested directory picker revision (2026-10-19)

The owner rejected the toggle UI and oversized Done button: show the actual
directory, provide Change directory... with the Windows folder picker, and
match the existing controls dialog's Done dimensions. The old toggle preview
and its qualification receipt remain preserved in private evidence.

Candidate: replace the two-mode setting with an arbitrary data folder.
The native IFileOpenDialog starts at the current folder; cancellation and
choosing the current folder do not copy or restart. A different selection uses
the authenticated settings-window IPC, preserves existing destination files,
copies missing persistent profile data and restarts. storage-location.txt uses
UTF-8, relative paths within the package and absolute paths outside it.
The chosen root propagates to the extracted helper, ROM import, caches and
reports. portable.txt and --portable compatibility remain supported.

Done now uses the controls dialog's 76dp minimum width, 36dp height and 16dp
horizontal padding. The window is shorter and only presents the data folder,
Change directory..., a short restart note and Done. Changing folders is disabled
during gameplay or an explicit --profile launch, while Done remains usable.

The first restart fixture in this revision stopped at a startup dialog; its
evidence is retained pending diagnosis. This does not establish a product
regression. Native picker cancellation and component UI checks passed.
Full restart qualification and owner review remain pending until recorded below.

The startup failure was a fixture-isolation defect: the storage-test executable
still used the production single-instance mutex, so the owner's open preview
correctly blocked it. The fixture now uses a test-only per-process mutex, as the
existing video fixture already does. Production singleton behavior is unchanged.
Failure evidence and the separate owner processes were preserved; only the
failed hidden fixture process was stopped.

## Directory-picker qualification and delivery

The revised candidate passes 655 launcher checks, 28 mocked setup checks,
23 storage filesystem checks, 21 storage UI checks (including cancellation
of a real Windows folder picker), and three actual frontend restarts.
The fixture verifies both normal and relative portable roots, preserves
existing destination progress, and reads back the dark-caption setting on
the main and Settings windows. The revised preview also includes the newly
requested Video Settings tabs and default-off fog enhancement.

The desktop Settings Preview has been updated, with original binaries/profile
files backed up privately. Saved progress was hashed before/after replacement
and retained. All qualification here was ROM-free; the owner still performs
visual/gameplay acceptance. The old toggle qualification remains historical.
See evidence/portable-storage.json for current source and binary pins.

## Owner acceptance (2026-10-19)

The owner states the settings work is done after testing the simplified directory picker; local owner acceptance recorded, unreleased.
