#include "jfg/boot/native_rom_dma.hpp"
#include "jfg/boot/original_timing_pi_dma.hpp"
#include <iostream>
#include <vector>
using namespace jfg::boot;
unsigned checks=0;
void check(bool value,const char* label){++checks;if(!value){std::cerr<<label<<'\n';std::exit(1);}}
struct Fixture {
 std::vector<std::uint8_t> ram=std::vector<std::uint8_t>(0x20000,0xa5),rom=std::vector<std::uint8_t>(8192);
 hle::GuestMemory memory{ram,hle::GuestMemory::Layout::native_word_big_endian};
 static constexpr std::uint32_t manager=0x80001000,thread=0x80002000,tail=0x80003000;
 NativeRomDmaRequest request{0x80005000,0,0,100,0x80010000,256,0x80006300,0x80004000};
 void put(std::uint32_t a,std::uint32_t v){check(memory.write_u32(a,v),"fixture write");}
 std::uint32_t get(std::uint32_t a){std::uint32_t v=0;check(memory.read_u32(a,v),"fixture read");return v;}
 Fixture(){
  for(std::size_t i=0;i<rom.size();++i)rom[i]=static_cast<std::uint8_t>(i*37U+i/257U);
  put(manager,1);put(manager+4,thread);put(manager+8,0x80006000);put(manager+12,0x80006100);put(manager+16,0x80006200);
  put(thread,tail);put(thread+4,150);put(thread+8,0x80006000);put(thread+16,8U<<16U);put(tail,0);put(tail+4,UINT32_MAX);
  for(unsigned i=0;i<4;++i){const auto q=0x80006000U+i*256U;put(q,i==0?thread:tail);put(q+4,tail);put(q+8,i==2?1:0);put(q+12,i==3?1:0);put(q+16,i==0?16:i==3?4:1);put(q+20,0x80007000U+i*256U);}
  put(0x80007200,0);
 }
 void reject(bool idle=true){const auto before=ram;check(!complete_native_rom_dma(ram,rom,manager,request,idle),"unsupported request admitted");check(ram==before,"fallback mutated memory");}
};
int main(){
 for(unsigned source:{0U,2U,100U,4096U,7680U})for(unsigned destination:{0U,2U,4U,6U})for(unsigned size:{2U,14U,128U,512U})for(unsigned priority:{0U,1U}){
  Fixture f;f.request.device=source;f.request.destination+=destination;f.request.length=size;f.request.priority=priority;const auto before=f.ram;
  auto expected=before;OriginalTimingPiDma original;
  check(original.write(0,f.request.destination-0x80000000U,1,expected,f.rom),"PI destination");
  check(original.write(4,0x10000000U+source,1,expected,f.rom),"PI source");
  check(original.write(12,size-1,1,expected,f.rom,nullptr,nullptr,true),"PI transfer");
  check(complete_native_rom_dma(f.ram,f.rom,f.manager,f.request,true),"valid ROM request declined");
  for(unsigned i=0;i<f.ram.size();++i){
   const auto a=0x80000000U+i;
   const bool descriptor=a>=f.request.message&&a<f.request.message+24U;
   const bool count=a>=f.request.completion+8U&&a<f.request.completion+12U;
   const bool message=a>=0x80007304U&&a<0x80007308U;
   if(!descriptor&&!count&&!message)check(f.ram[i]==expected[i],"payload or unrelated memory differs from PI model");
  }
  check(f.get(f.request.message)==((11U<<16U)|(priority<<8U)|0xa5U),"type/priority/preserved status");
  check(f.get(f.request.message+4)==f.request.completion&&f.get(f.request.message+8)==f.request.destination,"descriptor pointers");
  check(f.get(f.request.message+12)==source&&f.get(f.request.message+16)==size&&f.get(f.request.message+20)==0,"descriptor data/handle");
  check(f.get(0x80007304)==f.request.message&&f.get(f.request.completion+8)==1,"actual completion message pointer");
  check(hle::os_recv_mesg(f.memory,f.request.completion,0x80008000)==0&&f.get(0x80008000)==f.request.message,"normal guest queue consumption");
  check(f.get(f.request.completion+8)==0&&f.get(f.request.completion+12)==2,"normal FIFO position after consumption");
 }
 {Fixture f;f.request.device+=0x10000000U;check(complete_native_rom_dma(f.ram,f.rom,f.manager,f.request,true),"physical cartridge alias");check(f.get(f.request.message+12)==f.request.device,"original device argument retained");}
 for(unsigned scenario=0;scenario<23;++scenario){Fixture f;switch(scenario){
  case 0:f.request.direction=1;break;case 1:f.request.priority=2;break;case 2:f.request.device=0x08000000;break;
  case 3:f.request.device=0xb0000000;break;case 4:f.request.device=8190;break;case 5:f.request.length=0;break;
  case 6:f.request.length=0xffffffff;break;case 7:f.request.destination=0xa0010000;break;case 8:f.request.destination=0x8001fff0;break;
  case 9:f.request.destination++;break;case 10:f.request.device++;break;case 11:f.request.length++;break;
  case 12:f.request.message=0xfffffffc;break;case 13:f.request.message++;break;case 14:f.request.message=f.manager;break;
  case 15:f.request.destination=f.request.message;break;case 16:f.request.destination=f.thread;break;case 17:f.request.destination=f.request.completion;break;
  case 18:f.request.destination=0x80007300;break;case 19:f.request.completion=0x80006000;break;case 20:f.request.stack=0x8001fff0;break;
  case 21:f.request.destination=f.request.stack;break;case 22:f.request.message=0x80007300;break;
 }f.reject();}
 for(const auto& [address,value]:std::array<std::pair<std::uint32_t,std::uint32_t>,23>{{
  {0x80001000,0},{0x80001004,0xfffffff0},{0x80001008,0},{0x8000100c,0},{0x80001010,0},
  {0x80002000,0},{0x80002004,0},{0x80002008,0},{0x80002010,4U<<16U},{0x80003000,1},{0x80003004,0},
  {0x80006000,0x80003000},{0x80006008,1},{0x80006108,1},{0x80006208,0},{0x80006210,2},{0x80007200,1},
  {0x80006300,0x80002000},{0x80006304,0x80002000},{0x80006308,1},{0x8000630c,4},{0x80006310,4097},{0x80006314,0x8001fffe}}}){Fixture f;f.put(address,value);f.reject();}
 {Fixture f;f.reject(false);}
 std::cout<<checks<<" native ROM DMA checks passed\n";
}
