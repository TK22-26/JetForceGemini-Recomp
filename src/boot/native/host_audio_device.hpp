#pragma once
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
#include "jfg/audio/latency_recovery.hpp"
#include "jfg/audio/master_volume.hpp"
#include "jfg/boot/gameplay_trace.hpp"
#include "jfg/runtime/async_diagnostic_file.hpp"
#include "jfg/runtime/async_volume_file.hpp"
#include <SDL.h>
#include <chrono>
#include <cstdint>
#include <deque>
#include <filesystem>
#include <string>
#include <vector>
namespace jfg::boot::native::detail {
class HostAudioDevice final {
public:
  HostAudioDevice() = default;
  ~HostAudioDevice();
  HostAudioDevice(const HostAudioDevice &) = delete;
  HostAudioDevice &operator=(const HostAudioDevice &) = delete;

  void set_gameplay_trace(GameplayTrace *trace) noexcept;
  void frontend_pause(bool paused) noexcept;
  void set_vi_counter(const std::uint64_t *vi) noexcept;
  void renderer_ready() noexcept;

  bool configure_capture(const std::string &path);

  bool queue(const std::uint8_t *const rdram, std::uint32_t address,
             const std::uint32_t length, const std::uint32_t dac_rate);

  // Shader startup may accumulate more than the configured priming cushion.
  // Establish the wall clock only after that excess has played, so startup
  // work cannot permanently choose a larger audio/video phase offset.
  void settle_startup_queue();

  void service(const bool advance_emulated_clock, const bool throttle);

  // Called after submissions are drained, never from an SDL callback. This
  // changes only the host queue; guest DMA completion and VI pacing stay
  // intact.
  bool recover_latency(bool eligible,
                       std::chrono::steady_clock::time_point observation =
                           std::chrono::steady_clock::now());
  [[nodiscard]] std::uint32_t buffered_bytes() const noexcept;
  [[nodiscard]] std::uint64_t discarded_bytes() const noexcept;
  [[nodiscard]] std::uint64_t latency_recoveries() const noexcept;

  [[nodiscard]] bool capturing_pcm() const noexcept;
  void finish_capture() noexcept;

  void close() noexcept;

  [[nodiscard]] bool initialized() const noexcept;
  [[nodiscard]] bool started() const noexcept;
  [[nodiscard]] std::uint32_t frequency() const noexcept;
  [[nodiscard]] std::uint64_t submitted_buffers() const noexcept;
  [[nodiscard]] std::uint64_t queued_bytes() const noexcept;
  [[nodiscard]] std::uint64_t consumed_bytes() const noexcept;
  [[nodiscard]] std::uint64_t underruns() const noexcept;
  [[nodiscard]] std::uint64_t overruns() const noexcept;
  [[nodiscard]] std::uint64_t consumed_milliseconds() const noexcept;
  [[nodiscard]] std::uint32_t current_buffer_remaining() const noexcept;

private:
  void refresh_volume(const std::uint32_t frequency);

  bool initialize(const std::uint32_t frequency);

  [[nodiscard]] static bool null_sink_requested() noexcept;

  void update_metrics() noexcept;

  void update_playback_state() noexcept;

  void capture_event(const char *event) noexcept;

  void advance_emulated_dma() noexcept;

  GameplayTrace *gameplay_trace_ = nullptr;
  const std::uint64_t *capture_vi_ = nullptr;
  SDL_AudioDeviceID device_ = 0U;
  jfg::audio::MasterVolume master_volume_;
  jfg::audio::LatencyRecovery latency_recovery_;
  jfg::audio::RecoveryPcmHistory recovery_pcm_;
  std::uint64_t discarded_bytes_ = 0U, latency_recoveries_ = 0U;
  bool frontend_paused_ = false;
  std::filesystem::path volume_path_;
  jfg::AsyncVolumeFile volume_file_;
  std::chrono::steady_clock::time_point volume_next_read_{};
  bool volume_path_checked_ = false, volume_received_ = false;
  std::vector<std::uint8_t> converted_;
  jfg::AsyncDiagnosticFile capture_pcm_;
  jfg::AsyncDiagnosticFile capture_events_;
  std::chrono::steady_clock::time_point capture_started_{};
  std::deque<std::uint32_t> emulated_dma_lengths_;
  std::uint64_t emulated_byte_accumulator_ = 0U;
  std::uint32_t frequency_ = 0U;
  std::uint32_t prebuffer_bytes_ = 0U;
  std::uint32_t resume_bytes_ = 0U;
  std::uint32_t pacing_bytes_ = 0U;
  std::uint32_t overrun_bytes_ = 0U;
  std::uint32_t current_queued_bytes_ = 0U;
  bool renderer_ready_ = false;
  std::uint64_t submitted_buffers_ = 0U;
  std::uint64_t queued_bytes_ = 0U;
  std::uint64_t consumed_bytes_ = 0U;
  std::uint64_t underruns_ = 0U;
  std::uint64_t overruns_ = 0U;
  bool initialized_ = false;
  bool started_ = false;
  bool device_playing_ = false;
  bool empty_episode_ = false;
  bool overrun_episode_ = false;
  bool null_sink_ = false;
};
} // namespace jfg::boot::native::detail
#endif
