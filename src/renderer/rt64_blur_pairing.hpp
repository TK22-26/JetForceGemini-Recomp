#pragma once
#include "hle/rt64_workload.h"
#include <cstdint>

namespace jfg {
// N64 depth clears temporarily bind Z as an RGBA16 color image. They do not
// offer a second scene to the later blur pass. A fill-only screen clear is
// likewise not a source: real drawing must establish the source image.
inline std::uint32_t blur_world_source(const RT64::Workload& workload) {
    std::uint32_t source = 0U;
    for (std::uint32_t f = 0; f < workload.fbPairCount; ++f) {
        const auto& pair = workload.fbPairs[f];
        if (pair.colorImage.width != 320U || pair.colorImage.fmt != G_IM_FMT_RGBA ||
            pair.colorImage.siz != G_IM_SIZ_16b || pair.drawColorRect.isEmpty() ||
            pair.fillRectOnly || pair.fastPaths.clearDepthOnly)
            continue;
        if (source && source != pair.colorImage.address) return 0U;
        source = pair.colorImage.address;
    }
    return source;
}
} // namespace jfg
