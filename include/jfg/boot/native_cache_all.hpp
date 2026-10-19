#pragma once
#include <cstdint>
struct recomp_context;
namespace jfg::boot {
#if defined(JFG_NATIVE_CACHE_ALL_ENABLED)
// Pinned whole-cache walk in the existing coherent-memory model. Rejected inputs are untouched. The caller
// must refresh elapsed clocks/events before its next generated instruction.
bool native_cache_all_try(std::uint8_t* ram,recomp_context* cpu) noexcept;
#else
inline bool native_cache_all_try(std::uint8_t*,recomp_context*) noexcept { return false; }
#endif
}
