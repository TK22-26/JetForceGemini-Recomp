#include "jfg/platform/host.hpp"
#include "jfg/runtime/log.hpp"
#include "jfg/runtime/options.hpp"
#include "jfg/runtime/rom_validator.hpp"

#include <iostream>
#include <string_view>
#include <vector>

int main(const int argc, const char* const* argv) {
    std::vector<std::string_view> arguments;
    arguments.reserve(static_cast<std::size_t>(argc > 0 ? argc - 1 : 0));
    for (int index = 1; index < argc; ++index) {
        arguments.emplace_back(argv[index]);
    }

    const auto parsed = jfg::parse_options(arguments);
    if (!parsed.ok) {
        std::cerr << "Configuration error: " << parsed.error << "\n\n" << jfg::usage();
        return 2;
    }
    if (parsed.show_help) {
        std::cout << jfg::usage();
        return 0;
    }
    if (!parsed.options.rom_path) {
        std::cerr
            << "No ROM was provided. Supply your own verified US retail ROM with "
               "--rom <path>. The ROM must remain outside Git.\n";
        return 2;
    }

    const auto validation = jfg::validate_rom_metadata(*parsed.options.rom_path);
    if (!validation.accepted_for_hashing()) {
        std::cerr << "ROM validation failed: " << validation.message << '\n';
        return 3;
    }

    const auto host = jfg::current_host();
    jfg::write_log(std::cout, jfg::LogLevel::info, "ROM metadata accepted");
    std::cout
        << "JFG host shell configured: host=" << host.operating_system << '/'
        << host.architecture << ", behavior="
        << jfg::to_string(parsed.options.behavior)
        << ", backend=" << jfg::to_string(parsed.options.backend)
        << ", presentation=" << jfg::to_string(parsed.options.presentation)
        << "\n"
        << validation.message << "\n"
        << "Game execution is not implemented in the Phase 2 host shell.\n";
    return 0;
}
