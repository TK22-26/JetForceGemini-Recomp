// jfg-boot — the Phase 6 headless deterministic boot runner.
//
// ROM-free: it boots the representative program on a synthetic cartridge.
// The real entry-point bridge is the private research lane and is not built
// here. Nothing in this runner emits ROM-derived bytes.
//
// Subcommands:
//   self-check         boot once; require stable VI and cross-run determinism
//   report             print the canonical checkpoint record
//   repeat <n>         boot n times; require an identical checkpoint each time
//   invalid-rom        confirm a bad cartridge fails safe with no execution
//   event-log          print the boot event names in order

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <string_view>

#include "jfg/boot/driver.hpp"
#include "jfg/boot/representative.hpp"

namespace {

using namespace jfg::boot;

BootReport boot_representative() {
    return run_boot(
        representative::synthetic_rom(0x10000U),
        [](BootRuntime& runtime) { representative::install(runtime); },
        BootConfig{});
}

int fail(const char* message) {
    std::fprintf(stderr, "jfg-boot: FAIL: %s\n", message);
    return 1;
}

int run_self_check() {
    const BootReport first = boot_representative();
    if (!first.reached_gate()) {
        return fail("representative boot did not reach stable VI");
    }
    if (first.rsp_tasks.empty()) {
        return fail("expected at least one captured RSP task");
    }
    if (!first.stub_ledger.empty()) {
        return fail("representative boot must reach no unsupported operation");
    }
    const BootReport second = boot_representative();
    if (canonical_checkpoint(first) != canonical_checkpoint(second)) {
        return fail("boot is not deterministic across runs");
    }
    std::printf(
        "jfg-boot: self-check OK (vi_retraces=%llu, events=%llu, threads=%llu)\n",
        static_cast<unsigned long long>(first.vi_retraces),
        static_cast<unsigned long long>(first.dispatched_events),
        static_cast<unsigned long long>(first.threads_created));
    return 0;
}

int run_report() {
    const BootReport report = boot_representative();
    std::printf("%s\n", canonical_checkpoint(report).c_str());
    return report.reached_gate() ? 0 : 1;
}

int run_repeat(const char* count_text) {
    const long count = std::strtol(count_text, nullptr, 10);
    if (count < 2 || count > 1000) {
        return fail("repeat count must be in 2..1000");
    }
    const std::string baseline = canonical_checkpoint(boot_representative());
    for (long run = 1; run < count; ++run) {
        if (canonical_checkpoint(boot_representative()) != baseline) {
            std::fprintf(stderr, "jfg-boot: NONDETERMINISM at run %ld\n", run);
            return 1;
        }
    }
    std::printf("jfg-boot: %ld boots identical\n", count);
    return 0;
}

int run_invalid_rom() {
    std::vector<std::uint8_t> bad(0x2000U, 0xFFU); // wrong magic
    const BootReport report = run_boot(
        bad, [](BootRuntime& runtime) { representative::install(runtime); },
        BootConfig{});
    if (report.status != BootStatus::kInvalidRom) {
        return fail("invalid ROM did not fail safe");
    }
    if (report.vi_retraces != 0U || report.threads_created != 0U) {
        return fail("invalid ROM executed boot work");
    }
    std::printf("jfg-boot: invalid ROM rejected with no execution\n");
    return 0;
}

int run_event_log() {
    // Re-run with journal introspection is not exposed through the report;
    // the canonical checkpoint's journal digest is the stable witness. Print
    // the high-level outcome so a human can eyeball a boot.
    const BootReport report = boot_representative();
    std::printf(
        "status=%u vi=%llu events=%llu threads=%llu rsp=%zu journal=%s\n",
        static_cast<unsigned>(report.status),
        static_cast<unsigned long long>(report.vi_retraces),
        static_cast<unsigned long long>(report.dispatched_events),
        static_cast<unsigned long long>(report.threads_created),
        report.rsp_tasks.size(), report.journal_hex.c_str());
    return report.reached_gate() ? 0 : 1;
}

} // namespace

int main(const int argc, const char* const* argv) {
    if (argc >= 2) {
        const std::string_view command = argv[1];
        if (command == "self-check" && argc == 2) {
            return run_self_check();
        }
        if (command == "report" && argc == 2) {
            return run_report();
        }
        if (command == "repeat" && argc == 3) {
            return run_repeat(argv[2]);
        }
        if (command == "invalid-rom" && argc == 2) {
            return run_invalid_rom();
        }
        if (command == "event-log" && argc == 2) {
            return run_event_log();
        }
    }
    std::fprintf(
        stderr,
        "usage: jfg-boot self-check | report | repeat <n> | invalid-rom | "
        "event-log\n");
    return 2;
}
