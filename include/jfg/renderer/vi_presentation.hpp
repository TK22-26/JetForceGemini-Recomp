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

// The qualified original frontGetScreenMode in all three revisions reads bit
// 30 of the persistent display options. Bit 29 selects source resolution.
// Cinematics can temporarily select a wider VI without changing this preference.
[[nodiscard]] constexpr ViPresentationSize game_display_canvas(
    std::uint32_t frontend_options) noexcept {
    return {320U, (frontend_options & 0x40000000U) != 0U ? 180U : 240U};
}

// Display geometry is measured in scanout units, independent of framebuffer
// resolution. PAL's 576 active lines occupy the same TV height as NTSC/MPAL's
// 480 lines. Return an exact aspect pair (not framebuffer pixel dimensions),
// preserving native crop and centering without rounding PAL's 6:5 correction.
// See libdragon's PAL-NTSC-support documentation and Nintendo VI chapter 30.
// Retain the existing two-row/four-line filtering alignment at the scanout edge.
[[nodiscard]] constexpr ViPresentationSize vi_presentation_size(
    std::uint32_t horizontal_start, std::uint32_t vertical_start,
    std::uint32_t vertical_sync) noexcept {
    const auto left = (horizontal_start >> 16U) & 0x3FFU;
    const auto right = horizontal_start & 0x3FFU;
    const auto top = (vertical_start >> 16U) & 0x3FFU;
    const auto bottom = vertical_start & 0x3FFU;
    if (left == 0U || right <= left || bottom <= top) return {};
    const auto lines=vertical_sync&0x3FFU;
    const bool pal=lines>=600U && lines<=650U;
    const bool ntsc_or_mpal=lines>=500U && lines<=550U;
    if(!pal && !ntsc_or_mpal)return {};
    const auto width=(right-left)/2U;
    const auto height=((bottom-top)/2U+4U)/4U*4U;
    return pal ? ViPresentationSize{width*6U,height*5U} :
                 ViPresentationSize{width,height};
}

} // namespace jfg
