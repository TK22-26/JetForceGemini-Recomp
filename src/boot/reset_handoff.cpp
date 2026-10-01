#include "jfg/boot/reset_handoff.hpp"

#include <array>
#include <climits>

namespace jfg::boot {
namespace {
constexpr std::uint32_t kBase = 0x80000000U;
bool offset(const std::uint32_t address, const std::size_t size,
            std::size_t &output) noexcept {
  if (address < kBase)
    return false;
  const std::uint64_t value = static_cast<std::uint64_t>(address - kBase);
  if (value > size || 4U > size - value)
    return false;
  output = static_cast<std::size_t>(value);
  return true;
}
bool load(std::span<std::uint8_t> memory, const std::uint32_t pc,
          std::uint32_t &word, bool &unaligned) noexcept {
  std::size_t off = 0;
  unaligned = (pc & 3U) != 0U;
  if (unaligned || !offset(pc, memory.size(), off))
    return false;
  word = (std::uint32_t{memory[off]} << 24U) |
         (std::uint32_t{memory[off + 1U]} << 16U) |
         (std::uint32_t{memory[off + 2U]} << 8U) | memory[off + 3U];
  return true;
}
bool store(std::span<std::uint8_t> memory, const std::uint32_t address,
           const std::uint32_t value, bool &unaligned) noexcept {
  std::size_t off = 0;
  unaligned = (address & 3U) != 0U;
  if (unaligned || !offset(address, memory.size(), off))
    return false;
  memory[off] = static_cast<std::uint8_t>(value >> 24U);
  memory[off + 1U] = static_cast<std::uint8_t>(value >> 16U);
  memory[off + 2U] = static_cast<std::uint8_t>(value >> 8U);
  memory[off + 3U] = static_cast<std::uint8_t>(value);
  return true;
}

bool add_pc(const std::uint32_t pc, const std::int64_t displacement,
            std::uint32_t &result) noexcept {
  const std::int64_t value = static_cast<std::int64_t>(pc) + displacement;
  if (value < 0 || value > UINT32_MAX) {
    return false;
  }
  result = static_cast<std::uint32_t>(value);
  return true;
}
} // namespace

ResetHandoffResult
interpret_reset_handoff(std::span<std::uint8_t> memory, std::uint32_t entry,
                        const std::size_t instruction_budget) noexcept {
  std::array<std::uint32_t, 32> r{};
  ResetHandoffResult result{};
  const auto finish = [&]() noexcept {
    r[0] = 0U;
    result.gpr = r;
    return result;
  };
  std::uint32_t pc = entry;
  bool execute_delay = false;
  bool delayed_return = false;
  std::uint32_t delayed_pc = 0;
  while (result.instructions < instruction_budget) {
    std::uint32_t instruction = 0;
    bool unaligned = false;
    if (!load(memory, pc, instruction, unaligned)) {
      result.error = unaligned ? ResetHandoffError::unaligned_access
                               : ResetHandoffError::fetch_out_of_range;
      result.fault_address = pc;
      return finish();
    }
    ++result.instructions;
    const auto op = instruction >> 26U;
    const auto rs = (instruction >> 21U) & 31U;
    const auto rt = (instruction >> 16U) & 31U;
    const auto rd = (instruction >> 11U) & 31U;
    const auto imm = static_cast<std::int16_t>(instruction);
    bool branch = false;
    std::uint32_t target = 0;
    if (instruction == 0U) {
    } else if (op == 0x0FU)
      r[rt] = (instruction & 0xFFFFU) << 16U; // LUI
    else if (op == 0x08U || op == 0x09U) {    // ADDI(U)
      const std::int64_t sum =
          static_cast<std::int64_t>(static_cast<std::int32_t>(r[rs])) + imm;
      if (op == 0x08U && (sum < INT32_MIN || sum > INT32_MAX)) {
        result.error = ResetHandoffError::arithmetic_overflow;
        result.fault_address = pc;
        result.instruction = instruction;
        return finish();
      }
      r[rt] = static_cast<std::uint32_t>(sum);
    } else if (op == 0x0DU)
      r[rt] = r[rs] | (instruction & 0xFFFFU); // ORI
    else if (op == 0x2BU) {                    // SW
      const auto address =
          r[rs] + static_cast<std::uint32_t>(static_cast<std::int32_t>(imm));
      if (!store(memory, address, r[rt], unaligned)) {
        result.error = unaligned ? ResetHandoffError::unaligned_access
                                 : ResetHandoffError::store_out_of_range;
        result.fault_address = address;
        result.instruction = instruction;
        return finish();
      }
    } else if (op == 0x05U) { // BNE
      branch = true;
      const auto displacement = static_cast<std::int64_t>(imm) * 4;
      std::uint32_t next = 0U;
      if (!add_pc(pc, 4, next) ||
          !add_pc(next, r[rs] == r[rt] ? 4 : displacement, target)) {
        result.error = ResetHandoffError::arithmetic_overflow;
        result.fault_address = pc;
        result.instruction = instruction;
        return finish();
      }
    } else if (op == 0U && (instruction & 0x3FU) == 0x08U && rt == 0U &&
               rd == 0U) { // JR
      branch = true;
      target = r[rs];
      if ((target & 3U) != 0U) {
        result.error = ResetHandoffError::unaligned_access;
        result.fault_address = target;
        result.instruction = instruction;
        return finish();
      }
    } else {
      result.error = ResetHandoffError::unsupported_instruction;
      result.fault_address = pc;
      result.instruction = instruction;
      return finish();
    }
    if (execute_delay && branch) {
      result.error = ResetHandoffError::unsupported_instruction;
      result.fault_address = pc;
      result.instruction = instruction;
      return finish();
    }
    r[0] = 0U;
    if (execute_delay) {
      if (delayed_return) {
        result.transfer_target = delayed_pc;
        return finish();
      }
      execute_delay = false;
      pc = delayed_pc;
    } else if (branch) {
      execute_delay = true;
      delayed_return = op == 0U;
      delayed_pc = target;
      if (!add_pc(pc, 4, pc)) {
        result.error = ResetHandoffError::arithmetic_overflow;
        result.fault_address = pc;
        result.instruction = instruction;
        return finish();
      }
    } else {
      if (!add_pc(pc, 4, pc)) {
        result.error = ResetHandoffError::arithmetic_overflow;
        result.fault_address = pc;
        result.instruction = instruction;
        return finish();
      }
    }
  }
  result.error = ResetHandoffError::budget_exhausted;
  result.fault_address = pc;
  return finish();
}
} // namespace jfg::boot
