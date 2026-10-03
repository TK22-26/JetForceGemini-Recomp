#include "jfg/boot/sound_queue_recovery.hpp"
#include <cstdlib>
#include <iostream>
#include <vector>
struct Context { std::uint64_t r2 = 0, r29 = 0x80000100, r31 = 0x800844E0; };
static void check(bool value) {
  if (!value) { std::cerr << "sound queue recovery regression failed\n"; std::exit(1); }
}
int main() {
  using namespace jfg::boot;
  constexpr std::uint32_t player=0x80002000U, queue=player+0x14U, event=player+0x2CU;
  for (auto layout : {hle::GuestMemory::Layout::byte_linear_big_endian,
                      hle::GuestMemory::Layout::native_word_big_endian}) {
    std::vector<std::uint8_t> bytes(0x100000, 0);
    hle::GuestMemory memory(bytes, layout);
    auto put=[&](std::uint32_t at,std::uint32_t value) {check(memory.write_u32(at,value));};
    auto word=[&](std::uint32_t at) {std::uint32_t v=0;check(memory.read_u32(at,v));return v;};
    put(kSoundPlayerGlobal,player); put(player+8U,0x80084468U);
    put(0x80084468U,0x27BDFFD0U); put(0x8008446CU,0xAFBF0014U);
    put(queue,0x80003000U); put(queue+8U,0); put(queue+0x10U,276);
    put(queue+0x14U,200U<<16U); put(player+0x4CU,16000);
    put(event,0xFFFF1234U);put(event+4U,0x80004000U);
    put(event+8U,0xDEADBEEFU);put(event+12U,0xFFFFFFFFU);
    const auto original=bytes;
    Context context;
    check(recover_empty_sound_queue(memory,context,queue,event));
    check(context.r2==16000 && context.r29==0x80000100 && context.r31==0x800844E0);
    check(word(event)==0x00200000U && word(event+4U)==0 &&
          word(event+8U)==0 && word(event+12U)==0);
    // Queue links, delta nodes, drop count and high water remain byte-identical.
    const auto recovered=bytes;
    for (std::size_t i=0;i<bytes.size();++i)
      if (i < (event & 0x1FFFFFFFU) || i >= (event & 0x1FFFFFFFU)+16U)
        check(bytes[i]==original[i]);
    // A second empty read is not manufactured while the periodic event exists.
    bytes=recovered;context.r2=0;
    check(!recover_empty_sound_queue(memory,context,queue,event) && bytes==recovered);
    const std::uint32_t changes[][2]={
      {queue+8U,0x80003000U}, {queue+0x10U,0x00010114U}, {queue+0x10U,0},
      {queue,0}, {queue,0x80800000U}, {player+8U,0x80000000U},
      {player+0x4CU,0}, {player+0x4CU,0xFFFFFFFFU},
      {event,0x00200000U}, {0x80084468U,0}, {kSoundPlayerGlobal,0xFFFFFFF0U}
    };
    for (const auto &change:changes) {
      bytes=original;context=Context{};put(change[0],change[1]);const auto before=bytes;
      check(!recover_empty_sound_queue(memory,context,queue,event));
      check(bytes==before && context.r2==0);
    }
    bytes=original;context=Context{};context.r2=1;
    check(!recover_empty_sound_queue(memory,context,queue,event) && bytes==original);
    context.r2=0;
    check(!recover_empty_sound_queue(memory,context,queue+4U,event) && bytes==original);
    check(!recover_empty_sound_queue(memory,context,queue,event+4U) && bytes==original);
  }
  std::cout << "sound queue recovery: both layouts, overflow clock, queue preservation and rejection passed\n";
}
