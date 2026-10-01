#include "jfg/evidence/g2_private_task_adapter.hpp"
#include "jfg/evidence/g2_private_task_case.hpp"

#include <array>
#include <memory>

namespace {
volatile const char kProbeMarker[] = "jfg_g2_audio_native_probe";
volatile const char kBackendMarker[] = "jfg_g2_audio_generated_adapter_v2";

class CaptureValidator final : public jfg::AudioOutputValidator {
public:
  [[nodiscard]] bool validate(const std::span<const std::byte> output) override {
    bytes.assign(output.begin(), output.end());
    return !bytes.empty();
  }

  std::vector<std::byte> bytes;
};

class Completion final : public jfg::AudioTaskCompletionSink {
public:
  [[nodiscard]] bool prepare_sp_complete(const jfg::AudioTaskResult &) override {
    ++prepared;
    return true;
  }
  void commit_sp_complete(const jfg::AudioTaskResult &) noexcept override {
    ++committed;
  }
  std::size_t prepared = 0U, committed = 0U;
};
} // namespace

int main(const int argc, const char *const *argv) {
  try {
    if (kProbeMarker[0] != 'j' || kBackendMarker[0] != 'j')
      return 2;
    const auto identity = jfg::evidence::parse_producer_identity(
        argc, argv, "audio-tasks", "private-native-execution");
    const auto payload = jfg::evidence::read_private_task_case(
        jfg::evidence::PairedCaseFamily::audio, identity);
    jfg::evidence::G2PrivateTaskCaseCursor cursor(payload);
    const std::uint32_t output_address = cursor.u32();
    const std::size_t output_size = cursor.u32();
    const auto descriptor = cursor.blob(64U, 64U, 4U);
    const auto program = cursor.blob(
        4U, jfg::kMaximumAudioActiveProgramBytes,
        jfg::kAudioInstructionAlignmentBytes);
    const auto data = cursor.blob(
        4U, jfg::kMaximumAudioProgramDataBytes,
        jfg::kAudioInstructionAlignmentBytes);
    const auto commands = cursor.blob(
        8U, jfg::kMaximumAudioCommandStreamBytes,
        jfg::kAudioCommandAlignmentBytes);
    const auto initial_memory = cursor.blob(
        1U, jfg::kMaximumAudioReferencedRegionBytes);
    cursor.finish();
    if (output_size == 0U || output_size > jfg::kMaximumAudioOutputBytes ||
        output_size % jfg::kAudioOutputFrameBytes != 0U)
      return 1;

    std::vector<std::byte> output(output_size, std::byte{0xcc});
    std::vector<std::byte> committed_memory(
        initial_memory.size(), std::byte{0xcc});
    const std::array regions{
        jfg::AudioReferencedRegion{initial_memory, committed_memory},
    };
    std::unique_ptr<jfg::evidence::G2PrivateAudioProgram> private_program(
        jfg_g2_private_audio_program_v2(
            {descriptor, program, data, output_address, output_size}));
    if (!private_program)
      return 1;
    auto* const observer = private_program.get();
    jfg::AudioRuntimeTaskWorker worker;
    const auto installation = worker.install(std::move(private_program));
    if (!installation.ok())
      return 1;
    CaptureValidator validator;
    Completion completion;
    const auto result = worker.submit(
        installation.installation,
        {jfg::AudioProgramVariant::primary, program, data, commands, regions,
         output},
        validator, completion);
    const auto stats = observer->stats();
    const auto uninstall = worker.uninstall(installation.installation);
    if (!result.ok() || uninstall != jfg::AudioWorkerError::none ||
        stats.abi_version != jfg::evidence::kG2PrivateTaskAdapterAbiVersion ||
        stats.generated_entry_count != 1U ||
        stats.input_read_operation_count == 0U ||
        stats.output_write_operation_count == 0U ||
        stats.program_identity_check_count != 1U ||
        stats.active_program_sha256 !=
            jfg::evidence::g2_private_program_digest(program) ||
        completion.prepared != 1U || completion.committed != 1U ||
        !std::ranges::equal(output, validator.bytes))
      return 1;

    jfg::evidence::G2PrivateAudioFallbackStats fallback{};
    if (!jfg_g2_private_audio_fallback_v2(
            {descriptor, program, data, commands, initial_memory,
             output_address, output_size},
            fallback) ||
        fallback.abi_version !=
            jfg::evidence::kG2PrivateTaskAdapterAbiVersion ||
        fallback.generated_entry_count != 1U ||
        fallback.broker_write_count == 0U ||
        fallback.unsupported_return_count != 1U ||
        fallback.completion_count != 0U ||
        fallback.rolled_back_byte_count == 0U ||
        fallback.program_identity_check_count != 1U ||
        fallback.active_program_sha256 !=
            jfg::evidence::g2_private_program_digest(program))
      return 1;

    jfg::evidence::write_artifact("audio-output.bin", output);
    const std::string observation =
        "{\"case_id\":\"" + identity.case_id +
        "\",\"frame_alignment_bytes\":4,\"kind\":\"jfg-g2-audio-native-"
        "observation\",\"output_byte_count\":" +
        std::to_string(output.size()) + ",\"output_sha256\":\"" +
        jfg::evidence::hex_digest(output) +
        "\",\"primary\":{\"broker_read_count\":" +
        std::to_string(stats.input_read_operation_count) +
        ",\"broker_write_count\":" +
        std::to_string(stats.region_write_operation_count +
                       stats.output_write_operation_count) +
        ",\"completion_count\":1,\"completion_events\":[\"output-committed\","
        "\"completion-prepared\",\"completion-committed\"],\"declared_region_"
        "count\":1,\"generated_entry_count\":1,\"observed_region_count\":1,"
        "\"parsed_command_count\":" +
        std::to_string(result.scheduled.task.parsed_command_count) +
        ",\"unsupported_command_count\":0},\"program_evidence_sha256\":\"" +
        jfg::evidence::hex_digest(program) +
        "\",\"schema_version\":2,\"secondary_fallback\":{\"broker_write_count\":" +
        std::to_string(fallback.broker_write_count) +
        ",\"completion_count\":0,\"generated_entry_count\":1,\"rolled_back_byte_"
        "count\":" + std::to_string(fallback.rolled_back_byte_count) +
        ",\"unsupported_return_count\":1},\"subject_sha256\":\"" +
        identity.subject_sha256 + "\"}";
    return jfg::evidence::emit_envelope(identity, observation);
  } catch (...) {
    return 1;
  }
}
