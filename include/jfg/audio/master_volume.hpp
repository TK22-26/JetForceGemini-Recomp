#pragma once
#include <algorithm>
#include <array>
#include <bit>
#include <charconv>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <optional>
#include <span>
#include <string_view>
namespace jfg::audio {
struct VolumeSettings {
  unsigned percent = 100;
  bool muted = false;
};
inline std::optional<VolumeSettings> parse_volume(std::string_view text) {
  if (text.size() > 128U)
    return std::nullopt;
  std::array<std::string_view, 3> lines{};
  for (auto &line : lines) {
    const auto end = text.find('\n');
    if (end == std::string_view::npos)
      return std::nullopt;
    line = text.substr(0, end);
    if (!line.empty() && line.back() == '\r')
      line.remove_suffix(1);
    text.remove_prefix(end + 1U);
  }
  if (!text.empty() || lines[0] != "version=1" ||
      !lines[1].starts_with("volume=") ||
      (lines[2] != "muted=0" && lines[2] != "muted=1"))
    return std::nullopt;
  const auto number = lines[1].substr(7);
  if (number.empty())
    return std::nullopt;
  unsigned percent = 0;
  const auto parsed =
      std::from_chars(number.data(), number.data() + number.size(), percent);
  if ((number.size() > 1U && number.front() == '0') ||
      parsed.ec != std::errc{} || parsed.ptr != number.data() + number.size() ||
      percent > 100U)
    return std::nullopt;
  return VolumeSettings{percent, lines[2] == "muted=1"};
}
inline std::optional<VolumeSettings>
read_volume(const std::filesystem::path &path) {
  std::ifstream in(path, std::ios::binary);
  if (!in)
    return std::nullopt;
  std::array<char, 129> buffer{};
  in.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
  const auto count = in.gcount();
  if (in.bad() || count > 128)
    return std::nullopt;
  return parse_volume(
      std::string_view(buffer.data(), static_cast<std::size_t>(count)));
}
// Final stereo PCM gain only: guest clocks and queue sizes are unchanged.
// Five-ms ramps avoid discontinuities when changing volume during playback.
class MasterVolume {
  std::int32_t current_ = 65536, target_ = 65536;
  unsigned remaining_ = 0;

public:
  void configure(VolumeSettings settings, unsigned frequency,
                 bool initial = false) noexcept {
    const auto target =
        settings.muted
            ? 0
            : static_cast<std::int32_t>((std::min)(settings.percent, 100U) *
                                        65536U / 100U);
    if (initial) {
      current_ = target_ = target;
      remaining_ = 0;
      return;
    }
    if (target == target_)
      return;
    target_ = target;
    remaining_ = (std::max)(1U, frequency / 200U);
  }
  void apply(std::span<std::uint8_t> pcm) noexcept {
    if (current_ == 65536 && target_ == 65536)
      return;
    for (std::size_t i = 0; i + 3U < pcm.size(); i += 4U) {
      if (remaining_ != 0U) {
        current_ +=
            (target_ - current_) / static_cast<std::int32_t>(remaining_);
        --remaining_;
      }
      for (unsigned channel = 0; channel < 2U; ++channel) {
        const auto at = i + channel * 2U;
        const auto raw = static_cast<std::uint16_t>(
            pcm[at] | (static_cast<unsigned>(pcm[at + 1U]) << 8U));
        const auto sample = std::bit_cast<std::int16_t>(raw);
        const auto scaled = static_cast<std::int16_t>(
            static_cast<std::int64_t>(sample) * current_ / 65536);
        const auto output = std::bit_cast<std::uint16_t>(scaled);
        pcm[at] = static_cast<std::uint8_t>(output);
        pcm[at + 1U] = static_cast<std::uint8_t>(output >> 8U);
      }
    }
  }
};
} // namespace jfg::audio
