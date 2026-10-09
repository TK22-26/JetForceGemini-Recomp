#pragma once
#include <algorithm>
#include <cstddef>
#include <cstring>
#include <span>
namespace jfg {
inline void copy_changed_snapshot_bytes(const std::span<const std::byte> source,
                                        const std::span<std::byte> destination) noexcept {
  if(source.data()==destination.data())return;
  constexpr std::size_t chunk=4096U;
  for(std::size_t offset=0;offset<source.size();offset+=chunk) {
    const auto count=(std::min)(chunk,source.size()-offset);
    if(std::memcmp(source.data()+offset,destination.data()+offset,count)!=0)
      std::memcpy(destination.data()+offset,source.data()+offset,count);
  }
}
}
