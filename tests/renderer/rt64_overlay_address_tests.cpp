#include "jfg/runtime/rt64_overlay_address.hpp"

#include <cstdint>
#include <cstdlib>

namespace {

[[noreturn]] void fail() {
    std::abort();
}

void require(const bool condition) {
    if (!condition) {
        fail();
    }
}

void test_overlay_alias_translation() {
    constexpr jfg::Rt64OverlayAddressRange overlay{
        0x00E00000U, 0x48C0U, 0x0043AD80U};
    require(jfg::translate_rt64_overlay_address(
                0x80E040B8U, 0x00400000U, overlay) == 0x0043EE38U);
    require(jfg::translate_rt64_overlay_address(
                0xA0E040B8U, 0x00400000U, overlay) == 0x0043EE38U);
    require(jfg::translate_rt64_overlay_address(
                0x00E040B8U, 0x00400000U, overlay) == 0x0043EE38U);
    require(jfg::translate_rt64_overlay_address(
                0x00E048C0U, 0x00400000U, overlay) == 0x00E048C0U);
}

void test_real_rdram_alias_wins() {
    constexpr jfg::Rt64OverlayAddressRange overlay{
        0x00260000U, 0x2000U, 0x00410000U};
    require(jfg::translate_rt64_overlay_address(
                0x80260120U, 0x00400000U, overlay) == 0x80260120U);
    require(jfg::translate_rt64_overlay_address(
                0x00260120U, 0x00400000U, overlay) == 0x00260120U);
}

void test_empty_and_unrelated_ranges_are_untouched() {
    require(jfg::translate_rt64_overlay_address(
                0x00E00010U, 0x00400000U,
                {0x00E00000U, 0U, 0x0043AD80U}) == 0x00E00010U);
    require(jfg::translate_rt64_overlay_address(
                0x00F00010U, 0x00400000U,
                {0x00E00000U, 0x48C0U, 0x0043AD80U}) == 0x00F00010U);
}

void test_absolute_overlay_edge_with_active_scene_segment() {
    constexpr jfg::Rt64OverlayAddressRange overlay{0x02500000U, 0x2100U, 0x00490000U};
    const auto translated = jfg::translate_rt64_overlay_address(
        0x02501EC0U, 0x00400000U, overlay);
    require(translated == 0x00491EC0U);
    // The menu's synthetic high byte aliases segment 2; that scene base must
    // not redirect the two-command RDP state list into unrelated guest data.
    require(jfg::resolve_rt64_display_list_edge(0x02501EC0U, translated,
                0x00280000U) == 0x00491EC0U);
    require(jfg::resolve_rt64_display_list_edge(0x02501EC0U, translated,
                0U) == 0x00491EC0U);
    // Genuine scene and KSEG edges retain their original DMA semantics.
    require(jfg::resolve_rt64_display_list_edge(0x02000128U, 0x02000128U,
                0x80280000U) == 0x00280128U);
    require(jfg::resolve_rt64_display_list_edge(0x80296530U, 0x80296530U,
                0x80000000U) == 0x00296530U);
}

}  // namespace

int main() {
    test_absolute_overlay_edge_with_active_scene_segment();
    test_overlay_alias_translation();
    test_real_rdram_alias_wins();
    test_empty_and_unrelated_ranges_are_untouched();
    return 0;
}
