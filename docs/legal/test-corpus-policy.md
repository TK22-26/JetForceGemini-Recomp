# Test-corpus classification and handling policy

- Status: Mandatory Phase 0 policy
- Last reviewed: 2026-08-03
- Approval authority: Human maintainers
- Private-corpus owner: `TK22-26`

This policy governs replay inputs, state snapshots, emulator captures, graphics
and audio references, fuzz corpora, first-divergence evidence, and golden
baselines. It must be read together with `rom-and-assets-policy.md`.

## Classification

Every corpus item has exactly one classification in its manifest.

### `PUBLIC_SAFE`

Independently authored, non-expressive data that may be tracked after review:

- Controller input sequences created by the project.
- Scenario recipes and semantic assertions.
- Synthetic memory/device fixtures created without game bytes.
- Schemas, parsers, generators, and minimization tools.
- Cryptographic hashes and aggregate counts that do not enable reconstruction.
- Project-assigned opaque scenario, subsystem, and function identifiers.

### `PRIVATE_REGENERABLE`

ROM-backed material that may exist only on an approved local or isolated
runner and must be regenerable from an authorized local input:

- RDRAM pages and function-call snapshots.
- Emulator save states and game save bodies.
- ROM pages, extracted assets, generated code, and symbol exports.
- Display lists, graphics/RSP task buffers, framebuffers, screenshots, video,
  audio command streams, and PCM.
- Full traces, crash dumps, and divergence bundles containing game data.

`PRIVATE_REGENERABLE` data is forbidden from every GitHub storage or output
channel, even while the repository is private.

### `PROHIBITED`

Material whose origin, permission, or ability to avoid disclosure is unknown;
material received from an unauthorized source; and private material that is
not necessary or cannot be handled by the approved isolation controls.

`PROHIBITED` data is not retained or processed. Its metadata is escalated to a
human maintainer without copying the content.

## Corpus manifests

Tracked manifests describe how to regenerate and validate private items but do
not contain them. A manifest includes:

```yaml
id: scenario-boot-smoke
classification: PRIVATE_REGENERABLE
generator_schema: 1
supported_rom_id: jfg-us-retail
input_recipe: corpus/manifests/scenario-boot-smoke.yaml
expected_private_body_sha256: "<hash>"
sanitized_outputs:
  - pass
  - first_divergent_tick
  - state_hash
retention: ephemeral
owner: compatibility
```

Manifests record repository-relative recipe paths only. They MUST NOT contain
personal identifiers, machine-specific paths, raw bytes, screenshots, source
excerpts, or secrets.

## Local corpus rules

- Private bodies reside under ignored `corpus/private/`, `captures/private/`,
  or outside the checkout.
- Private bodies are content-addressed, access-restricted, and read-only during
  a normal test run.
- Test output goes to a fresh private scratch directory.
- Private bodies have a documented retention period and can be regenerated;
  they are not backed up to GitHub, cloud artifact stores, or shared caches.
- For Phase 0-4, no off-machine backup of private corpus bodies is authorized.
  `TK22-26` owns access, retention, deletion, and any future backup decision.
- A minimizer working on private data produces a private result. Minimization
  does not change classification.

## ROM-backed CI isolation

ROM-backed CI executes only trusted commits reconstructed or approved by a
human maintainer. It MUST NOT execute code directly from an untrusted pull
request, fork, issue command, dependency update, or agent branch.

The runner boundary requires:

- An ephemeral disposable VM or equivalent clean instance for each job.
- No inbound access and deny-by-default outbound network access.
- No GitHub token, SSH key, cloud credential, package-publish credential, or
  user credential inside the test environment.
- A read-only private input mount made available only after source checkout and
  trust verification.
- Workflows sourced from a protected trusted commit.
- No Actions artifact upload, cache save, job-summary body, core dump, or
  automatic diagnostic attachment from the private execution environment.
- Log capture disabled by default for child processes; sanitized orchestration
  emits only an allowlisted result schema.
- A fresh writable scratch disk destroyed with the runner.

The only allowed output crosses a validating gateway and contains fixed-schema
aggregate fields such as pass/fail, test ID, elapsed bucket, schema version,
approved hashes, first divergent tick, and project-owned opaque IDs. Free-form
stdout, stderr, filenames, memory ranges, source names, stack contents, and
binary attachments are rejected.

An isolation test MUST attempt harmless file-read, path-print, log, artifact,
cache, environment, and network-exfiltration canaries and prove they cannot
leave the runner.

## Goldens and evidence

- Public-safe goldens are versioned and human-reviewed.
- Private goldens are regenerated locally and verified by a tracked public-safe
  hash manifest.
- An AI agent may propose but may not apply or approve a golden change.
- Evidence bundles inherit the highest classification of any input or field.
- Passing a sanitizer or redactor does not automatically downgrade evidence.
- A golden update records old and new approved hashes, reason, affected tests,
  oracle provenance, and human approver without including private bodies.

## Failure handling

Private detailed failures remain inside the isolated runner or an explicitly
approved local environment. The sanitized result identifies the first failing
test and tells a trusted maintainer how to reproduce it locally. It does not
upload a crash dump, screenshot, audio clip, trace, disassembly, memory bytes,
or unrestricted log.

## Acceptance criteria

Corpus automation is acceptable only when:

1. Every item and output has a classification.
2. No `PRIVATE_REGENERABLE` or `PROHIBITED` body is tracked or uploaded.
3. A clean runner can regenerate private bodies from approved local inputs.
4. The output gateway rejects unknown fields, oversized values, free-form text,
   and binary data.
5. Isolation canaries demonstrate that private data cannot escape through
   network, logs, summaries, artifacts, or caches.
