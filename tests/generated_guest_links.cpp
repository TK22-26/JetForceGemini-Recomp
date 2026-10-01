extern "C" {
#include "recomp.h"
void link_direct(uint8_t*, recomp_context*);
void link_indirect(uint8_t*, recomp_context*);
void link_clobber(uint8_t*, recomp_context*);
void link_conditional(uint8_t*, recomp_context*);
void link_likely(uint8_t*, recomp_context*);
void link_tail(uint8_t*, recomp_context*);
void link_leaf(uint8_t*, recomp_context*);
void link_saved_return(uint8_t*, recomp_context*);
void link_register_tail(uint8_t*, recomp_context*);
}
#include <cstdint>
#include <cstdlib>
#include <iostream>
// Addresses are supplied by the assembled fixture's symbol/disassembly ledger.
#include "link_addresses.h"
static std::int32_t section_bases[64];
extern "C" { std::int32_t* section_addresses = section_bases; }
extern "C" recomp_func_t* get_function(int32_t address) {
  // The existing direct-call lookup ABI uses the linked identity; indirect
  // calls use the loaded address. Both resolve the same fixture body.
  if (static_cast<std::uint32_t>(address) == LINK_LEAF ||
      static_cast<std::uint32_t>(address) == LINK_LEAF + LINK_SHIFT) return link_leaf;
  std::abort();
}
int main() {
  for (auto& base : section_bases) base = static_cast<std::int32_t>(0x80001000U + LINK_SHIFT);
  unsigned matches = 0;
  struct Case { recomp_func_t* function; std::uint32_t expected; int argument; bool slot; bool taken; bool likely; };
  const Case cases[] = {
    {link_direct, DIRECT_LINK, 0, true, true, false},
    {link_indirect, INDIRECT_LINK, 0, true, true, false},
    {link_clobber, CLOBBER_LINK, 0, true, true, false},
    {link_conditional, CONDITIONAL_LINK, 0, true, true, false},
    {link_conditional, CONDITIONAL_LINK, -1, true, false, false},
    {link_likely, LIKELY_LINK, 0, true, true, true},
    {link_likely, LIKELY_LINK, -1, false, false, true},
    {link_tail, 0x80200000, 0, true, true, false}};
  unsigned index = 0;
  for (const auto& test : cases) {
    recomp_context ctx{};
    ctx.r31 = 0xffffffff80200000ULL;
    ctx.r4 = static_cast<gpr>(test.argument);
    test.function(nullptr, &ctx);
    const auto expected = static_cast<gpr>(static_cast<std::int64_t>(static_cast<std::int32_t>(
        test.expected + (test.function == link_tail ? 0U : LINK_SHIFT))));
    const bool match = ctx.r2 == (test.slot ? expected : 0) &&
        ctx.r3 == (test.taken ? expected : 0) &&
        (!test.likely || ctx.r5 == expected) &&
        ctx.r31 == 0xffffffff80200000ULL;
    matches += match ? 1U : 0U;
    std::cout << index++ << '\t' << std::hex << expected << '\t' << ctx.r2 << '\t' << ctx.r3 << std::dec << '\n';
  }
#if defined(TEST_DYNAMIC_RETURNS)
  recomp_context saved{};
  saved.r31 = 0xffffffff80200000ULL;
  link_saved_return(nullptr, &saved);
  matches += saved.r2 == 42 && saved.r18 == 0xffffffff80200000ULL ? 1U : 0U;
  recomp_context tail{};
  tail.r31 = 0xffffffff80200000ULL;
  tail.r4 = static_cast<gpr>(static_cast<std::int64_t>(static_cast<std::int32_t>(LINK_LEAF + LINK_SHIFT)));
  link_register_tail(nullptr, &tail);
  matches += tail.r4 == 0 && tail.r3 == 0xffffffff80200000ULL ? 1U : 0U;
  constexpr unsigned total = 10;
#else
  constexpr unsigned total = 8;
#endif
  std::cout << "matched\t" << matches << '\t' << total << '\n';
  return matches == total ? 0 : 1;
}
