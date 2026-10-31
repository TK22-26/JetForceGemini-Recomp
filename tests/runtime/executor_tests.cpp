#include "jfg/runtime/execution_local.hpp"
#include <cfenv>
#include <stdexcept>
// Phase 6 stackful executor tests. Verifies the baton discipline (one
// participant runs at a time), deterministic interleaving, run/yield/resume,
// and clean shutdown of a never-finishing (parked) participant.

#include "jfg/boot/executor.hpp"

#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace {

using namespace jfg::boot;

int failures = 0;

void check(const bool condition, const std::string_view message) {
    if (!condition) {
        ++failures;
        std::cerr << "FAIL: " << message << '\n';
    }
}

// Runs a two-participant cooperative scenario and returns the interleaving log.
// Because only the baton holder runs, the log is fully determined by the
// scheduler's resume order.
std::vector<std::string> run_scenario(unsigned spin = 0U) {
    std::vector<std::string> log;
    BatonExecutor executor;

    executor.set_spin_budget(spin);

    // Participant A: log a0, yield, log a1, yield, finish.
    const int a = executor.spawn([&log](BatonExecutor& ex, int) {
        log.push_back("a0");
        ex.yield_to_scheduler();
        log.push_back("a1");
        ex.yield_to_scheduler();
        log.push_back("a2");
    });
    // Participant B: log b0, yield, log b1, finish.
    const int b = executor.spawn([&log](BatonExecutor& ex, int) {
        log.push_back("b0");
        ex.yield_to_scheduler();
        log.push_back("b1");
    });

    // Deterministic scheduler order: A, B, A, B, A.
    check(!executor.resume(a), "A not finished after first slice");
    check(!executor.resume(b), "B not finished after first slice");
    check(!executor.resume(a), "A not finished after second slice");
    check(executor.resume(b), "B finished after second slice");
    check(executor.resume(a), "A finished after third slice");
    return log;
}

void test_deterministic_interleaving() {
    const std::vector<std::string> first = run_scenario();
    const std::vector<std::string> second = run_scenario();
    const std::vector<std::string> expected = {
        "a0", "b0", "a1", "b1", "a2"};
    check(first == expected, "interleaving matches the scheduler order");
    check(first == second, "interleaving is deterministic across runs");
    check(run_scenario(50U) == expected, "bounded spin preserves deterministic interleaving");
}

void test_single_runner_no_overlap() {
    // If two participants ever ran concurrently, this unguarded counter would
    // race; under the baton it cannot. We increment heavily while yielding.
    BatonExecutor executor;
    long counter = 0;
    const int a = executor.spawn([&counter](BatonExecutor& ex, int) {
        for (int i = 0; i < 1000; ++i) {
            ++counter;
            if ((i % 100) == 0) {
                ex.yield_to_scheduler();
            }
        }
    });
    const int b = executor.spawn([&counter](BatonExecutor& ex, int) {
        for (int i = 0; i < 1000; ++i) {
            ++counter;
            if ((i % 100) == 0) {
                ex.yield_to_scheduler();
            }
        }
    });
    bool a_done = false;
    bool b_done = false;
    // Drive both to completion, alternating.
    for (int round = 0; round < 100 && !(a_done && b_done); ++round) {
        if (!a_done) {
            a_done = executor.resume(a);
        }
        if (!b_done) {
            b_done = executor.resume(b);
        }
    }
    check(a_done && b_done, "both participants finished");
    check(counter == 2000, "no lost increments â€” exactly one ran at a time");
}

void test_shutdown_unwinds_parked_participant() {
    // A participant that yields forever must be unwound cleanly by shutdown
    // (no hang, thread joined), not leak or deadlock.
    bool reached_after_loop = false;
    {
        BatonExecutor executor;
        const int spinner = executor.spawn(
            [&reached_after_loop](BatonExecutor& ex, int) {
                while (true) {
                    ex.yield_to_scheduler();
                }
                // Unreachable; present to prove we do NOT fall through here.
                reached_after_loop = true;  // NOLINT
            });
        check(!executor.resume(spinner), "spinner yields, not finished");
        check(!executor.resume(spinner), "spinner still yielding");
        // executor destructor runs shutdown(): must unwind and join.
    }
    check(!reached_after_loop, "spinner body did not run past its wait loop");
    check(true, "shutdown completed without hanging");
}

void test_never_started_participant_shuts_down() {
    // A spawned-but-never-resumed participant must still join on shutdown.
    BatonExecutor executor;
    (void)executor.spawn([](BatonExecutor&, int) {
        // never resumed before shutdown
    });
    check(executor.participant_count() == 1U, "participant registered");
    // Destructor shutdown() must not hang joining the never-resumed thread.
}

void test_diagnostic_wake_boundaries() {
    for (unsigned spin : {0U, 50U}) for (bool enabled : {false, true}) {
        BatonExecutor ex;
        ex.enable_timing(enabled);
        ex.set_spin_budget(spin);
        const int id = ex.spawn([](BatonExecutor& body, int) {
            for (int i=0;i<20;++i) body.yield_to_scheduler();
        });
        for (int i=0;i<20;++i) check(!ex.resume(id), "timed body yielded");
        check(ex.resume(id), "timed body finished");
        const auto timing=ex.timing();
        check(timing.wakes==(enabled?42U:0U), "both sides of each transfer measured once");
        check(timing.max_wake_ns<=timing.wake_ns, "maximum is part of total");
        if (!enabled) check(timing.wake_ns==0 && timing.max_wake_ns==0, "ordinary transport stays unmeasured");
        bool rejected=false;
        try { ex.enable_timing(!enabled); } catch (const std::logic_error&) { rejected=true; }
        check(rejected, "no timing reconfiguration during active transport");
        rejected=false;
        try { ex.set_spin_budget(spin); } catch (const std::logic_error&) { rejected=true; }
        check(rejected, "no spin reconfiguration during active transport");
    }
}


struct FirstTouchTag;
struct SecondTouchTag;
int local_constructions=0,local_destructions=0;
struct FirstTouchValue {
    int number=0;
    FirstTouchValue() { ++local_constructions; }
    ~FirstTouchValue() { ++local_destructions; }
};
void test_first_touch_lifetime() {
    if (!BatonExecutor::fibers_supported()) return;
    BatonExecutor ex;ex.set_fiber_mode(true);
    const int id=ex.spawn([](BatonExecutor& body,int) {
        auto& first=jfg::runtime::execution_local<FirstTouchValue,FirstTouchTag>();
        check(local_constructions==1,"guest first touch does not construct ordinary TLS");
        auto& second=jfg::runtime::execution_local<FirstTouchValue,SecondTouchTag>();
        first.number=51;second.number=82;
        check(&first!=&second && local_constructions==2,"same value type with different tags has distinct storage");
        body.yield_to_scheduler();
        check(jfg::runtime::execution_local<FirstTouchValue,FirstTouchTag>().number==51 &&
              jfg::runtime::execution_local<FirstTouchValue,SecondTouchTag>().number==82,
              "tag identity and values survive cache invalidation");
    });
    check(!ex.resume(id) && ex.resume(id),"first touch scenario completes");
    ex.shutdown();
    check(local_destructions==2,"guest values are released after stack completion");
    check(jfg::runtime::execution_local<FirstTouchValue,FirstTouchTag>().number==0 &&
          local_constructions==3,"ordinary TLS constructs independently on its first use");
}

struct LocalTag;
struct StackLocal {
    int number=0;
    int* destroyed=nullptr;
    ~StackLocal() { if (destroyed) ++*destroyed; }
};
StackLocal& stack_local() { return jfg::runtime::execution_local<StackLocal,LocalTag>(); }
void test_fiber_stack_contract() {
    if (!BatonExecutor::fibers_supported()) return;
    const auto host_thread=std::this_thread::get_id();
    stack_local().number=17;
    const int previous_round=std::fegetround();
    for (int repetition=0;repetition<3;++repetition) {
        BatonExecutor ex;
        ex.enable_timing(true);ex.set_fiber_mode(true);
        std::vector<int> order;
        int destroyed=0,unwound=0;
        struct Unwind {int& count;~Unwind(){++count;}};
        const int a=ex.spawn([&](BatonExecutor& body,int) {
            Unwind unwind{unwound};
            check(std::this_thread::get_id()==host_thread,"fiber uses scheduler OS thread");
            check(stack_local().number==0,"new stack starts with its own state");
            stack_local().number=101;stack_local().destroyed=&destroyed;
            int nested_stack=731;
            std::fesetround(FE_DOWNWARD);
            order.push_back(1);body.yield_to_scheduler();
            check(nested_stack==731 && stack_local().number==101,"stack and local state survive handoff");
            check(std::fegetround()==FE_DOWNWARD,"first stack preserves FP mode");
            order.push_back(3);body.yield_to_scheduler();
            check(stack_local().number==101,"second handoff keeps first stack isolation");
            order.push_back(5);
        });
        const int b=ex.spawn([&](BatonExecutor& body,int) {
            Unwind unwind{unwound};
            check(stack_local().number==0,"second stack starts clean");
            stack_local().number=202;stack_local().destroyed=&destroyed;
            std::fesetround(FE_UPWARD);
            order.push_back(2);body.yield_to_scheduler();
            check(stack_local().number==202 && std::fegetround()==FE_UPWARD,"second stack owns TLS and FP");
            order.push_back(4);
            while (true) body.yield_to_scheduler();
        });
        check(!ex.resume(a) && !ex.resume(b),"both fibers yield");
        check(stack_local().number==17 && std::fegetround()==previous_round,"scheduler state survives fibers");
        check(!ex.resume(a) && !ex.resume(b) && ex.resume(a),"scheduler chooses exact fiber order");
        check(order==std::vector<int>({1,2,3,4,5}),"fiber interleaving matches chosen order");
        check(ex.timing().wakes==10,"fiber transfer timing measures both sides once");
        (void)ex.spawn([&](BatonExecutor&,int){check(false,"unresumed fiber must not execute during shutdown");});
        bool rejected=false;
        try { ex.set_fiber_mode(false); } catch (const std::logic_error&) {rejected=true;}
        check(rejected,"fiber backend cannot change while participants exist");
        ex.shutdown();ex.shutdown();
        check(unwound==2 && destroyed==2,"shutdown unwinds stacks before destroying their local state");
        check(stack_local().number==17,"ordinary TLS remains owned by scheduler");
    }
    {
        BatonExecutor ex;ex.set_fiber_mode(true);
        const int id=ex.spawn([](BatonExecutor&,int){throw std::runtime_error("fiber test exception");});
        bool caught=false;
        try {(void)ex.resume(id);}catch (const std::runtime_error& error){caught=std::string(error.what())=="fiber test exception";}
        check(caught,"guest exception crosses only through scheduler exception_ptr");
    }
    {
        BatonExecutor ex;ex.set_fiber_mode(true);
        bool rejected=false;
        std::thread other([&]{try {(void)ex.spawn([](BatonExecutor&,int){});}catch(const std::logic_error&){rejected=true;}});
        other.join();check(rejected,"cross-thread fiber access is rejected");
    }
    check(std::fegetround()==previous_round,"fiber shutdown restores scheduler floating point");
}

} // namespace

int main() {
    test_first_touch_lifetime();
    test_fiber_stack_contract();
    if (BatonExecutor::fibers_supported()) {
        BatonExecutor ex;ex.set_fiber_mode(true);ex.set_fiber_mode(false);
        bool ran=false;const int normal=ex.spawn([&](BatonExecutor&,int){ran=true;});
        check(ex.resume(normal) && ran,"empty fiber configuration can return to OS threads");
    }
    if (BatonExecutor::fibers_supported()) {
        BatonExecutor ex;ex.enable_timing(true);ex.set_fiber_mode(true);
        BatonExecutor::CycleSample first{},last{},other_first{},other_last{};
        const int a=ex.spawn([&](BatonExecutor& body,int) {
            first=body.execution_cycles();body.yield_to_scheduler();last=body.execution_cycles();
        });
        const int b=ex.spawn([&](BatonExecutor& body,int) {
            other_first=body.execution_cycles();volatile std::uint64_t value=3;
            for(unsigned i=0;i<1000000U;++i)value=value*1664525U+1013904223U;
            (void)value;other_last=body.execution_cycles();
        });
        check(!ex.resume(a) && ex.resume(b) && ex.resume(a),"cycle isolation scenario completes");
        check(first.valid && last.valid && other_first.valid && other_last.valid,"logical cycle samples are valid");
        check(first.participant==last.participant && first.participant!=other_first.participant,"cycle identities distinguish stacks");
        check(last.cycles>=first.cycles && other_last.cycles>=other_first.cycles,"per-stack cycles are monotonic");
        check(last.cycles-first.cycles < (other_last.cycles-other_first.cycles)/4U,"parked stack excludes another fiber's substantial CPU work");
    }
    test_diagnostic_wake_boundaries();
    test_deterministic_interleaving();
    test_single_runner_no_overlap();
    test_shutdown_unwinds_parked_participant();
    test_never_started_participant_shuts_down();
    if (failures != 0) {
        std::cerr << failures << " failure(s)\n";
        return 1;
    }
    std::cout << "all executor tests passed\n";
    return 0;
}
