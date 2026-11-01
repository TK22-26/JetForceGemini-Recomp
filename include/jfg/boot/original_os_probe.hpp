#pragma once
#include <array>
#include <charconv>
#include <cstdint>
#include <limits>
#include <optional>
#include <regex>
#include <string>
#include <string_view>
#include <utility>
namespace jfg::boot {
// A bounded diagnostic observation, never a gameplay or full-snapshot claim.
struct OriginalOsProbe {
  std::uint32_t retrace_target{}, poll_target{};
  std::uint64_t vi_retraces{}, controller_samples{}, completed_updates{}, cpu_count{},
      instructions{}, graphics_tasks{}, decoded_audio_tasks{};
  std::string state_hash;
};
inline bool valid_original_os_probe(const OriginalOsProbe& value,
    std::uint32_t requested_retraces, std::uint32_t requested_polls) {
  if(value.cpu_count==0 || value.instructions==0 || value.state_hash.size()!=64 ||
     value.state_hash.find_first_not_of("0123456789abcdef")!=std::string::npos ||
     value.poll_target!=requested_polls)return false;
  if(requested_polls!=0)
    return value.retrace_target==(std::numeric_limits<std::uint32_t>::max)() &&
        value.controller_samples==requested_polls;
  return requested_retraces>=3 && value.retrace_target==requested_retraces &&
      value.vi_retraces==requested_retraces;
}
inline std::string original_os_probe_json(const OriginalOsProbe& value) {
  if(!valid_original_os_probe(value,value.retrace_target,value.poll_target))return {};
  std::string result="{\"kind\":\"jfg-phase9-original-os-probe\",\"acceptance\":false,\"status\":\"";
  result+=value.poll_target?"poll-target":"retrace-target";
  result+="\",\"poll_target\":"+std::to_string(value.poll_target);
  result+=",\"retrace_target\":"+std::to_string(value.retrace_target);
  const std::array<std::pair<std::string_view,std::uint64_t>,7> fields{{
    {"vi_retraces",value.vi_retraces},{"controller_samples",value.controller_samples},
    {"completed_updates",value.completed_updates},{"cpu_count",value.cpu_count},
    {"instructions",value.instructions},{"graphics_tasks",value.graphics_tasks},
    {"decoded_audio_tasks",value.decoded_audio_tasks}}};
  for(const auto& [name,number]:fields)result+=",\""+std::string(name)+"\":"+std::to_string(number);
  result+=",\"unsupported_accesses\":0,\"runtime_snapshot_complete\":false,\"state_hash\":\""+value.state_hash+"\"}\n";
  return result;
}
inline std::optional<OriginalOsProbe> parse_original_os_probe(std::string_view output,
    std::uint32_t requested_retraces, std::uint32_t requested_polls) {
  // Bound regex work and require the exact diagnostic contract and stop boundary.
  if(output.size()>2048)return std::nullopt;
  static const std::regex pattern(R"jfg(\{"kind":"jfg-phase9-original-os-probe","acceptance":false,"status":"(retrace-target|poll-target)","poll_target":([0-9]+),"retrace_target":([0-9]+),"vi_retraces":([0-9]+),"controller_samples":([0-9]+),"completed_updates":([0-9]+),"cpu_count":([0-9]+),"instructions":([0-9]+),"graphics_tasks":([0-9]+),"decoded_audio_tasks":([0-9]+),"unsupported_accesses":0,"runtime_snapshot_complete":false,"state_hash":"([0-9a-f]{64})"\}\r?\n)jfg");
  const std::string text(output);std::smatch match;
  if(!std::regex_match(text,match,pattern))return std::nullopt;
  OriginalOsProbe value;
  auto number=[&](std::size_t index,auto& destination) {
    const auto field=match[index].str();
    const auto parsed=std::from_chars(field.data(),field.data()+field.size(),destination);
    return parsed.ec==std::errc{} && parsed.ptr==field.data()+field.size();
  };
  if(!number(2,value.poll_target)||!number(3,value.retrace_target)||!number(4,value.vi_retraces)||
     !number(5,value.controller_samples)||!number(6,value.completed_updates)||!number(7,value.cpu_count)||
     !number(8,value.instructions)||!number(9,value.graphics_tasks)||!number(10,value.decoded_audio_tasks))return std::nullopt;
  value.state_hash=match[11].str();
  if(match[1].str()!=(requested_polls?"poll-target":"retrace-target") ||
     !valid_original_os_probe(value,requested_retraces,requested_polls))return std::nullopt;
  auto canonical=text;
  if(canonical.size()>1 && canonical[canonical.size()-2]=='\r')canonical.erase(canonical.size()-2,1);
  if(original_os_probe_json(value)!=canonical)return std::nullopt;
  return value;
}
} // namespace jfg::boot
