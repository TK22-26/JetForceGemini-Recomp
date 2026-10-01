"""Validate bounded read-only hardware startup capture from the pinned US ROM."""
from pathlib import Path

HEADER = 'event count status cause compare fcr31 mi_pending mi_mask v_sync h_sync'.split()


def parse_trace(path):
    lines = Path(path).read_text().splitlines()
    if not 7 <= len(lines) <= 71 or lines[0].split('\t') != HEADER or lines[-1] != 'result\ttrue\t120':
        raise ValueError('incomplete startup hardware capture')
    rows = []
    counts = {}
    for line in lines[1:-1]:
        values = line.split('\t')
        if len(values) != len(HEADER) or values[0] not in ('entry', 'handoff', 'os-init', 'vi-init', 'vi-init-return', 'interrupt'):
            raise ValueError('invalid startup hardware event')
        if any(len(v) != 8 or any(c not in '0123456789abcdef' for c in v) for v in values[1:]):
            raise ValueError('invalid startup hardware register')
        counts[values[0]] = counts.get(values[0], 0) + 1
        rows.append(dict(zip(HEADER, [values[0], *[int(v, 16) for v in values[1:]]])))
    if any(counts.get(k) != 1 for k in ('entry', 'handoff', 'os-init', 'vi-init', 'vi-init-return')):
        raise ValueError('startup capture must contain each single entry')
    return {'events': rows, 'hardware_qualified': False, 'gameplay_state_copied': False}
