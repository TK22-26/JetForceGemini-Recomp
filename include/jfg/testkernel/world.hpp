#pragma once

// Cloneable RDRAM/context worlds for the deterministic test kernel
// (Phase 5, kernel v0).  A World owns a guest RDRAM image and a guest
// register context.  Cloning is byte-exact; diffing two worlds reports the
// exact pages and byte ranges that differ; hashing follows the pinned state
// hash schema v1.

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <vector>

#include "jfg/testkernel/sha256.hpp"

namespace jfg::testkernel {

inline constexpr std::size_t kWorldPageBytes = 4096U;
inline constexpr std::size_t kMinimumWorldRdramBytes = kWorldPageBytes;
// 8 MiB matches the Expansion Pak RDRAM ceiling.
inline constexpr std::size_t kMaximumWorldRdramBytes = 8U * 1024U * 1024U;
inline constexpr std::uint32_t kStateHashSchemaVersion = 1U;

// Layout-compatible with the generated-code recomp_context register file:
// thirty-two 64-bit general-purpose registers.  hi/lo/status live beside the
// register file rather than inside it so the kernel never guesses at fields
// the generated ABI does not expose.
struct GuestContext final {
    std::array<std::uint64_t, 32> gpr{};
    std::uint64_t hi = 0U;
    std::uint64_t lo = 0U;
    std::uint64_t status = 0U;

    [[nodiscard]] bool operator==(const GuestContext&) const = default;
};

// A half-open guest byte range excluded from the state hash.  v0 ships with
// zero exclusions; adding one is a human-approved schema revision.
struct StateHashExclusion final {
    std::uint64_t begin = 0U;
    std::uint64_t end = 0U;

    [[nodiscard]] bool operator==(const StateHashExclusion&) const = default;
};

struct StateHashSchema final {
    std::uint32_t version = kStateHashSchemaVersion;
    std::uint32_t page_bytes = static_cast<std::uint32_t>(kWorldPageBytes);
    bool include_context = true;
    std::vector<StateHashExclusion> exclusions;

    [[nodiscard]] bool valid_for(std::size_t rdram_bytes) const noexcept;

    [[nodiscard]] bool operator==(const StateHashSchema&) const = default;
};

// One byte-exact difference inside a single page.
struct PageDelta final {
    std::uint64_t page_index = 0U;
    std::uint64_t first_byte = 0U;   // absolute RDRAM offset
    std::uint64_t last_byte = 0U;    // absolute RDRAM offset, inclusive
};

class World final {
public:
    // Fails closed: returns std::nullopt for a size that is zero, not a
    // page multiple, or beyond the RDRAM ceiling.
    [[nodiscard]] static std::optional<World> create(std::size_t rdram_bytes);

    [[nodiscard]] World clone() const;

    [[nodiscard]] std::span<std::uint8_t> rdram() noexcept {
        return std::span(rdram_.data(), rdram_.size());
    }
    [[nodiscard]] std::span<const std::uint8_t> rdram() const noexcept {
        return std::span(rdram_.data(), rdram_.size());
    }
    [[nodiscard]] GuestContext& context() noexcept { return context_; }
    [[nodiscard]] const GuestContext& context() const noexcept {
        return context_;
    }
    [[nodiscard]] std::size_t page_count() const noexcept {
        return rdram_.size() / kWorldPageBytes;
    }

    // State hash schema v1: schema header, then every included RDRAM byte in
    // ascending address order, then the context when included.  Returns
    // std::nullopt when the schema does not fit this world.
    [[nodiscard]] std::optional<StateDigest> hash(
        const StateHashSchema& schema) const;

    // Exact dirty tracking by comparison against a baseline clone.  Reports
    // one PageDelta per maximal run of differing bytes, in ascending order.
    // Returns std::nullopt when the two worlds have different sizes.
    [[nodiscard]] std::optional<std::vector<PageDelta>> diff(
        const World& baseline) const;

    [[nodiscard]] bool operator==(const World&) const = default;

private:
    explicit World(std::size_t rdram_bytes) : rdram_(rdram_bytes, 0U) {}

    std::vector<std::uint8_t> rdram_;
    GuestContext context_{};
};

} // namespace jfg::testkernel
