#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <span>

#include "jfg/runtime/audio_task_bridge.hpp"
#include "librecomp/rsp.hpp"

namespace private_audio {

struct BrokerState {
    jfg::AudioMemoryAccess* memory = nullptr;
    std::uint32_t output_address = 0U;
    std::size_t output_size = 0U;
    std::size_t input_operations = 0U;
    std::size_t input_bytes = 0U;
    std::size_t region_write_operations = 0U;
    std::size_t region_write_bytes = 0U;
    std::size_t output_operations = 0U;
    std::size_t output_bytes = 0U;
    bool violation = false;
    bool write_violation = false;
    std::uint32_t first_violation_address = 0U;
};

inline thread_local BrokerState* active_broker = nullptr;

inline void dma_read(
    const std::uint32_t dmem_address,
    std::uint32_t dram_address,
    std::uint32_t length) noexcept {
    ++length;
    dram_address &= 0xFFFFF8U;
    if (active_broker == nullptr || active_broker->memory == nullptr ||
        length > 0x1000U || dmem_address > 0x1000U - length) {
        if (active_broker != nullptr) {
            active_broker->violation = true;
            active_broker->first_violation_address = dram_address;
        }
        return;
    }

    std::array<std::byte, 0x1000U> bytes{};
    const std::span<std::byte> transfer(bytes.data(), length);
    if (!active_broker->memory->read(0U, dram_address & 0x7FFFFFU, transfer)) {
        active_broker->violation = true;
        active_broker->first_violation_address = dram_address;
        return;
    }
    ++active_broker->input_operations;
    active_broker->input_bytes += length;
    for (std::uint32_t index = 0U; index < length; ++index) {
        RSP_MEM_B(index, dmem_address) =
            static_cast<std::int8_t>(bytes[index]);
    }
}

inline void dma_write(
    const std::uint32_t dmem_address,
    std::uint32_t dram_address,
    std::uint32_t length) noexcept {
    ++length;
    dram_address &= 0xFFFFF8U;
    if (active_broker == nullptr || active_broker->memory == nullptr ||
        length > 0x1000U || dmem_address > 0x1000U - length) {
        if (active_broker != nullptr) {
            active_broker->violation = true;
            active_broker->write_violation = true;
            active_broker->first_violation_address = dram_address;
        }
        return;
    }

    std::array<std::byte, 0x1000U> bytes{};
    for (std::uint32_t index = 0U; index < length; ++index) {
        bytes[index] = static_cast<std::byte>(RSP_MEM_BU(index, dmem_address));
    }
    const std::span<const std::byte> transfer(bytes.data(), length);
    if (!active_broker->memory->write_region(
            0U, dram_address & 0x7FFFFFU, transfer)) {
        active_broker->violation = true;
        active_broker->write_violation = true;
        active_broker->first_violation_address = dram_address;
        return;
    }
    ++active_broker->region_write_operations;
    active_broker->region_write_bytes += length;

    if (dram_address >= active_broker->output_address) {
        const std::size_t output_offset = static_cast<std::size_t>(
            dram_address - active_broker->output_address);
        if (output_offset < active_broker->output_size &&
            length <= active_broker->output_size - output_offset) {
            if (!active_broker->memory->write_output(output_offset, transfer)) {
                active_broker->violation = true;
                active_broker->write_violation = true;
                active_broker->first_violation_address = dram_address;
                return;
            }
            ++active_broker->output_operations;
            active_broker->output_bytes += length;
        }
    }
}

}  // namespace private_audio

#undef DO_DMA_READ
#undef DO_DMA_WRITE
#define DO_DMA_READ(rd_len) \
    private_audio::dma_read(dma_mem_address, dma_dram_address, (rd_len))
#define DO_DMA_WRITE(wr_len) \
    private_audio::dma_write(dma_mem_address, dma_dram_address, (wr_len))
