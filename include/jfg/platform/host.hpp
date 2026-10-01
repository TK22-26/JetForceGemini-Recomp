#pragma once

#include <string_view>

namespace jfg {

struct HostDescription {
    std::string_view operating_system;
    std::string_view architecture;
};

[[nodiscard]] HostDescription current_host();

}  // namespace jfg
