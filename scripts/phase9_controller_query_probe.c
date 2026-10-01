/* Diagnostic: execute the existing generated US query builder on copied
 * focused snapshots. Link fn_000_1494_recomp.c from the private generated root.
 * No game bytes or snapshots are embedded in this source. */
#include <stdio.h>
#include <string.h>
#include "recomp.h"

extern void fn_000_1494_recomp(uint8_t *, recomp_context *);

enum { RAM_BYTES = 4 * 1024 * 1024, MAX_CHANNELS = 0x105341,
       QUERY_BUFFER = 0x105030 };

static int probe(const char *label, const char *path, unsigned expected,
                 unsigned query_limit) {
    FILE *file = fopen(path, "rb");
    uint8_t *raw = malloc(RAM_BYTES), *memory = malloc(RAM_BYTES);
    if (!file || !raw || !memory) return 2;
    if (fread(raw, 1, RAM_BYTES, file) != RAM_BYTES || fgetc(file) != EOF)
        return 3;
    fclose(file);
    unsigned count = raw[MAX_CHANNELS];
    if (count != expected) return 4;
    raw[MAX_CHANNELS] = (uint8_t)query_limit;
    /* Snapshot bytes are canonical; generated MEM_B uses word-swapped RAM. */
    for (unsigned i = 0; i < RAM_BYTES; ++i) memory[i ^ 3U] = raw[i];
    recomp_context context = {0};
    context.r29 = 0x803ff000U;
    context.r4 = 0; /* controller status query */
    fn_000_1494_recomp(memory, &context);
    unsigned channels = 0;
    const uint8_t packet[8] = {0xff, 1, 3, 0, 0xff, 0xff, 0xff, 0xff};
    for (; channels < 4; ++channels) {
        unsigned start = QUERY_BUFFER + 8 * channels;
        if (memory[start ^ 3U] == 0xfe) break;
        for (unsigned byte = 0; byte < 8; ++byte)
            if (memory[(start + byte) ^ 3U] != packet[byte]) return 5;
    }
    if (channels != query_limit ||
        memory[(QUERY_BUFFER + 8 * channels) ^ 3U] != 0xfe) return 6;
    printf("%s: captured_limit=%u generated_query_channels=%u\n",
           label, count, channels);
    free(raw);
    free(memory);
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 3) return 1;
    int result = probe("native", argv[1], 0, 0);
    if (result) return result;
    result = probe("oracle", argv[2], 4, 4);
    if (result) return result;
    return probe("native-counterfactual-limit-four", argv[1], 0, 4);
}
