#pragma once
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <span>
#include <vector>

namespace jfg::audio {
// Exceptional host latency recovery, independent of emulated AI/game clocks.
// Ordinary playback (~100 ms) does not enter this policy. An eligible device
// must spend a full second above 250 ms, with demonstrable consumption, before
// stale PCM can be discarded. Pauses, startup and host-service gaps re-arm it.
class LatencyRecovery final {
public:
  void reset() noexcept { *this = {}; }
  void recovered(std::uint64_t now_ms) noexcept {
    reset(); not_before_ = now_ms + 5000U;
  }
  [[nodiscard]] bool observe(std::uint64_t now_ms, std::uint32_t queued_bytes,
      std::uint32_t frequency, std::uint64_t consumed_bytes, bool eligible) noexcept {
    if (!eligible || frequency < 8000U || frequency > 96000U) {
      reset(); return false;
    }
    if (!observed_ || frequency != frequency_ || now_ms < last_observation_ ||
        now_ms - last_observation_ > 250U || consumed_bytes < last_consumed_) {
      const auto cooldown = not_before_;
      reset(); observed_ = true; frequency_ = frequency;
      not_before_ = (std::max)(cooldown, now_ms + 1000U);
      last_observation_ = last_progress_ = now_ms;
      last_consumed_ = consumed_bytes;
      return false;
    }
    last_observation_ = now_ms;
    if (consumed_bytes != last_consumed_) last_progress_ = now_ms;
    last_consumed_ = consumed_bytes;
    if (now_ms < not_before_ || queued_bytes <= frequency ||
        now_ms - last_progress_ > 250U) {
      excessive_ = false; return false;
    }
    if (!excessive_) {
      excessive_ = true; high_since_ = now_ms; high_consumed_ = consumed_bytes;
    }
    return now_ms - high_since_ >= 1000U &&
        consumed_bytes - high_consumed_ >= std::uint64_t{frequency} * 2U;
  }
private:
  std::uint64_t not_before_ = 0, last_observation_ = 0, last_progress_ = 0;
  std::uint64_t last_consumed_ = 0, high_since_ = 0, high_consumed_ = 0;
  std::uint32_t frequency_ = 0;
  bool observed_ = false, excessive_ = false;
};

// Bounded post-volume S16 stereo history. The normal queue is never rewritten.
// A recovery keeps the newest 100 ms and crossfades the first 5 ms from the old
// queue head. If a fault exceeds the four-second history, fade in from silence
// instead; never replay unrelated or uninitialized samples.
class RecoveryPcmHistory final {
public:
  void configure(std::uint32_t frequency) {
    frequency_ = frequency >= 8000U && frequency <= 96000U ? frequency : 0U;
    bytes_.resize(std::size_t{frequency_} * 4U * 4U); clear();
  }
  void clear() noexcept { end_ = used_ = 0U; }
  void append(std::span<const std::uint8_t> pcm) noexcept {
    if (bytes_.empty() || pcm.size() % 4U != 0U) return;
    if (pcm.size() > bytes_.size()) pcm = pcm.last(bytes_.size());
    const auto first = (std::min)(pcm.size(), bytes_.size() - end_);
    std::copy_n(pcm.data(), first, bytes_.data() + end_);
    std::copy_n(pcm.data() + first, pcm.size() - first, bytes_.data());
    end_ = (end_ + pcm.size()) % bytes_.size();
    used_ = (std::min)(used_ + pcm.size(), bytes_.size());
  }
  [[nodiscard]] std::vector<std::uint8_t> replacement(std::uint32_t queued_bytes) const {
    const auto keep = std::size_t{frequency_ / 10U} * 4U;
    if (keep == 0U || queued_bytes % 4U != 0U || queued_bytes <= keep || used_ < keep)
      return {};
    std::vector<std::uint8_t> result(keep);
    for (std::size_t n = 0; n < keep; ++n) result[n] = back(keep - n);
    const auto frames = std::size_t{frequency_} * 5U / 1000U;
    const auto denominator = static_cast<std::int32_t>(frames - 1U);
    for (std::size_t frame = 0; frame < frames; ++frame) {
      for (std::size_t channel = 0; channel < 2U; ++channel) {
        const auto offset = frame * 4U + channel * 2U;
        const auto distance = std::size_t{queued_bytes} - offset;
        const auto old_sample = queued_bytes <= used_ ?
            sample(back(distance), back(distance - 1U)) : 0;
        const auto new_sample = sample(result[offset], result[offset + 1U]);
        const auto weight = static_cast<std::int32_t>(frame);
        const auto blended = (old_sample * (denominator - weight) + new_sample * weight) /
            denominator;
        const auto bits = static_cast<std::uint16_t>(blended);
        result[offset] = static_cast<std::uint8_t>(bits);
        result[offset + 1U] = static_cast<std::uint8_t>(bits >> 8U);
      }
    }
    return result;
  }
private:
  [[nodiscard]] std::uint8_t back(std::size_t distance) const noexcept {
    return bytes_[(end_ + bytes_.size() - distance) % bytes_.size()];
  }
  [[nodiscard]] static std::int32_t sample(std::uint8_t lo, std::uint8_t hi) noexcept {
    const auto bits = std::int32_t{lo} | (std::int32_t{hi} << 8U);
    return bits >= 32768 ? bits - 65536 : bits;
  }
  std::vector<std::uint8_t> bytes_;
  std::size_t end_ = 0U, used_ = 0U;
  std::uint32_t frequency_ = 0U;
};
} // namespace jfg::audio
