# Targeted framebuffer ownership evidence, active only with interpolation tracing.
function(jfg_flash_trace_replace before after)
 string(FIND "${contents}" "${before}" site)
 if(site EQUAL -1)
  message(FATAL_ERROR "Missing RT64 framebuffer diagnostic site")
 endif()
 string(REPLACE "${before}" "${after}" contents "${contents}")
 set(contents "${contents}" PARENT_SCOPE)
endfunction()

set(generated "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64/rt64_workload_queue.cpp")
file(READ "${generated}" contents)
jfg_flash_trace_replace(
[=[                bool validTargets = getTargetsFromPair(f);
                fbManager.recordOperations]=]
[=[                bool validTargets = getTargetsFromPair(f);
                if (jfg::interpolation_trace_enabled()) {
                    const auto snapshot = jfg::presentation_snapshot(&workload);
                    const auto tick = snapshot ? snapshot->tick : 0U;
                    const unsigned flags = unsigned(fbPair.fastPaths.clearDepthOnly) |
                        (unsigned(fbPair.depthRead) << 1U) | (unsigned(fbPair.depthWrite) << 2U) |
                        (unsigned(validTargets) << 3U);
                    jfg::trace_interpolation("fbpair-record", tick,
                        fbPair.colorImage.address, fbPair.depthImage.address, f,
                        workload.fbPairCount, curFrameWeight, flags, workload.workloadId);
                    if (validTargets && colorTarget)
                        jfg::trace_interpolation("fbpair-bind", tick,
                            colorFb ? colorFb->addressStart : 0U, colorTarget->addressForName,
                            colorFb ? unsigned(colorFb->lastWriteType) : 0U,
                            depthFb ? unsigned(depthFb->lastWriteType) : 0U, curFrameWeight,
                            reinterpret_cast<std::uintptr_t>(colorTarget->texture.get()),
                            reinterpret_cast<std::uintptr_t>(overrideTarget));
                }
                fbManager.recordOperations]=])
file(WRITE "${generated}" "${contents}")

set(generated "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64/rt64_present_queue.cpp")
file(READ "${generated}" contents)
jfg_flash_trace_replace(
[=[                commandList->begin();
                bool jfgPresentOverlayApplied = false;]=]
[=[                commandList->begin();
                if (colorTarget)
                    jfg::trace_interpolation("present-output-target", jfgOutputSample.tick,
                        present.screenVI.fbAddress(), colorTarget->addressForName,
                        unsigned(i), unsigned(framesToPresent), jfgOutputSample.alpha,
                        reinterpret_cast<std::uintptr_t>(colorTarget->texture.get()),
                        reinterpret_cast<std::uintptr_t>(colorTarget));
                bool jfgPresentOverlayApplied = false;]=])
file(WRITE "${generated}" "${contents}")

set(source "${jfg_rt64_root}/src/render/rt64_render_target.cpp")
file(SHA256 "${source}" digest)
if(NOT digest STREQUAL "0dee0d19a4be22c4fa34b7ef793e3d4f75a07ab0d31252f9a23a2a0355edb41d")
 message(FATAL_ERROR "Pinned RT64 framebuffer copy input differs")
endif()
file(READ "${source}" contents)
jfg_flash_trace_replace(
[=[        assert(format != src->format);

        // Select shader based on the formats.
        RenderTextureLayout requiredTextureLayout]=]
[=[        assert(format != src->format);

        jfg::trace_interpolation("framebuffer-type-copy", 0U,
            src->addressForName, addressForName, unsigned(src->type), unsigned(type), 0.0f,
            reinterpret_cast<std::uintptr_t>(src->texture.get()),
            reinterpret_cast<std::uintptr_t>(texture.get()));
        // Select shader based on the formats.
        RenderTextureLayout requiredTextureLayout]=])
set(generated "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64/rt64_render_target.cpp")
file(WRITE "${generated}" "#include \"jfg/renderer/interpolation_bridge.hpp\"\n${contents}")
jfg_interpolation_replace_source("rt64_render_target.cpp" "${generated}")
