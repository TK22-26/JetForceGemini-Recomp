# Jet Force Gemini Recomp

[![Build status](https://github.com/TK22-26/JetForceGemini-Recomp/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/TK22-26/JetForceGemini-Recomp/actions/workflows/ci.yml)

A native PC recompilation of Jet Force Gemini, currently available as a
Windows x64 development preview. Supply your own supported North American
ROM and build the game locally using the launcher or command-line tools.

[Get started](docs/getting-started.md) ·
[Known issues](docs/known-issues.md) ·
[Report a problem](docs/playtesting.md) ·
[Contribute](CONTRIBUTING.md)

## Current preview

Preview 0.4.0-preview.4 includes graphics/audio timing fixes,
a correction for opaque particle textures, and longer input recordings.

Live volume/mute controls, player-shadow correction, sound-player recovery,
and optional live map/inventory tools are available in preview.3.
The Navigation mod combines supported walking, jumps and NPC interactions;
it remains experimental and does not establish autonomous campaign completion.
HD cosmetic variants stay in independently maintained community branches.

## What works

- Native rendering and audio.
- Keyboard controls and configurable Xbox/XInput controllers.
- Verified saving and loading, with a launcher for setup and subsequent launches.

Full campaign completion and original-console accuracy remain unverified.
This preview needs playtesting across more PCs, controllers, and gameplay.
See [recent gameplay fixes](docs/development/boot-gameplay-fix.md) and
[development progress](docs/dashboard.md) for details.

## Campaign playtest progress

**Latest maintainer playtest:** the game is playable up to the final cutscene for
the final ship part. Testing stopped there; progression beyond that point and
full campaign completion remain unverified. This run used the optional
infinite-health and enemy auto-kill testing mods.

Earlier character-specific checkpoints:

| Character | Campaign progress |
| --- | --- |
| Juno | Reached Mizar's Palace after Tawfret. |
| Vela | Tested up to Cerulean. |
| Lupus | Progress not yet reported. |

## Getting started

Start with the [getting started guide](docs/getting-started.md) for requirements,
downloads, and setup. You need a supported US big-endian `.z64` ROM;
the project does not provide ROMs or game assets.

The [released launcher](https://github.com/TK22-26/JetForceGemini-Recomp/releases)
builds its own pinned source revision. The `main` branch can contain newer
fixes; the guide explains both installation paths. Windows 10 setup has
[reported issues](docs/known-issues.md#windows-10-setup) that are still open.

## Help by playtesting

Play normally and report problems: crashes, freezes, progression blockers,
incorrect controls, graphics or audio, and save/load failures. Check
[known issues](docs/known-issues.md) first and attach the launcher's support
ZIP when available. Successful sessions do not need a report.

See [playtesting and reporting](docs/playtesting.md). If you want to contribute
code, [CONTRIBUTING.md](CONTRIBUTING.md) explains the pull request workflow.

## Future additions

The goal is a complete, faithful PC version of Jet Force Gemini with optional
modern enhancements. Planned work and remaining validation include:

- **A complete campaign (unverified):** the campaign may already be complete,
  including all playable characters and required progression. Saving and loading
  are verified; full campaign playthroughs remain untested.
- **Original local multiplayer and optional content:** broader coverage of the
  modes and activities beyond the main campaign.
- **Ultrawide support:** wider aspect ratios with correct gameplay presentation,
  menus, and HUD layout.
- **Higher frame-rate presentation:** smoother visuals while preserving the
  original gameplay timing.
- **Mod support:** documented interfaces and tools for community modifications.
- **A more polished PC experience:** smoother setup, broader controller coverage,
  and better crash and freeze diagnostics.

Compatibility and stability come first. These are development goals; release
dates have not been set.

## Build and development status

- [Build status and CI runs](https://github.com/TK22-26/JetForceGemini-Recomp/actions/workflows/ci.yml)
- [Development progress](docs/dashboard.md)
- [Build the playable game from your ROM](docs/development/rom-bootstrap.md)
- [Build and test the project source](docs/development/setup.md)
- [Documentation index](docs/README.md) and [project roadmap](docs/planning/JFG_RECOMP_MASTER_PLAN.md)

CI checks source, tools, and tests without a ROM. A passing build does not
establish that every level or gameplay feature works.

## License

Original project code and documentation use the [MIT License](LICENSE).
Dependencies retain their [third-party notices](THIRD_PARTY_NOTICES.md).
Jet Force Gemini game content and trademarks belong to their respective owners.
