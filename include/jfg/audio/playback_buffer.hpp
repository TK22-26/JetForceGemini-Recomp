#pragma once
#include <cstdint>

namespace jfg::audio {
enum class PlaybackBufferAction { none, start, pause_empty, resume };

// Fractional bytes carry between VIs: both 50 Hz and 60 Hz consume exactly
// one second of stereo 16-bit PCM per second. Zero/unknown clocks do not advance.
[[nodiscard]] constexpr std::uint64_t nominal_vi_audio_bytes(
    std::uint32_t frequency,unsigned vi_rate,std::uint64_t& remainder) noexcept {
  if(vi_rate!=50U && vi_rate!=60U)return 0U;
  remainder+=std::uint64_t(frequency)*4U;
  const auto bytes=remainder/vi_rate;remainder%=vi_rate;return bytes;
}

// Initial priming and recovery after a real underrun need a cushion. A low
// queue that still contains audio must keep playing: pausing early creates a
// silent gap even when the producer replenishes it before it would run dry.
[[nodiscard]] constexpr PlaybackBufferAction playback_buffer_action(
    bool started, bool playing, std::uint32_t queued_bytes,
    std::uint32_t prebuffer_bytes, std::uint32_t resume_bytes) noexcept {
  if (!started)
    return queued_bytes >= prebuffer_bytes ? PlaybackBufferAction::start
                                          : PlaybackBufferAction::none;
  if (playing)
    return queued_bytes == 0U ? PlaybackBufferAction::pause_empty
                             : PlaybackBufferAction::none;
  return queued_bytes >= resume_bytes ? PlaybackBufferAction::resume
                                      : PlaybackBufferAction::none;
}
} // namespace jfg::audio
