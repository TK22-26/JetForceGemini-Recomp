#pragma once

#include <cstdint>
#include <unordered_map>

namespace jfg {

// Copied with its graphics task. Only the matching environment fog command and
// colour may use this refinement; damage flashes and other fog uses stay native.
struct DayNightFog {
    bool valid = false;
    std::uint32_t native_coefficients = 0;
    std::uint32_t smooth_coefficients = 0;
    std::uint32_t color = 0;
};

[[nodiscard]] inline DayNightFog make_daynight_fog(
    std::uint32_t elapsed, std::uint32_t duration,
    int near_start, int far_start, int near_end, int far_end,
    int native_near, int native_far, std::uint32_t color) noexcept {
    const auto valid_range = [](int near_value, int far_value) {
        return near_value >= 0 && near_value <= 1018 && far_value >= 5 && far_value <= 1023 && far_value - near_value >= 5;
    };
    if (duration == 0 || duration > 1'000'000 || elapsed >= duration ||
        !valid_range(near_start, far_start) || !valid_range(near_end, far_end) ||
        !valid_range(native_near, native_far)) return {};

    // The original controller uses a 14-bit phase fraction, then discards all
    // fractional distance before gSPFogPosition. Keep that distance precision
    // until the final, much finer signed 16-bit fog coefficients are encoded.
    constexpr std::int64_t unit = 1 << 14;
    const auto t = (std::int64_t(elapsed) * unit) / duration;
    const auto near_value = near_start * unit + (near_end - near_start) * t;
    const auto far_value = far_start * unit + (far_end - far_start) * t;
    if (near_value / unit != native_near || far_value / unit != native_far) return {};
    const auto pack = [](std::int64_t mul, std::int64_t offset) {
        return (std::uint32_t(static_cast<std::uint16_t>(mul)) << 16) |
               static_cast<std::uint16_t>(offset);
    };
    const auto native_span = native_far - native_near;
    const auto native = pack(128000 / native_span,
                             (128000 - 256 * native_near) / native_span);
    const auto span = far_value - near_value;
    const auto smooth = pack((128000 * unit) / span,
                             (128000 * unit - 256 * near_value) / span);
    return {true, native, smooth, color};
}

[[nodiscard]] inline std::uint32_t daynight_fog_command(
    const DayNightFog& fog, std::uint32_t original, std::uint32_t color) noexcept {
    return fog.valid && original == fog.native_coefficients && color == fog.color
        ? fog.smooth_coefficients : original;
}


// The native getter runs before the day/night update, whereas task submission
// runs afterward. Preserve the getter's state with the display list it built;
// rereading live controller globals at submission can alternate native/smooth
// fog whenever a colour component changes.
class DayNightFogFrames {
public:
    void queried(DayNightFog fog) noexcept { query_ = fog; }
    void submit(std::uint32_t list, bool primary, bool eligible) {
        list &= 0x00ffffffU;
        if (eligible && query_.valid) {
            if (submissions_.size() >= 16U) submissions_.clear();
            submissions_[list] = query_;
        } else {
            submissions_.erase(list);
        }
        if (primary) query_ = {};
    }
    [[nodiscard]] DayNightFog take(std::uint32_t list) {
        const auto found = submissions_.find(list & 0x00ffffffU);
        if (found == submissions_.end()) return {};
        const auto fog = found->second;
        submissions_.erase(found);
        return fog;
    }
private:
    DayNightFog query_{};
    std::unordered_map<std::uint32_t, DayNightFog> submissions_;
};

} // namespace jfg
