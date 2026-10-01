#include "jfg/runtime/log.hpp"

namespace jfg {

std::string_view to_string(const LogLevel level) {
    switch (level) {
    case LogLevel::debug:
        return "debug";
    case LogLevel::info:
        return "info";
    case LogLevel::warning:
        return "warning";
    case LogLevel::error:
        return "error";
    }
    return "unknown";
}

void write_log(std::ostream& output, const LogLevel level, const std::string_view message) {
    output << '[' << to_string(level) << "] " << message << '\n';
}

}  // namespace jfg
