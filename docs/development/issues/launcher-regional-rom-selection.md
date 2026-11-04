# Main launcher regional ROM selection

- Status: Implemented; native UI, all-region CLI and restart checks pass; owner review pending; local v34, unreleased.
- Scope: USA, PAL and Japanese ROMs in one launcher profile; local and unreleased.
- Severity: usability limitation; switching regions previously required manual reselection or separate shortcuts.

The owner requested the supplied cartridge-tile layout on 2026-11-04 UTC.
The previous home screen hides its single ROM card after import and exposes only
one active path, despite retaining separate canonical ROMs and save namespaces.

The library verifies stored ROMs by full catalog identity. Selection persists
independently of whether that region is loaded. The helper owns selection and
matching-runtime resolution under the same profile lock as import and Play.
Empty or damaged regions clear active Play state without silently falling back.
Regional save namespaces and shared input/audio settings remain authoritative.

Private work: launcher-regions-20261104. Initial supervisor admission used the
failed-job continuation API with a passed predecessor and was rejected before
any worker ran. Ordinary passed-job dependency inheritance corrected that setup
without renewing the allowance, changing the deadline or resetting counters.

Validation and owner acceptance remain pending.

The owner also requested region startup arguments. `--region usa|pal|jp` selects
a loaded region at startup; combine with `--play` for direct Play. `us`/`jpn`
and uppercase spellings are accepted. Missing ROMs never fall back to another
region. Command-line selection passes through the same locked helper and persists.

The first live CLI harness rejected a raw command-line substring comparison
for the save folder after the correct PAL runtime launched. That capture is
retained; the next check parses actual arguments and compares normalized Windows
paths. This setup assertion alone is not evidence of a game save-routing defect.
Initial native UI checks passed; screenshot review found inherited selected-button
background outside the bevel and a top-aligned Play label. The final styling
clears that background and centers Play, with fresh UI checks.

## Final regional selector verification

The managed launcher suite passes 759 checks and setup fixtures pass 28 checks.
Native policy, viewport and storage checks pass. The final cartridge UI passes
64 checks, including pointer/keyboard selection, empty and busy states, and
100/150-percent DPI. The existing update UI passes 78 checks. Native screenshots
were reviewed against the supplied design.

Actual packaged `--play --region USA`, `PAL` and `JP` sessions select the matching
executable and regional save path, advance the game, and close normally. The
first harness wrongly required the internal native child command line to repeat
`--save`; that option belongs to the host process. The corrected checker parses
arguments and verifies every explicit save path, preserving the failed trace.

Selection through the production helper survives two actual launcher closes and
reopens with no region argument. An explicitly empty JP selection also survives
restart with an available USA import, without fallback or stale Play state.
The first direct-helper fixture lacked the launcher-path environment variable;
the corrected fixture matches the environment supplied by the real launcher.

Two offscreen full-shell synthetic pointer attempts did not change selection;
their input-delivery cause is unresolved. The native widget pointer tests pass,
and selection-service/restart checks pass separately. Full-shell physical-pointer
acceptance remains an owner check; these fixtures do not establish that result.

Evidence is private under launcher-regions-20261104: build-launcher.json,
ui-final.json, launcher-cli-final.result.json, persistence-qualified.json and
empty-region.json. The package contains unchanged v33 game runtimes, copies of
all three regional saves, and the PAL manual preferences. Original data is
preserved. All automated game sessions used private muted profiles.

Compatibility lesson: persist the selected identity separately from availability;
resolve its runtime under the same profile lock as Play, and retain separate
regional save namespaces. UI fixtures and native-child protocol observations
must be distinguished from actual user-input acceptance.
