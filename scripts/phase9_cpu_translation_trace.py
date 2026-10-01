"""Observe boot TLB state; never assume undefined hardware reset contents."""
import re


def parse_trace(path):
    lines = path.read_text().splitlines()
    if len(lines) not in (37, 43) or lines[0] != "kind\tindex\thi_or_ticks\tlo0_or_result\tlo1\tmask":
        raise ValueError("incomplete translation experiment")
    footer = lines[-1].split("\t")
    if footer[:2] != ["result", "true"] or len(footer) not in (2, 3) or \
            (len(footer) == 3 and not re.fullmatch(r"0x[0-9a-f]{8}", footer[2])):
        raise ValueError("malformed translation footer")
    probe_index = footer[2] if len(footer) == 3 else None
    if probe_index is not None and int(probe_index, 16) & ~0x8000003f:
        raise ValueError("invalid probe Index register bits")
    entries, calls = [], []
    for index, line in enumerate(lines[1:33]):
        fields = line.split("\t")
        if len(fields) != 6 or fields[:2] != ["tlb", str(index)] or \
                not all(re.fullmatch(r"0x[0-9a-f]{8}", word) for word in fields[2:]):
            raise ValueError("malformed TLB observation")
        entries.append(dict(zip(("hi", "lo0", "lo1", "mask"), fields[2:])))
    for index, line in enumerate(lines[33:36]):
        fields = line.split("\t")
        if len(fields) != 6 or fields[:2] != ["call", str(index)] or fields[4:] != ["-", "-"] or \
                not fields[2].isdecimal() or not 0 < int(fields[2]) <= 0xffffffff or \
                not re.fullmatch(r"0x[0-9a-f]{8}", fields[3]):
            raise ValueError("malformed translation call")
        if index > 0 and fields[3] != "0x00001234":
            raise ValueError("direct translation mismatch")
        calls.append({"argument": ("0x00000000", "0x80001234", "0xa0001234")[index],
                      "ticks_including_boundary": int(fields[2]), "result": fields[3]})
    probes = []
    for index, line in enumerate(lines[36:-1]):
        fields = line.split("\t")
        if len(fields) != 6 or fields[:3] != ["probe", str(index), "-"] or \
                fields[4:] != ["-", "-"] or not re.fullmatch(r"0x[0-9a-f]{8}", fields[3]):
            raise ValueError("malformed additional TLB probe")
        value = int(fields[3], 16)
        if value & ~0x8000003f:
            raise ValueError("invalid probe bits")
        # Duplicate case zero is observational, not an architectural choice.
        if index in (1, 3, 5) and not value & 0x80000000:
            raise ValueError("ASID or VPN miss not reported")
        if index in (2, 4) and value != {2: 5, 4: 17}[index]:
            raise ValueError("global or masked-page probe mismatch")
        probes.append(fields[3])
    return {"hardware_qualified": False, "boot_tlb_observations": entries,
            "additional_probe_indices": probes,
            "null_probe_index": probe_index,
            "calls": calls, "null_translation_is_observation_not_reset_contract": True}
