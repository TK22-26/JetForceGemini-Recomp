#pragma once

// Function capture/replay format v1, first-divergence report format v1, and
// the exact-repeat nondeterminism detector (Phase 5, kernel v0).
//
// A capture records the complete pre-state (sparse non-zero pages plus
// context), the identity of the function under test, and the expected
// post-state (pages that changed, post context, journal bytes, and state
// hashes).  Replay reconstructs the pre-state world, invokes the function
// through the caller-supplied registry, and compares bit-for-bit.

#include <cstdint>
#include <functional>
#include <optional>
#include <span>
#include <string>
#include <vector>

#include "jfg/testkernel/journal.hpp"
#include "jfg/testkernel/world.hpp"

namespace jfg::testkernel {

inline constexpr std::array<std::byte, 8> kCaptureMagic{
    std::byte{'J'}, std::byte{'F'}, std::byte{'G'}, std::byte{'C'},
    std::byte{'A'}, std::byte{'P'}, std::byte{'0'}, std::byte{'1'}};
inline constexpr std::uint32_t kCaptureFormatVersion = 1U;
inline constexpr std::size_t kMaximumCaptureBytes = 64U * 1024U * 1024U;

struct SparsePage final {
    std::uint64_t page_index = 0U;
    std::array<std::uint8_t, kWorldPageBytes> bytes{};

    [[nodiscard]] bool operator==(const SparsePage&) const = default;
};

struct FunctionCapture final {
    std::uint64_t function_id = 0U;
    std::string function_label;
    std::uint64_t rdram_bytes = 0U;
    StateHashSchema schema{};
    std::vector<SparsePage> pre_pages;   // pages differing from zero
    GuestContext pre_context{};
    std::vector<SparsePage> post_pages;  // pages differing from pre-state
    GuestContext post_context{};
    std::vector<std::byte> journal_bytes;
    StateDigest pre_hash{};
    StateDigest post_hash{};

    [[nodiscard]] bool operator==(const FunctionCapture&) const = default;
};

// The function under test mutates the world's RDRAM/context and may append
// journal records.  Returns false to signal a failed invocation.
using CapturedFunction = std::function<bool(World&, Journal&)>;

// Resolves a function id to an executable body; empty result fails closed.
using FunctionRegistry =
    std::function<std::optional<CapturedFunction>(std::uint64_t)>;

// Where the first divergence between an expected and an actual run lies.
enum class DivergenceDomain : std::uint32_t {
    kRdram = 1U,
    kContext = 2U,
    kJournal = 3U,
    kInvocation = 4U,
};

// First-divergence report format v1.
struct DivergenceReport final {
    std::uint32_t format_version = 1U;
    DivergenceDomain domain = DivergenceDomain::kRdram;
    std::uint64_t function_id = 0U;
    // kRdram: absolute RDRAM offset.  kContext: register slot index, where
    // 0-31 are GPRs and 32/33/34 are hi/lo/status.  kJournal: byte offset
    // into the canonical journal serialization.
    std::uint64_t offset = 0U;
    std::uint64_t expected_value = 0U;
    std::uint64_t actual_value = 0U;
    std::string expected_hash_hex;
    std::string actual_hash_hex;

    [[nodiscard]] std::string to_text() const;
};

struct ReplayResult final {
    bool bit_identical = false;
    std::optional<DivergenceReport> divergence;
};

// Records a capture by cloning the pre-state, invoking the function, and
// diffing.  Fails closed when the function fails or the schema is invalid.
[[nodiscard]] std::optional<FunctionCapture> capture_function(
    std::uint64_t function_id,
    std::string function_label,
    const World& pre_state,
    const StateHashSchema& schema,
    const CapturedFunction& function);

// Rebuilds the pre-state world from a capture.
[[nodiscard]] std::optional<World> reconstruct_pre_state(
    const FunctionCapture& capture);

// Replays a capture and reports the first divergence, if any.  The scan
// order is fixed: RDRAM ascending, then context slots, then journal bytes,
// so the "first" divergence is well defined.
[[nodiscard]] std::optional<ReplayResult> replay_capture(
    const FunctionCapture& capture, const FunctionRegistry& registry);

// Binary round-trip, bounded and fail-closed.
[[nodiscard]] std::vector<std::byte> serialize_capture(
    const FunctionCapture& capture);
[[nodiscard]] std::optional<FunctionCapture> deserialize_capture(
    std::span<const std::byte> bytes);

// Exact-repeat nondeterminism detector: runs the scenario twice and returns
// the zero-based index of the first checkpoint hash that differs, or
// std::nullopt when the runs are exactly repeatable.  A scenario that
// produces different checkpoint counts diverges at the shorter length.
using CheckpointedScenario = std::function<std::vector<StateDigest>()>;
[[nodiscard]] std::optional<std::size_t> detect_nondeterminism(
    const CheckpointedScenario& scenario);

} // namespace jfg::testkernel
