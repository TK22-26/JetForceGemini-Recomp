#pragma once

#include <cstdint>

namespace jfg {

inline constexpr std::int32_t kXInputLeftStickDeadzone = 7849;
inline constexpr std::int32_t kXInputStickMaximum = 32767;
inline constexpr std::int32_t kN64StickMaximum = 80;

struct N64StickSample {
    std::int8_t x = 0;
    std::int8_t y = 0;

    bool operator==(const N64StickSample&) const = default;
};

[[nodiscard]] N64StickSample scale_xinput_left_stick(
    std::int32_t raw_x,
    std::int32_t raw_y) noexcept;

}  // namespace jfg
