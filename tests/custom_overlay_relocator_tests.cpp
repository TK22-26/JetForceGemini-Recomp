#include "jfg/runtime/custom_overlay_relocator.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <span>
#include <stdexcept>
#include <string_view>
#include <vector>

namespace {

int failures = 0;

void check(const bool condition, const std::string_view message) {
    if (!condition) {
        ++failures;
        std::cerr << "FAIL: " << message << '\n';
    }
}

void put_be32(
    const std::span<std::byte> image,
    const std::size_t offset,
    const std::uint32_t value) {
    image[offset] = static_cast<std::byte>(value >> 24U);
    image[offset + 1U] = static_cast<std::byte>(value >> 16U);
    image[offset + 2U] = static_cast<std::byte>(value >> 8U);
    image[offset + 3U] = static_cast<std::byte>(value);
}

[[nodiscard]] std::uint32_t get_be32(
    const std::span<const std::byte> image,
    const std::size_t offset) {
    return (std::to_integer<std::uint32_t>(image[offset]) << 24U) |
        (std::to_integer<std::uint32_t>(image[offset + 1U]) << 16U) |
        (std::to_integer<std::uint32_t>(image[offset + 2U]) << 8U) |
        std::to_integer<std::uint32_t>(image[offset + 3U]);
}

class Resolver final : public jfg::CustomOverlayRelocationResolver {
public:
    bool external_loaded = true;
    bool throw_during_external_resolution = false;
    std::uint32_t external = 0x12345678U;
    std::uint32_t main = 0xABCDEF02U;

    [[nodiscard]] bool resolve_external(
        const jfg::CustomOverlayRelocationSource,
        std::uint32_t,
        const std::uint32_t target,
        std::uint32_t& output) override {
        if (throw_during_external_resolution) {
            throw std::runtime_error("synthetic resolver failure");
        }
        if (!external_loaded) {
            return false;
        }
        output = target == 4U ? data_external : external;
        return true;
    }

    [[nodiscard]] bool resolve_local(
        const jfg::CustomOverlayRelocationSource,
        const std::uint32_t,
        const std::uint32_t target,
        std::uint32_t& output) override {
        output = base + target;
        return true;
    }

    std::uint32_t base = 0x80001000U;
    std::uint32_t data_external = 0xABCDEF02U;
};

[[nodiscard]] jfg::CustomOverlayRelocationSection section() {
    return {
        .section = 7U,
        .base = 0x80001000U,
        .text_size = 28U,
        .initialized_size = 32U,
        .mapped_size = 48U,
    };
}

void test_all_classes_and_formulas() {
    std::array<std::byte, 48U> image{};
    put_be32(image, 8U, 0x08000004U);
    put_be32(image, 16U, 0x08000000U);
    put_be32(image, 20U, 0x3C010000U);
    put_be32(image, 24U, 0x34210000U);
    put_be32(image, 28U, 0x34020000U);
    Resolver resolver;
    const std::array records{
        jfg::CustomOverlayRelocationRecord{0U, jfg::CustomOverlayRelocationSource::external, jfg::CustomOverlayRelocationPatch::full_word, 1U, 0},
        jfg::CustomOverlayRelocationRecord{4U, jfg::CustomOverlayRelocationSource::local_offset, jfg::CustomOverlayRelocationPatch::full_word, 12U, 0},
        jfg::CustomOverlayRelocationRecord{8U, jfg::CustomOverlayRelocationSource::local_jump, jfg::CustomOverlayRelocationPatch::full_word, 0U, 0},
        jfg::CustomOverlayRelocationRecord{12U, jfg::CustomOverlayRelocationSource::external, jfg::CustomOverlayRelocationPatch::full_word, 4U, 0},
        jfg::CustomOverlayRelocationRecord{16U, jfg::CustomOverlayRelocationSource::local_offset, jfg::CustomOverlayRelocationPatch::jump_target, 20U, 0},
        jfg::CustomOverlayRelocationRecord{20U, jfg::CustomOverlayRelocationSource::external, jfg::CustomOverlayRelocationPatch::hi16, 3U, 0x8000},
        jfg::CustomOverlayRelocationRecord{24U, jfg::CustomOverlayRelocationSource::external, jfg::CustomOverlayRelocationPatch::lo16, 3U, 0x8000},
        jfg::CustomOverlayRelocationRecord{28U, jfg::CustomOverlayRelocationSource::external_data, jfg::CustomOverlayRelocationPatch::lo16, 4U, 0},
    };

    const auto result = jfg::apply_custom_overlay_relocations(
        image, section(), records, resolver);
    check(result.applied(), "all relocation classes apply");
    check(get_be32(image, 0U) == 0x12345678U, "external full word");
    check(get_be32(image, 4U) == 0x8000100CU, "local offset full word");
    check(get_be32(image, 8U) == 0x80001010U, "local jump full word");
    check(get_be32(image, 12U) == 0xABCDEF02U, "external data target full word");
    check(get_be32(image, 16U) == 0x08000405U, "jump target preserves opcode and encodes index");
    check(get_be32(image, 20U) == 0x3C011235U, "HI16 carries bit fifteen");
    check(get_be32(image, 24U) == 0x3421D678U, "paired LO16 writes low bits");
    check(get_be32(image, 28U) == 0x3402EF02U, "standalone LO16 is supported");
    check(result.audit.applied_total == records.size(), "audit records all writes");
    check(result.audit.full_word_count == 4U &&
              result.audit.jump_target_count == 1U &&
              result.audit.hi16_count == 1U && result.audit.lo16_count == 2U,
          "audit class counts are exact");
}

void test_no_partial_mutation_and_reload() {
    std::array<std::byte, 48U> image{};
    const auto original = image;
    Resolver resolver;
    resolver.external_loaded = false;
    const std::array late_failure{
        jfg::CustomOverlayRelocationRecord{0U, jfg::CustomOverlayRelocationSource::external, jfg::CustomOverlayRelocationPatch::full_word, 4U, 0},
        jfg::CustomOverlayRelocationRecord{4U, jfg::CustomOverlayRelocationSource::external, jfg::CustomOverlayRelocationPatch::full_word, 0U, 0},
    };
    auto result = jfg::apply_custom_overlay_relocations(
        image, section(), late_failure, resolver);
    check(result.error == jfg::CustomOverlayRelocationError::dependency_unresolved,
          "unloaded dependency fails");
    check(image == original, "late failure does not partially mutate");

    resolver.external_loaded = true;
    resolver.external = 0x81234560U;
    result = jfg::apply_custom_overlay_relocations(
        image, section(), std::span(late_failure).last(1U), resolver);
    check(result.applied() && get_be32(image, 4U) == 0x81234560U,
          "dependency reload resolves fresh target");

    const auto before_throw = image;
    resolver.throw_during_external_resolution = true;
    const std::array throwing{
        jfg::CustomOverlayRelocationRecord{
            0U, jfg::CustomOverlayRelocationSource::external,
            jfg::CustomOverlayRelocationPatch::full_word, 4U, 0},
    };
    result = jfg::apply_custom_overlay_relocations(
        image, section(), throwing, resolver);
    check(result.error == jfg::CustomOverlayRelocationError::callback_exception,
          "throwing resolver becomes a fail-closed result");
    check(image == before_throw,
          "throwing resolver leaves the image byte-for-byte unchanged");
}

void test_pairs_determinism_and_errors() {
    Resolver resolver;
    const jfg::CustomOverlayRelocationRecord high{
        0U, jfg::CustomOverlayRelocationSource::external,
        jfg::CustomOverlayRelocationPatch::hi16, 0U, 0};
    const jfg::CustomOverlayRelocationRecord low{
        4U, jfg::CustomOverlayRelocationSource::external,
        jfg::CustomOverlayRelocationPatch::lo16, 0U, 0};
    std::array<std::byte, 48U> one{};
    std::array<std::byte, 48U> two{};
    const std::array pair{high, low};
    const auto first = jfg::apply_custom_overlay_relocations(one, section(), pair, resolver);
    const auto second = jfg::apply_custom_overlay_relocations(two, section(), pair, resolver);
    check(first.applied() && second.applied() && one == two &&
              first.audit.commitment == second.audit.commitment,
          "identical inputs have deterministic output and commitment");

    const std::array missing{high};
    const auto before_missing = one;
    check(jfg::apply_custom_overlay_relocations(one, section(), missing, resolver).error ==
              jfg::CustomOverlayRelocationError::malformed_pair,
          "HI16 requires adjacent LO16");
    check(one == before_missing, "malformed pair is atomic");
    const std::array non_adjacent{
        high,
        jfg::CustomOverlayRelocationRecord{12U, jfg::CustomOverlayRelocationSource::external, jfg::CustomOverlayRelocationPatch::lo16, 0U, 0}};
    std::array<std::byte, 48U> non_adjacent_image{};
    const auto non_adjacent_result = jfg::apply_custom_overlay_relocations(
        non_adjacent_image, section(), non_adjacent, resolver);
    check(non_adjacent_result.applied() &&
              get_be32(non_adjacent_image, 0U) == 0x00001234U &&
              get_be32(non_adjacent_image, 12U) == 0x00005678U,
          "adjacent records may have non-adjacent patch sites");
    const std::array duplicate{low, low};
    check(jfg::apply_custom_overlay_relocations(one, section(), duplicate, resolver).error ==
              jfg::CustomOverlayRelocationError::duplicate_site,
          "duplicate sites reject");
    const std::array unordered{low, high};
    check(jfg::apply_custom_overlay_relocations(one, section(), unordered, resolver).error ==
              jfg::CustomOverlayRelocationError::malformed_pair,
          "a trailing HI16 without its following LO16 rejects");
    const std::array standalone_then_pair{
        jfg::CustomOverlayRelocationRecord{0U, jfg::CustomOverlayRelocationSource::external, jfg::CustomOverlayRelocationPatch::lo16, 0U, 0},
        jfg::CustomOverlayRelocationRecord{4U, jfg::CustomOverlayRelocationSource::external, jfg::CustomOverlayRelocationPatch::hi16, 0U, 0},
        jfg::CustomOverlayRelocationRecord{12U, jfg::CustomOverlayRelocationSource::external, jfg::CustomOverlayRelocationPatch::lo16, 0U, 0}};
    std::array<std::byte, 48U> standalone_image{};
    check(jfg::apply_custom_overlay_relocations(
              standalone_image, section(), standalone_then_pair, resolver).applied(),
          "a standalone LO16 may precede a later HI16/LO16 pair");
    const std::array unaligned{jfg::CustomOverlayRelocationRecord{2U, jfg::CustomOverlayRelocationSource::external, jfg::CustomOverlayRelocationPatch::lo16, 0U, 0}};
    check(jfg::apply_custom_overlay_relocations(one, section(), unaligned, resolver).error ==
              jfg::CustomOverlayRelocationError::unaligned_site,
          "unaligned site rejects");
    const std::array bounds{jfg::CustomOverlayRelocationRecord{32U, jfg::CustomOverlayRelocationSource::external, jfg::CustomOverlayRelocationPatch::lo16, 0U, 0}};
    check(jfg::apply_custom_overlay_relocations(one, section(), bounds, resolver).error ==
              jfg::CustomOverlayRelocationError::site_out_of_bounds,
          "site bounds reject");
    const std::array bad_local{jfg::CustomOverlayRelocationRecord{0U, jfg::CustomOverlayRelocationSource::local_offset, jfg::CustomOverlayRelocationPatch::full_word, 48U, 0}};
    check(jfg::apply_custom_overlay_relocations(one, section(), bad_local, resolver).error ==
              jfg::CustomOverlayRelocationError::target_out_of_bounds,
          "local extent rejects");
    const std::array bad_local_jump_field{jfg::CustomOverlayRelocationRecord{0U, jfg::CustomOverlayRelocationSource::local_jump, jfg::CustomOverlayRelocationPatch::full_word, 4U, 0}};
    check(jfg::apply_custom_overlay_relocations(one, section(), bad_local_jump_field, resolver).error ==
              jfg::CustomOverlayRelocationError::target_out_of_bounds,
          "local jump rejects an adapter-supplied target");
    std::array<std::byte, 48U> distant_jump_image{};
    put_be32(distant_jump_image, 0U, 0x0C100000U);
    const std::array distant_jump{jfg::CustomOverlayRelocationRecord{0U, jfg::CustomOverlayRelocationSource::local_jump, jfg::CustomOverlayRelocationPatch::full_word, 0U, 0}};
    check(jfg::apply_custom_overlay_relocations(
              distant_jump_image, section(), distant_jump, resolver).applied() &&
              get_be32(distant_jump_image, 0U) == 0x80401000U,
          "local jump preserves the encoded 26-bit target beyond module extent");
    const std::array data_source_in_text{jfg::CustomOverlayRelocationRecord{0U, jfg::CustomOverlayRelocationSource::external_data, jfg::CustomOverlayRelocationPatch::full_word, 4U, 0}};
    check(jfg::apply_custom_overlay_relocations(one, section(), data_source_in_text, resolver).error ==
              jfg::CustomOverlayRelocationError::site_out_of_bounds,
          "data-source patch rejects a text site");
    const std::array instruction_in_data{jfg::CustomOverlayRelocationRecord{28U, jfg::CustomOverlayRelocationSource::external, jfg::CustomOverlayRelocationPatch::jump_target, 4U, 0}};
    check(jfg::apply_custom_overlay_relocations(one, section(), instruction_in_data, resolver).error ==
              jfg::CustomOverlayRelocationError::site_out_of_bounds,
          "instruction patch rejects a data site without the data source class");
    const std::array invalid_source{jfg::CustomOverlayRelocationRecord{0U, static_cast<jfg::CustomOverlayRelocationSource>(9U), jfg::CustomOverlayRelocationPatch::full_word, 0U, 0}};
    check(jfg::apply_custom_overlay_relocations(one, section(), invalid_source, resolver).error ==
              jfg::CustomOverlayRelocationError::invalid_source_type,
          "invalid source rejects");
    const std::array invalid_patch{jfg::CustomOverlayRelocationRecord{0U, jfg::CustomOverlayRelocationSource::external, static_cast<jfg::CustomOverlayRelocationPatch>(9U), 0U, 0}};
    check(jfg::apply_custom_overlay_relocations(one, section(), invalid_patch, resolver).error ==
              jfg::CustomOverlayRelocationError::invalid_patch_type,
          "invalid patch rejects");

    resolver.data_external = std::numeric_limits<std::uint32_t>::max();
    const std::array overflow{jfg::CustomOverlayRelocationRecord{0U, jfg::CustomOverlayRelocationSource::external, jfg::CustomOverlayRelocationPatch::full_word, 4U, 1}};
    check(jfg::apply_custom_overlay_relocations(one, section(), overflow, resolver).error ==
              jfg::CustomOverlayRelocationError::address_overflow,
          "address overflow rejects");
    resolver.data_external = 0x90000000U;
    const std::array bad_jump{jfg::CustomOverlayRelocationRecord{0U, jfg::CustomOverlayRelocationSource::external, jfg::CustomOverlayRelocationPatch::jump_target, 4U, 0}};
    check(jfg::apply_custom_overlay_relocations(one, section(), bad_jump, resolver).error ==
              jfg::CustomOverlayRelocationError::invalid_jump_target,
          "jump target region rejects");
}

} // namespace

int main() {
    test_all_classes_and_formulas();
    test_no_partial_mutation_and_reload();
    test_pairs_determinism_and_errors();
    return failures == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}
