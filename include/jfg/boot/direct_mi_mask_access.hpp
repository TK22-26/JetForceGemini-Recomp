#pragma once
#include <cstdint>
struct recomp_context;
namespace jfg::boot {
#if defined(JFG_DIRECT_MI_MASK_ACCESS_ENABLED)
bool direct_mi_mask_function(std::uint32_t,std::uint8_t*,recomp_context*);
#else
inline bool direct_mi_mask_function(std::uint32_t,std::uint8_t*,recomp_context*) {return false;}
#endif
}
