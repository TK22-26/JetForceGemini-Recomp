#include "jfg/platform/host.hpp"
#include "jfg/runtime/log.hpp"
#include "jfg/runtime/options.hpp"
#include "jfg/runtime/rom_validator.hpp"

#include <array>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string_view>
#include <system_error>

namespace {

int failures = 0;

void check(const bool condition, const std::string_view message) {
    if (!condition) {
        ++failures;
        std::cerr << "FAIL: " << message << '\n';
    }
}

void test_default_options() {
    const std::array<std::string_view, 0> arguments{};
    const auto result = jfg::parse_options(arguments);
    check(result.ok, "empty option list parses");
    check(result.options.behavior == jfg::BehaviorProfile::compatibility, "compatibility is default");
    check(result.options.backend == jfg::ExecutionBackend::production, "production is default");
    check(result.options.presentation == jfg::PresentationMode::rendered, "rendered is default");
}

void test_orthogonal_options() {
    const std::array arguments{
        std::string_view{"--behavior"},
        std::string_view{"enhanced"},
        std::string_view{"--backend"},
        std::string_view{"deterministic"},
        std::string_view{"--presentation"},
        std::string_view{"headless"},
        std::string_view{"--rom"},
        std::string_view{"private.z64"},
    };
    const auto result = jfg::parse_options(arguments);
    check(result.ok, "orthogonal options parse");
    check(result.options.behavior == jfg::BehaviorProfile::enhanced, "enhanced behavior parses");
    check(result.options.backend == jfg::ExecutionBackend::deterministic, "deterministic backend parses");
    check(result.options.presentation == jfg::PresentationMode::headless, "headless presentation parses");
    check(result.options.rom_path.has_value(), "ROM path parses");
}

void test_bad_options() {
    const std::array arguments{std::string_view{"--backend"}, std::string_view{"random"}};
    const auto result = jfg::parse_options(arguments);
    check(!result.ok, "invalid backend is rejected");
    check(result.error.find("unsupported execution backend") != std::string::npos, "invalid backend is explained");

    const std::array missing_value{
        std::string_view{"--rom"},
        std::string_view{"--behavior"},
        std::string_view{"enhanced"},
    };
    const auto missing_result = jfg::parse_options(missing_value);
    check(!missing_result.ok, "an option cannot consume the next flag as its value");
    check(missing_result.error == "missing value after --rom", "missing value names its option");

    const std::array duplicate{
        std::string_view{"--backend"},
        std::string_view{"production"},
        std::string_view{"--backend"},
        std::string_view{"deterministic"},
    };
    const auto duplicate_result = jfg::parse_options(duplicate);
    check(!duplicate_result.ok, "duplicate options are rejected");
    check(duplicate_result.error == "duplicate option: --backend", "duplicate option is explained");

    const std::array help{std::string_view{"--help"}};
    const auto help_result = jfg::parse_options(help);
    check(help_result.ok && help_result.show_help, "help is accepted without a ROM");
}

void test_platform_and_logging_boundaries() {
    const auto host = jfg::current_host();
    check(!host.operating_system.empty(), "host operating system is reported");
    check(!host.architecture.empty(), "host architecture is reported");

    std::ostringstream output;
    jfg::write_log(output, jfg::LogLevel::warning, "example");
    check(output.str() == "[warning] example\n", "logging format is stable");
}

void test_rom_metadata() {
    const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
    const auto path = std::filesystem::temp_directory_path() /
        ("jfg-rom-metadata-" + std::to_string(nonce) + ".z64");

    const auto directory_result = jfg::validate_rom_metadata(std::filesystem::temp_directory_path());
    check(directory_result.status == jfg::RomStatus::not_regular_file, "a directory is rejected");

    {
        std::ofstream stream(path, std::ios::binary);
        const std::array<unsigned char, 4> magic{0x80U, 0x37U, 0x12U, 0x40U};
        stream.write(reinterpret_cast<const char*>(magic.data()), static_cast<std::streamsize>(magic.size()));
    }

    const auto wrong_size = jfg::validate_rom_metadata(path);
    check(wrong_size.status == jfg::RomStatus::wrong_size, "a short file is rejected by size");

    std::filesystem::resize_file(path, jfg::kSupportedRomSize);

    const auto valid = jfg::validate_rom_metadata(path);
    check(valid.status == jfg::RomStatus::metadata_valid, "valid N64 metadata is accepted for hashing");

    {
        std::fstream stream(path, std::ios::binary | std::ios::in | std::ios::out);
        const std::array<unsigned char, 4> wrong_magic{0x37U, 0x80U, 0x40U, 0x12U};
        stream.write(
            reinterpret_cast<const char*>(wrong_magic.data()),
            static_cast<std::streamsize>(wrong_magic.size()));
    }

    const auto wrong_order = jfg::validate_rom_metadata(path);
    check(wrong_order.status == jfg::RomStatus::wrong_byte_order, "byte-swapped ROM is rejected");

    {
        std::fstream stream(path, std::ios::binary | std::ios::in | std::ios::out);
        const std::array<unsigned char, 4> little_endian_magic{0x40U, 0x12U, 0x37U, 0x80U};
        stream.write(
            reinterpret_cast<const char*>(little_endian_magic.data()),
            static_cast<std::streamsize>(little_endian_magic.size()));
    }

    const auto little_endian = jfg::validate_rom_metadata(path);
    check(little_endian.status == jfg::RomStatus::wrong_byte_order, "little-endian ROM is rejected");

    std::error_code ignored;
    std::filesystem::remove(path, ignored);

    const auto missing = jfg::validate_rom_metadata(path);
    check(missing.status == jfg::RomStatus::missing, "a missing file is rejected");
}

}  // namespace

int main() {
    test_default_options();
    test_orthogonal_options();
    test_bad_options();
    test_platform_and_logging_boundaries();
    test_rom_metadata();

    if (failures != 0) {
        std::cerr << failures << " test assertion(s) failed\n";
        return 1;
    }
    std::cout << "All ROM-free unit tests passed\n";
    return 0;
}
