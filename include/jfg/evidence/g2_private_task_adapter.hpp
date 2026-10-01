#pragma once

#include "jfg/evidence/g2_paired_producer.hpp"
#include "jfg/runtime/audio_task_bridge.hpp"
#include "jfg/runtime/graphics_task_bridge.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <span>
#include <vector>

namespace jfg::evidence {

inline constexpr std::uint32_t kG2PrivateTaskAdapterAbiVersion = 2U;

using G2PrivateProgramDigest = std::array<std::byte, 32>;

[[nodiscard]] inline G2PrivateProgramDigest g2_private_program_digest(
    const std::span<const std::byte> bytes) {
    Sha256 hasher;
    hasher.update(bytes);
    return hasher.finish();
}

struct G2PrivateGraphicsBackendInput final {
    std::span<const std::byte> task_descriptor;
    std::uint32_t command_stream_address = 0U;
};

struct G2PrivateGraphicsBackendStats final {
    std::uint32_t abi_version = 0U;
    std::size_t backend_execution_count = 0U;
    std::size_t program_identity_check_count = 0U;
    G2PrivateProgramDigest active_program_sha256{};
};

// The tracked adapter executes the project-owned bounded semantic backend.
// Merely carrying active_program through GraphicsTaskView is not sufficient:
// stats() binds the bytes authenticated from brokered task memory before
// execution.  This is semantic G2 evidence, not rendered-pixel evidence.
class G2PrivateGraphicsBackend : public GraphicsTaskBackend {
public:
    ~G2PrivateGraphicsBackend() override = default;
    [[nodiscard]] virtual G2PrivateGraphicsBackendStats stats() const noexcept = 0;
};

struct G2PrivateGraphicsOracleResult final {
    std::vector<std::byte> bytes;
    std::size_t width = 0U;
    std::size_t height = 0U;
    std::size_t row_pitch_bytes = 0U;
    std::size_t bytes_per_pixel = 0U;
    std::size_t execution_count = 0U;
    G2PrivateProgramDigest active_program_sha256{};
};

struct G2PrivateGraphicsOracleInput final {
    std::span<const std::byte> task_descriptor;
    GraphicsTaskView task;
    std::span<const GraphicsReferencedMemoryRegion> referenced_regions;
};

struct G2PrivateAudioProgramStats final {
    std::uint32_t abi_version = 0U;
    std::size_t generated_entry_count = 0U;
    std::size_t input_read_operation_count = 0U;
    std::size_t region_write_operation_count = 0U;
    std::size_t output_write_operation_count = 0U;
    std::size_t program_identity_check_count = 0U;
    G2PrivateProgramDigest active_program_sha256{};
};

// The implementation is intentionally supplied only by an ignored, reviewed
// private build input.  A public producer cannot replace the generated RSP
// wrapper with a synthetic AudioRspProgram and still satisfy this ABI.
class G2PrivateAudioProgram : public AudioRspProgram {
public:
    ~G2PrivateAudioProgram() override = default;
    [[nodiscard]] virtual G2PrivateAudioProgramStats stats() const noexcept = 0;
};

struct G2PrivateAudioProgramInput final {
    std::span<const std::byte> task_descriptor;
    std::span<const std::byte> active_program;
    std::span<const std::byte> program_data;
    std::uint32_t output_address = 0U;
    std::size_t output_size = 0U;
};

struct G2PrivateAudioFallbackStats final {
    std::uint32_t abi_version = 0U;
    std::size_t generated_entry_count = 0U;
    std::size_t broker_write_count = 0U;
    std::size_t unsupported_return_count = 0U;
    std::size_t completion_count = 0U;
    std::size_t rolled_back_byte_count = 0U;
    std::size_t program_identity_check_count = 0U;
    G2PrivateProgramDigest active_program_sha256{};
};

struct G2PrivateAudioFallbackInput final {
    std::span<const std::byte> task_descriptor;
    std::span<const std::byte> active_program;
    std::span<const std::byte> program_data;
    std::span<const std::byte> command_stream;
    std::span<const std::byte> initial_memory;
    std::uint32_t output_address = 0U;
    std::size_t output_size = 0U;
};

struct G2PrivateAudioOracleResult final {
    std::vector<std::byte> bytes;
    std::size_t execution_count = 0U;
    G2PrivateProgramDigest active_program_sha256{};
};

struct G2PrivateAudioOracleInput final {
    std::span<const std::byte> task_descriptor;
    std::span<const std::byte> active_program;
    std::span<const std::byte> program_data;
    std::span<const std::byte> command_stream;
    std::span<const std::byte> initial_memory;
    std::uint32_t output_address = 0U;
    std::size_t output_size = 0U;
};

}  // namespace jfg::evidence

// The graphics native factory is project-owned and tracked. Graphics/audio
// oracle functions and the generated audio adapter remain unresolved until
// their distinct ignored private closures are supplied.
extern "C" [[nodiscard]] jfg::evidence::G2PrivateGraphicsBackend*
jfg_g2_graphics_bounded_backend_v2(
    const jfg::evidence::G2PrivateGraphicsBackendInput& input) noexcept;

extern "C" [[nodiscard]] bool jfg_g2_private_graphics_oracle_v2(
    const jfg::evidence::G2PrivateGraphicsOracleInput& input,
    jfg::evidence::G2PrivateGraphicsOracleResult& output) noexcept;

extern "C" [[nodiscard]] jfg::evidence::G2PrivateAudioProgram*
jfg_g2_private_audio_program_v2(
    const jfg::evidence::G2PrivateAudioProgramInput& input) noexcept;

extern "C" [[nodiscard]] bool jfg_g2_private_audio_fallback_v2(
    const jfg::evidence::G2PrivateAudioFallbackInput& input,
    jfg::evidence::G2PrivateAudioFallbackStats& output) noexcept;

extern "C" [[nodiscard]] bool jfg_g2_private_audio_oracle_v2(
    const jfg::evidence::G2PrivateAudioOracleInput& input,
    jfg::evidence::G2PrivateAudioOracleResult& output) noexcept;
