#pragma once

#include <ostream>
#include <string_view>

namespace jfg {

enum class LogLevel {
    debug,
    info,
    warning,
    error,
};

[[nodiscard]] std::string_view to_string(LogLevel level);
void write_log(std::ostream& output, LogLevel level, std::string_view message);

}  // namespace jfg
