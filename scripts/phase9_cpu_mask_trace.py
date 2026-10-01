"""Strict original-OS interrupt-mask fixture parser, not interrupt-delivery proof."""
import re


def parse_trace(path):
    lines = path.read_text().splitlines()
    if len(lines) != 130 or lines[0] != "old_mask\trequested_mask\tticks\tresult\tstatus\tmi_mask":
        raise ValueError("incomplete mask probe")
    footer = lines[-1].split("\t")
    if len(footer) != 3 or footer[:2] != ["result", "true"] or \
            not re.fullmatch(r"0x[0-9a-f]{8}", footer[2]) or int(footer[2], 16) > 63:
        raise ValueError("invalid mask probe footer")
    calls = []
    for index, line in enumerate(lines[1:-1]):
        fields = line.split("\t")
        old, requested = (0 if index < 64 else 63), index % 64
        if len(fields) != 6 or fields[:2] != [str(old), str(requested)] or \
                not fields[2].isdecimal() or not 6 < int(fields[2]) <= 0xffffffff or \
                not all(re.fullmatch(r"0x[0-9a-f]{8}", word) for word in fields[3:]):
            raise ValueError("invalid mask call")
        if [int(value, 16) for value in fields[3:]] != [old << 16 | 0xff00, 0x0400ff00, requested]:
            raise ValueError("original mask semantics disagree with fixture")
        calls.append({"old_mask": old, "requested_mask": requested,
                      "ticks_including_boundary": int(fields[2])})
    return {"hardware_qualified": False, "boot_mi_mask_observed": int(footer[2], 16),
            "mask_semantics_pass": True, "interrupt_delivery_qualified": False, "calls": calls}
