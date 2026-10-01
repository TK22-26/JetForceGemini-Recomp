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

}  // namespace

int main() {
    test_overlay_alias_translation();
    test_real_rdram_alias_wins();
    test_empty_and_unrelated_ranges_are_untouched();
    return 0;
}
