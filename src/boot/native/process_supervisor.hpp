#pragma once
#include <cstdint>
#include <vector>
namespace jfg::boot::native {
bool reset_transfer_target(const std::vector<std::uint8_t>&,std::uint32_t&);
#if defined(_WIN32)
bool validate_child_capability(const char*,const char*);
int run_parent(const char*,const char*,unsigned,unsigned,unsigned,bool);
#endif
}
