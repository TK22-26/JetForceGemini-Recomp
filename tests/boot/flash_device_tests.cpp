#include "jfg/boot/flash_device.hpp"
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <source_location>
static void check(bool ok,std::source_location at=std::source_location::current()) {
  if(!ok){std::fprintf(stderr,"production FlashRAM check at %u\n",at.line());std::abort();}
}
int main() {
  jfg::FlashRamStore store;std::array<std::uint8_t,128> page{};
  for(std::size_t i=0;i<384U;++i){page.fill(static_cast<std::uint8_t>(0x10U+i/128U));check(store.stage_write(page).ok()&&store.begin_program(i).ok()&&store.complete().ok());}
  check(store.begin_erase_page(137U).ok()&&store.complete().ok());
  jfg::boot::FlashDevice device;check(device.bind(store,jfg::boot::FlashModel::mx29l1100,46875000U,1000U));
  std::array<std::uint8_t,256> ram{};ram.fill(0xF0U);std::uint64_t now=1000U;
  check(device.command(0xE1000000U,now));check(device.status()==jfg::boot::FlashDevice::silicon_type);
  check(device.transfer(true,0x08000000U,128U,8U,ram,now));
  check(ram[132U^3U]==0U&&ram[133U^3U]==0xC2U&&ram[135U^3U]==0x1EU);
  check(device.command(0xD2000000U,now)&&device.status()==jfg::boot::FlashDevice::silicon_type);
  check(device.command(0xD2000000U,now)&&(device.status()&255U)==0x8CU);
  check(device.write_status(0U,now));check(!device.write_status(1U,now));
  check(device.command(0xB4000000U,now));check(device.transfer(false,0x08000000U,0U,128U,ram,now));
  ram.fill(0U);check(device.command(0xA5000089U,now));
  check(device.deadline()==165063U&&device.busy()&&(device.status()&3U)==1U);
  check(device.command(0xF0000000U,now+1U));check(device.busy());
  const auto before=store.read(0,jfg::kFlashRamSizeBytes).bytes;
  check(device.advance(*device.deadline()-1U));check(store.read(0,before.size()).bytes==before);
  now=*device.deadline();check(device.advance(now)&&!device.busy()&&device.mutations()==1U);
  check((device.status()&255U)==0x8CU);check(device.command(0xF0000000U,now));
  check(device.transfer(true,0x08000000U+137U*64U,0U,128U,ram,now));
  check(std::all_of(ram.begin(),ram.begin()+128,[](auto byte){return byte==0xF0U;}));
  // Buffer ownership is at DMA time, and programming all ones preserves zeros.
  ram.fill(0xFFU);check(device.command(0xB4000000U,now));check(device.transfer(false,0x08000000U,0U,128U,ram,now));
  check(device.command(0xA5000089U,now));now=*device.deadline();check(device.advance(now));
  const auto programmed=store.read(137U*128U,128U).bytes;check(std::all_of(programmed.begin(),programmed.end(),[](auto byte){return byte==0xF0U;}));
  auto expected=store.read(0,jfg::kFlashRamSizeBytes).bytes;
  check(device.command(0x4B000089U,now));check(device.command(0x78000000U,now));
  check(*device.deadline()==now+3984375U&&(device.status()&3U)==2U);
  check(store.read(0,expected.size()).bytes==expected);
  now=*device.deadline();check(device.advance(now));
  std::fill_n(expected.begin()+16384,16384,std::uint8_t{0xFFU});check(store.read(0,expected.size()).bytes==expected);
  check(!device.command(0x4B000400U,now));check(!device.command(0x78000001U,now));check(!device.command(0x99000000U,now));
  check(device.command(0x3C000000U,now)&&device.command(0x78000000U,now));
  device.interrupt();check(!device.busy()&&store.read(0,expected.size()).bytes==expected);
  check(device.command(0x3C000000U,now)&&device.command(0x78000000U,now));now=*device.deadline();check(device.advance(now));
  const auto erased=store.read(0,jfg::kFlashRamSizeBytes).bytes;check(std::all_of(erased.begin(),erased.end(),[](auto byte){return byte==255U;}));
  check(device.mutations()==4U);check(!device.advance(now-1U));
  check(device.command(0xF0000000U,now));const auto prior_ram=ram;
  check(!device.transfer(true,0x0800FFC0U,0U,256U,ram,now));check(ram==prior_ram);
  check(!device.transfer(false,0x08000000U,0U,128U,ram,now));
  std::puts("production FlashRAM: ID, latched DMA, bitwise programming, command-time start, sector/chip erase, busy deadlines and reset passed");
}
