# Launcher notifications wait in a queue

- Status: Implemented; native UI regressions pass; owner visual acceptance pending; local v35, unreleased.
- Report: owner request on 2026-11-04 UTC.
- Severity: minor interface behavior and delayed feedback.
- Affected: launcher source through the local v34 package, all ROM regions.

## Cause and reproduction

Connect two controllers or trigger several controller/audio notices quickly.
Bottom-left notices previously shared one DOM node and one 4.62-second timer.
Later notices waited in a queue and appeared only after the previous notice
expired. The owner requested immediate vertical stacking with independent timing.

## Change

[NotificationStack](../../../launcher/ui/notification_stack.hpp) creates one DOM
card per notice. A new card enters at the bottom; older cards move upward. Each
retains its original birth time, entry animation and expiry. Stack motion uses
a separate position interpolation, so arrivals never restart another animation.
Wrapped text contributes its measured height. Consecutive duplicates do not
restart an existing card. Up to eight cards are retained; overflow drops the
oldest instead of delaying new messages in a hidden queue.

The native launcher, live-map error notices and standalone preview share the
implementation. Reduced motion keeps independent lifetimes without movement.
Launcher modal visibility continues to hide notices without restarting clocks.

Review caught the live-map document still using the old single-notice markup
with the shared theme. It was migrated before delivery, with a real failed mod
command exercised in a private UI fixture. The first extended fixture build
used an unavailable RmlUi `HasClass` method; the pinned API is `IsClassSet`.
Correcting that test query made the fixture compile; the failed log is retained.

## Validation and limits

The [native notification fixture](../../../launcher/ui/tests/notification_stack_ui_tests.cpp)
passes 38 checks covering immediate arrival, independent entry/exit ages,
original expiry, DOM preservation, duplicate suppression, wrapped heights,
reduced motion, bounded bursts, 150-percent DPI, hidden expiry and live-map error
presentation. Native screenshots were reviewed. Regional cartridge UI (64 checks)
and update UI (78 checks) also passed during this change.

The final packaged launcher initializes with all three imports and the remembered
PAL selection, then closes normally. This used a separate muted profile with
transient startup files cleared. Original ROMs, saves and preferences were
hash-checked and preserved. Game runtime source identities remain the same as
v33; PAL camera acceptance is retained, with separate USA/JP acceptance pending.
The standalone preview shares the implementation but was not separately built.

Owner visual acceptance of the notification motion and full-launcher physical
ROM-tile selection remains pending. No release or push was made. The existing
[regional selector record](launcher-regional-rom-selection.md) retains its CLI,
restart and input-fixture evidence.

Private evidence: launcher-notifications-20261104, including ui-checks.json,
notifications-shared-style/result.json and screenshots, shared-style-build.log,
shared-style-final.log, final-packaged-smoke.log and package.json. Work ran through
the production supervisor with its guard enabled and existing counters preserved.

Compatibility lesson: notification lifetime belongs to each message, separate
from layout motion. When changing a shared theme, audit every document that uses
its selectors, including auxiliary windows.
