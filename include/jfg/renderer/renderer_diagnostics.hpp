#pragma once
#include "graphics_api.hpp"
#include "jfg/runtime/support_log.hpp"
#include <array>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <limits>
namespace jfg {
enum class RendererOperation { present, acquire, resize };
enum class RendererLogDecision { unchanged, record, limit };
// Record first status and changes, not every frame. Each API/operation has an
// independent cap; a failed device cannot flood the shared support log.
struct RendererResultHistory {
    static constexpr unsigned channels = 6, maximum_changes = 16;
    std::array<std::atomic<std::uint64_t>, channels> last;
    std::array<std::atomic<unsigned>, channels> changes{};
    RendererResultHistory() noexcept {
        for (auto& value : last) value.store(UINT64_MAX);
    }
    RendererLogDecision observe(unsigned channel, std::uint32_t result) noexcept {
        if (channel >= channels || last[channel].exchange(result) == result)
            return RendererLogDecision::unchanged;
        unsigned count = changes[channel].load();
        while (count <= maximum_changes) {
            if (changes[channel].compare_exchange_weak(count, count + 1))
                return count < maximum_changes ? RendererLogDecision::record : RendererLogDecision::limit;
        }
        return RendererLogDecision::unchanged;
    }
};
inline void renderer_result(GraphicsApi api, RendererOperation operation, std::uint32_t result) noexcept {
    if ((api != GraphicsApi::d3d12 && api != GraphicsApi::vulkan) ||
        static_cast<unsigned>(operation) > 2) return;
    static RendererResultHistory history;
    const auto decision = history.observe((api == GraphicsApi::vulkan ? 3U : 0U) + static_cast<unsigned>(operation), result);
    if (decision == RendererLogDecision::unchanged) return;
    constexpr const char* operations[] = {"present", "acquire", "resize"};
    char event[96]{};
    if (decision == RendererLogDecision::limit)
        std::snprintf(event, sizeof(event), "renderer_result=%s/%s/limit", graphics_api_name(api).data(), operations[static_cast<unsigned>(operation)]);
    else
        std::snprintf(event, sizeof(event), "renderer_result=%s/%s/0x%08x", graphics_api_name(api).data(), operations[static_cast<unsigned>(operation)], static_cast<unsigned>(result));
    support_event(event);
}
} // namespace jfg
