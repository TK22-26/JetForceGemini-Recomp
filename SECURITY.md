# Security policy

## Supported versions

The project is pre-release and has no supported public binary version. Security
fixes target the default branch under the repository's documented manual
change-control process. The public source repository uses branch protection and private vulnerability
reporting. Published support commitments will be added before the first release.

## Reporting a vulnerability

Open the
[repository Security tab](https://github.com/TK22-26/JetForceGemini-Recomp/security)
and use its private reporting option when available. Do not open a normal issue,
discussion, or pull request containing security-sensitive details. If private
reporting is unavailable, request a private channel from the repository owner
through an existing private project channel without including exploit details
in the request. If no private channel is already available, retain the report
locally until the owner enables private reporting. Do not use an issue,
discussion, pull request, or other public repository surface as a fallback.

Reports should include:

- The affected project commit and component.
- Impact and required attacker capabilities.
- Minimal reproduction steps using synthetic or independently authored data.
- Suggested mitigations, if known.

Do not attach ROMs, game assets, private corpus bodies, memory dumps, save
states, credentials, tokens, personal data, machine-specific paths, or
unredacted logs. Describe protected-data exposure without copying the exposed
bytes into the report.

Maintainers aim to acknowledge a report within three business days and provide
an initial triage result within seven. These are response goals, not a service-
level guarantee.

## Security boundaries

The following are security invariants:

- User-supplied ROMs and derived game data never enter Git or GitHub.
- External tools and upstream repositories remain under ignored `tools/`
  paths.
- Unlicensed upstream source, headers, and symbol exports are not copied into
  the project pending written permission.
- The original development repository and its history remain private.
  Only the reviewed source snapshot is authorized for public visibility.
- Build and test output does not disclose personal or machine identifiers.
- No agent or untrusted test receives repository, user, cloud, or publishing
  credentials.

Violations of these invariants should be reported through the security process
even if no traditional code-execution vulnerability is involved.

## ROM-backed CI

ROM-backed CI is a trusted-code environment, not a general PR runner. It MUST:

1. Execute only a human-approved trusted commit and a workflow loaded from a
   human-controlled trusted branch (and a protected branch once enforceable
   branch protection is available).
2. Run on a fresh ephemeral VM or equivalent disposable instance.
3. Deny outbound network access and expose no inbound service.
4. Contain no GitHub token, SSH key, package credential, cloud credential, or
   user secret.
5. Mount private inputs read-only only after trust verification.
6. Use a disposable private scratch disk.
7. Disable caches, artifacts, core dumps, unrestricted logs, and job summaries.
8. Export only fixed-schema sanitized aggregate results through an allowlisted
   validating gateway.
9. Destroy the runner and scratch storage after every job.

Code from forks, pull-request heads, issue commands, automated dependency
updates, or unreviewed agent branches MUST NOT execute inside this boundary. A
maintainer must reconstruct an external contribution on a trusted branch after
review.

Isolation is tested with harmless canaries that attempt file, environment,
path, log, artifact, cache, and network disclosure. A failed isolation test
blocks ROM-backed CI.

## GitHub Actions and supply chain

- Workflow permissions default to read-only and are elevated per job only when
  required.
- Third-party Actions are pinned to full-length commits.
- Workflow, dependency-lock, release, legal-policy, and protected-data scanner
  changes require designated human review.
- External sources and binaries are pinned and integrity-checked.
- Dependency updates include a license and SBOM diff.
- Release builds use a clean environment and produce verifiable provenance,
  an SBOM, and required third-party notices.
- Secrets are never passed to code whose commit has not already been trusted.

## Application security requirements

- Treat ROMs, mods, configuration, saves, controller metadata, and imported
  files as untrusted input.
- Validate sizes, offsets, counts, compression bounds, archive paths, and
  integer arithmetic before allocation or access.
- Keep mod execution disabled until a separate threat model and permission
  model are approved.
- Save updates use bounded parsing and atomic replacement with recovery.
- Crash reporting is opt-in and redacts paths, memory, game data, saves, and
  identifiers before transmission.
- Network access is absent by default and requires a separate architecture and
  privacy review.

## Coordinated disclosure

Maintainers will validate the report, determine affected versions, prepare a
fix and regression test, and coordinate a disclosure date with the reporter.
Do not publicly disclose details before a fix or agreed disclosure date. Legal
or protected-data incidents may require an immediate distribution freeze while
hosted data and history are reviewed.
