#include "jfg/evidence/g2_cpu_producer.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace {
constexpr std::string_view kProbeMarker = "jfg_g2_cpu_sections_probe";
constexpr std::string_view kLinkMarker = "jfg_generated_link_smoke";
constexpr std::string_view kLookupMarker = "jfg_generated_lookup_function";
constexpr std::size_t kMaxCase = 64 * 1024;
constexpr std::size_t kMaxSections = 1024;
constexpr std::size_t kMaxOverlaySlots = 1024;
[[noreturn]] void fail() { throw std::runtime_error("invalid CPU evidence case"); }

bool id(std::string_view value) {
  if (value.size() < 2 || value.size() > 72 || value.front() == '-' || value.back() == '-') return false;
  for (char c : value) if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '.' || c == '_' || c == '-')) return false;
  return true;
}
bool digest_text(std::string_view value) {
  if (value.size() != 64) return false;
  for (char c : value) if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
  return true;
}

class Sha256 {
 public:
  void update(const std::byte* data, std::size_t size) {
    bits_ += static_cast<std::uint64_t>(size) * 8U;
    while (size) { const auto n = std::min(size, block_.size() - used_); for (std::size_t i=0;i<n;++i) block_[used_+i]=std::to_integer<unsigned char>(data[i]); used_+=n; data+=n; size-=n; if(used_==64){transform();used_=0;} }
  }
  std::string finish() {
    block_[used_++]=0x80; if(used_>56){while(used_<64)block_[used_++]=0;transform();used_=0;} while(used_<56)block_[used_++]=0;
    for (int shift = 56; shift >= 0; shift -= 8) {
      block_[used_++] = static_cast<unsigned char>(bits_ >> shift);
    }
    transform();
    std::ostringstream out;
    for (const auto word : state_) {
      out << std::hex << std::setfill('0') << std::setw(8) << word;
    }
    return out.str();
  }
 private:
  static std::uint32_t r(std::uint32_t v,unsigned n){return(v>>n)|(v<<(32U-n));}
  void transform() {
    static constexpr std::array<std::uint32_t,64> k={0x428a2f98U,0x71374491U,0xb5c0fbcfU,0xe9b5dba5U,0x3956c25bU,0x59f111f1U,0x923f82a4U,0xab1c5ed5U,0xd807aa98U,0x12835b01U,0x243185beU,0x550c7dc3U,0x72be5d74U,0x80deb1feU,0x9bdc06a7U,0xc19bf174U,0xe49b69c1U,0xefbe4786U,0x0fc19dc6U,0x240ca1ccU,0x2de92c6fU,0x4a7484aaU,0x5cb0a9dcU,0x76f988daU,0x983e5152U,0xa831c66dU,0xb00327c8U,0xbf597fc7U,0xc6e00bf3U,0xd5a79147U,0x06ca6351U,0x14292967U,0x27b70a85U,0x2e1b2138U,0x4d2c6dfcU,0x53380d13U,0x650a7354U,0x766a0abbU,0x81c2c92eU,0x92722c85U,0xa2bfe8a1U,0xa81a664bU,0xc24b8b70U,0xc76c51a3U,0xd192e819U,0xd6990624U,0xf40e3585U,0x106aa070U,0x19a4c116U,0x1e376c08U,0x2748774cU,0x34b0bcb5U,0x391c0cb3U,0x4ed8aa4aU,0x5b9cca4fU,0x682e6ff3U,0x748f82eeU,0x78a5636fU,0x84c87814U,0x8cc70208U,0x90befffaU,0xa4506cebU,0xbef9a3f7U,0xc67178f2U};
    std::array<std::uint32_t,64>w{}; for(std::size_t i=0;i<16;++i)w[i]=(std::uint32_t(block_[4*i])<<24U)|(std::uint32_t(block_[4*i+1])<<16U)|(std::uint32_t(block_[4*i+2])<<8U)|block_[4*i+3];
    for(std::size_t i=16;i<64;++i){auto s0=r(w[i-15],7)^r(w[i-15],18)^(w[i-15]>>3U);auto s1=r(w[i-2],17)^r(w[i-2],19)^(w[i-2]>>10U);w[i]=w[i-16]+s0+w[i-7]+s1;}
    auto a=state_[0],b=state_[1],c=state_[2],d=state_[3],e=state_[4],f=state_[5],g=state_[6],h=state_[7]; for(std::size_t i=0;i<64;++i){auto s1=r(e,6)^r(e,11)^r(e,25);auto ch=(e&f)^((~e)&g);auto t1=h+s1+ch+k[i]+w[i];auto s0=r(a,2)^r(a,13)^r(a,22);auto maj=(a&b)^(a&c)^(b&c);auto t2=s0+maj;h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;} state_[0]+=a;state_[1]+=b;state_[2]+=c;state_[3]+=d;state_[4]+=e;state_[5]+=f;state_[6]+=g;state_[7]+=h;
  }
  std::array<unsigned char,64>block_{}; std::array<std::uint32_t,8>state_{0x6a09e667U,0xbb67ae85U,0x3c6ef372U,0xa54ff53aU,0x510e527fU,0x9b05688cU,0x1f83d9abU,0x5be0cd19U}; std::size_t used_{}; std::uint64_t bits_{};
};
std::string sha(const std::vector<std::byte>& b){Sha256 h;h.update(b.data(),b.size());return h.finish();}
std::uint16_t u16(const std::vector<std::byte>& b,std::size_t& p){if(p+2>b.size())fail();auto v=static_cast<std::uint16_t>(std::uint16_t(std::to_integer<unsigned char>(b[p]))|(std::uint16_t(std::to_integer<unsigned char>(b[p+1]))<<8U));p+=2;return v;}
std::uint32_t u32(const std::vector<std::byte>& b,std::size_t& p){if(p+4>b.size())fail();std::uint32_t v=0;for(unsigned i=0;i<4;++i)v|=std::uint32_t(std::to_integer<unsigned char>(b[p+i]))<<(8U*i);p+=4;return v;}
std::string text(const std::vector<std::byte>&b,std::size_t&p){if(p>=b.size())fail();auto n=std::to_integer<unsigned char>(b[p++]);if(n<2||n>72||p+n>b.size())fail();std::string v(reinterpret_cast<const char*>(b.data()+p),n);p+=n;if(!id(v))fail();return v;}
std::string hex32(const std::vector<std::byte>&b,std::size_t&p){if(p+32>b.size())fail();std::ostringstream o;for(unsigned i=0;i<32;++i)o<<std::hex<<std::setfill('0')<<std::setw(2)<<unsigned(std::to_integer<unsigned char>(b[p++]));return o.str();}
struct Section{std::string id,kind;std::uint32_t expected,attempted,generated,excluded,failures,lookups,lifecycle,relocations;};
struct OverlaySlot{std::string id,disposition,section_id;};
struct CompilerProduct{std::string id,executable_sha256;}; struct Case{std::vector<CompilerProduct> compiler_products;std::string g3_product_binding;std::vector<Section>sections;std::vector<OverlaySlot>overlay_slots;std::array<std::uint32_t,9> audit;std::vector<std::uint8_t> tools;};
std::vector<std::byte> read_case(){std::ifstream f("case-input.bin",std::ios::binary);if(!f)fail();f.seekg(0,std::ios::end);auto n=f.tellg();if(n<=0||std::uint64_t(n)>kMaxCase)fail();f.seekg(0);std::vector<std::byte>b{std::size_t(n)};f.read(reinterpret_cast<char*>(b.data()),n);if(!f)fail();return b;}
Case parse(const std::vector<std::byte>&b){
  constexpr std::array<unsigned char,8>magic{'J','F','G','C','P','U','0','2'};if(b.size()<12||!std::equal(magic.begin(),magic.end(),reinterpret_cast<const unsigned char*>(b.data())))fail();std::size_t p=8;if(u16(b,p)!=jfg::evidence::g2_cpu_case_version)fail();auto compiler_count=u16(b,p);if(compiler_count!=3)fail();std::vector<std::string> ids;Case c;
  for(unsigned i=0;i<compiler_count;++i){auto compiler_id=text(b,p);for(const auto&known:ids)if(known==compiler_id)fail();ids.push_back(compiler_id);c.compiler_products.push_back({compiler_id,hex32(b,p)});}
  c.g3_product_binding=hex32(b,p);
  const auto count = u16(b, p);
  if (count < 2 || count > kMaxSections) fail();
  bool main = false, overlay = false;
  for (unsigned i = 0; i < count; ++i) {
    Section s{}; s.id = text(b, p);
    for (const auto& old : c.sections) if (old.id == s.id) fail();
    if (p >= b.size()) fail();
    const auto kind = std::to_integer<unsigned char>(b[p++]);
    if (kind > 1) fail();
    s.kind = kind == 0 ? "main" : "overlay"; main |= kind == 0; overlay |= kind == 1;
    s.expected=u32(b,p); s.attempted=u32(b,p); s.generated=u32(b,p); s.excluded=u32(b,p);
    s.failures=u32(b,p); s.lookups=u32(b,p); s.lifecycle=u32(b,p); s.relocations=u32(b,p);
    if (!s.expected || s.attempted != s.expected || s.generated + s.excluded != s.expected || s.failures || s.lookups < s.generated || (s.kind == "overlay" && !s.lifecycle)) fail();
    c.sections.push_back(s);
  }
  if (!main || !overlay) fail();
  const auto slot_count = u16(b, p);
  if (!slot_count || slot_count > kMaxOverlaySlots) fail();
  std::vector<std::string> populated_sections;
  for (unsigned i = 0; i < slot_count; ++i) {
    OverlaySlot slot{}; slot.id = text(b, p);
    for (const auto& old : c.overlay_slots) if (old.id == slot.id) fail();
    if (p >= b.size()) fail();
    const auto disposition = std::to_integer<unsigned char>(b[p++]);
    if (disposition > 1) fail();
    if (disposition == 0) {
      slot.disposition = "populated"; slot.section_id = text(b, p);
      bool overlay_section = false;
      for (const auto& section : c.sections) if (section.id == slot.section_id && section.kind == "overlay") overlay_section = true;
      if (!overlay_section || std::find(populated_sections.begin(), populated_sections.end(), slot.section_id) != populated_sections.end()) fail();
      populated_sections.push_back(slot.section_id);
    } else {
      slot.disposition = "empty-fail-closed";
    }
    c.overlay_slots.push_back(slot);
  }
  if (populated_sections.size() + 1U != static_cast<std::size_t>(count)) fail();
  for (auto& value : c.audit) value = u32(b, p);
  if (!c.audit[0] || c.audit[0] != count || c.audit[1] != c.audit[2] || c.audit[1] != c.audit[3] || c.audit[4] || c.audit[5] || c.audit[6] || c.audit[7] != c.audit[8]) fail();
  const auto tools = u16(b, p);
  if (tools != 5) fail();
  std::array<bool,6> seen{};
  for (unsigned i = 0; i < tools; ++i) {
    if (p >= b.size()) fail();
    const auto tool = std::to_integer<unsigned char>(b[p++]);
    if (tool < 1 || tool > 5 || seen[tool]) fail();
    seen[tool] = true;
    const auto code = u32(b, p), findings = u32(b, p);
    if (code || findings) fail();
    c.tools.push_back(tool);
  }
  if (p != b.size()) fail();
  for (unsigned i = 1; i <= 5; ++i) if (!seen[i]) fail();
  return c;
}
std::string q(std::string_view s){return "\""+std::string(s)+"\"";}
std::string output(const Case&c,std::string_view case_id,std::string_view subject,const CompilerProduct&compiler){std::ostringstream o;o<<"{\"analysis_records\":[";constexpr std::array<std::string_view,5>names{"compiler-link","forced-object-audit","asan","ubsan","clang-static-analyzer"};for(std::size_t i=0;i<c.tools.size();++i){if(i)o<<',';auto n=names[c.tools[i]-1];o<<"{\"exit_code\":0,\"finding_count\":0,\"source_set_sha256\":"<<q(subject)<<",\"tool\":"<<q(n)<<'}';}o<<"],\"case_id\":"<<q(case_id)<<",\"compiler_executable_sha256\":"<<q(compiler.executable_sha256)<<",\"compiler_id\":"<<q(compiler.id)<<",\"g3_product_binding_sha256\":"<<q(c.g3_product_binding)<<",\"kind\":\"jfg-g2-cpu-observation\",\"link_audit\":{\"duplicate_definition_count\":"<<c.audit[5]<<",\"expected_object_count\":"<<c.audit[1]<<",\"expected_runtime_bridge_count\":"<<c.audit[7]<<",\"forced_object_count\":"<<c.audit[3]<<",\"generated_object_count\":"<<c.audit[2]<<",\"generated_stub_count\":"<<c.audit[6]<<",\"resolved_runtime_bridge_count\":"<<c.audit[8]<<",\"section_count\":"<<c.audit[0]<<",\"unresolved_symbol_count\":"<<c.audit[4]<<"},\"overlay_slots\":[";for(std::size_t i=0;i<c.overlay_slots.size();++i){const auto&s=c.overlay_slots[i];if(i)o<<',';o<<"{\"disposition\":"<<q(s.disposition)<<",\"section_id\":"<<(s.section_id.empty()?"null":q(s.section_id))<<",\"slot_id\":"<<q(s.id)<<'}';}o<<"],\"schema_version\":4,\"sections\":[";for(std::size_t i=0;i<c.sections.size();++i){const auto&s=c.sections[i];if(i)o<<',';o<<"{\"approved_exclusion_count\":"<<s.excluded<<",\"attempted_body_count\":"<<s.attempted<<",\"expected_body_count\":"<<s.expected<<",\"generated_body_count\":"<<s.generated<<",\"kind\":"<<q(s.kind)<<",\"lifecycle_entry_count\":"<<s.lifecycle<<",\"lookup_entry_count\":"<<s.lookups<<",\"relocation_entry_count\":"<<s.relocations<<",\"section_id\":"<<q(s.id)<<",\"unclassified_failure_count\":"<<s.failures<<"}";}o<<"],\"source_set_sha256\":"<<q(subject)<<",\"subject_sha256\":"<<q(subject)<<'}';return o.str();}
}
int main(int argc,const char*const*argv){try{const volatile char*a=kProbeMarker.data();const volatile char*b=kLinkMarker.data();const volatile char*c=kLookupMarker.data();if(!*a||!*b||!*c||argc!=13||std::string_view(argv[1])!="--g2-evidence-probe"||!digest_text(argv[2])||std::string_view(argv[3])!="cpu-sections"||std::string_view(argv[4])!="private-g3-compiler-product-binding"||std::string_view(argv[5])!="--case-id"||!id(argv[6])||std::string_view(argv[7])!="--subject-sha256"||!digest_text(argv[8])||std::string_view(argv[9])!="--compiler-id"||!id(argv[10])||std::string_view(argv[11])!="--compiler-executable-sha256"||!digest_text(argv[12]))return 2;auto raw=read_case();if(sha(raw)!=argv[8])return 1;auto value=parse(raw);const CompilerProduct*chosen=nullptr;for(const auto&compiler:value.compiler_products)if(compiler.id==argv[10]&&compiler.executable_sha256==argv[12]){if(chosen)fail();chosen=&compiler;}if(!chosen)fail();std::cout<<"{\"execution_nonce\":"<<q(argv[2])<<",\"observation\":"<<output(value,argv[6],argv[8],*chosen)<<'}';return std::cout?0:1;}catch(...){return 1;}}
