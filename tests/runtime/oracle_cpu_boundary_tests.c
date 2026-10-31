/* Compile exact private upstream update_count/ERET bodies against controlled
 * CPU/interrupt surroundings. The snippets are extracted by the proof runner;
 * this fixture is original and contains no guest code. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "jfg/boot/device_event_probe.h"
#include "oracle_cpu_boundaries.h"

#define CORE_INTERPRETER 1
#define M64MSG_ERROR 1
static int r4300emu = CORE_INTERPRETER, stop;
static struct { uint32_t addr; } instruction;
static struct { uint32_t addr; } *unused_pc_type;
#define PC (&instruction)
#define PCADDR (PC->addr)
static uint32_t Count, last_addr, Status, Cause, EPC, llbit, next_interupt;
static int64_t reg[32];
static uint32_t rdram[1024 * 1024];
static uint32_t jfg_oracle_updates;
static jfg_device_event_probe jfg_oracle_probe;
#include "oracle_cpu_boundaries.c"

static unsigned checks, interrupts, jumps, errors, cases;
static void require(int condition) { if (!condition) abort(); }
static void DebugMessage(int severity, const char *message) { (void)severity; (void)message; ++errors; }
static void generic_jump_to(uint32_t pc) { PC->addr = pc; ++jumps; }
static void check_interupt(void) { ++checks; }
static void gen_interupt(void) {
    /* An enabled successful observer must have published the ERET before this
     * dispatcher mutates the state. A delayed wrapper would fail here. */
    if (jfg_cpu_stream && !jfg_cpu_failed) require(jfg_cpu_eret_rows == interrupts + 2U);
    ++interrupts; Status |= 2U;
}
#define DECLARE_INSTRUCTION(name) static void name(void)
#include "oracle_count_body.inc"
#include "oracle_eret_body.inc"

static void set_count(uint32_t value) {
    uint32_t before = Count, anchor = last_addr;
    Count = value;
    jfg_oracle_count_effect(JFG_COUNT_WRITE, before, anchor, value);
}
static void count_case(uint32_t pc, uint32_t anchor, uint32_t before, uint32_t expected) {
    PC->addr = pc; last_addr = anchor; set_count(before);
    update_count();
    require(Count == expected && last_addr == pc && !stop);
    ++cases;
}
int main(int argc, char **argv) {
    int i;
    require(argc == 3);
    (void)unused_pc_type;
    if (strcmp(argv[2], "disabled")) {
        require(setenv("JFG_PHASE9_CPU_BOUNDARY_UPDATE", "1", 1) == 0);
        require(setenv("JFG_PHASE9_ORACLE_ROOT", argv[1], 1) == 0);
        jfg_oracle_probe.stream = tmpfile(); require(jfg_oracle_probe.stream != NULL);
        jfg_oracle_probe.first = 1; jfg_oracle_probe.last = 1;
        if (!strcmp(argv[2], "bad-core")) r4300emu = 0;
        jfg_oracle_boundaries_open();
    }
    if (!strcmp(argv[2], "bad-core")) { require(stop && jfg_cpu_failed); return 0; }
    PC->addr = last_addr = 0x80001000U;
    jfg_oracle_boundaries_checkpoint(1);
    if (!strcmp(argv[2], "unobserved")) {
        ++Count; jfg_oracle_boundaries_checkpoint(1);
        require(stop && jfg_cpu_failed && !jfg_cpu_complete); return 0;
    }
    if (!strcmp(argv[2], "budget")) {
        jfg_cpu_sequence = JFG_CPU_BOUNDARY_LIMIT;
        update_count(); require(stop && jfg_cpu_failed && !jfg_cpu_complete); return 0;
    }
    count_case(0x80001010U, 0x80001000U, 100, 108);
    count_case(0x80001010U, 0x80001000U, 0xfffffffcU, 4);
    count_case(8, 0xfffffffcU, 7, 13);
    count_case(0x80001000U, 0x80001000U, 18, 18);
    for (i = 0; i < 2; ++i) {
        unsigned before_interrupts = interrupts;
        PC->addr = 0x80002010U; last_addr = 0x80002000U;
        set_count(100);
        Status = 0x34000003U; EPC = 0x80004000U; llbit = 1;
        next_interupt = i ? 0U : 0xffffffffU;
        reg[31] = (int64_t)UINT64_C(0xffffffff80005000);
        rdram[0xa9e90U / 4U] = 0x80006000U + (uint32_t)i * 0x200U;
        if (!strcmp(argv[2], "bad-eret")) Status |= 4U;
        ERET();
        if (!strcmp(argv[2], "bad-eret")) {
            require(stop && jfg_cpu_failed && !jfg_cpu_complete); return 0;
        }
        require(PC->addr == EPC && last_addr == EPC && llbit == 0 && Count == 108);
        require(Status == (i ? 0x34000003U : 0x34000001U));
        require(interrupts == before_interrupts + (unsigned)i && !errors && !stop);
        ++cases;
    }
    require(checks == 2 && jumps == 2);
    /* Writer accounting covers all direct mutation reasons as well; these
     * controlled mutations are not claims about full reset or CP0 semantics. */
    for (i = JFG_COUNT_IDLE; i < JFG_COUNT_REASON_LIMIT; ++i) {
        uint32_t before, anchor, operand;
        set_count(0xfffffff8U); before = Count; anchor = last_addr;
        operand = i == JFG_COUNT_IDLE ? 12U :
            i == JFG_COUNT_COMPARE_UP || i == JFG_COUNT_COMPARE_DOWN ? 2U :
            i == JFG_COUNT_NMI_RESET ? 0U : i == JFG_COUNT_HARD_RESET ? 0x5000U : 17U;
        Count = i == JFG_COUNT_IDLE || i == JFG_COUNT_COMPARE_UP ? Count + operand :
            i == JFG_COUNT_COMPARE_DOWN ? Count - operand : operand;
        jfg_oracle_count_effect((unsigned)i, before, anchor, operand);
        require(!stop); ++cases;
    }
    jfg_oracle_updates = 1;
    jfg_oracle_boundaries_checkpoint(2);
    if (jfg_cpu_stream) {
        require(jfg_cpu_complete && jfg_cpu_eret_rows == 2 && !jfg_cpu_failed);
        require(fclose(jfg_cpu_stream) == 0);
        require(fclose(jfg_oracle_probe.stream) == 0);
    }
    printf("passed\t%u\t%u\t%u\t%u\t%u\n", cases, Count, Status, checks, interrupts);
    return 0;
}
