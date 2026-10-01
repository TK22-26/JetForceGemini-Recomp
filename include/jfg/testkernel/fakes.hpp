#pragma once

// Test-only fake renderer/audio/storage and the fail-closed host-call gate
// (Phase 5, kernel v0).  Every supported host effect lands in the journal;
// an unsupported host call is journaled as a rejection and reported as a
// hard failure — it never silently succeeds and never reaches a real host
// device.

#include <cstdint>
#include <map>
#include <optional>
#include <span>
#include <string_view>
#include <vector>

#include "jfg/testkernel/journal.hpp"

namespace jfg::testkernel {

enum class HostCall : std::uint32_t {
    kRendererSubmit = 1U,
    kAudioSubmit = 2U,
    kStorageRead = 3U,
    kStorageWrite = 4U,
};

inline constexpr std::size_t kFakeStorageBlockBytes = 256U;
inline constexpr std::size_t kFakeStorageBlockCount = 512U;
inline constexpr std::size_t kMaximumFakeSubmissionBytes = 1U << 20U;

class FakeHostDevices final {
public:
    explicit FakeHostDevices(Journal& journal) noexcept : journal_(journal) {}

    FakeHostDevices(const FakeHostDevices&) = delete;
    FakeHostDevices& operator=(const FakeHostDevices&) = delete;

    // Supported calls journal their full payload identity and return true.
    [[nodiscard]] bool renderer_submit(
        std::string_view label, std::span<const std::byte> commands);
    [[nodiscard]] bool audio_submit(
        std::string_view label, std::span<const std::byte> samples);
    [[nodiscard]] bool storage_write(
        std::uint32_t block, std::span<const std::byte> bytes);
    [[nodiscard]] bool storage_read(
        std::uint32_t block, std::span<std::byte> destination);

    // The gate for anything else.  An id outside the supported set is
    // journaled as kHostCallRejected and returns false; the caller must
    // treat that as a failed run.
    [[nodiscard]] bool dispatch_host_call(
        std::uint32_t call_id, std::string_view label,
        std::span<const std::byte> payload);

    [[nodiscard]] std::size_t rejected_call_count() const noexcept {
        return rejected_calls_;
    }

private:
    Journal& journal_;
    std::map<std::uint32_t, std::vector<std::byte>> storage_;
    std::size_t rejected_calls_ = 0U;
};

} // namespace jfg::testkernel
