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
0.5.0-preview.4; it is not a published release.


## Reference layout completion (2026-10-08)

The native launcher now follows the eight supplied references with shared
compact title bars, amber active-menu indicators, a ROM status badge, orbital
home decoration, and lower-left device notifications. Notifications preserve
the assigned player on disconnect and do not cover settings controls.

Controller mapping uses player/device tabs and separate Buttons, C Buttons,
and D-pad columns. All bindings, three live threshold sliders and inversion
controls fit the standard dialog; smaller windows retain a scrollable body
and a fixed action footer. Learn exposes a Cancel action, and Escape cancels
learning before closing the panel. Tab and Shift+Tab remain inside the open
panel. Video uses explicit window-mode choices and a display explanation;
support uses selectable session rows beside the ZIP contents; setup presents
the actual status in a log card. Audio retains immediate volume and mute.

Validation: native build, 471 launcher checks and 12 setup checks passed.
Profile-isolated visual checks covered the home screen, all five child panels,
Game menu, standard and small windows, with no RmlUi parsing errors. Live tests
verified volume buttons/slider, mute, Player 4 assignment, binding clearing,
threshold persistence, hosted gameplay, coordinated pause/resume, fullscreen
round trip and graceful Stop. Screenshots and detailed receipts are retained
in the original production-guard investigation's private evidence folder.

This is a local source/build update; the existing archive and draft PR are not
published or merged by this pass. Physical multiplayer and fresh-PC setup
qualification remain as listed above.


## Live map and inventory implementation (2026-10-08)

The owner supplied **Child / Live map** and **Child / Live inventory** HTML
references. Their inventory symbols are layout placeholders. Game artwork is
derived on the user's computer from their supported ROM; no artwork is embedded
in source, launcher resources, release archives or support reports.

The inventory now has compact tinted Weapons, Keys & Quest and shared Ship Parts
groups, live ownership counts, selectable tiles, Juno/Vela/Lupus buttons, Follow,
and a selected-item footer. Unknown telemetry clears ownership; old exports that
omit the Arcade chip bit do not claim it is missing. The default 470 x 790 window
fits all three groups; smaller windows scroll. Keyboard focus, names and ownership
remain available on each tile.

The map uses compact View, Layers, AI and Tools menus, a live/saved room header,
optional inspector and legend, zoom/fit/center commands and inspector filters.
Its geometry, height slices, interaction details, actual counts and guarded AI
actions are preserved. The navigation-mod launch remains the entry point for
these tools. They continue to use managed service windows; the launcher and
settings panels use RmlUi. Teleport was not an existing action and is not added
by this presentation change.

### Local image pipeline and provenance

`InventoryImages.cs` calls the existing `OpenVerifiedRom`: exact supported US
32 MiB big-endian `.z64` and SHA-1 verification, with the file held read-locked
during extraction. Unsupported byte orders and different ROMs are rejected;
there is no implicit byte-order conversion. Verification also precedes cache hits.

The implementation reads asset ranges from the supported ROM's filesystem LUT.
Weapon enum + 10 selects the game's frontend menu entry in section 26, then the
sprite definition (table 22 / data 21), then its texture (table 3 / data 2, or
table 1 / data 0 for the high-bit bank). This yields all 15 weapon HUD images.
Textures use the actual US header, including compression at byte 0x19, expanded
header and pixels at 0x20, five-byte raw-DEFLATE wrapper, RGBA and intensity/alpha
formats, and the pre-swapped odd rows used by the game's LoadBlockS path.

Other pickups use object definitions (table 46 / data 47) and their referenced
models (table 38 / data 39). `InventoryModel.cs` independently renders the static
vertices, triangle batches, texture coordinates and ROM textures into transparent
128-pixel thumbnails. It uses a fixed preview view rather than gameplay lighting
or animation. Crowbar selects its separate display group 1 and fits that group's
referenced vertices. Format observations were checked against the locally
available supported-US loaders, `makeModelGfx` and the existing navigation mesh
interpretation. No upstream implementation or asset bytes are copied into source.

The verified object identifiers are:

- Character item IDs 0, 1, 2, 3, 9: objects 118, 119, 120, 121, 127.
- IDs 16, 17, 20, 21, 22: objects 513, 508, 539, 509, 534.
- IDs 23, 24, 25, 26, 27: objects 438, 437, 436, 586, 585.
- Shared parts 0-11: objects 610, 611, 612, 613, 614, 615, 617, 618, 619,
  620, 621, 622.

There are **45 verified images**: 15 weapons, 15 character items, 12 shared
parts and three named character-select plaques. The Tri-rocket key flag (item 10) retains its readable name and explicit
unavailable-image state until a standalone visual mapping is verified. It does
not reuse a guessed key or weapon image.

PNG files and a provenance manifest live only under
`%LOCALAPPDATA%/JFGRecomp/asset-cache/<verified ROM SHA-1>/inventory-v5`.
Writes are atomic. Missing or corrupt thumbnails regenerate. A read-only cache
still permits in-memory rendering; a missing/invalid ROM leaves the text catalogue
usable. ROM verification and extraction run off the UI thread. Bounds checks cap
asset ranges, decompression, dimensions, mesh sizes and indices.

The build receipt and package input checks include both new decoder sources.
Release packaging remains an explicit allowlist; support export still accepts
only its sanitized text files. Regression fixtures include ROM-art/cache canaries.
Tests use independently authored pixels and triangles, plus private validation
against the user's ROM. Derived thumbnails, reference screenshots and actual-ROM
test evidence are kept outside the public checkout.


### Menu, live-tool and animation corrections (2026-10-08)

All six top-level menus now open compact dropdowns. Hovering switches dropdowns;
only clicking or activating an item opens a dialog. Menus use a 24dp bar,
26dp rows, border-aligned popup placement, F10, Alt+G/C/V/A/T/H, arrows, Enter,
and outside-click dismissal. Testing mods was removed from the Game menu.
The modal close control has a centered 28dp hit area. Dropdowns capture input but leave gameplay running. Modal dialogs request the
cooperative game pause. Tool actions release menu capture.

Normal launches export read-only live map/inventory telemetry through
`JFG_LIVE_OUTPUT`, into a fresh directory inside the ordinary save profile.
The optional navigation mod retains its separate save profile and explicit
gate for enemy removal, health writes, speed changes, and synthetic input.
Player identification and map exports work without that gate. The observer's
regression checks compare guest memory before and after observation/export.
Older runtimes require rebuilding to provide the new read-only export.

The launcher publishes the current export directory and process identity
(PID plus creation time). Open tools follow the active session. A stopped
process cannot resurrect an older directory. Inventory clears ownership when
a game stops or live data expires: it shows NO GAME RUNNING or WAITING FOR
LIVE DATA, never a saved inventory snapshot. Map wheel zoom preserves the
world point beneath the cursor, including at zoom limits. Inventory tiles
paint without changing control properties; first-load layout and image loads
invalidate the child controls.

Character selection uses the named character-select artwork: texture pairs
35347/35348 (Vela), 35342/35343 (Juno), and 35344/35345 (Lupus). Each pair is
assembled horizontally and flipped vertically according to the model's UV
orientation. Buttons scale the plaque without cropping its name. Accessible
names and tooltips remain available; letters are the no-ROM fallback.

The home scene restores vector orbital paths, moons, star twinkle, clipped
planet bands, front/back rings, scan line, ruler, bars and cycling decorative
coordinates. Optional ship flybys use models 356, 357 and 358 extracted from
the selected verified ROM. Their original geometry, UVs and textures are
projected through a perspective camera. Ships enter off-screen, bank along
3D curves, and leave the viewport or recede to a few pixels before despawning.
Reduced motion freezes the procedural scene/readout and suppresses ships.
Nothing from the ROM is embedded in the executable or release package.
Local ship data is regenerated after verification for each launcher process.

Validation includes the full managed launcher/setup suite, read-only observer
and perspective flight lifecycle checks, profile-isolated real-window captures,
character selection, first-load painting, and the hosted runtime. Actual-ROM
artwork and private screenshots stay outside the source/package boundary.
The production autonomy guard stays enabled, with all earlier charges retained.

Video > Video settings includes a saved Pause when inactive option (off by
default to preserve existing behavior). Focus loss or minimization uses the
same acknowledged VI-boundary pause as modal dialogs. Refocusing clears only the
inactive reason; an open settings dialog continues to pause the game.

The ship preview also reads each model's joint hierarchy and batch limb IDs.
Side engines are assembled at their ROM pivots and gently gimbal during flight;
this is a decorative flight animation, not playback of game animation clips.
Non-rendering marker batches are excluded. No joint or mesh asset bytes ship.


## Live-tool rendering migration (2026-10-08)

Production map and inventory entry points now open separate native RmlUi
windows using the launcher's renderer, embedded fonts and DPI setup. The map
canvas emits RmlUi geometry directly; no GDI+ bitmap is stretched into it.
The supplied revised waiting-room and settings layouts provide a 44dp collapsed
inspector rail, a compact menu, a left-tab settings modal and corner zoom/Fit.
View > All object labels defaults off and restores optional descriptions over
every visible marker. Select values share vertically centered text and arrows.

`NativeLiveTools.cs` is a presentation-free adapter over the existing validated
map/inventory models, layer clipping and navigation planner. A fresh per-window
transfer directory carries bounded, atomically replaced snapshots and commands.
The session PID/creation-time check still gates all live state. The window clears
data on loss of its service or current game, while a verified launcher pause
retains current data and labels it PAUSED. Ephemeral transfer files are removed
on normal close; the verified-ROM artwork cache contains no ownership state.

The WinForms classes remain as compatibility model/regression fixtures. User
entry points route to RmlUi, including inventory opened from the map. ROM pixels
are converted locally to bounded TGA textures for the native renderer, preserving
the existing named-plaque orientation. No extracted textures are embedded.

Validation uses direct GPU readbacks from the production RmlUi implementation,
actual wheel dispatch and cursor-anchor checks at both zoom limits, compact
and large layouts at 125% DPI, and real normal-game telemetry with a copied save.
The game replay proves changing map updates and live inventory followed by an
honest no-game state after process exit. The source save remains unchanged.
