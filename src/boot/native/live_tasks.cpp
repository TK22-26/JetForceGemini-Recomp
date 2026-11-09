#include "runtime_services.hpp"
#include "gameplay_scopes.hpp"
namespace jfg::boot::native::detail {
#if defined(JFG_PHASE8_LIVE_RUNTIME)
bool configure_live_vi_mode(State &state, hle::GuestMemory &memory,
                            const std::uint32_t address) {
  // libultra's OSViMode is 0x50 bytes: a padded type byte, nine common
  // registers at +0x04, then five registers for each of the two fields.
  std::array<std::uint32_t, 9U> common{};
  std::array<LiveViFieldRegisters, 2U> fields{};
  for (std::size_t index = 0U; index < common.size(); ++index) {
    if (!memory.read_u32(address + 4U +
                             static_cast<std::uint32_t>(index * 4U),
                         common[index]))
      return false;
  }
  for (std::size_t field = 0U; field < fields.size(); ++field) {
    const std::uint32_t base =
        address + 0x28U + static_cast<std::uint32_t>(field * 0x14U);
    if (!memory.read_u32(base, fields[field].origin) ||
        !memory.read_u32(base + 4U, fields[field].y_scale) ||
        !memory.read_u32(base + 8U, fields[field].vertical_start) ||
        !memory.read_u32(base + 12U, fields[field].vertical_burst) ||
        !memory.read_u32(base + 16U, fields[field].intr))
      return false;
  }
  const std::uint32_t pixel_type = common[0U] & 0x03U;
  if ((pixel_type != 2U && pixel_type != 3U) || common[1U] == 0U ||
      common[1U] > 4096U || (common[7U] & 0x0FFFU) == 0U ||
      fields[0U].origin >= kRdramSize ||
      fields[1U].origin >= kRdramSize ||
      (fields[0U].y_scale & 0x0FFFU) == 0U ||
      (fields[1U].y_scale & 0x0FFFU) == 0U)
    return false;

  state.vi_mode_control = common[0U];
  state.rt64_vi.status = common[0U];
  state.rt64_vi.width = common[1U];
  state.rt64_vi.timing = common[2U];
  state.rt64_vi.vertical_sync = common[3U];
  state.rt64_vi.horizontal_sync = common[4U];
  state.rt64_vi.leap = common[5U];
  state.vi_mode_horizontal_start = common[6U];
  state.rt64_vi.horizontal_start =
      state.vi_blacked ? 0U : state.vi_mode_horizontal_start;
  state.rt64_vi.x_scale = common[7U];
  state.rt64_vi.current_line = common[8U] & 0x03FFU;
  state.vi_fields = fields;
  state.rt64_vi.y_scale = fields[0U].y_scale;
  state.rt64_vi.vertical_start = fields[0U].vertical_start;
  state.rt64_vi.vertical_burst = fields[0U].vertical_burst;
  state.rt64_vi.intr = fields[0U].intr;
  state.vi_mode_configured = true;
  state.gameplay_trace.event("vi-mode", {state.vi_retraces, common[0U], common[1U],
      common[6U], fields[0U].vertical_start, common[7U], fields[0U].y_scale});
  return true;
}

bool apply_live_vi_field(State &state, const std::uint32_t framebuffer) {
  const DiagnosticHostStage host_stage(state,"host-profile-vi");
  const bool serrate = (state.rt64_vi.status & 0x40U) != 0U;
  const std::size_t field = serrate
      ? static_cast<std::size_t>((state.rt64_vi.current_line >> 1U) & 1U)
      : 0U;
  const LiveViFieldRegisters &registers = state.vi_fields[field];
  const std::uint64_t origin =
      std::uint64_t{framebuffer & 0x00FF'FFFFU} + registers.origin;
  if (origin >= jfg::kRt64RequiredRdramBytes)
    return false;
  state.rt64_vi.origin = static_cast<std::uint32_t>(origin);
  state.rt64_vi.y_scale = registers.y_scale;
  state.rt64_vi.vertical_start = registers.vertical_start;
  state.rt64_vi.vertical_burst = registers.vertical_burst;
  state.rt64_vi.intr = registers.intr;
  return true;
}


#endif

#if defined(JFG_PHASE8_LIVE_RUNTIME)
class LiveAudioMemory final : public jfg::AudioMemoryAccess {
public:
  explicit LiveAudioMemory(std::uint8_t *rdram) : rdram_(rdram) {}

  [[nodiscard]] bool read(const std::size_t region_index,
                          const std::size_t offset,
                          const std::span<std::byte> destination) noexcept
      override {
    if (region_index != 0U || destination.empty() || offset > kRdramSize ||
        destination.size() > kRdramSize - offset)
      return false;
    for (std::size_t index = 0U; index < destination.size(); ++index)
      destination[index] =
          static_cast<std::byte>(rdram_[(offset + index) ^ 3U]);
    return true;
  }

  [[nodiscard]] bool write_region(
      const std::size_t region_index, const std::size_t offset,
      const std::span<const std::byte> source) noexcept override {
    if (region_index != 0U || source.empty() || offset > kRdramSize ||
        source.size() > kRdramSize - offset)
      return false;
    for (std::size_t index = 0U; index < source.size(); ++index)
      rdram_[(offset + index) ^ 3U] =
          static_cast<std::uint8_t>(source[index]);
    ++write_operations_;
    written_bytes_ += source.size();
    return true;
  }

  [[nodiscard]] bool write_output(
      std::size_t, std::span<const std::byte>) noexcept override {
    return false;
  }

  [[nodiscard]] std::size_t write_operations() const noexcept {
    return write_operations_;
  }
  [[nodiscard]] std::size_t written_bytes() const noexcept {
    return written_bytes_;
  }

private:
  std::uint8_t *rdram_ = nullptr;
  std::size_t write_operations_ = 0U;
  std::size_t written_bytes_ = 0U;
};

bool guest_task_blob(const State &state, const std::uint32_t address,
                     const std::size_t size,
                     std::vector<std::byte> &output) {
  const std::uint32_t physical = address & 0x1FFFFFFFU;
  if (size == 0U || physical > kRdramSize || size > kRdramSize - physical)
    return false;
  output.resize(size);
  for (std::size_t index = 0U; index < size; ++index) {
    output[index] =
        static_cast<std::byte>(state.rdram[(physical + index) ^ 3U]);
  }
  return true;
}

std::uint32_t translate_live_graphics_address(
    const State &state, const std::uint32_t address) noexcept {
  // The single-range translator always preserves real RDRAM aliases. Check
  // that invariant once instead of rechecking it for every overlay range.
  const auto segment = address & 0xE0000000U;
  if ((segment == 0U || segment == 0x80000000U || segment == 0xA0000000U) &&
      (address & 0x1FFFFFFFU) < kRdramSize)
    return address;
  for (const LiveGraphicsOverlayShadow &shadow :
       state.graphics_overlay_shadows) {
    const std::uint32_t translated = jfg::translate_rt64_overlay_address(
        address, static_cast<std::uint32_t>(kRdramSize),
        {shadow.linked_base, shadow.extent, shadow.physical_base});
    if (translated != address)
      return translated;
  }
  return address;
}

bool materialize_live_graphics_overlays(
    State &state, std::vector<std::byte> &snapshot,
    const std::uint32_t command_address,
    const std::uint32_t command_count,
    std::vector<jfg::Rt64RdramRange>* changed,
    bool overlays_initialized, std::span<const jfg::Rt64RdramRange> prior_dirty,
    std::vector<jfg::Rt64RdramRange>& overlay_dirty) {
  state.materialize_reject_reason = 0U;
  state.materialize_reject_address = 0U;
  state.materialize_reject_word0 = 0U;
  state.materialize_reject_word1 = 0U;
  state.materialize_parent_address = 0U;
  state.materialize_parent_word0 = 0U;
  state.materialize_parent_word1 = 0U;
  state.materialize_block_address = 0U;
  state.materialize_parent_segment_base = 0U;
  const auto reject = [&state](const std::uint32_t reason,
                               const std::uint32_t address,
                               const std::uint32_t word0,
                               const std::uint32_t word1) {
    state.materialize_reject_reason = reason;
    state.materialize_reject_address = address;
    state.materialize_reject_word0 = word0;
    state.materialize_reject_word1 = word1;
    return false;
  };
  if (state.rom == nullptr ||
      snapshot.size() != jfg::kRt64RequiredRdramBytes || command_count == 0U)
    return reject(1U, command_address, 0U, 0U);
  const auto remember_overlay = [&](std::size_t begin, std::size_t end) {
    begin=(std::max)(begin,kRdramSize);
    if (begin < end) overlay_dirty.push_back({begin,end});
  };
  if (state.graphics_overlay_initial_data.empty()) {
    for (const LiveGraphicsOverlayShadow &shadow :
         state.graphics_overlay_shadows) {
      JfgGeneratedSectionMetadata metadata{};
      if (jfg_generated_section_metadata(shadow.section, &metadata) == 0)
        return false;
      const std::uint64_t initialized =
          std::uint64_t{metadata.text_size} + metadata.data_size;
      if (
          initialized > shadow.extent || metadata.rom_start > state.rom_size ||
          initialized > state.rom_size - metadata.rom_start ||
          shadow.physical_base > snapshot.size() ||
          shadow.extent > snapshot.size() - shadow.physical_base)
        return false;
      for (std::size_t index = 0U; index < initialized; ++index)
        snapshot[(shadow.physical_base + index) ^ 3U] =
            static_cast<std::byte>(state.rom[metadata.rom_start + index]);
      std::fill_n(snapshot.begin() + shadow.physical_base + initialized,
                  metadata.bss_size, std::byte{0});
    }
    for (const LiveGraphicsOverlayShadow &shadow :
         state.graphics_overlay_shadows) {
      const JfgGeneratedR32Descriptor *descriptors = nullptr;
      std::size_t count = 0U;
      if (jfg_generated_relocation_descriptors(shadow.section, &descriptors,
                                               &count) == 0 ||
          (count != 0U && descriptors == nullptr))
        return false;
      for (std::size_t index = 0U; index < count; ++index) {
        JfgGeneratedSectionMetadata target{};
        if (jfg_generated_section_metadata(descriptors[index].target_section,
                                           &target) == 0 ||
            shadow.extent < 4U ||
            descriptors[index].site_offset > shadow.extent - 4U ||
            descriptors[index].target_offset >
                UINT32_MAX - target.linked_vram)
          return false;
        const std::uint32_t linked =
            target.linked_vram + descriptors[index].target_offset;
        const std::uint32_t translated =
            translate_live_graphics_address(state, linked);
        std::memcpy(snapshot.data() + shadow.physical_base +
                        descriptors[index].site_offset,
                    &translated, sizeof(translated));
      }
    }
    state.graphics_overlay_initial_data.assign(snapshot.begin() + kRdramSize,
                                                snapshot.end());
    if (changed) changed->push_back({kRdramSize, snapshot.size()});
  } else {
    for (const auto &shadow : state.graphics_overlay_shadows) {
      if (shadow.physical_base < kRdramSize ||
          shadow.physical_base - kRdramSize > state.graphics_overlay_initial_data.size() ||
          shadow.extent > state.graphics_overlay_initial_data.size() -
                              (shadow.physical_base - kRdramSize))
        return reject(1U, command_address, 0U, 0U);
      // Active writable data is supplied below. Restoring it to ROM first
      // would dirty it unnecessarily and force another identical GPU import.
      std::size_t restored = shadow.extent;
      if (state.active_overlay_sections.contains(shadow.section)) {
        JfgGeneratedSectionMetadata metadata{};
        if (jfg_generated_section_metadata(shadow.section, &metadata) == 0 ||
            metadata.text_size > shadow.extent)
          return reject(1U, command_address, 0U, 0U);
        restored = metadata.text_size;
      }
      if (overlays_initialized) {
        if (!jfg::restore_overlay_snapshot_ranges(
            std::span<const std::byte>(state.graphics_overlay_initial_data),std::span(snapshot),kRdramSize,
            shadow.physical_base,shadow.physical_base+restored,shadow.physical_base+shadow.extent,
            prior_dirty,overlay_dirty,[&](std::size_t begin,std::size_t count) {
              if (changed) changed->push_back({begin,begin+count});
            })) return reject(1U,command_address,0U,0U);
        continue;
      }
      jfg::copy_changed_snapshot_bytes(
          std::span<const std::byte>(state.graphics_overlay_initial_data).subspan(
              shadow.physical_base - kRdramSize, restored),
          std::span(snapshot).subspan(shadow.physical_base, restored),
          [&](std::size_t begin, std::size_t count) {
            if (changed) changed->push_back({shadow.physical_base + begin,
                shadow.physical_base + begin + count});
          });
    }
  }

  // Planet meshes and other overlay-local graphics are generated into
  // writable DATA/BSS. Keep cached text and inactive-module fallbacks, but
  // submit the current CPU-owned data for every published allocation.
  for (const auto &shadow : state.graphics_overlay_shadows) {
    if (!state.active_overlay_sections.contains(shadow.section))
      continue;
    JfgGeneratedSectionMetadata metadata{};
    if (jfg_generated_section_metadata(shadow.section, &metadata) == 0 ||
        metadata.text_size > shadow.extent ||
        shadow.physical_base > snapshot.size() ||
        shadow.extent > snapshot.size() - shadow.physical_base)
      return reject(1U, shadow.linked_base, 0U, 0U);
    const std::uint32_t host_offset = shadow.linked_base - kKseg0;
    if (host_offset > kGuestAddressSpan ||
        shadow.extent > kGuestAddressSpan - host_offset)
      return reject(1U, shadow.linked_base, 0U, 0U);
    jfg::copy_changed_snapshot_bytes(
        std::span(reinterpret_cast<const std::byte*>(state.rdram + host_offset + metadata.text_size),
            shadow.extent - metadata.text_size),
        std::span(snapshot).subspan(shadow.physical_base + metadata.text_size,
            shadow.extent - metadata.text_size),
        [&](std::size_t begin, std::size_t count) {
          if (changed) changed->push_back({shadow.physical_base + metadata.text_size + begin,
              shadow.physical_base + metadata.text_size + begin + count});
          remember_overlay(shadow.physical_base + metadata.text_size + begin,
              shadow.physical_base + metadata.text_size + begin + count);
        });

    // Live pointer fields contain CPU addresses. Translate the current value,
    // preserving pointers that the game has changed since module loading.
    const std::uint32_t *sites = nullptr;
    std::size_t count = 0U;
    if (jfg_generated_relocation_sites(shadow.section, &sites, &count) == 0 ||
        (count != 0U && sites == nullptr))
      return reject(1U, shadow.linked_base, 0U, 0U);
    for (std::size_t index = 0U; index < count; ++index) {
      const std::uint32_t offset = sites[index];
      if (shadow.extent < sizeof(std::uint32_t) ||
          offset > shadow.extent - sizeof(std::uint32_t))
        return reject(1U, shadow.linked_base, 0U, 0U);
      if (offset < metadata.text_size)
        continue;
      auto *const site = snapshot.data() + shadow.physical_base + offset;
      std::uint32_t value = 0U;
      std::memcpy(&value, site, sizeof(value));
      value = translate_live_graphics_address(state, value);
      std::memcpy(site, &value, sizeof(value));
      if (changed) changed->push_back({shadow.physical_base + offset,
          shadow.physical_base + offset + sizeof(value)});
      remember_overlay(shadow.physical_base + offset,shadow.physical_base + offset + sizeof(value));
    }
  }

  struct DisplayListFrame final {
    std::uint32_t address;
    std::uint32_t count;
    std::uint32_t index;
    std::uint32_t parent_address;
    std::uint32_t parent_word0;
    std::uint32_t parent_word1;
    std::uint32_t parent_segment_base;
    bool counted_dma;
  };
  std::array<bool, 16U> configured_segments{};
  std::array<std::uint32_t, 16U> segment_bases{};
  constexpr std::uint32_t kRt64DisplayListDmaMask =
      static_cast<std::uint32_t>(jfg::kRt64RequiredRdramBytes - 8U);
  const auto display_list_dma_address =
      [kRt64DisplayListDmaMask](const std::uint32_t address) {
    return address & kRt64DisplayListDmaMask;
  };
  constexpr std::uint32_t kUnboundedCommandLimit = 65536U;
  constexpr std::uint64_t kTraversalCommandLimit = 4U * 1024U * 1024U;
  std::vector<DisplayListFrame> frames{{
      display_list_dma_address(command_address), command_count, 0U,
      0U, 0U, 0U, 0U, false}};
  std::unordered_set<std::uint64_t> active_blocks;
  const auto block_key = [](const DisplayListFrame &frame) {
    return (std::uint64_t{frame.address} << 32U) |
           (std::uint64_t{frame.count} << 1U) |
           static_cast<std::uint64_t>(frame.counted_dma);
  };
  active_blocks.insert(block_key(frames.back()));
  std::uint64_t traversed_commands = 0U;
  while (!frames.empty()) {
    DisplayListFrame &frame = frames.back();
    state.materialize_parent_address = frame.parent_address;
    state.materialize_parent_word0 = frame.parent_word0;
    state.materialize_parent_word1 = frame.parent_word1;
    state.materialize_block_address = frame.address;
    state.materialize_parent_segment_base = frame.parent_segment_base;
    const std::uint32_t limit =
        frame.count == 0U ? kUnboundedCommandLimit : frame.count;
    if (frame.index >= limit) {
      if (frame.count == 0U)
        return reject(13U, frame.address, 0U, 0U);
      active_blocks.erase(block_key(frame));
      frames.pop_back();
      continue;
    }
    if (++traversed_commands > kTraversalCommandLimit)
      return reject(14U, frame.address, 0U, 0U);

    const std::uint64_t offset =
        std::uint64_t{frame.address} + frame.index * 8U;
    ++frame.index;
    if (offset > snapshot.size() || snapshot.size() - offset < 8U)
      return reject(10U, static_cast<std::uint32_t>(offset), 0U, 0U);
    std::uint32_t words[2]{};
    std::memcpy(words, snapshot.data() + offset, sizeof(words));
    const std::uint8_t opcode = static_cast<std::uint8_t>(words[0] >> 24U);

    // F3DDKR's counted DMA-list handler dispatches only RDP commands. Low
    // opcodes inside that fixed-size block are data/no-ops, not nested lists
    // or segment updates. Treating them as normal GBI commands caused the old
    // breadth-first walker to patch unrelated memory as display-list data.
    if (frame.counted_dma && (opcode & 0xC0U) != 0xC0U)
      continue;

    if (!frame.counted_dma && opcode == 0xBCU &&
        static_cast<std::uint8_t>(words[0]) == 0x06U) {
      const std::uint32_t segment = ((words[0] >> 8U) & 0xFFFFU) >> 2U;
      if (segment >= configured_segments.size())
        return reject(11U, static_cast<std::uint32_t>(offset), words[0],
                      words[1]);
      configured_segments[segment] = true;
      segment_bases[segment] = display_list_dma_address(
          translate_live_graphics_address(state, words[1]));
    }

    const bool address_command =
        (!frame.counted_dma &&
         (opcode == 0x01U || opcode == 0x02U || opcode == 0x03U ||
          opcode == 0x04U || opcode == 0x05U || opcode == 0x06U ||
          opcode == 0x07U)) ||
        opcode == 0xFDU || opcode == 0xFEU || opcode == 0xFFU;
    const std::uint32_t original_address = words[1];
    const std::uint32_t segment = original_address >> 24U;
    const std::uint32_t translated_address = address_command
        ? translate_live_graphics_address(state, original_address)
        : original_address;
    // A matched synthetic overlay pointer is absolute, even when its high
    // byte happens to name a configured RSP segment. The options overlay
    // links above 32 MiB; treating that address as segment 2 skips its RDP
    // state lists whenever the scene has installed a nonzero segment base.
    const std::uint32_t materialized_address = translated_address;
    if (address_command) {
      const bool overlay_payload_command =
          opcode == 0x01U || opcode == 0x02U || opcode == 0x03U ||
          opcode == 0x04U || opcode == 0x05U || opcode == 0xFDU;
      const bool translated_display_list_edge =
          (opcode == 0x06U || opcode == 0x07U) &&
          translated_address != original_address;
      if ((overlay_payload_command &&
           translated_address != original_address) ||
          translated_display_list_edge ||
          segment >= configured_segments.size() ||
          !configured_segments[segment])
        words[1] = materialized_address;
      std::memcpy(snapshot.data() + offset, words, sizeof(words));
      if (changed) changed->push_back({offset, offset + sizeof(words)});
      remember_overlay(offset,offset+sizeof(words));
    }

    if (!frame.counted_dma && (opcode == 0x06U || opcode == 0x07U)) {
      const std::uint32_t segment_base =
          segment < segment_bases.size() && configured_segments[segment]
              ? segment_bases[segment]
              : 0U;
      const std::uint32_t traversal_address = jfg::resolve_rt64_display_list_edge(
          original_address, materialized_address, segment_base);
      const bool counted_dma = opcode == 0x07U;
      const std::uint32_t nested_count =
          counted_dma ? ((words[0] >> 16U) & 0xFFU) : 0U;
      if (counted_dma &&
          (nested_count == 0U ||
           (words[0] & 0xFFFFU) != nested_count * 8U))
        return reject(12U, static_cast<std::uint32_t>(offset), words[0],
                      words[1]);

      // G_DL with the no-push flag is a branch: the parent never resumes.
      if (!counted_dma && ((words[0] >> 16U) & 1U) != 0U) {
        active_blocks.erase(block_key(frames.back()));
        frames.pop_back();
      }
      const DisplayListFrame nested{
          traversal_address, nested_count, 0U,
          static_cast<std::uint32_t>(offset), words[0], words[1],
          segment_base, counted_dma};
      const std::uint64_t key = block_key(nested);
      if (!active_blocks.insert(key).second)
        return reject(15U, traversal_address, words[0], words[1]);
      frames.push_back(nested);
    } else if (!frame.counted_dma && opcode == 0xB8U) {
      active_blocks.erase(block_key(frames.back()));
      frames.pop_back();
    }
  }
  return true;
}

bool execute_live_audio_task(State &state, hle::GuestMemory &memory) {
  std::array<std::byte, 64U> descriptor{};
  for (std::size_t offset = 0U; offset < descriptor.size(); offset += 4U) {
    std::uint32_t word = 0U;
    if (!memory.read_u32(state.loaded_rsp_task +
                             static_cast<std::uint32_t>(offset),
                         word))
      return false;
    descriptor[offset] = static_cast<std::byte>(word >> 24U);
    descriptor[offset + 1U] = static_cast<std::byte>(word >> 16U);
    descriptor[offset + 2U] = static_cast<std::byte>(word >> 8U);
    descriptor[offset + 3U] = static_cast<std::byte>(word);
  }
  std::uint32_t program_address = 0U, program_size = 0U,
                data_address = 0U, data_size = 0U,
                commands_address = 0U, commands_size = 0U;
  if (!memory.read_u32(state.loaded_rsp_task + 0x10U, program_address) ||
      !memory.read_u32(state.loaded_rsp_task + 0x14U, program_size) ||
      !memory.read_u32(state.loaded_rsp_task + 0x18U, data_address) ||
      !memory.read_u32(state.loaded_rsp_task + 0x1CU, data_size) ||
      !memory.read_u32(state.loaded_rsp_task + 0x30U, commands_address) ||
      !memory.read_u32(state.loaded_rsp_task + 0x34U, commands_size) ||
      program_size == 0U ||
      program_size > jfg::kMaximumAudioActiveProgramBytes ||
      data_size == 0U || data_size > jfg::kMaximumAudioProgramDataBytes ||
      commands_size == 0U ||
      commands_size > jfg::kMaximumAudioCommandStreamBytes ||
      program_size % jfg::kAudioInstructionAlignmentBytes != 0U ||
      commands_size % jfg::kAudioCommandAlignmentBytes != 0U)
    return false;
  std::vector<std::byte> program, program_data, commands;
  if (!guest_task_blob(state, program_address, program_size, program) ||
      !guest_task_blob(state, data_address, data_size, program_data) ||
      !guest_task_blob(state, commands_address, commands_size, commands))
    return false;
  std::unique_ptr<jfg::evidence::G2PrivateAudioProgram> generated_program(
      jfg_g2_private_audio_program_v2(
          {descriptor, program, program_data, 0U, 4U}));
  if (!generated_program)
    return false;
  LiveAudioMemory live_memory(state.rdram);
  const jfg::AudioBackendTaskView task{
      jfg::AudioProgramVariant::primary,
      program,
      program_data,
      commands,
      1U,
      1U,
      4U,
  };
  // Opt-in, bounded private DSP fixtures. Normal playback never copies RAM.
  struct AudioTaskCaptureConfig {
    std::filesystem::path root;
    std::uint64_t begin = 0U;
    std::uint64_t count = 1U;
  };
  static const AudioTaskCaptureConfig capture_config = [] {
    AudioTaskCaptureConfig config;
    auto read = [](const char* name) {
      char* value = nullptr; std::size_t size = 0U; std::string result;
      if (_dupenv_s(&value, &size, name) == 0 && value != nullptr) result = value;
      std::free(value); return result;
    };
    config.root = read("JFG_PHASE8_AUDIO_TASK_CAPTURE");
    if (!config.root.empty()) {
      const auto begin = read("JFG_PHASE8_AUDIO_TASK_CAPTURE_BEGIN");
      const auto count = read("JFG_PHASE8_AUDIO_TASK_CAPTURE_COUNT");
      if (!begin.empty()) config.begin = std::strtoull(begin.c_str(), nullptr, 10);
      if (!count.empty()) config.count = (std::min)(std::uint64_t{8U},
          static_cast<std::uint64_t>(std::strtoull(count.c_str(), nullptr, 10)));
    }
    return config;
  }();
  const bool capture_task = !capture_config.root.empty() &&
      state.decoded_audio_tasks >= capture_config.begin &&
      state.decoded_audio_tasks - capture_config.begin < capture_config.count;
  std::filesystem::path capture_task_root;
  auto write_fixture = [&](const char* name, const void* bytes, std::size_t size) {
    std::ofstream file(capture_task_root / name, std::ios::binary | std::ios::trunc);
    file.write(static_cast<const char*>(bytes), static_cast<std::streamsize>(size));
    return static_cast<bool>(file);
  };
  if (capture_task) {
    capture_task_root = capture_config.root / std::to_string(state.decoded_audio_tasks);
    std::error_code error;
    std::filesystem::create_directories(capture_task_root, error);
    if (error || !write_fixture("before.bin", state.rdram, kRdramSize) ||
        !write_fixture("descriptor.bin", descriptor.data(), descriptor.size())) return false;
    std::ofstream(capture_task_root / "vi.txt") << state.vi_retraces;
  }
  const jfg::AudioRspProgramReport report =
      generated_program->execute(task, live_memory);
  if (capture_task && !write_fixture("after.bin", state.rdram, kRdramSize)) return false;
  if (report.exit_reason != jfg::AudioRspExitReason::broke ||
      !report.parse_complete ||
      report.selected_variant != jfg::AudioProgramVariant::primary ||
      report.unsupported_command_count != 0U ||
      report.parsed_command_count !=
          commands.size() / jfg::kAudioCommandAlignmentBytes ||
      report.input_read_operation_count == 0U ||
      report.region_write_operation_count != live_memory.write_operations() ||
      report.region_bytes_written != live_memory.written_bytes())
    return false;
  ++state.decoded_audio_tasks;
  return true;
}

#if defined(_WIN32)
bool initialize_live_renderer(State &state, LiveRt64Window &window) {
  if (state.rdram == nullptr || state.rom == nullptr ||
      state.rom_size < jfg::kRt64RequiredHeaderBytes ||
      window.get() == nullptr)
    return false;
  state.rt64_rdram.assign(jfg::kRt64RequiredRdramBytes, std::byte{0});
  std::copy_n(reinterpret_cast<const std::byte *>(state.rdram), kRdramSize,
              state.rt64_rdram.begin());
  state.rt64_vi.status = 0x0000320EU;
  state.rt64_vi.width = 320U;
  state.rt64_vi.intr = 2U;
  state.rt64_vi.timing = 0x03E52239U;
  state.rt64_vi.vertical_sync = 525U;
  state.rt64_vi.horizontal_sync = 0x00000C15U;
  state.rt64_vi.leap = 0x0C150C15U;
  state.rt64_vi.horizontal_start = 0x006C02ECU;
  state.rt64_vi.vertical_start = 0x002501FFU;
  state.rt64_vi.vertical_burst = 0x000E0204U;
  state.rt64_vi.x_scale = 0x00000200U;
  state.rt64_vi.y_scale = 0x00000400U;
  jfg::Rt64ShellError error = jfg::Rt64ShellError::none;
  const int saved_stdout = _dup(_fileno(stdout));
  HANDLE null_handle = CreateFileW(
      L"NUL", GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr,
      OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
  const int null_stdout =
      null_handle == INVALID_HANDLE_VALUE
          ? -1
          : _open_osfhandle(reinterpret_cast<std::intptr_t>(null_handle),
                            _O_WRONLY);
  if (null_stdout < 0 && null_handle != INVALID_HANDLE_VALUE)
    CloseHandle(null_handle);
  if (saved_stdout < 0 || null_stdout < 0 ||
      _dup2(null_stdout, _fileno(stdout)) != 0) {
    if (saved_stdout >= 0)
      _close(saved_stdout);
    if (null_stdout >= 0)
      _close(null_stdout);
    return false;
  }
  const auto video_settings = []() -> std::optional<jfg::VideoSettings> {
    wchar_t* config_path = nullptr;
    std::size_t size = 0;
    (void)_wdupenv_s(&config_path, &size, L"JFG_VIDEO_CONFIG");
    const auto profile=config_path?std::filesystem::path(config_path).parent_path():std::filesystem::path{};
    jfg::configure_actor_lod(jfg::load_actor_lod(profile).value_or(jfg::ActorLod::original));
    jfg::configure_shadow_quality(jfg::load_shadow_quality(profile).value_or(jfg::ShadowQuality::original));
    auto settings = jfg::load_video_settings(config_path == nullptr ? std::filesystem::path{} : std::filesystem::path(config_path));
    std::free(config_path);
    if (!settings) return std::nullopt;
    char* text = nullptr;
    (void)_dupenv_s(&text, &size, "JFG_EXPERIMENTAL_RENDER_FPS");
    if (text != nullptr) {
      const std::string value(text);
      std::free(text);
      if (value == "unlimited") settings->mode = jfg::FrameRateMode::unlimited;
      else {
        const auto fps = jfg::parse_render_fps(value);
        if (!fps) return std::nullopt;
        settings->mode = *fps == 0 ? jfg::FrameRateMode::original : jfg::FrameRateMode::custom;
        if (*fps) settings->fps = *fps;
      }
    }
    text = nullptr;
    (void)_dupenv_s(&text, &size, "JFG_RENDER_VSYNC");
    if (text != nullptr) {
      const std::string value(text);
      std::free(text);
      if (value != "0" && value != "1") return std::nullopt;
      settings->vsync = value == "1";
    }
    return settings;
  }();
  state.presentation_identity_enabled = video_settings &&
      video_settings->mode != jfg::FrameRateMode::original;
  if (!video_settings) {
    jfg::support_event("renderer_setup=invalid-config");
    (void)_dup2(saved_stdout, _fileno(stdout));
    _close(null_stdout);
    _close(saved_stdout);
    std::fprintf(stderr, "Invalid video settings. Check frame rate, VSync and graphics API in JFG_VIDEO_CONFIG.\n");
    return false;
  }
  jfg::configure_native_blur(video_settings->blur);
  jfg::configure_fog_strength(video_settings->fog_percent);
  state.rt64_shell = jfg::Rt64Shell::create(
      {window.get(), window.thread_id(),
       std::span<const std::byte>(
           reinterpret_cast<const std::byte *>(state.rom),
           jfg::kRt64RequiredHeaderBytes),
       state.rt64_rdram, &state.rt64_vi, false,
       // Software overlays read and modify completed color pixels.
       // RT64 already completes its RAM readback before DP completion.
       jfg::Rt64MemoryLayout::host_word_swapped, true, true,
       video_settings->mode == jfg::FrameRateMode::custom ? video_settings->fps : 0U,
       video_settings->mode == jfg::FrameRateMode::unlimited, video_settings->vsync,kRendererGameLayout,video_settings->graphics_api},
      error);
  std::fflush(stdout);
  (void)_dup2(saved_stdout, _fileno(stdout));
  _close(null_stdout);
  _close(saved_stdout);
  state.last_rt64_error = error;
  return state.rt64_shell != nullptr && error == jfg::Rt64ShellError::none;
}



bool execute_live_graphics_task(State &state, hle::GuestMemory &memory) {
  if (state.rt64_shell == nullptr ||
      state.rt64_rdram.size() != jfg::kRt64RequiredRdramBytes)
    return false;
  std::uint32_t ucode_address = 0U, ucode_size = 0U,
                ucode_data_address = 0U, ucode_data_size = 0U,
                command_address = 0U, command_size = 0U;
  if (!memory.read_u32(state.loaded_rsp_task + 0x10U, ucode_address) ||
      !memory.read_u32(state.loaded_rsp_task + 0x14U, ucode_size) ||
      !memory.read_u32(state.loaded_rsp_task + 0x18U, ucode_data_address) ||
      !memory.read_u32(state.loaded_rsp_task + 0x1CU, ucode_data_size) ||
      !memory.read_u32(state.loaded_rsp_task + 0x30U, command_address) ||
      !memory.read_u32(state.loaded_rsp_task + 0x34U, command_size))
    return false;
  state.last_graphics_descriptor = {ucode_address, ucode_size,
                                    ucode_data_address, ucode_data_size,
                                    command_address, command_size};
  const auto physical_range = [](const std::uint32_t address,
                                 const std::uint32_t bytes) {
    const std::uint32_t physical = address & 0x00FFFFFFU;
    return physical <= kRdramSize && bytes <= kRdramSize - physical;
  };
  // libultra does not require graphics tasks to populate ucode_size, and the
  // game uses data_size as a display-list count for some tiny setup tasks.
  // RT64 consumes the addresses and terminates on the GBI end command, so
  // validate the fixed apertures that its shell will inspect instead.
  if (!physical_range(ucode_address, 4096U) ||
      !physical_range(ucode_data_address, 2048U) ||
      !physical_range(command_address, sizeof(std::uint64_t)))
    return false;
  state.last_graphics_command_address = command_address;
  if (!memory.read_u32(command_address, state.last_graphics_command_word))
    return false;
  const auto prepare_start = state.diagnostic_function_profile ? std::chrono::steady_clock::now()
      : std::chrono::steady_clock::time_point{};
  std::vector<std::byte> snapshot;
  std::uint64_t base_generation = 0U;
  std::vector<jfg::Rt64RdramRange> prior_overlay_dirty;
  bool overlays_initialized = false;
  if (!state.graphics_snapshot_pool.empty()) {
    auto cached = std::move(state.graphics_snapshot_pool.back());
    state.graphics_snapshot_pool.pop_back();
    snapshot = std::move(cached.rdram);
    base_generation = cached.renderer_generation;
    prior_overlay_dirty = std::move(cached.overlay_dirty);
    overlays_initialized = cached.overlays_initialized;
  }
  snapshot.resize(jfg::kRt64RequiredRdramBytes);
  PendingLiveGraphicsTask pending{
      {ucode_address, ucode_data_address, command_address, state.vi_retraces},
      state.last_graphics_descriptor, std::move(snapshot)};
  pending.task.daynight_fog = state.daynight_fog_frames.take(command_address);
  pending.base_renderer_generation = base_generation;
  if(const auto prompt=state.cutscene_prompt_submissions.find(command_address&0x00FFFFFFU);
     prompt!=state.cutscene_prompt_submissions.end()) {
    pending.task.cutscene_prompt=prompt->second;
    state.cutscene_prompt_submissions.erase(prompt);
  }

  jfg::copy_changed_snapshot_bytes(std::span(reinterpret_cast<const std::byte *>(state.rdram), kRdramSize),
      std::span(pending.rdram).first(kRdramSize), [&](std::size_t begin, std::size_t count) {
        pending.changed.push_back({begin, begin + count});
      });
  const auto prepare_copy_done = state.diagnostic_function_profile ? std::chrono::steady_clock::now()
      : std::chrono::steady_clock::time_point{};
  if (!materialize_live_graphics_overlays(
          state, pending.rdram, command_address, command_size, &pending.changed,
          overlays_initialized,prior_overlay_dirty,pending.overlay_dirty)) {
    (void)write_private_rdram_capture(state);
    (void)write_private_rt64_snapshot(state, pending.rdram);
    return false;
  }
  pending.overlays_initialized = true;
  std::sort(pending.overlay_dirty.begin(),pending.overlay_dirty.end(),[](auto a,auto b) { return a.begin<b.begin; });
  std::size_t overlay_count=0;
  for (const auto range : pending.overlay_dirty) {
    if (overlay_count && range.begin<=pending.overlay_dirty[overlay_count-1U].end)
      pending.overlay_dirty[overlay_count-1U].end=(std::max)(pending.overlay_dirty[overlay_count-1U].end,range.end);
    else pending.overlay_dirty[overlay_count++]=range;
  }
  pending.overlay_dirty.resize(overlay_count);
  // Merge changed guest pages, restored overlay blocks, current writable
  // overlay data and command rewrites into one bounded import list.
  std::sort(pending.changed.begin(), pending.changed.end(), [](const auto a, const auto b) {
    return a.begin < b.begin;
  });
  std::size_t count = 0U;
  for (const auto range : pending.changed) {
    if (count && range.begin <= pending.changed[count - 1U].end)
      pending.changed[count - 1U].end = (std::max)(pending.changed[count - 1U].end, range.end);
    else pending.changed[count++] = range;
  }
  pending.changed.resize(count);
  const auto prepare_overlay_done = state.diagnostic_function_profile ? std::chrono::steady_clock::now()
      : std::chrono::steady_clock::time_point{};
  // Native scene lists are built after the previous list is submitted. Keep
  // their metadata through the following update, including the intervening
  // shadow tasks. This counter is independent of logging and elapsed VIs.
  const auto current_fade=[&](const auto& fade) {
    return fade.actor && fade.alpha<255U && state.camera_fade_updates>=fade.update &&
        state.camera_fade_updates-fade.update<=1U;
  };
  const bool camera_fade_active=std::any_of(state.pc_camera_fades.begin(),state.pc_camera_fades.end(),current_fade);
  if ((state.presentation_identity_enabled || jfg::shadow_quality_preference().load(std::memory_order_relaxed)==jfg::ShadowQuality::enhanced) || camera_fade_active) {
    auto scene=state.presentation_identities.capture(
        {reinterpret_cast<const std::uint8_t*>(pending.rdram.data()),pending.rdram.size()},
        state.vi_retraces,[&state](std::uint32_t address) {
          return translate_live_graphics_address(state,address);
        });
    const jfg::PresentationGuestView fade_ram({
        reinterpret_cast<const std::uint8_t*>(pending.rdram.data()),pending.rdram.size()});
    for(const auto& fade:state.pc_camera_fades)
      if(current_fade(fade) &&
         fade_ram.valid(fade.actor,0xA4U) && fade_ram.u32(fade.actor+game_member("layout.actor.control"))==fade.control &&
         fade_ram.u32(fade.actor+game_member("layout.actor.header"))==fade.header)
        scene.camera_fades.push_back({fade.actor,fade.alpha/255.0F});
    pending.task.presentation_scene=std::make_shared<const jfg::PresentationSceneIdentity>(std::move(scene));
  }
  if (state.diagnostic_function_profile) {
    const auto elapsed = [](auto a, auto b) { return static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(b-a).count()); };
    state.gameplay_trace.event("graphics-prepare-stages", {state.vi_retraces,
        state.controller_samples, command_size, elapsed(prepare_start,prepare_copy_done),
        elapsed(prepare_copy_done,prepare_overlay_done),
        elapsed(prepare_overlay_done,std::chrono::steady_clock::now())});
  }
  state.pending_graphics_tasks.push_back(std::move(pending));
  return true;
}
#endif
#endif



#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
void complete_pending_live_graphics_tasks(
    State &state, const std::uint32_t target,
    const bool require_offscreen_target) {
  if (state.pending_graphics_tasks.empty())
    return;
  const auto sp = state.events.find(4U);
  const auto dp = state.events.find(9U);
  if (state.rt64_shell == nullptr || (!state.guest_os_probe && (state.scheduler == nullptr ||
      sp == state.events.end() || dp == state.events.end())))
    fail_closed_dispatch(state, "renderer", "completion-events", target);
  const std::uint32_t selected_vi_framebuffer =
      (state.vi_next_framebuffer != 0U ? state.vi_next_framebuffer
                                      : state.vi_current_framebuffer) &
      0x00FFFFFFU;
  for (PendingLiveGraphicsTask &pending : state.pending_graphics_tasks) {
    if (pending.skipped) {
      if (state.guest_os_probe)
        fail_closed_dispatch(state, "renderer", "guest-task-skipped", target);
      ++state.graphics_tasks;
      complete_guest_sp_status(state, target);
      if (state.scheduler->send(sp->second.first, sp->second.second, false) !=
          hle::kOsSuccess)
        fail_closed_dispatch(state, "rsp", "sp-completion", target);
      const std::int32_t dp_delivery = state.scheduler->send(
          dp->second.first, dp->second.second, false);
      if (dp_delivery != hle::kOsSuccess && dp_delivery != hle::kOsFull)
        fail_closed_dispatch(state, "rsp", "dp-completion", target);
      continue;
    }
    if (!state.rdram_capture_path.empty() &&
        state.vi_retraces + 1U >= state.retrace_target &&
        !write_private_rt64_snapshot(state, pending.rdram))
      fail_closed_dispatch(state, "renderer", "rt64-rdram-capture", target);
    write_private_progress(state, "graphics-submit-begin");
    struct SubmitThreadSample {std::uint64_t cycles=0,cpu100ns=0;DWORD thread=0;bool valid=false;};
    const auto sample_submit_thread=[&] {
      SubmitThreadSample sample{};
      if(!state.diagnostic_function_profile)return sample;
      ULONG64 cycles=0;FILETIME created{},exited{},kernel{},user{};
      sample.thread=GetCurrentThreadId();
      sample.valid=QueryThreadCycleTime(GetCurrentThread(),&cycles)!=0 &&
          GetThreadTimes(GetCurrentThread(),&created,&exited,&kernel,&user)!=0;
      if(sample.valid) {
        sample.cycles=cycles;
        sample.cpu100ns=(std::uint64_t(kernel.dwHighDateTime)<<32U)+kernel.dwLowDateTime+
            (std::uint64_t(user.dwHighDateTime)<<32U)+user.dwLowDateTime;
      }
      return sample;
    };
    const auto submit_thread_start=sample_submit_thread();
    const auto submit_start = std::chrono::steady_clock::now();
    jfg::SubmissionProfileScope sync_scope(state.diagnostic_function_profile!=0U);
    const auto sync_stamp=[&]{return sync_scope.enabled ? std::chrono::steady_clock::now() : std::chrono::steady_clock::time_point{};};
    state.last_rt64_error = state.rt64_shell->replace_rdram_snapshot_delta(
        pending.rdram, jfg::Rt64MemoryLayout::host_word_swapped,
        pending.base_renderer_generation, pending.changed);
    const auto snapshot_done=sync_stamp();
    const auto snapshot_thread=sample_submit_thread();
    if (state.last_rt64_error == jfg::Rt64ShellError::none)
      state.last_rt64_error = state.rt64_shell->submit(pending.task);
    const auto decode_done=sync_stamp();
    const auto decode_thread=sample_submit_thread();
    // Return completed intensity masks before delivering DP/SP completion:
    // the guest blurs and attenuates its shadow mask on the CPU.
    if (state.last_rt64_error == jfg::Rt64ShellError::none)
      state.last_rt64_error = state.rt64_shell->commit_cpu_writeback(pending.rdram,
          std::as_writable_bytes(std::span(state.rdram, kRdramSize)));
    const auto writeback_done=sync_stamp();
    const auto writeback_thread=sample_submit_thread();
    const jfg::Rt64GraphicsDiagnostics submission_graphics =
        state.rt64_shell->last_graphics_diagnostics();
    if (state.last_rt64_error == jfg::Rt64ShellError::none)
      state.host_audio.renderer_ready();

    const auto submit_us = static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::steady_clock::now() - submit_start)
            .count());
    state.gameplay_trace.event("submit", {state.vi_retraces, state.controller_samples,
        state.gameplay_trace_updates, submit_us, pending.descriptor[4], pending.descriptor[5],
        submission_graphics.rdram_check_microseconds, submission_graphics.full_sync_microseconds,
        submission_graphics.color_image_address});
    if(state.diagnostic_function_profile) {
      const auto timing=sync_scope.delta();
      const std::array<SubmitThreadSample,4> cpu{submit_thread_start,snapshot_thread,decode_thread,writeback_thread};
      bool cpu_valid=true;std::array<std::uint64_t,3> cycles{},ticks{};
      for(unsigned i=0;i<3;++i) {
        cpu_valid=cpu_valid && cpu[i].valid && cpu[i+1].valid && cpu[i].thread==cpu[i+1].thread &&
            cpu[i+1].cycles>=cpu[i].cycles && cpu[i+1].cpu100ns>=cpu[i].cpu100ns;
        if(cpu_valid){cycles[i]=cpu[i+1].cycles-cpu[i].cycles;ticks[i]=cpu[i+1].cpu100ns-cpu[i].cpu100ns;}
      }
      if(!cpu_valid){cycles={};ticks={};}
      state.gameplay_trace.event("submit-thread",{state.vi_retraces,state.controller_samples,state.gameplay_trace_updates,
        cpu[0].thread,cpu_valid?1U:0U,cycles[0],cycles[1],cycles[2],ticks[0],ticks[1],ticks[2]});
      const auto ns=[](auto a,auto z){return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(z-a).count());};
      state.gameplay_trace.event("submit-host",{
        state.vi_retraces,state.controller_samples,state.gameplay_trace_updates,
        ns(submit_start,snapshot_done),ns(snapshot_done,decode_done),ns(decode_done,writeback_done)});
      state.gameplay_trace.event("submit-sync",{
        state.vi_retraces,state.controller_samples,state.gameplay_trace_updates,
        timing.ns[0],timing.ns[1],timing.ns[2],timing.ns[3],timing.ns[4],timing.ns[5],
        timing.calls[0],timing.calls[1],timing.calls[2],timing.calls[3],timing.calls[4],timing.calls[5]});
      const auto& stages=submission_graphics.history_stage_microseconds;
      state.gameplay_trace.event("submit-detail",{state.vi_retraces,state.controller_samples,
        state.gameplay_trace_updates,submission_graphics.history_prepare_microseconds,
        submission_graphics.rdp_sync_microseconds,stages[0],stages[1],stages[2],stages[3],stages[4],
        submission_graphics.vertices_loaded,submission_graphics.triangles_drawn});
    }
    if (state.diagnostic_cpu_costs || state.diagnostic_gpu_costs) {
      const auto timing = state.rt64_shell->framebuffer_gpu_timing();
      state.gameplay_trace.event("gpu-framebuffer-time", {state.vi_retraces, state.controller_samples,
          timing.submissions, timing.total_nanoseconds, timing.last_nanoseconds,
          timing.maximum_nanoseconds, timing.failed});
      const auto workload = state.rt64_shell->workload_gpu_timing();
      state.gameplay_trace.event("gpu-workload-time", {state.vi_retraces, state.controller_samples,
          workload.submissions, workload.total_nanoseconds, workload.last_nanoseconds,
          workload.maximum_nanoseconds, workload.failed});
    }
    state.graphics_submit_microseconds += submit_us;
    state.graphics_submit_max_us =
        (std::max)(state.graphics_submit_max_us, submit_us);
    if (state.timing_trace) {
      state.timing_trace << "submit\t" << state.vi_frames << '\t'
                         << state.vi_retraces << '\t' << submit_us << '\t'
                         << std::hex << pending.descriptor[4] << '\t'
                         << pending.descriptor[5] << std::dec << '\t'
                         << submission_graphics.rdram_check_microseconds
                         << '\t'
                         << submission_graphics.full_sync_microseconds << '\t'
                         << std::hex << submission_graphics.color_image_address
                         << std::dec << '\n';
    }
    write_private_progress(state, "graphics-submit-end");
    if (state.last_rt64_error != jfg::Rt64ShellError::none) {
      const jfg::Rt64GraphicsDiagnostics rejected = submission_graphics;
      if (!state.rdram_capture_path.empty())
        (void)write_private_rt64_snapshot(state, pending.rdram);
      std::array<char, 192U> operation{};
      (void)std::snprintf(
          operation.data(), operation.size(),
          "submit-%u-c%08x-n%x-r%08x-w%08x-%08x-q%u-d%08x-"
          "s%08x-t%u-l%016llx-%04x",
          static_cast<unsigned>(state.last_rt64_error), pending.descriptor[4],
          pending.descriptor[5], rejected.rejected_command_address,
          rejected.rejected_command_word0, rejected.rejected_command_word1,
          rejected.rejection_reason, rejected.rejection_detail,
          rejected.rejection_source_address, rejected.rejection_triangle,
          static_cast<unsigned long long>(rejected.loaded_vertices_low),
          static_cast<unsigned>(rejected.loaded_vertices_high));
      fail_closed_dispatch(state, "renderer", operation.data(), target);
    }
    const jfg::Rt64GraphicsDiagnostics graphics = submission_graphics;
    const std::uint32_t current_target =
        state.vi_current_framebuffer & 0x00FFFFFFU;
    const std::uint32_t next_target =
        state.vi_next_framebuffer & 0x00FFFFFFU;
    if (require_offscreen_target &&
        (graphics.color_image_address == 0U ||
         graphics.color_image_address == current_target ||
         graphics.color_image_address == next_target))
      fail_closed_dispatch(state, "renderer", "auxiliary-target", target);
    ++state.graphics_tasks;
    state.graphics_commands += state.rt64_shell->last_command_count();
    state.graphics_triangles += graphics.triangles_drawn;
    const std::size_t graphics_slot =
        state.recent_graphics_position %
        state.recent_graphics_color_images.size();
    state.recent_graphics_command_addresses[graphics_slot] =
        pending.descriptor[4];
    state.recent_graphics_color_images[graphics_slot] =
        graphics.color_image_address;
    state.recent_graphics_vi_selections[graphics_slot] =
        selected_vi_framebuffer;
    state.recent_graphics_matrix_commands[graphics_slot] =
        static_cast<std::uint32_t>(graphics.matrix_commands);
    state.recent_graphics_vertices_loaded[graphics_slot] =
        static_cast<std::uint32_t>(graphics.vertices_loaded);
    state.recent_graphics_vertices_in_clip[graphics_slot] =
        static_cast<std::uint32_t>(graphics.vertices_in_clip);
    state.recent_graphics_triangles[graphics_slot] =
        static_cast<std::uint32_t>(graphics.triangles_drawn);
    ++state.recent_graphics_position;
    if (graphics.color_image_address != 0U) {
      state.graphics_color_image = graphics.color_image_address;
      state.graphics_frame_ready = true;

    }
    // Submission and writeback have consumed this snapshot. RT64 owns the
    // resident render targets; keeping a snapshot is not proof of residency.
    state.graphics_snapshot_pool.push_back({std::move(pending.rdram),
        state.rt64_shell->rdram_snapshot_generation(),std::move(pending.overlay_dirty),pending.overlays_initialized});
    if (state.guest_os_probe) continue; // device event owns status/IRQ; original OS owns messages
    complete_guest_sp_status(state, target);
    if (state.scheduler->send(sp->second.first, sp->second.second, false) !=
        hle::kOsSuccess)
      fail_closed_dispatch(state, "rsp", "sp-completion", target);
    const std::int32_t dp_delivery =
        state.scheduler->send(dp->second.first, dp->second.second, false);
    if (dp_delivery != hle::kOsSuccess && dp_delivery != hle::kOsFull)
      fail_closed_dispatch(state, "rsp", "dp-completion", target);
  }
  state.pending_graphics_tasks.clear();
}
#endif
} // namespace jfg::boot::native::detail
