#include "host_audio_device.hpp"
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
#include "jfg/audio/playback_buffer.hpp"
#include "jfg/runtime/support_log.hpp"
#include "runtime_constants.hpp"
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
namespace jfg::boot::native::detail {
HostAudioDevice::~HostAudioDevice() { close(); }

void HostAudioDevice::set_gameplay_trace(GameplayTrace *trace) noexcept {
  gameplay_trace_ = trace;
}

void HostAudioDevice::frontend_pause(bool paused) noexcept {
  frontend_paused_ = paused;
  latency_recovery_.reset();
  if (device_ != 0U && device_playing_)
    SDL_PauseAudioDevice(device_, paused ? 1 : 0);
}

void HostAudioDevice::set_vi_counter(const std::uint64_t *vi) noexcept {
  capture_vi_ = vi;
}

void HostAudioDevice::renderer_ready() noexcept {
  renderer_ready_ = true;
  update_playback_state();
}

bool HostAudioDevice::configure_capture(const std::string &path) {
  capture_pcm_.open(path, std::ios::binary | std::ios::trunc);
  capture_events_.open(path + ".events.csv",
                       std::ios::binary | std::ios::trunc);
  if (!capture_pcm_ || !capture_events_)
    return false;
  capture_started_ = std::chrono::steady_clock::now();
  capture_events_ << "wall_us,event,queued_bytes,total_queued_bytes,"
                     "consumed_bytes,vi,steady_us\n";
  return true;
}

bool HostAudioDevice::queue(const std::uint8_t *const rdram,
                            std::uint32_t address, const std::uint32_t length,
                            const std::uint32_t dac_rate, const std::uint32_t video_clock) {
  address &= 0x00FFFFFFU;
  if (rdram == nullptr || length == 0U || (length & 3U) != 0U ||
      address > kRdramSize || length > kRdramSize - address ||
      dac_rate == UINT32_MAX || video_clock == 0U)
    return false;
  const std::uint32_t frequency = video_clock / (dac_rate + 1U);
  if (frequency < 8000U || frequency > 96000U ||
      (!initialized_ && !initialize(frequency)) || frequency_ != frequency)
    return false;

  refresh_volume(frequency);
  update_metrics();
  converted_.resize(length);
  for (std::uint32_t offset = 0U; offset < length; offset += 2U) {
    const std::uint16_t sample = static_cast<std::uint16_t>(
        (static_cast<std::uint16_t>(rdram[(address + offset) ^ 3U]) << 8U) |
        rdram[(address + offset + 1U) ^ 3U]);
    converted_[offset] = static_cast<std::uint8_t>(sample);
    converted_[offset + 1U] = static_cast<std::uint8_t>(sample >> 8U);
  }
  if (capture_pcm_.is_open()) {
    capture_pcm_.write(reinterpret_cast<const char *>(converted_.data()),
                       static_cast<std::streamsize>(converted_.size()));
    if (!capture_pcm_)
      return false;
  }
  master_volume_.apply(converted_);
  if (device_ != 0U && SDL_QueueAudio(device_, converted_.data(), length) != 0)
    return false;
  recovery_pcm_.append(converted_);
  ++submitted_buffers_;
  queued_bytes_ += length;
  emulated_dma_lengths_.push_back(length);
  update_metrics();
  capture_event("queue");
  update_playback_state();
  return true;
}

void HostAudioDevice::settle_startup_queue() {
  latency_recovery_.reset();
  if (!device_playing_ || device_ == 0U)
    return;
  update_metrics();
  capture_event("anchor-drain-begin");
  while (device_playing_ && current_queued_bytes_ > prebuffer_bytes_) {
    SDL_Delay(1U);
    update_metrics();
    update_playback_state();
  }
  capture_event("anchor-drain-end");
}

void HostAudioDevice::service(unsigned nominal_vi_rate,
                              const bool throttle) {
  if (!initialized_)
    return;
  if (nominal_vi_rate)
    advance_emulated_dma(nominal_vi_rate);
  update_metrics();
  update_playback_state();
  while (throttle && device_playing_ && current_queued_bytes_ > pacing_bytes_) {
    SDL_Delay(1U);
    update_metrics();
    update_playback_state();
  }
  if (!nominal_vi_rate) {
    if (capture_pcm_.is_open())
      capture_pcm_.flush();
    if (capture_events_.is_open())
      capture_events_.flush();
  }
}

bool HostAudioDevice::recover_latency(
    bool eligible, std::chrono::steady_clock::time_point observation) {
  // service()/queue() supplied the same snapshot used by normal demand.
  // Do not add another SDL poll (or move that demand decision) on a healthy
  // queue. Re-query only after pausing for an actual recovery below.
  const auto now = static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::milliseconds>(
          observation.time_since_epoch())
          .count());
  if (!latency_recovery_.observe(
          now, current_queued_bytes_, frequency_, consumed_bytes_,
          eligible && device_ != 0U && device_playing_ && !frontend_paused_))
    return true;
  // SDL serializes its queue API internally. Pause to take a stable snapshot;
  // do not hold SDL_LockAudioDevice across these internally locked calls.
  SDL_PauseAudioDevice(device_, 1);
  update_metrics();
  const auto before = current_queued_bytes_;
  auto replacement = recovery_pcm_.replacement(before);
  if (before <= frequency_ || replacement.empty()) {
    SDL_PauseAudioDevice(device_, 0);
    latency_recovery_.reset();
    return true;
  }
  capture_event("latency-recovery-begin");
  SDL_ClearQueuedAudio(device_);
  if (SDL_QueueAudio(device_, replacement.data(),
                     static_cast<Uint32>(replacement.size())) != 0) {
    // Match the existing queue failure contract; never report dropped audio
    // as consumed or resume an empty device after a failed replacement.
    discarded_bytes_ += before;
    recovery_pcm_.clear();
    device_playing_ = false;
    update_metrics();
    jfg::support_event("audio=latency-recovery-queue-failed");
    return false;
  }
  discarded_bytes_ += before - replacement.size();
  recovery_pcm_.clear();
  recovery_pcm_.append(replacement);
  ++latency_recoveries_;
  latency_recovery_.recovered(now);
  update_metrics();
  capture_event("latency-recovery-end");
  SDL_PauseAudioDevice(device_, 0);
  jfg::support_event(
      "audio=latency-recovery/before_ms=" +
      std::to_string(std::uint64_t{before} * 1000U / (frequency_ * 4U)) +
      "/after_ms=" +
      std::to_string(replacement.size() * 1000U / (frequency_ * 4U)) +
      "/discarded_bytes=" + std::to_string(discarded_bytes_) +
      "/recoveries=" + std::to_string(latency_recoveries_));
  return true;
}

std::uint32_t HostAudioDevice::buffered_bytes() const noexcept {
  return current_queued_bytes_;
}

std::uint64_t HostAudioDevice::discarded_bytes() const noexcept {
  return discarded_bytes_;
}

std::uint64_t HostAudioDevice::latency_recoveries() const noexcept {
  return latency_recoveries_;
}

bool HostAudioDevice::capturing_pcm() const noexcept {
  return capture_pcm_.is_open();
}

void HostAudioDevice::finish_capture() noexcept {
  capture_pcm_.finish();
  capture_events_.finish();
}

void HostAudioDevice::close() noexcept {
  if (device_ != 0U) {
    update_metrics();
    SDL_PauseAudioDevice(device_, 1);
    SDL_CloseAudioDevice(device_);
    device_ = 0U;
  }
  initialized_ = false;
}

bool HostAudioDevice::initialized() const noexcept { return initialized_; }

bool HostAudioDevice::started() const noexcept { return started_; }

std::uint32_t HostAudioDevice::frequency() const noexcept { return frequency_; }

std::uint64_t HostAudioDevice::submitted_buffers() const noexcept {
  return submitted_buffers_;
}

std::uint64_t HostAudioDevice::queued_bytes() const noexcept {
  return queued_bytes_;
}

std::uint64_t HostAudioDevice::consumed_bytes() const noexcept {
  return consumed_bytes_;
}

std::uint64_t HostAudioDevice::underruns() const noexcept { return underruns_; }

std::uint64_t HostAudioDevice::overruns() const noexcept { return overruns_; }

std::uint64_t HostAudioDevice::consumed_milliseconds() const noexcept {
  return frequency_ == 0U ? 0U
                          : consumed_bytes_ * 1000U /
                                (static_cast<std::uint64_t>(frequency_) * 4U);
}

std::uint32_t HostAudioDevice::current_buffer_remaining() const noexcept {
  return emulated_dma_lengths_.empty() ? 0U : emulated_dma_lengths_.front();
}

void HostAudioDevice::refresh_volume(const std::uint32_t frequency) {
  if (!volume_path_checked_) {
    volume_path_checked_ = true;
    wchar_t *path = nullptr;
    std::size_t length = 0;
    if (_wdupenv_s(&path, &length, L"JFG_MASTER_VOLUME_CONFIG") == 0 && path) {
      volume_path_ = std::filesystem::path(path);
      std::free(path);
      volume_file_.start(volume_path_);
    }
  }
  if (volume_path_.empty())
    return;
  const auto now = std::chrono::steady_clock::now();
  if (now < volume_next_read_)
    return;
  volume_next_read_ = now + std::chrono::milliseconds(100);
  // Runs on the existing producer thread, never an SDL audio callback.
  // Missing/partial replacements keep the last accepted preference.
  const auto text = volume_file_.latest();
  if (!text)
    return;
  if (const auto settings = jfg::audio::parse_volume(*text)) {
    master_volume_.configure(*settings, frequency, !volume_received_);
    volume_received_ = true;
  }
}

bool HostAudioDevice::initialize(const std::uint32_t frequency) {
  if (SDL_InitSubSystem(SDL_INIT_AUDIO) != 0)
    return false;
  SDL_AudioSpec desired{};
  desired.freq = static_cast<int>(frequency);
  desired.format = AUDIO_S16SYS;
  desired.channels = 2U;
  desired.samples = 256U;
  SDL_AudioSpec obtained{};
  device_ = SDL_OpenAudioDevice(nullptr, 0, &desired, &obtained, 0);
  if (device_ == 0U || obtained.freq != desired.freq ||
      obtained.format != desired.format ||
      obtained.channels != desired.channels) {
    if (device_ != 0U)
      SDL_CloseAudioDevice(device_);
    device_ = 0U;
    // A missing or mismatched host device is a correctness failure by
    // default so a manual run cannot silently lose audio. Headless soak
    // hosts opt in to a null sink whose consumption follows the emulated
    // AI DMA clock, keeping the simulation deterministic without SDL.
    if (!null_sink_requested())
      return false;
    null_sink_ = true;
  }
  frequency_ = frequency;
  recovery_pcm_.configure(frequency);
  // Give the first renderer/shader work a generous cushion, then keep normal
  // host latency bounded independently of the emulated AI DMA clock.
  prebuffer_bytes_ = frequency_ * 4U / 10U;
  resume_bytes_ = frequency_ * 4U / 10U;
  pacing_bytes_ = frequency_ * 4U / 5U;
  overrun_bytes_ = frequency_ * 4U * 2U;
  initialized_ = true;
  return true;
}

bool HostAudioDevice::null_sink_requested() noexcept {
  char *value = nullptr;
  std::size_t length = 0U;
  if (_dupenv_s(&value, &length, "JFG_PHASE9_NULL_AUDIO") != 0 ||
      value == nullptr)
    return false;
  const bool requested = value[0] == '1' && value[1] == '\0';
  std::free(value);
  return requested;
}

void HostAudioDevice::update_metrics() noexcept {
  if (device_ == 0U) {
    if (!null_sink_)
      return;
    std::uint64_t remaining = 0U;
    for (const std::uint32_t length : emulated_dma_lengths_)
      remaining += length;
    current_queued_bytes_ = static_cast<std::uint32_t>(
        (std::min)(remaining, std::uint64_t{UINT32_MAX}));
    consumed_bytes_ = queued_bytes_ >= current_queued_bytes_
                          ? queued_bytes_ - current_queued_bytes_
                          : 0U;
    return;
  }
  current_queued_bytes_ = SDL_GetQueuedAudioSize(device_);
  const auto retained = queued_bytes_ - discarded_bytes_;
  consumed_bytes_ =
      retained >= current_queued_bytes_ ? retained - current_queued_bytes_ : 0U;
  if (device_playing_ && current_queued_bytes_ == 0U) {
    if (!empty_episode_) {
      ++underruns_;
      empty_episode_ = true;
      capture_event("underrun");
    }
  } else if (current_queued_bytes_ != 0U) {
    empty_episode_ = false;
  }
  if (current_queued_bytes_ > overrun_bytes_) {
    if (!overrun_episode_) {
      ++overruns_;
      overrun_episode_ = true;
    }
  } else {
    overrun_episode_ = false;
  }
}

void HostAudioDevice::update_playback_state() noexcept {
  if (device_ == 0U) {
    if (null_sink_ && !started_ && current_queued_bytes_ >= prebuffer_bytes_)
      started_ = true;
    return;
  }
  if (!started_ && !renderer_ready_)
    return;
  switch (jfg::audio::playback_buffer_action(started_, device_playing_,
                                             current_queued_bytes_,
                                             prebuffer_bytes_, resume_bytes_)) {
  case jfg::audio::PlaybackBufferAction::start:
    SDL_PauseAudioDevice(device_, 0);
    started_ = true;
    device_playing_ = true;
    empty_episode_ = false;
    capture_event("start");
    break;
  case jfg::audio::PlaybackBufferAction::pause_empty:
    SDL_PauseAudioDevice(device_, 1);
    device_playing_ = false;
    capture_event("pause-empty");
    break;
  case jfg::audio::PlaybackBufferAction::resume:
    SDL_PauseAudioDevice(device_, 0);
    device_playing_ = true;
    empty_episode_ = false;
    capture_event("resume");
    break;
  case jfg::audio::PlaybackBufferAction::none:
    break;
  }
}

void HostAudioDevice::capture_event(const char *event) noexcept {
  if (gameplay_trace_ != nullptr && *gameplay_trace_) {
    std::array<char, 48> name{};
    (void)std::snprintf(name.data(), name.size(), "audio-%s", event);
    gameplay_trace_->event(name.data(), {current_queued_bytes_, queued_bytes_,
                                         consumed_bytes_, frequency_,
                                         device_playing_ ? 1U : 0U});
  }
  if (!capture_events_.is_open())
    return;
  const auto wall_us = std::chrono::duration_cast<std::chrono::microseconds>(
                           std::chrono::steady_clock::now() - capture_started_)
                           .count();
  capture_events_ << wall_us << ',' << event << ',' << current_queued_bytes_
                  << ',' << queued_bytes_ << ',' << consumed_bytes_ << ','
                  << (capture_vi_ ? *capture_vi_ : 0U) << ','
                  << std::chrono::duration_cast<std::chrono::microseconds>(
                         std::chrono::steady_clock::now().time_since_epoch())
                         .count()
                  << '\n';
}

void HostAudioDevice::advance_emulated_dma(unsigned nominal_vi_rate) noexcept {
  std::uint64_t bytes = jfg::audio::nominal_vi_audio_bytes(
      frequency_,nominal_vi_rate,emulated_byte_accumulator_);
  while (bytes != 0U && !emulated_dma_lengths_.empty()) {
    std::uint32_t &remaining = emulated_dma_lengths_.front();
    if (bytes < remaining) {
      remaining -= static_cast<std::uint32_t>(bytes);
      bytes = 0U;
    } else {
      bytes -= remaining;
      emulated_dma_lengths_.pop_front();
    }
  }
}
} // namespace jfg::boot::native::detail
#endif
