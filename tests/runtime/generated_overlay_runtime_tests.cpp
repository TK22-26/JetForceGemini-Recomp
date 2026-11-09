#include "jfg/runtime/generated_overlay_runtime.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <functional>
#include <iostream>
#include <memory>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <utility>
#include <vector>

struct recomp_context {
    std::uint64_t result = 0U;
};

namespace {

constexpr std::uint64_t kModuleAlpha = 101U;
constexpr std::uint64_t kModuleBeta = 202U;
constexpr std::uint64_t kModuleGamma = 404U;
constexpr std::uint64_t kReferenceAlpha = 303U;
constexpr std::uint32_t kAlphaBase = jfg::kGeneratedCachedGuestBase + 0x20U;
constexpr std::uint32_t kBetaBase = jfg::kGeneratedCachedGuestBase + 0x40U;
constexpr std::uint32_t kGammaBase = jfg::kGeneratedCachedGuestBase + 0x60U;
constexpr std::size_t kGuestSize = 256U;

int failures = 0;
std::atomic<bool> block_alpha{false};
std::atomic<bool> alpha_entered{false};
std::atomic<bool> release_alpha{false};
std::atomic<jfg::GeneratedOverlayRuntime*> nested_dispatch_runtime{nullptr};
std::atomic<jfg::GeneratedOverlayError> nested_dispatch_error{
    jfg::GeneratedOverlayError::internal_failure};
std::atomic<jfg::GeneratedOverlayError> deep_nested_dispatch_error{
    jfg::GeneratedOverlayError::internal_failure};
std::atomic<bool> three_level_nested_dispatch{false};
std::atomic<std::size_t> alpha_mutation_offset{kGuestSize};
std::atomic<std::uint8_t> alpha_mutation_value{0U};

void check(const bool condition, const std::string_view message) {
    if (!condition) {
        ++failures;
        std::cerr << "FAIL: " << message << '\n';
    }
}

[[nodiscard]] bool invokes_with_result(
    const jfg::GeneratedOverlayFunctionHandle& function,
    const std::span<std::byte> memory,
    const std::uint64_t expected) {
    recomp_context context{};
    return function.invoke(
               reinterpret_cast<std::uint8_t*>(memory.data()), &context) ==
            jfg::GeneratedOverlayError::none &&
        context.result == expected;
}

void alpha_function(std::uint8_t* rdram, recomp_context* context) {
    if (block_alpha.load(std::memory_order_acquire)) {
        alpha_entered.store(true, std::memory_order_release);
        while (!release_alpha.load(std::memory_order_acquire)) {
            std::this_thread::yield();
        }
    }
    const std::size_t mutation_offset = alpha_mutation_offset.load(
        std::memory_order_acquire);
    if (mutation_offset < kGuestSize) {
        rdram[mutation_offset] = alpha_mutation_value.load(
            std::memory_order_acquire);
    }
    if (auto* const runtime = nested_dispatch_runtime.load(
            std::memory_order_acquire);
        runtime != nullptr) {
        nested_dispatch_error.store(
            runtime->invoke_leased_function_by_guest_address(
                three_level_nested_dispatch.load(std::memory_order_acquire)
                    ? kBetaBase
                    : kAlphaBase + 4U,
                rdram, context),
            std::memory_order_release);
        return;
    }
    context->result = 11U;
}

void alternate_alpha_function(std::uint8_t*, recomp_context* context) {
    context->result = 55U;
}

void beta_function(std::uint8_t* rdram, recomp_context* context) {
    if (three_level_nested_dispatch.load(std::memory_order_acquire)) {
        auto* const runtime = nested_dispatch_runtime.load(
            std::memory_order_acquire);
        deep_nested_dispatch_error.store(
            runtime == nullptr
                ? jfg::GeneratedOverlayError::internal_failure
                : runtime->invoke_leased_function_by_guest_address(
                    kGammaBase, rdram, context),
            std::memory_order_release);
        return;
    }
    context->result = 22U;
}

void gamma_function(std::uint8_t*, recomp_context* context) {
    context->result = 44U;
}

void main_function(std::uint8_t*, recomp_context* context) {
    context->result = 33U;
}

class SyntheticGeneratedTable final : public jfg::GeneratedOverlayTable {
public:
    ~SyntheticGeneratedTable() override {
        if (destructor_saw_bound_storage != nullptr) {
            *destructor_saw_bound_storage =
                !addresses_.empty() && addresses_[0] != 0;
        }
    }

    std::vector<jfg::GeneratedSectionExtents> metadata{
        {4U, 4U, 0U, false},
        {8U, 4U, 4U, true},
        {8U, 4U, 4U, true},
        {8U, 4U, 4U, true},
    };
    std::vector<std::size_t> relocation_counts{0U, 1U, 1U, 1U};
    std::vector<std::vector<std::uint32_t>> relocation_site_values{
        {}, {0U}, {0U}, {0U}};
    std::vector<std::vector<jfg::GeneratedR32RelocationDescriptor>>
        relocation_descriptor_values{
            {}, {{0U, 0U, 4U}}, {{0U, 0U, 4U}}, {{0U, 0U, 4U}}};
    std::vector<std::string>* events = nullptr;
    std::function<void(jfg::GeneratedSectionLifecycle, std::uint32_t)>
        lifecycle_hook;
    std::function<void()> lookup_hook;
    bool initialize_ok = true;
    bool publish_overlay_during_initialize = false;
    bool leave_main_unpublished = false;
    bool unstable_count = false;
    bool metadata_ok = true;
    bool lifecycle_load_ok = true;
    bool lifecycle_unload_ok = true;
    bool mutate_before_lifecycle_failure = false;
    bool throw_during_load = false;
    bool throw_during_unload = false;
    bool throw_during_relocation_count = false;
    bool throw_during_relocation_sites = false;
    bool throw_during_relocation_descriptors = false;
    bool throw_during_apply = false;
    bool throw_during_lookup = false;
    bool apply_ok = true;
    bool relocation_count_mismatch = false;
    bool swap_relocation_sites_after_first_read = false;
    bool swap_relocation_descriptors_after_first_read = false;
    bool write_outside_section = false;
    bool write_bss = false;
    bool hide_alpha_function = false;
    bool replace_alpha_function = false;
    bool expose_alpha_secondary_function = false;
    bool fail_rollback_unload = false;
    bool* destructor_saw_bound_storage = nullptr;
    std::vector<std::vector<std::uint32_t>> alternate_relocation_site_values{
        {}, {4U}, {4U}, {4U}};
    std::vector<std::vector<jfg::GeneratedR32RelocationDescriptor>>
        alternate_relocation_descriptor_values{
            {}, {{0U, 0U, 0U}}, {{0U, 0U, 0U}}, {{0U, 0U, 0U}}};
    std::size_t relocation_apply_calls = 0U;

    [[nodiscard]] std::size_t section_count() const override {
        if (unstable_count) {
            ++count_calls_;
            return metadata.size() + (count_calls_ > 1U ? 1U : 0U);
        }
        return metadata.size();
    }

    [[nodiscard]] bool initialize_sections(
        const std::span<std::int32_t> addresses) override {
        record("initialize");
        addresses_ = addresses;
        if (!initialize_ok || addresses.size() != metadata.size()) {
            return false;
        }
        std::fill(addresses.begin(), addresses.end(), 0);
        if (!leave_main_unpublished) {
            addresses[0] = static_cast<std::int32_t>(
                jfg::kGeneratedCachedGuestBase);
        }
        if (publish_overlay_during_initialize) {
            addresses[1] = static_cast<std::int32_t>(kAlphaBase);
        }
        return true;
    }

    [[nodiscard]] bool section_extents(
        const std::uint32_t section,
        jfg::GeneratedSectionExtents& output) const override {
        if (!metadata_ok || section >= metadata.size()) {
            return false;
        }
        output = metadata[section];
        return true;
    }

    [[nodiscard]] bool update_section_lifecycle(
        const jfg::GeneratedSectionLifecycle operation,
        const std::uint32_t section,
        const std::int32_t base) override {
        record(operation == jfg::GeneratedSectionLifecycle::load
                   ? "lifecycle-load"
                   : "lifecycle-unload");
        if (lifecycle_hook) {
            lifecycle_hook(operation, section);
        }
        if (section >= addresses_.size()) {
            return false;
        }
        if (operation == jfg::GeneratedSectionLifecycle::load) {
            if (mutate_before_lifecycle_failure || lifecycle_load_ok) {
                addresses_[section] = base;
            }
            if (throw_during_load) {
                throw std::runtime_error("synthetic lifecycle load");
            }
            return lifecycle_load_ok;
        }
        if (fail_rollback_unload && !lifecycle_load_ok) {
            return false;
        }
        if (mutate_before_lifecycle_failure || lifecycle_unload_ok) {
            addresses_[section] = 0;
        }
        if (throw_during_unload) {
            throw std::runtime_error("synthetic lifecycle unload");
        }
        return lifecycle_unload_ok;
    }

    [[nodiscard]] std::size_t relocation_count(
        const std::uint32_t source_section) const override {
        record("relocation-count");
        if (throw_during_relocation_count) {
            throw std::runtime_error("synthetic relocation count");
        }
        if (source_section >= relocation_counts.size()) {
            return 0U;
        }
        return relocation_counts[source_section];
    }

    [[nodiscard]] bool relocation_sites(
        const std::uint32_t source_section,
        std::span<const std::uint32_t>& output) const override {
        if (throw_during_relocation_sites) {
            throw std::runtime_error("synthetic relocation sites");
        }
        if (source_section >= relocation_site_values.size()) {
            return false;
        }
        ++relocation_sites_calls_;
        if (swap_relocation_sites_after_first_read &&
            relocation_sites_calls_ > 1U) {
            output = alternate_relocation_site_values[source_section];
            return true;
        }
        output = relocation_site_values[source_section];
        return true;
    }

    [[nodiscard]] bool relocation_descriptors(
        const std::uint32_t source_section,
        std::span<const jfg::GeneratedR32RelocationDescriptor>& output) const override {
        if (throw_during_relocation_descriptors) {
            throw std::runtime_error("synthetic relocation descriptors");
        }
        if (source_section >= relocation_descriptor_values.size()) {
            return false;
        }
        ++relocation_descriptor_calls_;
        if (swap_relocation_descriptors_after_first_read &&
            relocation_descriptor_calls_ > 1U) {
            output = alternate_relocation_descriptor_values[source_section];
            return true;
        }
        output = relocation_descriptor_values[source_section];
        return true;
    }

    [[nodiscard]] jfg::GeneratedRelocationResult apply_relocations_checked(
        const std::span<std::uint8_t> staged_rdram,
        const std::uint32_t source_section,
        const std::size_t expected_count) override {
        record("relocation-apply");
        ++relocation_apply_calls;
        if (throw_during_apply) {
            throw std::runtime_error("synthetic relocation apply");
        }
        if (!apply_ok || source_section >= addresses_.size() ||
            addresses_[source_section] == 0) {
            return {};
        }
        if (expected_count == 0U) {
            return {true, 0U};
        }
        const std::uint32_t address =
            static_cast<std::uint32_t>(addresses_[source_section]);
        const std::size_t offset = static_cast<std::size_t>(
            address - jfg::kGeneratedCachedGuestBase);
        if (source_section >= relocation_descriptor_values.size() ||
            relocation_descriptor_values[source_section].size() != expected_count) {
            return {};
        }
        for (const jfg::GeneratedR32RelocationDescriptor& descriptor :
             relocation_descriptor_values[source_section]) {
            if (descriptor.target_section >= addresses_.size() ||
                addresses_[descriptor.target_section] == 0 ||
                descriptor.site_offset > metadata[source_section].text_size +
                    metadata[source_section].data_size ||
                metadata[source_section].text_size + metadata[source_section].data_size -
                    descriptor.site_offset < 4U) {
                return {};
            }
            const std::uint32_t relocated_value = static_cast<std::uint32_t>(
                addresses_[descriptor.target_section]) + descriptor.target_offset;
            const std::size_t site = offset + descriptor.site_offset;
            staged_rdram[site] = static_cast<std::uint8_t>(relocated_value >> 24U);
            staged_rdram[site + 1U] = static_cast<std::uint8_t>(relocated_value >> 16U);
            staged_rdram[site + 2U] = static_cast<std::uint8_t>(relocated_value >> 8U);
            staged_rdram[site + 3U] = static_cast<std::uint8_t>(relocated_value);
        }
        if (write_outside_section) {
            staged_rdram[0x10U] ^= 0x1U;
        }
        if (write_bss) {
            staged_rdram[offset + metadata[source_section].text_size +
                metadata[source_section].data_size] = 0x7FU;
        }
        return {
            true,
            relocation_count_mismatch ? expected_count + 1U : expected_count,
        };
    }

    [[nodiscard]] jfg::GeneratedOverlayFunction lookup_function(
        const std::int32_t guest_address) const override {
        record("lookup");
        if (lookup_hook) {
            lookup_hook();
        }
        if (throw_during_lookup) {
            throw std::runtime_error("synthetic lookup");
        }
        const auto address = static_cast<std::uint32_t>(guest_address);
        if (!addresses_.empty() && addresses_[0] != 0 &&
            address == static_cast<std::uint32_t>(addresses_[0])) {
            return main_function;
        }
        if (!hide_alpha_function && addresses_.size() > 1U &&
            addresses_[1] != 0 &&
            address == static_cast<std::uint32_t>(addresses_[1])) {
            return replace_alpha_function
                ? alternate_alpha_function
                : alpha_function;
        }
        if (expose_alpha_secondary_function && addresses_.size() > 1U &&
            addresses_[1] != 0 &&
            address == static_cast<std::uint32_t>(addresses_[1]) + 4U) {
            return beta_function;
        }
        if (addresses_.size() > 2U && addresses_[2] != 0 &&
            address == static_cast<std::uint32_t>(addresses_[2])) {
            return beta_function;
        }
        if (addresses_.size() > 3U && addresses_[3] != 0 &&
            address == static_cast<std::uint32_t>(addresses_[3])) {
            return gamma_function;
        }
        return nullptr;
    }

    [[nodiscard]] std::int32_t address(const std::size_t section) const {
        return section < addresses_.size() ? addresses_[section] : 0;
    }

    void set_address(
        const std::size_t section,
        const std::int32_t address_value) {
        if (section < addresses_.size()) {
            addresses_[section] = address_value;
        }
    }

private:
    void record(const std::string_view event) const {
        if (events != nullptr) {
            events->emplace_back(event);
        }
    }

    std::span<std::int32_t> addresses_;
    mutable std::size_t count_calls_ = 0U;
    mutable std::size_t relocation_sites_calls_ = 0U;
    mutable std::size_t relocation_descriptor_calls_ = 0U;
};

class SyntheticCache final : public jfg::GeneratedInstructionCacheInvalidator {
public:
    std::vector<std::string>* events = nullptr;
    std::function<void()> prepare_hook;
    std::span<const std::byte> memory;
    std::size_t expected_offset = 0U;
    bool prepare_ok = true;
    bool throw_during_prepare = false;
    bool committed = false;
    bool commit_saw_relocated_memory = false;
    std::size_t prepare_calls = 0U;
    std::size_t reject_prepare_call = 0U;
    std::size_t abort_calls = 0U;

    [[nodiscard]] bool prepare(
        const jfg::GeneratedInstructionCacheRange& range) override {
        if (events != nullptr) {
            events->emplace_back("cache-prepare");
        }
        ++prepare_calls;
        last_range = range;
        if (prepare_hook) {
            prepare_hook();
        }
        if (throw_during_prepare) {
            throw std::runtime_error("synthetic cache prepare");
        }
        return prepare_ok && prepare_calls != reject_prepare_call;
    }

    void commit(
        const jfg::GeneratedInstructionCacheRange& range) noexcept override {
        if (events != nullptr) {
            events->emplace_back("cache-commit");
        }
        committed = true;
        std::uint32_t word = 0U;
        if (memory.size() >= expected_offset + sizeof(word)) {
            word = (std::to_integer<std::uint32_t>(memory[expected_offset]) << 24U) |
                (std::to_integer<std::uint32_t>(memory[expected_offset + 1U]) << 16U) |
                (std::to_integer<std::uint32_t>(memory[expected_offset + 2U]) << 8U) |
                std::to_integer<std::uint32_t>(memory[expected_offset + 3U]);
        }
        commit_saw_relocated_memory =
            range.opaque_module_id == last_range.opaque_module_id &&
            range.guest_base == last_range.guest_base &&
            range.byte_count == last_range.byte_count &&
            word == jfg::kGeneratedCachedGuestBase + 4U;
    }

    void abort(
        const jfg::GeneratedInstructionCacheRange&) noexcept override {
        ++abort_calls;
        if (events != nullptr) {
            events->emplace_back("cache-abort");
        }
    }

    jfg::GeneratedInstructionCacheRange last_range{};
};

struct Fixture {
    std::array<std::byte, kGuestSize> memory{};
    jfg::GeneratedOverlayRuntime runtime;
    SyntheticGeneratedTable* table = nullptr;
    SyntheticCache cache;
    std::vector<std::string> events;

    explicit Fixture(
        const bool extended_images = false,
        const bool all_text = false)
        : runtime(memory), cache{} {
        std::fill(memory.begin(), memory.end(), std::byte{0xCC});
        auto generated = std::make_unique<SyntheticGeneratedTable>();
        if (extended_images) {
            generated->metadata[1] = all_text
                ? jfg::GeneratedSectionExtents{16U, 0U, 4U, true}
                : jfg::GeneratedSectionExtents{8U, 8U, 4U, true};
            generated->metadata[2] = generated->metadata[1];
            generated->metadata[3] = generated->metadata[1];
        }
        table = generated.get();
        table->events = &events;
        cache.events = &events;
        cache.memory = memory;
        const auto installed = runtime.install_table(std::move(generated));
        check(installed.ok(), "synthetic generated table installs");
    }
};

[[nodiscard]] jfg::GeneratedOverlayImage image(
    const std::uint64_t module_id,
    const std::uint32_t section,
    std::vector<jfg::GeneratedOverlayDependency> dependencies = {}) {
    return {
        module_id,
        section,
        std::vector<std::byte>(12U, std::byte{0x5A}),
        std::move(dependencies),
        {},
        {},
    };
}

void write_be32(
    std::vector<std::byte>& bytes,
    const std::size_t offset,
    const std::uint32_t value) {
    bytes[offset] = static_cast<std::byte>(value >> 24U);
    bytes[offset + 1U] = static_cast<std::byte>(value >> 16U);
    bytes[offset + 2U] = static_cast<std::byte>(value >> 8U);
    bytes[offset + 3U] = static_cast<std::byte>(value);
}

[[nodiscard]] std::uint32_t read_be32(
    const std::span<const std::byte> bytes,
    const std::size_t offset) {
    return (std::to_integer<std::uint32_t>(bytes[offset]) << 24U) |
        (std::to_integer<std::uint32_t>(bytes[offset + 1U]) << 16U) |
        (std::to_integer<std::uint32_t>(bytes[offset + 2U]) << 8U) |
        std::to_integer<std::uint32_t>(bytes[offset + 3U]);
}

[[nodiscard]] std::vector<std::byte> memory_copy(
    const std::span<const std::byte> memory) {
    return {memory.begin(), memory.end()};
}

void test_table_installation_contract() {
    std::array<std::byte, kGuestSize> memory{};
    jfg::GeneratedOverlayRuntime runtime(memory);
    check(
        runtime.install_table(nullptr).error ==
            jfg::GeneratedOverlayError::invalid_table,
        "null generated table is rejected");

    auto unstable = std::make_unique<SyntheticGeneratedTable>();
    unstable->unstable_count = true;
    check(
        runtime.install_table(std::move(unstable)).error ==
            jfg::GeneratedOverlayError::invalid_section_count,
        "unstable generated section count is rejected");

    auto published = std::make_unique<SyntheticGeneratedTable>();
    published->publish_overlay_during_initialize = true;
    check(
        runtime.install_table(std::move(published)).error ==
            jfg::GeneratedOverlayError::initial_overlay_published,
        "initially published generated overlay is rejected");

    auto bad_metadata = std::make_unique<SyntheticGeneratedTable>();
    bad_metadata->metadata[1].text_size = 3U;
    check(
        runtime.install_table(std::move(bad_metadata)).error ==
            jfg::GeneratedOverlayError::invalid_section_metadata,
        "misaligned generated section extent is rejected");

    auto no_main = std::make_unique<SyntheticGeneratedTable>();
    no_main->leave_main_unpublished = true;
    check(
        runtime.install_table(std::move(no_main)).error ==
            jfg::GeneratedOverlayError::section_initialization_failed,
        "unpublished generated main section is rejected");

    auto valid = std::make_unique<SyntheticGeneratedTable>();
    check(runtime.install_table(std::move(valid)).ok(),
          "valid generated table installs after rejected candidates");
    check(
        runtime.install_table(std::make_unique<SyntheticGeneratedTable>()).error ==
            jfg::GeneratedOverlayError::table_already_installed,
        "generated table ownership cannot be replaced");

    bool destructor_saw_bound_storage = false;
    {
        std::array<std::byte, kGuestSize> scoped_memory{};
        jfg::GeneratedOverlayRuntime scoped_runtime(scoped_memory);
        auto scoped_table = std::make_unique<SyntheticGeneratedTable>();
        scoped_table->destructor_saw_bound_storage =
            &destructor_saw_bound_storage;
        check(scoped_runtime.install_table(std::move(scoped_table)).ok(),
              "scoped generated table installs");
    }
    check(destructor_saw_bound_storage,
          "owned adapter is destroyed while bound address storage is alive");
}

void test_transactional_load_lookup_unload_reload() {
    Fixture fixture;
    const auto static_function =
        fixture.runtime.lookup_function_by_guest_address(
            jfg::kGeneratedCachedGuestBase);
    check(static_function.ok() &&
              invokes_with_result(static_function.function, fixture.memory, 33U),
          "generated get_function bridge resolves initialized static text");
    fixture.cache.expected_offset = 0x20U;
    const auto before = memory_copy(fixture.memory);
    const auto loaded = fixture.runtime.load(
        image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
    check(loaded.ok(), "generated overlay loads transactionally");
    check(fixture.table->address(1U) == static_cast<std::int32_t>(kAlphaBase),
          "generated section address publishes on load");
    check(fixture.cache.committed && fixture.cache.commit_saw_relocated_memory,
          "cache commit observes relocated live memory");
    check(
        fixture.cache.last_range.opaque_module_id == kModuleAlpha &&
            fixture.cache.last_range.guest_base == kAlphaBase &&
            fixture.cache.last_range.byte_count == 8U,
        "cache invalidation range is bounded to synthetic text");

    const std::uint32_t relocated = read_be32(fixture.memory, 0x20U);
    check(relocated == jfg::kGeneratedCachedGuestBase + 4U,
          "checked relocation reaches live guest memory");
    check(std::all_of(
              fixture.memory.begin() + 0x2CU,
              fixture.memory.begin() + 0x30U,
              [](const std::byte value) { return value == std::byte{0}; }),
          "BSS is cleared before publication");
    check(std::equal(
              before.begin(), before.begin() + 0x20U, fixture.memory.begin()),
          "load leaves guest bytes before its mapped extent unchanged");
    check(std::equal(
              before.begin() + 0x30U,
              before.end(),
              fixture.memory.begin() + 0x30U),
          "load leaves guest bytes after its mapped extent unchanged");

    auto function = fixture.runtime.lookup_function(loaded.token, 0U);
    check(function.ok() && invokes_with_result(function.function, fixture.memory, 11U),
          "active generated function resolves through the runtime token");
    const jfg::GeneratedOverlayFunctionHandle stale_after_unload =
        function.function;
    std::array<std::uint8_t, kGuestSize> unrelated_memory{};
    recomp_context invocation_context{};
    check(
        function.function.invoke(unrelated_memory.data(), &invocation_context) ==
                jfg::GeneratedOverlayError::stale_token &&
            function.function.invoke(
                reinterpret_cast<std::uint8_t*>(fixture.memory.data()), nullptr) ==
                jfg::GeneratedOverlayError::invalid_mapping,
        "dispatch handle rejects unrelated RDRAM and a null ABI context");
    function = fixture.runtime.lookup_function_by_guest_address(kAlphaBase);
    check(function.ok() && invokes_with_result(function.function, fixture.memory, 11U),
          "generated get_function bridge resolves active overlay text");
    check(
        fixture.runtime.lookup_function(loaded.token, 4U).error ==
            jfg::GeneratedOverlayError::function_not_found,
        "unknown in-range function fails closed");
    check(
        fixture.runtime.lookup_function(loaded.token, 8U).error ==
            jfg::GeneratedOverlayError::function_not_found,
        "function lookup outside text fails closed");

    check(
        fixture.runtime.unload(loaded.token) ==
                jfg::GeneratedOverlayError::cache_invalidation_rejected &&
            fixture.runtime.lookup_function(loaded.token, 0U).ok(),
        "legacy unload without a cache transaction fails closed");
    check(fixture.runtime.unload(loaded.token, fixture.cache) ==
              jfg::GeneratedOverlayError::none,
          "generated overlay unload succeeds");
    check(
        stale_after_unload.invoke(
            reinterpret_cast<std::uint8_t*>(fixture.memory.data()),
            &invocation_context) == jfg::GeneratedOverlayError::stale_token,
        "a previously returned callable is permanently revoked on unload");
    check(fixture.table->address(1U) == 0,
          "unload removes generated lookup address");
    check(std::all_of(
              fixture.memory.begin() + 0x20U,
              fixture.memory.begin() + 0x30U,
              [](const std::byte value) { return value == std::byte{0}; }),
          "unload clears the complete mapped extent");
    check(
        fixture.runtime.lookup_function(loaded.token, 0U).error ==
            jfg::GeneratedOverlayError::module_inactive,
        "unloaded lifetime cannot resolve a function");
    check(
        fixture.runtime.lookup_function_by_guest_address(kAlphaBase).error ==
            jfg::GeneratedOverlayError::function_not_found,
        "generated get_function bridge rejects inactive overlay text");
    check(
        fixture.runtime.load(image(kModuleAlpha, 1U), kAlphaBase, fixture.cache)
                .error == jfg::GeneratedOverlayError::reload_required,
        "a known unloaded module cannot bypass reload");

    fixture.cache.committed = false;
    const auto reloaded = fixture.runtime.reload_same_base(
        loaded.token, fixture.cache);
    check(reloaded.ok() && reloaded.token != loaded.token,
          "same-base reload creates a new opaque generation");
    check(fixture.cache.committed && fixture.table->address(1U) ==
              static_cast<std::int32_t>(kAlphaBase),
          "reload repeats copy, relocation, cache, and publication");
    check(
        fixture.runtime.lookup_function(loaded.token, 0U).error ==
            jfg::GeneratedOverlayError::stale_token,
        "prior generation token is rejected after reload");
    check(fixture.runtime.unload(reloaded.token, fixture.cache) ==
              jfg::GeneratedOverlayError::none,
          "reloaded lifetime can unload");
}

void test_unload_quiesces_active_invocation() {
    Fixture fixture;
    const auto loaded = fixture.runtime.load(
        image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
    const auto callable = fixture.runtime.lookup_function(loaded.token, 0U);
    const auto static_callable = fixture.runtime.lookup_function_by_guest_address(
        jfg::kGeneratedCachedGuestBase);
    check(loaded.ok() && callable.ok() && static_callable.ok(),
          "quiescence fixture resolves overlay and static handles");

    block_alpha.store(true, std::memory_order_release);
    alpha_entered.store(false, std::memory_order_release);
    release_alpha.store(false, std::memory_order_release);
    std::atomic<jfg::GeneratedOverlayError> invocation_error{
        jfg::GeneratedOverlayError::internal_failure};
    std::thread invocation([&]() {
        recomp_context context{};
        invocation_error.store(
            callable.function.invoke(
                reinterpret_cast<std::uint8_t*>(fixture.memory.data()),
                &context),
            std::memory_order_release);
    });
    while (!alpha_entered.load(std::memory_order_acquire)) {
        std::this_thread::yield();
    }

    std::atomic<bool> unload_done{false};
    std::atomic<jfg::GeneratedOverlayError> unload_error{
        jfg::GeneratedOverlayError::internal_failure};
    std::thread unloading([&]() {
        unload_error.store(
            fixture.runtime.unload(loaded.token, fixture.cache),
            std::memory_order_release);
        unload_done.store(true, std::memory_order_release);
    });

    bool admission_closed = false;
    for (std::size_t attempt = 0U; attempt < 100'000U; ++attempt) {
        recomp_context context{};
        const auto error = static_callable.function.invoke(
            reinterpret_cast<std::uint8_t*>(fixture.memory.data()), &context);
        if (error == jfg::GeneratedOverlayError::busy) {
            admission_closed = true;
            break;
        }
        std::this_thread::yield();
    }
    check(admission_closed && !unload_done.load(std::memory_order_acquire),
          "unload closes admission and waits for an already active invocation");
    release_alpha.store(true, std::memory_order_release);
    invocation.join();
    unloading.join();
    block_alpha.store(false, std::memory_order_release);
    check(
        invocation_error.load(std::memory_order_acquire) ==
                jfg::GeneratedOverlayError::none &&
            unload_error.load(std::memory_order_acquire) ==
                jfg::GeneratedOverlayError::none,
        "active invocation completes before transactional unload commits");
}

void test_unload_quiescence_allows_nested_dispatch() {
    Fixture fixture;
    const auto loaded = fixture.runtime.load(
        image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
    const auto middle_loaded = fixture.runtime.load(
        image(kModuleBeta, 2U), kBetaBase, fixture.cache);
    const auto inner_loaded = fixture.runtime.load(
        image(kModuleGamma, 3U), kGammaBase, fixture.cache);
    const auto outer = fixture.runtime.lookup_function(loaded.token, 0U);
    const auto middle = fixture.runtime.lookup_function(middle_loaded.token, 0U);
    const auto inner = fixture.runtime.lookup_function(inner_loaded.token, 0U);
    const auto static_callable = fixture.runtime.lookup_function_by_guest_address(
        jfg::kGeneratedCachedGuestBase);
    check(loaded.ok() && middle_loaded.ok() && inner_loaded.ok() && outer.ok() &&
              middle.ok() && inner.ok() && static_callable.ok(),
          "three-level nested-quiescence fixture resolves all capabilities");

    block_alpha.store(true, std::memory_order_release);
    alpha_entered.store(false, std::memory_order_release);
    release_alpha.store(false, std::memory_order_release);
    nested_dispatch_error.store(
        jfg::GeneratedOverlayError::internal_failure,
        std::memory_order_release);
    deep_nested_dispatch_error.store(
        jfg::GeneratedOverlayError::internal_failure,
        std::memory_order_release);
    three_level_nested_dispatch.store(true, std::memory_order_release);
    nested_dispatch_runtime.store(&fixture.runtime, std::memory_order_release);
    std::atomic<jfg::GeneratedOverlayError> invocation_error{
        jfg::GeneratedOverlayError::internal_failure};
    std::atomic<std::uint64_t> invocation_result{0U};
    std::thread invocation([&]() {
        recomp_context context{};
        invocation_error.store(
            outer.function.invoke(
                reinterpret_cast<std::uint8_t*>(fixture.memory.data()),
                &context),
            std::memory_order_release);
        invocation_result.store(context.result, std::memory_order_release);
    });
    while (!alpha_entered.load(std::memory_order_acquire)) {
        std::this_thread::yield();
    }

    std::atomic<bool> unload_done{false};
    std::atomic<jfg::GeneratedOverlayError> unload_error{
        jfg::GeneratedOverlayError::internal_failure};
    std::thread unloading([&]() {
        unload_error.store(
            fixture.runtime.unload(loaded.token, fixture.cache),
            std::memory_order_release);
        unload_done.store(true, std::memory_order_release);
    });
    bool admission_closed = false;
    for (std::size_t attempt = 0U; attempt < 100'000U; ++attempt) {
        recomp_context context{};
        if (static_callable.function.invoke(
                reinterpret_cast<std::uint8_t*>(fixture.memory.data()),
                &context) == jfg::GeneratedOverlayError::busy) {
            admission_closed = true;
            break;
        }
        std::this_thread::yield();
    }
    check(admission_closed && !unload_done.load(std::memory_order_acquire),
          "quiescing unload waits without suspending admitted nested dispatch");
    release_alpha.store(true, std::memory_order_release);
    invocation.join();
    unloading.join();
    nested_dispatch_runtime.store(nullptr, std::memory_order_release);
    three_level_nested_dispatch.store(false, std::memory_order_release);
    block_alpha.store(false, std::memory_order_release);

    recomp_context stale_context{};
    check(
        invocation_error.load(std::memory_order_acquire) ==
                jfg::GeneratedOverlayError::none &&
            nested_dispatch_error.load(std::memory_order_acquire) ==
                jfg::GeneratedOverlayError::none &&
            deep_nested_dispatch_error.load(std::memory_order_acquire) ==
                jfg::GeneratedOverlayError::none &&
            invocation_result.load(std::memory_order_acquire) == 44U &&
            unload_error.load(std::memory_order_acquire) ==
                jfg::GeneratedOverlayError::none &&
            !outer.function.valid() && middle.function.valid() &&
            inner.function.valid() && outer.function.invoke(
                reinterpret_cast<std::uint8_t*>(fixture.memory.data()),
                &stale_context) == jfg::GeneratedOverlayError::stale_token,
        "admitted three-level dispatch completes before unload revokes the root");
}

void test_unload_preserves_inflight_dependent_data() {
    Fixture fixture;
    fixture.table->relocation_counts[2] = 0U;
    fixture.table->relocation_site_values[2].clear();
    fixture.table->relocation_descriptor_values[2].clear();
    const auto provider = fixture.runtime.load(
        image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
    auto dependent_image = image(
        kModuleBeta, 2U, {{kReferenceAlpha, kModuleAlpha, 0U}});
    dependent_image.custom_relocations = {{4U,
        jfg::CustomOverlayRelocationSource::external,
        jfg::CustomOverlayRelocationPatch::full_word, 600U, 0}};
    dependent_image.custom_bindings = {
        {600U, kModuleAlpha, jfg::kNoGeneratedStaticSection, 0U}};
    const auto dependent = fixture.runtime.load(
        std::move(dependent_image), kBetaBase, fixture.cache);
    const auto callable = fixture.runtime.lookup_function(provider.token, 0U);
    const auto static_callable = fixture.runtime.lookup_function_by_guest_address(
        jfg::kGeneratedCachedGuestBase);
    check(provider.ok() && dependent.ok() && callable.ok() &&
              static_callable.ok() &&
              read_be32(
                  std::span<const std::byte>(fixture.memory).subspan(0x40U),
                  4U) == kAlphaBase,
          "dependent-mutation fixture publishes its provider binding");

    block_alpha.store(true, std::memory_order_release);
    alpha_entered.store(false, std::memory_order_release);
    release_alpha.store(false, std::memory_order_release);
    alpha_mutation_offset.store(0x48U, std::memory_order_release);
    alpha_mutation_value.store(0x7BU, std::memory_order_release);
    std::atomic<jfg::GeneratedOverlayError> invocation_error{
        jfg::GeneratedOverlayError::internal_failure};
    std::thread invocation([&]() {
        recomp_context context{};
        invocation_error.store(
            callable.function.invoke(
                reinterpret_cast<std::uint8_t*>(fixture.memory.data()),
                &context),
            std::memory_order_release);
    });
    while (!alpha_entered.load(std::memory_order_acquire)) {
        std::this_thread::yield();
    }

    std::atomic<bool> unload_done{false};
    std::atomic<jfg::GeneratedOverlayError> unload_error{
        jfg::GeneratedOverlayError::internal_failure};
    std::thread unloading([&]() {
        unload_error.store(
            fixture.runtime.unload(provider.token, fixture.cache),
            std::memory_order_release);
        unload_done.store(true, std::memory_order_release);
    });
    bool admission_closed = false;
    for (std::size_t attempt = 0U; attempt < 100'000U; ++attempt) {
        recomp_context context{};
        if (static_callable.function.invoke(
                reinterpret_cast<std::uint8_t*>(fixture.memory.data()),
                &context) == jfg::GeneratedOverlayError::busy) {
            admission_closed = true;
            break;
        }
        std::this_thread::yield();
    }
    check(admission_closed && !unload_done.load(std::memory_order_acquire),
          "dependent mutation occurs only after unload has begun quiescing");
    release_alpha.store(true, std::memory_order_release);
    invocation.join();
    unloading.join();
    alpha_mutation_offset.store(kGuestSize, std::memory_order_release);
    alpha_mutation_value.store(0U, std::memory_order_release);
    block_alpha.store(false, std::memory_order_release);

    check(
        invocation_error.load(std::memory_order_acquire) ==
                jfg::GeneratedOverlayError::none &&
            unload_error.load(std::memory_order_acquire) ==
                jfg::GeneratedOverlayError::none &&
            fixture.memory[0x48U] == std::byte{0x7B} &&
            read_be32(
                std::span<const std::byte>(fixture.memory).subspan(0x40U),
                4U) == 0x5A5A5A5AU &&
            fixture.runtime.lookup_function(dependent.token, 0U).error ==
                jfg::GeneratedOverlayError::dependency_invalidated,
        "quiescent unload retains unrelated dependent writes and invalidates only binding sites");
}

void test_lookup_target_mutation_poisoning() {
    Fixture fixture;
    const auto loaded = fixture.runtime.load(
        image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
    const auto original = fixture.runtime.lookup_function(loaded.token, 0U);
    check(loaded.ok() && original.ok(),
          "lookup-mutation fixture publishes an initial capability");
    fixture.table->replace_alpha_function = true;
    check(
        fixture.runtime.lookup_function(loaded.token, 0U).error ==
                jfg::GeneratedOverlayError::runtime_poisoned &&
            !original.function.valid(),
        "same-identity target mutation revokes the old gate and poisons runtime");
    recomp_context context{};
    check(
        original.function.invoke(
            reinterpret_cast<std::uint8_t*>(fixture.memory.data()),
            &context) == jfg::GeneratedOverlayError::stale_token &&
            context.result == 0U &&
            fixture.runtime.lookup_function(loaded.token, 0U).error ==
                jfg::GeneratedOverlayError::runtime_poisoned,
        "replaced target capability cannot execute after table mutation");
}

void test_dependency_invalidation_and_rebind() {
    Fixture fixture;
    fixture.cache.expected_offset = 0x20U;
    const auto alpha = fixture.runtime.load(
        image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
    check(alpha.ok(), "dependency target loads");

    fixture.cache.expected_offset = 0x40U;
    const auto beta = fixture.runtime.load(
        image(
            kModuleBeta,
            2U,
            {{kReferenceAlpha, kModuleAlpha, 0U}}),
        kBetaBase,
        fixture.cache);
    check(beta.ok(), "dependent overlay loads against active target");
    auto resolved = fixture.runtime.resolve_dependency(
        beta.token, kReferenceAlpha);
    check(resolved.ok() && invokes_with_result(resolved.function, fixture.memory, 11U),
          "dependency resolves through a generation-bound binding");
    const jfg::GeneratedOverlayFunctionHandle first_dependency_capability =
        resolved.function;
    check(
        fixture.runtime.resolve_dependency(beta.token, 999U).error ==
            jfg::GeneratedOverlayError::invalid_dependency,
        "undeclared dependency identity is rejected");

    check(fixture.runtime.unload(alpha.token, fixture.cache) ==
              jfg::GeneratedOverlayError::none,
          "dependency target unload succeeds");
    recomp_context stale_context{};
    check(
        first_dependency_capability.invoke(
            reinterpret_cast<std::uint8_t*>(fixture.memory.data()),
            &stale_context) == jfg::GeneratedOverlayError::stale_token,
        "provider unload revokes previously resolved dependency capabilities");
    check(
        fixture.runtime.resolve_dependency(beta.token, kReferenceAlpha).error ==
            jfg::GeneratedOverlayError::dependency_invalidated,
        "target unload invalidates every dependent binding");
    check(
        fixture.runtime.lookup_function(beta.token, 0U).error ==
            jfg::GeneratedOverlayError::dependency_invalidated,
        "dependent native execution fails closed while a binding is invalidated");
    check(
        fixture.runtime.lookup_function_by_guest_address(kBetaBase).error ==
            jfg::GeneratedOverlayError::dependency_invalidated,
        "absolute generated lookup also blocks an invalidated dependent");

    fixture.cache.expected_offset = 0x20U;
    const auto alpha_reloaded = fixture.runtime.reload_same_base(
        alpha.token, fixture.cache);
    check(alpha_reloaded.ok(), "dependency target reload succeeds at same base");
    resolved = fixture.runtime.resolve_dependency(beta.token, kReferenceAlpha);
    check(resolved.ok() && invokes_with_result(resolved.function, fixture.memory, 11U),
          "target reload atomically rebinds active dependents");
    const jfg::GeneratedOverlayFunctionHandle owner_bound_capability =
        resolved.function;
    check(fixture.runtime.lookup_function(beta.token, 0U).ok(),
          "dependent native execution resumes only after atomic rebind");
    check(fixture.runtime.lookup_function_by_guest_address(kBetaBase).ok(),
          "absolute generated lookup resumes after atomic rebind");

    check(fixture.runtime.unload(alpha_reloaded.token, fixture.cache) ==
              jfg::GeneratedOverlayError::none,
          "rebound target unloads again");
    fixture.table->hide_alpha_function = true;
    const auto failed_reload = fixture.runtime.reload_same_base(
        alpha_reloaded.token, fixture.cache);
    check(
        failed_reload.error == jfg::GeneratedOverlayError::function_not_found &&
            fixture.table->address(1U) == 0,
        "failed dependent rebind rolls target publication back");
    check(
        fixture.runtime.resolve_dependency(beta.token, kReferenceAlpha).error ==
            jfg::GeneratedOverlayError::dependency_invalidated,
        "failed rebind leaves dependent fail-closed");
    check(fixture.runtime.unload(beta.token, fixture.cache) ==
              jfg::GeneratedOverlayError::none,
          "dependent remains independently unloadable");
    check(
        owner_bound_capability.invoke(
            reinterpret_cast<std::uint8_t*>(fixture.memory.data()),
            &stale_context) == jfg::GeneratedOverlayError::stale_token,
        "owner unload revokes a capability even when its provider remains registered");
}

void test_generated_r32_provider_lifecycle() {
    Fixture fixture;
    fixture.table->relocation_counts[3] = 2U;
    fixture.table->relocation_site_values[3] = {0U, 4U};
    fixture.table->relocation_descriptor_values[3] = {
        {0U, 1U, 8U},  // provider initialized data
        {4U, 2U, 12U}, // provider BSS
    };

    const auto alpha = fixture.runtime.load(
        image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
    const auto beta = fixture.runtime.load(
        image(kModuleBeta, 2U), kBetaBase, fixture.cache);
    const auto gamma = fixture.runtime.load(
        image(kModuleGamma, 3U), kGammaBase, fixture.cache);
    check(alpha.ok() && beta.ok() && gamma.ok(),
          "R32 dependent accepts active overlay providers");
    const auto gamma_bytes = std::span<const std::byte>(fixture.memory).subspan(0x60U, 12U);
    check(read_be32(gamma_bytes, 0U) == kAlphaBase + 8U &&
              read_be32(gamma_bytes, 4U) == kBetaBase + 12U,
          "R32 descriptors preserve data and BSS target offsets");

    check(fixture.runtime.unload(alpha.token, fixture.cache) ==
              jfg::GeneratedOverlayError::none,
          "first R32 provider unloads");
    check(fixture.runtime.lookup_function(gamma.token, 0U).error ==
              jfg::GeneratedOverlayError::dependency_invalidated,
          "provider unload invalidates descriptor-only dependent lookup");
    const auto before_failed_reload = memory_copy(fixture.memory);
    fixture.cache.prepare_ok = false;
    check(fixture.runtime.reload_same_base(alpha.token, fixture.cache).error ==
              jfg::GeneratedOverlayError::cache_invalidation_rejected &&
              memory_copy(fixture.memory) == before_failed_reload,
          "R32 rebind cache rejection leaves all guest bytes unchanged");
    fixture.cache.prepare_ok = true;
    const auto alpha_reloaded = fixture.runtime.reload_same_base(alpha.token, fixture.cache);
    check(alpha_reloaded.ok() && fixture.runtime.lookup_function(gamma.token, 0U).ok(),
          "same-base R32 provider reload atomically restores dependent validity");
    check(read_be32(std::span<const std::byte>(fixture.memory).subspan(0x60U), 0U) ==
              kAlphaBase + 8U,
          "R32 reload reapplies pristine descriptor bytes without double relocation");

    check(fixture.runtime.unload(beta.token, fixture.cache) ==
              jfg::GeneratedOverlayError::none,
          "second R32 provider unloads");
    check(fixture.runtime.lookup_function(gamma.token, 0U).error ==
              jfg::GeneratedOverlayError::dependency_invalidated,
          "multiple R32 provider invalidation stays fail-closed");
    const auto beta_reloaded = fixture.runtime.reload_same_base(beta.token, fixture.cache);
    check(beta_reloaded.ok() && fixture.runtime.lookup_function(gamma.token, 0U).ok(),
          "second provider reload restores a multi-provider descriptor dependent");
}

void test_generated_r32_descriptor_closure() {
    {
        Fixture fixture;
        const auto before = memory_copy(fixture.memory);
        fixture.table->swap_relocation_descriptors_after_first_read = true;
        check(fixture.runtime.load(image(kModuleAlpha, 1U), kAlphaBase, fixture.cache).error ==
                  jfg::GeneratedOverlayError::relocation_site_mismatch &&
                  memory_copy(fixture.memory) == before && fixture.table->address(1U) == 0,
              "mutated generated descriptor inventory fails before partial guest commit");
    }
    {
        Fixture fixture;
        fixture.table->relocation_descriptor_values[2] = {{0U, 1U, 0U}};
        const auto before = memory_copy(fixture.memory);
        check(fixture.runtime.load(image(kModuleBeta, 2U), kBetaBase, fixture.cache).error ==
                  jfg::GeneratedOverlayError::dependency_unresolved &&
                  memory_copy(fixture.memory) == before && fixture.table->address(2U) == 0,
              "generated R32 target overlay must already be active at admission");
    }
}

void test_generated_descriptor_callback_exceptions() {
    {
        Fixture fixture;
        const auto before = memory_copy(fixture.memory);
        fixture.table->throw_during_relocation_count = true;
        check(fixture.runtime.load(image(kModuleAlpha, 1U), kAlphaBase, fixture.cache).error ==
                  jfg::GeneratedOverlayError::callback_exception &&
                  memory_copy(fixture.memory) == before && fixture.table->address(1U) == 0,
              "generated relocation-count callback exception is sanitized at admission");
    }
    {
        Fixture fixture;
        const auto before = memory_copy(fixture.memory);
        fixture.table->throw_during_relocation_sites = true;
        check(fixture.runtime.load(image(kModuleAlpha, 1U), kAlphaBase, fixture.cache).error ==
                  jfg::GeneratedOverlayError::callback_exception &&
                  memory_copy(fixture.memory) == before && fixture.table->address(1U) == 0,
              "generated relocation-site callback exception is sanitized at admission");
    }
    {
        Fixture fixture;
        const auto before = memory_copy(fixture.memory);
        fixture.table->throw_during_relocation_descriptors = true;
        check(fixture.runtime.load(image(kModuleAlpha, 1U), kAlphaBase, fixture.cache).error ==
                  jfg::GeneratedOverlayError::callback_exception &&
                  memory_copy(fixture.memory) == before && fixture.table->address(1U) == 0,
              "generated descriptor callback exception is sanitized at admission");
    }
}

void test_generated_target_address_boundaries() {
    std::uint32_t address = 0U;
    check(
        jfg::try_add_generated_guest_address(0xFFFFFFFCU, 3U, address) &&
            address == 0xFFFFFFFFU,
        "the last representable generated relocation target is accepted");
    check(
        !jfg::try_add_generated_guest_address(0xFFFFFFFCU, 4U, address),
        "generated R32 and custom targets reject the one-past-32-bit endpoint");
    check(
        !jfg::try_add_generated_guest_address(0xFFFFFFFFU, 1U, address),
        "generated R32 and custom targets reject wrapping addresses");
}

void test_transactional_failure_paths() {
    {
        Fixture fixture;
        const auto before = memory_copy(fixture.memory);
        fixture.cache.prepare_ok = false;
        const auto loaded = fixture.runtime.load(
            image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
        check(
            loaded.error ==
                    jfg::GeneratedOverlayError::cache_invalidation_rejected &&
                memory_copy(fixture.memory) == before &&
                fixture.table->address(1U) == 0 && !fixture.cache.committed,
            "cache rejection leaves memory and publication unchanged");
    }
    {
        Fixture fixture;
        const auto before = memory_copy(fixture.memory);
        fixture.cache.throw_during_prepare = true;
        const auto loaded = fixture.runtime.load(
            image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
        check(
            loaded.error == jfg::GeneratedOverlayError::callback_exception &&
                memory_copy(fixture.memory) == before &&
                fixture.table->address(1U) == 0 && !fixture.cache.committed,
            "cache preparation exception rolls staged lifecycle back");
    }
    {
        Fixture fixture;
        const auto before = memory_copy(fixture.memory);
        fixture.table->relocation_counts[1] = 4U;
        const auto loaded = fixture.runtime.load(
            image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
        check(
            loaded.error ==
                    jfg::GeneratedOverlayError::invalid_relocation_count &&
                memory_copy(fixture.memory) == before &&
                fixture.table->address(1U) == 0,
            "relocation denominator cannot exceed initialized words");
    }
    {
        Fixture fixture;
        const auto before = memory_copy(fixture.memory);
        fixture.table->apply_ok = false;
        const auto loaded = fixture.runtime.load(
            image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
        check(
            loaded.error == jfg::GeneratedOverlayError::relocation_failed &&
                memory_copy(fixture.memory) == before &&
                fixture.table->address(1U) == 0,
            "relocation rejection rolls generated lifecycle back");
    }
    {
        Fixture fixture;
        const auto before = memory_copy(fixture.memory);
        fixture.table->relocation_count_mismatch = true;
        const auto loaded = fixture.runtime.load(
            image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
        check(
            loaded.error ==
                    jfg::GeneratedOverlayError::relocation_count_mismatch &&
                memory_copy(fixture.memory) == before &&
                fixture.table->address(1U) == 0,
            "relocation count mismatch cannot publish staged bytes");
    }
    {
        Fixture fixture;
        const auto before = memory_copy(fixture.memory);
        fixture.table->write_outside_section = true;
        const auto loaded = fixture.runtime.load(
            image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
        check(
            loaded.error ==
                    jfg::GeneratedOverlayError::relocation_wrote_outside_section &&
                memory_copy(fixture.memory) == before &&
                fixture.table->address(1U) == 0,
            "out-of-section relocation write is detected transactionally");
    }
    {
        Fixture fixture;
        const auto before = memory_copy(fixture.memory);
        fixture.table->write_bss = true;
        const auto loaded = fixture.runtime.load(
            image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
        check(
            loaded.error == jfg::GeneratedOverlayError::bss_not_zero &&
                memory_copy(fixture.memory) == before &&
                fixture.table->address(1U) == 0,
            "relocation cannot corrupt cleared BSS");
    }
    {
        Fixture fixture;
        const auto before = memory_copy(fixture.memory);
        fixture.table->throw_during_apply = true;
        const auto loaded = fixture.runtime.load(
            image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
        check(
            loaded.error == jfg::GeneratedOverlayError::callback_exception &&
                memory_copy(fixture.memory) == before &&
                fixture.table->address(1U) == 0,
            "relocation exception rolls lifecycle and staging back");
    }
    {
        Fixture fixture;
        const auto before = memory_copy(fixture.memory);
        fixture.table->lifecycle_load_ok = false;
        fixture.table->mutate_before_lifecycle_failure = true;
        const auto loaded = fixture.runtime.load(
            image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
        check(
            loaded.error == jfg::GeneratedOverlayError::section_load_failed &&
                memory_copy(fixture.memory) == before &&
                fixture.table->address(1U) == 0,
            "partially mutating lifecycle failure is explicitly rolled back");
    }
    {
        Fixture fixture;
        const auto before = memory_copy(fixture.memory);
        fixture.table->throw_during_load = true;
        fixture.table->mutate_before_lifecycle_failure = true;
        const auto loaded = fixture.runtime.load(
            image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
        check(
            loaded.error == jfg::GeneratedOverlayError::callback_exception &&
                memory_copy(fixture.memory) == before &&
                fixture.table->address(1U) == 0,
            "throwing lifecycle load is rolled back even after mutation");
    }
    {
        Fixture fixture;
        const auto before = memory_copy(fixture.memory);
        const auto loaded = fixture.runtime.load(
            image(
                kModuleBeta,
                2U,
                {{kReferenceAlpha, kModuleAlpha, 0U}}),
            kBetaBase,
            fixture.cache);
        check(
            loaded.error == jfg::GeneratedOverlayError::dependency_unresolved &&
                memory_copy(fixture.memory) == before &&
                fixture.table->address(2U) == 0,
            "unresolved dependency rolls generated load back");
    }
}

void test_validation_overlap_and_token_boundaries() {
    Fixture fixture;
    auto malformed = image(kModuleAlpha, 1U);
    malformed.initialized_bytes.pop_back();
    check(
        fixture.runtime.load(std::move(malformed), kAlphaBase, fixture.cache).error ==
            jfg::GeneratedOverlayError::invalid_image,
        "image size must match generated metadata exactly");
    check(
        fixture.runtime.load(
                image(kModuleAlpha, 0U), kAlphaBase, fixture.cache).error ==
            jfg::GeneratedOverlayError::invalid_image,
        "non-overlay generated section cannot enter overlay lifecycle");
    check(
        fixture.runtime.load(
                image(kModuleAlpha, 1U),
                jfg::kGeneratedCachedGuestBase - 4U,
                fixture.cache).error ==
            jfg::GeneratedOverlayError::invalid_mapping,
        "mapping before cached guest memory is rejected");
    check(
        fixture.runtime.load(
                image(
                    kModuleAlpha,
                    1U,
                    {{kReferenceAlpha, kModuleAlpha, 0U}}),
                kAlphaBase,
                fixture.cache).error ==
            jfg::GeneratedOverlayError::invalid_dependency,
        "self dependency is rejected");
    check(
        fixture.runtime.load(
                image(
                    kModuleAlpha,
                    1U,
                    {{kReferenceAlpha, kModuleBeta, 2U}}),
                kAlphaBase,
                fixture.cache).error ==
            jfg::GeneratedOverlayError::invalid_dependency,
        "misaligned dependency offset is rejected");
    check(
        fixture.runtime.load(
                image(kModuleAlpha, 1U),
                jfg::kGeneratedCachedGuestBase,
                fixture.cache).error ==
            jfg::GeneratedOverlayError::overlapping_mapping,
        "overlay mapping cannot replace an initialized static section");

    fixture.table->metadata[1].data_size = 8U;
    check(
        fixture.runtime.load(
                image(kModuleAlpha, 1U), kAlphaBase, fixture.cache).error ==
            jfg::GeneratedOverlayError::invalid_section_metadata,
        "generated section metadata drift is rejected before staging");
    fixture.table->metadata[1].data_size = 4U;

    fixture.cache.expected_offset = 0x20U;
    const auto alpha = fixture.runtime.load(
        image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
    check(alpha.ok(), "token-boundary target loads");
    check(
        fixture.runtime.load(
                image(kModuleBeta, 2U),
                kAlphaBase + 8U,
                fixture.cache).error ==
            jfg::GeneratedOverlayError::overlapping_mapping,
        "active overlay mappings cannot overlap");
    check(
        fixture.runtime.unload({}) == jfg::GeneratedOverlayError::stale_token,
        "empty lifetime token is rejected");
    check(
        fixture.runtime.reload_same_base({}, fixture.cache).error ==
            jfg::GeneratedOverlayError::stale_token,
        "reload rejects an empty prior-lifetime token");

    fixture.table->set_address(1U, 0);
    check(
        fixture.runtime.lookup_function(alpha.token, 0U).error ==
            jfg::GeneratedOverlayError::runtime_poisoned,
        "out-of-band generated address mutation poisons lookup fail-closed");

    std::array<std::byte, kGuestSize> other_memory{};
    jfg::GeneratedOverlayRuntime other(other_memory);
    auto other_table = std::make_unique<SyntheticGeneratedTable>();
    check(other.install_table(std::move(other_table)).ok(),
          "second runtime installs an independent generated table");
    check(
        other.unload(alpha.token, fixture.cache) ==
            jfg::GeneratedOverlayError::cross_runtime_token,
        "lifetime token is bound to one runtime identity");
    check(
        fixture.runtime.reload_same_base({}, fixture.cache).error ==
            jfg::GeneratedOverlayError::runtime_poisoned,
        "poisoned address state takes precedence over later reload requests");
}

void test_callback_reentry_exception_and_poisoning() {
    {
        Fixture fixture;
        jfg::GeneratedOverlayError reentry = jfg::GeneratedOverlayError::none;
        fixture.cache.prepare_hook = [&]() {
            reentry = fixture.runtime.lookup_function({}, 0U).error;
        };
        fixture.cache.expected_offset = 0x20U;
        const auto loaded = fixture.runtime.load(
            image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
        check(loaded.ok() && reentry == jfg::GeneratedOverlayError::busy,
              "cache callback re-entry is rejected while load completes");

        fixture.table->lookup_hook = [&]() {
            reentry = fixture.runtime.unload(loaded.token, fixture.cache);
        };
        const auto function = fixture.runtime.lookup_function(loaded.token, 0U);
        check(function.ok() && reentry == jfg::GeneratedOverlayError::busy,
              "generated lookup callback re-entry is rejected");
        fixture.table->lookup_hook = {};

        fixture.table->lifecycle_hook =
            [&](const jfg::GeneratedSectionLifecycle operation, std::uint32_t) {
                if (operation == jfg::GeneratedSectionLifecycle::unload) {
                    reentry = fixture.runtime.lookup_function(loaded.token, 0U).error;
                }
            };
        check(fixture.runtime.unload(loaded.token, fixture.cache) ==
                  jfg::GeneratedOverlayError::none &&
                  reentry == jfg::GeneratedOverlayError::busy,
              "generated lifecycle callback re-entry is rejected");
    }
    {
        Fixture fixture;
        fixture.cache.expected_offset = 0x20U;
        const auto loaded = fixture.runtime.load(
            image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
        fixture.table->throw_during_lookup = true;
        check(
            fixture.runtime.lookup_function(loaded.token, 0U).error ==
                jfg::GeneratedOverlayError::callback_exception,
            "generated lookup exception is sanitized");
        fixture.table->throw_during_lookup = false;
        check(fixture.runtime.lookup_function(loaded.token, 0U).ok(),
              "lookup exception does not corrupt active lifetime");

        fixture.table->throw_during_unload = true;
        fixture.table->mutate_before_lifecycle_failure = true;
        check(
            fixture.runtime.unload(loaded.token, fixture.cache) ==
                    jfg::GeneratedOverlayError::callback_exception &&
                fixture.table->address(1U) ==
                    static_cast<std::int32_t>(kAlphaBase) &&
                fixture.runtime.lookup_function(loaded.token, 0U).ok(),
            "throwing unload is restored transactionally");
        fixture.table->throw_during_unload = false;
        fixture.table->mutate_before_lifecycle_failure = false;
        check(fixture.runtime.unload(loaded.token, fixture.cache) ==
                  jfg::GeneratedOverlayError::none,
              "restored lifetime can later unload");
    }
    {
        Fixture fixture;
        fixture.cache.expected_offset = 0x20U;
        const auto loaded = fixture.runtime.load(
            image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
        fixture.table->lifecycle_unload_ok = false;
        check(
            fixture.runtime.unload(loaded.token, fixture.cache) ==
                    jfg::GeneratedOverlayError::section_unload_failed &&
                fixture.runtime.lookup_function(loaded.token, 0U).ok(),
            "non-mutating unload rejection keeps the lifetime active");
        fixture.table->lifecycle_unload_ok = true;
        check(fixture.runtime.unload(loaded.token, fixture.cache) ==
                  jfg::GeneratedOverlayError::none,
              "lifetime remains unloadable after rejected unload");
    }
    {
        Fixture fixture;
        const auto before = memory_copy(fixture.memory);
        fixture.table->lifecycle_load_ok = false;
        fixture.table->mutate_before_lifecycle_failure = true;
        fixture.table->fail_rollback_unload = true;
        const auto loaded = fixture.runtime.load(
            image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
        check(
            loaded.error == jfg::GeneratedOverlayError::runtime_poisoned &&
                memory_copy(fixture.memory) == before,
            "unrestorable generated lifecycle poisons runtime before memory commit");
        check(
            fixture.runtime.load(
                    image(kModuleBeta, 2U), kBetaBase, fixture.cache).error ==
                jfg::GeneratedOverlayError::runtime_poisoned,
            "poisoned runtime rejects subsequent work");
    }
}

void test_event_order_and_error_messages() {
    Fixture fixture;
    fixture.events.clear();
    fixture.cache.expected_offset = 0x20U;
    const auto loaded = fixture.runtime.load(
        image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
    const std::vector<std::string> expected{
        "relocation-count",
        "relocation-count",
        "lifecycle-load",
        "relocation-apply",
        "relocation-count",
        "cache-prepare",
        "cache-commit",
    };
    check(loaded.ok() && fixture.events == expected,
          "load order is lifecycle, checked relocate, cache, then publish");
    check(std::string_view(jfg::generated_overlay_error_message(
              jfg::GeneratedOverlayError::dependency_invalidated)) ==
              "overlay dependency binding is invalidated" &&
              std::string_view(jfg::generated_overlay_error_message(
                  static_cast<jfg::GeneratedOverlayError>(999))) ==
                  "unknown generated overlay runtime error",
          "generated overlay errors have stable sanitized messages");
    check(fixture.runtime.unload(loaded.token, fixture.cache) ==
              jfg::GeneratedOverlayError::none,
          "event-order fixture unloads");
}

void test_custom_relocation_metadata_and_formulas() {
    Fixture fixture(true);
    fixture.table->relocation_counts[1] = 0U;
    fixture.table->relocation_site_values[1].clear();
    fixture.table->relocation_descriptor_values[1].clear();
    auto custom = image(kModuleAlpha, 1U);
    custom.initialized_bytes.assign(16U, std::byte{0});
    write_be32(custom.initialized_bytes, 4U, 0x08000001U);
    write_be32(custom.initialized_bytes, 8U, 0x3C010000U);
    write_be32(custom.initialized_bytes, 12U, 0x34210000U);
    custom.custom_relocations = {
        {0U, jfg::CustomOverlayRelocationSource::external,
         jfg::CustomOverlayRelocationPatch::full_word, 55U, 0},
        {4U, jfg::CustomOverlayRelocationSource::local_jump,
         jfg::CustomOverlayRelocationPatch::jump_target, 0U, 0},
        {8U, jfg::CustomOverlayRelocationSource::external_data,
         jfg::CustomOverlayRelocationPatch::hi16, 66U, 0},
        {12U, jfg::CustomOverlayRelocationSource::external_data,
         jfg::CustomOverlayRelocationPatch::lo16, 66U, 0},
    };
    custom.custom_bindings = {
        {55U, kModuleAlpha, jfg::kNoGeneratedStaticSection, 0U},
        {66U, 0U, 0U, 0U},
    };
    const auto loaded = fixture.runtime.load(std::move(custom), kAlphaBase, fixture.cache);
    check(loaded.ok(), "custom relocation accepts validated self and local bindings");
    const auto mapped = std::span<const std::byte>(fixture.memory).subspan(0x20U, 16U);
    const auto custom_0 = read_be32(mapped, 0U);
    const auto custom_4 = read_be32(mapped, 4U);
    const auto custom_8 = read_be32(mapped, 8U);
    const auto custom_12 = read_be32(mapped, 12U);
    check(custom_0 == kAlphaBase && custom_4 == 0x08000009U &&
              custom_8 == 0x3C018000U && custom_12 == 0x34210000U,
          "custom records preserve authoritative order and all patch formulas use BE words");

    Fixture overlap;
    auto colliding = image(kModuleAlpha, 1U);
    colliding.custom_relocations = {{0U,
        jfg::CustomOverlayRelocationSource::local_offset,
        jfg::CustomOverlayRelocationPatch::full_word, 4U, 0}};
    check(overlap.runtime.load(std::move(colliding), kAlphaBase, overlap.cache).error ==
              jfg::GeneratedOverlayError::custom_relocation_overlap,
          "custom sites cannot overlap declared generated R32 sites");

    Fixture swapped_sites;
    const auto before_swapped_sites = memory_copy(swapped_sites.memory);
    swapped_sites.table->swap_relocation_sites_after_first_read = true;
    auto changed_after_validation = image(kModuleAlpha, 1U);
    changed_after_validation.custom_relocations = {{4U,
        jfg::CustomOverlayRelocationSource::local_offset,
        jfg::CustomOverlayRelocationPatch::full_word, 4U, 0}};
    const auto changed_result = swapped_sites.runtime.load(
        std::move(changed_after_validation), kAlphaBase, swapped_sites.cache);
    check(changed_result.error == jfg::GeneratedOverlayError::relocation_site_mismatch &&
              memory_copy(swapped_sites.memory) == before_swapped_sites &&
              swapped_sites.table->address(1U) == 0 &&
              swapped_sites.table->relocation_apply_calls == 0U,
          "same-count generated site swaps fail before relocation or guest commit");

    Fixture malformed(true, true);
    malformed.table->relocation_counts[1] = 0U;
    malformed.table->relocation_site_values[1].clear();
    malformed.table->relocation_descriptor_values[1].clear();
    auto nonadjacent = image(kModuleAlpha, 1U);
    nonadjacent.initialized_bytes.assign(16U, std::byte{0});
    nonadjacent.custom_relocations = {
        {0U, jfg::CustomOverlayRelocationSource::local_offset,
         jfg::CustomOverlayRelocationPatch::hi16, 4U, 0},
        {4U, jfg::CustomOverlayRelocationSource::local_offset,
         jfg::CustomOverlayRelocationPatch::full_word, 4U, 0},
        {8U, jfg::CustomOverlayRelocationSource::local_offset,
         jfg::CustomOverlayRelocationPatch::lo16, 4U, 0},
    };
    check(malformed.runtime.load(std::move(nonadjacent), kAlphaBase, malformed.cache).error ==
              jfg::GeneratedOverlayError::custom_relocation_failed,
          "non-adjacent HI16 and LO16 records fail before guest-memory commit");

    Fixture bad_binding;
    auto mismatch = image(kModuleAlpha, 1U);
    mismatch.custom_relocations = {{4U,
        jfg::CustomOverlayRelocationSource::external,
        jfg::CustomOverlayRelocationPatch::full_word, 77U, 0}};
    mismatch.custom_bindings = {{77U, kModuleAlpha, 0U, 0U}};
    check(bad_binding.runtime.load(std::move(mismatch), kAlphaBase, bad_binding.cache).error ==
              jfg::GeneratedOverlayError::invalid_custom_binding,
          "custom bindings cannot name both module and static mappings");

    Fixture cross_kind;
    auto mixed = image(kModuleAlpha, 1U);
    mixed.custom_relocations = {
        {4U, jfg::CustomOverlayRelocationSource::external,
         jfg::CustomOverlayRelocationPatch::full_word, 88U, 0},
        {8U, jfg::CustomOverlayRelocationSource::external_data,
         jfg::CustomOverlayRelocationPatch::full_word, 88U, 0},
    };
    mixed.custom_bindings = {{88U, 0U, 0U, 1U}};
    const auto mixed_loaded = cross_kind.runtime.load(
        std::move(mixed), kAlphaBase, cross_kind.cache);
    check(mixed_loaded.ok(),
          "text and data external source forms may share one symbol binding");
    check(cross_kind.runtime.unload(mixed_loaded.token, cross_kind.cache) ==
              jfg::GeneratedOverlayError::none,
          "shared external source-form fixture unloads");

    Fixture unaligned;
    auto byte_target = image(kModuleAlpha, 1U);
    byte_target.custom_relocations = {{4U,
        jfg::CustomOverlayRelocationSource::external,
        jfg::CustomOverlayRelocationPatch::full_word, 99U, 0}};
    byte_target.custom_bindings = {{99U, 0U, 0U, 1U}};
    const auto byte_target_loaded = unaligned.runtime.load(
        std::move(byte_target), kAlphaBase, unaligned.cache);
    check(byte_target_loaded.ok(),
          "external data symbols may have byte-aligned target offsets");
    check(unaligned.runtime.unload(byte_target_loaded.token, unaligned.cache) ==
              jfg::GeneratedOverlayError::none,
          "byte-aligned external target fixture unloads");

    Fixture capped;
    auto too_many = image(kModuleAlpha, 1U);
    too_many.custom_relocations.resize(
        jfg::kMaximumCustomOverlayRelocationsPerSection + 1U);
    check(capped.runtime.load(std::move(too_many), kAlphaBase, capped.cache).error ==
              jfg::GeneratedOverlayError::invalid_custom_relocation,
          "custom relocation hard cap is enforced before lifecycle allocation");
}

void test_custom_external_rebind_transaction() {
    Fixture fixture;
    fixture.table->relocation_counts[1] = 0U;
    fixture.table->relocation_counts[2] = 0U;
    fixture.table->relocation_site_values[1].clear();
    fixture.table->relocation_site_values[2].clear();
    fixture.table->relocation_descriptor_values[1].clear();
    fixture.table->relocation_descriptor_values[2].clear();
    const auto provider = fixture.runtime.load(
        image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
    check(provider.ok(), "custom-binding provider loads");
    auto dependent_image = image(kModuleBeta, 2U);
    dependent_image.custom_relocations = {{4U,
        jfg::CustomOverlayRelocationSource::external,
        jfg::CustomOverlayRelocationPatch::full_word, 600U, 0}};
    dependent_image.custom_bindings = {
        {600U, kModuleAlpha, jfg::kNoGeneratedStaticSection, 0U}};
    const auto dependent = fixture.runtime.load(
        std::move(dependent_image), kBetaBase, fixture.cache);
    check(dependent.ok() &&
              read_be32(std::span<const std::byte>(fixture.memory).subspan(0x40U), 4U) ==
                  kAlphaBase,
          "external custom site resolves only through an active declared module");
    check(fixture.runtime.unload(provider.token, fixture.cache) ==
              jfg::GeneratedOverlayError::none,
          "custom-binding provider unloads");
    check(fixture.runtime.lookup_function(dependent.token, 0U).error ==
              jfg::GeneratedOverlayError::dependency_invalidated,
          "provider unload invalidates custom-binding dependents");
    const auto before_failed_rebind = memory_copy(fixture.memory);
    fixture.cache.prepare_ok = false;
    check(fixture.runtime.reload_same_base(provider.token, fixture.cache).error ==
              jfg::GeneratedOverlayError::cache_invalidation_rejected &&
              memory_copy(fixture.memory) == before_failed_rebind,
          "cache preparation failure leaves every custom dependent byte unchanged");
    fixture.cache.prepare_ok = true;
    const auto reloaded = fixture.runtime.reload_same_base(provider.token, fixture.cache);
    check(reloaded.ok() && fixture.runtime.lookup_function(dependent.token, 0U).ok() &&
              read_be32(std::span<const std::byte>(fixture.memory).subspan(0x40U), 4U) ==
                  kAlphaBase,
          "same-base reload atomically rebinds pristine custom sites deterministically");
}

void test_custom_multi_provider_rebind_lifecycle() {
    Fixture fixture;
    for (const std::uint32_t section : {1U, 2U, 3U}) {
        fixture.table->relocation_counts[section] = 0U;
        fixture.table->relocation_site_values[section].clear();
        fixture.table->relocation_descriptor_values[section].clear();
    }
    const auto alpha = fixture.runtime.load(
        image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
    const auto beta = fixture.runtime.load(
        image(kModuleBeta, 2U), kBetaBase, fixture.cache);
    auto dependent_image = image(kModuleGamma, 3U);
    dependent_image.custom_relocations = {
        {0U, jfg::CustomOverlayRelocationSource::external,
         jfg::CustomOverlayRelocationPatch::full_word, 700U, 0},
        {4U, jfg::CustomOverlayRelocationSource::external,
         jfg::CustomOverlayRelocationPatch::full_word, 701U, 0},
    };
    dependent_image.custom_bindings = {
        {700U, kModuleAlpha, jfg::kNoGeneratedStaticSection, 0U},
        {701U, kModuleBeta, jfg::kNoGeneratedStaticSection, 0U},
    };
    const auto dependent = fixture.runtime.load(
        std::move(dependent_image), kGammaBase, fixture.cache);
    check(alpha.ok() && beta.ok() && dependent.ok(),
          "two-provider custom dependent loads with both providers active");
    check(fixture.runtime.unload(alpha.token, fixture.cache) ==
                  jfg::GeneratedOverlayError::none &&
              fixture.runtime.unload(beta.token, fixture.cache) ==
                  jfg::GeneratedOverlayError::none,
          "both custom providers can unload while the dependent remains registered");

    const auto alpha_reloaded = fixture.runtime.reload_same_base(alpha.token, fixture.cache);
    check(alpha_reloaded.ok() &&
              fixture.runtime.lookup_function(dependent.token, 0U).error ==
                  jfg::GeneratedOverlayError::dependency_invalidated,
          "first custom provider reload succeeds but leaves a multi-provider dependent blocked");
    const auto beta_reloaded = fixture.runtime.reload_same_base(beta.token, fixture.cache);
    const auto dependent_bytes = std::span<const std::byte>(fixture.memory).subspan(0x60U);
    check(beta_reloaded.ok() && fixture.runtime.lookup_function(dependent.token, 0U).ok() &&
              read_be32(dependent_bytes, 0U) == kAlphaBase &&
              read_be32(dependent_bytes, 4U) == kBetaBase,
          "second custom provider reload atomically restores every provider relocation");
}

void test_transitive_unload_rebind_and_capability_revocation() {
    Fixture fixture;
    fixture.table->relocation_counts[1] = 0U;
    fixture.table->relocation_site_values[1].clear();
    fixture.table->relocation_descriptor_values[1].clear();
    fixture.table->relocation_counts[2] = 0U;
    fixture.table->relocation_site_values[2].clear();
    fixture.table->relocation_descriptor_values[2].clear();
    fixture.table->relocation_counts[3] = 1U;
    fixture.table->relocation_site_values[3] = {0U};
    fixture.table->relocation_descriptor_values[3] = {{0U, 2U, 0U}};

    const auto alpha = fixture.runtime.load(
        image(kModuleAlpha, 1U), kAlphaBase, fixture.cache);
    auto beta_image = image(kModuleBeta, 2U);
    beta_image.custom_relocations = {{
        4U,
        jfg::CustomOverlayRelocationSource::external,
        jfg::CustomOverlayRelocationPatch::full_word,
        900U,
        0,
    }};
    beta_image.custom_bindings = {{
        900U,
        kModuleAlpha,
        jfg::kNoGeneratedStaticSection,
        0U,
    }};
    const auto beta = fixture.runtime.load(
        std::move(beta_image), kBetaBase, fixture.cache);
    const auto gamma = fixture.runtime.load(
        image(
            kModuleGamma,
            3U,
            {{kReferenceAlpha, kModuleBeta, 0U}}),
        kGammaBase,
        fixture.cache);
    const auto beta_callable = fixture.runtime.lookup_function(beta.token, 0U);
    const auto gamma_callable = fixture.runtime.lookup_function(gamma.token, 0U);
    check(alpha.ok() && beta.ok() && gamma.ok() && beta_callable.ok() &&
              gamma_callable.ok(),
          "multi-hop custom/R32/function closure loads");
    check(
        read_be32(
            std::span<const std::byte>(fixture.memory).subspan(0x40U), 4U) ==
                kAlphaBase &&
            read_be32(
                std::span<const std::byte>(fixture.memory).subspan(0x60U), 0U) ==
                kBetaBase,
        "multi-hop relocation sites initially bind in dependency order");

    const auto before_rejected_unload = memory_copy(fixture.memory);
    const std::size_t aborts_before = fixture.cache.abort_calls;
    fixture.cache.reject_prepare_call = fixture.cache.prepare_calls + 2U;
    check(
        fixture.runtime.unload(alpha.token, fixture.cache) ==
                jfg::GeneratedOverlayError::cache_invalidation_rejected &&
            fixture.cache.abort_calls == aborts_before + 2U &&
            memory_copy(fixture.memory) == before_rejected_unload &&
            fixture.runtime.lookup_function(alpha.token, 0U).ok() &&
            invokes_with_result(gamma_callable.function, fixture.memory, 44U),
        "later cache-prepare rejection aborts prior ranges and restores admission");
    fixture.cache.reject_prepare_call = 0U;

    check(
        fixture.runtime.unload(alpha.token, fixture.cache) ==
            jfg::GeneratedOverlayError::none,
        "root provider unload commits the complete dependent closure");
    recomp_context stale_context{};
    check(
        beta_callable.function.invoke(
            reinterpret_cast<std::uint8_t*>(fixture.memory.data()),
            &stale_context) == jfg::GeneratedOverlayError::stale_token &&
            gamma_callable.function.invoke(
                reinterpret_cast<std::uint8_t*>(fixture.memory.data()),
                &stale_context) == jfg::GeneratedOverlayError::stale_token &&
            fixture.runtime.lookup_function(beta.token, 0U).error ==
                jfg::GeneratedOverlayError::dependency_invalidated &&
            fixture.runtime.lookup_function(gamma.token, 0U).error ==
                jfg::GeneratedOverlayError::dependency_invalidated,
        "provider unload permanently revokes all previously issued closure handles");
    check(
        read_be32(
            std::span<const std::byte>(fixture.memory).subspan(0x40U), 4U) ==
                0x5A5A5A5AU &&
            read_be32(
                std::span<const std::byte>(fixture.memory).subspan(0x60U), 0U) ==
                0x5A5A5A5AU,
        "unload scrubs custom and generated R32 sites to pristine words");

    const auto alpha_reloaded = fixture.runtime.reload_same_base(
        alpha.token, fixture.cache);
    check(
        alpha_reloaded.ok() && fixture.runtime.lookup_function(beta.token, 0U).ok() &&
            fixture.runtime.lookup_function(gamma.token, 0U).ok() &&
            read_be32(
                std::span<const std::byte>(fixture.memory).subspan(0x40U), 4U) ==
                kAlphaBase &&
            read_be32(
                std::span<const std::byte>(fixture.memory).subspan(0x60U), 0U) ==
                kBetaBase,
        "provider reload cascades custom, R32, and function rebinds transitively");

    const auto owner_capability = fixture.runtime.resolve_dependency(
        gamma.token, kReferenceAlpha);
    check(owner_capability.ok(), "owner-bound dependency capability resolves");
    check(
        fixture.runtime.unload(gamma.token, fixture.cache) ==
                jfg::GeneratedOverlayError::none &&
            owner_capability.function.invoke(
                reinterpret_cast<std::uint8_t*>(fixture.memory.data()),
                &stale_context) == jfg::GeneratedOverlayError::stale_token &&
            fixture.runtime.lookup_function(beta.token, 0U).ok(),
        "owner unload revokes its capability while the provider remains executable");
}

}  // namespace

int main() {
    test_table_installation_contract();
    test_transactional_load_lookup_unload_reload();
    test_unload_quiesces_active_invocation();
    test_unload_quiescence_allows_nested_dispatch();
    test_unload_preserves_inflight_dependent_data();
    test_lookup_target_mutation_poisoning();
    test_dependency_invalidation_and_rebind();
    test_generated_r32_provider_lifecycle();
    test_generated_r32_descriptor_closure();
    test_generated_descriptor_callback_exceptions();
    test_generated_target_address_boundaries();
    test_transactional_failure_paths();
    test_validation_overlap_and_token_boundaries();
    test_callback_reentry_exception_and_poisoning();
    test_event_order_and_error_messages();
    test_custom_relocation_metadata_and_formulas();
    test_custom_external_rebind_transaction();
    test_custom_multi_provider_rebind_lifecycle();
    test_transitive_unload_rebind_and_capability_revocation();

    if (failures != 0) {
        std::cerr << failures << " generated overlay runtime test(s) failed\n";
        return 1;
    }
    std::cout << "generated overlay runtime tests passed\n";
    return 0;
}
