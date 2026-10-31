#pragma once
#include "jfg/runtime/input_replay.hpp"
#include "jfg/runtime/modern_roll.hpp"
#include <cstdint>
#include <limits>
#include <optional>
#include <span>

namespace jfg::boot {
// Qualification replay of a live poll recording at its recorded VI times.
// Held controls persist between polls; mouse deltas and menu selections are
// consumed once. The existing poll-index replay remains the reference oracle.
class RecordedInputTimeline {
public:
  std::optional<ControllerReplaySample> sample(
      std::uint64_t retrace, std::span<const InputReplayEvent> events) {
    if (started_ && retrace < previous_retrace_) return std::nullopt;
    started_ = true; previous_retrace_ = retrace;
    std::int64_t mouse_x = 0, mouse_y = 0;
    std::uint16_t pressed = 0;
    std::uint8_t roll_pressed = 0, roll_mode = 0;
    // Explicit Modern actions remain valid when uncaptured mouse look uses mode 0.
    const auto roll_context = [](const ControllerReplaySample& sample) {
      return sample.connected && (sample.modern_flags & 0x80U) != 0 &&
          (sample.pc_mode == 0U || sample.pc_mode == 3U || sample.pc_mode == 5U);
    };
    const auto roll_intent = [&](const ControllerReplaySample& sample) -> std::uint8_t {
      if (!roll_context(sample)) return 0;
      const auto flags = sample.modern_flags & kModernRollFlags;
      return flags == kModernRollFlags ? 0 : static_cast<std::uint8_t>(flags);
    };
    std::uint8_t menu_kind = 0, menu_target = 0;
    while (next_ < events.size() && events[next_].first_retrace <= retrace) {
      const auto& event = events[next_++];
      // Live recorder samples occupy exactly one VI interval. Reject scripted
      // held ranges, whose look fields may represent repeated rate inputs.
      if (event.end_retrace-event.first_retrace != 1U) return std::nullopt;
      // Recorded roll intent is an action, so a short pulse must survive a
      // skipped poll just like a native button press. A different direction or
      // source lifetime cannot be merged into one held-action sample safely.
      if (roll_pressed != 0 && (!roll_context(event.sample) || event.sample.pc_mode != roll_mode ||
          (event.sample.modern_flags & kModernRollFlags) == kModernRollFlags))
        return std::nullopt;
      const auto before_roll = roll_context(held_) && held_.pc_mode == event.sample.pc_mode
          ? roll_intent(held_) : 0;
      const auto new_roll = static_cast<std::uint8_t>(roll_intent(event.sample) & ~before_roll);
      if (new_roll != 0) {
        roll_pressed |= new_roll;
        roll_mode = event.sample.pc_mode;
        if (roll_pressed == kModernRollFlags) return std::nullopt;
      }
      pressed |= static_cast<std::uint16_t>(event.sample.buttons & ~held_.buttons);
      held_ = event.sample;
      if (held_.pc_mode == 3U) { mouse_x += held_.look_x; mouse_y += held_.look_y; }
      if (held_.menu_target != 0U) {
        if (menu_target != 0U && (menu_kind != held_.menu_kind || menu_target != held_.menu_target))
          return std::nullopt; // Cannot silently merge two different menu clicks.
        menu_kind = held_.menu_kind; menu_target = held_.menu_target;
      }
    }
    auto result = held_;
    // Preserve a short press released between consumer polls for one sample.
    // This matches the edge mailbox used for physical mouse/key input.
    result.buttons |= pressed;
    if (roll_pressed != 0) {
      const auto output_roll = static_cast<std::uint8_t>(roll_intent(result) | roll_pressed);
      if (output_roll == kModernRollFlags) return std::nullopt;
      result.modern_flags = static_cast<std::uint8_t>(
          (result.modern_flags & ~kModernRollFlags) | output_roll);
    }
    result.menu_kind = menu_kind; result.menu_target = menu_target;
    if (result.pc_mode == 3U) {
      if (mouse_x < INT16_MIN || mouse_x > INT16_MAX || mouse_y < INT16_MIN || mouse_y > INT16_MAX)
        return std::nullopt; // A stalled consumer must not silently clip motion.
      result.look_x = static_cast<std::int16_t>(mouse_x);
      result.look_y = static_cast<std::int16_t>(mouse_y);
    }
    return result;
  }
private:
  ControllerReplaySample held_{};
  std::size_t next_ = 0;
  std::uint64_t previous_retrace_ = 0;
  bool started_ = false;
};
} // namespace jfg::boot
