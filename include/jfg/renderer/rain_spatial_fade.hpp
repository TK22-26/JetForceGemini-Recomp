#pragma once
#include <algorithm>
#include "jfg/renderer/game_layout.hpp"
#include <array>
#include <cmath>
#include <cstdint>
#include <span>

namespace jfg::rain {
// Native type-3 black IN wipe only. Values are copied from the completed
// frame's mesh, matrix and viewport, never reconstructed from elapsed time.
// Pixel-center affine shading and source-over composition approximate the
// rasterizer: RDP subpixel coverage, alpha quantization and RGB555 rounding
// remain subject to live comparison.
struct SpatialScissor {
  int left = 0, top = 0, right = 0, bottom = 0;
  bool verified = false; // caller must prove the effective RDP scissor
};
struct SpatialFade {
  struct Vertex { std::int16_t x = 0, y = 0, z = 0; std::uint8_t alpha = 0; };
  std::array<Vertex,10> vertices{};
  SpatialScissor scissor{};
  double x_scale = 1.0, y_scale = 0.0;
  double center_x = 160.0, center_y = 120.0;
  double shift = 0.0;
  bool supported = false;
  bool partially_visible = false;

  std::uint8_t opacity(int x, int y) const noexcept {
    if (!supported) return 255;
    if (x < scissor.left || x >= scissor.right ||
        y < scissor.top || y >= scissor.bottom) return 0;
    // The three triangles of each strip share the same clamped affine
    // alpha plane. This avoids counting the shared triangle edges twice.
    const double vertical = (120.0-(center_y-(double(y)+0.5))/y_scale)/240.0;
    const double horizontal = ((double(x)+0.5-center_x)/x_scale+160.0)/320.0;
    const double left = std::clamp(2.0-horizontal-vertical-shift/320.0,0.0,1.0);
    const double right = std::clamp(horizontal+vertical-shift/320.0,0.0,1.0);
    const double alpha = 1.0-(1.0-left)*(1.0-right);
    return static_cast<std::uint8_t>(std::clamp(std::lround(alpha*255.0),0L,255L));
  }
};

namespace spatial_detail {
class Memory {
  std::span<const std::uint8_t> bytes_;
public:
  explicit Memory(std::span<const std::uint8_t> bytes) noexcept : bytes_(bytes) {}
  bool valid(std::uint32_t address, std::uint32_t count) const noexcept {
    const auto segment = address & 0xE0000000U;
    const auto offset = address & 0x1FFFFFFFU;
    return (segment == 0x80000000U || segment == 0xA0000000U) &&
      (bytes_.size() & 3U) == 0 && offset <= bytes_.size() &&
      count <= bytes_.size()-offset;
  }
  std::uint8_t u8(std::uint32_t a) const noexcept {
    return valid(a,1) ? bytes_[(a&0x1FFFFFFFU)^3U] : 0;
  }
  std::uint16_t u16(std::uint32_t a) const noexcept {
    return static_cast<std::uint16_t>((unsigned(u8(a))<<8U)|u8(a+1U));
  }
  std::uint32_t u32(std::uint32_t a) const noexcept {
    return (std::uint32_t(u16(a))<<16U)|u16(a+2U);
  }
};
}

// Invoke at native8006CC20 entry only, RA8006BE54. dl_cursor_pointer=a0,
// matrix_cursor_pointer=a1. The last two main-list commands are the viewport
// and matrix just emitted by80040D64; validate those exact command identities.
inline SpatialFade capture_spatial_fade(const RendererGameLayout& layout, std::span<const std::uint8_t> bytes,
    std::uint32_t dl_cursor_pointer, std::uint32_t matrix_cursor_pointer,
    std::uint32_t caller_ra, unsigned width, unsigned height,
    SpatialScissor scissor) noexcept {
  using spatial_detail::Memory;
  const Memory m(bytes);
  SpatialFade result;
  if (caller_ra != layout.rain_spatial_return || !width || width>1023U || !height || height>512U ||
      !scissor.verified || scissor.left < 0 || scissor.top < 0 ||
      scissor.right > static_cast<int>(width) || scissor.bottom > static_cast<int>(height) ||
      scissor.left >= scissor.right || scissor.top >= scissor.bottom ||
      !m.valid(layout.fade_type,4) || !m.valid(layout.fade_mode,24) ||
      m.u32(layout.fade_type) != 3U || m.u8(layout.fade_mode) != 0U ||
      m.u32(layout.camera_mode) != 0U || m.u32(layout.camera_number) != 0U ||
      !m.valid(dl_cursor_pointer,4) || !m.valid(matrix_cursor_pointer,4)) return result;
  const auto cursor = m.u32(dl_cursor_pointer);
  const auto matrix_end = m.u32(matrix_cursor_pointer);
  if (cursor < 16U || matrix_end < 64U || !m.valid(cursor-16U,16) ||
      !m.valid(matrix_end-64U,64) || (cursor&7U) || (matrix_end&7U) ||
      m.u32(cursor-16U) != 0x03800010U ||
      m.u32(cursor-8U) != 0x01000040U ||
      (m.u32(cursor-12U)&0x1FFFFFFFU) != ((layout.viewports+0x50U)&0x1FFFFFFFU) ||
      (m.u32(cursor-4U)&0x1FFFFFFFU) != ((matrix_end-64U)&0x1FFFFFFFU))
    return result;
  if (!m.valid(layout.viewports+0x50U,16)) return result;
  std::array<std::int16_t,8> viewport{};
  for (unsigned i=0;i<viewport.size();++i)
    viewport[i]=static_cast<std::int16_t>(m.u16(layout.viewports+0x50U+2U*i));
  if (viewport[0]<=0 || viewport[1]<=0 || viewport[4]<0 || viewport[5]<0 ||
      viewport[4]>static_cast<int>(4U*width) || viewport[5]>static_cast<int>(4U*height) ||
      viewport[2]!=511 || viewport[3]!=0 || viewport[6]!=511 || viewport[7]!=0)
    return result;
  const auto matrix = matrix_end-64U;
  std::array<double,16> projection{};
  // Derive the affine screen transform from the submitted fixed-point matrix
  // and viewport. PAL's 1.4 scale and other dimensions use the same geometry;
  // TV identity is not a substitute for the actual completed frame's state.
  for (unsigned i=0;i<projection.size();++i) {
    const auto bits=(std::uint32_t(m.u16(matrix+2U*i))<<16U)|m.u16(matrix+32U+2U*i);
    projection[i]=double(static_cast<std::int32_t>(bits))/65536.0;
    if (i!=0U && i!=5U && i!=15U && bits!=0U) return result;
  }
  if (projection[0]<=0.0 || projection[5]<=0.0 || projection[15]<=0.0) return result;
  result.x_scale=double(viewport[0])*projection[0]/(4.0*projection[15]);
  result.y_scale=double(viewport[1])*projection[5]/(4.0*projection[15]);
  result.center_x=double(viewport[4])/4.0;
  result.center_y=double(viewport[5])/4.0;
  if (result.x_scale<0.001 || result.x_scale>64.0 || result.y_scale<0.001 || result.y_scale>64.0)
    return {};
  // The original strip model covers the complete clipped frame. Reject a
  // projection whose mesh would expose a new boundary outside this alpha model.
  if (result.center_x-160.0*result.x_scale>double(scissor.left) ||
      result.center_x+160.0*result.x_scale<double(scissor.right) ||
      result.center_y-120.0*result.y_scale>double(scissor.top) ||
      result.center_y+120.0*result.y_scale<double(scissor.bottom)) return {};
  constexpr std::array<std::uint32_t,10> commands{
    0xE7000000U,0,0xB6000000U,0x10000U,0xFCFFFFFFU,0xFFFE793CU,
    0xEF080C0FU,0x00504340U,0xB8000000U,0};
  if (!m.valid(layout.fade_commands,40)) return result;
  for (unsigned i=0;i<commands.size();++i)
    if (m.u32(layout.fade_commands+4U*i)!=commands[i]) return result;
  const auto slot=m.u32(layout.fade_bank);
  if (slot > 1U) return result;
  const auto vp=m.u32(layout.fade_vertices+4U*slot);
  const auto tp=m.u32(layout.fade_triangles+4U*slot);
  if (!m.valid(vp,100) || !m.valid(tp,96)) return result;
  constexpr std::array<std::array<std::uint8_t,3>,6> triangles{{
    {0,1,3},{1,3,4},{1,4,2},{5,7,8},{5,8,6},{6,8,9}}};
  for (unsigned i=0;i<6;++i) {
    const auto p=tp+16U*i;
    if (m.u8(p)!=0x40U) return result;
    for (unsigned j=0;j<3;++j)
      if (m.u8(p+1U+j)!=triangles[i][j]) return result;
    for (unsigned j=4;j<16;++j) if (m.u8(p+j)!=0U) return result;
  }
  constexpr std::array<int,10> initial_x{-160,160,480,-160,160,-160,160,-480,-160,160};
  constexpr std::array<int,10> initial_y{120,120,120,-120,-120,120,120,-120,-120,-120};
  constexpr std::array<unsigned,10> initial_alpha{255,255,0,255,0,0,255,0,255,255};
  const auto first_x=static_cast<std::int16_t>(m.u16(vp));
  const int shift=-160-int(first_x);
  if (shift<0 || shift>640) return result;
  for (unsigned i=0;i<10;++i) {
    const auto p=vp+10U*i;
    const auto x=static_cast<std::int16_t>(m.u16(p));
    const auto y=static_cast<std::int16_t>(m.u16(p+2U));
    const auto z=static_cast<std::int16_t>(m.u16(p+4U));
    const auto a=m.u8(p+9U);
    const int expected_x=initial_x[i]+(i<5U ? -shift : shift);
    if (int(x)!=expected_x || int(y)!=initial_y[i] || z!=-16 ||
        m.u8(p+6U)!=0 || m.u8(p+7U)!=0 || m.u8(p+8U)!=0 ||
        a!=initial_alpha[i]) return {};
    result.vertices[i]={x,y,z,a};
  }
  result.shift=double(shift);
  result.scissor=scissor;
  result.supported=true;
  // The affine sum is monotonic in x/y. The maximum transmission is at
  // u=1, or at the closest point in the rectangular scissor to that value.
  // Sample the center and four corners to conservatively enable only a
  // numerically visible pixel; this may delay a tiny sub-byte reveal.
  const std::array<std::array<int,2>,5> samples{{
    {(scissor.left+scissor.right-1)/2,(scissor.top+scissor.bottom-1)/2},
    {scissor.left,scissor.top},{scissor.right-1,scissor.top},
    {scissor.left,scissor.bottom-1},{scissor.right-1,scissor.bottom-1}}};
  for (const auto& p:samples)
    result.partially_visible |= result.opacity(p[0],p[1])<255U;
  return result;
}

// The ordinary main frame always calls80064E8C at800453A8. With an empty
// debug-text buffer its native output is exactly six commands: setup, full
// framebuffer scissor, and the fixed font-state list. This function validates
// every command and the entire post-scissor nested list. The caller must tie
// end to the pending main list and require mesh_cursor == end+16, admitting
// only the known viewport/matrix commands before the mesh. Text/windows or
// any other intervening list output therefore fail closed.
inline SpatialScissor capture_spatial_scissor(const RendererGameLayout& layout, std::span<const std::uint8_t> bytes,
    std::uint32_t start, std::uint32_t end, std::uint32_t caller_ra,
    bool debug_empty_at_entry, unsigned width, unsigned height) noexcept {
  const spatial_detail::Memory m(bytes);
  if (caller_ra != layout.rain_debug_return || !debug_empty_at_entry ||
      !width || width>1023U || !height || height>512U || (start&7U) ||
      std::uint64_t(start)+48U != end || !m.valid(start,48U)) return {};
  const std::array<std::uint32_t,12> commands{
    0xE7000000U,0U,0xFF100000U|(width-1U),0x01000000U,0xFE000000U,0x02000000U,
    0x06000000U,layout.dp_setup,0xED000000U,((width*4U)<<12U)|(height*4U),
    0x06000000U,layout.font_commands};
  for (unsigned i=0;i<commands.size();++i)
    if (m.u32(start+4U*i)!=commands[i]) return {};
  // Validate the earlier setup list too: no branch or segment mutation can
  // redirect the subsequent explicit scissor/font list.
  constexpr std::array<std::uint32_t,32> setup_state{0xe7000000U,0x0U,0xba001402U,0x0U,0xba001701U,0x800000U,0xba001001U,0x0U,0xba000e02U,0x0U,0xba001102U,0x0U,0xba001301U,0x80000U,0xba000c02U,0x2000U,0xba000903U,0xc00U,0xfcffffffU,0xfffcf87cU,0xba000801U,0x0U,0xb9000002U,0x0U,0xb900031dU,0xf0a4000U,0xba000602U,0x0U,0xe7000000U,0x0U,0xb8000000U,0x0U};
  if (!m.valid(layout.dp_setup,128U)) return {};
  for (unsigned i=0;i<setup_state.size();++i)
    if (m.u32(layout.dp_setup+4U*i)!=setup_state[i]) return {};
  // No scissor, segment changes, or nested calls in this exact list.
  constexpr std::array<std::uint32_t,26> font_state{
    0xE7000000U,0U,0xBA001402U,0U,0xBA001001U,0U,0xBA000E02U,0U,
    0xBA001102U,0U,0xBA001301U,0U,0xBA000C02U,0x2000U,
    0xBA000903U,0xC00U,0xB9000002U,0U,0xB900031DU,0x00504240U,
    0xFB000000U,0xFFFFFFFFU,0xFA000000U,0U,0xB8000000U,0U};
  if (!m.valid(layout.font_commands,104U)) return {};
  for (unsigned i=0;i<font_state.size();++i)
    if (m.u32(layout.font_commands+4U*i)!=font_state[i]) return {};
  return {0,0,static_cast<int>(width),static_cast<int>(height),true};
}
}
