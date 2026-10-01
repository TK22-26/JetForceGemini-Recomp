#ifndef JFG_BOOT_DEVICE_EVENT_PROBE_H
#define JFG_BOOT_DEVICE_EVENT_PROBE_H

/* Observation-only C ABI, shared by the native observer and private oracle
 * adapter. This writer never reads guest memory, advances time or schedules
 * events. Clock values retain their engine-specific meaning; they are not a
 * hardware clock or permission to compare lazy Count with committed work. */
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define JFG_DEVICE_EVENT_LIMIT 65536U

enum jfg_device_event_phase {
    JFG_EVENT_INSTRUCTION = 0, JFG_EVENT_SUCCESSOR, JFG_EVENT_THREAD,
    JFG_EVENT_DISPATCH, JFG_EVENT_STATE, JFG_EVENT_ACCEPT,
    JFG_EVENT_PHASE_COUNT
};
enum jfg_device_event_source {
    JFG_EVENT_NONE = 0, JFG_EVENT_VI, JFG_EVENT_PI, JFG_EVENT_SI,
    JFG_EVENT_COMPARE, JFG_EVENT_SP, JFG_EVENT_DP, JFG_EVENT_AI,
    JFG_EVENT_CHECK, JFG_EVENT_OTHER, JFG_EVENT_SOURCE_COUNT
};
enum jfg_device_event_clock {
    JFG_EVENT_NATIVE_PRE_INSTRUCTION = 0,
    JFG_EVENT_ORACLE_LAZY_COUNT = 1
};

typedef struct jfg_device_event_row {
    uint32_t invocation, pc, opcode, previous_pc, previous_opcode;
    uint32_t clock_raw, clock_anchor_pc, deadline_valid, deadline;
    uint32_t status, cause, mi_pending, mi_mask, thread;
    uint64_t gpr[32];
    unsigned phase, source;
} jfg_device_event_row;

typedef struct jfg_device_event_probe {
    FILE *stream;
    uint32_t first, last, rows, previous_invocation;
    unsigned clock_basis;
    int failed, complete;
} jfg_device_event_probe;

static inline int jfg_device_event_open(jfg_device_event_probe *probe, FILE *stream,
    uint32_t first, uint32_t last, unsigned clock_basis) {
    unsigned i;
    memset(probe, 0, sizeof(*probe));
    if (stream == NULL || first == 0 || last < first || last > 1000000U ||
        last - first > 17U || clock_basis > JFG_EVENT_ORACLE_LAZY_COUNT) {
        probe->failed = 1;
        return 0;
    }
    probe->stream = stream;
    probe->first = first;
    probe->last = last;
    probe->clock_basis = clock_basis;
    fprintf(stream, "jfg-phase9-device-events-v1\t%s\t%" PRIu32 "\t%" PRIu32 "\n",
        clock_basis == JFG_EVENT_NATIVE_PRE_INSTRUCTION ? "native-pre-instruction-count" : "oracle-lazy-count",
        first, last);
    fputs("sequence\tphase\tsource\tinvocation\tpc\topcode\tprevious_pc\tprevious_opcode"
          "\tclock_raw\tclock_anchor_pc\tdeadline_valid\tdeadline\tstatus\tcause"
          "\tmi_pending\tmi_mask\tthread", stream);
    for (i = 0; i < 32; ++i) fprintf(stream, "\tr%u_lo\tr%u_hi", i, i);
    fputc('\n', stream);
    if (fflush(stream) != 0 || ferror(stream)) probe->failed = 1;
    return !probe->failed;
}

static inline int jfg_device_event_finish(jfg_device_event_probe *probe) {
    if (probe->failed || probe->stream == NULL) return 0;
    if (probe->complete) return 1;
    fprintf(probe->stream, "result\ttrue\t%" PRIu32 "\n", probe->rows);
    if (fflush(probe->stream) != 0 || ferror(probe->stream)) probe->failed = 1;
    probe->complete = !probe->failed;
    return probe->complete;
}

static inline int jfg_device_event_emit(jfg_device_event_probe *probe,
    const jfg_device_event_row *row) {
    static const char *const phases[] = {"instruction", "successor", "thread-word-change",
        "dispatch", "state", "accept"};
    static const char *const sources[] = {"none", "vi", "pi", "si", "compare",
        "sp", "dp", "ai", "check", "other"};
    unsigned i;
    if (probe->failed || probe->stream == NULL) return 0;
    if (probe->complete) return 1;
    if (row->invocation < probe->first) return 1;
    if (row->invocation > probe->last) return jfg_device_event_finish(probe);
    if (row->phase >= JFG_EVENT_PHASE_COUNT || row->source >= JFG_EVENT_SOURCE_COUNT ||
        row->deadline_valid > 1 || (!row->deadline_valid && row->deadline != 0) ||
        row->gpr[0] != 0 || row->invocation < probe->previous_invocation ||
        probe->rows == JFG_DEVICE_EVENT_LIMIT) {
        probe->failed = 1;
        return 0;
    }
    ++probe->rows;
    probe->previous_invocation = row->invocation;
    fprintf(probe->stream, "%" PRIu32 "\t%s\t%s\t%" PRIu32,
        probe->rows, phases[row->phase], sources[row->source], row->invocation);
#define JFG_DEVICE_EVENT_HEX(value) fprintf(probe->stream, "\t0x%08" PRIx32, (uint32_t)(value))
    JFG_DEVICE_EVENT_HEX(row->pc); JFG_DEVICE_EVENT_HEX(row->opcode);
    JFG_DEVICE_EVENT_HEX(row->previous_pc); JFG_DEVICE_EVENT_HEX(row->previous_opcode);
    JFG_DEVICE_EVENT_HEX(row->clock_raw); JFG_DEVICE_EVENT_HEX(row->clock_anchor_pc);
    fprintf(probe->stream, "\t%" PRIu32, row->deadline_valid);
    JFG_DEVICE_EVENT_HEX(row->deadline); JFG_DEVICE_EVENT_HEX(row->status);
    JFG_DEVICE_EVENT_HEX(row->cause); JFG_DEVICE_EVENT_HEX(row->mi_pending);
    JFG_DEVICE_EVENT_HEX(row->mi_mask); JFG_DEVICE_EVENT_HEX(row->thread);
    for (i = 0; i < 32; ++i) {
        JFG_DEVICE_EVENT_HEX(row->gpr[i]); JFG_DEVICE_EVENT_HEX(row->gpr[i] >> 32);
    }
#undef JFG_DEVICE_EVENT_HEX
    fputc('\n', probe->stream);
    if (fflush(probe->stream) != 0 || ferror(probe->stream)) probe->failed = 1;
    return !probe->failed;
}
#endif
