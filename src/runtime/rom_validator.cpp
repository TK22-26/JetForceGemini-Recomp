#include "jfg/runtime/rom_validator.hpp"

#include <array>
#include <fstream>
#include <system_error>

namespace jfg {

RomValidation validate_rom_metadata(const std::filesystem::path& path) {
    std::error_code error;
    const bool exists = std::filesystem::exists(path, error);
    if (error) {
        return {RomStatus::unreadable, "ROM path could not be inspected"};
    }
    if (!exists) {
        return {RomStatus::missing, "ROM file does not exist"};
    }
    const bool regular_file = std::filesystem::is_regular_file(path, error);
    if (error) {
        return {RomStatus::unreadable, "ROM path could not be inspected"};
    }
    if (!regular_file) {
        return {RomStatus::not_regular_file, "ROM path is not a regular file"};
    }

    const auto size = std::filesystem::file_size(path, error);
    if (error) {
        return {RomStatus::unreadable, "ROM size could not be read"};
    }
    if (size != kSupportedRomSize) {
        return {
            RomStatus::wrong_size,
            "unsupported ROM size; expected 33554432 bytes for the US retail image",
        };
    }

    std::ifstream stream(path, std::ios::binary);
    std::array<unsigned char, 4> magic{};
    if (!stream.read(reinterpret_cast<char*>(magic.data()), static_cast<std::streamsize>(magic.size()))) {
        return {RomStatus::unreadable, "ROM header could not be read"};
    }

    const auto value =
        (static_cast<std::uint32_t>(magic[0]) << 24U) |
        (static_cast<std::uint32_t>(magic[1]) << 16U) |
        (static_cast<std::uint32_t>(magic[2]) << 8U) |
        static_cast<std::uint32_t>(magic[3]);
    if (value != kBigEndianN64Magic) {
        return {
            RomStatus::wrong_byte_order,
            "unsupported ROM byte order; use the verified big-endian .z64 image",
        };
    }

    return {
        RomStatus::metadata_valid,
        "ROM metadata is valid; SHA-1 verification is still required before use",
    };
}

}  // namespace jfg
