/* Exact private jump/dispatch/ERET/exception bodies in controlled surroundings.
 * The test runner extracts those bodies; this fixture contains no guest ROM. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "oracle_instruction_effects.h"
#include "oracle_cpu_boundaries.h"
#define CORE_INTERPRETER 1
#define CORE_DYNAREC 2
#define M64MSG_ERROR 1
typedef struct instruction { void (*ops)(void); uint32_t addr, jfg_decoded_opcode; } instruction;
static instruction code[32], vector, *PC;
static struct { instruction *block; uint32_t start; } block, *actual = &block;
static int r4300emu = CORE_INTERPRETER, stop, llbit, dyna_interp;
static uint32_t Count, last_addr, Status, Cause, EPC, next_interupt, delay_slot, skip_jump;
static long long reg[32], *test_link;
static uint32_t rdram[1024*1024], jfg_oracle_updates, jfg_cpu_update = 1;
static FILE *jfg_cpu_stream;
static struct { uint32_t rows; } jfg_oracle_probe;
static uint32_t test_target;
static int test_taken, test_likely, cop_unusable;
static unsigned cases;
#include "oracle_instruction_effects.c"

static void require(int value) { if (!value) abort(); }
static void jfg_observed_cached_execute(void);
static void NOP(void) { ++PC; }
static void ADD(void) { reg[2] += 1; ++PC; }
static void READ_LINK(void) { reg[8] = reg[31]; ++PC; }
static void WRITE_LINK(void) { reg[31] += 4; ++PC; }
static void SET_EXL(void) { Status |= 2U; ++PC; }
static void FIN_BLOCK(void) { PC->ops = NOP; jfg_observed_cached_execute(); }
static void NOTCOMPILED(void) { PC->ops = ADD; jfg_observed_cached_execute(); }
static void NOTCOMPILED2(void) { NOTCOMPILED(); }
static void jfg_oracle_events_cached_instruction(void) { }
static void update_count(void) { Count += (PC->addr-last_addr)/2U; last_addr = PC->addr; }
static int check_cop1_unusable(void) { return cop_unusable; }
static void jump_to(uint32_t target) { require(target >= block.start && target < block.start+sizeof(code)/sizeof(code[0])*4U); PC = &code[(target-block.start)/4U]; }
static void generic_jump_to(uint32_t target) { vector.addr = target; PC = &vector; }
static void gen_interupt(void) {
    if (jfg_ofx_stream && !jfg_ofx_failed) require(!jfg_ofx_pending);
    Status |= 2U;
}
static void check_interupt(void) { }
static void dyna_jump(void) { }
static void DebugMessage(int severity, const char *message) { (void)severity; (void)message; }
void jfg_oracle_count_effect(unsigned a,uint32_t b,uint32_t c,uint32_t d) { (void)a; (void)b; (void)c; (void)d; }
jfg_eret_start jfg_oracle_eret_start(void) { jfg_eret_start start = {0}; return start; }
void jfg_oracle_eret_effect(jfg_eret_start start) { (void)start; }
#define UPDATE_DEBUGGER() do { } while (0)
#define TRACECB() do { } while (0)
#define sign_extended(value) ((value) = (int32_t)(value))
#define PCADDR PC->addr
#define DECLARE_INSTRUCTION(name) static void name(void)
#include "oracle_jump_macro.inc"
DECLARE_JUMP(TEST, test_target, test_taken, test_link, test_likely, 0)
#include "oracle_dispatch_body.inc"
#include "oracle_eret_body.inc"
#include "oracle_exception_body.inc"
static void SYSCALL(void) { Cause = 8U << 2U; exception_general(); }

static void reset(void) {
    unsigned i;
    for (i = 0; i < 32; ++i) {
        code[i].addr = 0x80001000U+i*4U; code[i].jfg_decoded_opcode = 0; code[i].ops = NOP;
        reg[i] = i ? (long long)(UINT64_C(0xa0b0c00000000000)+i) : 0;
    }
    PC = code; actual->block = code; actual->start = code[0].addr;
    test_target = code[4].addr; test_taken = 1; test_likely = 0; test_link = &reg[31];
    Count = 100; last_addr = PC->addr; Status = 1; Cause = 0; EPC = 0x80004000;
    llbit = 0; next_interupt = 0xffffffffU; delay_slot = skip_jump = 0;
    rdram[0xa9e90U/4U] = 0x80007000;
}
static void run_case(void) { jfg_observed_cached_execute(); require(!stop); ++cases; }
int main(int argc, char **argv) {
    int enabled;
    require(argc == 3); enabled = strcmp(argv[2], "disabled") != 0;
    reset();
    if (enabled) {
        require(!setenv("JFG_PHASE9_ORACLE_EFFECT_UPDATE", "1", 1));
        require(!setenv("JFG_PHASE9_ORACLE_ROOT", argv[1], 1));
        jfg_cpu_stream = tmpfile(); require(jfg_cpu_stream != NULL);
        if (!strcmp(argv[2], "bad-core")) r4300emu = 0;
        jfg_oracle_effects_open();
    }
    if (!strcmp(argv[2], "bad-core")) { require(stop && jfg_ofx_failed); return 0; }
    if (!strcmp(argv[2], "missing-effect")) {
        PC->jfg_decoded_opcode = 0x0c000404;
        jfg_oracle_effect_return(jfg_oracle_effect_entry());
        require(stop && !jfg_ofx_complete); return 0;
    }
    if (!strcmp(argv[2], "overlap")) {
        jfg_oracle_effect_entry(); jfg_oracle_effect_entry();
        require(stop && !jfg_ofx_complete); return 0;
    }
    if (!strcmp(argv[2], "budget")) {
        jfg_ofx_rows = JFG_OFX_MAX_ROWS;
        jfg_oracle_effect_entry(); require(stop && !jfg_ofx_complete); return 0;
    }
    code[0].ops = ADD; code[0].jfg_decoded_opcode = 0x24420001;
    run_case(); require((uint64_t)reg[2] == UINT64_C(0xa0b0c00000000003));
    reset(); code[0].ops = TEST; code[0].jfg_decoded_opcode = 0x0c000404;
    code[1].ops = READ_LINK; code[1].jfg_decoded_opcode = 0x03e04025;
    run_case(); require((uint64_t)reg[8] == UINT64_C(0xffffffff80001008));
    reset(); code[0].ops = TEST; code[0].jfg_decoded_opcode = 0x04130003;
    test_taken = 0; test_likely = 1; code[1].ops = READ_LINK; code[1].jfg_decoded_opcode = 0x03e04025;
    run_case(); require(PC == &code[2] && (uint64_t)reg[8] == UINT64_C(0xa0b0c00000000008));
    reset(); code[0].ops = TEST; code[0].jfg_decoded_opcode = 0x0c000404;
    code[1].ops = WRITE_LINK; code[1].jfg_decoded_opcode = 0x27ff0004;
    run_case(); require((uint64_t)reg[31] == UINT64_C(0xffffffff8000100c));
    reset(); code[0].ops = TEST_OUT; code[0].jfg_decoded_opcode = 0x0c000404;
    run_case(); require(PC == &code[4]);
    reset(); code[0].ops = TEST_IDLE; code[0].jfg_decoded_opcode = 0x1000ffff;
    test_target = PC->addr; test_link = &reg[0]; next_interupt = 164;
    run_case(); require(PC == code && Count == 164);
    reset(); code[0].ops = TEST_IDLE; code[0].jfg_decoded_opcode = 0x1000ffff;
    test_target = PC->addr; test_link = &reg[0]; next_interupt = 102;
    run_case(); require(PC == code && Count == 104);
    reset(); code[0].ops = ERET; code[0].jfg_decoded_opcode = 0x42000018; Status = 3;
    run_case(); require(PC->addr == EPC && Status == 1);
    reset(); code[0].ops = ERET; code[0].jfg_decoded_opcode = 0x42000018; Status = 3; next_interupt = 0;
    run_case(); require(PC->addr == EPC && Status == 3);
    reset(); code[0].ops = SYSCALL; code[0].jfg_decoded_opcode = 0x0000000c;
    run_case(); require(PC->addr == 0x80000180 && EPC == code[0].addr && Status == 3);
    reset(); code[0].ops = NOTCOMPILED; code[0].jfg_decoded_opcode = 0x24420001;
    run_case(); require(PC == &code[1]);
    reset(); code[0].ops = SET_EXL; code[0].jfg_decoded_opcode = 0x40806000;
    run_case(); require(Status == 3);
    jfg_oracle_updates = 1; jfg_oracle_effect_entry();
    if (enabled) {
        require(jfg_ofx_complete && !jfg_ofx_failed && !jfg_ofx_pending);
        require(!fclose(jfg_ofx_stream)); require(!fclose(jfg_cpu_stream));
    }
    printf("passed\t%u\t%u\t%u\t%u\n", cases, Count, Status, PC->addr);
    return 0;
}
