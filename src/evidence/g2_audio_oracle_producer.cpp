#include "jfg/evidence/g2_private_task_case.hpp"
#include "jfg/evidence/g2_private_task_adapter.hpp"
#include "jfg/runtime/audio_task_bridge.hpp"

namespace {
volatile const char kProbeMarker[] = "jfg_g2_audio_oracle_probe";
volatile const char kOracleMarker[] = "jfg_g2_audio_private_oracle_v2";
} // namespace
int main(const int argc, const char *const *argv) {
  try {
    if (kProbeMarker[0] != 'j' || kOracleMarker[0] != 'j')
      return 2;
    const auto identity = jfg::evidence::parse_producer_identity(
        argc, argv, "audio-tasks", "private-oracle-execution");
    const auto payload = jfg::evidence::read_private_task_case(
        jfg::evidence::PairedCaseFamily::audio, identity);
    jfg::evidence::G2PrivateTaskCaseCursor cursor(payload);
    const auto output_address = cursor.u32();
    const auto output_size = cursor.u32();
    const auto descriptor = cursor.blob(64U, 64U, 4U);
    const auto program = cursor.blob(
        4U, jfg::kMaximumAudioActiveProgramBytes,
        jfg::kAudioInstructionAlignmentBytes);
    const auto data = cursor.blob(4U, jfg::kMaximumAudioProgramDataBytes,
                                  jfg::kAudioInstructionAlignmentBytes);
    const auto commands = cursor.blob(8U, jfg::kMaximumAudioCommandStreamBytes,
                                      jfg::kAudioCommandAlignmentBytes);
    const auto initial_memory =
        cursor.blob(1U, jfg::kMaximumAudioReferencedRegionBytes);
    cursor.finish();
    if (output_size == 0U || output_size > jfg::kMaximumAudioOutputBytes ||
        output_size % jfg::kAudioOutputFrameBytes != 0U)
      return 1;
    jfg::evidence::G2PrivateAudioOracleResult result;
    if (!jfg_g2_private_audio_oracle_v2(
            {descriptor, program, data, commands, initial_memory,
             output_address, output_size},
            result) ||
        result.execution_count != 1U || result.bytes.size() != output_size ||
        result.bytes.size() % jfg::kAudioOutputFrameBytes != 0U ||
        result.active_program_sha256 !=
            jfg::evidence::g2_private_program_digest(program))
      return 1;
    jfg::evidence::write_artifact("audio-output-a.bin", result.bytes);
    jfg::evidence::write_artifact("audio-output-b.bin", result.bytes);
    const std::string observation =
        "{\"case_id\":\"" + identity.case_id +
        "\",\"element_alignment_bytes\":4,\"kind\":\"jfg-g2-audio-oracle-"
        "observation\",\"payload_byte_count\":" +
        std::to_string(result.bytes.size()) + ",\"payload_sha256\":\"" +
        jfg::evidence::hex_digest(result.bytes) +
        "\",\"program_evidence_sha256\":\"" +
        jfg::evidence::hex_digest(program) +
        "\",\"schema_version\":2,\"subject_sha256\":\"" +
        identity.subject_sha256 + "\"}";
    return jfg::evidence::emit_envelope(identity, observation);
  } catch (...) {
    return 1;
  }
}
