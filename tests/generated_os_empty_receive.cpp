// Original driver, private original OS bodies. No scheduler/wait-path claim.
extern "C" {
#include "recomp.h"
void fn_000_1526_recomp(uint8_t*, recomp_context*);
void fn_000_1600_recomp(uint8_t*, recomp_context*);
void fn_000_1601_recomp(uint8_t*, recomp_context*);
}
#include <array>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>

static std::uint64_t instructions;
static gpr status;
extern "C" void jfg_phase9_execution_probe(unsigned, unsigned, unsigned, void*) {
  ++instructions;
}
extern "C" gpr cop0_status_read(recomp_context*) { return status; }
extern "C" void cop0_status_write(recomp_context*, gpr value) { status = value; }
extern "C" recomp_func_t* get_function(int32_t address) {
  switch (static_cast<std::uint32_t>(address)) {
  case 0x80099d40: return fn_000_1600_recomp;
  case 0x80099d60: return fn_000_1601_recomp;
  default: std::abort(); // Any blocking/wakeup path is outside this proof.
  }
}
extern "C" void do_break(uint32_t) { std::abort(); }
int main() {
  unsigned cases = 0;
  for (unsigned mask : {0U, 1U, 0x0400ff00U, 0x0400ff01U}) {
    for (unsigned displacement : {0U, 8U, 16U, 24U}) {
      for (unsigned queue_pattern : {0U, 0x5a5a5a5aU}) {
        std::array<std::uint8_t, 8192> memory;
        memory.fill(0xa5);
        for (unsigned i = 0; i < 24; i += 4)
          std::memcpy(memory.data() + 256 + i, &queue_pattern, 4);
        const std::uint32_t empty = 0;
        std::memcpy(memory.data() + 264, &empty, 4);
        const auto before = memory;
        recomp_context context{};
        context.r4 = static_cast<gpr>(static_cast<std::int32_t>(0x80000100));
        context.r5 = 0;
        context.r6 = 0;
        context.r16 = 123;
        context.r17 = 456;
        const auto sp = static_cast<gpr>(static_cast<std::int32_t>(0x80001000U + displacement));
        context.r29 = sp;
        context.r31 = static_cast<gpr>(static_cast<std::int32_t>(0x80000400));
        instructions = 0;
        status = mask;
        fn_000_1526_recomp(memory.data(), &context);
        if (instructions != 40 || static_cast<std::int64_t>(context.r2) != -1 ||
            status != mask || context.r16 != 123 || context.r17 != 456 ||
            context.r29 != sp || static_cast<std::uint32_t>(context.r31) != 0x80000400)
          std::abort();
        for (unsigned i = 0; i < memory.size(); ++i) {
          // The original routine writes only its frame and the caller's O32
          // argument spill area. Invalid queue links must never be touched.
          if (i >= 4096 + displacement - 0x28 && i < 4096 + displacement + 12) continue;
          if (memory[i] != before[i]) std::abort();
        }
        ++cases;
      }
    }
  }
  std::cout << "passed\t" << cases << "\ninstructions_per_empty_receive\t40\n";
}
