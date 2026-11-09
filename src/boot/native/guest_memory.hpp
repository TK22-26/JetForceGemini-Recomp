#pragma once
#ifndef NOMINMAX
#define NOMINMAX
#endif
#if defined(_WIN32)
#include <windows.h>
#endif
#include "event_journal.hpp"
#include "jfg/boot/vi_device_clock.hpp"
#include "jfg/boot/mi_interrupt_mask.hpp"
#include "jfg/boot/original_timing_ai_dma.hpp"
#include "jfg/boot/original_timing_pi_dma.hpp"
#include "jfg/boot/flash_device.hpp"
#include "jfg/boot/reference_pif_boot.hpp"
#include "jfg/boot/reference_si_dma.hpp"
#include "jfg/boot/reference_sp_dma.hpp"
#include "jfg/boot/sp_status.hpp"
#include "runtime_constants.hpp"
#include <optional>
#include <span>
#include <vector>

namespace jfg::boot::native::detail {
struct MmioTrace final {
  // Explicit diagnostic reference-device ownership. The cooperative control
  // continues using its existing register behavior unless this is enabled.
  bool guest_execution = false;
  bool native_elapsed_time = false;
  bool native_rom_completion = false;
  std::uint64_t guest_count = 0U;
  std::uint64_t vi_next = 0U;
  std::uint64_t execution_io_revision = 0U;
  // vi_next is only the dispatch cache; the VI device owns scan phase.
  jfg::boot::ViDeviceClock vi_clock;
  std::uint32_t mi_pending = 0U;
  std::uint64_t vi_acknowledgements = 0U;
  jfg::boot::ReferenceSiDma si_dma;
  jfg::boot::OriginalTimingPiDma pi_dma;
  jfg::boot::FlashDevice flash_bus;
  jfg::boot::OriginalTimingAiDma ai_dma;
  std::uint64_t persisted_flash_mutations = 0;
  std::optional<std::uint64_t> sp_launch, sp_deadline, dp_deadline;
  std::span<std::uint8_t> device_rdram;
  std::span<const std::uint8_t> device_rom;
  const char *device_error = nullptr;
  std::uint32_t device_write_page = 0U, device_write_offset = 0U,
                device_write_value = 0U;
  std::uint32_t device_pi_offset = 0U, device_pi_value = 0U;
  std::uint32_t device_si_offset = 0U, device_si_value = 0U;
  std::uint64_t device_si_sequence = 0U, traced_si_sequence = 0U;
  std::optional<std::uint64_t> device_si_prior_deadline;
  std::uint64_t traced_pi_transfers = 0U;
  struct AiSubmission final {
    std::uint32_t address = 0U;
    std::uint32_t length = 0U;
    std::uint32_t dac_rate = 0U;
    std::uint64_t submitted_count = 0U, payload_hash = 0U;
  };
  // PCM-capture-only ownership diagnostic. Compare the buffer at AI submission
  // and at host consumption; never change guest memory, clocks or queue order.
  bool trace_audio_payloads = false;
  std::uint64_t audio_payload_hash(std::uint32_t address,
                                   std::uint32_t length) const noexcept;
  static constexpr std::size_t kAiSubmissionCapacity = 2048U;

  EventJournal *journal = nullptr;
  std::array<void *, kMmioHostOffsets.size()> pages{};
  void *pending_page = nullptr;
  std::size_t pending_page_index = SIZE_MAX;
  std::uintptr_t pending_address = 0U;
  bool pending_write = false;
  // The handler is process-wide. Only the thread that touched the guarded
  // page is single-stepping on our behalf; a trap-flag exception on any
  // other thread (debugger, GPU driver) must be left alone.
  std::uint32_t pending_thread = 0U;
  std::uint64_t accesses = 0U;
  std::uint64_t unsupported_accesses = 0U;
  std::uint64_t ai_register_writes = 0U;
  std::uint64_t ai_buffer_submissions = 0U;
  std::uint32_t ai_dram_address = 0U;
  std::uint32_t ai_length = 0U;
  std::uint32_t ai_control = 0U;
  std::uint32_t ai_dac_rate = 0U;
  std::uint32_t ai_bit_rate = 0U;
  std::uint32_t ai_emulated_remaining_length = 0U;
  std::array<AiSubmission, kAiSubmissionCapacity> ai_submissions{};
  std::uint64_t ai_submission_write = 0U;
  std::uint64_t ai_submission_read = 0U;
  std::uint64_t ai_submission_overflows = 0U;
  bool guest_mi_mask = false;
  jfg::boot::MiInterruptMask mi_mask;
  bool direct_sp_access = false;
  bool direct_mi_mask_access = false;
  std::uint64_t direct_mi_mask_reads = 0, direct_mi_mask_writes = 0;
  std::uint64_t direct_sp_reads = 0, direct_sp_writes = 0;
  // Private attribution only. Counts actual guarded device accesses, excluding
  // the direct SP fast path. QPC spans include handler/single-step wall time,
  // including preemption, but not kernel dispatch before the handler begins.
  struct FaultCost {
    std::uint64_t reads = 0, writes = 0, qpc = 0, max_qpc = 0;
  };
  bool profile_faults = false;
  std::array<FaultCost, kMmioHostOffsets.size()> fault_costs{};
#if defined(_WIN32)
  LARGE_INTEGER fault_started{}, fault_frequency{};
#endif
  bool guest_sp_status = false;
  jfg::boot::SpStatus sp_status;
  jfg::boot::ReferenceSpDma sp_dma;
  std::span<const std::uint8_t> sp_rdram;
  bool guest_pif_boot = false;
  jfg::boot::ReferencePifBoot pif_boot;

  void record(const std::size_t page_index, const std::uintptr_t address,
              const bool write) noexcept;
};

class GuestBacking final {
public:
  GuestBacking() = default;
  ~GuestBacking();
  GuestBacking(const GuestBacking &) = delete;
  GuestBacking &operator=(const GuestBacking &) = delete;

  bool create();
  std::span<std::uint8_t> bytes() noexcept;

#if defined(_WIN32)
  [[nodiscard]] std::size_t reserved_gap_count() const noexcept;

private:
  bool reserve_gaps();

  void release_gaps() noexcept;

public:
#endif

  bool arm_mmio_monitor(EventJournal &journal) noexcept;

  [[nodiscard]] const MmioTrace &mmio_trace() const noexcept;
  [[nodiscard]] MmioTrace &mmio_trace() noexcept;

  bool load_overlay_images(const std::span<const std::uint8_t> rom) noexcept;

private:
#if defined(_WIN32)
  HANDLE mapping_ = nullptr;
  HANDLE rom_mapping_ = nullptr;
  std::uint8_t *base_ = nullptr;
  std::uint8_t *alias_ = nullptr;
  std::uint8_t *cart_cached_ = nullptr;
  std::uint8_t *cart_uncached_ = nullptr;
  std::array<void *, kMmioHostOffsets.size()> mmio_{};
  std::vector<void *> overlays_;
  std::vector<void *> gaps_;
  PVOID exception_handler_ = nullptr;
#else
  std::vector<std::uint8_t> bytes_;
#endif
  MmioTrace mmio_trace_{};
};

#if defined(_WIN32)
extern MmioTrace *g_mmio_trace;
bool apply_sp_register_write(MmioTrace &, std::size_t, std::uint32_t,
                             std::uint32_t &);
std::optional<std::uint32_t> read_sp_register(MmioTrace &, std::size_t,
                                              std::uint32_t);
#endif
} // namespace jfg::boot::native::detail
