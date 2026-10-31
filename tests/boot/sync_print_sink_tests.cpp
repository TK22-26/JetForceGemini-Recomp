#include "jfg/boot/sync_print_sink.hpp"
#include <cstdlib>
#include <iostream>
#include <vector>
struct Context {
  std::uint64_t r2 = 99, r4 = 0xffffffff89abcdefULL, r5 = 0,
                r6 = 0xffffffffffffffffULL, r29 = 0x80000100, r31 = 0x80001234;
};
static void check(bool value) {
  if (!value) { std::cerr << "sync print sink regression failed\n"; std::exit(1); }
}
int main() {
  using namespace jfg::boot;
  for (auto layout : {hle::GuestMemory::Layout::byte_linear_big_endian,
                      hle::GuestMemory::Layout::native_word_big_endian}) {
    std::vector<std::uint8_t> bytes(0x100000, 0x5a);
    hle::GuestMemory memory(bytes, layout);
    for (std::uint32_t i = 0; i < kSyncPrintSinkSignature.size(); ++i)
      check(memory.write_u32(kSyncPrintSink + i * 4U, kSyncPrintSinkSignature[i]));
    Context context;
    const auto original = bytes;
    check(invoke_sync_print_sink(memory, context));
    check(context.r2 == 1 && context.r29 == 0x80000100 && context.r31 == 0x80001234);
    for (auto offset : {0U,4U,8U,12U}) {
      std::uint32_t word=0; check(memory.read_u32(0x80000100U+offset,word));
      check(word == (offset==0 ? 0x89abcdefU : offset==4 ? 0U :
                     offset==8 ? 0xffffffffU : 0x5a5a5a5aU));
    }
    for (auto bad_stack : {0x800ffff8U,0xfffffffcU,0x80000101U,0U}) {
      bytes = original; context = Context{}; context.r29=bad_stack;
      check(!invoke_sync_print_sink(memory,context));
      check(bytes==original && context.r2==99);
    }
    bytes=original; context=Context{};
    check(memory.write_u32(kSyncPrintSink+16U,0));
    const auto bad_code=bytes;
    check(!invoke_sync_print_sink(memory,context));
    check(bytes==bad_code && context.r2==99);
  }
  std::cout << "sync print sink: both layouts, ABI, signature and range checks passed\n";
}
