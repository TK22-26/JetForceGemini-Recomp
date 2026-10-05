#pragma once
// Independently authored, read-only decoding of the supported hinttext state.
// Controller requests are bound to a specific ready page, room and input epoch.
#include <cstdint>
#include <istream>
#include <ostream>
#include <string>
#include <vector>
#include <span>
#include <stdexcept>
namespace jfg::mod {
// Narrow read-only view for the normalized runtime's separately mapped overlay.
// The owner must supply a live, metadata-validated section; all other pointers
// retain the ordinary RDRAM bounds checks.
template<class M> class DialogueMemory {
  const M &ram_;std::uint32_t base_;std::span<const std::uint8_t> section_;
  bool section_range(std::uint32_t a,std::uint64_t n) const noexcept {
    return a>=base_ && std::uint64_t(a-base_)<=section_.size() &&
      n<=section_.size()-std::uint64_t(a-base_);
  }
public:
  DialogueMemory(const M &ram,std::uint32_t base,std::span<const std::uint8_t> section)
    :ram_(ram),base_(base),section_(section) {}
  bool valid(std::uint32_t a,std::uint64_t n) const noexcept {
    return ram_.valid(a,n)||section_range(a,n);
  }
  std::uint8_t u8(std::uint32_t a) const {
    if(ram_.valid(a,1))return ram_.u8(a);
    if(!section_range(a,1)||((a-base_)^3U)>=section_.size())
      throw std::runtime_error("invalid dialogue memory");
    return section_[(a-base_)^3U];
  }
  std::uint16_t u16(std::uint32_t a) const {
    if(!valid(a,2))throw std::runtime_error("invalid dialogue halfword");
    return std::uint16_t((u8(a)<<8U)|u8(a+1U));
  }
  std::int16_t s16(std::uint32_t a) const {return static_cast<std::int16_t>(u16(a));}
  std::uint32_t u32(std::uint32_t a) const {
    if(!valid(a,4))throw std::runtime_error("invalid dialogue word");
    return (std::uint32_t(u16(a))<<16U)|u16(a+2U);
  }
};
struct DialogueChoice { unsigned action{}; int prerequisite{}; };
struct DialogueState {
  bool known{},active{},ready{},choices{};
  std::uint32_t token{},text{},table{};
  unsigned type{},selected{};
  std::vector<DialogueChoice> rows;
};
template<class M> DialogueState read_dialogue(const M &m,std::uint32_t base) noexcept {
  DialogueState d;
  try {
    if((base&3U)||!m.valid(base,0x2C44U)||
       (m.u32(base+0xD84U)&0xFFFF0000U)!=0x8C420000U||
       m.u32(base+0xD88U)!=0x03E00008U)return d;
    const auto active=m.u32(base+0x2A24U),type=m.u32(base+0x2A44U);
    if(active>1U||type>4U)return d;
    d.known=true;d.active=active!=0;d.type=type;
    if(!d.active)return d;
    d.text=m.u32(base+0x2A58U);d.table=m.u32(base+0x2A5CU);
    d.choices=type==1U||d.text==0U;
    d.ready=m.u32(base+0x2A28U)==0U&&m.u32(base+0x2A2CU)==0U&&
      m.u32(base+0x2A38U)==0U&&m.u32(base+0x2A20U)>=256U;
    if(d.choices) {
      if(!m.valid(d.table,4))return {};
      const int count=m.s16(d.table),selected=m.s16(d.table+2);
      if(count<1||count>32||selected<0||selected>=count||!m.valid(d.table,4U+16U*static_cast<unsigned>(count)))return {};
      d.selected=unsigned(selected);
      for(int i=0;i<count;++i) {
        const auto row=d.table+4U+unsigned(i)*16U;
        d.rows.push_back({m.u16(row+8U),m.s16(row+6U)});
      }
    } else if(!m.valid(d.text,1U))return {};
    std::uint32_t hash=2166136261U;
    for(auto value:{base,type,d.text,d.table,d.selected,m.u32(base+0x2A3CU),m.u32(base+0x2A40U),m.u32(base+0x2A4CU)})
      hash=(hash^value)*16777619U;
    for(const auto &row:d.rows)hash=(hash^row.action)*16777619U;
    d.token=hash;
  } catch(...) { return {}; }
  return d;
}
inline void write_dialogue(std::ostream &out,const DialogueState &d) {
  out<<"{\"known\":"<<(d.known?"true":"false")<<",\"active\":"<<(d.active?"true":"false")
     <<",\"ready\":"<<(d.ready?"true":"false")<<",\"choices\":"<<(d.choices?"true":"false")
     <<",\"token\":"<<d.token<<",\"selected\":"<<d.selected<<",\"rows\":[";
  bool first=true;for(const auto &row:d.rows) {
    if (!first) { out << ','; }
    first = false;
    out<<"{\"action\":"<<row.action<<",\"prerequisite\":"<<row.prerequisite<<'}';
  }out<<"]}";
}
class DialogueInput {
  std::uint64_t last_{};
public:
  int command(std::istream &in,const DialogueState &d,bool manual,bool replay,
              std::uint32_t level,std::uint64_t generation,std::uint64_t inputs,std::int64_t now) {
    std::string magic,extra;std::uint32_t room{},token{};std::uint64_t gen{},nonce{},epoch{};
    std::int64_t stamp{};int action{};
    if(!(in>>magic>>room>>gen>>nonce>>stamp>>epoch>>token>>action)||magic!="JFGDIALOGUE1"||
       nonce<=last_||stamp<0||stamp>now||now-stamp>1000||(in>>extra))return 0;
    last_=nonce; // Refused requests cannot become valid on a later page.
    if(room!=level||gen!=generation||epoch!=inputs||manual||replay||
       !d.known||!d.active||!d.ready||d.token!=token)return 0;
    if(action==0)return 1; // A
    if(d.choices&&action==1&&d.selected>0)return 2; // stick up
    if(d.choices&&action==2&&d.selected+1<d.rows.size())return 3; // stick down
    return 0;
  }
};
}
