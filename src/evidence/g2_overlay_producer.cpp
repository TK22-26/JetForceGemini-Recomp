#include "jfg/runtime/generated_overlay_runtime.hpp"
#include "jfg/evidence/g2_trap_probe_runtime.hpp"

#include "recomp.h"

#include <algorithm>
#include <array>
#include <bit>
#include <charconv>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <ranges>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <type_traits>
#include <vector>

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#elif JFG_G2_TRAP_PROBE_LINUX
#include <sys/mman.h>
#include <unistd.h>
#endif

extern "C" {

struct JfgGeneratedSectionMetadata {
    std::uint32_t rom_start;
    std::uint32_t linked_vram;
    std::uint32_t text_rom_offset;
    std::uint32_t text_size;
    std::uint32_t data_size;
    std::uint32_t bss_size;
    std::uint32_t is_overlay;
};

struct JfgGeneratedR32Descriptor {
    std::uint32_t site_offset;
    std::uint32_t target_section;
    std::uint32_t target_offset;
};

jfg::GeneratedOverlayFunction jfg_generated_lookup_function(std::int32_t vram);
std::size_t jfg_generated_section_count(void);
int jfg_generated_initialize_sections(std::int32_t* addresses, std::size_t capacity);
int jfg_generated_section_metadata(
    std::uint32_t section,
    JfgGeneratedSectionMetadata* output);
int jfg_generated_section_lifecycle(
    std::uint32_t operation,
    std::uint32_t section,
    std::int32_t base);
std::size_t jfg_generated_relocation_count(std::uint32_t source_section);
int jfg_generated_relocation_sites(
    std::uint32_t source_section,
    const std::uint32_t** output,
    std::size_t* count);
int jfg_generated_relocation_descriptors(
    std::uint32_t source_section,
    const JfgGeneratedR32Descriptor** output,
    std::size_t* count);
int jfg_generated_apply_relocations_checked(
    std::uint8_t* rdram,
    std::size_t rdram_size,
    std::uint32_t source_section);
int jfg_minimal_runtime_initialize(void);
int jfg_minimal_runtime_bind_dispatch(
    int (*callback)(void*, std::int32_t, std::uint8_t*, recomp_context*),
    void* opaque);
int jfg_minimal_runtime_unbind_dispatch(
    int (*callback)(void*, std::int32_t, std::uint8_t*, recomp_context*),
    void* opaque);

}  // extern "C"

namespace {

constexpr std::size_t kMaximumCaseBytes = 64U * 1024U * 1024U;
constexpr std::size_t kMaximumGuestBytes = 64U * 1024U * 1024U;
constexpr std::size_t kMaximumCaseIdBytes = 72U;
constexpr std::size_t kMaximumRelocationProbes = 4096U;
constexpr std::uint32_t kMaximumGeneratedSection = 65'499U;
// Shared by every subject in one V3 suite. Even if all children time out,
// 48 * 250 ms leaves substantial margin inside the dispatcher's 20 s limit.
#if defined(JFG_G2_OVERLAY_PRODUCER_TESTING) && \
    defined(JFG_G2_OVERLAY_TEST_MAX_PROBE_ATTEMPTS)
constexpr std::size_t kMaximumV3FunctionProbeAttempts =
    JFG_G2_OVERLAY_TEST_MAX_PROBE_ATTEMPTS;
#else
constexpr std::size_t kMaximumV3FunctionProbeAttempts = 48U;
#endif
static_assert(kMaximumV3FunctionProbeAttempts > 0U);
[[maybe_unused]] constexpr std::uint32_t
    kV3FunctionCandidateDeadlineMilliseconds = 250U;
constexpr std::size_t kV3ExecutionGuestBytes = 8U * 1024U * 1024U;
constexpr std::size_t kMinimumV3ProbeScratchBytes = 4096U;
constexpr std::size_t kMaximumV3ProbeScratchBytes = 64U * 1024U;
constexpr std::size_t kV3ProbeStackGuardBytes = 256U;
constexpr std::uint64_t kV3GuestAddressSpaceBytes = UINT64_C(1) << 32U;
constexpr std::array<std::byte, 8> kCaseMagicV1{
    std::byte{'J'},
    std::byte{'F'},
    std::byte{'G'},
    std::byte{'2'},
    std::byte{'O'},
    std::byte{'V'},
    std::byte{'L'},
    std::byte{'1'},
};
constexpr std::array<std::byte, 8> kCaseMagicV2{
    std::byte{'J'},
    std::byte{'F'},
    std::byte{'G'},
    std::byte{'2'},
    std::byte{'O'},
    std::byte{'V'},
    std::byte{'L'},
    std::byte{'2'},
};
constexpr std::array<std::byte, 8> kCaseMagicV3{
    std::byte{'J'},
    std::byte{'F'},
    std::byte{'G'},
    std::byte{'2'},
    std::byte{'O'},
    std::byte{'V'},
    std::byte{'L'},
    std::byte{'3'},
};
constexpr std::size_t kMaximumSuiteSubjects = 7U;
constexpr std::size_t kMaximumSuiteModules = 64U;

// The outer evidence dispatcher requires these exact markers in the reviewed
// binary. They are identities only; evidence is derived from the bounded case
// and actual generated-table/runtime calls below.
volatile const char kProbeMarker[] = "jfg_g2_overlay_lifecycle_probe";
volatile const char kLifecycleMarker[] = "jfg_generated_section_lifecycle";
volatile const char kRelocationMarker[] =
    "jfg_generated_apply_relocations_checked";
volatile const char kLookupMarker[] = "jfg_generated_lookup_function";

[[nodiscard]] bool markers_present() noexcept {
    return kProbeMarker[0] == 'j' && kLifecycleMarker[0] == 'j' &&
        kRelocationMarker[0] == 'j' && kLookupMarker[0] == 'j';
}

[[nodiscard]] std::uint32_t rotate_right(
    const std::uint32_t value,
    const unsigned shift) noexcept {
    return std::rotr(value, static_cast<int>(shift));
}

class Sha256 final {
public:
    void update(const std::span<const std::byte> input) noexcept {
        for (const std::byte value : input) {
            buffer_[buffer_size_++] = static_cast<std::uint8_t>(value);
            if (buffer_size_ == buffer_.size()) {
                transform();
                bit_count_ += 512U;
                buffer_size_ = 0U;
            }
        }
    }

    void update(const std::string_view input) noexcept {
        update(std::as_bytes(std::span(input.data(), input.size())));
    }

    [[nodiscard]] std::array<std::byte, 32> finish() noexcept {
        const std::uint64_t total_bits = bit_count_ + buffer_size_ * 8U;
        buffer_[buffer_size_++] = 0x80U;
        if (buffer_size_ > 56U) {
            std::fill(buffer_.begin() + static_cast<std::ptrdiff_t>(buffer_size_),
                      buffer_.end(), 0U);
            transform();
            buffer_size_ = 0U;
        }
        std::fill(buffer_.begin() + static_cast<std::ptrdiff_t>(buffer_size_),
                  buffer_.begin() + 56, 0U);
        for (std::size_t index = 0U; index < 8U; ++index) {
            buffer_[63U - index] = static_cast<std::uint8_t>(
                total_bits >> static_cast<unsigned>(index * 8U));
        }
        transform();

        std::array<std::byte, 32> result{};
        for (std::size_t index = 0U; index < state_.size(); ++index) {
            const std::uint32_t word = state_[index];
            result[index * 4U] = static_cast<std::byte>(word >> 24U);
            result[index * 4U + 1U] = static_cast<std::byte>(word >> 16U);
            result[index * 4U + 2U] = static_cast<std::byte>(word >> 8U);
            result[index * 4U + 3U] = static_cast<std::byte>(word);
        }
        return result;
    }

private:
    void transform() noexcept {
        static constexpr std::array<std::uint32_t, 64> constants{
            0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U,
            0x3956c25bU, 0x59f111f1U, 0x923f82a4U, 0xab1c5ed5U,
            0xd807aa98U, 0x12835b01U, 0x243185beU, 0x550c7dc3U,
            0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U, 0xc19bf174U,
            0xe49b69c1U, 0xefbe4786U, 0x0fc19dc6U, 0x240ca1ccU,
            0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU,
            0x983e5152U, 0xa831c66dU, 0xb00327c8U, 0xbf597fc7U,
            0xc6e00bf3U, 0xd5a79147U, 0x06ca6351U, 0x14292967U,
            0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU, 0x53380d13U,
            0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U,
            0xa2bfe8a1U, 0xa81a664bU, 0xc24b8b70U, 0xc76c51a3U,
            0xd192e819U, 0xd6990624U, 0xf40e3585U, 0x106aa070U,
            0x19a4c116U, 0x1e376c08U, 0x2748774cU, 0x34b0bcb5U,
            0x391c0cb3U, 0x4ed8aa4aU, 0x5b9cca4fU, 0x682e6ff3U,
            0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U,
            0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U,
        };
        std::array<std::uint32_t, 64> schedule{};
        for (std::size_t index = 0U; index < 16U; ++index) {
            schedule[index] =
                static_cast<std::uint32_t>(buffer_[index * 4U]) << 24U |
                static_cast<std::uint32_t>(buffer_[index * 4U + 1U]) << 16U |
                static_cast<std::uint32_t>(buffer_[index * 4U + 2U]) << 8U |
                static_cast<std::uint32_t>(buffer_[index * 4U + 3U]);
        }
        for (std::size_t index = 16U; index < schedule.size(); ++index) {
            const std::uint32_t s0 = rotate_right(schedule[index - 15U], 7U) ^
                rotate_right(schedule[index - 15U], 18U) ^
                (schedule[index - 15U] >> 3U);
            const std::uint32_t s1 = rotate_right(schedule[index - 2U], 17U) ^
                rotate_right(schedule[index - 2U], 19U) ^
                (schedule[index - 2U] >> 10U);
            schedule[index] = schedule[index - 16U] + s0 +
                schedule[index - 7U] + s1;
        }

        std::uint32_t a = state_[0];
        std::uint32_t b = state_[1];
        std::uint32_t c = state_[2];
        std::uint32_t d = state_[3];
        std::uint32_t e = state_[4];
        std::uint32_t f = state_[5];
        std::uint32_t g = state_[6];
        std::uint32_t h = state_[7];
        for (std::size_t index = 0U; index < schedule.size(); ++index) {
            const std::uint32_t sum1 = rotate_right(e, 6U) ^
                rotate_right(e, 11U) ^ rotate_right(e, 25U);
            const std::uint32_t choice = (e & f) ^ (~e & g);
            const std::uint32_t temporary1 =
                h + sum1 + choice + constants[index] + schedule[index];
            const std::uint32_t sum0 = rotate_right(a, 2U) ^
                rotate_right(a, 13U) ^ rotate_right(a, 22U);
            const std::uint32_t majority = (a & b) ^ (a & c) ^ (b & c);
            const std::uint32_t temporary2 = sum0 + majority;
            h = g;
            g = f;
            f = e;
            e = d + temporary1;
            d = c;
            c = b;
            b = a;
            a = temporary1 + temporary2;
        }
        state_[0] += a;
        state_[1] += b;
        state_[2] += c;
        state_[3] += d;
        state_[4] += e;
        state_[5] += f;
        state_[6] += g;
        state_[7] += h;
    }

    std::array<std::uint32_t, 8> state_{
        0x6a09e667U,
        0xbb67ae85U,
        0x3c6ef372U,
        0xa54ff53aU,
        0x510e527fU,
        0x9b05688cU,
        0x1f83d9abU,
        0x5be0cd19U,
    };
    std::array<std::uint8_t, 64> buffer_{};
    std::uint64_t bit_count_ = 0U;
    std::size_t buffer_size_ = 0U;
};

[[nodiscard]] std::string hex_digest(const std::span<const std::byte> bytes) {
    static constexpr char digits[] = "0123456789abcdef";
    Sha256 digest;
    digest.update(bytes);
    const auto raw = digest.finish();
    std::string result(raw.size() * 2U, '0');
    for (std::size_t index = 0U; index < raw.size(); ++index) {
        const auto value = static_cast<std::uint8_t>(raw[index]);
        result[index * 2U] = digits[value >> 4U];
        result[index * 2U + 1U] = digits[value & 0x0fU];
    }
    return result;
}

[[nodiscard]] bool is_identifier(const std::string_view value) noexcept {
    if (value.size() < 3U || value.size() > kMaximumCaseIdBytes) {
        return false;
    }
    const auto allowed = [](const char character) {
        return (character >= 'a' && character <= 'z') ||
            (character >= '0' && character <= '9') || character == '.' ||
            character == '_' || character == '-';
    };
    return value.front() != '.' && value.front() != '_' && value.front() != '-' &&
        value.back() != '.' && value.back() != '_' && value.back() != '-' &&
        std::all_of(value.begin(), value.end(), allowed);
}

[[nodiscard]] bool is_digest(const std::string_view value) noexcept {
    return value.size() == 64U && std::all_of(
        value.begin(), value.end(), [](const char character) {
            return (character >= '0' && character <= '9') ||
                (character >= 'a' && character <= 'f');
        });
}

class Reader final {
public:
    explicit Reader(const std::span<const std::byte> bytes) noexcept
        : bytes_(bytes) {}

    [[nodiscard]] std::uint8_t u8() {
        return static_cast<std::uint8_t>(take(1U)[0]);
    }

    [[nodiscard]] std::uint16_t u16() {
        const auto bytes = take(2U);
        return static_cast<std::uint16_t>(
            static_cast<std::uint16_t>(bytes[0]) |
            static_cast<std::uint16_t>(bytes[1]) << 8U);
    }

    [[nodiscard]] std::uint32_t u32() {
        const auto bytes = take(4U);
        return static_cast<std::uint32_t>(bytes[0]) |
            static_cast<std::uint32_t>(bytes[1]) << 8U |
            static_cast<std::uint32_t>(bytes[2]) << 16U |
            static_cast<std::uint32_t>(bytes[3]) << 24U;
    }

    [[nodiscard]] std::uint64_t u64() {
        const auto low = static_cast<std::uint64_t>(u32());
        const auto high = static_cast<std::uint64_t>(u32());
        return low | high << 32U;
    }

    [[nodiscard]] std::span<const std::byte> take(const std::size_t size) {
        if (size > bytes_.size() - position_) {
            throw std::runtime_error("bounded case");
        }
        const auto result = bytes_.subspan(position_, size);
        position_ += size;
        return result;
    }

    [[nodiscard]] bool done() const noexcept {
        return position_ == bytes_.size();
    }

private:
    std::span<const std::byte> bytes_;
    std::size_t position_ = 0U;
};

struct ModuleCase {
    std::uint64_t module_id = 0U;
    std::uint32_t section = 0U;
    std::uint32_t base = 0U;
    std::uint32_t function_offset = 0U;
    std::vector<std::byte> initialized;
};

struct RelocationProbe {
    std::uint32_t offset = 0U;
    std::uint8_t kind = 0U;
};

// V2 deliberately carries site identities and opaque binding identities, not
// generated addresses or caller-supplied relocation outcomes.  The generated
// table remains the source of truth for R_MIPS_32 sites.
struct CustomBindingCase {
    std::uint32_t opaque_target_id = 0U;
    std::uint32_t target_offset = 0U;
    std::uint8_t target_kind = 0U;
};

struct OverlayCase {
    std::string case_identifier;
    std::size_t guest_size = 0U;
    ModuleCase target;
    ModuleCase dependent;
    std::uint64_t reference_id = 0U;
    std::uint32_t copy_offset = 0U;
    std::uint32_t copy_size = 0U;
    std::vector<RelocationProbe> relocation_probes;
    bool is_custom_v2 = false;
    std::vector<std::uint32_t> generated_r32_sites;
    std::vector<jfg::CustomOverlayRelocationRecord> custom_relocations;
    std::vector<CustomBindingCase> custom_bindings;
};

// V3 is deliberately an opaque, multi-overlay transport. The private case
// binds each module to one reviewed section-relative generated-body identity
// and context seed, but contains no expected outcome/pass bit. Neither the
// identity nor the seed is emitted in the public observation.
struct V3ModuleCase {
    std::uint64_t opaque_module_id = 0U;
    std::uint32_t slot = 0U;
    std::uint32_t base = 0U;
    std::uint32_t text_size = 0U;
    std::uint32_t function_offset = 0U;
    std::uint8_t context_seed = 0U;
    std::vector<std::byte> initialized;
};

struct V3BindingCase {
    std::uint32_t opaque_target_id = 0U;
    std::uint32_t target_offset = 0U;
    std::uint8_t kind = 0U;
    std::uint32_t provider_slot = 0U;
};

struct V3SubjectCase {
    std::uint32_t slot = 0U;
    std::vector<std::uint32_t> generated_r32_sites;
    std::vector<jfg::CustomOverlayRelocationRecord> custom_relocations;
    std::vector<V3BindingCase> bindings;
};

struct V3SuiteCase {
    std::size_t guest_size = 0U;
    std::vector<std::byte> static_initialized;
    std::size_t static_bss_size = 0U;
    std::array<std::byte, 16U> token{};
    std::array<std::byte, 32U> commitment_salt{};
    std::array<std::byte, 32U> function_plan_digest{};
    std::vector<V3ModuleCase> modules;
    std::vector<V3SubjectCase> subjects;
};

struct ParsedCase {
    bool is_v3 = false;
    OverlayCase legacy;
    V3SuiteCase suite;
};

[[nodiscard]] ModuleCase read_module(Reader& reader) {
    ModuleCase result;
    result.module_id = reader.u64();
    result.section = reader.u32();
    result.base = reader.u32();
    result.function_offset = reader.u32();
    const std::uint32_t size = reader.u32();
    if (result.module_id == 0U || result.section > kMaximumGeneratedSection ||
        result.base < jfg::kGeneratedCachedGuestBase ||
        (result.base & 3U) != 0U || (result.function_offset & 3U) != 0U ||
        size == 0U || size > kMaximumCaseBytes || (size & 3U) != 0U ||
        result.function_offset >= size) {
        throw std::runtime_error("bounded module");
    }
    const auto initialized = reader.take(size);
    result.initialized.assign(initialized.begin(), initialized.end());
    return result;
}

void validate_module_geometry(const OverlayCase& result) {
    const std::uint64_t target_start =
        result.target.base - jfg::kGeneratedCachedGuestBase;
    const std::uint64_t dependent_start =
        result.dependent.base - jfg::kGeneratedCachedGuestBase;
    const std::uint64_t target_end = target_start + result.target.initialized.size();
    const std::uint64_t dependent_end =
        dependent_start + result.dependent.initialized.size();
    if (target_end > result.guest_size || dependent_end > result.guest_size ||
        !(target_end <= dependent_start || dependent_end <= target_start) ||
        result.target.module_id == result.dependent.module_id ||
        result.target.section == result.dependent.section ||
        result.target.base == result.dependent.base) {
        throw std::runtime_error("module geometry");
    }
}

[[nodiscard]] OverlayCase read_case_v1(Reader& reader) {
    if (reader.u32() != 1U) {
        throw std::runtime_error("case identity");
    }
    const auto identifier_bytes = reader.take(reader.u16());
    OverlayCase result;
    result.case_identifier = std::string(
        reinterpret_cast<const char*>(identifier_bytes.data()),
        identifier_bytes.size());
    if (!is_identifier(result.case_identifier)) {
        throw std::runtime_error("case id");
    }
    result.guest_size = reader.u32();
    if (result.guest_size == 0U || result.guest_size > kMaximumGuestBytes) {
        throw std::runtime_error("guest size");
    }
    result.target = read_module(reader);
    result.dependent = read_module(reader);
    validate_module_geometry(result);
    result.reference_id = reader.u64();
    result.copy_offset = reader.u32();
    result.copy_size = reader.u32();
    const std::uint32_t probe_count = reader.u32();
    const std::uint64_t copy_end =
        static_cast<std::uint64_t>(result.copy_offset) + result.copy_size;
    if (result.reference_id == 0U || result.copy_size == 0U ||
        copy_end > result.dependent.initialized.size() || probe_count < 4U ||
        probe_count > kMaximumRelocationProbes) {
        throw std::runtime_error("case denominator");
    }
    result.relocation_probes.reserve(probe_count);
    std::vector<std::uint32_t> probe_offsets;
    probe_offsets.reserve(probe_count);
    std::array<bool, 4> classes{};
    for (std::uint32_t index = 0U; index < probe_count; ++index) {
        const std::uint32_t offset = reader.u32();
        const std::uint8_t kind = reader.u8();
        if (kind > 3U || reader.u8() != 0U || reader.u8() != 0U ||
            reader.u8() != 0U || (offset & 3U) != 0U ||
            static_cast<std::uint64_t>(offset) + 4U >
                result.dependent.initialized.size() ||
            !(static_cast<std::uint64_t>(offset) + 4U <= result.copy_offset ||
              offset >= copy_end) ||
            std::ranges::find(probe_offsets, offset) != probe_offsets.end()) {
            throw std::runtime_error("relocation probe");
        }
        probe_offsets.push_back(offset);
        classes.at(kind) = true;
        result.relocation_probes.push_back({offset, kind});
    }
    if (!reader.done() || !std::ranges::all_of(
            classes, [](const bool present) { return present; })) {
        throw std::runtime_error("case closure");
    }
    return result;
}

[[nodiscard]] OverlayCase read_case_v2(Reader& reader) {
    if (reader.u32() != 2U) {
        throw std::runtime_error("case identity");
    }
    const auto identifier_bytes = reader.take(reader.u16());
    OverlayCase result;
    result.is_custom_v2 = true;
    result.case_identifier = std::string(
        reinterpret_cast<const char*>(identifier_bytes.data()),
        identifier_bytes.size());
    if (!is_identifier(result.case_identifier)) {
        throw std::runtime_error("case id");
    }
    result.guest_size = reader.u32();
    if (result.guest_size == 0U || result.guest_size > kMaximumGuestBytes) {
        throw std::runtime_error("guest size");
    }
    result.target = read_module(reader);
    result.dependent = read_module(reader);
    validate_module_geometry(result);

    const std::uint32_t r32_count = reader.u32();
    if (r32_count > kMaximumRelocationProbes) {
        throw std::runtime_error("r32 denominator");
    }
    result.generated_r32_sites.reserve(r32_count);
    for (std::uint32_t index = 0U; index < r32_count; ++index) {
        const std::uint32_t site = reader.u32();
        if (reader.u8() != 0U || reader.u8() != 0U || reader.u8() != 0U ||
            reader.u8() != 0U || (site & 3U) != 0U ||
            static_cast<std::uint64_t>(site) + 4U >
                result.dependent.initialized.size() ||
            (!result.generated_r32_sites.empty() &&
             site <= result.generated_r32_sites.back())) {
            throw std::runtime_error("r32 inventory");
        }
        result.generated_r32_sites.push_back(site);
    }

    const std::uint32_t custom_count = reader.u32();
    if (custom_count < 4U ||
        custom_count > jfg::kMaximumCustomOverlayRelocationsPerSection) {
        throw std::runtime_error("custom denominator");
    }
    result.custom_relocations.reserve(custom_count);
    std::vector<std::uint32_t> custom_sites;
    custom_sites.reserve(custom_count);
    std::array<bool, 4> patch_classes{};
    for (std::uint32_t index = 0U; index < custom_count; ++index) {
        const std::uint32_t site = reader.u32();
        const std::uint8_t source = reader.u8();
        const std::uint8_t patch = reader.u8();
        if (reader.u8() != 0U || reader.u8() != 0U) {
            throw std::runtime_error("custom reserved");
        }
        const std::uint32_t target = reader.u32();
        const std::int32_t addend = std::bit_cast<std::int32_t>(reader.u32());
        const bool source_valid = source <= 3U;
        const bool patch_valid = patch == 2U || patch == 4U || patch == 5U ||
            patch == 6U;
        const bool site_valid = (site & 3U) == 0U &&
            static_cast<std::uint64_t>(site) + 4U <=
                result.dependent.initialized.size();
        if (!source_valid || !patch_valid || !site_valid ||
            std::ranges::find(custom_sites, site) != custom_sites.end() ||
            ((source == 0U || source == 3U) && target == 0U) ||
            (source == 2U && target != 0U)) {
            throw std::runtime_error("custom relocation");
        }
        custom_sites.push_back(site);
        patch_classes.at(patch == 2U ? 0U : patch == 4U ? 1U :
            patch == 5U ? 2U : 3U) = true;
        result.custom_relocations.push_back({
            site,
            static_cast<jfg::CustomOverlayRelocationSource>(source),
            static_cast<jfg::CustomOverlayRelocationPatch>(patch),
            target,
            addend,
        });
    }
    const std::uint32_t binding_count = reader.u32();
    if (binding_count == 0U ||
        binding_count > jfg::kMaximumCustomOverlayRelocationsPerSection) {
        throw std::runtime_error("binding denominator");
    }
    result.custom_bindings.reserve(binding_count);
    std::vector<std::uint32_t> binding_ids;
    binding_ids.reserve(binding_count);
    for (std::uint32_t index = 0U; index < binding_count; ++index) {
        const std::uint32_t opaque = reader.u32();
        const std::uint32_t offset = reader.u32();
        const std::uint8_t kind = reader.u8();
        if (reader.u8() != 0U || reader.u8() != 0U || reader.u8() != 0U ||
            opaque == 0U || kind > 2U ||
            std::ranges::find(binding_ids, opaque) != binding_ids.end()) {
            throw std::runtime_error("custom binding");
        }
        binding_ids.push_back(opaque);
        result.custom_bindings.push_back({opaque, offset, kind});
    }
    if (!reader.done() || !std::ranges::all_of(
            patch_classes, [](const bool present) { return present; })) {
        throw std::runtime_error("custom closure");
    }
    for (const jfg::CustomOverlayRelocationRecord& record :
         result.custom_relocations) {
        if (record.source != jfg::CustomOverlayRelocationSource::external &&
            record.source != jfg::CustomOverlayRelocationSource::external_data) {
            continue;
        }
        if (std::ranges::find(binding_ids, record.target) == binding_ids.end()) {
            throw std::runtime_error("custom binding closure");
        }
        (void)record;
    }
    // The existing lifecycle exercise also proves ordinary generated binding
    // invalidation.  V2 adds custom-binding invalidation to that same bounded
    // two-module lifetime without accepting another untrusted identity field.
    result.reference_id = 1U;
    for (const jfg::CustomOverlayRelocationRecord& record :
         result.custom_relocations) {
        const std::uint8_t kind = record.patch ==
                jfg::CustomOverlayRelocationPatch::full_word ? 0U :
            record.patch == jfg::CustomOverlayRelocationPatch::jump_target ? 1U :
            record.patch == jfg::CustomOverlayRelocationPatch::hi16 ? 2U : 3U;
        result.relocation_probes.push_back({record.site_offset, kind});
    }
    return result;
}

[[nodiscard]] const V3ModuleCase& v3_module(
    const V3SuiteCase& suite, const std::uint32_t slot) {
    const auto found = std::find_if(
        suite.modules.begin(), suite.modules.end(), [slot](const V3ModuleCase& item) {
            return item.slot == slot;
        });
    if (found == suite.modules.end()) {
        throw std::runtime_error("v3 module closure");
    }
    return *found;
}

[[nodiscard]] const V3SubjectCase& v3_subject(
    const V3SuiteCase& suite, const std::uint32_t slot) {
    const auto found = std::find_if(
        suite.subjects.begin(), suite.subjects.end(), [slot](const V3SubjectCase& item) {
            return item.slot == slot;
        });
    if (found == suite.subjects.end()) {
        throw std::runtime_error("v3 subject closure");
    }
    return *found;
}

[[nodiscard]] V3SuiteCase read_case_v3(Reader& reader) {
    if (reader.u32() != 3U) {
        throw std::runtime_error("v3 identity");
    }
    const std::uint16_t subject_count = reader.u16();
    const std::uint16_t module_count = reader.u16();
    V3SuiteCase result;
    result.guest_size = reader.u32();
    const std::uint32_t static_initialized_size = reader.u32();
    result.static_bss_size = reader.u32();
    const auto token = reader.take(result.token.size());
    std::copy(token.begin(), token.end(), result.token.begin());
    const auto commitment_salt = reader.take(result.commitment_salt.size());
    std::copy(
        commitment_salt.begin(), commitment_salt.end(), result.commitment_salt.begin());
    auto sorted_commitment_salt = result.commitment_salt;
    std::ranges::sort(sorted_commitment_salt);
    const std::size_t commitment_salt_diversity = 1U + static_cast<std::size_t>(
        std::ranges::count_if(
            std::views::iota(std::size_t{1U}, sorted_commitment_salt.size()),
            [&sorted_commitment_salt](const std::size_t index) {
                return sorted_commitment_salt[index - 1U] !=
                    sorted_commitment_salt[index];
            }));
    const auto function_plan_digest = reader.take(result.function_plan_digest.size());
    std::copy(
        function_plan_digest.begin(),
        function_plan_digest.end(),
        result.function_plan_digest.begin());
    // A suite is a complete exercise of the packed populated-overlay set.
    // Leaving a module provider-only would leave its generated relocation
    // inventory outside the exact descriptor/formula proof below.
    if (subject_count == 0U || subject_count > kMaximumSuiteSubjects ||
        module_count != subject_count || module_count > kMaximumSuiteModules ||
        result.guest_size == 0U ||
        result.guest_size > kV3ExecutionGuestBytes ||
        static_initialized_size == 0U ||
        static_initialized_size > kMaximumCaseBytes ||
        (static_initialized_size & 3U) != 0U ||
        result.static_bss_size == 0U ||
        result.static_bss_size > kMaximumCaseBytes ||
        (result.static_bss_size & 3U) != 0U ||
        std::ranges::all_of(result.token, [](const std::byte value) {
            return value == std::byte{0};
        }) ||
        commitment_salt_diversity < 16U ||
        std::ranges::all_of(result.function_plan_digest, [](const std::byte value) {
            return value == std::byte{0};
        })) {
        throw std::runtime_error("v3 header");
    }
    const auto static_image = reader.take(static_initialized_size);
    result.static_initialized.assign(static_image.begin(), static_image.end());
    result.modules.reserve(module_count);
    for (std::uint16_t index = 0U; index < module_count; ++index) {
        V3ModuleCase module;
        module.opaque_module_id = reader.u64();
        module.slot = reader.u32();
        module.base = reader.u32();
        module.text_size = reader.u32();
        if (reader.u32() != 0U) {
            throw std::runtime_error("v3 module reserved");
        }
        const std::uint32_t initialized_size = reader.u32();
        module.function_offset = reader.u32();
        module.context_seed = reader.u8();
        const bool function_reserved = reader.u8() != 0U || reader.u8() != 0U ||
            reader.u8() != 0U;
        if (module.opaque_module_id == 0U || module.slot == 0U ||
            module.slot > kMaximumGeneratedSection ||
            module.base < jfg::kGeneratedCachedGuestBase ||
            (module.base & 3U) != 0U || module.text_size == 0U ||
            (module.text_size & 3U) != 0U || initialized_size == 0U ||
            initialized_size > kMaximumCaseBytes ||
            (initialized_size & 3U) != 0U || module.text_size > initialized_size ||
            (module.function_offset & 3U) != 0U ||
            module.function_offset >= module.text_size ||
            module.context_seed > 4U || function_reserved ||
            std::any_of(result.modules.begin(), result.modules.end(),
                [&module](const V3ModuleCase& prior) {
                    return prior.opaque_module_id == module.opaque_module_id ||
                        prior.slot == module.slot || prior.base == module.base;
                })) {
            throw std::runtime_error("v3 module");
        }
        const std::uint64_t end =
            static_cast<std::uint64_t>(module.base - jfg::kGeneratedCachedGuestBase) +
            initialized_size;
        if (end > result.guest_size || std::any_of(
                result.modules.begin(), result.modules.end(),
                [&module, initialized_size](const V3ModuleCase& prior) {
                    const std::uint64_t left =
                        prior.base - jfg::kGeneratedCachedGuestBase;
                    const std::uint64_t right = left + prior.initialized.size();
                    const std::uint64_t candidate =
                        module.base - jfg::kGeneratedCachedGuestBase;
                    return !(candidate + initialized_size <= left || right <= candidate);
                })) {
            throw std::runtime_error("v3 geometry");
        }
        const auto image = reader.take(initialized_size);
        module.initialized.assign(image.begin(), image.end());
        result.modules.push_back(std::move(module));
    }
    result.subjects.reserve(subject_count);
    std::array<bool, 4U> patch_classes{};
    std::array<bool, 3U> binding_classes{};
    bool any_generated_r32 = false;
    for (std::uint16_t index = 0U; index < subject_count; ++index) {
        V3SubjectCase subject;
        subject.slot = reader.u32();
        const std::uint32_t r32_count = reader.u32();
        const V3ModuleCase& module = v3_module(result, subject.slot);
        if (std::any_of(result.subjects.begin(), result.subjects.end(),
                [&subject](const V3SubjectCase& prior) {
                    return prior.slot == subject.slot;
                }) || r32_count > kMaximumRelocationProbes) {
            throw std::runtime_error("v3 subject");
        }
        subject.generated_r32_sites.reserve(r32_count);
        for (std::uint32_t item = 0U; item < r32_count; ++item) {
            const std::uint32_t site = reader.u32();
            if (reader.u8() != 0U || reader.u8() != 0U || reader.u8() != 0U ||
                reader.u8() != 0U || (site & 3U) != 0U ||
                static_cast<std::uint64_t>(site) + 4U > module.initialized.size() ||
                (!subject.generated_r32_sites.empty() &&
                 site <= subject.generated_r32_sites.back())) {
                throw std::runtime_error("v3 r32");
            }
            subject.generated_r32_sites.push_back(site);
        }
        any_generated_r32 = any_generated_r32 || r32_count != 0U;
        // The normalizer promotes authoritative patch-2 records into this
        // generated R32 inventory.  It is therefore the real full-word class
        // proof; requiring a second custom patch-2 record would demand a
        // duplicate relocation that the runtime correctly rejects.
        patch_classes[0] = patch_classes[0] || r32_count != 0U;
        const std::uint32_t custom_count = reader.u32();
        if (custom_count > jfg::kMaximumCustomOverlayRelocationsPerSection) {
            throw std::runtime_error("v3 custom denominator");
        }
        subject.custom_relocations.reserve(custom_count);
        for (std::uint32_t item = 0U; item < custom_count; ++item) {
            const std::uint32_t site = reader.u32();
            const std::uint8_t source = reader.u8();
            const std::uint8_t patch = reader.u8();
            if (reader.u8() != 0U || reader.u8() != 0U) {
                throw std::runtime_error("v3 custom reserved");
            }
            const std::uint32_t target = reader.u32();
            const std::int32_t addend = std::bit_cast<std::int32_t>(reader.u32());
            const bool valid_source = source <= 3U;
            const bool valid_patch = patch == 2U || patch == 4U || patch == 5U ||
                patch == 6U;
            const bool valid_site = (site & 3U) == 0U &&
                static_cast<std::uint64_t>(site) + 4U <= module.initialized.size() &&
                (source == 3U ? site >= module.text_size :
                    (patch == 2U || site < module.text_size));
            if (!valid_source || !valid_patch || !valid_site ||
                std::any_of(subject.custom_relocations.begin(),
                    subject.custom_relocations.end(), [site](const auto& prior) {
                        return prior.site_offset == site;
                    }) ||
                ((source == 0U || source == 3U) && target == 0U) ||
                (source == 1U && ((target & 3U) != 0U)) ||
                (source == 2U && target != 0U)) {
                throw std::runtime_error("v3 custom");
            }
            const auto relocation = jfg::CustomOverlayRelocationRecord{
                site,
                static_cast<jfg::CustomOverlayRelocationSource>(source),
                static_cast<jfg::CustomOverlayRelocationPatch>(patch),
                target,
                addend,
            };
            patch_classes.at(patch == 2U ? 0U : patch == 4U ? 1U :
                patch == 5U ? 2U : 3U) = true;
            subject.custom_relocations.push_back(relocation);
        }
        for (std::size_t item = 0U; item < subject.custom_relocations.size(); ++item) {
            const auto& record = subject.custom_relocations[item];
            if (record.patch != jfg::CustomOverlayRelocationPatch::hi16) {
                continue;
            }
            if (item + 1U >= subject.custom_relocations.size()) {
                throw std::runtime_error("v3 pair");
            }
            const auto& low = subject.custom_relocations[item + 1U];
            if (low.patch != jfg::CustomOverlayRelocationPatch::lo16 ||
                low.source != record.source || low.target != record.target ||
                low.addend != record.addend) {
                throw std::runtime_error("v3 pair");
            }
        }
        const std::uint32_t binding_count = reader.u32();
        if (binding_count > jfg::kMaximumCustomOverlayRelocationsPerSection) {
            throw std::runtime_error("v3 binding denominator");
        }
        subject.bindings.reserve(binding_count);
        for (std::uint32_t item = 0U; item < binding_count; ++item) {
            V3BindingCase binding;
            binding.opaque_target_id = reader.u32();
            binding.target_offset = reader.u32();
            binding.kind = reader.u8();
            if (reader.u8() != 0U || reader.u8() != 0U || reader.u8() != 0U) {
                throw std::runtime_error("v3 binding reserved");
            }
            binding.provider_slot = reader.u32();
            if (binding.opaque_target_id == 0U || binding.kind > 2U ||
                std::any_of(subject.bindings.begin(), subject.bindings.end(),
                    [&binding](const V3BindingCase& prior) {
                        return prior.opaque_target_id == binding.opaque_target_id;
                    }) ||
                (binding.kind != 2U && binding.provider_slot != 0U) ||
                (binding.kind == 2U &&
                    (binding.provider_slot == 0U || binding.provider_slot == subject.slot))) {
                throw std::runtime_error("v3 binding");
            }
            if (binding.kind == 2U) {
                (void)v3_module(result, binding.provider_slot);
            }
            binding_classes.at(binding.kind) = true;
            subject.bindings.push_back(binding);
        }
        for (const auto& record : subject.custom_relocations) {
            if ((record.source == jfg::CustomOverlayRelocationSource::external ||
                 record.source == jfg::CustomOverlayRelocationSource::external_data) &&
                std::none_of(subject.bindings.begin(), subject.bindings.end(),
                    [&record](const V3BindingCase& binding) {
                        return binding.opaque_target_id == record.target;
                    })) {
                throw std::runtime_error("v3 binding closure");
            }
        }
        for (const auto& binding : subject.bindings) {
            if (std::none_of(subject.custom_relocations.begin(),
                    subject.custom_relocations.end(), [&binding](const auto& record) {
                        return (record.source ==
                                    jfg::CustomOverlayRelocationSource::external ||
                                record.source ==
                                    jfg::CustomOverlayRelocationSource::external_data) &&
                            record.target == binding.opaque_target_id;
                    })) {
                throw std::runtime_error("v3 binding surplus");
            }
        }
        result.subjects.push_back(std::move(subject));
    }
    if (!reader.done() || !any_generated_r32 || !std::ranges::all_of(
            patch_classes, [](const bool item) { return item; }) ||
        !std::ranges::all_of(
            binding_classes, [](const bool item) { return item; })) {
        throw std::runtime_error("v3 suite closure");
    }
    return result;
}

[[nodiscard]] ParsedCase read_case(const std::span<const std::byte> bytes) {
    Reader reader(bytes);
    const auto magic = reader.take(kCaseMagicV1.size());
    if (std::ranges::equal(magic, kCaseMagicV1)) {
        ParsedCase result;
        result.legacy = read_case_v1(reader);
        return result;
    }
    if (std::ranges::equal(magic, kCaseMagicV2)) {
        ParsedCase result;
        result.legacy = read_case_v2(reader);
        return result;
    }
    if (std::ranges::equal(magic, kCaseMagicV3)) {
        ParsedCase result;
        result.is_v3 = true;
        result.suite = read_case_v3(reader);
        return result;
    }
    throw std::runtime_error("case identity");
}

[[nodiscard]] std::vector<std::byte> read_case_file() {
    std::ifstream stream("case-input.bin", std::ios::binary | std::ios::ate);
    if (!stream) {
        throw std::runtime_error("case unavailable");
    }
    const std::streamoff length = stream.tellg();
    if (length <= 0 || static_cast<std::uint64_t>(length) > kMaximumCaseBytes) {
        throw std::runtime_error("case size");
    }
    stream.seekg(0, std::ios::beg);
    std::vector<std::byte> result(static_cast<std::size_t>(length));
    if (!stream.read(reinterpret_cast<char*>(result.data()), length)) {
        throw std::runtime_error("case read");
    }
    return result;
}

class GeneratedAbiTable final : public jfg::GeneratedOverlayTable {
public:
    using R32Descriptor = jfg::GeneratedR32RelocationDescriptor;
    [[nodiscard]] std::size_t section_count() const override {
        return jfg_generated_section_count();
    }

    [[nodiscard]] bool initialize_sections(
        const std::span<std::int32_t> addresses) override {
        return jfg_generated_initialize_sections(addresses.data(), addresses.size()) != 0;
    }

    [[nodiscard]] bool section_extents(
        const std::uint32_t section,
        jfg::GeneratedSectionExtents& output) const override {
        JfgGeneratedSectionMetadata metadata{};
        if (jfg_generated_section_metadata(section, &metadata) == 0) {
            return false;
        }
        output = {
            metadata.text_size,
            metadata.data_size,
            metadata.bss_size,
            metadata.is_overlay == 1U,
        };
        return metadata.is_overlay <= 1U;
    }

    [[nodiscard]] bool update_section_lifecycle(
        const jfg::GeneratedSectionLifecycle operation,
        const std::uint32_t section,
        const std::int32_t base) override {
        const std::uint32_t code =
            operation == jfg::GeneratedSectionLifecycle::load ? 1U : 2U;
        return jfg_generated_section_lifecycle(code, section, base) == 0;
    }

    [[nodiscard]] std::size_t relocation_count(
        const std::uint32_t source_section) const override {
        return jfg_generated_relocation_count(source_section);
    }

    [[nodiscard]] bool relocation_sites(
        const std::uint32_t source_section,
        std::span<const std::uint32_t>& output) const override {
        const std::uint32_t* sites = nullptr;
        std::size_t count = 0U;
        if (jfg_generated_relocation_sites(source_section, &sites, &count) == 0 ||
            count != jfg_generated_relocation_count(source_section)) {
            output = {};
            return false;
        }
        if (count == 0U) {
            if (sites != nullptr) {
                output = {};
                return false;
            }
            output = {};
            return true;
        }
        if (sites == nullptr) {
            output = {};
            return false;
        }
        output = std::span<const std::uint32_t>(sites, count);
        return true;
    }

    [[nodiscard]] bool relocation_descriptors(
        const std::uint32_t source_section,
        std::span<const R32Descriptor>& output) const override {
        const JfgGeneratedR32Descriptor* descriptors = nullptr;
        std::size_t count = 0U;
        if (jfg_generated_relocation_descriptors(
                source_section, &descriptors, &count) == 0 ||
            count != jfg_generated_relocation_count(source_section)) {
            output = {};
            return false;
        }
        if (count == 0U) {
            if (descriptors != nullptr) {
                output = {};
                return false;
            }
            output = {};
            return true;
        }
        if (descriptors == nullptr) {
            output = {};
            return false;
        }
        descriptors_.clear();
        descriptors_.reserve(count);
        for (std::size_t index = 0U; index < count; ++index) {
            descriptors_.push_back({
                descriptors[index].site_offset,
                descriptors[index].target_section,
                descriptors[index].target_offset,
            });
        }
        output = descriptors_;
        return true;
    }

    [[nodiscard]] jfg::GeneratedRelocationResult apply_relocations_checked(
        const std::span<std::uint8_t> staged_rdram,
        const std::uint32_t source_section,
        const std::size_t expected_count) override {
        const bool applied = jfg_generated_apply_relocations_checked(
            staged_rdram.data(), staged_rdram.size(), source_section) != 0;
        return {applied, applied ? expected_count : 0U};
    }

    [[nodiscard]] jfg::GeneratedOverlayFunction lookup_function(
        const std::int32_t guest_address) const override {
        return jfg_generated_lookup_function(guest_address);
    }

private:
    mutable std::vector<R32Descriptor> descriptors_;
};

class EvidenceCache final : public jfg::GeneratedInstructionCacheInvalidator {
public:
    jfg::GeneratedOverlayRuntime* runtime = nullptr;
    jfg::GeneratedOverlayError reentry = jfg::GeneratedOverlayError::none;
    bool prepared = false;
    bool committed = false;
    bool throw_from_prepare = false;

    [[nodiscard]] bool prepare(
        const jfg::GeneratedInstructionCacheRange&) override {
        prepared = true;
        if (runtime != nullptr) {
            reentry = runtime->lookup_function({}, 0U).error;
        }
        if (throw_from_prepare) {
            throw std::runtime_error("bounded callback failure");
        }
        return true;
    }

    void commit(const jfg::GeneratedInstructionCacheRange&) noexcept override {
        committed = true;
    }
};

static_assert(std::is_same_v<jfg::GeneratedOverlayFunction, recomp_func_t*>);

#if JFG_G2_TRAP_PROBE_LINUX
[[nodiscard]] int generated_body_dispatch(
    void* const opaque,
    const std::int32_t guest_address,
    std::uint8_t* const rdram,
    recomp_context* const context) noexcept {
    auto* const runtime = static_cast<jfg::GeneratedOverlayRuntime*>(opaque);
    if (runtime == nullptr) {
        return 0;
    }
    return runtime->invoke_leased_function_by_guest_address(
               static_cast<std::uint32_t>(guest_address), rdram, context) ==
            jfg::GeneratedOverlayError::none
        ? 1
        : 0;
}

struct GeneratedBodyInvocation final {
    jfg::GeneratedOverlayFunctionHandle function;
    std::uint8_t* rdram = nullptr;
    recomp_context context{};
    std::size_t scratch_offset = 0U;
    std::size_t scratch_size = 0U;
};

void invoke_generated_body(void* const opaque) {
    auto* const invocation = static_cast<GeneratedBodyInvocation*>(opaque);
    if (invocation == nullptr || !invocation->function.valid() ||
        invocation->rdram == nullptr) {
        std::abort();
    }
    if (invocation->scratch_size != 0U) {
        std::fill_n(
            invocation->rdram + invocation->scratch_offset,
            invocation->scratch_size,
            std::uint8_t{0U});
    }
    if (invocation->function.invoke(invocation->rdram, &invocation->context) !=
            jfg::GeneratedOverlayError::none) {
        std::abort();
    }
}
#endif

enum class GeneratedContextSeed : std::uint8_t {
    zero,
    stack,
    stack_and_frame,
    stack_and_arguments,
    stack_frame_and_arguments,
};

static_assert(std::is_standard_layout_v<recomp_context>);
static_assert(std::is_same_v<decltype(recomp_context::r4), gpr>);
static_assert(std::is_same_v<decltype(recomp_context::r7), gpr>);
static_assert(std::is_same_v<decltype(recomp_context::r29), gpr>);
static_assert(std::is_same_v<decltype(recomp_context::r30), gpr>);
static_assert(offsetof(recomp_context, r4) == 4U * sizeof(gpr));
static_assert(offsetof(recomp_context, r7) == 7U * sizeof(gpr));
static_assert(offsetof(recomp_context, r29) == 29U * sizeof(gpr));
static_assert(offsetof(recomp_context, r30) == 30U * sizeof(gpr));

struct GeneratedProbeScratch final {
    std::size_t offset = 0U;
    std::size_t size = 0U;
    gpr stack_address = 0U;

    [[nodiscard]] bool valid() const noexcept {
        return size >= kMinimumV3ProbeScratchBytes &&
            size <= kMaximumV3ProbeScratchBytes && stack_address != 0U;
    }
};

struct GeneratedProbeBudget final {
    std::size_t attempts = 0U;

    [[nodiscard]] bool consume() noexcept {
        if (attempts >= kMaximumV3FunctionProbeAttempts) {
            return false;
        }
        ++attempts;
        return true;
    }
};

class V3GuestMemory final {
public:
    V3GuestMemory() {
#if SIZE_MAX < UINT64_MAX
        throw std::runtime_error("v3 guest backing");
#elif defined(_WIN32)
        mapping_ = VirtualAlloc(
            nullptr,
            static_cast<SIZE_T>(kV3GuestAddressSpaceBytes),
            MEM_RESERVE,
            PAGE_NOACCESS);
        if (mapping_ == nullptr || VirtualAlloc(
                mapping_,
                kV3ExecutionGuestBytes,
                MEM_COMMIT,
                PAGE_READWRITE) != mapping_) {
            if (mapping_ != nullptr) {
                (void)VirtualFree(mapping_, 0U, MEM_RELEASE);
                mapping_ = nullptr;
            }
            throw std::runtime_error("v3 guest backing");
        }
        bytes_ = {
            static_cast<std::byte*>(mapping_),
            kV3ExecutionGuestBytes,
        };
#elif JFG_G2_TRAP_PROBE_LINUX
        mapping_ = mmap(
            nullptr,
            static_cast<std::size_t>(kV3GuestAddressSpaceBytes),
            PROT_NONE,
            MAP_PRIVATE | MAP_ANONYMOUS
#if defined(MAP_NORESERVE)
                | MAP_NORESERVE
#endif
            ,
            -1,
            0);
        if (mapping_ == MAP_FAILED) {
            mapping_ = nullptr;
            throw std::runtime_error("v3 guest backing");
        }
        if (mprotect(
                mapping_,
                kV3ExecutionGuestBytes,
                PROT_READ | PROT_WRITE) != 0) {
            (void)munmap(
                mapping_, static_cast<std::size_t>(kV3GuestAddressSpaceBytes));
            mapping_ = nullptr;
            throw std::runtime_error("v3 guest backing");
        }
        bytes_ = {
            static_cast<std::byte*>(mapping_),
            kV3ExecutionGuestBytes,
        };
#else
        throw std::runtime_error("v3 guest backing");
#endif
        std::ranges::fill(bytes_, std::byte{0xa5});
    }

    ~V3GuestMemory() {
#if defined(_WIN32)
        if (mapping_ != nullptr) {
            (void)VirtualFree(mapping_, 0U, MEM_RELEASE);
        }
#elif JFG_G2_TRAP_PROBE_LINUX
        if (mapping_ != nullptr) {
            (void)munmap(
                mapping_, static_cast<std::size_t>(kV3GuestAddressSpaceBytes));
        }
#endif
    }

    V3GuestMemory(const V3GuestMemory&) = delete;
    V3GuestMemory& operator=(const V3GuestMemory&) = delete;

    [[nodiscard]] std::span<std::byte> bytes() noexcept {
        return bytes_;
    }

#if defined(JFG_G2_OVERLAY_PRODUCER_TESTING)
    [[nodiscard]] volatile std::byte* test_address(
        const std::uint64_t offset) noexcept {
        return reinterpret_cast<volatile std::byte*>(
            reinterpret_cast<std::uintptr_t>(bytes_.data()) + offset);
    }
#endif

private:
    std::span<std::byte> bytes_;
#if defined(_WIN32) || JFG_G2_TRAP_PROBE_LINUX
    void* mapping_ = nullptr;
#endif
};

#if JFG_G2_TRAP_PROBE_LINUX
[[nodiscard]] bool seed_generated_context(
    recomp_context& context,
    const GeneratedContextSeed seed,
    const GeneratedProbeScratch& scratch) noexcept {
    context = {};
    if (seed == GeneratedContextSeed::zero) {
        return true;
    }
    if (!scratch.valid()) {
        return false;
    }
    context.r29 = scratch.stack_address;
    if (seed == GeneratedContextSeed::stack_and_frame ||
        seed == GeneratedContextSeed::stack_frame_and_arguments) {
        context.r30 = scratch.stack_address;
    }
    if (seed == GeneratedContextSeed::stack_and_arguments ||
        seed == GeneratedContextSeed::stack_frame_and_arguments) {
        // A reviewed leaf may expect the standard four argument registers to
        // name guest storage. Bind them to the isolated, zeroed scratch range
        // instead of allowing a zero register value to translate 2 GiB past
        // rdram. The profile remains fixed input data; it does not encode an
        // expected outcome or adapt after execution.
        context.r4 = scratch.stack_address;
        context.r5 = scratch.stack_address;
        context.r6 = scratch.stack_address;
        context.r7 = scratch.stack_address;
    }
    return true;
}
#endif

[[maybe_unused, nodiscard]] jfg::evidence::trap_probe::RunOutcome
probe_generated_handle_invocation(
    jfg::GeneratedOverlayRuntime& runtime,
    const jfg::GeneratedOverlayFunctionHandle& function,
    const std::span<std::byte> guest,
    const std::array<std::byte, 16U>& suite_token,
    const std::uint32_t deadline_milliseconds,
    const GeneratedContextSeed seed,
    const GeneratedProbeScratch& scratch) {
#if !JFG_G2_TRAP_PROBE_LINUX
    (void)runtime;
    (void)function;
    (void)guest;
    (void)suite_token;
    (void)deadline_milliseconds;
    (void)seed;
    (void)scratch;
    throw std::runtime_error("generated body probe unavailable");
#else
    if (!function.valid() || guest.empty()) {
        throw std::runtime_error("generated body probe setup");
    }
    GeneratedBodyInvocation invocation{};
    invocation.function = function;
    invocation.rdram = reinterpret_cast<std::uint8_t*>(guest.data());
    invocation.scratch_offset = scratch.offset;
    invocation.scratch_size = seed == GeneratedContextSeed::zero
        ? 0U
        : scratch.size;
    if (!seed_generated_context(invocation.context, seed, scratch)) {
        return jfg::evidence::trap_probe::RunOutcome::kUnavailable;
    }
    if (jfg_minimal_runtime_bind_dispatch(generated_body_dispatch, &runtime) == 0) {
        throw std::runtime_error("generated body probe setup");
    }
    jfg::evidence::trap_probe::RunOptions options{};
    options.deadline_milliseconds = deadline_milliseconds;
    options.allow_normal_return = true;
    for (std::size_t index = 0U; index < options.candidate_token.size(); ++index) {
        options.candidate_token[index] = suite_token[index % suite_token.size()];
    }
    jfg::evidence::trap_probe::RunOutcome outcome{};
    try {
        const auto result = jfg::evidence::trap_probe::run_isolated(
            invoke_generated_body, &invocation, options);
        outcome = result.outcome;
    }
    catch (...) {
        (void)jfg_minimal_runtime_unbind_dispatch(
            generated_body_dispatch, &runtime);
        throw;
    }
    if (jfg_minimal_runtime_unbind_dispatch(
            generated_body_dispatch, &runtime) == 0) {
        throw std::runtime_error("generated body probe");
    }
    return outcome;
#endif
}

void require_generated_handle_invocation(
    jfg::GeneratedOverlayRuntime& runtime,
    const jfg::GeneratedOverlayFunctionHandle& function,
    const std::span<std::byte> guest,
    const std::array<std::byte, 16U>& suite_token,
    const GeneratedContextSeed seed,
    const GeneratedProbeScratch& scratch,
    GeneratedProbeBudget& budget) {
#if !JFG_G2_TRAP_PROBE_LINUX
    (void)runtime;
    (void)function;
    (void)guest;
    (void)suite_token;
    (void)seed;
    (void)scratch;
    (void)budget;
    throw std::runtime_error("generated body probe unavailable");
#else
    if (!budget.consume()) {
        throw std::runtime_error("generated body probe budget");
    }
    const auto outcome = probe_generated_handle_invocation(
        runtime, function, guest, suite_token,
        kV3FunctionCandidateDeadlineMilliseconds, seed, scratch);
    if (outcome != jfg::evidence::trap_probe::RunOutcome::kNormalReturn &&
        outcome != jfg::evidence::trap_probe::RunOutcome::kObservedFatal) {
        throw std::runtime_error("generated body probe");
    }
#endif
}

struct SelectedGeneratedFunction final {
    std::uint32_t offset = 0U;
    jfg::GeneratedOverlayFunctionHandle function;
    GeneratedContextSeed seed = GeneratedContextSeed::zero;
};

[[nodiscard]] SelectedGeneratedFunction resolve_reviewed_generated_function(
    jfg::GeneratedOverlayRuntime& runtime,
    const jfg::GeneratedOverlayToken lifetime,
    const V3ModuleCase& module,
    const std::span<std::byte> guest,
    const std::array<std::byte, 16U>& suite_token,
    const GeneratedProbeScratch& scratch,
    GeneratedProbeBudget& budget) {
    const auto resolved = runtime.lookup_function(
        lifetime, module.function_offset);
    if (!resolved.ok()) {
        throw std::runtime_error("reviewed generated body lookup");
    }
    const auto seed = static_cast<GeneratedContextSeed>(module.context_seed);
    require_generated_handle_invocation(
        runtime, resolved.function, guest, suite_token, seed, scratch, budget);
    return {module.function_offset, resolved.function, seed};
}

[[nodiscard]] std::size_t checked_offset(
    const ModuleCase& module,
    const jfg::GeneratedSectionExtents& extents,
    const std::size_t guest_size) {
    if (module.base < jfg::kGeneratedCachedGuestBase ||
        (module.base & 3U) != 0U || (module.function_offset & 3U) != 0U) {
        throw std::runtime_error("module mapping");
    }
    const std::uint64_t offset =
        static_cast<std::uint64_t>(module.base - jfg::kGeneratedCachedGuestBase);
    const std::uint64_t initialized =
        static_cast<std::uint64_t>(extents.text_size) + extents.data_size;
    const std::uint64_t total = initialized + extents.bss_size;
    if (!extents.is_overlay || initialized != module.initialized.size() ||
        module.function_offset >= extents.text_size || offset + total > guest_size) {
        throw std::runtime_error("module extents");
    }
    return static_cast<std::size_t>(offset);
}

[[nodiscard]] std::uint32_t read_be32(
    const std::span<const std::byte> bytes,
    const std::size_t offset) {
    if (offset > bytes.size() || bytes.size() - offset < 4U) {
        throw std::runtime_error("word bounds");
    }
    return (std::to_integer<std::uint32_t>(bytes[offset]) << 24U) |
        (std::to_integer<std::uint32_t>(bytes[offset + 1U]) << 16U) |
        (std::to_integer<std::uint32_t>(bytes[offset + 2U]) << 8U) |
        std::to_integer<std::uint32_t>(bytes[offset + 3U]);
}

[[nodiscard]] std::uint32_t add_signed_address(
    const std::uint32_t address,
    const std::int32_t addend) {
    const std::int64_t value = static_cast<std::int64_t>(address) + addend;
    if (value < 0 || value > std::numeric_limits<std::uint32_t>::max()) {
        throw std::runtime_error("address overflow");
    }
    return static_cast<std::uint32_t>(value);
}

[[nodiscard]] std::uint32_t add_unsigned_address(
    const std::uint32_t address,
    const std::uint32_t offset) {
    if (address > std::numeric_limits<std::uint32_t>::max() - offset) {
        throw std::runtime_error("address overflow");
    }
    return address + offset;
}

[[nodiscard]] std::uint32_t custom_binding_address(
    const OverlayCase& input,
    const CustomBindingCase& binding) {
    switch (binding.target_kind) {
    case 0U: {
        // Static binding kinds are an ABI enum, never a guest address from
        // the packed case. Section zero's generated metadata supplies the
        // independently checked initial guest base and extent.
        JfgGeneratedSectionMetadata metadata{};
        if (jfg_generated_section_metadata(0U, &metadata) == 0 ||
            metadata.is_overlay != 0U) {
            throw std::runtime_error("static binding extent");
        }
        const std::uint64_t mapped_size =
            static_cast<std::uint64_t>(metadata.text_size) +
            metadata.data_size + metadata.bss_size;
        if (binding.target_offset >= mapped_size) {
            throw std::runtime_error("static binding extent");
        }
        return add_unsigned_address(metadata.linked_vram, binding.target_offset);
    }
    case 1U:
        return add_unsigned_address(input.dependent.base, binding.target_offset);
    case 2U:
        return add_unsigned_address(input.target.base, binding.target_offset);
    default:
        throw std::runtime_error("binding kind");
    }
}

[[nodiscard]] std::uint32_t expected_custom_word(
    const OverlayCase& input,
    const jfg::CustomOverlayRelocationRecord& record,
    const std::uint32_t original) {
    std::uint32_t target = 0U;
    if (record.source == jfg::CustomOverlayRelocationSource::local_offset) {
        target = add_unsigned_address(input.dependent.base, record.target);
    }
    else if (record.source == jfg::CustomOverlayRelocationSource::local_jump) {
        target = add_unsigned_address(
            input.dependent.base, (original & 0x03FFFFFFU) << 2U);
    }
    else {
        const auto found = std::find_if(
            input.custom_bindings.begin(), input.custom_bindings.end(),
            [&record](const CustomBindingCase& binding) {
                return binding.opaque_target_id == record.target;
            });
        if (found == input.custom_bindings.end()) {
            throw std::runtime_error("binding closure");
        }
        target = custom_binding_address(input, *found);
    }
    const std::uint32_t value = add_signed_address(target, record.addend);
    switch (record.patch) {
    case jfg::CustomOverlayRelocationPatch::full_word:
        return value;
    case jfg::CustomOverlayRelocationPatch::jump_target:
        if ((value & 3U) != 0U ||
            (value & 0xF0000000U) !=
                ((input.dependent.base + record.site_offset + 4U) & 0xF0000000U)) {
            throw std::runtime_error("jump formula");
        }
        return (original & 0xFC000000U) | ((value >> 2U) & 0x03FFFFFFU);
    case jfg::CustomOverlayRelocationPatch::hi16:
        return (original & 0xFFFF0000U) |
            static_cast<std::uint32_t>(
                (static_cast<std::uint64_t>(value) + 0x8000ULL) >> 16U);
    case jfg::CustomOverlayRelocationPatch::lo16:
        return (original & 0xFFFF0000U) | (value & 0xFFFFU);
    }
    throw std::runtime_error("patch formula");
}

void validate_custom_formulas(
    const OverlayCase& input,
    const std::span<const std::byte> before,
    const std::span<const std::byte> after) {
    for (const jfg::CustomOverlayRelocationRecord& record :
         input.custom_relocations) {
        const std::uint32_t expected = expected_custom_word(
            input, record, read_be32(before, record.site_offset));
        if (read_be32(after, record.site_offset) != expected) {
            throw std::runtime_error("custom relocation formula");
        }
    }
}

[[nodiscard]] std::uint32_t generated_descriptor_target_address(
    const OverlayCase& input,
    const jfg::GeneratedSectionExtents& target_extents,
    const jfg::GeneratedSectionExtents& dependent_extents,
    const GeneratedAbiTable::R32Descriptor& descriptor) {
    std::uint32_t base = 0U;
    std::uint64_t extent = 0U;
    if (descriptor.target_section == input.target.section) {
        base = input.target.base;
        extent = static_cast<std::uint64_t>(target_extents.text_size) +
            target_extents.data_size + target_extents.bss_size;
    }
    else if (descriptor.target_section == input.dependent.section) {
        base = input.dependent.base;
        extent = static_cast<std::uint64_t>(dependent_extents.text_size) +
            dependent_extents.data_size + dependent_extents.bss_size;
    }
    else {
        // Non-overlay sections are initialized from their generated linked
        // base before the runtime accepts any overlay.  Do not substitute an
        // arbitrary packed-case address for this table-owned mapping.
        JfgGeneratedSectionMetadata metadata{};
        if (jfg_generated_section_metadata(descriptor.target_section, &metadata) ==
                0 ||
            metadata.is_overlay != 0U ||
            metadata.linked_vram < jfg::kGeneratedCachedGuestBase) {
            throw std::runtime_error("r32 descriptor target");
        }
        base = metadata.linked_vram;
        extent = static_cast<std::uint64_t>(metadata.text_size) +
            metadata.data_size + metadata.bss_size;
    }
    if (descriptor.target_offset >= extent) {
        throw std::runtime_error("r32 descriptor extent");
    }
    return add_unsigned_address(base, descriptor.target_offset);
}

void validate_generated_r32_formulas(
    const OverlayCase& input,
    const jfg::GeneratedSectionExtents& target_extents,
    const jfg::GeneratedSectionExtents& dependent_extents,
    const std::span<const GeneratedAbiTable::R32Descriptor> descriptors,
    const std::span<const std::byte> relocated) {
    if (descriptors.size() != input.generated_r32_sites.size()) {
        throw std::runtime_error("r32 descriptor count");
    }
    for (std::size_t index = 0U; index < descriptors.size(); ++index) {
        const GeneratedAbiTable::R32Descriptor& descriptor = descriptors[index];
        if (descriptor.site_offset != input.generated_r32_sites[index]) {
            throw std::runtime_error("r32 descriptor order");
        }
        const std::uint32_t expected = generated_descriptor_target_address(
            input, target_extents, dependent_extents, descriptor);
        if (read_be32(relocated, descriptor.site_offset) != expected) {
            throw std::runtime_error("r32 descriptor formula");
        }
    }
}

[[nodiscard]] jfg::GeneratedSectionExtents v3_extents(const V3ModuleCase& module) {
    JfgGeneratedSectionMetadata metadata{};
    if (jfg_generated_section_metadata(module.slot, &metadata) == 0 ||
        metadata.is_overlay != 1U || metadata.text_size != module.text_size ||
        static_cast<std::uint64_t>(metadata.text_size) + metadata.data_size !=
            module.initialized.size()) {
        throw std::runtime_error("v3 generated extents");
    }
    return {metadata.text_size, metadata.data_size, metadata.bss_size, true};
}

struct V3StaticMapping final {
    std::uint32_t slot = 0U;
    JfgGeneratedSectionMetadata metadata{};
    std::size_t begin = 0U;
    std::size_t end = 0U;
};

[[nodiscard]] V3StaticMapping v3_static_mapping(const V3SuiteCase& suite) {
    const std::size_t count = jfg_generated_section_count();
    if (count == 0U || count > static_cast<std::size_t>(kMaximumGeneratedSection) + 1U) {
        throw std::runtime_error("v3 static metadata");
    }
    bool found = false;
    V3StaticMapping result;
    for (std::size_t index = 0U; index < count; ++index) {
        JfgGeneratedSectionMetadata metadata{};
        if (jfg_generated_section_metadata(static_cast<std::uint32_t>(index), &metadata) == 0) {
            throw std::runtime_error("v3 static metadata");
        }
        if (metadata.is_overlay != 0U) {
            continue;
        }
        if (found || index != 0U || metadata.linked_vram < jfg::kGeneratedCachedGuestBase ||
            (metadata.linked_vram & 3U) != 0U || metadata.text_size == 0U ||
            (metadata.text_size & 3U) != 0U || (metadata.data_size & 3U) != 0U ||
            (metadata.bss_size & 3U) != 0U ||
            static_cast<std::uint64_t>(metadata.text_size) + metadata.data_size !=
                suite.static_initialized.size() ||
            metadata.bss_size != suite.static_bss_size) {
            throw std::runtime_error("v3 static metadata");
        }
        const std::uint64_t begin = metadata.linked_vram - jfg::kGeneratedCachedGuestBase;
        const std::uint64_t end = begin + metadata.text_size + metadata.data_size +
            metadata.bss_size;
        if (end > suite.guest_size || end > kV3ExecutionGuestBytes) {
            throw std::runtime_error("v3 static geometry");
        }
        result.slot = static_cast<std::uint32_t>(index);
        result.metadata = metadata;
        result.begin = static_cast<std::size_t>(begin);
        result.end = static_cast<std::size_t>(end);
        found = true;
    }
    if (!found) {
        throw std::runtime_error("v3 static metadata");
    }
    return result;
}

void initialize_v3_static_memory(
    const V3SuiteCase& suite, const std::span<std::byte> guest) {
    const V3StaticMapping mapping = v3_static_mapping(suite);
    if (mapping.begin > guest.size() || mapping.end > guest.size()) {
        throw std::runtime_error("v3 static geometry");
    }
    std::copy(
        suite.static_initialized.begin(),
        suite.static_initialized.end(),
        guest.begin() + static_cast<std::ptrdiff_t>(mapping.begin));
    std::fill(
        guest.begin() + static_cast<std::ptrdiff_t>(
            mapping.begin + suite.static_initialized.size()),
        guest.begin() + static_cast<std::ptrdiff_t>(mapping.end),
        std::byte{0});
}

[[nodiscard]] std::uint32_t v3_binding_address(
    const V3SuiteCase& suite,
    const V3SubjectCase& subject,
    const V3BindingCase& binding) {
    if (binding.kind == 0U) {
        const V3StaticMapping mapping = v3_static_mapping(suite);
        if (binding.target_offset >=
                static_cast<std::uint64_t>(mapping.metadata.text_size) +
                    mapping.metadata.data_size + mapping.metadata.bss_size) {
            throw std::runtime_error("v3 static binding");
        }
        return add_unsigned_address(mapping.metadata.linked_vram, binding.target_offset);
    }
    const V3ModuleCase& target = binding.kind == 1U
        ? v3_module(suite, subject.slot)
        : v3_module(suite, binding.provider_slot);
    const jfg::GeneratedSectionExtents extents = v3_extents(target);
    if (binding.target_offset >= static_cast<std::uint64_t>(extents.text_size) +
            extents.data_size + extents.bss_size) {
        throw std::runtime_error("v3 binding extent");
    }
    return add_unsigned_address(target.base, binding.target_offset);
}

void validate_v3_custom_formulas(
    const V3SuiteCase& suite,
    const V3SubjectCase& subject,
    const V3ModuleCase& module,
    const std::span<const std::byte> before,
    const std::span<const std::byte> after) {
    for (const auto& record : subject.custom_relocations) {
        const std::uint32_t original = read_be32(before, record.site_offset);
        std::uint32_t target = 0U;
        if (record.source == jfg::CustomOverlayRelocationSource::local_offset) {
            target = add_unsigned_address(module.base, record.target);
        } else if (record.source == jfg::CustomOverlayRelocationSource::local_jump) {
            target = add_unsigned_address(module.base, (original & 0x03ffffffU) << 2U);
        } else {
            const auto binding = std::find_if(
                subject.bindings.begin(), subject.bindings.end(), [&record](const auto& item) {
                    return item.opaque_target_id == record.target;
                });
            if (binding == subject.bindings.end()) {
                throw std::runtime_error("v3 formula binding");
            }
            target = v3_binding_address(suite, subject, *binding);
        }
        const std::uint32_t value = add_signed_address(target, record.addend);
        std::uint32_t expected = 0U;
        switch (record.patch) {
        case jfg::CustomOverlayRelocationPatch::full_word:
            expected = value;
            break;
        case jfg::CustomOverlayRelocationPatch::jump_target:
            if ((value & 3U) != 0U || (value & 0xf0000000U) !=
                ((module.base + record.site_offset + 4U) & 0xf0000000U)) {
                throw std::runtime_error("v3 jump formula");
            }
            expected = (original & 0xfc000000U) | ((value >> 2U) & 0x03ffffffU);
            break;
        case jfg::CustomOverlayRelocationPatch::hi16:
            // Keep this byte-for-byte identical to the relocation runtime.
            // Addition can carry into the preserved instruction bits when the
            // rounded high half is 0x10000.
            expected = (original & 0xffff0000U) | static_cast<std::uint32_t>(
                (static_cast<std::uint64_t>(value) + 0x8000ULL) >> 16U);
            break;
        case jfg::CustomOverlayRelocationPatch::lo16:
            expected = (original & 0xffff0000U) | (value & 0xffffU);
            break;
        }
        if (read_be32(after, record.site_offset) != expected) {
            throw std::runtime_error("v3 custom formula");
        }
    }
}

void validate_v3_r32_formulas(
    const V3SuiteCase& suite,
    const V3ModuleCase& source,
    const V3SubjectCase& subject,
    const std::span<const std::byte> relocated) {
    GeneratedAbiTable table;
    std::span<const std::uint32_t> sites;
    std::span<const GeneratedAbiTable::R32Descriptor> descriptors;
    if (!table.relocation_sites(source.slot, sites) ||
        !table.relocation_descriptors(source.slot, descriptors) ||
        sites.size() != descriptors.size() ||
        !std::ranges::equal(sites, subject.generated_r32_sites)) {
        throw std::runtime_error("v3 r32 closure");
    }
    for (std::size_t index = 0U; index < descriptors.size(); ++index) {
        const auto& descriptor = descriptors[index];
        if (descriptor.site_offset != sites[index]) {
            throw std::runtime_error("v3 r32 descriptor");
        }
        std::uint32_t base = 0U;
        std::uint64_t extent = 0U;
        const auto module = std::find_if(
            suite.modules.begin(), suite.modules.end(), [&descriptor](const auto& item) {
                return item.slot == descriptor.target_section;
            });
        if (module != suite.modules.end()) {
            const auto extents = v3_extents(*module);
            base = module->base;
            extent = static_cast<std::uint64_t>(extents.text_size) + extents.data_size +
                extents.bss_size;
        } else {
            JfgGeneratedSectionMetadata metadata{};
            if (jfg_generated_section_metadata(descriptor.target_section, &metadata) == 0 ||
                metadata.is_overlay != 0U) {
                throw std::runtime_error("v3 r32 target");
            }
            base = metadata.linked_vram;
            extent = static_cast<std::uint64_t>(metadata.text_size) + metadata.data_size +
                metadata.bss_size;
        }
        if (descriptor.target_offset >= extent ||
            read_be32(relocated, descriptor.site_offset) !=
                add_unsigned_address(base, descriptor.target_offset)) {
            throw std::runtime_error("v3 r32 formula");
        }
    }
}

struct V3RunSummary {
    std::string state_digest;
    std::size_t state_size = 0U;
    std::string copy_digest;
    std::size_t copy_size = 0U;
    std::string bss_digest;
    std::size_t bss_size = 0U;
    bool provider_rebound = false;
    // Class ordinals for every relocation validated during the initial load.
    // These are converted to per-record opaque IDs only when emitting the
    // public-safe observation; guest sites and module identities stay local.
    std::vector<std::uint8_t> relocation_classes;
};

void validate_v3_suite_geometry(const V3SuiteCase& suite) {
    const V3StaticMapping static_mapping = v3_static_mapping(suite);
    for (std::size_t index = 0U; index < suite.modules.size(); ++index) {
        const auto extents = v3_extents(suite.modules[index]);
        const std::uint64_t start = suite.modules[index].base -
            jfg::kGeneratedCachedGuestBase;
        const std::uint64_t end = start + extents.text_size + extents.data_size +
            extents.bss_size;
        if (end > suite.guest_size ||
            !(end <= static_mapping.begin || static_mapping.end <= start)) {
            throw std::runtime_error("v3 mapped geometry");
        }
        for (std::size_t other = 0U; other < index; ++other) {
            const auto other_extents = v3_extents(suite.modules[other]);
            const std::uint64_t other_start = suite.modules[other].base -
                jfg::kGeneratedCachedGuestBase;
            const std::uint64_t other_end = other_start + other_extents.text_size +
                other_extents.data_size + other_extents.bss_size;
            if (!(end <= other_start || other_end <= start)) {
                throw std::runtime_error("v3 mapped overlap");
            }
        }
    }
}

[[nodiscard]] GeneratedProbeScratch make_v3_probe_scratch(
    const V3SuiteCase& suite,
    const std::size_t execution_guest_size) {
    std::vector<std::pair<std::size_t, std::size_t>> occupied;
    occupied.reserve(suite.modules.size() + 1U);
    const V3StaticMapping static_mapping = v3_static_mapping(suite);
    occupied.emplace_back(static_mapping.begin, static_mapping.end);
    for (const V3ModuleCase& module : suite.modules) {
        const auto extents = v3_extents(module);
        const std::size_t begin = module.base - jfg::kGeneratedCachedGuestBase;
        occupied.emplace_back(
            begin,
            begin + extents.text_size + extents.data_size + extents.bss_size);
    }
    std::ranges::sort(occupied);
    std::size_t cursor = 0U;
    std::size_t selected_begin = 0U;
    bool selected = false;
    std::size_t selected_size = 0U;
    const auto consider_gap = [&](const std::size_t begin, const std::size_t end) {
        const std::size_t aligned_begin = (begin + 15U) & ~std::size_t{15U};
        const std::size_t aligned_end = end & ~std::size_t{15U};
        if (aligned_end >= aligned_begin &&
            aligned_end - aligned_begin >= kMinimumV3ProbeScratchBytes) {
            const std::size_t candidate_size =
                std::min(
                    aligned_end - aligned_begin,
                    kMaximumV3ProbeScratchBytes) &
                ~std::size_t{15U};
            const std::size_t candidate_begin = aligned_end - candidate_size;
            if (!selected || candidate_size >= selected_size) {
                selected_begin = candidate_begin;
                selected_size = candidate_size;
                selected = true;
            }
        }
    };
    for (const auto& [begin, end] : occupied) {
        consider_gap(cursor, begin);
        cursor = std::max(cursor, end);
    }
    consider_gap(cursor, execution_guest_size);
    if (!selected || selected_begin > execution_guest_size ||
        execution_guest_size - selected_begin < selected_size) {
        return {};
    }
    // Generated callees may use both the current function's downward-growing
    // frame and the caller argument area above the incoming stack pointer.
    // Center the seed so neither direction can escape the isolated scratch
    // merely because adjacent host heap storage happens to be mapped.
    const std::size_t stack_offset =
        (selected_begin + selected_size / 2U) & ~std::size_t{15U};
    std::uint32_t stack_address = 0U;
    if (stack_offset < selected_begin + kV3ProbeStackGuardBytes ||
        selected_begin + selected_size - stack_offset <
            kV3ProbeStackGuardBytes ||
        stack_offset > std::numeric_limits<std::uint32_t>::max() ||
        !jfg::try_add_generated_guest_address(
            jfg::kGeneratedCachedGuestBase,
            static_cast<std::uint32_t>(stack_offset),
            stack_address)) {
        return {};
    }
    return {
        selected_begin,
        selected_size,
        static_cast<gpr>(static_cast<std::int64_t>(
            static_cast<std::int32_t>(stack_address))),
    };
}

[[nodiscard]] V3RunSummary execute_v3_subject(
    const V3SuiteCase& suite,
    const V3SubjectCase& subject,
    GeneratedProbeBudget& probe_budget) {
    const V3ModuleCase& source = v3_module(suite, subject.slot);
    V3GuestMemory guest_memory;
    const std::span<std::byte> guest = guest_memory.bytes();
    initialize_v3_static_memory(suite, guest);
    const GeneratedProbeScratch probe_scratch =
        make_v3_probe_scratch(suite, guest.size());
    if (!probe_scratch.valid()) {
        throw std::runtime_error("v3 probe scratch");
    }
    jfg::GeneratedOverlayRuntime runtime(guest);
    // Initialize the generated ABI's minimal dispatch state before the
    // overlay table installs its own checked section-address storage.  A
    // generated body may call get_function() in the child; it must route
    // through the runtime lifetime gate rather than reinitialize the table.
    if (jfg_minimal_runtime_initialize() == 0 ||
        !runtime.install_table(std::make_unique<GeneratedAbiTable>()).ok()) {
        throw std::runtime_error("v3 table");
    }
    const auto source_extents = v3_extents(source);
    const std::size_t source_offset = source.base - jfg::kGeneratedCachedGuestBase;
    if (source_offset + source.initialized.size() + source_extents.bss_size > guest.size()) {
        throw std::runtime_error("v3 mapped geometry");
    }
    EvidenceCache cache;
    cache.runtime = &runtime;
    const auto require_unload = [&runtime, &cache](
                                    const jfg::GeneratedOverlayToken token,
                                    const char* const failure) {
        cache.prepared = false;
        cache.committed = false;
        cache.reentry = jfg::GeneratedOverlayError::none;
        if (runtime.unload(token, cache) != jfg::GeneratedOverlayError::none ||
            !cache.prepared || !cache.committed ||
            cache.reentry != jfg::GeneratedOverlayError::busy) {
            throw std::runtime_error(failure);
        }
    };
    struct Loaded { std::uint32_t slot; jfg::GeneratedOverlayToken token; };
    std::vector<Loaded> loaded;
    struct SelectedSlot {
        std::uint32_t slot = 0U;
        SelectedGeneratedFunction selected;
    };
    std::vector<SelectedSlot> selected_functions;
    const auto required_for = [&suite](const V3SubjectCase& current) {
        std::vector<std::uint32_t> result;
        const auto add = [&result, &current](const std::uint32_t slot) {
            if (slot != current.slot &&
                std::ranges::find(result, slot) == result.end()) {
                result.push_back(slot);
            }
        };
        for (const V3BindingCase& binding : current.bindings) {
            if (binding.kind == 2U) {
                add(binding.provider_slot);
            }
        }
        GeneratedAbiTable table;
        std::span<const GeneratedAbiTable::R32Descriptor> descriptors;
        if (!table.relocation_descriptors(current.slot, descriptors)) {
            throw std::runtime_error("v3 planned r32");
        }
        for (const auto& descriptor : descriptors) {
            const auto target = std::find_if(
                suite.modules.begin(), suite.modules.end(), [&descriptor](const auto& item) {
                    return item.slot == descriptor.target_section;
                });
            if (target != suite.modules.end()) {
                add(target->slot);
            }
        }
        return result;
    };
    const std::vector<std::uint32_t> required_slots = required_for(subject);
    std::vector<std::uint32_t> visiting;
    std::vector<std::uint32_t> load_order;
    const auto visit = [&suite, &required_for, &visiting, &load_order](
                           const auto& self, const std::uint32_t slot) -> void {
        if (std::ranges::find(load_order, slot) != load_order.end()) {
            return;
        }
        if (std::ranges::find(visiting, slot) != visiting.end()) {
            throw std::runtime_error("v3 dependency cycle");
        }
        visiting.push_back(slot);
        for (const std::uint32_t provider : required_for(v3_subject(suite, slot))) {
            self(self, provider);
        }
        visiting.pop_back();
        load_order.push_back(slot);
    };
    visit(visit, source.slot);

    const auto dependency_reference = [](const std::uint32_t owner_slot,
                                         const std::uint32_t provider_slot) {
        return (static_cast<std::uint64_t>(owner_slot) + 1U) << 32U |
            (static_cast<std::uint64_t>(provider_slot) + 1U);
    };

    jfg::GeneratedOverlayToken active_token;
    for (const std::uint32_t slot : load_order) {
        const V3ModuleCase& module = v3_module(suite, slot);
        const V3SubjectCase& current = v3_subject(suite, slot);
        (void)v3_extents(module);
        std::vector<jfg::GeneratedOverlayCustomBinding> bindings;
        bindings.reserve(current.bindings.size());
        for (const V3BindingCase& binding : current.bindings) {
            jfg::GeneratedOverlayCustomBinding item{};
            item.opaque_target_id = binding.opaque_target_id;
            item.target_offset = binding.target_offset;
            if (binding.kind == 0U) {
                item.static_section_index = 0U;
            } else if (binding.kind == 1U) {
                item.target_module_id = module.opaque_module_id;
                item.static_section_index = jfg::kNoGeneratedStaticSection;
            } else {
                item.target_module_id =
                    v3_module(suite, binding.provider_slot).opaque_module_id;
                item.static_section_index = jfg::kNoGeneratedStaticSection;
            }
            bindings.push_back(item);
        }
        std::vector<jfg::GeneratedOverlayDependency> dependencies;
        for (const std::uint32_t provider_slot : required_for(current)) {
            const auto selected_provider = std::find_if(
                selected_functions.begin(), selected_functions.end(),
                [provider_slot](const SelectedSlot& item) {
                    return item.slot == provider_slot;
                });
            if (selected_provider == selected_functions.end()) {
                throw std::runtime_error("v3 provider function ordering");
            }
            dependencies.push_back({
                dependency_reference(module.slot, provider_slot),
                v3_module(suite, provider_slot).opaque_module_id,
                selected_provider->selected.offset,
            });
        }
        cache.prepared = false;
        cache.committed = false;
        cache.reentry = jfg::GeneratedOverlayError::none;
        const auto loaded_module = runtime.load({module.opaque_module_id, module.slot,
            module.initialized, std::move(dependencies),
            current.custom_relocations, bindings},
            module.base, cache);
        if (!loaded_module.ok() || !cache.prepared || !cache.committed ||
            cache.reentry != jfg::GeneratedOverlayError::busy) {
            throw std::runtime_error("v3 provider load");
        }
        loaded.push_back({module.slot, loaded_module.token});
        selected_functions.push_back({
            module.slot,
            resolve_reviewed_generated_function(
                runtime, loaded_module.token, module, guest,
                suite.token, probe_scratch, probe_budget),
        });
        if (slot == source.slot) {
            active_token = loaded_module.token;
        }
    }
    const auto selected_source = std::find_if(
        selected_functions.begin(), selected_functions.end(),
        [&source](const SelectedSlot& item) { return item.slot == source.slot; });
    if (!active_token.valid() || selected_source == selected_functions.end()) {
        throw std::runtime_error("v3 subject load");
    }
    const auto live = std::span<const std::byte>(guest).subspan(
        source_offset, source.initialized.size() + source_extents.bss_size);
    validate_v3_custom_formulas(suite, subject, source, source.initialized,
        live.first(source.initialized.size()));
    validate_v3_r32_formulas(suite, source, subject,
        live.first(source.initialized.size()));
    const auto bss = live.subspan(source.initialized.size(), source_extents.bss_size);
    if (!bss.empty() && !std::ranges::all_of(bss, [](const std::byte value) {
            return value == std::byte{0};
        })) {
        throw std::runtime_error("v3 bss");
    }
    require_generated_handle_invocation(
        runtime, selected_source->selected.function, guest, suite.token,
        selected_source->selected.seed, probe_scratch, probe_budget);
    struct DependencyCapability {
        std::uint32_t provider_slot = 0U;
        std::uint64_t reference = 0U;
        jfg::GeneratedOverlayFunctionHandle function;
        GeneratedContextSeed seed = GeneratedContextSeed::zero;
    };
    std::vector<DependencyCapability> capabilities;
    capabilities.reserve(required_slots.size());
    for (const std::uint32_t provider_slot : required_slots) {
        const std::uint64_t reference = dependency_reference(
            source.slot, provider_slot);
        const auto resolved = runtime.resolve_dependency(active_token, reference);
        if (!resolved.ok()) {
            throw std::runtime_error("v3 dependency capability");
        }
        const auto selected_provider = std::find_if(
            selected_functions.begin(), selected_functions.end(),
            [provider_slot](const SelectedSlot& item) {
                return item.slot == provider_slot;
            });
        if (selected_provider == selected_functions.end()) {
            throw std::runtime_error("v3 dependency seed");
        }
        require_generated_handle_invocation(
            runtime, resolved.function, guest, suite.token,
            selected_provider->selected.seed, probe_scratch, probe_budget);
        capabilities.push_back({provider_slot, reference, resolved.function,
            selected_provider->selected.seed});
    }
    std::uint32_t copy_offset = 0U;
    bool found_copy = false;
    for (std::uint32_t candidate = 0U;
         static_cast<std::uint64_t>(candidate) + 4U <= source.initialized.size();
         candidate += 4U) {
        const bool custom = std::any_of(
            subject.custom_relocations.begin(), subject.custom_relocations.end(),
            [candidate](const auto& record) { return record.site_offset == candidate; });
        const bool r32 = std::binary_search(
            subject.generated_r32_sites.begin(), subject.generated_r32_sites.end(), candidate);
        if (!custom && !r32) {
            copy_offset = candidate;
            found_copy = true;
            break;
        }
    }
    if (found_copy && !std::ranges::equal(
            std::span(source.initialized).subspan(copy_offset, 4U),
            live.subspan(copy_offset, 4U))) {
        throw std::runtime_error("v3 copy");
    }
    std::vector<std::uint8_t> relocation_classes;
    relocation_classes.reserve(subject.custom_relocations.size() +
        subject.generated_r32_sites.size());
    for (const auto& record : subject.custom_relocations) {
        switch (record.patch) {
        case jfg::CustomOverlayRelocationPatch::full_word:
            relocation_classes.push_back(0U);
            break;
        case jfg::CustomOverlayRelocationPatch::jump_target:
            relocation_classes.push_back(1U);
            break;
        case jfg::CustomOverlayRelocationPatch::hi16:
            relocation_classes.push_back(2U);
            break;
        case jfg::CustomOverlayRelocationPatch::lo16:
            relocation_classes.push_back(3U);
            break;
        }
    }
    // R_MIPS_32 writes an entire word.  The table and descriptor checks above
    // bind each of these opaque entries to the generated relocation ABI.
    relocation_classes.insert(
        relocation_classes.end(), subject.generated_r32_sites.size(), 0U);
    V3RunSummary summary{hex_digest(live), live.size(),
        found_copy ? hex_digest(live.subspan(copy_offset, 4U)) : std::string{},
        found_copy ? 4U : 0U, hex_digest(bss), bss.size(), false,
        std::move(relocation_classes)};
    const std::vector<std::byte> first_state(live.begin(), live.end());
    // required_slots is the unique union of custom-binding providers and
    // generated-R32 overlay targets. Exercise invalidation/rebind for both;
    // data/BSS R32 targets are lifecycle dependencies even though they are not
    // function bindings.
    for (const std::uint32_t provider_slot : required_slots) {
        const auto token = std::find_if(loaded.begin(), loaded.end(),
            [provider_slot](const Loaded& item) { return item.slot == provider_slot; });
        if (token == loaded.end()) {
            throw std::runtime_error("v3 provider invalidation");
        }
        auto capability = std::find_if(
            capabilities.begin(), capabilities.end(),
            [provider_slot](const DependencyCapability& item) {
                return item.provider_slot == provider_slot;
            });
        if (capability == capabilities.end()) {
            throw std::runtime_error("v3 dependency capability");
        }
        require_unload(token->token, "v3 provider invalidation");
        recomp_context stale_context{};
        if (capability->function.valid() ||
            capability->function.invoke(
                reinterpret_cast<std::uint8_t*>(guest.data()),
                &stale_context) != jfg::GeneratedOverlayError::stale_token ||
            runtime.lookup_function(
                active_token, selected_source->selected.offset).error !=
                jfg::GeneratedOverlayError::dependency_invalidated) {
            throw std::runtime_error("v3 provider invalidation");
        }
        cache.prepared = false;
        cache.committed = false;
        cache.reentry = jfg::GeneratedOverlayError::none;
        const auto rebound = runtime.reload_same_base(token->token, cache);
        if (!rebound.ok() || !cache.prepared || !cache.committed ||
            cache.reentry != jfg::GeneratedOverlayError::busy ||
            !runtime.lookup_function(
                active_token, selected_source->selected.offset).ok()) {
            throw std::runtime_error("v3 provider rebind");
        }
        token->token = rebound.token;
        const auto rebound_capability = runtime.resolve_dependency(
            active_token, capability->reference);
        if (!rebound_capability.ok()) {
            throw std::runtime_error("v3 dependency rebind");
        }
        require_generated_handle_invocation(
            runtime, rebound_capability.function, guest, suite.token,
            capability->seed, probe_scratch, probe_budget);
        capability->function = rebound_capability.function;
        // Rebinding is only a proof if the dependent guest bytes still meet
        // both the custom and generated-table formulas afterwards.
        const auto rebound_live = std::span<const std::byte>(guest).subspan(
            source_offset, source.initialized.size() + source_extents.bss_size);
        validate_v3_custom_formulas(suite, subject, source, source.initialized,
            rebound_live.first(source.initialized.size()));
        validate_v3_r32_formulas(suite, source, subject,
            rebound_live.first(source.initialized.size()));
        summary.provider_rebound = true;
    }

    // Exercise every source-lifetime event that the observation reports.  A
    // successful same-base reload must reproduce the exact mapped state, make
    // the prior capability stale, and survive the same formula checks.  A
    // throwing cache callback must then leave both publication and guest bytes
    // rolled back.
    require_unload(active_token, "v3 subject unload");
    recomp_context stale_owner_context{};
    for (const DependencyCapability& capability : capabilities) {
        if (capability.function.valid() ||
            capability.function.invoke(
                reinterpret_cast<std::uint8_t*>(guest.data()),
                &stale_owner_context) != jfg::GeneratedOverlayError::stale_token) {
            throw std::runtime_error("v3 subject capability invalidation");
        }
    }
    cache.prepared = false;
    cache.committed = false;
    cache.reentry = jfg::GeneratedOverlayError::none;
    const auto second = runtime.reload_same_base(active_token, cache);
    if (!second.ok() || !cache.prepared || !cache.committed ||
        cache.reentry != jfg::GeneratedOverlayError::busy ||
        runtime.lookup_function(
            active_token, selected_source->selected.offset).error !=
            jfg::GeneratedOverlayError::stale_token ||
        !runtime.lookup_function(
            second.token, selected_source->selected.offset).ok()) {
        throw std::runtime_error("v3 subject reload");
    }
    for (const DependencyCapability& capability : capabilities) {
        const auto reloaded_capability = runtime.resolve_dependency(
            second.token, capability.reference);
        if (!reloaded_capability.ok()) {
            throw std::runtime_error("v3 subject capability reload");
        }
        require_generated_handle_invocation(
            runtime, reloaded_capability.function, guest, suite.token,
            capability.seed, probe_scratch, probe_budget);
    }
    const auto reloaded_source = runtime.lookup_function(
        second.token, selected_source->selected.offset);
    if (!reloaded_source.ok()) {
        throw std::runtime_error("v3 subject function reload");
    }
    require_generated_handle_invocation(
        runtime, reloaded_source.function, guest, suite.token,
        selected_source->selected.seed, probe_scratch, probe_budget);
    const auto second_live = std::span<const std::byte>(guest).subspan(
        source_offset, source.initialized.size() + source_extents.bss_size);
    if (!std::ranges::equal(first_state, second_live)) {
        throw std::runtime_error("v3 reload state");
    }
    validate_v3_custom_formulas(suite, subject, source, source.initialized,
        second_live.first(source.initialized.size()));
    validate_v3_r32_formulas(suite, source, subject,
        second_live.first(source.initialized.size()));

    require_unload(second.token, "v3 subject final unload");
    const std::vector<std::byte> before_failure(guest.begin(), guest.end());
    EvidenceCache failing_cache;
    failing_cache.runtime = &runtime;
    failing_cache.throw_from_prepare = true;
    const auto failed = runtime.reload_same_base(second.token, failing_cache);
    if (failed.error != jfg::GeneratedOverlayError::callback_exception ||
        !std::ranges::equal(guest, before_failure) ||
        runtime.lookup_function_by_guest_address(source.base).error !=
            jfg::GeneratedOverlayError::function_not_found) {
        throw std::runtime_error("v3 callback rollback");
    }

    // Providers were loaded in topological order.  Tear them down in reverse
    // order after the source is inactive so no dependent remains published.
    for (auto item = loaded.rbegin(); item != loaded.rend(); ++item) {
        if (item->slot == source.slot) {
            continue;
        }
        require_unload(item->token, "v3 provider final unload");
    }
    return summary;
}

[[nodiscard]] std::string integer(const std::uint64_t value) {
    std::array<char, 24> buffer{};
    const auto converted = std::to_chars(buffer.data(), buffer.data() + buffer.size(), value);
    if (converted.ec != std::errc{}) {
        throw std::runtime_error("integer encoding");
    }
    return {buffer.data(), converted.ptr};
}

void append_event(
    std::string& output,
    const std::size_t sequence,
    const std::string_view kind,
    const std::size_t generation) {
    if (sequence != 1U) {
        output += ',';
    }
    output += "{\"generation\":" + integer(generation) +
        ",\"kind\":\"" + std::string(kind) + "\",\"sequence\":" +
        integer(sequence) + '}';
}

[[nodiscard]] std::string produce_v3_observation(
    const V3SuiteCase& suite,
    const std::span<const std::byte> case_bytes,
    const std::string_view nonce,
    const std::string_view trusted_case_id,
    const std::string_view trusted_subject_digest) {
    const std::string case_digest = hex_digest(case_bytes);
    const std::string derived_case_id = "g2-custom-" + case_digest.substr(0U, 16U);
    if (!is_identifier(trusted_case_id) || trusted_case_id != derived_case_id ||
        !is_digest(trusted_subject_digest) || case_digest != trusted_subject_digest) {
        throw std::runtime_error("v3 trusted identity");
    }
    validate_v3_suite_geometry(suite);
    std::vector<V3RunSummary> summaries;
    summaries.reserve(suite.subjects.size());
    bool provider_rebound = false;
    GeneratedProbeBudget probe_budget;
    for (const auto& subject : suite.subjects) {
        summaries.push_back(execute_v3_subject(suite, subject, probe_budget));
        provider_rebound = provider_rebound || summaries.back().provider_rebound;
    }
    if (!provider_rebound || summaries.empty()) {
        throw std::runtime_error("v3 lifecycle closure");
    }
    std::string events;
    static constexpr std::array<std::string_view, 17> event_names{
        "load-begin", "copy-complete", "bss-cleared", "relocation-applied",
        "cache-invalidated", "module-published", "callback-enter",
        "callback-reentry-rejected", "callback-complete", "lookup", "unpublish",
        "dependency-invalidated", "unload-complete", "dependency-rebound",
        "stale-token-rejected", "reload-verified", "callback-failure-rolled-back"};
    for (std::size_t index = 0U; index < event_names.size(); ++index) {
        append_event(events, index + 1U, event_names[index],
            index < 13U ? 1U : (index < 16U ? 2U : 3U));
    }
    // Emit one opaque entry for every relocation validated on initial load.
    // The ordinal is deliberately local to this bounded execution; it cannot
    // disclose guest sites, module slots, addresses, or generated names.
    std::vector<std::uint8_t> relocation_classes;
    for (const V3RunSummary& summary : summaries) {
        relocation_classes.insert(relocation_classes.end(),
            summary.relocation_classes.begin(), summary.relocation_classes.end());
    }
    if (relocation_classes.empty()) {
        throw std::runtime_error("v3 relocation inventory");
    }
    std::string relocations;
    static constexpr std::array<std::string_view, 4U> relocation_names{
        "full-word", "jump-target", "hi16", "lo16"};
    for (std::size_t index = 0U; index < relocation_classes.size(); ++index) {
        if (relocation_classes[index] >= relocation_names.size()) {
            throw std::runtime_error("v3 relocation class");
        }
        if (index != 0U) {
            relocations += ',';
        }
        relocations += "{\"class\":\"" +
            std::string(relocation_names[relocation_classes[index]]) +
            "\",\"generation\":1,\"site_id\":\"relocation-" +
            integer(index + 1U) + "\",\"write_count\":1}";
    }
    const V3RunSummary& sample = summaries.front();
    const auto copy_sample = std::ranges::find_if(
        summaries, [](const V3RunSummary& item) { return item.copy_size != 0U; });
    const auto bss_sample = std::ranges::find_if(
        summaries, [](const V3RunSummary& item) { return item.bss_size != 0U; });
    if (copy_sample == summaries.end() || bss_sample == summaries.end()) {
        throw std::runtime_error("v3 memory coverage");
    }
    const std::string observation =
        "{\"case_id\":\"" + std::string(trusted_case_id) +
        "\",\"events\":[" + events +
        "],\"kind\":\"jfg-g2-overlay-lifecycle-observation\",\"lifetimes\":[" +
        "{\"generation\":1,\"mapping_sha256\":\"" + hex_digest(case_bytes) +
        "\",\"state_sha256\":\"" + sample.state_digest + "\"}," +
        "{\"generation\":2,\"mapping_sha256\":\"" + hex_digest(case_bytes) +
        "\",\"state_sha256\":\"" + sample.state_digest + "\"}],\"memory_checks\":[" +
        "{\"byte_count\":" + integer(copy_sample->copy_size) +
        ",\"expected_sha256\":\"" + copy_sample->copy_digest +
        "\",\"observed_sha256\":\"" + copy_sample->copy_digest +
        "\",\"phase\":\"copy\",\"zero_byte_count\":0}," +
        "{\"byte_count\":" + integer(bss_sample->bss_size) +
        ",\"expected_sha256\":\"" + bss_sample->bss_digest +
        "\",\"observed_sha256\":\"" + bss_sample->bss_digest +
        "\",\"phase\":\"bss-clear\",\"zero_byte_count\":" +
        integer(bss_sample->bss_size) + "}," +
        "{\"byte_count\":" + integer(sample.state_size) +
        ",\"expected_sha256\":\"" + sample.state_digest +
        "\",\"observed_sha256\":\"" + sample.state_digest +
        "\",\"phase\":\"reload\",\"zero_byte_count\":0}],\"relocations\":[" +
        relocations + "],\"schema_version\":1,\"subject_sha256\":\"" +
        std::string(trusted_subject_digest) + "\"}";
    return "{\"execution_nonce\":\"" + std::string(nonce) +
        "\",\"observation\":" + observation + '}';
}

[[nodiscard]] std::string relocation_class(const std::uint8_t kind) {
    static constexpr std::array<std::string_view, 4> names{
        "full-word", "jump-target", "hi16", "lo16"};
    return std::string(names.at(kind));
}

[[nodiscard]] std::string produce_observation(
    const OverlayCase& input,
    const std::span<const std::byte> case_bytes,
    const std::string_view nonce,
    const std::string_view trusted_case_id,
    const std::string_view trusted_subject_digest) {
    if (!is_identifier(trusted_case_id) ||
        trusted_case_id != input.case_identifier ||
        !is_digest(trusted_subject_digest) ||
        hex_digest(case_bytes) != trusted_subject_digest) {
        throw std::runtime_error("trusted identity");
    }
    std::vector<std::byte> guest(input.guest_size, std::byte{0xa5});
    jfg::GeneratedOverlayRuntime runtime(guest);
    if (!runtime.install_table(std::make_unique<GeneratedAbiTable>()).ok()) {
        throw std::runtime_error("table install");
    }

    JfgGeneratedSectionMetadata target_raw{};
    JfgGeneratedSectionMetadata dependent_raw{};
    if (jfg_generated_section_metadata(input.target.section, &target_raw) == 0 ||
        jfg_generated_section_metadata(input.dependent.section, &dependent_raw) == 0) {
        throw std::runtime_error("metadata");
    }
    const jfg::GeneratedSectionExtents target_extents{
        target_raw.text_size,
        target_raw.data_size,
        target_raw.bss_size,
        target_raw.is_overlay == 1U,
    };
    const jfg::GeneratedSectionExtents dependent_extents{
        dependent_raw.text_size,
        dependent_raw.data_size,
        dependent_raw.bss_size,
        dependent_raw.is_overlay == 1U,
    };
    const std::size_t target_offset =
        checked_offset(input.target, target_extents, guest.size());
    const std::size_t dependent_offset =
        checked_offset(input.dependent, dependent_extents, guest.size());
    (void)target_offset;
    const std::size_t primary_initialized = input.dependent.initialized.size();
    const std::size_t primary_extent =
        primary_initialized + dependent_extents.bss_size;
    std::uint32_t copy_offset = input.copy_offset;
    std::uint32_t copy_size = input.copy_size;
    std::span<const GeneratedAbiTable::R32Descriptor> generated_descriptors;
    // The descriptor span is backed by GeneratedAbiTable storage.  Retain the
    // table through the later post-load formula check; a block-local table
    // here would leave a dangling span and could turn a valid case into an
    // arbitrary accept/reject decision.
    GeneratedAbiTable generated_inventory_table;
    if (input.is_custom_v2) {
        // The input does not name generated R32 relocation classes.  Compare
        // its complete, sorted site inventory to the generated table itself.
        std::span<const std::uint32_t> generated_sites;
        if (!generated_inventory_table.relocation_sites(input.dependent.section, generated_sites) ||
            !generated_inventory_table.relocation_descriptors(
                input.dependent.section, generated_descriptors) ||
            generated_sites.size() != generated_descriptors.size() ||
            !std::ranges::equal(generated_sites, input.generated_r32_sites)) {
            throw std::runtime_error("r32 table closure");
        }
        for (std::size_t index = 0U; index < generated_sites.size(); ++index) {
            if (generated_descriptors[index].site_offset != generated_sites[index]) {
                throw std::runtime_error("r32 descriptor closure");
            }
        }
        // V2 derives this public-safe check from untouched initialized bytes,
        // never from a caller-provided expected relocation result.
        bool found_copy = false;
        for (std::uint32_t candidate = 0U;
             static_cast<std::uint64_t>(candidate) + 4U <= primary_initialized;
             candidate += 4U) {
            const bool overlaps_custom = std::any_of(
                input.custom_relocations.begin(), input.custom_relocations.end(),
                [candidate](const jfg::CustomOverlayRelocationRecord& record) {
                    return record.site_offset == candidate;
                });
            const bool overlaps_r32 = std::binary_search(
                input.generated_r32_sites.begin(), input.generated_r32_sites.end(),
                candidate);
            if (!overlaps_custom && !overlaps_r32) {
                copy_offset = candidate;
                copy_size = 4U;
                found_copy = true;
                break;
            }
        }
        if (!found_copy) {
            throw std::runtime_error("v2 copy coverage");
        }
    }
    if (copy_size == 0U ||
        static_cast<std::uint64_t>(copy_offset) + copy_size > primary_initialized ||
        (!input.is_custom_v2 &&
         jfg_generated_relocation_count(input.dependent.section) <
             input.relocation_probes.size())) {
        throw std::runtime_error("case coverage");
    }

    std::array<bool, 4> classes{};
    std::vector<std::uint32_t> sites;
    sites.reserve(input.relocation_probes.size());
    for (const RelocationProbe& probe : input.relocation_probes) {
        if ((probe.offset & 3U) != 0U ||
            static_cast<std::uint64_t>(probe.offset) + 4U > primary_initialized ||
            !(static_cast<std::uint64_t>(probe.offset) + 4U <= copy_offset ||
              probe.offset >=
                  static_cast<std::uint64_t>(copy_offset) + copy_size)) {
            throw std::runtime_error("relocation coverage");
        }
        classes.at(probe.kind) = true;
        sites.push_back(probe.offset);
    }
    std::ranges::sort(sites);
    if (!std::ranges::all_of(classes, [](const bool value) { return value; }) ||
        std::adjacent_find(sites.begin(), sites.end()) != sites.end()) {
        throw std::runtime_error("relocation classes");
    }

    EvidenceCache cache;
    cache.runtime = &runtime;
    const auto require_unload = [&runtime, &cache](
                                    const jfg::GeneratedOverlayToken token,
                                    const char* const failure) {
        cache.prepared = false;
        cache.committed = false;
        cache.reentry = jfg::GeneratedOverlayError::none;
        if (runtime.unload(token, cache) != jfg::GeneratedOverlayError::none ||
            !cache.prepared || !cache.committed ||
            cache.reentry != jfg::GeneratedOverlayError::busy) {
            throw std::runtime_error(failure);
        }
    };
    const jfg::GeneratedOverlayImage target_image{
        input.target.module_id,
        input.target.section,
        input.target.initialized,
        {},
        {},
        {},
    };
    const auto provider = runtime.load(target_image, input.target.base, cache);
    const auto provider_function = runtime.lookup_function(
        provider.token, input.target.function_offset);
    if (!provider.ok() || !provider_function.ok() || !cache.prepared ||
        !cache.committed ||
        cache.reentry != jfg::GeneratedOverlayError::busy) {
        throw std::runtime_error("provider load");
    }

    std::vector<jfg::GeneratedOverlayCustomBinding> custom_bindings;
    if (input.is_custom_v2) {
        custom_bindings.reserve(input.custom_bindings.size());
        for (const CustomBindingCase& binding : input.custom_bindings) {
            jfg::GeneratedOverlayCustomBinding runtime_binding{};
            runtime_binding.opaque_target_id = binding.opaque_target_id;
            runtime_binding.target_offset = binding.target_offset;
            switch (binding.target_kind) {
            case 0U:
                runtime_binding.target_module_id = 0U;
                runtime_binding.static_section_index = 0U;
                break;
            case 1U:
                runtime_binding.target_module_id = input.dependent.module_id;
                runtime_binding.static_section_index = jfg::kNoGeneratedStaticSection;
                break;
            case 2U:
                runtime_binding.target_module_id = input.target.module_id;
                runtime_binding.static_section_index = jfg::kNoGeneratedStaticSection;
                break;
            default:
                throw std::runtime_error("binding kind");
            }
            custom_bindings.push_back(runtime_binding);
        }
    }

    const jfg::GeneratedOverlayImage dependent_image{
        input.dependent.module_id,
        input.dependent.section,
        input.dependent.initialized,
        {{input.reference_id, input.target.module_id, input.target.function_offset}},
        input.custom_relocations,
        std::move(custom_bindings),
    };
    cache.prepared = false;
    cache.committed = false;
    const auto first = runtime.load(dependent_image, input.dependent.base, cache);
    const auto initially_resolved = runtime.resolve_dependency(
        first.token, input.reference_id);
    if (!first.ok() || !initially_resolved.ok() || !cache.prepared ||
        !cache.committed ||
        initially_resolved.function == provider_function.function) {
        throw std::runtime_error("primary dependency load");
    }
    const auto first_live = std::span<const std::byte>(guest).subspan(
        dependent_offset, primary_extent);
    if (input.is_custom_v2) {
        validate_custom_formulas(
            input, input.dependent.initialized,
            first_live.first(primary_initialized));
        // The table—not the packed case—provided these sites.  The checked
        // relocation ABI emits guest-endian words, so host-endian memcpy
        // results are rejected even though no caller labels are accepted.
        validate_generated_r32_formulas(
            input, target_extents, dependent_extents, generated_descriptors,
            first_live.first(primary_initialized));
    }
    for (const RelocationProbe& probe : input.relocation_probes) {
        const auto before =
            std::span(input.dependent.initialized).subspan(probe.offset, 4U);
        const auto after = first_live.subspan(probe.offset, 4U);
        if (std::ranges::equal(before, after)) {
            throw std::runtime_error("relocation not observed");
        }
    }
    const auto expected_copy = std::span(input.dependent.initialized).subspan(
        copy_offset, copy_size);
    const auto observed_copy = first_live.subspan(copy_offset, copy_size);
    if (!std::ranges::equal(expected_copy, observed_copy)) {
        throw std::runtime_error("copy mismatch");
    }
    const std::string copy_observed_digest = hex_digest(observed_copy);
    const auto bss = first_live.subspan(
        primary_initialized, dependent_extents.bss_size);
    if (bss.empty() || !std::ranges::all_of(
            bss, [](const std::byte value) { return value == std::byte{0}; })) {
        throw std::runtime_error("bss mismatch");
    }
    const std::string bss_digest = hex_digest(bss);
    const auto direct = runtime.lookup_function(
        first.token, input.dependent.function_offset);
    const auto absolute = runtime.lookup_function_by_guest_address(
        input.dependent.base + input.dependent.function_offset);
    if (!direct.ok() || !absolute.ok() || direct.function != absolute.function) {
        throw std::runtime_error("primary lookup");
    }

    const std::vector<std::byte> first_state(first_live.begin(), first_live.end());
    std::array<std::byte, 24> mapping_material{};
    auto put_u32 = [&mapping_material](const std::size_t at, const std::uint32_t value) {
        for (std::size_t index = 0U; index < 4U; ++index) {
            mapping_material[at + index] = static_cast<std::byte>(
                value >> static_cast<unsigned>(index * 8U));
        }
    };
    put_u32(0U, input.dependent.section);
    put_u32(4U, input.dependent.base);
    put_u32(8U, dependent_extents.text_size);
    put_u32(12U, dependent_extents.data_size);
    put_u32(16U, dependent_extents.bss_size);
    put_u32(20U, static_cast<std::uint32_t>(primary_extent));
    const std::string mapping_digest = hex_digest(mapping_material);
    const std::string first_state_digest = hex_digest(first_state);

    require_unload(provider.token, "dependency invalidation");
    if (runtime.resolve_dependency(first.token, input.reference_id).error !=
            jfg::GeneratedOverlayError::dependency_invalidated ||
        runtime.lookup_function(first.token, input.dependent.function_offset).error !=
            jfg::GeneratedOverlayError::dependency_invalidated) {
        throw std::runtime_error("dependency invalidation");
    }
    cache.prepared = false;
    cache.committed = false;
    const auto provider_reloaded = runtime.reload_same_base(provider.token, cache);
    if (!provider_reloaded.ok() || !cache.prepared || !cache.committed) {
        throw std::runtime_error("provider reload");
    }
    const auto rebound = runtime.resolve_dependency(first.token, input.reference_id);
    if (!rebound.ok() ||
        !runtime.lookup_function(first.token, input.dependent.function_offset).ok()) {
        throw std::runtime_error("dependency rebind");
    }

    require_unload(first.token, "primary unload");
    cache.prepared = false;
    cache.committed = false;
    const auto second = runtime.reload_same_base(first.token, cache);
    if (!second.ok() || !cache.prepared || !cache.committed ||
        runtime.lookup_function(first.token, input.dependent.function_offset).error !=
            jfg::GeneratedOverlayError::stale_token ||
        !runtime.resolve_dependency(second.token, input.reference_id).ok()) {
        throw std::runtime_error("primary reload");
    }
    const auto second_live = std::span<const std::byte>(guest).subspan(
        dependent_offset, primary_extent);
    if (!std::ranges::equal(first_state, second_live)) {
        throw std::runtime_error("reload state");
    }
    const std::string second_state_digest = hex_digest(second_live);
    const std::string reload_digest = hex_digest(second_live);

    require_unload(second.token, "primary final unload");
    const std::vector<std::byte> before_failure(guest.begin(), guest.end());
    EvidenceCache failing_cache;
    failing_cache.runtime = &runtime;
    failing_cache.throw_from_prepare = true;
    const auto failed = runtime.reload_same_base(second.token, failing_cache);
    if (failed.error != jfg::GeneratedOverlayError::callback_exception ||
        guest != before_failure ||
        runtime.lookup_function_by_guest_address(input.dependent.base).error !=
            jfg::GeneratedOverlayError::function_not_found) {
        throw std::runtime_error("callback rollback");
    }
    require_unload(provider_reloaded.token, "provider final unload");

    std::string events;
    static constexpr std::array<std::string_view, 17> event_names{
        "load-begin",
        "copy-complete",
        "bss-cleared",
        "relocation-applied",
        "cache-invalidated",
        "module-published",
        "callback-enter",
        "callback-reentry-rejected",
        "callback-complete",
        "lookup",
        "unpublish",
        "dependency-invalidated",
        "unload-complete",
        "dependency-rebound",
        "stale-token-rejected",
        "reload-verified",
        "callback-failure-rolled-back",
    };
    for (std::size_t index = 0U; index < event_names.size(); ++index) {
        const std::size_t generation = index < 13U ? 1U : (index < 16U ? 2U : 3U);
        append_event(events, index + 1U, event_names[index], generation);
    }

    std::string relocations;
    for (std::size_t index = 0U; index < input.relocation_probes.size(); ++index) {
        if (index != 0U) {
            relocations += ',';
        }
        std::string site = "relocation-";
        std::array<char, 16> number{};
        const auto converted = std::to_chars(
            number.data(), number.data() + number.size(), index + 1U);
        if (converted.ec != std::errc{}) {
            throw std::runtime_error("site encoding");
        }
        site.append(number.data(), converted.ptr);
        relocations += "{\"class\":\"" +
            relocation_class(input.relocation_probes[index].kind) +
            "\",\"generation\":1,\"site_id\":\"" + site +
            "\",\"write_count\":1}";
    }

    const std::string copy_expected_digest = hex_digest(expected_copy);
    const std::string observation =
        "{\"case_id\":\"" + std::string(trusted_case_id) + "\",\"events\":[" + events +
        "],\"kind\":\"jfg-g2-overlay-lifecycle-observation\",\"lifetimes\":[" +
        "{\"generation\":1,\"mapping_sha256\":\"" + mapping_digest +
        "\",\"state_sha256\":\"" + first_state_digest + "\"}," +
        "{\"generation\":2,\"mapping_sha256\":\"" + mapping_digest +
        "\",\"state_sha256\":\"" + second_state_digest + "\"}]," +
        "\"memory_checks\":[" +
        "{\"byte_count\":" + integer(copy_size) +
        ",\"expected_sha256\":\"" + copy_expected_digest +
        "\",\"observed_sha256\":\"" + copy_observed_digest +
        "\",\"phase\":\"copy\",\"zero_byte_count\":0}," +
        "{\"byte_count\":" + integer(bss.size()) +
        ",\"expected_sha256\":\"" + bss_digest +
        "\",\"observed_sha256\":\"" + bss_digest +
        "\",\"phase\":\"bss-clear\",\"zero_byte_count\":" +
        integer(bss.size()) + "}," +
        "{\"byte_count\":" + integer(second_live.size()) +
        ",\"expected_sha256\":\"" + first_state_digest +
        "\",\"observed_sha256\":\"" + reload_digest +
        "\",\"phase\":\"reload\",\"zero_byte_count\":0}]," +
        "\"relocations\":[" + relocations + "],\"schema_version\":1," +
        "\"subject_sha256\":\"" + std::string(trusted_subject_digest) + "\"}";
    return "{\"execution_nonce\":\"" + std::string(nonce) +
        "\",\"observation\":" + observation + '}';
}

}  // namespace

int main(const int argc, const char* const* argv) {
    try {
#if defined(JFG_G2_OVERLAY_PRODUCER_TESTING)
        if (argc == 3 &&
            std::string_view(argv[1]) == "--g2-v3-reservation-test") {
            V3GuestMemory memory;
            const std::string_view location = argv[2];
            const std::uint64_t offset = location == "inside"
                ? 0U
                : location == "one-past"
                ? kV3ExecutionGuestBytes
                : location == "far-half"
                ? UINT64_C(0x80000000)
                : location == "far-end"
                ? UINT64_C(0xffffffff)
                : kV3GuestAddressSpaceBytes;
            if (offset >= kV3GuestAddressSpaceBytes) {
                return 2;
            }
            const std::byte value = *memory.test_address(offset);
            return location == "inside" && value == std::byte{0xa5} ? 0 : 1;
        }
#endif
        if (argc != 9 || !markers_present() ||
            std::string_view(argv[1]) != "--g2-evidence-probe" ||
            !is_digest(argv[2]) ||
            std::string_view(argv[3]) != "overlay-lifecycle" ||
            std::string_view(argv[4]) != "private-native-execution" ||
            std::string_view(argv[5]) != "--case-id" ||
            !is_identifier(argv[6]) ||
            std::string_view(argv[7]) != "--subject-sha256" ||
            !is_digest(argv[8])) {
            return 2;
        }
        const std::vector<std::byte> case_bytes = read_case_file();
        const ParsedCase input = read_case(case_bytes);
        const std::string output = input.is_v3
            ? produce_v3_observation(input.suite, case_bytes, argv[2], argv[6], argv[8])
            : produce_observation(input.legacy, case_bytes, argv[2], argv[6], argv[8]);
        std::cout.write(output.data(), static_cast<std::streamsize>(output.size()));
        return std::cout ? 0 : 1;
    } catch (...) {
        return 1;
    }
}
