#include "jfg/boot/device_event_probe.h"
#include <stdlib.h>

static void check(int ok) { if (!ok) abort(); }

static FILE *temporary_stream(void) {
    FILE *stream = NULL;
#ifdef _MSC_VER
    check(tmpfile_s(&stream) == 0);
#else
    stream = tmpfile();
#endif
    check(stream != NULL);
    return stream;
}

int main(int argc, char **argv) {
    FILE *stream = temporary_stream();
    jfg_device_event_probe probe;
    jfg_device_event_row row;
    unsigned phase;
    memset(&row, 0, sizeof(row));
    check(jfg_device_event_open(&probe, stream, 7, 9, JFG_EVENT_NATIVE_PRE_INSTRUCTION));
    row.invocation = 6;
    check(jfg_device_event_emit(&probe, &row) && probe.rows == 0);
    row.invocation = 7; row.pc = 0x8009693cU; row.opcode = 0x15e0001cU;
    row.gpr[31] = UINT64_C(0xffffffff80096930);
    row.clock_raw = UINT32_MAX; row.thread = 0x800f92a0U;
    for (phase = 0; phase < JFG_EVENT_PHASE_COUNT; ++phase) {
        row.phase = phase;
        row.source = phase >= JFG_EVENT_DISPATCH ? JFG_EVENT_VI : JFG_EVENT_NONE;
        row.deadline_valid = phase >= JFG_EVENT_DISPATCH ? 1U : 0U;
        row.deadline = row.deadline_valid ? 42U : 0U;
        check(jfg_device_event_emit(&probe, &row));
    }
    row.invocation = 10;
    check(jfg_device_event_emit(&probe, &row) && probe.complete && probe.rows == 6);
    check(jfg_device_event_finish(&probe));
    if (argc == 2 && strcmp(argv[1], "--fixture") == 0) {
        int c;
        rewind(stream);
        while ((c = fgetc(stream)) != EOF) putchar(c);
    }
    fclose(stream);

    stream = temporary_stream();
    check(!jfg_device_event_open(&probe, stream, 0, 2, 0));
    check(!jfg_device_event_open(&probe, stream, 1, 19, 0));
    check(!jfg_device_event_open(&probe, stream, 1, 2, 2));
    check(jfg_device_event_open(&probe, stream, 7, 9, JFG_EVENT_ORACLE_LAZY_COUNT));
    row.invocation = 7; row.gpr[0] = 1;
    check(!jfg_device_event_emit(&probe, &row) && probe.failed);
    check(!jfg_device_event_finish(&probe));
    fclose(stream);

    stream = temporary_stream();
    check(jfg_device_event_open(&probe, stream, 7, 9, JFG_EVENT_ORACLE_LAZY_COUNT));
    row.gpr[0] = 0; probe.rows = JFG_DEVICE_EVENT_LIMIT;
    check(!jfg_device_event_emit(&probe, &row) && probe.failed);
    fclose(stream);
    return 0;
}
