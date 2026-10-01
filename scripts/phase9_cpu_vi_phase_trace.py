"""Direct CPU observations of VI phase, scanline reads and mode latching."""
from pathlib import Path
from itertools import product


def parse_trace(path):
    lines = Path(path).read_text().splitlines()
    if len(lines) != 130 or lines[0] != 'v_sync\tsample\tcount\tcurrent\tedge_count' or lines[-1] != 'result\ttrue\t128':
        raise ValueError('incomplete VI phase trace')
    rows = []
    for line, expected in zip(lines[1:-1], product((0, 525, 262, 625), range(32))):
        fields = line.split('\t')
        if len(fields) != 5 or any(not v.isdecimal() or int(v) > 0xffffffff for v in fields):
            raise ValueError('invalid VI phase record')
        values = tuple(map(int, fields))
        if values[:2] != expected:
            raise ValueError('reordered VI phase case')
        rows.append(dict(zip(('v_sync', 'sample', 'count', 'current', 'edge_count'), values)))
    return {'cases': rows, 'hardware_qualified': False}


def qualify(path):
    rows = parse_trace(path)['cases']
    edges = rows[::8]
    # Candidate independently inferred from earlier boot observations; this
    # held-out ROM must support it within the 14-tick polling interval.
    first = edges[0]['edge_count']
    # A successful LW is followed by ANDI/branch/delay/MFC0: the recorded
    # Count trails the device observation by eight ticks. The seven-op
    # retry loop supplies a 14-tick quantization window.
    if not 8 <= (first - 5000) % 500000 <= 22:
        raise ValueError('startup VI phase differs')
    previous = None
    deadline = first - (first - 5000) % 500000
    deadlines = {}
    for edge in edges:
        if previous:
            period = (previous['v_sync'] + 1) * 1500 if previous['v_sync'] else 500000
            if abs(edge['edge_count'] - previous['edge_count'] - period) > 14:
                raise ValueError('VI period latching differs')
            deadline += period
        if not 8 <= edge['edge_count'] - deadline <= 22:
            raise ValueError('VI edge leaves polling observation window')
        deadlines[edge['edge_count']] = deadline
        previous = edge
    for row in rows:
        if row['edge_count'] not in deadlines or row['count'] < row['edge_count']:
            raise ValueError('VI phase sample lacks its observed edge')
        # CPU LW precedes MFC0 by one instruction, independently of the
        # polling quantization. Check exact sampled line values.
        expected = (row['count'] - 2 - deadlines[row['edge_count']]) // 1500 & ~1
        if row['current'] != expected:
            raise ValueError('VI CPU scanline read differs')
    return {'startup_period': 500000, 'startup_phase': 5000,
            'scanline_ticks': 1500, 'field_bit': 0, 'mode_latches_at_event': True,
            'edges': len(edges), 'scanline_reads': len(rows), 'hardware_qualified': False}
