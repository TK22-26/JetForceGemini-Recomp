# BUILD-AUDIT-MEMORY-20261102 — MSVC diagnostic-buffer initialization

Status: corrected and verified in isolated compiler, actual RT64 and full
US/PAL/JP enhanced native builds. Public-default build remains unverified. Severity: blocks resource-bounded Windows runtime delivery.
Affected configuration: MSVC 14.40, Release, RT64 presentation consumers.

## Symptoms and evidence

Serial enhanced builds failed with MSBuild StackOverflowException under 8 and
12 GiB nested limits. Measuring the unchanged 12 GiB run shows `cl.exe`, rather
than MSBuild, growing to 12.49 GB while compiling the presentation queue. Reducing
build parallelism did not fix the allocation. Production containment remains
active and its 16 GiB ceiling was not raised.

An isolated translation unit including the existing blur-source audit reproduces
the failure under 3 GiB in 6.6 seconds. The collector value-initializes 262,144
rows in an inline `std::array`; MSVC expands this initialization at compile time.
The same test with a fixed-size vector passes in 2.4 seconds with about 290 MiB
peak job memory. This comparison isolates the compiler pressure from game code,
RT64 workload size and .NET process memory.

## Remedy and limits

Use a vector sized once to the same capacity when the opt-in collector starts.
Recording still writes only within that capacity, preserves overflow counts,
and performs no frame-by-frame allocation or disk writes. The original row
format and explicit shutdown export remain unchanged. This is an implementation
change to diagnostic storage, not a relaxation of memory limits or optimization.
Full runtime compilation and collector output validation remain pending.

Private evidence: `regional-presentation-20261102-owner2h/rt64-resource-measurement`
and `audit-buffer-compiler`. Prior failures remain linked from
[Modern Aim return](modern-aim-release-camera-snap.md) and
[regional support](regional-rom-support.md). No release resolution is claimed.

Lesson: measure the allocating child process; a parent CLR error can obscure
compiler exhaustion caused by a large inline aggregate initializer.

## Actual dependency and collector verification

The actual enhanced RT64 library now builds successfully in 182 seconds under
the unchanged 12 GiB nested limit. A compiled consumer also records 262,147
rows and exports exactly 262,144, reporting three dropped rows, on each regional
fixture run. The complete footer and row format remain intact. Full native
runtime builds proceed separately; public-default compile/link has not been
rerun and is not claimed by this enhanced dependency result.

Source: [bounded audit collector](../../../include/jfg/renderer/blur_source_audit.hpp).
The subsequent PAL executable also compiled and linked after correcting the
separate [turn-bank adapter](pal-modern-backward-body-tilt.md#native-integration-follow-up-2026-11-02).
Neither the memory ceiling nor production guard was relaxed.

Full US/PAL/JP enhanced executables now compile and link under the unchanged
12 GiB nested ceiling and pass normal Play. Receipts: `regional-build-v4.result.json`
and `candidate-v3-{us,pal,jpn}` in the current private evidence root.

Local implementation commit: `0e97d2e347b1bd33c714de9de3ef678aa0e48cec` on `develop`.
The local test package is not a published release.
