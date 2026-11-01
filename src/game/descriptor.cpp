#include "jfg/game/descriptor.hpp"
#include <limits>

namespace jfg::game {
namespace {
constexpr std::uint64_t address_limit = std::uint64_t{1} << 32;
bool hex_digest(std::string_view value, std::size_t size) noexcept {
  if (value.size() != size) return false;
  for (const char c : value) if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
  return true;
}
std::uint64_t initialized(const Section& s) noexcept { return std::uint64_t{s.text_size} + s.data_size; }
std::uint64_t memory(const Section& s) noexcept { return initialized(s) + s.bss_size; }
bool overlap(std::uint64_t a, std::uint64_t size_a, std::uint64_t b, std::uint64_t size_b) noexcept {
  return size_a && size_b && a < b + size_b && b < a + size_a;
}
const FunctionBody* body_at(const Descriptor& d, std::uint32_t section, std::uint32_t offset) noexcept {
  const FunctionBody* found = nullptr;
  for (const auto& body : d.bodies) {
    if (body.section == section && body.offset <= offset && std::uint64_t{offset} < std::uint64_t{body.offset} + body.size) {
      if (found) return nullptr;
      found = &body;
    }
  }
  return found;
}
std::optional<std::uint64_t> data_offset(const Descriptor& d, DataRef ref, bool writable) noexcept {
  if (ref.revision != d.revision || ref.section >= d.sections.size() || !ref.size || !ref.alignment ||
      (ref.alignment & (ref.alignment - 1U))) return {};
  const auto& section = d.sections[ref.section];
  std::uint64_t start = 0, size = 0;
  switch (ref.domain) {
    case DataDomain::data: start = section.text_size; size = section.data_size; break;
    case DataDomain::bss: start = initialized(section); size = section.bss_size; break;
    case DataDomain::retained_relocations:
      if (writable || section.kind != SectionKind::overlay) return {};
      start = memory(section); size = section.retained_size; break;
    default: return {};
  }
  const auto offset = start + ref.offset;
  if (std::uint64_t{ref.offset} + ref.size > size || offset % ref.alignment ||
      (std::uint64_t{section.linked_address} + offset) % ref.alignment) return {};
  return offset;
}
}

bool valid_entry_ref(const Descriptor& d, EntryRef ref) noexcept {
  return ref.revision == d.revision && ref.section < d.sections.size() &&
      d.sections[ref.section].kind != SectionKind::overlay && ref.offset % 4U == 0 &&
      std::uint64_t{ref.offset} + 4 <= d.sections[ref.section].text_size;
}
std::optional<std::uint32_t> resident_address(const Descriptor& d, EntryRef ref) noexcept {
  if (!valid_entry_ref(d, ref)) return {};
  const auto address = std::uint64_t{d.sections[ref.section].linked_address} + ref.offset;
  if (address >= address_limit) return {};
  return static_cast<std::uint32_t>(address);
}
bool valid_instruction_ref(const Descriptor& d, InstructionRef ref) noexcept {
  return ref.revision == d.revision && ref.section < d.sections.size() && ref.offset % 4U == 0 && body_at(d, ref.section, ref.offset);
}
bool valid_code_ref(const Descriptor& d, CodeRef ref) noexcept {
  if (!valid_instruction_ref(d, {ref.revision, ref.section, ref.offset})) return false;
  const auto* body = body_at(d, ref.section, ref.offset);
  if (body->offset == ref.offset) return true;
  for (const auto& entry : d.alternate_entries)
    if (entry.revision == ref.revision && entry.section == ref.section && entry.offset == ref.offset) return true;
  return false;
}
bool valid_data_ref(const Descriptor& d, DataRef ref, bool writable) noexcept { return data_offset(d, ref, writable).has_value(); }
std::optional<std::uint32_t> resident_address(const Descriptor& d, InstructionRef ref) noexcept {
  if(!valid_instruction_ref(d,ref) || d.sections[ref.section].kind==SectionKind::overlay)return {};
  const auto address=std::uint64_t{d.sections[ref.section].linked_address}+ref.offset;
  if(address>=address_limit)return {};
  return static_cast<std::uint32_t>(address);
}
std::optional<std::uint32_t> resident_address(const Descriptor& d, CodeRef ref) noexcept {
  if (!valid_code_ref(d, ref) || d.sections[ref.section].kind == SectionKind::overlay) return {};
  const auto address = std::uint64_t{d.sections[ref.section].linked_address} + ref.offset;
  if (address >= address_limit) return {};
  return static_cast<std::uint32_t>(address);
}
std::optional<std::uint32_t> resident_address(const Descriptor& d, DataRef ref, bool writable) noexcept {
  const auto offset = data_offset(d, ref, writable);
  if (!offset || d.sections[ref.section].kind == SectionKind::overlay) return {};
  const auto address = std::uint64_t{d.sections[ref.section].linked_address} + *offset;
  if (address >= address_limit || address + ref.size > address_limit) return {};
  return static_cast<std::uint32_t>(address);
}
DescriptorError validate(const Descriptor& d) noexcept {
  if (d.abi != kDescriptorAbi) return DescriptorError::unsupported_abi;
  const auto* revision = roms::find_revision(d.revision);
  if (!revision) return DescriptorError::unknown_revision;
  if (d.rom_sha1 != revision->sha1) return DescriptorError::identity_mismatch;
  if (!hex_digest(d.model_sha256, 64) || !hex_digest(d.input_sha256, 64)) return DescriptorError::malformed_digest;
  if (d.initial_tv_mode != (revision->country == 'P' ? TvMode::pal : TvMode::ntsc)) return DescriptorError::invalid_tv_mode;
  unsigned mains = 0, entries = 0;
  if (d.sections.empty() || d.bodies.empty()) return DescriptorError::invalid_sections;
  for (std::size_t i = 0; i < d.sections.size(); ++i) {
    const auto& s = d.sections[i];
    switch (s.kind) {
      case SectionKind::entry: ++entries; break;
      case SectionKind::main: ++mains; break;
      case SectionKind::overlay: break;
      default: return DescriptorError::invalid_sections;
    }
    if (!s.text_size || (s.rom_start | s.linked_address | s.text_size | s.data_size | s.bss_size | s.retained_size) % 4U ||
        std::uint64_t{s.rom_start} + initialized(s) > revision->size ||
        std::uint64_t{s.linked_address} + memory(s) + s.retained_size > address_limit ||
        (s.kind == SectionKind::overlay ? !s.overlay_slot : s.overlay_slot || s.retained_size)) return DescriptorError::invalid_sections;
    for (std::size_t j = 0; j < i; ++j) {
      const auto& other = d.sections[j];
      if (overlap(s.rom_start, initialized(s), other.rom_start, initialized(other)) ||
          (s.kind != SectionKind::overlay && other.kind != SectionKind::overlay && overlap(s.linked_address, memory(s), other.linked_address, memory(other))) ||
          (s.overlay_slot && s.overlay_slot == other.overlay_slot)) return DescriptorError::overlapping_sections;
    }
  }
  if (mains != 1 || entries > 1) return DescriptorError::invalid_sections;
  for (std::size_t i = 0; i < d.bodies.size(); ++i) {
    const auto& b = d.bodies[i];
    if (b.section >= d.sections.size() || !b.size || (b.offset | b.size) % 4U ||
        std::uint64_t{b.offset} + b.size > d.sections[b.section].text_size) return DescriptorError::invalid_body;
    for (std::size_t j = 0; j < i; ++j) {
      const auto& other = d.bodies[j];
      if (b.section == other.section && overlap(b.offset, b.size, other.offset, other.size)) return DescriptorError::overlapping_bodies;
    }
  }
  for (std::size_t i = 0; i < d.alternate_entries.size(); ++i) {
    const auto ref = d.alternate_entries[i];
    const auto* body = body_at(d, ref.section, ref.offset);
    if (!valid_instruction_ref(d, {ref.revision, ref.section, ref.offset}) || !body || body->offset == ref.offset) return DescriptorError::invalid_alternate_entry;
    for (std::size_t j = 0; j < i; ++j) {
      const auto other = d.alternate_entries[j];
      if (other.section == ref.section && other.offset == ref.offset) return DescriptorError::invalid_alternate_entry;
    }
  }
  if (!valid_entry_ref(d, d.entry)) return DescriptorError::invalid_entry;
  return DescriptorError::none;
}
bool accepts_rom(const Descriptor& d, std::string_view sha1, std::uint64_t bytes) noexcept {
  const auto* revision = roms::find_revision(d.revision);
  return revision && validate(d) == DescriptorError::none && sha1 == revision->sha1 && bytes == revision->size;
}
} // namespace jfg::game
