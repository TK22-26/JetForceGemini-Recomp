#include "jfg/boot/instruction_effect_trace.hpp"
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>

using jfg::boot::InstructionEffectRow;
using jfg::boot::InstructionEffectTrace;
static void require(bool value) { if (!value) std::abort(); }
static InstructionEffectRow entry() {
  InstructionEffectRow row{};
  row.pc = 0x00401000U; row.opcode = 0x24020007U; row.owner = row.thread_word = 0x80001000U;
  row.count = 0xfffffffcU; row.status = 0x2400ff01U; row.device_sequence = 11;
  for (unsigned index = 1; index < 32; ++index)
    row.gpr[index] = (std::uint64_t{index} << 32U) | (0x80000000U + index * 3U);
  row.gpr[2] = 0;
  row.gpr[31] = 0xffffffff80004000ULL;
  return row;
}
int main(int argc, char** argv) {
  require(argc == 2);
  std::ostringstream output(std::ios::binary);
  InstructionEffectTrace trace;
  require(trace.open(output, 7));
  auto row = entry();
  require(trace.emit(6, row) && trace.rows() == 0);
  require(trace.emit(7, row));
  row.phase = 1; row.gpr[2] = 7; row.count = 0;
  require(trace.emit(7, row));
  row.phase = 0; row.pc = 0x800759c0U; row.opcode = 0x42000018U; row.status |= 2U;
  require(trace.emit(7, row));
  row.phase = 2; row.status &= ~2U; row.target = 0x80302514U;
  row.selected_owner = row.thread_word = 0x80105410U;
  require(trace.emit(7, row));
  require(!trace.complete() && trace.rows() == 4);
  require(trace.advance(8) && trace.complete());
  require(output.str().size() == trace.bytes());
  std::ofstream artifact(argv[1], std::ios::binary);
  artifact << output.str(); artifact.close(); require(artifact.good());

  unsigned rejected = 0;
  for (unsigned test = 0; test < 13; ++test) {
    std::ostringstream stream(std::ios::binary);
    InstructionEffectTrace probe;
    require(probe.open(stream, 7, test == 10 ? 1U : InstructionEffectTrace::max_rows,
                       test == 11 ? 17U : InstructionEffectTrace::max_bytes));
    auto bad = entry();
    bool result = true;
    if (test == 0) { bad.gpr[0] = 1; result = probe.emit(7, bad); }
    if (test == 1) { ++bad.pc; result = probe.emit(7, bad); }
    if (test == 2) { bad.phase = 1; result = probe.emit(7, bad); }
    if (test == 3) { require(probe.emit(7, bad)); result = probe.emit(7, bad); }
    if (test == 4) { require(probe.emit(7, bad)); bad.phase = 1; bad.pc += 4; result = probe.emit(7, bad); }
    if (test == 5) { require(probe.emit(7, bad)); bad.phase = 1; --bad.device_sequence; result = probe.emit(7, bad); }
    if (test == 6) {
      bad.opcode = 0x42000018U; require(probe.emit(7, bad));
      bad.phase = 1; result = probe.emit(7, bad);
    }
    if (test == 7) {
      bad.opcode = 0x42000018U; require(probe.emit(7, bad));
      bad.phase = 2; bad.status |= 2U; bad.target = 0x80004000U;
      bad.selected_owner = bad.thread_word; result = probe.emit(7, bad);
    }
    if (test == 8) { require(probe.emit(7, bad)); result = probe.advance(8); }
    if (test == 9) { result = probe.advance(8); }
    if (test == 10) { require(probe.emit(7, bad)); bad.phase = 1; result = probe.emit(7, bad); }
    if (test == 11) { result = probe.emit(7, bad); }
    if (test == 12) { stream.setstate(std::ios::badbit); result = probe.emit(7, bad); }
    require(!result && !probe.complete() && !probe.advance(8));
    ++rejected;
  }
  std::cout << "passed\t4\t" << rejected << '\n';
}
