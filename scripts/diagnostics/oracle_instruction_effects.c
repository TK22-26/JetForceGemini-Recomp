/* Original host observer, included after oracle_cpu_boundaries.c. Cached
 * interpreter only. No guest accessors, clock writes, dispatch or RAM writes.
 * Opcode is retained at decode, not fetched again from mutable RDRAM. */
#include "oracle_instruction_effects.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define JFG_OFX_MAX_ROWS 4194304U
#define JFG_OFX_MAX_BYTES (512U * 1024U * 1024U)
static FILE *jfg_ofx_stream;
static uint32_t jfg_ofx_update, jfg_ofx_rows, jfg_ofx_bytes, jfg_ofx_pending;
static uint32_t jfg_ofx_pc, jfg_ofx_opcode, jfg_ofx_entry_status, jfg_ofx_previous_device;
static uint32_t jfg_ofx_last_invocation;
static uint64_t jfg_ofx_registers[32];
static int jfg_ofx_complete, jfg_ofx_failed, jfg_ofx_started, jfg_ofx_initialized;

static void jfg_ofx_fail(void) { jfg_ofx_failed = 1; stop = 1; }
static int jfg_ofx_branch_word(uint32_t word) {
    unsigned op = word >> 26U, rt = (word >> 16U) & 31U;
    return (op == 0 && ((word & 63U) == 8U || (word & 63U) == 9U)) ||
        (op == 1 && (rt <= 3U || (rt >= 16U && rt <= 19U))) ||
        (op >= 2U && op <= 7U) || (op >= 20U && op <= 23U) ||
        (op == 17U && ((word >> 21U) & 31U) == 8U);
}
static void jfg_ofx_put(const void *data, size_t size) {
    if (jfg_ofx_failed) return;
    if (size > JFG_OFX_MAX_BYTES - jfg_ofx_bytes ||
        fwrite(data, 1, size, jfg_ofx_stream) != size) { jfg_ofx_fail(); return; }
    jfg_ofx_bytes += (uint32_t)size;
}
static void jfg_ofx_u32(uint32_t word) {
    unsigned char bytes[4]; unsigned i;
    for (i = 0; i < 4; ++i) bytes[i] = (unsigned char)(word >> (8U*i));
    jfg_ofx_put(bytes, sizeof(bytes));
}
static void jfg_ofx_row(unsigned phase, uint32_t target, uint32_t flags, uint32_t idle_ticks) {
    uint32_t words[16], mask = 0; unsigned i; unsigned char tag = (unsigned char)phase;
    if (jfg_ofx_rows == JFG_OFX_MAX_ROWS ||
        jfg_ofx_bytes > JFG_OFX_MAX_BYTES - (1U + 16U*4U + 32U*8U + 5U) ||
        (uint64_t)reg[0] != 0 || PC->addr % 4U || last_addr % 4U ||
        rdram[0xa9e90U/4U] % 4U || delay_slot > 3U || (llbit != 0 && llbit != 1) ||
        jfg_oracle_probe.rows < jfg_ofx_previous_device || jfg_oracle_probe.rows > 65536U) {
        jfg_ofx_fail(); return;
    }
    for (i = 0; i < 32; ++i)
        if (!jfg_ofx_rows || (uint64_t)reg[i] != jfg_ofx_registers[i]) mask |= UINT32_C(1) << i;
    words[0] = jfg_ofx_pc; words[1] = jfg_ofx_opcode;
    words[2] = rdram[0xa9e90U/4U]; words[3] = Count; words[4] = last_addr;
    words[5] = Status; words[6] = Cause; words[7] = PC->addr;
    words[8] = delay_slot; words[9] = jfg_oracle_probe.rows;
    words[10] = target; words[11] = flags; words[12] = idle_ticks;
    words[13] = EPC; words[14] = (uint32_t)llbit; words[15] = mask;
    jfg_ofx_put(&tag, 1);
    for (i = 0; i < 16; ++i) jfg_ofx_u32(words[i]);
    for (i = 0; i < 32; ++i) if (mask & (UINT32_C(1) << i)) {
        uint64_t value = (uint64_t)reg[i];
        jfg_ofx_u32((uint32_t)value); jfg_ofx_u32((uint32_t)(value >> 32U));
        jfg_ofx_registers[i] = value;
    }
    ++jfg_ofx_rows; jfg_ofx_previous_device = jfg_oracle_probe.rows;
}
void jfg_oracle_effects_open(void) {
    const char *enabled = getenv("JFG_PHASE9_ORACLE_EFFECT_UPDATE"), *root;
    char *end, path[32768]; unsigned long update; int length;
    if (enabled == NULL) return;
    if (jfg_ofx_initialized || r4300emu != CORE_INTERPRETER || !*enabled ||
        strspn(enabled, "0123456789") != strlen(enabled)) { jfg_ofx_fail(); return; }
    jfg_ofx_initialized = 1;
    update = strtoul(enabled, &end, 10); root = getenv("JFG_PHASE9_ORACLE_ROOT");
    if (*end || update == 0 || update > 1000000UL || root == NULL ||
        jfg_cpu_stream == NULL || jfg_cpu_update != update) { jfg_ofx_fail(); return; }
    jfg_ofx_update = (uint32_t)update;
    length = snprintf(path, sizeof(path), "%s/oracle-effects.bin", root);
    if (length < 0 || (size_t)length >= sizeof(path)) { jfg_ofx_fail(); return; }
#ifdef _MSC_VER
    if (fopen_s(&jfg_ofx_stream, path, "wb") != 0) jfg_ofx_stream = NULL;
#else
    jfg_ofx_stream = fopen(path, "wb");
#endif
    if (jfg_ofx_stream == NULL) { jfg_ofx_fail(); return; }
    jfg_ofx_put("JFGOFX1\0", 8); jfg_ofx_u32(jfg_ofx_update);
}
uint32_t jfg_oracle_effect_entry(void) {
    uint32_t invocation = jfg_oracle_updates + 1U;
    if (jfg_ofx_stream == NULL || jfg_ofx_complete || jfg_ofx_failed) return 0;
    if (invocation < jfg_ofx_last_invocation || jfg_ofx_pending) { jfg_ofx_fail(); return 0; }
    jfg_ofx_last_invocation = invocation;
    if (invocation < jfg_ofx_update) return 0;
    if (invocation > jfg_ofx_update) {
        unsigned char footer = 255;
        if (!jfg_ofx_started || !jfg_ofx_rows) { jfg_ofx_fail(); return 0; }
        jfg_ofx_put(&footer, 1); jfg_ofx_u32(jfg_ofx_rows);
        if (fflush(jfg_ofx_stream) || ferror(jfg_ofx_stream)) jfg_ofx_fail();
        if (!jfg_ofx_failed) jfg_ofx_complete = 1;
        return 0;
    }
    if (!PC->addr || PC->addr % 4U ||
        (delay_slot && jfg_ofx_branch_word(PC->jfg_decoded_opcode))) { jfg_ofx_fail(); return 0; }
    jfg_ofx_started = 1;
    jfg_ofx_pc = PC->addr; jfg_ofx_opcode = PC->jfg_decoded_opcode;
    jfg_ofx_entry_status = Status;
    jfg_ofx_row(JFG_OFX_ENTRY, 0, 0, 0);
    jfg_ofx_pending = jfg_ofx_rows;
    return jfg_ofx_failed ? 0 : jfg_ofx_pending;
}
static int jfg_ofx_active(void) {
    return jfg_ofx_stream != NULL && !jfg_ofx_complete && !jfg_ofx_failed && jfg_ofx_pending != 0;
}
void jfg_oracle_effect_return(uint32_t token) {
    if (!token || jfg_ofx_failed || jfg_ofx_complete) return;
    /* Branch/ERET/exception hooks close the pair before nested dispatch. */
    if (token < jfg_ofx_rows && !jfg_ofx_pending) return;
    if (!jfg_ofx_active() || token != jfg_ofx_pending ||
        jfg_ofx_branch_word(jfg_ofx_opcode) || jfg_ofx_opcode == 0x42000018U ||
        (((Status ^ jfg_ofx_entry_status) & 2U) &&
         (jfg_ofx_opcode & 0xffe0ffffU) != 0x40806000U)) { jfg_ofx_fail(); return; }
    jfg_ofx_row(JFG_OFX_ORDINARY, 0, 0, 0); jfg_ofx_pending = 0;
}
void jfg_oracle_effect_branch(uint32_t target, int taken, int likely) {
    if (!jfg_ofx_active()) return;
    if (!jfg_ofx_branch_word(jfg_ofx_opcode) || PC->addr != jfg_ofx_pc || target % 4U ||
        (taken != 0 && taken != 1) || (likely != 0 && likely != 1)) { jfg_ofx_fail(); return; }
    jfg_ofx_row(JFG_OFX_BRANCH, target, (uint32_t)taken | ((uint32_t)likely << 1U), 0);
    jfg_ofx_pending = 0;
}
void jfg_oracle_effect_eret(void) {
    if (!jfg_ofx_active()) return;
    if (jfg_ofx_opcode != 0x42000018U || (jfg_ofx_entry_status & 6U) != 2U ||
        Status != (jfg_ofx_entry_status & ~2U) || PC->addr != EPC || last_addr != EPC || llbit) {
        jfg_ofx_fail(); return;
    }
    jfg_ofx_row(JFG_OFX_ERET, EPC, 0, 0); jfg_ofx_pending = 0;
}
void jfg_oracle_effect_exception(void) {
    if (!jfg_ofx_active()) return;
    if (!(Status & 2U) || (PC->addr != 0x80000000U && PC->addr != 0x80000180U)) {
        jfg_ofx_fail(); return;
    }
    jfg_ofx_row(JFG_OFX_EXCEPTION, PC->addr, 0, 0); jfg_ofx_pending = 0;
}
void jfg_oracle_effect_idle(uint32_t ticks) {
    if (!jfg_ofx_active()) return;
    if (!jfg_ofx_branch_word(jfg_ofx_opcode) || PC->addr != jfg_ofx_pc || ticks == 0 || ticks % 4U) {
        jfg_ofx_fail(); return;
    }
    jfg_ofx_row(JFG_OFX_IDLE, PC->addr, 0, ticks); jfg_ofx_pending = 0;
}
