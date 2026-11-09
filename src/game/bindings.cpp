#include "jfg/game/bindings.hpp"
namespace jfg::game {
BindingError validate(const Descriptor& d, const Bindings& b) noexcept {
  if (b.abi != kBindingAbi) return BindingError::unsupported_abi;
  if (b.revision != d.revision || b.model_sha256 != d.model_sha256 || b.input_sha256 != d.input_sha256)
    return BindingError::identity_mismatch;
  if (!b.overlay_slot_count || b.runlink_record_size != 32 || b.suspended_record_size != 8 || b.suspended_record_count != 16)
    return BindingError::invalid_runlink_abi;
  for (const auto& s : d.sections)
    if (s.kind == SectionKind::overlay && s.overlay_slot > b.overlay_slot_count) return BindingError::invalid_runlink_abi;
  for (std::size_t i = 0; i < b.code.size(); ++i) {
    const auto& row = b.code[i];
    if (row.name.empty() || !valid_code_ref(d, row.reference) ||
        (row.name.starts_with("sdk.") && d.sections[row.reference.section].kind == SectionKind::overlay))
      return BindingError::invalid_code;
    for (std::size_t j = 0; j < i; ++j) if (b.code[j].name == row.name) return BindingError::duplicate_name;
  }
  for (std::size_t i = 0; i < b.data.size(); ++i) {
    const auto& row = b.data[i];
    if (row.name.empty() || !valid_data_ref(d, row.reference, row.writable)) return BindingError::invalid_data;
    for (std::size_t j = 0; j < i; ++j) if (b.data[j].name == row.name) return BindingError::duplicate_name;
    for (const auto& code : b.code) if (code.name == row.name) return BindingError::duplicate_name;
  }
  for (std::size_t i = 0; i < b.instructions.size(); ++i) {
    const auto& row = b.instructions[i];
    if (row.name.empty() || !valid_instruction_ref(d, row.reference)) return BindingError::invalid_instruction;
    for (std::size_t j = 0; j < i; ++j) if (b.instructions[j].name == row.name) return BindingError::duplicate_name;
    for (const auto& code : b.code) if (code.name == row.name) return BindingError::duplicate_name;
    for (const auto& data : b.data) if (data.name == row.name) return BindingError::duplicate_name;
  }
  return BindingError::none;
}
std::optional<InstructionRef> instruction_binding(const Bindings& b, std::string_view name) noexcept {
  for (const auto& row : b.instructions) if (row.name == name) return row.reference;
  return {};
}
std::optional<CodeRef> code_binding(const Bindings& b, std::string_view name) noexcept {
  for (const auto& row : b.code) if (row.name == name) return row.reference;
  return {};
}
std::optional<DataRef> data_binding(const Bindings& b, std::string_view name, bool writable) noexcept {
  for (const auto& row : b.data) if (row.name == name && (!writable || row.writable)) return row.reference;
  return {};
}
} // namespace jfg::game
