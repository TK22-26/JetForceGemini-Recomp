#include "jfg/boot/reference_flash_bus.hpp"
#include "jfg/boot/reference_pi_dma.hpp"
#include <array>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <source_location>
#include <string>

int main(int argc, char** argv) {
  auto check = [](bool ok, std::source_location at = std::source_location::current()) {
    if (!ok) { std::fprintf(stderr, "flash check at %u\n", at.line()); std::abort(); }
  };
  check(argc == 1 || argc == 4 || argc == 5);
  std::ifstream trace, commands, epochs, clears;
  auto header = [&](std::ifstream& stream, const char* expected) {
    std::string line; check(bool(std::getline(stream, line)));
    if (!line.empty() && line.back() == '\r') line.pop_back();
    check(line == expected);
  };
  if (argc >= 4) {
    trace.open(argv[1]); commands.open(argv[2]); epochs.open(argv[3]);
    header(trace, "phase\tstage\tlaunch\tlast_pending\tfirst_complete\tpi_status\tpayload");
    header(commands, "phase\tstage\tcommand\tstatus_before\tstatus_after");
    header(epochs, "phase\tstage\tbefore_store\tafter_store\tmfc0_value");
    if (argc == 5) {
      clears.open(argv[4]);
      header(clears, "phase\tstage\tcommand\tstatus_before\tstatus_after");
    }
  }
  jfg::FlashRamStore store;
  jfg::boot::ReferenceFlashBus bus;
  jfg::boot::ReferencePiDma pi;
  bus.bind(store);
  std::array<std::uint8_t, 512> ram{};
  auto callback = +[](void* owner, bool read, std::uint32_t cart, std::uint32_t dram,
                               std::uint32_t length, std::span<std::uint8_t> memory) {
    return static_cast<jfg::boot::ReferenceFlashBus*>(owner)->transfer(read, cart, dram, length, memory);
  };
  auto put = [&](unsigned address, std::uint8_t value) { ram[address ^ 3U] = value; };
  for (unsigned phase = 0; phase < 8; ++phase) {
    ram.fill(0xcc);
    for (unsigned i = 0; i < 128; ++i) put(i, static_cast<std::uint8_t>(phase + 7 * i));
    auto command = [&](unsigned stage, std::uint32_t value) {
      const auto before = bus.status();
      check(bus.command(value, ram));
      if (argc >= 4) {
        unsigned p, s; std::uint32_t v, b, a;
        check(bool(commands >> p >> s >> v >> b >> a));
        check(p == phase && s == stage && v == value && b == before && a == bus.status());
      }
      const auto after = bus.status();
      check(bus.write_status(0) && bus.status() == after);
      if (argc == 5) {
        unsigned p, s; std::uint32_t v, b, a;
        check(bool(clears >> p >> s >> v >> b >> a));
        check(p == phase && s == stage && v == value && b == after && a == bus.status());
      }
    };
    auto transfer = [&](unsigned stage) {
      const auto cart = 0x08000000U + (stage == 0 || stage == 2 ? 0U : phase * 64U);
      check(pi.write(16, 2, 1000, ram, {}));
      check(pi.write(0, stage == 2 ? 0 : 256, 1000, ram, {}));
      check(pi.write(4, cart, 1000, ram, {}));
      check(pi.write(stage == 2 ? 8 : 12, stage == 0 ? 7 : 127, 1000, ram, {}, callback, &bus));
      check(pi.read(16) == 1U && pi.deadline() == 5096U);
      if (argc >= 4) {
        unsigned p, s, status; std::uint64_t launch, last, first;
        std::string payload;
        check(bool(trace >> p >> s >> launch >> last >> first >> status >> payload));
        check(p == phase && s == stage && status == 1);
        std::string actual;
        constexpr char digits[] = "0123456789abcdef";
        for (unsigned i = 256; i < 384; ++i) {
          const auto value = ram[i ^ 3U]; actual += digits[value >> 4]; actual += digits[value & 15];
        }
        check(actual == payload);
        std::uint64_t before, after, mfc0;
        check(bool(epochs >> p >> s >> before >> after >> mfc0));
        check(p == phase && s == stage && before == launch && mfc0 == before && after == before + 4);
        check(last < after + 4096 && after + 4096 <= first);
      }
      pi.advance(5095); check(!pi.interrupt());
      pi.advance(5096); check(pi.interrupt() && pi.read(16) == 0U);
    };
    command(0, 0xd2000000); command(0, 0xe1000000); transfer(0);
    command(1, 0xf0000000); transfer(1);
    for (unsigned i = 256; i < 384; ++i) check(ram[i ^ 3U] == 0xff);
    command(2, 0xb4000000); transfer(2); command(2, 0xa5000000 | phase);
    if (phase & 1) { put(0, 0x12); put(1, 0x34); put(2, 0x56); put(3, 0x78); }
    command(2, 0xd2000000); command(3, 0xf0000000); transfer(3);
    for (unsigned i = 0; i < 128; ++i) check(ram[(256 + i) ^ 3U] == ram[i ^ 3U]);
    command(3, 0x4b000000 | phase); command(3, 0x78000000); command(3, 0xd2000000);
    command(4, 0xf0000000); transfer(4);
    for (unsigned i = 256; i < 384; ++i) check(ram[i ^ 3U] == 0xff);
  }
  check(bus.mutations() == 16 && pi.transfers() == 40);
  const auto before = bus.status();
  check(!bus.command(0x78000001, ram) && bus.status() == before);
  check(!bus.command(0x4b000400, ram));
  check(!bus.transfer(true, 0x0800ffc0, 0, 256, ram));
  check(!bus.transfer(false, 0x08000000, 0, 128, ram));
  if (argc >= 4) {
    std::string result, truth, extra; unsigned count;
    check(bool(trace >> result >> truth >> count) && result == "result" && truth == "true" && count == 40);
    check(!(trace >> extra) && !(commands >> extra) && !(epochs >> extra));
    if (argc == 5) check(!(clears >> extra));
  }
}
