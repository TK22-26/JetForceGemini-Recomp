#pragma once
// Original implementation of the SDK-visible MX29L1100 command contract.
// Model constants come from the pinned Ares reference; native-console timing
// has not been measured. The store owns bytes/durability, this device owns
// command mode, its latched page buffer and Count-domain completion.
#include "jfg/runtime/save_device_runtime.hpp"
#include <array>
#include <cstdint>
#include <optional>
#include <span>

namespace jfg::boot {
enum class FlashModel { mx29l1100 };
class FlashDevice final {
public:
  static constexpr std::uint8_t ready_status = 0x8CU;
  static constexpr std::uint32_t silicon_type = 0x11118001U;
  static constexpr std::uint32_t silicon_id = 0x00C2001EU;
  bool bind(jfg::FlashRamStore& store,FlashModel model,std::uint64_t count_hz,
            std::uint64_t initial_count=0) {
    if(store_ || store.status().busy || model!=FlashModel::mx29l1100 ||
       count_hz==0 || count_hz>1000000000ULL)return false;
    store_=&store;count_hz_=count_hz;now_=initial_count;buffer_.fill(0xFFU);return true;
  }
  [[nodiscard]] std::optional<std::uint64_t> deadline() const {return deadline_;}
  [[nodiscard]] std::uint64_t mutations() const {return mutations_;}
  [[nodiscard]] bool busy() const {return deadline_.has_value();}
  bool advance(std::uint64_t count) {
    if(!store_ || count<now_)return false;
    now_=count;
    if(deadline_ && count>=*deadline_) {
      if(!store_->complete().ok())return false;
      deadline_.reset();status_=ready_status;++mutations_;
    }
    return true;
  }
  // An interrupted pending operation is discarded deterministically. This
  // defines emulator reset behavior, not physical power-loss recovery.
  void interrupt() {
    if(store_)store_->interrupt();
    deadline_.reset();setup_=Setup::none;mode_=Mode::array;status_=ready_status;
    status_select_=false;buffer_.fill(0xFFU);
  }
  [[nodiscard]] std::uint32_t status() const {
    if(mode_==Mode::id)return silicon_type;
    if(mode_==Mode::array && store_) {
      const auto result=store_->read(0,4);
      if(result.ok())return (std::uint32_t(result.bytes[0])<<24U)|(std::uint32_t(result.bytes[1])<<16U)|(std::uint32_t(result.bytes[2])<<8U)|result.bytes[3];
    }
    if(mode_==Mode::buffer)return (std::uint32_t(buffer_[0])<<24U)|(std::uint32_t(buffer_[1])<<16U)|(std::uint32_t(buffer_[2])<<8U)|buffer_[3];
    return (std::uint32_t(status_)<<16U)|status_;
  }
  bool write_status(std::uint32_t value,std::uint64_t count) {
    if(!advance(count) || value!=0 || mode_!=Mode::status)return false;
    status_|=0x0CU;return true;
  }
  bool command(std::uint32_t word,std::uint64_t count) {
    if(!advance(count))return false;
    const auto command=word>>24U,argument=word&0xFFFFFFU;
    if(command!=0x3CU && command!=0x4BU && command!=0x78U && command!=0xA5U &&
       command!=0xB4U && command!=0xD2U && command!=0xE1U && command!=0xF0U)return false;
    if((command==0x4BU || command==0xA5U) ? argument>=jfg::kFlashRamPageCount : argument!=0U)return false;
    // The selected chip ignores commands while its write-state machine is busy.
    if(busy())return true;
    if(command==0xD2U) {
      if(!status_select_){status_select_=true;return true;}
      status_select_=false;mode_=Mode::status;return true;
    }
    status_select_=false;
    if(command==0xE1U){mode_=Mode::id;return true;}
    if(command==0xF0U){mode_=Mode::array;return true;}
    if(command==0xB4U){mode_=Mode::buffer;return true;}
    if(command==0x3CU){setup_=Setup::chip;return true;}
    if(command==0x4BU){setup_=Setup::sector;page_=argument;return true;}
    if(command==0x78U && setup_==Setup::none)return true;
    const auto duration=(count_hz_*(command==0xA5U?3500ULL:85000ULL)+999999ULL)/1000000ULL;
    if(count>UINT64_MAX-duration)return false;
    if(command==0xA5U) {
      if(!store_->stage_write(buffer_).ok() || !store_->begin_program(argument).ok())return false;
      buffer_.fill(0xFFU);status_=0x0DU;
    } else {
      const auto result=setup_==Setup::chip?store_->begin_erase_all():store_->begin_erase_sector(page_);
      if(!result.ok())return false;
      setup_=Setup::none;status_=0x0EU;
    }
    mode_=Mode::status;deadline_=count+duration;return true;
  }
  bool transfer(bool to_ram,std::uint32_t cart,std::uint32_t dram,std::uint32_t length,
                std::span<std::uint8_t> ram,std::uint64_t count) {
    if(!advance(count) || (ram.size()&3U) || (dram&3U) || dram>ram.size() ||
       length>ram.size()-dram || cart<0x08000000U || cart>=0x08010000U)return false;
    const auto offset=cart-0x08000000U;
    if(!to_ram) {
      if(busy() || mode_!=Mode::buffer || offset!=0U || length!=buffer_.size())return false;
      for(std::size_t i=0;i<buffer_.size();++i)buffer_[i]=ram[(dram+i)^3U];
      return true;
    }
    if(mode_==Mode::id) {
      if(offset!=0U || length!=8U)return false;
      constexpr std::array<std::uint8_t,8> id{0x11,0x11,0x80,0x01,0x00,0xC2,0x00,0x1E};
      for(std::size_t i=0;i<id.size();++i)ram[(dram+i)^3U]=id[i];
      return true;
    }
    if(mode_==Mode::status) {
      if(offset!=0U || length!=8U)return false;
      for(unsigned i=0;i<length;++i)ram[(dram+i)^3U]=(i&1U)?status_:0U;
      return true;
    }
    if(mode_!=Mode::array || (offset&63U) || length==0U || (length&127U))return false;
    const auto result=store_->read(offset*2U,length);
    if(!result.ok())return false;
    for(unsigned i=0;i<length;++i)ram[(dram+i)^3U]=result.bytes[i];
    return true;
  }
private:
  enum class Mode {array,status,id,buffer};
  enum class Setup {none,sector,chip};
  jfg::FlashRamStore* store_=nullptr;
  std::array<std::uint8_t,jfg::kFlashRamPageBytes> buffer_{};
  Mode mode_=Mode::array;Setup setup_=Setup::none;
  std::uint64_t count_hz_=0,now_=0,mutations_=0;
  std::uint32_t page_=0;std::uint8_t status_=ready_status;
  bool status_select_=false;
  std::optional<std::uint64_t> deadline_;
};
} // namespace jfg::boot
