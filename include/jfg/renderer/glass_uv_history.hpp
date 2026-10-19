#pragma once
#include <array>
#include <cmath>
#include <cstdint>
#include <map>
#include <span>
#include <vector>

namespace jfg {
struct GlassUvSample {
  std::array<std::uint64_t,5> key{};
  std::array<float,2> uv{},period{};
};
// Intact pane UVs are camera-dependent. History is owned by the pane lifetime,
// camera and original quad vertex, never by transient RT64 vertex numbering.
class GlassUvHistory {
  struct Entry { GlassUvSample sample; bool conflict=false; };
  std::map<std::array<std::uint64_t,5>,Entry> previous_;
  std::uint64_t tick_=0;
  bool have_tick_=false;
  static bool valid(const GlassUvSample& s) {
    if(!s.key[0] || !s.key[3])return false;
    for(unsigned c=0;c<2;++c)
      if(!std::isfinite(s.uv[c]) || !std::isfinite(s.period[c]) ||
         s.period[c]<=0 || s.period[c]>256)return false;
    return true;
  }
public:
  void clear() {previous_.clear();have_tick_=false;}
  std::vector<std::array<float,2>> record(std::span<const GlassUvSample> samples,
                                        std::uint64_t tick) {
    std::vector<std::array<float,2>> result(samples.size());
    if(have_tick_ && tick==tick_)return result;
    const bool contiguous=have_tick_ && tick>tick_ && tick-tick_<=6U;
    std::map<std::array<std::uint64_t,5>,Entry> current;
    for(const auto& s:samples) if(valid(s)) {
      const auto [it,inserted]=current.emplace(s.key,Entry{s});
      if(!inserted && (it->second.sample.uv!=s.uv ||
                     it->second.sample.period!=s.period))it->second.conflict=true;
    }
    for(std::size_t i=0;i<samples.size() && contiguous;++i) {
      const auto& s=samples[i];
      const auto now=current.find(s.key),old=previous_.find(s.key);
      if(now==current.end() || old==previous_.end() || now->second.conflict ||
         old->second.conflict || old->second.sample.period!=s.period)continue;
      for(unsigned c=0;c<2;++c)
        result[i][c]=std::remainder(s.uv[c]-old->second.sample.uv[c],s.period[c]);
    }
    previous_=std::move(current);tick_=tick;have_tick_=true;
    return result;
  }
};
}
