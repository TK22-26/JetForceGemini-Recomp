#include "jfg/boot/native_shadow_filter.hpp"
extern "C" {
#include "recomp.h"
}
#include <cstring>
namespace jfg::boot::shadow_filter_detail {
#pragma warning(push, 0)
#include JFG_NATIVE_SHADOW_FILTER_BODY
#pragma warning(pop)
static bool range(std::uint32_t address,std::size_t bytes) {
 return address>=0x80000000U && address<=0x80400000U && bytes<=0x80400000ULL-address;
}
}
namespace jfg::boot {
bool native_shadow_filter_try(std::uint8_t* ram,recomp_context* cpu) noexcept {
 if(!ram || !cpu || cpu->r0)return false;
 const auto object=static_cast<std::uint32_t>(cpu->r4);
 if(cpu->r4!=U64(S32(object)) || (object&3U) || !shadow_filter_detail::range(object,36U))return false;
 std::uint32_t image=0;
 std::memcpy(&image,ram+(object-0x80000000U)+32U,sizeof(image));
 if((image&3U) || !shadow_filter_detail::range(image,4096U))return false;
 // The leaf reloads its image pointer after filtering. Its pointer field must
 // not alias any image byte written by the in-place operation.
 if(std::uint64_t(object)+32U<std::uint64_t(image)+4096U && std::uint64_t(object)+36U>image)return false;
 shadow_filter_detail::shadow_filter_core(ram,cpu);
 return true;
}
}
