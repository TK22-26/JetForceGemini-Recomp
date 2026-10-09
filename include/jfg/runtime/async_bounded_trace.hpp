#pragma once
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <filesystem>
#include <fstream>
#include <memory>
#include <mutex>
#include <string>
#include <string_view>
#include <thread>
#include <utility>

namespace jfg {
// Diagnostic-only output. Never hold the queue lock during filesystem work;
// slow storage may drop diagnostic rows at the queue bound, never pace gameplay.
class AsyncBoundedTrace {
public:
  class Sink {
  public:
    virtual ~Sink() = default;
    virtual bool open(std::uintmax_t &existing_bytes) = 0;
    virtual bool append(std::string_view row) = 0;
    virtual bool flush() = 0;
  };

  AsyncBoundedTrace() = default;
  AsyncBoundedTrace(const AsyncBoundedTrace &) = delete;
  AsyncBoundedTrace &operator=(const AsyncBoundedTrace &) = delete;
  ~AsyncBoundedTrace() { finish(); }

  bool start(const std::filesystem::path &path, std::size_t file_limit,
             std::size_t queue_limit = 64U * 1024U) noexcept {
    try {
      return start(std::make_unique<FileSink>(path), file_limit, queue_limit);
    } catch (...) { failed_ = true; return false; }
  }

  bool start(std::unique_ptr<Sink> sink, std::size_t file_limit,
             std::size_t queue_limit = 64U * 1024U) noexcept {
    if (worker_.joinable() || !sink || file_limit == 0 || queue_limit == 0)
      return false;
    try {
      sink_ = std::move(sink);
      file_limit_ = file_limit;
      queue_limit_ = queue_limit;
      stopping_ = false;
      accepting_ = true;
      worker_ = std::thread([this] { run(); });
      return true;
    } catch (...) {
      accepting_ = false;
      failed_ = true;
      return false;
    }
  }

  // One complete newline-terminated record, copied from main-thread state.
  // The worker never sees guest memory, State, or another thread's streams.
  bool append(std::string row) noexcept { return enqueue(std::move(row),true); }
  bool append_bytes(std::string bytes) noexcept { return enqueue(std::move(bytes),false); }
private:
  bool enqueue(std::string row,bool require_newline) noexcept {
    if (!accepting_.load(std::memory_order_relaxed)) return false;
    try {
      std::lock_guard lock(mutex_);
      if (!accepting_.load(std::memory_order_relaxed)) return false;
      if (row.empty() || (require_newline && row.back() != '\n') ||
          row.size() > queue_limit_ - queued_bytes_) {
        ++dropped_;
        return false;
      }
      const auto bytes = row.size();
      queue_.push_back(std::move(row));
      queued_bytes_ += bytes;
      changed_.notify_one();
      return true;
    } catch (...) { ++dropped_; return false; }
  }

public:
  // Called only at shutdown, not from a frame/update callback.
  void finish() noexcept {
    if (!worker_.joinable()) return;
    {
      std::lock_guard lock(mutex_);
      accepting_ = false;
      stopping_ = true;
      changed_.notify_one();
    }
    worker_.join();
    sink_.reset();
  }

  bool failed() const noexcept { return failed_.load(); }
  std::uint64_t dropped() const noexcept { return dropped_.load(); }
  std::uintmax_t written_bytes() const noexcept { return written_bytes_.load(); }

private:
  class FileSink final : public Sink {
  public:
    explicit FileSink(std::filesystem::path path) : path_(std::move(path)) {}
    bool open(std::uintmax_t &existing_bytes) override {
      std::error_code ec;
      existing_bytes = std::filesystem::file_size(path_, ec);
      if (ec) existing_bytes = 0;
      stream_.open(path_, std::ios::binary | std::ios::app);
      return static_cast<bool>(stream_);
    }
    bool append(std::string_view row) override {
      stream_.write(row.data(), static_cast<std::streamsize>(row.size()));
      return static_cast<bool>(stream_);
    }
    bool flush() override { stream_.flush(); return static_cast<bool>(stream_); }
  private:
    std::filesystem::path path_;
    std::ofstream stream_;
  };

  void run() noexcept {
    try {
      std::uintmax_t written = 0;
      if (!sink_->open(written)) { fail(); return; }
      written_bytes_ = written;
      if (written >= file_limit_) { stop_accepting(); return; }
      for (;;) {
        std::deque<std::string> batch;
        bool stopping = false;
        {
          std::unique_lock lock(mutex_);
          changed_.wait(lock, [this] { return stopping_ || !queue_.empty(); });
          // Small batches keep the live diagnostic readable without reopening
          // or flushing the file on every game update.
          changed_.wait_for(lock, std::chrono::milliseconds(100),
              [this] { return stopping_ || queued_bytes_ >= 4096; });
          batch.swap(queue_);
          queued_bytes_ = 0;
          stopping = stopping_;
        }
        bool capped = false;
        for (const auto &row : batch) {
          if (capped || row.size() > file_limit_ - written) {
            capped = true;
            ++dropped_;
            continue; // Preserve complete CSV records at the file-size bound.
          }
          if (!sink_->append(row)) { fail(); return; }
          written += row.size();
          written_bytes_ = written;
        }
        if (!batch.empty() && !sink_->flush()) { fail(); return; }
        if (capped || written >= file_limit_) { stop_accepting(); return; }
        if (stopping) return;
      }
    } catch (...) { fail(); }
  }

  void stop_accepting() noexcept {
    std::lock_guard lock(mutex_);
    accepting_ = false;
    dropped_ += queue_.size();
    queue_.clear();
    queued_bytes_ = 0;
  }
  void fail() noexcept { failed_ = true; stop_accepting(); }

  std::unique_ptr<Sink> sink_;
  std::thread worker_;
  std::mutex mutex_;
  std::condition_variable changed_;
  std::deque<std::string> queue_;
  std::size_t queued_bytes_ = 0, file_limit_ = 0, queue_limit_ = 0;
  bool stopping_ = false;
  std::atomic<bool> accepting_{false}, failed_{false};
  std::atomic<std::uint64_t> dropped_{0};
  std::atomic<std::uintmax_t> written_bytes_{0};
};
} // namespace jfg
