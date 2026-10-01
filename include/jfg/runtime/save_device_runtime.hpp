#pragma once

#include "jfg/runtime/controller_pak.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <memory>
#include <span>
#include <string_view>
#include <vector>

namespace jfg {

inline constexpr std::size_t kControllerPortCount = 4U;

enum class ControllerAccessoryKind {
    none,
    controller_pak,
    rumble_pak,
};

class ControllerPakSession final {
public:
    ControllerPakSession() = default;

    bool operator==(const ControllerPakSession&) const = default;

private:
    friend class ControllerAccessoryBus;

    ControllerPakSession(
        std::size_t port,
        std::uint64_t generation,
        std::uint64_t bus_identity) noexcept;

    std::size_t port_ = 0;
    std::uint64_t generation_ = 0;
    std::uint64_t bus_identity_ = 0;
};

struct ControllerPakProbeResult {
    ControllerPakError error = ControllerPakError::none;
    ControllerPakSession session;

    [[nodiscard]] bool ok() const noexcept {
        return error == ControllerPakError::none;
    }
};

class ControllerAccessoryBus final {
public:
    explicit ControllerAccessoryBus(ControllerPakGeometry controller_pak_geometry);
    ~ControllerAccessoryBus();

    ControllerAccessoryBus(const ControllerAccessoryBus&) = delete;
    ControllerAccessoryBus& operator=(const ControllerAccessoryBus&) = delete;
    ControllerAccessoryBus(ControllerAccessoryBus&&) = delete;
    ControllerAccessoryBus& operator=(ControllerAccessoryBus&&) = delete;

    [[nodiscard]] ControllerPakResult set_accessory(
        std::size_t port,
        ControllerAccessoryKind kind);
    [[nodiscard]] ControllerAccessoryKind accessory(std::size_t port) const noexcept;
    [[nodiscard]] ControllerPakProbeResult probe_controller_pak(std::size_t port) const;

    [[nodiscard]] ControllerPakResult create_note(
        ControllerPakSession session,
        std::string_view id,
        std::size_t size);
    [[nodiscard]] ControllerPakResult delete_note(
        ControllerPakSession session,
        std::string_view id);
    [[nodiscard]] ControllerPakResult write_note(
        ControllerPakSession session,
        std::string_view id,
        std::size_t offset,
        std::span<const std::uint8_t> bytes);
    [[nodiscard]] ControllerPakReadResult read_note(
        ControllerPakSession session,
        std::string_view id,
        std::size_t offset,
        std::size_t length) const;
    [[nodiscard]] std::vector<ControllerPakNoteInfo> enumerate_notes(
        ControllerPakSession session,
        ControllerPakError& error) const;
    [[nodiscard]] ControllerPakResult persist(
        ControllerPakSession session,
        const std::filesystem::path& destination) const;
    [[nodiscard]] ControllerPakResult reload(
        ControllerPakSession session,
        const std::filesystem::path& source);

    [[nodiscard]] ControllerPakResult set_rumble(std::size_t port, bool active);
    [[nodiscard]] bool rumble_active(std::size_t port) const noexcept;

private:
    struct Port;

    [[nodiscard]] ControllerPakError validate_session(
        ControllerPakSession session) const noexcept;

    ControllerPakGeometry geometry_;
    std::array<std::unique_ptr<Port>, kControllerPortCount> ports_;
    std::uint64_t identity_ = 0;
};

inline constexpr std::size_t kFlashRamSizeBytes = 128U * 1024U;
inline constexpr std::size_t kFlashRamPageBytes = 128U;
inline constexpr std::size_t kFlashRamPageCount =
    kFlashRamSizeBytes / kFlashRamPageBytes;

enum class FlashRamError {
    none = 0,
    invalid_argument = 1,
    out_of_bounds = 2,
    busy = 3,
    write_buffer_empty = 4,
    io_error = 5,
    corrupt_snapshot = 6,
};

enum class FlashRamOperation {
    none,
    program_page,
    erase_page,
    erase_all,
};

struct FlashRamResult {
    FlashRamError error = FlashRamError::none;

    [[nodiscard]] bool ok() const noexcept {
        return error == FlashRamError::none;
    }
};

struct FlashRamReadResult {
    FlashRamError error = FlashRamError::none;
    std::vector<std::uint8_t> bytes;

    [[nodiscard]] bool ok() const noexcept {
        return error == FlashRamError::none;
    }
};

struct FlashRamStatus {
    FlashRamOperation operation = FlashRamOperation::none;
    bool busy = false;
    bool write_buffer_valid = false;
};

class FlashRamStore final {
public:
    FlashRamStore();

    [[nodiscard]] FlashRamStatus status() const noexcept;
    [[nodiscard]] FlashRamResult stage_write(
        std::span<const std::uint8_t> page_bytes);
    [[nodiscard]] FlashRamResult begin_program(std::size_t page_index);
    [[nodiscard]] FlashRamResult begin_erase_page(std::size_t page_index);
    [[nodiscard]] FlashRamResult begin_erase_all();
    [[nodiscard]] FlashRamResult complete();
    [[nodiscard]] FlashRamResult complete_and_persist(
        const std::filesystem::path& destination);
    void interrupt() noexcept;

    [[nodiscard]] FlashRamReadResult read(
        std::size_t offset,
        std::size_t length) const;
    [[nodiscard]] FlashRamResult persist_atomic(
        const std::filesystem::path& destination) const;
    // FlashRAM images use the conventional raw 128 KiB representation.
    [[nodiscard]] FlashRamResult reload(const std::filesystem::path& source);

private:
    [[nodiscard]] std::vector<std::uint8_t> completed_image() const;
    [[nodiscard]] static FlashRamResult persist_image(
        std::span<const std::uint8_t> image,
        const std::filesystem::path& destination);

    std::vector<std::uint8_t> bytes_;
    std::array<std::uint8_t, kFlashRamPageBytes> write_buffer_{};
    bool write_buffer_valid_ = false;
    FlashRamOperation operation_ = FlashRamOperation::none;
    std::size_t operation_page_ = 0;
};

[[nodiscard]] std::string_view flash_ram_error_message(FlashRamError error) noexcept;

}  // namespace jfg
