"""Independent ERET/fallthrough Count and EXL observations, not hardware truth."""
from itertools import product

HEADER = 'kind iterations effects ticks status'.split()


def parse_trace(path):
    lines = path.read_text().splitlines()
    if len(lines) != 6 or lines[0].split('\t') != HEADER or lines[-1] != 'result\ttrue\t4':
        raise ValueError('incomplete ERET microtest')
    rows = []
    for line, expected in zip(lines[1:-1], product(range(2), (16, 128))):
        fields = line.split('\t')
        if len(fields) != 5 or not all(value.isdecimal() and int(value) <= 0xffffffff for value in fields):
            raise ValueError('invalid ERET observation')
        values = tuple(map(int, fields))
        if values[:2] != expected or values[2] != expected[1] or values[3] == 0 or \
                values[4] != (0x04000000 if expected[0] else 0x04000002):
            raise ValueError('incorrect ERET effects')
        rows.append(dict(zip(HEADER, values)))
    differences = [rows[i+1]['ticks'] - rows[i]['ticks'] for i in (0, 2)]
    return {'cases': rows, 'slopes_per_112': differences,
            'eret_zero_increment_reference': differences == [2016, 1792],
            'hardware_qualified': False}
