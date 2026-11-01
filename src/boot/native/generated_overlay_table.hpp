#pragma once
#include "jfg/runtime/generated_overlay_runtime.hpp"
#include <vector>
namespace jfg::boot::native::detail {
class GeneratedOverlayTableAdapter final : public jfg::GeneratedOverlayTable {
public:
  std::size_t section_count() const override;
  bool initialize_sections(std::span<std::int32_t> addresses) override;
  bool section_extents(std::uint32_t section,
                       jfg::GeneratedSectionExtents &output) const override;
  bool update_section_lifecycle(jfg::GeneratedSectionLifecycle operation,
                                std::uint32_t section,
                                std::int32_t base) override;
  std::size_t relocation_count(std::uint32_t section) const override;
  bool relocation_sites(std::uint32_t section,
                        std::span<const std::uint32_t> &output) const override;
  bool
  relocation_descriptors(std::uint32_t section,
                         std::span<const jfg::GeneratedR32RelocationDescriptor>
                             &output) const override;
  jfg::GeneratedRelocationResult
  apply_relocations_checked(std::span<std::uint8_t> rdram,
                            std::uint32_t section,
                            std::size_t expected) override;
  jfg::GeneratedOverlayFunction
  lookup_function(std::int32_t address) const override;

private:
  mutable std::vector<jfg::GeneratedR32RelocationDescriptor> descriptors_;
};
} // namespace jfg::boot::native::detail
