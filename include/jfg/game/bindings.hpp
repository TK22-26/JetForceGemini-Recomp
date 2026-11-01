#pragma once
#include "jfg/game/descriptor.hpp"

namespace jfg::game {
inline constexpr std::uint32_t kBindingAbi = 3;
struct NamedInstructionRef { std::string_view name; InstructionRef reference; std::uint32_t original_word; };
struct NamedCodeRef { std::string_view name; CodeRef reference; };
struct NamedDataRef { std::string_view name; DataRef reference; bool writable; };
struct SdkMapping { std::uint32_t vram; const char* name; CodeRef reference; };
struct Bindings {
  std::uint32_t abi;
  std::string_view revision, model_sha256, input_sha256;
  std::span<const NamedCodeRef> code;
  std::span<const NamedDataRef> data;
  std::uint32_t overlay_slot_count, runlink_record_size, suspended_record_size, suspended_record_count;
  std::span<const NamedInstructionRef> instructions;
};
enum class BindingError { none, unsupported_abi, identity_mismatch, duplicate_name, invalid_code, invalid_data, invalid_instruction, invalid_runlink_abi };
[[nodiscard]] BindingError validate(const Descriptor&, const Bindings&) noexcept;
[[nodiscard]] std::optional<InstructionRef> instruction_binding(const Bindings&, std::string_view) noexcept;
[[nodiscard]] std::optional<CodeRef> code_binding(const Bindings&, std::string_view) noexcept;
[[nodiscard]] std::optional<DataRef> data_binding(const Bindings&, std::string_view, bool writable = false) noexcept;
} // namespace jfg::game
