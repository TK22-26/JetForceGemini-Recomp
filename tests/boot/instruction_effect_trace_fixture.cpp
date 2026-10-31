// Wrap the existing independently checked generated-instruction fixture.
// Context ownership, invocation and Count here are synthetic transport fields;
// instruction order, link/store effects and GPRs come from the generated code.
extern "C" {
#include "recomp.h"
void effect_fixture_expected(unsigned, unsigned, uint8_t*, recomp_context*);
}
#include "jfg/boot/instruction_effect_trace.hpp"
#include "effect_opcodes.h"
#include <cstdlib>
#include <fstream>

namespace {
struct Recorder {
  std::ofstream output;
  jfg::boot::InstructionEffectTrace trace;
  bool enabled = false;
  Recorder() {
    const char* path = std::getenv("JFG_EFFECT_TRACE_FIXTURE");
    if (!path) return;
    output.open(path, std::ios::binary);
    if (!output || !trace.open(output, 7)) std::abort();
    enabled = true;
  }
  ~Recorder() {
    if (enabled && (!trace.advance(8) || !trace.complete())) std::abort();
  }
};
Recorder recorder;
}

extern "C" void effect_observe(unsigned phase, unsigned pc, uint8_t* ram, recomp_context* ctx) {
  effect_fixture_expected(phase, pc, ram, ctx);
  if (!recorder.enabled) return;
  bool found = false;
  unsigned word = 0;
  for (const auto& opcode : effect_opcodes) {
    if (opcode.pc == pc) { found = true; word = opcode.word; break; }
  }
  if (!found) std::abort();
  jfg::boot::InstructionEffectRow row{};
  row.phase = phase; row.pc = pc; row.opcode = word;
  row.owner = row.thread_word = 0x80001000U;
  row.gpr = {0,
#define GPR(n) static_cast<std::uint64_t>(ctx->r##n)
    GPR(1), GPR(2), GPR(3), GPR(4), GPR(5), GPR(6), GPR(7), GPR(8),
    GPR(9), GPR(10), GPR(11), GPR(12), GPR(13), GPR(14), GPR(15), GPR(16),
    GPR(17), GPR(18), GPR(19), GPR(20), GPR(21), GPR(22), GPR(23), GPR(24),
    GPR(25), GPR(26), GPR(27), GPR(28), GPR(29), GPR(30), GPR(31)
#undef GPR
  };
  if (!recorder.trace.emit(7, row)) std::abort();
}
