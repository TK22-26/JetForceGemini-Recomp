#include "jfg/evidence/g2_private_task_case.hpp"
#include "jfg/evidence/g2_private_task_adapter.hpp"

#include <array>

namespace {
volatile const char kProbeMarker[] = "jfg_g2_graphics_oracle_probe";
volatile const char kOracleMarker[] = "jfg_g2_graphics_private_oracle_v2";
} // namespace
int main(const int argc, const char *const *argv) {
  try {
    if (kProbeMarker[0] != 'j' || kOracleMarker[0] != 'j')
      return 2;
    const auto identity = jfg::evidence::parse_producer_identity(
        argc, argv, "graphics-tasks", "private-oracle-execution");
    const auto payload = jfg::evidence::read_private_task_case(
        jfg::evidence::PairedCaseFamily::graphics, identity);
    jfg::evidence::G2PrivateTaskCaseCursor cursor(payload);
    const auto descriptor = cursor.blob(64U, 64U, 4U);
    const auto program = cursor.blob(
        4U, jfg::kMaximumGraphicsActiveProgramBytes,
        jfg::kGraphicsInstructionAlignmentBytes);
    const auto data = cursor.blob(4U, jfg::kMaximumGraphicsProgramDataBytes,
                                  jfg::kGraphicsInstructionAlignmentBytes);
    const auto commands = cursor.blob(8U, jfg::kMaximumGraphicsCommandStreamBytes,
                                      jfg::kGraphicsCommandAlignmentBytes);
    const auto memory = cursor.blob(1U, jfg::kMaximumGraphicsReferencedMemoryBytes);
    cursor.finish();
    const std::array<jfg::GraphicsReferencedMemoryRegion, 1> regions{
        {{0U, memory}}};
    jfg::evidence::G2PrivateGraphicsOracleResult result;
    if (!jfg_g2_private_graphics_oracle_v2(
            {descriptor,
             {jfg::GraphicsFamily::bounded_custom, program, data, commands},
             regions},
            result) ||
        result.execution_count != 1U || result.bytes.empty() ||
        result.bytes.size() > jfg::kMaximumGraphicsOutputBytes ||
        result.bytes.size() % 32U != 0U ||
        result.width == 0U || result.height == 0U ||
        result.width > jfg::kMaximumGraphicsOutputDimension ||
        result.height > jfg::kMaximumGraphicsOutputDimension ||
        result.bytes_per_pixel == 0U ||
        result.width >
            jfg::kMaximumGraphicsOutputBytes / result.bytes_per_pixel ||
        result.row_pitch_bytes < result.width * result.bytes_per_pixel ||
        result.row_pitch_bytes > jfg::kMaximumGraphicsOutputBytes ||
        result.height >
            jfg::kMaximumGraphicsOutputBytes / result.row_pitch_bytes ||
        result.bytes.size() != result.row_pitch_bytes * result.height ||
        result.active_program_sha256 !=
            jfg::evidence::g2_private_program_digest(program))
      return 1;
    jfg::evidence::write_artifact("graphics-output-a.bin", result.bytes);
    jfg::evidence::write_artifact("graphics-output-b.bin", result.bytes);
    const std::string observation =
        "{\"case_id\":\"" + identity.case_id +
        "\",\"element_alignment_bytes\":32,\"kind\":\"jfg-g2-graphics-"
        "oracle-observation\",\"payload_byte_count\":" +
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
