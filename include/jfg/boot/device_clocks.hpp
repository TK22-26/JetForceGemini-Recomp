#pragma once
#include <cstdint>
#include <limits>
#include <optional>
namespace jfg::boot {
// Physical clock inputs, independent of presentation FPS and game revision.
// Video frequencies follow the pinned SDK's VI_*_CLOCK constants. Count runs
// at half the 93.75 MHz CPU frequency for both supported TV standards.
// Convert a monotonic clock without assuming a display refresh rate. The
// quotient/remainder form avoids overflowing on long captures.
[[nodiscard]] constexpr std::optional<std::uint64_t> clock_milliseconds(
    std::uint64_t ticks, std::uint32_t frequency) noexcept {
  if (!frequency || frequency > 1000000000U) return {};
  const auto whole = ticks / frequency;
  constexpr auto maximum = (std::numeric_limits<std::uint64_t>::max)();
  if (whole > maximum / 1000U) return {};
  const auto milliseconds = whole * 1000U;
  const auto fraction = (ticks % frequency) * 1000U / frequency;
  if (fraction > maximum - milliseconds) return {};
  return milliseconds + fraction;
}

struct DeviceClocks {
  std::uint32_t count_hz = 0, video_hz = 0;
  [[nodiscard]] constexpr bool valid() const noexcept {
    return count_hz > 0 && count_hz <= 1000000000U && video_hz > 0 && video_hz <= 1000000000U;
  }
};
inline constexpr DeviceClocks kNtscDeviceClocks{46875000U,48681812U};
inline constexpr DeviceClocks kPalDeviceClocks{46875000U,49656530U};
} // namespace jfg::boot
