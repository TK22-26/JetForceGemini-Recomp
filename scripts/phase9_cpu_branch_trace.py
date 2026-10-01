"""Strict independent branch-slot behavior and reference Count observations."""
from itertools import product

HEADER = 'kind taken iterations slot_effects ticks'.split()


def parse_trace(path):
    lines = path.read_text().splitlines()
    if len(lines) != 30 or lines[0].split('\t') != HEADER or lines[-1] != 'result\ttrue\t28':
        raise ValueError('incomplete branch microtest')
    rows = []
    for line, expected in zip(lines[1:-1], product(range(7), range(2), (16, 128))):
        fields = line.split('\t')
        if len(fields) != 5 or not all(v.isdecimal() and int(v) <= 0xffffffff for v in fields):
            raise ValueError('malformed branch observation')
        values = tuple(map(int, fields))
        if values[:3] != expected or values[3] != (expected[2] if expected[0] == 6 or expected[1] else 0) or values[4] == 0:
            raise ValueError('incorrect branch delay-slot behavior')
        rows.append(dict(zip(HEADER, values)))
    slopes = [rows[i + 1]['ticks'] - rows[i]['ticks'] for i in range(0, 28, 2)]
    return {'cases': rows, 'delta_per_112_iterations': slopes,
            'counts_annulled_slots_at_two_ticks': slopes == [1120] * 14,
            'hardware_qualified': False}
