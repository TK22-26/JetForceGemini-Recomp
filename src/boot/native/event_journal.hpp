#pragma once
#include <array>
#include <cstddef>
#include <cstdint>

namespace jfg::boot::native::detail {
enum class NativeEventKind : std::uint32_t {
  kDispatch = 1U,
  kThreadCreated = 2U,
  kThreadStarted = 3U,
  kQueueCreated = 4U,
  kViConfigured = 5U,
  kViFrame = 6U,
  kViInterruptRaised = 7U,
  kViMessageDelivered = 8U,
  kViMessageConsumed = 9U,
  kMmioRead = 10U,
  kMmioWrite = 11U,
  kCacheMaintenance = 12U,
  kInterruptMask = 13U,
  kPiDma = 14U,
  kOverlayPublished = 15U,
  kController = 16U,
  kThreadPaused = 17U,
};

struct NativeEvent final {
  NativeEventKind kind = NativeEventKind::kDispatch;
  std::uint32_t a = 0U;
  std::uint32_t b = 0U;
  std::uint32_t c = 0U;
};

struct EventJournal final {
  static constexpr std::size_t kCapacity = 16384U;
  std::array<NativeEvent, kCapacity> entries{};
  std::array<std::uint64_t, 18U> observed_counts{};
  std::uint64_t observed_total = 0U;
  std::size_t count = 0U;
  bool overflow = false;

  void append(const NativeEventKind kind, const std::uint32_t a = 0U,
              const std::uint32_t b = 0U, const std::uint32_t c = 0U) noexcept {
    const std::size_t kind_index = static_cast<std::size_t>(kind);
    if (kind_index < observed_counts.size())
      ++observed_counts[kind_index];
    ++observed_total;
#if defined(JFG_PHASE8_LIVE_RUNTIME)
    // Live execution can run indefinitely, so its fixed-capacity journal keeps
    // structural events while the aggregate counters above retain exact totals
    // for high-frequency activity. Non-live Phase 6 evidence continues to
    // retain and hash every event exactly as before.
    switch (kind) {
    case NativeEventKind::kThreadCreated:
    case NativeEventKind::kThreadStarted:
    case NativeEventKind::kQueueCreated:
    case NativeEventKind::kViConfigured:
    case NativeEventKind::kOverlayPublished:
    case NativeEventKind::kThreadPaused:
      break;
    default:
      return;
    }
#endif
    if (count == entries.size()) {
      overflow = true;
      return;
    }
    entries[count++] = NativeEvent{kind, a, b, c};
  }
};

} // namespace jfg::boot::native::detail
