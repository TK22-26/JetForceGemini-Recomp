#pragma once
#include <algorithm>
#include <cstddef>
#include <cstring>
#include <span>
#include <vector>
namespace jfg {
template<class Changed>
inline void copy_changed_snapshot_bytes(const std::span<const std::byte> source,
                                        const std::span<std::byte> destination, Changed&& changed) {
  if(source.data()==destination.data())return;
  constexpr std::size_t chunk=4096U;
  for(std::size_t offset=0;offset<source.size();offset+=chunk) {
    const auto count=(std::min)(chunk,source.size()-offset);
    if(std::memcmp(source.data()+offset,destination.data()+offset,count)!=0) {
      std::memcpy(destination.data()+offset,source.data()+offset,count);
      changed(offset,count);
    }
  }
}
// Restore only ranges changed in a cached expanded overlay image. Writable
// bytes of an active module remain cached, and their dirty ownership carries
// forward even when this task does not change them. If the module becomes
// inactive, those retained bytes are restored to the immutable ROM baseline.
template<class Range, class Changed>
inline bool restore_overlay_snapshot_ranges(std::span<const std::byte> initial,
    std::span<std::byte> destination, std::size_t initial_base,
    std::size_t begin, std::size_t restore_end, std::size_t end,
    std::span<const Range> dirty, std::vector<Range>& retained, Changed&& changed) {
  if (initial_base > destination.size() || initial.size() != destination.size()-initial_base ||
      begin < initial_base || begin > restore_end || restore_end > end || end > destination.size()) return false;
  for (const auto range : dirty)
    if (range.begin < initial_base || range.begin > range.end || range.end > destination.size()) return false;
  for (const auto range : dirty) {
    const auto lo=(std::max)(begin,range.begin), hi=(std::min)(end,range.end);
    if (lo >= hi) continue;
    const auto stop=(std::min)(hi,restore_end);
    if (lo < stop) copy_changed_snapshot_bytes(initial.subspan(lo-initial_base,stop-lo),
        destination.subspan(lo,stop-lo),[&](std::size_t offset,std::size_t count) { changed(lo+offset,count); });
    const auto keep=(std::max)(lo,restore_end);
    if (keep < hi) retained.push_back({keep,hi});
  }
  return true;
}
inline void copy_changed_snapshot_bytes(const std::span<const std::byte> source,
                                        const std::span<std::byte> destination) noexcept {
  copy_changed_snapshot_bytes(source,destination,[](std::size_t,std::size_t) noexcept {});
}
} // namespace jfg
