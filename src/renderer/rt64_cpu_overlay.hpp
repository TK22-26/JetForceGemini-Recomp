#pragma once
// CPU screen edits belong to the game's VI buffer, which can be older than
// SkipBuffering's scene. Retain only the changed pixels, with bounded lifetime.
#include "hle/rt64_state.h"
#include "jfg/renderer/interpolation_bridge.hpp"
#include <array>
#include <memory>
#include <mutex>
namespace jfg {
struct CpuOverlayFrame {
    RT64::FramebufferChangePool pool;
    std::uint64_t id = 0, tick = 0;
    std::uint32_t address = 0, width = 0, height = 0;
    bool valid = false;
};
struct CpuOverlayStorage {
    std::mutex mutex;
    std::array<std::shared_ptr<CpuOverlayFrame>, 3> frames;
};
inline CpuOverlayStorage& cpu_overlay_storage() {
    static CpuOverlayStorage storage; return storage;
}
inline void release_cpu_overlays() {
    auto& storage = cpu_overlay_storage();
    const std::scoped_lock lock(storage.mutex);
    for (auto& frame : storage.frames) frame.reset();
}
inline std::shared_ptr<const CpuOverlayFrame> cpu_overlay_for(
        std::uint32_t address, std::uint64_t tick) {
    auto& storage = cpu_overlay_storage();
    const std::scoped_lock lock(storage.mutex);
    std::shared_ptr<const CpuOverlayFrame> result;
    for (const auto& frame : storage.frames) {
        if (frame && frame->valid && frame->address == address &&
            frame->tick <= tick && tick - frame->tick <= 2U &&
            (!result || frame->tick > result->tick)) result = frame;
    }
    return result;
}
inline void preserve_cpu_overlay(RT64::State& state, std::uint64_t tick) {
    if (state.ext.enhancementConfig->presentation.mode !=
            RT64::EnhancementConfiguration::Presentation::Mode::SkipBuffering) return;
    for (const auto& op : state.drawFbOperations) {
        if (op.type != RT64::FramebufferOperation::Type::WriteChanges) continue;
        const auto* fb = state.framebufferManager.find(op.writeChanges.address);
        if (!fb || fb->lastWriteFmt != G_IM_FMT_RGBA || fb->siz != G_IM_SIZ_16b ||
            fb->width != 320U || fb->height != 240U) continue;
        bool screen = false;
        for (const auto& entry : state.viHistory.history) {
            if (entry.vi.fbAddress() == fb->addressStart && entry.fbWidth == fb->width &&
                entry.vi.fbSiz() == fb->siz && entry.vi.compatibleWith(state.lastScreenVI)) {
                screen = true; break;
            }
        }
        if (!screen) continue;
        auto& workload = state.ext.workloadQueue->workloads[state.ext.workloadQueue->writeCursor];
        const auto* source = workload.fbChangePool.get(op.writeChanges.id);
        if (!source || !source->used || source->type != RT64::FramebufferChange::Type::Color) continue;
        auto& storage = cpu_overlay_storage();
        std::shared_ptr<CpuOverlayFrame> frame;
        {
            const std::scoped_lock lock(storage.mutex);
            std::shared_ptr<CpuOverlayFrame>* oldest = nullptr;
            for (auto& slot : storage.frames) {
                if (!slot) { slot = std::make_shared<CpuOverlayFrame>(); oldest = &slot; break; }
                if (slot.use_count() == 1 && (!oldest || slot->tick < (*oldest)->tick)) oldest = &slot;
            }
            if (!oldest) continue; // Never overwrite a mask still used by the GPU.
            frame = *oldest;
            frame->valid = false;
        }
        auto* worker = state.ext.framebufferGraphicsWorker;
        frame->pool.reset();
        auto& dest = frame->pool.use(worker, source->type, source->width, source->height,
            state.ext.shaderLibrary->usesHDR);
        {
            RT64::RenderWorkerExecution execution(worker);
            RenderTextureBarrier barriers[] = {
                RenderTextureBarrier(source->pixelTexture.get(), RenderTextureLayout::COPY_SOURCE),
                RenderTextureBarrier(source->booleanTexture.get(), RenderTextureLayout::COPY_SOURCE),
                RenderTextureBarrier(dest.pixelTexture.get(), RenderTextureLayout::COPY_DEST),
                RenderTextureBarrier(dest.booleanTexture.get(), RenderTextureLayout::COPY_DEST)
            };
            worker->commandList->barriers(RenderBarrierStage::COPY, barriers, 4U);
            worker->commandList->copyTexture(dest.pixelTexture.get(), source->pixelTexture.get());
            worker->commandList->copyTexture(dest.booleanTexture.get(), source->booleanTexture.get());
        }
        {
            const std::scoped_lock lock(storage.mutex);
            frame->id = dest.id; frame->tick = tick; frame->address = fb->addressStart;
            frame->width = fb->width; frame->height = fb->height; frame->valid = true;
        }
        trace_interpolation("cpu-overlay-retained", tick, fb->addressStart,
            state.lastScreenVI.fbAddress(), 0U, 0U, 0.0f, fb->width, fb->height);
    }
}
}
