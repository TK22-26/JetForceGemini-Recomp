"""Strict independent original VI-manager trace; startup epoch stays explicit."""
from pathlib import Path


def parse_trace(path):
    lines = Path(path).read_text().splitlines()
    if len(lines) != 26 or lines[0] != 'case\tcount\tpayload\tvi_count\ttime_hi\ttime_lo\tstatus' or lines[-1] != 'result\ttrue\t24':
        raise ValueError('incomplete original VI manager trace')
    rows = []
    for index, line in enumerate(lines[1:-1]):
        fields = line.split('\t')
        if len(fields) != 7 or any(not value.isdecimal() or int(value) > 0xffffffff for value in fields):
            raise ValueError('invalid VI manager observation')
        case, count, payload, vi_count, hi, lo, status = map(int, fields)
        if case != index or payload != 1234 or hi != 0 or status != 0x0400ff01:
            raise ValueError('unexpected VI manager state')
        rows.append(dict(case=case, count=count, payload=payload, vi_count=vi_count, time_lo=lo, status=status))
    return {'cases': rows, 'intervals': [(b['count'] - a['count']) & 0xffffffff for a, b in zip(rows, rows[1:])]}
