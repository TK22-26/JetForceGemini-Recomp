"""Independent back-to-back SI observations; no game-state injection."""
def parse_trace(path):
    lines = path.read_text().splitlines()
    header = 'case first second last_pending first_complete late_mi late_si'.split()
    if len(lines) != 34 or lines[0].split('\t') != header or lines[-1] != 'result\ttrue\t32':
        raise ValueError('incomplete SI overlap experiment')
    rows = []
    for index, line in enumerate(lines[1:-1]):
        fields = line.split('\t')
        if len(fields) != 7 or any(not f.isdecimal() or int(f) > 0xffffffff for f in fields):
            raise ValueError('invalid SI overlap row')
        row = dict(zip(header, map(int, fields)))
        if row['case'] != index or not row['first'] < row['second'] <= row['last_pending'] < row['first_complete']:
            raise ValueError('SI overlap coverage/timing mismatch')
        if not row['last_pending'] < row['first'] + 2304 <= row['first_complete'] or row['late_mi'] & 2 or row['late_si'] != 0:
            raise ValueError('SI first-deadline coalescing differs')
        rows.append(row)
    return {'cases': rows, 'hardware_qualified': False}
