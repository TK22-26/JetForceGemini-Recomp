# UI-ABOUT-20261107: About Jet Force Gemini opens slowly

## Timing investigation and diagnostic delivery - 2026-11-07

Status: open, not reproduced; no proven cause or remedy. Three controlled Windows
opens built the content in about 0.4-0.7 ms; two rendered settling frames took
about 6-12 ms. Under actual GE-Proton software Vulkan, content took about
0.6-0.8 ms and settling frames about 34-63 ms. These direct-panel fixture timings
do not measure the owner's physical click or prove their delay absent.

Source review finds embedded local About resources and no network fetch in
`aboutHtml()`. This rules out a fetch in that function, not all event-loop or
driver stalls. `frontend-ui-timing.log` now records message age, content build,
wait-to-frame and presentation-call timing once per open. Appending stops near
64 KiB. Values are numeric and contain no paths; old-message/sentinel values
from programmatic fixture opens are not evidence of owner input backlog.

Timing logging is present in the updated E: launcher and its collector includes
the file. The owner should compare first/repeated opens from home and gameplay.
No matching owner log was available on E: during this review. Cause and final
remedy remain pending; logging is not called a fix. Private evidence:
`gh40-ui-fixes-20261107`, with exact package hash in the [Proton record](github-steam-deck-proton-startup.md).
The initial unmeasured report below remains historical evidence.


- Severity: minor responsiveness defect; no crash or permanent failure reported.
- Status: controlled Windows/Proton checks do not reproduce delay; bounded timing logging delivered; cause open.
- Reported and last updated: 2026-11-07.
- Affected build/profile: current launcher during Bazzite #40 review. The owner
  states that this also affects Windows; exact machine/build combinations and
  first-open versus repeat-open behavior were not supplied.
- Evidence origin: owner's report; no timed capture or diagnostic log supplied.
- Related: [Proton menu visibility](github-steam-deck-proton-startup.md) is a
  separate platform-specific defect.

## Symptoms and reproduction

Open **Help > About Jet Force Gemini...**. The owner reports that it takes a
while before the About window appears. Expected behavior is prompt feedback and
opening. No precise duration was given; do not reuse the historical approximately
20-second Audio settings delay as an About measurement.

## Evidence and hypotheses

The owner's November 7 feedback says: "clicking about jet force gemini takes a
while to actually launch that window" and clarifies that only the gameplay-hiding
finding is platform-specific. This establishes a shared responsiveness report,
not its internal cause. The three accompanying screenshots illustrate the
[layout issues](launcher-rom-and-search-layout.md), not the About latency.

About content and menu action handling are in
[`native_ui.cpp`](../../../launcher/ui/native_ui.cpp), with embedded
[`about.rml`](../../../launcher/ui/assets/about.rml) and
[`about.rcss`](../../../launcher/ui/assets/about.rcss). No blocking operation,
graphics/font initialization, process-startup or network cause has been isolated.

## Attempts and resolution

| Date | Action | Result |
|---|---|---|
| 2026-11-07 | Record owner feedback alongside #40 manual review | No timing experiment or code change; cause and remedy remain pending |

Measure action-to-first-visible-content time for first and subsequent opens,
then identify the blocking stage before choosing a fix. Verify normal close and
reopen behavior after any change. No candidate, automated verification, live
acceptance or released correction exists for this report.

## Lessons and compatibility

A similar symptom in another settings window does not establish the same cause.
Record timings and the actual presentation route, and keep shared launcher
responsiveness separate from Proton-specific game/window composition.

### Actual launcher menu follow-up

A separate Windows probe opened About three times through the actual production
launcher's posted Help / End / Enter menu messages, with normal device discovery
enabled and a fresh isolated home profile. Observed queue-to-log completion was
62-63 ms (50 ms polling); internal request-to-present records were 16-31 ms. All
three opens and clean shutdown passed. This strengthens the direct-panel fixture
result but still does not reproduce the owner's physical click, imported-ROM
profile or active gameplay. The reported delay remains open. Private evidence:
`gh40-ui-fixes-20261107/production-about-result`.

The owner subsequently confirmed a separate structural bug: About is still an
embedded dialog. See [the separate-window report](launcher-about-separate-window.md).
The timing checks above did not verify a separate native window.

The separate-window candidate now passes actual native-window/process checks,
with three Windows openings at 359-375 ms and Proton at 639-752 ms in controlled
conditions. This supersedes the embedded-panel architecture, not the unknown
cause of the original reported delay. Child timing excludes process startup.
