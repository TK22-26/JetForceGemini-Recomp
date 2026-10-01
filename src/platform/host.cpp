#include "jfg/platform/host.hpp"

namespace jfg {

HostDescription current_host() {
#if defined(_WIN32)
    constexpr std::string_view operating_system = "windows";
#elif defined(__linux__)
    constexpr std::string_view operating_system = "linux";
#elif defined(__APPLE__)
    constexpr std::string_view operating_system = "macos";
#else
    constexpr std::string_view operating_system = "unknown";
#endif

#if defined(_M_X64) || defined(__x86_64__)
    constexpr std::string_view architecture = "x86_64";
#elif defined(_M_ARM64) || defined(__aarch64__)
    constexpr std::string_view architecture = "arm64";
#else
    constexpr std::string_view architecture = "unknown";
#endif

    return {operating_system, architecture};
}

}  // namespace jfg
