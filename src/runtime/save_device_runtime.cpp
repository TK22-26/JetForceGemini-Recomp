#include "jfg/runtime/save_device_runtime.hpp"

#include <algorithm>
#include <atomic>
#include <chrono>
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

struct ControllerAccessoryBus::Port {
    ControllerAccessoryKind kind = ControllerAccessoryKind::none;
    std::uint64_t generation = 1U;
    std::unique_ptr<ControllerPakStore> controller_pak;
    bool rumble_active = false;
};

namespace {

[[nodiscard]] ControllerPakResult controller_result(
    const ControllerPakError error) noexcept {
    return {error};
}

[[nodiscard]] FlashRamResult flash_result(const FlashRamError error) noexcept {
    return {error};
}

[[nodiscard]] std::uint64_t next_bus_identity() noexcept {
    static std::atomic<std::uint64_t> sequence{1U};
    std::uint64_t identity = sequence.fetch_add(1U, std::memory_order_relaxed);
    if (identity == 0U) {
        identity = sequence.fetch_add(1U, std::memory_order_relaxed);
    }
    return identity;
}

[[nodiscard]] bool valid_accessory_kind(const ControllerAccessoryKind kind) noexcept {
    switch (kind) {
        case ControllerAccessoryKind::none:
        case ControllerAccessoryKind::controller_pak:
        case ControllerAccessoryKind::rumble_pak:
            return true;
    }
    return false;
}

[[nodiscard]] std::filesystem::path flash_temporary_path(
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

[[nodiscard]] std::uint64_t next_flash_temporary_token() noexcept {
    static std::atomic<std::uint64_t> sequence{0U};
    const auto timestamp = static_cast<std::uint64_t>(
        std::chrono::steady_clock::now().time_since_epoch().count());
#if defined(_WIN32)
    const auto process = static_cast<std::uint64_t>(GetCurrentProcessId());
#else
    const auto process = static_cast<std::uint64_t>(::getpid());
#endif
    return timestamp ^ (process << 32U) ^
        sequence.fetch_add(1U, std::memory_order_relaxed);
}

void remove_flash_temporary(const std::filesystem::path& path) noexcept {
    std::error_code ignored;
    std::filesystem::remove(path, ignored);
}

#if defined(_WIN32)
[[nodiscard]] bool write_new_flash_file(
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
    std::size_t offset = 0U;
    while (offset < bytes.size()) {
        const std::size_t remaining = bytes.size() - offset;
        const auto chunk = static_cast<DWORD>(std::min<std::size_t>(
            remaining,
            static_cast<std::size_t>((std::numeric_limits<DWORD>::max)())));
        DWORD written = 0U;
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

[[nodiscard]] bool replace_flash_file_atomically(
    const std::filesystem::path& temporary,
    const std::filesystem::path& destination) noexcept {
    return MoveFileExW(
        temporary.c_str(),
        destination.c_str(),
        MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) != 0;
}
#else
[[nodiscard]] bool write_new_flash_file(
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
    std::size_t offset = 0U;
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

[[nodiscard]] bool replace_flash_file_atomically(
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
    const bool synchronized = ::fsync(descriptor) == 0;
    const bool closed = ::close(descriptor) == 0;
    return synchronized && closed;
}
#endif

[[nodiscard]] FlashRamResult write_flash_image_atomic(
    const std::filesystem::path& destination,
    const std::span<const std::uint8_t> bytes) {
    if (destination.empty() || destination.filename().empty() ||
        bytes.size() != kFlashRamSizeBytes) {
        return flash_result(FlashRamError::invalid_argument);
    }

    std::error_code status_error;
    const auto destination_status = std::filesystem::symlink_status(
        destination, status_error);
    if (!status_error && std::filesystem::exists(destination_status) &&
        !std::filesystem::is_regular_file(destination_status)) {
        return flash_result(FlashRamError::io_error);
    }

    std::filesystem::path temporary;
    bool written = false;
    for (unsigned int attempt = 0U; attempt < 64U; ++attempt) {
        temporary = flash_temporary_path(destination, next_flash_temporary_token());
        bool collision = false;
        if (write_new_flash_file(temporary, bytes, collision)) {
            written = true;
            break;
        }
        if (!collision) {
            remove_flash_temporary(temporary);
            return flash_result(FlashRamError::io_error);
        }
    }
    if (!written) {
        return flash_result(FlashRamError::io_error);
    }
    if (!replace_flash_file_atomically(temporary, destination)) {
        remove_flash_temporary(temporary);
        return flash_result(FlashRamError::io_error);
    }
    return flash_result(FlashRamError::none);
}

}  // namespace

ControllerPakSession::ControllerPakSession(
    const std::size_t port,
    const std::uint64_t generation,
    const std::uint64_t bus_identity) noexcept
    : port_(port), generation_(generation), bus_identity_(bus_identity) {}

ControllerAccessoryBus::ControllerAccessoryBus(
    const ControllerPakGeometry controller_pak_geometry)
    : geometry_(controller_pak_geometry), identity_(next_bus_identity()) {
    // Validate geometry once without retaining a disposable store.
    const ControllerPakStore validation{geometry_};
    (void)validation;
    for (auto& port : ports_) {
        port = std::make_unique<Port>();
    }
}

ControllerAccessoryBus::~ControllerAccessoryBus() = default;

ControllerPakResult ControllerAccessoryBus::set_accessory(
    const std::size_t port,
    const ControllerAccessoryKind kind) {
    if (port >= ports_.size() || !valid_accessory_kind(kind)) {
        return controller_result(ControllerPakError::invalid_argument);
    }
    Port& state = *ports_[port];
    if (state.kind == kind) {
        return controller_result(ControllerPakError::none);
    }
    // The project-owned store represents the physical Pak assigned to this
    // port. Detaching or temporarily selecting a Rumble Pak invalidates the
    // host session without erasing non-volatile Controller Pak contents.
    std::unique_ptr<ControllerPakStore> candidate;
    if (kind == ControllerAccessoryKind::controller_pak && !state.controller_pak) {
        candidate = std::make_unique<ControllerPakStore>(geometry_);
    }
    state.kind = kind;
    ++state.generation;
    if (state.generation == 0U) {
        ++state.generation;
    }
    state.rumble_active = false;
    if (candidate) {
        state.controller_pak = std::move(candidate);
    }
    return controller_result(ControllerPakError::none);
}

ControllerAccessoryKind ControllerAccessoryBus::accessory(
    const std::size_t port) const noexcept {
    return port < ports_.size() ? ports_[port]->kind : ControllerAccessoryKind::none;
}

ControllerPakProbeResult ControllerAccessoryBus::probe_controller_pak(
    const std::size_t port) const {
    if (port >= ports_.size()) {
        return {ControllerPakError::invalid_argument, {}};
    }
    const Port& state = *ports_[port];
    if (state.kind == ControllerAccessoryKind::none) {
        return {ControllerPakError::no_device, {}};
    }
    if (state.kind != ControllerAccessoryKind::controller_pak || !state.controller_pak) {
        return {ControllerPakError::wrong_accessory, {}};
    }
    return {
        ControllerPakError::none,
        ControllerPakSession{port, state.generation, identity_},
    };
}

ControllerPakError ControllerAccessoryBus::validate_session(
    const ControllerPakSession session) const noexcept {
    if (session.bus_identity_ != identity_) {
        return ControllerPakError::stale_session;
    }
    if (session.port_ >= ports_.size()) {
        return ControllerPakError::invalid_argument;
    }
    const Port& state = *ports_[session.port_];
    if (state.kind == ControllerAccessoryKind::none) {
        return ControllerPakError::no_device;
    }
    if (state.kind != ControllerAccessoryKind::controller_pak || !state.controller_pak) {
        return ControllerPakError::wrong_accessory;
    }
    if (session.generation_ == 0U || session.generation_ != state.generation) {
        return ControllerPakError::stale_session;
    }
    return ControllerPakError::none;
}

ControllerPakResult ControllerAccessoryBus::create_note(
    const ControllerPakSession session,
    const std::string_view id,
    const std::size_t size) {
    const ControllerPakError validation = validate_session(session);
    return validation == ControllerPakError::none
        ? ports_[session.port_]->controller_pak->create_note(id, size)
        : controller_result(validation);
}

ControllerPakResult ControllerAccessoryBus::delete_note(
    const ControllerPakSession session,
    const std::string_view id) {
    const ControllerPakError validation = validate_session(session);
    return validation == ControllerPakError::none
        ? ports_[session.port_]->controller_pak->delete_note(id)
        : controller_result(validation);
}

ControllerPakResult ControllerAccessoryBus::write_note(
    const ControllerPakSession session,
    const std::string_view id,
    const std::size_t offset,
    const std::span<const std::uint8_t> bytes) {
    const ControllerPakError validation = validate_session(session);
    return validation == ControllerPakError::none
        ? ports_[session.port_]->controller_pak->write_note(id, offset, bytes)
        : controller_result(validation);
}

ControllerPakReadResult ControllerAccessoryBus::read_note(
    const ControllerPakSession session,
    const std::string_view id,
    const std::size_t offset,
    const std::size_t length) const {
    const ControllerPakError validation = validate_session(session);
    return validation == ControllerPakError::none
        ? ports_[session.port_]->controller_pak->read_note(id, offset, length)
        : ControllerPakReadResult{validation, {}};
}

std::vector<ControllerPakNoteInfo> ControllerAccessoryBus::enumerate_notes(
    const ControllerPakSession session,
    ControllerPakError& error) const {
    error = validate_session(session);
    if (error != ControllerPakError::none) {
        return {};
    }
    return ports_[session.port_]->controller_pak->enumerate_notes();
}

ControllerPakResult ControllerAccessoryBus::persist(
    const ControllerPakSession session,
    const std::filesystem::path& destination) const {
    const ControllerPakError validation = validate_session(session);
    return validation == ControllerPakError::none
        ? ports_[session.port_]->controller_pak->persist_atomic(destination)
        : controller_result(validation);
}

ControllerPakResult ControllerAccessoryBus::reload(
    const ControllerPakSession session,
    const std::filesystem::path& source) {
    const ControllerPakError validation = validate_session(session);
    return validation == ControllerPakError::none
        ? ports_[session.port_]->controller_pak->reload(source)
        : controller_result(validation);
}

ControllerPakResult ControllerAccessoryBus::set_rumble(
    const std::size_t port,
    const bool active) {
    if (port >= ports_.size()) {
        return controller_result(ControllerPakError::invalid_argument);
    }
    Port& state = *ports_[port];
    if (state.kind == ControllerAccessoryKind::none) {
        return controller_result(ControllerPakError::no_device);
    }
    if (state.kind != ControllerAccessoryKind::rumble_pak) {
        return controller_result(ControllerPakError::wrong_accessory);
    }
    state.rumble_active = active;
    return controller_result(ControllerPakError::none);
}

bool ControllerAccessoryBus::rumble_active(const std::size_t port) const noexcept {
    return port < ports_.size() && ports_[port]->kind == ControllerAccessoryKind::rumble_pak &&
        ports_[port]->rumble_active;
}

FlashRamStore::FlashRamStore() : bytes_(kFlashRamSizeBytes, 0xFFU) {}

FlashRamStatus FlashRamStore::status() const noexcept {
    return {operation_, operation_ != FlashRamOperation::none, write_buffer_valid_};
}

FlashRamResult FlashRamStore::stage_write(
    const std::span<const std::uint8_t> page_bytes) {
    if (operation_ != FlashRamOperation::none) {
        return flash_result(FlashRamError::busy);
    }
    if (page_bytes.size() != write_buffer_.size()) {
        return flash_result(FlashRamError::invalid_argument);
    }
    std::copy(page_bytes.begin(), page_bytes.end(), write_buffer_.begin());
    write_buffer_valid_ = true;
    return flash_result(FlashRamError::none);
}

FlashRamResult FlashRamStore::begin_program(const std::size_t page_index) {
    if (operation_ != FlashRamOperation::none) {
        return flash_result(FlashRamError::busy);
    }
    if (page_index >= kFlashRamPageCount) {
        return flash_result(FlashRamError::out_of_bounds);
    }
    if (!write_buffer_valid_) {
        return flash_result(FlashRamError::write_buffer_empty);
    }
    operation_ = FlashRamOperation::program_page;
    operation_page_ = page_index;
    return flash_result(FlashRamError::none);
}

FlashRamResult FlashRamStore::begin_erase_page(const std::size_t page_index) {
    if (operation_ != FlashRamOperation::none) {
        return flash_result(FlashRamError::busy);
    }
    if (page_index >= kFlashRamPageCount) {
        return flash_result(FlashRamError::out_of_bounds);
    }
    operation_ = FlashRamOperation::erase_page;
    operation_page_ = page_index;
    return flash_result(FlashRamError::none);
}

FlashRamResult FlashRamStore::begin_erase_all() {
    if (operation_ != FlashRamOperation::none) {
        return flash_result(FlashRamError::busy);
    }
    operation_ = FlashRamOperation::erase_all;
    operation_page_ = 0;
    return flash_result(FlashRamError::none);
}

std::vector<std::uint8_t> FlashRamStore::completed_image() const {
    std::vector<std::uint8_t> candidate = bytes_;
    if (operation_ == FlashRamOperation::program_page) {
        const std::size_t offset = operation_page_ * kFlashRamPageBytes;
        std::copy(
            write_buffer_.begin(),
            write_buffer_.end(),
            candidate.begin() + static_cast<std::ptrdiff_t>(offset));
    } else if (operation_ == FlashRamOperation::erase_page) {
        const std::size_t offset = operation_page_ * kFlashRamPageBytes;
        std::fill_n(candidate.begin() + static_cast<std::ptrdiff_t>(offset),
                    kFlashRamPageBytes,
                    static_cast<std::uint8_t>(0xFFU));
    } else if (operation_ == FlashRamOperation::erase_all) {
        std::fill(candidate.begin(), candidate.end(), static_cast<std::uint8_t>(0xFFU));
    }
    return candidate;
}

FlashRamResult FlashRamStore::complete() {
    if (operation_ == FlashRamOperation::none) {
        return flash_result(FlashRamError::invalid_argument);
    }
    bytes_ = completed_image();
    operation_ = FlashRamOperation::none;
    return flash_result(FlashRamError::none);
}

FlashRamResult FlashRamStore::persist_image(
    const std::span<const std::uint8_t> image,
    const std::filesystem::path& destination) {
    if (image.size() != kFlashRamSizeBytes) {
        return flash_result(FlashRamError::invalid_argument);
    }
    return write_flash_image_atomic(destination, image);
}

FlashRamResult FlashRamStore::complete_and_persist(
    const std::filesystem::path& destination) {
    if (operation_ == FlashRamOperation::none) {
        return flash_result(FlashRamError::invalid_argument);
    }
    if (destination.empty() || destination.filename().empty()) {
        return flash_result(FlashRamError::invalid_argument);
    }
    // Device completion and host durability are separate events. Commit the
    // completed command in memory first; a persistence failure can then be
    // retried with persist_atomic without retaining an ambiguous busy state.
    bytes_ = completed_image();
    operation_ = FlashRamOperation::none;
    return persist_image(bytes_, destination);
}

void FlashRamStore::interrupt() noexcept {
    operation_ = FlashRamOperation::none;
    operation_page_ = 0;
}

FlashRamReadResult FlashRamStore::read(
    const std::size_t offset,
    const std::size_t length) const {
    if (offset > bytes_.size() || length > bytes_.size() - offset) {
        return {FlashRamError::out_of_bounds, {}};
    }
    return {
        FlashRamError::none,
        std::vector<std::uint8_t>(
            bytes_.begin() + static_cast<std::ptrdiff_t>(offset),
            bytes_.begin() + static_cast<std::ptrdiff_t>(offset + length)),
    };
}

FlashRamResult FlashRamStore::persist_atomic(
    const std::filesystem::path& destination) const {
    if (operation_ != FlashRamOperation::none) {
        return flash_result(FlashRamError::busy);
    }
    return persist_image(bytes_, destination);
}

FlashRamResult FlashRamStore::reload(const std::filesystem::path& source) {
    if (operation_ != FlashRamOperation::none) {
        return flash_result(FlashRamError::busy);
    }
    if (source.empty() || source.filename().empty()) {
        return flash_result(FlashRamError::invalid_argument);
    }
    std::error_code status_error;
    const auto status = std::filesystem::symlink_status(source, status_error);
    if (status_error || !std::filesystem::exists(status) ||
        !std::filesystem::is_regular_file(status)) {
        return flash_result(FlashRamError::io_error);
    }
    std::error_code size_error;
    const auto size = std::filesystem::file_size(source, size_error);
    if (size_error) {
        return flash_result(FlashRamError::io_error);
    }
    if (size != kFlashRamSizeBytes) {
        return flash_result(FlashRamError::corrupt_snapshot);
    }
    std::vector<std::uint8_t> image(kFlashRamSizeBytes);
    std::ifstream stream(source, std::ios::binary);
    stream.read(
        reinterpret_cast<char*>(image.data()),
        static_cast<std::streamsize>(image.size()));
    if (!stream || stream.peek() != std::ifstream::traits_type::eof()) {
        return flash_result(FlashRamError::io_error);
    }
    bytes_ = std::move(image);
    write_buffer_valid_ = false;
    operation_ = FlashRamOperation::none;
    operation_page_ = 0;
    return flash_result(FlashRamError::none);
}

std::string_view flash_ram_error_message(const FlashRamError error) noexcept {
    switch (error) {
        case FlashRamError::none:
            return "success";
        case FlashRamError::invalid_argument:
            return "invalid FlashRAM operation";
        case FlashRamError::out_of_bounds:
            return "FlashRAM address is outside the device";
        case FlashRamError::busy:
            return "FlashRAM operation is already active";
        case FlashRamError::write_buffer_empty:
            return "FlashRAM write buffer is empty";
        case FlashRamError::io_error:
            return "FlashRAM persistence failed";
        case FlashRamError::corrupt_snapshot:
            return "FlashRAM raw image has an invalid size";
    }
    return "unknown FlashRAM error";
}

}  // namespace jfg
