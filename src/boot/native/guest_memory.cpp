#include "jfg/boot/native_periodic_deadline.hpp"
#include "jfg/boot/native_periodic_deadline.hpp"
#include "guest_memory.hpp"
#include "funcs.h"
#include "generated_lookup_entry.h"
#include <algorithm>
#include <cstring>
#include <limits>
namespace jfg::boot::native::detail {
std::uint64_t
MmioTrace::audio_payload_hash(std::uint32_t address,
                              std::uint32_t length) const noexcept {
  address &= 0x00ffffffU;
  if (address > device_rdram.size() || length > device_rdram.size() - address)
    return 0U;
  std::uint64_t hash = 14695981039346656037ULL;
  for (auto byte : device_rdram.subspan(address, length)) {
    hash ^= byte;
    hash *= 1099511628211ULL;
  }
  return hash;
}

void MmioTrace::record(const std::size_t page_index,
                       const std::uintptr_t address,
                       const bool write) noexcept {
  ++accesses;
  const auto offset = static_cast<std::uint32_t>(
      address - reinterpret_cast<std::uintptr_t>(pages[page_index]));
  const bool supported =
      page_index == 9U
          ? guest_pif_boot && offset == 0x7fcU
          : (offset & 3U) == 0U && offset <= kMmioLastRegister[page_index];
  if (!supported)
    ++unsupported_accesses;
  if (journal != nullptr) {
    journal->append(
        write ? NativeEventKind::kMmioWrite : NativeEventKind::kMmioRead,
        kMmioGuestBases[page_index] + offset, supported ? 1U : 0U, 4U);
  }
}

#if defined(_WIN32)
MmioTrace *g_mmio_trace = nullptr;

bool apply_sp_register_write(MmioTrace &trace, std::size_t page_index,
                             std::uint32_t offset, std::uint32_t &command) {
  const bool status_register = page_index == 0U && offset == 0x10U;
  const bool stopped = (trace.sp_status.read() & 0x1dU) == 1U;
  const bool valid =
      status_register ? trace.sp_status.command(command)
      : page_index == 8U
          ? (stopped && offset == 0U && trace.sp_dma.write_pc(command))
          : (stopped && trace.sp_dma.write(offset, command, trace.sp_rdram));
  if (!valid)
    return false;
  if (status_register) {
    const auto status = trace.sp_status.read();
    if (trace.guest_execution) {
      trace.mi_pending =
          (trace.mi_pending & ~1U) | (trace.sp_status.interrupt() ? 1U : 0U);
      if (stopped && (status & 1U) == 0U) {
        if (trace.sp_launch || trace.sp_deadline)
          trace.device_error = "overlapping-sp-launch";
        else
          trace.sp_launch = trace.guest_count;
      }
    }
    command = status;
  }
  return true;
}

std::optional<std::uint32_t> read_sp_register(MmioTrace &trace,
                                              std::size_t page_index,
                                              std::uint32_t offset) {
  return page_index == 8U
             ? (offset == 0U ? std::optional<std::uint32_t>{trace.sp_dma.pc()}
                             : std::nullopt)
         : offset == 0x10U
             ? std::optional<std::uint32_t>{trace.sp_status.read()}
             : trace.sp_dma.read(offset);
}

LONG CALLBACK mmio_exception_handler(EXCEPTION_POINTERS *exception) {
  if (g_mmio_trace == nullptr || exception == nullptr ||
      exception->ExceptionRecord == nullptr ||
      exception->ContextRecord == nullptr)
    return EXCEPTION_CONTINUE_SEARCH;
  const DWORD code = exception->ExceptionRecord->ExceptionCode;
  if (code == EXCEPTION_SINGLE_STEP && g_mmio_trace->pending_page != nullptr &&
      g_mmio_trace->pending_thread == GetCurrentThreadId()) {
    if (g_mmio_trace->pending_page_index == 9U && g_mmio_trace->pending_write) {
      std::uint32_t command = 0U;
      std::memcpy(&command,
                  reinterpret_cast<const void *>(g_mmio_trace->pending_address),
                  4U);
      if (!g_mmio_trace->guest_pif_boot ||
          g_mmio_trace->pending_address - reinterpret_cast<std::uintptr_t>(
                                              g_mmio_trace->pending_page) !=
              0x7fcU ||
          !g_mmio_trace->pif_boot.write(command)) {
        ++g_mmio_trace->unsupported_accesses;
        return EXCEPTION_CONTINUE_SEARCH;
      }
      const auto control = g_mmio_trace->pif_boot.read();
      std::memcpy(reinterpret_cast<void *>(g_mmio_trace->pending_address),
                  &control, 4U);
      if (g_mmio_trace->guest_execution) {
        if (!g_mmio_trace->si_dma.boot_command(g_mmio_trace->guest_count)) {
          ++g_mmio_trace->unsupported_accesses;
          return EXCEPTION_CONTINUE_SEARCH;
        }
        // Independently phased direct PIF-command-8 probe: SI assertion is
        // 2304 Count ticks after retirement, not immediate acknowledgement.
      }
    }
    if (g_mmio_trace->guest_sp_status && g_mmio_trace->pending_write &&
        (g_mmio_trace->pending_page_index == 0U ||
         g_mmio_trace->pending_page_index == 8U)) {
      std::uint32_t command = 0U;
      std::memcpy(&command,
                  reinterpret_cast<const void *>(g_mmio_trace->pending_address),
                  4U);
      const auto offset = static_cast<std::uint32_t>(
          g_mmio_trace->pending_address -
          reinterpret_cast<std::uintptr_t>(g_mmio_trace->pending_page));
      if (!apply_sp_register_write(*g_mmio_trace,
                                   g_mmio_trace->pending_page_index, offset,
                                   command)) {
        ++g_mmio_trace->unsupported_accesses;
        return EXCEPTION_CONTINUE_SEARCH;
      }
      if (g_mmio_trace->pending_page_index == 0U && offset == 0x10U)
        std::memcpy(reinterpret_cast<void *>(g_mmio_trace->pending_address),
                    &command, 4U);
    }
    if (g_mmio_trace->guest_mi_mask && g_mmio_trace->pending_write &&
        g_mmio_trace->pending_page_index == 2U &&
        g_mmio_trace->pending_address ==
            reinterpret_cast<std::uintptr_t>(g_mmio_trace->pending_page) +
                0x0cU) {
      std::uint32_t command = 0U;
      std::memcpy(&command,
                  reinterpret_cast<const void *>(g_mmio_trace->pending_address),
                  4U);
      if (!g_mmio_trace->mi_mask.command(command)) {
        ++g_mmio_trace->unsupported_accesses;
        return EXCEPTION_CONTINUE_SEARCH;
      }
      const auto mask = g_mmio_trace->mi_mask.read();
      std::memcpy(reinterpret_cast<void *>(g_mmio_trace->pending_address),
                  &mask, 4U);
    }
    if (g_mmio_trace->guest_execution && g_mmio_trace->pending_write) {
      ++g_mmio_trace->execution_io_revision;
      const auto offset = static_cast<std::uint32_t>(
          g_mmio_trace->pending_address -
          reinterpret_cast<std::uintptr_t>(g_mmio_trace->pending_page));
      std::uint32_t value = 0U;
      std::memcpy(&value,
                  reinterpret_cast<const void *>(g_mmio_trace->pending_address),
                  4U);
      g_mmio_trace->device_write_page =
          static_cast<std::uint32_t>(g_mmio_trace->pending_page_index);
      g_mmio_trace->device_write_offset = offset;
      g_mmio_trace->device_write_value = value;
      if (g_mmio_trace->pending_page_index == 2U && offset == 0U &&
          (value & 0x800U))
        g_mmio_trace->mi_pending &= ~32U;
      if (g_mmio_trace->pending_page_index == 3U) {
        if (offset == 0x10U) {
          if (g_mmio_trace->mi_pending & 8U)
            ++g_mmio_trace->vi_acknowledgements;
          g_mmio_trace->mi_pending &= ~8U;
        }
        if (offset == 0x18U)
          g_mmio_trace->vi_v_sync = value;
        if (offset == 0x1cU)
          g_mmio_trace->vi_h_sync = value;
      }
      if (g_mmio_trace->pending_page_index == 7U) {
        g_mmio_trace->device_si_offset = offset;
        g_mmio_trace->device_si_value = value;
        g_mmio_trace->device_si_prior_deadline =
            g_mmio_trace->si_dma.deadline();
        ++g_mmio_trace->device_si_sequence;
        if (!g_mmio_trace->si_dma.write(offset, value,
                                        g_mmio_trace->guest_count,
                                        g_mmio_trace->device_rdram))
          g_mmio_trace->device_error = "unsupported-si-transaction";
        g_mmio_trace->mi_pending = (g_mmio_trace->mi_pending & ~2U) |
                                   (g_mmio_trace->si_dma.interrupt() ? 2U : 0U);
      }
      if (g_mmio_trace->pending_page_index == 4U) {
        if (!g_mmio_trace->ai_dma.write(
                offset, value, g_mmio_trace->guest_count,
                g_mmio_trace->device_rdram.size(), g_mmio_trace->vi_period))
          g_mmio_trace->device_error = "unsupported-ai-transaction";
        g_mmio_trace->mi_pending = (g_mmio_trace->mi_pending & ~4U) |
                                   (g_mmio_trace->ai_dma.interrupt() ? 4U : 0U);
      }
      if (g_mmio_trace->pending_page_index == 5U) {

        g_mmio_trace->device_pi_offset = offset;
        g_mmio_trace->device_pi_value = value;
        if (!g_mmio_trace->pi_dma.write(
                offset, value, g_mmio_trace->guest_count,
                g_mmio_trace->device_rdram, g_mmio_trace->device_rom,
                [](void *device, bool to_ram, std::uint32_t cart,
                   std::uint32_t dram, std::uint32_t length,
                   std::span<std::uint8_t> ram) {
                  return static_cast<jfg::boot::ReferenceFlashBus *>(device)
                      ->transfer(to_ram, cart, dram, length, ram);
                },
                &g_mmio_trace->flash_bus,
                g_mmio_trace->native_rom_completion &&
                    g_mmio_trace->native_elapsed_time))
          g_mmio_trace->device_error = "unsupported-pi-transaction";
        g_mmio_trace->mi_pending =
            (g_mmio_trace->mi_pending & ~16U) |
            (g_mmio_trace->pi_dma.interrupt() ? 16U : 0U);
      }
      if (g_mmio_trace->pending_page_index >= 10U) {
        const bool valid =
            offset == 0U && (g_mmio_trace->pending_page_index == 10U
                                 ? g_mmio_trace->flash_bus.write_status(value)
                                 : g_mmio_trace->pending_page_index == 11U &&
                                       g_mmio_trace->flash_bus.command(
                                           value, g_mmio_trace->device_rdram));
        if (!valid)
          g_mmio_trace->device_error = "unsupported-flash-command";
      }
    }
    if (g_mmio_trace->pending_write && g_mmio_trace->pending_page_index == 4U) {
      const auto page =
          reinterpret_cast<std::uintptr_t>(g_mmio_trace->pending_page);
      const auto offset =
          static_cast<std::uint32_t>(g_mmio_trace->pending_address - page);
      std::uint32_t value = 0U;
      std::memcpy(&value,
                  reinterpret_cast<const void *>(g_mmio_trace->pending_address),
                  sizeof(value));
      ++g_mmio_trace->ai_register_writes;
      switch (offset) {
      case 0x00U:
        g_mmio_trace->ai_dram_address = value;
        break;
      case 0x04U:
        g_mmio_trace->ai_length = value;
        ++g_mmio_trace->ai_buffer_submissions;
        if (value != 0U) {
          if (g_mmio_trace->ai_submission_write -
                  g_mmio_trace->ai_submission_read >=
              MmioTrace::kAiSubmissionCapacity) {
            ++g_mmio_trace->ai_submission_overflows;
          } else {
            const std::size_t slot =
                static_cast<std::size_t>(g_mmio_trace->ai_submission_write %
                                         MmioTrace::kAiSubmissionCapacity);
            g_mmio_trace->ai_submissions[slot] = {g_mmio_trace->ai_dram_address,
                                                  value,
                                                  g_mmio_trace->ai_dac_rate};
            if (g_mmio_trace->trace_audio_payloads) {
              auto &submission = g_mmio_trace->ai_submissions[slot];
              submission.submitted_count = g_mmio_trace->guest_count;
              submission.payload_hash = g_mmio_trace->audio_payload_hash(
                  submission.address, submission.length);
            }
            ++g_mmio_trace->ai_submission_write;
          }
        }
        break;
      case 0x08U:
        g_mmio_trace->ai_control = value;
        break;
      case 0x10U:
        g_mmio_trace->ai_dac_rate = value;
        break;
      case 0x14U:
        g_mmio_trace->ai_bit_rate = value;
        break;
      default:
        break;
      }
    }
    DWORD previous = 0U;
    (void)VirtualProtect(g_mmio_trace->pending_page, kMmioPageSize,
                         PAGE_READWRITE | PAGE_GUARD, &previous);
    if (g_mmio_trace->profile_faults) {
      LARGE_INTEGER end{};
      QueryPerformanceCounter(&end);
      if (end.QuadPart >= g_mmio_trace->fault_started.QuadPart) {
        const auto elapsed = static_cast<std::uint64_t>(
            end.QuadPart - g_mmio_trace->fault_started.QuadPart);
        auto &cost =
            g_mmio_trace->fault_costs[g_mmio_trace->pending_page_index];
        cost.qpc += elapsed;
        cost.max_qpc = (std::max)(cost.max_qpc, elapsed);
      }
    }
    g_mmio_trace->pending_page = nullptr;
    g_mmio_trace->pending_page_index = SIZE_MAX;
    g_mmio_trace->pending_address = 0U;
    g_mmio_trace->pending_write = false;
    g_mmio_trace->pending_thread = 0U;
    exception->ContextRecord->EFlags &= ~DWORD{0x100U};
    return EXCEPTION_CONTINUE_EXECUTION;
  }
  if (code != STATUS_GUARD_PAGE_VIOLATION ||
      exception->ExceptionRecord->NumberParameters < 2U)
    return EXCEPTION_CONTINUE_SEARCH;
  const auto address = static_cast<std::uintptr_t>(
      exception->ExceptionRecord->ExceptionInformation[1]);
  for (std::size_t index = 0U; index < g_mmio_trace->pages.size(); ++index) {
    const auto page =
        reinterpret_cast<std::uintptr_t>(g_mmio_trace->pages[index]);
    if (address < page || address >= page + kMmioPageSize)
      continue;
    const bool write =
        exception->ExceptionRecord->ExceptionInformation[0] == 1U;
    const auto offset = static_cast<std::uint32_t>(address - page);
    if (g_mmio_trace->profile_faults) {
      QueryPerformanceCounter(&g_mmio_trace->fault_started);
      auto &cost = g_mmio_trace->fault_costs[index];
      if (write)
        ++cost.writes;
      else
        ++cost.reads;
    }
    if (g_mmio_trace->guest_execution && !write && index >= 10U) {
      if (index != 10U || offset != 0U)
        g_mmio_trace->device_error = "unsupported-flash-read";
      const auto value = g_mmio_trace->flash_bus.status();
      std::memcpy(reinterpret_cast<void *>(address), &value, 4U);
    }
    if (g_mmio_trace->guest_execution && !write && index == 5U) {
      const auto value = g_mmio_trace->pi_dma.read(offset);
      if (!value)
        g_mmio_trace->device_error = "unsupported-pi-register";
      const auto result = value.value_or(0U);
      std::memcpy(reinterpret_cast<void *>(address), &result, 4U);
    }
    if (g_mmio_trace->guest_execution && !write && index == 4U) {
      const auto value =
          g_mmio_trace->ai_dma.read(offset, g_mmio_trace->guest_count);
      if (!value)
        g_mmio_trace->device_error = "unsupported-ai-register";
      const auto result = value.value_or(0U);
      std::memcpy(reinterpret_cast<void *>(address), &result, 4U);
    }
    if (g_mmio_trace->guest_execution && !write && index == 7U) {
      const auto value = g_mmio_trace->si_dma.read(offset);
      if (!value)
        g_mmio_trace->device_error = "unsupported-si-register";
      const auto result = value.value_or(0U);
      std::memcpy(reinterpret_cast<void *>(address), &result, 4U);
    }
    if (g_mmio_trace->guest_execution && !write && index == 2U && offset == 8U)
      std::memcpy(reinterpret_cast<void *>(address), &g_mmio_trace->mi_pending,
                  4U);
    if (g_mmio_trace->guest_execution && !write && index == 3U &&
        offset == 0x10U) {
      const auto origin = g_mmio_trace->vi_next - g_mmio_trace->vi_period;
      const auto elapsed =
          g_mmio_trace->native_elapsed_time
              ? jfg::boot::native_periodic_phase(g_mmio_trace->guest_count,
                                                 g_mmio_trace->vi_next,
                                                 g_mmio_trace->vi_period)
              : g_mmio_trace->guest_count - origin;
      const auto line = g_mmio_trace->vi_period == 783520U
                            ? static_cast<std::uint32_t>(
                                  (elapsed * 263U) / g_mmio_trace->vi_period) *
                                  2U
                            : static_cast<std::uint32_t>(elapsed / 1500U) & ~1U;
      std::memcpy(reinterpret_cast<void *>(address), &line, 4U);
    }
    if (index == 9U && (!g_mmio_trace->guest_pif_boot || offset != 0x7fcU)) {
      ++g_mmio_trace->unsupported_accesses;
      return EXCEPTION_CONTINUE_SEARCH;
    }
    if (!write && index == 9U) {
      const auto control = g_mmio_trace->pif_boot.read();
      std::memcpy(reinterpret_cast<void *>(address), &control, 4U);
    }
    if (!write && g_mmio_trace->guest_sp_status &&
        (index == 0U || index == 8U)) {
      const auto value = read_sp_register(*g_mmio_trace, index, offset);
      if (!value.has_value()) {
        ++g_mmio_trace->unsupported_accesses;
        return EXCEPTION_CONTINUE_SEARCH;
      }
      std::memcpy(reinterpret_cast<void *>(address), &*value, 4U);
    }
    if (!write && g_mmio_trace->guest_mi_mask && index == 2U &&
        offset == 0x0cU) {
      const auto mask = g_mmio_trace->mi_mask.read();
      std::memcpy(reinterpret_cast<void *>(address), &mask, 4U);
    }
    if (!g_mmio_trace->guest_execution && !write && index == 4U &&
        offset == 0x04U) {
      std::memcpy(reinterpret_cast<void *>(address),
                  &g_mmio_trace->ai_emulated_remaining_length,
                  sizeof(g_mmio_trace->ai_emulated_remaining_length));
    }
    g_mmio_trace->record(index, address, write);
    g_mmio_trace->pending_page = g_mmio_trace->pages[index];
    g_mmio_trace->pending_page_index = index;
    g_mmio_trace->pending_address = address;
    g_mmio_trace->pending_write = write;
    g_mmio_trace->pending_thread = GetCurrentThreadId();
    exception->ContextRecord->EFlags |= DWORD{0x100U};
    return EXCEPTION_CONTINUE_EXECUTION;
  }
  return EXCEPTION_CONTINUE_SEARCH;
}
#endif

GuestBacking::~GuestBacking() {
#if defined(_WIN32)
  if (exception_handler_ != nullptr)
    (void)RemoveVectoredExceptionHandler(exception_handler_);
  if (g_mmio_trace == &mmio_trace_)
    g_mmio_trace = nullptr;
  if (alias_ != nullptr)
    UnmapViewOfFile(alias_);
  if (cart_cached_ != nullptr)
    UnmapViewOfFile(cart_cached_);
  if (cart_uncached_ != nullptr)
    UnmapViewOfFile(cart_uncached_);
  if (base_ != nullptr)
    UnmapViewOfFile(base_);
  for (void *page : mmio_)
    if (page != nullptr)
      (void)VirtualFree(page, 0U, MEM_RELEASE);
  for (void *region : overlays_)
    if (region != nullptr)
      (void)VirtualFree(region, 0U, MEM_RELEASE);
  release_gaps();
  if (mapping_ != nullptr)
    CloseHandle(mapping_);
  if (rom_mapping_ != nullptr)
    CloseHandle(rom_mapping_);
#endif
}

bool GuestBacking::create() {
#if defined(_WIN32)
  mapping_ = CreateFileMappingW(INVALID_HANDLE_VALUE, nullptr, PAGE_READWRITE,
                                0U, static_cast<DWORD>(kRdramSize), nullptr);
  rom_mapping_ =
      CreateFileMappingW(INVALID_HANDLE_VALUE, nullptr, PAGE_READWRITE, 0U,
                         static_cast<DWORD>(kRomSize), nullptr);
  if (mapping_ == nullptr || rom_mapping_ == nullptr)
    return false;
  for (unsigned attempt = 0U; attempt < 16U; ++attempt) {
    void *candidate =
        VirtualAlloc(nullptr, kGuestAddressSpan, MEM_RESERVE, PAGE_NOACCESS);
    if (candidate == nullptr)
      return false;
    (void)VirtualFree(candidate, 0U, MEM_RELEASE);
    base_ = static_cast<std::uint8_t *>(MapViewOfFileEx(
        mapping_, FILE_MAP_ALL_ACCESS, 0U, 0U, kRdramSize, candidate));
    if (base_ == nullptr)
      continue;
    void *alias_address = reinterpret_cast<void *>(
        reinterpret_cast<std::uintptr_t>(base_) + kKseg1AliasOffset);
    alias_ = static_cast<std::uint8_t *>(MapViewOfFileEx(
        mapping_, FILE_MAP_ALL_ACCESS, 0U, 0U, kRdramSize, alias_address));
    void *const cart_cached_address = reinterpret_cast<void *>(
        reinterpret_cast<std::uintptr_t>(base_) + kCartCachedAliasOffset);
    cart_cached_ = static_cast<std::uint8_t *>(
        MapViewOfFileEx(rom_mapping_, FILE_MAP_ALL_ACCESS, 0U, 0U, kRomSize,
                        cart_cached_address));
    void *const cart_uncached_address = reinterpret_cast<void *>(
        reinterpret_cast<std::uintptr_t>(base_) + kCartUncachedAliasOffset);
    cart_uncached_ = static_cast<std::uint8_t *>(MapViewOfFileEx(
        rom_mapping_, FILE_MAP_READ, 0U, 0U, kRomSize, cart_uncached_address));
    bool mmio_ok = alias_ != nullptr && cart_cached_ == cart_cached_address &&
                   cart_uncached_ == cart_uncached_address;
    for (std::size_t index = 0U; mmio_ok && index < mmio_.size(); ++index) {
      void *const page_address = reinterpret_cast<void *>(
          reinterpret_cast<std::uintptr_t>(base_) + kMmioHostOffsets[index]);
      mmio_[index] = VirtualAlloc(page_address, kMmioPageSize,
                                  MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
      mmio_ok = mmio_[index] == page_address;
    }
    if (mmio_ok) {
      overlays_.assign(jfg_generated_section_count(), nullptr);
      bool overlays_ok = true;
      for (std::uint32_t section = 0U;
           overlays_ok && section < overlays_.size(); ++section) {
        JfgGeneratedSectionMetadata metadata{};
        if (jfg_generated_section_metadata(section, &metadata) == 0) {
          overlays_ok = false;
          break;
        }
        if (metadata.is_overlay != 1U)
          continue;
        const std::uint64_t extent = std::uint64_t{metadata.text_size} +
                                     metadata.data_size + metadata.bss_size;
        const std::uint64_t allocation =
            (extent + kWindowsAllocationGranularity - 1U) &
            ~(std::uint64_t{kWindowsAllocationGranularity} - 1U);
        const std::uint64_t host_offset =
            std::uint64_t{0x80000000U} + metadata.linked_vram;
        if (extent == 0U || allocation > SIZE_MAX ||
            host_offset > kGuestAddressSpan ||
            allocation > kGuestAddressSpan - host_offset) {
          overlays_ok = false;
          break;
        }
        void *const overlay_address = reinterpret_cast<void *>(
            reinterpret_cast<std::uintptr_t>(base_) + host_offset);
        overlays_[section] =
            VirtualAlloc(overlay_address, static_cast<std::size_t>(allocation),
                         MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
        overlays_ok = overlays_[section] == overlay_address;
      }
      // The span was released so the views could be placed; anything
      // the host allocated into a gap since then would be reachable by
      // a wild guest pointer instead of faulting. Re-reserve every
      // remaining free gap as no-access memory, and treat a gap that is
      // no longer free as a failed attempt.
      if (overlays_ok && reserve_gaps())
        return true;
    }
    release_gaps();
    for (void *&region : overlays_) {
      if (region != nullptr)
        (void)VirtualFree(region, 0U, MEM_RELEASE);
      region = nullptr;
    }
    overlays_.clear();
    for (void *&page : mmio_) {
      if (page != nullptr)
        (void)VirtualFree(page, 0U, MEM_RELEASE);
      page = nullptr;
    }
    if (alias_ != nullptr)
      UnmapViewOfFile(alias_);
    alias_ = nullptr;
    if (cart_cached_ != nullptr)
      UnmapViewOfFile(cart_cached_);
    cart_cached_ = nullptr;
    if (cart_uncached_ != nullptr)
      UnmapViewOfFile(cart_uncached_);
    cart_uncached_ = nullptr;
    UnmapViewOfFile(base_);
    base_ = nullptr;
  }
  return false;
#else
  bytes_.resize(kRdramSize);
  return true;
#endif
}

std::span<std::uint8_t> GuestBacking::bytes() noexcept {
#if defined(_WIN32)
  return {base_, base_ == nullptr ? 0U : kRdramSize};
#else
  return bytes_;
#endif
}

#if defined(_WIN32)
std::size_t GuestBacking::reserved_gap_count() const noexcept {
  return gaps_.size();
}

bool GuestBacking::reserve_gaps() {
  const std::uintptr_t begin = reinterpret_cast<std::uintptr_t>(base_);
  const std::uintptr_t end = begin + kGuestAddressSpan;
  std::uintptr_t cursor = begin;
  while (cursor < end) {
    MEMORY_BASIC_INFORMATION info{};
    if (VirtualQuery(reinterpret_cast<void *>(cursor), &info, sizeof(info)) ==
        0U)
      return false;
    const std::uintptr_t region_begin =
        reinterpret_cast<std::uintptr_t>(info.BaseAddress);
    const std::uintptr_t region_end = region_begin + info.RegionSize;
    if (info.State == MEM_FREE) {
      // Reservations are placed at allocation granularity. A free tail
      // below the next 64 KiB boundary cannot be claimed by any other
      // allocation either, so it is safe to leave unreserved.
      const std::uintptr_t gap_begin =
          ((std::max)(region_begin, cursor) + kWindowsAllocationGranularity -
           1U) &
          ~(std::uintptr_t{kWindowsAllocationGranularity} - 1U);
      const std::uintptr_t gap_end = (std::min)(region_end, end);
      if (gap_begin < gap_end) {
        void *const reserved =
            VirtualAlloc(reinterpret_cast<void *>(gap_begin),
                         gap_end - gap_begin, MEM_RESERVE, PAGE_NOACCESS);
        if (reserved != reinterpret_cast<void *>(gap_begin)) {
          if (reserved != nullptr)
            (void)VirtualFree(reserved, 0U, MEM_RELEASE);
          return false;
        }
        gaps_.push_back(reserved);
      }
    }
    if (region_end <= cursor)
      return false;
    cursor = region_end;
  }
  return true;
}

void GuestBacking::release_gaps() noexcept {
  for (void *gap : gaps_)
    if (gap != nullptr)
      (void)VirtualFree(gap, 0U, MEM_RELEASE);
  gaps_.clear();
}

#endif

bool GuestBacking::arm_mmio_monitor(EventJournal &journal) noexcept {
#if defined(_WIN32)
  mmio_trace_.journal = &journal;
  mmio_trace_.pages = mmio_;
  g_mmio_trace = &mmio_trace_;
  exception_handler_ = AddVectoredExceptionHandler(1U, mmio_exception_handler);
  if (exception_handler_ == nullptr) {
    g_mmio_trace = nullptr;
    return false;
  }
  for (void *page : mmio_) {
    DWORD previous = 0U;
    if (page == nullptr ||
        VirtualProtect(page, kMmioPageSize, PAGE_READWRITE | PAGE_GUARD,
                       &previous) == 0)
      return false;
  }
  return true;
#else
  (void)journal;
  return false;
#endif
}

const MmioTrace &GuestBacking::mmio_trace() const noexcept {
  return mmio_trace_;
}

MmioTrace &GuestBacking::mmio_trace() noexcept { return mmio_trace_; }

bool GuestBacking::load_overlay_images(
    const std::span<const std::uint8_t> rom) noexcept {
#if defined(_WIN32)
  if (rom.size() != kRomSize || cart_cached_ == nullptr ||
      cart_uncached_ == nullptr ||
      overlays_.size() != jfg_generated_section_count())
    return false;
  for (std::size_t index = 0U; index < rom.size(); ++index)
    cart_cached_[index ^ 3U] = rom[index];
  DWORD previous = 0U;
  if (VirtualProtect(cart_cached_, kRomSize, PAGE_READONLY, &previous) == 0 ||
      VirtualProtect(cart_uncached_, kRomSize, PAGE_READONLY, &previous) == 0)
    return false;
  for (std::uint32_t section = 0U; section < overlays_.size(); ++section) {
    JfgGeneratedSectionMetadata metadata{};
    if (jfg_generated_section_metadata(section, &metadata) == 0)
      return false;
    if (metadata.is_overlay != 1U)
      continue;
    const std::uint64_t initialized =
        std::uint64_t{metadata.text_size} + metadata.data_size;
    if (overlays_[section] == nullptr || metadata.rom_start > rom.size() ||
        initialized > rom.size() - metadata.rom_start)
      return false;
    auto *destination = static_cast<std::uint8_t *>(overlays_[section]);
    for (std::size_t index = 0U; index < static_cast<std::size_t>(initialized);
         ++index) {
      destination[index ^ 3U] = rom[metadata.rom_start + index];
    }
  }
  return true;
#else
  (void)rom;
  return false;
#endif
}
} // namespace jfg::boot::native::detail
