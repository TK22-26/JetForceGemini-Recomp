#pragma once
#include <cstdint>

namespace jfg::boot {
// NEC VR4300 manual chapter 17, ERET. Only its Status transition; PC selection
// and LLbit clearing are separate responsibilities. This is not a full ERET.
constexpr std::uint32_t status_after_exception_return(std::uint32_t saved) {
  return (saved & 4U) != 0U ? saved & ~4U : saved & ~2U;
}
} // namespace jfg::boot
