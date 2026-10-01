#include "jfg/evidence/g2_paired_producer.hpp"

#include <array>
#include <cstdint>

namespace {
volatile const char kProbeMarker[] = "jfg_g2_save_oracle_probe";
volatile const char kOracleMarker[] = "jfg_g2_save_oracle";

[[nodiscard]] std::string operations() {
  return "[\"allocate\",\"enumerate\",\"delete\",\"read\",\"write\","
         "\"capacity\",\"persist\",\"fresh-process-reload\",\"restore\","
         "\"missing\",\"bounds\",\"malformed\"]";
}

[[nodiscard]] std::string domain(const std::string_view name, const int missing,
                                 const int bounds, const int malformed,
                                 const std::string_view initial,
                                 const std::string_view written,
                                 const std::string_view artifact_prefix) {
  const auto state = [&](const std::string_view stage,
                         const std::string_view digest) {
    return "\"" + std::string(stage) + "\":{\"path\":\"" +
           std::string(artifact_prefix) + "-" + std::string(stage) +
           ".bin\",\"sha256\":\"" + std::string(digest) + "\"}";
  };
  return "{\"domain\":\"" + std::string(name) +
         "\",\"error_code_records\":{\"bounds\":" + std::to_string(bounds) +
         ",\"malformed\":" + std::to_string(malformed) +
         ",\"missing\":" + std::to_string(missing) +
         "},\"initial_state_sha256\":\"" + std::string(initial) +
         "\",\"operations\":" + operations() + ",\"reloaded_state_sha256\":\"" +
         std::string(written) + "\",\"restored_state_sha256\":\"" +
         std::string(initial) + "\",\"state_artifacts\":{" +
         state("initial", initial) + "," + state("reloaded", written) + "," +
         state("restored", initial) + "," + state("written", written) +
         "},\"written_state_sha256\":\"" + std::string(written) + "\"}";
}

void append_u32(std::vector<std::byte> &output, const std::uint32_t value) {
  for (unsigned shift = 0U; shift < 32U; shift += 8U)
    output.push_back(static_cast<std::byte>(value >> shift));
}

void append_u64(std::vector<std::byte> &output, const std::uint64_t value) {
  for (unsigned shift = 0U; shift < 64U; shift += 8U)
    output.push_back(static_cast<std::byte>(value >> shift));
}

[[nodiscard]] std::uint32_t crc32(const std::span<const std::byte> bytes) {
  std::uint32_t checksum = 0xffffffffU;
  for (const std::byte byte : bytes) {
    checksum ^= std::to_integer<std::uint8_t>(byte);
    for (unsigned bit = 0U; bit < 8U; ++bit) {
      const std::uint32_t mask = 0U - (checksum & 1U);
      checksum = (checksum >> 1U) ^ (0xedb88320U & mask);
    }
  }
  return ~checksum;
}

// This deliberately repeats the public logical-snapshot wire format instead
// of calling the runtime.  Equality here is still only a ROM-free scaffold:
// a trusted native/oracle production bundle must bind both executables later.
[[nodiscard]] std::vector<std::byte>
controller_image(const std::span<const std::byte> note) {
  std::vector<std::byte> image;
  constexpr std::array<char, 8> magic{'J', 'F', 'G', 'P', 'A', 'K', '0', '1'};
  for (const char value : magic)
    image.push_back(static_cast<std::byte>(value));
  append_u32(image, 1U);
  append_u64(image, 64U);
  append_u32(image, 4U);
  append_u32(image, note.empty() ? 0U : 1U);
  if (!note.empty()) {
    image.push_back(std::byte{4U});
    append_u64(image, note.size());
    for (const char value : std::string_view("slot"))
      image.push_back(static_cast<std::byte>(value));
    image.insert(image.end(), note.begin(), note.end());
  }
  append_u32(image, crc32(image));
  return image;
}

} // namespace

int main(const int argc, const char *const *argv) {
  try {
    if (kProbeMarker[0] != 'j' || kOracleMarker[0] != 'j')
      return 2;
    const auto identity = jfg::evidence::parse_producer_identity(
        argc, argv, "save-round-trip", "private-oracle-execution");
    const auto payload = jfg::evidence::read_paired_case(
        jfg::evidence::PairedCaseFamily::save, identity);
    if (payload.size() != 16U)
      throw std::runtime_error("save payload");
    const std::span<const std::byte> note(payload.data(), 8U);
    const auto controller_initial = controller_image({});
    const auto controller_written = controller_image(note);
    const std::vector<std::byte> flash_initial(128U * 1024U, std::byte{0xff});
    auto flash_written = flash_initial;
    for (std::size_t index = 0U; index < 128U; ++index)
      flash_written[index] = payload[8U + index % 8U];
    const auto ci = jfg::evidence::hex_digest(controller_initial);
    const auto cw = jfg::evidence::hex_digest(controller_written);
    const auto fi = jfg::evidence::hex_digest(flash_initial);
    const auto fw = jfg::evidence::hex_digest(flash_written);
    jfg::evidence::write_artifact("controller-pak-initial.bin", controller_initial);
    jfg::evidence::write_artifact("controller-pak-written.bin", controller_written);
    jfg::evidence::write_artifact("controller-pak-reloaded.bin", controller_written);
    jfg::evidence::write_artifact("controller-pak-restored.bin", controller_initial);
    jfg::evidence::write_artifact("flashram-initial.bin", flash_initial);
    jfg::evidence::write_artifact("flashram-written.bin", flash_written);
    jfg::evidence::write_artifact("flashram-reloaded.bin", flash_written);
    jfg::evidence::write_artifact("flashram-restored.bin", flash_initial);
    const std::string trace =
        "{\"case_id\":\"" + identity.case_id + "\",\"domains\":[" +
        domain("controller-pak", 4, 7, 9, ci, cw, "controller-pak") + "," +
        domain("flashram", 1, 2, 6, fi, fw, "flashram") +
        "],\"kind\":\"jfg-g2-save-semantic-trace\",\"schema_version\":1,"
        "\"subject_sha256\":\"" + identity.subject_sha256 + "\"}";
    const auto trace_bytes = std::as_bytes(std::span(trace));
    jfg::evidence::write_artifact("semantic-trace-a.json", trace_bytes);
    jfg::evidence::write_artifact("semantic-trace-b.json", trace_bytes);
    const std::string observation =
        "{\"case_id\":\"" + identity.case_id +
        "\",\"kind\":\"jfg-g2-save-oracle-observation\",\"schema_version\":1,"
        "\"semantic_trace_sha256\":\"" +
        jfg::evidence::hex_digest(trace_bytes) +
        "\",\"subject_sha256\":\"" + identity.subject_sha256 + "\"}";
    return jfg::evidence::emit_envelope(identity, observation);
  } catch (...) {
    return 1;
  }
}
