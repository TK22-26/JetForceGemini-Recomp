// Phase 6 boot tests. Discharges the ten master-plan Phase 6 obligations
// mapped in docs/planning/phase6-acceptance.md. ROM-free: all boots use the
// representative program on a synthetic cartridge.

#include "jfg/boot/driver.hpp"
#include "jfg/boot/representative.hpp"

#include <iostream>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace {

using namespace jfg::boot;
using jfg::testkernel::Journal;
using jfg::testkernel::JournalRecord;
using jfg::testkernel::StateHashSchema;
using jfg::testkernel::VirtualClock;
using jfg::testkernel::World;

int failures = 0;

void check(const bool condition, const std::string_view message) {
    if (!condition) {
        ++failures;
        std::cerr << "FAIL: " << message << '\n';
    }
}

// The pinned emulator/native oracle checkpoint for the representative boot.
// Logic-level digests (canonical little-endian journal, byte-wise state hash)
// are host- and compiler-independent, so this golden holds across platforms.
constexpr std::string_view kOracleCheckpoint =
    "status=1;vi=5;events=14;threads=2;rsp=1;stubs=0;"
    "journal=2f8f8e185e7f380e643e64910d64bb88f77fb46def622cb6277e1f5c6f836800;"
    "state=4edff7780cc9a41302f9fa52fef8d054f5aff4cf57d7a7fe76983753eb77025f";

BootReport boot_once() {
    return run_boot(
        representative::synthetic_rom(0x10000U),
        [](BootRuntime& runtime) { representative::install(runtime); },
        BootConfig{});
}

// Manual harness that keeps the world and journal for inspection.
struct Harness final {
    std::optional<World> world;
    VirtualClock clock;
    Journal journal;
    BootReport report;
};

std::unique_ptr<Harness> boot_with_inspection() {
    auto harness = std::make_unique<Harness>();
    harness->world = World::create(kBootRdramBytes);
    RomImage rom = *RomImage::create(representative::synthetic_rom(0x10000U));
    StateHashSchema schema{};
    BootRuntime runtime(
        *harness->world, harness->clock, harness->journal, std::move(rom),
        schema);
    representative::install(runtime);
    harness->report = runtime.run(5U, 100'000U);
    return harness;
}

std::uint64_t read_field(const JournalRecord& record, const std::size_t index) {
    // note_event payload is three little-endian u64s: tick, a, b.
    std::uint64_t value = 0U;
    const std::size_t base = index * 8U;
    if (record.payload.size() < base + 8U) {
        return 0U;
    }
    for (std::size_t i = 0; i < 8U; ++i) {
        value |= std::to_integer<std::uint64_t>(record.payload[base + i])
            << (8U * i);
    }
    return value;
}

std::vector<std::string> event_labels(const Journal& journal) {
    std::vector<std::string> labels;
    for (const JournalRecord& record : journal.records()) {
        labels.push_back(record.label);
    }
    return labels;
}

std::optional<std::size_t> index_of(
    const std::vector<std::string>& labels, const std::string_view label) {
    for (std::size_t i = 0; i < labels.size(); ++i) {
        if (labels[i] == label) {
            return i;
        }
    }
    return std::nullopt;
}

void test_reset_to_entry_replay() {
    const BootReport first = boot_once();
    const BootReport second = boot_once();
    check(first.reached_gate(), "reset-to-entry boot reaches stable VI");
    check(canonical_checkpoint(first) == canonical_checkpoint(second),
          "reset-to-entry replay is identical");
}

void test_deterministic_boot_event_log() {
    const auto a = boot_with_inspection();
    const auto b = boot_with_inspection();
    check(a->journal.serialize() == b->journal.serialize(),
          "boot event log bytes are identical across runs");
    check(a->journal.digest() == b->journal.digest(),
          "boot event log digest is stable");
    check(!a->journal.records().empty(), "boot produced an event log");
}

void test_expected_thread_creation_order() {
    const auto harness = boot_with_inspection();
    std::vector<const JournalRecord*> creates;
    for (const JournalRecord& record : harness->journal.records()) {
        if (record.label == "thread.create") {
            creates.push_back(&record);
        }
    }
    check(creates.size() == 2U, "exactly two threads created");
    if (creates.size() == 2U) {
        check(read_field(*creates[0], 1) == 1U &&
                  read_field(*creates[0], 2) == 10U,
              "boot-main is created first at priority 10");
        check(read_field(*creates[1], 1) == 2U &&
                  read_field(*creates[1], 2) == 5U,
              "boot-worker is created second at priority 5");
    }
}

void test_expected_overlay_dma_sequence() {
    const auto harness = boot_with_inspection();
    const std::vector<std::string> labels = event_labels(harness->journal);
    const auto start = index_of(labels, "pi_dma.start");
    const auto done = index_of(labels, "pi_dma.done");
    check(start.has_value() && done.has_value(), "DMA start and done logged");
    if (start.has_value() && done.has_value()) {
        check(*start < *done, "DMA starts before it completes");
    }
    // The DMA'd bytes match the cartridge contents at the source offset.
    const std::vector<std::uint8_t> rom =
        representative::synthetic_rom(0x10000U);
    const auto memory = harness->world->rdram();
    const std::size_t ram =
        representative::kDmaRamVaddr - kKseg0Base;
    bool copied = true;
    for (std::uint32_t i = 0; i < representative::kDmaLength; ++i) {
        if (memory[ram + i] != rom[representative::kDmaCartOffset + i]) {
            copied = false;
            break;
        }
    }
    check(copied, "PI DMA copied the exact cartridge bytes into RDRAM");
}

void test_no_unresolved_call() {
    const BootReport report = boot_once();
    check(report.stub_ledger.empty(),
          "representative boot reaches no unsupported operation");
    check(report.status != BootStatus::kTrapped, "boot does not trap");
    check(report.trap_operation.empty(), "no trap operation recorded");
}

void test_no_unbounded_busy_loop() {
    // A thread that never yields must be caught by the step limit, not spin.
    const BootReport report = run_boot(
        representative::synthetic_rom(0x10000U),
        [](BootRuntime& runtime) {
            (void)runtime.create_thread(
                10U, "spin",
                [](BootRuntime&, std::optional<Message>) -> ThreadDirective {
                    return {ThreadWait::kRunnable, kInvalidId};
                });
        },
        BootConfig{.target_retraces = 5U, .step_limit = 1'000U});
    check(report.status == BootStatus::kUnbounded,
          "an unbounded busy loop is detected, not run forever");
}

void test_repeated_boot_hash_consistency() {
    const std::string baseline = canonical_checkpoint(boot_once());
    for (int i = 0; i < 3; ++i) {
        check(canonical_checkpoint(boot_once()) == baseline,
              "repeated boots produce an identical checkpoint");
    }
}

void test_emulator_native_checkpoint_comparison() {
    const BootReport report = boot_once();
    check(canonical_checkpoint(report) == std::string(kOracleCheckpoint),
          "boot checkpoint matches the pinned oracle record");
}

void test_invalid_rom_fails_safe() {
    const BootReport bad_magic = run_boot(
        std::vector<std::uint8_t>(0x2000U, 0xFFU),
        [](BootRuntime& runtime) { representative::install(runtime); },
        BootConfig{});
    check(bad_magic.status == BootStatus::kInvalidRom,
          "wrong-magic ROM is rejected");
    check(bad_magic.vi_retraces == 0U && bad_magic.threads_created == 0U,
          "rejected ROM executes nothing");
    const BootReport too_short = run_boot(
        std::vector<std::uint8_t>{std::uint8_t{0x80}, std::uint8_t{0x37}},
        [](BootRuntime& runtime) { representative::install(runtime); },
        BootConfig{});
    check(too_short.status == BootStatus::kInvalidRom,
          "truncated ROM is rejected");
}

void test_rsp_task_captured_for_phase7() {
    const BootReport report = boot_once();
    check(report.rsp_tasks.size() == 1U, "one RSP task captured");
    if (report.rsp_tasks.size() == 1U) {
        const RspTaskRecord& task = report.rsp_tasks.front();
        check(task.task_type == 1U, "captured task type recorded");
        check(task.data_ptr == representative::kDmaRamVaddr,
              "captured task data pointer recorded");
        check(task.data_size == representative::kDmaLength,
              "captured task data size recorded");
    }
}

} // namespace

int main() {
    test_reset_to_entry_replay();
    test_deterministic_boot_event_log();
    test_expected_thread_creation_order();
    test_expected_overlay_dma_sequence();
    test_no_unresolved_call();
    test_no_unbounded_busy_loop();
    test_repeated_boot_hash_consistency();
    test_emulator_native_checkpoint_comparison();
    test_invalid_rom_fails_safe();
    test_rsp_task_captured_for_phase7();
    if (failures != 0) {
        std::cerr << failures << " failure(s)\n";
        return 1;
    }
    std::cout << "all boot tests passed\n";
    return 0;
}
