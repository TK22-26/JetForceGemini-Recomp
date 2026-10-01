#include "jfg/boot/hle.hpp"

#include <cstring>

namespace jfg::boot::hle {

std::optional<std::size_t>
GuestMemory::offset(const std::uint32_t vaddr) const noexcept {
  if (vaddr < kKseg0Base) {
    return std::nullopt;
  }
  const std::size_t off = vaddr - kKseg0Base;
  if (off + 4U > rdram_.size()) {
    return std::nullopt;
  }
  return off;
}

bool GuestMemory::read_u32(const std::uint32_t vaddr,
                           std::uint32_t &out) const noexcept {
  if ((vaddr & 3U) != 0U) {
    return false;
  }
  const std::optional<std::size_t> off = offset(vaddr);
  if (!off.has_value()) {
    return false;
  }
  // Guest words are big-endian in RDRAM.
  if (layout_ == Layout::native_word_big_endian) {
    std::memcpy(&out, rdram_.data() + *off, sizeof(out));
    return true;
  }
  out = (std::uint32_t{rdram_[*off]} << 24U) |
        (std::uint32_t{rdram_[*off + 1U]} << 16U) |
        (std::uint32_t{rdram_[*off + 2U]} << 8U) |
        std::uint32_t{rdram_[*off + 3U]};
  return true;
}

bool GuestMemory::write_u32(const std::uint32_t vaddr,
                            const std::uint32_t value) noexcept {
  if ((vaddr & 3U) != 0U) {
    return false;
  }
  const std::optional<std::size_t> off = offset(vaddr);
  if (!off.has_value()) {
    return false;
  }
  if (layout_ == Layout::native_word_big_endian) {
    std::memcpy(rdram_.data() + *off, &value, sizeof(value));
    return true;
  }
  rdram_[*off] = static_cast<std::uint8_t>(value >> 24U);
  rdram_[*off + 1U] = static_cast<std::uint8_t>(value >> 16U);
  rdram_[*off + 2U] = static_cast<std::uint8_t>(value >> 8U);
  rdram_[*off + 3U] = static_cast<std::uint8_t>(value);
  return true;
}

namespace {

struct QueueState final {
  std::uint32_t valid = 0U;
  std::uint32_t first = 0U;
  std::uint32_t count = 0U;
  std::uint32_t msg_base = 0U;
};

bool guest_span(const GuestMemory &memory, const std::uint32_t address,
                const std::uint64_t size) noexcept {
  if ((address & 3U) != 0U || address < kKseg0Base || size > memory.size()) {
    return false;
  }
  const std::uint64_t offset = address - kKseg0Base;
  return offset <= memory.size() && size <= memory.size() - offset;
}

bool valid_queue(const GuestMemory &memory,
                 const std::uint32_t queue) noexcept {
  QueueState state;
  return guest_span(memory, queue, kOsMesgQueueSize) &&
         memory.read_u32(queue + kMqOffValidCount, state.valid) &&
         memory.read_u32(queue + kMqOffFirst, state.first) &&
         memory.read_u32(queue + kMqOffMsgCount, state.count) &&
         memory.read_u32(queue + kMqOffMsg, state.msg_base) &&
         state.count != 0U && state.valid <= state.count &&
         state.first < state.count &&
         guest_span(memory, state.msg_base,
                    static_cast<std::uint64_t>(state.count) *
                        sizeof(std::uint32_t));
}

[[nodiscard]] bool load_queue(const GuestMemory &memory,
                              const std::uint32_t mq_ptr, QueueState &state) {
  return memory.read_u32(mq_ptr + kMqOffValidCount, state.valid) &&
         memory.read_u32(mq_ptr + kMqOffFirst, state.first) &&
         memory.read_u32(mq_ptr + kMqOffMsgCount, state.count) &&
         memory.read_u32(mq_ptr + kMqOffMsg, state.msg_base);
}

} // namespace

bool os_create_mesg_queue(GuestMemory &memory, const std::uint32_t mq_ptr,
                          const std::uint32_t msg_buf_ptr,
                          const std::int32_t count) {
  if (count <= 0) {
    return false;
  }
  return memory.write_u32(mq_ptr + kMqOffMtQueue, 0U) &&
         memory.write_u32(mq_ptr + kMqOffFullQueue, 0U) &&
         memory.write_u32(mq_ptr + kMqOffValidCount, 0U) &&
         memory.write_u32(mq_ptr + kMqOffFirst, 0U) &&
         memory.write_u32(mq_ptr + kMqOffMsgCount,
                          static_cast<std::uint32_t>(count)) &&
         memory.write_u32(mq_ptr + kMqOffMsg, msg_buf_ptr);
}

std::int32_t os_send_mesg(GuestMemory &memory, const std::uint32_t mq_ptr,
                          const std::uint32_t message, const bool jam) {
  QueueState state;
  if (!load_queue(memory, mq_ptr, state) || state.count == 0U) {
    return kOsFull;
  }
  if (state.valid >= state.count) {
    return kOsFull;
  }
  std::uint32_t slot;
  if (jam) {
    // Insert at the front: first moves back one (mod count).
    state.first = (state.first + state.count - 1U) % state.count;
    slot = state.first;
  } else {
    slot = (state.first + state.valid) % state.count;
  }
  if (!memory.write_u32(state.msg_base + slot * 4U, message)) {
    return kOsFull;
  }
  state.valid += 1U;
  if (!memory.write_u32(mq_ptr + kMqOffValidCount, state.valid) ||
      !memory.write_u32(mq_ptr + kMqOffFirst, state.first)) {
    return kOsFull;
  }
  return kOsSuccess;
}

std::int32_t os_recv_mesg(GuestMemory &memory, const std::uint32_t mq_ptr,
                          const std::uint32_t mesg_out_ptr) {
  QueueState state;
  if (!load_queue(memory, mq_ptr, state) || state.count == 0U) {
    return kOsEmpty;
  }
  if (state.valid == 0U) {
    return kOsEmpty;
  }
  std::uint32_t message = 0U;
  if (!memory.read_u32(state.msg_base + state.first * 4U, message)) {
    return kOsEmpty;
  }
  if (mesg_out_ptr != 0U && !memory.write_u32(mesg_out_ptr, message)) {
    return kOsEmpty;
  }
  state.first = (state.first + 1U) % state.count;
  state.valid -= 1U;
  if (!memory.write_u32(mq_ptr + kMqOffFirst, state.first) ||
      !memory.write_u32(mq_ptr + kMqOffValidCount, state.valid)) {
    return kOsEmpty;
  }
  return kOsSuccess;
}

QueueDispatchResult
dispatch_queue_call(GuestMemory &memory,
                    const QueueDispatchCall &call) noexcept {
  if (call.function == HleFunction::kOsCreateMesgQueue) {
    const std::int32_t count = static_cast<std::int32_t>(call.a2);
    if (count <= 0 || !guest_span(memory, call.a0, kOsMesgQueueSize) ||
        !guest_span(
            memory, call.a1,
            static_cast<std::uint64_t>(static_cast<std::uint32_t>(count)) *
                4U) ||
        !os_create_mesg_queue(memory, call.a0, call.a1, count)) {
      return {};
    }
    return {QueueDispatchDisposition::accepted, kOsSuccess};
  }

  if (call.function != HleFunction::kOsSendMesg &&
      call.function != HleFunction::kOsJamMesg &&
      call.function != HleFunction::kOsRecvMesg) {
    return {};
  }
  const std::int32_t block = static_cast<std::int32_t>(call.a2);
  // libultra's non-blocking receive observes validCount before it needs the
  // ring metadata. Some titles use a zero-initialized queue as an optional
  // mailbox and expect OS_MESG_NOBLOCK to report empty before initialization.
  // Preserve that read-only behavior, while retaining full structural
  // validation for any operation that can touch the message ring.
  std::uint32_t valid_count = 0U;
  if (call.function == HleFunction::kOsRecvMesg &&
      block == kOsMesgNoBlock && call.a1 == 0U &&
      guest_span(memory, call.a0, kOsMesgQueueSize) &&
      memory.read_u32(call.a0 + kMqOffValidCount, valid_count) &&
      valid_count == 0U) {
    return {QueueDispatchDisposition::accepted, kOsEmpty};
  }
  if ((block != kOsMesgNoBlock && block != kOsMesgBlock) ||
      !valid_queue(memory, call.a0) ||
      (call.function == HleFunction::kOsRecvMesg && call.a1 != 0U &&
       !guest_span(memory, call.a1, sizeof(std::uint32_t)))) {
    return {};
  }
  const bool recv = call.function == HleFunction::kOsRecvMesg;
  const std::int32_t value =
      recv ? os_recv_mesg(memory, call.a0, call.a1)
           : os_send_mesg(memory, call.a0, call.a1,
                          call.function == HleFunction::kOsJamMesg);
  if (value == kOsSuccess || block == kOsMesgNoBlock) {
    return {QueueDispatchDisposition::accepted, value};
  }
  return {QueueDispatchDisposition::block, value};
}

void HleDispatch::bind(const std::uint32_t vram, const HleFunction function) {
  table_[vram] = function;
}

std::optional<HleFunction> HleDispatch::lookup(const std::uint32_t vram) const {
  const auto found = table_.find(vram);
  if (found == table_.end()) {
    return std::nullopt;
  }
  return found->second;
}

} // namespace jfg::boot::hle
