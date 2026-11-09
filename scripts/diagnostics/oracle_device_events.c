/* Independently authored host observer, included in private pure_interp.c.
 * Core declarations come from that translation unit; no guest state writes,
 * MMIO accessors, update_count calls or event scheduling occur here. */
#include "device_event_probe.h"
#include "oracle_device_events.h"
#include <stdlib.h>

static jfg_device_event_probe jfg_oracle_probe;
static uint32_t jfg_oracle_updates, jfg_oracle_previous_pc, jfg_oracle_previous_word;
static uint32_t jfg_oracle_previous_thread, jfg_oracle_pcs[16];
static unsigned jfg_oracle_pc_count;
static int jfg_oracle_successor, jfg_oracle_initialized;
typedef struct jfg_oracle_dispatch {
    unsigned source;
    uint32_t deadline;
    int active, state_emitted;
} jfg_oracle_dispatch;
static jfg_oracle_dispatch jfg_oracle_dispatches[8];
static unsigned jfg_oracle_dispatch_depth;

static void jfg_oracle_events_fail(void) {
    jfg_oracle_probe.failed = 1;
    stop = 1;
}

static void jfg_oracle_emit(unsigned phase, unsigned source, uint32_t opcode,
    int deadline_valid, uint32_t deadline) {
    jfg_device_event_row row;
    unsigned i;
    if (jfg_oracle_probe.stream == NULL || jfg_oracle_probe.complete) return;
    memset(&row, 0, sizeof(row));
    row.invocation = jfg_oracle_updates + 1U;
    row.pc = PC->addr; row.opcode = opcode;
    row.previous_pc = jfg_oracle_previous_pc;
    row.previous_opcode = jfg_oracle_previous_word;
    row.phase = phase; row.source = source;
    row.clock_raw = Count; row.clock_anchor_pc = last_addr;
    row.deadline_valid = deadline_valid ? 1U : 0U; row.deadline = deadline;
    row.status = Status; row.cause = Cause;
    row.mi_pending = MI_register.mi_intr_reg;
    row.mi_mask = MI_register.mi_intr_mask_reg;
    row.thread = rdram[0xa9e90U / 4U];
    for (i = 0; i < 32; ++i) row.gpr[i] = (uint64_t)reg[i];
    if (!jfg_device_event_emit(&jfg_oracle_probe, &row)) jfg_oracle_events_fail();
}

void jfg_oracle_events_begin(void) {
    const char *enabled = getenv("JFG_PHASE9_DEVICE_EVENTS");
    const char *root, *focus, *pcs;
    char path[32768], extra;
    unsigned first, last;
    FILE *stream = NULL;
    int length;
    if (enabled == NULL) return;
    if (strcmp(enabled, "1") || jfg_oracle_initialized) {
        jfg_oracle_events_fail(); return;
    }
    jfg_oracle_initialized = 1;
    root = getenv("JFG_PHASE9_ORACLE_ROOT");
    focus = getenv("JFG_PHASE9_FOCUS_UPDATES");
    pcs = getenv("JFG_PHASE9_POINT_PCS");
    if (root == NULL || focus == NULL || pcs == NULL ||
        sscanf(focus, "%u:%u%c", &first, &last, &extra) != 2 ||
        first == 0 || last < first || last - first > 15U || last >= 1000000U) {
        jfg_oracle_events_fail(); return;
    }
    while (*pcs) {
        char *end;
        unsigned long value;
        unsigned i;
        if (jfg_oracle_pc_count == 16U || strlen(pcs) < 10U || pcs[0] != '0' || pcs[1] != 'x') {
            jfg_oracle_events_fail(); return;
        }
        value = strtoul(pcs + 2, &end, 16);
        if (end != pcs + 10 || (*end && *end != ',') || value < 0x80000000UL ||
            value > 0x803ffffcUL || value % 4UL) {
            jfg_oracle_events_fail(); return;
        }
        for (i = 0; i < jfg_oracle_pc_count; ++i)
            if (jfg_oracle_pcs[i] == (uint32_t)value) { jfg_oracle_events_fail(); return; }
        jfg_oracle_pcs[jfg_oracle_pc_count++] = (uint32_t)value;
        pcs = *end ? end + 1 : end;
        if (*end && !*pcs) { jfg_oracle_events_fail(); return; }
    }
    if (!jfg_oracle_pc_count) { jfg_oracle_events_fail(); return; }
    length = snprintf(path, sizeof(path), "%s/device-events.tsv", root);
    if (length < 0 || (size_t)length >= sizeof(path)) { jfg_oracle_events_fail(); return; }
#ifdef _MSC_VER
    if (fopen_s(&stream, path, "wb") != 0) stream = NULL;
#else
    stream = fopen(path, "wb");
#endif
    if (!jfg_device_event_open(&jfg_oracle_probe, stream, first > 1U ? first - 1U : 1U,
        last + 1U, JFG_EVENT_ORACLE_LAZY_COUNT)) jfg_oracle_events_fail();
}

void jfg_oracle_events_instruction(unsigned int opcode) {
    unsigned i;
    int selected = 0;
    uint32_t thread;
    if (jfg_oracle_probe.stream == NULL || jfg_oracle_probe.complete) return;
    /* Same observed US update-return site as the Lua update-hash callback.
     * This is an entry hook, not a claim that JR/its delay slot have retired. */
    if (PC->addr == 0x80045814U) ++jfg_oracle_updates;
    if (jfg_oracle_updates + 1U < jfg_oracle_probe.first) return;
    if (jfg_oracle_updates + 1U > jfg_oracle_probe.last) {
        if (!jfg_device_event_finish(&jfg_oracle_probe)) jfg_oracle_events_fail();
        return;
    }
    thread = rdram[0xa9e90U / 4U];
    if (thread != jfg_oracle_previous_thread)
        jfg_oracle_emit(JFG_EVENT_THREAD, JFG_EVENT_NONE, opcode, 0, 0);
    if (jfg_oracle_successor)
        jfg_oracle_emit(JFG_EVENT_SUCCESSOR, JFG_EVENT_NONE, opcode, 0, 0);
    for (i = 0; i < jfg_oracle_pc_count; ++i)
        if (PC->addr == jfg_oracle_pcs[i]) selected = 1;
    if (selected) jfg_oracle_emit(JFG_EVENT_INSTRUCTION, JFG_EVENT_NONE, opcode, 0, 0);
    jfg_oracle_successor = selected;
    jfg_oracle_previous_pc = PC->addr;
    jfg_oracle_previous_word = opcode;
    jfg_oracle_previous_thread = thread;
}

void jfg_oracle_events_cached_instruction(void) {
    uint32_t physical;
    if (jfg_oracle_probe.stream == NULL || jfg_oracle_probe.complete) return;
    physical = PC->addr & 0x1fffffffU;
    /* Direct RAM only, never fast_mem_access or an MMIO/debugger accessor.
     * Boot instructions outside RDRAM precede the focus window and do not
     * require an opcode. The generic row validator makes no retirement claim. */
    jfg_oracle_events_instruction(physical <= 0x3ffffcU && physical % 4U == 0U ?
        rdram[physical / 4U] : 0U);
}

void jfg_oracle_events_enter_dispatch(void) {
    if (jfg_oracle_probe.stream == NULL || jfg_oracle_probe.complete) return;
    if (jfg_oracle_dispatch_depth == 8U) { jfg_oracle_events_fail(); return; }
    memset(&jfg_oracle_dispatches[jfg_oracle_dispatch_depth++], 0, sizeof(jfg_oracle_dispatch));
}

void jfg_oracle_events_dispatch(int type, unsigned int deadline) {
    jfg_oracle_dispatch *event;
    if (jfg_oracle_probe.stream == NULL || jfg_oracle_probe.complete || !jfg_oracle_dispatch_depth) return;
    event = &jfg_oracle_dispatches[jfg_oracle_dispatch_depth - 1U];
    event->source = JFG_EVENT_OTHER;
    switch (type) {
    case VI_INT: event->source = JFG_EVENT_VI; break;
    case PI_INT: event->source = JFG_EVENT_PI; break;
    case SI_INT: event->source = JFG_EVENT_SI; break;
    case COMPARE_INT: event->source = JFG_EVENT_COMPARE; break;
    case SP_INT: event->source = JFG_EVENT_SP; break;
    case DP_INT: event->source = JFG_EVENT_DP; break;
    case AI_INT: event->source = JFG_EVENT_AI; break;
    case CHECK_INT: event->source = JFG_EVENT_CHECK; break;
    }
    event->active = 1; event->deadline = deadline;
    /* No opcode is fetched at device edges: doing so could invoke callbacks.
     * The zero opcode is an explicit unavailable value at these phases. */
    jfg_oracle_emit(JFG_EVENT_DISPATCH, event->source, 0, 1, deadline);
}

void jfg_oracle_events_accept(void) {
    jfg_oracle_dispatch *event;
    if (jfg_oracle_probe.stream == NULL || jfg_oracle_probe.complete || !jfg_oracle_dispatch_depth) return;
    event = &jfg_oracle_dispatches[jfg_oracle_dispatch_depth - 1U];
    if (!event->active) { jfg_oracle_events_fail(); return; }
    jfg_oracle_emit(JFG_EVENT_STATE, event->source, 0, 1, event->deadline);
    event->state_emitted = 1;
    jfg_oracle_emit(JFG_EVENT_ACCEPT, event->source, 0, 1, event->deadline);
}

void jfg_oracle_events_leave_dispatch(void) {
    jfg_oracle_dispatch *event;
    if (jfg_oracle_probe.stream == NULL || !jfg_oracle_dispatch_depth) return;
    event = &jfg_oracle_dispatches[--jfg_oracle_dispatch_depth];
    if (event->active && !event->state_emitted)
        jfg_oracle_emit(JFG_EVENT_STATE, event->source, 0, 1, event->deadline);
}
