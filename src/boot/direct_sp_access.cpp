#include "jfg/boot/direct_sp_access.hpp"
extern "C" {
#include "recomp.h"
#include "funcs.h"
std::int32_t jfg_sp_load_word(std::uint8_t*,std::uint64_t,std::int16_t);
void jfg_sp_store_word(std::uint8_t*,std::uint64_t,std::int16_t,std::int32_t);
}
namespace jfg::boot::direct_sp_detail {
#pragma warning(push, 0)
#include JFG_DIRECT_SP_ACCESS_BODY
#pragma warning(pop)
}
namespace jfg::boot {
bool direct_sp_function(std::uint32_t target,std::uint8_t* ram,recomp_context* cpu) {
 return direct_sp_detail::sp_access_dispatch(target,ram,cpu);
}
}
