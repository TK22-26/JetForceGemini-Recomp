#include "jfg/evidence/g2_paired_producer.hpp"
#include "jfg/evidence/g2_private_task_adapter.hpp"

#include <algorithm>
#include <array>

namespace {
constexpr std::array<std::byte, 4> kExpectedProgram{
    std::byte{0x01}, std::byte{0x02}, std::byte{0x03}, std::byte{0x04}};

[[nodiscard]] jfg::evidence::G2PrivateProgramDigest digest(
    const std::span<const std::byte> bytes) {
  jfg::evidence::Sha256 hasher;
  hasher.update(bytes);
  return hasher.finish();
}

[[nodiscard]] bool expected_program(
    const std::span<const std::byte> bytes) noexcept {
  return std::ranges::equal(bytes, kExpectedProgram);
}

[[nodiscard]] std::uint32_t be32(
    const std::span<const std::byte> bytes,
    const std::size_t offset) noexcept {
  return (std::to_integer<std::uint32_t>(bytes[offset]) << 24U) |
         (std::to_integer<std::uint32_t>(bytes[offset + 1U]) << 16U) |
         (std::to_integer<std::uint32_t>(bytes[offset + 2U]) << 8U) |
         std::to_integer<std::uint32_t>(bytes[offset + 3U]);
}

}  // namespace

extern "C" bool jfg_g2_private_graphics_oracle_v2(
    const jfg::evidence::G2PrivateGraphicsOracleInput& input,
    jfg::evidence::G2PrivateGraphicsOracleResult& output) noexcept {
  if (input.task_descriptor.size() != 64U ||
      !expected_program(input.task.active_program) ||
      input.task.command_stream.size() != 8U ||
      input.referenced_regions.size() != 1U ||
      input.referenced_regions[0].id != 0U) {
    return false;
  }
  const std::uint32_t command_address =
      be32(input.task_descriptor, 48U) &
      (jfg::kMaximumGraphicsReferencedMemoryBytes - 1U);
  const auto memory = input.referenced_regions[0].bytes;
  if (command_address > memory.size() ||
      memory.size() - command_address < input.task.command_stream.size() ||
      !std::ranges::equal(
          input.task.command_stream,
          memory.subspan(command_address, input.task.command_stream.size()))) {
    return false;
  }
  const std::uint32_t word0 = be32(input.task.command_stream, 0U);
  const std::uint32_t word1 = be32(input.task.command_stream, 4U);
  if ((word0 >> 24U) != 0xB8U) {
    return false;
  }
  output.bytes.assign(32U, std::byte{0});
  output.bytes[0] = std::byte{3};
  output.bytes[1] = std::byte{0xB8};
  output.bytes[3] = std::byte{1};
  output.bytes[24] = std::byte{0xB8};
  for (std::size_t index = 0U; index < 4U; ++index) {
    output.bytes[28U + index] =
        static_cast<std::byte>(word1 >> ((3U - index) * 8U));
  }
  output.width = 32U;
  output.height = 1U;
  output.row_pitch_bytes = 32U;
  output.bytes_per_pixel = 1U;
  output.execution_count = 1U;
  output.active_program_sha256 = digest(input.task.active_program);
  return true;
}
