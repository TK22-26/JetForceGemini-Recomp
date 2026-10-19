#pragma once

// Per-stack state for the optional cooperative executor. Ordinary OS-thread
// callers retain real TLS. Contexts and their values live until their stacks
// have unwound; no value is shared across guest participants.
#include <cstdint>
#include <memory>
#include <unordered_map>

namespace jfg::runtime {
class ExecutionLocalContext final {
    struct Value { virtual ~Value() = default; };
    template<class T> struct Box final : Value { T value{}; };
    std::unordered_map<const void*, std::unique_ptr<Value>> values_;
public:
    template<class T, class Tag> T& get() {
        // Writable identity cannot be merged with another type/tag constant.
        static char key = 0;
        auto it = values_.find(&key);
        if (it == values_.end()) {
            it = values_.emplace(&key, std::make_unique<Box<T>>()).first;
        }
        return static_cast<Box<T>*>(it->second.get())->value;
    }
};
inline thread_local ExecutionLocalContext* execution_local_context = nullptr;
inline thread_local std::uint64_t execution_local_epoch = 1;

// Only the stack transport changes this, immediately before switching stacks.
// Epoch invalidation also prevents stale cache hits after context destruction
// and address reuse by a later executor on the same host thread.
inline void select_execution_local_context(ExecutionLocalContext* context) noexcept {
    execution_local_context = context;
    ++execution_local_epoch;
}
template<class T, class Tag> T& execution_local() {
    if (!execution_local_context) { static thread_local T ordinary{}; return ordinary; }
    static thread_local std::uint64_t epoch = 0;
    static thread_local T* cached = nullptr;
    if (epoch != execution_local_epoch) {
        cached = &execution_local_context->get<T,Tag>();
        epoch = execution_local_epoch;
    }
    return *cached;
}
} // namespace jfg::runtime
