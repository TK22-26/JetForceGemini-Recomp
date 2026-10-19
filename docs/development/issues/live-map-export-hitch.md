# PERF-007: Live-map export stalls the game thread

- Status: cause reproduced; faster serialization and background command reads verified in scoped normal-Play checks.
- Target: 1.3; no released resolution.
- Affected profile: normal Play with live map observation enabled, including the
  muted copied-save 15,600-VI route through room 119 to Ichor.

## Symptoms, cause and evidence

Two repeatable approximately 43 ms update gaps survived the controller-settings
I/O correction. Both still advanced two native VI; they are host pacing hitches,
not evidence of a native 20 FPS simulation step.

The update-work span had already finished about 9.9 ms before the update trace.
Additional opt-in spans attribute approximately 9 ms to navigation mesh export.
A finer split attributes most of this to JSON number/string formatting rather
than guest geometry reads. The existing disk writer already runs asynchronously;
preparing the large JSON string still ran on the game thread. Separate synchronous
reads of mods.txt and warp-exit.txt can also take several milliseconds on this
route. Their independent contribution remains open.

Private evidence: vela-composite/room119-hitch-attribution.json,
current-play-navigation-costs.json, split-play-navigation-costs.json and
play-navigation-split. Keep actual normal Play evidence separate from older
probe-mode runs and screenshot captures.

## Candidate and verification

Replace repeated locale-aware numeric stream formatting in write_mesh with
buffered locale-free to_chars formatting, preserving the existing default
six-significant-digit values, keys and array order. The differential test
retains the old implementation as a reference, including empty geometry,
integer limits, signed zero, extreme finite values, random finite floats,
triangle indices and an optional private captured-RDRAM mesh.

This changes host tooling export only; it does not alter game geometry, collision,
AI, timing or map generation IDs. Build, exact output comparison and the same
normal-Play route must pass before calling the measured hitch fixed.
Command-file I/O and other campaign stalls remain separate acceptance items.

## Lessons and limits

Asynchronous disk writes alone do not remove the CPU cost of serialization.
Profile the entire path after the guest update, and distinguish a two-VI host
wall-time gap from a genuine three-VI game update. A successful microbenchmark
does not establish clean campaign timing.

## Implemented candidate and measured route

The exact-output differential test passes for 10,000 random finite values,
numeric boundaries, triangles and privately captured native geometry. A focused
large synthetic mesh benchmark measured about 40.5 ms for the old writer and
5.2 ms for the new writer. This is serialization speed, not whole-game FPS.

Navigation commands now use the same bounded immutable background snapshots
as controller settings. The three limits remain 128 bytes (mods), 256 (warp)
and 32,768 (pilot). Game-thread parsing, nonce consumption, generation/actor
checks and the five-second expiry remain in place. Missing/invalid commands
retain prior mod settings; old warp requests still cannot fire twice.
Polling adds at most roughly 450 ms plus a delayed storage read to a new map
command. Slow storage can delay the command, but cannot stall a game update.

The optimized normal-Play route completed with 2194 measured boss intervals, VI deltas {'2': 2194}, maximum boss wall interval 36.682 ms, 0 audio error events and 0 same-room gaps above 42 ms after VI 3000. These are scoped route results; all-campaign qualification remains open.

Retained route summaries: vela-composite/optimized-play-navigation-costs.json and split-play-navigation-costs.json. Navigation cost counts above the one-millisecond diagnostic threshold changed from {'host-profile-navigation-read': 13, 'host-profile-navigation': 33, 'host-profile-navigation-json': 20, 'host-profile-navigation-mesh': 20} to {'host-profile-navigation-mesh': 4, 'host-profile-navigation': 8, 'host-profile-navigation-json': 1}. Detailed nested spans are not additive percentages.

## v1.3.0 source availability

The documented change is included in tag v1.3.0 (launcher/source
02be6fa9a4c50f4056f778c5148ca8ac70b0e92b; clean runtime
665596482a7395593e85dbe73f1bd4b016d183d9). See the
[combined release qualification](../releases-1.3.0-qualification.md) for owner
acceptance, source CI, package and publication evidence. Earlier failed attempts
and the scene/device/seed limits above remain part of this record; inclusion
does not turn an unverified broader report into a confirmed resolution.
