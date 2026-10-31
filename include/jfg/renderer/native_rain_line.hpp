
#pragma once
#include <cstdint>
#include <span>
#include <vector>
#include <utility>

namespace jfg::rain::spatial {
struct LineArguments {
  std::uint32_t buffer = 0, width = 0, height = 0;
  std::int32_t x0 = 0, y0 = 0, x1 = 0, y1 = 0;
  std::uint32_t color = 0;
};
struct StrokePixel {
  std::uint32_t address;
  std::int32_t x, y;
  std::uint16_t before;
};
// Read-only capture before the unchanged native leaf; restore/replay afterwards
// keeps its register effects while applying a spatially transformed source.
class NativeLineStroke {
  std::vector<StrokePixel> pixels_;
  std::uint32_t color_ = 0;
  static std::uint32_t physical(std::uint32_t a) noexcept { return a & 0x1FFFFFFFU; }
  static bool valid(std::span<std::uint8_t> memory, std::uint32_t address,
                    std::uint32_t count) noexcept {
    const auto segment = address & 0xE0000000U, offset = physical(address);
    return (segment == 0x80000000U || segment == 0xA0000000U) &&
      !(memory.size() & 3U) && offset <= memory.size() &&
      count <= memory.size()-offset;
  }
  static std::uint16_t read(std::span<std::uint8_t> memory, std::uint32_t a) noexcept {
    return std::uint16_t((std::uint16_t(memory[physical(a)^3U])<<8U) |
                         memory[physical(a+1U)^3U]);
  }
  static void write(std::span<std::uint8_t> memory, std::uint32_t a,
                    std::uint16_t value) noexcept {
    memory[physical(a)^3U] = std::uint8_t(value>>8U);
    memory[physical(a+1U)^3U] = std::uint8_t(value);
  }
public:
  static std::uint16_t blend(std::uint16_t destination, std::uint32_t source) noexcept {
    const std::uint32_t rb = ((source>>16U)&0xF800U) | ((source>>10U)&0x3EU);
    const std::uint32_t green = (source>>13U)&0x7C0U;
    if (!(source&255U)) return std::uint16_t(rb | green | 1U);
    const auto shift = source&31U;
    const std::uint32_t drb = destination&0xF83EU, dg = destination&0x7C0U;
    return std::uint16_t(((((drb<<shift)-drb+rb)>>shift)&0xF83EU) |
                         ((((dg<<shift)-dg+green)>>shift)&0x7C0U) | 1U);
  }
  bool capture(std::span<std::uint8_t> memory, LineArguments line) {
    pixels_.clear();
    color_ = line.color;
    if (!line.width || line.width>1024U || !line.height || line.height>512U ||
        (line.buffer&1U) || !valid(memory,line.buffer,line.width*line.height*2U))
      return false;
    // Native clipping rejects the entire line if any endpoint is outside.
    if (std::uint32_t(line.x0)>=line.width || std::uint32_t(line.x1)>=line.width ||
        std::uint32_t(line.y0)>=line.height || std::uint32_t(line.y1)>=line.height)
      return true;
    const auto dx = line.x1>=line.x0 ? line.x1-line.x0 : line.x0-line.x1;
    const auto dy = line.y1>=line.y0 ? line.y1-line.y0 : line.y0-line.y1;
    const bool horizontal = dx>dy;
    if ((horizontal && line.x0>=line.x1) || (!horizontal && line.y0>=line.y1)) {
      std::swap(line.x0,line.x1);std::swap(line.y0,line.y1);
    }
    const auto major = horizontal ? dx : dy, minor = horizontal ? dy : dx;
    const auto sign = horizontal ? (line.y1<line.y0 ? -1 : 1)
                                : (line.x1<line.x0 ? -1 : 1);
    std::int32_t error = -(major+1)/2, x = line.x0, y = line.y0;
    pixels_.reserve(std::size_t(major)+1U);
    for (std::int32_t i=0;i<=major;++i) {
      const auto address = line.buffer + 2U*(std::uint32_t(y)*line.width+std::uint32_t(x));
      pixels_.push_back({address,x,y,read(memory,address)});
      error += minor;
      if (horizontal) ++x; else ++y;
      if (error>=0) {error-=major;if(horizontal)y+=sign;else x+=sign;}
    }
    return true;
  }
  const std::vector<StrokePixel>& pixels() const noexcept { return pixels_; }
  template<class Transform>
  void restore_and_draw(std::span<std::uint8_t> memory, Transform&& transform) const {
    for (const auto& pixel:pixels_) write(memory,pixel.address,pixel.before);
    for (const auto& pixel:pixels_) {
      const auto source = (std::uint32_t(transform(pixel.address,pixel.x,pixel.y,color_))&0xFFFFFF00U) |
                          (color_&255U);
      write(memory,pixel.address,blend(read(memory,pixel.address),source));
    }
  }
};
}
