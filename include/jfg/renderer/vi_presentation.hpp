#pragma once

#include <cstdint>

namespace jfg {

// Apply libultra feature requests to VI_CONTROL. A simultaneous ON/OFF
// request resolves to OFF; unspecified features and unrelated bits survive.
[[nodiscard]] constexpr std::uint32_t vi_apply_special_features(
    std::uint32_t control, std::uint32_t mode_control,
    std::uint32_t features) noexcept {
    constexpr std::uint32_t controls[] = {0x8U, 0x4U, 0x10U};
    for (unsigned i = 0; i < 3; ++i) {
        if ((features & (1U << (i * 2U))) != 0U) control |= controls[i];
        if ((features & (2U << (i * 2U))) != 0U) control &= ~controls[i];
    }
    if ((features & 0x40U) != 0U) control = (control | 0x10000U) & ~0x300U;
    if ((features & 0x80U) != 0U)
        control = (control & ~0x10300U) | (mode_control & 0x300U);
    return control;
}

struct ViPresentationSize {
    std::uint32_t width = 0U;
    std::uint32_t height = 0U;
    [[nodiscard]] constexpr bool valid() const noexcept {
        return width != 0U && height != 0U;
    }
};

// The supported NTSC game keeps a 320x240 source buffer in its widescreen
// mode and scans it into 180 display lines. Source dimensions therefore
// cannot determine the displayed aspect. Account for the VI filtering rows
// using the same two-row/four-line alignment as framebuffer sizing.
[[nodiscard]] constexpr ViPresentationSize vi_presentation_size(
    std::uint32_t horizontal_start, std::uint32_t vertical_start) noexcept {
    const auto left = (horizontal_start >> 16U) & 0x3FFU;
    const auto right = horizontal_start & 0x3FFU;
    const auto top = (vertical_start >> 16U) & 0x3FFU;
    const auto bottom = vertical_start & 0x3FFU;
    if (left == 0U || right <= left || bottom <= top) return {};
    return {(right - left) / 2U, ((bottom - top) / 2U + 4U) / 4U * 4U};
}

} // namespace jfg
