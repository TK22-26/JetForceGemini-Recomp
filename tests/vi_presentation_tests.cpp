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
    const auto normal = jfg::vi_presentation_size(0x006C02ECU, 0x002501FFU);
    check(normal.width == 320 && normal.height == 240);
    const auto wide = jfg::vi_presentation_size(0x006C02ECU, 0x00330195U);
    check(wide.width == 320 && wide.height == 180);
    // Vertical centering changes both endpoints; it must not change aspect.
    const auto shifted = jfg::vi_presentation_size(0x006C02ECU, 0x004301A5U);
    check(shifted.width == wide.width && shifted.height == wide.height);
    check(!jfg::vi_presentation_size(0, 0x002501FFU).valid());
    check(!jfg::vi_presentation_size(0x02EC006CU, 0x002501FFU).valid());
    check(!jfg::vi_presentation_size(0x006C02ECU, 0x01FF0025U).valid());
    return 0;
}
