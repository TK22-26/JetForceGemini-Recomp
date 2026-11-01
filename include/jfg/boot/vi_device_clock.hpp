#pragma once
#include "jfg/boot/device_clocks.hpp"
#include <cstdint>
#include <optional>

namespace jfg::boot {
// Register-driven scan timing. This owner keeps horizontal fractional phase,
// field parity, the five-field leap pattern and sticky VI interrupt state.
// It does not draw frames, alter guest Count or choose a host presentation FPS.
// Register masks and line/interrupt transitions were reviewed against pinned
// SDK tables and the Ares VI source; console timing parity remains unqualified.
class ViDeviceClock final {
public:
  bool initialize(DeviceClocks clocks, std::uint64_t count, bool pending) noexcept {
    if (initialized_ || !clocks.valid()) return false;
    clocks_=clocks; now_=count; interrupt_=pending; initialized_=true; return true;
  }
  bool advance(std::uint64_t count) noexcept {
    if (!initialized_ || !valid_ || count<now_) return false;
    while (line_end_ && *line_end_<=count) {
      const auto boundary=*line_end_;
      if (!transition(boundary)) return false;
    }
    now_=count; return true;
  }
  bool write(std::uint32_t offset, std::uint32_t value, std::uint64_t count) noexcept {
    if (offset>0x34U || offset%4U || !advance(count)) return false;
    switch(offset) {
    case 0x0c: coincidence_=value&1023U; break;
    case 0x10: interrupt_=false; break;
    case 0x18: vertical_=value&1023U; break;
    case 0x1c: horizontal_=value&4095U; leap_pattern_=(value>>16U)&31U; break;
    case 0x20: leap_[0]=value&4095U; leap_[1]=(value>>16U)&4095U; break;
    default: break; // Other VI registers are retained by the renderer's MMIO image.
    }
    if (!active()) { line_end_.reset(); line_=0; }
    else if (!line_end_ && !schedule(count)) return false;
    return true;
  }
  [[nodiscard]] std::optional<std::uint32_t> current(std::uint64_t count) noexcept {
    if (!advance(count)) return {};
    return (line_<<1U)|field_;
  }
  [[nodiscard]] std::optional<std::uint64_t> deadline() const noexcept {
    if (!initialized_ || !valid_ || !active() || !line_end_) return {};
    // No code or memory observation occurs here: forecast this device alone.
    // Two maximal fields include every reachable parity/coincidence state.
    auto future=*this;
    for (unsigned i=0;i<1026U;++i) {
      const auto boundary=*future.line_end_; const auto before=future.events_;
      if (!future.transition(boundary)) return {};
      if (future.events_!=before) return boundary;
    }
    return {}; // A coincidence outside the programmed field never interrupts.
  }
  [[nodiscard]] bool interrupt() const noexcept { return interrupt_; }
  [[nodiscard]] std::uint64_t events() const noexcept { return events_; }
  [[nodiscard]] DeviceClocks clocks() const noexcept { return clocks_; }
private:
  [[nodiscard]] bool active() const noexcept { return vertical_!=0 && horizontal_!=0; }
  bool schedule(std::uint64_t count) noexcept {
    const std::uint32_t video_ticks=line_==1U ? leap_[(leap_pattern_>>leap_counter_)&1U] : horizontal_+1U;
    // A zero leap duration is representable; the next ordinary line still
    // advances. Retain the remainder instead of rounding each scan line.
    const auto scaled=std::uint64_t(video_ticks)*clocks_.count_hz+fraction_;
    const auto duration=scaled/clocks_.video_hz;
    if (count>UINT64_MAX-duration) { valid_=false; line_end_.reset(); return false; }
    fraction_=scaled%clocks_.video_hz; line_end_=count+duration; return true;
  }
  bool transition(std::uint64_t count) noexcept {
    ++line_;
    if (((line_<<1U)|field_)>=vertical_+1U) {
      line_=0; if (!(vertical_&1U)) field_^=1U;
      leap_counter_=(leap_counter_+1U)%5U;
    }
    bool coincidence=false;
    if ((vertical_&1U) || (coincidence_&1U)) coincidence=line_==(coincidence_>>1U);
    else {
      const auto halfline=(line_<<1U)|field_;
      coincidence=(!field_ && halfline==coincidence_) || (field_ && halfline+1U==coincidence_) ||
          (!field_ && halfline==vertical_ && coincidence_==0U);
    }
    if (coincidence) { interrupt_=true; ++events_; }
    return schedule(count);
  }
  DeviceClocks clocks_{};
  std::optional<std::uint64_t> line_end_;
  std::uint64_t now_=0, fraction_=0, events_=0;
  std::uint32_t vertical_=0, horizontal_=0, coincidence_=0, leap_pattern_=0;
  std::uint32_t leap_[2]{},line_=0,field_=0,leap_counter_=0;
  bool initialized_=false, valid_=true, interrupt_=false;
};
} // namespace jfg::boot
