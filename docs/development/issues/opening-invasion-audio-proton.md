# AUDIO-OPENING-20261107: Audible glitch in opening Invasion on Bazzite

- Severity: intermittent audible interruption; overall play reported generally okay.
- Status: owner-reported, cause unconfirmed; evidence retrieval pending.
- Reported: 2026-11-07; Bazzite x64 PC, RTX 4070, private issue #40 test bundle.
- Build: launcher 067f9a8 and reviewed v33 regional game runtimes. USB supplies
  USA ROM/default; actual active region and installed Proton version are unverified.

## Symptoms and reproduction

The owner heard what they described as an audio underrun during the initial
Invasion and clarified that this was the opening cutscene, rather than King
Jeff's later replay. They also reported [awkward skip completion](cutscene-skip-completion-time.md).
Occurrence count, precise shot, settings and duration are not yet measured.

## Evidence and attempted review

The owner says they followed the handoff. The USB currently contains no owner
results archive or gameplay logs. Its existing evidence folder is our previous
automated verification, not the owner's run. Original instructions enabled
Proton logging but not a detailed gameplay trace. The revised collector includes
launcher/support logs (including recovery events), presentation and About timing;
the updater saves pre-update evidence and copies it to the USB automatically.

[Earlier opening continuity evidence](../../../evidence/opening-cutscene-audio-continuity.json)
records a Windows host-work/pacing problem fixed in October. It does not establish
the cause on Bazzite/NVIDIA. [GitHub #19](github-invasion-replay-stutter.md) covered
a later replay and is historically reporter-resolved. Neither history is reopened
or treated as proof of this report's cause. The pinned upstream review/catalog
was consulted; it does not supply evidence for this machine's audible interruption.

## Cause, remedy and next verification

Unknown; no game/audio change or claimed resolution. An audible interruption is
reported, but no queue/device capture confirms an underrun, backend fault or
relation to skip timing. Review the saved session/build identity and available
logs first. If insufficient, capture the opening only with diagnostics and compare
normal Play separately, because diagnostic overhead changes timing. No long
underrun investigation or buffering workaround is justified by counters alone.

## Compatibility lesson

Keep platform, entry route and audio symptom distinct. A past Windows pass or
successful software-Vulkan Proton UI check cannot certify Linux/NVIDIA audio.
Automated runs remain muted with processing and counters enabled; manual testing
retains normal sound. ROMs, saves and memory dumps remain outside collected results.
