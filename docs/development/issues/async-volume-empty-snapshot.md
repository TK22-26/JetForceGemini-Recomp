# Empty volume-file snapshot during an in-place rewrite

- Status: verified in focused tests and complete host-suite reruns; unreleased.
- Severity: low. Discovered by the full host suite during regional architecture qualification on 2026-11-01.
- Affected: shared Windows and portable asynchronous volume-file reader; independent of ROM revision.

The first new layout run built all targets and passed 110/111 tests. The volume
reader test failed at `oversized file preserves last bounded value`. Its writer
truncates a live file before writing the next value. Source review found that
the asynchronous reader accepted a zero-byte read as a new immutable snapshot.
The later oversized read is correctly rejected, leaving that empty snapshot
instead of the prior settings. This is a concrete race window; the failed run
did not record the intermediate bytes, so that run's exact interleaving remains
unobserved.

The candidate rejects empty reads as well as oversized reads. An empty file
cannot express volume settings. A deterministic startup check and an explicit
empty-file interval cover preservation of the previous snapshot. This does not
claim transactional support for arbitrary partial nonempty writes; product
writers should publish complete settings atomically. No audible regression was
reported or inferred from the test failure.

Evidence: private `regional-architecture-20261101-owner5h/member-migration-tests-v1`
retains the first full-suite failure. `async-volume-empty-v1` records the rebuilt focused test passing eight consecutive runs. Complete host-suite reruns pass all 111 tests, including `member-migration-tests-v8`.
Source: [reader](../../../include/jfg/runtime/async_volume_file.hpp) and
[test](../../../tests/runtime/async_volume_file_tests.cpp).
