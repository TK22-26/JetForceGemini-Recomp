#include "jfg/runtime/rt64_overlay_address.hpp"

namespace jfg {

std::uint32_t translate_rt64_overlay_address(
    const std::uint32_t address,
    const std::uint32_t simulation_rdram_bytes,
    const Rt64OverlayAddressRange& overlay) noexcept {
    constexpr std::uint32_t kPhysicalMask = 0x1FFFFFFFU;
    const std::uint32_t segment = address & 0xE0000000U;
    const bool direct_alias = segment == 0U || segment == 0x80000000U ||
                              segment == 0xA0000000U;
    const std::uint32_t physical = address & kPhysicalMask;

    // Generated overlays whose linked aliases are inside real RDRAM are
    // already present there. Preserve that storage rather than substituting
    // an RT64 shadow copy.
    if (direct_alias && physical < simulation_rdram_bytes) {
        return address;
    }
    if (overlay.extent == 0U) {
        return address;
    }

    if (address >= overlay.linked_base &&
        address - overlay.linked_base < overlay.extent) {
        return overlay.shadow_base + address - overlay.linked_base;
    }

    const std::uint32_t linked_physical =
        overlay.linked_base & kPhysicalMask;
    if (direct_alias && physical >= linked_physical &&
        physical - linked_physical < overlay.extent) {
        return overlay.shadow_base + physical - linked_physical;
    }
    return address;
}

}  // namespace jfg
