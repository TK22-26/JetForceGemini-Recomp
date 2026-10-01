#pragma once

// Corpus container format v1 and page-level minimization (Phase 5, kernel
// v0).  A corpus is an ordered set of named capture blobs.  Entries are
// stored with deterministic run-length compression; round-trips are
// byte-lossless.  Compression beyond this and sub-page minimization are
// kernel v1 work per the acceptance contract.

#include <cstdint>
#include <functional>
#include <optional>
#include <span>
#include <string>
#include <vector>

#include "jfg/testkernel/capture.hpp"

namespace jfg::testkernel {

inline constexpr std::array<std::byte, 8> kCorpusMagic{
    std::byte{'J'}, std::byte{'F'}, std::byte{'G'}, std::byte{'C'},
    std::byte{'O'}, std::byte{'R'}, std::byte{'P'}, std::byte{'1'}};
inline constexpr std::uint32_t kCorpusFormatVersion = 1U;
inline constexpr std::size_t kMaximumCorpusEntries = 4096U;
inline constexpr std::size_t kMaximumCorpusEntryNameBytes = 256U;
inline constexpr std::size_t kMaximumCorpusBytes = 256U * 1024U * 1024U;

struct CorpusEntry final {
    std::string name;
    std::vector<std::byte> blob;

    [[nodiscard]] bool operator==(const CorpusEntry&) const = default;
};

class Corpus final {
public:
    [[nodiscard]] bool add(std::string name, std::vector<std::byte> blob);
    [[nodiscard]] const std::vector<CorpusEntry>& entries() const noexcept {
        return entries_;
    }

    [[nodiscard]] std::vector<std::byte> serialize() const;
    [[nodiscard]] static std::optional<Corpus> deserialize(
        std::span<const std::byte> bytes);

    [[nodiscard]] bool operator==(const Corpus&) const = default;

private:
    std::vector<CorpusEntry> entries_;
};

// Deterministic byte-level run-length coding used inside the corpus
// container.  Exposed for direct testing.
[[nodiscard]] std::vector<std::byte> rle_compress(
    std::span<const std::byte> input);
[[nodiscard]] std::optional<std::vector<std::byte>> rle_decompress(
    std::span<const std::byte> input, std::size_t maximum_output_bytes);

// Greedy page-level minimization: repeatedly drops pre-state pages from a
// capture while the caller's predicate still reproduces the failure.  The
// predicate receives a candidate capture and returns true when the failure
// still reproduces.  Returns the minimized capture; the input is returned
// unchanged when nothing can be dropped.
using FailurePredicate = std::function<bool(const FunctionCapture&)>;
[[nodiscard]] FunctionCapture minimize_capture(
    const FunctionCapture& capture, const FailurePredicate& reproduces);

} // namespace jfg::testkernel
