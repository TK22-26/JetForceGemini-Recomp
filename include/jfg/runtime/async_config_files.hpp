#pragma once
#if defined(_WIN32)
#include <windows.h>
#else
#include <fstream>
#endif
#include <chrono>
#include <condition_variable>
#include <filesystem>
#include <functional>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace jfg {
struct ConfigFileRequest {
    std::filesystem::path path;
    std::size_t max_bytes;
};
struct ConfigFileValue {
    enum class Status { unavailable, missing, ready };
    Status status = Status::unavailable;
    std::string text;
};
// Files are read before gameplay starts, then by one background worker.
// The game thread only obtains an immutable snapshot; it never waits for I/O.
class AsyncConfigFiles {
public:
    using Values = std::vector<ConfigFileValue>;
    using Loader = std::function<ConfigFileValue(const ConfigFileRequest&)>;
    ~AsyncConfigFiles() { finish(); }
    void start(std::vector<ConfigFileRequest> requests, Loader loader = read) {
        if (worker_.joinable()) throw std::logic_error("config reader already started");
        requests_ = std::move(requests);
        loader_ = std::move(loader);
        stop_ = false;
        refresh(); // Initial settings are required before the first input sample.
        worker_ = std::thread([this] {
            std::unique_lock lock(mutex_);
            while (!stop_) {
                if (changed_.wait_for(lock, std::chrono::milliseconds(250), [this] { return stop_; })) break;
                lock.unlock(); refresh(); lock.lock();
            }
        });
    }
    std::shared_ptr<const Values> latest() const {
        std::lock_guard lock(mutex_);
        return latest_;
    }
    void finish() noexcept {
        if (!worker_.joinable()) return;
        { std::lock_guard lock(mutex_); stop_ = true; }
        changed_.notify_one();
        worker_.join();
    }
    static ConfigFileValue read(const ConfigFileRequest& request) noexcept {
        try {
            if (request.max_bytes > 32768U) return {};
            std::string text(request.max_bytes + 1U, '\0');
            std::size_t count = 0;
#if defined(_WIN32)
            const HANDLE file = CreateFileW(request.path.c_str(), GENERIC_READ,
                FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
                OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
            if (file == INVALID_HANDLE_VALUE) {
                const auto error = GetLastError();
                return {error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND
                    ? ConfigFileValue::Status::missing : ConfigFileValue::Status::unavailable, {}};
            }
            DWORD bytes = 0;
            const bool okay = ReadFile(file, text.data(), static_cast<DWORD>(text.size()), &bytes, nullptr) != 0;
            CloseHandle(file);
            if (!okay) return {};
            count = bytes;
#else
            std::ifstream file(request.path, std::ios::binary);
            if (!file) {
                std::error_code error;
                const bool exists = std::filesystem::exists(request.path, error);
                return {!error && !exists ? ConfigFileValue::Status::missing
                    : ConfigFileValue::Status::unavailable, {}};
            }
            file.read(text.data(), static_cast<std::streamsize>(text.size()));
            if (file.bad()) return {};
            count = static_cast<std::size_t>(file.gcount());
#endif
            if (!count || count > request.max_bytes) return {};
            text.resize(count);
            return {ConfigFileValue::Status::ready, std::move(text)};
        } catch (...) { return {}; }
    }
private:
    void refresh() noexcept {
        try {
            auto values = std::make_shared<Values>();
            values->reserve(requests_.size());
            for (const auto& request : requests_) values->push_back(loader_(request));
            std::lock_guard lock(mutex_);
            latest_ = std::move(values);
        } catch (...) {} // A failed refresh retains the previous complete snapshot.
    }
    std::vector<ConfigFileRequest> requests_;
    Loader loader_;
    mutable std::mutex mutex_;
    std::condition_variable changed_;
    std::shared_ptr<const Values> latest_;
    bool stop_ = false;
    std::thread worker_;
};
}
