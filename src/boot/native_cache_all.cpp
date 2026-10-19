#include "jfg/boot/native_cache_all.hpp"
#include "jfg/boot/reference_cache.hpp"
#include <exception>
extern "C" {
#include "recomp.h"
}
namespace jfg::boot::cache_all_detail {
// Cache operations are validation-only in this explicit coherent-memory
// profile. Inline those same checks; retain every generated register effect.
// This is not valid for a future model with dirty lines or hardware cache tags.
static_assert(reference_coherent_cache_operation(1U,0xffffffff80000000ULL,0x400000U));
static_assert(reference_coherent_cache_operation(1U,0xffffffff80001ff0ULL,0x400000U));
#pragma warning(push, 0)
#include JFG_NATIVE_CACHE_ALL_BODY
#pragma warning(pop)
}
namespace jfg::boot {
bool native_cache_all_try(std::uint8_t* ram,recomp_context* cpu) noexcept {
 if (!ram || !cpu || cpu->r0) return false;
 cache_all_detail::cache_all_core(ram,cpu);
 return true;
}
}
