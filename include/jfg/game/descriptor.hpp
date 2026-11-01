#pragma once

#include "jfg/game/rom_catalog.hpp"
#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <string_view>

namespace jfg::game {
inline constexpr std::uint32_t kDescriptorAbi = 1;
enum class SectionKind { entry, main, overlay };
enum class DataDomain { data, bss, retained_relocations };
enum class TvMode : std::uint32_t { pal = 0, ntsc = 1 };

struct Section {
  SectionKind kind;
  std::uint32_t rom_start, linked_address, text_size, data_size, bss_size;
  std::uint32_t retained_size = 0;
  std::uint32_t overlay_slot = 0;
};
struct FunctionBody { std::uint32_t section, offset, size; };
// The IPL handoff is interpreted before generated dispatch. An original ELF
// need not label the bootstrap instructions as a C-callable function body.
struct EntryRef {
  std::string_view revision;
  std::uint32_t section, offset;
};
struct CodeRef {
  std::string_view revision;
  std::uint32_t section, offset;
};
// An instruction site is not an executable entry. Keeping these types distinct
// prevents an instruction guard or return-site hook becoming an implicit thunk.
struct InstructionRef {
  std::string_view revision;
  std::uint32_t section, offset;
};
struct DataRef {
  std::string_view revision;
  std::uint32_t section;
  DataDomain domain;
  std::uint32_t offset, size, alignment;
};
struct Descriptor {
  std::uint32_t abi;
  std::string_view revision, rom_sha1, model_sha256, input_sha256;
  std::span<const Section> sections;
  std::span<const FunctionBody> bodies;
  std::span<const CodeRef> alternate_entries;
  EntryRef entry;
  TvMode initial_tv_mode;
};
enum class DescriptorError {
  none, unsupported_abi, unknown_revision, identity_mismatch, malformed_digest,
  invalid_sections, overlapping_sections, invalid_body, overlapping_bodies,
  invalid_alternate_entry, invalid_entry, invalid_tv_mode
};

[[nodiscard]] DescriptorError validate(const Descriptor&) noexcept;
[[nodiscard]] bool valid_entry_ref(const Descriptor&, EntryRef) noexcept;
[[nodiscard]] std::optional<std::uint32_t> resident_address(const Descriptor&, EntryRef) noexcept;
[[nodiscard]] bool valid_code_ref(const Descriptor&, CodeRef) noexcept;
[[nodiscard]] bool valid_instruction_ref(const Descriptor&, InstructionRef) noexcept;
[[nodiscard]] bool valid_data_ref(const Descriptor&, DataRef, bool writable = false) noexcept;
// Only resident references can be resolved without a live overlay lease.
// Overlay invocation/data access must use the existing runtime's lifetime owner.
[[nodiscard]] std::optional<std::uint32_t> resident_address(const Descriptor&, CodeRef) noexcept;
[[nodiscard]] std::optional<std::uint32_t> resident_address(const Descriptor&, InstructionRef) noexcept;
[[nodiscard]] std::optional<std::uint32_t> resident_address(const Descriptor&, DataRef, bool writable = false) noexcept;
[[nodiscard]] bool accepts_rom(const Descriptor&, std::string_view normalized_sha1, std::uint64_t bytes) noexcept;
} // namespace jfg::game
