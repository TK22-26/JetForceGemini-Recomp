#include "jfg/renderer/vi_presentation.hpp"
#include <cstdint>
#include <cstdlib>

static void check(bool ok) { if (!ok) std::abort(); }

int main() {
    using jfg::vi_apply_special_features;
    // The original game requests gamma off, divot on, and dither filtering on.
    check(vi_apply_special_features(0x311EU, 0x311EU, 0x52U) == 0x13016U);
    check(vi_apply_special_features(0x13016U, 0x311EU, 0x80U) == 0x3116U);
    check(vi_apply_special_features(0x13016U, 0x311EU, 0xC0U) == 0x3116U);
    check(vi_apply_special_features(0xFFFFFFFFU, 0x311EU, 0xFFU) == 0xFFFEFDE3U);
    for (std::uint32_t feature = 0; feature < 256; ++feature) {
        const auto control = vi_apply_special_features(0xF012U, 0x320EU, feature);
        check((control & ~0x1031CU) == (0xF012U & ~0x1031CU));
        check(vi_apply_special_features(control, 0x320EU, feature) == control);
        check(vi_apply_special_features(control, 0x320EU, 0x80000000U) == control);
    }
    // The saved option owns the canvas. Hi-res and every unrelated option
    // bit must leave its aspect unchanged, even while the VI is cinematic.
    for (unsigned bit = 0; bit < 32; ++bit) {
        const auto canvas = jfg::game_display_canvas(1U << bit);
        check(canvas.width == 320);
        check(canvas.height == (bit == 30 ? 180U : 240U));
        check(jfg::game_display_canvas((1U << bit) | 0x40000000U).height == 180);
    }
    check(jfg::game_display_canvas(0).height == 240);
    check(jfg::game_display_canvas(0xBFFFFFFFU).height == 240);
    check(jfg::game_display_canvas(0xFFFFFFFFU).height == 180);
    const auto cinematic = jfg::vi_presentation_size(0x006C02ECU, 0x006101C3U, 525U);
    check(cinematic.width == 320 && cinematic.height == 180);
    // Preserve a 4:3 container around the naturally letterboxed cinematic.
    check(jfg::game_display_canvas(0).height > cinematic.height);
    const auto normal = jfg::vi_presentation_size(0x006C02ECU, 0x002501FFU, 525U);
    check(normal.width == 320 && normal.height == 240);
    const auto wide = jfg::vi_presentation_size(0x006C02ECU, 0x00330195U, 525U);
    check(wide.width == 320 && wide.height == 180);
    // Vertical centering changes both endpoints; it must not change aspect.
    const auto shifted = jfg::vi_presentation_size(0x006C02ECU, 0x004301A5U, 525U);
    check(shifted.width == wide.width && shifted.height == wide.height);
    check(!jfg::vi_presentation_size(0, 0x002501FFU, 525U).valid());
    check(!jfg::vi_presentation_size(0x02EC006CU, 0x002501FFU, 525U).valid());
    check(!jfg::vi_presentation_size(0x006C02ECU, 0x01FF0025U, 525U).valid());
    // Full PAL scanout and NTSC/MPAL have the same 4:3 display aspect.
    const auto pal_full=jfg::vi_presentation_size(0x00800300U,0x002D0269U,625U);
    check(pal_full.valid()&&pal_full.width*3U==pal_full.height*4U);
    // Actual observed PAL Goldwood and cinematic VI ranges retain their crop.
    const auto pal_game=jfg::vi_presentation_size(0x00800300U,0x00370261U,625U);
    const auto pal_movie=jfg::vi_presentation_size(0x00800300U,0x00730225U,625U);
    check(pal_game.width==1920U&&pal_game.height==1400U);
    check(pal_movie.width==1920U&&pal_movie.height==1100U);
    check(pal_game.width*3U>pal_game.height*4U);
    check(pal_movie.width*pal_game.height>pal_game.width*pal_movie.height);
    const auto pal_shift=jfg::vi_presentation_size(0x00800300U,0x00470271U,626U);
    check(pal_shift.width==pal_game.width&&pal_shift.height==pal_game.height);
    check(!jfg::vi_presentation_size(0x00800300U,0x00370261U,0U).valid());
    return 0;
}
