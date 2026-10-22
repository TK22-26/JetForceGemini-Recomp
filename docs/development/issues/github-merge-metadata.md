# GitHub-created merge metadata differs from local policy

- Status: observed in public PR #42; history preserved. Local publication commit identity is checked explicitly before push.
- Discovered: 2026-10-22 UTC.
- Severity: maintainer metadata/privacy policy; no game or package behavior change.

The repository requires the maintainer no-reply email and UTC timestamps for
locally created commits. The GitHub merge service created `04cded4` with the
account-default author email and a local timezone, and GitHub as committer.
Local Git identity and environment overrides do not control server-created
merge metadata. The owner was informed of the discrepancy and the email.
The private address is deliberately not repeated in this report.

Evidence is the raw merge commit and PR #42. All preceding local release
commits retain the required identity; the merge tree exactly matches the
approved source. No history rewrite or account-setting change was attempted.

For publication, create the commit and annotated tag locally with explicit
maintainer author/committer/tagger identity and UTC dates, inspect the resulting
raw objects, and use ordinary protected-branch integration of the checked
revision. Keep the GitHub protections intact. Future merges must account for
server-generated metadata before selecting a merge method; do not assume a
local Git setting controls GitHub's author identity or timezone.
