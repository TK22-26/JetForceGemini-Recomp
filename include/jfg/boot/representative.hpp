#pragma once

// A representative deterministic boot program for Phase 6 (ROM-free).
//
// It exercises the full runtime surface the exit gate cares about — thread
// creation and priority ordering, message queues and events, a PI DMA load,
// an RSP task submission, and a VI retrace loop — and reaches stable, repeated
// VI activity. It stands in for the real game's boot the way the Phase 5
// synthetic functions stood in for real generated bodies: it validates the
// machinery deterministically without a ROM. The real entry-point bridge is
// the private research lane.

#include <cstdint>
#include <memory>
#include <optional>
#include <vector>

#include "jfg/boot/runtime.hpp"

namespace jfg::boot::representative {

inline constexpr std::uint32_t kDmaRamVaddr = 0x80300000U;
inline constexpr std::uint32_t kDmaCartOffset = 0x1000U;
inline constexpr std::uint32_t kDmaLength = 256U;
inline constexpr std::uint32_t kInitMarkerVaddr = 0x80310000U;
inline constexpr std::uint32_t kWorkerMarkerVaddr = 0x80320000U;
inline constexpr Message kDmaDoneMessage = 7U;
inline constexpr Message kViMessage = 1U;

// A synthetic cartridge with a valid .z64 header and deterministic contents.
[[nodiscard]] inline std::vector<std::uint8_t> synthetic_rom(
    const std::size_t size) {
    std::vector<std::uint8_t> rom(size < 0x2000U ? 0x2000U : size, 0U);
    rom[0] = 0x80U;
    rom[1] = 0x37U;
    rom[2] = 0x12U;
    rom[3] = 0x40U;
    for (std::size_t i = 4; i < rom.size(); ++i) {
        rom[i] = static_cast<std::uint8_t>((i * 31U + 7U) & 0xFFU);
    }
    return rom;
}

// Installs the boot's initial thread. Mirrors a minimal libultra boot: set up
// the VI client and an I/O queue, DMA an initial block in, initialize a little
// state, spawn a lower-priority worker, submit one RSP task, then service VI
// retraces.
inline void install(BootRuntime& runtime) {
    struct State final {
        int phase = 0;
        QueueId vi_queue = kInvalidId;
        QueueId pi_queue = kInvalidId;
        std::uint64_t vi_count = 0U;
    };
    auto state = std::make_shared<State>();

    (void)runtime.create_thread(
        10U, "boot-main",
        [state](BootRuntime& rt,
                std::optional<Message> received) -> ThreadDirective {
            (void)received;
            switch (state->phase) {
            case 0: {
                state->vi_queue = rt.create_queue("vi", 8U);
                state->pi_queue = rt.create_queue("pi", 1U);
                (void)rt.register_vi_client(state->vi_queue, kViMessage);
                (void)rt.start_pi_dma(
                    state->pi_queue, kDmaDoneMessage, kDmaRamVaddr,
                    kDmaCartOffset, kDmaLength);
                state->phase = 1;
                return {ThreadWait::kReceive, state->pi_queue};
            }
            case 1: {
                (void)rt.write_u32(kInitMarkerVaddr, 0x0000B007U);
                RspTaskRecord task;
                task.task_type = 1U; // a graphics task, captured for Phase 7
                task.data_ptr = kDmaRamVaddr;
                task.data_size = kDmaLength;
                (void)rt.submit_rsp_task(task);
                auto worker_done = std::make_shared<bool>(false);
                (void)rt.create_thread(
                    5U, "boot-worker",
                    [worker_done](BootRuntime& worker_rt,
                                  std::optional<Message>) -> ThreadDirective {
                        (void)worker_rt.write_u32(
                            kWorkerMarkerVaddr, 0xD0DE0077U);
                        *worker_done = true;
                        return {ThreadWait::kExit, kInvalidId};
                    });
                state->phase = 2;
                return {ThreadWait::kReceive, state->vi_queue};
            }
            default: {
                ++state->vi_count;
                return {ThreadWait::kReceive, state->vi_queue};
            }
            }
        });
}

} // namespace jfg::boot::representative
