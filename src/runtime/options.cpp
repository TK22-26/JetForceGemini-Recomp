#include "jfg/runtime/options.hpp"

#include <array>

namespace jfg {
namespace {

std::optional<std::string_view> read_value(
    std::span<const std::string_view> arguments,
    std::size_t& index,
    std::string& error) {
    if (index + 1U >= arguments.size()) {
        error = "missing value after " + std::string(arguments[index]);
        return std::nullopt;
    }
    if (arguments[index + 1U].starts_with("-")) {
        error = "missing value after " + std::string(arguments[index]);
        return std::nullopt;
    }
    ++index;
    return arguments[index];
}

bool reject_duplicate(bool& seen, const std::string_view argument, std::string& error) {
    if (seen) {
        error = "duplicate option: " + std::string(argument);
        return true;
    }
    seen = true;
    return false;
}

}  // namespace

ParseResult parse_options(std::span<const std::string_view> arguments) {
    ParseResult result;
    result.ok = true;
    bool saw_rom = false;
    bool saw_behavior = false;
    bool saw_backend = false;
    bool saw_presentation = false;

    for (std::size_t index = 0; index < arguments.size(); ++index) {
        const auto argument = arguments[index];

        if (argument == "--help" || argument == "-h") {
            result.show_help = true;
            continue;
        }

        if (argument == "--rom") {
            if (reject_duplicate(saw_rom, argument, result.error)) {
                result.ok = false;
                return result;
            }
            const auto value = read_value(arguments, index, result.error);
            if (!value) {
                result.ok = false;
                return result;
            }
            result.options.rom_path = std::filesystem::path(*value);
            continue;
        }

        if (argument == "--behavior") {
            if (reject_duplicate(saw_behavior, argument, result.error)) {
                result.ok = false;
                return result;
            }
            const auto value = read_value(arguments, index, result.error);
            if (!value) {
                result.ok = false;
                return result;
            }
            if (*value == "compatibility") {
                result.options.behavior = BehaviorProfile::compatibility;
            } else if (*value == "enhanced") {
                result.options.behavior = BehaviorProfile::enhanced;
            } else {
                result.ok = false;
                result.error = "unsupported behavior profile: " + std::string(*value);
                return result;
            }
            continue;
        }

        if (argument == "--backend") {
            if (reject_duplicate(saw_backend, argument, result.error)) {
                result.ok = false;
                return result;
            }
            const auto value = read_value(arguments, index, result.error);
            if (!value) {
                result.ok = false;
                return result;
            }
            if (*value == "production") {
                result.options.backend = ExecutionBackend::production;
            } else if (*value == "deterministic") {
                result.options.backend = ExecutionBackend::deterministic;
            } else {
                result.ok = false;
                result.error = "unsupported execution backend: " + std::string(*value);
                return result;
            }
            continue;
        }

        if (argument == "--presentation") {
            if (reject_duplicate(saw_presentation, argument, result.error)) {
                result.ok = false;
                return result;
            }
            const auto value = read_value(arguments, index, result.error);
            if (!value) {
                result.ok = false;
                return result;
            }
            if (*value == "rendered") {
                result.options.presentation = PresentationMode::rendered;
            } else if (*value == "headless") {
                result.options.presentation = PresentationMode::headless;
            } else {
                result.ok = false;
                result.error = "unsupported presentation mode: " + std::string(*value);
                return result;
            }
            continue;
        }

        result.ok = false;
        result.error = "unknown option: " + std::string(argument);
        return result;
    }

    return result;
}

std::string_view to_string(const BehaviorProfile value) {
    switch (value) {
    case BehaviorProfile::compatibility:
        return "compatibility";
    case BehaviorProfile::enhanced:
        return "enhanced";
    }
    return "unknown";
}

std::string_view to_string(const ExecutionBackend value) {
    switch (value) {
    case ExecutionBackend::production:
        return "production";
    case ExecutionBackend::deterministic:
        return "deterministic";
    }
    return "unknown";
}

std::string_view to_string(const PresentationMode value) {
    switch (value) {
    case PresentationMode::rendered:
        return "rendered";
    case PresentationMode::headless:
        return "headless";
    }
    return "unknown";
}

std::string usage() {
    return
        "Usage: jfg [options]\n"
        "  --rom <path>                    Path to a lawful user-supplied US ROM\n"
        "  --behavior compatibility|enhanced\n"
        "  --backend production|deterministic\n"
        "  --presentation rendered|headless\n"
        "  --help                          Show this message\n";
}

}  // namespace jfg
