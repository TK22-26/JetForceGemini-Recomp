#include "timing.h"
#include "jfg/boot/native_cache_all.hpp"
#include "jfg/boot/reference_cache.hpp"
#include <vector>
#include <random>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <chrono>
static unsigned cache_calls=0;
static void check(bool b,const char* what){if(!b){std::printf("FAIL %s\n",what);std::exit(1);}}
extern "C" {
JfgOriginalTimingFast* jfg_original_timing_state=nullptr;
int32_t* section_addresses=nullptr;
void cache_all_reference(uint8_t*,recomp_context*);
void jfg_phase9_execution_probe_predecoded(unsigned,unsigned,unsigned,void*){}
void cache_op(uint8_t*,recomp_context*,uint32_t operation,gpr address) {
 check(operation==1 && address==0xffffffff80000000ULL+16ULL*cache_calls,"exact cache walk order");
 check(jfg::boot::reference_coherent_cache_operation(operation,address,0x400000U),"reference cache accepts operation");
 ++cache_calls;
}
}
int main(){
 std::vector<uint8_t> original(4U*1024U*1024U),ram(original.size());
 std::mt19937_64 random(0xcac4e123);for(auto& b:original)b=static_cast<uint8_t>(random());
 uint64_t reference_ns=0,native_ns=0;
 for(unsigned n=0;n<512;++n){
  recomp_context initial{};
  #define REGISTER(i) initial.r##i=random();
  REGISTER(1) REGISTER(2) REGISTER(3) REGISTER(4) REGISTER(5) REGISTER(6) REGISTER(7)
  REGISTER(8) REGISTER(9) REGISTER(10) REGISTER(11) REGISTER(12) REGISTER(13) REGISTER(14) REGISTER(15)
  REGISTER(16) REGISTER(17) REGISTER(18) REGISTER(19) REGISTER(20) REGISTER(21) REGISTER(22) REGISTER(23)
  REGISTER(24) REGISTER(25) REGISTER(26) REGISTER(27) REGISTER(28) REGISTER(29) REGISTER(30) REGISTER(31)
  #undef REGISTER
  initial.hi=random();initial.lo=random();initial.status_reg=static_cast<uint32_t>(random());initial.fcr31=static_cast<uint32_t>(random());
  initial.mips3_float_mode=static_cast<uint8_t>(n%2);initial.f4.u64=random();initial.f12.u64=random();
  auto a=initial,b=initial;ram=original;cache_calls=0;
  auto start=std::chrono::steady_clock::now();cache_all_reference(ram.data(),&a);
  reference_ns+=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-start).count();
  check(cache_calls==512 && ram==original,"reference complete walk has no RAM writes");
  start=std::chrono::steady_clock::now();check(jfg::boot::native_cache_all_try(ram.data(),&b),"admitted pinned routine");
  native_ns+=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-start).count();
  check(std::memcmp(&a,&b,sizeof(a))==0 && ram==original,"full CPU and all RAM match");
 }
 recomp_context bad{};bad.r0=1;const auto before=bad;
 check(!jfg::boot::native_cache_all_try(ram.data(),&bad) && std::memcmp(&before,&bad,sizeof(bad))==0 && ram==original,"atomic bad-zero-register rejection");
 check(!jfg::boot::native_cache_all_try(nullptr,&bad) && !jfg::boot::native_cache_all_try(ram.data(),nullptr),"null rejection");
 std::printf("PASS 512 complete CPU/RAM cases; each reference performs 512 validated cache operations; 3 rejected inputs; reference_ns=%llu native_ns=%llu\n",reference_ns,native_ns);
}
