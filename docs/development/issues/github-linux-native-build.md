# Linux native build rejects compiler-specific probe declarations

- ID: BUILD-002; severity: high for Linux native/AppImage builds.
- Source: [GitHub #15](https://github.com/TK22-26/JetForceGemini-Recomp/issues/15), filed 2026-10-16.
- Affected report: Linux AppImage source `8b6837d`, GCC 16.2.1, CachyOS x86-64.
- Status: reported declaration defect confirmed in current source; no Linux remedy or build qualification in this review. Open.

Both declaration and definition of `jfg_phase9_execution_probe_slow` still use `__declspec(noinline)` in `src/boot/native_boot.cpp`. GCC rejects that MSVC spelling. The reported missing declaration and unused `emit_device_event` diagnostics are consistent with that first compilation failure; they are not evidence that the event function should be removed.

The reporter proposes a compiler-selected noinline macro and reports a successful build/play on the Linux branch. That external success has not been reproduced here. Current source also unconditionally includes `include/jfg/runtime/async_volume_file.hpp`, which includes `<windows.h>` and uses Win32 file APIs. Replacing the noinline spelling alone therefore cannot qualify this branch for Linux.

No patch, upstream merge or Linux build was performed in this launcher review. A follow-up must use portable noinline declarations, provide or gate the volume-file implementation appropriately, and build the actual native/AppImage target on GCC with warnings-as-errors. Host-shell tests alone do not qualify the generated game runtime. This is a Linux release blocker; it is not evidence of a Windows runtime regression. Private report: `launcher-update-button-20261016/issue-15.json`.

Lesson: fix the first compiler error and assess the complete platform path; do not claim whole-platform support from a two-line compiler workaround.
