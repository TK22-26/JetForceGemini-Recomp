# Original N64 bugs

Hardware-confirmed observations and owner-reported native behavior are recorded
separately. A screenshot alone does not establish the console or capture setup.

## Confirmed on original N64 hardware

### N64-001: Tawfret chief cinematic shows a camera-helper square

- **Symptom:** a small yellow floating square is visible beside the chief in several cinematic shots.
- **Reproduction:** view the Tawfret chief cinematic and inspect the background around the chief;
  native resolution and television blur can make the helper resemble scenery.
- **Hardware evidence:** the owner rechecked the original N64 and confirmed it in the 2026-10-22
  investigation. The earlier claim that hardware did not show it was withdrawn. Exact ROM region,
  revision, console model and display were not recorded; they must not be inferred from the US code analysis.
- **Expected/actual:** an animation camera should supply a viewpoint without presenting its helper mesh;
  the old camera object remains drawable after another camera is selected.
- **Established cause:** starting path 13 clears the actor's hidden bit. Subsequent camera commands
  change the active view without stopping that path, so the ordinary draw gate submits its `camera` mesh.
- **Supporting emulator/analysis evidence:** Angrylion/software-RSP observation and actor-state analysis;
  removing the camera mesh in an immutable display-list replay isolated 120 changed pixels. These
  complement the hardware report rather than replacing it.
- **Recomp decision: fixed intentionally.** The supported `AnimCamera` is hidden only at its draw
  boundary, with the original flag restored immediately. Camera simulation and legitimate props with
  the same behavior remain intact. Included in **v1.4.0**; owner accepted the reviewed sequence at 120 FPS.
- **Limits:** not an exhaustive survey of every camera helper, ROM region or cinematic.

The separate bad-angle camera-cut interpolation was a recomp defect, not this native bug.
See the [complete investigation, failures, source and validation](../development/issues/tawfret-chief-camera-and-square.md)
and [published qualification](../releases/qualification-1.4.0.md).

## Owner-reported native bugs

### N64-002: Texture wash over the Goldwood starting bridge (NTSC)

- **Symptom:** the owner describes a weird texture that "washes over" the
  Goldwood starting bridge. Two supplied screenshots show the bridge deck from
  nearby views; the reported moving effect is not captured by still images alone.
- **Reported:** 2026-11-07, by the owner, who identifies this as an original-game
  bug in **NTSC**. Exact ROM revision, console/display and screenshot capture
  source were not specified. This records the native-game report without
  inferring a separate physical-N64 test from the screenshots.
- **Location/reproduction:** inspect the starting bridge in Goldwood. Exact
  movement, camera angle, timing and repeatability were not recorded.
- **Cause:** unknown; no rendering cause has been established or investigated.
- **Recomp decision: preserve; no fix requested.** The owner explicitly asked
  for documentation only. No runtime change, experiment or fix is scheduled.
- **Limits:** cosmetic report; no gameplay effect reported. PAL and JP behavior
  is unverified, not assumed to match NTSC.
- **Evidence:** both original screenshots are retained privately with hashes in
  the [issue record](../development/issues/goldwood-starting-bridge-texture-wash.md).
