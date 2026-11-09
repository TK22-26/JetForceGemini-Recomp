#ifndef JFG_ORACLE_CPU_BOUNDARIES_H
#define JFG_ORACLE_CPU_BOUNDARIES_H
#include <stdint.h>
enum jfg_count_reason {
    JFG_COUNT_LAZY, JFG_COUNT_IDLE, JFG_COUNT_WRITE, JFG_COUNT_COMPARE_UP,
    JFG_COUNT_COMPARE_DOWN, JFG_COUNT_NMI_RESET, JFG_COUNT_HARD_RESET,
    JFG_COUNT_REASON_LIMIT
};
typedef struct jfg_eret_start {
    uint32_t pc, count, anchor, status, epc, llbit, thread;
} jfg_eret_start;
void jfg_oracle_boundaries_open(void);
void jfg_oracle_boundaries_checkpoint(uint32_t invocation);
void jfg_oracle_count_effect(unsigned reason, uint32_t before,
    uint32_t anchor_before, uint32_t operand);
jfg_eret_start jfg_oracle_eret_start(void);
void jfg_oracle_eret_effect(jfg_eret_start before);
#endif
