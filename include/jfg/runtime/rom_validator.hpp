#pragma once

#include <cstdint>
#include <filesystem>
#include <string>
#include <string_view>

namespace jfg {

inline constexpr std::uintmax_t kSupportedRomSize = 33'554'432;
inline constexpr std::uint32_t kBigEndianN64Magic = 0x80371240U;
inline constexpr std::string_view kSupportedRomSha1 =
    "493ced9008dbe932d6e91179b68e8630cf23a023";

enum class RomStatus {
    metadata_valid,
    missing,
    not_regular_file,
    unreadable,
    wrong_size,
    wrong_byte_order,
};

struct RomValidation {
    RomStatus status = RomStatus::unreadable;
    std::string message;

    [[nodiscard]] bool accepted_for_hashing() const noexcept {
        return status == RomStatus::metadata_valid;
    }
};

// This Phase 2 boundary intentionally validates only safe file metadata and the
// N64 byte-order marker. The Phase 1 local build script performs the required
// SHA-1 check before any ROM-backed operation.
[[nodiscard]] RomValidation validate_rom_metadata(const std::filesystem::path& path);

}  // namespace jfg
