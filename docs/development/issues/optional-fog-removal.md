# RENDER-017: Adjustable distance fog (GitHub #26)

Status: revised implementation candidate; owner gameplay review pending.
Report: https://github.com/TK22-26/JetForceGemini-Recomp/issues/26
Severity: requested visual enhancement, not a gameplay bug.

The reporter requests removal of heavy distance mist. The owner requested the
supplied sidebar Video Settings layout, then found complete removal visually
unappealing and requested a percentage and live changes. Original fog is default.

Video Settings > Enhancements > Fog strength provides 0–100%, default 100%.
0 removes distance fog; 100 preserves the original signed fog coefficients
bit-for-bit. Intermediate values scale both depth coefficients, reducing the
fog buildup. This is a strength control, not a linear opacity control after
the native fog clamp. Level draw distance and culling remain unchanged.

Apply saves fog_percent in video.ini and sends WM_APP+26 to the active runtime
window. The runtime checks the owner window and range and updates an atomic
preference consumed by the next F3DDKR fog command. No restart or per-frame file
poll is needed. Cancel leaves the running game unchanged. Fog-only edits do
not request a restart; FPS/VSync/blur changes retain their restart behavior.

The F3DDKR MoveWord handler preserves G_FOG, fog color, material blend modes,
depth, object alpha and game state. Clearing G_FOG would incorrectly substitute
vertex alpha into the fog blender. Pinned RT64 RSPProcessCS.hlsl and rt64_rsp.cpp
establish the signed multiplier/offset calculation. Both coefficients must be
scaled together, retaining their native zero point.

History: the first candidate was a Remove fog toggle applied on next launch.
The owner requested finer control and asked whether restart was essential.
It was an implementation limitation, not an engine requirement. Existing
remove_fog=0/1 preview files migrate to 100/0 respectively; absent keys use 100.
Malformed/out-of-range/duplicate keys are rejected, including both old and new
fog keys in one file. Older binaries can reject newer configuration keys.

The sidebar has Display, Rendering, Frame rate and Enhancements plus search.
The owner rejected the initial CSS icon approximations. They were replaced by
the supplied design's actual vector paths, with source SVGs and a 4x raster
atlas for RmlUi, normal and JFG amber selected states.

Validation: prior 202 UI checks covered tabs/search and the original fog toggle.
The revised checks cover percentage drafts, tab retention, no restart notice,
signed coefficient scaling, exact original behavior and legacy configuration.
See evidence/portable-storage.json for the latest completed checks and hashes.
No autonomous gameplay/visual verification was performed. Live appearance,
translucent materials and scene transitions remain for owner review.

Scope limits: distance fog only; no extra draw distance, particle removal or
guarantee that all areas look better at lower settings. This is not released,
and GitHub #26 remains open. Prior private evidence is preserved under
D:/JFG-private/v13-settings-revision-20261018.

Revised qualification: 204 UI checks pass; video configuration/coefficient checks report zero failures. Launcher and runtime builds pass. The initial revised UI run correctly exposed an obsolete test expectation (a restart notice with no changed settings); the expectation now matches the new behavior. Both runs are preserved. Updated Settings Preview delivered, preserving save hashes and the owner's video settings. Live gameplay review remains pending.

## Owner acceptance (2026-10-19)

The owner states fog/settings are done after testing the live strength preview. Local owner acceptance recorded; not released or posted to GitHub.

## v1.3.0 source availability

The documented change is included in tag v1.3.0 (launcher/source
02be6fa9a4c50f4056f778c5148ca8ac70b0e92b; clean runtime
665596482a7395593e85dbe73f1bd4b016d183d9). See the
[combined release qualification](../releases-1.3.0-qualification.md) for owner
acceptance, source CI, package and publication evidence. Earlier failed attempts
and the scene/device/seed limits above remain part of this record; inclusion
does not turn an unverified broader report into a confirmed resolution.
