#include "jfg/evidence/g2_paired_producer.hpp"
#include "jfg/runtime/save_device_runtime.hpp"

#include <array>
#include <filesystem>

namespace {
volatile const char kProbeMarker[] = "jfg_g2_save_native_probe";
volatile const char kRuntimeMarker[] = "jfg_g2_save_runtime";

[[nodiscard]] std::vector<std::byte>
read_file(const std::filesystem::path &path) {
  std::ifstream stream(path, std::ios::binary | std::ios::ate);
  if (!stream)
    throw std::runtime_error("save output");
  const auto length = stream.tellg();
  if (length <= 0 || length > static_cast<std::streamoff>(
                                  jfg::evidence::kMaximumPairedCaseBytes))
    throw std::runtime_error("save output size");
  std::vector<std::byte> bytes(static_cast<std::size_t>(length));
  stream.seekg(0);
  stream.read(reinterpret_cast<char *>(bytes.data()), length);
  if (!stream)
    throw std::runtime_error("save output read");
  return bytes;
}
void write_malformed(const std::filesystem::path &path) {
  std::ofstream stream(path, std::ios::binary | std::ios::trunc);
  const std::array<char, 3> bytes{'b', 'a', 'd'};
  stream.write(bytes.data(), bytes.size());
  if (!stream)
    throw std::runtime_error("malformed fixture");
}
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
} // namespace

int main(const int argc, const char *const *argv) {
  try {
    if (kProbeMarker[0] != 'j' || kRuntimeMarker[0] != 'j')
      return 2;
    const auto identity = jfg::evidence::parse_producer_identity(
        argc, argv, "save-round-trip", "private-native-execution");
    const auto payload = jfg::evidence::read_paired_case(
        jfg::evidence::PairedCaseFamily::save, identity);
    if (payload.size() != 16U)
      throw std::runtime_error("save payload");
    std::array<std::uint8_t, 8> note{};
    for (std::size_t i = 0; i < note.size(); ++i)
      note[i] = std::to_integer<std::uint8_t>(payload[i]);
    const std::filesystem::path controller_initial_path = "controller-pak-initial.bin",
                                controller_path = "controller-pak-written.bin",
                                controller_reloaded_path = "controller-pak-reloaded.bin",
                                controller_restored_path = "controller-pak-restored.bin",
                                flash_initial_path = "flashram-initial.bin",
                                flash_path = "flashram-written.bin",
                                flash_reloaded_path = "flashram-reloaded.bin",
                                flash_restored_path = "flashram-restored.bin",
                                malformed_controller =
                                    "malformed-controller.bin",
                                malformed_flash = "malformed-flash.bin";
    jfg::ControllerPakStore capacity_probe({64U, 4U});
    if (capacity_probe.capacity_bytes() != 64U ||
        capacity_probe.free_bytes() != 64U || capacity_probe.max_notes() != 4U)
      return 1;
    jfg::ControllerAccessoryBus bus({64U, 4U});
    if (!bus.set_accessory(0U, jfg::ControllerAccessoryKind::controller_pak)
             .ok())
      return 1;
    const auto session = bus.probe_controller_pak(0U);
    if (!session.ok())
      return 1;
    if (!bus.persist(session.session, controller_initial_path).ok())
      return 1;
    const int controller_missing =
        static_cast<int>(bus.read_note(session.session, "slot", 0U, 1U).error);
    if (!bus.create_note(session.session, "slot", note.size()).ok() ||
        !bus.write_note(session.session, "slot", 0U, note).ok())
      return 1;
    jfg::ControllerPakError enumerate_error{};
    if (bus.enumerate_notes(session.session, enumerate_error).size() != 1U ||
        enumerate_error != jfg::ControllerPakError::none)
      return 1;
    if (bus.read_note(session.session, "slot", 0U, note.size()).bytes !=
        std::vector<std::uint8_t>(note.begin(), note.end()))
      return 1;
    const int controller_bounds = static_cast<int>(
        bus.read_note(session.session, "slot", note.size(), 1U).error);
    if (!bus.persist(session.session, controller_path).ok())
      return 1;
    jfg::ControllerAccessoryBus reloaded({64U, 4U});
    if (!reloaded
             .set_accessory(0U, jfg::ControllerAccessoryKind::controller_pak)
             .ok())
      return 1;
    const auto reload_session = reloaded.probe_controller_pak(0U);
    if (!reloaded.reload(reload_session.session, controller_path).ok() ||
        reloaded.read_note(reload_session.session, "slot", 0U, note.size())
                .bytes != std::vector<std::uint8_t>(note.begin(), note.end()))
      return 1;
    if (!reloaded.persist(reload_session.session, controller_reloaded_path).ok())
      return 1;
    write_malformed(malformed_controller);
    const int controller_malformed = static_cast<int>(
        reloaded.reload(reload_session.session, malformed_controller).error);
    if (!reloaded.delete_note(reload_session.session, "slot").ok())
      return 1;
    if (!reloaded.persist(reload_session.session, controller_restored_path).ok())
      return 1;
    if (reloaded.read_note(reload_session.session, "slot", 0U, 1U).error !=
        jfg::ControllerPakError::note_not_found)
      return 1;
    std::array<std::uint8_t, jfg::kFlashRamPageBytes> page{};
    for (std::size_t i = 0; i < page.size(); ++i)
      page[i] = std::to_integer<std::uint8_t>(payload[8U + i % 8U]);
    jfg::FlashRamStore flash;
    if (!flash.persist_atomic(flash_initial_path).ok())
      return 1;
    const int flash_missing = static_cast<int>(flash.complete().error);
    if (!flash.stage_write(page).ok() || !flash.begin_program(0U).ok() ||
        !flash.complete_and_persist(flash_path).ok())
      return 1;
    const auto written_page = flash.read(0U, page.size());
    if (!written_page.ok() ||
        written_page.bytes !=
            std::vector<std::uint8_t>(page.begin(), page.end()))
      return 1;
    const int flash_bounds =
        static_cast<int>(flash.read(jfg::kFlashRamSizeBytes, 1U).error);
    jfg::FlashRamStore flash_reloaded;
    if (!flash_reloaded.reload(flash_path).ok() ||
        flash_reloaded.read(0U, page.size()).bytes !=
            std::vector<std::uint8_t>(page.begin(), page.end()))
      return 1;
    if (!flash_reloaded.persist_atomic(flash_reloaded_path).ok())
      return 1;
    write_malformed(malformed_flash);
    const int flash_malformed =
        static_cast<int>(flash_reloaded.reload(malformed_flash).error);
    if (!flash_reloaded.begin_erase_all().ok() ||
        !flash_reloaded.complete().ok())
      return 1;
    const auto restored_flash =
        flash_reloaded.read(0U, jfg::kFlashRamSizeBytes);
    if (!restored_flash.ok() ||
        !std::ranges::all_of(
            restored_flash.bytes,
            [](const std::uint8_t value) { return value == 0xffU; }))
      return 1;
    if (!flash_reloaded.persist_atomic(flash_restored_path).ok())
      return 1;
    const auto controller_initial = read_file(controller_initial_path),
               controller_written = read_file(controller_path),
               controller_reloaded = read_file(controller_reloaded_path),
               controller_restored = read_file(controller_restored_path),
               flash_initial = read_file(flash_initial_path),
               flash_written = read_file(flash_path),
               flash_reloaded_image = read_file(flash_reloaded_path),
               flash_restored_image = read_file(flash_restored_path);
    const auto ci = jfg::evidence::hex_digest(controller_initial),
               cw = jfg::evidence::hex_digest(controller_written),
               cr = jfg::evidence::hex_digest(controller_reloaded),
               cres = jfg::evidence::hex_digest(controller_restored),
               fi = jfg::evidence::hex_digest(flash_initial),
               fw = jfg::evidence::hex_digest(flash_written),
               fr = jfg::evidence::hex_digest(flash_reloaded_image),
               fres = jfg::evidence::hex_digest(flash_restored_image);
    if (cw != cr || ci != cres || fw != fr || fi != fres)
      return 1;
    const std::string trace =
        "{\"case_id\":\"" + identity.case_id + "\",\"domains\":[" +
        domain("controller-pak", controller_missing, controller_bounds,
               controller_malformed, ci, cw, "controller-pak") +
        "," +
        domain("flashram", flash_missing, flash_bounds, flash_malformed, fi,
               fw, "flashram") +
        "],\"kind\":\"jfg-g2-save-semantic-trace\",\"schema_version\":1,"
        "\"subject_sha256\":\"" +
        identity.subject_sha256 + "\"}";
    if (flash_written.size() != jfg::kFlashRamSizeBytes)
      return 1;
    const std::string observation =
        "{\"case_id\":\"" + identity.case_id +
        "\",\"controller_pak_image_sha256\":\"" + cw +
        "\",\"flashram_image_sha256\":\"" +
        fw +
        "\",\"kind\":\"jfg-g2-save-native-observation\",\"schema_version\":1,"
        "\"semantic_trace\":" +
        trace + ",\"subject_sha256\":\"" + identity.subject_sha256 + "\"}";
    return jfg::evidence::emit_envelope(identity, observation);
  } catch (...) {
    return 1;
  }
}
