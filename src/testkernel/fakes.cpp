#include "jfg/testkernel/fakes.hpp"

#include <algorithm>

namespace jfg::testkernel {

namespace {

[[nodiscard]] std::vector<std::byte> block_payload(
    const std::uint32_t block, const std::span<const std::byte> bytes) {
    std::vector<std::byte> payload;
    payload.reserve(4U + bytes.size());
    for (std::size_t i = 0; i < 4U; ++i) {
        payload.push_back(static_cast<std::byte>(block >> (8U * i)));
    }
    payload.insert(payload.end(), bytes.begin(), bytes.end());
    return payload;
}

} // namespace

bool FakeHostDevices::renderer_submit(
    const std::string_view label, const std::span<const std::byte> commands) {
    if (commands.size() > kMaximumFakeSubmissionBytes) {
        return false;
    }
    return journal_.append(JournalEffect::kRendererSubmit, label, commands);
}

bool FakeHostDevices::audio_submit(
    const std::string_view label, const std::span<const std::byte> samples) {
    if (samples.size() > kMaximumFakeSubmissionBytes) {
        return false;
    }
    return journal_.append(JournalEffect::kAudioSubmit, label, samples);
}

bool FakeHostDevices::storage_write(
    const std::uint32_t block, const std::span<const std::byte> bytes) {
    if (block >= kFakeStorageBlockCount ||
        bytes.size() != kFakeStorageBlockBytes) {
        return false;
    }
    if (!journal_.append(
            JournalEffect::kStorageWrite, "storage-write",
            std::span<const std::byte>(block_payload(block, bytes)))) {
        return false;
    }
    storage_[block] = std::vector<std::byte>(bytes.begin(), bytes.end());
    return true;
}

bool FakeHostDevices::storage_read(
    const std::uint32_t block, const std::span<std::byte> destination) {
    if (block >= kFakeStorageBlockCount ||
        destination.size() != kFakeStorageBlockBytes) {
        return false;
    }
    const auto found = storage_.find(block);
    if (found != storage_.end()) {
        std::copy(found->second.begin(), found->second.end(),
                  destination.begin());
    } else {
        std::fill(destination.begin(), destination.end(), std::byte{0});
    }
    return journal_.append(
        JournalEffect::kStorageRead, "storage-read",
        std::span<const std::byte>(block_payload(block, destination)));
}

bool FakeHostDevices::dispatch_host_call(
    const std::uint32_t call_id, const std::string_view label,
    const std::span<const std::byte> payload) {
    switch (static_cast<HostCall>(call_id)) {
    case HostCall::kRendererSubmit:
        return renderer_submit(label, payload);
    case HostCall::kAudioSubmit:
        return audio_submit(label, payload);
    case HostCall::kStorageWrite:
        if (payload.size() != 4U + kFakeStorageBlockBytes) {
            break;
        }
        {
            std::uint32_t block = 0U;
            for (std::size_t i = 0; i < 4U; ++i) {
                block |= std::to_integer<std::uint32_t>(payload[i])
                    << (8U * i);
            }
            return storage_write(block, payload.subspan(4U));
        }
    case HostCall::kStorageRead:
        break; // reads need a destination; the raw gate rejects them
    default:
        break;
    }
    ++rejected_calls_;
    // The rejection itself is a journaled effect so a run that attempts an
    // unsupported call can never hash identically to one that did not.
    (void)journal_.append(JournalEffect::kHostCallRejected, label, payload);
    return false;
}

} // namespace jfg::testkernel
