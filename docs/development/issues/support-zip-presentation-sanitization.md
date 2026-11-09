# SUPPORT-ZIP-20261027: Presentation diagnostics export audit

- Status: final rebuilt exporter passes actual-archive privacy and boundary checks; local candidate, unreleased.
- Severity: privacy/distribution boundary.
- Reported: 2026-10-27 UTC.
- Scope: owner requests revalidation after adding presentation.log for GH-058.
- Local-only approval; no upload, GitHub mutation, release or personal-data publication.

## Required checks

Audit the actual staged managed exporter and report producers, real session exports,
adversarial input, fixed archive entries, bounded values, metadata and exclusion of
ROMs, saves, raw memory, paths, generated code and symbols. Retained system/build/
controller/relative-stack data must be documented. The private review package
contains copied game/save data and is not a public distribution artifact.

## Evidence and limits

Private artifact root: emuhawk-sanitization-20261027. Earlier launcher unit tests
passed, but do not replace this explicit export audit. EmuHawk verification of
game behavior is tracked separately and has no bearing on ZIP privacy.

## Attempts and results

The actual staged JFG-Setup exporter produces exactly ten bounded log files plus
README.txt for both a real final-runtime session and a deliberately contaminated
session. Private path/email/token/ROM/save/dump/asset canaries are absent; unexpected
files are excluded; entries are flat and have no extra ZIP metadata/comments.
Valid backend/HRESULT/window fields survive. The initial scanner mistakenly
recognized the final letter of https:// as a drive prefix; correcting the audit
regex resolved that false positive without a product change. Producer, exact-byte boundary and relevant regression checks subsequently passed.

## Exact byte-boundary correction

Adversarial tests found one bounded-output defect: if a valid unterminated line
ends at exactly input byte 65536, export appended LF and produced 65537 bytes.
No private data leaked, but this exceeded the documented per-log cap by one
byte. The sanitizer now reserves room for the output newline and drops a whole
line that cannot fit, rather than truncating a diagnostic value. The regression
uses an actual 65536-byte file ending in a valid omitted-count line. The rebuilt
exporter returns 65520 bytes, retaining complete preceding lines and omitting
the last line that cannot fit. All 690 managed launcher checks pass.

The rebuilt earlier exporter passed real and contaminated archives, producer
filtering with a 100000-byte hostile tail, directory-junction rejection and
unrelated-directory rejection. The test harness initially needed explicit
PowerShell reflection argument casts and base-exception matching; these were
fixture failures, not exporter bypasses.

## Final actual-archive result

The rebuilt helper in launcher-019 passes the real-session and deliberately
contaminated exports again. Each archive has exactly ten allowlisted text logs
plus README.txt, flat entry names, no extra entry metadata/comments, UTF-8 text
without NUL, and no unexpected files or private canaries. The real export has
21713 uncompressed bytes. Its SHA-256 is
62a94d38c8bd5771a8c6b1fe3189bbd868cda26a950c05c0e8a3c3658617efa0.

Producer tests retain valid backend/HRESULT/window values while excluding
malformed fields, private strings and a 100000-byte hostile tail. Selected
directory junctions and unrelated directories are rejected. The first exact-byte
fixture used Windows newline translation and was not actually 65536 bytes;
that assertion failure was discarded and the corrected byte-written fixture
reproduced the one-byte defect before the fix.

The exported support ZIP is suitable for voluntary issue attachment within
this documented diagnostic scope. It intentionally retains technical
timestamps, build hashes, GPU/driver identifiers, settings, module basenames
and relative stack offsets; it is not anonymous. No automatic upload occurs.
The private preview folder and original-ROM reference captures contain ROM,
save or memory material and are not upload artifacts.

Private evidence: support-audit-021/result-final.json, producer-result.json,
boundary-after.txt, support-boundary-019/before.txt and checks-019.json.
