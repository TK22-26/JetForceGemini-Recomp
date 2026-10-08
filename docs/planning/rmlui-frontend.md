# RmlUi frontend design handoff

Owner-selected framework: RmlUi, with C++ behavior and RML/RCSS presentation.
PR #10 remains draft until the owner approves manual testing and UI direction.

## Source designs

Eight owner-provided HTML ZIP exports on 2026-10-08: launcher, in-game menu,
in-game child window, controller mapping, video, support report, setup/build,
and audio. Preserve navy backgrounds, amber action/focus colors, cyan device
indicators, Barlow/Chakra Petch typography, orbital animation, spacing, and
keyboard/controller focus states. The React export is a visual reference;
the native UI does not embed React, JavaScript, or a browser.

Latest owner correction: the home screen has a required **Game ROM** card.
Remove **Game Build**. Setup owns the generated executable automatically.
The install location and rebuild action belong in Setup; Play guides a user
through setup when no compatible runtime is ready.

## Notifications

Show the controller notification at the bottom on Play and first activation
of a controller, as well as connection/reconnection and disconnection.
Use actual device and assigned player information, never hard-coded DualSense.
Do not retrigger for every gameplay button or steal focus/input.
The reference has a 400 ms spring entry, approximately 4 s hold, and 220 ms
exit. Its 7 s repeating animation is for demonstration only. Queue/coalesce
multiple device events. Honor reduced motion with a fade. Preserve safe
placement in windowed/fullscreen and avoid covering gameplay controls.

## Implementation sequence and acceptance

1. Pin RmlUi and font dependencies; provide a native review harness and shared
   RML/RCSS components. Include font and dependency license notices.
2. Bind home/ROM/setup to existing validated setup and process supervision.
   Show actual verification/build state; never display fabricated percentage,
   ETA, device identity, session records, or "up to date".
3. Move controller/audio/settings presentation to RmlUi and C++; preserve atomic
   configuration, four independent ports, release-before-learn, live application,
   invalid-input handling, reconnect isolation, and safe input capture.
4. Integrate the same presentation into the game render host with an explicit
   settings channel. The existing separate session process/crash recovery must
   remain functional. Dimming and the PAUSED badge require real coordinated
   pause semantics; hiding the game does not constitute pausing.
5. Connect support sessions, ZIP creation and freeze capture; no ROM/save
   inclusion. Preserve crash evidence and prevent UI-thread blocking.
6. Audit video settings against the 1:1 game policy and renderer capabilities.
   Expanded widescreen, interpolation, resolution and AA shown by the mockup
   are not already supported merely because a widget exists. Keep unsupported
   controls unavailable until implemented and tested. Distinguish the game's
   native widescreen option from host window mode.
7. Validate design comparison, resize/DPI/fullscreen, keyboard/gamepad navigation,
   real controllers, live audio, start/stop/recovery, packaged resource loading,
   and source/license inventory. Obtain owner UI approval before merging.

## Implemented integration

The production native target now uses RmlUi with embedded RML, RCSS and fonts.
DirectComposition places the interface above the hosted native game child
window. The game process stays isolated and supervised, and Stop returns to
home after saving. The optional standalone design harness remains available.

Audio and four-player controller mapping are native C++ panels using the
runtime's existing settings formats. Assignment, binding learning, clearing,
deadzone/thresholds, inversion and reset save atomically. Settings capture all
game inputs; a cooperative VI-boundary pause stops gameplay and queued audio.
The PAUSED indicator requires acknowledgment from the game process.

ROM verification, setup/download/build, support-session enumeration, sanitized
ZIP export and freeze capture use the embedded existing helper as background
services. The interface is C++; the existing managed setup/map/inventory
services have not been rewritten. Setup uses actual status, without invented
percentages or completion estimates. ROM selection is required; the generated
build is managed automatically.

Host window sizing and borderless fullscreen are available. Aspect continues
to follow the original game's widescreen setting. Enhancement controls from
the mockup, such as interpolation, expanded aspect and AA overrides, are
omitted until supported and approved.

## Review gate

This is a draft UI migration. Manual design approval and physical multiplayer
qualification are still required. Automated profile-isolated window/session
checks supplement, rather than replace, the owner's testing. Do not merge
PR #10 or publish a release until that approval.

## Validation of the draft

The Windows native frontend and game runtime compile. Profile-isolated UI
checks exercised ROM-to-game launch, the hosted renderer, settings capture,
runtime pause acknowledgment and resume, fullscreen round trip, graceful
Stop/return-home, volume and mute, slider input, Player 4 device assignment,
binding clearing and clean shutdown. The existing 471 launcher and 12 setup
checks passed, together with 47 policy/bootstrap/font tests. The repository
history scan passed. Only the three exact OFL font hashes are permitted as
binary additions; modified and unknown font bodies remain rejected.

Four simultaneously connected physical controllers and the final visual
direction still need owner testing. The local candidate is
0.5.0-preview.3; it is not a published release.
