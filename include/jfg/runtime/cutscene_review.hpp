#pragma once
#include <cstdint>
#include <optional>
#include <span>
#include <sstream>
#include <string>
#include <string_view>
namespace jfg {

// The review selector borrows the native credits frontend for room360.
// Keep the entry mode across repeated credit selections, then let the native
// room transition free/reinitialize the frontend when returning to a scene.
struct CutsceneReviewMode {
  std::optional<unsigned> before_credits;
  std::optional<unsigned> review_mode;
  std::optional<unsigned> destination(unsigned level,unsigned current) noexcept {
    // Remember the mode of the loaded review game, including when a later
    // script (rather than the selector) enters credits/character selection.
    if(!review_mode && current!=23U && current!=5U && current!=3U)
      review_mode=current;
    if(level==360U) {
      if(current!=23U)before_credits=
        (current==5U || current==3U)?review_mode.value_or(current):current;
      return 23U;
    }
    if(current==23U) {
      const auto mode=before_credits?before_credits:review_mode;
      before_credits.reset();
      return mode;
    }
    before_credits.reset();
    if((current==5U || current==3U) && review_mode)return review_mode;
    return current;
  }
};

struct CutsceneReviewRequest {
  std::uint64_t nonce=0;
  std::int64_t timestamp=0;
  unsigned level=0,group=0,character=0;
};
// Room207 is Juno's completed first-route return. Its original ending sets
// completion flag91, then chooses unfinished unlocked characters (flags1/0/2,
// completion91/90/92). A fresh Juno-only review save would leave no choice.
// Prepare only unlock prerequisites in the isolated diagnostic game; ordinary
// campaign entry and skip completion never call this helper.
constexpr bool cutscene_review_needs_character_unlocks(unsigned level,unsigned group) noexcept {
  return level==207U && group==0U;
}
inline std::optional<CutsceneReviewRequest> parse_cutscene_review(
    std::string_view text,std::uint64_t previous,std::int64_t now,
    std::int64_t session_started=0) {
  if(text.size()>192 || text.find('-')!=std::string_view::npos)return {};
  std::istringstream in{std::string(text)};std::string magic,extra;
  CutsceneReviewRequest x;
  if(!(in>>magic>>x.nonce>>x.timestamp>>x.level>>x.group>>x.character) ||
     magic!="JFGCUTSCENE1" || (in>>extra) || x.nonce<=previous ||
     // A request belongs only to the Play session in which it was created.
     // Freshness alone lets the previous scene replay after a crash/restart.
     x.timestamp<=session_started || now<x.timestamp || now-x.timestamp>60000 ||
     x.level>=412 || x.group>255 || x.character>2)return {};
  return x;
}
// Validate the selected native cinematic room and variant against original data.
// This does not assert story prerequisites or qualify skip completion.
// BigShip (45) has no safe standalone entry: native severed-limb setup
// requires a parent model absent from the review context. Keep normal campaign
// loading untouched; diagnostic requests must fail before creating its actors.
inline bool cutscene_review_entry_valid(std::span<const std::uint8_t> level_index,
    std::span<const std::uint8_t> headers,std::span<const std::uint8_t> sequence_index,
    std::span<const std::uint8_t> sequences,const CutsceneReviewRequest& x) {
  const auto word=[](auto b,std::size_t p) {
    return (std::uint32_t{b[p]}<<24)|(std::uint32_t{b[p+1]}<<16)|
           (std::uint32_t{b[p+2]}<<8)|b[p+3];
  };
  if(x.level>=412||x.group>255||x.character>2 ||
     x.level==0||x.level==1||x.level==45||x.level==73||x.level==79||x.level==127||x.level==161 ||
     level_index.size()<std::size_t{x.level+2}*4)return false;
  const auto begin=word(level_index,x.level*4),end=word(level_index,(x.level+1)*4);
  if(begin>end||end>headers.size()||end-begin<0xEA)return false;
  auto h=headers.subspan(begin,end-begin);
  if(h[0x6C]!=1 && h[0x6C]!=2)return false;
  const unsigned asset=(unsigned{h[0xE8]}<<8)|h[0xE9];
  if(asset==65535||sequence_index.size()<std::size_t{asset+2}*4)return false;
  const auto a=word(sequence_index,asset*4),b=word(sequence_index,(asset+1)*4);
  if(a>b||b>sequences.size())return false;
  auto data=sequences.subspan(a,b-a);
  for(unsigned i=0;i<256 && i*4U+4U<=data.size();++i) {
    const auto v=word(data,i*4U),group=v>>24,offset=v&0xFFFFFF;
    if(group==255)return false;
    if(group!=x.group)continue;
    if(offset>data.size()||data.size()-offset<4)return false;
    const auto script=word(data,offset)&0xFFFFFF;
    return script<=data.size()-offset && data.size()-offset-script>=4;
  }
  return false;
}
} // namespace jfg
