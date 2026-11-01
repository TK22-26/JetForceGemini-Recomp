#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>

namespace jfg {
enum class PcRumbleRequest { start, alter, maximum, stop };

// Host envelope for JFG's high-level rumble requests. The guest routines still
// execute normally; no Controller Pak, save, or guest rumble fields are changed.
// The caller supplies the clock frequency. Native output uses Count ticks;
// duration arguments remain seconds, independent of the selected TV system.
class PcRumbleEffect {
  std::uint64_t started_=0, until_=0, cooldown_=0, last_tick_=0, ticks_per_second_=0;
  std::uint16_t strength_=0;
  bool active_=false;
  static std::uint64_t add(std::uint64_t a,std::uint64_t b) noexcept {
    return a>UINT64_MAX-b?UINT64_MAX:a+b;
  }
  void advance(std::uint64_t tick) noexcept {
    if(tick<last_tick_) {const auto frequency=ticks_per_second_;clear();ticks_per_second_=frequency;}
    last_tick_=tick;
    if(active_ && tick>=until_)active_=false;
    if(active_ && tick>=add(started_,4*ticks_per_second_)) {
      active_=false;strength_=0;cooldown_=add(started_,5*ticks_per_second_);
    }
  }
public:
  void clear() noexcept {*this={};}
  void request(PcRumbleRequest kind,int intensity,float seconds,std::uint64_t tick,
               std::uint64_t ticks_per_second) noexcept {
    if(ticks_per_second==0 || ticks_per_second>UINT64_MAX/5) {clear();return;}
    if(ticks_per_second_!=ticks_per_second) {clear();ticks_per_second_=ticks_per_second;}
    advance(tick);
    if(kind==PcRumbleRequest::stop) {clear();return;}
    if(tick<cooldown_ || !std::isfinite(seconds) || seconds<0.0F)return;
    const auto bounded=std::clamp(intensity,0,100);
    // The N64 effect uses intensity squared * 0.1; 490 is continuous duty.
    const auto strength=static_cast<std::uint16_t>(std::min(65535LL,bounded*bounded*65535LL/4900));
    const auto duration=static_cast<std::uint64_t>(static_cast<double>(std::min(4.0F,seconds))*static_cast<double>(ticks_per_second_));
    if(kind==PcRumbleRequest::start) {
      if(!active_)started_=tick;
      strength_=strength;until_=add(tick,duration);active_=duration!=0;
    } else if(kind==PcRumbleRequest::maximum) {
      if(!active_) {started_=tick;strength_=0;until_=tick;}
      strength_=std::max(strength_,strength);until_=std::max(until_,add(tick,duration));
      active_=until_>tick;
    } else {
      if(intensity!=0)strength_=strength;
      if(seconds!=0.0F) {
        if(!active_)started_=tick;
        until_=add(tick,duration);active_=duration!=0;
      }
    }
  }
  [[nodiscard]] std::uint16_t sample(std::uint64_t tick,int percent=100) noexcept {
    advance(tick);
    return active_?static_cast<std::uint16_t>(unsigned(strength_)*unsigned(std::clamp(percent,0,100))/100U):0;
  }
};

inline std::array<std::uint16_t,4> route_pc_rumble(
    const std::array<std::uint16_t,4>& ports,const std::array<int,4>& devices) noexcept {
  std::array<std::uint16_t,4> result{};
  for(std::size_t p=0;p<ports.size();++p)
    if(devices[p]>=0 && devices[p]<4) {
      auto& value=result[static_cast<std::size_t>(devices[p])];
      value=std::max(value,ports[p]);
    }
  return result;
}
} // namespace jfg
