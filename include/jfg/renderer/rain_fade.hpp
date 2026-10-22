#pragma once
#include <cstdint>
#include <initializer_list>
#include <span>
#include <optional>
#include "jfg/renderer/rain_spatial_fade.hpp"
#include "jfg/renderer/native_rain_line.hpp"

namespace jfg::rain {
// Native rain colors are RRGGBBnn: nn is a blend exponent, not alpha.
// Fade the source color before the native weighted blend. The affine identity
// holds before RGB555 quantization. A single stroke differs by at most one
// level in the isolated native harness; repeated rounding can accumulate.
inline constexpr std::uint32_t fade_source(std::uint32_t source,
    std::uint32_t fade_rgb, std::uint8_t alpha) noexcept {
  std::uint32_t result = source & 0xFFU;
  for (unsigned shift : {24U, 16U, 8U}) {
    const auto color = (source >> shift) & 0xFFU;
    const auto fade = (fade_rgb >> shift) & 0xFFU;
    result |= ((color * (255U - alpha) + fade * alpha + 127U) / 255U) << shift;
  }
  return result;
}

struct Fade {
  bool simple_in = false;
  std::uint8_t alpha = 0;
  std::uint32_t rgb = 0;
  std::uint64_t transition = 0;
  SpatialFade spatial{};
};
struct Frame {
  std::uint32_t buffer = 0, bytes = 0;
  Fade fade;
  std::uint32_t width = 0, height = 0;
};
inline constexpr std::uint32_t physical(std::uint32_t address) noexcept {
  return address & 0x1FFFFFFFU;
}
// One main list is being built and one has been submitted for CPU effects.
// Bind/record/seal/submit rather than sampling the next frame's global opacity.
class Tracker {
  struct Pending {
    std::uint32_t base = 0, end = 0, fade_end = 0;
    bool sealed = false;
    std::uint32_t scissor_end = 0;
    SpatialScissor scissor;
    Frame frame;
  } pending_;
  Frame submitted_;
public:
  void invalidate_pending() noexcept { pending_ = {}; }
  void begin(std::uint32_t base, std::uint32_t buffer, std::uint32_t bytes,
             std::uint32_t width = 0, std::uint32_t height = 0) noexcept {
    pending_ = {};
    if (!base || (base & 7U) || !buffer || !bytes) return;
    pending_.base = base;
    pending_.frame.buffer = physical(buffer);
    pending_.frame.bytes = bytes;
    pending_.frame.width = width;
    pending_.frame.height = height;
  }
  void unsupported() noexcept { pending_.frame.fade = {}; }
  void record_scissor(std::uint32_t begin, std::uint32_t end, SpatialScissor scissor) noexcept {
    pending_.scissor = {};
    pending_.scissor_end = 0;
    if (!pending_.base || pending_.sealed || begin < pending_.base ||
        end <= begin || end-pending_.base > 0x20000U || (end&7U) || !scissor.verified) return;
    pending_.scissor = scissor;
    pending_.scissor_end = end;
  }
  SpatialScissor scissor_for_mesh(std::uint32_t cursor) const noexcept {
    return pending_.base && !pending_.sealed && pending_.scissor_end &&
        pending_.frame.width == 320U && pending_.frame.height == 240U &&
        pending_.frame.bytes == 320U*240U*2U &&
        cursor == pending_.scissor_end+16U ? pending_.scissor : SpatialScissor{};
  }
  void record(std::uint32_t begin, std::uint32_t end, Fade fade) noexcept {
    if (!pending_.base || pending_.sealed || begin < pending_.base ||
        end <= begin || end - pending_.base > 0x20000U || (end & 7U)) {
      invalidate_pending();
      return;
    }
    pending_.frame.fade = fade;
    pending_.fade_end = end;
  }
  void seal(std::uint32_t end) noexcept {
    if (!pending_.base || end <= pending_.base || end < pending_.fade_end ||
        end - pending_.base > 0x20000U || (end & 7U)) {
      invalidate_pending();
      return;
    }
    pending_.end = end;
    pending_.sealed = true;
  }
  void submit(std::uint32_t base, std::uint32_t end, std::uint32_t buffer,
              bool main_task) noexcept {
    submitted_ = {};
    if (main_task && pending_.sealed && base == pending_.base &&
        end == pending_.end && physical(buffer) == pending_.frame.buffer)
      submitted_ = pending_.frame;
    invalidate_pending();
  }

  // Known auxiliary tasks render separate images and own separate command lists.
  // They must not discard a valid main frame or the next list under construction.
  void auxiliary(std::uint32_t base, std::uint32_t end, std::uint32_t buffer,
                 std::uint32_t bytes, std::uint32_t main_cursor) noexcept {
    const auto overlaps = [](std::uint32_t a, std::uint32_t an,
                             std::uint32_t b, std::uint32_t bn) {
      return std::uint64_t(a) < std::uint64_t(b)+bn &&
          std::uint64_t(b) < std::uint64_t(a)+an;
    };
    if (!base || end <= base || end-base > 0x20000U || (base & 7U) ||
        (end & 7U) || !buffer || !bytes) {
      submitted_ = {};
      invalidate_pending();
      return;
    }
    if (submitted_.buffer && (overlaps(physical(buffer), bytes,
                                       submitted_.buffer, submitted_.bytes) ||
                              overlaps(physical(base), end-base,
                                       submitted_.buffer, submitted_.bytes)))
      submitted_ = {};
    if (pending_.base) {
      const auto main_end = pending_.sealed ? pending_.end : main_cursor;
      if (main_end <= pending_.base || main_end-pending_.base > 0x20000U ||
          overlaps(physical(base), end-base, physical(pending_.base), main_end-pending_.base) ||
          overlaps(physical(buffer), bytes, physical(pending_.base), main_end-pending_.base))
        invalidate_pending();
    }
  }
  Frame frame(std::uint32_t buffer) const noexcept {
    return submitted_.buffer && physical(buffer) == submitted_.buffer ? submitted_ : Frame{};
  }
};

// Bounded word-swapped guest view; independent of diagnostic logging.
class Memory {
  std::span<std::uint8_t> bytes_;
public:
  explicit Memory(std::span<std::uint8_t> bytes) : bytes_(bytes) {}
  bool valid(std::uint32_t address, std::uint32_t count) const noexcept {
    const auto segment = address & 0xE0000000U;
    const auto offset = physical(address);
    return (segment == 0x80000000U || segment == 0xA0000000U) &&
        (bytes_.size() & 3U) == 0U && offset <= bytes_.size() && count <= bytes_.size() - offset;
  }
  std::uint8_t u8(std::uint32_t address) const noexcept {
    return valid(address, 1U) ? bytes_[physical(address) ^ 3U] : 0U;
  }
  std::uint32_t u32(std::uint32_t address) const noexcept {
    if (!valid(address, 4U)) return 0U;
    return (std::uint32_t(u8(address)) << 24U) | (std::uint32_t(u8(address+1U)) << 16U) |
        (std::uint32_t(u8(address+2U)) << 8U) | u8(address+3U);
  }
  void put32(std::uint32_t address, std::uint32_t value) const noexcept {
    if (!valid(address, 4U)) return;
    for (unsigned i = 0; i < 4U; ++i)
      bytes_[physical(address+i) ^ 3U] = std::uint8_t(value >> (24U-8U*i));
  }
};
struct Call {
  std::uint32_t a0 = 0, a1 = 0, a2 = 0, a3 = 0, sp = 0, ra = 0;
};
struct Runtime {
  Tracker tracker;
  std::uint64_t transition = 0;
  const Frame* post = nullptr;
  bool rain_draw = false;
  bool supported = false;
  unsigned auxiliary_type = 0;
  std::uint64_t spatial_attempts = 0, spatial_accepted = 0;
  std::uint64_t scissor_attempts = 0, scissor_accepted = 0;
  std::uint64_t spatial_lines = 0, spatial_pixels = 0;
};
// Supported US call sites. Restore temporary line arguments and nesting state.
// Native fade state, particle tables and frame history remain intact.
class Dispatch {
  Runtime& runtime_;
  Memory memory_;
  std::span<std::uint8_t> bytes_;
  Call call_;
  std::uint32_t target_;
  Frame frame_;
  const Frame* previous_post_ = nullptr;
  bool previous_rain_ = false, post_scope_ = false, rain_scope_ = false;
  bool patched_ = false, recorded_ = false;
  std::uint32_t color_ = 0, cursor_ = 0;
  Fade fade_;
  unsigned previous_auxiliary_ = 0;
  bool auxiliary_scope_ = false;
  bool scissor_scope_ = false, debug_empty_ = false;
  std::optional<spatial::NativeLineStroke> stroke_;
  std::uint32_t vi_width() const noexcept {
    const auto mode = memory_.u8(0x800FECA8U);
    return mode < 4U ? memory_.u32(0x800A392CU+0x28U*mode) : 0U;
  }
  std::uint32_t vi_height() const noexcept {
    const auto mode = memory_.u8(0x800FECA8U);
    return mode < 4U ? memory_.u32(0x800A3930U+0x28U*mode) : 0U;
  }
  bool simple_in() const noexcept {
    return memory_.u32(0x80102D38U) == 0U && memory_.u8(0x800A67A0U) == 0U;
  }
  std::uint32_t vi_bytes() const noexcept {
    const auto mode = memory_.u8(0x800FECA8U);
    const auto width = mode < 4U ? memory_.u32(0x800A392CU+0x28U*mode) : 0U;
    const auto height = mode < 4U ? memory_.u32(0x800A3930U+0x28U*mode) : 0U;
    return width && width <= 1024U && height && height <= 512U ? width*height*2U : 0U;
  }
public:
  static constexpr bool observes(std::uint32_t target) noexcept {
    switch (target) {
    case 0x80044FACU: case 0x8006B9CCU: case 0x80050E90U:
    case 0x80064E8CU: case 0x8006CC20U:
    case 0x8006BD54U: case 0x8006C124U: case 0x80045A44U:
    case 0x800237D8U: case 0x80023600U: case 0x8004DA10U: case 0x8006B978U:
    case 0x004001BCU: case 0x00200788U: case 0x030006F0U: return true;
    default: return false;
    }
  }
  Dispatch(Runtime& runtime, std::span<std::uint8_t> bytes,
           std::uint32_t target, Call call) noexcept
      : runtime_(runtime), memory_(bytes), bytes_(bytes), call_(call), target_(target) {
    if (target == 0x80044FACU) {
      runtime.supported = memory_.u32(0x80045AB8U) == 0x0C01AE5EU &&
          memory_.u32(0x80045160U) == 0x0C0143A4U &&
          memory_.u32(0x800455A8U) == 0x0C011691U;
      if (!runtime.supported) runtime.tracker = {};
    }
    if (!runtime.supported) return;
    switch (target) {
    case 0x8006B9CCU:
      ++runtime.transition;
      break;
    case 0x80050E90U:
      if (call.a1 != 1U || call.a0 != 0x800FB408U) break;
      runtime.tracker.invalidate_pending();
      if (call.ra == 0x80045168U && call.a2 == memory_.u32(0x800FECB8U)) {
        const auto index = memory_.u32(0x800FD7C0U);
        const auto base = index < 2U ? memory_.u32(0x800FB400U + 4U*index) : 0U;
        const auto frame_bytes = vi_bytes();
        if (frame_bytes && memory_.valid(call.a2, frame_bytes) && memory_.valid(base, 8U) &&
            memory_.u32(call.a0) == base+8U)
          runtime.tracker.begin(base, call.a2, frame_bytes, vi_width(), vi_height());
      }
      break;
    case 0x80064E8CU:
      if (call.ra == 0x800453B0U && call.a0 == 0x800FB408U) {
        cursor_ = memory_.u32(call.a0);
        debug_empty_ = memory_.u32(0x800A6384U) == 0x80100960U;
        scissor_scope_ = true;
        ++runtime.scissor_attempts;
      }
      break;
    case 0x8006CC20U:
      if (call.ra == 0x8006BE54U && call.a0 == 0x800FB408U) {
        ++runtime.spatial_attempts;
        cursor_ = memory_.u32(call.a0);
        fade_.spatial = capture_spatial_fade(bytes, call.a0, call.a1, call.ra,
            vi_width(), vi_height(), runtime.tracker.scissor_for_mesh(cursor_));
        if (fade_.spatial.supported) {
          fade_.transition = runtime.transition;
          recorded_ = true;
          ++runtime.spatial_accepted;
        }
      }
      break;
    case 0x8006BD54U:
      runtime.tracker.unsupported();
      break;
    case 0x8006C124U:
      if (call.ra == 0x8006BE18U && call.a0 == 0x800FB408U && simple_in()) {
        cursor_ = memory_.u32(call.a0);
        fade_ = {true, memory_.u8(0x80102D88U),
            (std::uint32_t(memory_.u8(0x80102D50U)) << 24U) |
            (std::uint32_t(memory_.u8(0x80102D58U)) << 16U) |
            (std::uint32_t(memory_.u8(0x80102D70U)) << 8U), runtime.transition};
        recorded_ = true;
      }
      break;
    case 0x80045A44U:
      if (memory_.u32(0x800A32ACU) != 8U)
        frame_ = runtime.tracker.frame(call.a0);
      previous_post_ = runtime.post;
      post_scope_ = true;
      runtime.post = frame_.buffer && memory_.valid(call.a0, frame_.bytes) ? &frame_ : nullptr;
      break;
    case 0x800237D8U:
      previous_rain_ = runtime.rain_draw;
      rain_scope_ = true;
      runtime.rain_draw = false;
      if (runtime.post && (runtime.post->fade.simple_in || runtime.post->fade.spatial.supported) && call.a1 && call.a1 <= 1024U &&
          call.a2 && call.a2 <= 512U && memory_.valid(call.a0, call.a1*call.a2*2U)) {
        const auto offset = physical(call.a0) - runtime.post->buffer;
        runtime.rain_draw = offset <= runtime.post->bytes &&
            call.a1*call.a2*2U <= runtime.post->bytes-offset;
      }
      break;
    case 0x004001BCU: case 0x00200788U: case 0x030006F0U:
      previous_auxiliary_ = runtime.auxiliary_type;
      auxiliary_scope_ = true;
      runtime.auxiliary_type = target == 0x004001BCU ? 3U : target == 0x00200788U ? 4U : 5U;
      break;
    case 0x80023600U:
      if (runtime.rain_draw && runtime.post && call.sp <= 0xFFFFFFDFU &&
          memory_.valid(call.sp, 0x20U)) {
        color_ = memory_.u32(call.sp+0x1CU);
        const auto& fade = runtime.post->fade;
        if (fade.simple_in) {
          memory_.put32(call.sp+0x1CU, fade_source(color_, fade.rgb, fade.alpha));
          patched_ = true;
        } else if (fade.spatial.supported && runtime.post->width &&
                   call.a1 && call.a1 <= 1024U && call.a2 && call.a2 <= 512U) {
          const auto offset = physical(call.a0)-runtime.post->buffer;
          if (offset <= runtime.post->bytes && call.a1*call.a2*2U <= runtime.post->bytes-offset) {
            try {
              stroke_.emplace();
              if (!stroke_->capture(bytes, spatial::LineArguments{call.a0,call.a1,call.a2,
                  static_cast<std::int32_t>(call.a3),static_cast<std::int32_t>(memory_.u32(call.sp+0x10U)),
                  static_cast<std::int32_t>(memory_.u32(call.sp+0x14U)),
                  static_cast<std::int32_t>(memory_.u32(call.sp+0x18U)),color_})) stroke_.reset();
            } catch (...) { stroke_.reset(); }
          }
        }
        // A rejected line or allocation failure must not bypass the fade
        // with its original bright source after the batch gate was opened.
        if (fade.spatial.supported && !stroke_) {
          memory_.put32(call.sp+0x1CU, color_ & 0xFFU);
          patched_ = true;
        }
      }
      break;
    default: break;
    }
  }
  Dispatch(const Dispatch&) = delete;
  Dispatch& operator=(const Dispatch&) = delete;
  ~Dispatch() {
    if (patched_) memory_.put32(call_.sp+0x1CU, color_);
    if (rain_scope_) runtime_.rain_draw = previous_rain_;
    if (post_scope_) runtime_.post = previous_post_;
    if (auxiliary_scope_) runtime_.auxiliary_type = previous_auxiliary_;
  }
  std::uint64_t finish(std::uint64_t result) noexcept {
    if (!runtime_.supported) return result;
    if (scissor_scope_) {
      const auto end = memory_.u32(call_.a0);
      const auto scissor = capture_spatial_scissor(bytes_, cursor_, end, call_.ra,
          debug_empty_, vi_width(), vi_height());
      runtime_.tracker.record_scissor(cursor_, end, scissor);
      if (scissor.verified) ++runtime_.scissor_accepted;
    }
    if (stroke_ && runtime_.post) {
      const auto& frame = *runtime_.post;
      stroke_->restore_and_draw(bytes_, [&frame](std::uint32_t address, int, int,
                                               std::uint32_t source) noexcept {
        const auto offset = (physical(address)-frame.buffer)/2U;
        return fade_source(source,0U,frame.fade.spatial.opacity(
            static_cast<int>(offset%frame.width),static_cast<int>(offset/frame.width)));
      });
      ++runtime_.spatial_lines;
      runtime_.spatial_pixels += stroke_->pixels().size();
      stroke_.reset();
    }
    if (recorded_) {
      const auto end = memory_.u32(call_.a0);
      if (end > cursor_ && memory_.valid(cursor_, end-cursor_))
        runtime_.tracker.record(cursor_, end, fade_);
      else runtime_.tracker.invalidate_pending();
    }
    if (target_ == 0x80044FACU) runtime_.tracker.seal(memory_.u32(0x800FB408U));
    if (target_ == 0x8004DA10U) {
      const auto type = runtime_.auxiliary_type;
      const auto bytes = type == 3U ? 4096U : vi_bytes();
      if (result == 0U && type >= 3U && type <= 5U && call_.a2 == type && bytes &&
          call_.a1 > call_.a0 && memory_.valid(call_.a0, call_.a1-call_.a0) &&
          memory_.valid(call_.a3, bytes))
        runtime_.tracker.auxiliary(call_.a0, call_.a1, call_.a3, bytes, memory_.u32(0x800FB408U));
      else
        runtime_.tracker.submit(call_.a0, call_.a1, call_.a3,
            result == 0U && call_.ra == 0x80045090U && call_.a2 == 0U);
    }
    if (target_ == 0x8006B978U && call_.ra == 0x80045AC0U && result && runtime_.post) {
      const auto& fade = runtime_.post->fade;
      if (fade.simple_in && fade.alpha < 255U && fade.transition == runtime_.transition &&
          simple_in() && memory_.u32(0x800A6784U)) return 0U;
      if (fade.spatial.supported && fade.spatial.partially_visible &&
          fade.transition == runtime_.transition && memory_.u32(0x80102D38U) == 3U &&
          memory_.u8(0x800A67A0U) == 0U && memory_.u32(0x800A6784U)) return 0U;
    }
    return result;
  }
};
} // namespace jfg::rain
