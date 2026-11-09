// Independent CPU/stackful transport for private original OS code. The guest
// dispatcher, not this driver, chooses the next thread and saves/restores it.
// Integer queues and a bounded SP/lazy-FPU interrupt fixture; not osInitialize.
extern "C" {
#include "recomp.h"
}
#include "jfg/boot/guest_thread_transport.hpp"
#include "jfg/boot/mi_interrupt_mask.hpp"
#include "jfg/boot/tlb.hpp"
#include "jfg/boot/reference_cache.hpp"
#include "jfg/boot/reference_pif_boot.hpp"
#include <sys/mman.h>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>

static uint8_t* memory;
static std::unique_ptr<jfg::boot::GuestThreadTransport<recomp_context>> transport;
static jfg::boot::MiInterruptMask mi;
static std::uint32_t count, epc, pending_store, last_pc, last_opcode;
#if defined(JFG_TEST_INITIALIZE)
static jfg::boot::TlbRegisters32 tlb = jfg::boot::TlbRegisters32::observed_mupen_boot();
static std::ofstream initialization;
static jfg::boot::ReferencePifBoot pif_boot;
#endif
#if defined(JFG_TEST_INTERRUPTS)
static std::uint32_t cause, sp_status = 1;
static bool sp_interrupt, previous_delay, previous_branch;
static unsigned exception_count;
#endif
static unsigned instructions;
#if defined(JFG_TEST_PENDING_MASK)
static std::ofstream exception_trace;
#endif
#if defined(JFG_TEST_VI_MANAGER)
// Independent fixture clock origin, deliberately not the observed IPL epoch.
// Only steady-state worker intervals are qualified by this bounded experiment.
static std::uint32_t next_vi, vi_period;
static bool vi_interrupt;
#endif
static std::int32_t section_bases[] = {static_cast<std::int32_t>(0x80000400U)};
extern "C" { std::int32_t* section_addresses = section_bases; }
static void check(bool condition, const char* reason) {
  if (!condition) { std::cerr << reason << " pc=" << std::hex << last_pc << '\n'; std::abort(); }
}
static std::uint32_t word(std::uint32_t address) {
  std::uint32_t value;
  std::memcpy(&value, memory + address - 0x80000000U, 4);
  return value;
}
static void put(std::uint32_t address, std::uint32_t value) {
  std::memcpy(memory + address - 0x80000000U, &value, 4);
}
static void finish_store() {
  if (pending_store) {
#if defined(JFG_TEST_VI_MANAGER)
    if (pending_store >= 0xa4400000U && pending_store <= 0xa4400034U) {
      if (pending_store == 0xa4400010U) vi_interrupt = false;
      if (pending_store == 0xa4400018U) {
        const auto value = word(pending_store);
        check(value == 525U, "qualified VI period configuration");
        vi_period = (value + 1) * 1500;
        if (next_vi == 0) next_vi = count + vi_period;
      }
      pending_store = 0;
      return;
    }
#endif
#if defined(JFG_TEST_INITIALIZE)
    if (pending_store == 0xbfc007fcU) {
      check(pif_boot.write(word(pending_store)), "qualified PIF boot acknowledgement");
      put(pending_store, pif_boot.read());
      pending_store = 0;
      return;
    }
#endif
#if defined(JFG_TEST_INTERRUPTS)
    if (pending_store == 0xa4040010U) {
      const auto command = word(pending_store);
      check(command == 0x4010U || command == 8U, "SP interrupt fixture commands");
      if (command == 0x4010U) { sp_status |= 0x200; sp_interrupt = true; }
      else sp_interrupt = false;
      pending_store = 0;
      return;
    }
#endif
    check(pending_store == 0xa430000cU && mi.command(word(pending_store)), "MI command");
    pending_store = 0;
  }
}
static void repair_pointer(recomp_context& context) {
  context.f_odd = context.mips3_float_mode ? &context.f1.u32l : &context.f0.u32h;
#if defined(JFG_TEST_INTERRUPTS)
  set_cop1_cs(context.fcr31);
#endif
}
extern "C" void do_break(std::uint32_t) { std::abort(); }
extern "C" void pause_self(uint8_t*) { std::abort(); }
extern "C" void switch_error(const char*, uint32_t, uint32_t) { std::abort(); }
extern "C" gpr cop0_status_read(recomp_context* context) {
  return static_cast<gpr>(static_cast<std::int64_t>(static_cast<std::int32_t>(context->status_reg)));
}
extern "C" void cop0_status_write(recomp_context* context, gpr value) {
  context->status_reg = static_cast<std::uint32_t>(value);
  context->mips3_float_mode = (value & 0x04000000U) != 0;
  repair_pointer(*context);
}
extern "C" gpr cop0_read(recomp_context*, std::uint32_t reg) {
#if defined(JFG_TEST_INITIALIZE)
  if (const auto value = tlb.read(reg))
    return static_cast<gpr>(static_cast<std::int64_t>(static_cast<std::int32_t>(*value)));
#endif
#if defined(JFG_TEST_INTERRUPTS)
  if (reg == 13) return cause | ((sp_interrupt && (mi.read() & 1)) ? 0x400U : 0U)
#if defined(JFG_TEST_VI_MANAGER)
      | ((vi_interrupt && (mi.read() & 8)) ? 0x400U : 0U)
#endif
      ;
  if (reg == 14) return static_cast<gpr>(static_cast<std::int64_t>(static_cast<std::int32_t>(epc)));
#endif
  check(reg == 9, "only Count reads qualified");
  return static_cast<gpr>(static_cast<std::int64_t>(static_cast<std::int32_t>(count)));
}
extern "C" void cop0_write(recomp_context*, std::uint32_t reg, gpr value) {
#if defined(JFG_TEST_VI_MANAGER)
  if (reg == 11) { check(value == 0, "only timer initialization in VI worker fixture"); return; }
#endif
#if defined(JFG_TEST_INITIALIZE)
  if (tlb.write(reg, static_cast<std::uint32_t>(value))) return;
#endif
#if defined(JFG_TEST_INTERRUPTS)
  if (reg == 13) { cause = (cause & ~0x300U) | (static_cast<std::uint32_t>(value) & 0x300U); return; }
#endif
  check(reg == 14, "only EPC writes qualified");
  epc = static_cast<std::uint32_t>(value);
}
#if defined(JFG_TEST_INITIALIZE)
extern "C" void cache_op(uint8_t*, recomp_context*, uint32_t operation, gpr address) {
  check(jfg::boot::reference_coherent_cache_operation(operation, address, 0x400000), "cache operation");
}
extern "C" void cop0_tlb_op(recomp_context*, uint32_t operation) {
  const bool accepted = operation == 0 ? tlb.probe() : operation == 1 ? tlb.read_indexed() :
                        operation == 2 ? tlb.write_indexed() : false;
  check(accepted, "qualified 32-bit TLB operation");
}
static void record_initialization(const char* label, const recomp_context& c) {
  initialization << label << std::hex << std::setfill('0') << "\tCP0 REG9=" << std::setw(8) << count
    << "\tCP0 REG12=" << std::setw(8) << c.status_reg << "\tCP0 REG13=" << std::setw(8) << cause
    << "\tFCR31=" << std::setw(8) << c.fcr31;
  for (auto address : {0xa4600014U,0xa4600018U,0xa460001cU,0xa4600020U,
      0xa4600024U,0xa4600028U,0xa460002cU,0xa4600030U,0xa4800018U,0xbfc007fcU,
      0xa4500008U,0xa4500010U,0xa4500014U,0xa430000cU})
    initialization << '\t' << std::setw(8) << address << '=' << std::setw(8)
      << (address == 0xa430000cU ? mi.read() : word(address));
  initialization << '\n';
  initialization.flush();
}
#endif
extern "C" void cop0_eret(uint8_t*, recomp_context* context) {
  finish_store();
  check((context->status_reg & 6) == 2, "ERET expects EXL, not ERL");
  context->status_reg &= ~2U;
  const auto next = word(0x800a9e90U);
  check(next == 0x80300000U || next == 0x80300200U
#if defined(JFG_TEST_VI_MANAGER)
      || next == 0x80105410U
#endif
      , "original dispatcher target");
#if defined(JFG_TEST_INTERRUPTS)
  previous_delay = previous_branch = false;
#endif
  transport->eret(next, epc, *context);
}
extern "C" void fixture_setup(uint8_t*, recomp_context* context) {
  // Explicit untimed setup, outside all eight measured intervals. Main data
  // and the initialized thread-tail/runqueue come from the pinned original ROM.
  check(word(0x800a9e80U) == 0 && word(0x800a9e84U) == 0xffffffffU &&
        word(0x800a9e88U) == 0x800a9e80U, "original static thread data");
  check(word(0x800a9a6cU) == 0x003fff01U, "original global interrupt mask");
  cop0_status_write(context, 0x34000000U);
  check(mi.initialize(63), "initial MI mask");
#if defined(JFG_TEST_INTERRUPTS)
  // The oracle independently verifies the installed vector is this original
  // four-instruction position-independent preamble. Execute its real body.
  for (unsigned offset = 0; offset < 16; offset += 4)
    put(0x80000180U + offset, word(0x80075020U + offset));
#endif
}
#if defined(JFG_TEST_INTERRUPTS)
static void exception(recomp_context& context, unsigned pc, unsigned code) {
  check(!(context.status_reg & 2), "nested exception unsupported");
  epc = pc;
  transport->park_at(pc);
  cause = (cause & ~0x8000007cU) | (code << 2);
  if (code == 11) cause = (cause & ~0x30000000U) | 0x10000000U;
  context.status_reg |= 2;
  ++exception_count;
  previous_delay = previous_branch = false;
  for (unsigned offset = 0; offset < 16; offset += 4)
    check(word(0x80000180U + offset) == word(0x80075020U + offset), "installed vector bytes");
  get_function(static_cast<std::int32_t>(0x80075020U))(memory, &context);
  check(epc == pc && !(context.status_reg & 2), "exception resumes exact instruction");
}
#endif
extern "C" void jfg_phase9_execution_probe(unsigned, unsigned pc, unsigned opcode, void* opaque) {
  finish_store();
#if defined(JFG_TEST_PENDING_MASK)
  if (pc == 0x80075030U)
    exception_trace << std::hex << std::setfill('0') << std::setw(8)
        << (cause | ((sp_interrupt && (mi.read() & 1U)) ? 0x400U : 0U)) << '\t'
        << std::setw(8) << epc << '\t' << std::setw(8) << count << '\n';
#endif
#if defined(JFG_TEST_VI_MANAGER)
  const bool complete = word(0x80301780U) == 0x4a464756U;
  if (next_vi && count >= next_vi) { next_vi += vi_period; vi_interrupt = true; }
#elif defined(JFG_TEST_INTERRUPTS)
  const bool complete = word(0x80301780U) == 0x4a464749U;
#else
  const bool complete = word(0x80301588U) == 0x4a464754U;
#endif
  if (complete) {
    transport->stop();
  }
  auto& c = *static_cast<recomp_context*>(opaque);
#if defined(JFG_TEST_INITIALIZE)
  if (pc == 0x80097520U) record_initialization("entry", c);
  if (pc == 0x80000410U) record_initialization("return", c);
#endif
#if defined(JFG_TEST_INTERRUPTS)
  const bool boundary = previous_delay || (last_opcode & 0xffe0ffffU) == 0x40806000U;
  bool delay = previous_branch && pc == last_pc + 4;
  const bool external = (sp_interrupt && (mi.read() & 1))
#if defined(JFG_TEST_VI_MANAGER)
      || (vi_interrupt && (mi.read() & 8))
#endif
      ;
  if (boundary && external &&
      (c.status_reg & 0x407U) == 0x401U) {
    exception(c, pc, 0);
    delay = false;
  }
  const unsigned primary = opcode >> 26;
  const bool fpu = primary == 0x11 || primary == 0x31 || primary == 0x35 || primary == 0x39 || primary == 0x3d;
  if (fpu && !(c.status_reg & 0x20000000U)) {
    check(!delay, "unqualified delay-slot COP1 exception");
    exception(c, pc, 11);
    check(c.status_reg & 0x20000000U, "original OS enables COP1");
  }
  previous_delay = delay;
  previous_branch = primary == 1 || (primary >= 2 && primary <= 7) ||
      (primary >= 20 && primary <= 23) || (primary == 0 && ((opcode & 63) == 8 || (opcode & 63) == 9)) ||
      (primary == 0x11 && ((opcode >> 21) & 31) == 8);
#endif
  // Entered instructions plus independently qualified Mupen annulled slots.
  if (instructions && last_opcode >> 26 >= 0x14 && last_opcode >> 26 <= 0x17 && pc == last_pc + 8)
    count += 2;
  last_pc = pc;
  last_opcode = opcode;
  // Independent ERET/control micro-ROM qualifies zero Count increment for
  // ERET in this Mupen profile. This is not a hardware latency assertion.
  if (opcode != 0x42000018U) count += 2;
  check(++instructions <
#if defined(JFG_TEST_VI_MANAGER)
      20000000U,
#else
      100000U,
#endif
      "instruction limit");
#if !defined(JFG_TEST_INTERRUPTS)
  check(opcode >> 26 != 0x11, "FPU execution not qualified by integer fixture");
#endif
  // A JAL into the OS yielding routine establishes the parked continuation.
  if (opcode >> 26 == 3 && ((pc + 4) & 0xf0000000U | (opcode & 0x03ffffffU) << 2) == 0x80075698U)
    transport->park_at(pc + 8);
  if (opcode >> 26 != 0x23 && opcode >> 26 != 0x2b) return;
  const std::array<gpr, 32> r{0,c.r1,c.r2,c.r3,c.r4,c.r5,c.r6,c.r7,c.r8,c.r9,c.r10,c.r11,
    c.r12,c.r13,c.r14,c.r15,c.r16,c.r17,c.r18,c.r19,c.r20,c.r21,c.r22,c.r23,c.r24,c.r25,
    c.r26,c.r27,c.r28,c.r29,c.r30,c.r31};
  const auto address = static_cast<std::uint32_t>(r[(opcode >> 21) & 31]) +
      static_cast<std::uint32_t>(static_cast<std::int16_t>(opcode));
  if (address == 0xa430000cU) {
    if (opcode >> 26 == 0x2b) pending_store = address;
    else put(address, mi.read());
  }
#if defined(JFG_TEST_INTERRUPTS)
  else if (address == 0xa4300008U && primary == 0x23) put(address, (sp_interrupt ? 1U : 0U)
#if defined(JFG_TEST_VI_MANAGER)
      | (vi_interrupt ? 8U : 0U)
#endif
      );
  else if (address == 0xa4040010U) {
    if (primary == 0x2b) pending_store = address;
    else put(address, sp_status);
  }
#endif
#if defined(JFG_TEST_VI_MANAGER)
  else if (address >= 0xa4400000U && address <= 0xa4400034U) {
    if (primary == 0x2b) pending_store = address;
    // V_CURRENT is sampled at the interrupt boundary; this fixture does not
    // qualify scanline reads or arbitrary first-frame phase.
    else if (address == 0xa4400010U) put(address, 0U);
  }
#endif
#if defined(JFG_TEST_INITIALIZE)
  else if (address == 0xbfc007fcU) {
    if (primary == 0x2b) pending_store = address;
  }
  else if (address == 0xa4800018U || (address >= 0xa4600014U && address <= 0xa4600030U))
    check(primary == 0x23 && word(address) == 0U, "qualified idle PI/SI boot register");
  else if (address == 0xa4500008U || address == 0xa4500010U || address == 0xa4500014U)
    check(primary == 0x2b, "initialization AI write");
#endif
  else check(address < 0xa0000000U, "unsupported MMIO");
}
int main(int argc, char** argv) {
#if defined(JFG_TEST_INITIALIZE)
  check(argc ==
#if defined(JFG_TEST_PENDING_MASK)
      4,
#else
      3,
#endif
      "ROM and diagnostic output arguments");
#if defined(JFG_TEST_PENDING_MASK)
  exception_trace.open(argv[3]);
  check(exception_trace.good(), "exception trace output");
  exception_trace << "cause\tepc\tcount\n";
#endif
  initialization.open(argv[2]);
  check(initialization.good(), "initialization output");
  constexpr auto span = 0x40001000U;
#else
  check(argc == 2, "ROM argument");
  constexpr auto span = 0x25000000U;
#endif
  memory = static_cast<uint8_t*>(mmap(nullptr, span, PROT_READ | PROT_WRITE,
      MAP_PRIVATE | MAP_ANONYMOUS, -1, 0));
  check(memory != MAP_FAILED, "map memory");
  std::ifstream rom(argv[1], std::ios::binary);
  check(rom.good(), "open ROM");
  rom.seekg(0x1000);
  for (unsigned i = 0; i < 0xb0750U; ++i) {
    const auto value = rom.get();
    check(value != EOF, "original main data");
    memory[(0x400U + i) ^ 3] = static_cast<uint8_t>(value);
  }
  recomp_context initial{};
#if defined(JFG_TEST_INITIALIZE)
  cop0_status_write(&initial, 0x34000000U);
  check(mi.initialize(0), "reference fixture initial MI mask");
  put(0x80000300U, 1U);
  put(0x80000308U, 0xb0000000U);
  put(0x80000318U, 0x00400000U);
#endif
  initial.r29 = static_cast<gpr>(static_cast<std::int32_t>(0x803ff000U));
  transport = std::make_unique<jfg::boot::GuestThreadTransport<recomp_context>>(
      [](std::uint32_t entry, recomp_context& context) {
        get_function(static_cast<std::int32_t>(entry))(memory, &context);
      }, repair_pointer);
  transport->run(0x80000400U, initial, 256);
  check(transport->handoffs() > 4, "real handoffs required");
#if defined(JFG_TEST_VI_MANAGER)
  check(exception_count == 24, "24 VI interrupts");
  std::cout << "case\tcount\tpayload\tvi_count\ttime_hi\ttime_lo\tstatus\n";
  for (unsigned row = 0; row < 24; ++row) {
    const auto base = 0x80301400U + row * 28;
    std::cout << word(base + 24);
    for (unsigned column = 0; column < 6; ++column) std::cout << '\t' << word(base + column * 4);
    std::cout << '\n';
  }
  std::cout << "result\ttrue\t24\n";
#elif defined(JFG_TEST_INTERRUPTS)
  check(exception_count == 10, "eight SP and two lazy-FPU exceptions");
  std::cout << "case\tticks\thi\tlo\tf0\tfcr31\tworker\tpayload\n";
  for (unsigned row = 0; row < 8; ++row) {
    for (unsigned column = 0; column < 8; ++column) {
      if (column) std::cout << '\t';
      std::cout << word(0x80301400U + row * 32 + column * 4);
    }
    std::cout << '\n';
  }
  std::cout << "result\ttrue\t8\n";
#else
  const char* names[] = {"send_lower", "send_higher", "recv_wake_sender", "recv_final",
    "worker_recv_first", "worker_recv_second", "worker_fill", "worker_block_send"};
  std::cout << "case\tticks\tresult\tvalid\tstatus\n";
  for (unsigned index = 0; index < 8; ++index) {
    const auto base = 0x80301400U + 16 * index;
    std::cout << names[index] << '\t' << word(base) << "\t0x" << std::hex << std::setw(8)
      << std::setfill('0') << word(base + 4) << std::dec << '\t' << word(base + 8)
      << "\t0x" << std::hex << std::setw(8) << word(base + 12) << std::dec << '\n';
  }
  std::cout << "payloads";
  for (unsigned i = 0; i < 4; ++i) std::cout << '\t' << word(0x80301500U + 4 * i);
  std::cout << "\nentry-status";
  for (unsigned i = 0; i < 2; ++i) std::cout << "\t0x" << std::hex << std::setw(8) << word(0x80301590U + 4 * i);
  std::cout << "\nmi-masks";
  for (unsigned i = 0; i < 5; ++i) std::cout << "\t0x" << std::hex << std::setw(8) << word(0x80301598U + 4 * i);
  std::cout << "\nresult\ttrue\t0\t" << word(0x80301584U);
  for (auto addr : {0x80301580U, 0x8030158cU}) std::cout << "\t0x" << std::hex << std::setw(8) << word(addr);
  std::cout << '\n';
#endif
  check(munmap(memory, span) == 0, "unmap memory");
}
