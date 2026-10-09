# Unified frontend and multiplayer controllers

Status: implemented locally; validation and hardware qualification are listed below.

## Goal

One visible native application window for ROM setup, home, gameplay, and live settings. Preserve the original game's rules, graphics, and in-game aspect-ratio selection. Support four independent N64 controller ports so local multiplayer can be tested.

## Starting limitations

Before this change, the C# launcher started a native game executable with a separate Win32/RT64 window. One controller profile chose one XInput device, and the native input bridge reported only port 1 connected. Mapping changes applied on restart.

## Delivery plan

1. Replace the single input sample with four independently assigned, latched controller ports. Preserve legacy port-1 mappings, keyboard fallback, replay behavior, and SI polling boundaries. Empty ports must report disconnected. Device selection must distinguish physical devices from player ports.
2. Add the native game-window menu: Game, Controllers, Video, Audio, Tools, Help. Live changes use one validated settings model and persistent configuration. Settings dialogs capture gameplay input and clear held state on close/focus loss. Preserve game timing while editing settings.
3. Add borderless fullscreen with F11, restore prior placement, and keep display mode separate from the base game's widescreen option. Menu access remains available in fullscreen. Remember window preferences.
4. Provide controller port tabs, device assignment, binding capture, deadzones, inversion, and live input feedback. Prevent unintended device sharing; handle disconnect/reconnect without moving a device to another player's slot.
5. Move the startup/home interface into the native application shell. Keep the window alive across game start/stop. Existing setup tooling can run as a background helper. Provide ROM selection, setup/build progress, cancel/retry, Play, return home, and useful failure reports.
6. Integrate packaging and launch entry points so users enter the unified frontend by default. Keep diagnostic command-line runs usable.
7. Validate and document the delivered experience.

## Settings and presentation

Use a readable, DPI-aware layout with clear connected/disconnected states and keyboard navigation. Windowed mode exposes a top menu. Fullscreen exposes settings via Esc and restores the menu when needed. Retain volume/mute and open-support-folder actions. Tools can open the map and inventory where available; optional testing mods remain explicit.

Persist controller profiles, master volume, display mode, and window placement in the user's profile. Apply changes at a safe runtime boundary. Do not overwrite unrelated profile data. Mark settings that require a restart.

## Architecture

The native frontend owns presentation and application lifetime; the game session owns guest execution and rendering. The game session can start and stop without destroying the home window. Shared settings feed both the frontend and runtime. Setup work runs outside the UI thread and reports progress/failure. Preserve support logs and crash recovery when changing process boundaries.

The current runtime executes generated ROM-derived code, so first-run setup must still prepare that runtime. The bootstrap and runtime handoff must be designed explicitly before claiming seamless first-run ownership.

## Acceptance

- Ports 1 through 4 have distinct samples, connected flags, mappings, and stable assignment.
- Two or more physical controllers can independently operate original multiplayer.
- Disconnecting one controller does not transfer another player's controls or leave buttons held.
- Legacy profiles and single-player replays still work.
- Controller changes and mute/volume take effect during a running game.
- Settings input does not also move, shoot, or pause characters.
- Fullscreen round-trips preserve window placement and game aspect ratio, including cutscenes.
- Home -> Play -> Stop -> Home works repeatedly without losing saves, leaking sessions, or leaving invisible windows.
- Setup failure/cancellation returns a usable home screen.
- Packaged launcher enters the new flow; diagnostic runs remain supported.
- Hardware-dependent checks are explicitly distinguished from automated checks.

## Inspiration

Ship of Harkinian's newer releases use a searchable Esc menu and F11 fullscreen:
- https://www.shipofharkinian.com/changelog
- https://github.com/HarbourMasters/Shipwright

Borrow interaction patterns. Game-specific cosmetic enhancements are outside this work.

## Delivery record

- Native C++ frontend owns the window; isolated game processes create a render
  child inside its viewport. Stopping or crashing a session leaves home alive.
- Setup, controller/audio dialogs and existing tools reuse embedded managed
  services. The primary launcher is native; settings/tool dialogs remain WinForms.
- Four independent port samples and SI status/read delivery implemented, with
  atomic per-port profile files, live reload, automatic device discovery, explicit disconnection and sticky
  automatic XInput assignment.
- Home/game fullscreen round-trips, settings capture, embedded helper extraction,
  two start/stop cycles, cancellation/close during startup, mute persistence,
  and recovery after a deliberately crashed test session passed isolated UI tests.
- Three focused C++ tests passed, including four-port SI packet delivery,
  disconnect isolation and release gating across all four players.
  Launcher checks: 471 passed. Setup fixture checks: 12 passed.
- Remaining qualification: physical two/four-controller multiplayer, fresh-PC
  first-run installation/UAC/reboot, and long play sessions through cutscenes.
- A complete Windows game build from this public checkout passed in a fresh,
  short build directory; the frontend lifecycle tests also passed with that build.
- Release publication is separate: the source revision must be committed and
  available remotely before publishing a launcher that builds that revision.
