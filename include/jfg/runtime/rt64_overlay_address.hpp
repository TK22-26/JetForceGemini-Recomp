#pragma once

#include <cstdint>

namespace jfg {

struct Rt64OverlayAddressRange final {
    std::uint32_t linked_base = 0U;
    std::uint32_t extent = 0U;
    std::uint32_t shadow_base = 0U;
};

// Maps KSEG or physical aliases of a generated overlay into its RT64-only
// shadow. Genuine addresses inside simulation-owned RDRAM always win.
[[nodiscard]] std::uint32_t translate_rt64_overlay_address(
    std::uint32_t address,
    std::uint32_t simulation_rdram_bytes,
    const Rt64OverlayAddressRange& overlay) noexcept;

// Resolve an edge after overlay translation. A translated shadow is absolute;
// a genuine segmented edge still uses the scene's configured segment base.
[[nodiscard]] constexpr std::uint32_t resolve_rt64_display_list_edge(
    std::uint32_t original, std::uint32_t translated,
    std::uint32_t segment_base) noexcept {
    const auto address = translated != original
        ? translated : segment_base + (original & 0x00FFFFFFU);
    return address & 0x007FFFF8U;
}

}  // namespace jfg
