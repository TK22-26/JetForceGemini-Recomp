#pragma once
// Native host-only observation at validated ERET transfer, before host yield.
// Raw Count remains native-owned; this is not a hardware-retirement clock.
#include <array>
#include <cstdint>
#include <iomanip>
#include <ostream>

namespace jfg::boot {
struct EretTransferRow {
  std::uint32_t invocation, pc, opcode, from_thread, to_thread, target_pc;
  std::uint32_t status, count;
  std::array<std::uint64_t, 32> gpr;
};
class EretTransferProbe final {
public:
  static constexpr std::uint32_t limit = 65536;
  bool open(std::ostream& stream, std::uint32_t first, std::uint32_t last) {
    if (failed_ || stream_ || first == 0 || last < first || last > 1000000 || last - first > 17)
      return fail();
    stream_ = &stream; first_ = first; last_ = last;
    stream << "jfg-native-eret-transfers-v1\t" << first << '\t' << last
      << "\nsequence\tinvocation\tpc\topcode\tfrom_thread\tto_thread\ttarget_pc\tstatus\tcount";
    for (unsigned index = 0; index < 32; ++index) stream << "\tr" << index;
    stream << '\n'; stream.flush();
    return stream.good() || fail();
  }
  bool advance(std::uint32_t invocation) {
    if (failed_ || !stream_) return false;
    if (complete_) return true;
    if (invocation < previous_invocation_) return fail();
    previous_invocation_ = invocation;
    if (invocation > last_) {
      *stream_ << "result\ttrue\t" << rows_ << '\n';
      stream_->flush();
      complete_ = stream_->good();
      return complete_ || fail();
    }
    return true;
  }
  bool emit(const EretTransferRow& row) {
    if (!advance(row.invocation)) return false;
    if (complete_ || row.invocation < first_) return true;
    if (rows_ == limit || row.opcode != 0x42000018U || (row.status & 6U) != 0 ||
        row.gpr[0] != 0 || !row.to_thread || (row.pc | row.from_thread |
        row.to_thread | row.target_pc) % 4U) return fail();
    *stream_ << std::dec << ++rows_ << '\t' << row.invocation;
    for (auto value : {row.pc, row.opcode, row.from_thread, row.to_thread,
                      row.target_pc, row.status, row.count})
      *stream_ << "\t0x" << std::hex << std::setfill('0') << std::setw(8) << value;
    for (auto value : row.gpr)
      *stream_ << "\t0x" << std::setw(16) << value;
    *stream_ << std::dec << '\n'; stream_->flush();
    return stream_->good() || fail();
  }
  [[nodiscard]] bool complete() const { return complete_; }
private:
  bool fail() { failed_ = true; return false; }
  std::ostream* stream_ = nullptr;
  std::uint32_t first_ = 0, last_ = 0, previous_invocation_ = 0, rows_ = 0;
  bool failed_ = false, complete_ = false;
};
}
