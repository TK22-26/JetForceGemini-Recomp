"""Strict independent DMA observation bounds, not installed timing constants."""


def parse_trace(path):
    lines = path.read_text().splitlines()
    if len(lines) not in (98, 130, 258, 322) or lines[0] != 'kind\tlength\tphase\tlaunch\tlast_pending\tfirst_complete' or lines[-1] != f'result\ttrue\t{len(lines) - 2}':
        raise ValueError('incomplete DMA probe')
    rows = []
    for index, line in enumerate(lines[1:-1]):
        fields = line.split('\t')
        if len(fields) != 6 or not all(v.isdecimal() and int(v) <= 0xffffffff for v in fields):
            raise ValueError('malformed DMA row')
        kind, length, phase, launch, last, first = map(int, fields)
        if (kind, length, phase) != (index // 32, (16, 64, 1024, 4096)[index // 8 % 4], index % 8):
            raise ValueError('DMA coverage differs')
        lower, upper = (last - launch) & 0xffffffff, (first - launch) & 0xffffffff
        if not 0 <= lower < upper < 1000000:
            raise ValueError('invalid DMA timing bounds')
        rows.append({'kind': kind, 'length': length, 'phase': phase,
                     'exclusive_lower': lower, 'inclusive_upper': upper})
    return {'cases': rows, 'hardware_qualified': False}
