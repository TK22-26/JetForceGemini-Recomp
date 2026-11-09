#pragma once
#include "hle/rt64_framebuffer_pair.h"
#include "hle/rt64_vi.h"
#include <cstddef>

namespace jfg {
// A depth clear is submitted through SetColorImage on N64. It is not a new
// display image, even if the same address appeared in an earlier scene's VI.
inline bool early_present_pair_candidate(const RT64::FramebufferPair& pair,
                                         bool scene) {
    return !pair.fastPaths.clearDepthOnly &&
        (pair.earlyPresentCandidate() ||
         (scene && pair.colorImage.width >= 320U &&
          pair.colorImage.siz == G_IM_SIZ_16b));
}

// Some JFG tasks bind their depth allocation as color again for readback.
// RT64 then correctly marks the allocation Color, but those pixels are still
// encoded depth. An old cinematic's interpolationEnabled flag must not select
// that readback pass as this scene's display output. Qualify against the
// current workload's depth usage, not only the candidate pass or history.
inline bool early_present_workload_candidate(const RT64::FramebufferPair& pair,
        bool scene, const RT64::FramebufferPair* pairs, std::size_t pairCount) {
    if (!early_present_pair_candidate(pair, scene)) return false;
    for (std::size_t i = 0; i < pairCount; ++i) {
        const auto& other = pairs[i];
        const bool depth = other.depthRead || other.depthWrite ||
            other.fastPaths.clearDepthOnly;
        const auto address = other.fastPaths.clearDepthOnly ?
            other.colorImage.address : other.depthImage.address;
        if (depth && address == pair.colorImage.address) return false;
    }
    return true;
}

// A newly selected display buffer may not yet carry RT64's prior-VI flag.
// It may not have a manager entry until threadRenderFrame creates it.
// Its first continuous scene already has valid endpoints. Permit generating
// those outputs only for the native color shape and current-workload proof;
// presentation itself still chooses the actual VI/history-approved buffer.
inline bool bootstrap_interpolation_target(const RT64::Framebuffer* framebuffer,
        const RT64::FramebufferPair& pair,const RT64::FramebufferPair* pairs,
        std::size_t pairCount,bool scene,bool paused,unsigned sourceRate,bool hasHistory) {
    return scene && !paused && sourceRate>0 && hasHistory &&
        (!framebuffer || (framebuffer->lastWriteType==RT64::Framebuffer::Type::Color &&
         framebuffer->addressStart==pair.colorImage.address && framebuffer->width==320U &&
         framebuffer->siz==G_IM_SIZ_16b)) && pair.colorImage.width==320U &&
        pair.colorImage.fmt==G_IM_FMT_RGBA && pair.colorImage.siz==G_IM_SIZ_16b &&
        early_present_workload_candidate(pair,scene,pairs,pairCount);
}

// An inferred startup target must never outrank a confirmed display target,
// regardless of their draw-list order. Keep the first provisional candidate.
inline bool select_interpolation_target(bool selected,bool provisional,
        bool confirmed,bool bootstrap) {
    return confirmed ? (!selected || provisional) : (!selected && bootstrap);
}

// History proves that an address USED to be displayed, not that the current
// contents are still color. Keep the actual VI/debugger depth display path
// separate; this predicate is only for redirecting early presentation.
inline bool early_present_history_match(const RT64::Framebuffer& framebuffer,
                                        const RT64::VIHistory::Present& history,
                                        const RT64::VI& current) {
    return framebuffer.lastWriteType == RT64::Framebuffer::Type::Color &&
        framebuffer.addressStart == history.vi.fbAddress() &&
        framebuffer.width == history.fbWidth &&
        framebuffer.siz == history.vi.fbSiz() &&
        history.vi.compatibleWith(current);
}
} // namespace jfg
