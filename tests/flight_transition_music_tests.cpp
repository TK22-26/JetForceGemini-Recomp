#include "jfg/runtime/flight_transition_music.hpp"
#include "jfg/mod/navigation_mod.hpp"
#include <cstdlib>
#include <iostream>
#include <vector>
int main() {
 unsigned checks=0;
 const auto check=[&](bool ok){++checks;if(!ok){std::cerr<<"failed "<<checks<<"\n";std::exit(1);}};
 std::vector<std::uint8_t> bytes(4*1024*1024);jfg::mod::Memory ram(bytes,false);
 const auto put=[&](std::uint32_t at,std::uint32_t value){for(unsigned i=0;i<4;++i)bytes[(at&0x1FFFFFFFU)+i]=std::uint8_t(value>>(24U-8U*i));};
 const auto setup=[&](const jfg::FlightMusicScene& s){
  put(0x8004455C,0x27BDFFE8);put(0x80044570,0x91CF0072);put(0x80043BE0,0x93220004);
  put(0x80046FC0,0x0C010EEE);put(0x800468AC,0xA4243254);put(0x800FB124,412);put(0x800FB12C,0x80210000);
  put(0x800FB114,s.level);put(0x800FB118,0x80200000);put(0x800A74C0,s.group);
  put(0x800A3250,s.level<<16);put(0x800A3254,s.group<<16);
  bytes[0x20006C]=1;bytes[0x200072]=std::uint8_t(s.track);bytes[0x200073]=0xA5;
  bytes[0x2000E8]=std::uint8_t(s.asset>>8);bytes[0x2000E9]=std::uint8_t(s.asset);
  put(0x80210000+s.level*5,s.metadata);bytes[0x210000+s.level*5+4]=std::uint8_t(s.track);
 };
 for(const auto& s:jfg::flight_music_scenes){
  setup(s);const auto original=bytes;
  // Transition prediction and actual playback agree; no stop/restart is needed
  // when the native current-tune comparison already reports the flight theme.
  check(jfg::flight_transition_next_music(ram,s.level,0x80046FC8)==7U);check(bytes==original);
  check(jfg::apply_flight_transition_music_header(ram));auto expected=original;expected[0x200072]=7;
  check(bytes==expected);check(!jfg::apply_flight_transition_music_header(ram));check(bytes==expected);
  for(auto caller:{0U,0x800445C4U,0x80046FC0U,0x80046FD0U})check(!jfg::flight_transition_next_music(ram,s.level,caller));
  setup(s);put(0x800A74C0,s.group+1);check(!jfg::apply_flight_transition_music_header(ram));
  setup(s);put(0x800A3254,(s.group+1)<<16);check(!jfg::flight_transition_next_music(ram,s.level,0x80046FC8));
  setup(s);put(0x800A3250,(s.level+1)<<16);check(!jfg::flight_transition_next_music(ram,s.level,0x80046FC8));
  setup(s);++bytes[0x2000E9];check(!jfg::apply_flight_transition_music_header(ram));
  setup(s);bytes[0x20006C]=0;check(!jfg::apply_flight_transition_music_header(ram));
  for(unsigned tune=0;tune<128;++tune)if(tune!=s.track){setup(s);bytes[0x200072]=std::uint8_t(tune);check(!jfg::apply_flight_transition_music_header(ram));}
  for(unsigned offset=0;offset<5;++offset){setup(s);bytes[0x210000+s.level*5+offset]^=1;check(!jfg::flight_transition_next_music(ram,s.level,0x80046FC8));}
  for(auto pc:{0x8004455CU,0x80044570U}){setup(s);put(pc,0);check(!jfg::apply_flight_transition_music_header(ram));}
  for(auto pc:{0x80046FC0U,0x80043BE0U,0x800468ACU}){setup(s);put(pc,0);check(!jfg::flight_transition_next_music(ram,s.level,0x80046FC8));}
  setup(s);put(0x800FB118,0xFFFFFFF0);check(!jfg::apply_flight_transition_music_header(ram));
  setup(s);put(0x800FB12C,0x803FFFF0);check(!jfg::flight_transition_next_music(ram,s.level,0x80046FC8));
  setup(s);put(0x800FB124,413);check(!jfg::flight_transition_next_music(ram,s.level,0x80046FC8));
 }
 // Incoming Walkway and unrelated scenes must retain original selections.
 for(const auto& s:std::array<jfg::FlightMusicScene,7>{{{15,0,15,2,0x010E0001},{22,0,22,2,0},{94,0,46,7,0},{102,0,104,7,0},{368,0,368,7,0},{271,0,272,7,0},{342,1,342,7,0}}}){
  setup(s);const auto before=bytes;check(!jfg::flight_transition_next_music(ram,s.level,0x80046FC8));check(!jfg::apply_flight_transition_music_header(ram));check(bytes==before);
 }
 std::cout<<"PASS "<<checks<<" flight music boundary checks\n";
}
