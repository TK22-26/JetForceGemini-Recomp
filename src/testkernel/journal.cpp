#include "jfg/testkernel/journal.hpp"

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

class Reader final {
public:
    explicit Reader(const std::span<const std::byte> bytes) noexcept
        : bytes_(bytes) {}

    [[nodiscard]] bool read_u32(std::uint32_t& value) noexcept {
        if (bytes_.size() - offset_ < 4U || offset_ > bytes_.size()) {
            return false;
        }
        value = 0U;
        for (std::size_t i = 0; i < 4U; ++i) {
            value |= std::to_integer<std::uint32_t>(bytes_[offset_ + i])
                << (8U * i);
        }
        offset_ += 4U;
        return true;
    }

    [[nodiscard]] bool read_u64(std::uint64_t& value) noexcept {
        if (bytes_.size() - offset_ < 8U || offset_ > bytes_.size()) {
            return false;
        }
        value = 0U;
        for (std::size_t i = 0; i < 8U; ++i) {
            value |= std::to_integer<std::uint64_t>(bytes_[offset_ + i])
                << (8U * i);
        }
        offset_ += 8U;
        return true;
    }

    [[nodiscard]] bool read_bytes(
        const std::size_t size, std::span<const std::byte>& view) noexcept {
        if (offset_ > bytes_.size() || bytes_.size() - offset_ < size) {
            return false;
        }
        view = bytes_.subspan(offset_, size);
        offset_ += size;
        return true;
    }

    [[nodiscard]] bool exhausted() const noexcept {
        return offset_ == bytes_.size();
    }

private:
    std::span<const std::byte> bytes_;
    std::size_t offset_ = 0U;
};

[[nodiscard]] bool known_effect(const std::uint32_t value) noexcept {
    return value >= static_cast<std::uint32_t>(
                        JournalEffect::kRendererSubmit) &&
        value <= static_cast<std::uint32_t>(JournalEffect::kCheckpoint);
}

} // namespace

bool Journal::append(
    const JournalEffect effect,
    const std::string_view label,
    const std::span<const std::byte> payload) {
    if (records_.size() >= kMaximumJournalRecords ||
        label.size() > kMaximumJournalLabelBytes ||
        payload.size() > kMaximumJournalPayloadBytes ||
        !known_effect(static_cast<std::uint32_t>(effect))) {
        return false;
    }
    records_.push_back(JournalRecord{
        .effect = effect,
        .label = std::string(label),
        .payload = std::vector<std::byte>(payload.begin(), payload.end()),
    });
    return true;
}

std::vector<std::byte> Journal::serialize() const {
    std::vector<std::byte> out;
    put_u64(out, records_.size());
    for (const JournalRecord& record : records_) {
        put_u32(out, static_cast<std::uint32_t>(record.effect));
        put_u32(out, static_cast<std::uint32_t>(record.label.size()));
        for (const char character : record.label) {
            out.push_back(static_cast<std::byte>(character));
        }
        put_u64(out, record.payload.size());
        out.insert(out.end(), record.payload.begin(), record.payload.end());
    }
    return out;
}

StateDigest Journal::digest() const {
    const std::vector<std::byte> bytes = serialize();
    return sha256_digest(std::span(bytes.data(), bytes.size()));
}

std::optional<Journal> Journal::deserialize(
    const std::span<const std::byte> bytes) {
    Reader reader(bytes);
    std::uint64_t count = 0U;
    if (!reader.read_u64(count) || count > kMaximumJournalRecords) {
        return std::nullopt;
    }
    Journal journal;
    for (std::uint64_t i = 0; i < count; ++i) {
        std::uint32_t effect = 0U;
        std::uint32_t label_size = 0U;
        if (!reader.read_u32(effect) || !known_effect(effect) ||
            !reader.read_u32(label_size) ||
            label_size > kMaximumJournalLabelBytes) {
            return std::nullopt;
        }
        std::span<const std::byte> label_bytes;
        if (!reader.read_bytes(label_size, label_bytes)) {
            return std::nullopt;
        }
        std::uint64_t payload_size = 0U;
        std::span<const std::byte> payload_bytes;
        if (!reader.read_u64(payload_size) ||
            payload_size > kMaximumJournalPayloadBytes ||
            !reader.read_bytes(
                static_cast<std::size_t>(payload_size), payload_bytes)) {
            return std::nullopt;
        }
        std::string label;
        label.reserve(label_bytes.size());
        for (const std::byte byte : label_bytes) {
            label.push_back(static_cast<char>(std::to_integer<std::uint8_t>(byte)));
        }
        if (!journal.append(
                static_cast<JournalEffect>(effect), label, payload_bytes)) {
            return std::nullopt;
        }
    }
    if (!reader.exhausted()) {
        return std::nullopt;
    }
    return journal;
}

} // namespace jfg::testkernel
