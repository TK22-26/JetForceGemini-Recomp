#include "generated_overlay_table.hpp"
#include "funcs.h"
#include "generated_lookup_entry.h"
namespace jfg::boot::native::detail {
std::size_t GeneratedOverlayTableAdapter::section_count() const {
  return jfg_generated_section_count();
}

bool GeneratedOverlayTableAdapter::initialize_sections(
    std::span<std::int32_t> addresses) {
  return jfg_generated_initialize_sections(addresses.data(),
                                           addresses.size()) != 0;
}

bool GeneratedOverlayTableAdapter::section_extents(
    std::uint32_t section, jfg::GeneratedSectionExtents &output) const {
  JfgGeneratedSectionMetadata metadata{};
  if (jfg_generated_section_metadata(section, &metadata) == 0 ||
      metadata.is_overlay > 1U)
    return false;
  output = {metadata.text_size, metadata.data_size, metadata.bss_size,
            metadata.is_overlay == 1U};
  return true;
}

bool GeneratedOverlayTableAdapter::update_section_lifecycle(
    jfg::GeneratedSectionLifecycle operation, std::uint32_t section,
    std::int32_t base) {
  return jfg_generated_section_lifecycle(
             operation == jfg::GeneratedSectionLifecycle::load ? 1U : 2U,
             section, base) == 0;
}

std::size_t
GeneratedOverlayTableAdapter::relocation_count(std::uint32_t section) const {
  return jfg_generated_relocation_count(section);
}

bool GeneratedOverlayTableAdapter::relocation_sites(
    std::uint32_t section, std::span<const std::uint32_t> &output) const {
  const std::uint32_t *sites = nullptr;
  std::size_t count = 0U;
  if (jfg_generated_relocation_sites(section, &sites, &count) == 0 ||
      count != relocation_count(section) || (count != 0U && sites == nullptr))
    return false;
  output = {sites, count};
  return true;
}

bool GeneratedOverlayTableAdapter::relocation_descriptors(
    std::uint32_t section,
    std::span<const jfg::GeneratedR32RelocationDescriptor> &output) const {
  const JfgGeneratedR32Descriptor *raw = nullptr;
  std::size_t count = 0U;
  if (jfg_generated_relocation_descriptors(section, &raw, &count) == 0 ||
      count != relocation_count(section) || (count != 0U && raw == nullptr))
    return false;
  descriptors_.clear();
  descriptors_.reserve(count);
  for (std::size_t index = 0U; index < count; ++index)
    descriptors_.push_back({raw[index].site_offset, raw[index].target_section,
                            raw[index].target_offset});
  output = descriptors_;
  return true;
}

jfg::GeneratedRelocationResult
GeneratedOverlayTableAdapter::apply_relocations_checked(
    std::span<std::uint8_t> rdram, std::uint32_t section,
    std::size_t expected) {
  const bool applied = jfg_generated_apply_relocations_checked(
                           rdram.data(), rdram.size(), section) != 0;
  return {applied, applied ? expected : 0U};
}

jfg::GeneratedOverlayFunction
GeneratedOverlayTableAdapter::lookup_function(std::int32_t address) const {
  return jfg_generated_lookup_function(address);
}
} // namespace jfg::boot::native::detail
