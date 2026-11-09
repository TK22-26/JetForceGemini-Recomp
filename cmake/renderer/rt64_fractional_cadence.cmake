# Applied after the existing adapters to hash-checked build-tree RT64 sources.
# The upstream integer FPS fields remain compatibility/diagnostic hints. This
# adapter owns all scheduling arithmetic with the exact authored interval.
function(jfg_fractional_cadence_workload)
    jfg_video_replace([=[        int64_t logicalTicks = 0;
        int64_t displayTicks = 0;
        uint32_t originalRateForTicks = 0;
        uint32_t displayRateForTicks = 0;]=]
        [=[        jfg::PresentationCadence jfgCadence;]=])
    jfg_video_replace([=[                const bool jfgOffscreen = jfgSnapshot && (!jfgSnapshot->scene || jfgSnapshot->defer_to_blur);]=]
        [=[                const bool jfgOffscreen = jfgSnapshot && (!jfgSnapshot->scene || jfgSnapshot->defer_to_blur);
                const auto jfgInterval = jfg::workload_presentation_interval(jfgSnapshot, workload.viOriginalRate);]=])
    jfg_video_replace([=[const bool displayRateAboveOriginal = (workload.viOriginalRate > 0) && (workloadConfig.targetRate > workload.viOriginalRate);]=]
        [=[const bool displayRateAboveOriginal = jfgInterval.below_rate(workloadConfig.targetRate);]=])
    jfg_video_replace([=[                    const bool resetTicks = !generateInterpolatedFrames || (originalRateForTicks != workload.viOriginalRate) || (displayRateForTicks != workloadConfig.targetRate) || !displayRateAboveOriginal;
                    if (resetTicks && !jfgOffscreen) {
                        logicalTicks = 0;
                        displayTicks = 0;
                        originalRateForTicks = workload.viOriginalRate;
                        displayRateForTicks = workloadConfig.targetRate;
                    }]=]
        [=[                    if (!generateInterpolatedFrames && !jfgOffscreen) jfgCadence.reset();]=])
    jfg_video_replace([=[                    logicalTicks += workloadConfig.targetRate;
                    displayFrames = uint32_t((logicalTicks - displayTicks) / workload.viOriginalRate);]=]
        [=[                    displayFrames = jfgCadence.begin(jfgInterval, workloadConfig.targetRate);]=])
    jfg_video_replace([=[                    assert((logicalTicks > displayTicks) && "Logical ticks must always remain bigger than the display ticks.");
                    assert(((logicalTicks - displayTicks) <= (workloadConfig.targetRate + workload.viOriginalRate)) && "The gap between logical ticks and display ticks can't be bigger than the target rate.");
]=] [=[]=])
    jfg_video_replace([=[                else if (workload.viOriginalRate > 0) {
                    deltaTimeMs = 1.0f / float(workload.viOriginalRate);
                }]=]
        [=[                else if (jfgInterval) {
                    deltaTimeMs = static_cast<float>(jfgInterval.seconds());
                }]=])
    jfg_video_replace([=[const int64_t originalTimeMicro = (workload.viOriginalRate > 0) ? (1000000 / workload.viOriginalRate) : 0;]=]
        [=[const int64_t originalTimeMicro = jfgInterval.microseconds();]=])
    jfg_video_replace([=[std::clamp((workloadConfig.targetRate + displayTicks - logicalTicks) / float(workloadConfig.targetRate), 0.0f, 1.0f)]=]
        [=[jfgCadence.alpha()]=])
    jfg_video_replace([=[displayTicks += workload.viOriginalRate * (displayFrames - (frame + 1));]=]
        [=[jfgCadence.advance(displayFrames - (frame + 1));]=])
    jfg_video_replace([=[displayTicks += workload.viOriginalRate;]=] [=[jfgCadence.advance();]=])
    jfg_video_replace([=[deltaTimeMs = (curFrameWeight - prevFrameWeight) / float(workload.viOriginalRate);]=]
        [=[deltaTimeMs = (curFrameWeight - prevFrameWeight) * static_cast<float>(jfgInterval.seconds());]=])
    jfg_video_replace([=[jfgSnapshot ? jfgSnapshot->tick : 0U);]=]
        [=[jfgSnapshot ? jfgSnapshot->tick : 0U, jfgInterval);]=])
    jfg_video_replace([=[                float jfgPreviousAlpha = 0.0f;]=]
        [=[                float jfgPreviousAlpha = 0.0f;
                if (jfgSnapshot && !jfgOffscreen)
                    jfg::trace_interpolation("source-interval", jfgSnapshot->tick,
                        jfgInterval.rate, jfgInterval.ticks, workloadConfig.targetRate,
                        0U, 0.0f, 0U, 0U);]=])
    if(contents MATCHES "logicalTicks|displayTicks|originalRateForTicks|displayRateForTicks")
        message(FATAL_ERROR "Unmigrated integer RT64 presentation cadence")
    endif()
    set(contents "${contents}" PARENT_SCOPE)
endfunction()

function(jfg_fractional_cadence_present)
    jfg_video_replace([=[const auto jfgSequenceTick = jfg::presentation_sequence_tick(&frameCounters);]=]
        [=[const auto jfgSequence = jfg::presentation_sequence(&frameCounters);
        const auto jfgSequenceTick = jfgSequence.tick;
        const auto jfgSequenceInterval = jfgSequence.interval;]=])
    jfg_video_replace([=[(targetRate > 0) && (targetRate > viOriginalRate)]=]
        [=[(jfgSequenceInterval ? jfgSequenceInterval.below_rate(targetRate) :
                    jfg::PresentationInterval{1U, viOriginalRate}.below_rate(targetRate))]=])
    set(contents "${contents}" PARENT_SCOPE)
endfunction()
