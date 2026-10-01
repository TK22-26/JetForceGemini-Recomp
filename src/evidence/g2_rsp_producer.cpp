#include "jfg/evidence/g2_rsp_producer.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace {

// These stable marker strings are checked by the private dispatcher after a
// separately reviewed binary pin is installed.  This public scaffold has no
// pin and cannot be submitted as private execution evidence.
constexpr std::string_view kProbeMarker = "jfg_g2_rsp_programs_probe";
constexpr std::string_view kInventoryMarker = "jfg_g2_rsp_program_inventory";
constexpr std::string_view kReviewedManifestEvidenceSha256 =
    "99526b4401ef61307b21bc788a7b497711ffb33d3efb96391d2cae0687802a26";
constexpr std::size_t kMaximumCaseBytes = 64 * 1024;
constexpr std::size_t kMaximumPrograms = 32;

[[noreturn]] void fail() { throw std::runtime_error("invalid case"); }

bool is_identifier(const std::string_view value) {
    if (value.size() < 2 || value.size() > 72 || value.front() == '-' ||
        value.back() == '-') return false;
    for (const char c : value) {
        if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '.' ||
              c == '_' || c == '-')) return false;
    }
    return true;
}

bool is_digest(const std::string_view value) {
    if (value.size() != 64) return false;
    for (const char c : value) {
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    }
    return true;
}

std::uint16_t read_u16(const std::vector<std::byte>& input, std::size_t& at) {
    if (at + 2 > input.size()) fail();
    const auto value = static_cast<std::uint16_t>(
        static_cast<std::uint16_t>(std::to_integer<unsigned char>(input[at])) |
        (static_cast<std::uint16_t>(std::to_integer<unsigned char>(input[at + 1])) << 8U));
    at += 2;
    return value;
}

// Compact, self-contained SHA-256 for binding the exact case and per-record
// classification evidence.  It is not used as a success signal.
class Sha256 {
 public:
  void update(const std::byte* data, std::size_t size) {
    bit_count_ += static_cast<std::uint64_t>(size) * 8U;
    while (size != 0) {
      const std::size_t copy = std::min(size, block_.size() - used_);
      for (std::size_t i = 0; i < copy; ++i) block_[used_ + i] = std::to_integer<unsigned char>(data[i]);
      used_ += copy; data += copy; size -= copy;
      if (used_ == block_.size()) { transform(); used_ = 0; }
    }
  }
  std::string finish() {
    block_[used_++] = 0x80;
    if (used_ > 56) { while (used_ < 64) block_[used_++] = 0; transform(); used_ = 0; }
    while (used_ < 56) block_[used_++] = 0;
    for (int shift = 56; shift >= 0; shift -= 8) block_[used_++] = static_cast<unsigned char>(bit_count_ >> shift);
    transform();
    std::ostringstream out;
    for (const auto word : state_) out << std::hex << std::setfill('0') << std::setw(8) << word;
    return out.str();
  }
 private:
  static constexpr std::array<std::uint32_t, 64> k = {0x428a2f98U,0x71374491U,0xb5c0fbcfU,0xe9b5dba5U,0x3956c25bU,0x59f111f1U,0x923f82a4U,0xab1c5ed5U,0xd807aa98U,0x12835b01U,0x243185beU,0x550c7dc3U,0x72be5d74U,0x80deb1feU,0x9bdc06a7U,0xc19bf174U,0xe49b69c1U,0xefbe4786U,0x0fc19dc6U,0x240ca1ccU,0x2de92c6fU,0x4a7484aaU,0x5cb0a9dcU,0x76f988daU,0x983e5152U,0xa831c66dU,0xb00327c8U,0xbf597fc7U,0xc6e00bf3U,0xd5a79147U,0x06ca6351U,0x14292967U,0x27b70a85U,0x2e1b2138U,0x4d2c6dfcU,0x53380d13U,0x650a7354U,0x766a0abbU,0x81c2c92eU,0x92722c85U,0xa2bfe8a1U,0xa81a664bU,0xc24b8b70U,0xc76c51a3U,0xd192e819U,0xd6990624U,0xf40e3585U,0x106aa070U,0x19a4c116U,0x1e376c08U,0x2748774cU,0x34b0bcb5U,0x391c0cb3U,0x4ed8aa4aU,0x5b9cca4fU,0x682e6ff3U,0x748f82eeU,0x78a5636fU,0x84c87814U,0x8cc70208U,0x90befffaU,0xa4506cebU,0xbef9a3f7U,0xc67178f2U};
  static std::uint32_t rotr(std::uint32_t value, unsigned shift) { return (value >> shift) | (value << (32U - shift)); }
  void transform() {
    std::array<std::uint32_t, 64> w{};
    for (std::size_t i = 0; i < 16; ++i) w[i] = (static_cast<std::uint32_t>(block_[i*4]) << 24U) | (static_cast<std::uint32_t>(block_[i*4+1]) << 16U) | (static_cast<std::uint32_t>(block_[i*4+2]) << 8U) | block_[i*4+3];
    for (std::size_t i = 16; i < 64; ++i) { const auto s0 = rotr(w[i-15],7)^rotr(w[i-15],18)^(w[i-15]>>3U); const auto s1 = rotr(w[i-2],17)^rotr(w[i-2],19)^(w[i-2]>>10U); w[i] = w[i-16]+s0+w[i-7]+s1; }
    auto a=state_[0],b=state_[1],c=state_[2],d=state_[3],e=state_[4],f=state_[5],g=state_[6],h=state_[7];
    for (std::size_t i=0;i<64;++i) { const auto s1=rotr(e,6)^rotr(e,11)^rotr(e,25); const auto ch=(e&f)^((~e)&g); const auto t1=h+s1+ch+k[i]+w[i]; const auto s0=rotr(a,2)^rotr(a,13)^rotr(a,22); const auto maj=(a&b)^(a&c)^(b&c); const auto t2=s0+maj; h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2; }
    state_[0]+=a;state_[1]+=b;state_[2]+=c;state_[3]+=d;state_[4]+=e;state_[5]+=f;state_[6]+=g;state_[7]+=h;
  }
  std::array<unsigned char,64> block_{}; std::array<std::uint32_t,8> state_{0x6a09e667U,0xbb67ae85U,0x3c6ef372U,0xa54ff53aU,0x510e527fU,0x9b05688cU,0x1f83d9abU,0x5be0cd19U}; std::size_t used_{}; std::uint64_t bit_count_{};
};

std::string digest(const std::vector<std::byte>& bytes) { Sha256 hash; hash.update(bytes.data(), bytes.size()); return hash.finish(); }
std::string digest_range(const std::vector<std::byte>& bytes, std::size_t begin, std::size_t end) { Sha256 hash; hash.update(bytes.data()+begin, end-begin); return hash.finish(); }

struct Program { std::string id, family, classification, owner, estimate, probe; std::uint32_t entries, accesses, completions, exit_code; std::string evidence; };

std::vector<std::byte> read_case() {
    std::ifstream input("case-input.bin", std::ios::binary);
    if (!input) fail();
    input.seekg(0, std::ios::end); const auto length = input.tellg();
    if (length <= 0 || static_cast<std::uint64_t>(length) > kMaximumCaseBytes) fail();
    input.seekg(0); std::vector<std::byte> value(static_cast<std::size_t>(length));
    input.read(reinterpret_cast<char*>(value.data()), length); if (!input) fail(); return value;
}

std::vector<Program> parse(const std::vector<std::byte>& input) {
    constexpr std::array<unsigned char,8> magic{'J','F','G','R','S','P','0','1'};
    if (input.size() < 12 || !std::equal(magic.begin(), magic.end(), reinterpret_cast<const unsigned char*>(input.data()))) fail();
    constexpr std::array<std::string_view, 4> expected_ids{
        "graphics-representative", "audio-primary", "audio-secondary",
        "boot-loader"};
    constexpr std::array<unsigned char, 4> expected_families{0U, 1U, 2U, 3U};
    std::size_t at=8; if (read_u16(input, at) != jfg::evidence::g2_rsp_case_version) fail(); const auto count=read_u16(input,at); if (count != expected_ids.size() || count > kMaximumPrograms) fail();
    bool graphics=false, primary=false, secondary=false; std::vector<Program> out;
    for (std::uint16_t index=0; index<count; ++index) {
      if (at >= input.size()) fail();
      const auto id_size=std::to_integer<unsigned char>(input[at++]); if (id_size < 2 || id_size > 72 || at+id_size+3 > input.size()) fail();
      std::string id(reinterpret_cast<const char*>(input.data()+at), id_size); at+=id_size; if (!is_identifier(id)) fail();
      for (const auto& existing: out) if (existing.id == id) fail();
      const auto family_code=std::to_integer<unsigned char>(input[at++]); if (id != expected_ids[index] || family_code != expected_families[index]) fail(); const auto blob_size=read_u16(input,at); if (blob_size == 0 || blob_size > 4096 || at+blob_size > input.size()) fail(); at += blob_size;
      Program p{}; p.id=id; p.entries=1;
      p.evidence=digest_range(input,at-blob_size,at);
      if (family_code == 0) { p.family="graphics"; p.classification="executable"; p.owner="rsp-graphics"; p.probe="classification-only"; p.completions=0;p.exit_code=0;graphics=true; }
      else if (family_code == 1) { p.family="audio-primary"; p.classification="executable"; p.owner="rsp-audio-primary"; p.probe="classification-only"; p.completions=0;p.exit_code=0;primary=true; }
      else if (family_code == 2) { p.family="audio-secondary"; p.classification="unsupported-with-fallback"; p.owner="rsp-audio-secondary"; p.probe="classification-only"; p.completions=0;p.exit_code=0;secondary=true; }
      else if (family_code == 3) { if (blob_size != 32U || p.evidence != kReviewedManifestEvidenceSha256) fail(); p.family="other"; p.classification="empty"; p.owner="rsp-other"; p.probe="classification-only"; p.entries=0;p.completions=0;p.exit_code=0; }
      else fail();
      // This producer classifies bounded program bytes only.  It deliberately
      // cannot claim that graphics/audio executed; the trusted bundle binds
      // these evidence digests to the independent native producers.
      p.entries = 0U; p.accesses = 0U;
      p.estimate=blob_size < 64 ? "small" : (blob_size < 512 ? "medium" : "large"); out.push_back(std::move(p));
    }
    if (at != input.size() || !graphics || !primary || !secondary) {
        fail();
    }
    return out;
}

std::string quote(const std::string& value) { return "\"" + value + "\""; }
std::string observation(const std::vector<Program>& programs, std::string_view case_id, std::string_view subject) {
  std::ostringstream out; out << "{\"case_id\":" << quote(std::string(case_id)) << ",\"kind\":\"jfg-g2-rsp-program-observation\",\"native_probes\":[";
  for (std::size_t i=0;i<programs.size();++i) { const auto& p=programs[i]; if(i)out<<','; out << "{\"broker_access_count\":"<<p.accesses<<",\"completion_count\":"<<p.completions<<",\"entry_count\":"<<p.entries<<",\"probe_kind\":"<<quote(p.probe)<<",\"program_exit_code\":"<<p.exit_code<<",\"program_id\":"<<quote(p.id)<<"}"; }
  out << "],\"overlay_slots\":["; for(std::size_t i=0;i<programs.size();++i){const auto&p=programs[i];if(i)out<<',';out<<"{\"classification\":"<<quote(p.classification)<<",\"estimate_class\":"<<quote(p.estimate)<<",\"evidence_sha256\":"<<quote(p.evidence)<<",\"owner_id\":"<<quote(p.owner)<<",\"program_id\":"<<quote(p.id)<<",\"slot_id\":"<<quote("slot-"+p.id)<<"}";} out<<"],\"programs\":[";
  for(std::size_t i=0;i<programs.size();++i){const auto&p=programs[i];if(i)out<<',';out<<"{\"classification_evidence_sha256\":"<<quote(p.evidence)<<",\"family\":"<<quote(p.family)<<",\"generated_entry_count\":"<<p.entries<<",\"program_id\":"<<quote(p.id)<<"}";} out<<"],\"schema_version\":1,\"subject_sha256\":"<<quote(std::string(subject))<<"}"; return out.str();
}

}  // namespace

int main(int argc, const char* const* argv) {
  try {
    const volatile char* probe_marker = kProbeMarker.data();
    const volatile char* inventory_marker = kInventoryMarker.data();
    if (*probe_marker == '\0' || *inventory_marker == '\0' || argc != 9 || std::string_view(argv[1]) != "--g2-evidence-probe" || !is_digest(argv[2]) || std::string_view(argv[3]) != "rsp-programs" || std::string_view(argv[4]) != "private-native-execution" || std::string_view(argv[5]) != "--case-id" || !is_identifier(argv[6]) || std::string_view(argv[7]) != "--subject-sha256" || !is_digest(argv[8])) return 2;
    const auto bytes=read_case(); if (digest(bytes) != argv[8]) return 1; const auto value=observation(parse(bytes),argv[6],argv[8]); std::cout << "{\"execution_nonce\":" << quote(argv[2]) << ",\"observation\":" << value << '}'; return std::cout ? 0 : 1;
  } catch (...) { return 1; }
}
