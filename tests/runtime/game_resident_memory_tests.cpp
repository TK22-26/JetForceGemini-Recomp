#include "jfg/game/resident_memory.hpp"
#include <array>
#include <iostream>
using namespace jfg::game;
struct Memory {
  std::uint32_t base;std::array<std::uint8_t,64> bytes{};
  bool valid(std::uint32_t address,std::uint32_t size) const {return address>=base && address-base<=bytes.size() && size<=bytes.size()-(address-base);}
  std::uint8_t u8(std::uint32_t address) const {return bytes.at(address-base);}
  std::uint16_t u16(std::uint32_t address) const {return (u8(address)<<8)|u8(address+1);}
  std::uint32_t u32(std::uint32_t address) const {return (std::uint32_t{u16(address)}<<16)|u16(address+2);}
};
int main() {
  int failures=0;const auto check=[&](bool v){if(!v)++failures;};
  for(const auto base:{0x80001000U,0x80102000U,0x80203000U}) {
    Memory memory{base};memory.bytes[16]=0x12;memory.bytes[17]=0x34;memory.bytes[18]=0x56;memory.bytes[19]=0x78;
    const std::array sections{Section{SectionKind::main,0,base,16,16,32}};
    Descriptor d{};d.revision="fixture";d.sections=sections;
    ResidentMemory view(d,memory);DataRef ref{"fixture",0,DataDomain::data,0,4,4};
    check(view.u32(ref)==0x12345678U);check(view.u16(ref,2)==0x5678U);check(view.u8(ref,3)==0x78U);
    const auto rejects=[&](auto action){try{action();++failures;}catch(const std::runtime_error&) {}};
    rejects([&]{view.u8(ref,4);});rejects([&]{view.u16(ref,3);});rejects([&]{view.u32(ref,1);});
    auto wrong=ref;wrong.revision="another";rejects([&]{view.u8(wrong);});
    wrong=ref;wrong.offset=15;rejects([&]{view.u8(wrong);});
    auto overlay=sections;overlay[0].kind=SectionKind::overlay;d.sections=overlay;rejects([&]{view.u8(ref);});
    d.sections=sections;memory.base=base+32;rejects([&]{view.u8(ref);});
  }
  if(failures)std::cerr<<failures<<" resident memory failures\n";
  return failures?1:0;
}
