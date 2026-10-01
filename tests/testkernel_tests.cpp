// Phase 5 deterministic-test-kernel tests.  Together with
// tests/test_phase5_policy.py these discharge the nine master-plan Phase 5
// test obligations mapped in docs/planning/phase5-acceptance.md.

#include "jfg/testkernel/capture.hpp"
#include "jfg/testkernel/corpus.hpp"
#include "jfg/testkernel/fakes.hpp"
#include "jfg/testkernel/scheduler.hpp"

#include <iostream>
#include <string_view>

namespace {

using namespace jfg::testkernel;

int failures = 0;

void check(const bool condition, const std::string_view message) {
    if (!condition) {
        ++failures;
        std::cerr << "FAIL: " << message << '\n';
    }
}

constexpr std::uint64_t kFillId = 1U;

bool fill_function(World& world, Journal& journal) {
    auto memory = world.rdram();
    for (std::size_t i = 0; i < 64U; ++i) {
        memory[2U * kWorldPageBytes + i] = static_cast<std::uint8_t>(i + 1U);
    }
    world.context().gpr[2] = 0xDEADBEEFU;
    return journal.append(JournalEffect::kCheckpoint, "fill", {});
}

std::optional<CapturedFunction> registry(const std::uint64_t id) {
    if (id == kFillId) {
        return CapturedFunction(fill_function);
    }
    return std::nullopt;
}

void test_sha256_known_answer() {
    Sha256 hasher;
    hasher.update_bytes("abc", 3U);
    check(
        hex_digest(hasher.finish()) ==
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        "sha256 matches the FIPS 180-2 'abc' vector");
}

void test_world_bounds_fail_closed() {
    check(!World::create(0U).has_value(), "zero-size world rejected");
    check(!World::create(kWorldPageBytes + 1U).has_value(),
          "non-page-multiple world rejected");
    check(!World::create(kMaximumWorldRdramBytes + kWorldPageBytes)
               .has_value(),
          "oversized world rejected");
}

void test_world_clone_identical_hashes() {
    auto world = World::create(8U * kWorldPageBytes);
    check(world.has_value(), "world creates");
    world->rdram()[123U] = 0x42U;
    world->context().gpr[7] = 7U;
    const StateHashSchema schema{};
    const World clone = world->clone();
    check(world->hash(schema).has_value(), "hash computes");
    check(world->hash(schema) == clone.hash(schema),
          "clone produces identical hashes");
    check(*world == clone, "clone is byte-identical");
}

void test_dirty_page_tracker_exact_writes() {
    auto world = World::create(8U * kWorldPageBytes);
    check(world.has_value(), "world creates");
    const World baseline = world->clone();
    world->rdram()[10U] = 1U;
    world->rdram()[11U] = 2U;
    world->rdram()[3U * kWorldPageBytes + 100U] = 3U;
    const auto deltas = world->diff(baseline);
    check(deltas.has_value(), "diff computes");
    check(deltas->size() == 2U, "exactly two dirty runs");
    if (deltas->size() == 2U) {
        check((*deltas)[0].page_index == 0U && (*deltas)[0].first_byte == 10U &&
                  (*deltas)[0].last_byte == 11U,
              "first run is bytes 10..11 of page 0");
        check((*deltas)[1].page_index == 3U &&
                  (*deltas)[1].first_byte == 3U * kWorldPageBytes + 100U &&
                  (*deltas)[1].last_byte == (*deltas)[1].first_byte,
              "second run is the single byte in page 3");
    }
    check(world->diff(*world)->empty(), "self-diff is empty");
}

void test_state_hash_schema_validation() {
    auto world = World::create(4U * kWorldPageBytes);
    check(world.has_value(), "world creates");
    StateHashSchema overlapping{};
    overlapping.exclusions = {
        {.begin = 0U, .end = 64U}, {.begin = 32U, .end = 128U}};
    check(!world->hash(overlapping).has_value(),
          "overlapping exclusions fail closed");
    StateHashSchema excluding{};
    excluding.exclusions = {{.begin = 0U, .end = kWorldPageBytes}};
    const auto full = world->hash(StateHashSchema{});
    const auto partial = world->hash(excluding);
    check(full.has_value() && partial.has_value() && *full != *partial,
          "exclusions change the schema-bound hash");
}

void test_scheduler_replay_repeats_event_order() {
    const auto run_once = []() {
        DeterministicScheduler scheduler;
        bool ok = scheduler.schedule_at(30U, "late", [](auto&) {});
        ok = scheduler.schedule_at(10U, "early", [](auto&) {}) && ok;
        ok = scheduler.schedule_at(10U, "early-tie", [](auto&) {}) && ok;
        ok = scheduler.schedule_every(
                 7U, 3U, "timer",
                 [](DeterministicScheduler& inner) {
                     (void)inner.schedule_after(1U, "nested", [](auto&) {});
                 }) &&
            ok;
        if (!ok || !scheduler.run(64U).has_value()) {
            return std::vector<DispatchedEvent>{};
        }
        return scheduler.dispatch_log();
    };
    const auto first = run_once();
    const auto second = run_once();
    check(!first.empty(), "scheduler run dispatches events");
    check(first == second, "replay repeats the exact event order");
    for (std::size_t i = 1U; i < first.size(); ++i) {
        check(first[i - 1U].due < first[i].due ||
                  (first[i - 1U].due == first[i].due &&
                   first[i - 1U].sequence < first[i].sequence),
              "dispatch order is (due, sequence) sorted");
    }
    DeterministicScheduler limited;
    check(limited.schedule_every(1U, 100U, "spin", [](auto&) {}),
          "periodic timer schedules");
    check(!limited.run(10U).has_value(),
          "step limit reports unbounded work instead of spinning");
}

void test_journal_stable_and_round_trips() {
    const auto build = []() {
        Journal journal;
        const std::vector<std::byte> payload{std::byte{1}, std::byte{2}};
        bool ok = journal.append(
            JournalEffect::kRendererSubmit, "frame",
            std::span<const std::byte>(payload));
        ok = journal.append(JournalEffect::kCheckpoint, "done", {}) && ok;
        return ok ? journal : Journal{};
    };
    const Journal first = build();
    const Journal second = build();
    check(first.records().size() == 2U, "journal appends");
    check(first.serialize() == second.serialize(),
          "identical operations serialize to identical bytes");
    check(first.digest() == second.digest(), "journal digest is stable");
    const auto bytes = first.serialize();
    const auto round_trip =
        Journal::deserialize(std::span(bytes.data(), bytes.size()));
    check(round_trip.has_value() && *round_trip == first,
          "journal round-trips losslessly");
    auto truncated = bytes;
    truncated.pop_back();
    check(!Journal::deserialize(std::span(truncated.data(), truncated.size()))
               .has_value(),
          "truncated journal fails closed");
}

void test_replay_twice_bit_identical() {
    auto world = World::create(8U * kWorldPageBytes);
    check(world.has_value(), "world creates");
    world->rdram()[5U] = 0x77U;
    const auto capture = capture_function(
        kFillId, "fill", *world, StateHashSchema{},
        CapturedFunction(fill_function));
    check(capture.has_value(), "capture succeeds");
    const auto serialized = serialize_capture(*capture);
    const auto parsed =
        deserialize_capture(std::span(serialized.data(), serialized.size()));
    check(parsed.has_value() && *parsed == *capture,
          "capture format v1 round-trips losslessly");
    for (int attempt = 0; attempt < 2; ++attempt) {
        const auto replay = replay_capture(*parsed, registry);
        check(replay.has_value() && replay->bit_identical,
              "replayed function is bit-identical");
    }
    check(!replay_capture(*parsed, [](std::uint64_t) {
               return std::optional<CapturedFunction>{};
           }).has_value(),
          "unknown function id fails closed");
}

void test_first_divergence_localizes_seeded_fault() {
    auto world = World::create(8U * kWorldPageBytes);
    check(world.has_value(), "world creates");
    auto capture = capture_function(
        kFillId, "fill", *world, StateHashSchema{},
        CapturedFunction(fill_function));
    check(capture.has_value(), "capture succeeds");
    // Seed a one-byte fault in the expected post state at a known offset.
    const std::uint64_t seeded_offset = 2U * kWorldPageBytes + 17U;
    check(!capture->post_pages.empty(), "capture has post pages");
    bool seeded = false;
    for (SparsePage& page : capture->post_pages) {
        if (page.page_index == 2U) {
            page.bytes[17U] ^= 0x01U;
            seeded = true;
        }
    }
    check(seeded, "seeded page found");
    // The tampered expected state no longer matches the recorded post hash,
    // so recompute it the way a corrupted-oracle scenario would present it.
    auto expected_world = reconstruct_pre_state(*capture);
    check(expected_world.has_value(), "pre state reconstructs");
    for (const SparsePage& page : capture->post_pages) {
        std::copy(
            page.bytes.begin(), page.bytes.end(),
            expected_world->rdram().begin() +
                static_cast<std::ptrdiff_t>(
                    page.page_index * kWorldPageBytes));
    }
    expected_world->context() = capture->post_context;
    const auto tampered_hash = expected_world->hash(capture->schema);
    check(tampered_hash.has_value(), "tampered hash computes");
    capture->post_hash = *tampered_hash;
    const auto replay = replay_capture(*capture, registry);
    check(replay.has_value(), "replay runs");
    check(replay.has_value() && !replay->bit_identical,
          "seeded fault detected");
    if (replay.has_value() && replay->divergence.has_value()) {
        const DivergenceReport& report = *replay->divergence;
        check(report.domain == DivergenceDomain::kRdram,
              "divergence domain is rdram");
        check(report.offset == seeded_offset,
              "first divergence is exactly the seeded byte");
        check(report.format_version == 1U, "report format v1");
        check(!report.to_text().empty(), "report renders");
    } else {
        check(false, "divergence report present");
    }
}

void test_unsupported_host_call_rejected() {
    Journal journal;
    FakeHostDevices devices(journal);
    const std::vector<std::byte> payload{std::byte{9}};
    check(!devices.dispatch_host_call(
              999U, "bogus-call", std::span<const std::byte>(payload)),
          "unsupported host call rejected");
    check(devices.rejected_call_count() == 1U, "rejection counted");
    check(journal.records().size() == 1U &&
              journal.records()[0].effect == JournalEffect::kHostCallRejected,
          "rejection is journaled");
    check(devices.dispatch_host_call(
              static_cast<std::uint32_t>(HostCall::kRendererSubmit),
              "frame", std::span<const std::byte>(payload)),
          "supported host call accepted");
    std::vector<std::byte> block(kFakeStorageBlockBytes, std::byte{0x33});
    check(devices.storage_write(1U, std::span<const std::byte>(block)),
          "fake storage writes");
    std::vector<std::byte> readback(kFakeStorageBlockBytes);
    check(devices.storage_read(1U, std::span<std::byte>(readback)) &&
              readback == block,
          "fake storage reads back");
}

void test_corpus_round_trip_lossless() {
    auto world = World::create(8U * kWorldPageBytes);
    check(world.has_value(), "world creates");
    world->rdram()[9U] = 0xABU;
    const auto capture = capture_function(
        kFillId, "fill", *world, StateHashSchema{},
        CapturedFunction(fill_function));
    check(capture.has_value(), "capture succeeds");
    Corpus corpus;
    check(corpus.add("case-a", serialize_capture(*capture)), "adds entry");
    check(!corpus.add("case-a", {}), "duplicate name rejected");
    const std::vector<std::byte> raw{
        std::byte{0}, std::byte{0}, std::byte{0}, std::byte{7},
        std::byte{7}, std::byte{7}, std::byte{7}, std::byte{1}};
    Corpus mixed = corpus;
    check(mixed.add("case-b", raw), "adds raw entry");
    const auto bytes = mixed.serialize();
    const auto round_trip =
        Corpus::deserialize(std::span(bytes.data(), bytes.size()));
    check(round_trip.has_value() && *round_trip == mixed,
          "corpus round-trip is lossless");
    auto corrupted = bytes;
    corrupted[corrupted.size() / 2U] ^= std::byte{0xFF};
    const auto reject =
        Corpus::deserialize(std::span(corrupted.data(), corrupted.size()));
    check(!reject.has_value() || !(*reject == mixed),
          "corruption cannot round-trip silently");
    const auto compressed = rle_compress(std::span(raw.data(), raw.size()));
    const auto decompressed = rle_decompress(
        std::span(compressed.data(), compressed.size()), raw.size());
    check(decompressed.has_value() && *decompressed == raw,
          "rle round-trip is lossless");
}

void test_minimization_preserves_failure() {
    auto world = World::create(8U * kWorldPageBytes);
    check(world.has_value(), "world creates");
    // Two populated pre pages; only page 5 matters to the "failure".
    world->rdram()[1U * kWorldPageBytes] = 0x11U;
    world->rdram()[5U * kWorldPageBytes] = 0x55U;
    const auto capture = capture_function(
        kFillId, "fill", *world, StateHashSchema{},
        CapturedFunction(fill_function));
    check(capture.has_value(), "capture succeeds");
    check(capture->pre_pages.size() == 2U, "two pre pages recorded");
    const auto reproduces = [](const FunctionCapture& candidate) {
        for (const SparsePage& page : candidate.pre_pages) {
            if (page.page_index == 5U) {
                return true;
            }
        }
        return false;
    };
    const FunctionCapture minimized = minimize_capture(*capture, reproduces);
    check(minimized.pre_pages.size() == 1U &&
              minimized.pre_pages[0].page_index == 5U,
          "minimization drops the irrelevant page and keeps the failure");
    const auto rebuilt = reconstruct_pre_state(minimized);
    check(rebuilt.has_value(), "minimized capture stays consistent");
}

void test_exact_repeat_detector() {
    check(!detect_nondeterminism([]() {
               std::vector<StateDigest> digests;
               Sha256 hasher;
               hasher.update_bytes("same", 4U);
               digests.push_back(hasher.finish());
               return digests;
           }).has_value(),
          "repeatable scenario passes");
    int counter = 0;
    const auto diverging = detect_nondeterminism([&]() {
        std::vector<StateDigest> digests;
        Sha256 hasher;
        const std::string text = "run" + std::to_string(counter++);
        hasher.update_bytes(text.data(), text.size());
        digests.push_back(hasher.finish());
        return digests;
    });
    check(diverging.has_value() && *diverging == 0U,
          "nondeterministic scenario detected at the first checkpoint");
}

} // namespace

int main() {
    test_sha256_known_answer();
    test_world_bounds_fail_closed();
    test_world_clone_identical_hashes();
    test_dirty_page_tracker_exact_writes();
    test_state_hash_schema_validation();
    test_scheduler_replay_repeats_event_order();
    test_journal_stable_and_round_trips();
    test_replay_twice_bit_identical();
    test_first_divergence_localizes_seeded_fault();
    test_unsupported_host_call_rejected();
    test_corpus_round_trip_lossless();
    test_minimization_preserves_failure();
    test_exact_repeat_detector();
    if (failures != 0) {
        std::cerr << failures << " failure(s)\n";
        return 1;
    }
    std::cout << "all testkernel tests passed\n";
    return 0;
}
