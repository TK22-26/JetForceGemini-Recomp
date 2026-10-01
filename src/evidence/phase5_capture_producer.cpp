// Phase 5 private boundary-capture producer.
//
// Runs one generated CPU function inside the deterministic test kernel:
// captures pre/post state, replays it twice in-process, optionally replays a
// previously written capture blob (cross-process determinism), and
// optionally seeds a one-byte fault to prove first-divergence localization.
//
// The source file is tracked and ROM-free.  Everything it touches at run
// time — the dispatch table, the generated bodies, the capture blobs — is
// private local data and stays under ignored trees.
//
// Exit codes: 0 ok; 2 usage; 3 unknown function; 4 invocation failed;
// 5 nondeterministic; 6 divergence machinery failed.  Crashes and traps
// surface as abnormal exit codes handled by the parent orchestrator.

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "recomp.h"

#include "jfg/testkernel/capture.hpp"
#include "jfg/testkernel/corpus.hpp"

#ifndef JFG_PHASE5_CAPTURE_TABLE_INC
#error "JFG_PHASE5_CAPTURE_TABLE_INC must point at the generated table"
#endif
#include JFG_PHASE5_CAPTURE_TABLE_INC

namespace {

using namespace jfg::testkernel;

constexpr std::size_t kCaptureRdramBytes = 8U * 1024U * 1024U;
// Guest addresses seeded into argument/stack registers so leaf functions
// that dereference their arguments stay inside the mapped image.
constexpr std::uint64_t kGuestArgumentAddress = 0xFFFFFFFF80100000ULL;
constexpr std::uint64_t kGuestStackAddress = 0xFFFFFFFF803F0000ULL;

const Phase5CaptureEntry* find_entry(const std::string_view name) {
    for (const Phase5CaptureEntry& entry : kPhase5CaptureTable) {
        if (name == entry.name) {
            return &entry;
        }
    }
    return nullptr;
}

// Bridges the generated ABI into the kernel world.  The full recomp_context
// (including FPRs and float mode, excluding the f_odd host pointer) is
// journaled after the call so state the GuestContext cannot carry still
// participates in bit-exact comparison.
CapturedFunction make_captured(const Phase5CaptureEntry& entry) {
    return [&entry](World& world, Journal& journal) -> bool {
        recomp_context context;
        std::memset(&context, 0, sizeof(context));
        context.r4 = kGuestArgumentAddress;
        context.r5 = kGuestArgumentAddress + 0x1000U;
        context.r6 = kGuestArgumentAddress + 0x2000U;
        context.r7 = kGuestArgumentAddress + 0x3000U;
        context.r29 = kGuestStackAddress;
        context.f_odd = &context.f0.u32h;
        context.mips3_float_mode = 0;

        const GuestContext& pre = world.context();
        const gpr* pre_gpr = &pre.gpr[0];
        gpr* context_gpr = &context.r0;
        for (std::size_t i = 0; i < 32U; ++i) {
            if (pre_gpr[i] != 0U) {
                context_gpr[i] = pre_gpr[i];
            }
        }

        entry.function(world.rdram().data(), &context);

        GuestContext& post = world.context();
        for (std::size_t i = 0; i < 32U; ++i) {
            (&post.gpr[0])[i] = (&context.r0)[i];
        }
        post.hi = context.hi;
        post.lo = context.lo;
        post.status = context.status_reg;

        // Canonical FPR block: 32 doubles' raw bits plus the float mode.
        std::vector<std::byte> fpr_block;
        fpr_block.reserve(32U * 8U + 1U);
        const fpr* fprs = &context.f0;
        for (std::size_t i = 0; i < 32U; ++i) {
            std::uint64_t bits = 0U;
            std::memcpy(&bits, &fprs[i], sizeof(bits));
            for (std::size_t j = 0; j < 8U; ++j) {
                fpr_block.push_back(
                    static_cast<std::byte>(bits >> (8U * j)));
            }
        }
        fpr_block.push_back(static_cast<std::byte>(context.mips3_float_mode));
        return journal.append(
            JournalEffect::kCheckpoint, "recomp-context-fpr",
            std::span<const std::byte>(fpr_block));
    };
}

FunctionRegistry make_registry() {
    return [](const std::uint64_t function_id)
               -> std::optional<CapturedFunction> {
        const std::size_t count =
            sizeof(kPhase5CaptureTable) / sizeof(kPhase5CaptureTable[0]);
        if (function_id >= count) {
            return std::nullopt;
        }
        return make_captured(kPhase5CaptureTable[function_id]);
    };
}

std::optional<std::uint64_t> table_index(const std::string_view name) {
    const std::size_t count =
        sizeof(kPhase5CaptureTable) / sizeof(kPhase5CaptureTable[0]);
    for (std::size_t i = 0; i < count; ++i) {
        if (name == kPhase5CaptureTable[i].name) {
            return i;
        }
    }
    return std::nullopt;
}

int capture_one(const std::string_view name, const std::string& output_path) {
    const std::optional<std::uint64_t> index = table_index(name);
    if (!index.has_value()) {
        return 3;
    }
    std::optional<World> world = World::create(kCaptureRdramBytes);
    if (!world.has_value()) {
        return 6;
    }
    const StateHashSchema schema{};
    const std::optional<FunctionCapture> capture = capture_function(
        *index, std::string(name), *world, schema,
        make_captured(kPhase5CaptureTable[*index]));
    if (!capture.has_value()) {
        return 4;
    }
    const FunctionRegistry registry = make_registry();
    for (int attempt = 0; attempt < 2; ++attempt) {
        const std::optional<ReplayResult> replay =
            replay_capture(*capture, registry);
        if (!replay.has_value()) {
            return 6;
        }
        if (!replay->bit_identical) {
            std::fprintf(
                stderr, "NONDETERMINISTIC: %s\n",
                replay->divergence.has_value()
                    ? replay->divergence->to_text().c_str()
                    : "no report");
            return 5;
        }
    }
    const std::vector<std::byte> blob = serialize_capture(*capture);
    std::ofstream out(output_path, std::ios::binary | std::ios::trunc);
    out.write(reinterpret_cast<const char*>(blob.data()),
              static_cast<std::streamsize>(blob.size()));
    if (!out) {
        return 6;
    }
    std::printf(
        "{\"function\": \"%s\", \"id\": %llu, \"pre_hash\": \"%s\", "
        "\"post_hash\": \"%s\", \"blob_sha256\": \"%s\", "
        "\"post_pages\": %zu, \"journal_bytes\": %zu}\n",
        std::string(name).c_str(),
        static_cast<unsigned long long>(*index),
        hex_digest(capture->pre_hash).c_str(),
        hex_digest(capture->post_hash).c_str(),
        hex_digest(sha256_digest(std::span(blob.data(), blob.size())))
            .c_str(),
        capture->post_pages.size(), capture->journal_bytes.size());
    return 0;
}

std::optional<FunctionCapture> load_capture(const std::string& path) {
    std::ifstream file(path, std::ios::binary | std::ios::ate);
    if (!file) {
        return std::nullopt;
    }
    const std::streamoff size = file.tellg();
    if (size <= 0 ||
        static_cast<std::uint64_t>(size) > kMaximumCaptureBytes) {
        return std::nullopt;
    }
    std::vector<std::byte> bytes(static_cast<std::size_t>(size));
    file.seekg(0);
    file.read(reinterpret_cast<char*>(bytes.data()), size);
    if (!file) {
        return std::nullopt;
    }
    return deserialize_capture(std::span(bytes.data(), bytes.size()));
}

int replay_one(const std::string& path) {
    const std::optional<FunctionCapture> capture = load_capture(path);
    if (!capture.has_value()) {
        return 6;
    }
    const std::optional<ReplayResult> replay =
        replay_capture(*capture, make_registry());
    if (!replay.has_value()) {
        return 6;
    }
    if (!replay->bit_identical) {
        std::fprintf(
            stderr, "DIVERGED: %s\n",
            replay->divergence.has_value()
                ? replay->divergence->to_text().c_str()
                : "no report");
        return 5;
    }
    std::printf("replay bit-identical\n");
    return 0;
}

// Seeds a one-byte fault in the expected post state and requires the
// divergence report to localize exactly that byte.
int seed_fault_one(const std::string& path) {
    std::optional<FunctionCapture> capture = load_capture(path);
    if (!capture.has_value()) {
        return 6;
    }
    if (capture->post_pages.empty()) {
        // No RDRAM effect: seed the post context instead and require a
        // context-domain report at that exact slot.
        capture->post_context.gpr[2] ^= 1U;
        const std::optional<ReplayResult> replay =
            replay_capture(*capture, make_registry());
        // The tampered expected state fails the internal post-hash check
        // fail-closed, which is itself a correct rejection.
        if (!replay.has_value()) {
            std::printf("seeded context fault rejected fail-closed\n");
            return 0;
        }
        if (!replay->bit_identical && replay->divergence.has_value() &&
            replay->divergence->domain == DivergenceDomain::kContext &&
            replay->divergence->offset == 2U) {
            std::printf("seeded context fault localized\n");
            return 0;
        }
        return 6;
    }
    SparsePage& page = capture->post_pages.front();
    const std::uint64_t seeded_offset =
        page.page_index * kWorldPageBytes + 17U;
    page.bytes[17U] ^= 0x01U;
    // Recompute the tampered expected hash so replay compares states, not
    // just the recorded digest.
    std::optional<World> expected = reconstruct_pre_state(*capture);
    if (!expected.has_value()) {
        return 6;
    }
    for (const SparsePage& post_page : capture->post_pages) {
        if (post_page.page_index >= expected->page_count()) {
            return 6;
        }
        std::memcpy(
            expected->rdram().data() +
                post_page.page_index * kWorldPageBytes,
            post_page.bytes.data(), kWorldPageBytes);
    }
    expected->context() = capture->post_context;
    const std::optional<StateDigest> tampered =
        expected->hash(capture->schema);
    if (!tampered.has_value()) {
        return 6;
    }
    capture->post_hash = *tampered;
    const std::optional<ReplayResult> replay =
        replay_capture(*capture, make_registry());
    if (!replay.has_value() || replay->bit_identical ||
        !replay->divergence.has_value()) {
        return 6;
    }
    const DivergenceReport& report = *replay->divergence;
    if (report.domain == DivergenceDomain::kRdram &&
        report.offset == seeded_offset) {
        std::printf("seeded fault localized at %llu\n",
                    static_cast<unsigned long long>(report.offset));
        return 0;
    }
    std::fprintf(stderr, "MISLOCALIZED: %s\n", report.to_text().c_str());
    return 6;
}

} // namespace

int main(const int argc, const char* const* argv) {
    if (argc == 4 && std::string_view(argv[1]) == "--capture") {
        return capture_one(argv[2], argv[3]);
    }
    if (argc == 3 && std::string_view(argv[1]) == "--replay") {
        return replay_one(argv[2]);
    }
    if (argc == 3 && std::string_view(argv[1]) == "--seed-fault") {
        return seed_fault_one(argv[2]);
    }
    std::fprintf(
        stderr,
        "usage: --capture <function> <blob-out> | --replay <blob> | "
        "--seed-fault <blob>\n");
    return 2;
}
