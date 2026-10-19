#include "jfg/boot/direct_mi_mask_access.hpp"
extern "C" {
#include "recomp.h"
#include "funcs.h"
std::int32_t jfg_sp_load_word(std::uint8_t*,std::uint64_t,std::int16_t);
void jfg_sp_store_word(std::uint8_t*,std::uint64_t,std::int16_t,std::int32_t);
std::int32_t jfg_mmio_mask_read32(std::uint8_t*,void*,std::uint64_t);
void jfg_mmio_mask_write32(std::uint8_t*,void*,std::uint64_t,std::uint32_t);
}
namespace jfg::boot::direct_mi_mask_detail {
#pragma warning(push, 0)
#include JFG_DIRECT_MI_MASK_ACCESS_BODY
#pragma warning(pop)
}
namespace jfg::boot {
bool direct_mi_mask_function(std::uint32_t target,std::uint8_t* ram,recomp_context* cpu) {
 return direct_mi_mask_detail::mi_mask_dispatch(target,ram,cpu);
}
}
