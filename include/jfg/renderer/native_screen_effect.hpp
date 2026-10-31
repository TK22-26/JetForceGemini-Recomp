#pragma once
#include <cstdint>
namespace jfg {
// The original fxScreenEffect materials, shared by night vision and the damage
// tint. They sample RGBA16 screen strips, never CPU-softened intensity shadows.
constexpr bool native_screen_effect_material(std::uint32_t mode_high,
    std::uint32_t mode_low,std::uint32_t combine_low,std::uint32_t combine_high) noexcept {
    return (mode_high==0x00100C0FU && mode_low==0x03024000U &&
            combine_low==0xFC11FEE5U && combine_high==0xFFFFFC3EU) ||
           (mode_high==0x00000C0FU && mode_low==0x0F0A4000U &&
            combine_low==0xFC11FE23U && combine_high==0xFFFFFDFEU);
}
} // namespace jfg
