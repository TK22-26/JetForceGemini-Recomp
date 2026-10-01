#include "jfg/runtime/controller_pak.hpp"

#include <array>
#include <chrono>
#include <cstdio>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <system_error>
#include <utility>
#include <vector>

namespace {

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
        const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
        path_ = std::filesystem::temp_directory_path() /
            ("jfg-controller-pak-test-" + std::to_string(nonce));
        std::filesystem::create_directory(path_);
    }

    ~TemporaryDirectory() noexcept {
        try {
            std::error_code ignored;
            std::filesystem::remove_all(path_, ignored);
        } catch (...) {
            ++failures;
        }
    }

    TemporaryDirectory(const TemporaryDirectory&) = delete;
    TemporaryDirectory& operator=(const TemporaryDirectory&) = delete;

    [[nodiscard]] const std::filesystem::path& path() const noexcept {
        return path_;
    }

private:
    std::filesystem::path path_;
};

[[nodiscard]] std::vector<std::uint8_t> read_file(const std::filesystem::path& path) {
    const auto size = std::filesystem::file_size(path);
    std::vector<std::uint8_t> bytes(static_cast<std::size_t>(size));
    std::ifstream stream(path, std::ios::binary);
    stream.read(reinterpret_cast<char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
    if (!stream) {
        throw std::runtime_error("synthetic test fixture could not be read");
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
        throw std::runtime_error("synthetic test fixture could not be written");
    }
}

[[nodiscard]] std::uint32_t test_crc32(
    const std::span<const std::uint8_t> bytes) noexcept {
    std::uint32_t checksum = 0xFFFFFFFFU;
    for (const std::uint8_t byte : bytes) {
        checksum ^= byte;
        for (unsigned int bit = 0; bit < 8U; ++bit) {
            const std::uint32_t mask = 0U - (checksum & 1U);
            checksum = (checksum >> 1U) ^ (0xEDB88320U & mask);
        }
    }
    return ~checksum;
}

void repair_checksum(std::vector<std::uint8_t>& bytes) {
    const std::uint32_t checksum = test_crc32(
        std::span<const std::uint8_t>(bytes).first(bytes.size() - 4U));
    for (unsigned int index = 0; index < 4U; ++index) {
        bytes[bytes.size() - 4U + index] =
            static_cast<std::uint8_t>(checksum >> (index * 8U));
    }
}

void test_configuration_bounds() {
    bool rejected_zero_capacity = false;
    try {
        const jfg::ControllerPakStore invalid({0U, 1U});
    } catch (const std::invalid_argument&) {
        rejected_zero_capacity = true;
    }
    check(rejected_zero_capacity, "zero capacity is rejected");

    bool rejected_large_capacity = false;
    try {
        const jfg::ControllerPakStore invalid({
            jfg::kMaximumControllerPakCapacityBytes + 1U,
            1U});
    } catch (const std::invalid_argument&) {
        rejected_large_capacity = true;
    }
    check(rejected_large_capacity, "oversized capacity is rejected");

    bool rejected_large_note_count = false;
    try {
        const jfg::ControllerPakStore invalid({
            1U,
            jfg::kMaximumControllerPakNotes + 1U});
    } catch (const std::invalid_argument&) {
        rejected_large_note_count = true;
    }
    check(rejected_large_note_count, "oversized note count is rejected");
}

void test_in_memory_lifecycle() {
    jfg::ControllerPakStore store({24U, 3U});
    check(store.capacity_bytes() == 24U, "capacity is reported");
    check(store.free_bytes() == 24U, "new store reports all bytes free");
    check(
        store.create_note("slot-b", 8U).ok() && store.create_note("slot-a", 12U).ok(),
        "notes can be created");
    check(store.used_bytes() == 20U && store.free_bytes() == 4U, "capacity is accounted");

    const std::vector<jfg::ControllerPakNoteInfo> expected{
        {"slot-a", 12U},
        {"slot-b", 8U},
    };
    check(store.enumerate_notes() == expected, "enumeration is deterministic and sorted");

    const std::array<std::uint8_t, 4> payload{1U, 2U, 3U, 4U};
    check(store.write_note("slot-a", 3U, payload).ok(), "bounded note write succeeds");
    const auto read = store.read_note("slot-a", 3U, payload.size());
    check(read.ok() && read.bytes == std::vector<std::uint8_t>(payload.begin(), payload.end()),
          "bounded note read returns written bytes");
    check(store.write_note("slot-a", 12U, {}).ok(), "empty write at end is valid");
    check(store.read_note("slot-a", 12U, 0U).ok(), "empty read at end is valid");

    check(
        store.write_note("slot-a", 10U, payload).error == jfg::ControllerPakError::out_of_bounds,
        "overflowing write is rejected");
    check(
        store.read_note("slot-a", 11U, 2U).error == jfg::ControllerPakError::out_of_bounds,
        "overflowing read is rejected");
    check(
        store.create_note("slot-c", 5U).error == jfg::ControllerPakError::capacity_exceeded,
        "allocation beyond remaining capacity is rejected");
    check(
        store.create_note("slot-a", 1U).error == jfg::ControllerPakError::note_exists,
        "duplicate note is rejected");
    check(
        store.create_note("Slot-c", 1U).error == jfg::ControllerPakError::invalid_note_id,
        "non-opaque note identifier is rejected");
    check(
        store.write_note("Slot-a", 0U, payload).error ==
            jfg::ControllerPakError::invalid_note_id,
        "write rejects invalid note identifier");
    check(
        store.read_note("Slot-a", 0U, 1U).error ==
            jfg::ControllerPakError::invalid_note_id,
        "read rejects invalid note identifier");
    check(
        store.delete_note("Slot-a").error == jfg::ControllerPakError::invalid_note_id,
        "delete rejects invalid note identifier");
    check(
        store.create_note("slot-c", 0U).error == jfg::ControllerPakError::invalid_argument,
        "empty note is rejected");

    check(store.delete_note("slot-a").ok(), "existing note can be deleted");
    check(store.used_bytes() == 8U && store.free_bytes() == 16U, "delete releases capacity");
    check(
        store.delete_note("slot-a").error == jfg::ControllerPakError::note_not_found,
        "deleting a missing note fails deterministically");
    check(
        store.read_note("slot-a", 0U, 0U).error == jfg::ControllerPakError::note_not_found,
        "reading a missing note fails deterministically");

    jfg::ControllerPakStore limited({8U, 1U});
    check(limited.create_note("slot-a", 1U).ok(), "limited store accepts first note");
    check(
        limited.create_note("slot-b", 1U).error ==
            jfg::ControllerPakError::note_limit_reached,
        "note-count limit is enforced independently of capacity");
}

void test_move_preserves_store_invariants() {
    jfg::ControllerPakStore source({24U, 3U});
    check(source.create_note("slot-a", 8U).ok(), "move source note is created");

    jfg::ControllerPakStore moved(std::move(source));
    check(moved.used_bytes() == 8U && moved.note_count() == 1U,
          "move construction transfers note accounting");
    check(source.used_bytes() == 0U && source.note_count() == 0U,
          "move construction leaves an internally consistent empty source");
    check(source.free_bytes() == source.capacity_bytes(),
          "moved-from source reports consistent free capacity");
    check(source.create_note("slot-b", 3U).ok(),
          "moved-from source remains reusable");

    jfg::ControllerPakStore destination({12U, 2U});
    check(destination.create_note("old", 2U).ok(),
          "move-assignment destination starts populated");
    destination = std::move(moved);
    check(destination.capacity_bytes() == 24U && destination.used_bytes() == 8U &&
              destination.note_count() == 1U,
          "move assignment transfers geometry and accounting");
    check(moved.used_bytes() == 0U && moved.note_count() == 0U &&
              moved.free_bytes() == moved.capacity_bytes(),
          "move assignment leaves an internally consistent empty source");

    using MoveAssignment = jfg::ControllerPakStore& (
        jfg::ControllerPakStore::*)(jfg::ControllerPakStore&&) noexcept;
    const auto move_assign = static_cast<MoveAssignment>(
        &jfg::ControllerPakStore::operator=);
    (destination.*move_assign)(std::move(destination));
    check(destination.used_bytes() == 8U && destination.note_count() == 1U,
          "self move assignment preserves the store");
}

void test_persistence_round_trip_and_determinism() {
    TemporaryDirectory directory;
    const auto snapshot = directory.path() / "logical-save.bin";
    const auto stale_temporary = directory.path() / "logical-save.bin.tmp-stale";

    jfg::ControllerPakStore source({64U, 4U});
    check(
        source.create_note("slot-b", 9U).ok() && source.create_note("slot-a", 15U).ok(),
        "round-trip source notes are created");
    const std::array<std::uint8_t, 6> first_payload{9U, 8U, 7U, 6U, 5U, 4U};
    const std::array<std::uint8_t, 3> second_payload{3U, 2U, 1U};
    check(source.write_note("slot-a", 4U, first_payload).ok(), "first body is populated");
    check(source.write_note("slot-b", 1U, second_payload).ok(), "second body is populated");
    check(source.persist_atomic(snapshot).ok(), "atomic persistence succeeds");
    const auto first_snapshot = read_file(snapshot);

    check(source.persist_atomic(snapshot).ok(), "atomic replacement succeeds");
    check(read_file(snapshot) == first_snapshot, "unchanged logical state serializes identically");

    const std::array<std::uint8_t, 5> stale{0U, 1U, 2U, 3U, 4U};
    write_file(stale_temporary, stale);
    jfg::ControllerPakStore restored({64U, 4U});
    check(restored.reload(snapshot).ok(), "fresh store reloads durable snapshot");
    check(restored.enumerate_notes() == source.enumerate_notes(), "note inventory survives reload");
    check(restored.used_bytes() == source.used_bytes(), "capacity accounting survives reload");
    check(restored.read_note("slot-a", 4U, first_payload.size()).bytes ==
              std::vector<std::uint8_t>(first_payload.begin(), first_payload.end()),
          "first note body survives process-style reload");
    check(restored.read_note("slot-b", 1U, second_payload.size()).bytes ==
              std::vector<std::uint8_t>(second_payload.begin(), second_payload.end()),
          "second note body survives process-style reload");
    check(std::filesystem::exists(stale_temporary), "uncommitted sibling file is ignored");

    const auto blocked_destination = directory.path() / "destination-is-directory";
    std::filesystem::create_directory(blocked_destination);
    check(
        source.persist_atomic(blocked_destination).error == jfg::ControllerPakError::io_error,
        "invalid replacement target fails without deleting it");
    check(std::filesystem::is_directory(blocked_destination), "failed replacement preserves target");
}

void test_corrupt_and_malformed_snapshot_rejection() {
    TemporaryDirectory directory;
    const auto valid_path = directory.path() / "valid.bin";
    jfg::ControllerPakStore source({64U, 4U});
    check(source.create_note("slot-a", 8U).ok(), "corruption fixture note is created");
    const std::array<std::uint8_t, 4> payload{1U, 3U, 3U, 7U};
    check(source.write_note("slot-a", 2U, payload).ok(), "corruption fixture is populated");
    check(source.persist_atomic(valid_path).ok(), "corruption fixture is persisted");
    const auto valid = read_file(valid_path);

    jfg::ControllerPakStore destination({64U, 4U});
    check(destination.create_note("keep", 3U).ok(), "transaction sentinel is created");
    const auto sentinel = destination.enumerate_notes();

    const auto expect_rejected = [&](const std::string_view name,
                                     const std::vector<std::uint8_t>& bytes,
                                     const jfg::ControllerPakError expected) {
        const auto path = directory.path() / (std::string{name} + ".bin");
        write_file(path, bytes);
        check(destination.reload(path).error == expected, name);
        check(destination.enumerate_notes() == sentinel, "failed reload preserves live notes");
    };

    auto bad_checksum = valid;
    bad_checksum[0] ^= 0x80U;
    expect_rejected(
        "checksum corruption is rejected",
        bad_checksum,
        jfg::ControllerPakError::corrupt_snapshot);

    std::vector<std::uint8_t> truncated(valid.begin(), valid.begin() + 12);
    expect_rejected(
        "truncated snapshot is rejected",
        truncated,
        jfg::ControllerPakError::corrupt_snapshot);

    auto bad_magic = valid;
    bad_magic[0] = static_cast<std::uint8_t>('X');
    repair_checksum(bad_magic);
    expect_rejected(
        "malformed magic with valid checksum is rejected",
        bad_magic,
        jfg::ControllerPakError::corrupt_snapshot);

    auto unsupported_version = valid;
    unsupported_version[8] = 2U;
    unsupported_version[9] = 0U;
    unsupported_version[10] = 0U;
    unsupported_version[11] = 0U;
    repair_checksum(unsupported_version);
    expect_rejected(
        "unsupported format version is rejected",
        unsupported_version,
        jfg::ControllerPakError::incompatible_snapshot);

    auto invalid_id = valid;
    constexpr std::size_t first_id_offset = 37U;
    invalid_id[first_id_offset] = static_cast<std::uint8_t>('S');
    repair_checksum(invalid_id);
    expect_rejected(
        "invalid note record with valid checksum is rejected",
        invalid_id,
        jfg::ControllerPakError::corrupt_snapshot);

    auto excessive_record_count = valid;
    excessive_record_count[24] = 5U;
    repair_checksum(excessive_record_count);
    expect_rejected(
        "record count beyond configured limit is rejected before parsing",
        excessive_record_count,
        jfg::ControllerPakError::corrupt_snapshot);

    auto excessive_body_length = valid;
    constexpr std::size_t first_body_length_offset = 29U;
    for (std::size_t index = first_body_length_offset;
         index < first_body_length_offset + 8U;
         ++index) {
        excessive_body_length[index] = 0xFFU;
    }
    repair_checksum(excessive_body_length);
    expect_rejected(
        "body length beyond capacity is rejected before allocation",
        excessive_body_length,
        jfg::ControllerPakError::corrupt_snapshot);

    auto trailing_payload = valid;
    trailing_payload.insert(trailing_payload.end() - 4, 0U);
    repair_checksum(trailing_payload);
    expect_rejected(
        "unexpected trailing payload is rejected",
        trailing_payload,
        jfg::ControllerPakError::corrupt_snapshot);

    jfg::ControllerPakStore different_geometry({32U, 4U});
    check(
        different_geometry.reload(valid_path).error ==
            jfg::ControllerPakError::incompatible_snapshot,
        "snapshot with different capacity is rejected");
    check(
        destination.reload(directory.path() / "missing.bin").error ==
            jfg::ControllerPakError::io_error,
        "missing snapshot is rejected");
    check(
        destination.reload(directory.path()).error == jfg::ControllerPakError::io_error,
        "directory is rejected as a snapshot");

    std::vector<std::uint8_t> oversized(512U, 0U);
    expect_rejected(
        "snapshot larger than configured maximum is rejected",
        oversized,
        jfg::ControllerPakError::corrupt_snapshot);
}

}  // namespace

int main() noexcept {
    try {
        test_configuration_bounds();
        test_in_memory_lifecycle();
        test_move_preserves_store_invariants();
        test_persistence_round_trip_and_determinism();
        test_corrupt_and_malformed_snapshot_rejection();

        if (failures != 0) {
            std::cerr << failures << " Controller Pak assertion(s) failed\n";
            return 1;
        }
        std::cout << "All ROM-free Controller Pak tests passed\n";
        return 0;
    } catch (const std::exception&) {
        std::fputs("Controller Pak test harness failed unexpectedly\n", stderr);
        return 1;
    } catch (...) {
        std::fputs("Controller Pak test harness failed unexpectedly\n", stderr);
        return 1;
    }
}
