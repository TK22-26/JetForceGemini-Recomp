#pragma once

#include <filesystem>
#include <optional>
#include <span>
#include <string>
#include <string_view>

namespace jfg {

enum class BehaviorProfile {
    compatibility,
    enhanced,
};

enum class ExecutionBackend {
    production,
    deterministic,
};

enum class PresentationMode {
    rendered,
    headless,
};

struct LaunchOptions {
    BehaviorProfile behavior = BehaviorProfile::compatibility;
    ExecutionBackend backend = ExecutionBackend::production;
    PresentationMode presentation = PresentationMode::rendered;
    std::optional<std::filesystem::path> rom_path;
};

struct ParseResult {
    LaunchOptions options;
    bool ok = false;
    bool show_help = false;
    std::string error;
};

[[nodiscard]] ParseResult parse_options(std::span<const std::string_view> arguments);
[[nodiscard]] std::string_view to_string(BehaviorProfile value);
[[nodiscard]] std::string_view to_string(ExecutionBackend value);
[[nodiscard]] std::string_view to_string(PresentationMode value);
[[nodiscard]] std::string usage();

}  // namespace jfg
