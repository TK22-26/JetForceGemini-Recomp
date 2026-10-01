#pragma once

// Independently authored libultra HLE — data-structure layer (Phase 6).
//
// AUTHORSHIP: original work implemented to the public N64 SDK (libultra)
// contract. The struct layouts below are the documented OSMesgQueue ABI; the
// implementations are ours. No decomp source was copied — the decomp was
// consulted facts-only to learn which ROM addresses are libultra (see
// THIRD_PARTY_NOTICES.md and src/boot/PROVENANCE.md).
//
// This layer operates on the guest's own structures in RDRAM (as the
// recompiled code passes them), bridging libultra calls into deterministic
// host behavior. It is the ABI the dispatch interception routes the
// identified libultra vrams to. The stackful thread-execution parts
// (osStartThread actually running recompiled bodies) are a later increment;
// this brick covers the message-queue/event data-structure operations the
// boot's threads block and wake on.

#include <cstdint>
#include <optional>
#include <span>
#include <unordered_map>

namespace jfg::boot::hle {

inline constexpr std::uint32_t kKseg0Base = 0x80000000U;

// Documented OSMesgQueue layout (big-endian guest words). Sizes/offsets are
// the public libultra ABI, identical across SDK builds.
inline constexpr std::uint32_t kMqOffMtQueue = 0x00U;   // OSThread* (send-wait)
inline constexpr std::uint32_t kMqOffFullQueue = 0x04U; // OSThread* (recv-wait)
inline constexpr std::uint32_t kMqOffValidCount = 0x08U;
inline constexpr std::uint32_t kMqOffFirst = 0x0CU;
inline constexpr std::uint32_t kMqOffMsgCount = 0x10U;
inline constexpr std::uint32_t kMqOffMsg = 0x14U; // OSMesg* (buffer base)
inline constexpr std::uint32_t kOsMesgQueueSize = 0x18U;

// osSendMesg / osRecvMesg block flag.
inline constexpr std::int32_t kOsMesgNoBlock = 0;
inline constexpr std::int32_t kOsMesgBlock = 1;

// A bounds-checked view over guest RDRAM in KSEG0 addressing.
class GuestMemory final {
public:
  enum class Layout : std::uint8_t {
    byte_linear_big_endian,
    native_word_big_endian
  };
  explicit GuestMemory(std::span<std::uint8_t> rdram) noexcept
      : rdram_(rdram) {}
  GuestMemory(std::span<std::uint8_t> rdram, Layout layout) noexcept
      : rdram_(rdram), layout_(layout) {}

  [[nodiscard]] bool read_u32(std::uint32_t vaddr,
                              std::uint32_t &out) const noexcept;
  [[nodiscard]] bool write_u32(std::uint32_t vaddr,
                               std::uint32_t value) noexcept;
  [[nodiscard]] std::size_t size() const noexcept { return rdram_.size(); }

private:
  [[nodiscard]] std::optional<std::size_t>
  offset(std::uint32_t vaddr) const noexcept;
  std::span<std::uint8_t> rdram_;
  Layout layout_ = Layout::byte_linear_big_endian;
};

// Return codes match libultra: 0 == success, -1 == queue full/empty.
inline constexpr std::int32_t kOsSuccess = 0;
inline constexpr std::int32_t kOsFull = -1;
inline constexpr std::int32_t kOsEmpty = -1;

// osCreateMesgQueue(mq, msgBuf, count): initialize the guest queue struct.
[[nodiscard]] bool os_create_mesg_queue(GuestMemory &memory,
                                        std::uint32_t mq_ptr,
                                        std::uint32_t msg_buf_ptr,
                                        std::int32_t count);

// osSendMesg / osJamMesg (jam inserts at the front). Non-blocking buffer
// operation on the guest ring; the block/wake of a waiting thread is handled
// by the scheduler layer (later brick). Returns kOsSuccess or kOsFull.
[[nodiscard]] std::int32_t os_send_mesg(GuestMemory &memory,
                                        std::uint32_t mq_ptr,
                                        std::uint32_t message, bool jam);

// osRecvMesg: pop the front message into *mesg_out (if non-zero). Returns
// kOsSuccess or kOsEmpty.
[[nodiscard]] std::int32_t os_recv_mesg(GuestMemory &memory,
                                        std::uint32_t mq_ptr,
                                        std::uint32_t mesg_out_ptr);

// The libultra functions this data-structure layer implements. Thread and
// hardware functions are separate (later) bricks.
enum class HleFunction : std::uint32_t {
  kOsCreateMesgQueue = 1U,
  kOsSendMesg = 2U,
  kOsJamMesg = 3U,
  kOsRecvMesg = 4U,
};

enum class QueueDispatchDisposition : std::uint8_t {
  accepted,
  block,
  reject,
};

struct QueueDispatchCall {
  HleFunction function{};
  std::uint32_t a0 = 0U;
  std::uint32_t a1 = 0U;
  std::uint32_t a2 = 0U;
};

struct QueueDispatchResult {
  QueueDispatchDisposition disposition = QueueDispatchDisposition::reject;
  std::int32_t return_value = kOsEmpty;
};

// Validates the generated-ABI-neutral queue call before changing guest state.
// A blocking full/empty operation is reported to the caller rather than being
// silently accepted.
[[nodiscard]] QueueDispatchResult
dispatch_queue_call(GuestMemory &memory,
                    const QueueDispatchCall &call) noexcept;

// Maps identified libultra ROM addresses to HLE handlers. The vram→function
// pairs come from the private identification (scripts/identify_libultra.py);
// they are supplied at construction, never hardcoded from ROM-derived data.
class HleDispatch final {
public:
  void bind(std::uint32_t vram, HleFunction function);
  [[nodiscard]] std::optional<HleFunction> lookup(std::uint32_t vram) const;
  [[nodiscard]] std::size_t size() const noexcept { return table_.size(); }

private:
  std::unordered_map<std::uint32_t, HleFunction> table_;
};

} // namespace jfg::boot::hle
