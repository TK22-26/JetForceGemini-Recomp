# Exit marker and grenade fire cadence

Status: exit marker owner-verified locally, unreleased; grenade fire improved but not fully confirmed, 2026-10-24.

In Projectile Motion Fix Preview at120FPS the owner accepts bullets, shockwaves and actor motion but reports grenade fire still appears30FPS and the exit marker opening jitters while turning the camera. Screenshot: owner screenshot codex-clipboard-HVugRl.png (retained privately). The original travelling-shot capture includes effects, but this normal preview has logging off. Separate local shape/texture animation from anchor/camera interpolation before altering authored behavior. No cause or remedy verified yet. Related: high-refresh-shot-effects.md.

## Follow-up replay

A matching-enabled replay of the older fight completed. It identified 4,218 sampled owned billboard draws. The FireWork samples matched; most rejected samples were separate particle allocations. One six-corner particle at VI 8370 was partly visible and rejected on projected movement while a molotov actor was live. Its native matrix changed only in translation: the perspective divide magnified movement at off-screen corners of a large nearby quad. This is a concrete candidate mechanism, not proof that it is the owner's remaining fire symptom. Changing general projection/motion limits would affect unrelated geometry and is not justified by this one sample.

The replay did not provide an identified sequence of the opening exit marker. The exitControl actor is a trigger, not the visual beam, so its name alone cannot identify the reported effect. A short targeted marker/fire capture is needed to bind the visible symptom to draw ownership and distinguish camera movement from authored sprite/shape animation. No fire or marker rendering change has been made.

A bounded diagnostic observer now samples visible owned sprites, their actual match flag, transform and up to six local corners at 10 Hz during explicit interpolation recording. It does not enable matching-comparison renders or alter presentation. This will distinguish a held anchor from stepped local shape in the next targeted capture. Normal Play has recording disabled and does not collect these rows. The diagnostic runtime built and passed its renderer checks. Live capture remains pending.

The owner confirms both the opening cone/beam and its sparkles look choppy during camera movement; the fire remains affected too. The earlier normal preview did not record this pass. A separate capture launcher is prepared with visible-sprite telemetry and the FPS overlay hidden.

## Targeted owner capture

Capture 20261024-232129 completed. The room-21 beam matched on 227/230 frames;
its holds were VI 2940, 3294 and 3708, around appearance/visibility boundaries.
Visible particle asset 0x8024B4E0 had 537 sampled holds, including 413 more than
six VI after its first sampled appearance within a lifetime. Most held samples
also changed local sprite geometry. These observations do not establish that
all remaining choppiness has one cause.

The matching replay exited successfully but did not reproduce the owner's
map exit-warps from room 47 to 199/399/21. It therefore cannot explain the
Goldwood fire/marker behavior. Preserve this informative failure; successful
process exit is not route reproduction. The next bounded live observer adds
the exact history rejection reason and topology-key hash without enabling
comparison replays or changing renderer behavior.

## Exact live rejection and candidate

The second live capture (20261024-233129) records the exact history decision.
Asset 0x8024B4E0 has 159 sampled missing-history/no-anchor holds (reason 136),
and 1,121 matches. There are no motion-rejection holds for this asset in that
capture. Repeated holds occur within the same allocation lifetime; sampled
topology-key hashes change as the animated sprite's local mesh changes.

The billboard transform key retained vertex count and triangle connectivity
after removing positions. Those are properties of the animated local sprite,
not the identity of its world/camera transform. The candidate keys known sprite
transforms only by validated particle/actor lifetime, asset and camera identity.
It does not interpolate vertex correspondence or texture frames. Unknown shapes,
ambiguous owner claims, actual jumps, camera/asset replacement and stale lifetimes
retain their rejection rules. Build, tests and owner visual review pending.

The topology-independent sprite-transform candidate builds and passes the interpolation-history, semantic-presentation and renderer texture suites. Fire and Marker Motion Preview was opened for owner review with capture enabled and the overlay hidden. This is a candidate, not a verified resolution; the local sprite texture/shape animation remains authored at native cadence.

## Candidate owner result

In capture 20261024-234301 the owner reports: "Fire improved; marker still choppy." This is partial improvement, not resolution. The fire-associated sprite asset 0x8024B4E0 now matches 2,402 sampled draws and holds 58, with no sampled repeated holds within a continuing lifetime. The opening cone and sparkles remain open. Diagnostics-on/off history decisions also pass the same focused regression test.

## Marker-specific source finding

US regionidDraw (overlay 117, 0x0750070C) computes 20 persistent sparkle slots, sorts their indices by camera distance, then calls camDoSprite at 0x07500B04 with a temporary stack ObjectTransform. Generic actor-sprite tracking cannot resolve that temporary address to a live actor. A candidate records the real RegionID actor, control allocation and sorted logical slot for each emitted anchor. Actor retirement, room changes, control replacement and hidden/malformed markers reject history. This addresses sparkle provenance, not native texture-frame animation. The procedural LightBeam matches in the capture; colour/UV diagnostics now cover that beam too. Live verification remains required for the cone and sparkles.

The marker-specific candidate builds and passes all three focused suites (semantic presentation, interpolation history and F3DDKR textures). Regression coverage exercises all 20 sparkle slots in reversed draw order, hidden markers, changed control/asset, invalid index/type, expiry and actor retirement/reuse. Native camDoSprite unconditionally emits its ten-byte world anchor before its branches, validating observation at the call's entry output pointer. The owner preview is open; its live result is pending. Private receipt: shot-effects-detail-20261024/region-marker-review-receipt.json.

## Owner verification

The owner reports "worked" after the Exit Marker Motion Preview. The completed
capture 20261024-235833 preserves 20 distinct logical sparkle keys for the
Goldwood RegionID actor. Its visible samples include 3,102 matched draws and
20 first-history holds. This supports the source-level identity repair and the
owner's visual acceptance. The beam's geometry interpolation was already active;
this candidate changed sparkle ownership, not beam animation or gameplay speed.

The exit-marker report is resolved locally in the development changes and remains
unreleased. Fire remains recorded as improved from the preceding owner review;
this marker acceptance does not invent a separate full-fire confirmation.
The rendering change is independent of recording. Unknown sprites retain their
existing matching, and marker removal, room change, control replacement,
invalid slots and stale captures do not reuse the sparkle history.

Transferable lesson: effects emitted through temporary transforms need the
persistent logical owner from their caller. Draw order, stack address and
animated mesh topology are not stable effect identities. Keep this provenance
separate from geometry correspondence and preserve lifetime/camera cut checks.
