#pragma once

#include <algorithm>
#include <array>
#include <bit>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace jfg::evidence {

inline constexpr std::size_t kMaximumPairedCaseBytes = 1024U * 1024U;
inline constexpr std::array<std::byte, 8> kPairedCaseMagic{
    std::byte{'J'}, std::byte{'F'}, std::byte{'G'}, std::byte{'2'},
    std::byte{'P'}, std::byte{'R'}, std::byte{'D'}, std::byte{'1'}};

enum class PairedCaseFamily : std::uint32_t {
  graphics = 1U,
  audio = 2U,
  save = 3U,
};

struct ProducerIdentity final {
  std::string nonce;
  std::string case_id;
  std::string subject_sha256;
};

[[nodiscard]] inline bool is_lower_hex_digest(const std::string_view value) {
  return value.size() == 64U &&
         std::all_of(value.begin(), value.end(), [](const char character) {
           return (character >= '0' && character <= '9') ||
                  (character >= 'a' && character <= 'f');
         });
}

[[nodiscard]] inline bool is_case_identifier(const std::string_view value) {
  if (value.size() < 3U || value.size() > 72U || value.front() < 'a' ||
      value.front() > 'z' ||
      !((value.back() >= 'a' && value.back() <= 'z') ||
        (value.back() >= '0' && value.back() <= '9'))) {
    return false;
  }
  return std::all_of(value.begin(), value.end(), [](const char character) {
    return (character >= 'a' && character <= 'z') ||
           (character >= '0' && character <= '9') || character == '.' ||
           character == '_' || character == '-';
  });
}

[[nodiscard]] inline ProducerIdentity
parse_producer_identity(const int argc, const char *const *argv,
                        const std::string_view requirement,
                        const std::string_view evidence_class) {
  if (argc != 9 || std::string_view(argv[1]) != "--g2-evidence-probe" ||
      !is_lower_hex_digest(argv[2]) ||
      std::string_view(argv[3]) != requirement ||
      std::string_view(argv[4]) != evidence_class ||
      std::string_view(argv[5]) != "--case-id" ||
      !is_case_identifier(argv[6]) ||
      std::string_view(argv[7]) != "--subject-sha256" ||
      !is_lower_hex_digest(argv[8])) {
    throw std::runtime_error("producer arguments");
  }
  return {argv[2], argv[6], argv[8]};
}

class Sha256 final {
public:
  void update(const std::span<const std::byte> input) noexcept {
    for (const std::byte value : input) {
      buffer_[buffer_size_++] = std::to_integer<std::uint8_t>(value);
      if (buffer_size_ == buffer_.size()) {
        transform();
        bit_count_ += 512U;
        buffer_size_ = 0U;
      }
    }
  }

  [[nodiscard]] std::array<std::byte, 32> finish() noexcept {
    const std::uint64_t total_bits = bit_count_ + buffer_size_ * 8U;
    buffer_[buffer_size_++] = 0x80U;
    if (buffer_size_ > 56U) {
      std::fill(buffer_.begin() + static_cast<std::ptrdiff_t>(buffer_size_),
                buffer_.end(), std::uint8_t{0});
      transform();
      buffer_size_ = 0U;
    }
    std::fill(buffer_.begin() + static_cast<std::ptrdiff_t>(buffer_size_),
              buffer_.begin() + 56, std::uint8_t{0});
    for (std::size_t index = 0U; index < 8U; ++index) {
      buffer_[63U - index] =
          static_cast<std::uint8_t>(total_bits >> (index * 8U));
    }
    transform();
    std::array<std::byte, 32> result{};
    for (std::size_t index = 0U; index < state_.size(); ++index) {
      for (std::size_t byte = 0U; byte < 4U; ++byte) {
        result[index * 4U + byte] =
            static_cast<std::byte>(state_[index] >> ((3U - byte) * 8U));
      }
    }
    return result;
  }

private:
  void transform() noexcept {
    static constexpr std::array<std::uint32_t, 64> constants{
        0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U, 0x3956c25bU,
        0x59f111f1U, 0x923f82a4U, 0xab1c5ed5U, 0xd807aa98U, 0x12835b01U,
        0x243185beU, 0x550c7dc3U, 0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U,
        0xc19bf174U, 0xe49b69c1U, 0xefbe4786U, 0x0fc19dc6U, 0x240ca1ccU,
        0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU, 0x983e5152U,
        0xa831c66dU, 0xb00327c8U, 0xbf597fc7U, 0xc6e00bf3U, 0xd5a79147U,
        0x06ca6351U, 0x14292967U, 0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU,
        0x53380d13U, 0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U,
        0xa2bfe8a1U, 0xa81a664bU, 0xc24b8b70U, 0xc76c51a3U, 0xd192e819U,
        0xd6990624U, 0xf40e3585U, 0x106aa070U, 0x19a4c116U, 0x1e376c08U,
        0x2748774cU, 0x34b0bcb5U, 0x391c0cb3U, 0x4ed8aa4aU, 0x5b9cca4fU,
        0x682e6ff3U, 0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U,
        0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U};
    std::array<std::uint32_t, 64> words{};
    for (std::size_t index = 0U; index < 16U; ++index) {
      words[index] =
          static_cast<std::uint32_t>(buffer_[index * 4U]) << 24U |
          static_cast<std::uint32_t>(buffer_[index * 4U + 1U]) << 16U |
          static_cast<std::uint32_t>(buffer_[index * 4U + 2U]) << 8U |
          static_cast<std::uint32_t>(buffer_[index * 4U + 3U]);
    }
    for (std::size_t index = 16U; index < words.size(); ++index) {
      const auto s0 = std::rotr(words[index - 15U], 7) ^
                      std::rotr(words[index - 15U], 18) ^
                      (words[index - 15U] >> 3U);
      const auto s1 = std::rotr(words[index - 2U], 17) ^
                      std::rotr(words[index - 2U], 19) ^
                      (words[index - 2U] >> 10U);
      words[index] = words[index - 16U] + s0 + words[index - 7U] + s1;
    }
    auto a = state_[0], b = state_[1], c = state_[2], d = state_[3],
         e = state_[4], f = state_[5], g = state_[6], h = state_[7];
    for (std::size_t index = 0U; index < words.size(); ++index) {
      const auto sum1 = std::rotr(e, 6) ^ std::rotr(e, 11) ^ std::rotr(e, 25);
      const auto choice = (e & f) ^ (~e & g);
      const auto temporary1 =
          h + sum1 + choice + constants[index] + words[index];
      const auto sum0 = std::rotr(a, 2) ^ std::rotr(a, 13) ^ std::rotr(a, 22);
      const auto majority = (a & b) ^ (a & c) ^ (b & c);
      const auto temporary2 = sum0 + majority;
      h = g;
      g = f;
      f = e;
      e = d + temporary1;
      d = c;
      c = b;
      b = a;
      a = temporary1 + temporary2;
    }
    state_[0] += a;
    state_[1] += b;
    state_[2] += c;
    state_[3] += d;
    state_[4] += e;
    state_[5] += f;
    state_[6] += g;
    state_[7] += h;
  }
  std::array<std::uint32_t, 8> state_{0x6a09e667U, 0xbb67ae85U, 0x3c6ef372U,
                                      0xa54ff53aU, 0x510e527fU, 0x9b05688cU,
                                      0x1f83d9abU, 0x5be0cd19U};
  std::array<std::uint8_t, 64> buffer_{};
  std::size_t buffer_size_ = 0U;
  std::uint64_t bit_count_ = 0U;
};

[[nodiscard]] inline std::string
hex_digest(const std::span<const std::byte> bytes) {
  Sha256 hasher;
  hasher.update(bytes);
  const auto digest = hasher.finish();
  constexpr std::string_view digits = "0123456789abcdef";
  std::string result;
  result.reserve(64U);
  for (const auto value : digest) {
    const auto octet = std::to_integer<unsigned>(value);
    result.push_back(digits[octet >> 4U]);
    result.push_back(digits[octet & 15U]);
  }
  return result;
}

[[nodiscard]] inline std::uint32_t
read_u32_le(const std::span<const std::byte> bytes, const std::size_t offset) {
  if (offset > bytes.size() || bytes.size() - offset < 4U)
    throw std::runtime_error("case truncated");
  return std::to_integer<std::uint32_t>(bytes[offset]) |
         std::to_integer<std::uint32_t>(bytes[offset + 1U]) << 8U |
         std::to_integer<std::uint32_t>(bytes[offset + 2U]) << 16U |
         std::to_integer<std::uint32_t>(bytes[offset + 3U]) << 24U;
}

[[nodiscard]] inline std::vector<std::byte>
read_paired_case(const PairedCaseFamily family,
                 const ProducerIdentity &identity) {
  std::ifstream stream("case-input.bin", std::ios::binary | std::ios::ate);
  if (!stream)
    throw std::runtime_error("case unavailable");
  const auto length = stream.tellg();
  if (length < 0 ||
      static_cast<std::uint64_t>(length) > kMaximumPairedCaseBytes)
    throw std::runtime_error("case size");
  std::vector<std::byte> bytes(static_cast<std::size_t>(length));
  stream.seekg(0);
  stream.read(reinterpret_cast<char *>(bytes.data()), length);
  if (!stream || bytes.size() < 20U ||
      !std::ranges::equal(std::span(bytes).first<8U>(), kPairedCaseMagic) ||
      read_u32_le(bytes, 8U) != 1U ||
      read_u32_le(bytes, 12U) != static_cast<std::uint32_t>(family) ||
      read_u32_le(bytes, 16U) != bytes.size() - 20U ||
      hex_digest(bytes) != identity.subject_sha256)
    throw std::runtime_error("case invalid");
  return {bytes.begin() + 20, bytes.end()};
}

inline int emit_envelope(const ProducerIdentity &identity,
                         const std::string_view observation) {
  const std::string envelope =
      "{\"execution_nonce\":\"" + identity.nonce +
      "\",\"observation\":" + std::string(observation) + "}";
  std::cout.write(envelope.data(),
                  static_cast<std::streamsize>(envelope.size()));
  return std::cout ? 0 : 1;
}

inline void write_artifact(const std::string_view name,
                           const std::span<const std::byte> bytes) {
  std::ofstream stream(std::string(name), std::ios::binary | std::ios::trunc);
  stream.write(reinterpret_cast<const char *>(bytes.data()),
               static_cast<std::streamsize>(bytes.size()));
  if (!stream)
    throw std::runtime_error("artifact write");
}

} // namespace jfg::evidence
