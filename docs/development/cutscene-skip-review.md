# Native cutscene review inventory

Status: diagnostic selector and inventory prepared on 2026-10-20; owner confirms
the corrected selector loads a scene. Broader entry and skip coverage is unverified. Accepted runtime fixes are on develop
through a31a4c919ecb4e8eac21d41d6f0867b909881f12, including owner-confirmed
skip-audio and launcher-menu fixes. The diagnostic selector remains uncommitted
work; one owner-confirmed entry does not establish all-scene coverage.

[Review checklist](cutscene-skip-review.csv) contains 168 room/group variants.
This is not a count of unique movies. The original US data contains 412 room
headers, 406 animation asset slots and 120 rooms marked cinematic/menu.
The checklist excludes the initially identified frontend rooms and retains chained shots,
reused variants and potentially unused data. It does not establish coverage
of every gameplay-scripted event or dialogue.

## Owner workflow

Use the desktop **JFG - Cutscene Review** shortcut. Start its review launcher,
press Play and load the copied save. Select the native scene name and variant,
choose the character, press Load scene, and return focus to the game within
one minute. A, B or Start should reveal the prompt on supported scenes;
hold A to skip. Each row now has separate Juno, Vela and Lupus review checkboxes.
Select the character to edit that scene/variant/character notes box. Record prompt,
completion destination, controls or audio problems there. Checks mean reviewed,
not automatically passed. The original desktop CSV remains available for detailed
results; it is not overwritten by the selector. The normal profile is not used.

Close the review game and launcher before Restore copied save. Restore between
independent tests when story changes or remembered return rooms may matter.
Direct-entry tests exercise skip eligibility and completion; normal-route
progression still needs representative campaign testing.

Some entries depend on prior story flags, a remembered return room, a boss
state or earlier shots. A failed direct entry is not a confirmed skip failure.
Report the room/group and whether the scene loaded before testing the prompt.
The six non-monotonic scripts, two looped scripts and one pause-gated script
remain explicitly unqualified by the inventory parser.

## Implementation and checks

The explicit --cutscene-review-request diagnostic option is forwarded by the
launcher after its normal environment sanitization. Ordinary Play still strips
inherited JFG variables. The runtime also requires gameplay tracing and play
mode, and reads requests on an asynchronous file-reader thread.

Requests are bounded, timestamped and single-use. The update thread validates
room kind, sequence asset, requested group and data bounds against original
data, rejects frontend destinations, and waits until a save is loaded before
using the native level-transition and animation-group setters. No story flags
are manufactured by the selector. The current game mode is retained except for
the original credits mode.

Validation includes malformed/stale/repeated request checks, invalid-data bounds,
launcher diagnostic handoff and sanitization tests, selector control construction
and filtering, and all 168 real room/group entries for three characters.
1,792 excluded frontend/out-of-range room/group combinations were rejected.
These checks do not constitute gameplay or visual verification.

Private evidence is under v131-rnd-20261019/cutscene-skip/inventory and
selector-preview-receipt.json. Original ROM sections and saves remain private.

## Audio follow-up

The owner corrected the symptom to fragmented ambient effects, not music.
The diagnostic capture and original scripts identify short effect starts/stops
in intermediate skipped shots. A scoped candidate suppresses only their
qualified script starts and preserves music, cleanup and normal gameplay audio.
The owner confirmed the sound fix and corrected launcher menu behavior. The
cutscene selector package now includes those accepted binaries, preserving its
copied profile, baseline save and desktop checklist. Vela rescue (room 378,
group 2, Juno) is selected for the first direct-entry review. The refresh and
selector checks do not establish gameplay acceptance of direct scene loading.

See [the persistent skip report](issues/optional-cutscene-skipping.md) for prior
failures, reviewed completion contracts and owner acceptance.

## First direct-entry review blocker

The first owner attempt exposed a selector process-count bug: one running game
normally has a native parent and child, so the exactly-one-process check rejected
it without writing a request. The selector now counts native process families,
with focused parent/child and independent-game tests. The owner confirms Load
scene now works. See [DIAG-003](issues/cutscene-review-selector-loading.md).

## Character selection limits

The inventory records room, group and script structure, not a verified required
playable character for each entry. The selector does not infer character from a
scene name. Use the known story character when available; the reviewed Vela-rescue
entry uses Juno despite its subject being Vela. Boy/Girl/Dog native labels are useful
navigation hints, not proof of the complete entry recipe. Record chosen character
with failures. No claim is made that every group needs all three characters or
that one successful character qualifies the others.

## Persistent per-character review checklist

Owner-requested on 2026-10-20: review each scene without stopping to report every
failure. The private selector grid stores independent reviewed flags and multiline
notes keyed by native room number, variant and character. The Has notes column
shows which characters have notes. Checking/unchecking a character does not erase
its notes. Search filtering does not change the keys or saved data.

The desktop file JFG-cutscene-review-progress.json is separate from the preview,
copied profile and baseline save. Checks save immediately; notes save after a short
typing pause and flush on character/scene changes, focus exit, Load scene and
window close. Restore copied save does not touch the review file. Each save reads
the latest file under a per-file mutex, applies only the edited field and writes
by atomic replacement, retaining the prior version as .bak. Invalid saved data
is preserved and reported rather than silently reset. Failed saves remain visible;
a pending note prevents normal window close until it can be saved.

Validation: isolated UI checks exercised all 168 rows, native parent/child session
detection, character and variant separation, checkbox reversal without note loss,
filtering, navigation flush, Unicode/multiline notes, atomic backup and preservation
of another writer's entry. A fresh process reopened the fixture and populated the
correct checks and notes; an independent parser verified exact stored text.
No game or real save was used. The first grid smoke caught a PowerShell array
binding error, corrected before handoff. A later independent-check fixture had
an ASCII-shell expected-string error; actual persisted Unicode was correct and
the escaped expectation passed. The offscreen layout was also inspected.

Private evidence: cutscene-skip/selector-progress-20261020. Owner review of the
new checklist UI is pending. No completion marks are fabricated from runtime
logs or from this automated fixture, and no new cutscene acceptance is implied.


## Catalog classifications from the completed review
The selector list still preserves all168 entries and their original keys. A
follow-up source audit identifies eight menu-background variants and five
setup-only variants; they are not standalone story skip tests. Six other
variants need their native trigger/completion context established. BigShip45/0
has an unsafe direct-entry initializer and is explicitly blocked by the
diagnostic selector candidate rather than patched in normal gameplay. The
unresolved native context and campaign reachability are still recorded in the
[skip issue](issues/optional-cutscene-skipping.md). No owner notes or review
checkboxes are changed by these labels.
