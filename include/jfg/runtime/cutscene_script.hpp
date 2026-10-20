#pragma once
#include <array>
#include <cstdint>
#include <span>
#include <vector>

namespace jfg {
enum class CutsceneScriptStatus {
  finite, truncated, unsupported_command, non_monotonic_time,
  pause_gate, loop, command_limit
};
struct CutsceneScriptCommand {
  std::uint16_t time=0, word=0;
  std::array<std::uint16_t,5> payload{};
  std::uint8_t payload_count=0;
  std::uint32_t offset=0;
};
struct CutsceneScriptInspection {
  CutsceneScriptStatus status=CutsceneScriptStatus::truncated;
  std::vector<CutsceneScriptCommand> commands;
  // These are evidence for an explicit completion contract, never permission
  // to skip. Actor callbacks and level initialization may also change progress.
  bool changes_level=false, conditional_end=false, writes_game_flags=false;
};
constexpr unsigned cutscene_command_size(unsigned opcode) noexcept {
  switch(opcode) {
   case 0x00:case 0x01:case 0x02:case 0x03:case 0x04:case 0x05:
   case 0x09:case 0x0A:case 0x21:case 0x23:case 0x24:case 0x26:
   case 0x28:case 0x2A:case 0x41:case 0x42:case 0x64:case 0x65:
   case 0x74:case 0x75:case 0x76:case 0x77:case 0x7B:case 0x7C:
   case 0x7D:return 4;
   case 0x06:case 0x07:case 0x20:case 0x22:case 0x25:case 0x27:
   case 0x29:case 0x2B:case 0x43:case 0x46:case 0x4B:case 0x61:
   case 0x66:case 0x67:case 0x6C:case 0x78:case 0x79:case 0x7A:return 6;
   case 0x08:case 0x48:case 0x4A:case 0x62:case 0x63:case 0x68:
   case 0x69:case 0x6F:return 8;
   case 0x47:case 0x60:return 10;
   case 0x40:case 0x44:case 0x45:case 0x49:case 0x6A:case 0x6B:
   case 0x6D:return 12;
   case 0x4C:case 0x4D:case 0x6E:return 14;
   default:return 0;
  }
}
// Immutable, big-endian command bytes from the original US sequence asset.
// Inspects at most 2,048 commands and performs no game writes or calls.
inline CutsceneScriptInspection inspect_cutscene_script(std::span<const std::uint8_t> bytes) {
  CutsceneScriptInspection result;
  unsigned offset=0, previous=0;
  const auto u16=[&](unsigned p) {
    return static_cast<std::uint16_t>((unsigned{bytes[p]}<<8)|bytes[p+1]);
  };
  for(unsigned n=0;n<2048;++n) {
    if(offset>bytes.size() || bytes.size()-offset<4)return result;
    CutsceneScriptCommand command;
    command.offset=offset;command.time=u16(offset);command.word=u16(offset+2);
    if(command.word==0x7F00) {
      result.commands.push_back(command);
      result.status=CutsceneScriptStatus::finite;return result;
    }
    if(command.time<previous) {
      result.status=CutsceneScriptStatus::non_monotonic_time;return result;
    }
    previous=command.time;
    const unsigned op=command.word>>8;
    if(op==0x7E){result.status=CutsceneScriptStatus::loop;return result;}
    if(op==0x7B){result.status=CutsceneScriptStatus::pause_gate;return result;}
    const unsigned size=cutscene_command_size(op);
    if(!size){result.status=CutsceneScriptStatus::unsupported_command;return result;}
    if(bytes.size()-offset<size)return result;
    command.payload_count=static_cast<std::uint8_t>(size/2-2);
    for(unsigned p=0;p<command.payload_count;++p)command.payload[p]=u16(offset+4+2*p);
    result.changes_level|=op==0x7A;result.conditional_end|=op==0x77;
    result.writes_game_flags|=op==0x78;
    result.commands.push_back(command);offset+=size;
  }
  result.status=CutsceneScriptStatus::command_limit;
  return result;
}
} // namespace jfg
