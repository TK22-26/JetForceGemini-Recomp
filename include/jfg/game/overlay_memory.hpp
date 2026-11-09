#pragma once
#include "jfg/game/descriptor.hpp"
#include <stdexcept>

namespace jfg::game {
// A non-owning field view inside an already-held live overlay lease. The
// runtime owns activation/suspension and must not retain this view beyond that
// lease. A linked dispatch token is never accepted as a loaded address here.
template<class Memory> class OverlayMemory {
  const Descriptor& descriptor_;
  Memory& memory_;
  std::uint32_t owner_,base_;
  std::uint32_t address(DataRef ref,std::uint32_t offset,std::uint32_t width) const {
    if(owner_>=descriptor_.sections.size() || ref.section!=owner_ ||
       descriptor_.sections[owner_].kind!=SectionKind::overlay ||
       (ref.domain!=DataDomain::data && ref.domain!=DataDomain::bss) ||
       !valid_data_ref(descriptor_,ref) || offset>ref.size || width>ref.size-offset)
      throw std::runtime_error("Overlay field leaves its revision, module or extent");
    const auto& section=descriptor_.sections[owner_];
    const std::uint64_t relative=std::uint64_t(section.text_size)+
        (ref.domain==DataDomain::bss?section.data_size:0U)+ref.offset+offset;
    const std::uint64_t result=std::uint64_t(base_)+relative;
    if(result+width>0x100000000ULL || (result&(width-1U)) ||
       !memory_.valid(static_cast<std::uint32_t>(result),width))
      throw std::runtime_error("Overlay field leaves its loaded memory view");
    return static_cast<std::uint32_t>(result);
  }
public:
  OverlayMemory(const Descriptor& descriptor,std::uint32_t owner,std::uint32_t base,Memory& memory)
      :descriptor_(descriptor),memory_(memory),owner_(owner),base_(base) {}
  std::uint8_t u8(DataRef ref,std::uint32_t offset=0) const {return memory_.u8(address(ref,offset,1));}
  std::uint16_t u16(DataRef ref,std::uint32_t offset=0) const {return memory_.u16(address(ref,offset,2));}
  std::uint32_t u32(DataRef ref,std::uint32_t offset=0) const {return memory_.u32(address(ref,offset,4));}
};
} // namespace jfg::game
