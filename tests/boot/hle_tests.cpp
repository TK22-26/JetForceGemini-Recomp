// Phase 6 libultra HLE (data-structure layer) tests. ROM-free: builds guest
// OSMesgQueue structures in a local RDRAM buffer and exercises the message-
// queue ABI the boot's threads block and wake on.

#include "jfg/boot/hle.hpp"

#include <array>
#include <cstdint>
#include <iostream>
#include <string_view>
#include <vector>

namespace {

using namespace jfg::boot::hle;

int failures = 0;

void check(const bool condition, const std::string_view message) {
  if (!condition) {
    ++failures;
    std::cerr << "FAIL: " << message << '\n';
  }
}

// A small guest layout: queue struct at 0x80001000, 4-slot message buffer at
// 0x80001100.
constexpr std::uint32_t kQueue = 0x80001000U;
constexpr std::uint32_t kMsgBuf = 0x80001100U;
constexpr std::int32_t kDepth = 4;

void test_create_and_fifo_order() {
  std::vector<std::uint8_t> rdram(0x10000U, 0U);
  GuestMemory memory(std::span<std::uint8_t>(rdram.data(), rdram.size()));

  check(os_create_mesg_queue(memory, kQueue, kMsgBuf, kDepth), "queue creates");
  std::uint32_t validate = 0xFFFFFFFFU;
  check(memory.read_u32(kQueue + kMqOffMsgCount, validate) && validate == 4U,
        "msgCount initialized");

  check(os_send_mesg(memory, kQueue, 0x1111U, false) == kOsSuccess, "send 1");
  check(os_send_mesg(memory, kQueue, 0x2222U, false) == kOsSuccess, "send 2");
  check(os_send_mesg(memory, kQueue, 0x3333U, false) == kOsSuccess, "send 3");

  std::uint32_t out_slot = 0x80002000U;
  std::uint32_t got = 0U;
  check(os_recv_mesg(memory, kQueue, out_slot) == kOsSuccess, "recv 1");
  check(memory.read_u32(out_slot, got) && got == 0x1111U, "FIFO order 1");
  check(os_recv_mesg(memory, kQueue, out_slot) == kOsSuccess, "recv 2");
  check(memory.read_u32(out_slot, got) && got == 0x2222U, "FIFO order 2");
}

void test_full_and_empty_fail_closed() {
  std::vector<std::uint8_t> rdram(0x10000U, 0U);
  GuestMemory memory(std::span<std::uint8_t>(rdram.data(), rdram.size()));
  check(os_create_mesg_queue(memory, kQueue, kMsgBuf, kDepth), "queue creates");
  for (std::uint32_t i = 0; i < 4U; ++i) {
    check(os_send_mesg(memory, kQueue, 0xA0U + i, false) == kOsSuccess,
          "fill slot");
  }
  check(os_send_mesg(memory, kQueue, 0xBEEFU, false) == kOsFull,
        "send on full queue fails");
  // Drain and confirm empty fails.
  std::uint32_t out_slot = 0x80002000U;
  for (int i = 0; i < 4; ++i) {
    check(os_recv_mesg(memory, kQueue, out_slot) == kOsSuccess, "drain");
  }
  check(os_recv_mesg(memory, kQueue, out_slot) == kOsEmpty,
        "recv on empty queue fails");
}

void test_jam_inserts_at_front() {
  std::vector<std::uint8_t> rdram(0x10000U, 0U);
  GuestMemory memory(std::span<std::uint8_t>(rdram.data(), rdram.size()));
  check(os_create_mesg_queue(memory, kQueue, kMsgBuf, kDepth), "queue creates");
  check(os_send_mesg(memory, kQueue, 0x1111U, false) == kOsSuccess, "send");
  check(os_send_mesg(memory, kQueue, 0x9999U, true) == kOsSuccess, "jam");
  std::uint32_t out_slot = 0x80002000U;
  std::uint32_t got = 0U;
  check(os_recv_mesg(memory, kQueue, out_slot) == kOsSuccess, "recv");
  check(memory.read_u32(out_slot, got) && got == 0x9999U,
        "jammed message is received first");
}

void test_wrap_around_ring() {
  std::vector<std::uint8_t> rdram(0x10000U, 0U);
  GuestMemory memory(std::span<std::uint8_t>(rdram.data(), rdram.size()));
  check(os_create_mesg_queue(memory, kQueue, kMsgBuf, kDepth), "queue creates");
  std::uint32_t out_slot = 0x80002000U;
  std::uint32_t got = 0U;
  // Cycle enough to wrap the ring several times.
  for (std::uint32_t i = 0; i < 20U; ++i) {
    check(os_send_mesg(memory, kQueue, 0x100U + i, false) == kOsSuccess,
          "send in cycle");
    check(os_recv_mesg(memory, kQueue, out_slot) == kOsSuccess,
          "recv in cycle");
    check(memory.read_u32(out_slot, got) && got == 0x100U + i,
          "wrapped ring preserves order");
  }
}

void test_misaligned_and_oob_rejected() {
  std::vector<std::uint8_t> rdram(0x2000U, 0U);
  GuestMemory memory(std::span<std::uint8_t>(rdram.data(), rdram.size()));
  std::uint32_t dummy = 0U;
  check(!memory.read_u32(0x80000001U, dummy), "misaligned read rejected");
  check(!memory.write_u32(0x80000002U, 1U), "misaligned write rejected");
  check(!memory.read_u32(0x90000000U, dummy), "out-of-range read rejected");
  check(!memory.read_u32(0x00000000U, dummy), "below-kseg0 read rejected");
}

void test_dispatch_registry() {
  HleDispatch dispatch;
  // vram→handler pairs as supplied from the private identification.
  dispatch.bind(0x80096BB0U, HleFunction::kOsCreateMesgQueue);
  dispatch.bind(0x80096910U, HleFunction::kOsRecvMesg);
  dispatch.bind(0x80096F20U, HleFunction::kOsSendMesg);
  check(dispatch.size() == 3U, "three handlers bound");
  check(dispatch.lookup(0x80096910U) == HleFunction::kOsRecvMesg,
        "osRecvMesg vram routes to recv handler");
  check(dispatch.lookup(0x80096BB0U) == HleFunction::kOsCreateMesgQueue,
        "osCreateMesgQueue vram routes to create handler");
  check(!dispatch.lookup(0x80000450U).has_value(),
        "unbound vram (audio fn) is not intercepted");
}

void test_native_word_layout() {
  std::vector<std::uint8_t> rdram(0x10000U, 0U);
  GuestMemory memory({rdram.data(), rdram.size()},
                     GuestMemory::Layout::native_word_big_endian);
  check(memory.write_u32(kQueue, 0x11223344U), "native layout write");
  check(rdram[0x1000U] == 0x44U && rdram[0x1003U] == 0x11U,
        "native layout storage");
  std::uint32_t word = 0U;
  check(memory.read_u32(kQueue, word) && word == 0x11223344U,
        "native layout read");
}

void test_abi_queue_dispatch() {
  std::vector<std::uint8_t> rdram(0x10000U, 0U);
  GuestMemory memory({rdram.data(), rdram.size()});
  constexpr std::uint32_t output = 0x80002000U;
  const auto optional_empty = dispatch_queue_call(
      memory, {HleFunction::kOsRecvMesg, kQueue, 0U, kOsMesgNoBlock});
  check(optional_empty.disposition == QueueDispatchDisposition::accepted &&
            optional_empty.return_value == kOsEmpty,
        "ABI no-block receive observes an optional zeroed mailbox as empty");
  check(dispatch_queue_call(
            memory, {HleFunction::kOsCreateMesgQueue, kQueue, kMsgBuf, 1U})
                .disposition == QueueDispatchDisposition::accepted,
        "ABI create accepted");
  check(dispatch_queue_call(
            memory, {HleFunction::kOsCreateMesgQueue, kQueue, kMsgBuf, 0U})
                .disposition == QueueDispatchDisposition::reject,
        "ABI create rejects zero capacity");
  check(dispatch_queue_call(memory,
                            {HleFunction::kOsSendMesg, kQueue, 0x89ABCDEFU, 0U})
                .return_value == kOsSuccess,
        "ABI send accepted");
  check(dispatch_queue_call(memory, {HleFunction::kOsJamMesg, kQueue, 0U, 0U})
                .return_value == kOsFull,
        "ABI no-block full returns signed error");
  const auto recv = dispatch_queue_call(
      memory, {HleFunction::kOsRecvMesg, kQueue, output, 0U});
  std::uint32_t value = 0U;
  check(recv.disposition == QueueDispatchDisposition::accepted &&
            recv.return_value == kOsSuccess && memory.read_u32(output, value) &&
            value == 0x89ABCDEFU,
        "ABI recv writes message");
  check(dispatch_queue_call(memory, {HleFunction::kOsRecvMesg, kQueue, 0U, 0U})
                .return_value == kOsEmpty,
        "ABI no-block empty returns signed error");
  check(dispatch_queue_call(memory,
                            {HleFunction::kOsRecvMesg, kQueue, output + 2U, 0U})
                .disposition == QueueDispatchDisposition::reject,
        "ABI recv rejects unaligned output");
  check(dispatch_queue_call(memory,
                            {HleFunction::kOsRecvMesg, kQueue, 0x80010000U, 0U})
                .disposition == QueueDispatchDisposition::reject,
        "ABI recv rejects out-of-range output");
  check(dispatch_queue_call(memory, {HleFunction::kOsRecvMesg, kQueue, 0U, 1U})
                .disposition == QueueDispatchDisposition::block,
        "ABI blocking empty traps");
}

} // namespace

int main() {
  test_create_and_fifo_order();
  test_full_and_empty_fail_closed();
  test_jam_inserts_at_front();
  test_wrap_around_ring();
  test_misaligned_and_oob_rejected();
  test_dispatch_registry();
  test_native_word_layout();
  test_abi_queue_dispatch();
  if (failures != 0) {
    std::cerr << failures << " failure(s)\n";
    return 1;
  }
  std::cout << "all hle tests passed\n";
  return 0;
}
