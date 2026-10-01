#include "jfg/testkernel/world.hpp"

#include <algorithm>

namespace jfg::testkernel {

namespace {

void hash_u32(Sha256& hasher, const std::uint32_t value) noexcept {
    std::array<std::byte, 4> bytes{};
    for (std::size_t i = 0; i < bytes.size(); ++i) {
        bytes[i] = static_cast<std::byte>(value >> (8U * i));
    }
    hasher.update(bytes);
}

void hash_u64(Sha256& hasher, const std::uint64_t value) noexcept {
    std::array<std::byte, 8> bytes{};
    for (std::size_t i = 0; i < bytes.size(); ++i) {
        bytes[i] = static_cast<std::byte>(value >> (8U * i));
    }
    hasher.update(bytes);
}

} // namespace

bool StateHashSchema::valid_for(const std::size_t rdram_bytes) const noexcept {
    if (version != kStateHashSchemaVersion ||
        page_bytes != kWorldPageBytes) {
        return false;
    }
    std::uint64_t previous_end = 0U;
    for (const StateHashExclusion& exclusion : exclusions) {
        if (exclusion.begin >= exclusion.end ||
            exclusion.end > rdram_bytes ||
            exclusion.begin < previous_end) {
            return false;
        }
        previous_end = exclusion.end;
    }
    return true;
}

std::optional<World> World::create(const std::size_t rdram_bytes) {
    if (rdram_bytes < kMinimumWorldRdramBytes ||
        rdram_bytes > kMaximumWorldRdramBytes ||
        rdram_bytes % kWorldPageBytes != 0U) {
        return std::nullopt;
    }
    return World(rdram_bytes);
}

World World::clone() const {
    return *this;
}

std::optional<StateDigest> World::hash(const StateHashSchema& schema) const {
    if (!schema.valid_for(rdram_.size())) {
        return std::nullopt;
    }
    Sha256 hasher;
    hash_u32(hasher, schema.version);
    hash_u32(hasher, schema.page_bytes);
    hash_u32(hasher, schema.include_context ? 1U : 0U);
    hash_u32(hasher, static_cast<std::uint32_t>(schema.exclusions.size()));
    for (const StateHashExclusion& exclusion : schema.exclusions) {
        hash_u64(hasher, exclusion.begin);
        hash_u64(hasher, exclusion.end);
    }
    hash_u64(hasher, rdram_.size());

    std::uint64_t cursor = 0U;
    const auto include_range = [&](const std::uint64_t begin,
                                   const std::uint64_t end) {
        if (begin < end) {
            hasher.update_bytes(rdram_.data() + begin,
                                static_cast<std::size_t>(end - begin));
        }
    };
    for (const StateHashExclusion& exclusion : schema.exclusions) {
        include_range(cursor, exclusion.begin);
        cursor = exclusion.end;
    }
    include_range(cursor, rdram_.size());

    if (schema.include_context) {
        for (const std::uint64_t value : context_.gpr) {
            hash_u64(hasher, value);
        }
        hash_u64(hasher, context_.hi);
        hash_u64(hasher, context_.lo);
        hash_u64(hasher, context_.status);
    }
    return hasher.finish();
}

std::optional<std::vector<PageDelta>> World::diff(
    const World& baseline) const {
    if (rdram_.size() != baseline.rdram_.size()) {
        return std::nullopt;
    }
    std::vector<PageDelta> deltas;
    const std::size_t size = rdram_.size();
    std::size_t offset = 0U;
    while (offset < size) {
        if (rdram_[offset] == baseline.rdram_[offset]) {
            ++offset;
            continue;
        }
        // Extend a maximal differing run, splitting at page boundaries so
        // each delta names exactly one page.
        const std::size_t page_end = std::min(
            size, (offset / kWorldPageBytes + 1U) * kWorldPageBytes);
        std::size_t run_end = offset + 1U;
        while (run_end < page_end &&
               rdram_[run_end] != baseline.rdram_[run_end]) {
            ++run_end;
        }
        deltas.push_back(PageDelta{
            .page_index = offset / kWorldPageBytes,
            .first_byte = offset,
            .last_byte = run_end - 1U,
        });
        offset = run_end;
    }
    return deltas;
}

} // namespace jfg::testkernel
