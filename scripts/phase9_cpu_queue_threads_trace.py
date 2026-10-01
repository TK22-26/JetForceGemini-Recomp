"""Validate original-OS thread handoffs; never label blocked time CPU cost."""

NAMES = ("send_lower", "send_higher", "recv_wake_sender", "recv_final",
         "worker_recv_first", "worker_recv_second", "worker_fill", "worker_block_send")
VALID = (1, 1, 1, 0, 0, 0, 1, 1)


def parse_trace(path):
    lines = path.read_text().splitlines()
    if len(lines) not in (11, 12, 13) or lines[0] != "case\tticks\tresult\tvalid\tstatus" or \
            lines[9] != "payloads\t1111\t2222\t3333\t4444":
        raise ValueError("incomplete or incorrect thread queue microtest")
    footer = lines[-1].split("\t")
    if len(footer) != 6 or footer[:4] != ["result", "true", "0", "0"]:
        raise ValueError("exception or premature lower-priority handoff")
    masks = [int(value, 16) for value in footer[4:]]
    if any(not 0 < value <= 0xffffffff or value & 7 for value in masks):
        raise ValueError("thread test must run with IE/EXL/ERL clear")
    entry_status = None
    if len(lines) >= 12:
        entry = lines[10].split("\t")
        if len(entry) != 3 or entry[0] != "entry-status":
            raise ValueError("invalid thread entry observation")
        entry_status = [int(word, 16) for word in entry[1:]]
        if any(value != mask | 1 for value, mask in zip(entry_status, masks)):
            raise ValueError("thread entry must have IE set and EXL/ERL clear")
    mi_masks = None
    if len(lines) == 13:
        mi = lines[11].split("\t")
        if len(mi) != 6 or mi[0] != "mi-masks":
            raise ValueError("invalid thread MI mask observation")
        mi_masks = [int(word, 16) for word in mi[1:]]
        if mi_masks != [63, 63, 63, 62, 62]:
            raise ValueError("original OS did not preserve per-thread RCP masks")
    ticks = {}
    for index, (line, name, valid) in enumerate(zip(lines[1:9], NAMES, VALID)):
        fields = line.split("\t")
        if len(fields) != 5 or fields[0] != name or fields[2] != "0x00000000" or \
                fields[3] != str(valid) or not fields[1].isdecimal() or \
                not 0 < int(fields[1]) <= 0xffffffff or \
                int(fields[4], 16) != masks[0 if index < 4 else 1]:
            raise ValueError("thread queue semantics, mask restoration or timing malformed")
        ticks[name] = int(fields[1])
    return {"wall_ticks_including_measurement_boundary": ticks,
            "entry_status": entry_status,
            "thread_mi_masks": mi_masks,
            "queue_semantics_pass": True, "interrupt_masks_restored": True,
            "exceptions": 0, "hardware_qualified": False,
            "uninterrupted_cases": ["send_lower", "recv_final", "worker_fill"],
            "scheduling_or_wait_intervals": [name for name in NAMES
                if name not in ("send_lower", "recv_final", "worker_fill")]}
