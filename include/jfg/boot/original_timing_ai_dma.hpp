#pragma once
// Shared AI FIFO: retained DMA/register semantics with explicit physical clocks.
// Two slots by default, sticky completion interrupt and byte-granular remaining
// length. Fractional sample timing is independent of VI mode and host playback.
// Historical reference receipts used truncated NTSC sample rates; they do not
// qualify this revised timing model or PAL/JP gameplay.
#include "jfg/boot/device_clocks.hpp"
#include <array>
#include <cstdint>
#include <optional>
#include <span>

namespace jfg::boot {
class OriginalTimingAiDma final {
public:
  bool configure_clocks(DeviceClocks clocks) noexcept {
    if (clocks_.valid() || !clocks.valid() || size_) return false;
    clocks_=clocks; return true;
  }
  // Default remains the physical two-slot FIFO. Native playback may retain
  // bounded catch-up PCM after missed host deadlines; original probes never opt in.
  bool native_queue_capacity(unsigned capacity) {
    if(capacity<2U || capacity>queue_.size() || capacity<size_)return false;
    capacity_=capacity;return true;
  }
  [[nodiscard]] std::optional<std::uint32_t> read(std::uint32_t offset, std::uint64_t count) const {
    switch (offset) {
    case 0: return dram_;
    case 4:
      if (!deadline_ || count >= *deadline_) return 0;
      return static_cast<std::uint32_t>((std::uint64_t(queue_[0].length) * (*deadline_ - count)) / queue_[0].duration);
    case 8: return control_;
    case 12: return (size_ ? 0x40000000U : 0U) | (size_ == capacity_ ? 0x80000000U : 0U);
    case 16: return rate_;
    case 20: return bits_;
    default: return std::nullopt;
    }
  }
  bool write(std::uint32_t offset, std::uint32_t value, std::uint64_t count,
             std::size_t ram_size) {
    if (!clocks_.valid()) return false;
    switch (offset) {
    case 0: dram_ = value; return true;
    case 8:
      if (value > 1 || (size_ && value != control_)) return false;
      control_ = value; return true;
    case 12:
      // Write-only acknowledgement; the data bits have no meaning.
      interrupt_ = false; return true;
    case 16:
      if (value > 0x3fffU || (size_ && value != rate_)) return false;
      rate_ = value; return true;
    case 20:
      if (value > 15) return false;
      bits_ = value; return true;
    case 4: break;
    default: return false;
    }
    if (value == 0) return true;
    if (control_ != 1 || bits_ != 15 || rate_ == 0 || size_ == capacity_ ||
        (value & 7U) || value > 0x3fff8U || (dram_ & 7U) ||
        dram_ > ram_size || value > ram_size - dram_) return false;
    // Stereo 16-bit frames consume (DAC_RATE+1) physical video clocks.
    // Keep fractional Count ticks across DMA buffers instead of truncating
    // the sample frequency before scheduling each completion.
    const auto scaled=std::uint64_t(value/4U)*(rate_+1U)*clocks_.count_hz+fraction_;
    const auto duration=scaled/clocks_.video_hz;
    auto start = deadline_.value_or(count);
    // Validate the tail of the expanded native queue, not only the currently
    // playing buffer. With the physical two-slot default this loop is empty.
    for(unsigned i=1;i<size_;++i) {
      if(start>UINT64_MAX-queue_[i].duration)return false;
      start+=queue_[i].duration;
    }
    if (duration == 0 || start > UINT64_MAX - duration) return false;
    fraction_=scaled%clocks_.video_hz;
    queue_[size_++] = {value, duration};
    if (!deadline_) deadline_ = count + duration;
    return true;
  }
  void advance(std::uint64_t count) {
    if (!deadline_ || count < *deadline_) return;
    interrupt_ = true;
    if (--size_) {
      for(unsigned i=0;i<size_;++i)queue_[i]=queue_[i+1U];
      *deadline_ += queue_[0].duration;
    }
    else deadline_.reset();
  }
  [[nodiscard]] bool interrupt() const { return interrupt_; }
  [[nodiscard]] std::optional<std::uint64_t> deadline() const { return deadline_; }
private:
  DeviceClocks clocks_{};
  std::uint64_t fraction_=0;
  struct Buffer { std::uint32_t length = 0; std::uint64_t duration = 0; };
  std::array<Buffer, 4> queue_{};
  std::optional<std::uint64_t> deadline_;
  std::uint32_t dram_ = 0, control_ = 0, rate_ = 0, bits_ = 0;
  unsigned size_ = 0, capacity_ = 2;
  bool interrupt_ = false;
};
} // namespace jfg::boot
