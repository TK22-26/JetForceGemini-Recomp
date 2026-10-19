# RENDER-016: GitHub #25 Ally X cutscenes, homing reticle and rain

- Status: AWAITING REPORTER RETEST ON v1.3. Owner confirms Tawfret rain and smooth hut cutscene, and cannot reproduce missing weapon reticles with mouse/Modern Controls. Reporter hardware/control-mode verification remains open; no new reticle or rain patch claimed.
- Report: https://github.com/TK22-26/JetForceGemini-Recomp/issues/25
- Hardware: Windows 11, Xbox Ally X; no support ZIP or recording attached.
- Severity: substantial cutscene slowdown and missing gameplay/weather visuals.

The reporter identifies large slowdown during the first-level hut tribal
cutscene, missing reticles for weapons including homing missiles, and missing
rain in the zombie world. They also saw reticle/rain omissions in PJ64 with
GLideN64; this is not proof of original-hardware behavior or our root cause.

Existing v1.3 cutscene/blur work and the released shuriken CPU-framebuffer
retention fix are relevant leads, not verification of these cases. Treat the
three paths independently: exact cutscene and hardware performance, weapon
visibility/CPU drawing and final presentation, and weather production/import.
At initial triage there was no patch or live verification for this report. Owner prioritized #24 first; subsequent rain verification is recorded below.
No GitHub comment or closure has been sent. Target v1.3; retain open status
until each symptom has independent evidence and acceptance.

## Owner Tawfret confirmation and active rain investigation (2026-10-19)

The owner confirms rain is missing on Tawfret in the current v1.3 preview,
including after selecting Original FPS. Rain is the active priority; missing
homing-missile/other weapon reticles and Ally X hut performance remain separate
open targets. Similar GLideN64 behavior is a reporter observation, not evidence
that native hardware omits the effects.

The latest closed Settings Preview run is the owner's Tawfret capture:
20261019-033008-f8512a61d2ad4e24a151061b91c43362. Retained private inputs,
frame timings, map state, controls, save and configuration have SHA-256 manifests
under v13-tawfret-rain-20261019/owner-tawfret-original. Its configuration is
Original, VSync on, Reduced blur and 100% original fog. This rules out the new
zero-fog setting for this sample. Frame counters alone cannot prove weather
pixels were generated or displayed.

Historical fix f53dea1 preserved CPU framebuffer effects by completed color
readback, CPU import before VI hashing, and game-selected-buffer presentation.
The fix remains in the current source; high-refresh later adds a retained CPU
mask path. Current hypotheses: native effect gating, CPU draw/import visibility,
or subsequent presentation overwrite. No root cause or rain correction yet.
The latest capture has compact timing/control data, not a complete framebuffer
or original software-drawing trace; its observational limits will be retained.

The production guard remains enabled with the same investigation and counters.
The owner approved two hours for this rain continuation. No autonomous gameplay
or emulator runs; the owner verifies the candidate.


### Focused Tawfret diagnostic prepared (2026-10-19 UTC)

The latest owner capture is level 0x9e, Original presentation, VSync on and
fog 100%. It contains no weather or rain pixel-write events, so it cannot
establish whether weather generation or presentation fails. The earlier CPU
framebuffer preservation fix is still present. A missing module-5 publication
in this recording is a lead only, not a confirmed cause.

The owner approved a short new capture. The explicit --weather-diagnostics
launcher action enables read-only native weather setup/update/draw observations,
postprocess gating returns, actual rainFastDraw changed-pixel counts, deferred
software-line writes and the existing renderer import trace. Ordinary play and
ordinary diagnostics leave this extra probe disabled. No weather values are
forced and no game-state writes are introduced. This is diagnostic preparation,
not a rain fix; owner gameplay capture and analysis remain pending.

Private evidence: D:/JFG-private/v13-tawfret-rain-20261019, including a hashed
copy of the original owner capture/save/config before preparation. No ROM,
generated native source, or personal save is checked in.

Validation: native Release runtime and launcher compiled; 658 launcher checks
passed, including explicit weather-capture activation and duplicate-capture
rejection. Package hashes verified, copied save hash matches the untouched
source, and muted/Original/full-fog configuration checked. The desktop
JFG - Tawfret Rain Capture shortcut opens this diagnostic for the owner;
gameplay and visual verification remain pending. Logs are private under
D:/JFG-private/v13-tawfret-rain-20261019/owner-capture.

Capture preparation failure: launching the managed helper directly omitted
the required launcher identity and was rejected before game startup. The
desktop shortcut now uses the normal native launcher with an explicit weather
diagnostic argument; that launcher supplies the normal package identity and
keeps the map/settings menus available. No recording or save change occurred
in the rejected launch.


### First focused capture reviewed (2026-10-19 UTC)

Owner capture 20261019-034831-1010b4b44f124fabac6b32474af5f777
completed in level 158 / 0x9e. It recorded 1,640 CPU postprocess calls,
no weather setup/update/rain-drawer calls, and no rain pixel writes.
The native weather state stayed at type zero. The final logical RAM snapshot
has a zero weather count and zero weather parameters in the current level
header (header +0xa0 through +0xab). Native initialization and drawing both
gate weather on this count. This narrows the next check to why that room has
no weather setup; it does not yet establish whether the loaded header is
wrong, whether this room uses another rain effect, or whether native game
conditions intentionally disable rain. No weather-forcing workaround applied.

Private summary and header observations: owner-weather-summary.json and
owner-header.json under the investigation evidence directory. Reticle review
remains queued; the owner requested a Map / Settings / Mods all-weapons action
to make each weapon available for testing.


### Landing-room hypothesis resolved against original assets

The native room-158 header in captured RAM exactly matches the original ROM
weather fields: all zero, with native name Swamp Landing Play. The same
0x118-byte raw header layout shows Swamp Maze (138) also has weather count zero.
In contrast Swamp (115), Swamp bog (118), Swamp Creek (121), Swamp track (125)
and Swamp_Ruin (132) each specify 1,104 rain particles. Swamp Landing (135),
a distinct cutscene room, also has rain. Thus absence of weather setup in the
owner recording is expected for the recorded landing gameplay room and does
not prove a renderer regression or resolve the broader GitHub report.

Private header-rom-compare.json and native-weather-rooms.json record this
read-only comparison. No room assets or weather values have been patched.
The owner was asked for a short capture past the landing/maze in a rain-enabled
room, with an option to prepare a direct starting point. Rain remains the
owner-prioritized investigation; all-weapons packaging and live FPS follow-up
are secondary. The weapons test byte-diff check initially assumed swapped
memory even in the unswapped fixture; the fixture was corrected, rerun pending.


### Owner confirms rain past the landing zone

On 2026-10-19 the owner continued the focused capture and explicitly confirmed
rain is visible beyond the landing zone. Live room logs reached Swamp bog (118)
and Swamp (115), both rain-enabled in the original ROM. The closed capture's
initial-profile/video.ini records Custom 120 FPS, VSync on, Reduced blur and
100% fog. This corrects the earlier provisional attribution to Original FPS:
the earlier dry landing capture used Original, but the owner changed settings
before the later wet-room run. No rain correction was needed for this reported
reproduction: landing/maze dryness matches native room data.

The completed wet-room capture is
20261019-040009-de0a1a0d65fe4f768f401d83f14f6a34. It contains 1,363
rainFastDraw observations and all 1,363 changed framebuffer pixels (210 to
4,399 changed pixels per call). The owner visually confirmed the rain. Final
RAM identifies Swamp Grave Yard (242), so this was not limited to the landing.
Private wet-capture-summary.json links the draw counts and recorded session.
These diagnostic timings are not a performance qualification.

The owner separately questioned rain in the opening cutscene, replayed it,
and confirmed: "nevermind the rain is there". Record this as owner visual
verification, separate from the completed wet-room log and consistent with
the rain-enabled native Swamp Landing cutscene header (135). Do not confuse
the cutscene with the deliberately dry Swamp Landing Play room (158).

Rain is verified for these owner-tested v1.3 scenes/settings, not every device
or weather scene. No weather values, assets or renderer behavior were changed
to obtain this result. The GitHub reporter's v1.2.1 / Ally X environment has
not been independently verified, and the issue remains open for weapon
reticles and device-specific cutscene performance. If their rain report
persists, obtain the exact room, version and settings before changing weather.

Transferable lesson: distinguish playable-room and cutscene weather headers,
and use each capture's initial settings instead of assuming settings stayed
unchanged between runs. Pair actual pixel-write observations with visual
confirmation; an inactive weather module in a dry room is not proof of a
rendering regression.

Owner follow-up decision: ask the GitHub reporter to confirm rain on v1.3. No additional rain patch is planned from the verified owner reproduction. Reporter confirmation remains pending; no comment has been posted in this continuation.

## Owner reticle/hut review and reporter follow-up (2026-10-19)

The owner cannot reproduce the missing weapon reticle using mouse/Modern
Controls, and reports the hut scene plays fine. This is scoped owner feedback,
not proof that the Ally X reporter's input path or machine is fixed. No new
reticle correction is justified by the current reproduction.

Owner decision: request a v1.3 retest for weapon reticles, rain and the hut
scene. Ask which input device and control mode the reporter uses (mouse versus
controller/handheld; Modern Controls versus Original Mapping), plus exact
weapons and aim/fire bindings if the reticle still fails. Preserve the distinct
performance report and request location/settings or support logs if it persists.
This follow-up is queued for v1.3 availability; no message or closure was sent.
