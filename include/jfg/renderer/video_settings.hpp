#pragma once
#include "blur_settings.hpp"
#include <charconv>
#include <filesystem>
#include <fstream>
#include <optional>
#include <string>
#include <string_view>

namespace jfg {
enum class FrameRateMode { original, custom, unlimited };
struct VideoSettings {
  FrameRateMode mode = FrameRateMode::original;
  unsigned fps = 60;
  bool vsync = true;
  BlurMode blur = BlurMode::reduced;
  unsigned fog_percent = 100;
};
inline bool valid_video_settings(const VideoSettings &settings) {
  return (settings.mode == FrameRateMode::original ||
          settings.mode == FrameRateMode::custom ||
          settings.mode == FrameRateMode::unlimited) &&
         settings.fps >= 60 && settings.fps <= 1000 && valid_blur_mode(settings.blur) && settings.fog_percent <= 100;
}
inline std::optional<unsigned> parse_video_fps(std::string_view text) {
  if (text.empty())
    return std::nullopt;
  unsigned value = 0;
  const auto result =
      std::from_chars(text.data(), text.data() + text.size(), value);
  if (result.ec != std::errc{} || result.ptr != text.data() + text.size() ||
      value < 60 || value > 1000)
    return std::nullopt;
  return value;
}
inline std::optional<VideoSettings>
parse_video_settings(std::string_view text) {
  if (text.size() > 4096)
    return std::nullopt;
  VideoSettings result;
  unsigned seen = 0;
  while (!text.empty()) {
    const auto end = text.find('\n');
    auto line = text.substr(0, end);
    text = end == std::string_view::npos ? std::string_view{}
                                         : text.substr(end + 1);
    if (!line.empty() && line.back() == '\r')
      line.remove_suffix(1);
    if (line.empty() || line.front() == '#')
      continue;
    const auto equal = line.find('=');
    if (equal == std::string_view::npos)
      return std::nullopt;
    const auto key = line.substr(0, equal), value = line.substr(equal + 1);
    unsigned bit = 0;
    if (key == "version") {
      bit = 1;
      if (value != "1")
        return std::nullopt;
    } else if (key == "mode") {
      bit = 2;
      if (value == "original")
        result.mode = FrameRateMode::original;
      else if (value == "custom")
        result.mode = FrameRateMode::custom;
      else if (value == "unlimited")
        result.mode = FrameRateMode::unlimited;
      else
        return std::nullopt;
    } else if (key == "fps") {
      bit = 4;
      const auto fps = parse_video_fps(value);
      if (!fps)
        return std::nullopt;
      result.fps = *fps;
    } else if (key == "vsync") {
      bit = 8;
      if (value != "0" && value != "1")
        return std::nullopt;
      result.vsync = value == "1";
    } else if (key == "blur") {
      bit = 16;
      if (value == "off") result.blur = BlurMode::off;
      else if (value == "reduced") result.blur = BlurMode::reduced;
      else if (value == "original") result.blur = BlurMode::original;
      else return std::nullopt;
    } else if (key == "remove_fog") {
      bit = 32;
      if (value != "0" && value != "1") return std::nullopt;
      result.fog_percent = value == "1" ? 0 : 100;
    } else if (key == "fog_percent") {
      bit = 32;
      unsigned n=0; const auto parsed=std::from_chars(value.data(),value.data()+value.size(),n);
      if(value.empty() || parsed.ec!=std::errc{} || parsed.ptr!=value.data()+value.size() || n>100) return std::nullopt;
      result.fog_percent=n;
    } else
      return std::nullopt;
    if (seen & bit)
      return std::nullopt;
    seen |= bit;
  }
  // Existing v1 files omit blur and migrate to the owner-selected Reduced default.
  return ((seen & 15U) == 15U) ? std::optional<VideoSettings>(result) : std::nullopt;
}
inline std::string serialize_video_settings(const VideoSettings &settings) {
  const char *mode = settings.mode == FrameRateMode::custom      ? "custom"
                     : settings.mode == FrameRateMode::unlimited ? "unlimited"
                                                                 : "original";
  const char *blur = settings.blur == BlurMode::off ? "off" :
                     settings.blur == BlurMode::original ? "original" : "reduced";
  return std::string("version=1\nmode=") + mode +
         "\nfps=" + std::to_string(settings.fps) +
         "\nvsync=" + (settings.vsync ? "1\n" : "0\n") + "blur=" + blur + "\nfog_percent=" + std::to_string(settings.fog_percent) + "\n";
}
// Missing configuration uses the original rendering mode. Corrupt or unreadable
// configuration is reported to the caller rather than silently changing modes.
inline std::optional<VideoSettings>
load_video_settings(const std::filesystem::path &path) {
  if (path.empty())
    return VideoSettings{};
  std::error_code error;
  const bool exists = std::filesystem::exists(path, error);
  if (error)
    return std::nullopt;
  if (!exists)
    return VideoSettings{};
  std::ifstream file(path, std::ios::binary | std::ios::ate);
  if (!file || file.tellg() < 0 || file.tellg() > 4096)
    return std::nullopt;
  const auto size = static_cast<std::size_t>(file.tellg());
  file.seekg(0);
  std::string text(size, '\0');
  if (size && !file.read(text.data(), static_cast<std::streamsize>(size)))
    return std::nullopt;
  return parse_video_settings(text);
}
} // namespace jfg
