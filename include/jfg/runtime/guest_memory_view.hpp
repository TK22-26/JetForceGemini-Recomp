#pragma once
#include <bit>
#include <cmath>
#include <cstdint>
#include <span>
#include <stdexcept>

namespace jfg {
// Checked raw RDRAM access; this type has no knowledge of game revisions.
class GuestMemory {
  std::span<std::uint8_t> bytes_;
  bool swapped_;

public:
  explicit GuestMemory(std::span<std::uint8_t> bytes, bool native_words = true)
      : bytes_(bytes), swapped_(native_words) {
    if (native_words && bytes.size() % 4U != 0U)
      throw std::runtime_error("native mod memory must contain complete words");
  }
  bool valid(std::uint32_t a, std::uint64_t n) const noexcept {
    const auto segment = a & 0xE0000000U;
    const auto offset = a & 0x1FFFFFFFU;
    return (segment == 0x80000000U || segment == 0xA0000000U) &&
           offset <= bytes_.size() && n <= bytes_.size() - offset;
  }
  void require(std::uint32_t a, std::uint64_t n) const {
    if (!valid(a, n))
      throw std::runtime_error("invalid mod memory range");
  }
  std::uint8_t u8(std::uint32_t a) const {
    require(a, 1);
    return bytes_[(a & 0x1FFFFFFFU) ^ (swapped_ ? 3U : 0U)];
  }
  std::uint16_t u16(std::uint32_t a) const {
    require(a, 2);
    return static_cast<std::uint16_t>((u8(a) << 8U) | u8(a + 1U));
  }
  std::int16_t s16(std::uint32_t a) const {
    return std::bit_cast<std::int16_t>(u16(a));
  }
  std::uint32_t u32(std::uint32_t a) const {
    require(a, 4);
    return (static_cast<std::uint32_t>(u16(a)) << 16U) | u16(a + 2U);
  }
  float f32(std::uint32_t a) const {
    const auto value = std::bit_cast<float>(u32(a));
    if (!std::isfinite(value))
      throw std::runtime_error("nonfinite mod coordinate");
    return value;
  }
  void put16(std::uint32_t a, std::uint16_t v) {
    require(a, 2);
    bytes_[(a & 0x1FFFFFFFU) ^ (swapped_ ? 3U : 0U)] =
        static_cast<std::uint8_t>(v >> 8U);
    bytes_[((a + 1U) & 0x1FFFFFFFU) ^ (swapped_ ? 3U : 0U)] =
        static_cast<std::uint8_t>(v);
  }
};
} // namespace jfg
