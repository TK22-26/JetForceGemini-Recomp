// Project-authored host adapter. Contains no generated game instructions.
#include "brokered-rsp.hpp"
#include "jfg/evidence/g2_private_task_adapter.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <ranges>
#include <vector>

#if defined(_WIN32)
#include <fcntl.h>
#include <io.h>
#include <share.h>
#else
#include <fcntl.h>
#include <unistd.h>
#endif

RspExitReason jfg_audio_probe(std::uint8_t* rdram, std::uint32_t ucode_addr);
extern std::uint32_t jfg_audio_probe_overlay_swaps;
extern std::uint32_t jfg_audio_probe_overlay_variant_one;

std::uint8_t dmem[0x1000]{};
std::uint16_t rspReciprocals[512]{};
std::uint16_t rspInverseSquareRoots[512]{};

namespace {

class ScopedStdoutSilence final {
public:
    ScopedStdoutSilence() noexcept {
        (void)std::fflush(stdout);
#if defined(_WIN32)
        saved_ = _dup(_fileno(stdout));
        if (_sopen_s(&null_, "NUL", _O_WRONLY, _SH_DENYNO, 0) != 0) {
            null_ = -1;
        }
        valid_ = saved_ >= 0 && null_ >= 0 &&
            _dup2(null_, _fileno(stdout)) == 0;
#else
        saved_ = dup(STDOUT_FILENO);
        null_ = open("/dev/null", O_WRONLY | O_CLOEXEC);
        valid_ = saved_ >= 0 && null_ >= 0 &&
            dup2(null_, STDOUT_FILENO) >= 0;
#endif
    }

    ~ScopedStdoutSilence() noexcept {
        (void)std::fflush(stdout);
        if (saved_ >= 0) {
#if defined(_WIN32)
            (void)_dup2(saved_, _fileno(stdout));
            (void)_close(saved_);
#else
            (void)dup2(saved_, STDOUT_FILENO);
            (void)close(saved_);
#endif
        }
        if (null_ >= 0) {
#if defined(_WIN32)
            (void)_close(null_);
#else
            (void)close(null_);
#endif
        }
    }

    [[nodiscard]] bool valid() const noexcept { return valid_; }

private:
    int saved_ = -1;
    int null_ = -1;
    bool valid_ = false;
};

[[nodiscard]] std::uint32_t be32(
    const std::span<const std::byte> bytes,
    const std::size_t offset) noexcept {
    if (offset > bytes.size() || bytes.size() - offset < 4U) {
        return 0U;
    }
    return (std::uint32_t(bytes[offset]) << 24U) |
        (std::uint32_t(bytes[offset + 1U]) << 16U) |
        (std::uint32_t(bytes[offset + 2U]) << 8U) |
        std::uint32_t(bytes[offset + 3U]);
}

[[nodiscard]] jfg::AudioRspExitReason map_exit(
    const RspExitReason reason) noexcept {
    switch (reason) {
    case RspExitReason::Broke:
        return jfg::AudioRspExitReason::broke;
    case RspExitReason::ImemOverrun:
        return jfg::AudioRspExitReason::imem_overrun;
    case RspExitReason::UnhandledJumpTarget:
        return jfg::AudioRspExitReason::unhandled_jump_target;
    case RspExitReason::Unsupported:
        return jfg::AudioRspExitReason::unsupported;
    case RspExitReason::SwapOverlay:
        return jfg::AudioRspExitReason::swap_overlay;
    case RspExitReason::UnhandledResumeTarget:
        return jfg::AudioRspExitReason::unhandled_resume_target;
    case RspExitReason::Invalid:
        return jfg::AudioRspExitReason::invalid;
    }
    return jfg::AudioRspExitReason::invalid;
}

class PrivateGeneratedAudioProgram final
    : public jfg::evidence::G2PrivateAudioProgram {
public:
    explicit PrivateGeneratedAudioProgram(
        const jfg::evidence::G2PrivateAudioProgramInput& input) noexcept
        : descriptor_(input.task_descriptor),
          active_program_(input.active_program),
          ucode_data_(input.program_data),
          output_address_(input.output_address),
          output_size_(input.output_size) {}

    [[nodiscard]] jfg::AudioRspProgramReport execute(
        const jfg::AudioBackendTaskView& task,
        jfg::AudioMemoryAccess& memory) override {
        ++stats_.generated_entry_count;
        stats_.abi_version = jfg::evidence::kG2PrivateTaskAdapterAbiVersion;
        stats_.active_program_sha256 =
            jfg::evidence::g2_private_program_digest(active_program_);
        std::vector<std::byte> brokered_program(active_program_.size());
        const std::uint32_t program_address =
            be32(descriptor_, 16U) & 0x7FFFFFU;
        if (!std::ranges::equal(task.active_program, active_program_) ||
            !memory.read(0U, program_address, brokered_program) ||
            !std::ranges::equal(brokered_program, active_program_)) {
            return {};
        }
        ++stats_.program_identity_check_count;
        std::ranges::fill(dmem, 0U);
        for (std::size_t index = 0U; index < descriptor_.size(); ++index) {
            dmem[0xFC0U + (index ^ 3U)] =
                static_cast<std::uint8_t>(descriptor_[index]);
        }
        for (std::size_t index = 0U; index < ucode_data_.size(); ++index) {
            dmem[index ^ 3U] = static_cast<std::uint8_t>(ucode_data_[index]);
        }

        private_audio::BrokerState broker{
            &memory,
            output_address_,
            output_size_,
        };
        jfg_audio_probe_overlay_swaps = 0U;
        jfg_audio_probe_overlay_variant_one = 0U;
        private_audio::active_broker = &broker;
        const ScopedStdoutSilence silence;
        const RspExitReason exit_reason = silence.valid()
            ? jfg_audio_probe(nullptr, be32(descriptor_, 16U))
            : RspExitReason::Invalid;
        private_audio::active_broker = nullptr;

        stats_.input_read_operation_count = broker.input_operations + 1U;
        stats_.region_write_operation_count = broker.region_write_operations;
        stats_.output_write_operation_count = broker.output_operations;

        jfg::AudioRspProgramReport report{};
        report.exit_reason = broker.violation
            ? jfg::AudioRspExitReason::invalid
            : map_exit(exit_reason);
        report.selected_variant = jfg_audio_probe_overlay_variant_one > 0U
            ? jfg::AudioProgramVariant::secondary
            : jfg::AudioProgramVariant::primary;
        report.parse_complete = !broker.violation &&
            exit_reason == RspExitReason::Broke;
        report.parsed_command_count =
            task.command_stream.size() / jfg::kAudioCommandAlignmentBytes;
        report.input_read_operation_count = broker.input_operations + 1U;
        report.input_bytes_read = broker.input_bytes + active_program_.size();
        report.region_write_operation_count = broker.region_write_operations;
        report.region_bytes_written = broker.region_write_bytes;
        report.output_write_operation_count = broker.output_operations;
        report.output_bytes_written = broker.output_bytes;
        return report;
    }

    [[nodiscard]] jfg::evidence::G2PrivateAudioProgramStats
    stats() const noexcept override {
        return stats_;
    }

private:
    std::span<const std::byte> descriptor_;
    std::span<const std::byte> active_program_;
    std::span<const std::byte> ucode_data_;
    std::uint32_t output_address_ = 0U;
    std::size_t output_size_ = 0U;
    jfg::evidence::G2PrivateAudioProgramStats stats_{};
};

}  // namespace

extern "C" jfg::evidence::G2PrivateAudioProgram*
jfg_g2_private_audio_program_v2(
    const jfg::evidence::G2PrivateAudioProgramInput& input) noexcept {
    try {
        if (input.task_descriptor.size() != 64U ||
            input.active_program.empty() || input.program_data.empty() ||
            input.active_program.size() >
                jfg::kMaximumAudioActiveProgramBytes ||
            input.active_program.size() %
                    jfg::kAudioInstructionAlignmentBytes != 0U ||
            input.program_data.size() > jfg::kMaximumAudioProgramDataBytes ||
            input.output_size == 0U ||
            input.output_size > jfg::kMaximumAudioOutputBytes) {
            return nullptr;
        }
        return new PrivateGeneratedAudioProgram(input);
    } catch (...) {
        return nullptr;
    }
}
