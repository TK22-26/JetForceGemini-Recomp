#pragma once
#include <atomic>
#include <filesystem>
#include <fstream>
#include <optional>
#include <string>
#include <string_view>
namespace jfg {
enum class ShadowQuality { original, enhanced };
inline std::atomic<ShadowQuality>& shadow_quality_preference() {
  static std::atomic<ShadowQuality> value{ShadowQuality::original};return value;
}
inline void configure_shadow_quality(ShadowQuality value) noexcept {
  shadow_quality_preference().store(value,std::memory_order_relaxed);
}
inline std::string serialize_shadow_quality(ShadowQuality value) {
  return std::string("version=1\nshadow_quality=")+(value==ShadowQuality::enhanced?"enhanced\n":"original\n");
}
inline std::optional<ShadowQuality> parse_shadow_quality(std::string_view text) {
  if(text.size()>1024)return std::nullopt;
  unsigned seen=0;ShadowQuality result=ShadowQuality::original;
  while(!text.empty()) {
    const auto end=text.find('\n');auto line=text.substr(0,end);
    text=end==std::string_view::npos?std::string_view{}:text.substr(end+1);
    if(!line.empty() && line.back()=='\r')line.remove_suffix(1);
    if(line.empty())continue;
    if(line=="version=1") {if(seen&1)return std::nullopt;seen|=1;}
    else if(line=="shadow_quality=original" || line=="shadow_quality=enhanced") {
      if(seen&2)return std::nullopt;
      seen|=2;
      result=line=="shadow_quality=enhanced"?ShadowQuality::enhanced:ShadowQuality::original;
    } else return std::nullopt;
  }
  return seen==3?std::optional<ShadowQuality>(result):std::nullopt;
}
inline std::optional<ShadowQuality> load_shadow_quality(const std::filesystem::path& profile) {
  if(profile.empty())return ShadowQuality::original;
  const auto path=profile/"shadows.ini";std::error_code ec;
  const bool exists=std::filesystem::exists(path,ec);
  if(ec)return std::nullopt;
  if(!exists)return ShadowQuality::original;
  std::ifstream file(path,std::ios::binary|std::ios::ate);
  if(!file || file.tellg()<0 || file.tellg()>1024)return std::nullopt;
  const auto size=static_cast<std::size_t>(file.tellg());file.seekg(0);
  std::string text(size,'\0');
  if(size&&!file.read(text.data(),static_cast<std::streamsize>(size)))return std::nullopt;
  return parse_shadow_quality(text);
}
}
