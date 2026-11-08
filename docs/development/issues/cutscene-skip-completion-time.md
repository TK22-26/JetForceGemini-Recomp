# GH-041: Cutscene skips take too long to complete

## Owner confirmation — November 7 Proton test

The owner reports "it works" after testing the delivered native-ROM candidate
on Proton. Record this as acceptance of the reported opening-skip improvement;
the owner supplied no new exact latency measurement. A separate high-severity
[mouse-confinement defect](proton-mouse-confinement.md) was reported in the same
message. USA/PAL/JP-wide manual acceptance and released status are not inferred.
The earlier pending-acceptance statements below describe their historical stage.

## Current result — native ROM API candidate

Status: **cause isolated and candidate verified locally; owner Bazzite/RTX4070
retest pending; unreleased**. The owner reports 5–15 seconds after the opening
skip indicator fills, including with logging disabled.

The skip correctly accepts the request, then executes nine required scene
transitions. The slow part is loading their assets: one profile counts 8,060
immutable-ROM transfers for 4,913,256 bytes. Their original PI manager,
register/interrupt handling and guest-thread handoffs cost seconds even though
the ROM is already in host memory. The earlier next-Count-tick policy removed
cartridge bus delay but retained this protocol overhead. Inclusive parked-thread
and load durations overlap and must not be added as independent CPU costs.

A same-binary Proton off/on/on/off comparison with detailed tracing disabled
measured controls of 5.301/5.457s and the checked adapter at
1.925/1.961s. All four complete the same nine scenes and reach
character selection. An earlier private copy-only cause probe is retained as
nonshipping evidence; the delivered implementation uses the SDK boundary.

| Final build check | Confirmation to character selection |
|---|---:|
| Windows USA, adapter disabled | 3.078 seconds |
| Windows USA, normal Play | 1.594 seconds |
| Windows PAL, normal Play | 1.734 seconds |
| Windows JP, normal Play | 1.625 seconds |
| GE-Proton USA, normal Play 1 | 1.998 seconds |
| GE-Proton USA, normal Play 2 | 2.044 seconds |

The native adapter validates the region-qualified SDK manager, idle bus and
queues, waiting PI thread, descriptor, arguments, bounds and memory aliasing
before writing anything. It preserves descriptor fields/status and enqueues the
actual `OSIoMesg` pointer. The original `romCopy` and subsequent `osRecvMesg`
still execute, including chunking, cache invalidation and regional behavior.
Busy/queued/unsupported calls and save-device operations fall back unchanged.
No scene jump, skipped initialization, thread-transport replacement or shortened
input hold is introduced. This is SDK-level native behavior, not a claim of
identical internal PI registers or OS scheduling in elapsed-time Play.

Unit checks compare payload bytes to the existing PI transfer model and cover
descriptor/status fields, completion consumption and mutation-free fallback.
Fresh USA/PAL/JP generation validates original SDK bodies and manager bindings.
The normal Play replays, instruction-timed and recorded-clock comparisons, and
save-load qualification are retained in the private guarded manifest. Historical
checks below do not automatically qualify this candidate.

Ordinary Play enables the checked path. `JFG_DIAGNOSTIC_NATIVE_ROM_API=0` is the
private control; instruction/recorded observers keep their existing paths.
An ordinary support log records `assets=native-rom-api-active` on first use and
the existing bounded cutscene milestones. No detailed tracing is needed for
the owner retest. Original video FPS is not synonymous with instruction timing;
see the separate simulation-parity issue.

Source: [adapter](../../../include/jfg/boot/native_rom_dma.hpp),
[SDK integration](../../../src/boot/native/guest_execution.cpp),
[policy](../../../src/boot/native_boot.cpp), and
[regressions](../../../tests/runtime/native_rom_dma_tests.cpp).
[Qualification identities and timings](../../../evidence/cutscene-skip-native-rom.json).
The remaining scene initialization/decompression/rendering time is real work;
this is not an instantaneous-skip guarantee. Local software Vulkan results are
not RTX4070 measurements. Owner visual/audio/latency acceptance remains pending.
No commit, push, GitHub closure or release is claimed.

Transferable lessons: measure all participating guest threads, distinguish bus
delay from transfer-protocol cost, verify SDK queue layout against original
source, and confirm observed savings with profiling disabled. Synthetic tests
alone do not establish real request admission; all three live regional checks
must show activation and correct progression. Private evidence:
`gh41-root-cause-20261107`, including all failed attempts and earlier probe builds.


## Earlier diagnostic-only checkpoint — November 7

Status: **open skip latency issue**. The owner reports 5–15 seconds after the
indicator completes and confirms the same behavior with logging disabled.
Logging is not the explanation. No speed fix, owner acceptance or release is
claimed by this investigation.

| Measurement | Confirmation to character selection |
|---|---:|
| USA Windows baseline, detailed trace | 3.415 seconds |
| USA GE-Proton11-11 baseline, software Vulkan, Proton logging off | 6.618 seconds |
| Updated USA normal Play, Windows, detailed trace off | 3.250 seconds |
| Updated USA normal Play, GE-Proton, detailed trace off | 5.447 seconds |

All four complete the same nine internal scenes from one hold and reach room127.
The trace baselines begin completion within 0.4ms of confirmation. The existing
10/30-to-1 outgoing fade shortening activates for the eight chained departures;
the remaining interval accumulates through native scene loading/initialization
and the final handoff. Eight measured Windows transition calls account for
2.693s in a separate profiled replay; measured recipient wake latency accounts
for 0.253s within those calls. Do not mislabel inclusive parked-thread time as
thread-switch overhead. The Proton function profiler marks all 1,363 root
samples invalid, so its zero cost fields cannot attribute a Proton CPU cause.
The memory-buffered profile is flushed at shutdown; its observer saw zero
on-disk completions during the run, but the final trace contains all nine.

The local Proton result reproduces a delay within the owner's reported range.
It uses software Vulkan, so it does not establish RTX4070 performance, exact
visual behavior or a complete platform-specific cause. Skipping full native
loads or replacing the chain with a direct character-selection jump has not
been justified by these results; native script effects, actor initialization,
cleanup, readiness and audio transitions remain intact.

### Corrected evidence capture

The old `cutscene=explicit-completion level=... group=...` message contains
spaces. The support logger's restricted alphabet rejects the entire message,
which explains why the received ordinary logs lacked completion milestones.
The updated USA runtime uses valid bounded records for request, each completed
segment, arrival, unsupported handoff and timeout. Elapsed milliseconds are
relative to the confirmed request. `next` is the planned chain destination
(conditional terminal commands have no literal planned destination); the
settled record's `level` is the actual arrival room. No private guest pointers,
ROM bytes, save data or personal paths are included in these milestones.

The regression suite passes **8,816 checks**, including actual support-file
writes and worst-case formatting limits. Windows and actual GE-Proton normal
Play retain exactly 11 milestones with gameplay tracing and Proton logging off,
then close cleanly. This verifies the logging repair, not a speed improvement;
the timing differences between runs are not credited as a fix.

Candidate USA runtime SHA-256:
`fac569636f648f7d6cc1052d3c627697cc65c8c452926514be298ca18c7116cb`.
Source files: [diagnostic formatting](../../../include/jfg/runtime/cutscene_skip_diagnostics.hpp),
[input confirmation](../../../src/boot/native/controller_input.cpp),
[completion/handoff reporting](../../../src/boot/native/guest_execution.cpp), and
[regression checks](../../../tests/runtime/cutscene_skip_tests.cpp).
No commit exists for this change yet. PAL/JP runtime binaries are unchanged.

A separate [Vulkan screenshot-readback defect](vulkan-diagnostic-frame-readback.md)
was reproduced and explained from matching symbols/source. The no-screenshot
Proton runs pass; that does not fix or qualify optional Vulkan screenshot capture.

Private evidence: `gh41-opening-skip-20261107`, including preserved owner archive
and full Proton log, `opening-review.json`, normal-support verification records,
all failed/inconclusive attempts, and the guarded manifest. The production guard
remains enabled, with the same investigation/root and all earlier counters.
Automated runs used a private muted configuration. Underrun counts were retained
as observations; no broad audio remediation was pursued.

The USB updater is prepared to replace only the USA executable/manifest alongside
existing launcher/document updates, with old files backed up and saves/settings/
ROMs/PAL/JP preserved. It is checked using paths with spaces, repeated updates,
archive retention and symlink rejection before any replacement. The next owner
capture can use normal Play and the existing collector; no video or large Proton
log is required. USB delivery is recorded separately after copy verification.

## Historical evidence and transfer history

## November 7 Bazzite opening-cutscene report

### Returned archive and owner feedback

The owner subsequently reports that everything looks good except cutscene skips
taking an unusually long time. The skip report remains open; this is not a new
runtime fix or a measured skip-duration result.

A read-only receipt check found one owner archive on E:,
`results/results-20261107T091458423237Z.tar.gz` in the issue #40 bundle. It contains
24 collected files plus system and inventory metadata. Its system record identifies
Bazzite 44, Wayland and RTX 4070; the two launcher/native reports identify USA
sessions at 07:24 and 07:33 UTC, both ending with exit code zero.

The collected installation identifies launcher SHA-256
`a2911b7e48caba0620bd863d2d657d3d79491e9735afefc8da0dc2173cf63101`,
the original USB build. The current E: launcher is
`e35e776913be966a24030eef45043ebb241ec4a0466c05beff5d86ae440fd219`.
This archive may be the updater's pre-update collection; it does not establish
which build the owner's latest feedback describes. The included manual-results
form still says not tested. Do not override the owner's report with that stale
form or treat the archive timestamp as the gameplay timestamp.

The collector retained only the final 32 MiB of the 2,934,644,272-byte Proton log
and explicitly marked it truncated. No detailed gameplay trace or About timing
log is listed. These receipts do not measure skip completion or establish its
cause. Collect again after the latest run from the actual installed test folder,
using the USB collector's `--root` and `--copy-to` options. Preserve the original
Linux logs and this archive. No experiment, replay or code change was performed;
the production guard remains enabled and the previous three-attempt continuation
is exhausted. Further autonomous investigation requires a new bounded admission.

Second receipt check: the owner returned
`results-20261107T094900521513Z.tar.gz` at the USB bundle root. The 4,278-byte
archive opens successfully but contains only `system.json`, `log-inventory.json`,
`verification.txt` and the blank USB `test-results.md`. Its inventory explicitly
lists two collected files and no launcher, native, Proton or gameplay logs.
System metadata now matches the latest `e35e7769...` launcher and the owner's
Bazzite/RTX 4070 environment. This proves which executable the collector hashed,
not which executable was played. The archive location and contents are consistent
with collecting the USB bundle rather than the installed game directory; that is
an inference, not an observed collector command. Requested the current Steam
Target and Launch Options to identify the correct log location. Latest-run logs
and the skip-delay cause remain unconfirmed. Original archives were left intact.

The owner confirms they used the handoff configuration. The original archive's
`steam-shortcut-settings.txt` recovers the expected installed Target and Proton
log directory under `$HOME/Games/JFG-Issue40-20261107`; no further path lookup by
the owner is needed. Updated the USB's `collect-logs-command.txt` to enter that
installed folder explicitly in a subshell, then invoke the USB collector with
an explicit installed root and absolute USB results destination. This is a
collection instruction only, not an executed Linux collection or runtime change.

Status: open owner follow-up; no new runtime fix or acceptance. On the private
issue #40 Bazzite x64 / RTX 4070 bundle (v33 runtime, launcher 067f9a8), the owner
reports that skipping continues the scene briefly or holds a frame while music
continues before ending. They clarified that this was the opening cutscene.
The exact shot, region, measured hold-to-completion interval and installed Proton
version have not been recovered from logs. The supplied ROM/default was USA;
that is not independent proof of the actual active profile.

The owner followed the handoff, but E: contains no collected owner archive as of
this review. Logs may remain in the Linux installation. Ordinary Proton logging
is not a gameplay trace: the original handoff did not enable `--diagnostics`.
The revised USB updater collects the existing logs before replacing the launcher.

The October 27 timing comparison below covers flight/rescue routes, not opening
Invasion. It cannot establish this report fixed. Native loading/readiness and
script/audio completion are still required; continuing music alone does not
identify the blocking stage. Review the owner's collected evidence, then time a
short opening-only diagnostic capture if ordinary logs are insufficient. Keep
skip pacing separate from the new [audible opening glitch](opening-invasion-audio-proton.md).
No scene commands, fades, audio cleanup or progression were changed in this UI work.


- Severity: pacing / responsiveness improvement.
- Status: local candidate; three native routes complete; owner batch review pending.
- Reported (UTC): 2026-10-21.
- Affected build: v1.4.0 release candidate, source `ea9845e`.
- Report: [GitHub #41](https://github.com/TK22-26/JetForceGemini-Recomp/issues/41).
- Related: [native cutscene skipping](optional-cutscene-skipping.md) and
  [owner scene review](cutscene-owner-retest-20261020.md).

## Symptoms and reproduction

During the final candidate pass, the owner requested that some cutscenes finish
skipping faster. The specific slow scenes and per-scene delays have not yet been
measured. Measure from acceptance of the one-second hold to gameplay or the
intended next scene; the confirmation hold itself is a separate interaction.

## Evidence and hypotheses

This is an owner-reported follow-up, not a demonstrated new correctness failure.
The current skip preserves native progression and completion behavior. The cause
of the remaining delay is unproved; scene completion work must be measured before
changing scheduling or bypassing commands.

## Attempts and results

2026-10-21: owner explicitly requested a GitHub issue; #41 created. No skip code
changed and no speed improvement claimed. This request does not itself block
the owner's v1.4 final pass.

## Verification and remaining limits

Identify affected scenes and measure before/after completion times. Include
multi-segment sequences and compare story progression, actors, room transitions
and audio with normal completion. One accepted skip should finish the intended
sequence without a black screen or a second hold for an internal segment.
Verify with normal release launch settings, diagnostics and FPS logging off.

## Lessons

Optimizing skip latency must preserve native completion semantics. A faster
transition with lost progression, incomplete audio cleanup or an invalid next
room is not an acceptable optimization.

## October 27 measured transition delay

A bounded normal Play run entered 97/0 through the diagnostic selector and held A. Native completion occurred at 60.724399 seconds, followed by 101/0 completion at 61.444288 and 102/0 completion at 61.860844, then gameplay room35. The same capture also completed 135/0 to158 and 93/0 to92. Each internal scene's completion handler ran once; there was no extra confirmation hold. Times are trace elapsed time, not a production performance benchmark.

Source review found mainChangeLevel writes a 10- or 30-tick presentation delay to 800A3294, and the native level-transition routine subtracts normal update ticks before checking its video-readiness gate and running cleanup/loading. The existing skip already covers transitions with a black native overlay. A candidate can shorten only that presentation wait after a qualified explicit completion, retaining the ordinary readiness gate, loader, script side effects and first update in each internal scene. This is a hypothesis under validation, not yet a verified speed fix.

Private evidence: remaining-gh-issues-20261027/cutscene-timing-030 and native mainChangeLevel/transition source observations. Native scene state and saves remain private. No GitHub action.

### Candidate scope

After an accepted, qualified explicit completion schedules its known destination, the candidate shortens a newly installed 10/30-tick outgoing fade countdown to one tick. It validates the pending level/group, absence of cue/confirmation waits, and the exact native countdown/readiness instructions. Credits, ordinary room transitions, unqualified scenes and unrelated waits are unchanged. The native transition routine still waits for video readiness and runs cleanup, loading and destination fade-in; it is not called early or bypassed. Native source at 80047480 explicitly replaces the outgoing fade with the destination fade after loading. Paired route timing and state comparisons remain pending.

## October 27 validation update

Three normal-Play routes completed with the same explicit completion sequence and destination as the baseline: 97→101→102→35, 135→158, and 93→92. The interval from first to third completion in the flight chain was 1.136445 seconds before and 0.551965 seconds after. This excludes the player's hold time and does not claim loading takes zero time. Native readiness/loading checks remain. Both paired runs exited cleanly. Private evidence: cutscene-timing-030 and cutscene-timing-040. Final owner batch review remains pending.


## Runnable USB collection entrypoint

At the owner's explicit request, `E:/collect-jfg-logs.sh` now locates the USB
bundle relative to its own filename and defaults to the handoff installation
under `$HOME/Games/JFG-Issue40-20261107`. It refuses a missing installation, the
USB bundle as the source, a running game/launcher, and absent or empty run logs.
It invokes the existing bounded collector with explicit source/destination paths,
keeps terminal status visible, and leaves existing archives and original data.
The original collector's no-argument default remains unchanged; this wrapper
avoids that documentation-only collection trap for the owner's no-argument run.

Isolated WSL checks pass: shell syntax, missing source, wrong USB source, absent
logs, empty logs, collection from an unrelated working directory with spaces in
paths, and a second collection retaining the first. Archive contents include the
fixture run log and exclude ROM/save/binary sentinels; original inputs survive.
This verifies packaging, not the owner's latest Bazzite session or skip timing.
The .sh uses LF and no BOM. On an exFAT/noexec mount, Run in Konsole or `bash`
can interpret it without requiring persistent executable permissions.

Private evidence: `gh40-collect-wrapper-20261107`. One scoped worker was admitted
for this new explicit artifact request within existing ledger limits. Guard,
root, limits and prior counters were preserved; the expired UI continuation was
not renewed. No game run, runtime edit, commit, publication or remote connection.

### Returned wrapper run: empty USB file

The next returned USB contains
`results/results-20261107T100146873094Z.tar.gz`, but its file length is zero and
opening it returns EOF immediately. It cannot establish any session, installed
build or skip timing. Windows reports the exFAT volume's health as Warning with
29,504,438,272 bytes free. Insufficient capacity is not indicated; the volume
warning does not by itself diagnose media failure or the empty-file cause.

Asked whether the collector reached Done and whether the USB was safely ejected.
An interrupted copy or pending removable-drive writes are hypotheses only.
The underlying collector closes the destination and compares its hash, but does
not explicitly fsync the USB file or its directory. A cached readback hash is not
proof of persistence after removal; the isolated fixture checks did not cover
removable-media durability. The live transfer remains unverified. Original Linux
logs/local archives should be retained; no filesystem repair, deletion, runtime
investigation or new guarded job was performed during this read-only receipt check.

The owner then explicitly confirms the wrapper reported Done and found seven
logs in a new capture. At 10:09 UTC, a fresh read of E: still shows only the
09:14 archive and the same zero-byte 10:01 archive in `results/`; no newer
archive exists elsewhere on the USB. The script hash matches the delivered
wrapper. Preserve the owner's reported completion as evidence, while noting
that the latest archive has not become visible on this Windows drive. Asked
specifically about safe ejection and reconnection; those steps are not yet
confirmed. Do not claim seven logs were received or diagnose the transfer cause.

The owner confirms safe ejection. A subsequent read-only Windows check still
finds the same zero-byte archive. `fsutil dirty query E:` reports Dirty;
`Get-Volume` reports exFAT HealthStatus Warning and OperationalStatus
Full Repair Needed. The underlying USB disk reports Online/Healthy and is not
read-only. These are volume-state observations, not proof of hardware failure,
unsafe removal or the specific reason the archive is missing. Do not attribute
the failure to the owner ignoring ejection instructions.

The collector code creates and closes a local `results-*.tar.gz` under the
installed Bazzite folder before attempting the USB copy. Given the owner's Done
report, retrieve that existing local archive directly from Bazzite (or through
another transfer medium) instead of asking for another game run or repeating
the same USB route. Local archive existence/integrity remains remotely
unverified. No filesystem repair or additional write to E: was performed.

### Manual transfer succeeded: current logs received

The owner manually copied the installed folder to `E:/JFG-Issue40-20261107`.
Its newest archive, `results-20261107T100733764015Z.tar.gz`, is 1,129,038 bytes;
a complete gzip read passes CRC validation and the tar contains 38 files:
36 collected files plus system and inventory metadata. The seven nonempty core
run logs are three launcher/native pairs and one Proton log. A newer USA session
started at 09:17:40 UTC and closed normally with exit code zero. The collected
installation identifies the latest launcher `e35e7769...`; Bazzite/Wayland and
RTX 4070 metadata match the owner's machine. About timing/presentation logs are
also present. Earlier build-only and empty-archive limitations no longer block
receipt of the current logs.

A byte-identical private copy is retained under
`D:/JFG-private/gh40-owner-logs-20261107/`. Archive SHA-256:
`e781077e1ed2e0bf08a40775f22f1302efb69a425825d940512514d7e94eeb9d`.
The Proton entry retains the last 32 MiB of a 4,929,564,511-byte original and is
marked truncated; no detailed gameplay trace is listed. Successful collection,
normal process exit and positive owner UI feedback do not establish the cause
or duration of the slow skips. No new game run or runtime fix was performed.


## November 7 authorized opening-skip investigation

Owner approved two hours after successful log transfer. The existing production
guard remains enabled on the same investigation, with prior counters retained;
the continuation covers focused opening-skip evidence and checks. Preserve the
complete returned Proton log privately before analyzing it. Automated sessions
use a private muted audio configuration, and no owner save/profile is edited.
Initial questions: whether the delay follows accepted input, script advancement,
audio/cue waits, transition readiness/loading, or diagnostic overhead. The prior
flight/rescue timing tests do not qualify the opening sequence. No cause or fix
is established yet. Private evidence: `gh41-opening-skip-20261107`.

Owner correction: the same bad opening skip also occurs with logging disabled.
Logging does not explain the reported defect; no logging-based remedy is being
pursued. The full Proton log was retained and scanned, but it lacks precise
skip-completion timings. Initial isolated replay launch rejected an unsupported
`JFG_GAMEPLAY_TRACE_MEMORY=0` setting before gameplay (exit 3); omit that opt-in
variable for the corrected measurement. This is a harness configuration failure,
not a game skip result.

### Measured opening route and ordinary-log defect

Owner estimates 5–15 seconds after the skip indicator finishes, also with
logging disabled. A fresh USA Windows normal-Play replay accepted the request
at 66.531816s, began completion 0.246ms later, completed nine internal scenes by
69.524678s and reached character selection (room127) at 69.946713s: about3.415s
from confirmation. One hold completed the chain; no continuation hold or timeout
occurred. Trace cover state remained set across the internal scenes. This does
not reproduce or dismiss the longer owner-observed Bazzite delay.

Source review found the existing ordinary completion message contained spaces,
but support_event rejects every event containing spaces. Consequently normal
native.log silently omitted these messages. Candidate diagnostics use the
existing bounded support stream's permitted alphabet and record request,
per-segment elapsed wall time, final handoff, unsupported resume and timeout.
They do not need gameplay tracing or PROTON_LOG. Skip semantics are unchanged;
this is an evidence-capture correction, not a latency fix. Tests must verify
actual support-log writes as well as formatting and size limits.

The local GE-Proton11-11/software-rendering baseline exited with a native fault
at VI187/poll67, before any skip. The owner's RTX4070 session exited normally;
this fixture failure is not the owner's skip symptom. Its private fault capture
is retained, and one ordinary-window run distinguishes the hidden-window setup
before further Proton timing claims. No broad renderer investigation is opened.

The first diagnostics build caught an include-order error: placing the new
support header before existing pure game headers exposed Windows' `near` macro
to a local variable. The include is moved beside the existing support header;
no navigation code is changed. The initial formatter/writer regression suite
passed 8,816 checks. Full build and gameplay verification remain required.

Both Proton fixture failures resolve through symbols to CaptureContext::draw
and VulkanCommandList::copyTextureRegion, before the opening scene. The pinned
Vulkan implementation handles buffer-to-image and image-to-image copies but
has no image-to-readback-buffer branch; the screenshot probe reaches its image
branch with a null destination texture. A run without optional frame readback
will test whether normal Play reaches the opening sequence. This is separate
from the owner's skip defect and is not evidence against logging-disabled skips.

USB delivery: the updated USA executable/manifest, tested updater, handoff and
compact evidence were copied into the existing issue40 test bundle. All 123
manifest entries and the installed program identity verify. Replaced bytes are
retained under previous-build/opening-skip-timing; the returned owner logs and
archives were untouched. The desktop issue log and root USB handoff are updated.
No commit, push, GitHub action or released resolution.

## 2026-11-07 owner continuation: root-cause attribution

Owner authorized eight further hours to find the actual cause. The existing
production investigation and all counters are preserved. Slow skips without
logging remain the target; no logging change is considered a latency fix.
The prior Proton full-function profile invalidated wall-clock samples whenever
CPU cycle sampling was unavailable. Independent wall validity is being added
and tested before using that evidence to attribute scene-loading time.
Status: investigation in progress; no speed fix or owner approval claimed.

The first repaired Proton profile records 8,060 ROM DMA transfers for 4,913,256
bytes during opening completion. The game-thread dispatch scopes include
3.324 seconds parked while other guest threads execute; measured recipient
wake time across eight load roots is about one second. These overlap and are
not pure CPU cost. Unprofiled direct-register controls measure 5.601/5.757s,
versus 5.231/5.019s with the existing SP/MI diagnostic variants. This does not
explain the whole delay. A fiber transport probe measures 3.731s, still pending
repeat and compatibility checks. Neither optimization is selected by default.
The detailed MMIO probe itself materially changes timing (14.131s control),
so it is not used as an ordinary-play benchmark. The analysis initially
rejected repeated audio roots sharing VI/poll/thread identity; the corrected
review checks their combined additive wall totals and preserves that failure.
A bounded all-guest-stack profile is next to distinguish ROM-manager execution
from actual thread wake latency. No speed fix is claimed yet.

The isolated USA cause probe reduces an unprofiled Proton skip from 5.143s
to 2.123s while completing the same nine scene transitions. It bypasses the
ROM-copy protocol only during the confirmed skip and is explicitly **not a
deliverable implementation**: the original OS descriptor/queue effects have
not been qualified. Its source was restored after freezing the private binary.
The first probe build failed on CRLF translation before gameplay; a digest-checked
restoration and corrected build preserve that failed attempt. This experiment
isolates cartridge-transfer emulation overhead from the required scene work.
The proposed production direction is a checked native immutable-ROM API path,
preserving I/O descriptors and completion messages, with original fallback for
busy/queued transfers, save devices, instruction/recorded timing and unsupported
states. Regional ABI/identity and compatibility checks are still required.

Source qualification caught a candidate fixture error before runtime testing: `OSMesgQueue.mtqueue` at offset 0 holds blocked receivers; `fullqueue` at offset 4 holds blocked senders. The initial adapter and synthetic fixture transposed these names, which would safely decline real transfers. Corrected both against the original `osRecvMesg`/`osSendMesg` source, including the blocked PI thread queue pointer. Unit success alone was insufficient to establish that real guest requests would be admitted; live activation remains required.

The checked adapter completes all nine opening scenes on USA/PAL/JP, with live admission and correct character-selection captures. The initial JP reference fixture selected a nonexistent `jfg-jp-r0` folder instead of the catalog identity `star-twins-jp-r0`; it failed before launching that comparison. USA/PAL reference comparisons had already passed. The corrected JP test derives its directory from the actual program manifest and completes the remaining check. Dependent steps rejected the failed prerequisite without promoting or delivering the candidate; all failures and guard counters remain preserved.

Final default verification: the second Proton repeat failed in pressure-vessel before launching the game because the private 8 GiB test image was full. The image was unmounted, preserved byte-for-byte, checked offline and grown to 16 GiB without deleting evidence or touching the USB filesystem. A new labeled repeat completes all nine scenes; the failed startup remains in the guarded manifest and is not a game performance sample.

Packaging check: the repository hygiene gate rejected the summary field name `rom_bytes`, reserved for private payloads, before any USB mutation. Its value was only the integer transfer count in bytes (4,913,256), with no ROM body. Renamed it to `rom_byte_count`, retained the failed-check evidence, and kept the hygiene rule unchanged. This metadata correction does not change runtime identity or updater behavior.

USB delivery verified: all three final native runtimes, updater, handoff and compact evidence are in the existing issue40 test bundle. All 124 pinned package files and three program identities verify. Previous bytes are backed up under `previous-build/native-rom-api-*`; existing saves/settings/ROMs and returned owner logs were preserved. Root USB handoff and desktop review are updated. Owner Bazzite acceptance remains pending; no commit/push/release or GitHub closure.

Owner timing now corroborated by the supplied 18:47 UTC USA session: the delivered native-ROM executable completes all nine opening scenes in **1.828 seconds** from confirmation to character selection on Bazzite/RTX4070. Two later skips in that session complete in 453 and 546 ms; their level chains are retained privately. This supplements the earlier owner acceptance without inferring other-region manual tests.
