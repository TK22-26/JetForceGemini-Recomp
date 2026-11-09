#pragma once
#include "jfg/game/descriptor.hpp"
#include <stdexcept>

namespace jfg::game {
// A game reference is interpreted only against its owning immutable descriptor.
// This view does not translate raw US addresses or grant overlay lifetimes.
template<class Memory> class ResidentMemory {
  const Descriptor& descriptor_;
  Memory& memory_;
  std::uint32_t address(DataRef ref,std::uint32_t offset,std::uint32_t width) const {
    const auto base=resident_address(descriptor_,ref);
    if(!base || offset>ref.size || width>ref.size-offset ||
       std::uint64_t{*base}+offset+width>0x100000000ULL ||
       ((*base+offset)&(width-1U))!=0 || !memory_.valid(*base+offset,width))
      throw std::runtime_error("Game data reference leaves its revision, owner or extent");
    return *base+offset;
  }
public:
  ResidentMemory(const Descriptor& descriptor,Memory& memory):descriptor_(descriptor),memory_(memory) {}
  std::uint32_t range(DataRef ref,std::uint32_t offset,std::uint32_t width,std::uint32_t alignment=1) const {
    const auto base=resident_address(descriptor_,ref);
    if(!base || !width || !alignment || (alignment&(alignment-1U)) || offset>ref.size || width>ref.size-offset ||
       std::uint64_t{*base}+offset+width>0x100000000ULL || ((*base+offset)&(alignment-1U)) || !memory_.valid(*base+offset,width))
      throw std::runtime_error("Game data range leaves its revision, owner or extent");
    return *base+offset;
  }
  std::uint8_t u8(DataRef ref,std::uint32_t offset=0) const {return memory_.u8(address(ref,offset,1));}
  std::uint16_t u16(DataRef ref,std::uint32_t offset=0) const {return memory_.u16(address(ref,offset,2));}
  std::uint32_t u32(DataRef ref,std::uint32_t offset=0) const {return memory_.u32(address(ref,offset,4));}
};
} // namespace jfg::game
