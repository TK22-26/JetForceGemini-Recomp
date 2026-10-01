#pragma once

#include "jfg/evidence/g2_paired_producer.hpp"

#include <cstddef>
#include <cstdint>
#include <span>
#include <stdexcept>
#include <vector>

namespace jfg::evidence {

inline constexpr std::uint32_t kG2PrivateTaskCaseVersion = 3U;
inline constexpr std::size_t kMaximumPrivateTaskCaseBytes =
    24U * 1024U * 1024U;

class G2PrivateTaskCaseCursor final {
public:
    explicit G2PrivateTaskCaseCursor(
        const std::span<const std::byte> payload) noexcept
        : payload_(payload) {}

    [[nodiscard]] std::uint32_t u32() {
        const std::uint32_t value = read_u32_le(payload_, cursor_);
        cursor_ += 4U;
        return value;
    }

    [[nodiscard]] std::span<const std::byte> blob(
        const std::size_t minimum,
        const std::size_t maximum,
        const std::size_t alignment = 1U) {
        const std::size_t size = u32();
        if (size < minimum || size > maximum || alignment == 0U ||
            size % alignment != 0U || cursor_ > payload_.size() ||
            size > payload_.size() - cursor_) {
            throw std::runtime_error("private task case field");
        }
        const auto result = payload_.subspan(cursor_, size);
        cursor_ += size;
        return result;
    }

    void finish() const {
        if (cursor_ != payload_.size()) {
            throw std::runtime_error("private task case trailing bytes");
        }
    }

private:
    std::span<const std::byte> payload_;
    std::size_t cursor_ = 0U;
};

[[nodiscard]] inline std::vector<std::byte> read_private_task_case(
    const PairedCaseFamily family,
    const ProducerIdentity& identity) {
    std::ifstream stream("case-input.bin", std::ios::binary | std::ios::ate);
    if (!stream) {
        throw std::runtime_error("case unavailable");
    }
    const auto length = stream.tellg();
    if (length < 0 || static_cast<std::uint64_t>(length) >
            kMaximumPrivateTaskCaseBytes) {
        throw std::runtime_error("case size");
    }
    std::vector<std::byte> bytes(static_cast<std::size_t>(length));
    stream.seekg(0);
    stream.read(reinterpret_cast<char*>(bytes.data()), length);
    if (!stream || bytes.size() < 20U ||
        !std::ranges::equal(std::span(bytes).first<8U>(), kPairedCaseMagic) ||
        read_u32_le(bytes, 8U) != kG2PrivateTaskCaseVersion ||
        read_u32_le(bytes, 12U) != static_cast<std::uint32_t>(family) ||
        read_u32_le(bytes, 16U) != bytes.size() - 20U ||
        hex_digest(bytes) != identity.subject_sha256) {
        throw std::runtime_error("case invalid");
    }
    return {bytes.begin() + 20, bytes.end()};
}

}  // namespace jfg::evidence
