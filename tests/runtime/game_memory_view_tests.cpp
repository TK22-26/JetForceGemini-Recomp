#include "jfg/mod/navigation_mod.hpp"
#include "jfg/runtime/flight_transition_music.hpp"
#include "regional_game_fixture.hpp"
#include "jfg/game/overlay_memory.hpp"
#include <iostream>
int main() {
  using namespace jfg;
  int failures=0;const auto check=[&](bool ok){if(!ok)++failures;};
  const auto rejects=[&](auto action){try{action();++failures;}catch(const std::runtime_error&) {}};
  for(bool native_words:{false,true}) {
    std::array<std::uint8_t,8> bytes;bytes.fill(0xa5);
    GuestMemory raw(bytes,native_words);
    for(unsigned lane=0;lane<bytes.size();++lane) {
      bytes.fill(0xa5);raw.put8(0x80000000U+lane,0x37);
      for(unsigned i=0;i<bytes.size();++i)check(raw.u8(0xa0000000U+i)==(i==lane?0x37:0xa5));
    }
    const auto before=bytes;
    for(auto invalid:{0U,0x80000008U,0xffffffffU})rejects([&]{raw.put8(invalid,0);});
    check(bytes==before);
  }
  unsigned target=0;
  for(const auto& revision:roms::kRevisions) {
    const auto delta=++target*0x2000U;
    auto sections=test::memory_sections;sections[0].linked_address+=delta;
    auto bodies=test::memory_bodies;
    auto descriptor=test::memory_descriptor;descriptor.sections=sections;descriptor.bodies=bodies;
    descriptor.revision=revision.id;descriptor.rom_sha1=revision.sha1;descriptor.entry.revision=revision.id;
    descriptor.initial_tv_mode=revision.country=='P'?game::TvMode::pal:game::TvMode::ntsc;
    std::vector<game::NamedDataRef> data(std::begin(test::memory_data),std::end(test::memory_data));
    for(auto& row:data)row.reference.revision=revision.id;
    auto bindings=test::memory_bindings;bindings.revision=revision.id;bindings.data=data;
    std::vector<game::NamedInstructionRef> instructions(std::begin(test::memory_instructions),std::end(test::memory_instructions));
    for(auto& row:instructions)row.reference.revision=revision.id;
    bindings.instructions=instructions;

    game::MemoryContext context(descriptor,bindings);
    std::vector<std::uint8_t> bytes(0x400000);
    game::MemoryView memory(bytes,context,false);
    const auto put=[&](std::uint32_t address,std::uint32_t value){memory.put16(address,static_cast<std::uint16_t>(value>>16));memory.put16(address+2,static_cast<std::uint16_t>(value));};
    const auto global=[&](std::string_view name){return *game::resident_address(descriptor,context.data(name));};
    const auto& guard=instructions.front();
    const auto site=*game::resident_address(descriptor,guard.reference);
    check(!memory.instruction_matches(guard.name));put(site,guard.original_word);
    check(memory.instruction_matches(guard.name));put(site,guard.original_word^1U);
    check(!memory.instruction_matches(guard.name));
    rejects([&]{memory.instruction_matches("guard.absent");});
    if(revision.id!="jfg-us-r0") {
      check(!apply_flight_transition_music_header(memory));
      check(!flight_transition_next_music(memory,88,memory.instruction_address("guard.flight.transition_call")+8U));
    }
    const auto cameras=global("globals.cameraActors");
    check(memory.global_contains("globals.cameraActors",cameras+3*0x4c,0x4c,0x4c));
    check(!memory.global_contains("globals.cameraActors",cameras+4*0x4c,0x4c,0x4c));
    check(!memory.global_contains("globals.cameraActors",cameras+1,0x4c,0x4c));
    rejects([&]{memory.global_address("globals.multiplayerRecords",4*0xa0,1);});
    rejects([&]{memory.global_address("globals.multiplayerRecords",1,4,4);});

    const auto actor=0x80200000U,control=0x80201000U,list=0x80202000U;
    put(global("globals.objectList"),list);put(global("globals.objectCount"),1);put(list,actor);
    memory.put16(actor+0x48,1);put(actor+0x68,control);
    const auto actors=mod::actors(memory);check(actors.size()==1 && actors[0].address==actor);
    check(mod::gameplay_active(memory,actor));put(global("globals.controllerDisabled"),1);
    check(!mod::gameplay_active(memory,actor));put(global("globals.controllerDisabled"),0);
    bytes[global("globals.playerPorts")&0x1fffffffU]=2;check(mod::pc_input_port(memory,0)==2);
    rejects([&]{memory.global_u8("globals.playerPorts",4);});
    rejects([&]{memory.global_u32("globals.absent");});
    auto wrong=bindings;wrong.revision="another";rejects([&]{game::MemoryContext invalid(descriptor,wrong);});
    game::MemoryView truncated(std::span<std::uint8_t>(bytes).first(16),context,false);
    rejects([&]{truncated.global_u32("globals.objectList");});
  }
  {
    std::array sections{game::Section{game::SectionKind::main,0,0x80000000U,4,0,0},
      game::Section{game::SectionKind::overlay,4,15U<<20U,8,8,8,0,15}};
    std::array bodies{game::FunctionBody{0,0,4},game::FunctionBody{1,0,8}};
    auto descriptor=test::memory_descriptor;descriptor.sections=sections;descriptor.bodies=bodies;
    std::vector<std::uint8_t> bytes(64);GuestMemory memory(bytes,false);
    const game::DataRef field{descriptor.revision,1,game::DataDomain::bss,2,2,2};
    memory.put16(0x80000012U,0x1234);
    game::OverlayMemory view(descriptor,1,0x80000000U,memory);
    check(view.u16(field)==0x1234);
    rejects([&]{view.u32(field);});rejects([&]{view.u16(field,1);});
    auto wrong=field;wrong.revision="another";rejects([&]{view.u16(wrong);});
    wrong=field;wrong.section=0;rejects([&]{view.u16(wrong);});
    wrong=field;wrong.domain=game::DataDomain::retained_relocations;rejects([&]{view.u16(wrong);});
    game::OverlayMemory overflow(descriptor,1,0xfffffff0U,memory);rejects([&]{overflow.u16(field);});
    game::OverlayMemory unmapped(descriptor,1,0x80001000U,memory);rejects([&]{unmapped.u16(field);});
  }
  if(failures)std::cerr<<failures<<" bound memory failures\n";
  return failures?1:0;
}
