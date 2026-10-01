// Private original OS bodies; independent memory/register driver.
extern "C" {
#include "recomp.h"
void fn_000_1573_recomp(uint8_t*, recomp_context*);
void fn_000_1556_recomp(uint8_t*, recomp_context*);
void fn_000_1641_recomp(uint8_t*, recomp_context*);
}
#include "jfg/boot/sp_status.hpp"
#include <sys/mman.h>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
using jfg::boot::SpStatus;
static uint8_t* memory;
static SpStatus sp;
static unsigned instructions, writes;
static unsigned helper_instruction, store_instruction;
static bool pending_write;
static void check(bool condition) { if (!condition) std::abort(); }
static void finish_store() {
  if (!pending_write) return;
  std::uint32_t command = 0;
  std::memcpy(&command, memory + 0x24040010, 4);
  check(sp.command(command));
  pending_write = false;
  ++writes;
}
extern "C" void jfg_phase9_execution_probe(unsigned, unsigned pc, unsigned word, void* opaque) {
  finish_store();
  check(++instructions < 1000);
  if (pc == 0x80098030) helper_instruction = instructions;
  if (pc == 0x80098038) store_instruction = instructions;
  const auto& ctx = *static_cast<recomp_context*>(opaque);
  // These qualified routines use t6 for SP MMIO and sp for stack accesses.
  if (((word >> 21) & 31) != 14) return;
  const auto address = static_cast<std::uint32_t>(ctx.r14) +
      static_cast<std::uint32_t>(static_cast<std::int16_t>(word));
  if (address != 0xa4040010) return;
  if ((word >> 26) == 0x23) {
    const auto value = sp.read();
    std::memcpy(memory + 0x24040010, &value, 4);
  } else if ((word >> 26) == 0x2b) pending_write = true;
}
extern "C" recomp_func_t* get_function(int32_t address) {
  switch (static_cast<std::uint32_t>(address)) {
  case 0x80098030: return fn_000_1556_recomp;
  case 0x8009b9f0: return fn_000_1641_recomp;
  default: std::abort();
  }
}
int main() {
  constexpr auto span = 0x25000000U;
  memory = static_cast<uint8_t*>(mmap(nullptr, span, PROT_READ | PROT_WRITE,
      MAP_PRIVATE | MAP_ANONYMOUS, -1, 0));
  check(memory != MAP_FAILED);
  unsigned cases = 0;
  for (unsigned initial : {1U, 3U, 0x43U, 0x243U, 0x7fc3U}) {
    for (unsigned displacement : {0U, 8U, 16U, 24U}) {
      check(sp.initialize(initial, false));
      recomp_context ctx{};
      ctx.r4 = static_cast<gpr>(static_cast<std::int32_t>(0x80001000));
      ctx.r29 = static_cast<gpr>(static_cast<std::int32_t>(0x80010000 + displacement));
      ctx.r31 = static_cast<gpr>(static_cast<std::int32_t>(0x80000400));
      ctx.r16 = 1234;
      const auto old_sp = ctx.r29;
      instructions = writes = 0;
      pending_write = false;
      fn_000_1573_recomp(memory, &ctx);
      finish_store();
      check(instructions == 24 && writes == 1 && ctx.r29 == old_sp && ctx.r16 == 1234 &&
          static_cast<std::uint32_t>(ctx.r31) == 0x80000400);
      check(helper_instruction == 18 && store_instruction == 20);
      check(sp.read() == ((initial & ~0x23U) | 0x40U) && !sp.interrupt());
      ++cases;
    }
  }
  check(munmap(memory, span) == 0);
  std::cout << "passed\t" << cases << "\ninstructions_per_ready_start\t24\n";
}
