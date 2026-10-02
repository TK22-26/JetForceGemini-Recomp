# Phase 0 decision record

> License update, 2026-10-01: the owner selected [MIT](../../LICENSE) for
> original project contributions. License decisions below describe the
> historical phase; third-party terms remain separate.

Historical record: on 2026-10-01 the owner authorized a separate scrubbed
public source repository. That snapshot decision supersedes the private-only
visibility rule for the exported source, while preserving the data boundary,
license reservation and private operational accounting described below. See
[the current publication handoff](publication-handoff.md).

- Status: accepted for private Phase 0-4 work under the local-generation boundary
- Decision date: 2026-08-03
- Maintainer handle: `TK22-26`

This record chooses the most conservative available boundary. It is an
engineering and repository-governance decision, not legal advice.

## Upstream permission path

The upstream coordination request is deliberately deferred and remains
unsent. Until written permission or a license is recorded, this repository
will not copy, adapt, publish, link, or distribute upstream decompilation or
RecompFrontend source, headers, declarations, symbols, or other expressive
material. External checkouts and generated private bodies remain ignored,
local-only research inputs. Tracked evidence is limited to approved hashes,
aggregate counts, schemas, independently authored automation, and synthetic
fixtures.

Sending the drafted request is a future human action. Deferral does not imply
permission and does not prevent later coordination.

## Repository license and publication

The current project-license choice is the all-rights-reserved notice in
`LICENSE`. No public-use or redistribution permission is granted during the
private feasibility phase. Selecting an open-source license is a later human
gate after the runtime architecture, recursive dependency inventory, upstream
permissions, and generated-output treatment are settled.

The repository stays private. No ROM, extracted asset, generated game code,
symbol export, save body, capture, screenshot, audio, trace, memory dump, or
other private ROM-derived body may enter GitHub, including private Actions,
caches, artifacts, issues, pull requests, or releases.

## Private corpus ownership

`TK22-26` owns private-corpus storage, retention, access approval, deletion,
and backup decisions. For Phase 0-4, approved private bodies are regenerable
and local-only under ignored paths; no GitHub, shared-cache, or cloud backup is
authorized. Project automation may publish only schema-validated aggregate
evidence allowed by the corpus and ROM policies.

## Phase 3-4 expansion decision

On 2026-08-04, `TK22-26` directed the project to continue through Phase 4
while retaining the conservative policies in this record. This is authority
for local feasibility experiments, local CPU generation, and local compile and
link evidence. It does not authorize a release or any change in the legal
classification of generated output.

The expansion therefore has these fixed conditions:

- ROMs, detailed symbol models, generated source, generated libraries, private
  manifests, unrestricted diagnostics, and ROM-backed test bodies remain only
  under ignored local paths.
- GitHub receives only independently authored orchestration, synthetic tests,
  closed aggregate evidence, approved dependency facts, and documentation.
- No ROM-backed GitHub Actions lane, artifact, cache, issue body, pull-request
  body, or review comment is authorized.
- N64Recomp and other build tools remain external local tools under `tools/`;
  no unlicensed JFG-decompilation or RecompFrontend material may be copied.
- A minimal project-authored Phase 4 link harness does not select a shipping
  runtime, renderer, frontend, audio, or input architecture.
- Completing engineering work does not itself approve generated-code or symbol
  distribution, a project license change, or a release.

The Phase 4 branch and pull request remain subject to human review. The
maintainer must separately approve any later dependency-selection, policy,
distribution, or release decision.

## Repository controls

The current private-repository plan does not enforce the requested branch
protection rules. Until enforceable protection is available:

- no work is pushed directly to `main`;
- changes use a topic branch and draft pull request;
- `TK22-26` performs the required human review for workflow, dependency,
  release, legal-policy, and protected-data-scanner changes;
- all required policy, Windows, and Linux checks must pass before merge;
- history rewrites are limited to removing protected or private metadata and
  require a fresh hygiene scan afterward.

Before the repository becomes public or accepts external collaborators, the
owner must enable enforceable branch protection and a dedicated private
vulnerability-reporting path, or record an equivalent reviewed replacement.

## Phase 0 outcome

The no-copy/local-generation path is understood, the current repository
license is chosen, ROM and corpus policies are committed, and there is no
known governance blocker to local work in the separate private repository
through Phase 4. Any expansion beyond this boundary, or any attempt to commit
or distribute generated output, reopens Phase 0.
