# VERIFY-EMU-20261027: Original-ROM reference qualification

- Status: scoped original-ROM comparisons and full available regression checks
  complete; findings and remaining review limits below.
- Scope: four-hour owner approval on 2026-10-27 UTC; local only.
- No GitHub mutations, uploads, release changes or original-save changes.

## Original-ROM reference

EmuHawk 2.11.1, Mupen64Plus with Angrylion/cxd4, US ROM, original four-MiB
memory configuration. All runs use isolated muted instances and copied saves.
Emulator and ROM hashes, settings, actions and fixture edits are retained
privately under emuhawk-sanitization-20261027. Emulator host wall speed is not
used as game speed. This is emulator evidence, not new physical N64 testing.

| Area | Original-ROM result | Candidate comparison and remaining limit |
| --- | --- | --- |
| GH-057 menu icons/vignette | Widescreen menu has transparent icon borders and a smooth native VI-filtered vignette. | Actual candidate menu preserves border transparency and smooths the upscale-only mask. Different resolutions/animation phases are not pixel-exact comparisons; owner review pending. |
| Vine/gem occlusion | Matched camera/player viewpoint reproduces gems through opaque vine pixels. Original pickup positions, textures, alpha, draw order and render modes are unchanged. | Confirms an original-game depth-write defect. Candidate captured-frame GPU/state tests preserve holes/soft edges and foreground gems; owner review pending. |
| GH-048 flying enemies | Repeated original-ROM flight/death and probe-removal runs match exactly. All 1,410 common live-flight position/velocity samples match the candidate by update, spread over more guest VI retraces. All three controlled death curves match their common prefixes. | Warm Original/120 run at 30 updates/second, versus roughly 19 in the emulator encounter. Confirms inherited per-update timing sensitivity. No arbitrary speed factor; gameplay timing remedy and wider hardware/type qualification remain open. |
| GH-051 damage tint | Actual original enemy hits emit the expected red-tint RGBA16 screen strips. | Candidate material predicate matches; prior GPU resolution, ownership and four-phase 120 Hz motion checks pass. |
| GH-051 night vision | Lupus walks to the original room 316 pad and presses A, activating the original green effect. Only copied-save checkpoint/character/goggles prerequisites are changed. | Same save/controller-poll route activates the effect in the 120 FPS candidate, with clean exit and actual output captures. Owner campaign-route review pending. |

See the linked per-issue records for symptoms, causes, candidate changes and
qualification details: [menu](github-menu-icon-vignette.md),
[vine](vine-gem-occlusion.md), [flight timing](github-flying-enemy-speed.md),
[screen effects](github-nightvision-damage-presentation.md).

PC launcher, support ZIP, Proton, Modern bindings/settings and Enhanced Shadows
have no equivalent N64 feature to compare. They retain their platform tests and
intended-behavior/native-handler checks rather than an invented emulator pass.
Prior owner-approved camera, effects, reflections and shadows keep their
recorded finite acceptance; this follow-up does not claim a complete campaign
replay or all-scenes coverage.

## Full available regression results

- Windows Release build and CTest: 115/115 pass.
- Linux current-source Release CTest: 108/108 enabled cases pass. The existing
  jfg.g2_trap_probe_runtime platform fixture exclusion remains.
- Python: 1807 run, 49 explicit environment/platform skips, zero failures.
  The newer installed WSL executable does not match the older pinned sanitizer
  integration fixture; that coverage is unavailable, not silently counted as
  passed. The pin is unchanged.
- Final rebuilt managed launcher: 690 checks; setup: 28 mocked checks.
- Graphics adapter: 6, viewport checks, and storage policy: 23 pass.
- Full rebuilt launcher UI suite: Modern 1015, composition menu 104, Windows
  HWND fallback 105, update UI 78, video UI 247, storage UI 21, and original
  controller mapping/device/capture regression suite pass.
- Native RT64 texture/material integration passes.
- Final embedded helper/shell ordinary hosted Play and close pass with a
  separate muted copied profile; native runtime and owner review save unchanged.
- Actual final support archives pass privacy, fixed-entry, producer and exact
  byte-boundary checks; see the [audit](support-zip-presentation-sanitization.md).
- Earlier batch actual GE-Proton/umu/steamrt menu/pixel checks remain scoped to
  their recorded source. The 105-check run above is a Windows fallback test,
  not a fresh Steam Deck or Proton execution.

Private results: checks-005.json, checks-019.json, linux-012.json,
ui-026-result.json, hosted-smoke-024/result.json and support-audit-021.
Final whitespace/hygiene/schema checks are recorded with the final report.

## Informative failures and limitations

- A first vine placement forced camera fields at the wrong time and yielded sky
  only; discarded. Writing the recorded view coherently after controlPlayer
  returns reproduces the actual overlap without changing materials.
- The first death Lua wrapper had an invalid newline escape and never ran;
  corrected before comparison.
- Register probes require BizHawk's a0_lo/a1_lo/ra_lo aliases. Earlier callbacks
  without them failed and are not evidence.
- The first native timestep probe misspelled its hash-output variable and failed
  setup; corrected probe completed. Dump probes are not performance benchmarks.
- A forced night-vision selector without its palette rendered black. Actual
  original pad activation replaces it as visual evidence. Copied-save selection
  and inventory-bit-order mistakes were corrected before qualification.
- EmuHawk initially failed while removing temporary breakpoints during shutdown
  after completing screen-effect captures. Explicit callback cleanup fixes the
  fixture; the final real-pad run exits cleanly.
- One documentation update used the Windows default code page and failed before
  writing the changelog. It was resumed with explicit UTF-8, and the affected
  flight-note punctuation was restored. No runtime source changed for this.
- EmuHawk cannot validate Windows 10/GTX1080 delivery or Steam Deck hardware.
  GH-032/GH-035/GH-040 reporter retests, GH-054 project clarification, GH-058
  affected-machine evidence and the buried-drone collision sequence remain open.
