#include "jfg/boot/eret_transfer_probe.hpp"
#include <cstdlib>
#include <fstream>
#include <sstream>

using namespace jfg::boot;
static void check(bool valid) { if (!valid) std::abort(); }
static EretTransferRow valid() {
  EretTransferRow row{7, 0x80001000, 0x42000018, 0x80002000, 0x80003000,
                      0x80004000, 0x34000001, 0xfffffff0, {}};
  row.gpr[31] = 0xffffffff80000000ULL;
  return row;
}
int main(int argc, char** argv) {
  std::ostringstream stream;
  EretTransferProbe probe;
  check(probe.open(stream, 7, 8));
  check(probe.advance(6));
  auto row = valid();
  check(probe.emit(row));
  row.invocation = 8;
  row.from_thread = row.to_thread;
  row.count = 2; // Raw native Count may wrap; never impose global ordering.
  check(probe.emit(row));
  check(!probe.complete() && probe.advance(9) && probe.complete());
  const auto text = stream.str();
  check(text.ends_with("result\ttrue\t2\n"));
  check(probe.advance(10) && stream.str() == text);
  if (argc == 2) {
    std::ofstream artifact(argv[1], std::ios::binary);
    artifact << text; artifact.flush(); check(artifact.good());
  }
  for (unsigned mutation = 0; mutation < 8; ++mutation) {
    std::ostringstream invalid_stream;
    EretTransferProbe invalid;
    check(invalid.open(invalid_stream, 7, 8));
    row = valid();
    switch (mutation) {
      case 0: row.opcode = 0; break;
      case 1: row.status |= 2; break;
      case 2: row.status |= 4; break;
      case 3: row.gpr[0] = 1; break;
      case 4: row.to_thread = 0; break;
      case 5: row.target_pc |= 1; break;
      case 6: row.from_thread |= 2; break;
      case 7: row.pc |= 1; break;
    }
    check(!invalid.emit(row) && !invalid.advance(9) && !invalid.complete());
  }
  std::ostringstream backwards;
  EretTransferProbe ordered;
  check(ordered.open(backwards, 7, 8) && ordered.advance(8));
  check(!ordered.advance(7) && !ordered.advance(9));
  std::ostringstream bad;
  bad.setstate(std::ios::badbit);
  EretTransferProbe failed;
  check(!failed.open(bad, 7, 8) && !failed.advance(9));
  std::ostringstream wrong_range;
  EretTransferProbe range;
  check(!range.open(wrong_range, 0, 1) && !range.open(wrong_range, 7, 8));
}
