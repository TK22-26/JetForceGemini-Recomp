#pragma once
#include <cstdint>
namespace jfg {
enum class BlurMode : std::uint32_t { off, reduced, original };
inline constexpr bool valid_blur_mode(BlurMode mode) noexcept {
    return mode == BlurMode::off || mode == BlurMode::reduced || mode == BlurMode::original;
}
// The recognized native composite mixes current source alpha with retained
// destination (1-alpha). Reduced retains one quarter of that authored history.
// This coefficient is applied to the native draw, independent of output FPS.
inline constexpr std::uint8_t blur_source_alpha(BlurMode mode, std::uint8_t native_alpha) noexcept {
    if (mode == BlurMode::off) return 255U;
    if (mode == BlurMode::reduced)
        return static_cast<std::uint8_t>(255U - (255U - native_alpha + 2U) / 4U);
    return native_alpha;
}
inline constexpr std::uint32_t blur_color_word(BlurMode mode, std::uint32_t word) noexcept {
    return (word & 0xffffff00U) | blur_source_alpha(mode, static_cast<std::uint8_t>(word));
}
} // namespace jfg
