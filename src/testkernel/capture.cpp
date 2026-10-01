#include "jfg/testkernel/capture.hpp"

#include <algorithm>
#include <cstring>

namespace jfg::testkernel {

namespace {

void put_u32(std::vector<std::byte>& out, const std::uint32_t value) {
    for (std::size_t i = 0; i < 4U; ++i) {
        out.push_back(static_cast<std::byte>(value >> (8U * i)));
    }
}

void put_u64(std::vector<std::byte>& out, const std::uint64_t value) {
    for (std::size_t i = 0; i < 8U; ++i) {
        out.push_back(static_cast<std::byte>(value >> (8U * i)));
    }
}

void put_context(std::vector<std::byte>& out, const GuestContext& context) {
    for (const std::uint64_t value : context.gpr) {
        put_u64(out, value);
    }
    put_u64(out, context.hi);
    put_u64(out, context.lo);
    put_u64(out, context.status);
}

void put_digest(std::vector<std::byte>& out, const StateDigest& digest) {
    out.insert(out.end(), digest.begin(), digest.end());
}

void put_pages(
    std::vector<std::byte>& out, const std::vector<SparsePage>& pages) {
    put_u64(out, pages.size());
    for (const SparsePage& page : pages) {
        put_u64(out, page.page_index);
        for (const std::uint8_t byte : page.bytes) {
            out.push_back(static_cast<std::byte>(byte));
        }
    }
}

class Reader final {
public:
    explicit Reader(const std::span<const std::byte> bytes) noexcept
        : bytes_(bytes) {}

    [[nodiscard]] bool read_u32(std::uint32_t& value) noexcept {
        std::span<const std::byte> view;
        if (!read_span(4U, view)) {
            return false;
        }
        value = 0U;
        for (std::size_t i = 0; i < 4U; ++i) {
            value |= std::to_integer<std::uint32_t>(view[i]) << (8U * i);
        }
        return true;
    }

    [[nodiscard]] bool read_u64(std::uint64_t& value) noexcept {
        std::span<const std::byte> view;
        if (!read_span(8U, view)) {
            return false;
        }
        value = 0U;
        for (std::size_t i = 0; i < 8U; ++i) {
            value |= std::to_integer<std::uint64_t>(view[i]) << (8U * i);
        }
        return true;
    }

    [[nodiscard]] bool read_span(
        const std::size_t size, std::span<const std::byte>& view) noexcept {
        if (bytes_.size() - offset_ < size) {
            return false;
        }
        view = bytes_.subspan(offset_, size);
        offset_ += size;
        return true;
    }

    [[nodiscard]] bool read_context(GuestContext& context) noexcept {
        for (std::uint64_t& value : context.gpr) {
            if (!read_u64(value)) {
                return false;
            }
        }
        return read_u64(context.hi) && read_u64(context.lo) &&
            read_u64(context.status);
    }

    [[nodiscard]] bool read_digest(StateDigest& digest) noexcept {
        std::span<const std::byte> view;
        if (!read_span(digest.size(), view)) {
            return false;
        }
        std::copy(view.begin(), view.end(), digest.begin());
        return true;
    }

    [[nodiscard]] bool read_pages(
        std::vector<SparsePage>& pages, const std::uint64_t page_count_limit)
        noexcept {
        std::uint64_t count = 0U;
        if (!read_u64(count) || count > page_count_limit) {
            return false;
        }
        pages.clear();
        std::uint64_t previous_index = 0U;
        for (std::uint64_t i = 0; i < count; ++i) {
            SparsePage page{};
            if (!read_u64(page.page_index) ||
                page.page_index >= page_count_limit ||
                (i > 0U && page.page_index <= previous_index)) {
                return false;
            }
            previous_index = page.page_index;
            std::span<const std::byte> view;
            if (!read_span(kWorldPageBytes, view)) {
                return false;
            }
            for (std::size_t j = 0; j < kWorldPageBytes; ++j) {
                page.bytes[j] = std::to_integer<std::uint8_t>(view[j]);
            }
            pages.push_back(page);
        }
        return true;
    }

    [[nodiscard]] bool exhausted() const noexcept {
        return offset_ == bytes_.size();
    }

private:
    std::span<const std::byte> bytes_;
    std::size_t offset_ = 0U;
};

[[nodiscard]] std::vector<SparsePage> collect_nonzero_pages(
    const World& world) {
    std::vector<SparsePage> pages;
    const std::span<const std::uint8_t> memory = world.rdram();
    for (std::size_t page = 0; page < world.page_count(); ++page) {
        const std::uint8_t* begin = memory.data() + page * kWorldPageBytes;
        const bool nonzero = std::any_of(
            begin, begin + kWorldPageBytes,
            [](const std::uint8_t byte) { return byte != 0U; });
        if (nonzero) {
            SparsePage sparse{};
            sparse.page_index = page;
            std::memcpy(sparse.bytes.data(), begin, kWorldPageBytes);
            pages.push_back(sparse);
        }
    }
    return pages;
}

[[nodiscard]] std::vector<SparsePage> collect_changed_pages(
    const World& post, const World& pre) {
    std::vector<SparsePage> pages;
    const std::span<const std::uint8_t> post_memory = post.rdram();
    const std::span<const std::uint8_t> pre_memory = pre.rdram();
    for (std::size_t page = 0; page < post.page_count(); ++page) {
        const std::size_t offset = page * kWorldPageBytes;
        if (std::memcmp(
                post_memory.data() + offset,
                pre_memory.data() + offset,
                kWorldPageBytes) != 0) {
            SparsePage sparse{};
            sparse.page_index = page;
            std::memcpy(
                sparse.bytes.data(),
                post_memory.data() + offset,
                kWorldPageBytes);
            pages.push_back(sparse);
        }
    }
    return pages;
}

[[nodiscard]] std::optional<std::uint64_t> context_slot(
    const GuestContext& context, const std::size_t slot) noexcept {
    if (slot < context.gpr.size()) {
        return context.gpr[slot];
    }
    switch (slot) {
    case 32U:
        return context.hi;
    case 33U:
        return context.lo;
    case 34U:
        return context.status;
    default:
        return std::nullopt;
    }
}

[[nodiscard]] DivergenceReport make_report(
    const FunctionCapture& capture,
    const DivergenceDomain domain,
    const std::uint64_t offset,
    const std::uint64_t expected_value,
    const std::uint64_t actual_value,
    const StateDigest& actual_hash) {
    DivergenceReport report{};
    report.domain = domain;
    report.function_id = capture.function_id;
    report.offset = offset;
    report.expected_value = expected_value;
    report.actual_value = actual_value;
    report.expected_hash_hex = hex_digest(capture.post_hash);
    report.actual_hash_hex = hex_digest(actual_hash);
    return report;
}

} // namespace

std::string DivergenceReport::to_text() const {
    const char* domain_name = "unknown";
    switch (domain) {
    case DivergenceDomain::kRdram:
        domain_name = "rdram";
        break;
    case DivergenceDomain::kContext:
        domain_name = "context";
        break;
    case DivergenceDomain::kJournal:
        domain_name = "journal";
        break;
    case DivergenceDomain::kInvocation:
        domain_name = "invocation";
        break;
    }
    std::string text = "first-divergence v";
    text += std::to_string(format_version);
    text += " function=";
    text += std::to_string(function_id);
    text += " domain=";
    text += domain_name;
    text += " offset=";
    text += std::to_string(offset);
    text += " expected=";
    text += std::to_string(expected_value);
    text += " actual=";
    text += std::to_string(actual_value);
    text += " expected_hash=";
    text += expected_hash_hex;
    text += " actual_hash=";
    text += actual_hash_hex;
    return text;
}

std::optional<FunctionCapture> capture_function(
    const std::uint64_t function_id,
    std::string function_label,
    const World& pre_state,
    const StateHashSchema& schema,
    const CapturedFunction& function) {
    if (!function || function_label.size() > kMaximumJournalLabelBytes ||
        !schema.valid_for(pre_state.rdram().size())) {
        return std::nullopt;
    }
    const std::optional<StateDigest> pre_hash = pre_state.hash(schema);
    if (!pre_hash.has_value()) {
        return std::nullopt;
    }
    World working = pre_state.clone();
    Journal journal;
    if (!function(working, journal)) {
        return std::nullopt;
    }
    const std::optional<StateDigest> post_hash = working.hash(schema);
    if (!post_hash.has_value()) {
        return std::nullopt;
    }
    FunctionCapture capture{};
    capture.function_id = function_id;
    capture.function_label = std::move(function_label);
    capture.rdram_bytes = pre_state.rdram().size();
    capture.schema = schema;
    capture.pre_pages = collect_nonzero_pages(pre_state);
    capture.pre_context = pre_state.context();
    capture.post_pages = collect_changed_pages(working, pre_state);
    capture.post_context = working.context();
    capture.journal_bytes = journal.serialize();
    capture.pre_hash = *pre_hash;
    capture.post_hash = *post_hash;
    return capture;
}

std::optional<World> reconstruct_pre_state(const FunctionCapture& capture) {
    std::optional<World> world =
        World::create(static_cast<std::size_t>(capture.rdram_bytes));
    if (!world.has_value()) {
        return std::nullopt;
    }
    const std::size_t page_count = world->page_count();
    for (const SparsePage& page : capture.pre_pages) {
        if (page.page_index >= page_count) {
            return std::nullopt;
        }
        std::memcpy(
            world->rdram().data() + page.page_index * kWorldPageBytes,
            page.bytes.data(),
            kWorldPageBytes);
    }
    world->context() = capture.pre_context;
    const std::optional<StateDigest> pre_hash = world->hash(capture.schema);
    if (!pre_hash.has_value() || *pre_hash != capture.pre_hash) {
        return std::nullopt;
    }
    return world;
}

std::optional<ReplayResult> replay_capture(
    const FunctionCapture& capture, const FunctionRegistry& registry) {
    if (!registry) {
        return std::nullopt;
    }
    std::optional<World> pre_state = reconstruct_pre_state(capture);
    if (!pre_state.has_value()) {
        return std::nullopt;
    }
    const std::optional<CapturedFunction> function =
        registry(capture.function_id);
    if (!function.has_value() || !*function) {
        return std::nullopt;
    }

    // Build the expected post world from the capture.
    World expected = pre_state->clone();
    for (const SparsePage& page : capture.post_pages) {
        if (page.page_index >= expected.page_count()) {
            return std::nullopt;
        }
        std::memcpy(
            expected.rdram().data() + page.page_index * kWorldPageBytes,
            page.bytes.data(),
            kWorldPageBytes);
    }
    expected.context() = capture.post_context;
    const std::optional<StateDigest> expected_hash =
        expected.hash(capture.schema);
    if (!expected_hash.has_value() || *expected_hash != capture.post_hash) {
        return std::nullopt;
    }

    World actual = pre_state->clone();
    Journal journal;
    ReplayResult result{};
    if (!(*function)(actual, journal)) {
        result.bit_identical = false;
        result.divergence = make_report(
            capture, DivergenceDomain::kInvocation, 0U, 1U, 0U,
            StateDigest{});
        return result;
    }
    const std::optional<StateDigest> actual_hash = actual.hash(capture.schema);
    if (!actual_hash.has_value()) {
        return std::nullopt;
    }

    // Fixed scan order: RDRAM ascending, context slots, journal bytes.
    const std::span<const std::uint8_t> expected_memory = expected.rdram();
    const std::span<const std::uint8_t> actual_memory = actual.rdram();
    for (std::size_t offset = 0; offset < expected_memory.size(); ++offset) {
        if (expected_memory[offset] != actual_memory[offset]) {
            result.bit_identical = false;
            result.divergence = make_report(
                capture, DivergenceDomain::kRdram, offset,
                expected_memory[offset], actual_memory[offset],
                *actual_hash);
            return result;
        }
    }
    for (std::size_t slot = 0; slot < 35U; ++slot) {
        const std::optional<std::uint64_t> expected_value =
            context_slot(expected.context(), slot);
        const std::optional<std::uint64_t> actual_value =
            context_slot(actual.context(), slot);
        if (expected_value != actual_value) {
            result.bit_identical = false;
            result.divergence = make_report(
                capture, DivergenceDomain::kContext, slot,
                expected_value.value_or(0U), actual_value.value_or(0U),
                *actual_hash);
            return result;
        }
    }
    const std::vector<std::byte> actual_journal = journal.serialize();
    const std::size_t journal_common =
        std::min(actual_journal.size(), capture.journal_bytes.size());
    for (std::size_t offset = 0; offset < journal_common; ++offset) {
        if (capture.journal_bytes[offset] != actual_journal[offset]) {
            result.bit_identical = false;
            result.divergence = make_report(
                capture, DivergenceDomain::kJournal, offset,
                std::to_integer<std::uint8_t>(capture.journal_bytes[offset]),
                std::to_integer<std::uint8_t>(actual_journal[offset]),
                *actual_hash);
            return result;
        }
    }
    if (actual_journal.size() != capture.journal_bytes.size()) {
        result.bit_identical = false;
        result.divergence = make_report(
            capture, DivergenceDomain::kJournal, journal_common,
            capture.journal_bytes.size(), actual_journal.size(),
            *actual_hash);
        return result;
    }

    result.bit_identical = *actual_hash == capture.post_hash;
    if (!result.bit_identical) {
        // Hash mismatch with no byte mismatch means the schema drifted;
        // report it against the hash domain via the journal offset 0 slot.
        result.divergence = make_report(
            capture, DivergenceDomain::kInvocation, 0U, 0U, 0U, *actual_hash);
    }
    return result;
}

std::vector<std::byte> serialize_capture(const FunctionCapture& capture) {
    std::vector<std::byte> out;
    out.insert(out.end(), kCaptureMagic.begin(), kCaptureMagic.end());
    put_u32(out, kCaptureFormatVersion);
    put_u64(out, capture.function_id);
    put_u32(out, static_cast<std::uint32_t>(capture.function_label.size()));
    for (const char character : capture.function_label) {
        out.push_back(static_cast<std::byte>(character));
    }
    put_u64(out, capture.rdram_bytes);
    put_u32(out, capture.schema.version);
    put_u32(out, capture.schema.page_bytes);
    put_u32(out, capture.schema.include_context ? 1U : 0U);
    put_u32(out, static_cast<std::uint32_t>(capture.schema.exclusions.size()));
    for (const StateHashExclusion& exclusion : capture.schema.exclusions) {
        put_u64(out, exclusion.begin);
        put_u64(out, exclusion.end);
    }
    put_pages(out, capture.pre_pages);
    put_context(out, capture.pre_context);
    put_pages(out, capture.post_pages);
    put_context(out, capture.post_context);
    put_u64(out, capture.journal_bytes.size());
    out.insert(
        out.end(), capture.journal_bytes.begin(), capture.journal_bytes.end());
    put_digest(out, capture.pre_hash);
    put_digest(out, capture.post_hash);
    return out;
}

std::optional<FunctionCapture> deserialize_capture(
    const std::span<const std::byte> bytes) {
    if (bytes.size() > kMaximumCaptureBytes) {
        return std::nullopt;
    }
    Reader reader(bytes);
    std::span<const std::byte> magic;
    if (!reader.read_span(kCaptureMagic.size(), magic) ||
        !std::equal(magic.begin(), magic.end(), kCaptureMagic.begin())) {
        return std::nullopt;
    }
    std::uint32_t version = 0U;
    if (!reader.read_u32(version) || version != kCaptureFormatVersion) {
        return std::nullopt;
    }
    FunctionCapture capture{};
    if (!reader.read_u64(capture.function_id)) {
        return std::nullopt;
    }
    std::uint32_t label_size = 0U;
    std::span<const std::byte> label_bytes;
    if (!reader.read_u32(label_size) ||
        label_size > kMaximumJournalLabelBytes ||
        !reader.read_span(label_size, label_bytes)) {
        return std::nullopt;
    }
    for (const std::byte byte : label_bytes) {
        capture.function_label.push_back(
            static_cast<char>(std::to_integer<std::uint8_t>(byte)));
    }
    if (!reader.read_u64(capture.rdram_bytes) ||
        capture.rdram_bytes < kMinimumWorldRdramBytes ||
        capture.rdram_bytes > kMaximumWorldRdramBytes ||
        capture.rdram_bytes % kWorldPageBytes != 0U) {
        return std::nullopt;
    }
    std::uint32_t include_context = 0U;
    std::uint32_t exclusion_count = 0U;
    if (!reader.read_u32(capture.schema.version) ||
        !reader.read_u32(capture.schema.page_bytes) ||
        !reader.read_u32(include_context) || include_context > 1U ||
        !reader.read_u32(exclusion_count) ||
        exclusion_count > kMaximumWorldRdramBytes / kWorldPageBytes) {
        return std::nullopt;
    }
    capture.schema.include_context = include_context == 1U;
    for (std::uint32_t i = 0; i < exclusion_count; ++i) {
        StateHashExclusion exclusion{};
        if (!reader.read_u64(exclusion.begin) ||
            !reader.read_u64(exclusion.end)) {
            return std::nullopt;
        }
        capture.schema.exclusions.push_back(exclusion);
    }
    if (!capture.schema.valid_for(
            static_cast<std::size_t>(capture.rdram_bytes))) {
        return std::nullopt;
    }
    const std::uint64_t page_count = capture.rdram_bytes / kWorldPageBytes;
    if (!reader.read_pages(capture.pre_pages, page_count) ||
        !reader.read_context(capture.pre_context) ||
        !reader.read_pages(capture.post_pages, page_count) ||
        !reader.read_context(capture.post_context)) {
        return std::nullopt;
    }
    std::uint64_t journal_size = 0U;
    std::span<const std::byte> journal_view;
    if (!reader.read_u64(journal_size) ||
        journal_size > kMaximumJournalPayloadBytes ||
        !reader.read_span(
            static_cast<std::size_t>(journal_size), journal_view)) {
        return std::nullopt;
    }
    capture.journal_bytes.assign(journal_view.begin(), journal_view.end());
    if (!Journal::deserialize(
            std::span(capture.journal_bytes.data(),
                      capture.journal_bytes.size()))
             .has_value()) {
        return std::nullopt;
    }
    if (!reader.read_digest(capture.pre_hash) ||
        !reader.read_digest(capture.post_hash) || !reader.exhausted()) {
        return std::nullopt;
    }
    return capture;
}

std::optional<std::size_t> detect_nondeterminism(
    const CheckpointedScenario& scenario) {
    if (!scenario) {
        return 0U;
    }
    const std::vector<StateDigest> first = scenario();
    const std::vector<StateDigest> second = scenario();
    const std::size_t common = std::min(first.size(), second.size());
    for (std::size_t i = 0; i < common; ++i) {
        if (first[i] != second[i]) {
            return i;
        }
    }
    if (first.size() != second.size()) {
        return common;
    }
    return std::nullopt;
}

} // namespace jfg::testkernel
