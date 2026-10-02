#include "jfg/runtime/input_stick.hpp"

#include <algorithm>
#include <cmath>

namespace jfg {

N64StickSample scale_xinput_left_stick(const std::int32_t raw_x,
                                       const std::int32_t raw_y,
                                       const std::int32_t deadzone) noexcept {
    const auto effective_deadzone = std::clamp(deadzone, 0, 30000);
    const double x = static_cast<double>(std::clamp(
        raw_x, -kXInputStickMaximum, kXInputStickMaximum));
    const double y = static_cast<double>(std::clamp(
        raw_y, -kXInputStickMaximum, kXInputStickMaximum));
    const double magnitude = std::hypot(x, y);
    if (magnitude <= static_cast<double>(effective_deadzone)) {
        return {};
    }

    const double unit_x = x / magnitude;
    const double unit_y = y / magnitude;
    const double largest_unit_component =
        (std::max)(std::abs(unit_x), std::abs(unit_y));
    const double outer_radius =
        static_cast<double>(kXInputStickMaximum) / largest_unit_component;
    const double travel = std::clamp(
        (magnitude - static_cast<double>(effective_deadzone)) /
            (outer_radius - static_cast<double>(effective_deadzone)),
        0.0, 1.0);
    const double output_radius =
        static_cast<double>(kN64StickMaximum) / largest_unit_component;
    const auto output_x = static_cast<std::int32_t>(
        std::lround(unit_x * output_radius * travel));
    const auto output_y = static_cast<std::int32_t>(
        std::lround(unit_y * output_radius * travel));
    return {
        static_cast<std::int8_t>(std::clamp(
            output_x, -kN64StickMaximum, kN64StickMaximum)),
        static_cast<std::int8_t>(std::clamp(
            output_y, -kN64StickMaximum, kN64StickMaximum)),
    };
}

}  // namespace jfg
