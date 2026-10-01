#pragma once

// Side-effect journal for the deterministic test kernel (Phase 5, kernel
// v0).  Every host-visible effect a run produces is appended as one record;
// serialization is canonical (fixed little-endian framing, no timestamps,
// no host pointers), so identical runs produce identical journal bytes and
// a journal digest is a stable determinism witness.

#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

#include "jfg/testkernel/sha256.hpp"

namespace jfg::testkernel {

enum class JournalEffect : std::uint32_t {
    kRendererSubmit = 1U,
    kAudioSubmit = 2U,
    kStorageRead = 3U,
    kStorageWrite = 4U,
    kHostCallRejected = 5U,
    kCheckpoint = 6U,
};

struct JournalRecord final {
    JournalEffect effect = JournalEffect::kCheckpoint;
    std::string label;
    std::vector<std::byte> payload;

    [[nodiscard]] bool operator==(const JournalRecord&) const = default;
};

inline constexpr std::size_t kMaximumJournalRecords = 1U << 20U;
inline constexpr std::size_t kMaximumJournalPayloadBytes = 1U << 24U;
inline constexpr std::size_t kMaximumJournalLabelBytes = 256U;

class Journal final {
public:
    // Fails closed on oversized labels/payloads or a full journal.
    [[nodiscard]] bool append(
        JournalEffect effect,
        std::string_view label,
        std::span<const std::byte> payload);

    [[nodiscard]] const std::vector<JournalRecord>& records() const noexcept {
        return records_;
    }

    // Canonical bytes: record count, then per record the effect id, label
    // length/bytes, payload length/bytes.  All integers little-endian.
    [[nodiscard]] std::vector<std::byte> serialize() const;

    [[nodiscard]] StateDigest digest() const;

    // Round-trip for the replay/corpus formats.  Fails closed on any
    // truncation, bound violation, or unknown effect id.
    [[nodiscard]] static std::optional<Journal> deserialize(
        std::span<const std::byte> bytes);

    [[nodiscard]] bool operator==(const Journal&) const = default;

private:
    std::vector<JournalRecord> records_;
};

} // namespace jfg::testkernel
