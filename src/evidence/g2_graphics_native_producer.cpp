#include "jfg/evidence/g2_private_task_case.hpp"
#include "jfg/evidence/g2_private_task_adapter.hpp"

#include <array>
#include <memory>

namespace {
volatile const char kProbeMarker[] = "jfg_g2_graphics_native_probe";
volatile const char kBackendMarker[] = "jfg_g2_graphics_real_task_backend_v2";

[[nodiscard]] std::uint32_t be32(
    const std::span<const std::byte> bytes,
    const std::size_t offset) noexcept {
  if (offset > bytes.size() || bytes.size() - offset < 4U)
    return 0U;
  return (std::to_integer<std::uint32_t>(bytes[offset]) << 24U) |
         (std::to_integer<std::uint32_t>(bytes[offset + 1U]) << 16U) |
         (std::to_integer<std::uint32_t>(bytes[offset + 2U]) << 8U) |
         std::to_integer<std::uint32_t>(bytes[offset + 3U]);
}

class CaptureValidator final : public jfg::GraphicsOutputOracle {
public:
  [[nodiscard]] bool validate(const jfg::GraphicsOutputView &output) override {
    bytes.assign(output.bytes.begin(), output.bytes.end());
    width = output.width;
    height = output.height;
    pitch = output.row_pitch_bytes;
    bytes_per_pixel = output.bytes_per_pixel;
    return !output.bytes.empty();
  }
  std::vector<std::byte> bytes;
  std::size_t width = 0U, height = 0U, pitch = 0U, bytes_per_pixel = 0U;

};

class ObservedBackend final : public jfg::GraphicsTaskBackend {
public:
  explicit ObservedBackend(jfg::GraphicsTaskBackend& backend) noexcept
      : backend_(backend) {}

  [[nodiscard]] jfg::GraphicsBackendCapabilities capabilities() const override {
    return backend_.capabilities();
  }

  [[nodiscard]] jfg::GraphicsBackendReport execute(
      const jfg::GraphicsTaskView& task,
      jfg::GraphicsMemoryBroker& memory) override {
    const auto report = backend_.execute(task, memory);
    access_count = memory.access_count();
    broker_closed = memory.closed();
    return report;
  }

  std::size_t access_count = 0U;
  bool broker_closed = false;

private:
  jfg::GraphicsTaskBackend& backend_;
};

class Completion final : public jfg::GraphicsCompletionSink {
public:
  [[nodiscard]] bool prepare_renderer_complete(std::size_t) override {
    ++prepared;
    return true;
  }
  void commit_renderer_complete(std::size_t) noexcept override { ++committed; }
  std::size_t prepared = 0U, committed = 0U;
};
} // namespace

int main(const int argc, const char *const *argv) {
  try {
    if (kProbeMarker[0] != 'j' || kBackendMarker[0] != 'j')
      return 2;
    const auto identity = jfg::evidence::parse_producer_identity(
        argc, argv, "graphics-tasks", "private-native-execution");
    const auto payload = jfg::evidence::read_private_task_case(
        jfg::evidence::PairedCaseFamily::graphics, identity);
    jfg::evidence::G2PrivateTaskCaseCursor cursor(payload);
    const auto descriptor = cursor.blob(64U, 64U, 4U);
    const auto program = cursor.blob(
        4U, jfg::kMaximumGraphicsActiveProgramBytes,
        jfg::kGraphicsInstructionAlignmentBytes);
    const auto data = cursor.blob(
        4U, jfg::kMaximumGraphicsProgramDataBytes,
        jfg::kGraphicsInstructionAlignmentBytes);
    const auto prefix = cursor.blob(
        8U, jfg::kMaximumGraphicsCommandStreamBytes,
        jfg::kGraphicsCommandAlignmentBytes);
    const auto memory = cursor.blob(
        1U, jfg::kMaximumGraphicsReferencedMemoryBytes);
    cursor.finish();

    const auto command_address = static_cast<std::uint32_t>(
        be32(descriptor, 48U) &
        (jfg::kMaximumGraphicsReferencedMemoryBytes - 1U));
    const std::array<jfg::GraphicsReferencedMemoryRegion, 1> regions{
        {{0U, memory}}};
    std::unique_ptr<jfg::evidence::G2PrivateGraphicsBackend> private_backend(
        jfg_g2_graphics_bounded_backend_v2({descriptor, command_address}));
    if (!private_backend)
      return 1;
    ObservedBackend backend(*private_backend);
    CaptureValidator oracle;
    Completion completion;
    const auto result = jfg::GraphicsTaskBridge{}.submit(
        {jfg::GraphicsFamily::bounded_custom, program, data, prefix}, regions,
        backend, oracle, completion);
    const auto stats = private_backend->stats();
    const auto program_digest = jfg::evidence::hex_digest(program);
    if (!result.ok() || !backend.broker_closed || backend.access_count == 0U ||
        completion.prepared != 1U || completion.committed != 1U ||
        oracle.bytes.empty() ||
        stats.abi_version != jfg::evidence::kG2PrivateTaskAdapterAbiVersion ||
        stats.backend_execution_count != 1U ||
        stats.program_identity_check_count != 1U ||
        stats.active_program_sha256 !=
            jfg::evidence::g2_private_program_digest(program))
      return 1;
    jfg::evidence::write_artifact("graphics-output.bin", oracle.bytes);
    const std::string observation =
        "{\"bytes_per_pixel\":" + std::to_string(oracle.bytes_per_pixel) +
        ",\"case_id\":\"" + identity.case_id +
        "\",\"command_count\":" +
        std::to_string(result.parsed_command_count) +
        ",\"completion_events\":[\"output-committed\",\"completion-prepared\","
        "\"completion-committed\"],\"declared_region_count\":1,\"family\":"
        "\"f3ddkr-gbi\",\"height\":" + std::to_string(oracle.height) +
        ",\"kind\":\"jfg-g2-graphics-native-observation\",\"memory_access_"
        "count\":" + std::to_string(backend.access_count) +
        ",\"observed_region_count\":1,\"output_byte_count\":" +
        std::to_string(oracle.bytes.size()) + ",\"output_sha256\":\"" +
        jfg::evidence::hex_digest(oracle.bytes) +
        "\",\"parsed_command_count\":" +
        std::to_string(result.parsed_command_count) +
        ",\"program_evidence_sha256\":\"" +
        program_digest +
        "\",\"renderer_path\":\"project-bounded-semantic\",\"row_pitch_bytes\":" +
        std::to_string(oracle.pitch) +
        ",\"schema_version\":2,\"subject_sha256\":\"" +
        identity.subject_sha256 +
        "\",\"unsupported_command_count\":0,\"width\":" +
        std::to_string(oracle.width) + "}";
    return jfg::evidence::emit_envelope(identity, observation);
  } catch (...) {
    return 1;
  }
}
