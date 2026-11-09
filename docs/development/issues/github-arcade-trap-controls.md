# GH-050: [Playtest] With Modern Controls can't use trap items in Jeff's Arcade race

Status: fixed in the local develop working tree; owner manually tested and approved USA, PAL and JP on November 8. Uncommitted and unreleased.

Source: [[Playtest] With Modern Controls can't use trap items in Jeff's Arcade race](https://github.com/TK22-26/JetForceGemini-Recomp/issues/50). Evidence snapshot retained privately in D:/JFG-private/remaining-gh-issues-20261027/github-issues.json.

## Reported symptoms and reproduction

### Problem type

Controls

### Launcher and game build

1.4.0 Release build

### Windows version, GPU, and input device

Windows 10, GTX 1080, XBOX Controller

### What happened and how to reproduce it

With modern controls it is not possible to use trap items in the Jeff's Arcade Race from the nightclub, but it is possible to use the boost.

### How often does it happen?

Every attempt

### Support ZIP and additional details

_No response_

## Scope and evidence

Local owner-authorized batch: trace native item input in arcade racing. Preserve existing approved fixes, user profiles and ROMs. No GitHub posting or issue changes. A reported symptom is not yet a confirmed cause. Attempts, results, final remedy and verification limits will be recorded here.

## October 27 local candidate

Native racing uses its own A boost / Z trap inputs. Racing did not have a Modern action context and fell into menu mapping, admitting A but dropping Fire. Candidate routes validated racing sessions through native boost/trap controls and preserves the racing camera; it does not enable character locomotion or aim adapters. Stale multiplayer type outside multiplayer does not select racing.

Status: implementation candidate; component and native verification pending.

Verification: Modern controller/mouse mapping checks; both memory layouts and stale multiplayer/pause/port exclusion checks; Release native build passes. Owner live batch review pending; unreleased.

## October 27 validation update

A private fixture executes the actual native hovershipControl, race input helper and sprintPlayerFire routines with isolated physics/audio/world-spawn dependencies. Across 96 cases, all four player slots and both compiled timing-span modes, configured Fire creates the appropriate native trap (0x278/0x279) and consumes the held item. No input/no item do not spawn; the formerly suppressed menu mapping does not fire. This validates input through native item consumption, not the full physical race. The first fixture omitted the fixed module's 80000400 relocation base and failed before reaching the native Fire branch; correcting that fixture setup passed. Private evidence: native-race/result-042.json. Owner batch review remains pending.

## November 8 owner test preparation

Prepared a private USA desktop shortcut using the existing November 7 launcher/runtime,
with Modern controls and an isolated copy of a populated save. The shortcut passes
ordinary title, save and character menus, then restores the copied controller
selection. A muted Windows qualification reached the Arcade room in about 33
seconds, in Arcade as Vela; entering the cabinet is a separate interaction. The public issue's remaining
acceptance is the race itself: collect a trap, deploy it with configured Fire,
verify item consumption, and check boost, steering and pause. Owner acceptance
is still pending; neither room entry nor the earlier 96-case fixture establishes
full live-race acceptance.

The test slot's three character checkpoints target the arcade. An initial check
patched only Juno's checkpoints; ordinary character selection chose Vela and
correctly loaded her previous room instead. Preparing all three checkpoints in
this private slot resolved that test-setup mismatch. A first launcher-helper check
also combined diagnostic recording with a separate progress-output argument;
the launcher rejected the duplicate stream as designed. The final helper uses
only the progress stream and completed normal entry. These were preparation
failures, not new game regressions.

The desktop link is `JFG - Test Issue 50 (Arcade).lnk`. Its private directory is
`D:/JFG-previews/issue50-arcade-20261108`; evidence and production-guard receipts
are in `D:/JFG-private/issue50-desktop-test-20261108`. Each launch resets only
this dedicated test save. Source saves, other copied slots, ordinary controller
settings and manual audio preferences were preserved. No input replay remains
active during owner testing. ROM/save data and screenshots remain private.

Compatibility lesson: per-character resume checkpoints must be prepared for the
character that the normal save-load flow actually selects. A valid save checksum
and a successful boot alone do not verify the intended room or playable input.

## November 8 owner race result: oil still does not deploy

The owner reports: "launcher worked - fire didnt place the oil" after using the
dedicated desktop test and receiving the Modern Fire / right-trigger instructions.
The shortcut is accepted as usable; the controls fix failed this live test. The
prepared profile is USA with Modern controls enabled, `pad.fire=25` (right trigger),
and automatic controller selection restored to `device=-1`. The reported symptom
is oil deployment; other trap types, item consumption, boost and pause were not
separately confirmed by this reply. Gameplay impact remains that an arcade race
item cannot be used through the requested action.

The manual launch retained a startup/progress stream, not a full controller and
race-state capture. Its final snapshot does not establish which input reached the
race handler or why deployment failed. The runtime SHA-256 is
`d2af03c8ca6de568aff2c1e01d188e05c4fdd004ab26e472c62eb3558831c282`.
The existing fixture isolates physics, audio and world spawning and therefore
does not qualify live context selection, physical input delivery or the arcade
race's item state. Those are investigation targets, not established causes.

At this failed-test checkpoint, next verification needed to cover the actual arcade route, Modern physical Fire,
race-context selection, held item and the native deployment call together, with
Original controls as a comparison where useful. No replacement fix or cause is
claimed at that checkpoint. The production guard remained enabled; its prior setup job was complete
and its attempt/activity allowance was exhausted (146/146 and 122/122). Further
runtime investigation required a newly authorized bounded continuation with the
same investigation, roots and existing counters preserved.

## November 8 live cause and corrected candidate

The owner approved a two-hour, three-attempt continuation. The production guard
kept the same investigation, roots and counters. The actual arcade race (USA
level 258) sets a static overview camera throughout playable racing. The former
`pc_race_gameplay_active` rejected that camera as scripted; the controller sampler
also unconditionally classified static-camera scenes as menu input. Modern Fire
was therefore dropped before the native race handler. The baseline retained 237
race polls, all with a zero button mask despite host Fire presses. Its captured
RDRAM rejected all four valid racers for the same reason.

A first candidate corrected those camera checks but still delivered zero Fire
polls in a complete live race (1,062 captured race polls). This exposed the second
blocker: [original_modules.hpp](../../../include/jfg/game/original_modules.hpp)
defined `OriginalModule::racing` as 30, the old generated section ordinal. The
actual original runlink module slot is 31; slot 30 was absent during the captured
race. Consequently the active-overlay check never selected racing. Correcting
the semantic module ID to 31 resolves the active section through each regional
descriptor, rather than assuming a generated ordinal.

The correction in [navigation_mod.hpp](../../../include/jfg/mod/navigation_mod.hpp)
recognizes an owned, playable race independently of its fixed camera. Pause,
cinematic mode, controller disable, scripted movement and port ownership checks
remain required. [controller_input.cpp](../../../src/boot/native/controller_input.cpp)
uses that qualified context for race action mapping and mouse action ownership.
Fire still maps to native Z; the native overview camera and ordinary character
camera exclusions remain intact. This also prevents mouse Fire from being denied
by the separate general scripted-camera check.

Validation under the guarded worker, with automated audio muted:

- A regression with the real static-camera condition fails on the old code and
  passes with the correction. The 154 context checks, 231 Modern controls checks
  and navigation suite pass. Coverage includes four ports, both memory layouts,
  cinematic/controller/scripted locks, ordinary static-camera exclusion and
  multiplayer race selection.
- The descriptor suite now includes the real original racing slot, an adjacent
  slot-30 decoy and reordered generated sections for each supported ROM. It fails
  the old module ID and passes the correction. This covers module ownership as
  well as the earlier context checks.
- A normal USA title/save/cabinet route using actual host keyboard events reaches
  the race. 198 of 1060 captured race polls deliver native Z.
  This is not an input replay; it exercises the runtime context and host mapping.
- The final full-game item fixture seeds only held oil, then uses normal host
  Fire. Oil remained held both without input and after Fire; no new world actor
  was observed. This check FAILED and does not establish working oil deployment.
  Whether this is a remaining runtime defect or a fixture/player-selection issue
  is unconfirmed. The owner requested that automated investigation stop so they
  can test the candidate directly. No further gameplay runs were made after that
  request. Natural pickup and physical controller deployment remain pending.
- USA, PAL and JP Release runtimes build and pass identity/package validation;
  the complete portable package resolves all three regions. USA launcher entry
  reaches Arcade and restores the copied controller selection. PAL/JP live races
  and the owner's physical-controller retest remain pending.

Informative setup failures are retained: two initial cabinet attempts lacked
tokens and never entered the race. Adding tokens only to the isolated test save
enabled entry. Later candidate captures stopped at the room entrance or just
outside the cabinet trigger; those runs did not qualify race input. An explicit
normal-keyboard approach inside the native 32-unit trigger and actual mouse-look
alignment to the cabinet facing requirement corrected this test setup. The first
private item observer also assumed an 8 MiB mapping; this game uses 4 MiB. It
failed before any item write; deriving the mapping size from the real capture
corrected that fixture. The item observer also initially selected the native
process supervisor rather than its game child; selecting the actual game window
PID corrected its target. Both observer failures occurred before item writes. Standalone observer/test compilation initially omitted the
generated catalog, descriptor/binding objects, then input-stick linkage; those
harness omissions were corrected before reporting passes. Earlier 96-case native
handler tests did not contain the playable static-camera state and missed the
host context defect. The new regression preserves that condition explicitly.

The existing desktop shortcut now targets
`D:/JFG-previews/issue50-arcade-fixed-20261108`, with the corrected regional
runtimes and ten tokens per character in the dedicated test slot. The prior
preview and failed owner capture are preserved. The original save hash and
copied controller restoration were checked. Private evidence, source snapshots,
red/green results and guard receipts are in
`D:/JFG-private/issue50-live-race-20261108`. No ROMs, generated native code or
personal saves are added to the repository.

Remaining acceptance: collect oil naturally, deploy with configured controller
Fire/RT, then check other traps, boost, steering and pause. The candidate is in
the develop working tree, uncommitted and unreleased. The prior owner failure is
not superseded by owner approval until the new build is retested.

Transferable lesson: camera ownership and action ownership are distinct. A fixed
camera can accompany playable vehicle controls. Context tests must preserve the
real scene's camera flags. Original runlink IDs must resolve through descriptors,
not copy generated section ordinals. Mapped-action tests alone cannot establish host
input delivery through the full game's context selection.

## November 8 USA owner acceptance and regional test saves

The owner reports: "checked and works on USA" and requests PAL and JP saves for
the same room, adding "I will test." USA gameplay acceptance now applies to the
corrected candidate delivered by the desktop arcade shortcut (runtime SHA-256
`e4472949a643fea162efde1663e3faaa7e48c671334413ea7cd4e2b9df254ae4`).
This does not imply PAL/JP acceptance or individually establish every other race
action/device combination. The earlier failed controlled oil fixture remains
historical evidence; its failure has not been explained or relabeled as a pass.

Prepared separate PAL and JP slot-1 saves from previously validated saves of
their own revisions, with all three character checkpoints set to Arcade (375)
and ten tokens per character. File length, checksum, untouched other slots,
revision markers, ROM identity and regional runtime identity were checked.
Each regional shortcut selects its matching ROM and resets only its dedicated
test save before normal menu entry. The existing USA shortcut/save is unchanged.
Current copied controller and manual audio preferences are preserved.

Desktop links: `JFG - Test Issue 50 - PAL (Arcade).lnk` and
`JFG - Test Issue 50 - JP (Arcade).lnk`. Their private directories are
`D:/JFG-previews/issue50-arcade-pal-20261108` and
`D:/JFG-previews/issue50-arcade-jpn-20261108`; both use the same already-built
regional package as the accepted USA candidate. PAL and JP saves reside under
each profile's `revisions/<revision-id>/jfg.flash`, with the corresponding
`rom-revision.txt`; they are not USA saves with changed identity labels.

The owner will perform room-entry and race checks. No additional game sessions,
gameplay experiments or runtime builds were run during this preparation. The
first preparation stopped on an overly strict assumption that the accepted USA
test profile had no audio file; the owner now has manual audio preferences.
Preserving and copying those preferences corrected the preparation check.
Private receipts and that partial preparation are retained in
`D:/JFG-private/issue50-regional-saves-20261108`. The same enabled production
guard, investigation counters and remaining approval deadline were retained.

## November 8 final owner acceptance: USA, PAL and JP

After explicitly confirming USA worked and receiving separate PAL and JP arcade
test saves/shortcuts, the owner reports: "fix approved - manually tested and
approved." This completes owner acceptance for issue #50 across USA, PAL and JP
on the supplied corrected regional builds. The reported Modern-controls arcade
trap defect is considered fixed for this review.

The remedy is the original racing module ID correction (31 rather than 30) plus
race action eligibility that preserves the playable fixed camera. Automated
context/module regressions and live native-Z delivery remain the supporting
checks recorded above. The earlier controlled oil fixture failure is retained
as an unexplained limitation of that check; it is not retrospectively reported
as passing. Owner approval does not establish every trap/player/device or race
mode combination individually.

The desktop issue review, issue index, known-issues and controls notes now record
all three regional approvals. No additional game session, runtime change or
build was needed for this acceptance update. Commit, publication and GitHub
issue closure remain separate actions; none was performed here.
