#include "jfg/game/bindings.hpp"
#include "jfg/game/original_modules.hpp"
#include <array>
#include <iostream>
using namespace jfg::game;
namespace {
int failures = 0;
void check(bool value, const char* message) { if (!value) { ++failures; std::cerr << message << '\n'; } }
constexpr std::string_view fingerprint = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
}
int main() {
  for (const auto& revision : jfg::roms::kRevisions) {
    const std::array sections = {Section{SectionKind::entry,0x1000,0x80000400,0x50,0,0},
      Section{SectionKind::main,0x1050,0x80000450,0x100,0x20,0x40},
      Section{SectionKind::overlay,0x2000,0x200000,0x20,0x10,0x10,0x10,1},
      Section{SectionKind::overlay,0x2100,0x200000,0x20,0x10,0x10,0x10,2}};
    const std::array bodies = {FunctionBody{0,0,0x50},FunctionBody{1,0,0x100},FunctionBody{2,0,0x20},FunctionBody{3,0,0x20}};
    const std::array aliases = {CodeRef{revision.id,1,0x10}};
    Descriptor d{kDescriptorAbi,revision.id,revision.sha1,fingerprint,fingerprint,sections,bodies,aliases,{revision.id,0,0},revision.country=='P'?TvMode::pal:TvMode::ntsc};
    auto bootstrap = d; bootstrap.entry = {revision.id,0,0x40};
    check(valid_entry_ref(bootstrap,bootstrap.entry),"unlabelled IPL bootstrap is an entry reference");
    check(!valid_code_ref(bootstrap,{revision.id,0,0x40}),"bootstrap is not an implicit generated callable");
    check(validate(d)==DescriptorError::none,"separate entry and overlapping overlay coordinates");
    check(original_module_section(d,static_cast<OriginalModule>(1))==2U,"original module ID resolves independently of generated ordinal");
    check(original_module_section(d,static_cast<OriginalModule>(2))==3U,"overlapping linked addresses do not merge module owners");
    check(!original_module_section(d,OriginalModule::hint_text),"missing original module cannot fall back to an ordinal");
    // Racing occupies original runlink slot 31, not generated section 30.
    // Include slot 30 as a decoy and reorder sections to catch both mistakes.
    auto racing_sections=sections;racing_sections[2].overlay_slot=30;racing_sections[3].overlay_slot=31;
    auto racing=d;racing.sections=racing_sections;
    check(original_module_section(racing,OriginalModule::racing)==3U,"racing selects original module 31 rather than adjacent module 30");
    std::swap(racing_sections[2],racing_sections[3]);
    check(original_module_section(racing,OriginalModule::racing)==2U,"racing follows original ownership after generated section reordering");
    auto duplicate_sections=sections;duplicate_sections[3].overlay_slot=1;
    auto ambiguous=d;ambiguous.sections=duplicate_sections;
    check(!original_module_section(ambiguous,static_cast<OriginalModule>(1)),"ambiguous original module cannot select an image");

    check(accepts_rom(d,revision.sha1,revision.size),"exact ROM accepted");
    check(!accepts_rom(d,revision.sha1,revision.size-1),"truncated ROM rejected");
    check(valid_code_ref(d,{revision.id,1,0x10}),"declared alternate entry accepted");
    check(!valid_code_ref(d,{revision.id,1,0x14}),"arbitrary interior entry rejected");
    check(valid_instruction_ref(d,{revision.id,1,0x14}),"instruction site distinct from callable");
    check(!valid_code_ref(d,{"wrong",1,0}),"cross-revision code rejected");
    check(!resident_address(d,CodeRef{revision.id,2,0}),"overlay needs lifetime lease");
    check(resident_address(d,CodeRef{revision.id,1,0})==0x80000450U,"resident code resolves");
    check(resident_address(d,DataRef{revision.id,1,DataDomain::data,0,4,4},true)==0x80000550U,"data zero follows text");
    check(!valid_data_ref(d,{revision.id,1,DataDomain::data,0x20,4,4}),"data cannot flow into BSS");
    check(!valid_data_ref(d,{revision.id,2,DataDomain::retained_relocations,0,4,4},true),"retained metadata immutable");
    check(!valid_data_ref(d,{revision.id,1,DataDomain::data,1,4,4}),"unaligned data rejected");
    const std::array code_refs = {NamedCodeRef{"sdk.example",{revision.id,1,0}}};
    const std::array data_refs = {NamedDataRef{"example.value",{revision.id,1,DataDomain::data,0,4,4},true}};
    const std::array instructions = {NamedInstructionRef{"vi.idle",{revision.id,1,0x14},0}};
    Bindings bindings{kBindingAbi,revision.id,fingerprint,fingerprint,code_refs,data_refs,2,32,8,16,instructions};
    check(instruction_binding(bindings,"vi.idle").has_value(),"instruction binding remains distinct from a callable");
    check(validate(d,bindings)==BindingError::none,"typed binding set validates against descriptor");
    check(code_binding(bindings,"sdk.example").has_value(),"semantic code lookup");
    check(!code_binding(bindings,"unknown"),"missing semantic operation does not fall back");
    check(data_binding(bindings,"example.value",true).has_value(),"writable semantic data lookup");
    auto wrong_bindings=bindings;wrong_bindings.revision="wrong";
    check(validate(d,wrong_bindings)==BindingError::identity_mismatch,"mixed revision binding set rejected");
    wrong_bindings=bindings;wrong_bindings.input_sha256="another-input";
    check(validate(d,wrong_bindings)==BindingError::identity_mismatch,"mixed generation input rejected");
    const std::array invalid_code = {NamedCodeRef{"sdk.example",{revision.id,2,0}}};
    wrong_bindings=bindings;wrong_bindings.code=invalid_code;
    check(validate(d,wrong_bindings)==BindingError::invalid_code,"SDK binding cannot escape into an overlay");
    const std::array invalid_data = {NamedDataRef{"example.value",{revision.id,1,DataDomain::data,0x1c,8,4},true}};
    wrong_bindings=bindings;wrong_bindings.data=invalid_data;
    check(validate(d,wrong_bindings)==BindingError::invalid_data,"semantic data cannot cross section domains");
    const std::array invalid_instructions = {NamedInstructionRef{"vi.idle",{revision.id,1,0x100},0}};
    wrong_bindings=bindings;wrong_bindings.instructions=invalid_instructions;
    check(validate(d,wrong_bindings)==BindingError::invalid_instruction,"instruction outside text rejected");
    auto wrong=d;wrong.abi=99;check(validate(wrong)==DescriptorError::unsupported_abi,"unknown ABI rejected");
    wrong=d;wrong.rom_sha1="wrong";check(validate(wrong)==DescriptorError::identity_mismatch,"descriptor ROM mismatch rejected");
    wrong=d;wrong.initial_tv_mode=revision.country=='P'?TvMode::ntsc:TvMode::pal;check(validate(wrong)==DescriptorError::invalid_tv_mode,"regional boot TV mode checked");
  }
  return failures?1:0;
}
