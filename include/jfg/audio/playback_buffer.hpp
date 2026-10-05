#pragma once
#include <cstdint>

namespace jfg::audio {
enum class PlaybackBufferAction { none, start, pause_empty, resume };

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
