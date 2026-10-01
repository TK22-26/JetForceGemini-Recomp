#include "jfg/boot/tlb.hpp"
#include <cstdlib>
#include <iostream>

using jfg::boot::Tlb32;
static void check(bool value, const char* why) {
  if (!value) { std::cerr << why << '\n'; std::exit(1); }
}
static Tlb32 initialized() {
  Tlb32 tlb;
  for (unsigned i = 0; i < 32; ++i)
    check(tlb.write_indexed(i, {0x80000000U + i * 0x2000U, 0, 0, 0}), "initialize unique tags");
  return tlb;
}
int main() {
  Tlb32 unknown;
  check(!unknown.read_indexed(0), "reset entry is unknown");
  check(unknown.probe(0).status == Tlb32::ProbeStatus::uninitialized, "unknown not a miss");
  auto tlb = initialized();
  check(tlb.probe(0).status == Tlb32::ProbeStatus::miss, "unique initialized miss");
  check(tlb.probe(0x80000000).status == Tlb32::ProbeStatus::match, "invalid page still probes");
  check(tlb.write_indexed(35, {0x00400007, 0x407, 0x806, 0}), "write index bit five ignored");
  check(tlb.read_indexed(3)->lo0 == 0x406, "G stored as conjunction of both halves");
  check(tlb.probe(0x00400008).status == Tlb32::ProbeStatus::miss, "ASID mismatch");
  check(tlb.probe(0x00400007).index == 3, "ASID match");
  check(tlb.write_indexed(3, {0x00400007, 0x407, 0x807, 0}), "global entry");
  check(tlb.probe(0x00400008).status == Tlb32::ProbeStatus::match, "global ignores ASID");
  for (auto mask : {0U, 0x6000U, 0x1e000U, 0x7e000U, 0x1fe000U, 0x7fe000U, 0x1ffe000U}) {
    auto pages = initialized();
    check(pages.write_indexed(7, {0x40000005, 7, 7, mask}), "legal page mask");
    check(pages.probe(0x40000005U | mask).index == 7, "masked VPN bits ignored");
    check(pages.probe(0x40000005U + mask + 0x2000U).status == Tlb32::ProbeStatus::miss,
          "next page pair excluded");
    const auto before = pages.read_indexed(7);
    check(!pages.write_indexed(7, {0, 0, 0, 0x2000}), "undefined mask rejected");
    check(pages.read_indexed(7) == before, "invalid write is atomic");
  }
  check(tlb.write_indexed(4, {0x00400007, 7, 7, 0}), "duplicate match setup");
  check(tlb.probe(0x00400007).status == Tlb32::ProbeStatus::multiple_matches,
        "undefined duplicate result not silently chosen");
  jfg::boot::TlbRegisters32 registers;
  check(!registers.read(10) && !registers.read_indexed() && !registers.probe(),
        "uninitialized register operations fail");
  check(!registers.write(12, 1), "unrelated CP0 register refused");
  for (unsigned i = 0; i < 32; ++i) {
    check(registers.write(0, i) && registers.write(10, 0x80000000U + i * 0x2000U) &&
          registers.write(2, 0) && registers.write(3, 0) && registers.write(5, 0) &&
          registers.write_indexed(), "CP0 indexed initialization");
  }
  check(registers.write(10, 0x80004000) && registers.probe() && registers.read(0) == 2U,
        "CP0 probe hit publishes index");
  check(registers.write(10, 0x40000000) && registers.probe() && registers.read(0) == 0x80000000U,
        "CP0 probe miss publishes P bit");
  check(registers.write(0, 34) && registers.read_indexed() && registers.read(10) == 0x80004000U,
        "CP0 indexed read restores selected entry");
  check(registers.write(10, 0x80006000) && registers.write_indexed(), "duplicate CP0 entry");
  check(!registers.probe() && registers.read(0) == 34U, "ambiguous probe leaves registers intact");
  auto reference = jfg::boot::TlbRegisters32::observed_mupen_boot();
  check(reference.probe() && reference.read(0) == 0U && reference.read_indexed() &&
        reference.read(2) == 0U, "explicit reference boot duplicate policy");
  const auto put = [&](unsigned slot, unsigned tag, unsigned lo0, unsigned lo1, unsigned mask) {
    check(reference.write(0, slot) && reference.write(10, tag) && reference.write(2, lo0) &&
          reference.write(3, lo1) && reference.write(5, mask) && reference.write_indexed(),
          "reference fixture TLB write");
  };
  const auto probe = [&](unsigned tag, unsigned expected) {
    check(reference.write(10, tag) && reference.probe() && reference.read(0) == expected,
          "independent original-assembly reference observation");
  };
  put(17, 0x00200007, 0x106, 0x146, 0);
  put(5, 0x00200007, 0x206, 0x246, 0);
  probe(0x00200007, 5);
  probe(0x00200008, 0x80000005);
  put(5, 0x00200007, 0x207, 0x247, 0);
  probe(0x00200008, 5);
  put(5, 0x00200007, 0x207, 0x246, 0);
  probe(0x00200008, 0x80000005);
  put(17, 0x00400007, 0x406, 0x446, 0x6000);
  probe(0x00406007, 17);
  probe(0x00408007, 0x80000011);
  std::cout << "TLB storage/probe tests passed\n";
}
