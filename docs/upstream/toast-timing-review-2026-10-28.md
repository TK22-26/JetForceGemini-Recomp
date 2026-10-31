# Current Toast timing review

Reviewed immutable revision
[b391568af0416f4c68c5f46b037dcf369d0361e4](https://github.com/VibinToast/JetForceGemini-Recomp/tree/b391568af0416f4c68c5f46b037dcf369d0361e4).
This is source review, not a qualification run of that project. No upstream
implementation was copied into our runtime.

The [frame-rate implementation](https://github.com/VibinToast/JetForceGemini-Recomp/blob/b391568af0416f4c68c5f46b037dcf369d0361e4/src/jfg/jfg_frame_rate.cpp)
identifies the same structural hazard: squad members integrate velocity,
behaviour probabilities and some counters once per call despite receiving
elapsed video frames. Its 60 Hz option pairs ticks and accumulates elapsed
frames for squad updates. That supports the per-call diagnosis; it does not
prove that a fixed 30 Hz squad rate matches N64 load-dependent pacing.

The 60 Hz path replaces viFrameSync waits and changes scheduler retrace
handling. These are explicit enhancements. They are not candidates for our
Original policy without original-state and timing comparisons. The current
upstream changelog labels 60 Hz experimental and recommends 30 plus
interpolation in its presets.

The same file retries recovery from the 20 Hz mode after a number of ticks,
writing gVideoDeltaTime and its counter, with a growing retry interval.
This addresses native pacing lock-in but changes the original recovery rule.
Our own recovery adjustment also changes that rule. Controlled local tests
show removing our adjustment alone does not fix the faster game-update rate.

Useful transferable findings are the per-call squad cadence hazard, scheduler
backpressure and integer-angle convergence at shorter timesteps. Each is a
hypothesis or enhancement to qualify separately. A visually working scene,
a stable output rate, or matching another recomp is not proof of native N64
simulation timing. See the [active parity issue](../development/issues/original-mode-simulation-parity.md).

Private source and tool receipts are retained under
original-timing-cause-20261028. Original game code, ROMs and personal saves
remain private. This review does not modify the pinned production dependency
or erase the earlier October reference review.
