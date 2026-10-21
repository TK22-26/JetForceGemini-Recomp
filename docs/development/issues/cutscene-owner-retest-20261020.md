# Cutscene owner retest - 2026-10-20 Eastern

> 2026-10-21: owner explicitly approved #31. Feature acceptance is complete; release is pending. Preserve the exact checked passes and eleven unchecked ?Debug Cutscene? annotations below; approval does not certify untested entries.

**Current scope:** all four targeted Juno fixes (376/0, 405/2, 207/0 and
335/0) are owner-confirmed. The 11 remaining unchecked entries are classified
as likely development/setup variants, with the limits documented below.
The type 145 source-rationale audit is complete; runtime behavior is unchanged.


Status: targeted owner retests complete; remaining entries classified for
reference. Earlier failures and pending-test statements below are chronological
history superseded by the later acceptance and classification sections.
No release or exhaustive campaign coverage is claimed.

Initial affected preview (historical): 1.3.1 development candidate, native runtime SHA-256
ca94e6b4c3437fa86086c7bc8e0009767144313c2eef0654ce020d8265ccd50d.
The Quarry atmosphere correction in this same binary is separately approved.
The owner uses the persistent scene selector and copied review profile.
Do not change that profile, executable or owner checklist during active review.

| Entry | Owner observation | Current status / evidence |
| --- | --- | --- |
| 045 / BigShip | No longer crashes, but does nothing | Validator deliberately blocks unsafe standalone entry. Crash prevention observed; safe entry and clear selector feedback unresolved. |
| 207 / 0 | Prompt appears; stops progressing after skip | High-severity skip completion/transition failure. Owner clarified earlier ?crashes? to ?it stops after.? Request trace identifies native character1/Juno. |
| 235 | Still crashes after playing; owner suspects unused | High-severity reported failure. Unused status, variant/character and exact exit mechanism remain unconfirmed. |
| 240 / 1 | Does not allow skip | Skip availability failure. Prompt behavior not specified; context-only/unclassified in previous source audit. |
| 271 / 2 | Still does nothing | No visible action reported. Exact failure stage and native context requirements not yet correlated. |
| 275 / 1 | Still does nothing | No visible action reported. Prior checklist also questioned whether it is a standalone cutscene; unused status is not established. |
| 308 / 1 | Does nothing; explicitly no freeze | No visible action. Do not classify as a crash or hang. Request/scene context still needs correlation. |
| 322 / 1 | Does nothing; explicitly no freeze | No visible action. Do not classify as a crash or hang. Request/scene context still needs correlation. |
| 335 / 1, Juno | Still cannot skip | Current persistent note updated2026-10-21T01:30:13Z identifies variant1/Juno. Prompt behavior not specified. Older335/0 ?cannot skip? note remains separately unresolved. |

Reproduction: select the stated entry in the review selector, load it into the
active game, return focus, and attempt playback/skip as described above.
Where unspecified, do not invent character, variant, button or fault details.
?Does nothing? does not by itself distinguish request rejection, scene entry,
waiting for native story context, or an unsupported completion route.

Existing evidence and source findings:
- [Optional cutscene skipping](optional-cutscene-skipping.md), including original
  command audit, supported completion routes, context-dependent variants, and
  the current owner reports.
- [Selector loading](cutscene-review-selector-loading.md), including BigShip's
  deliberate diagnostic rejection and earlier crash evidence.
- [Accepted Quarry atmosphere](quarry-atmospheric-transitions.md).
- Private live intake: cutscene-skip/review-intake-20261021/
  207-235-240-live-intake.json. These are partial live samples, not complete
  crash reports. Preserve original sessions and personal saves privately.

No new runtime remedy or replay has been performed for this retest intake.
The original story path must be distinguished from standalone diagnostic entry.
Do not remove an entry as unused based solely on inactivity or a crash.
Keep the owner's persistent per-character notes unchanged; this record
supplements them. Further diagnosis and owner validation remain outstanding.

335 follow-up: the owner message names335 without a variant; the freshly updated saved review entry identifies335/1/Juno. Its reviewed=true means the owner reviewed it, not that the skip passed: its note says ?cannot skip.? Preserve that distinction for all checklist imports. No note or checkbox was changed by this intake.


## Final Juno review and authorized follow-up, 2026-10-21

Owner confirms remaining failures are legitimate and narrows investigation to Juno. Two hours approved; original production guard/root/counters retained. The accepted Quarry lighting/fog fixes remain separate. Do not equate a checked review box with passing behaviour. Current build ca94e6b4 has the current cutscene headers; root native-source differences also include concurrent controls work. No new fix is claimed yet.

Additional explicit reports:376 does not skip;378/1 does not skip;380/1 does not skip (owner corrected280 to380). 207 is a stall after skipping, not a confirmed process crash.235 reportedly crashes after playback; unused status is unconfirmed. Snapshot and event correlation: private cutscene-skip/juno-final-retest-20261021. Owner notes remain unchanged.

| Scene/variant | Juno note | Last updated UTC |
|---|---|---|
| 15/0 | Cannot skip and this shows velas ship so this is velas cutscene | 2026-10-21T01:20:58.5945132Z |
| 15/1 | cannot skip | 2026-10-21T01:21:07.4871571Z |
| 45/0 | crashed the program (is this a real scene?) | 2026-10-20T19:15:51.2206749Z |
| 66/0 | cannot skip | 2026-10-21T01:21:49.2381579Z |
| 94/0 | cant skip | 2026-10-21T01:21:56.8243653Z |
| 97/0 | cant skip | 2026-10-21T01:22:04.3319436Z |
| 98/0 | cant skip | 2026-10-21T01:22:14.6771733Z |
| 193/0 | cant skip - boss intro cutscene | 2026-10-21T01:22:25.9147140Z |
| 207/0 | cant skip | 2026-10-20T19:35:26.5209387Z |
| 212/0 | cant skip | 2026-10-21T01:23:46.0797866Z |
| 235/0 | cant skip - this freezes. Is this a real cutscene? | 2026-10-20T19:36:26.0788096Z |
| 240/1 | cant skip - gets stuck in a loop. Is this a real cutscene? | 2026-10-20T19:37:55.1860695Z |
| 240/2 | works but slow to skip | 2026-10-20T20:01:35.2995481Z |
| 240/3 | works but also semi-slow skip | 2026-10-20T20:01:50.1268363Z |
| 252/0 | cant skip | 2026-10-21T01:25:18.5194153Z |
| 253/0 | cant skip | 2026-10-21T01:25:25.8579451Z |
| 271/1 | cant skip | 2026-10-21T01:25:35.0152278Z |
| 271/2 | cant skip and softlocks - is this a real screen cutscene? | 2026-10-20T19:39:34.0979056Z |
| 275/1 | cant skip and doesnt run - is this a real cutscene? | 2026-10-20T19:40:09.5950415Z |
| 282/0 | Quarry tribals after the cutscene flash during the day. We fixed this in a past commit. It happens on all fps original and higher. | 2026-10-20T19:47:46.8089040Z |
| 282/1 | this one you can skip the first part but it forces you to watch the second part | 2026-10-21T01:26:28.1591793Z |
| 282/2 | cant skip | 2026-10-21T01:26:34.8034742Z |
| 283/0 | you can skip the first section but then you cannot skip the full thing | 2026-10-21T01:26:42.3174122Z |
| 284/0 | cannot skip | 2026-10-21T01:26:52.6370600Z |
| 284/1 | cannot skip | 2026-10-21T01:27:01.3155873Z |
| 308/0 | cannot skip | 2026-10-21T01:27:07.0221792Z |
| 308/1 | cannot skip | 2026-10-20T19:50:45.7534213Z |
| 309/0 | does not skip the full sequence | 2026-10-21T01:27:38.3467517Z |
| 322/0 | skippable but slow | 2026-10-20T19:52:39.5015560Z |
| 322/1 | cant skip | 2026-10-20T19:52:15.9861391Z |
| 323/0 | skippable but slow | 2026-10-20T19:52:32.4322899Z |
| 323/1 | works but slow | 2026-10-20T20:02:14.4724664Z |
| 323/2 | works but slow | 2026-10-20T20:02:33.5486709Z |
| 324/0 | works but slow | 2026-10-20T20:03:02.7801365Z |
| 325/0 | works - slow | 2026-10-20T20:03:21.5186133Z |
| 326/0 | works - slow | 2026-10-20T20:03:34.5554193Z |
| 331/0 | does not skip the full cutscene | 2026-10-21T01:28:05.7433352Z |
| 334/0 | does not skip the full cutscene | 2026-10-21T01:28:12.4433219Z |
| 334/1 | cannot skip | 2026-10-21T01:28:18.3878084Z |
| 334/2 | cannot skip | 2026-10-21T01:29:07.4232285Z |
| 335/0 | cannot skip | 2026-10-20T20:05:41.7634486Z |
| 335/1 | cannot skip | 2026-10-21T01:30:13.4536359Z |
| 341/0 | does not skip the full scene | 2026-10-21T01:30:18.9710377Z |
| 342/0 | cannot skip | 2026-10-21T01:30:25.9782739Z |
| 342/1 | does not skip the full scene | 2026-10-21T01:30:32.5053444Z |
| 343/0 | cannot skip | 2026-10-21T01:30:45.7641857Z |
| 344/0 | works - slow | 2026-10-20T20:07:06.3622694Z |
| 346/0 | does not skip the full scene | 2026-10-21T01:31:30.1406874Z |
| 347/0 | cannot skip | 2026-10-21T01:31:35.5697854Z |
| 348/0 | opening sequence | 2026-10-21T01:31:42.0567955Z |
| 349/0 | opening sequence | 2026-10-21T01:31:43.9979802Z |
| 350/0 | cannot skip | 2026-10-21T01:31:49.6936048Z |
| 350/1 | cannot skip | 2026-10-21T01:31:57.1092712Z |
| 352/0 | cannot skip | 2026-10-21T01:32:04.7693408Z |
| 353/0 | cannot skip all of the scene | 2026-10-21T01:32:18.2442525Z |
| 353/1 | cannot skip | 2026-10-21T01:32:18.9857113Z |
| 354/0 | does not skip full scene | 2026-10-21T01:32:57.0921707Z |
| 357/0 | cannot skip | 2026-10-21T01:33:03.1826327Z |
| 357/1 | cannot skip | 2026-10-21T01:33:08.8317847Z |
| 359/0 | does not skip the full scene | 2026-10-21T01:33:18.2965663Z |
| 359/1 | cannot skip | 2026-10-21T01:33:33.2144616Z |
| 360/0 | cannot skip - BUG IT STILL SHOWS CREDITS OVERLAYED OVER THE GAME IF you force a skip (make sure that this gets addressed) | 2026-10-21T01:33:40.5084483Z |
| 366/0 | cannot fully skip | 2026-10-21T01:33:51.7253934Z |
| 373/0 | it requires two skips - not sure if that was intentional or not | 2026-10-20T20:33:23.7110217Z |
| 374/0 | cannot skip | 2026-10-21T01:33:58.5082088Z |
| 376/0 | cannot skip | 2026-10-20T20:33:48.2796828Z |
| 378/1 | cannot skip | 2026-10-20T20:34:04.0398844Z |
| 378/2 | slow | 2026-10-20T20:34:17.1466348Z |
| 378/3 | slow | 2026-10-20T20:34:28.1801772Z |
| 379/1 | slow | 2026-10-20T20:34:57.9837016Z |
| 380/1 | cannot skip | 2026-10-20T20:35:11.2386266Z |
| 380/2 | slow | 2026-10-20T20:35:26.4896439Z |
| 380/3 | slow | 2026-10-20T20:35:35.8961562Z |
| 381/0 | opening | 2026-10-20T20:35:51.6770838Z |
| 381/1 | odd buggy opening - unused | 2026-10-20T20:36:07.9967166Z |
| 382/0 | opening | 2026-10-20T20:36:17.3346953Z |
| 383/0 | opening | 2026-10-20T20:36:24.9228745Z |
| 384/0 | opening | 2026-10-20T20:36:31.5054169Z |
| 385/0 | opening | 2026-10-20T20:36:37.6346114Z |
| 388/0 | cannot fully skip | 2026-10-21T01:35:32.8424266Z |
| 388/1 | cannot fully skip | 2026-10-21T01:35:46.4917928Z |
| 388/2 | cannot fully skip | 2026-10-21T01:36:11.7058889Z |
| 389/0 | cannot fully skip | 2026-10-21T01:36:20.1489730Z |
| 390/0 | cannot fully skip | 2026-10-21T01:36:29.1481086Z |
| 391/0 | cannot skip | 2026-10-21T01:36:37.1626394Z |
| 392/0 | cannot fully skip | 2026-10-21T01:36:46.5355571Z |
| 394/0 | cannot skip | 2026-10-21T01:36:56.5188986Z |
| 399/0 | slow | 2026-10-20T20:42:06.8737651Z |
| 404/0 | slow | 2026-10-20T20:42:58.3879710Z |
| 405/1 | cannot fully skip | 2026-10-21T01:37:06.0310546Z |
| 405/2 | cannot fully skip | 2026-10-20T20:43:33.1296000Z |
| 409/0 | cannot skip - seems to be debug | 2026-10-21T01:44:22.3092101Z |
| 410/0 | cannot skip | 2026-10-20T20:44:36.1668297Z |
| 411/0 | the quarry tribal flashing is gone here somehow | 2026-10-20T20:45:15.8716741Z |


### Confirmed source causes and candidate, 2026-10-21

Credits skipping rejected the valid normalized overlay address03B00000 because it lies below KSEG0. The loader and other overlay readers intentionally use unsigned subtraction into the reserved guest address span. Candidate uses that same mapping with the existing metadata, bounds and signature checks. The credits scene also contains visual actor types112 (attachment/shadow) and132 (timed visual effect), which were absent from the reviewed control list. Their native handlers have no progression/inventory/transition writes; event and movement callbacks remain disallowed.

Scene376 includes a type50 projectile-trigger region. Its bit40 branch only reads projectile proximity and latches local actor state, then returns; the previous qualification rejected this branch even with zero players. Candidate allows this reviewed branch while preserving the separate active audio/script-region rejection. Sparse rejection logs now include actor+88 and entry flags for further diagnosis.

Validation pending.48 selected entries in the latest captures reached a completion handler, but this is NOT visual acceptance. Remaining no-exit variants are real selector-context limitations, not classified as unused. No owner notes changed.


### Owner clarification: checked Juno entries are passed

Owner explicitly confirms: "Yes - work on unchecked Juno entries." This supersedes the earlier inference that a checked box with an old failure note remained unresolved. Preserve the original notes as history; do not reopen checked entries from them. The active scope is the following unchecked Juno entries only. No owner checklist files were modified.

| Scene/variant | Current note |
|---|---|
| 45/0 | crashed the program (is this a real scene?) |
| 207/0 | cant skip |
| 235/0 | cant skip - this freezes. Is this a real cutscene? |
| 240/1 | cant skip - gets stuck in a loop. Is this a real cutscene? |
| 271/2 | cant skip and softlocks - is this a real screen cutscene? |
| 275/1 | cant skip and doesnt run - is this a real cutscene? |
| 308/1 | cannot skip |
| 322/1 | cant skip |
| 335/0 | cannot skip |
| 376/0 | cannot skip |
| 378/1 | cannot skip |
| 380/1 | cannot skip |
| 405/2 | cannot fully skip |
| 409/0 | cannot skip - seems to be debug |
| 410/0 | cannot skip |


First candidate built: native runtime bad068704a5fa6f308dc8d42dbe1d77d56cb104a6f0cdc0f458db16a39a95bae.48 extracted native address/actor/captured-credits checks and both cutscene component suites pass. Old credits address resolver reproduces its rejection; corrected resolver accepts the real normalized section identity and still rejects invalid identity/signature/state. Installed in copied review preview with all package entries verified and profile/checklist preserved. Owner live verification remains pending. This build does not claim all15 unchecked entries fixed.


335/0 trace narrows its missing prompt: the scene stayed qualified, physical/mapped A appeared, but effective game buttons stayed zero throughout the attempts. Capture flags2D/3D have UI capture and input blocking set, with Settings capture unset. In this source that means the foreground window differed from the game root. Thus this recorded attempt did not deliver A to the skip hold handler. Improve the selector focus handoff and retest; do not disable the game focus guard or mark the scene passed from eligibility alone.


### Remaining context-dependent entries, source refresh2026-10-21

A fresh scan uses the current native command sizes and preserves stream order across descending timestamps. It reconfirms that none of the following exact room/variant pairs has an unconditional or conditional departure in its own script, and finds no incoming direct transition in the scanned original command lists. Data-driven object triggers and parent state remain separate; this does not prove an entry unused.

| Unchecked Juno entry | Source evidence | Remaining limitation |
|---|---|---|
|45/0|Four time-zero setup commands; native entry previously lacked a required parent model.|Direct entry is blocked before actor creation; selector now explains why.|
|235/0|Visual camera/fog script ends at10.50seconds without departure.|Native context/completion remains unknown. A recorded session continued to later entries; no process crash was proved from that session.|
|240/1,378/1,380/1|All reuse asset243/group1;100commands, final sentinel at50.35seconds, no departure.|One shared standalone-completion limitation, not three distinct native movie endings.|
|271/2,322/1|Two/three time-zero setup commands, respectively.|No independent story ending established.|
|275/1,308/1|Empty command lists followed immediately by sentinel.|No standalone movie/ending in these command lists; owner rows remain unresolved.|
|409/0|Setup then native pause gate. Same asset/group also belongs to ordinary gameplay room315, Dog Tunnels.|External trigger/context needed; group1 is a different sequence.|
|410/0|One time-zero setup command; same asset/group belongs to ordinary gameplay room243, DogChasm.|No standalone completion contract established.|

Original code callers examined for308 and322 explicitly request group0; the275 numeric literal is a sound ID. No extra native destination, progression flags or automatic success marker was invented for these rows. The private selector exposes the existing limitation and preserves every owner note/check. Its initial selection is376/0 and focus handoff targets only the copied preview launcher.

Candidate owner review order:376/0;405/2 (whole ending chain);207/0 followed by loading another scene from character selection;335/0 (input/focus). All four remain pending. A checked Juno box supplied by the owner, not a completion log or this report, establishes a pass. The current allowance ends03:45:24UTC; production guard/root/counters remain enabled and unchanged.


### Owner review resumed, 2026-10-21 afternoon

The owner approved a further two-hour continuation ending21:39:20UTC. The existing production guard remains enabled with the same investigation root/counters. The prepared bad068704 candidate and updated selector are open; all15 Juno entries remain unchecked at handoff. The owner will drive gameplay and update the persistent checklist. No runtime/profile change was made during play, and no pass is inferred from launching. First retests are376/0,405/2,207/0 plus another scene load, then335/0.


## Owner review, October 21, 19:50 UTC

On candidate bad068704a5f, the owner confirmed **405/2 passes**. Do not reopen it. **376/0 still fails**, and **207/0 permits a skip but then shows a black screen**. The latter supersedes any inference that reaching character-select state alone proves correct visible completion. Both remain open. The owner checklist and running preview are unchanged; compare the fresh traces before proposing another candidate. Private evidence: juno-final-retest-20261021/owner-verdict-1950.json and the 19:45/19:47 owner sessions.


### Corrected dispatch audit and new candidate, October 21

The earlier actor audit indexed the native control jump table by type instead of type minus two, contrary to instruction8000FC88. This made type50 incorrectly subject to an audio-region restriction. In fact it calls no-op animobjControl80026FD4, the same handler as46/47; its entry pointer need not meet the unrelated trigger layout. Candidate removes that restriction and retains callback rejection. Type112 has no ordinary control; type132 is07C00678 (can write game flags), so it now additionally requires ordinary control disabled by cinematic animation. All four retained Credits snapshots satisfy that requirement. The previous handler descriptions and synthetic type50 fixtures are superseded, not verification of the original mapping. Private correct-original-control-map.json pins the captured original table and original branch instructions.

207 final snapshot shows native main thread cycling inside08701754, searching character selection for an eligible actor; it is runnable, not blocked on GPU/audio queues. A diagnostic story-context mismatch is being checked. No destination, progression flags or save data have been changed as a remedy. New runtime build and live verification remain pending.


207 cause confirmed: Juno-only unlock state plus native207 completion flag91 leaves zero eligible characters. Two closed/live captures and original-ROM eligibility tables agree. Diagnostic207/0 candidate prepares all three unlock prerequisites in the copied review game, without changing completion flags or normal campaign skip logic. See [selector loading](cutscene-review-selector-loading.md).376 actor correction and207 fixture preparation await live review;405/2 remains owner-confirmed passed.


Batch2 delivery20:12UTC: runtime96a6b2577d73c4a65541843dfeef5ebd4c0e3e3fa84f14d5af79d091357d3ebf
installed and both launcher/selector windows verified visible. All14 package
entries verify; copied userdata and owner checklist are unchanged. Matching
support identity replaces the stale build-directory sidecar. Both component
suites,46 native qualification checks and8 original selection-loop checks pass.
Owner visual verification of376/0,207/0 and335/0 is still pending;405/2 is passed.
Private receipts: batch2-staged-receipt.json, batch2-installed-receipt.json,
batch2-opened-receipt.json, original-menu-loop-v3/run.log.


Follow-up source audit while batch2 remains immutable: the earlier claim that
actor types145/147 share800270EC is also incorrect. Type145 dispatches to
05A002B4, which runs a visual particle/light sequence and calls
partUpdateTriggers8005F5AC; type147 dispatches to800270EC. The former reads the
trigger count from actor data+22 and requires a separate qualification review.
No observed scene regression or missing progression is established from this
finding, and checked owner scenes remain passed. The source comment/qualification
needs correction before release; do not treat the old common-handler rationale
as evidence. Original instructions are retained privately in
fn_088_0002_recomp.c.corrected-native-audit.asm.txt. Current owner preview is unchanged.

Owner acceptance20:46UTC: "376 works -207 works." The saved checklist
independently checks both Juno entries. This verifies the corrected type50
qualification in376 and the207 copied-review unlock prerequisites visibly;
do not reopen them from older failure notes.335/0 remains unchecked and is
the next targeted focus/skip test. Eleven other rows need original entry or
completion context; none is classified as unused or passed by this acceptance.
Private owner-batch2-acceptance.json preserves exact runtime and checklist hash.


Owner acceptance20:55UTC:335/0 works;207/0 works again. Saved Juno boxes agree. All four targeted retests (376/0,405/2,207/0,335/0) now pass. Eleven context-dependent entries remain open; no owner notes or checks were modified. Private owner-335-acceptance.json pins the source checklist. The focus-handoff fix has owner verification for335/0.


### Remaining variants: source classification, October 21

The owner suspects all remaining entries are debug scenes. A new original-data
audit supports treating them as likely development/setup variants, rather than
confirmed normal-campaign skip failures. This is a classification, not a claim
that every possible data-driven entry is unreachable.

The original object loader identifies asset28/29 as map index/data. All806 map
slots were examined:775 contain valid map headers,31 are empty, and631 exit
records decode without malformed nonempty maps. Original object definitions and
the translation table confirm the only exit-object alias is11 (definition92).
The only exits referencing any remaining room IDs are:

| Native source room | Actual destination/variant | Owner result |
| --- | --- | --- |
|241 CargoShip Brig|378/2|Checked/pass|
|243 DogChasm|409/1|Checked/pass|
|315 Dog Tunnels|410/1|Checked/pass|

The native player exit consumer at80032D1C/80032D90 reads the signed group byte
at exit setup+16, and mainChangeLevel defaults its group to0 before any override.
The actual bytes select2,1,1 respectively. Thus none of these exits reaches
the unchecked variants378/1,409/0 or410/0. A preliminary room-ID-only concern
about409/0 and410/0 is resolved by the variant decode. Likewise, the earlier
conversational mention of378/0 was premature; the validated group is2.

| Unchecked Juno entries | Original content | Classification |
| --- | --- | --- |
|275/1,308/1|Empty command lists|Empty variants; no standalone movie to complete|
|271/2,322/1,410/0|Only time-zero path/setup commands|Setup/development variants|
|409/0|Path setup then a pause gate; shares the gameplay room315 asset|Gameplay/setup variant, distinct from campaign409/1|
|45/0|Four setup commands and invalid standalone limb-parent setup|Unsafe development/context entry; direct review stays blocked|
|235/0|Camera/fog sequence ends without departure|Likely unfinished/demo sequence|
|240/1,378/1,380/1|Shared asset243/group1, no departure|Likely development version of the Brig sequence|

The original command interpreter's7F00 sentinel retains the cursor and returns;
it does not select another room, restore gameplay or run a hidden completion
handler. No incoming exact-variant script transition was found in the earlier
full animation-command scan. Original callers examined for308 and322 request
group0, not group1. These facts explain the direct-selector stalls without
inventing a skip destination or changing progression.

The owner has confirmed all four targeted fixes:376/0,405/2,207/0 and335/0.
Keep the11 remaining rows and old notes for reference, classified as likely
development/setup or unresolved entry contexts. Do not silently check them as
passed, hide them, or equate this source classification with exhaustive live
campaign verification. No game runtime, save or current selector was changed.

Private evidence: remaining-variant-classification.json,
remaining-scenes-object-inventory.json, original-map-exit-reference-variants.json,
native-player-transition-original.asm.txt, native-command-end-audit.asm.txt.
Only the findings belong in public docs; original ROM data and saves stay private.


### Final qualification audit, October 21

The type 145 follow-up is resolved as an incorrect source rationale, not a
demonstrated skip regression. Original object definition 238 identifies it as
FireWork; it has one particle trigger and no event script. Its actual ordinary
control at 05A002B4 updates local position/velocity, light intensity, visual
bursts, RNG and self-removal/reinitialization. Type 147 instead uses the short
animdroidControl texture-animation handler at 800270EC.

The transitive partUpdateTriggers audit contains no indirect callback dispatch.
Its external calls are model/texture/sprite allocation and release, animation,
math and RNG; no game-flag, inventory, player-input or level-transition function
is called. Particle trigger count is therefore not a gameplay-event count;
requiring zero would incorrectly reject the original FireWork definition.
Event and movement callbacks remain excluded by the existing qualification.

Corrected only the source comment in the main checkout and the isolated
high-refresh checkout. Non-comment code was compared before/after and is
identical. No executable rebuild or new visual test is warranted for this
documentation-only correction. The owner's accepted preview remains unchanged.
This audit does not claim bit-identical RNG state after skipping, or exhaustive
qualification of modified ROM object definitions.

Private evidence: firework-helper-scope.json,
firework-particle-transitive-scope.json, type145-original-definitions.json and
qualification-audit-final.json. Original instruction excerpts remain private.


Owner checklist update, 21:08 UTC: all eleven remaining Juno rows now have
owner-written "Debug Cutscene" notes and remain unchecked. This agrees with the
source classification above; it is not an independent proof of unreachability.
The original crash note for 45/0 remains present. No checkbox or note was
rewritten by the investigation. Private owner-debug-classification.json preserves
the updated evidence.
