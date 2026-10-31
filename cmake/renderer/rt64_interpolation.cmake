# Experimental interpolation adapters; pinned dependency sources stay pristine.
include("${CMAKE_CURRENT_LIST_DIR}/rt64_video_settings.cmake")
function(jfg_interpolation_replace_source basename generated)
    get_target_property(sources rt64 SOURCES)
    set(patched)
    set(found FALSE)
    foreach(unit IN LISTS sources)
        get_filename_component(name "${unit}" NAME)
        if(name STREQUAL "${basename}")
            list(APPEND patched "${generated}")
            set(found TRUE)
        else()
            list(APPEND patched "${unit}")
        endif()
    endforeach()
    if(NOT found)
        message(FATAL_ERROR "Missing RT64 interpolation source: ${basename}")
    endif()
    set_property(TARGET rt64 PROPERTY SOURCES "${patched}")
endfunction()

set(source "${jfg_rt64_root}/src/hle/rt64_workload_queue.cpp")
file(SHA256 "${source}" digest)
if(NOT digest STREQUAL "6e53030e8899c42347b51e67879fcb9679ad487ac067c192612c432d85bca4a4" AND NOT digest STREQUAL "090cab491982923b41c75a55664586a61492343b89fe8963895c85bd6040d48f")
 message(FATAL_ERROR "Pinned RT64 interpolation input differs: src/hle/rt64_workload_queue.cpp")
endif()
file(READ "${jfg_workload_generated}" contents)
set(before [=[                // Detect the color image to interpolate for this workload.]=])
set(after [=[                const auto jfgSnapshot = jfg::presentation_snapshot(&workload);
                const bool jfgOffscreen = jfgSnapshot && (!jfgSnapshot->scene || jfgSnapshot->defer_to_blur);
                std::vector<uint32_t> jfgOffscreenColors;
                std::unordered_set<uint32_t> jfgOffscreenColorSet;
                InterpolatedFrameCounters jfgOffscreenCounters;
                // Detect the color image to interpolate for this workload.]=])
string(FIND "${contents}" "${before}" offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Missing RT64 interpolation patch site")
endif()
string(REPLACE "${before}" "${after}" contents "${contents}")
set(before [=[std::vector<uint32_t> &colorVector = ext.sharedResources->colorImageAddressVector;]=])
set(after [=[std::vector<uint32_t> &colorVector = jfgOffscreen ? jfgOffscreenColors : ext.sharedResources->colorImageAddressVector;]=])
string(FIND "${contents}" "${before}" offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Missing RT64 interpolation patch site")
endif()
string(REPLACE "${before}" "${after}" contents "${contents}")
set(before [=[std::unordered_set<uint32_t> &colorSet = ext.sharedResources->colorImageAddressSet;]=])
set(after [=[std::unordered_set<uint32_t> &colorSet = jfgOffscreen ? jfgOffscreenColorSet : ext.sharedResources->colorImageAddressSet;]=])
string(FIND "${contents}" "${before}" offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Missing RT64 interpolation patch site")
endif()
string(REPLACE "${before}" "${after}" contents "${contents}")
set(before [=[bool interpolationCandidate = fbPair.earlyPresentCandidate();]=])
set(after [=[bool interpolationCandidate = jfg::early_present_workload_candidate(fbPair, jfgSnapshot && jfgSnapshot->scene,
                            workload.fbPairs.data(), workload.fbPairCount);]=])
string(FIND "${contents}" "${before}" offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Missing RT64 interpolation patch site")
endif()
string(REPLACE "${before}" "${after}" contents "${contents}")
set(before [=[                int32_t interpolationTargetFbPairIndex = -1;]=])
set(after [=[                int32_t interpolationTargetFbPairIndex = -1;
                bool jfgProvisionalTarget = false;]=])
string(FIND "${contents}" "${before}" offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Missing RT64 target priority declaration")
endif()
string(REPLACE "${before}" "${after}" contents "${contents}")
set(before [=[if (!interpolationCandidate || !interpolationTargetKey.isEmpty()) {]=])
set(after [=[if (!interpolationCandidate || (!interpolationTargetKey.isEmpty() && !jfgProvisionalTarget)) {]=])
string(FIND "${contents}" "${before}" offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Missing RT64 target priority selection")
endif()
string(REPLACE "${before}" "${after}" contents "${contents}")
set(before [=[                        if ((interpolationFb != nullptr) && interpolationFb->interpolationEnabled) {]=])
set(after [=[                        const bool jfgConfirmed = interpolationFb && interpolationFb->interpolationEnabled;
                        const bool jfgBootstrap = !jfgOffscreen && jfgSnapshot &&
                            !jfgSnapshot->blur_source && jfg::bootstrap_interpolation_target(interpolationFb,
                                fbPair,workload.fbPairs.data(),workload.fbPairCount,jfgSnapshot->scene,
                                workload.paused,workload.viOriginalRate,
                                std::any_of(jfgSnapshot->transforms.begin(),jfgSnapshot->transforms.end(),
                                    [](const auto& transform){return transform.matched;}));
                        if (jfg::interpolation_trace_enabled() && jfgSnapshot) {
                            const unsigned flags=(jfgSnapshot->scene?1U:0U)|(jfgOffscreen?2U:0U)|
                                (jfgSnapshot->blur_source?4U:0U)|(workload.paused?8U:0U)|
                                (interpolationFb?16U:0U)|
                                (interpolationFb && interpolationFb->lastWriteType==Framebuffer::Type::Color?32U:0U)|
                                (interpolationFb && interpolationFb->interpolationEnabled?64U:0U)|
                                (std::any_of(jfgSnapshot->transforms.begin(),jfgSnapshot->transforms.end(),
                                  [](const auto& transform){return transform.matched;})?128U:0U)|
                                (jfgBootstrap?256U:0U);
                            jfg::trace_interpolation("target-candidate",jfgSnapshot->tick,colorImg.address,
                                colorImg.width,interpolationFb?interpolationFb->width:0U,flags,
                                float(workload.viOriginalRate),
                                colorImg.siz|(colorImg.fmt<<8U)|(interpolationFb?interpolationFb->siz<<16U:0U),
                                interpolationFb?interpolationFb->addressStart:0U);
                        }
                        if (jfgBootstrap && !jfgConfirmed)
                            jfg::trace_interpolation("target-history-bootstrap",jfgSnapshot->tick,
                                colorImg.address,workload.viOriginalRate,workloadConfig.targetRate,0U,0.0f,0U,0U);
                        if (jfg::select_interpolation_target(!interpolationTargetKey.isEmpty(),
                                jfgProvisionalTarget,jfgConfirmed,jfgBootstrap)) {
                            jfgProvisionalTarget = !jfgConfirmed;]=])
string(FIND "${contents}" "${before}" offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Missing RT64 first continuous scene target patch site")
endif()
string(REPLACE "${before}" "${after}" contents "${contents}")
set(before [=[if (resetTicks) {]=])
set(after [=[if (resetTicks && !jfgOffscreen) {]=])
string(FIND "${contents}" "${before}" offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Missing RT64 interpolation patch site")
endif()
string(REPLACE "${before}" "${after}" contents "${contents}")
set(before [=[ext.sharedResources->viOriginalRate = workload.viOriginalRate;]=])
set(after [=[if (!jfgOffscreen) ext.sharedResources->viOriginalRate = workload.viOriginalRate;]=])
string(FIND "${contents}" "${before}" offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Missing RT64 interpolation patch site")
endif()
string(REPLACE "${before}" "${after}" contents "${contents}")
set(before [=[const bool useDifferentCounters = (lastPresentId != workload.presentId);]=])
set(after [=[const bool useDifferentCounters = !jfgOffscreen && (lastPresentId != workload.presentId);]=])
string(FIND "${contents}" "${before}" offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Missing RT64 interpolation patch site")
endif()
string(REPLACE "${before}" "${after}" contents "${contents}")
set(before [=[                InterpolatedFrameCounters &curFrameCounters = ext.sharedResources->interpolatedFrames[ext.sharedResources->interpolatedFramesIndex];
                curFrameCounters.skipped = false;]=])
set(after [=[                InterpolatedFrameCounters &curFrameCounters = jfgOffscreen ? jfgOffscreenCounters : ext.sharedResources->interpolatedFrames[ext.sharedResources->interpolatedFramesIndex];
                curFrameCounters.skipped = false;]=])
string(FIND "${contents}" "${before}" offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Missing RT64 interpolation patch site")
endif()
string(REPLACE "${before}" "${after}" contents "${contents}")
set(before [=[                    framesRendered++;]=])
set(after [=[                    jfg::trace_presentation_workload(workload, workloadConfig.targetRate,
                        frame, displayFrames, curFrameWeight);
                    framesRendered++;]=])
string(FIND "${contents}" "${before}" offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Missing RT64 interpolation patch site")
endif()
string(REPLACE "${before}" "${after}" contents "${contents}")
set(before [=[                uint32_t workloadIndex = processCursor;
                curFrame.set(*this, &workloadIndex, 1);]=])
set(after [=[                uint32_t workloadIndex = processCursor;
                uint32_t jfgFrameWorkloads[2] = { workloadIndex, workloadIndex };
                uint32_t jfgFrameWorkloadCount = 1;
                unsigned jfgPairFlags = 1U; // Previous GameFrame is not one workload.
                const auto jfgFrameSnapshot = jfg::presentation_snapshot(&workload);
                if (jfg::native_blur_render_mode() >= 2U && jfgFrameSnapshot &&
                    jfgFrameSnapshot->blur_source && prevFrame.workloads.size() == 1U) {
                    const auto parentIndex = prevFrame.workloads.front();
                    const auto expected = (workloadIndex + workloads.size() - 1U) % workloads.size();
                    auto &parent = workloads[parentIndex];
                    const auto parentSnapshot = jfg::presentation_snapshot(&parent);
                    bool sourceMatches = false;
                    for (uint32_t f=0;f<parent.fbPairCount;++f) {
                        const auto &pair=parent.fbPairs[f];
                        sourceMatches |= pair.colorImage.address==jfgFrameSnapshot->blur_source &&
                            pair.colorImage.width==320U && pair.colorImage.siz==G_IM_SIZ_16b;
                    }
                    jfgPairFlags = (parentIndex != expected ? 2U : 0U) |
                        (!parentSnapshot ? 4U : 0U) |
                        (parentSnapshot && !parentSnapshot->defer_to_blur ? 8U : 0U) |
                        (!jfgFrameSnapshot->blur_parent_serial ? 16U : 0U) |
                        (parentSnapshot && parentSnapshot->presentation_serial != jfgFrameSnapshot->blur_parent_serial ? 32U : 0U) |
                        (parentSnapshot && parentSnapshot->tick != jfgFrameSnapshot->tick ? 64U : 0U) |
                        (!sourceMatches ? 128U : 0U) |
                        (parent.drawData.worldIndices.empty() ? 256U : 0U);
                    if (!jfgPairFlags) {
                        jfgFrameWorkloads[0]=parentIndex;jfgFrameWorkloads[1]=workloadIndex;
                        jfgFrameWorkloadCount=2;
                    }
                    jfg::trace_interpolation("blur-composite",jfgFrameSnapshot->tick,
                        jfgFrameSnapshot->blur_source,jfgFrameSnapshot->blur_target,
                        jfgFrameWorkloadCount,sourceMatches?1U:0U,0.0f,
                        parent.drawData.worldIndices.size(),parentIndex);
                }
                if (jfg::native_blur_render_mode() >= 2U && jfgFrameSnapshot &&
                    jfgFrameSnapshot->blur_source && jfgFrameWorkloadCount != 2U)
                    workload.viOriginalRate = 0U; // No repeated-image FPS claim on failed pairing.
                if (jfg::native_blur_render_mode() == 5U && jfgFrameSnapshot && jfgFrameSnapshot->blur_source)
                    jfg::record_blur_source_audit({jfgFrameSnapshot->tick, workload.workloadId, 2U,
                        jfgFrameSnapshot->blur_source, jfgFrameSnapshot->blur_target,
                        0U, 0U, 0U, 0U, jfgPairFlags});
                curFrame.set(*this, jfgFrameWorkloads, jfgFrameWorkloadCount);]=])
string(FIND "${contents}" "${before}" offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Missing private composite patch site")
endif()
string(REPLACE "${before}" "${after}" contents "${contents}")

set(before [=[                    threadAdvanceBarrier();]=])
set(after [=[                    if (jfg::native_blur_render_mode() >= 2U) {
                        // Protect the entire most-recent GameFrame, including
                        // its retained world task, until the next match/render
                        // completes. The producer cannot cross this boundary.
                        {
                            std::scoped_lock<std::mutex> cursorLock(cursorMutex);
                            barrierCursor = static_cast<int>(curFrame.workloads.front());
                        }
                        cursorCondition.notify_all();
                    }
                    else threadAdvanceBarrier();]=])
string(FIND "${contents}" "${before}" offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Missing private composite patch site")
endif()
string(REPLACE "${before}" "${after}" contents "${contents}")

set(before "                    framebufferRenderer->recordFramebuffer(ext.workloadGraphicsWorker, framebufferIndex++);")
set(after [=[                    // Every interpolated blur output starts with the same
                    // authored destination, not stale contents of a recycled
                    // output slot or the previously blended output phase.
                    const auto jfgBlurSnapshot = jfg::presentation_snapshot(&workload);
                    if (jfg::native_blur_render_mode() >= 2U && curFrame.workloads.size() == 2U &&
                        w == 1U && colorTarget && colorFb && jfgBlurSnapshot &&
                        jfgBlurSnapshot->blur_target == colorImg.address) {
                        struct BlurSeed {
                            std::unique_ptr<RenderTarget> target, previous;
                            uint64_t tick = 0;
                            uint32_t source = 0;
                            bool linked = false;
                            uint64_t workloadId = UINT64_MAX;
                        };
                        thread_local BlurSeed seed;
                        if (!seed.target || seed.target->format != colorTarget->format ||
                            seed.target->multisampling.sampleCount != colorTarget->multisampling.sampleCount) {
                            seed.target = std::make_unique<RenderTarget>(colorImg.address,
                                Framebuffer::Type::Color, colorTarget->multisampling, colorTarget->usesHDR);
                            seed.workloadId = UINT64_MAX; seed.tick = 0; seed.linked = false;
                            seed.previous.reset();
                        }
                        if (seed.target->width != colorTarget->width || seed.target->height != colorTarget->height) {
                            seed.target->setupColor(ext.workloadGraphicsWorker, colorTarget->width, colorTarget->height);
                            seed.workloadId = UINT64_MAX; seed.tick = 0; seed.linked = false;
                            seed.previous.reset();
                        }
                        if (jfg::native_blur_render_mode() == 4U && !seed.previous) {
                            seed.previous = std::make_unique<RenderTarget>(colorImg.address,
                                Framebuffer::Type::Color, colorTarget->multisampling, colorTarget->usesHDR);
                            seed.previous->setupColor(ext.workloadGraphicsWorker, colorTarget->width, colorTarget->height);
                        }
                        auto *commands = ext.workloadGraphicsWorker->commandList.get();
                        if (seed.workloadId != workload.workloadId) {
                            if (jfg::native_blur_render_mode() == 4U) {
                                seed.linked = seed.tick && jfgBlurSnapshot->tick > seed.tick &&
                                    jfgBlurSnapshot->tick - seed.tick <= 4U &&
                                    jfgBlurSnapshot->blur_target == seed.source;
                                std::swap(seed.target, seed.previous);
                                seed.tick = jfgBlurSnapshot->tick; seed.source = jfgBlurSnapshot->blur_source;
                            }
                            // The output override may be a recycled interpolation
                            // slot. Read the actual guest framebuffer's retained
                            // target, never that slot's unrelated older contents.
                            auto &nativeDestination = targetManager.get(fbKey.colorTargetKey, true);
                            RenderTextureBarrier barriers[] = {
                                RenderTextureBarrier(nativeDestination.texture.get(), RenderTextureLayout::COPY_SOURCE),
                                RenderTextureBarrier(seed.target->texture.get(), RenderTextureLayout::COPY_DEST)
                            };
                            commands->barriers(RenderBarrierStage::COPY, barriers, 2U);
                            commands->copyTexture(seed.target->texture.get(), nativeDestination.texture.get());
                            seed.workloadId = workload.workloadId;
                        }
                        {
                            RenderTextureBarrier barriers[] = {
                                RenderTextureBarrier(seed.target->texture.get(), RenderTextureLayout::COPY_SOURCE),
                                RenderTextureBarrier(colorTarget->texture.get(), RenderTextureLayout::COPY_DEST)
                            };
                            commands->barriers(RenderBarrierStage::COPY, barriers, 2U);
                            commands->copyTexture(colorTarget->texture.get(), seed.target->texture.get());
                        }
                        commands->barriers(RenderBarrierStage::GRAPHICS,
                            RenderTextureBarrier(colorTarget->texture.get(), RenderTextureLayout::COLOR_WRITE));
                        colorTarget->markForResolve();
                        if (jfg::native_blur_render_mode() == 4U && seed.linked)
                            jfg::blur_history_blend().draw(ext.workloadGraphicsWorker,
                                *seed.previous, *seed.target, *colorTarget, curFrameWeight);
                    }
                    if (jfg::render_target_size_trace_enabled() && colorTarget && jfgBlurSnapshot &&
                        curFrameWeight >= 1.0f)
                        jfg::trace_interpolation("target-size",jfgBlurSnapshot->tick,
                            colorImg.address,colorImg.width,colorTarget->width,colorTarget->height,
                            curFrameWeight,colorTarget->multisampling.sampleCount,w);
                    framebufferRenderer->recordFramebuffer(ext.workloadGraphicsWorker, framebufferIndex++);
                    // Private visual diagnosis only. Show the freshly rendered
                    // source at its actual GPU resolution. Retain all native
                    // task/resource work; do not interpret this as a fidelity fix.
                    if (jfg::native_blur_render_mode() == 5U && jfgBlurSnapshot && jfgBlurSnapshot->blur_source) {
                        jfg::BlurSourceAuditRow audit{jfgBlurSnapshot->tick, workload.workloadId, 3U,
                            jfgBlurSnapshot->blur_source, jfgBlurSnapshot->blur_target};
                        audit.tiles = static_cast<unsigned>(workload.drawData.callTiles.size());
                        for (const auto &tile : workload.drawData.callTiles)
                            audit.gpu_tiles += tile.tileCopyUsed ? 1U : 0U;
                        if (curFrame.workloads.size() != 2U || w != 1U || !colorTarget ||
                            jfgBlurSnapshot->blur_target != colorImg.address) {
                            audit.flags = 64U;
                        }
                        else {
                            RenderTargetKey sourceKey(jfgBlurSnapshot->blur_source, 320U,
                                G_IM_SIZ_16b, Framebuffer::Type::Color);
                            auto &sourceTarget = targetManager.get(sourceKey);
                            audit.source_width = sourceTarget.width; audit.source_height = sourceTarget.height;
                            audit.target_width = colorTarget->width; audit.target_height = colorTarget->height;
                            audit.flags = (sourceTarget.isEmpty() ? 1U : 0U) |
                                (sourceTarget.texture.get() == colorTarget->texture.get() ? 2U : 0U) |
                                (sourceTarget.width != colorTarget->width ? 4U : 0U) |
                                (sourceTarget.height != colorTarget->height ? 8U : 0U) |
                                (sourceTarget.format != colorTarget->format ? 16U : 0U) |
                                (sourceTarget.multisampling.sampleCount != 1U ||
                                 colorTarget->multisampling.sampleCount != 1U ? 32U : 0U);
                            if (!audit.flags) {
                                auto *commands = ext.workloadGraphicsWorker->commandList.get();
                                RenderTextureBarrier barriers[] = {
                                    RenderTextureBarrier(sourceTarget.texture.get(), RenderTextureLayout::COPY_SOURCE),
                                    RenderTextureBarrier(colorTarget->texture.get(), RenderTextureLayout::COPY_DEST)
                                };
                                commands->barriers(RenderBarrierStage::COPY, barriers, 2U);
                                commands->copyTexture(colorTarget->texture.get(), sourceTarget.texture.get());
                                colorTarget->markForResolve();
                                commands->barriers(RenderBarrierStage::GRAPHICS,
                                    RenderTextureBarrier(sourceTarget.texture.get(), RenderTextureLayout::SHADER_READ));
                            }
                        }
                        jfg::record_blur_source_audit(audit);
                    }]=])
string(FIND "${contents}" "${before}" offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Missing blur feedback seed patch site")
endif()
string(REPLACE "${before}" "${after}" contents "${contents}")

set(before [=[        Thread::setCurrentThreadName("RT64 Workload");]=])
set(after [=[        Thread::setCurrentThreadName("RT64 Workload");
        if (jfg::native_blur_render_mode() == 4U)
            jfg::blur_history_blend().prepare(ext.device,
                ext.createdGraphicsAPI == UserConfiguration::GraphicsAPI::D3D12,
                ext.shaderLibrary->usesHDR);]=])
string(FIND "${contents}" "${before}" offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Missing blur pipeline prewarm patch site")
endif()
string(REPLACE "${before}" "${after}" contents "${contents}")

jfg_video_patch_workload()
set(generated "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64/rt64_workload_queue.cpp")
file(WRITE "${generated}" [=[#include "rt64_interpolation_adapter.hpp"
#include "rt64_blur_history.hpp"
#include "jfg/renderer/blur_source_audit.hpp"
#include "jfg/renderer/resource_worker_profile.hpp"
]=] "${contents}")
jfg_interpolation_replace_source("rt64_workload_queue.cpp" "${generated}")

set(source "${jfg_rt64_root}/src/hle/rt64_present_queue.cpp")
file(SHA256 "${source}" digest)
if(NOT digest STREQUAL "023dc3f4bc74bf6863e37ad1781fb32eaa543a7713bd8b9a3757b2262a1a1e52" AND NOT digest STREQUAL "e024b012b30304b0232581790af6416412264fc40a2b2e00494ba7ed0c842566")
 message(FATAL_ERROR "Pinned RT64 interpolation input differs: src/hle/rt64_present_queue.cpp")
endif()
file(READ "${source}" contents)
set(before [=[swapChainValid = ext.swapChain->present(swapChainIndex, &waitSemaphore, 1);]=])
set(after [=[swapChainValid = ext.swapChain->present(swapChainIndex, &waitSemaphore, 1);
                if (swapChainValid) jfg::frame_diagnostic_state().presented();
                jfg::trace_interpolation("present", present.presentId, viOriginalRate,
                    targetRate, static_cast<unsigned>(i), static_cast<unsigned>(framesToPresent),
                    0.0f, 0U, 0U);]=])
string(FIND "${contents}" "${before}" offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Missing RT64 interpolation patch site")
endif()
string(REPLACE "${before}" "${after}" contents "${contents}")
set(before [=[                    commandList->barriers(RenderBarrierStage::NONE, RenderTextureBarrier(swapChainTexture, RenderTextureLayout::PRESENT));]=])
set(after [=[                    auto jfgCapture = jfg::begin_interpolation_capture(ext.device, commandList,
                        swapChainTexture, ext.swapChain->getWidth(), ext.swapChain->getHeight(),
                        present.presentId, static_cast<unsigned>(i), jfgOutputSample.tick);
                    commandList->barriers(RenderBarrierStage::NONE, RenderTextureBarrier(swapChainTexture, RenderTextureLayout::PRESENT));]=])
string(FIND "${contents}" "${before}" offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Missing RT64 frame capture patch site")
endif()
string(REPLACE "${before}" "${after}" contents "${contents}")
set(before [=[                    ext.presentGraphicsWorker->commandQueue->executeCommandLists(&commandList, 1, &waitSemaphore, 1, &signalSemaphore, 1, ext.presentGraphicsWorker->commandFence.get());
                    ext.presentGraphicsWorker->wait();]=])
set(after [=[                    ext.presentGraphicsWorker->commandQueue->executeCommandLists(&commandList, 1, &waitSemaphore, 1, &signalSemaphore, 1, ext.presentGraphicsWorker->commandFence.get());
                    ext.presentGraphicsWorker->wait();
                    jfg::finish_interpolation_capture(jfgCapture);]=])
string(FIND "${contents}" "${before}" offset)
if(offset EQUAL -1)
 message(FATAL_ERROR "Missing RT64 frame capture completion site")
endif()
string(REPLACE "${before}" "${after}" contents "${contents}")
jfg_video_patch_present()
# A color allocation can become depth after a room/cinematic change. Previous
# VI history cannot authorize displaying that new role as early color output.
jfg_video_replace([=[                            if ((colorFb->addressStart == entry.vi.fbAddress()) && (colorFb->width == entry.fbWidth) && (colorFb->siz == entry.vi.fbSiz()) && entry.vi.compatibleWith(present.screenVI)) {]=]
[=[                            if (colorFb->lastWriteType == Framebuffer::Type::Depth &&
                                colorFb->addressStart == entry.vi.fbAddress() &&
                                colorFb->width == entry.fbWidth && colorFb->siz == entry.vi.fbSiz() &&
                                entry.vi.compatibleWith(present.screenVI)) {
                                jfg::trace_interpolation("present-depth-history-rejected", jfgSequenceTick,
                                    present.screenVI.fbAddress(), colorFb->addressStart,
                                    static_cast<unsigned>(colorFb->lastWriteType), 0U, 0.0f,
                                    present.presentId, h);
                            }
                            if (jfg::early_present_history_match(*colorFb, entry, present.screenVI)) {]=])
jfg_video_replace([=[                RenderTargetKey colorTargetKey(presentFb->addressStart, presentFb->width, presentFb->siz, Framebuffer::Type::Color);]=]
[=[                jfg::trace_interpolation("present-source", jfgSequenceTick,
                    present.screenVI.fbAddress(), presentFb->addressStart,
                    static_cast<unsigned>(presentFb->lastWriteType),
                    static_cast<unsigned>(framesToPresent), 0.0f,
                    present.presentId, presentFb->interpolationEnabled ? 1U : 0U);
                RenderTargetKey colorTargetKey(presentFb->addressStart, presentFb->width, presentFb->siz, Framebuffer::Type::Color);]=])
jfg_video_replace([=[                    if (presentFb->isLastWriteDifferent(Framebuffer::Type::Color)) {]=]
[=[                    if (presentFb->isLastWriteDifferent(Framebuffer::Type::Color)) {
                        jfg::trace_interpolation("present-depth-conversion", jfgSequenceTick,
                            present.screenVI.fbAddress(), presentFb->addressStart,
                            static_cast<unsigned>(presentFb->lastWriteType),
                            static_cast<unsigned>(framesToPresent), 0.0f,
                            present.presentId, present.debuggerFramebuffer.view ? 1U : 0U);]=])
# Capture selected target metadata while this frame still owns its target.
# Do not dereference it after notifying the producer/presenting.
jfg_video_replace([=[                commandList->begin();]=] [=[                if (jfg::native_blur_render_mode() == 5U && colorTarget)
                    jfg::record_blur_source_audit({jfgSequenceTick, present.presentId, 4U,
                        colorTarget->addressForName, 0U, colorTarget->width, colorTarget->height,
                        ext.swapChain->getWidth(), ext.swapChain->getHeight(),
                        static_cast<unsigned>(present.fbOperations.size())});
                commandList->begin();]=])
set(generated "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64/rt64_present_queue.cpp")
file(WRITE "${generated}" [=[#include "jfg/renderer/frame_diagnostics_state.hpp"
#include "jfg/renderer/blur_source_audit.hpp"
#include "rt64_interpolation_capture.hpp"
#include "rt64_present_source.hpp"
]=] "${contents}")
jfg_interpolation_replace_source("rt64_present_queue.cpp" "${generated}")

file(READ "${jfg_rt64_transform_processor_generated}" contents)
string(REPLACE "            DrawData &drawData = workload.drawData;"
    "            DrawData &drawData = workload.drawData;\n            if (jfg::apply_presentation_interpolation(workload, p.prevFrameWeight, p.curFrameWeight)) continue;"
    contents "${contents}")
string(REPLACE "prevFrameValid ? drawData.lerpWorldTransforms.data()"
    "(prevFrameValid || jfg::presentation_snapshot(&workload)) ? drawData.lerpWorldTransforms.data()"
    contents "${contents}")
string(REPLACE "prevFrameValid ? drawData.prevWorldTransforms.data()"
    "(prevFrameValid || jfg::presentation_snapshot(&workload)) ? drawData.prevWorldTransforms.data()"
    contents "${contents}")
file(WRITE "${jfg_rt64_transform_processor_generated}"
    "#include \"rt64_interpolation_adapter.hpp\"\n${contents}")
target_include_directories(rt64 PRIVATE "${PROJECT_SOURCE_DIR}/include"
    "${PROJECT_SOURCE_DIR}/src/renderer" "${jfg_rt64_root}/src/hle")

if(WIN32)
 function(jfg_build_blur_history_shader)
  set(DXC "${jfg_rt64_root}/src/contrib/dxc/bin/x64/dxc.exe")
  set(DXC_DXIL_OPTS "-Wno-ignored-attributes")
  set(DXC_SPV_OPTS "-spirv" "-fspv-target-env=vulkan1.0" "-fvk-use-dx-layout")
  set(input "${PROJECT_SOURCE_DIR}/src/renderer/blur_history.hlsl")
  set(output "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64/jfg_blur_history")
  file(MAKE_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64")
  build_shader_dxil_impl(rt64 "${input}" JfgBlurHistory "${output}" -E PSMain -T ps_6_3)
  build_shader_spirv_impl(rt64 "${input}" JfgBlurHistory "${output}" -E PSMain -T ps_6_3)
  # RT64's target belongs to another CMake directory. Give these local
  # custom commands an explicit target so MSBuild runs them before compilation.
  add_custom_target(jfg_blur_history_shaders
      DEPENDS "${output}.dxil.c" "${output}.spirv.c")
  add_dependencies(rt64 jfg_blur_history_shaders)
 endfunction()
 jfg_build_blur_history_shader()
 target_include_directories(rt64 PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/generated/rt64")
endif()

include("${CMAKE_CURRENT_LIST_DIR}/rt64_framebuffer_diagnostics.cmake")
