#include "jfg/runtime/cutscene_audio.hpp"
#include "jfg/runtime/guest_memory_view.hpp"
#include <cstdlib>
#include <iostream>
#include <vector>

int main() {
  unsigned checks=0;
  const auto check=[&](bool ok){++checks;if(!ok){std::cerr<<"failed "<<checks<<"\n";std::exit(1);}};
  std::vector<std::uint8_t> bytes(4*1024*1024);
  jfg::GuestMemory ram(bytes,false);
  using namespace jfg::game;
  const std::array sections{Section{SectionKind::main,0,0x80000000U,0xa0000,0x80000,0}};
  const std::array bodies{FunctionBody{0,0x1248,4},FunctionBody{0,0x3410,4},FunctionBody{0,0x77abc,0x2000}};
  Descriptor descriptor{};descriptor.revision="sound-fixture";descriptor.sections=sections;descriptor.bodies=bodies;
  const auto data=[](std::uint32_t address,std::uint32_t size=4){return DataRef{"sound-fixture",0,DataDomain::data,address-0x800a0000U,size,4};};
  const jfg::CutsceneSoundBindings bindings{data(0x800fb114),data(0x800fb118),data(0x800a74c0),data(0x800a74c8),data(0x801045c8,64),
    {"sound-fixture",0,0x1248},{"sound-fixture",0,0x3410},
    {"sound-fixture",0,0x77ef4},{"sound-fixture",0,0x7804c},{"sound-fixture",0,0x78100}};
  const auto omit=[&](const auto& memory,const jfg::CutsceneSoundCall& call){return jfg::omit_skipped_cutscene_sound(memory,call,descriptor,bindings);};

  const auto put=[&](std::uint32_t at,std::uint32_t value) {
    for(unsigned i=0;i<4;++i)bytes[(at&0x1FFFFFFFU)+i]=std::uint8_t(value>>(24U-8U*i));
  };
  put(0x800FB114,379);put(0x800FB118,0x80200000);
  bytes[0x20006c]=1;put(0x800A74C0,1);put(0x800A74C8,0x80210000);
  put(0x80001248,0x3C0F800F);put(0x80003410,0x27BDFFC0);
  put(0x80077EF4,0x0C000492);put(0x8007804C,0x0C000492);put(0x80078100,0x0C000D04);
  jfg::CutsceneSoundCall call{true,(std::uint64_t{379}<<48U)|(std::uint64_t{1}<<32U)|0x80210000U,
    379,1,0x80001248,0x80078054,0x801045C8,0};
  const auto baseline=bytes;
  check(omit(ram,call));
  for(unsigned slot=0;slot<16;++slot) {
    auto c=call;c.handle+=slot*4;
    check(omit(ram,c));
    put(c.handle,0x800E6E20);check(!omit(ram,c));put(c.handle,0);
  }
  auto c=call;c.chain=false;check(!omit(ram,c));
  c=call;c.qualified_scene=0;check(!omit(ram,c));
  c=call;++c.qualified_scene;check(!omit(ram,c));
  c=call;++c.destination;check(!omit(ram,c));
  c=call;++c.group;check(!omit(ram,c));
  for(auto target:{0x80000510U,0x80000F2CU,0x80000E6CU,0x80001228U}) {
    c=call;c.target=target;check(!omit(ram,c));
  }
  for(auto pc:{0U,0x80078050U,0x80078058U,0x80050000U}) {
    c=call;c.return_address=pc;check(!omit(ram,c));
  }
  for(auto ptr:{0U,0x801045C4U,0x801045C9U,0x80104608U,0xFFFFFFFFU}) {
    c=call;c.handle=ptr;check(!omit(ram,c));
  }
  c=call;c.return_address=0x80077EFC;c.handle=0;
  check(omit(ram,c));c.handle=0x801045C8;
  check(!omit(ram,c));
  c=call;c.target=0x80003410;c.return_address=0x80078108;c.actor=0x80220000;c.handle=c.actor+0x88;
  check(omit(ram,c));
  put(c.handle,0x800E6E20);check(!omit(ram,c));put(c.handle,0);
  ++c.handle;check(!omit(ram,c));--c.handle;
  c.actor=0xFFFFFFFF;check(!omit(ram,c));
  bytes[0x20006c]=0;check(!omit(ram,call));bytes[0x20006c]=1;
  put(0x80077EF4,0);c=call;c.return_address=0x80077EFC;c.handle=0;
  check(!omit(ram,c));put(0x80077EF4,0x0C000492);
  auto wrongBindings=bindings;wrongBindings.level.revision="another";
  check(!jfg::omit_skipped_cutscene_sound(ram,call,descriptor,wrongBindings));
  put(0x800FB118,0);check(!omit(ram,call));put(0x800FB118,0x80200000);
  check(bytes==baseline);
  for(const auto delta:{0x4000U,0x8000U}) {
    auto relocatedSections=sections;relocatedSections[0].linked_address+=delta;
    auto relocatedDescriptor=descriptor;relocatedDescriptor.sections=relocatedSections;
    const auto address=[&](auto ref){return *resident_address(relocatedDescriptor,ref);};
    const auto start=0x80210000U+delta,header=0x80200000U+delta;
    put(address(bindings.level),379);put(address(bindings.header),header);
    put(address(bindings.group),1);put(address(bindings.script_start),start);bytes[(header&0x1fffffffU)+0x6c]=1;
    put(address(bindings.handles),0);const auto target=address(bindings.plain),caller=address(bindings.handle_call);
    put(caller,0x0c000000U|((target>>2)&0x03ffffffU));
    auto relocatedCall=call;relocatedCall.target=target;relocatedCall.return_address=caller+8;
    relocatedCall.handle=address(bindings.handles);relocatedCall.qualified_scene=(std::uint64_t{379}<<48U)|(std::uint64_t{1}<<32U)|start;
    check(jfg::omit_skipped_cutscene_sound(ram,relocatedCall,relocatedDescriptor,bindings));
    relocatedCall.handle+=64;check(!jfg::omit_skipped_cutscene_sound(ram,relocatedCall,relocatedDescriptor,bindings));
    relocatedCall.handle-=64;relocatedCall.return_address+=4;check(!jfg::omit_skipped_cutscene_sound(ram,relocatedCall,relocatedDescriptor,bindings));
  }

  std::cout<<"PASS "<<checks<<" sound-boundary checks; native memory unchanged\n";
}
