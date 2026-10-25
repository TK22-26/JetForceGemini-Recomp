#pragma once
#include <atomic>
#include <filesystem>
#include <fstream>
#include <optional>
#include <string>
#include <string_view>
namespace jfg {
enum class ActorLod { original, high };
inline std::atomic<ActorLod>& actor_lod_preference() {
  static std::atomic<ActorLod> value{ActorLod::original};return value;
}
inline void configure_actor_lod(ActorLod value) noexcept {
  actor_lod_preference().store(value,std::memory_order_relaxed);
}
inline std::string serialize_actor_lod(ActorLod value) {
  return std::string("version=1\nactor_lod=")+(value==ActorLod::high?"high\n":"original\n");
}
inline std::optional<ActorLod> parse_actor_lod(std::string_view text) {
  if(text.size()>1024)return std::nullopt;
  unsigned seen=0;ActorLod result=ActorLod::original;
  while(!text.empty()) {
    const auto end=text.find('\n');auto line=text.substr(0,end);
    text=end==std::string_view::npos?std::string_view{}:text.substr(end+1);
    if(!line.empty() && line.back()=='\r')line.remove_suffix(1);
    if(line.empty())continue;
    if(line=="version=1") {if(seen&1)return std::nullopt;seen|=1;}
    else if(line=="actor_lod=original" || line=="actor_lod=high") {
      if(seen&2)return std::nullopt;seen|=2;
      result=line=="actor_lod=high"?ActorLod::high:ActorLod::original;
    } else return std::nullopt;
  }
  return seen==3?std::optional<ActorLod>(result):std::nullopt;
}
inline std::optional<ActorLod> load_actor_lod(const std::filesystem::path& profile) {
  if(profile.empty())return ActorLod::original;
  const auto path=profile/"game-settings.ini";std::error_code ec;
  const bool exists=std::filesystem::exists(path,ec);
  if(ec)return std::nullopt;if(!exists)return ActorLod::original;
  std::ifstream file(path,std::ios::binary|std::ios::ate);
  if(!file || file.tellg()<0 || file.tellg()>1024)return std::nullopt;
  const auto size=static_cast<std::size_t>(file.tellg());file.seekg(0);
  std::string text(size,'\0');
  if(size&&!file.read(text.data(),static_cast<std::streamsize>(size)))return std::nullopt;
  return parse_actor_lod(text);
}
}
