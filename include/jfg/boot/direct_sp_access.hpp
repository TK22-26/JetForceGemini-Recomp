#pragma once
#include <cstdint>
struct recomp_context;
namespace jfg::boot {
#if defined(JFG_DIRECT_SP_ACCESS_ENABLED)
// Private generated variants retain every instruction probe and fallback span.
bool direct_sp_function(std::uint32_t target,std::uint8_t* ram,recomp_context* cpu);
#else
inline bool direct_sp_function(std::uint32_t,std::uint8_t*,recomp_context*) {return false;}
#endif
}
