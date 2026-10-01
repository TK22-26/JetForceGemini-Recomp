#include "jfg/testkernel/corpus.hpp"

#include <algorithm>

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

[[nodiscard]] bool read_u32(
    const std::span<const std::byte> bytes, std::size_t& offset,
    std::uint32_t& value) noexcept {
    if (bytes.size() - offset < 4U) {
        return false;
    }
    value = 0U;
    for (std::size_t i = 0; i < 4U; ++i) {
        value |= std::to_integer<std::uint32_t>(bytes[offset + i]) << (8U * i);
    }
    offset += 4U;
    return true;
}

[[nodiscard]] bool read_u64(
    const std::span<const std::byte> bytes, std::size_t& offset,
    std::uint64_t& value) noexcept {
    if (bytes.size() - offset < 8U) {
        return false;
    }
    value = 0U;
    for (std::size_t i = 0; i < 8U; ++i) {
        value |= std::to_integer<std::uint64_t>(bytes[offset + i]) << (8U * i);
    }
    offset += 8U;
    return true;
}

} // namespace

std::vector<std::byte> rle_compress(const std::span<const std::byte> input) {
    // Format: repeated (count: u8 in 1..=255, value: u8) pairs, prefixed by
    // the u64 uncompressed size.
    std::vector<std::byte> out;
    put_u64(out, input.size());
    std::size_t offset = 0U;
    while (offset < input.size()) {
        const std::byte value = input[offset];
        std::size_t run = 1U;
        while (offset + run < input.size() && run < 255U &&
               input[offset + run] == value) {
            ++run;
        }
        out.push_back(static_cast<std::byte>(run));
        out.push_back(value);
        offset += run;
    }
    return out;
}

std::optional<std::vector<std::byte>> rle_decompress(
    const std::span<const std::byte> input,
    const std::size_t maximum_output_bytes) {
    std::size_t offset = 0U;
    std::uint64_t expected_size = 0U;
    if (!read_u64(input, offset, expected_size) ||
        expected_size > maximum_output_bytes) {
        return std::nullopt;
    }
    std::vector<std::byte> out;
    out.reserve(static_cast<std::size_t>(expected_size));
    while (offset < input.size()) {
        if (input.size() - offset < 2U) {
            return std::nullopt;
        }
        const auto run = std::to_integer<std::uint8_t>(input[offset]);
        const std::byte value = input[offset + 1U];
        offset += 2U;
        if (run == 0U || out.size() + run > expected_size) {
            return std::nullopt;
        }
        out.insert(out.end(), run, value);
    }
    if (out.size() != expected_size) {
        return std::nullopt;
    }
    return out;
}

bool Corpus::add(std::string name, std::vector<std::byte> blob) {
    if (entries_.size() >= kMaximumCorpusEntries || name.empty() ||
        name.size() > kMaximumCorpusEntryNameBytes ||
        blob.size() > kMaximumCaptureBytes) {
        return false;
    }
    const bool duplicate = std::any_of(
        entries_.begin(), entries_.end(),
        [&](const CorpusEntry& entry) { return entry.name == name; });
    if (duplicate) {
        return false;
    }
    entries_.push_back(CorpusEntry{std::move(name), std::move(blob)});
    return true;
}

std::vector<std::byte> Corpus::serialize() const {
    std::vector<std::byte> out;
    out.insert(out.end(), kCorpusMagic.begin(), kCorpusMagic.end());
    put_u32(out, kCorpusFormatVersion);
    put_u32(out, static_cast<std::uint32_t>(entries_.size()));
    for (const CorpusEntry& entry : entries_) {
        put_u32(out, static_cast<std::uint32_t>(entry.name.size()));
        for (const char character : entry.name) {
            out.push_back(static_cast<std::byte>(character));
        }
        const std::vector<std::byte> compressed = rle_compress(
            std::span(entry.blob.data(), entry.blob.size()));
        put_u64(out, compressed.size());
        out.insert(out.end(), compressed.begin(), compressed.end());
    }
    return out;
}

std::optional<Corpus> Corpus::deserialize(
    const std::span<const std::byte> bytes) {
    if (bytes.size() > kMaximumCorpusBytes) {
        return std::nullopt;
    }
    std::size_t offset = 0U;
    if (bytes.size() < kCorpusMagic.size() ||
        !std::equal(kCorpusMagic.begin(), kCorpusMagic.end(), bytes.begin())) {
        return std::nullopt;
    }
    offset = kCorpusMagic.size();
    std::uint32_t version = 0U;
    std::uint32_t count = 0U;
    if (!read_u32(bytes, offset, version) ||
        version != kCorpusFormatVersion ||
        !read_u32(bytes, offset, count) || count > kMaximumCorpusEntries) {
        return std::nullopt;
    }
    Corpus corpus;
    for (std::uint32_t i = 0; i < count; ++i) {
        std::uint32_t name_size = 0U;
        if (!read_u32(bytes, offset, name_size) || name_size == 0U ||
            name_size > kMaximumCorpusEntryNameBytes ||
            bytes.size() - offset < name_size) {
            return std::nullopt;
        }
        std::string name;
        name.reserve(name_size);
        for (std::uint32_t j = 0; j < name_size; ++j) {
            name.push_back(static_cast<char>(
                std::to_integer<std::uint8_t>(bytes[offset + j])));
        }
        offset += name_size;
        std::uint64_t compressed_size = 0U;
        if (!read_u64(bytes, offset, compressed_size) ||
            bytes.size() - offset < compressed_size) {
            return std::nullopt;
        }
        std::optional<std::vector<std::byte>> blob = rle_decompress(
            bytes.subspan(offset, static_cast<std::size_t>(compressed_size)),
            kMaximumCaptureBytes);
        offset += static_cast<std::size_t>(compressed_size);
        if (!blob.has_value()) {
            return std::nullopt;
        }
        if (!corpus.add(std::move(name), std::move(*blob))) {
            return std::nullopt;
        }
    }
    if (offset != bytes.size()) {
        return std::nullopt;
    }
    return corpus;
}

FunctionCapture minimize_capture(
    const FunctionCapture& capture, const FailurePredicate& reproduces) {
    if (!reproduces || !reproduces(capture)) {
        return capture;
    }
    FunctionCapture minimized = capture;
    bool progressed = true;
    while (progressed) {
        progressed = false;
        for (std::size_t i = 0; i < minimized.pre_pages.size(); ++i) {
            FunctionCapture candidate = minimized;
            candidate.pre_pages.erase(
                candidate.pre_pages.begin() + static_cast<std::ptrdiff_t>(i));
            // Dropping a pre page changes the pre state, so its hash must be
            // recomputed for the candidate to stay internally consistent.
            std::optional<World> world = World::create(
                static_cast<std::size_t>(candidate.rdram_bytes));
            if (!world.has_value()) {
                return minimized;
            }
            for (const SparsePage& page : candidate.pre_pages) {
                std::copy(
                    page.bytes.begin(), page.bytes.end(),
                    world->rdram().begin() +
                        static_cast<std::ptrdiff_t>(
                            page.page_index * kWorldPageBytes));
            }
            world->context() = candidate.pre_context;
            const std::optional<StateDigest> pre_hash =
                world->hash(candidate.schema);
            if (!pre_hash.has_value()) {
                return minimized;
            }
            candidate.pre_hash = *pre_hash;
            if (reproduces(candidate)) {
                minimized = std::move(candidate);
                progressed = true;
                break;
            }
        }
    }
    return minimized;
}

} // namespace jfg::testkernel
