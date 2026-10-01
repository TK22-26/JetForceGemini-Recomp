#include "recomp.h"
#include "jfg/runtime/cpu_operation_bridge.h"
#include "jfg/boot/tlb.hpp"
#include "jfg/boot/reference_cache.hpp"
#include "jfg/boot/cpu_status.hpp"

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <string>
#include <thread>
#include <vector>

#if defined(_WIN32)
#include <crtdbg.h>
#endif

namespace {

std::size_t required_sections = 1;
int generated_lookup_calls = 0;
std::atomic<int> generated_section_count_calls{0};
std::atomic<int> generated_initialize_calls{0};
std::atomic<int> routed_call_count{0};
std::atomic<bool> teardown_was_refused{false};
std::atomic<bool> routed_call_observed{false};

void generated_lookup_result(std::uint8_t*, recomp_context*) {}
void routed_lookup_result(std::uint8_t*, recomp_context*) {}

using DispatchCallback = int (*)(
    void*, int32_t, std::uint8_t*, recomp_context*);

extern "C" int jfg_minimal_runtime_bind_dispatch(
    DispatchCallback callback,
    void* opaque
);
extern "C" int jfg_minimal_runtime_unbind_dispatch(
    DispatchCallback callback,
    void* opaque
);

int routed_lookup(
    void* opaque,
    int32_t vram,
    std::uint8_t* rdram,
    recomp_context* context) {
    const auto expected_vram = static_cast<const int32_t*>(opaque);
    if (expected_vram == nullptr || vram != *expected_vram ||
        rdram == nullptr || context == nullptr) {
        return 0;
    }
    routed_call_observed = true;
    routed_call_count.fetch_add(1, std::memory_order_relaxed);
    routed_lookup_result(rdram, context);
    return 1;
}

int reentrant_unbind_lookup(
    void* opaque,
    int32_t vram,
    std::uint8_t* rdram,
    recomp_context* context) {
    const auto expected_vram = static_cast<const int32_t*>(opaque);
    if (expected_vram == nullptr || vram != *expected_vram) {
        return 0;
    }
    teardown_was_refused =
        jfg_minimal_runtime_unbind_dispatch(reentrant_unbind_lookup, opaque) == 0;
    routed_call_observed = true;
    routed_call_count.fetch_add(1, std::memory_order_relaxed);
    routed_lookup_result(rdram, context);
    return 1;
}

int initialize_for_lookup() {
    required_sections = 1;
    return jfg_minimal_runtime_initialize();
}

struct CpuOwner {
    jfg::boot::TlbRegisters32 registers = jfg::boot::TlbRegisters32::observed_mupen_boot();
    bool active_unbind_refused = false;
    unsigned cache_calls = 0;
    unsigned eret_calls = 0;
};
int cpu_lookup(void* opaque, void* context, std::uint32_t operation,
               std::uint32_t selector, std::uint64_t* value) {
    if (!opaque || !context || !value) return 0;
    auto& owner = *static_cast<CpuOwner*>(opaque);
    owner.active_unbind_refused = jfg_minimal_runtime_unbind_cpu(cpu_lookup, opaque) == 0;
    if (operation == JFG_CPU_EXCEPTION_RETURN) {
        auto& cpu = *static_cast<recomp_context*>(context);
        const auto status = static_cast<std::uint32_t>(cop0_status_read(&cpu));
        if (selector != 0 || (status & 6U) != 2U) return 0;
        cop0_status_write(&cpu, status & ~2U);
        ++owner.eret_calls;
        return 1;
    }
    if (operation == JFG_CPU_CACHE_OPERATION) {
        if (!jfg::boot::reference_coherent_cache_operation(selector, *value, 0x400000)) return 0;
        ++owner.cache_calls;
        return 1;
    }
    if (operation == JFG_CPU_READ_REGISTER) {
        const auto result = owner.registers.read(selector);
        if (!result) return 0;
        *value = static_cast<std::uint64_t>(static_cast<std::int64_t>(static_cast<std::int32_t>(*result)));
        return 1;
    }
    if (operation == JFG_CPU_WRITE_REGISTER)
        return owner.registers.write(selector, static_cast<std::uint32_t>(*value)) ? 1 : 0;
    if (operation == JFG_CPU_TLB_OPERATION) {
        if (selector == 0) return owner.registers.probe() ? 1 : 0;
        if (selector == 1) return owner.registers.read_indexed() ? 1 : 0;
        if (selector == 2) return owner.registers.write_indexed() ? 1 : 0;
    }
    return 0;
}

int run_death_case(const char* argument) {
    if (std::string(argument) == "--eret-unbound" || std::string(argument) == "--eret-rejected") {
        CpuOwner owner;
        recomp_context context{};
        std::uint8_t memory[1]{};
        if (std::string(argument) == "--eret-rejected" &&
            !jfg_minimal_runtime_bind_cpu(cpu_lookup, &owner)) return 0;
        cop0_eret(memory, &context);
        return 0;
    }
    if (std::string(argument) == "--cache-unbound" ||
        std::string(argument) == "--cache-rejected") {
        CpuOwner owner;
        recomp_context context{};
        std::uint8_t memory[1]{};
        if (std::string(argument) == "--cache-rejected") {
            if (!jfg_minimal_runtime_bind_cpu(cpu_lookup, &owner)) return 0;
            cache_op(memory, &context, 5, static_cast<gpr>(-2147483648LL)); // Tag store unsupported.
        } else {
            cache_op(memory, &context, 25, static_cast<gpr>(-2147483648LL));
        }
        return 0;
    }
    if (std::string(argument) == "--cpu-unbound") {
        recomp_context context{};
        (void)cop0_read(&context, 10);
        return 0;
    }
    if (std::string(argument) == "--cpu-rejected") {
        CpuOwner owner;
        if (!jfg_minimal_runtime_bind_cpu(cpu_lookup, &owner)) return 0;
        recomp_context context{};
        (void)cop0_read(&context, 9); // Count is not provided by this bridge.
        return 0;
    }
    if (std::string(argument) == "--concurrent-init") {
        required_sections = 1;
        generated_section_count_calls.store(0, std::memory_order_relaxed);
        generated_initialize_calls.store(0, std::memory_order_relaxed);
        routed_call_count.store(0, std::memory_order_relaxed);
        int32_t expected_vram = 7;
        if (jfg_minimal_runtime_bind_dispatch(
                routed_lookup, &expected_vram) == 0) {
            return 40;
        }
        std::atomic<int> failures{0};
        std::vector<std::thread> workers;
        constexpr int worker_count = 12;
        workers.reserve(worker_count);
        for (int index = 0; index < worker_count; ++index) {
            workers.emplace_back([&, index]() {
                if (jfg_minimal_runtime_initialize() == 0) {
                    failures.fetch_add(1, std::memory_order_relaxed);
                    return;
                }
                std::uint8_t memory[1]{};
                recomp_context context{};
                for (int iteration = 0; iteration < 1000; ++iteration) {
                    cop0_status_write(
                        &context,
                        static_cast<gpr>(index * 1000 + iteration));
                    (void)cop0_status_read(&context);
                }
                get_function(expected_vram)(memory, &context);
            });
        }
        for (std::thread& worker : workers) {
            worker.join();
        }
        if (jfg_minimal_runtime_unbind_dispatch(
                routed_lookup, &expected_vram) == 0 ||
            failures.load(std::memory_order_relaxed) != 0 ||
            generated_section_count_calls.load(std::memory_order_relaxed) != 1 ||
            generated_initialize_calls.load(std::memory_order_relaxed) != 1 ||
            routed_call_count.load(std::memory_order_relaxed) != worker_count) {
            return 41;
        }
        recomp_context context{};
        constexpr gpr final_status = static_cast<gpr>(0x13579BDFU);
        cop0_status_write(&context, final_status);
        if (cop0_status_read(&context) != final_status) {
            return 42;
        }
        return 0;
    }
    if (std::string(argument) == "--unbound") {
        if (initialize_for_lookup() == 0) {
            return 20;
        }
        std::uint8_t memory[1]{};
        recomp_context context{};
        get_function(7)(memory, &context);
        return 21;
    }
    if (std::string(argument) == "--null-result") {
        if (initialize_for_lookup() == 0) {
            return 22;
        }
        int32_t expected_vram = 7;
        if (jfg_minimal_runtime_bind_dispatch(routed_lookup, &expected_vram) == 0) {
            return 23;
        }
        // The valid callback is deliberately replaced by an always-rejecting one
        // only in this fresh subprocess.
        if (jfg_minimal_runtime_unbind_dispatch(routed_lookup, &expected_vram) == 0 ||
            jfg_minimal_runtime_bind_dispatch(
                [](void*, int32_t, std::uint8_t*, recomp_context*) -> int {
                    return 0;
                },
                nullptr
            ) == 0) {
            return 24;
        }
        std::uint8_t memory[1]{};
        recomp_context context{};
        get_function(expected_vram)(memory, &context);
        return 25;
    }
    if (std::string(argument) == "--replay") {
        if (initialize_for_lookup() == 0) {
            return 27;
        }
        int32_t expected_vram = 7;
        if (jfg_minimal_runtime_bind_dispatch(
                routed_lookup, &expected_vram) == 0) {
            return 28;
        }
        std::uint8_t memory[1]{};
        recomp_context context{};
        recomp_func_t* const trampoline = get_function(expected_vram);
        trampoline(memory, &context);
        trampoline(memory, &context);
        return 29;
    }
    if (std::string(argument) == "--nested-unresolved") {
        if (initialize_for_lookup() == 0) {
            return 30;
        }
        int32_t expected_vram = 7;
        if (jfg_minimal_runtime_bind_dispatch(
                routed_lookup, &expected_vram) == 0) {
            return 31;
        }
        (void)get_function(expected_vram);
        (void)get_function(expected_vram);
        return 32;
    }
    if (std::string(argument) == "--stale-binding") {
        if (initialize_for_lookup() == 0) {
            return 33;
        }
        int32_t expected_vram = 7;
        if (jfg_minimal_runtime_bind_dispatch(
                routed_lookup, &expected_vram) == 0) {
            return 34;
        }
        recomp_func_t* const stale = get_function(expected_vram);
        if (jfg_minimal_runtime_unbind_dispatch(
                routed_lookup, &expected_vram) == 0 ||
            jfg_minimal_runtime_bind_dispatch(
                routed_lookup, &expected_vram) == 0) {
            return 35;
        }
        std::uint8_t memory[1]{};
        recomp_context context{};
        stale(memory, &context);
        return 36;
    }
    return 26;
}

bool expect_death(const char* executable, const char* argument) {
    const std::string command = "\"" + std::string(executable) + "\" " + argument;
    return std::system(command.c_str()) != 0;
}

bool expect_success(const char* executable, const char* argument) {
    const std::string command = "\"" + std::string(executable) + "\" " + argument;
    return std::system(command.c_str()) == 0;
}

} // namespace

extern "C" std::size_t jfg_generated_section_count(void) {
    generated_section_count_calls.fetch_add(1, std::memory_order_relaxed);
    return required_sections;
}

extern "C" int jfg_generated_initialize_sections(
    int32_t* addresses,
    std::size_t capacity
) {
    generated_initialize_calls.fetch_add(1, std::memory_order_relaxed);
    if (required_sections == 0 || required_sections > capacity) {
        return 0;
    }
    addresses[required_sections - 1] = 0;
    return 1;
}

extern "C" recomp_func_t* jfg_generated_lookup_function(int32_t vram) {
    (void)vram;
    ++generated_lookup_calls;
    return generated_lookup_result;
}

int main(int argc, char** argv) {
    if (argc == 2) {
#if defined(_WIN32)
        // Intentional fail-closed child paths must never open an interactive
        // Windows Error Reporting or debug-CRT dialog under CTest.
        (void)_set_abort_behavior(0U, _WRITE_ABORT_MSG | _CALL_REPORTFAULT);
#endif
        return run_death_case(argv[1]);
    }
    if (argc != 1) {
        return 100;
    }

    const std::size_t capacity = jfg_minimal_runtime_section_capacity();
    if (capacity < 2) {
        return 1;
    }

    if (!expect_success(argv[0], "--concurrent-init")) {
        return 2;
    }

    required_sections = capacity + 1;
    if (jfg_minimal_runtime_initialize() != 0) {
        return 3;
    }

    required_sections = 0;
    if (jfg_minimal_runtime_initialize() != 0) {
        return 4;
    }

    generated_section_count_calls.store(0, std::memory_order_relaxed);
    generated_initialize_calls.store(0, std::memory_order_relaxed);
    required_sections = capacity;
    if (jfg_minimal_runtime_initialize() == 0) {
        return 5;
    }
    required_sections = capacity + 1;
    if (jfg_minimal_runtime_initialize() == 0 ||
        generated_section_count_calls.load(std::memory_order_relaxed) != 1 ||
        generated_initialize_calls.load(std::memory_order_relaxed) != 1) {
        return 11;
    }

    int32_t expected_vram = 7;
    if (jfg_minimal_runtime_bind_dispatch(nullptr, nullptr) != 0 ||
        jfg_minimal_runtime_bind_dispatch(routed_lookup, &expected_vram) == 0 ||
        jfg_minimal_runtime_bind_dispatch(routed_lookup, &expected_vram) != 0) {
        return 6;
    }
    routed_call_observed = false;
    std::uint8_t dispatch_memory[1]{};
    recomp_context dispatch_context{};
    get_function(expected_vram)(dispatch_memory, &dispatch_context);
    if (!routed_call_observed || generated_lookup_calls != 0) {
        return 7;
    }
    if (jfg_minimal_runtime_unbind_dispatch(routed_lookup, nullptr) != 0 ||
        jfg_minimal_runtime_unbind_dispatch(routed_lookup, &expected_vram) == 0) {
        return 8;
    }

    teardown_was_refused = false;
    routed_call_observed = false;
    if (jfg_minimal_runtime_bind_dispatch(reentrant_unbind_lookup, &expected_vram) == 0) {
        return 9;
    }
    get_function(expected_vram)(dispatch_memory, &dispatch_context);
    if (!routed_call_observed || !teardown_was_refused ||
        jfg_minimal_runtime_unbind_dispatch(reentrant_unbind_lookup, &expected_vram) == 0) {
        return 9;
    }
    if (!expect_death(argv[0], "--unbound") ||
        !expect_death(argv[0], "--cache-unbound") ||
        !expect_death(argv[0], "--cache-rejected") ||
        !expect_death(argv[0], "--cpu-unbound") ||
        !expect_death(argv[0], "--cpu-rejected") ||
        !expect_death(argv[0], "--eret-unbound") ||
        !expect_death(argv[0], "--eret-rejected") ||
        !expect_death(argv[0], "--null-result") ||
        !expect_death(argv[0], "--replay") ||
        !expect_death(argv[0], "--nested-unresolved") ||
        !expect_death(argv[0], "--stale-binding")) {
        return 10;
    }
    CpuOwner cpu_owner;
    using jfg::boot::status_after_exception_return;
    if (status_after_exception_return(0x0400ff03) != 0x0400ff01 ||
        status_after_exception_return(0x0000ff03) != 0x0000ff01 ||
        status_after_exception_return(0x0400ff07) != 0x0400ff03 ||
        status_after_exception_return(0x0400ff01) != 0x0400ff01) return 45;
    if (jfg_minimal_runtime_bind_cpu(nullptr, &cpu_owner) != 0 ||
        jfg_minimal_runtime_bind_cpu(cpu_lookup, &cpu_owner) != 1 ||
        jfg_minimal_runtime_bind_cpu(cpu_lookup, &cpu_owner) != 0) return 40;
    cop0_write(&dispatch_context, 0, 5);
    cop0_status_write(&dispatch_context, 0x0400ff03);
    cop0_eret(dispatch_memory, &dispatch_context);
    if (cop0_status_read(&dispatch_context) != 0x0400ff01 || cpu_owner.eret_calls != 1) return 46;
    cop0_write(&dispatch_context, 10, 0x00200007);
    cop0_write(&dispatch_context, 2, 0x207);
    cop0_write(&dispatch_context, 3, 0x247);
    cop0_write(&dispatch_context, 5, 0);
    cop0_tlb_op(&dispatch_context, 2);
    cop0_write(&dispatch_context, 10, 0x00200008);
    cop0_tlb_op(&dispatch_context, 0);
    if (cop0_read(&dispatch_context, 0) != 5) return 41;
    cop0_tlb_op(&dispatch_context, 1);
    for (unsigned operation : {0U, 1U, 16U, 17U, 21U, 25U})
        cache_op(dispatch_memory, &dispatch_context, operation, static_cast<gpr>(-2147483648LL));
    if (cpu_owner.cache_calls != 6 || dispatch_memory[0] != 0) return 43;
    using jfg::boot::reference_coherent_cache_operation;
    if (reference_coherent_cache_operation(25, 0x80000000, 0x400000) ||
        reference_coherent_cache_operation(25, 0xffffffffa0000000ULL, 0x400000) ||
        reference_coherent_cache_operation(25, 0xffffffff80400000ULL, 0x400000) ||
        reference_coherent_cache_operation(5, 0xffffffff80000000ULL, 0x400000) ||
        !reference_coherent_cache_operation(25, 0xffffffff803fffffULL, 0x400000)) return 44;
    if (cop0_read(&dispatch_context, 2) != 0x207 || !cpu_owner.active_unbind_refused ||
        jfg_minimal_runtime_unbind_cpu(cpu_lookup, nullptr) != 0 ||
        jfg_minimal_runtime_unbind_cpu(cpu_lookup, &cpu_owner) != 1 ||
        jfg_minimal_runtime_unbind_cpu(cpu_lookup, &cpu_owner) != 0) return 42;
    return 0;
}
