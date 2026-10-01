#pragma once

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace jfg {

inline constexpr std::size_t kMaximumControllerPakCapacityBytes =
    std::size_t{16U} * 1024U * 1024U;
inline constexpr std::size_t kMaximumControllerPakNotes = 4096U;
inline constexpr std::size_t kMaximumControllerPakNoteIdBytes = 32U;

enum class ControllerPakError {
    none = 0,
    invalid_argument = 1,
    invalid_note_id = 2,
    note_exists = 3,
    note_not_found = 4,
    note_limit_reached = 5,
    capacity_exceeded = 6,
    out_of_bounds = 7,
    io_error = 8,
    corrupt_snapshot = 9,
    incompatible_snapshot = 10,
    no_device = 11,
    wrong_accessory = 12,
    stale_session = 13,
};

struct ControllerPakResult {
    ControllerPakError error = ControllerPakError::none;

    [[nodiscard]] bool ok() const noexcept {
        return error == ControllerPakError::none;
    }
};

struct ControllerPakReadResult {
    ControllerPakError error = ControllerPakError::none;
    std::vector<std::uint8_t> bytes;

    [[nodiscard]] bool ok() const noexcept {
        return error == ControllerPakError::none;
    }
};

struct ControllerPakNoteInfo {
    std::string id;
    std::size_t size = 0;

    bool operator==(const ControllerPakNoteInfo&) const = default;
};

struct ControllerPakGeometry {
    std::size_t capacity_bytes = 0;
    std::size_t max_notes = 0;
};

// Project-owned logical note storage. This class intentionally does not model
// or serialize a proprietary Controller Pak filesystem image.
class ControllerPakStore final {
public:
    explicit ControllerPakStore(ControllerPakGeometry geometry);
    ~ControllerPakStore();

    ControllerPakStore(const ControllerPakStore&) = delete;
    ControllerPakStore& operator=(const ControllerPakStore&) = delete;
    ControllerPakStore(ControllerPakStore&&) noexcept;
    ControllerPakStore& operator=(ControllerPakStore&&) noexcept;

    [[nodiscard]] std::size_t capacity_bytes() const noexcept;
    [[nodiscard]] std::size_t used_bytes() const noexcept;
    [[nodiscard]] std::size_t free_bytes() const noexcept;
    [[nodiscard]] std::size_t max_notes() const noexcept;
    [[nodiscard]] std::size_t note_count() const noexcept;

    [[nodiscard]] ControllerPakResult create_note(std::string_view id, std::size_t size);
    [[nodiscard]] ControllerPakResult delete_note(std::string_view id);
    [[nodiscard]] ControllerPakResult write_note(
        std::string_view id,
        std::size_t offset,
        std::span<const std::uint8_t> bytes);
    [[nodiscard]] ControllerPakReadResult read_note(
        std::string_view id,
        std::size_t offset,
        std::size_t length) const;
    [[nodiscard]] std::vector<ControllerPakNoteInfo> enumerate_notes() const;

    // Writes a canonical snapshot to a unique sibling temporary file, flushes
    // it to stable storage, and atomically replaces the destination. A failure
    // before replacement leaves the previous snapshot untouched.
    [[nodiscard]] ControllerPakResult persist_atomic(
        const std::filesystem::path& destination) const;

    // Reload is transactional: malformed, corrupt, or incompatible input is
    // rejected without changing the current in-memory note collection.
    [[nodiscard]] ControllerPakResult reload(const std::filesystem::path& source);

private:
    struct Note;

    std::size_t capacity_bytes_;
    std::size_t max_notes_;
    std::size_t used_bytes_ = 0;
    std::vector<Note> notes_;
};

[[nodiscard]] std::string_view controller_pak_error_message(
    ControllerPakError error) noexcept;

}  // namespace jfg
