#pragma once

// Independently measured, explicitly limited corrected-Mupen HLE profile.
// Not hardware timing and not the runtime's default clock. See the private
// VI register sweep and phased SP probe in phase9-os-clock-qualification.md.
#include <cstdint>
#include <optional>

namespace jfg::boot {
enum class ObservedRspTask { jfg_f3ddkr, jfg_audio };

// Caller must identify the qualified original microcode/task class. These
// are effective delays from CPU retirement of the start-register write;
// OS entry/return, interrupt handling and scheduling are separate CPU work.
constexpr std::optional<std::uint64_t> observed_rsp_latency(ObservedRspTask task) {
  switch (task) {
  case ObservedRspTask::jfg_f3ddkr: return 1000U;
  case ObservedRspTask::jfg_audio: return 4000U;
  default: return std::nullopt;
  }
}

// Admit only independently tested configurations. Initial deadline phase,
// mode-change latching and VI_CURRENT are not defined by this period query.
constexpr std::optional<std::uint64_t> observed_vi_period(
    std::uint32_t v_sync, std::uint32_t h_sync) {
  if (h_sync != 3093U && h_sync != 3177U) return std::nullopt;
  switch (v_sync) {
  case 261: case 262: case 525: case 526: case 624: case 625:
    return std::uint64_t(v_sync + 1U) * 1500U;
  default: return std::nullopt;
  }
}
} // namespace jfg::boot
