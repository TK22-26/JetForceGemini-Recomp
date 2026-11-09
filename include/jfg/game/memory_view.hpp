#pragma once
#include "jfg/game/bindings.hpp"
#include "jfg/game/resident_memory.hpp"
#include "jfg/runtime/guest_memory_view.hpp"
#include <bit>

namespace jfg::game {
// A session composes one immutable descriptor and one matching binding set.
// Callers retain both objects for the lifetime of this context and its views.
class MemoryContext {
  const Descriptor& descriptor_;
  const Bindings& bindings_;
public:
  MemoryContext(const Descriptor& descriptor,const Bindings& bindings)
      :descriptor_(descriptor),bindings_(bindings) {
    if(validate(descriptor)!=DescriptorError::none || validate(descriptor,bindings)!=BindingError::none)
      throw std::runtime_error("Game memory context has incompatible descriptor or bindings");
  }
  const Descriptor& descriptor() const noexcept {return descriptor_;}
  const NamedInstructionRef& instruction(std::string_view name) const {
    for(const auto& row:bindings_.instructions)if(row.name==name)return row;
    throw std::runtime_error("Required game instruction binding is absent");
  }

  DataRef data(std::string_view name) const {
    const auto reference=data_binding(bindings_,name);
    if(!reference || !resident_address(descriptor_,*reference))
      throw std::runtime_error("Required resident game data binding is absent");
    return *reference;
  }
};

class MemoryView : public jfg::GuestMemory {
  const MemoryContext& context_;
public:
  MemoryView(std::span<std::uint8_t> bytes,const MemoryContext& context,bool native_words=true)
      :GuestMemory(bytes,native_words),context_(context) {}
  const MemoryContext& context() const noexcept {return context_;}
  std::uint32_t instruction_address(std::string_view name) const {
    const auto address=resident_address(context_.descriptor(),context_.instruction(name).reference);
    if(!address)throw std::runtime_error("Game instruction requires its resident owner");
    return *address;
  }
  std::uint32_t member_offset(std::string_view name) const {
    const auto word=context_.instruction(name).original_word,op=word>>26U,base=(word>>21U)&31U;
    if(!name.starts_with("layout.") || base==0U || base==29U || (word&0x8000U) ||
       !(op==32U || op==33U || op==35U || op==36U || op==37U || op==39U || op==40U || op==41U || op==43U || op==49U || op==53U || op==57U || op==61U))
      throw std::runtime_error("Required object member binding is invalid");
    return word&0xffffU;
  }
  bool instruction_matches(std::string_view name,std::uint32_t mask=0xffffffffU) const {
    const auto& row=context_.instruction(name);
    const auto address=resident_address(context_.descriptor(),row.reference);
    return address && valid(*address,4) && (u32(*address)&mask)==(row.original_word&mask);
  }
  bool global_valid(std::string_view name) const {
    const auto reference=context_.data(name);
    const auto address=resident_address(context_.descriptor(),reference);
    return address && valid(*address,reference.size);
  }

  std::uint32_t global_address(std::string_view name,std::uint32_t offset=0,std::uint32_t width=1,std::uint32_t alignment=1) const {
    return ResidentMemory(context_.descriptor(),*this).range(context_.data(name),offset,width,alignment);
  }
  bool global_contains(std::string_view name,std::uint32_t address,std::uint32_t width,std::uint32_t stride=1) const {
    const auto reference=context_.data(name);const auto base=resident_address(context_.descriptor(),reference);
    return base && width && stride && address>=*base && address-*base<=reference.size && width<=reference.size-(address-*base) &&
      (address-*base)%stride==0 && valid(address,width);
  }
  std::uint8_t global_u8(std::string_view name,std::uint32_t offset=0) const {
    return ResidentMemory(context_.descriptor(),*this).u8(context_.data(name),offset);
  }
  std::uint16_t global_u16(std::string_view name,std::uint32_t offset=0) const {
    return ResidentMemory(context_.descriptor(),*this).u16(context_.data(name),offset);
  }
  std::uint32_t global_u32(std::string_view name,std::uint32_t offset=0) const {
    return ResidentMemory(context_.descriptor(),*this).u32(context_.data(name),offset);
  }
  std::int16_t global_s16(std::string_view name,std::uint32_t offset=0) const {
    return std::bit_cast<std::int16_t>(global_u16(name,offset));
  }
  float global_f32(std::string_view name,std::uint32_t offset=0) const {
    const auto value=std::bit_cast<float>(global_u32(name,offset));
    if(!std::isfinite(value))throw std::runtime_error("Nonfinite game global");
    return value;
  }
};
} // namespace jfg::game
