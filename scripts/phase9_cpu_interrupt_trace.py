"""Strict payload/state observations for the independent SP interrupt probe."""
HEADER = 'case ticks hi lo f0 fcr31 worker payload'.split()


def parse_trace(path):
    lines = path.read_text().splitlines()
    if len(lines) != 10 or lines[0].split('\t') != HEADER or lines[-1] != 'result\ttrue\t8':
        raise ValueError('incomplete interrupt probe')
    rows = []
    for index, line in enumerate(lines[1:-1], 1):
        fields = line.split('\t')
        if len(fields) != 8 or not all(value.isdecimal() and int(value) <= 0xffffffff for value in fields):
            raise ValueError('malformed interrupt observation')
        values = tuple(map(int, fields))
        if values[0] != index or values[1] == 0 or values[2:] != (100+index, 200+index, 0x3f800000, 0x00800000, index, 1234):
            raise ValueError('interrupt did not preserve CPU state or deliver event')
        rows.append(dict(zip(HEADER, values)))
    return {'cases': rows, 'hardware_qualified': False}
