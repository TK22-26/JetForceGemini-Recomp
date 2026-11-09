#pragma once
#include <cstdint>
namespace jfg {
// A repeated frontend object has one allocation but 41 independent key poses.
// Native loop index supplies identity only inside the qualified draw caller.
class KeyboardPresentationScope {
 public:
  static constexpr std::uint32_t inactive = UINT32_MAX;
  KeyboardPresentationScope(std::uint32_t& current, bool draw_object,
      bool qualified_caller, std::uint32_t mode, std::uint32_t object,
      std::uint32_t index) noexcept : current_(current), previous_(current) {
    if (draw_object)
      current_ = qualified_caller && mode == 24U && object == 52U && index < 41U
          ? index : inactive;
  }
  ~KeyboardPresentationScope() { current_ = previous_; }
  KeyboardPresentationScope(const KeyboardPresentationScope&) = delete;
  KeyboardPresentationScope& operator=(const KeyboardPresentationScope&) = delete;
 private:
  std::uint32_t& current_;
  std::uint32_t previous_;
};
}
