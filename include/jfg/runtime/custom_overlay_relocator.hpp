#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <span>

namespace jfg {

// The values deliberately mirror the compact relocation record vocabulary used
// by the project-owned adapter.  They are not a ROM format.
enum class CustomOverlayRelocationSource : std::uint8_t {
    external = 0U,
    local_offset = 1U,
    local_jump = 2U,
    // The target still uses the external reference-table resolver.  This
    // source class records that the patch site came from the initialized data
    // section rather than the text section.
    external_data = 3U,
};

enum class CustomOverlayRelocationPatch : std::uint8_t {
    full_word = 2U,
    jump_target = 4U,
    hi16 = 5U,
    lo16 = 6U,
};

struct CustomOverlayRelocationRecord {
    std::uint32_t site_offset = 0U;
    CustomOverlayRelocationSource source =
        CustomOverlayRelocationSource::external;
    CustomOverlayRelocationPatch patch =
        CustomOverlayRelocationPatch::full_word;
    // This is a local offset for local_offset, an opaque reference-table
    // identity for either external class, and must be zero for local_jump
    // because that target is derived from the original instruction word. The
    // relocator never exposes its resolved address through its result.
    std::uint32_t target = 0U;
    std::int32_t addend = 0;
};

struct CustomOverlayRelocationSection {
    std::uint32_t section = 0U;
    std::uint32_t base = 0U;
    std::uint32_t text_size = 0U;
    std::uint32_t initialized_size = 0U;
    std::uint32_t mapped_size = 0U;
};

class CustomOverlayRelocationResolver {
public:
    virtual ~CustomOverlayRelocationResolver() = default;

    [[nodiscard]] virtual bool resolve_external(
        CustomOverlayRelocationSource source_kind,
        std::uint32_t source_section,
        std::uint32_t opaque_target,
        std::uint32_t& resolved_address) = 0;
    [[nodiscard]] virtual bool resolve_local(
        CustomOverlayRelocationSource source_kind,
        std::uint32_t source_section,
        std::uint32_t target_offset,
        std::uint32_t& resolved_address) = 0;
};

enum class CustomOverlayRelocationError : std::uint8_t {
    none = 0U,
    invalid_section_extents,
    duplicate_site,
    invalid_source_type,
    invalid_patch_type,
    unaligned_site,
    site_out_of_bounds,
    target_out_of_bounds,
    dependency_unresolved,
    address_overflow,
    invalid_jump_target,
    malformed_pair,
    // The resolver callback raised an exception. The input image is left
    // unchanged because resolution completes before any write is committed.
    callback_exception,
    // Transactional planning could not allocate its bounded temporary state.
    internal_failure,
};

struct CustomOverlayRelocationAudit {
    std::size_t applied_total = 0U;
    std::size_t full_word_count = 0U;
    std::size_t jump_target_count = 0U;
    std::size_t hi16_count = 0U;
    std::size_t lo16_count = 0U;
    // Deterministic opaque commitment bytes.  This is intentionally a
    // commitment rather than a list of guest addresses or relocation sites.
    std::array<std::uint8_t, 32U> commitment{};
};

struct CustomOverlayRelocationResult {
    CustomOverlayRelocationError error = CustomOverlayRelocationError::none;
    CustomOverlayRelocationAudit audit{};

    [[nodiscard]] bool applied() const noexcept {
        return error == CustomOverlayRelocationError::none;
    }
};

// Validates and resolves the complete record set before modifying image.  A
// failed call leaves image byte-for-byte unchanged.
[[nodiscard]] CustomOverlayRelocationResult apply_custom_overlay_relocations(
    std::span<std::byte> image,
    const CustomOverlayRelocationSection& source,
    std::span<const CustomOverlayRelocationRecord> records,
    CustomOverlayRelocationResolver& resolver) noexcept;

} // namespace jfg
