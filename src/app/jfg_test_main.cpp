// jfg-test — the Phase 5 headless deterministic test kernel runner.
//
// ROM-free by construction: the built-in registry contains synthetic
// functions only.  ROM-derived corpora are private local inputs replayed
// through the same code paths; nothing here fetches, embeds, or emits
// ROM-derived bytes.
//
// Subcommands:
//   self-check              run the kernel v0 determinism battery
//   print-schema            print state hash schema v1 defaults as JSON
//   replay <corpus-file>    replay every capture in a corpus file
//   repeat <n>              run the self-check scenario n times and report
//                           the exact-repeat verdict

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "jfg/testkernel/capture.hpp"
#include "jfg/testkernel/corpus.hpp"
#include "jfg/testkernel/fakes.hpp"
#include "jfg/testkernel/scheduler.hpp"

namespace {

using namespace jfg::testkernel;

constexpr std::uint64_t kSyntheticFillFunctionId = 1U;
constexpr std::uint64_t kSyntheticJournalFunctionId = 2U;

// Deterministically fills one page and bumps two registers.
bool synthetic_fill(World& world, Journal& journal) {
    auto memory = world.rdram();
    for (std::size_t i = 0; i < kWorldPageBytes; ++i) {
        memory[kWorldPageBytes + i] =
            static_cast<std::uint8_t>((i * 7U + 3U) & 0xFFU);
    }
    world.context().gpr[2] += 0x1234U;
    world.context().gpr[31] = 0x80001234U;
    return journal.append(
        JournalEffect::kCheckpoint, "synthetic-fill", {});
}

// Exercises the fakes: one renderer submit, one storage round-trip.
bool synthetic_journal(World& world, Journal& journal) {
    FakeHostDevices devices(journal);
    const std::vector<std::byte> commands{
        std::byte{0xDE}, std::byte{0xAD}, std::byte{0xBE}, std::byte{0xEF}};
    std::vector<std::byte> block(kFakeStorageBlockBytes, std::byte{0x5A});
    if (!devices.renderer_submit(
            "synthetic-frame", std::span<const std::byte>(commands)) ||
        !devices.storage_write(7U, std::span<const std::byte>(block))) {
        return false;
    }
    std::vector<std::byte> readback(kFakeStorageBlockBytes);
    if (!devices.storage_read(7U, std::span<std::byte>(readback))) {
        return false;
    }
    world.context().gpr[4] = readback.size();
    return true;
}

std::optional<CapturedFunction> synthetic_registry(
    const std::uint64_t function_id) {
    switch (function_id) {
    case kSyntheticFillFunctionId:
        return CapturedFunction(synthetic_fill);
    case kSyntheticJournalFunctionId:
        return CapturedFunction(synthetic_journal);
    default:
        return std::nullopt;
    }
}

[[nodiscard]] StateHashSchema default_schema() {
    return StateHashSchema{};
}

[[nodiscard]] std::optional<std::vector<StateDigest>> checkpoint_scenario() {
    std::optional<World> world = World::create(16U * kWorldPageBytes);
    if (!world.has_value()) {
        return std::nullopt;
    }
    const StateHashSchema schema = default_schema();
    std::vector<StateDigest> checkpoints;
    DeterministicScheduler scheduler;
    bool scheduled = scheduler.schedule_every(
        10U, 5U, "tick",
        [&](DeterministicScheduler& inner) {
            const std::uint64_t now = inner.clock().now();
            world->rdram()[static_cast<std::size_t>(now) % kWorldPageBytes] =
                static_cast<std::uint8_t>(now & 0xFFU);
            const std::optional<StateDigest> digest = world->hash(schema);
            if (digest.has_value()) {
                checkpoints.push_back(*digest);
            }
        });
    scheduled = scheduler.schedule_after(
                    25U, "midpoint",
                    [&](DeterministicScheduler&) {
                        world->context().gpr[8] ^= 0xA5A5A5A5U;
                    }) &&
        scheduled;
    if (!scheduled || !scheduler.run(64U).has_value()) {
        return std::nullopt;
    }
    return checkpoints;
}

[[nodiscard]] int fail(const char* message) {
    std::fprintf(stderr, "jfg-test: FAIL: %s\n", message);
    return 1;
}

int run_self_check() {
    // Known-answer hash vector.
    {
        const std::string_view input = "abc";
        Sha256 hasher;
        hasher.update_bytes(input.data(), input.size());
        if (hex_digest(hasher.finish()) !=
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad") {
            return fail("sha256 known-answer vector");
        }
    }
    // World clone and replay determinism.
    std::optional<World> world = World::create(16U * kWorldPageBytes);
    if (!world.has_value()) {
        return fail("world creation");
    }
    world->rdram()[42U] = 0x17U;
    world->context().gpr[5] = 0x55U;
    const StateHashSchema schema = default_schema();
    const World clone = world->clone();
    if (world->hash(schema) != clone.hash(schema)) {
        return fail("clone hash identity");
    }
    const std::optional<FunctionCapture> capture = capture_function(
        kSyntheticFillFunctionId, "synthetic-fill", *world, schema,
        CapturedFunction(synthetic_fill));
    if (!capture.has_value()) {
        return fail("capture");
    }
    for (int i = 0; i < 2; ++i) {
        const std::optional<ReplayResult> replay =
            replay_capture(*capture, synthetic_registry);
        if (!replay.has_value() || !replay->bit_identical) {
            return fail("bit-identical replay");
        }
    }
    // Corpus round-trip.
    Corpus corpus;
    if (!corpus.add("self-check", serialize_capture(*capture))) {
        return fail("corpus add");
    }
    const std::vector<std::byte> corpus_bytes = corpus.serialize();
    const std::optional<Corpus> round_trip = Corpus::deserialize(
        std::span(corpus_bytes.data(), corpus_bytes.size()));
    if (!round_trip.has_value() || !(*round_trip == corpus)) {
        return fail("corpus round-trip");
    }
    // Exact-repeat detector over the scheduler scenario.
    const std::optional<std::size_t> divergence = detect_nondeterminism(
        []() {
            const std::optional<std::vector<StateDigest>> checkpoints =
                checkpoint_scenario();
            return checkpoints.value_or(std::vector<StateDigest>{});
        });
    if (divergence.has_value()) {
        return fail("exact-repeat scenario diverged");
    }
    std::printf("jfg-test: self-check OK\n");
    return 0;
}

int run_print_schema() {
    const StateHashSchema schema = default_schema();
    std::printf(
        "{\"version\": %u, \"page_bytes\": %u, \"include_context\": %s, "
        "\"exclusions\": []}\n",
        schema.version, schema.page_bytes,
        schema.include_context ? "true" : "false");
    return 0;
}

int run_replay(const char* path) {
    std::ifstream file(path, std::ios::binary | std::ios::ate);
    if (!file) {
        return fail("cannot open corpus file");
    }
    const std::streamoff size = file.tellg();
    if (size < 0 || static_cast<std::uint64_t>(size) > kMaximumCorpusBytes) {
        return fail("corpus size out of bounds");
    }
    std::vector<std::byte> bytes(static_cast<std::size_t>(size));
    file.seekg(0);
    file.read(reinterpret_cast<char*>(bytes.data()), size);
    if (!file) {
        return fail("corpus read");
    }
    const std::optional<Corpus> corpus =
        Corpus::deserialize(std::span(bytes.data(), bytes.size()));
    if (!corpus.has_value()) {
        return fail("corpus parse");
    }
    for (const CorpusEntry& entry : corpus->entries()) {
        const std::optional<FunctionCapture> capture = deserialize_capture(
            std::span(entry.blob.data(), entry.blob.size()));
        if (!capture.has_value()) {
            std::fprintf(
                stderr, "jfg-test: FAIL: entry %s: capture parse\n",
                entry.name.c_str());
            return 1;
        }
        const std::optional<ReplayResult> replay =
            replay_capture(*capture, synthetic_registry);
        if (!replay.has_value()) {
            std::fprintf(
                stderr, "jfg-test: FAIL: entry %s: replay setup\n",
                entry.name.c_str());
            return 1;
        }
        if (!replay->bit_identical) {
            const std::string report = replay->divergence.has_value()
                ? replay->divergence->to_text()
                : std::string("no report");
            std::fprintf(
                stderr, "jfg-test: DIVERGED: entry %s: %s\n",
                entry.name.c_str(), report.c_str());
            return 1;
        }
        std::printf("jfg-test: entry %s replayed bit-identical\n",
                    entry.name.c_str());
    }
    return 0;
}

int run_repeat(const char* count_text) {
    const long count = std::strtol(count_text, nullptr, 10);
    if (count < 2 || count > 1000) {
        return fail("repeat count must be in 2..1000");
    }
    std::optional<std::vector<StateDigest>> baseline = checkpoint_scenario();
    if (!baseline.has_value() || baseline->empty()) {
        return fail("scenario produced no checkpoints");
    }
    for (long run = 1; run < count; ++run) {
        const std::optional<std::vector<StateDigest>> repeat =
            checkpoint_scenario();
        if (!repeat.has_value() || !(*repeat == *baseline)) {
            std::fprintf(
                stderr, "jfg-test: NONDETERMINISM at run %ld\n", run);
            return 1;
        }
    }
    std::printf(
        "jfg-test: %ld runs exactly repeatable (%zu checkpoints)\n",
        count, baseline->size());
    return 0;
}

} // namespace

int main(const int argc, const char* const* argv) {
    if (argc >= 2) {
        const std::string_view command = argv[1];
        if (command == "self-check" && argc == 2) {
            return run_self_check();
        }
        if (command == "print-schema" && argc == 2) {
            return run_print_schema();
        }
        if (command == "replay" && argc == 3) {
            return run_replay(argv[2]);
        }
        if (command == "repeat" && argc == 3) {
            return run_repeat(argv[2]);
        }
    }
    std::fprintf(
        stderr,
        "usage: jfg-test self-check | print-schema | replay <corpus> | "
        "repeat <n>\n");
    return 2;
}
