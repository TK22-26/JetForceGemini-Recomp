#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <span>
#include <vector>

namespace jfg {
// Host time controls only the confirmation gesture, never the guest sequence
// clock. A completion handler must be qualified separately before eligible=true.
class CutsceneSkipHold {
 public:
  bool sample(std::uint64_t scene, bool eligible, bool a_down, bool focused,
              std::uint64_t now_ms, bool reveal_down = false) noexcept {
    const bool any_down = a_down || reveal_down;
    const bool reveal_rising = any_down && !was_any_down_;
    was_any_down_ = any_down;
    const bool rising = a_down && !was_down_;
    was_down_ = a_down;
    if (!focused || !eligible || scene == 0 || scene != scene_) {
      scene_ = scene;
      holding_ = false; visible_ = false; fired_ = false;
      // A button held across a focus/scene handoff cannot confirm a new skip.
      armed_ = !a_down;
      return false;
    }
    if (reveal_rising) { visible_ = true; last_activity_ = now_ms; }
    if (any_down) last_activity_ = now_ms;
    if (!a_down) {
      armed_ = true; holding_ = false;
      if (visible_ && now_ms >= last_activity_ && now_ms-last_activity_ >= 2500)
        visible_ = false;
      return false;
    }
    if (!armed_ || fired_) return false;
    if (rising) {
      visible_ = true; holding_ = true; hold_started_ = now_ms;
    }
    if (!holding_) return false;
    last_activity_ = now_ms;
    if (now_ms >= hold_started_ && now_ms-hold_started_ >= 1000) {
      holding_ = false; fired_ = true; armed_ = false;
      return true;
    }
    return false;
  }
  bool visible() const noexcept { return visible_; }
  float progress(std::uint64_t now_ms) const noexcept {
    if (fired_) return 1.0f;
    if (!holding_ || now_ms < hold_started_) return 0.0f;
    return std::min(1.0f, static_cast<float>(now_ms-hold_started_)/1000.0f);
  }
 private:
  std::uint64_t scene_=0, hold_started_=0, last_activity_=0;
  bool was_any_down_=false, was_down_=false, armed_=false, holding_=false, visible_=false, fired_=false;
};

struct SkipGbiCommand { std::uint32_t w0, w1; };


// Native RDP commands for the progress ring and label; no host overlay or SVG.
// The renderer may supply the blue button and styled label as native textures.
// The caller owns the display-list allocation and restores the original RDP
// state afterward. Coordinates are the game's native color-buffer coordinates.
// This bounded list can also be emitted into a dedicated native HUD sub-list.
inline std::vector<SkipGbiCommand> cutscene_skip_gbi(unsigned width,
                                                   unsigned height,
                                                   float progress,
                                                   bool textured_button = false) {
  std::vector<SkipGbiCommand> out;
  if(width<160||width>1023||height<100||height>1023||!std::isfinite(progress))return out;
  out.reserve(320);
  const int scale=width>=512?2:1;
  const int cx=static_cast<int>(width)-61*scale,cy=static_cast<int>(height)-18*scale;
  const auto cmd=[&](std::uint32_t a,std::uint32_t b){out.push_back({a,b});};
  cmd(0xE7000000U,0);
  cmd(0xED000000U,(width*4U<<12U)|(height*4U));
  cmd(0xBA001402U,0x00300000U);
  cmd(0xB900031DU,0);
  const auto colour=[&](unsigned r,unsigned g,unsigned b) {
    cmd(0xE7000000U,0);
    const auto rgba=static_cast<std::uint32_t>(((r>>3)<<11)|((g>>3)<<6)|((b>>3)<<1)|1);
    cmd(0xF7000000U,(rgba<<16)|rgba);
  };
  const auto rect=[&](int x0,int y0,int x1,int y1) {
    if(x0<0||y0<0||x1>=static_cast<int>(width)||y1>=static_cast<int>(height))return;
    cmd(0xF6000000U|(static_cast<unsigned>(x1*4)<<12)|static_cast<unsigned>(y1*4),
        (static_cast<unsigned>(x0*4)<<12)|static_cast<unsigned>(y0*4));
  };
  const auto disk=[&](int radius) {
    for(int y=-radius;y<=radius;++y) {
      const int x=static_cast<int>(std::sqrt(static_cast<double>(radius*radius-y*y)));
      rect(cx-x,cy+y,cx+x,cy+y);
    }
  };
  // Half the former diameter (one-quarter area). Integer native pixels keep
  // the N64 fill spans and minimum 5x7 font complete at every output scale.
  if(!textured_button) {
    colour(25,48,122);disk(5*scale);
    colour(47,91,224);disk(4*scale);
  }
  colour(255,255,255);
  const int steps=static_cast<int>(std::clamp(progress,0.0f,1.0f)*96);
  for(int i=0;i<steps;++i) {
    const double angle=static_cast<double>(i)*6.283185307179586/96.0;
    const int x=cx+static_cast<int>(std::lround(std::sin(angle)*(textured_button?8:7)*scale));
    const int y=cy-static_cast<int>(std::lround(std::cos(angle)*(textured_button?8:7)*scale));
    rect(x,y,x+scale-1,y+scale-1);
  }
  const auto glyph=[&](int x,int y,const std::array<unsigned,7>& rows) {
    for(int row=0;row<7;++row)for(int col=0;col<5;) {
      if(!(rows[row]&(1U<<(4-col)))){++col;continue;}
      const int first=col;
      while(col<5&&(rows[row]&(1U<<(4-col))))++col;
      rect(x+first*scale,y+row*scale,x+col*scale-1,y+(row+1)*scale-1);
    }
  };
  if(!textured_button)glyph(cx-2*scale,cy-3*scale,{14,17,17,31,17,17,17});
  if(!textured_button) {
  int x=cx+12*scale,y=cy-3*scale;
  glyph(x,y,{15,16,16,14,1,1,30});x+=7*scale;
  glyph(x,y,{17,18,20,24,20,18,17});x+=7*scale;
  glyph(x,y,{31,4,4,4,4,4,31});x+=7*scale;
  glyph(x,y,{30,17,17,30,16,16,16});
  }
  cmd(0xE7000000U,0);
  return out;
}
inline std::vector<SkipGbiCommand> cutscene_transition_gbi(unsigned width,unsigned height) {
  if(width<160||width>1023||height<100||height>1023)return {};
  return {{0xE7000000U,0},{0xED000000U,(width*4U<<12U)|(height*4U)},
    {0xBA001402U,0x00300000U},{0xB900031DU,0},{0xF7000000U,0x00010001U},
    {0xF6000000U|(((width-1)*4U)<<12U)|((height-1)*4U),0},{0xE7000000U,0}};
}
} // namespace jfg
