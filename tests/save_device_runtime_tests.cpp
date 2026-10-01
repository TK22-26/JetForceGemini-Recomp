#include "jfg/runtime/save_device_runtime.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <system_error>
#include <vector>

namespace {

static_assert(static_cast<int>(jfg::ControllerPakError::io_error) == 8);
static_assert(static_cast<int>(jfg::ControllerPakError::corrupt_snapshot) == 9);
static_assert(static_cast<int>(jfg::ControllerPakError::incompatible_snapshot) == 10);

int failures = 0;

void check(const bool condition, const std::string_view message) {
    if (!condition) {
        ++failures;
        std::cerr << "FAIL: " << message << '\n';
    }
}

class TemporaryDirectory final {
public:
    TemporaryDirectory() {
        static std::atomic<std::uint64_t> sequence{0U};
        const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
        for (unsigned int attempt = 0U; attempt < 128U; ++attempt) {
            const auto token = sequence.fetch_add(1U, std::memory_order_relaxed);
            path_ = std::filesystem::temp_directory_path() /
                ("jfg-save-runtime-test-" + std::to_string(nonce) + "-" +
                 std::to_string(token));
            std::error_code error;
            if (std::filesystem::create_directory(path_, error)) {
                return;
            }
            if (error) {
                throw std::runtime_error("synthetic save fixture directory failed");
            }
        }
        throw std::runtime_error("synthetic save fixture directory collided");
    }

    ~TemporaryDirectory() noexcept {
        std::error_code ignored;
        std::filesystem::remove_all(path_, ignored);
    }

    TemporaryDirectory(const TemporaryDirectory&) = delete;
    TemporaryDirectory& operator=(const TemporaryDirectory&) = delete;

    [[nodiscard]] const std::filesystem::path& path() const noexcept {
        return path_;
    }

private:
    std::filesystem::path path_;
};

[[nodiscard]] std::vector<std::uint8_t> read_file(
    const std::filesystem::path& path) {
    const auto size = std::filesystem::file_size(path);
    std::vector<std::uint8_t> bytes(static_cast<std::size_t>(size));
    std::ifstream stream(path, std::ios::binary);
    stream.read(
        reinterpret_cast<char*>(bytes.data()),
        static_cast<std::streamsize>(bytes.size()));
    if (!stream) {
        throw std::runtime_error("synthetic save fixture could not be read");
    }
    return bytes;
}

void write_file(
    const std::filesystem::path& path,
    const std::span<const std::uint8_t> bytes) {
    std::ofstream stream(path, std::ios::binary | std::ios::trunc);
    stream.write(
        reinterpret_cast<const char*>(bytes.data()),
        static_cast<std::streamsize>(bytes.size()));
    if (!stream) {
        throw std::runtime_error("synthetic save fixture could not be written");
    }
}

[[nodiscard]] bool all_equal(
    const std::vector<std::uint8_t>& bytes,
    const std::uint8_t expected) {
    return std::all_of(bytes.begin(), bytes.end(), [expected](const std::uint8_t value) {
        return value == expected;
    });
}

void test_controller_accessory_lifecycle() {
    jfg::ControllerAccessoryBus bus({64U, 4U});
    check(
        bus.probe_controller_pak(0U).error == jfg::ControllerPakError::no_device,
        "empty port reports no device");
    check(
        bus.probe_controller_pak(jfg::kControllerPortCount).error ==
            jfg::ControllerPakError::invalid_argument,
        "invalid port is rejected");
    check(
        bus.set_accessory(
               0U,
               static_cast<jfg::ControllerAccessoryKind>(0x7FFF)).error ==
            jfg::ControllerPakError::invalid_argument &&
            bus.accessory(0U) == jfg::ControllerAccessoryKind::none,
        "invalid accessory kind is rejected without changing the port");

    check(bus.set_accessory(0U, jfg::ControllerAccessoryKind::rumble_pak).ok(),
          "Rumble Pak can be connected");
    check(
        bus.probe_controller_pak(0U).error == jfg::ControllerPakError::wrong_accessory,
        "Controller Pak probe distinguishes Rumble Pak");
    check(bus.set_rumble(0U, true).ok() && bus.rumble_active(0U),
          "Rumble Pak can be activated");

    check(bus.set_accessory(0U, jfg::ControllerAccessoryKind::controller_pak).ok(),
          "Controller Pak can replace Rumble Pak");
    check(!bus.rumble_active(0U), "accessory switch clears rumble state");
    const auto first_probe = bus.probe_controller_pak(0U);
    check(first_probe.ok(), "connected Controller Pak can be probed");
    check(
        bus.set_rumble(0U, true).error == jfg::ControllerPakError::wrong_accessory,
        "rumble command rejects Controller Pak");

    const std::array<std::uint8_t, 4> first_payload{1U, 2U, 3U, 4U};
    check(bus.create_note(first_probe.session, "slot-a", 8U).ok(),
          "session creates a bounded Controller Pak note");
    check(bus.write_note(first_probe.session, "slot-a", 2U, first_payload).ok(),
          "session writes Controller Pak data");

    jfg::ControllerPakError enumeration_error = jfg::ControllerPakError::none;
    const auto notes = bus.enumerate_notes(first_probe.session, enumeration_error);
    check(
        enumeration_error == jfg::ControllerPakError::none && notes.size() == 1U &&
            notes.front().id == "slot-a",
        "session enumerates deterministic Controller Pak inventory");

    check(bus.set_accessory(0U, jfg::ControllerAccessoryKind::none).ok(),
          "Controller Pak can be disconnected");
    check(
        bus.read_note(first_probe.session, "slot-a", 2U, first_payload.size()).error ==
            jfg::ControllerPakError::no_device,
        "disconnected session observes no device");
    check(bus.set_accessory(0U, jfg::ControllerAccessoryKind::controller_pak).ok(),
          "Controller Pak can be reconnected");
    check(
        bus.read_note(first_probe.session, "slot-a", 2U, first_payload.size()).error ==
            jfg::ControllerPakError::stale_session,
        "reconnect invalidates stale session handle");
    const auto second_probe = bus.probe_controller_pak(0U);
    const auto retained = bus.read_note(
        second_probe.session, "slot-a", 2U, first_payload.size());
    check(
        retained.ok() && retained.bytes ==
            std::vector<std::uint8_t>(first_payload.begin(), first_payload.end()),
        "non-volatile Controller Pak content survives accessory reconnect");

    check(bus.set_accessory(1U, jfg::ControllerAccessoryKind::controller_pak).ok(),
          "second controller port accepts a Controller Pak");
    const auto other_probe = bus.probe_controller_pak(1U);
    const std::array<std::uint8_t, 2> other_payload{9U, 8U};
    check(bus.create_note(other_probe.session, "slot-a", 2U).ok() &&
              bus.write_note(other_probe.session, "slot-a", 0U, other_payload).ok(),
          "second port stores independent contents");
    check(
        bus.read_note(second_probe.session, "slot-a", 2U, first_payload.size()).bytes ==
            std::vector<std::uint8_t>(first_payload.begin(), first_payload.end()),
        "port-local write does not alter another Controller Pak");

    jfg::ControllerAccessoryBus separate_bus({64U, 4U});
    check(separate_bus.set_accessory(0U, jfg::ControllerAccessoryKind::controller_pak).ok(),
          "separate bus reaches matching local generation");
    check(
        separate_bus.create_note(first_probe.session, "foreign", 1U).error ==
            jfg::ControllerPakError::stale_session,
        "session from another bus cannot mutate a matching port generation");
    const auto separate_probe = separate_bus.probe_controller_pak(0U);
    jfg::ControllerPakError separate_error = jfg::ControllerPakError::none;
    check(
        separate_bus.enumerate_notes(separate_probe.session, separate_error).empty() &&
            separate_error == jfg::ControllerPakError::none,
        "rejected foreign session leaves destination device unchanged");
}

void test_controller_pak_process_round_trip() {
    TemporaryDirectory directory;
    const auto snapshot = directory.path() / "controller-pak.bin";
    jfg::ControllerAccessoryBus source({64U, 4U});
    check(source.set_accessory(2U, jfg::ControllerAccessoryKind::controller_pak).ok(),
          "round-trip source device is connected");
    const auto source_probe = source.probe_controller_pak(2U);
    const std::array<std::uint8_t, 5> payload{4U, 3U, 2U, 1U, 0U};
    check(source.create_note(source_probe.session, "save", 12U).ok() &&
              source.write_note(source_probe.session, "save", 5U, payload).ok() &&
              source.persist(source_probe.session, snapshot).ok(),
          "Controller Pak session persists a logical snapshot");

    jfg::ControllerAccessoryBus restored({64U, 4U});
    check(restored.set_accessory(2U, jfg::ControllerAccessoryKind::controller_pak).ok(),
          "fresh process model connects destination device");
    const auto restored_probe = restored.probe_controller_pak(2U);
    check(restored.reload(restored_probe.session, snapshot).ok(),
          "fresh process model reloads Controller Pak snapshot");
    const auto read = restored.read_note(
        restored_probe.session, "save", 5U, payload.size());
    check(
        read.ok() && read.bytes == std::vector<std::uint8_t>(payload.begin(), payload.end()),
        "Controller Pak bytes survive process-style round trip");
}

void test_flashram_command_lifecycle() {
    jfg::FlashRamStore flash;
    const auto erased = flash.read(0U, jfg::kFlashRamPageBytes);
    check(erased.ok() && all_equal(erased.bytes, 0xFFU),
          "fresh FlashRAM is erased");
    check(
        flash.read(jfg::kFlashRamSizeBytes, 1U).error ==
            jfg::FlashRamError::out_of_bounds,
        "FlashRAM read enforces bounds");

    const std::array<std::uint8_t, 1> short_write{0U};
    check(
        flash.stage_write(short_write).error == jfg::FlashRamError::invalid_argument,
        "FlashRAM requires an exact page write buffer");
    check(
        flash.begin_program(0U).error == jfg::FlashRamError::write_buffer_empty,
        "program command requires a staged write buffer");
    check(
        flash.begin_erase_page(jfg::kFlashRamPageCount).error ==
            jfg::FlashRamError::out_of_bounds,
        "erase command enforces page bounds");

    std::array<std::uint8_t, jfg::kFlashRamPageBytes> pattern{};
    pattern.fill(0xF0U);
    check(flash.stage_write(pattern).ok(), "FlashRAM stages a complete page");
    check(
        flash.begin_program(jfg::kFlashRamPageCount).error ==
                jfg::FlashRamError::out_of_bounds &&
            flash.status().write_buffer_valid,
        "out-of-range program leaves staged data available for retry");
    check(flash.begin_program(3U).ok(),
          "program operation enters busy state");
    check(
        flash.status().busy &&
            flash.stage_write(pattern).error == jfg::FlashRamError::busy &&
            flash.begin_erase_all().error == jfg::FlashRamError::busy &&
            flash.reload({}).error == jfg::FlashRamError::busy &&
            flash.persist_atomic({}).error == jfg::FlashRamError::busy,
        "busy FlashRAM rejects overlapping commands and persistence");
    check(all_equal(flash.read(3U * jfg::kFlashRamPageBytes,
                               jfg::kFlashRamPageBytes).bytes,
                    0xFFU),
          "program operation is not visible before completion");
    check(flash.complete().ok(), "program operation completes");
    check(
        flash.complete().error == jfg::FlashRamError::invalid_argument,
        "completion without an active command is rejected");
    check(all_equal(flash.read(3U * jfg::kFlashRamPageBytes,
                               jfg::kFlashRamPageBytes).bytes,
                    0xF0U),
          "completed program changes the selected page");

    pattern.fill(0xFFU);
    check(flash.stage_write(pattern).ok() && flash.begin_program(3U).ok() &&
              flash.complete().ok(),
          "second program operation completes");
    check(all_equal(flash.read(3U * jfg::kFlashRamPageBytes,
                               jfg::kFlashRamPageBytes).bytes,
                    0xFFU),
          "FlashRAM high-level page programming replaces the complete page");

    check(flash.begin_erase_page(3U).ok() && flash.complete().ok(),
          "page erase completes");
    check(all_equal(flash.read(3U * jfg::kFlashRamPageBytes,
                               jfg::kFlashRamPageBytes).bytes,
                    0xFFU),
          "page erase restores ones");

    pattern.fill(0x00U);
    check(flash.stage_write(pattern).ok() && flash.begin_program(4U).ok(),
          "interrupt fixture begins programming");
    flash.interrupt();
    check(!flash.status().busy && flash.status().write_buffer_valid &&
              all_equal(flash.read(4U * jfg::kFlashRamPageBytes,
                                   jfg::kFlashRamPageBytes).bytes,
                        0xFFU),
          "interrupted command preserves staged buffer without committing bytes");

    check(flash.begin_program(4U).ok() &&
              flash.complete().ok() && flash.begin_erase_all().ok() &&
              flash.complete().ok(),
          "staged buffer can be reused and chip erase completes");
    check(all_equal(flash.read(0U, jfg::kFlashRamSizeBytes).bytes, 0xFFU),
          "chip erase restores the complete FlashRAM image");

    pattern.fill(0x55U);
    check(flash.stage_write(pattern).ok() &&
              flash.begin_program(jfg::kFlashRamPageCount - 1U).ok() &&
              flash.complete().ok() &&
              all_equal(flash.read(jfg::kFlashRamSizeBytes - jfg::kFlashRamPageBytes,
                                   jfg::kFlashRamPageBytes).bytes,
                        0x55U),
          "last FlashRAM page is writable at the exact upper boundary");
}

void test_flashram_transactional_persistence() {
    TemporaryDirectory directory;
    const auto snapshot = directory.path() / "flashram.bin";
    jfg::FlashRamStore source;
    std::array<std::uint8_t, jfg::kFlashRamPageBytes> payload{};
    for (std::size_t index = 0; index < payload.size(); ++index) {
        payload[index] = static_cast<std::uint8_t>(index);
    }
    check(source.stage_write(payload).ok() && source.begin_program(7U).ok() &&
              source.complete_and_persist(snapshot).ok(),
          "FlashRAM command commits atomically with persistence");
    check(
        std::filesystem::file_size(snapshot) == jfg::kFlashRamSizeBytes,
        "FlashRAM persistence emits a conventional raw fixed-size image");

    jfg::FlashRamStore restored;
    check(restored.reload(snapshot).ok(), "fresh FlashRAM reloads durable snapshot");
    check(
        restored.read(7U * jfg::kFlashRamPageBytes, payload.size()).bytes ==
            std::vector<std::uint8_t>(payload.begin(), payload.end()),
        "FlashRAM page survives process-style round trip");

    payload.fill(0x00U);
    check(restored.stage_write(payload).ok() && restored.begin_program(8U).ok(),
          "failed-persistence fixture enters busy state");
    const auto unavailable = directory.path() / "missing-parent" / "flashram.bin";
    check(
        restored.complete_and_persist(unavailable).error == jfg::FlashRamError::io_error,
        "failed durable write reports I/O failure");
    check(!restored.status().busy && restored.status().write_buffer_valid &&
              all_equal(restored.read(8U * jfg::kFlashRamPageBytes,
                                      jfg::kFlashRamPageBytes).bytes,
                        0x00U),
          "device completion remains committed after host persistence failure");
    check(restored.persist_atomic(snapshot).ok(),
          "completed FlashRAM image can be durably retried");

    const auto before_rejection = restored.read(
        7U * jfg::kFlashRamPageBytes, payload.size()).bytes;
    auto corrupt = read_file(snapshot);
    corrupt.pop_back();
    const auto corrupt_path = directory.path() / "corrupt.bin";
    write_file(corrupt_path, corrupt);
    check(
        restored.reload(corrupt_path).error == jfg::FlashRamError::corrupt_snapshot &&
            restored.read(7U * jfg::kFlashRamPageBytes, payload.size()).bytes ==
                before_rejection,
        "corrupt reload is rejected transactionally");

    const auto oversized_path = directory.path() / "oversized.bin";
    std::vector<std::uint8_t> oversized(jfg::kFlashRamSizeBytes + 1U, 0x5AU);
    write_file(oversized_path, oversized);
    check(
        restored.reload(oversized_path).error == jfg::FlashRamError::corrupt_snapshot &&
            restored.read(7U * jfg::kFlashRamPageBytes, payload.size()).bytes ==
                before_rejection,
        "oversized raw FlashRAM image is rejected transactionally");
}

}  // namespace

int main() noexcept {
    try {
        test_controller_accessory_lifecycle();
        test_controller_pak_process_round_trip();
        test_flashram_command_lifecycle();
        test_flashram_transactional_persistence();

        if (failures != 0) {
            std::cerr << failures << " save-device assertion(s) failed\n";
            return 1;
        }
        std::cout << "All ROM-free save-device runtime tests passed\n";
        return 0;
    } catch (const std::exception&) {
        std::fputs("Save-device test harness failed unexpectedly\n", stderr);
        return 1;
    } catch (...) {
        std::fputs("Save-device test harness failed unexpectedly\n", stderr);
        return 1;
    }
}
