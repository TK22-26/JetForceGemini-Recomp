#pragma once
#include <array>
#include <atomic>
#include <condition_variable>
#include <deque>
#include <filesystem>
#include <fstream>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <thread>
#include <vector>
#if defined(_WIN32)
#include <windows.h>
#endif
namespace jfg {
class AsyncSnapshots {
public:
  struct File { std::filesystem::path path; std::shared_ptr<const std::string> text; };
  using Batch = std::vector<File>;
  class Sink {
  public:
    virtual ~Sink() = default;
    virtual bool replace(const File&) = 0;
  };
  AsyncSnapshots() : AsyncSnapshots(nullptr) {}
  explicit AsyncSnapshots(std::unique_ptr<Sink> sink, std::size_t limit = 16U*1024U*1024U)
      : sink_(sink ? std::move(sink) : std::make_unique<FileSink>()), limit_(limit) {
    worker_ = std::thread([this] { run(); });
  }
  ~AsyncSnapshots() { finish(); }
  AsyncSnapshots(const AsyncSnapshots&) = delete;
  AsyncSnapshots& operator=(const AsyncSnapshots&) = delete;
  // Each channel is a complete publication. Coalescing cannot discard the
  // mesh prerequisite while retaining a newer live-state publication.
  bool submit(unsigned channel, Batch files) noexcept {
    try {
      if (channel >= pending_.size() || files.empty() || files.size() > 4U) return false;
      std::size_t size = 0;
      for (const auto& file : files) {
        if (file.path.empty() || !file.text || file.text->size() > limit_ - size) return false;
        size += file.text->size();
      }
      std::lock_guard lock(mutex_);
      if (stopping_) return false;
      if (!pending_[channel]) order_.push_back(channel);
      else ++coalesced_;
      pending_[channel] = std::move(files);
      changed_.notify_one();
      return true;
    } catch (...) { ++failed_; return false; }
  }
  void finish() noexcept {
    if (!worker_.joinable()) return;
    { std::lock_guard lock(mutex_); stopping_ = true; changed_.notify_one(); }
    worker_.join();
  }
  std::uint64_t failed() const noexcept { return failed_; }
  std::uint64_t coalesced() const noexcept { return coalesced_; }
private:
  class FileSink final : public Sink {
    bool replace(const File& file) override {
      auto temp = file.path;
#if defined(_WIN32)
      temp += L".snapshot-" + std::to_wstring(GetCurrentProcessId()) + L".tmp";
#else
      temp += ".snapshot.tmp";
#endif
      { std::ofstream out(temp, std::ios::binary | std::ios::trunc);
        out.write(file.text->data(), static_cast<std::streamsize>(file.text->size()));
        out.flush(); if (!out) return false; }
#if defined(_WIN32)
      return MoveFileExW(temp.c_str(),file.path.c_str(),
          MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) != 0;
#else
      std::error_code error; std::filesystem::rename(temp,file.path,error); return !error;
#endif
    }
  };
  void run() noexcept {
    for (;;) {
      Batch batch; unsigned channel = 0;
      {
        std::unique_lock lock(mutex_);
        changed_.wait(lock,[this]{ return stopping_ || !order_.empty(); });
        if (order_.empty()) return;
        channel = order_.front(); order_.pop_front();
        batch = std::move(*pending_[channel]); pending_[channel].reset();
      }
      bool success = true;
      try {
        for (const auto& file : batch) {
          bool unchanged = false;
          for (const auto& old : completed_[channel])
            if (old.path == file.path && old.text == file.text) unchanged = true;
          if (!unchanged && !sink_->replace(file)) { success = false; break; }
        }
      } catch (...) { success = false; }
      if (success) completed_[channel] = std::move(batch);
      else ++failed_;
    }
  }
  std::unique_ptr<Sink> sink_;
  std::size_t limit_;
  std::mutex mutex_;
  std::condition_variable changed_;
  std::array<std::optional<Batch>,2> pending_;
  std::array<Batch,2> completed_;
  std::deque<unsigned> order_;
  bool stopping_ = false;
  std::atomic<std::uint64_t> failed_{0}, coalesced_{0};
  std::thread worker_;
};
} // namespace jfg
