#pragma once
#include <optional>
#include <string_view>
namespace jfg {
// Stable values shared by persisted settings and the launcher IPC protocol.
enum class GraphicsApi { automatic = 0, d3d12 = 1, vulkan = 2 };
inline constexpr bool valid_graphics_api(GraphicsApi api) noexcept {
    return api == GraphicsApi::automatic || api == GraphicsApi::d3d12 || api == GraphicsApi::vulkan;
}
inline constexpr std::string_view graphics_api_name(GraphicsApi api) noexcept {
    switch (api) {
    case GraphicsApi::automatic: return "auto";
    case GraphicsApi::d3d12: return "d3d12";
    case GraphicsApi::vulkan: return "vulkan";
    }
    return "invalid";
}
inline constexpr std::optional<GraphicsApi> parse_graphics_api(std::string_view value) noexcept {
    if (value == "auto") return GraphicsApi::automatic;
    if (value == "d3d12") return GraphicsApi::d3d12;
    if (value == "vulkan") return GraphicsApi::vulkan;
    return std::nullopt;
}
} // namespace jfg
