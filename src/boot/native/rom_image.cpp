#include "runtime_services.hpp"
namespace jfg::boot::native::detail {
bool range(std::uint64_t offset, std::uint64_t bytes, std::size_t limit) {
  return offset <= limit && bytes <= limit - offset;
}
bool write_boot_word(std::vector<std::uint8_t> &bytes, std::uint32_t address,
                     std::uint32_t value) {
  if (address < kKseg0 || !range(address - kKseg0, 4U, bytes.size()))
    return false;
  const std::size_t offset = address - kKseg0;
  bytes[offset] = static_cast<std::uint8_t>(value >> 24U);
  bytes[offset + 1U] = static_cast<std::uint8_t>(value >> 16U);
  bytes[offset + 2U] = static_cast<std::uint8_t>(value >> 8U);
  bytes[offset + 3U] = static_cast<std::uint8_t>(value);
  return true;
}
bool initialize_ipl_state(std::vector<std::uint8_t> &bytes,
                          std::span<const std::uint8_t> rom) {
  // Documented libultra boot globals populated by the IPL before the ROM
  // entry point. This runner admits the USA image, so the TV mode is NTSC;
  // it models a cold cartridge boot with the oracle-observed 4 MiB RDRAM.
  return initialize_6105_handoff(bytes, rom) &&
         write_boot_word(bytes, 0x80000300U, 1U) &&
         write_boot_word(bytes, 0x80000304U, 0U) &&
         write_boot_word(bytes, 0x80000308U, 0xB0000000U) &&
         write_boot_word(bytes, 0x8000030CU, 0U) &&
         write_boot_word(bytes, 0x80000318U,
                         static_cast<std::uint32_t>(kRdramSize));
}
bool load_static_sections(const std::vector<std::uint8_t> &rom,
                          std::vector<std::uint8_t> &bytes) {
  const std::size_t count = jfg_generated_section_count();
  for (std::size_t index = 0U; index < count; ++index) {
    JfgGeneratedSectionMetadata metadata{};
    if (jfg_generated_section_metadata(static_cast<std::uint32_t>(index),
                                       &metadata) == 0 ||
        metadata.is_overlay > 1U)
      return false;
    if (metadata.is_overlay == 1U)
      continue;
    if (metadata.linked_vram < kKseg0 || (metadata.linked_vram & 3U) != 0U ||
        (metadata.rom_start & 3U) != 0U ||
        metadata.text_rom_offset > metadata.text_size)
      return false;
    const std::uint64_t copy =
        std::uint64_t(metadata.text_size) + metadata.data_size;
    const std::uint64_t total = copy + metadata.bss_size;
    const std::uint64_t destination = metadata.linked_vram - kKseg0;
    if (!range(metadata.rom_start, copy, rom.size()) ||
        !range(destination, total, bytes.size()))
      return false;
    std::memcpy(bytes.data() + destination, rom.data() + metadata.rom_start,
                static_cast<std::size_t>(copy));
    std::memset(bytes.data() + destination + copy, 0, metadata.bss_size);
  }
  return true;
}



std::array<std::uint8_t, 20U> sha1(std::span<const std::uint8_t> input) {
  std::array<std::uint32_t, 5U> hash = {0x67452301U, 0xefcdab89U, 0x98badcfeU,
                                        0x10325476U, 0xc3d2e1f0U};
  std::vector<std::uint8_t> padded(input.begin(), input.end());
  padded.push_back(0x80U);
  while ((padded.size() % 64U) != 56U)
    padded.push_back(0U);
  const std::uint64_t bits = static_cast<std::uint64_t>(input.size()) * 8U;
  for (int shift = 56; shift >= 0; shift -= 8)
    padded.push_back(static_cast<std::uint8_t>(bits >> shift));
  for (std::size_t block = 0U; block < padded.size(); block += 64U) {
    std::array<std::uint32_t, 80U> words{};
    for (std::size_t index = 0U; index < 16U; ++index)
      words[index] = (std::uint32_t(padded[block + index * 4U]) << 24U) |
                     (std::uint32_t(padded[block + index * 4U + 1U]) << 16U) |
                     (std::uint32_t(padded[block + index * 4U + 2U]) << 8U) |
                     padded[block + index * 4U + 3U];
    for (std::size_t index = 16U; index < words.size(); ++index)
      words[index] = std::rotl(words[index - 3U] ^ words[index - 8U] ^
                                   words[index - 14U] ^ words[index - 16U],
                               1);
    auto [a, b, c, d, e] = hash;
    for (std::size_t index = 0U; index < words.size(); ++index) {
      const std::uint32_t f = index < 20U   ? ((b & c) | (~b & d))
                              : index < 40U ? (b ^ c ^ d)
                              : index < 60U ? ((b & c) | (b & d) | (c & d))
                                            : (b ^ c ^ d);
      const std::uint32_t k = index < 20U   ? 0x5a827999U
                              : index < 40U ? 0x6ed9eba1U
                              : index < 60U ? 0x8f1bbcdcU
                                            : 0xca62c1d6U;
      const std::uint32_t next = std::rotl(a, 5) + f + e + k + words[index];
      e = d;
      d = c;
      c = std::rotl(b, 30);
      b = a;
      a = next;
    }
    hash[0] += a;
    hash[1] += b;
    hash[2] += c;
    hash[3] += d;
    hash[4] += e;
  }
  std::array<std::uint8_t, 20U> result{};
  for (std::size_t index = 0U; index < hash.size(); ++index)
    for (std::size_t byte = 0U; byte < 4U; ++byte)
      result[index * 4U + byte] =
          static_cast<std::uint8_t>(hash[index] >> (24U - byte * 8U));
  return result;
}


bool read_supported_rom(const char *path, std::vector<std::uint8_t> &rom) {
  std::ifstream input(path, std::ios::binary | std::ios::ate);
  if (!input || input.tellg() != static_cast<std::streamoff>(kRomSize))
    return false;
  input.seekg(0);
  rom.resize(kRomSize);
  return input.read(reinterpret_cast<char *>(rom.data()),
                    static_cast<std::streamsize>(rom.size())) &&
         sha1(rom) == kSupportedRomSha1;
}


} // namespace jfg::boot::native::detail
