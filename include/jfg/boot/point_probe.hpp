#pragma once

#include <algorithm>
#include <charconv>
#include <cstdint>
#include <optional>
#include <string_view>
#include <vector>

namespace jfg::boot {
// Diagnostic reads only: canonical 4 MiB KSEG0 words, never device registers.
inline std::optional<std::vector<std::uint32_t>> point_probe_addresses(
    std::string_view text) {
  std::vector<std::uint32_t> result;
  if (text.empty()) return result;
  while (!text.empty()) {
    const auto comma = text.find(',');
    const auto item = text.substr(0, comma);
    std::uint32_t address = 0;
    if (item.size() != 10 || !item.starts_with("0x")) return std::nullopt;
    const auto parsed = std::from_chars(item.data() + 2, item.data() + item.size(), address, 16);
    if (parsed.ec != std::errc{} || parsed.ptr != item.data() + item.size() ||
        address < 0x80000000U || address > 0x803ffffcU || address % 4U != 0U ||
        result.size() == 16U || std::find(result.begin(), result.end(), address) != result.end())
      return std::nullopt;
    result.push_back(address);
    if (comma == std::string_view::npos) break;
    text.remove_prefix(comma + 1);
    if (text.empty()) return std::nullopt;
  }
  return result;
}
} // namespace jfg::boot
