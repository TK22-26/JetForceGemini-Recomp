#pragma once

// Independently authored 32-bit VR4300 TLB storage/probe mechanism.
// NEC U10504EJ7V0UM00, chapters 5 and 16. This is not a cache, timing,
// exception-delivery, or 64-bit virtual-address implementation.
#include <array>
#include <cstdint>
#include <optional>

namespace jfg::boot {
class Tlb32 final {
public:
  struct Entry {
    std::uint32_t hi, lo0, lo1, mask;
    bool operator==(const Entry&) const = default;
  };
  enum class ProbeStatus { match, miss, uninitialized, multiple_matches };
  struct Probe { ProbeStatus status; std::uint32_t index; };

  // Reset contents are architecturally undefined. Do not invent valid zero
  // entries. A separately qualified boot profile or guest initialization
  // must explicitly supply every entry before an unambiguous probe.
  bool write_indexed(std::uint32_t index, Entry entry) {
    entry.mask &= 0x01ffe000U;
    if (!valid_mask(entry.mask)) return false;
    entry.hi &= 0xffffe0ffU;
    entry.hi &= ~entry.mask;
    const auto global = (entry.lo0 & entry.lo1) & 1U;
    entry.lo0 = (entry.lo0 & 0x03fffffeU) | global;
    entry.lo1 = (entry.lo1 & 0x03fffffeU) | global;
    // VR4300 Index bit 5 is readable/writable but ignored for TLB access.
    entries_[index & 31U] = entry;
    return true;
  }
  [[nodiscard]] std::optional<Entry> read_indexed(std::uint32_t index) const {
    return entries_[index & 31U];
  }
  [[nodiscard]] Probe probe(std::uint32_t hi) const {
    std::optional<std::uint32_t> found;
    bool unknown = false, multiple = false;
    for (std::uint32_t index = 0; index < entries_.size(); ++index) {
      const auto& candidate = entries_[index];
      if (!candidate) { unknown = true; continue; }
      const auto& entry = *candidate;
      const auto vpn_mask = ~(entry.mask | 0x1fffU);
      if ((hi & vpn_mask) != (entry.hi & vpn_mask) ||
          ((entry.lo0 & 1U) == 0 && (hi & 0xffU) != (entry.hi & 0xffU))) continue;
      // V bits affect translation, not the associative probe itself.
      if (found) multiple = true;
      else found = index;
    }
    if (unknown) return {ProbeStatus::uninitialized, 0};
    if (multiple) return {ProbeStatus::multiple_matches, *found};
    if (!found) return {ProbeStatus::miss, 0};
    return {ProbeStatus::match, *found};
  }
private:
  static constexpr bool valid_mask(std::uint32_t mask) {
    return mask == 0 || mask == 0x6000 || mask == 0x1e000 ||
        mask == 0x7e000 || mask == 0x1fe000 || mask == 0x7fe000 || mask == 0x1ffe000;
  }
  std::array<std::optional<Entry>, 32> entries_{};
};

// CP0 register boundary for the 32-bit indexed/probe operations. The caller
// remains responsible for privilege checks, instruction hazards and timing.
// Random/Wired and 64-bit EntryHi operations are deliberately unsupported.
class TlbRegisters32 final {
public:
  // Explicit reference-only policy: boot fields observed as zero; duplicate
  // matches select the lowest index; misses preserve low Index bits. Never
  // use this factory as a claim about architecturally undefined reset state.
  static TlbRegisters32 observed_mupen_boot() {
    TlbRegisters32 state;
    state.reference_policy_ = true;
    for (unsigned reg : {0U, 2U, 3U, 5U, 10U}) state.registers_[reg] = 0U;
    for (unsigned index = 0; index < 32; ++index)
      (void)state.tlb_.write_indexed(index, {0, 0, 0, 0});
    return state;
  }
  bool write(unsigned reg, std::uint32_t value) {
    std::uint32_t mask;
    switch (reg) {
    case 0: mask = 0x8000003fU; break;
    case 2: case 3: mask = 0x03ffffffU; break;
    case 5: mask = 0x01ffe000U; break;
    case 10: mask = 0xffffe0ffU; break;
    default: return false;
    }
    registers_[reg] = value & mask;
    return true;
  }
  [[nodiscard]] std::optional<std::uint32_t> read(unsigned reg) const {
    return reg < registers_.size() ? registers_[reg] : std::nullopt;
  }
  bool write_indexed() {
    for (unsigned reg : {0U, 2U, 3U, 5U, 10U})
      if (!registers_[reg]) return false;
    return tlb_.write_indexed(*registers_[0],
        {*registers_[10], *registers_[2], *registers_[3], *registers_[5]});
  }
  bool read_indexed() {
    if (!registers_[0]) return false;
    const auto entry = tlb_.read_indexed(*registers_[0]);
    if (!entry) return false;
    registers_[10] = entry->hi;
    registers_[2] = entry->lo0;
    registers_[3] = entry->lo1;
    registers_[5] = entry->mask;
    return true;
  }
  bool probe() {
    if (!registers_[10]) return false;
    const auto result = tlb_.probe(*registers_[10]);
    if (result.status == Tlb32::ProbeStatus::uninitialized ||
        (result.status == Tlb32::ProbeStatus::multiple_matches && !reference_policy_)) return false;
    registers_[0] = result.status == Tlb32::ProbeStatus::miss
        ? 0x80000000U | (reference_policy_ ? registers_[0].value_or(0U) & 0x3fU : 0U)
        : result.index;
    return true;
  }
private:
  Tlb32 tlb_;
  bool reference_policy_ = false;
  std::array<std::optional<std::uint32_t>, 11> registers_{};
};
} // namespace jfg::boot
