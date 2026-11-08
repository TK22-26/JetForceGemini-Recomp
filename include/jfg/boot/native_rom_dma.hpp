#pragma once
#include "jfg/boot/hle.hpp"
#include <array>
#include <cstdlib>
#include <span>

namespace jfg::boot {
struct NativeRomDmaRequest {
  std::uint32_t message, priority, direction, device, destination, length, completion, stack;
};
// The region binding resolves the original SDK's OSDevMgr. Its queues and
// thread remain owned by the executed guest OS; this path admits only idle ROM
// reads with no waiting completion consumer. All other requests fall back.
inline bool complete_native_rom_dma(std::span<std::uint8_t> ram,
    std::span<const std::uint8_t> rom, std::uint32_t manager,
    const NativeRomDmaRequest& request, bool device_idle) {
  constexpr std::uint32_t base=0x80000000U;
  const auto range=[&](std::uint32_t address,std::uint64_t size) {
    return address>=base && std::uint64_t(address)-base<=ram.size() &&
      size<=ram.size()-(std::uint64_t(address)-base);
  };
  const auto overlap=[](std::uint32_t a,std::uint64_t n,std::uint32_t b,std::uint64_t m) {
    return std::uint64_t(a)<std::uint64_t(b)+m && std::uint64_t(b)<std::uint64_t(a)+n;
  };
  const auto word_range=[&](std::uint32_t a,std::uint64_t n) {return !(a&3U) && range(a,n);};
  const auto source=request.device>=0x10000000U ? request.device-0x10000000U : request.device;
  if(!device_idle || request.direction!=0U || request.priority>1U ||
      !request.length || request.length>0x1000000U ||
      ((source|request.destination|request.length)&1U) ||
      source>rom.size() || request.length>rom.size()-source ||
      !range(request.destination,request.length) || (ram.size()&3U) ||
      !word_range(request.message,24U) || !word_range(manager,28U) ||
      !word_range(request.stack,0x80U))return false;
  hle::GuestMemory memory(ram,hle::GuestMemory::Layout::native_word_big_endian);
  const auto read=[&](std::uint32_t a) {
    std::uint32_t v=0;
    if(!memory.read_u32(a,v))std::abort(); // every read has a preflight extent
    return v;
  };
  if(read(manager)!=1U)return false;
  const auto thread=read(manager+4U),command=read(manager+8U),event=read(manager+12U),access=read(manager+16U);
  if(!word_range(thread,0x1b0U) || !word_range(request.completion,24U) ||
      !word_range(command,24U) || !word_range(event,24U) || !word_range(access,24U))return false;
  struct Queue {std::uint32_t address,receive,send,valid,first,count,buffer;};
  const auto queue=[&](std::uint32_t a) {return Queue{a,read(a),read(a+4U),read(a+8U),read(a+12U),read(a+16U),read(a+20U)};};
  const std::array queues{queue(command),queue(event),queue(access),queue(request.completion)};
  for(std::size_t i=0;i<queues.size();++i) {
    const auto& q=queues[i];
    if(q.count==0U || q.count>4096U || q.valid>q.count || q.first>=q.count ||
        !word_range(q.buffer,std::uint64_t(q.count)*4U))return false;
    for(std::size_t j=0;j<i;++j)if(overlap(q.address,24U,queues[j].address,24U))return false;
  }
  const auto tail=queues[0].send;
  if(!word_range(tail,8U) || read(tail)!=0U || read(tail+4U)!=UINT32_MAX ||
      queues[0].receive!=thread || queues[0].valid!=0U ||
      read(thread)!=tail || read(thread+8U)!=command ||
      (read(thread+16U)>>16U)!=8U || read(thread+4U)==0U || read(thread+4U)>255U)return false;
  for(std::size_t i=1;i<queues.size();++i)
    if(queues[i].send!=tail || queues[i].receive!=tail)return false;
  if(queues[1].valid!=0U || queues[2].count!=1U || queues[2].valid!=1U ||
      read(queues[2].buffer)!=0U || queues[3].valid!=0U)return false;
  // Reject aliasing before any mutation, including malformed queue buffers.
  struct Region {std::uint32_t address;std::uint64_t size;};
  std::array<Region,13> protected_regions{};
  protected_regions[0]={manager,28U};protected_regions[1]={thread,0x1b0U};
  protected_regions[2]={tail,8U};protected_regions[3]={request.message,24U};
  protected_regions[4]={request.stack,0x80U};
  for(std::size_t i=0;i<queues.size();++i) {
    protected_regions[5U+2U*i]={queues[i].address,24U};
    protected_regions[6U+2U*i]={queues[i].buffer,std::uint64_t(queues[i].count)*4U};
  }
  for(std::size_t i=0;i<protected_regions.size();++i) {
    const auto& a=protected_regions[i];
    if(overlap(request.destination,request.length,a.address,a.size))return false;
    for(std::size_t j=0;j<i;++j) {
      const auto& b=protected_regions[j];
      if(overlap(a.address,a.size,b.address,b.size))return false;
    }
  }
  const auto status=read(request.message)&255U;
  const auto write=[&](std::uint32_t a,std::uint32_t v) {
    if(!memory.write_u32(a,v))std::abort(); // commit cannot fall back partially
  };
  // Preserve osPiStartDma's public descriptor fields, including untouched status.
  write(request.message,(11U<<16U)|(request.priority<<8U)|status);
  write(request.message+4U,request.completion);
  write(request.message+8U,request.destination);
  write(request.message+12U,request.device);
  write(request.message+16U,request.length);
  write(request.message+20U,0U);
  const auto destination=request.destination-base;
  for(std::uint32_t i=0;i<request.length;++i)ram[(destination+i)^3U]=rom[source+i];
  // The original manager sends the OSIoMesg pointer, not a fabricated null.
  // No guest is waiting on this queue; its normal osRecvMesg consumes the entry.
  write(queues[3].buffer+queues[3].first*4U,request.message);
  write(request.completion+8U,1U);
  return true;
}
} // namespace jfg::boot
