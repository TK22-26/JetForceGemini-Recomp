# ADR 0002: Orthogonal execution profiles and deterministic test backend

- Status: Accepted for Phase 0; backend implementation pending
- Date: 2026-08-03
- Decision owners: Human maintainers for scheduler and hash semantics
- Supersedes: The three mutually exclusive modes described by the initial plan

## Context

Compatibility behavior, enhanced behavior, deterministic execution, and
headless rendering are independent concerns. Treating them as three mutually
exclusive modes prevents deterministic testing of enhancements and encourages
test-only conditionals to leak into game behavior.

The candidate upstream runtime currently uses host threads and wall-clock
timers. A deterministic runtime therefore requires an explicit backend seam;
it cannot be implemented reliably as a launcher flag around uncontrolled host
threads.

## Decision

Every run is described by four orthogonal axes.

### Behavior profile

- `compatibility`: original simulation cadence and behavior, minimum required
  native patches, no optional fixes or quality-of-life changes.
- `enhanced`: compatibility behavior plus individually named and independently
  switchable enhancements.

Compatibility is always buildable and testable. An enhanced feature MUST NOT
silently alter compatibility behavior.

### Execution backend

- `production`: the approved production scheduler, clock, and host integration.
- `deterministic`: a controlled scheduler, virtual clock, deterministic device
  inputs, and journaled host effects.

Both behavior profiles MUST run on the deterministic backend. The production
backend MUST also be able to run compatibility and enhanced profiles.

### Presentation backend

- `rendered`: renderer and audio presentation are active.
- `headless`: graphics, audio, and UI outputs terminate at deterministic sinks.

Headless execution may omit presentation work but MUST preserve the timing and
observable completion semantics of submitted N64 tasks.

### Feature set

Every optional behavior change has a stable feature ID, declared dependencies,
incompatibilities, default state, tests, and rollback action. Required native
compatibility patches are versioned but are not represented as optional
enhancements.

## Required runtime boundary

Game-facing code may reach the host only through approved interfaces:

- `Clock`: VI count, counter/time reads, timer deadlines, and virtual sleep.
- `Scheduler`: thread creation, priority, wakeup, blocking, and event ordering.
- `InputSource`: controller state, connection state, and accessory state.
- `DeviceBus`: PI/SI operations, ROM reads, save devices, and rumble.
- `StorageBackend`: durable saves, atomic replacement, and failure injection.
- `RendererSink`: graphics/RSP task submission and completion.
- `AudioSink`: audio task submission, sample accounting, and completion.
- `HostServices`: configuration and diagnostics that cannot affect simulation.

The deterministic binary MUST reject or intercept direct wall-clock reads,
host sleeps, uncontrolled thread creation, nondeterministic randomness, and
unmocked filesystem/network access from compatibility logic.

The implementation strategy—an upstream abstraction, maintained runtime fork,
or independent backend—requires a follow-up ADR before integration. Until that
decision is accepted, deterministic-runtime work is a feasibility spike and
not a completed feature.

## Deterministic event contract

The deterministic backend MUST define:

1. The canonical logical point at which controller input is sampled.
2. Total ordering for events sharing a virtual timestamp.
3. Thread-priority and equal-priority tie-breaking rules.
4. Timer rounding, wraparound, cancellation, and periodic reload behavior.
5. RSP, DMA, audio, save, and message-queue completion ordering.
6. Reset, boot, overlay-load, process-restart, and shutdown semantics.
7. A versioned schedule/event journal schema.

Queue, thread, overlay, and device journal entries use stable logical IDs, not
host pointers or process-specific handles.

## State and floating-point contract

State hashes are computed only at a named synchronization barrier after all
work for the canonical tick is complete. Hash input is an explicit canonical
serialization with:

- Declared byte order and integer widths.
- Stable N64 address representation.
- Explicit fields rather than native struct bytes.
- No padding, host pointers, resource handles, timestamps, or log counters.
- A fixed floating-point environment and documented handling of NaNs,
  denormals, rounding, contractions, and fused operations.
- Schema/version identifiers included in every checkpoint.

Changing the serialization, synchronization barrier, FP contract, or exclusion
list is a human-approved compatibility decision. Existing goldens may not be
silently regenerated.

## Profile manifest

Every replay records at least:

```yaml
behavior: compatibility
execution: deterministic
presentation: headless
features: []
profile_schema: 1
event_schema: 1
state_hash_schema: 1
```

It also records the supported ROM identifier, project commit, dependency lock
digest, compiler/toolchain identifier, and approved baseline identifier. It
does not record machine-specific paths or personal identifiers.

## CI contract

At minimum, trusted ROM-backed CI runs:

- Compatibility + deterministic + headless on every trusted candidate.
- Compatibility + deterministic + rendered for graphics smoke scenarios.
- Enhanced + deterministic at every supported feature-matrix boundary.
- Compatibility + production as a differential scheduling/timing smoke test.
- Repeated identical deterministic runs for nondeterminism detection.

Changing display rate, aspect ratio, renderer backend, or interpolation MUST
NOT change compatibility simulation hashes at canonical ticks.

## Human-only gates

Human approval is required for scheduler semantics, state-hash exclusions,
floating-point policy, test tolerances, golden updates, save semantics, and any
production/test-backend difference that is visible to game logic.

## Acceptance criteria

The deterministic backend is accepted only when:

1. One canonical replay produces identical event and state hashes over 100
   consecutive runs in both debug and release configurations.
2. A recorded schedule can be replayed exactly, while a deliberately changed
   event produces a stable first-divergence tick.
3. Forbidden host calls are blocked by tests, not merely prohibited by policy.
4. Compatibility runs with rendered and headless presentation reach identical
   simulation checkpoints.
5. At least two host CPU-count configurations produce identical deterministic
   results; any intended cross-OS limitation is recorded explicitly.
