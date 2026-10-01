#pragma once
// Independently authored corrected-Mupen cartridge flash profile, qualified by
// isolated command/DMA probes. This is not physical flash timing. The existing
// save store owns bytes; the device owns command mode and CPU-visible status.
#include "jfg/runtime/save_device_runtime.hpp"
#include <array>
#include <cstdint>
#include <optional>
#include <span>

namespace jfg::boot {
class ReferenceFlashBus final {
public:
  void bind(jfg::FlashRamStore& store) { store_ = &store; }
  [[nodiscard]] std::uint32_t status() const { return status_; }
  [[nodiscard]] std::uint64_t mutations() const { return mutations_; }
  // The original SDK's zero write to the status aperture has no observable
  // effect in this reference profile (separately tested in every mode).
  bool write_status(std::uint32_t value) const { return store_ && value == 0; }
  bool command(std::uint32_t word, std::span<const std::uint8_t> ram) {
    if (!store_) return false;
    switch (word >> 24) {
    case 0xe1:
      if ((word & 0xffffffU) != 0) return false;
      mode_ = Mode::id; status_ = 0x11118001U; return true;
    case 0xf0:
      if ((word & 0xffffffU) != 0) return false;
      mode_ = Mode::array; status_ = 0x11118004U; return true;
    case 0xb4:
      if ((word & 0xffffffU) != 0) return false;
      mode_ = Mode::write; return true;
    case 0x4b: case 0xa5:
      if ((word & 0xffffffU) >= jfg::kFlashRamPageCount) return false;
      page_ = word & 0xffffffU;
      if ((word >> 24) == 0xa5) status_ = 0x11118004U;
      return true;
    case 0x78:
      if ((word & 0xffffffU) != 0) return false;
      mode_ = Mode::erase; status_ = 0x11118008U; return true;
    case 0xd2:
      if ((word & 0xffffffU) != 0) return false;
      if (mode_ == Mode::write) {
        if (!source_ || *source_ > ram.size() || 128U > ram.size() - *source_) return false;
        std::array<std::uint8_t, 128> page{};
        for (unsigned i = 0; i < page.size(); ++i) page[i] = ram[(*source_ + i) ^ 3U];
        if (!store_->stage_write(page).ok() || !store_->begin_program(page_).ok() || !store_->complete().ok()) return false;
        ++mutations_;
      } else if (mode_ == Mode::erase) {
        if (!store_->begin_erase_page(page_).ok() || !store_->complete().ok()) return false;
        ++mutations_;
      }
      mode_ = Mode::idle;
      return true;
    default: return false;
    }
  }
  bool transfer(bool cart_to_ram, std::uint32_t cart, std::uint32_t dram,
                std::uint32_t length, std::span<std::uint8_t> ram) {
    if (!store_ || (ram.size() & 3U) || (dram & 3U) || dram > ram.size() ||
        length > ram.size() - dram || cart < 0x08000000U || cart >= 0x08010000U) return false;
    const auto offset = cart - 0x08000000U;
    if (!cart_to_ram) {
      if (mode_ != Mode::write || offset != 0 || length != 128) return false;
      source_ = dram; // reference reads this buffer on execute, not on DMA
      return true;
    }
    if (mode_ == Mode::id) {
      if (offset != 0 || length != 8) return false;
      constexpr std::array<std::uint8_t, 8> id{0x11,0x11,0x80,0x01,0x00,0xc2,0x00,0x00};
      for (unsigned i = 0; i < id.size(); ++i) ram[(dram + i) ^ 3U] = id[i];
      return true;
    }
    if (mode_ != Mode::array || (offset & 63U) || length == 0 || (length & 127U)) return false;
    const auto bytes = store_->read(offset * 2U, length);
    if (!bytes.ok()) return false;
    for (unsigned i = 0; i < length; ++i) ram[(dram + i) ^ 3U] = bytes.bytes[i];
    return true;
  }
private:
  enum class Mode { idle, id, array, write, erase };
  jfg::FlashRamStore* store_ = nullptr;
  Mode mode_ = Mode::idle;
  std::uint32_t status_ = 0, page_ = 0;
  std::optional<std::uint32_t> source_;
  std::uint64_t mutations_ = 0;
};
} // namespace jfg::boot
