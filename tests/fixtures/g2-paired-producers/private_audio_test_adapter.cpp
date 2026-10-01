#include "jfg/evidence/g2_paired_producer.hpp"
#include "jfg/evidence/g2_private_task_adapter.hpp"

#include <algorithm>
#include <array>
#include <new>
#include <vector>

namespace {
constexpr std::array<std::byte, 4> kExpectedProgram{
    std::byte{0x11}, std::byte{0x12}, std::byte{0x13}, std::byte{0x14}};

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

class TestAudioProgram final : public jfg::evidence::G2PrivateAudioProgram {
public:
  TestAudioProgram(const std::size_t output_size,
                   const jfg::evidence::G2PrivateProgramDigest& program_digest)
      noexcept
      : output_size_(output_size), program_digest_(program_digest) {}

  [[nodiscard]] jfg::AudioRspProgramReport execute(
      const jfg::AudioBackendTaskView& task,
      jfg::AudioMemoryAccess& memory) override {
    jfg::AudioRspProgramReport report{};
    if (task.variant != jfg::AudioProgramVariant::primary ||
        !expected_program(task.active_program) ||
        task.output_size != output_size_ || output_size_ == 0U) {
      report.exit_reason = jfg::AudioRspExitReason::unsupported;
      report.unsupported_command_count = 1U;
      return report;
    }
    std::vector<std::byte> output(output_size_);
    if (!memory.read(0U, 0U, output) || !memory.write_output(0U, output)) {
      return report;
    }
    stats_ = {
        jfg::evidence::kG2PrivateTaskAdapterAbiVersion,
        1U,
        1U,
        0U,
        1U,
        1U,
        program_digest_,
    };
    report.exit_reason = jfg::AudioRspExitReason::broke;
    report.parse_complete = true;
    report.selected_variant = jfg::AudioProgramVariant::primary;
    report.parsed_command_count =
        task.command_stream.size() / jfg::kAudioCommandAlignmentBytes;
    report.input_read_operation_count = 1U;
    report.input_bytes_read = output_size_;
    report.output_write_operation_count = 1U;
    report.output_bytes_written = output_size_;
    return report;
  }

  [[nodiscard]] jfg::evidence::G2PrivateAudioProgramStats stats()
      const noexcept override {
    return stats_;
  }

private:
  std::size_t output_size_ = 0U;
  jfg::evidence::G2PrivateProgramDigest program_digest_{};
  jfg::evidence::G2PrivateAudioProgramStats stats_{};
};
}  // namespace

extern "C" jfg::evidence::G2PrivateAudioProgram*
jfg_g2_private_audio_program_v2(
    const jfg::evidence::G2PrivateAudioProgramInput& input) noexcept {
  if (input.task_descriptor.size() != 64U ||
      !expected_program(input.active_program) || input.program_data.empty() ||
      input.output_size == 0U) {
    return nullptr;
  }
  return new (std::nothrow)
      TestAudioProgram(input.output_size, digest(input.active_program));
}

extern "C" bool jfg_g2_private_audio_fallback_v2(
    const jfg::evidence::G2PrivateAudioFallbackInput& input,
    jfg::evidence::G2PrivateAudioFallbackStats& output) noexcept {
  if (input.task_descriptor.size() != 64U ||
      !expected_program(input.active_program) || input.program_data.empty() ||
      input.command_stream.empty() || input.initial_memory.empty() ||
      input.output_size == 0U) {
    return false;
  }
  output = {
      jfg::evidence::kG2PrivateTaskAdapterAbiVersion,
      1U,
      1U,
      1U,
      0U,
      jfg::kAudioOutputFrameBytes,
      1U,
      digest(input.active_program),
  };
  return true;
}

extern "C" bool jfg_g2_private_audio_oracle_v2(
    const jfg::evidence::G2PrivateAudioOracleInput& input,
    jfg::evidence::G2PrivateAudioOracleResult& output) noexcept {
  if (input.task_descriptor.size() != 64U ||
      !expected_program(input.active_program) || input.program_data.empty() ||
      input.command_stream.empty() || input.output_size == 0U ||
      input.output_size > input.initial_memory.size()) {
    return false;
  }
  output.bytes.assign(input.initial_memory.begin(),
                      input.initial_memory.begin() +
                          static_cast<std::ptrdiff_t>(input.output_size));
  output.execution_count = 1U;
  output.active_program_sha256 = digest(input.active_program);
  return true;
}
