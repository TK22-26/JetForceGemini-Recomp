#ifndef JFG_ORACLE_INSTRUCTION_EFFECTS_H
#define JFG_ORACLE_INSTRUCTION_EFFECTS_H
#include <stdint.h>
enum jfg_oracle_effect_phase {
    JFG_OFX_ENTRY, JFG_OFX_ORDINARY, JFG_OFX_BRANCH, JFG_OFX_ERET,
    JFG_OFX_EXCEPTION, JFG_OFX_IDLE
};
void jfg_oracle_effects_open(void);
uint32_t jfg_oracle_effect_entry(void);
void jfg_oracle_effect_return(uint32_t token);
void jfg_oracle_effect_branch(uint32_t target, int taken, int likely);
void jfg_oracle_effect_eret(void);
void jfg_oracle_effect_exception(void);
void jfg_oracle_effect_idle(uint32_t ticks);
#endif
