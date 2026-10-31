#pragma once
#include "jfg/runtime/controller_device_key.hpp"
#include <set>
#include <string>
#include <string_view>
#include <utility>

namespace jfg {
// Explicit Remove suppresses automatic reuse, without reserving the controller
// against an explicit Add. XInput keeps its existing 0..3 slot identity; SDL
// persists the same stable key as controller mappings, never a catalog index.
inline bool valid_controller_assignment_key(std::string_view key) {
  return valid_controller_device_key(key) ||
      (key.size() == 8 && key.starts_with("xinput:") && key[7] >= '0' && key[7] <= '3');
}
struct ControllerAutoAssignmentPolicy {
  static constexpr std::size_t max_excluded = 64;
  std::set<std::string, std::less<>> excluded;
  bool set_excluded(std::string_view key, bool remove) {
    if (!valid_controller_assignment_key(key)) return false;
    if (!remove) { excluded.erase(std::string(key)); return true; }
    if (excluded.contains(key)) return true;
    if (excluded.size() == max_excluded) return false;
    excluded.emplace(key);
    return true;
  }
};
inline bool parse_controller_auto_assignment(std::string_view text,
                                            ControllerAutoAssignmentPolicy& result) {
  if (text.empty() || text.size() > 8192) return false;
  ControllerAutoAssignmentPolicy candidate;
  bool version = false;
  while (!text.empty()) {
    const auto end = text.find('\n');
    auto line = text.substr(0, end);
    text = end == std::string_view::npos ? std::string_view{} : text.substr(end + 1);
    if (!line.empty() && line.back() == '\r') line.remove_suffix(1);
    if (line == "version=1" && !version) { version = true; continue; }
    if (!line.starts_with("exclude=")) return false;
    const auto key = line.substr(8);
    if (candidate.excluded.contains(key) || !candidate.set_excluded(key, true)) return false;
  }
  if (!version) return false;
  result = std::move(candidate);
  return true;
}
inline std::string serialize_controller_auto_assignment(const ControllerAutoAssignmentPolicy& policy) {
  std::string text = "version=1\n";
  for (const auto& key : policy.excluded) text += "exclude=" + key + "\n";
  return text;
}
} // namespace jfg
