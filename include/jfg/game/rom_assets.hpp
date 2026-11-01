#pragma once
#include <cstdint>
#include <span>
#include <stdexcept>
#include <string_view>
namespace jfg::game {
// ROM coordinates are never guest RAM addresses. The selected executable
// composes these operands from hash-qualified original PI initialization code.
struct RomAssetDirectory { std::string_view revision; std::uint32_t table, data; };
constexpr std::uint32_t rom_address_operand(std::uint32_t high,std::uint32_t low) {
  if(high>>26U!=15U || ((high>>21U)&31U)!=0U || ((high>>16U)&31U)==0U ||
     low>>26U!=9U || ((low>>21U)&31U)!=((high>>16U)&31U))
    throw "Invalid original ROM-address operand";
  return ((high&0xFFFFU)<<16U)+static_cast<std::int16_t>(low&0xFFFFU);
}
class RomAssetView {
  std::span<const std::uint8_t> rom_;
  RomAssetDirectory directory_;
  std::uint32_t count_{};
  std::uint32_t word(std::size_t offset) const {
    if(offset>rom_.size() || rom_.size()-offset<4U)throw std::runtime_error("Short ROM asset directory");
    return (std::uint32_t(rom_[offset])<<24U)|(std::uint32_t(rom_[offset+1U])<<16U)|
      (std::uint32_t(rom_[offset+2U])<<8U)|rom_[offset+3U];
  }
public:
  RomAssetView(std::span<const std::uint8_t> rom,RomAssetDirectory directory,
      std::string_view revision):rom_(rom),directory_(directory) {
    if(revision.empty() || revision!=directory.revision || directory.table%4U ||
       directory.table>=directory.data || directory.data>rom.size())
      throw std::runtime_error("ROM asset directory belongs to a different or invalid image");
    // The original table stores 71 sections, then 72 offsets and alignment padding.
    // The original loader permits the terminal index; this checked host view
    // excludes it because its following word is padding, not an end offset.
    count_=word(directory.table);
    if(count_==0U || count_>4095U || std::uint64_t(directory.table)+4ULL*(count_+2U)>directory.data)
      throw std::runtime_error("ROM asset directory exceeds its declared table");
    std::uint32_t previous=0;
    for(std::uint32_t i=0;i<=count_;++i) {
      const auto offset=word(std::size_t(directory.table)+4U*(i+1U));
      if(offset<previous || offset>rom.size()-directory.data)
        throw std::runtime_error("ROM asset section leaves its image");
      previous=offset;
    }
  }
  std::span<const std::uint8_t> section(std::uint32_t index) const {
    if(index>=count_)throw std::runtime_error("ROM asset index is unavailable");
    const auto first=word(std::size_t(directory_.table)+4U*(index+1U));
    const auto last=word(std::size_t(directory_.table)+4U*(index+2U));
    return rom_.subspan(std::size_t(directory_.data)+first,last-first);
  }
};
} // namespace jfg::game
