#include "jfg/boot/reset_handoff.hpp"

#include <cstdint>
#include <iostream>
#include <string_view>
#include <vector>

namespace {
constexpr std::uint32_t kBase = 0x80000000U;
int failures = 0;

void check(bool condition, std::string_view message) {
  if (!condition) {
    ++failures;
    std::cerr << "FAIL: " << message << '\n';
  }
}

void put(std::vector<std::uint8_t> &memory, std::uint32_t address,
         std::uint32_t word) {
  const std::size_t offset = address - kBase;
  memory[offset] = static_cast<std::uint8_t>(word >> 24U);
  memory[offset + 1U] = static_cast<std::uint8_t>(word >> 16U);
  memory[offset + 2U] = static_cast<std::uint8_t>(word >> 8U);
  memory[offset + 3U] = static_cast<std::uint8_t>(word);
}

std::uint32_t get(const std::vector<std::uint8_t> &memory,
                  std::uint32_t address) {
  const std::size_t offset = address - kBase;
  return (std::uint32_t{memory[offset]} << 24U) |
         (std::uint32_t{memory[offset + 1U]} << 16U) |
         (std::uint32_t{memory[offset + 2U]} << 8U) | memory[offset + 3U];
}

void test_clear_loop_and_transfer() {
  std::vector<std::uint8_t> memory(0x1000U);
  constexpr std::uint32_t entry = 0x80000400U;
  put(memory, entry, 0x3C088000U);       // lui t0, 0x8000
  put(memory, entry + 4U, 0x35080800U);  // ori t0, t0, 0x800
  put(memory, entry + 8U, 0x24090002U);  // addiu t1, zero, 2
  put(memory, entry + 12U, 0xAD000000U); // sw zero, 0(t0)
  put(memory, entry + 16U, 0x25080004U); // addiu t0, t0, 4
  put(memory, entry + 20U, 0x2529FFFFU); // addiu t1, t1, -1
  put(memory, entry + 24U, 0x1520FFFCU); // bne t1, zero, clear
  put(memory, entry + 28U, 0x00000000U); // nop delay slot
  put(memory, entry + 32U, 0x3C1F8000U); // lui ra, 0x8000
  put(memory, entry + 36U, 0x37FF0900U); // ori ra, ra, 0x900
  put(memory, entry + 40U, 0x03E00008U); // jr ra
  put(memory, entry + 44U, 0x00000000U); // nop delay slot
  put(memory, 0x80000800U, 0xFFFFFFFFU);
  put(memory, 0x80000804U, 0xFFFFFFFFU);
  const auto result = jfg::boot::interpret_reset_handoff(memory);
  check(result.ok() && result.transfer_target == 0x80000900U,
        "clear loop transfers through jr");
  check(get(memory, 0x80000800U) == 0U && get(memory, 0x80000804U) == 0U,
        "clear loop writes both words");
  check(result.gpr[0] == 0U && result.gpr[8] == 0x80000808U &&
            result.gpr[9] == 0U && result.gpr[31] == 0x80000900U,
        "handoff preserves loop temporaries and jr source");
}

void test_jr_delay_slot_side_effect() {
  std::vector<std::uint8_t> memory(0x1000U);
  put(memory, 0x80000400U, 0x3C1D8000U); // lui sp, 0x8000
  put(memory, 0x80000404U, 0x37BD1000U); // ori sp, sp, 0x1000
  put(memory, 0x80000408U, 0x3C1F8000U); // lui ra, 0x8000
  put(memory, 0x8000040CU, 0x37FF0900U); // ori ra, ra, 0x900
  put(memory, 0x80000410U, 0x03E00008U); // jr ra
  put(memory, 0x80000414U, 0x27BDFFE0U); // addiu sp, sp, -32
  const auto result = jfg::boot::interpret_reset_handoff(memory);
  check(result.ok() && result.transfer_target == 0x80000900U &&
            result.gpr[29] == 0x80000FE0U,
        "jr delay slot preserves updated stack pointer for handoff");
}

void test_rejections() {
  std::vector<std::uint8_t> memory(0x100U);
  put(memory, kBase, 0x8C010000U);
  check(jfg::boot::interpret_reset_handoff(memory, kBase).error ==
            jfg::boot::ResetHandoffError::unsupported_instruction,
        "unsupported instruction");
  put(memory, kBase, 0xAC010001U);
  check(jfg::boot::interpret_reset_handoff(memory, kBase).error ==
            jfg::boot::ResetHandoffError::unaligned_access,
        "unaligned store");
  check(jfg::boot::interpret_reset_handoff(memory, kBase + 1U).error ==
            jfg::boot::ResetHandoffError::unaligned_access,
        "unaligned fetch");
  put(memory, kBase, 0xAC010000U);
  check(jfg::boot::interpret_reset_handoff(memory, 0x80000100U).error ==
            jfg::boot::ResetHandoffError::fetch_out_of_range,
        "out of bounds fetch");
  check(jfg::boot::interpret_reset_handoff(memory, kBase).error ==
            jfg::boot::ResetHandoffError::store_out_of_range,
        "out of bounds store");
  put(memory, kBase, 0x1400FFFFU);
  check(jfg::boot::interpret_reset_handoff(memory, kBase, 1U).error ==
            jfg::boot::ResetHandoffError::budget_exhausted,
        "budget exhaustion");
}

void test_addi_overflow_and_addiu_wrap() {
  std::vector<std::uint8_t> memory(0x100U);
  put(memory, kBase, 0x3C017FFFU);      // lui at, 0x7fff
  put(memory, kBase + 4U, 0x3421FFFFU); // ori at, at, 0xffff
  put(memory, kBase + 8U, 0x20220001U); // addi v0, at, 1
  check(jfg::boot::interpret_reset_handoff(memory, kBase).error ==
            jfg::boot::ResetHandoffError::arithmetic_overflow,
        "addi positive overflow");
  put(memory, kBase, 0x3C018000U);      // lui at, 0x8000
  put(memory, kBase + 4U, 0x2022FFFFU); // addi v0, at, -1
  check(jfg::boot::interpret_reset_handoff(memory, kBase).error ==
            jfg::boot::ResetHandoffError::arithmetic_overflow,
        "addi negative overflow");
  put(memory, kBase + 4U, 0x2422FFFFU); // addiu v0, at, -1
  put(memory, kBase + 8U, 0x00400008U); // jr v0 (unaligned after wrap)
  put(memory, kBase + 12U, 0U);
  check(jfg::boot::interpret_reset_handoff(memory, kBase).error ==
            jfg::boot::ResetHandoffError::unaligned_access,
        "addiu wraps before checked jr");
}

void test_mips_gpr_sign_extension() {
  check(jfg::boot::sign_extend_mips32(0x12345678U) == 0x0000000012345678ULL,
        "positive MIPS gpr sign extension");
  check(jfg::boot::sign_extend_mips32(0x80000000U) == 0xFFFFFFFF80000000ULL,
        "negative MIPS gpr sign extension");
}

} // namespace

int main() {
  test_clear_loop_and_transfer();
  test_jr_delay_slot_side_effect();
  test_rejections();
  test_addi_overflow_and_addiu_wrap();
  test_mips_gpr_sign_extension();
  return failures == 0 ? 0 : 1;
}
