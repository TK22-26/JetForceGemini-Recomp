#include "jfg/runtime/controller_pak.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <limits>
#include <stdexcept>
#include <system_error>
#include <utility>

#if defined(_WIN32)
#define NOMINMAX
#include <Windows.h>
#else
#include <cerrno>
#include <fcntl.h>
#include <unistd.h>
#endif

namespace jfg {

struct ControllerPakStore::Note {
    std::string id;
    std::vector<std::uint8_t> bytes;
};

namespace {

constexpr std::array<std::uint8_t, 8> kSnapshotMagic{
    'J', 'F', 'G', 'P', 'A', 'K', '0', '1'};
constexpr std::uint32_t kSnapshotVersion = 1U;
constexpr std::size_t kSnapshotHeaderBytes = 28U;
constexpr std::size_t kSnapshotChecksumBytes = 4U;

[[nodiscard]] ControllerPakResult result(const ControllerPakError error) noexcept {
    return {error};
}

[[nodiscard]] bool valid_note_id(const std::string_view id) noexcept {
    if (id.empty() || id.size() > kMaximumControllerPakNoteIdBytes) {
        return false;
    }
    const auto first = static_cast<unsigned char>(id.front());
    if (first < static_cast<unsigned char>('a') || first > static_cast<unsigned char>('z')) {
        return false;
    }
    return std::all_of(id.begin() + 1, id.end(), [](const char value) {
        const auto byte = static_cast<unsigned char>(value);
        return (byte >= static_cast<unsigned char>('a') &&
                byte <= static_cast<unsigned char>('z')) ||
            (byte >= static_cast<unsigned char>('0') &&
             byte <= static_cast<unsigned char>('9')) ||
            byte == static_cast<unsigned char>('-');
    });
}

void append_u32(std::vector<std::uint8_t>& output, const std::uint32_t value) {
    for (unsigned int shift = 0; shift < 32U; shift += 8U) {
        output.push_back(static_cast<std::uint8_t>(value >> shift));
    }
}

void append_u64(std::vector<std::uint8_t>& output, const std::uint64_t value) {
    for (unsigned int shift = 0; shift < 64U; shift += 8U) {
        output.push_back(static_cast<std::uint8_t>(value >> shift));
    }
}

[[nodiscard]] std::uint32_t crc32(const std::span<const std::uint8_t> bytes) noexcept {
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

class SnapshotReader final {
public:
    explicit SnapshotReader(const std::span<const std::uint8_t> bytes) : bytes_(bytes) {}

    [[nodiscard]] bool take_u8(std::uint8_t& value) noexcept {
        if (remaining() < 1U) {
            return false;
        }
        value = bytes_[offset_];
        ++offset_;
        return true;
    }

    [[nodiscard]] bool take_u32(std::uint32_t& value) noexcept {
        if (remaining() < 4U) {
            return false;
        }
        value = 0;
        for (unsigned int index = 0; index < 4U; ++index) {
            value |= static_cast<std::uint32_t>(bytes_[offset_ + index]) << (index * 8U);
        }
        offset_ += 4U;
        return true;
    }

    [[nodiscard]] bool take_u64(std::uint64_t& value) noexcept {
        if (remaining() < 8U) {
            return false;
        }
        value = 0;
        for (unsigned int index = 0; index < 8U; ++index) {
            value |= static_cast<std::uint64_t>(bytes_[offset_ + index]) << (index * 8U);
        }
        offset_ += 8U;
        return true;
    }

    [[nodiscard]] bool take_bytes(
        const std::size_t length,
        std::span<const std::uint8_t>& value) noexcept {
        if (length > remaining()) {
            return false;
        }
        value = bytes_.subspan(offset_, length);
        offset_ += length;
        return true;
    }

    [[nodiscard]] std::size_t remaining() const noexcept {
        return bytes_.size() - offset_;
    }

private:
    std::span<const std::uint8_t> bytes_;
    std::size_t offset_ = 0;
};

[[nodiscard]] std::uint32_t read_trailing_u32(
    const std::span<const std::uint8_t> bytes) noexcept {
    const std::size_t offset = bytes.size() - kSnapshotChecksumBytes;
    std::uint32_t value = 0;
    for (unsigned int index = 0; index < 4U; ++index) {
        value |= static_cast<std::uint32_t>(bytes[offset + index]) << (index * 8U);
    }
    return value;
}

[[nodiscard]] std::size_t maximum_snapshot_bytes(
    const std::size_t capacity_bytes,
    const std::size_t max_notes) noexcept {
    constexpr std::size_t record_overhead = 1U + 8U + kMaximumControllerPakNoteIdBytes;
    return kSnapshotHeaderBytes + kSnapshotChecksumBytes + capacity_bytes +
        max_notes * record_overhead;
}

[[nodiscard]] std::filesystem::path temporary_path(
    const std::filesystem::path& destination,
    const std::uint64_t token) {
#if defined(_WIN32)
    return destination.parent_path() /
        (destination.filename().wstring() + L".tmp-" + std::to_wstring(token));
#else
    return destination.parent_path() /
        (destination.filename().string() + ".tmp-" + std::to_string(token));
#endif
}

[[nodiscard]] std::uint64_t next_temporary_token() noexcept {
    static std::atomic<std::uint64_t> sequence{0};
    const auto timestamp = static_cast<std::uint64_t>(
        std::chrono::steady_clock::now().time_since_epoch().count());
#if defined(_WIN32)
    const auto process = static_cast<std::uint64_t>(GetCurrentProcessId());
#else
    const auto process = static_cast<std::uint64_t>(::getpid());
#endif
    return timestamp ^ (process << 32U) ^ sequence.fetch_add(1U, std::memory_order_relaxed);
}

void remove_temporary(const std::filesystem::path& path) noexcept {
    std::error_code ignored;
    std::filesystem::remove(path, ignored);
}

#if defined(_WIN32)
[[nodiscard]] bool write_new_file(
    const std::filesystem::path& path,
    const std::span<const std::uint8_t> bytes,
    bool& collision) noexcept {
    collision = false;
    const HANDLE handle = CreateFileW(
        path.c_str(),
        GENERIC_WRITE,
        0,
        nullptr,
        CREATE_NEW,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);
    if (handle == INVALID_HANDLE_VALUE) {
        const DWORD error = GetLastError();
        collision = error == ERROR_FILE_EXISTS || error == ERROR_ALREADY_EXISTS;
        return false;
    }

    bool success = true;
    std::size_t offset = 0;
    while (offset < bytes.size()) {
        const std::size_t remaining = bytes.size() - offset;
        const auto chunk = static_cast<DWORD>(std::min<std::size_t>(
            remaining,
            static_cast<std::size_t>((std::numeric_limits<DWORD>::max)())));
        DWORD written = 0;
        if (WriteFile(handle, bytes.data() + offset, chunk, &written, nullptr) == 0 ||
            written != chunk) {
            success = false;
            break;
        }
        offset += static_cast<std::size_t>(written);
    }
    if (success && FlushFileBuffers(handle) == 0) {
        success = false;
    }
    if (CloseHandle(handle) == 0) {
        success = false;
    }
    return success;
}

[[nodiscard]] bool replace_file_atomically(
    const std::filesystem::path& temporary,
    const std::filesystem::path& destination) noexcept {
    return MoveFileExW(
        temporary.c_str(),
        destination.c_str(),
        MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) != 0;
}
#else
[[nodiscard]] bool write_new_file(
    const std::filesystem::path& path,
    const std::span<const std::uint8_t> bytes,
    bool& collision) noexcept {
    collision = false;
    const int descriptor = ::open(
        path.c_str(),
        O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC,
        static_cast<mode_t>(0600));
    if (descriptor < 0) {
        collision = errno == EEXIST;
        return false;
    }

    bool success = true;
    std::size_t offset = 0;
    while (offset < bytes.size()) {
        const ssize_t written = ::write(
            descriptor,
            bytes.data() + offset,
            bytes.size() - offset);
        if (written < 0 && errno == EINTR) {
            continue;
        }
        if (written <= 0) {
            success = false;
            break;
        }
        offset += static_cast<std::size_t>(written);
    }
    if (success && ::fsync(descriptor) != 0) {
        success = false;
    }
    if (::close(descriptor) != 0) {
        success = false;
    }
    return success;
}

[[nodiscard]] bool replace_file_atomically(
    const std::filesystem::path& temporary,
    const std::filesystem::path& destination) noexcept {
    if (::rename(temporary.c_str(), destination.c_str()) != 0) {
        return false;
    }
    const auto parent = destination.parent_path().empty()
        ? std::filesystem::path{"."}
        : destination.parent_path();
    const int descriptor = ::open(parent.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (descriptor < 0) {
        return false;
    }
    const bool success = ::fsync(descriptor) == 0;
    const bool closed = ::close(descriptor) == 0;
    return success && closed;
}
#endif

[[nodiscard]] ControllerPakResult write_atomic(
    const std::filesystem::path& destination,
    const std::span<const std::uint8_t> bytes) {
    if (destination.empty() || destination.filename().empty()) {
        return result(ControllerPakError::invalid_argument);
    }

    std::error_code status_error;
    const auto destination_status = std::filesystem::symlink_status(destination, status_error);
    if (!status_error && std::filesystem::exists(destination_status) &&
        !std::filesystem::is_regular_file(destination_status)) {
        return result(ControllerPakError::io_error);
    }

    std::filesystem::path temporary;
    bool written = false;
    for (unsigned int attempt = 0; attempt < 64U; ++attempt) {
        temporary = temporary_path(destination, next_temporary_token());
        bool collision = false;
        if (write_new_file(temporary, bytes, collision)) {
            written = true;
            break;
        }
        if (!collision) {
            remove_temporary(temporary);
            return result(ControllerPakError::io_error);
        }
    }
    if (!written) {
        return result(ControllerPakError::io_error);
    }
    if (!replace_file_atomically(temporary, destination)) {
        remove_temporary(temporary);
        return result(ControllerPakError::io_error);
    }
    return result(ControllerPakError::none);
}

}  // namespace

ControllerPakStore::ControllerPakStore(const ControllerPakGeometry geometry)
    : capacity_bytes_(geometry.capacity_bytes), max_notes_(geometry.max_notes) {
    if (capacity_bytes_ == 0U || capacity_bytes_ > kMaximumControllerPakCapacityBytes) {
        throw std::invalid_argument("Controller Pak capacity is outside the supported bound");
    }
    if (max_notes_ == 0U || max_notes_ > kMaximumControllerPakNotes) {
        throw std::invalid_argument("Controller Pak note count is outside the supported bound");
    }
}

ControllerPakStore::~ControllerPakStore() = default;

ControllerPakStore::ControllerPakStore(ControllerPakStore&& other) noexcept
    : capacity_bytes_(other.capacity_bytes_),
      max_notes_(other.max_notes_),
      used_bytes_(other.used_bytes_),
      notes_(std::move(other.notes_)) {
    other.used_bytes_ = 0U;
    other.notes_.clear();
}

ControllerPakStore& ControllerPakStore::operator=(ControllerPakStore&& other) noexcept {
    if (this != &other) {
        capacity_bytes_ = other.capacity_bytes_;
        max_notes_ = other.max_notes_;
        used_bytes_ = other.used_bytes_;
        notes_ = std::move(other.notes_);
        other.used_bytes_ = 0U;
        other.notes_.clear();
    }
    return *this;
}

std::size_t ControllerPakStore::capacity_bytes() const noexcept {
    return capacity_bytes_;
}

std::size_t ControllerPakStore::used_bytes() const noexcept {
    return used_bytes_;
}

std::size_t ControllerPakStore::free_bytes() const noexcept {
    return capacity_bytes_ - used_bytes_;
}

std::size_t ControllerPakStore::max_notes() const noexcept {
    return max_notes_;
}

std::size_t ControllerPakStore::note_count() const noexcept {
    return notes_.size();
}

ControllerPakResult ControllerPakStore::create_note(
    const std::string_view id,
    const std::size_t size) {
    if (!valid_note_id(id)) {
        return result(ControllerPakError::invalid_note_id);
    }
    const auto existing = std::lower_bound(
        notes_.begin(),
        notes_.end(),
        id,
        [](const Note& note, const std::string_view candidate) { return note.id < candidate; });
    if (existing != notes_.end() && existing->id == id) {
        return result(ControllerPakError::note_exists);
    }
    if (notes_.size() >= max_notes_) {
        return result(ControllerPakError::note_limit_reached);
    }
    if (size == 0U) {
        return result(ControllerPakError::invalid_argument);
    }
    if (size > free_bytes()) {
        return result(ControllerPakError::capacity_exceeded);
    }

    Note note{std::string{id}, std::vector<std::uint8_t>(size, 0U)};
    notes_.insert(existing, std::move(note));
    used_bytes_ += size;
    return result(ControllerPakError::none);
}

ControllerPakResult ControllerPakStore::delete_note(const std::string_view id) {
    if (!valid_note_id(id)) {
        return result(ControllerPakError::invalid_note_id);
    }
    const auto existing = std::lower_bound(
        notes_.begin(),
        notes_.end(),
        id,
        [](const Note& note, const std::string_view candidate) { return note.id < candidate; });
    if (existing == notes_.end() || existing->id != id) {
        return result(ControllerPakError::note_not_found);
    }
    used_bytes_ -= existing->bytes.size();
    notes_.erase(existing);
    return result(ControllerPakError::none);
}

ControllerPakResult ControllerPakStore::write_note(
    const std::string_view id,
    const std::size_t offset,
    const std::span<const std::uint8_t> bytes) {
    if (!valid_note_id(id)) {
        return result(ControllerPakError::invalid_note_id);
    }
    const auto existing = std::lower_bound(
        notes_.begin(),
        notes_.end(),
        id,
        [](const Note& note, const std::string_view candidate) { return note.id < candidate; });
    if (existing == notes_.end() || existing->id != id) {
        return result(ControllerPakError::note_not_found);
    }
    if (offset > existing->bytes.size() || bytes.size() > existing->bytes.size() - offset) {
        return result(ControllerPakError::out_of_bounds);
    }
    std::copy(bytes.begin(), bytes.end(), existing->bytes.begin() +
        static_cast<std::vector<std::uint8_t>::difference_type>(offset));
    return result(ControllerPakError::none);
}

ControllerPakReadResult ControllerPakStore::read_note(
    const std::string_view id,
    const std::size_t offset,
    const std::size_t length) const {
    if (!valid_note_id(id)) {
        return {ControllerPakError::invalid_note_id, {}};
    }
    const auto existing = std::lower_bound(
        notes_.begin(),
        notes_.end(),
        id,
        [](const Note& note, const std::string_view candidate) { return note.id < candidate; });
    if (existing == notes_.end() || existing->id != id) {
        return {ControllerPakError::note_not_found, {}};
    }
    if (offset > existing->bytes.size() || length > existing->bytes.size() - offset) {
        return {ControllerPakError::out_of_bounds, {}};
    }
    const auto begin = existing->bytes.begin() +
        static_cast<std::vector<std::uint8_t>::difference_type>(offset);
    const auto end = begin + static_cast<std::vector<std::uint8_t>::difference_type>(length);
    return {ControllerPakError::none, std::vector<std::uint8_t>(begin, end)};
}

std::vector<ControllerPakNoteInfo> ControllerPakStore::enumerate_notes() const {
    std::vector<ControllerPakNoteInfo> result_notes;
    result_notes.reserve(notes_.size());
    for (const Note& note : notes_) {
        result_notes.push_back({note.id, note.bytes.size()});
    }
    return result_notes;
}

ControllerPakResult ControllerPakStore::persist_atomic(
    const std::filesystem::path& destination) const {
    std::vector<std::uint8_t> snapshot;
    snapshot.reserve(kSnapshotHeaderBytes + kSnapshotChecksumBytes + used_bytes_ +
        notes_.size() * (1U + 8U + kMaximumControllerPakNoteIdBytes));
    snapshot.insert(snapshot.end(), kSnapshotMagic.begin(), kSnapshotMagic.end());
    append_u32(snapshot, kSnapshotVersion);
    append_u64(snapshot, static_cast<std::uint64_t>(capacity_bytes_));
    append_u32(snapshot, static_cast<std::uint32_t>(max_notes_));
    append_u32(snapshot, static_cast<std::uint32_t>(notes_.size()));
    for (const Note& note : notes_) {
        snapshot.push_back(static_cast<std::uint8_t>(note.id.size()));
        append_u64(snapshot, static_cast<std::uint64_t>(note.bytes.size()));
        snapshot.insert(snapshot.end(), note.id.begin(), note.id.end());
        snapshot.insert(snapshot.end(), note.bytes.begin(), note.bytes.end());
    }
    append_u32(snapshot, crc32(snapshot));
    return write_atomic(destination, snapshot);
}

ControllerPakResult ControllerPakStore::reload(const std::filesystem::path& source) {
    if (source.empty() || source.filename().empty()) {
        return result(ControllerPakError::invalid_argument);
    }
    std::error_code error;
    const auto status = std::filesystem::symlink_status(source, error);
    if (error || !std::filesystem::is_regular_file(status)) {
        return result(ControllerPakError::io_error);
    }
    const std::uintmax_t file_size = std::filesystem::file_size(source, error);
    if (error) {
        return result(ControllerPakError::io_error);
    }
    if (file_size < kSnapshotHeaderBytes + kSnapshotChecksumBytes ||
        file_size > maximum_snapshot_bytes(capacity_bytes_, max_notes_)) {
        return result(ControllerPakError::corrupt_snapshot);
    }

    std::vector<std::uint8_t> snapshot(static_cast<std::size_t>(file_size));
    std::ifstream stream(source, std::ios::binary);
    if (!stream.read(
            reinterpret_cast<char*>(snapshot.data()),
            static_cast<std::streamsize>(snapshot.size())) ||
        stream.peek() != std::ifstream::traits_type::eof()) {
        return result(ControllerPakError::io_error);
    }

    const auto payload = std::span<const std::uint8_t>(snapshot).first(
        snapshot.size() - kSnapshotChecksumBytes);
    if (read_trailing_u32(snapshot) != crc32(payload)) {
        return result(ControllerPakError::corrupt_snapshot);
    }

    SnapshotReader reader(payload);
    std::span<const std::uint8_t> magic;
    std::uint32_t version = 0;
    std::uint64_t stored_capacity = 0;
    std::uint32_t stored_max_notes = 0;
    std::uint32_t count = 0;
    if (!reader.take_bytes(kSnapshotMagic.size(), magic) ||
        !std::equal(magic.begin(), magic.end(), kSnapshotMagic.begin()) ||
        !reader.take_u32(version)) {
        return result(ControllerPakError::corrupt_snapshot);
    }
    if (version != kSnapshotVersion) {
        return result(ControllerPakError::incompatible_snapshot);
    }
    if (!reader.take_u64(stored_capacity) || !reader.take_u32(stored_max_notes) ||
        !reader.take_u32(count)) {
        return result(ControllerPakError::corrupt_snapshot);
    }
    if (stored_capacity != static_cast<std::uint64_t>(capacity_bytes_) ||
        stored_max_notes != static_cast<std::uint32_t>(max_notes_)) {
        return result(ControllerPakError::incompatible_snapshot);
    }
    if (count > max_notes_) {
        return result(ControllerPakError::corrupt_snapshot);
    }

    std::vector<Note> parsed_notes;
    parsed_notes.reserve(count);
    std::size_t parsed_bytes = 0;
    std::string previous_id;
    for (std::uint32_t index = 0; index < count; ++index) {
        std::uint8_t id_length = 0;
        std::uint64_t body_length = 0;
        if (!reader.take_u8(id_length) || !reader.take_u64(body_length) ||
            id_length == 0U || id_length > kMaximumControllerPakNoteIdBytes ||
            body_length == 0U || body_length > capacity_bytes_ - parsed_bytes) {
            return result(ControllerPakError::corrupt_snapshot);
        }
        std::span<const std::uint8_t> id_bytes;
        std::span<const std::uint8_t> body;
        if (!reader.take_bytes(id_length, id_bytes) ||
            !reader.take_bytes(static_cast<std::size_t>(body_length), body)) {
            return result(ControllerPakError::corrupt_snapshot);
        }
        const std::string id(id_bytes.begin(), id_bytes.end());
        if (!valid_note_id(id) || (!previous_id.empty() && id <= previous_id)) {
            return result(ControllerPakError::corrupt_snapshot);
        }
        parsed_notes.push_back({id, std::vector<std::uint8_t>(body.begin(), body.end())});
        previous_id = id;
        parsed_bytes += static_cast<std::size_t>(body_length);
    }
    if (reader.remaining() != 0U) {
        return result(ControllerPakError::corrupt_snapshot);
    }

    notes_ = std::move(parsed_notes);
    used_bytes_ = parsed_bytes;
    return result(ControllerPakError::none);
}

std::string_view controller_pak_error_message(const ControllerPakError error) noexcept {
    switch (error) {
        case ControllerPakError::none:
            return "operation completed";
        case ControllerPakError::invalid_argument:
            return "invalid Controller Pak operation";
        case ControllerPakError::invalid_note_id:
            return "invalid opaque note identifier";
        case ControllerPakError::note_exists:
            return "note already exists";
        case ControllerPakError::note_not_found:
            return "note does not exist";
        case ControllerPakError::note_limit_reached:
            return "note limit reached";
        case ControllerPakError::capacity_exceeded:
            return "Controller Pak capacity exceeded";
        case ControllerPakError::out_of_bounds:
            return "note operation exceeds its bounds";
        case ControllerPakError::no_device:
            return "no controller accessory is connected";
        case ControllerPakError::wrong_accessory:
            return "the connected accessory is not a Controller Pak";
        case ControllerPakError::stale_session:
            return "the Controller Pak session is stale";
        case ControllerPakError::io_error:
            return "snapshot I/O failed";
        case ControllerPakError::corrupt_snapshot:
            return "snapshot is malformed or corrupt";
        case ControllerPakError::incompatible_snapshot:
            return "snapshot format or geometry is incompatible";
    }
    return "unknown Controller Pak error";
}

}  // namespace jfg
