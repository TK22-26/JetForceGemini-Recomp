#include "jfg/runtime/generated_overlay_runtime.hpp"
#include "recomp.h"

#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>

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

void do_break(std::uint32_t vram);

namespace {

std::int32_t* fixture_section_addresses = nullptr;
std::size_t section_capacity = 0U;

void main_function(std::uint8_t*, recomp_context*) {}
void target_function(std::uint8_t*, recomp_context*) {}
void dependent_function(std::uint8_t*, recomp_context*) {
#if defined(JFG_G2_OVERLAY_FIXTURE_UNSAFE_FIRST_BODY) || \
    defined(JFG_G2_OVERLAY_FIXTURE_STACK_FIRST_BODY)
    std::abort();
#elif defined(JFG_G2_OVERLAY_FIXTURE_FATAL_BODY)
    do_break(0U);
#elif defined(JFG_G2_OVERLAY_FIXTURE_ABORT_BODY)
    std::abort();
#elif defined(JFG_G2_OVERLAY_FIXTURE_HANG_BODY)
    // A volatile read keeps this loop observable so optimizing compilers
    // cannot assume forward progress and delete the intentional hang.
    volatile int hang = 1;
    while (hang != 0) {
    }
#endif
}

void safe_dependent_function(std::uint8_t*, recomp_context*) {}

void stack_dependent_function(
    std::uint8_t* const rdram,
    recomp_context* const context) {
    const std::uint32_t stack = static_cast<std::uint32_t>(context->r29);
#if defined(JFG_G2_OVERLAY_FIXTURE_HIGH_STATIC)
    if (stack < UINT32_C(0x807E0000) || stack >= UINT32_C(0x807F0000)) {
#else
    if (stack < UINT32_C(0x807F0000) || stack >= UINT32_C(0x80800000)) {
#endif
        std::abort();
    }
    volatile std::int32_t value = MEM_W(-16, context->r29);
    (void)value;
}

void beyond_backing_function(
    std::uint8_t* const rdram,
    recomp_context*) {
    constexpr gpr one_past_rdram = UINT64_C(0xFFFFFFFF80800000);
    volatile std::int32_t value = MEM_W(0, one_past_rdram);
    (void)value;
}

void far_beyond_backing_function(
    std::uint8_t* const rdram,
    recomp_context*) {
#if defined(JFG_G2_OVERLAY_FIXTURE_FAR_END_BODY)
    constexpr gpr far_outside_rdram = UINT64_C(0x000000007FFFFFFF);
#else
    constexpr gpr far_outside_rdram = UINT64_C(0);
#endif
    volatile std::int32_t value = MEM_W(0, far_outside_rdram);
    (void)value;
}

void static_state_function(
    std::uint8_t* const rdram,
    recomp_context*) {
#if defined(JFG_G2_OVERLAY_FIXTURE_HIGH_STATIC)
    constexpr gpr static_base = UINT64_C(0xFFFFFFFF807F0000);
#else
    constexpr gpr static_base = UINT64_C(0xFFFFFFFF80000000);
#endif
    if (static_cast<std::uint32_t>(MEM_W(4, static_base)) != UINT32_C(0x88776655) ||
        MEM_W(8, static_base) != 0) {
        std::abort();
    }
}

void argument_dependent_function(
    std::uint8_t* const rdram,
    recomp_context* const context) {
    const std::uint32_t argument = static_cast<std::uint32_t>(context->r4);
    if (argument < UINT32_C(0x807F0000) ||
        argument >= UINT32_C(0x80800000)) {
        std::abort();
    }
    volatile std::int32_t value = MEM_W(-16, context->r4);
    (void)value;
}

}  // namespace

std::size_t jfg_generated_section_count(void) {
    return 4U;
}

int jfg_generated_initialize_sections(
    std::int32_t* addresses,
    const std::size_t capacity) {
    if (addresses == nullptr || capacity < 4U) {
        return 0;
    }
    fixture_section_addresses = addresses;
    section_capacity = 4U;
#if defined(JFG_G2_OVERLAY_FIXTURE_HIGH_STATIC)
    addresses[0] = static_cast<std::int32_t>(UINT32_C(0x807F0000));
#else
    addresses[0] = static_cast<std::int32_t>(jfg::kGeneratedCachedGuestBase);
#endif
    addresses[1] = 0;
    addresses[2] = 0;
    addresses[3] = 0;
    return 1;
}

int jfg_generated_section_metadata(
    const std::uint32_t section,
    JfgGeneratedSectionMetadata* const output) {
    static constexpr JfgGeneratedSectionMetadata metadata[]{
#if defined(JFG_G2_OVERLAY_FIXTURE_HIGH_STATIC)
        {0U, UINT32_C(0x807F0000), 0U, 4U, 4U, UINT32_C(0x0000FFF8), 0U},
#else
        {0U, jfg::kGeneratedCachedGuestBase, 0U, 4U, 4U, 4U, 0U},
#endif
        {0U, 0U, 0U, 32U, 0U,
#if defined(JFG_G2_OVERLAY_FIXTURE_NO_SCRATCH)
            UINT32_C(0x007FFFA0),
#else
            16U,
#endif
            1U},
        {0U, 0U, 0U, 32U, 0U, 16U, 1U},
        {0U, 0U, 0U, 24U, 16U, 16U, 1U},
    };
    if (output == nullptr || section >= 4U) {
        return 0;
    }
    *output = metadata[section];
    return 1;
}

int jfg_generated_section_lifecycle(
    const std::uint32_t operation,
    const std::uint32_t section,
    const std::int32_t base) {
    if (fixture_section_addresses == nullptr || section_capacity != 4U || section >= 4U) {
        return -1;
    }
    if (operation == 1U) {
        fixture_section_addresses[section] = base;
        return 0;
    }
    if (operation == 2U) {
        fixture_section_addresses[section] = 0;
        return 0;
    }
    return -1;
}

std::size_t jfg_generated_relocation_count(const std::uint32_t section) {
    return section == 1U ? 1U : (section == 2U ? 4U : (section == 3U ? 2U : 0U));
}

int jfg_generated_relocation_sites(
    const std::uint32_t section,
    const std::uint32_t** const output,
    std::size_t* const count) {
    static constexpr std::uint32_t target_sites[]{0U};
    static constexpr std::uint32_t legacy_dependent_sites[]{0U, 4U, 8U, 12U};
    static constexpr std::uint32_t custom_dependent_sites[]{20U, 28U};
    if (output == nullptr || count == nullptr) {
        return 0;
    }
    if (section == 1U) {
        *output = target_sites;
        *count = sizeof(target_sites) / sizeof(target_sites[0]);
        return 1;
    }
    if (section == 2U) {
        *output = legacy_dependent_sites;
        *count = sizeof(legacy_dependent_sites) / sizeof(legacy_dependent_sites[0]);
        return 1;
    }
    if (section == 3U) {
        *output = custom_dependent_sites;
        *count = sizeof(custom_dependent_sites) / sizeof(custom_dependent_sites[0]);
        return 1;
    }
    if (section == 0U) {
        *output = nullptr;
        *count = 0U;
        return 1;
    }
    return 0;
}

int jfg_generated_relocation_descriptors(
    const std::uint32_t section,
    const JfgGeneratedR32Descriptor** const output,
    std::size_t* const count) {
    static constexpr JfgGeneratedR32Descriptor target_descriptors[]{
        {0U, 0U, 0U},
    };
    static constexpr JfgGeneratedR32Descriptor legacy_dependent_descriptors[]{
        {0U, 1U, 0U},
        {4U, 1U, 4U},
        {8U, 1U, 8U},
        {12U, 1U, 12U},
    };
    static constexpr JfgGeneratedR32Descriptor custom_dependent_descriptors[]{
        {20U, 1U, 16U},
        {28U, 1U, 20U},
    };
    if (output == nullptr || count == nullptr) {
        return 0;
    }
    if (section == 1U) {
        *output = target_descriptors;
        *count = sizeof(target_descriptors) / sizeof(target_descriptors[0]);
        return 1;
    }
    if (section == 2U) {
        *output = legacy_dependent_descriptors;
        *count = sizeof(legacy_dependent_descriptors) /
            sizeof(legacy_dependent_descriptors[0]);
        return 1;
    }
    if (section == 3U) {
        *output = custom_dependent_descriptors;
        *count = sizeof(custom_dependent_descriptors) /
            sizeof(custom_dependent_descriptors[0]);
        return 1;
    }
    if (section == 0U) {
        *output = nullptr;
        *count = 0U;
        return 1;
    }
    return 0;
}

bool relocation_truth(
    const std::uint32_t source_section,
    const std::uint32_t site,
    std::uint32_t* const target_section,
    std::uint32_t* const target_offset) {
    if (target_section == nullptr || target_offset == nullptr) {
        return false;
    }
    if (source_section == 1U && site == 0U) {
        *target_section = 0U;
        *target_offset = 0U;
        return true;
    }
    if (source_section == 2U && site <= 12U && (site & 3U) == 0U) {
        *target_section = 1U;
        *target_offset = site;
        return true;
    }
    if (source_section == 3U && (site == 20U || site == 28U)) {
        *target_section = 1U;
        *target_offset = site == 20U ? 16U : 20U;
        return true;
    }
    return false;
}

int jfg_generated_apply_relocations_checked(
    std::uint8_t* const rdram,
    const std::size_t rdram_size,
    const std::uint32_t section) {
    if (rdram == nullptr || fixture_section_addresses == nullptr || section >= 4U ||
        fixture_section_addresses[section] == 0) {
        return 0;
    }
    const std::uint32_t base = static_cast<std::uint32_t>(fixture_section_addresses[section]);
    const std::size_t offset = base - jfg::kGeneratedCachedGuestBase;
    const std::uint32_t* sites = nullptr;
    std::size_t count = 0U;
    if (jfg_generated_relocation_sites(section, &sites, &count) == 0 ||
        (count != 0U && sites == nullptr) || offset > rdram_size) {
        return 0;
    }
    for (std::size_t index = 0U; index < count; ++index) {
        if (sites[index] > rdram_size - offset ||
            rdram_size - offset - sites[index] < sizeof(std::uint32_t)) {
            return 0;
        }
        std::uint32_t target_section = 0U;
        std::uint32_t target_offset = 0U;
        if (!relocation_truth(section, sites[index], &target_section, &target_offset) ||
            target_section >= 4U || fixture_section_addresses[target_section] == 0) {
            return 0;
        }
        const std::uint32_t target_base = static_cast<std::uint32_t>(
            fixture_section_addresses[target_section]);
        if (target_base > UINT32_MAX - target_offset) {
            return 0;
        }
        const std::uint32_t value = target_base + target_offset;
        rdram[offset + sites[index]] = static_cast<std::uint8_t>(value >> 24U);
        rdram[offset + sites[index] + 1U] = static_cast<std::uint8_t>(value >> 16U);
        rdram[offset + sites[index] + 2U] = static_cast<std::uint8_t>(value >> 8U);
        rdram[offset + sites[index] + 3U] = static_cast<std::uint8_t>(value);
    }
    return 1;
}

jfg::GeneratedOverlayFunction jfg_generated_lookup_function(
    const std::int32_t signed_address) {
    if (fixture_section_addresses == nullptr) {
        return nullptr;
    }
    const std::uint32_t address = static_cast<std::uint32_t>(signed_address);
#if defined(JFG_G2_OVERLAY_FIXTURE_HIGH_STATIC)
    if (address == UINT32_C(0x807F0000)) {
#else
    if (address == jfg::kGeneratedCachedGuestBase) {
#endif
        return main_function;
    }
    if (fixture_section_addresses[1] != 0 &&
        (address == static_cast<std::uint32_t>(fixture_section_addresses[1]) ||
         address == static_cast<std::uint32_t>(fixture_section_addresses[1]) + 16U)) {
        return target_function;
    }
    if (fixture_section_addresses[2] != 0 &&
        (address == static_cast<std::uint32_t>(fixture_section_addresses[2]) ||
         address == static_cast<std::uint32_t>(fixture_section_addresses[2]) + 16U)) {
#if defined(JFG_G2_OVERLAY_FIXTURE_UNSAFE_FIRST_BODY) || \
    defined(JFG_G2_OVERLAY_FIXTURE_STACK_FIRST_BODY) || \
    defined(JFG_G2_OVERLAY_FIXTURE_BEYOND_BACKING_BODY) || \
    defined(JFG_G2_OVERLAY_FIXTURE_FAR_HALF_BODY) || \
    defined(JFG_G2_OVERLAY_FIXTURE_FAR_END_BODY) || \
    defined(JFG_G2_OVERLAY_FIXTURE_STATIC_STATE_BODY) || \
    defined(JFG_G2_OVERLAY_FIXTURE_ARGUMENTS_BODY)
        return address == static_cast<std::uint32_t>(fixture_section_addresses[2])
            ? dependent_function
#if defined(JFG_G2_OVERLAY_FIXTURE_BEYOND_BACKING_BODY)
            : beyond_backing_function;
#elif defined(JFG_G2_OVERLAY_FIXTURE_FAR_HALF_BODY) || \
    defined(JFG_G2_OVERLAY_FIXTURE_FAR_END_BODY)
            : far_beyond_backing_function;
#elif defined(JFG_G2_OVERLAY_FIXTURE_STATIC_STATE_BODY)
            : static_state_function;
#elif defined(JFG_G2_OVERLAY_FIXTURE_ARGUMENTS_BODY)
            : argument_dependent_function;
#elif defined(JFG_G2_OVERLAY_FIXTURE_STACK_FIRST_BODY)
            : stack_dependent_function;
#else
            : safe_dependent_function;
#endif
#else
        return dependent_function;
#endif
    }
    if (fixture_section_addresses[3] != 0 &&
        (address == static_cast<std::uint32_t>(fixture_section_addresses[3]) ||
         address == static_cast<std::uint32_t>(fixture_section_addresses[3]) + 16U)) {
#if defined(JFG_G2_OVERLAY_FIXTURE_UNSAFE_FIRST_BODY) || \
    defined(JFG_G2_OVERLAY_FIXTURE_STACK_FIRST_BODY) || \
    defined(JFG_G2_OVERLAY_FIXTURE_BEYOND_BACKING_BODY) || \
    defined(JFG_G2_OVERLAY_FIXTURE_FAR_HALF_BODY) || \
    defined(JFG_G2_OVERLAY_FIXTURE_FAR_END_BODY) || \
    defined(JFG_G2_OVERLAY_FIXTURE_STATIC_STATE_BODY) || \
    defined(JFG_G2_OVERLAY_FIXTURE_ARGUMENTS_BODY)
        return address == static_cast<std::uint32_t>(fixture_section_addresses[3])
            ? dependent_function
#if defined(JFG_G2_OVERLAY_FIXTURE_BEYOND_BACKING_BODY)
            : beyond_backing_function;
#elif defined(JFG_G2_OVERLAY_FIXTURE_FAR_HALF_BODY) || \
    defined(JFG_G2_OVERLAY_FIXTURE_FAR_END_BODY)
            : far_beyond_backing_function;
#elif defined(JFG_G2_OVERLAY_FIXTURE_STATIC_STATE_BODY)
            : static_state_function;
#elif defined(JFG_G2_OVERLAY_FIXTURE_ARGUMENTS_BODY)
            : argument_dependent_function;
#elif defined(JFG_G2_OVERLAY_FIXTURE_STACK_FIRST_BODY)
            : stack_dependent_function;
#else
            : safe_dependent_function;
#endif
#else
        return dependent_function;
#endif
    }
    return nullptr;
}

}  // extern "C"
