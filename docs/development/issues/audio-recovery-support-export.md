# AUDIO-SUPPORT-20261104: Support ZIP drops audio recovery events

- Severity: medium diagnostic reliability; no demonstrated change to gameplay/audio output.
- Status: fixed on develop in 067f9a8; logger-to-ZIP and bounded grammar checks pass; unreleased.
- Reported: 2026-11-04 UTC; publication status reconciled 2026-11-08 UTC.
- Affected: develop `ed5f7c7`, local v35 managed support exporter, Windows; region/profile independent.
- Origin: synthetic host diagnostics through the actual production logger and packaged exporter; no original-ROM or N64 comparison applies.
- Related: [persistent audio delay #35](audio-crackle-persistent-latency.md), [support export privacy audit](support-zip-presentation-sanitization.md).

## Symptom and reproduction

A runtime may write an audio backlog recovery success or queue-failure event to
its raw support `native.log`, but Export Support Report removes that event.
The ZIP can therefore show no recovery even when the raw file proves one was
recorded. This is an observability defect, not the established trigger of #35.

A private C++ fixture calls the real [support_event](../../../include/jfg/runtime/support_log.hpp)
with `native=running`, a synthetic numeric recovery record and
`audio=latency-recovery-queue-failed`. Its raw file contains all three lines.
The current managed `SupportSession.ExportSelected` exports an actual ZIP whose
`native.log` contains only `native=running`. Both recovery records are absent.
Synthetic values are test data; no live audio stall was induced or measured.

## Demonstrated cause

[HostAudioDevice::recover_latency](../../../src/boot/native/host_audio_device.cpp)
emits `audio=latency-recovery/before_ms=.../after_ms=.../discarded_bytes=.../recoveries=...`
or `audio=latency-recovery-queue-failed`. The production logger permits these
bounded characters and writes them to disk. However,
[Support.cs](../../../launcher/windows/Support.cs) `SafeLine` has no `audio=`
branch. `SanitizeFile` discards every line outside that grammar, and
`ExportSelected` sanitizes `native.log` just like the other entries.
The bug is the mismatch between the producer's valid fields and export grammar.

Earlier logger-on-disk tests correctly established that the producer writes the
records; they did not establish delivery through the ordinary support ZIP.
The earlier [presentation ZIP audit](support-zip-presentation-sanitization.md)
validated its stated fields/privacy boundaries, not these missing audio fields.

## Attempts and results

| Date | Check | Result |
|---|---|---|
| 2026-11-04 | Review current producer and export allowlist | Both audio forms are produced but neither is admitted for export |
| 2026-11-04 | Verify test package identity | Initial fixture compared the native launcher's manifest hash with the managed helper; failed before tests. Corrected the comparison; retained both executable hashes and matching Support.cs/Diagnostics.cs input hashes |
| 2026-11-04 | Exercise managed exporter by reflection | First invocation failed on PowerShell PSObject/string conversion. Explicit string casts corrected the fixture; no product edit |
| 2026-11-04 | Export controlled native log using actual v35 helper | Both audio forms dropped; native marker retained; a synthetic private-path canary excluded |
| 2026-11-04 | Production logger to actual ZIP | Raw file has three records, export has one; logger itself rejects the private-path canary |
| 2026-11-04 | Preserve real reporter mouse diagnostics | All five mouse logs survive sanitization; 209 snapshots round-trip through production C++ formatter; counter/history suite passes |

Source `Support.cs` SHA-256:
`e998065c46c5f249dc6d51c4d2d687fec3d1a6993fcd0303c781ae273439c503`.
Tested v35 `JFG-Setup.exe` SHA-256:
`8b40bf2353ea64840b3c51fe793f17d46b9cdbfad007744fa580418679f70fec`.
The package manifest's `executable_sha256` pins the native launcher, not this
managed helper. Its Support.cs and Diagnostics.cs input hashes match current
source; helper identity is recorded separately. Raw evidence, ZIPs, failed
fixtures and results are under private `reporter-evidence-20261104`, especially
`validation-v2/verification.json` and `producer-export/result.json`.

## Remedy and acceptance still needed

No production change was made: the owner authorized research and additional
context. A scoped remedy should admit exactly the two documented event forms,
with bounded unsigned numeric fields. Preserve the per-file/output caps and
rejection of paths, arbitrary text, malformed values and unexpected fields;
do not admit an unrestricted `audio=` prefix.

Acceptance requires the actual production logger and rebuilt packaged exporter
to preserve success and failure records through an actual ZIP, while malformed
fields and privacy canaries stay excluded. Check missing/oversized/truncated
records without weakening the existing export bounds. This would fix diagnostic
transport only, not qualify #35's affected-machine audible behavior.

The November 1 reporter used older v1.4.0 runtime `521f6662`, which has no sustained
recovery producer. Do not infer that this exporter flaw hid a recovery in that
capture. Do not infer absence of recovery from an affected current exporter.
Normal queued duration is still not continuously logged even after these event
forms are preserved; further bounded telemetry may be necessary to find the
actual delay trigger.

## Compatibility lesson

A successful producer test is insufficient for support diagnostics. Track each
field through its producer, file bounds, sanitizer, final archive and interpretation.
Keep privacy allowlists explicit and add producer-to-export coverage when adding
new diagnostic categories. This record does not alter ROMs, saves, audio settings,
release status or prior owner/reporter acceptance.

## Implemented remedy and verification

[Commit 067f9a8](https://github.com/TK22-26/JetForceGemini-Recomp/commit/067f9a898ceff90b789e0af779693f6cdc64a300)
adds the two bounded audio-event forms to the support sanitizer and documents
them in the archive README. Final-ZIP tests cover success/failure events, zero and
maximum counters, malformed/private fields, missing files and truncated history
at the byte cap. The regression fails on the old exporter; 778 launcher and 28
setup checks pass. The native launcher build and actual producer-to-embedded-helper
ZIP check pass with byte-for-byte preservation of the allowed records.

This supersedes the research-stage pending remedy above. It fixes diagnostic
transport only; the affected reporter's audio-delay cause and current-build
acceptance for #35 remain separate and open. No audible result is inferred from
these synthetic export checks.
