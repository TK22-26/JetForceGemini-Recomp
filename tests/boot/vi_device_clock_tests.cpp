#include "jfg/boot/vi_device_clock.hpp"
#include <cstdlib>
#include <iostream>
using namespace jfg::boot;
static void check(bool ok,const char* text) { if(!ok){std::cerr<<text<<'\n';std::exit(1);} }
static ViDeviceClock configured(DeviceClocks clocks, unsigned vertical,unsigned hsync,unsigned leap) {
  ViDeviceClock vi;check(vi.initialize(clocks,0,false),"initialize clocks");
  check(!vi.deadline(),"inactive VI has no invented retraces");
  check(vi.write(0x0c,2,0)&&vi.write(0x20,leap,0)&&vi.write(0x1c,hsync,0)&&vi.write(0x18,vertical,0),"program VI");
  return vi;
}
int main() {
  check(clock_milliseconds(kNtscDeviceClocks.count_hz,kNtscDeviceClocks.count_hz)==1000U,
        "NTSC Count owns one-second duration");
  check(clock_milliseconds(kPalDeviceClocks.count_hz,kPalDeviceClocks.count_hz)==1000U,
        "PAL Count owns the same one-second duration");
  check(clock_milliseconds(50,50)==1000U&&clock_milliseconds(60,60)==1000U,
        "historical nominal clocks require their own frequency");
  check(clock_milliseconds(46874999U,46875000U)==999U&&clock_milliseconds(46875001U,46875000U)==1000U,
        "millisecond conversion floors exact Count boundaries");
  constexpr auto maximum=(std::numeric_limits<std::uint64_t>::max)();
  check(clock_milliseconds(maximum,1000U)==maximum,
        "quotient/remainder supports long captures without multiplication overflow");
  check(!clock_milliseconds(maximum,1U)&&!clock_milliseconds(1U,0U)&&!clock_milliseconds(1U,1000000001U),
        "invalid clocks and unrepresentable time fail closed");
  ViDeviceClock absent;check(!absent.current(0)&&!absent.write(0x18,525,0),"missing clocks reject use");
  auto ntsc=configured(kNtscDeviceClocks,525,3093,0x0c150c15);
  const auto first=*ntsc.deadline();check(first==2979,"first coincidence uses physical line clock");
  check(ntsc.advance(first-1)&&!ntsc.interrupt(),"interrupt cannot arrive early");
  check(ntsc.current(first)==2U&&ntsc.interrupt(),"current line and interrupt share one phase");
  check(ntsc.write(0x10,0,first)&&!ntsc.interrupt(),"write current acknowledges interrupt");
  std::uint64_t last=first;
  for(unsigned i=0;i<100;++i) {last=*ntsc.deadline();check(ntsc.advance(last),"advance NTSC");check(ntsc.write(0x10,0,last),"ack NTSC");}
  // 263 lines/field; line 1 replaces 3094 clocks with the 3093-clock leap.
  check(last==(3094ULL+100ULL*813721ULL)*46875000ULL/48681812ULL,"fraction carries across one hundred fields");
  auto pal=configured(kPalDeviceClocks,625,(21U<<16U)|3177U,0x0c6f0c6e);
  last=*pal.deadline();check(pal.advance(last),"first PAL coincidence");
  for(unsigned i=0;i<5;++i){last=*pal.deadline();check(pal.advance(last),"PAL leap cycle");}
  // Pattern 10101 selects three 3183 and two 3182 clocks over five fields.
  check(last==(3178ULL+5ULL*312ULL*3178ULL+3ULL*3183ULL+2ULL*3182ULL)*46875000ULL/49656530ULL,"PAL five-field leap pattern");
  check(pal.current(last)==2U,"PAL current line follows PAL clock");
  check(pal.write(0x0c,1000,last)&&!pal.deadline(),"unreachable coincidence has no synthetic interrupt");
  check(pal.write(0x18,0,last)&&pal.current(last)==0U&&!pal.deadline(),"disabled VI stops scan clock");
  check(!pal.advance(last-1),"backwards Count is rejected");
  auto interlaced=configured(kNtscDeviceClocks,524,3093,0x0c150c15);
  auto at=*interlaced.deadline();check(interlaced.advance(at)&&interlaced.current(at)==2U,"first interlaced field");
  at=*interlaced.deadline();check(interlaced.advance(at)&&interlaced.current(at)==1U,"second interlaced coincidence uses field parity");
  check(interlaced.write(0x18,625,at)&&interlaced.write(0x1c,(21U<<16U)|3177U,at),"mode change retains device owner");
  check(interlaced.deadline().has_value(),"mode change reschedules a future coincidence");
  std::cout<<"shared VI clocks passed\n";
}
