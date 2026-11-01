#include "jfg/boot/native_audio_source.hpp"
#include <cstdlib>
#include <iostream>
#include <vector>
using namespace jfg::boot;
static void check(bool value,const char* why) { if(!value){std::cerr<<why<<'\n';std::exit(1);} }
struct Fixture {
 std::vector<std::uint8_t> bytes=std::vector<std::uint8_t>(0x200000,0xA5),rom=std::vector<std::uint8_t>(65536);
 NativeAudioSourceLayout binding;
 hle::GuestMemory memory;
 explicit Fixture(hle::GuestMemory::Layout layout, NativeAudioSourceLayout config):binding(config),memory(bytes,layout) {
  const auto signature=audio_source_signature(binding);
  for(std::size_t i=0;i<rom.size();++i)rom[i]=static_cast<std::uint8_t>((i*37U+i/257U)&255U);
  for(std::uint32_t i=0;i<signature.size();++i)put(binding.callback+i*4U,signature[i]);
  put(binding.control+4U,0);put(binding.control+8U,binding.nodes);put(binding.frame,1);put(binding.pending_dma,0);
  for(std::uint32_t i=0;i<kAudioCacheCount;++i){const auto p=binding.nodes+i*20U;
   put(p,i+1U==kAudioCacheCount?0U:p+20U);put(p+4U,i==0U?0U:p-20U);
   put(p+8U,0);put(p+12U,0);put(p+16U,0x80100000U+i*kAudioCacheBytes);
  }
 }
 void put(std::uint32_t p,std::uint32_t v){check(memory.write_u32(p,v),"fixture write");}
 std::uint32_t get(std::uint32_t p){std::uint32_t v=0;check(memory.read_u32(p,v),"fixture read");return v;}
 void payload(std::uint32_t physical,std::uint32_t source,std::uint32_t n){
  for(std::uint32_t i=0;i<n;++i){const auto a=0x80000000U+physical+i;
   check(static_cast<std::uint8_t>(get(a&~3U)>>((3U-(a&3U))*8U))==rom[source+i],"returned samples must be ready immediately");}
 }
 void reject(std::uint32_t source,std::uint32_t n){const auto before=bytes;check(!provide_native_audio_source(memory,binding,rom,source,n),"invalid request should reject");check(bytes==before,"reject mutated guest memory");}
};
int main(){
 for(const auto binding:{NativeAudioSourceLayout{0x80008000U,0x80021000U,0x80021010U,0x80010000U,0x80010004U},
                         NativeAudioSourceLayout{0x8000A400U,0x80038000U,0x80038010U,0x80018400U,0x80018404U}}){
 for(auto layout:{hle::GuestMemory::Layout::byte_linear_big_endian,hle::GuestMemory::Layout::native_word_big_endian}){
  Fixture f(layout,binding);const auto queue=f.get(0x800F28A0U);
  auto a=provide_native_audio_source(f.memory,binding,f.rom,103U,99U);check(a.has_value()&&!a->cache_hit,"first miss");
  check(a->physical_address==0x100001U,"odd source address");f.payload(a->physical_address,103,99);f.payload(0x100000,102,640);
  check(f.get(binding.pending_dma)==0&&f.get(0x800F28A0U)==queue,"native source must not publish deferred requests or messages");
  const auto remaining=f.get(binding.control+8U);f.put(binding.frame,7);
  a=provide_native_audio_source(f.memory,binding,f.rom,110U,600U);check(a&&a->cache_hit,"contained range hit");
  check(f.get(binding.control+8U)==remaining&&f.get(binding.nodes+12U)==7,"hit lifetime / no allocation");f.payload(a->physical_address,110,600);
  for(auto source:{900U,20U,600U,2000U}){a=provide_native_audio_source(f.memory,binding,f.rom,source,300U);check(a.has_value(),"head/middle/tail cache insertion");f.payload(a->physical_address,source,300);}
  auto p=f.get(binding.control+4U);std::uint32_t last=0;
  while(p){check(f.get(p+8U)>=last,"used list source order");last=f.get(p+8U);p=f.get(p);}
  // Exercise the original owner's reclamation contract: unlink the oldest
  // entry to the free-list head, then require its new payload before return.
  const auto reclaimed=f.get(binding.control+4U),next=f.get(reclaimed),free=f.get(binding.control+8U);
  f.put(binding.control+4U,next);f.put(next+4U,0);f.put(reclaimed,free);f.put(reclaimed+4U,0);f.put(free+4U,reclaimed);f.put(binding.control+8U,reclaimed);
  a=provide_native_audio_source(f.memory,binding,f.rom,5000U,400U);check(a&&!a->cache_hit,"reclaimed entry must refill");f.payload(a->physical_address,5000,400);
  f.reject(0,0);f.reject(101,640);f.reject(0xFFFFFFFFU,20);f.reject(65500,100);f.reject(65500,20);
  {Fixture x(layout,binding);x.put(binding.pending_dma,1);x.reject(1000,100);}
  {Fixture x(layout,binding);x.put(binding.callback,0);x.reject(1000,100);}
  {Fixture x(layout,binding);x.put(binding.nodes,binding.nodes);x.reject(1000,100);}
  {Fixture x(layout,binding);x.put(binding.nodes+20U+16U,x.get(binding.nodes+16U));x.reject(1000,100);}
  {Fixture x(layout,binding);x.put(binding.nodes+16U,0x801FFFF8U);x.reject(1000,100);}
  {Fixture x(layout,binding);x.put(binding.nodes+16U,binding.nodes);x.reject(1000,100);}
  {Fixture x(layout,binding);for(std::uint32_t i=0;i<kAudioCacheCount;++i){auto v=provide_native_audio_source(x.memory,binding,x.rom,i*642U,640U);check(v.has_value(),"fill cache");x.payload(v->physical_address,i*642U,640U);}
   check(x.get(binding.control+8U)==0,"all cache entries allocated");x.reject(60000,300);
   auto v=provide_native_audio_source(x.memory,binding,x.rom,642U,640U);check(v&&v->cache_hit,"full cache still serves existing range");}
 }
 }
 std::cout<<"native audio source: immediate readiness, offsets, hits, reclamation, exhaustion, malformed state and both memory layouts passed\n";
}
