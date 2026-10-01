#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#include "jfg/evidence/g2_paired_producer.hpp"

namespace jfg::evidence::trap {

inline constexpr std::size_t kMaximumCaseBytes = 1024U * 1024U;
inline constexpr std::array<std::byte, 8> kCaseMagic{
    std::byte{'J'}, std::byte{'F'}, std::byte{'G'}, std::byte{'2'},
    std::byte{'T'}, std::byte{'R'}, std::byte{'P'}, std::byte{'1'}};

struct Identity final { std::string nonce; std::string case_id; std::string digest; };

[[nodiscard]] inline bool digest_text(const std::string_view value) {
    return value.size() == 64U && std::all_of(value.begin(), value.end(), [](const char c) {
        return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
    });
}
[[nodiscard]] inline bool identifier(const std::string_view value) {
    if (value.size() < 3U || value.size() > 72U || value.front() < 'a' || value.front() > 'z' ||
        !((value.back() >= 'a' && value.back() <= 'z') || (value.back() >= '0' && value.back() <= '9'))) return false;
    return std::all_of(value.begin(), value.end(), [](const char c) {
        return (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '.' || c == '_' || c == '-';
    });
}
[[nodiscard]] inline Identity parse_identity(const int argc, const char* const* argv,
    const std::string_view evidence_class = "private-native-execution") {
    if (argc != 9 || std::string_view(argv[1]) != "--g2-evidence-probe" || !digest_text(argv[2]) ||
        std::string_view(argv[3]) != "runtime-traps" || std::string_view(argv[4]) != evidence_class ||
        std::string_view(argv[5]) != "--case-id" || !identifier(argv[6]) || std::string_view(argv[7]) != "--subject-sha256" || !digest_text(argv[8])) throw std::runtime_error("arguments");
    return {argv[2], argv[6], argv[8]};
}

[[nodiscard]] inline std::uint32_t u32(const std::span<const std::byte> bytes, const std::size_t at) { if(at>bytes.size()||bytes.size()-at<4U) throw std::runtime_error("truncated"); return std::to_integer<std::uint32_t>(bytes[at])|(std::to_integer<std::uint32_t>(bytes[at+1U])<<8U)|(std::to_integer<std::uint32_t>(bytes[at+2U])<<16U)|(std::to_integer<std::uint32_t>(bytes[at+3U])<<24U); }
[[nodiscard]] inline std::vector<std::byte> read_case(const Identity& identity) { std::ifstream file("case-input.bin",std::ios::binary|std::ios::ate); if(!file)throw std::runtime_error("case");const auto length=file.tellg();if(length<0||static_cast<std::uint64_t>(length)>kMaximumCaseBytes)throw std::runtime_error("case size");std::vector<std::byte> bytes(static_cast<std::size_t>(length));file.seekg(0);file.read(reinterpret_cast<char*>(bytes.data()),length);if(!file||bytes.size()<20U||!std::ranges::equal(std::span(bytes).first<8U>(),kCaseMagic)||u32(bytes,8U)!=2U||::jfg::evidence::hex_digest(bytes)!=identity.digest)throw std::runtime_error("case digest");return bytes; }
inline int emit(const Identity& identity, const std::string_view observation) { const std::string out="{\"execution_nonce\":\""+identity.nonce+"\",\"observation\":"+std::string(observation)+"}";std::cout.write(out.data(),static_cast<std::streamsize>(out.size()));return std::cout?0:1; }
} // namespace jfg::evidence::trap
