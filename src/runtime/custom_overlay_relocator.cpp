#include "jfg/runtime/custom_overlay_relocator.hpp"

#include <array>
#include <limits>
#include <new>
#include <type_traits>
#include <unordered_set>
#include <vector>

namespace jfg {
namespace {

struct PlannedWrite {
    std::uint32_t site = 0U;
    std::uint32_t value = 0U;
};

struct ResolvedRecord {
    std::uint32_t value = 0U;
    std::uint32_t original_word = 0U;
};

[[nodiscard]] bool valid_source(
    const CustomOverlayRelocationSource source) noexcept {
    switch (source) {
    case CustomOverlayRelocationSource::external:
    case CustomOverlayRelocationSource::local_offset:
    case CustomOverlayRelocationSource::local_jump:
    case CustomOverlayRelocationSource::external_data:
        return true;
    }
    return false;
}

[[nodiscard]] bool valid_patch(
    const CustomOverlayRelocationPatch patch) noexcept {
    switch (patch) {
    case CustomOverlayRelocationPatch::full_word:
    case CustomOverlayRelocationPatch::jump_target:
    case CustomOverlayRelocationPatch::hi16:
    case CustomOverlayRelocationPatch::lo16:
        return true;
    }
    return false;
}

[[nodiscard]] std::uint32_t read_be32(
    const std::span<const std::byte> bytes,
    const std::size_t offset) noexcept {
    return (std::to_integer<std::uint32_t>(bytes[offset]) << 24U) |
        (std::to_integer<std::uint32_t>(bytes[offset + 1U]) << 16U) |
        (std::to_integer<std::uint32_t>(bytes[offset + 2U]) << 8U) |
        std::to_integer<std::uint32_t>(bytes[offset + 3U]);
}

void write_be32(
    const std::span<std::byte> bytes,
    const std::size_t offset,
    const std::uint32_t value) noexcept {
    bytes[offset] = static_cast<std::byte>(value >> 24U);
    bytes[offset + 1U] = static_cast<std::byte>(value >> 16U);
    bytes[offset + 2U] = static_cast<std::byte>(value >> 8U);
    bytes[offset + 3U] = static_cast<std::byte>(value);
}

[[nodiscard]] bool add_signed(
    const std::uint32_t value,
    const std::int32_t addend,
    std::uint32_t& output) noexcept {
    if (addend >= 0) {
        const std::uint32_t positive = static_cast<std::uint32_t>(addend);
        if (value > std::numeric_limits<std::uint32_t>::max() - positive) {
            return false;
        }
        output = value + positive;
        return true;
    }

    const std::uint32_t magnitude = static_cast<std::uint32_t>(
        -static_cast<std::int64_t>(addend));
    if (value < magnitude) {
        return false;
    }
    output = value - magnitude;
    return true;
}

void commitment_byte(
    std::array<std::uint64_t, 4U>& state,
    const std::uint8_t byte) noexcept {
    constexpr std::array<std::uint64_t, 4U> kPrimes{
        1099511628211ULL,
        14029467366897019727ULL,
        1609587929392839161ULL,
        9650029242287828579ULL,
    };
    for (std::size_t index = 0U; index < state.size(); ++index) {
        state[index] ^= static_cast<std::uint64_t>(byte) +
            static_cast<std::uint64_t>(index * 0x31U);
        state[index] *= kPrimes[index];
        state[index] ^= state[index] >> 29U;
    }
}

template <typename Value>
void commitment_value(
    std::array<std::uint64_t, 4U>& state,
    const Value value) noexcept {
    static_assert(std::is_integral_v<Value>);
    using Unsigned = std::make_unsigned_t<Value>;
    const Unsigned bits = static_cast<Unsigned>(value);
    for (std::size_t index = 0U; index < sizeof(Value); ++index) {
        commitment_byte(
            state,
            static_cast<std::uint8_t>(bits >> (index * 8U)));
    }
}

[[nodiscard]] std::array<std::uint8_t, 32U> finish_commitment(
    const std::array<std::uint64_t, 4U>& state) noexcept {
    std::array<std::uint8_t, 32U> output{};
    for (std::size_t word = 0U; word < state.size(); ++word) {
        for (std::size_t byte = 0U; byte < 8U; ++byte) {
            output[word * 8U + byte] = static_cast<std::uint8_t>(
                state[word] >> (byte * 8U));
        }
    }
    return output;
}

[[nodiscard]] CustomOverlayRelocationResult failure(
    const CustomOverlayRelocationError error) noexcept {
    return {.error = error};
}

} // namespace

CustomOverlayRelocationResult apply_custom_overlay_relocations(
    const std::span<std::byte> image,
    const CustomOverlayRelocationSection& source,
    const std::span<const CustomOverlayRelocationRecord> records,
    CustomOverlayRelocationResolver& resolver) noexcept {
    try {
    if (source.text_size == 0U || source.text_size > source.initialized_size ||
        source.initialized_size > source.mapped_size ||
        source.mapped_size > image.size() ||
        source.mapped_size >
            std::numeric_limits<std::uint32_t>::max() - source.base) {
        return failure(CustomOverlayRelocationError::invalid_section_extents);
    }

    std::vector<ResolvedRecord> resolved;
    resolved.reserve(records.size());
    std::unordered_set<std::uint32_t> sites;
    sites.reserve(records.size());
    for (std::size_t index = 0U; index < records.size(); ++index) {
        const CustomOverlayRelocationRecord& record = records[index];
        if (!sites.insert(record.site_offset).second) {
            return failure(CustomOverlayRelocationError::duplicate_site);
        }
        if (!valid_source(record.source)) {
            return failure(CustomOverlayRelocationError::invalid_source_type);
        }
        if (!valid_patch(record.patch)) {
            return failure(CustomOverlayRelocationError::invalid_patch_type);
        }
        if ((record.site_offset & 3U) != 0U) {
            return failure(CustomOverlayRelocationError::unaligned_site);
        }
        if (record.site_offset > source.initialized_size ||
            source.initialized_size - record.site_offset < 4U) {
            return failure(CustomOverlayRelocationError::site_out_of_bounds);
        }
        if ((record.source == CustomOverlayRelocationSource::external_data &&
             record.site_offset < source.text_size) ||
            (record.source != CustomOverlayRelocationSource::external_data &&
             record.patch != CustomOverlayRelocationPatch::full_word &&
             record.site_offset >= source.text_size)) {
            return failure(CustomOverlayRelocationError::site_out_of_bounds);
        }

        const std::uint32_t original_word = read_be32(image, record.site_offset);
        std::uint32_t target = 0U;
        bool target_resolved = false;
        switch (record.source) {
        case CustomOverlayRelocationSource::external:
        case CustomOverlayRelocationSource::external_data:
            target_resolved = resolver.resolve_external(
                record.source, source.section, record.target, target);
            break;
        case CustomOverlayRelocationSource::local_offset: {
            if (record.target >= source.mapped_size) {
                return failure(CustomOverlayRelocationError::target_out_of_bounds);
            }
            const std::uint32_t expected = source.base + record.target;
            target_resolved = resolver.resolve_local(
                record.source, source.section, record.target, target);
            if (target_resolved && target != expected) {
                return failure(CustomOverlayRelocationError::dependency_unresolved);
            }
            break;
        }
        case CustomOverlayRelocationSource::local_jump: {
            // This source class carries no symbol offset.  Its local target is
            // encoded by the instruction already present at the patch site.
            // Requiring a zero adapter field keeps ignored input from being
            // silently accepted without affecting the result.
            if (record.target != 0U) {
                return failure(CustomOverlayRelocationError::target_out_of_bounds);
            }
            const std::uint32_t target_offset =
                (original_word & 0x03FFFFFFU) << 2U;
            if (source.base >
                std::numeric_limits<std::uint32_t>::max() - target_offset) {
                return failure(CustomOverlayRelocationError::address_overflow);
            }
            const std::uint32_t expected = source.base + target_offset;
            target_resolved = resolver.resolve_local(
                record.source, source.section, target_offset, target);
            if (target_resolved && target != expected) {
                return failure(CustomOverlayRelocationError::dependency_unresolved);
            }
            break;
        }
        }
        if (!target_resolved) {
            return failure(CustomOverlayRelocationError::dependency_unresolved);
        }

        std::uint32_t value = 0U;
        if (!add_signed(target, record.addend, value)) {
            return failure(CustomOverlayRelocationError::address_overflow);
        }
        resolved.push_back({
            .value = value,
            .original_word = original_word,
        });
    }

    for (std::size_t index = 0U; index < records.size(); ++index) {
        if (records[index].patch != CustomOverlayRelocationPatch::hi16) {
            continue;
        }
        if (index + 1U >= records.size()) {
            return failure(CustomOverlayRelocationError::malformed_pair);
        }
        const CustomOverlayRelocationRecord& high = records[index];
        const CustomOverlayRelocationRecord& low = records[index + 1U];
        if (low.patch != CustomOverlayRelocationPatch::lo16 ||
            low.source != high.source || low.target != high.target ||
            low.addend != high.addend ||
            resolved[index].value != resolved[index + 1U].value) {
            return failure(CustomOverlayRelocationError::malformed_pair);
        }
    }

    std::vector<PlannedWrite> writes;
    writes.reserve(records.size());
    CustomOverlayRelocationAudit audit;
    std::array<std::uint64_t, 4U> commitment{
        1469598103934665603ULL,
        0x9E3779B185EBCA87ULL,
        0xC2B2AE3D27D4EB4FULL,
        0x165667B19E3779F9ULL,
    };
    for (std::size_t index = 0U; index < records.size(); ++index) {
        const CustomOverlayRelocationRecord& record = records[index];
        const std::uint32_t original = resolved[index].original_word;
        const std::uint32_t value = resolved[index].value;
        std::uint32_t replacement = 0U;
        switch (record.patch) {
        case CustomOverlayRelocationPatch::full_word:
            replacement = value;
            ++audit.full_word_count;
            break;
        case CustomOverlayRelocationPatch::jump_target: {
            if ((value & 3U) != 0U ||
                source.base > std::numeric_limits<std::uint32_t>::max() -
                    record.site_offset - 4U) {
                return failure(CustomOverlayRelocationError::invalid_jump_target);
            }
            const std::uint32_t next_pc = source.base + record.site_offset + 4U;
            if ((value & 0xF0000000U) != (next_pc & 0xF0000000U)) {
                return failure(CustomOverlayRelocationError::invalid_jump_target);
            }
            replacement = (original & 0xFC000000U) |
                ((value >> 2U) & 0x03FFFFFFU);
            ++audit.jump_target_count;
            break;
        }
        case CustomOverlayRelocationPatch::hi16:
            replacement = (original & 0xFFFF0000U) |
                static_cast<std::uint32_t>(
                    (static_cast<std::uint64_t>(value) + 0x8000ULL) >> 16U);
            ++audit.hi16_count;
            break;
        case CustomOverlayRelocationPatch::lo16:
            replacement = (original & 0xFFFF0000U) | (value & 0xFFFFU);
            ++audit.lo16_count;
            break;
        }
        writes.push_back({.site = record.site_offset, .value = replacement});
        commitment_value(commitment, static_cast<std::uint8_t>(record.source));
        commitment_value(commitment, static_cast<std::uint8_t>(record.patch));
        commitment_value(commitment, record.site_offset);
        commitment_value(commitment, record.target);
        commitment_value(commitment, record.addend);
        commitment_value(commitment, original);
        commitment_value(commitment, replacement);
    }

    for (const PlannedWrite& write : writes) {
        write_be32(image, write.site, write.value);
    }
    audit.applied_total = writes.size();
    audit.commitment = finish_commitment(commitment);
    return {.error = CustomOverlayRelocationError::none, .audit = audit};
    }
    catch (const std::bad_alloc&) {
        return failure(CustomOverlayRelocationError::internal_failure);
    }
    catch (...) {
        return failure(CustomOverlayRelocationError::callback_exception);
    }
}

} // namespace jfg
