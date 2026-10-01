#pragma once
// Host-only bounded entry/effect stream. Raw Count and PCs retain producer
// meaning; this is not full CPU state, hardware retirement or clock alignment.
#include <array>
#include <cstdint>
#include <initializer_list>
#include <ostream>

namespace jfg::boot {
struct InstructionEffectRow {
  // 0: entry, 1: ordinary effect, 2: ERET before host handoff.
  std::uint32_t phase, section, pc, opcode, owner, thread_word;
  std::uint32_t count, status, cause, target, selected_owner, device_sequence;
  std::array<std::uint64_t, 32> gpr;
};

class InstructionEffectTrace final {
public:
  static constexpr std::uint32_t max_rows = 4194304;
  static constexpr std::uint64_t max_bytes = 512ULL * 1024ULL * 1024ULL;

  bool open(std::ostream& stream, std::uint32_t update,
            std::uint32_t row_limit = max_rows, std::uint64_t byte_limit = max_bytes) {
    if (failed_ || stream_ || !update || update > 1000000 || !row_limit || row_limit > max_rows ||
        byte_limit < 17 || byte_limit > max_bytes) return fail();
    stream_ = &stream;
    update_ = update; row_limit_ = row_limit; byte_limit_ = byte_limit;
    stream.write("JFGEFX1\0", 8);
    u32(update);
    bytes_ = 12;
    stream.flush();
    return stream.good() || fail();
  }

  bool advance(std::uint32_t invocation) {
    if (failed_ || !stream_) return false;
    if (complete_) return true;
    if (invocation < previous_invocation_) return fail();
    previous_invocation_ = invocation;
    if (invocation > update_) {
      if (pending_ || rows_ == 0 || bytes_ + 5 > byte_limit_) return fail();
      stream_->put(static_cast<char>(0xff)); u32(rows_); bytes_ += 5;
      stream_->flush();
      complete_ = stream_->good();
      return complete_ || fail();
    }
    return true;
  }

  bool emit(std::uint32_t invocation, const InstructionEffectRow& row) {
    if (!advance(invocation)) return false;
    if (complete_ || invocation < update_) return true;
    if (row.phase > 2 || row.gpr[0] != 0 || !row.pc ||
        ((row.pc | row.owner | row.thread_word | row.target | row.selected_owner) & 3U) ||
        row.device_sequence < previous_device_ || row.device_sequence > 65536U || rows_ == row_limit_)
      return fail();
    if (row.phase == 0) {
      if (pending_ || row.target || row.selected_owner) return fail();
    } else {
      if (!pending_ || row.section != entry_.section || row.pc != entry_.pc ||
          row.opcode != entry_.opcode || row.owner != entry_.owner) return fail();
      if (row.phase == 1 && (row.opcode == 0x42000018U || row.target || row.selected_owner)) return fail();
      if (row.phase == 2 && (row.opcode != 0x42000018U || (row.status & 6U) ||
          !row.target || !row.selected_owner || row.thread_word != row.selected_owner)) return fail();
    }
    std::uint32_t mask = 0;
    unsigned changed = 0;
    for (unsigned index = 0; index < 32; ++index) {
      if (rows_ == 0 || row.gpr[index] != previous_gpr_[index]) {
        mask |= std::uint32_t{1} << index;
        ++changed;
      }
    }
    // One tag, eleven scalar words, a GPR mask, and changed full-width GPRs.
    const std::uint64_t size = 49U + 8U * changed;
    if (bytes_ + size + 5U > byte_limit_) return fail();
    stream_->put(static_cast<char>(row.phase));
    for (auto value : {row.section, row.pc, row.opcode, row.owner, row.thread_word,
                      row.count, row.status, row.cause, row.target, row.selected_owner, row.device_sequence})
      u32(value);
    u32(mask);
    for (unsigned index = 0; index < 32; ++index)
      if (mask & (std::uint32_t{1} << index)) u64(row.gpr[index]);
    if (!stream_->good()) return fail();
    bytes_ += size; ++rows_;
    previous_device_ = row.device_sequence;
    previous_gpr_ = row.gpr;
    pending_ = row.phase == 0;
    if (pending_) entry_ = row;
    return true;
  }

  [[nodiscard]] bool complete() const { return complete_; }
  [[nodiscard]] std::uint32_t rows() const { return rows_; }
  [[nodiscard]] std::uint64_t bytes() const { return bytes_; }

private:
  bool fail() { failed_ = true; return false; }
  void u32(std::uint32_t value) {
    for (unsigned shift = 0; shift < 32; shift += 8) stream_->put(static_cast<char>(value >> shift));
  }
  void u64(std::uint64_t value) {
    for (unsigned shift = 0; shift < 64; shift += 8) stream_->put(static_cast<char>(value >> shift));
  }
  std::ostream* stream_ = nullptr;
  std::uint32_t update_ = 0, previous_invocation_ = 0, previous_device_ = 0, rows_ = 0, row_limit_ = 0;
  std::uint64_t bytes_ = 0, byte_limit_ = 0;
  std::array<std::uint64_t, 32> previous_gpr_{};
  InstructionEffectRow entry_{};
  bool complete_ = false, failed_ = false, pending_ = false;
};
}
