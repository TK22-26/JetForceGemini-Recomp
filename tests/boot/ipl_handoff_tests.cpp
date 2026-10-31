#include "jfg/boot/ipl_handoff.hpp"
#include <algorithm>
#include <array>
#include <vector>

int main() {
  std::vector<std::uint8_t> ram(0x400000U, 0xa5U);
  std::vector<std::uint8_t> rom(0x1000U);
  for (std::size_t i = 0; i < rom.size(); ++i)
    rom[i] = static_cast<std::uint8_t>((i * 17U + i / 256U) & 255U);
  const auto before = ram;
  if (jfg::boot::initialize_6105_handoff(std::span(ram).first(0x3fffffU), rom) || ram != before)
    return 1;
  if (jfg::boot::initialize_6105_handoff(ram, std::span(rom).first(0xfffU)) || ram != before)
    return 2;
  if (!jfg::boot::initialize_6105_handoff(ram, rom)) return 3;
  auto expected = before;
  // Distinct fixture data detects incorrect source offsets and byte swapping.
  std::copy_n(rom.begin() + 0x838U, 4U, expected.begin() + 0x2e8U);
  std::copy_n(rom.begin() + 0x73cU, 4U, expected.begin() + 0x2fb1f4U);
  std::copy_n(rom.begin() + 0x750U, 4U, expected.begin() + 0x2fe1c0U);
  expected[0x310U] = 0; expected[0x311U] = 0;
  expected[0x312U] = 0x17U; expected[0x313U] = 0xd9U;
  if (ram != expected) return 4;
  // Guest checks consume the high residues. Initialization is a boot operation,
  // not a recurring repair of gameplay state.
  ram[0x2fb1f4U] = 0;
  if (rom[0x73cU] == 0 || ram[0x2e8U] != rom[0x838U]) return 5;
  return 0;
}
