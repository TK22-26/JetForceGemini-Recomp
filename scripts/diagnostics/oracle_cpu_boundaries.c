/* Included after oracle_device_events.c in the private pure-interpreter TU.
 * These host observations never update Count, invoke guest accessors, change
 * an event deadline or schedule work. Unknown Count changes reject capture.
 * The current implementation is specifically for the cached interpreter. */
#include "oracle_cpu_boundaries.h"
#include <inttypes.h>
#include <stdlib.h>
#include <string.h>

#define JFG_CPU_BOUNDARY_LIMIT 524288U
static FILE *jfg_cpu_stream;
static uint32_t jfg_cpu_update, jfg_cpu_sequence, jfg_cpu_count_rows, jfg_cpu_eret_rows;
static uint32_t jfg_cpu_previous_invocation, jfg_cpu_expected_count, jfg_cpu_previous_eret_thread;
static int jfg_cpu_started, jfg_cpu_complete, jfg_cpu_failed, jfg_cpu_initialized;

static void jfg_cpu_fail(void) { jfg_cpu_failed = 1; stop = 1; }
static int jfg_cpu_flush(void) {
    if (fflush(jfg_cpu_stream) != 0 || ferror(jfg_cpu_stream)) jfg_cpu_fail();
    return !jfg_cpu_failed;
}
static int jfg_cpu_active(void) {
    return jfg_cpu_stream != NULL && !jfg_cpu_complete && !jfg_cpu_failed &&
        jfg_oracle_updates + 1U == jfg_cpu_update;
}
static int jfg_cpu_row(void) {
    if (jfg_cpu_sequence == JFG_CPU_BOUNDARY_LIMIT) { jfg_cpu_fail(); return 0; }
    ++jfg_cpu_sequence;
    return 1;
}
static void jfg_cpu_hex(uint32_t value) {
    fprintf(jfg_cpu_stream, "\t0x%08" PRIx32, value);
}
void jfg_oracle_boundaries_open(void) {
    const char *enabled = getenv("JFG_PHASE9_CPU_BOUNDARY_UPDATE");
    const char *root;
    char *end, path[32768];
    unsigned long update;
    int size;
    if (enabled == NULL) return;
    if (jfg_cpu_initialized || r4300emu != CORE_INTERPRETER ||
        !*enabled || strspn(enabled, "0123456789") != strlen(enabled)) {
        jfg_cpu_fail(); return;
    }
    jfg_cpu_initialized = 1;
    update = strtoul(enabled, &end, 10);
    root = getenv("JFG_PHASE9_ORACLE_ROOT");
    if (*end || update == 0 || update > 1000000UL || root == NULL ||
        jfg_oracle_probe.stream == NULL || update < jfg_oracle_probe.first ||
        update > jfg_oracle_probe.last) { jfg_cpu_fail(); return; }
    jfg_cpu_update = (uint32_t)update;
    size = snprintf(path, sizeof(path), "%s/cpu-boundaries.tsv", root);
    if (size < 0 || (size_t)size >= sizeof(path)) { jfg_cpu_fail(); return; }
#ifdef _MSC_VER
    if (fopen_s(&jfg_cpu_stream, path, "wb") != 0) jfg_cpu_stream = NULL;
#else
    jfg_cpu_stream = fopen(path, "wb");
#endif
    if (jfg_cpu_stream == NULL) { jfg_cpu_fail(); return; }
    fprintf(jfg_cpu_stream, "jfg-oracle-cpu-boundaries-v1\t%" PRIu32 "\n", jfg_cpu_update);
    fputs("count-columns\tsequence\tinvocation\treason\tpc\tanchor_before\tanchor_after"
          "\tcount_before\tcount_after\toperand\tstatus\tcause\tthread_word\tdevice_sequence\n", jfg_cpu_stream);
    fputs("eret-columns\tsequence\tinvocation\tpc\ttarget_pc\tcount_before\tcount_after"
          "\tanchor_before\tanchor_after\tstatus_before\tstatus_after\tepc_before\tepc_after"
          "\tllbit_before\tllbit_after\tthread_word_before\tthread_word_after\tprevious_eret_thread_word"
          "\tdevice_sequence", jfg_cpu_stream);
    { unsigned i; for (i = 0; i < 32; ++i) fprintf(jfg_cpu_stream, "\tr%u", i); }
    fputc('\n', jfg_cpu_stream);
    jfg_cpu_flush();
}
void jfg_oracle_boundaries_checkpoint(uint32_t invocation) {
    if (jfg_cpu_stream == NULL || jfg_cpu_complete || jfg_cpu_failed) return;
    if (invocation < jfg_cpu_previous_invocation) { jfg_cpu_fail(); return; }
    jfg_cpu_previous_invocation = invocation;
    if (invocation < jfg_cpu_update) return;
    if (!jfg_cpu_started) {
        if (invocation != jfg_cpu_update) { jfg_cpu_fail(); return; }
        jfg_cpu_expected_count = Count;
        jfg_cpu_started = 1;
    }
    if (Count != jfg_cpu_expected_count) { jfg_cpu_fail(); return; }
    if (invocation > jfg_cpu_update) {
        fprintf(jfg_cpu_stream, "result\ttrue\t%" PRIu32 "\t%" PRIu32 "\t%" PRIu32 "\n",
            jfg_cpu_sequence, jfg_cpu_count_rows, jfg_cpu_eret_rows);
        if (jfg_cpu_flush()) jfg_cpu_complete = 1;
    }
}
void jfg_oracle_count_effect(unsigned reason, uint32_t before, uint32_t anchor_before, uint32_t operand) {
    static const char *const names[] = {"lazy", "idle", "write", "compare-up", "compare-down", "nmi-reset", "hard-reset"};
    uint32_t expected;
    if (!jfg_cpu_active()) return;
    if (!jfg_cpu_started || reason >= JFG_COUNT_REASON_LIMIT || before != jfg_cpu_expected_count) {
        jfg_cpu_fail(); return;
    }
    expected = reason == JFG_COUNT_LAZY ? before + (PC->addr - anchor_before) / 2U :
        reason == JFG_COUNT_IDLE || reason == JFG_COUNT_COMPARE_UP ? before + operand :
        reason == JFG_COUNT_COMPARE_DOWN ? before - operand : operand;
    if (Count != expected || (reason == JFG_COUNT_LAZY ? last_addr != PC->addr : last_addr != anchor_before) ||
        (reason == JFG_COUNT_LAZY && operand != 0) ||
        ((reason == JFG_COUNT_COMPARE_UP || reason == JFG_COUNT_COMPARE_DOWN) && operand != 2) ||
        (reason == JFG_COUNT_IDLE && (operand == 0 || operand % 4U)) ||
        (reason == JFG_COUNT_NMI_RESET && operand != 0) ||
        (reason == JFG_COUNT_HARD_RESET && operand != 0x5000U)) { jfg_cpu_fail(); return; }
    if (!jfg_cpu_row()) return;
    jfg_cpu_expected_count = Count;
    ++jfg_cpu_count_rows;
    fprintf(jfg_cpu_stream, "count\t%" PRIu32 "\t%" PRIu32 "\t%s", jfg_cpu_sequence, jfg_cpu_update, names[reason]);
    jfg_cpu_hex(PC->addr); jfg_cpu_hex(anchor_before); jfg_cpu_hex(last_addr);
    jfg_cpu_hex(before); jfg_cpu_hex(Count); jfg_cpu_hex(operand);
    jfg_cpu_hex(Status); jfg_cpu_hex(Cause); jfg_cpu_hex(rdram[0xa9e90U / 4U]);
    fprintf(jfg_cpu_stream, "\t%" PRIu32 "\n", jfg_oracle_probe.rows);
    jfg_cpu_flush();
}
jfg_eret_start jfg_oracle_eret_start(void) {
    jfg_eret_start result;
    memset(&result, 0, sizeof(result));
    if (jfg_cpu_stream != NULL && !jfg_cpu_complete && !jfg_cpu_failed) {
        result.pc = PC->addr; result.count = Count; result.anchor = last_addr;
        result.status = Status; result.epc = EPC; result.llbit = llbit;
        result.thread = rdram[0xa9e90U / 4U];
    }
    return result;
}
void jfg_oracle_eret_effect(jfg_eret_start before) {
    uint32_t thread;
    unsigned i;
    if (jfg_cpu_stream == NULL || jfg_cpu_complete || jfg_cpu_failed) return;
    thread = rdram[0xa9e90U / 4U];
    if (jfg_cpu_active()) {
        if (!jfg_cpu_started || Count != jfg_cpu_expected_count || (before.status & 6U) != 2U ||
            Status != (before.status & ~2U) || PC->addr != before.epc || EPC != before.epc ||
            last_addr != PC->addr || llbit != 0 || (uint64_t)reg[0] != 0 || !jfg_cpu_row()) {
            jfg_cpu_fail(); return;
        }
        ++jfg_cpu_eret_rows;
        fprintf(jfg_cpu_stream, "eret\t%" PRIu32 "\t%" PRIu32, jfg_cpu_sequence, jfg_cpu_update);
        jfg_cpu_hex(before.pc); jfg_cpu_hex(PC->addr); jfg_cpu_hex(before.count); jfg_cpu_hex(Count);
        jfg_cpu_hex(before.anchor); jfg_cpu_hex(last_addr); jfg_cpu_hex(before.status); jfg_cpu_hex(Status);
        jfg_cpu_hex(before.epc); jfg_cpu_hex(EPC); jfg_cpu_hex(before.llbit); jfg_cpu_hex(llbit);
        jfg_cpu_hex(before.thread); jfg_cpu_hex(thread); jfg_cpu_hex(jfg_cpu_previous_eret_thread);
        fprintf(jfg_cpu_stream, "\t%" PRIu32, jfg_oracle_probe.rows);
        for (i = 0; i < 32; ++i) fprintf(jfg_cpu_stream, "\t0x%016" PRIx64, (uint64_t)reg[i]);
        fputc('\n', jfg_cpu_stream); jfg_cpu_flush();
    }
    jfg_cpu_previous_eret_thread = thread;
}
