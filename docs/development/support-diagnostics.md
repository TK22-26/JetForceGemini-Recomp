# Support diagnostics

Source candidate: 0.4.0-preview.2. These additions have not been released.

Validated locally on 2026-10-04: full Windows Debug and Release builds from the
deep checkout, all 69 native tests in each configuration, 66 launcher checks
and 12 setup checks. Build-path, policy and schema checks also passed. The actual
crash/freeze fixture output survives ZIP filtering, and the fault RVA resolves
to `crash_leaf` with the exact local executable and PDB. This is ROM-free
diagnostic validation, not a new game-playthrough or clean-machine installation.

The launcher selects a session explicitly and exports eight bounded text files
plus instructions. It accepts only the grammar in `SupportSession.SafeLine`,
both when recording and when exporting. It never archives an entire directory.
Game data, raw stack/register contents, personal paths and symbol files are
excluded. Successful sessions need no issue; GitHub issue attachments are the intake.

`frame=thread/index/module/pe-timestamp/image-size/rva` gives a module-relative
instruction location. The native crash handler starts with the exception's
CONTEXT and unwinds at most 48 frames. Its SEH boundary tolerates unreadable
stack metadata. A catastrophic stack/heap failure or forced process termination
may prevent capture; the ordinary stage/failure logs remain useful.

Freeze capture uses the separate `jfg-support-capture.exe`. It checks the
launched process's creation time and executable, prefers its direct native child,
then validates the selected identity again before using a Windows PSS snapshot.
Only stack locations leave that process. DbgHelp runs serially in the helper,
with an empty symbol path and no requested symbol downloads. Limits: 64 threads,
48 frames per thread, 256 frames overall, and a 12-second launcher deadline.
No game thread is explicitly suspended by the helper. A failed retry retains
the previous successful capture and records the retry failure in `launcher.log`.

GPU IDs list installed PCI display adapters with registry driver versions; they
do not prove which adapter RT64 selected. Missing GPU data is explicitly marked.

The recent-progress file is a rolling 60-sample window. Its fields are elapsed
milliseconds since the first VI sample, frame count, retrace count and controller
poll count. It can distinguish stalled emulation from continuing progress;
testers must still describe the level/menu and actions that triggered the issue.

`build_from_rom.py` enables local MSVC symbols and emits an adjacent
`jfg-native-boot.exe.support` manifest. The launcher accepts that manifest only
when its executable SHA-256 matches the selected game, and enables freeze capture
only when the helper hash also matches. `source=` remains the launcher revision;
`build_source=` identifies the game, with a dirty flag and source-content hash.
The dependency lock, local PDB hash and PE CodeView GUID bytes/age are also recorded.
Keep the exact executable, dependencies and symbols locally: rebuilding the same
source is not guaranteed to reproduce instruction offsets. Neither the executable
nor PDB belongs in public issue attachments.

For a local symbol lookup, run:

```powershell
python scripts/resolve_support.py --report JFG-support.zip --executable path/to/jfg-native-boot.exe --symbols path/to/jfg-native-boot.pdb
```

This checks the executable and PDB hashes plus the PE CodeView identity before
resolving captured game frames. Its function-name output stays local and is not
added to the public ZIP. System/driver frames require their own matching symbols.

To interpret frames manually, first match the executable/PDB hashes to `build.log`.
Load that executable and PDB in a local debugger, then resolve each executable
RVA relative to its loaded module base. For system/driver frames match the module
name, PE timestamp and image size before resolving an RVA. A symbol mismatch
must be reported as unresolved, never guessed from another build. CodeView GUID
bytes are stored in file byte order, followed by the age in hexadecimal.

Validation (no ROM needed):

```powershell
./scripts/build_launcher.ps1 -Test
python -m unittest discover -s tests -p test_runtime_identity.py
python scripts/build_windows.py --config Release --test
```

The Windows integration fixture triggers a real access violation, checks fault
frames, captures a waiting process, rejects a stale process identity and verifies
continued progress after capture. Launcher tests check failed-session retention,
safe exports, legacy/stale build metadata and setup error projection. Windows
PowerShell 5.1 setup tests exercise a real subprocess writing stderr and exiting
with a nonzero code. These checks do not establish a clean Windows/UAC setup or
campaign playthrough; those still need playtest coverage.

API references: [Windows process snapshots](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/nf-processsnapshot-psscapturesnapshot),
[thread records](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ns-processsnapshot-pss_thread_entry),
and [DbgHelp stack walking](https://learn.microsoft.com/en-us/windows/win32/api/dbghelp/nf-dbghelp-stackwalk64).


Windows build paths: use `python scripts/build_windows.py --test` for ROM-free
development builds. It keeps output under `%LOCALAPPDATA%\JFG\b\<checkout-id>`
so deep source checkouts do not lengthen MSBuild tracking paths. The ROM builder
uses the same cache for dependencies, generated inputs and native output. Existing
workspaces are preserved; `--build-root D:/JFG-builds` selects a shorter writable
location when necessary. Different checkouts receive separate cache IDs. Keep
these local generated builds and symbols out of issue attachments.
