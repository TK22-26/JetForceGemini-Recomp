"""AI DMA observations for the named reference profile, not hardware timing."""
from itertools import product
def parse_trace(path):
    lines = path.read_text().splitlines()
    header = 'rate length phase launch initial_length initial_status last_pending first_complete final_length final_status'.split()
    columns = len(lines[0].split('\t')) if lines else 0
    if columns in (12, 16): header += ['half_count', 'half_length']
    if columns == 16: header += ['second_pending', 'second_complete', 'second_length', 'second_status']
    if len(lines) != 74 or lines[0].split('\t') != header or lines[-1] != 'result\ttrue\t72':
        raise ValueError('incomplete AI experiment')
    rows = []
    for line, expected in zip(lines[1:-1], product((1103,2209,4419),(32,128,4096),range(8))):
        fields = line.split('\t')
        if len(fields) != len(header) or any(not f.isdecimal() or int(f) > 0xffffffff for f in fields):
            raise ValueError('invalid AI observation')
        values = list(map(int, fields))
        if tuple(values[:3]) != expected or not values[3] < values[6] < values[7]:
            raise ValueError('AI coverage/timing differs')
        rows.append(dict(zip(header, values)))
    return {'cases': rows, 'hardware_qualified': False}
