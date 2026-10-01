"""Isolated Flash bus observations, not a hardware timing assertion."""
def parse_trace(path):
    lines = path.read_text().splitlines()
    header = 'phase stage launch last_pending first_complete pi_status payload'.split()
    if len(lines) != 42 or lines[0].split('\t') != header or lines[-1] != 'result\ttrue\t40':
        raise ValueError('incomplete flash probe')
    rows = []
    for i, line in enumerate(lines[1:-1]):
        fields = line.split('\t')
        if len(fields) != 7 or any(not f.isdecimal() or int(f) > 0xffffffff for f in fields[:6]):
            raise ValueError('invalid flash observation')
        values = [*map(int, fields[:6]), fields[6]]
        if values[:2] != [i // 5, i % 5] or len(fields[6]) != 256 or len(bytes.fromhex(fields[6])) != 128:
            raise ValueError('flash coverage differs')
        rows.append(dict(zip(header, values)))
    return {'cases': rows, 'hardware_qualified': False}
