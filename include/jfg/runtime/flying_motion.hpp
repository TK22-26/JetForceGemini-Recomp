#pragma once
// Independently authored time integration for the supported game's flying
// squad movement class. Velocity remains in legacy per-tick units so native
// steering, collision responses and velocity-dependent AI retain their units.
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace jfg::flight {
// Candidate reference: three NTSC VIs per legacy movement tick (20 Hz).
// Presentation frequency never participates in this clock.
inline constexpr float reference_vis = 3.0f;
inline float ticks(unsigned elapsed_vis) noexcept {
  return static_cast<float>(elapsed_vis) / reference_vis;
}
inline bool supported(unsigned movement, unsigned death) noexcept {
  return movement == 5U && death == 1U;
}
inline float damp(float velocity, float retention, float elapsed) noexcept {
  return elapsed == 1.0f ? velocity * retention :
      velocity * std::pow(retention, elapsed);
}
// Fractional extension of the original "accelerate, then move" integrator.
// Composes exactly for constant acceleration; one tick reproduces the original.
inline float accelerated_distance(float before, float after, float elapsed) noexcept {
  return elapsed == 1.0f ? after :
      elapsed * before + (elapsed + 1.0f) * 0.5f * (after - before);
}
// Sum of the damped velocity over a fractional number of legacy ticks.
// This is the geometric-series extension, not velocity-at-end times dt.
inline float damped_distance(float before, float retention, float elapsed) noexcept {
  if (elapsed == 1.0f) return before * retention;
  return before * retention * (-std::expm1(elapsed * std::log(retention))) /
      (1.0f - retention);
}
inline std::uint16_t approach_angle(std::uint16_t before, std::uint16_t target,
                                   float elapsed) noexcept {
  const auto difference = static_cast<std::int16_t>(target - before);
  const float limit = 1000.0f * elapsed;
  const float delta = std::clamp(static_cast<float>(difference), -limit, limit);
  return static_cast<std::uint16_t>(static_cast<int>(before) +
      static_cast<int>(std::lround(delta)));
}
} // namespace jfg::flight
