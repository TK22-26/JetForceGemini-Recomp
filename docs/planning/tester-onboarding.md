# Tester onboarding plan

Prepare a clear public project introduction and an issue-focused playtesting
workflow before inviting more contributors. The maintainer reviewed the README
and approved final review and publication of this documentation cleanup.
The reply to issue 4 and richer diagnostic tooling remain separate work.

## Decisions

- The README introduces the project, current capabilities, getting started,
  build status, and ways to help. Detailed phase milestones stay linked in
  the development dashboard. A short Future additions section translates
  the roadmap into player-facing goals without enumerating the phases.
- Playtesting is the primary contribution path. Code contributions use focused,
  reviewed pull requests; a PR invitation is not a merge commitment.
- Testers play normally and report problems on GitHub. A short self-check is
  optional; successful sessions and completed checklists do not need reports.
- Reports about the same problem stay together. New comments should add useful
  reproduction details, requested diagnostics, or retest results.
- Public-facing instructions describe available tools and practical limitations.
  Superseded publication discussions and experiment journals remain in Git history.
  Preserve licenses, attribution, historical evidence, and guard requirements.
- GitHub issue attachments are the intended destination for diagnostic bundles.
  Describe the current log ZIP honestly while planning richer logs and dumps.

## Audit findings

| Area | Finding | Action |
| --- | --- | --- |
| README | Setup instructions, phase records, publication history, and repeated data rules compete with the project introduction. | Replace with a concise project README and direct navigation. |
| First steps | Several guides repeat onboarding and mix source tests with playable builds. | Add one getting-started guide and give each existing guide a clear purpose. |
| Contributions | The contribution guide opens with restrictions and assumes code changes. | Lead with playtesting, then offer the PR workflow. |
| Reporting | The form lacks consistent problem type and frequency; successful reporting expectations are unclear. | Document problem-only reporting and update the issue form. |
| Known limitations | Windows 10 setup failures are recorded in issue 4 but absent from the initial setup path. | Link a short known-issues page from README and getting started. |
| Diagnostics | The released preview has two logs; the source candidate adds selected sessions and stack snapshots. | Validate and release the candidate before promising its capture features. |
| Historical handoff | Old onboarding mixes operational history with instructions for newcomers. | Use Git history for the old text and provide a short development index. |

The audited public baseline is `2c55b0f082395e2be4407958637dbb4effb3c43d`.
Its [ROM-free CI run](https://github.com/TK22-26/JetForceGemini-Recomp/actions/runs/37069412610)
passed. That is source validation, not complete gameplay acceptance.

## Documentation delivery

- [x] Audit README, contribution guidance, setup, reporting, and historical handoff.
- [x] Draft the project README with live build status and a separate progress link.
- [x] Add getting started, known issues, and a short playtesting guide.
- [x] Make contribution guidance tester-first with an optional PR path.
- [x] Update the issue form for actionable, non-duplicate reports.
- [x] Replace historical handoffs with a development index; retain originals in Git history.
- [x] Verify changed links, formatting, repository hygiene, and project validation.
- [x] Maintainer reviewed the README and approved final review and documentation publication.
- [x] Final review and launcher/support-export checks passed.
- Publication uses a pull request and the required protected-branch checks.
- [ ] Review the contributor reply separately before sending it.

The owner also authorized removal of obsolete research helpers and documents,
consolidation of journals, and reorganization of the development references. Installer,
runtime, and reporting features remain separate implementation work.

## Repository cleanup

- [x] Remove unused Phase 4 helpers and superseded narrative records.
- [x] Consolidate the roadmap, automation guidance, and timing summaries.
- [x] Simplify proposal/PR templates and current policy wording.
- [x] Preserve runtime tools, tests, signed contracts, notices, and guard requirements.
- [x] Validate the complete reorganized candidate and inspect the final diff.

## Reporting improvements

The diagnostics follow-up implements these in the source candidate; the released
launcher still needs a separate release. See [support diagnostics](../development/support-diagnostics.md)
for its scope and validation.

1. Select the affected session and retain failures across later launches.
2. Export richer setup/runtime diagnostics, settings, machine information,
   timestamps, and actual build identities with personal paths filtered.
3. Capture crashes and hangs through an explicit diagnostic workflow.
4. Preserve the exact locally built executable and matching debug-symbol
   identity so captured failures can be interpreted correctly.
5. Define and validate the public diagnostic bundle, including dump contents,
   size limits, and a clear description before attachment. GitHub is the intake
   destination; the exporter must not silently collect or upload arbitrary files.
6. Reconcile the existing attachment instructions and detailed data policies
   with the implemented bundle before telling testers to submit new dump formats.

Begin with a controlled example failure and prove that its exported evidence
can be inspected and diagnosed. Keep the richer capture work separate from
this documentation cleanup and from the existing internal test program.

## Contributor onboarding checkpoint

Before sending a reply to [issue 4](https://github.com/TK22-26/JetForceGemini-Recomp/issues/4):

- Review and publish the documentation through the normal repository workflow.
- Verify the contributor links resolve on the published branch.
- Invite a focused installer PR and testing on the reporter's Windows 10 setup.
- Point to the playtesting guide and current support ZIP without promising
  planned diagnostics or an unsupported research workflow.
- Keep the reply brief and practical; acknowledge the report and describe
  the useful next contribution.

Publish the reviewed documentation through the protected-branch workflow.
Contributor contact, runtime changes, and a new launcher release are outside
this documentation delivery.
