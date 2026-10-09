#pragma once
#include "jfg/runtime/async_diagnostic_file.hpp"
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <initializer_list>
#include <span>

namespace jfg::boot {
// Explicit, private diagnostics. Disabled by default; never part of support ZIPs.
class GameplayTrace {
public:
  bool open(const std::filesystem::path &path,
            std::uint64_t limit = 256ULL * 1024ULL * 1024ULL) {
    if (limit < 128U || stream_.is_open()) return false;
    stream_.open(path, std::ios::binary | std::ios::trunc);
    if (!stream_) return false;
    limit_ = limit;
    start_ = flushed_ = std::chrono::steady_clock::now();
    stream_ << "jfg-gameplay-trace-v1\ttime_us\tevent\tvalues_hex\n";
    bytes_ = 50U; // Conservative header charge.
    return true;
  }
  explicit operator bool() const { return stream_.is_open() && !stopped_; }
  // finish() drains at shutdown; flush() only submits buffered diagnostics.
  void finish() noexcept { stream_.finish(); }
  void flush() { if (stream_.is_open()) stream_.flush(); }
  void event(const char *kind, std::span<const std::uint64_t> values) {
    if (!*this) return;
    const auto now = std::chrono::steady_clock::now();
    const auto us = std::chrono::duration_cast<std::chrono::microseconds>(now - start_).count();
    std::array<char, 2048> row{};
    int used = std::snprintf(row.data(), row.size(), "%lld\t%.32s",
                            static_cast<long long>(us), kind);
    if (used < 0) return;
    for (const auto value : values) {
      if (static_cast<std::size_t>(used) + 19U >= row.size()) { stop("record-limit"); return; }
      const int n = std::snprintf(row.data() + used, row.size() - static_cast<std::size_t>(used),
                                  "\t%llx", static_cast<unsigned long long>(value));
      if (n < 0) { stop("format-error"); return; }
      used += n;
    }
    row[static_cast<std::size_t>(used++)] = '\n';
    if (bytes_ + static_cast<std::uint64_t>(used) + 64U > limit_) { stop("byte-limit"); return; }
    stream_.write(row.data(), used);
    bytes_ += static_cast<std::uint64_t>(used);
    if (!stream_) { stopped_ = true; return; }
    if (now - flushed_ >= std::chrono::seconds(1)) { flush(); flushed_ = now; }
  }
  void event(const char *kind, std::initializer_list<std::uint64_t> values) {
    event(kind, std::span<const std::uint64_t>(values.begin(), values.size()));
  }
private:
  void stop(const char *reason) {
    stream_ << "limit\t" << reason << '\n';
    flush(); stopped_ = true;
  }
  jfg::AsyncDiagnosticFile stream_;
  std::chrono::steady_clock::time_point start_{}, flushed_{};
  std::uint64_t bytes_ = 0, limit_ = 0;
  bool stopped_ = false;
};
} // namespace jfg::boot
