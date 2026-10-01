#pragma once

// Boot driver and canonical checkpoint record (Phase 6).
//
// The driver is the reset-to-entry sequencer: it validates the cartridge,
// and only if the header is accepted does it build the world, install the
// entry, and run. An invalid ROM returns a safe report with no execution.
// The canonical checkpoint record is the stable, host-independent witness
// compared across runs and against the emulator oracle.

#include <cstdint>
#include <functional>
#include <optional>
#include <string>
#include <vector>

#include "jfg/boot/runtime.hpp"
#include "jfg/testkernel/journal.hpp"
#include "jfg/testkernel/scheduler.hpp"
#include "jfg/testkernel/world.hpp"

namespace jfg::boot {

inline constexpr std::size_t kBootRdramBytes = 8U * 1024U * 1024U;

struct BootConfig final {
    std::uint64_t target_retraces = 5U;
    std::uint64_t step_limit = 100'000U;
};

using BootInstaller = std::function<void(BootRuntime&)>;

// Runs a boot from raw cartridge bytes. Fails safe (no execution) when the
// ROM header is rejected.
[[nodiscard]] inline BootReport run_boot(
    std::vector<std::uint8_t> rom_bytes, const BootInstaller& install,
    const BootConfig config) {
    std::optional<RomImage> rom = RomImage::create(std::move(rom_bytes));
    if (!rom.has_value()) {
        BootReport report;
        report.status = BootStatus::kInvalidRom;
        return report; // nothing was executed
    }
    std::optional<World> world = World::create(kBootRdramBytes);
    if (!world.has_value()) {
        BootReport report;
        report.status = BootStatus::kTrapped;
        report.trap_operation = "world:creation";
        return report;
    }
    jfg::testkernel::VirtualClock clock;
    jfg::testkernel::Journal journal;
    jfg::testkernel::StateHashSchema schema{};
    BootRuntime runtime(
        *world, clock, journal, std::move(*rom), schema);
    if (install) {
        install(runtime);
    }
    return runtime.run(config.target_retraces, config.step_limit);
}

// A stable, comparable record of a boot outcome. Contains no host time, no
// pointers, and no ROM-derived bytes — only logical counts and digests.
[[nodiscard]] inline std::string canonical_checkpoint(const BootReport& report) {
    std::string text;
    text += "status=" + std::to_string(static_cast<std::uint32_t>(report.status));
    text += ";vi=" + std::to_string(report.vi_retraces);
    text += ";events=" + std::to_string(report.dispatched_events);
    text += ";threads=" + std::to_string(report.threads_created);
    text += ";rsp=" + std::to_string(report.rsp_tasks.size());
    text += ";stubs=" + std::to_string(report.stub_ledger.size());
    text += ";journal=" + report.journal_hex;
    text += ";state=" + report.state_hash_hex;
    return text;
}

} // namespace jfg::boot
