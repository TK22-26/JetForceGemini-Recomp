#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <span>

namespace jfg::boot {

enum class ResetHandoffError : std::uint8_t {
  none,
  fetch_out_of_range,
  unaligned_access,
  unsupported_instruction,
  store_out_of_range,
  arithmetic_overflow,
  budget_exhausted,
};

[[nodiscard]] constexpr std::uint64_t
sign_extend_mips32(const std::uint32_t value) noexcept {
  return (value & 0x80000000U) == 0U ? value : 0xFFFFFFFF00000000ULL | value;
}

struct ResetHandoffResult {
  ResetHandoffError error = ResetHandoffError::none;
  std::uint32_t fault_address = 0;
  std::uint32_t instruction = 0;
  std::uint32_t transfer_target = 0;
  std::array<std::uint32_t, 32> gpr{};
  std::size_t instructions = 0;
  [[nodiscard]] bool ok() const noexcept {
    return error == ResetHandoffError::none;
  }
};

// Executes only the independently-authored, small reset handoff subset. rdram
// is byte-linear big-endian guest storage; production converts its generated
// native-word storage before calling this bounded interpreter.
[[nodiscard]] ResetHandoffResult
interpret_reset_handoff(std::span<std::uint8_t> rdram,
                        std::uint32_t entry = 0x80000400U,
                        std::size_t instruction_budget = 4096U) noexcept;

} // namespace jfg::boot
