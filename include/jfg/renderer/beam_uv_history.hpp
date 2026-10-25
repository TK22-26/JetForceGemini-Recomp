#pragma once
#include <array>
#include <cmath>
#include <cstdint>
#include <map>
#include <span>
#include <vector>
namespace jfg {
struct BeamUvSample {
  // Actor lifetime/control/shape/camera/logical vertex plus DMA triangle corner.
  // The corner is essential: one logical beam vertex has several UV seams.
  std::array<std::uint64_t,7> key{};
  std::array<float,2> uv{};
  bool geometry_matched=false;
};
class BeamUvHistory {
  struct Entry { BeamUvSample sample; bool conflict=false; };
  std::map<std::array<std::uint64_t,7>,Entry> previous_;
  std::uint64_t tick_=0;
  bool have_tick_=false;
  static bool valid(const BeamUvSample& s) {
    return s.key[0] && s.key[3] && s.key[4]==0x4245414dU && s.key[6] &&
      std::isfinite(s.uv[0]) && std::isfinite(s.uv[1]);
  }
public:
  void clear() { previous_.clear();have_tick_=false; }
  std::vector<std::array<float,2>> record(std::span<const BeamUvSample> samples,
                                         std::uint64_t tick,bool continuous) {
    std::vector<std::array<float,2>> result(samples.size());
    if(have_tick_ && tick==tick_)return result;
    const bool adjacent=continuous && have_tick_ && tick>tick_ && tick-tick_<=6;
    std::map<std::array<std::uint64_t,7>,Entry> current;
    for(const auto& s:samples)if(valid(s)) {
      const auto [it,inserted]=current.emplace(s.key,Entry{s});
      if(!inserted && it->second.sample.uv!=s.uv)it->second.conflict=true;
    }
    for(std::size_t i=0;i<samples.size() && adjacent;++i) {
      const auto& s=samples[i];if(!s.geometry_matched)continue;
      const auto now=current.find(s.key),old=previous_.find(s.key);
      if(now==current.end() || old==previous_.end() || now->second.conflict ||
         old->second.conflict || s.uv[0]!=old->second.sample.uv[0])continue;
      // US beamScroll (0x04C0096C) adds its phase only to T, masking it
      // with 0x3ff in s10.5 coordinates: exactly a 32-texel cycle.
      result[i][1]=std::remainder(s.uv[1]-old->second.sample.uv[1],32.0F);
    }
    previous_=std::move(current);tick_=tick;have_tick_=true;
    return result;
  }
};
}
