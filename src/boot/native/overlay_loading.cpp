#include "runtime_services.hpp"
namespace jfg::boot::native::detail {
#if defined(JFG_PHASE8_LIVE_RUNTIME)
bool mirror_synthetic_overlay_in_runlink(
    State &state, const JfgGeneratedSectionMetadata &metadata) {
  if (state.rdram == nullptr)
    return false;
  hle::GuestMemory memory({state.rdram, kRdramSize},
                          hle::GuestMemory::Layout::native_word_big_endian);
  const RunlinkPublicationResult result = publish_runlink_module(
      memory, kRunlinkModuleTablePointer, kRunlinkOverlaySlotCount,
      RunlinkModuleIdentity{metadata.rom_start, metadata.text_size,
                            metadata.data_size, metadata.bss_size},
      metadata.linked_vram);
  return result == RunlinkPublicationResult::published ||
         result == RunlinkPublicationResult::already_published ||
         result == RunlinkPublicationResult::table_uninitialized;
}



// Observe the original cold loader without publishing a synthetic base into
// its still-empty record. Publication is deferred until the guest allocated
// the module, so its allocator, relocation work and init ordering stay intact.
bool note_guest_cold_overlay_load(State &state, const std::uint32_t slot) {
  if (slot == 0U)
    return true;
  if (slot > kRunlinkOverlaySlotCount)
    return false;
  hle::GuestMemory memory({state.rdram, kRdramSize},
                         hle::GuestMemory::Layout::native_word_big_endian);
  std::uint32_t table = 0U, base = 0U;
  if (!memory.read_u32(kRunlinkModuleTablePointer, table) || table == 0U ||
      (table & 3U) != 0U || table < kKseg0 ||
      std::uint64_t{table} + (slot + 1U) * kRunlinkModuleRecordSize >
          std::uint64_t{kKseg0} + kRdramSize)
    return false;
  const auto record = table + slot * kRunlinkModuleRecordSize;
  if (!memory.read_u32(record, base))
    return false;
  if (base != 0U)
    return true; // The original loader also returns without loading anything.
  const auto suspension = resolve_runlink_suspension(memory, kRunlinkSuspendedModules, kRunlinkSuspendedCount, slot);
  if (suspension != RunlinkSuspensionResult::absent)
    return suspension == RunlinkSuspensionResult::suspended;
  RunlinkModuleIdentity identity{};
  if (!memory.read_u32(record + 4U, identity.rom_start) ||
      !memory.read_u32(record + 8U, identity.text_size) ||
      !memory.read_u32(record + 12U, identity.data_size) ||
      !memory.read_u32(record + 16U, identity.bss_size))
    return false;
  std::uint32_t linked = 0U;
  for (std::uint32_t section = 0U; section < jfg_generated_section_count(); ++section) {
    JfgGeneratedSectionMetadata metadata{};
    if (jfg_generated_section_metadata(section, &metadata) == 0)
      return false;
    if (metadata.is_overlay != 1U || metadata.rom_start != identity.rom_start ||
        metadata.text_size != identity.text_size || metadata.data_size != identity.data_size ||
        metadata.bss_size != identity.bss_size)
      continue;
    if (linked != 0U)
      return false;
    linked = metadata.linked_vram;
  }
  if (linked != 0U) {
    state.pending_cold_overlay_images.insert(linked);
    state.gameplay_trace.event("overlay-cold-prepare",
        {state.vi_retraces, state.controller_samples, slot, linked});
  }
  return true;
}

bool ensure_guest_overlay_allocation(
    State &state, const JfgGeneratedSectionMetadata &metadata,
    recomp_context &caller_context) {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  const auto inventory_started = state.diagnostic_cpu_costs ? std::chrono::steady_clock::now()
      : std::chrono::steady_clock::time_point{};
#endif
  hle::GuestMemory memory({state.rdram, kRdramSize},
                         hle::GuestMemory::Layout::native_word_big_endian);
  std::uint32_t table = 0U;
  if (!memory.read_u32(kRunlinkModuleTablePointer, table))
    return false;
  if (table == 0U)
    return true; // The guest has not initialized its module inventory yet.
  // Validate the complete word-aligned inventory once. Its native-word
  // layout allows a byte-exact inventory comparison on every call. The
  // derived identity index is invalidated by any changed byte, preserving
  // unloads, duplicates and malformed-table rejection. Bases stay live below.
  const std::uint64_t first_record = std::uint64_t{table} + kRunlinkModuleRecordSize;
  const std::uint64_t inventory_end = std::uint64_t{table} +
      kRunlinkOverlaySlotCount * kRunlinkModuleRecordSize + 20U;
  if ((table & 3U) != 0U || first_record + 4U < kKseg0 ||
      inventory_end > std::uint64_t{kKseg0} + kRdramSize)
    return false;
  static_assert(kRunlinkOverlaySlotCount == NativeRunlinkIdentityIndex::kSlotCount);
  const auto matched_slot = state.native_overlay_identity_index.find(
      {state.rdram + static_cast<std::size_t>(first_record - kKseg0),
       NativeRunlinkIdentityIndex::kRecordBytes},
      {metadata.rom_start, metadata.text_size, metadata.data_size, metadata.bss_size});
  const auto matched_record = table + matched_slot * kRunlinkModuleRecordSize;
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  if (state.diagnostic_cpu_costs) {
    state.profile_overlay_inventory_ns += static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now()-inventory_started).count());
    ++state.profile_overlay_inventory_calls;
  }
#endif
  if (matched_slot == 0U)
    return false;
  std::uint32_t base = 0U;
  if (!memory.read_u32(matched_record, base))
    return false;
  if (base != 0U && base != metadata.linked_vram)
    return true; // Preserve the allocation chosen by the guest loader.
  if (!state.guest_overlay_loads_in_progress.insert(matched_slot).second)
    return false;
  // A suspended module retains its data/BSS allocation. The cold loader
  // deliberately rejects its pending entry; resume through the generated
  // guest routine so it can reacquire text without resetting that state.
  const auto suspension = resolve_runlink_suspension(
      memory, kRunlinkSuspendedModules, kRunlinkSuspendedCount, matched_slot);
  if (suspension == RunlinkSuspensionResult::invalid) {
    state.guest_overlay_loads_in_progress.erase(matched_slot);
    return false;
  }
  const bool resume = suspension == RunlinkSuspensionResult::suspended;
  auto *loader = jfg_generated_lookup_function(static_cast<std::int32_t>(
      resume ? kRunlinkResume : kRunlinkColdLoad));
  if (loader == nullptr || !memory.write_u32(matched_record, 0U)) {
    state.guest_overlay_loads_in_progress.erase(matched_slot);
    return false;
  }
  // Use the real generated loader, including temporary relocation allocations,
  // PI completion and module lifetime state. Preserve the pending call's CPU
  // arguments; the loader uses the current guest stack below its incoming SP.
  if (!resume)
    state.pending_cold_overlay_images.insert(metadata.linked_vram);
  recomp_context loader_context = caller_context;
  // A context copy retains f_odd's host pointer into its source. The detached
  // loader must own every FPR; otherwise odd-register writes leak to the caller.
  loader_context.f_odd = loader_context.mips3_float_mode
      ? &loader_context.f1.u32l : &loader_context.f0.u32h;
  loader_context.r4 = matched_slot;
  loader(state.rdram, &loader_context);
  set_cop1_cs(caller_context.fcr31);
  state.guest_overlay_loads_in_progress.erase(matched_slot);
  // Resume has a void guest ABI; its published base is the success condition.
  return (resume || static_cast<std::uint32_t>(loader_context.r2) != 0U) &&
         memory.read_u32(matched_record, base) && base != 0U &&
         base != metadata.linked_vram;
}

bool publish_synthetic_overlay(
    State &state, const std::uint32_t section,
    const JfgGeneratedSectionMetadata &metadata,
    SyntheticOverlayPublication publication) {
  const auto reject = [&state](const char *reason) {
    state.last_overlay_publication_failure = reason;
    return false;
  };
  state.last_overlay_publication_failure = "none";
  if (state.rdram == nullptr || state.rom == nullptr ||
      metadata.is_overlay != 1U)
    return reject("invalid-input");
  const bool cold_image = state.pending_cold_overlay_images.contains(metadata.linked_vram);
  if (cold_image)
    publication = SyntheticOverlayPublication::reload;
  const bool was_active = state.active_overlay_sections.contains(section);
  if (was_active &&
      publication == SyntheticOverlayPublication::ensure_active) {
    if (!mirror_synthetic_overlay_in_runlink(state, metadata))
      return reject("active-runlink");
    return true;
  }
  const std::uint64_t initialized =
      std::uint64_t{metadata.text_size} + metadata.data_size;
  const std::uint64_t extent = initialized + metadata.bss_size;
  const std::uint32_t host_offset = metadata.linked_vram - kKseg0;
  if (initialized > SIZE_MAX || extent > SIZE_MAX || extent == 0U ||
      metadata.rom_start > state.rom_size ||
      initialized > state.rom_size - metadata.rom_start ||
      host_offset > kGuestAddressSpan ||
      extent > kGuestAddressSpan - host_offset)
    return reject("range");

  const std::size_t expected = jfg_generated_relocation_count(section);
  const std::uint32_t *sites = nullptr;
  const JfgGeneratedR32Descriptor *descriptors = nullptr;
  std::size_t site_count = 0U, descriptor_count = 0U;
  if (jfg_generated_relocation_sites(section, &sites, &site_count) == 0 ||
      jfg_generated_relocation_descriptors(section, &descriptors,
                                           &descriptor_count) == 0 ||
      site_count != expected || descriptor_count != expected ||
      (expected != 0U && (sites == nullptr || descriptors == nullptr)))
    return reject("relocation-table");

  std::vector<std::pair<std::size_t, std::uint32_t>> patches;
  patches.reserve(expected);
  std::unordered_set<std::uint32_t> unique_sites;
  for (std::size_t index = 0U; index < expected; ++index) {
    const auto &descriptor = descriptors[index];
    JfgGeneratedSectionMetadata target{};
    if (sites[index] != descriptor.site_offset ||
        !unique_sites.insert(descriptor.site_offset).second ||
        descriptor.site_offset > initialized ||
        initialized - descriptor.site_offset < sizeof(std::uint32_t) ||
        jfg_generated_section_metadata(descriptor.target_section, &target) ==
            0)
      return reject("relocation-descriptor");
    const std::uint64_t target_extent = std::uint64_t{target.text_size} +
                                        target.data_size + target.bss_size;
    // The normalized ABI assigns every overlay a stable synthetic address.
    // Cross-overlay R_MIPS_32 values must therefore be published even while
    // the target module is inactive: the game stores these as deferred
    // function/data references and loads the selected target later. Requiring
    // every referenced cutscene module to be active made the shared animation
    // overlay impossible to load at all.
    if (descriptor.target_offset >= target_extent)
      return reject("relocation-target");
    const std::uint64_t value =
        std::uint64_t{target.linked_vram} + descriptor.target_offset;
    if (value > UINT32_MAX)
      return reject("relocation-value");
    patches.emplace_back(static_cast<std::size_t>(host_offset) +
                             descriptor.site_offset,
                         static_cast<std::uint32_t>(value));
  }

  // Direct calls merely ensure that a normalized overlay is available. An
  // exact PI load of the module ROM start is different: it is the game's
  // genuine overlay load boundary. Honor the generated lifecycle inventory
  // there so mutable data and BSS (including the health-meter state in
  // section 6) cannot survive a death/respawn reload.
  if (was_active &&
      jfg_generated_section_lifecycle(
          2U, section, static_cast<std::int32_t>(metadata.linked_vram)) != 0)
    return reject("lifecycle-unload");

  auto *const destination = state.rdram + host_offset;
  for (std::size_t index = 0U; index < static_cast<std::size_t>(initialized);
       ++index)
    destination[index ^ 3U] = state.rom[metadata.rom_start + index];
  std::fill_n(destination + static_cast<std::size_t>(initialized),
              static_cast<std::size_t>(metadata.bss_size), 0U);
  if (jfg_generated_section_lifecycle(
          1U, section, static_cast<std::int32_t>(metadata.linked_vram)) != 0)
    return reject("lifecycle");
  for (const auto &[offset, value] : patches)
    std::memcpy(state.rdram + offset, &value, sizeof(value));
  if (!mirror_synthetic_overlay_in_runlink(state, metadata))
    return reject("runlink");
  state.active_overlay_sections.insert(section);
  if (cold_image) {
    state.pending_cold_overlay_images.erase(metadata.linked_vram);
    state.gameplay_trace.event("overlay-cold-publish",
        {state.vi_retraces, state.controller_samples, section, metadata.linked_vram,
         was_active ? 1U : 0U});
  }
  return true;
}

#endif

bool resolve_bzero_host_offset(const State &state, const std::uint32_t address,
                               const std::uint32_t length,
                               std::size_t &host_offset) {
  const std::uint32_t segment = address & 0xE0000000U;
  const std::uint64_t physical = address & 0x1FFFFFFFU;
  if ((segment == 0x80000000U || segment == 0xA0000000U) &&
      physical <= kRdramSize && length <= kRdramSize - physical) {
    host_offset = static_cast<std::size_t>(physical);
    return true;
  }

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  // Generated overlay-local references use their normalized synthetic VRAM
  // addresses. GuestBacking reserves and commits those exact windows at the
  // offset used by the generated MEM_* helpers, so HLE memory primitives must
  // recognize an active overlay's bounded window as well as ordinary RDRAM.
  for (const std::uint32_t section : state.active_overlay_sections) {
    JfgGeneratedSectionMetadata metadata{};
    if (jfg_generated_section_metadata(section, &metadata) == 0 ||
        metadata.is_overlay != 1U)
      continue;
    const std::uint64_t extent = std::uint64_t{metadata.text_size} +
                                 metadata.data_size + metadata.bss_size;
    const std::uint64_t begin = metadata.linked_vram;
    const std::uint64_t requested = address;
    if (requested < begin || requested - begin > extent ||
        length > extent - (requested - begin))
      continue;
    const std::uint64_t synthetic_host_offset =
        std::uint64_t{0x80000000U} + requested;
    if (synthetic_host_offset > kGuestAddressSpan ||
        length > kGuestAddressSpan - synthetic_host_offset)
      return false;
    host_offset = static_cast<std::size_t>(synthetic_host_offset);
    return true;
  }
#else
  (void)state;
#endif
  return false;
}

#if defined(JFG_PHASE8_LIVE_RUNTIME)

#endif
} // namespace jfg::boot::native::detail
