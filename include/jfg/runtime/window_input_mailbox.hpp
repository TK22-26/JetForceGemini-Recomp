#pragma once
#include <array>
#include <algorithm>
#include <cstddef>
#include <mutex>
namespace jfg {
class WindowInputMailbox {
public:
  struct Motion {int x=0,y=0,wheel=0;bool focus_lost=false;};
  void motion(int x,int y){const std::lock_guard lock(mutex_);motion_.x=std::clamp(motion_.x+std::clamp(x,-4096,4096),-4096,4096);motion_.y=std::clamp(motion_.y+std::clamp(y,-4096,4096),-4096,4096);}
  void wheel(int delta){const std::lock_guard lock(mutex_);motion_.wheel=std::clamp(motion_.wheel+std::clamp(delta,-3840,3840),-3840,3840);}
  Motion take_motion(){const std::lock_guard lock(mutex_);const auto result=motion_;motion_={};return result;}
  void key(std::size_t code, bool down) {
    if (code >= down_.size()) return;
    const std::lock_guard lock(mutex_);
    if (down && !down_[code]) pressed_[code] = true;
    down_[code] = down;
  }
  void lose_focus() {
    const std::lock_guard lock(mutex_);
    motion_={};motion_.focus_lost=true;
    down_.fill(false);
    pressed_.fill(false);
  }
  void close() {
    const std::lock_guard lock(mutex_);
    close_ = true;
  }
  void consume(std::array<bool,256>& down, std::array<bool,256>& pressed, bool& close) {
    const std::lock_guard lock(mutex_);
    down = down_;
    if (motion_.focus_lost) pressed.fill(false);
    for (std::size_t i = 0; i < down.size(); ++i) pressed[i] = pressed[i] || pressed_[i];
    pressed_.fill(false);
    close = close || close_;
  }
private:
  std::mutex mutex_;
  std::array<bool,256> down_{}, pressed_{};
  bool close_ = false;
  Motion motion_{};
};
}
