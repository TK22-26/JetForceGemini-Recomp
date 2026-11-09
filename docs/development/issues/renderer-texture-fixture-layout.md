# TEST-RENDERER-LAYOUT-20261108: Texture fixtures omit their regional layout

Status: corrected and verified in the local renderer test; uncommitted and unreleased.
Severity: test coverage limitation, not a demonstrated gameplay regression.

## Symptom and reproduction

While reviewing [GH-051](github-nightvision-damage-presentation.md), compiling
the current `tests/renderer/rt64_f3ddkr_texture_tests.cpp` against the current
regional preview renderer libraries failed with `Owned blended level face must
retain colour plus opaque-core depth contribution`. The screen-effect ownership
case runs first and had already passed. An unchanged private driver that runs
only that case also passed. The initial progress update incorrectly placed the
failure before the screen-effect case; the actual call order corrects that.

## Cause and remedy

The multi-region `Rt64F3ddkr` constructor accepts an optional `RendererGameLayout`.
Without a qualified layout, guest-dependent presentation policies intentionally
fail closed. The synthetic fixtures still constructed the renderer without the
existing USA fixture layout, so their native-address level geometry was not
recognized and no solid-core depth contribution was generated.

All seven renderer instances in this test now receive
`jfg::test::renderer_layout`, matching the synthetic guest addresses already used
by the fixtures. The production renderer, regional selection and game binaries
are unchanged. This is a test setup correction, not a new foliage or night-vision
runtime fix.

## Verification and limits

The original failing run is preserved. After the explicit fixture layout change,
the complete `jfg_rt64_f3ddkr_texture_tests` executable passes, including native
night-vision/damage ownership, menu alpha, solid-core depth, reflections, shadow
reuse, LOD and command handling. The test was freshly compiled with current
source and linked against the renderer libraries used by the current USA preview;
it creates no GPU device and runs no game ROM. This does not claim a full project
test run or a new visual acceptance of any issue.

Private evidence: `issue51-review-saves-20261108/renderer-regression/`, including
`result.json`, `focused-result.json`, `qualified-result.json`, build logs and the
original test source. Source remains uncommitted; no release is claimed.

Compatibility lesson: tests that simulate guest addresses must provide the same
qualified regional layout as the runtime. A missing layout is intentionally safe
but cannot exercise address-dependent behavior.
