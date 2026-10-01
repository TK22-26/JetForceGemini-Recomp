"""Strict, observational cache-call measurement parser; no hardware cache claim."""
import re

ALIGNMENTS = (0, 1, 15, 31)
LENGTHS = (-4, -1, 0, 1, 2, 15, 16, 17, 31, 32, 33, 8191, 8192, 8193, 16383, 16384)
CASES = tuple((function, alignment, length) for function in range(3)
              for alignment in ALIGNMENTS for length in LENGTHS) + ((3, 0, 0),)


def parse_trace(path):
    lines = path.read_text().splitlines()
    if len(lines) != 207 or lines[0] != "kind\tfunction\talignment\tlength\tvalue":
        raise ValueError("incomplete cache experiment")
    footer = lines[-1].split("\t")
    if len(footer) != 3 or footer[:2] != ["result", "true"] or \
            not re.fullmatch(r"0x[0-9a-f]{8}", footer[2]) or int(footer[2], 16) & 1:
        raise ValueError("cache experiment did not retain disabled interrupts")
    calls, aliases = [], []
    for case, line in zip(CASES, lines[1:194]):
        fields = line.split("\t")
        if len(fields) != 5 or fields[:4] != ["call", *map(str, case)] or \
                not fields[4].isdecimal() or not 6 < int(fields[4]) <= 0xffffffff:
            raise ValueError("malformed cache call")
        calls.append({"function": case[0], "alignment": case[1], "length": case[2],
                      "ticks_including_boundary": int(fields[4])})
    for index, line in enumerate(lines[194:-1]):
        fields = line.split("\t")
        if len(fields) != 5 or fields[:4] != ["alias", str(index // 3), str(index % 3), "-"] or \
                not re.fullmatch(r"0x[0-9a-f]{8}", fields[4]):
            raise ValueError("malformed cache alias observation")
        aliases.append(fields[4])
    return {"hardware_qualified": False, "calls": calls, "data_alias_observations": aliases,
            "data_aliases_coherent_in_probe": aliases == ["0x13579bdf", "0x2468ace0", "0x2468ace0"] * 4,
            "instruction_cache_and_self_modifying_code_qualified": False}
