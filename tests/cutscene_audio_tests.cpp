#include "jfg/runtime/cutscene_audio.hpp"
#include "jfg/mod/navigation_mod.hpp"
#include <cstdlib>
#include <iostream>
#include <vector>

int main() {
  unsigned checks=0;
  const auto check=[&](bool ok){++checks;if(!ok){std::cerr<<"failed "<<checks<<"\n";std::exit(1);}};
  std::vector<std::uint8_t> bytes(4*1024*1024);
  jfg::mod::Memory ram(bytes,false);
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
  check(jfg::omit_skipped_cutscene_sound(ram,call));
  for(unsigned slot=0;slot<16;++slot) {
    auto c=call;c.handle+=slot*4;
    check(jfg::omit_skipped_cutscene_sound(ram,c));
    put(c.handle,0x800E6E20);check(!jfg::omit_skipped_cutscene_sound(ram,c));put(c.handle,0);
  }
  auto c=call;c.chain=false;check(!jfg::omit_skipped_cutscene_sound(ram,c));
  c=call;c.qualified_scene=0;check(!jfg::omit_skipped_cutscene_sound(ram,c));
  c=call;++c.qualified_scene;check(!jfg::omit_skipped_cutscene_sound(ram,c));
  c=call;++c.destination;check(!jfg::omit_skipped_cutscene_sound(ram,c));
  c=call;++c.group;check(!jfg::omit_skipped_cutscene_sound(ram,c));
  for(auto target:{0x80000510U,0x80000F2CU,0x80000E6CU,0x80001228U}) {
    c=call;c.target=target;check(!jfg::omit_skipped_cutscene_sound(ram,c));
  }
  for(auto pc:{0U,0x80078050U,0x80078058U,0x80050000U}) {
    c=call;c.return_address=pc;check(!jfg::omit_skipped_cutscene_sound(ram,c));
  }
  for(auto ptr:{0U,0x801045C4U,0x801045C9U,0x80104608U,0xFFFFFFFFU}) {
    c=call;c.handle=ptr;check(!jfg::omit_skipped_cutscene_sound(ram,c));
  }
  c=call;c.return_address=0x80077EFC;c.handle=0;
  check(jfg::omit_skipped_cutscene_sound(ram,c));c.handle=0x801045C8;
  check(!jfg::omit_skipped_cutscene_sound(ram,c));
  c=call;c.target=0x80003410;c.return_address=0x80078108;c.actor=0x80220000;c.handle=c.actor+0x88;
  check(jfg::omit_skipped_cutscene_sound(ram,c));
  put(c.handle,0x800E6E20);check(!jfg::omit_skipped_cutscene_sound(ram,c));put(c.handle,0);
  ++c.handle;check(!jfg::omit_skipped_cutscene_sound(ram,c));--c.handle;
  c.actor=0xFFFFFFFF;check(!jfg::omit_skipped_cutscene_sound(ram,c));
  bytes[0x20006c]=0;check(!jfg::omit_skipped_cutscene_sound(ram,call));bytes[0x20006c]=1;
  put(0x80077EF4,0);c=call;c.return_address=0x80077EFC;c.handle=0;
  check(!jfg::omit_skipped_cutscene_sound(ram,c));put(0x80077EF4,0x0C000492);
  put(0x80001248,0);check(!jfg::omit_skipped_cutscene_sound(ram,call));put(0x80001248,0x3C0F800F);
  put(0x800FB118,0);check(!jfg::omit_skipped_cutscene_sound(ram,call));put(0x800FB118,0x80200000);
  check(bytes==baseline);
  std::cout<<"PASS "<<checks<<" sound-boundary checks; native memory unchanged\n";
}
