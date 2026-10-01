// Independent task/ABI driver; original routines are private generated inputs.
extern "C" {
#include "recomp.h"
}
#include "jfg/boot/reference_cache.hpp"
#include "jfg/boot/reference_sp_dma.hpp"
#include "jfg/boot/sp_status.hpp"
#include <sys/mman.h>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <span>
using jfg::boot::ReferenceSpDma;
using jfg::boot::SpStatus;
static uint8_t* memory;
static ReferenceSpDma dma;
static SpStatus sp;
static unsigned instructions;
static unsigned annulled, last_pc, last_opcode;
static std::uint32_t pending;
static void check(bool condition) { if (!condition) std::abort(); }
static std::uint32_t word(const uint8_t* p) { std::uint32_t v; std::memcpy(&v, p, 4); return v; }
static void put(uint8_t* p, std::uint32_t v) { std::memcpy(p, &v, 4); }
static void finish_store() {
  if (pending == 0) return;
  const auto value = word(memory + pending - 0x80000000U);
  if (pending == 0xa4080000U) check(dma.write_pc(value));
  else if (pending == 0xa4040010U) check(sp.command(value));
  else check(dma.write(pending - 0xa4040000U, value, {memory, 0x400000}));
  pending = 0;
}
extern "C" void jfg_phase9_execution_probe(unsigned, unsigned pc, unsigned opcode, void* opaque) {
  finish_store();
  if (instructions != 0 && last_opcode >> 26 >= 0x14 && last_opcode >> 26 <= 0x17 &&
      pc == last_pc + 8) ++annulled;
  last_pc = pc;
  last_opcode = opcode;
  check(++instructions < 10000);
  if (opcode >> 26 != 0x23 && opcode >> 26 != 0x2b) return;
  const auto& c = *static_cast<recomp_context*>(opaque);
  const std::array<gpr, 32> r{0,c.r1,c.r2,c.r3,c.r4,c.r5,c.r6,c.r7,c.r8,c.r9,c.r10,c.r11,
    c.r12,c.r13,c.r14,c.r15,c.r16,c.r17,c.r18,c.r19,c.r20,c.r21,c.r22,c.r23,c.r24,c.r25,
    c.r26,c.r27,c.r28,c.r29,c.r30,c.r31};
  const auto address = static_cast<std::uint32_t>(r[(opcode >> 21) & 31]) +
      static_cast<std::uint32_t>(static_cast<std::int16_t>(opcode));
  if (address < 0xa4040000 || address > 0xa4080000) return;
  if (opcode >> 26 == 0x2b) { pending = address; return; }
  auto value = address == 0xa4080000 ? std::optional<std::uint32_t>{dma.pc()} :
      address == 0xa4040010 ? std::optional<std::uint32_t>{sp.read()} : dma.read(address - 0xa4040000);
  check(value.has_value());
  put(memory + address - 0x80000000U, *value);
}
extern "C" void cache_op(uint8_t*, recomp_context*, uint32_t operation, gpr address) {
  check(jfg::boot::reference_coherent_cache_operation(operation, address, 0x400000));
}
// The task matrix uses only unmapped KSEG0 addresses. Mapped paths must not
// silently acquire a fabricated translation in this limited test driver.
extern "C" gpr cop0_read(recomp_context*, unsigned) { std::abort(); }
extern "C" void cop0_write(recomp_context*, unsigned, gpr) { std::abort(); }
extern "C" void cop0_tlb_op(recomp_context*, unsigned) { std::abort(); }
static void hex_words(std::span<const uint8_t> data) {
  std::cout << std::hex << std::setfill('0');
  for (unsigned i = 0; i < data.size(); i += 4) std::cout << std::setw(8) << word(data.data() + i);
  std::cout << std::dec;
}
int main(int argc, char** argv) {
  check(argc == 2);
  constexpr auto span = 0x25000000U;
  memory = static_cast<uint8_t*>(mmap(nullptr, span, PROT_READ | PROT_WRITE,
      MAP_PRIVATE | MAP_ANONYMOUS, -1, 0));
  check(memory != MAP_FAILED);
  std::ifstream rom(argv[1], std::ios::binary);
  check(rom.good());
  rom.seekg(0x1000 + 0x9f250 - 0x400);
  std::array<uint8_t, 384> boot{};
  rom.read(reinterpret_cast<char*>(boot.data()), boot.size());
  check(rom.gcount() == boot.size());
  for (unsigned i = 0; i < boot.size(); ++i) memory[(0x9f250 + i) ^ 3] = boot[i];
  check(sp.initialize(1, false));
  std::cout << "case\tload_instructions\tload_annulled\tstart_instructions\tsp_mem\tsp_dram\tread_length\tdma_full\tdma_busy\tsp_pc\tsp_status\ttask_dmem\tboot_imem\n";
  unsigned cases = 0;
  for (unsigned type : {1U, 2U}) for (unsigned nops : {1U,8U,64U,256U}) for (unsigned flags : {0U,2U}) {
    check(sp.command(10));
    const std::array<std::uint32_t, 16> task{type, flags, 0x8009f250, 0x180,
      type == 1 ? 0x8009f3d0U : 0x8009da10U, 0x1000,
      type == 1 ? 0x800b0350U : 0x800afc10U, 0x800,
      0x80202000, 0x400, 0, 0, 0x80201000, nops * 8 + (type == 1 ? 16U : 0U), 0x80203000, 0xa00};
    for (unsigned i = 0; i < task.size(); ++i) put(memory + 0x1800 + i * 4, task[i]);
    recomp_context ctx{};
    ctx.r4 = static_cast<gpr>(static_cast<std::int32_t>(0x80001800));
    ctx.r29 = static_cast<gpr>(static_cast<std::int32_t>(0x803fefe0));
    ctx.r31 = static_cast<gpr>(static_cast<std::int32_t>(0x80000400));
    const auto stack = ctx.r29;
    instructions = annulled = 0;
    get_function(static_cast<std::int32_t>(0x8009905c))(memory, &ctx);
    finish_store();
    const auto load_instructions = instructions;
    const auto load_annulled = annulled;
    check(ctx.r29 == stack && dma.transfers() == 2 * (cases + 1));
    const auto status = sp.read();
    ctx.r4 = static_cast<gpr>(static_cast<std::int32_t>(0x80001800));
    instructions = 0;
    get_function(static_cast<std::int32_t>(0x800991bc))(memory, &ctx);
    finish_store();
    check(ctx.r29 == stack && instructions == 24);
    std::cout << ++cases << '\t' << load_instructions << '\t' << load_annulled << '\t' << instructions;
    for (unsigned offset : {0U,4U,8U,0x14U,0x18U}) std::cout << '\t' << *dma.read(offset);
    std::cout << '\t' << dma.pc() << '\t' << status << '\t';
    hex_words(dma.memory().subspan(0xfc0, 64));
    std::cout << '\t';
    hex_words(dma.memory().subspan(0x1000, 384));
    std::cout << '\n';
    check(sp.complete_task());
  }
  check(munmap(memory, span) == 0);
  std::cout << "passed\t" << cases << '\n';
}
