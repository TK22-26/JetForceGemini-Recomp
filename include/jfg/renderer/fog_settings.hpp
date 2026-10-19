#pragma once
#include <atomic>
#include <cstdint>
namespace jfg {
inline std::atomic<unsigned>& fog_strength_preference() {
  static std::atomic<unsigned> value{100};return value;
}
inline void configure_fog_strength(unsigned percent) noexcept {
  if(percent<=100)fog_strength_preference().store(percent,std::memory_order_relaxed);
}
// Preserve fog/blend modes. Scale signed depth coefficients, not vertex alpha.
// 100 keeps native coefficients bit-for-bit; 0 produces zero fog alpha.
inline constexpr std::uint32_t fog_coefficients(std::uint32_t original,unsigned percent) noexcept {
  if(percent>=100)return original;
  const auto mul=static_cast<std::int16_t>(original>>16);
  const auto offset=static_cast<std::int16_t>(original&0xffff);
  return (std::uint32_t(static_cast<std::uint16_t>(std::int32_t(mul)*int(percent)/100))<<16) |
         std::uint16_t(std::int32_t(offset)*int(percent)/100);
}
}
