#include "timing.h"
#include "jfg/boot/native_shadow_filter.hpp"
#include <vector>
#include <random>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <chrono>
extern "C" {
JfgOriginalTimingFast* jfg_original_timing_state=nullptr;
int32_t* section_addresses=nullptr;
void shadow_filter_reference(uint8_t*,recomp_context*);
void jfg_phase9_execution_probe_predecoded(unsigned,unsigned,unsigned,void*){}
}
static void check(bool b,unsigned n,const char* what){if(!b){std::printf("FAIL %u %s\n",n,what);std::exit(1);}}
static void word(std::vector<uint8_t>& ram,uint32_t address,uint32_t value){std::memcpy(ram.data()+address-0x80000000U,&value,4);}
int main(){
 constexpr uint32_t object=0x80010000U;
 std::vector<uint8_t> source(4U*1024U*1024U),reference(source.size()),candidate(source.size());
 std::mt19937_64 random(0x9ab3a312);uint64_t fast_ns=0,reference_ns=0;
 for(unsigned n=0;n<2048;++n){
  for(auto& b:source)b=static_cast<uint8_t>(n<4?n*85:random());
  const uint32_t image=n%3==0?0x80000000U:n%3==1?0x803ff000U:0x80100000U;
  word(source,object+32U,image);reference=source;candidate=source;
  recomp_context initial{};
  #define REGISTER(i) initial.r##i=random();
  REGISTER(1) REGISTER(2) REGISTER(3) REGISTER(4) REGISTER(5) REGISTER(6) REGISTER(7)
  REGISTER(8) REGISTER(9) REGISTER(10) REGISTER(11) REGISTER(12) REGISTER(13) REGISTER(14) REGISTER(15)
  REGISTER(16) REGISTER(17) REGISTER(18) REGISTER(19) REGISTER(20) REGISTER(21) REGISTER(22) REGISTER(23)
  REGISTER(24) REGISTER(25) REGISTER(26) REGISTER(27) REGISTER(28) REGISTER(29) REGISTER(30) REGISTER(31)
  #undef REGISTER
  initial.r4=U64(S32(object));initial.hi=random();initial.lo=random();initial.status_reg=static_cast<uint32_t>(random());initial.fcr31=static_cast<uint32_t>(random());
  initial.mips3_float_mode=static_cast<uint8_t>(n%2);initial.f4.u64=random();initial.f12.u64=random();
  auto a=initial,b=initial;auto start=std::chrono::steady_clock::now();
  shadow_filter_reference(reference.data(),&a);
  reference_ns+=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-start).count();
  start=std::chrono::steady_clock::now();check(jfg::boot::native_shadow_filter_try(candidate.data(),&b),n,"admitted known leaf");
  fast_ns+=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-start).count();
  check(std::memcmp(&a,&b,sizeof(a))==0,n,"complete CPU context");check(reference==candidate,n,"all RAM including image borders");
 }
 for(unsigned n=0;n<10;++n){
  recomp_context cpu{};cpu.r4=U64(S32(object));word(source,object+32,0x80100000U);
  switch(n){
   case 0:cpu.r0=1;break;
   case 1:cpu.r4=object;break;
   case 2:cpu.r4=U64(S32(object+1));break;
   case 3:cpu.r4=U64(S32(0x803fffe0U));break;
   case 4:word(source,object+32,0x80100001U);break;
   case 5:word(source,object+32,0x803ff004U);break;
   case 6:word(source,object+32,0xa0100000U);break;
   case 7:word(source,object+32,object);break;
   case 8:word(source,object+32,object+32);break;
   case 9:word(source,object+32,0);break;
  }
  const auto before=cpu;candidate=source;
  check(!jfg::boot::native_shadow_filter_try(candidate.data(),&cpu),n,"reject unsupported admission");
  check(std::memcmp(&before,&cpu,sizeof(cpu))==0 && source==candidate,n,"atomic rejection");
 }
 check(!jfg::boot::native_shadow_filter_try(nullptr,nullptr),0,"null rejection");
 std::printf("PASS 2048 full-context/full-RAM cases; 11 rejected inputs; reference_ns=%llu native_ns=%llu\n",reference_ns,fast_ns);
}
