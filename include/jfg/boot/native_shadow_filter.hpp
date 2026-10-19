#pragma once
#include <cstdint>
struct recomp_context;
namespace jfg::boot {
#if defined(JFG_NATIVE_SHADOW_FILTER_ENABLED)
// A complete fixed-size integer leaf. Rejected inputs are untouched. The caller
// must refresh elapsed clocks/events before its next generated instruction.
bool native_shadow_filter_try(std::uint8_t* ram,recomp_context* cpu) noexcept;
#else
inline bool native_shadow_filter_try(std::uint8_t*,recomp_context*) noexcept { return false; }
#endif
}
